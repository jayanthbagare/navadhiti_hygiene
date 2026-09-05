"""
Thin GitHub REST API client shared by all deterministic checks.

Design goals:
- One authenticated session, one optional token (GIT_TOKEN env var).
- The recursive git-tree call is cached per repo so multiple checks
  (environment separation, security baseline, UAT signoff artifact
  discovery) share a single API round-trip per run.
- API failures raise GitHubApiError; callers (checks) are expected to
  degrade to `undefined_standard`/`unverifiable` with evidence rather
  than crash the whole run over one inaccessible repo.
"""

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests


class GitHubApiError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class GitHubResponse:
    status_code: int
    body: Any
    headers: Dict[str, str]

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


def parse_github_timestamp(value: Optional[str]) -> Optional[datetime]:
    """GitHub returns ISO-8601 UTC timestamps like '2026-09-01T12:34:56Z'."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


class GitHubClient:
    def __init__(self, api_url: str = "https://api.github.com", token: Optional[str] = None):
        self.api_url = api_url.rstrip("/")
        self.token = token or os.getenv("GIT_TOKEN")
        self._session = requests.Session()
        if self.token:
            self._session.headers.update({
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
            })
        self._session.headers.update({"X-GitHub-Api-Version": "2022-11-28"})
        self._tree_cache: Dict[str, Optional[dict]] = {}

    @classmethod
    def from_config(cls, git_provider_config: dict) -> "GitHubClient":
        return cls(
            api_url=git_provider_config.get("api_url", "https://api.github.com"),
            token=os.getenv("GIT_TOKEN"),
        )

    @property
    def authenticated(self) -> bool:
        return bool(self.token)

    # ------------------------------------------------------------------
    # Low-level request helpers
    # ------------------------------------------------------------------

    def request(self, method: str, path: str, **kwargs) -> GitHubResponse:
        url = path if path.startswith("http") else f"{self.api_url}{path}"
        try:
            resp = self._session.request(method, url, timeout=30, **kwargs)
        except requests.RequestException as exc:
            raise GitHubApiError(f"GitHub API request failed ({url}): {exc}") from exc

        if resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0":
            raise GitHubApiError(
                "GitHub API rate limit exhausted; set GIT_TOKEN to raise the limit",
                status_code=403,
            )
        try:
            body = resp.json()
        except ValueError:
            body = resp.text
        return GitHubResponse(resp.status_code, body, dict(resp.headers))

    def get(self, path: str, **kwargs) -> GitHubResponse:
        return self.request("GET", path, **kwargs)

    def get_json(self, path: str, **kwargs) -> Any:
        resp = self.get(path, **kwargs)
        if not resp.ok:
            raise GitHubApiError(
                f"GitHub API error {resp.status_code} for {path}: {resp.body}", resp.status_code
            )
        return resp.body

    def get_json_or_none(self, path: str, statuses_ok: tuple = (200,), **kwargs) -> Optional[Any]:
        """Fetch JSON; return None on 404, raise on other errors."""
        resp = self.get(path, **kwargs)
        if resp.status_code == 404:
            return None
        if not resp.ok:
            raise GitHubApiError(
                f"GitHub API error {resp.status_code} for {path}: {resp.body}", resp.status_code
            )
        return resp.body

    # ------------------------------------------------------------------
    # Repo-level helpers
    # ------------------------------------------------------------------

    def get_repo(self, owner: str, repo: str) -> dict:
        return self.get_json(f"/repos/{owner}/{repo}")

    def list_org_repos(self, org: str) -> List[dict]:
        """All repos in an org, following pagination (per_page=100)."""
        repos: List[dict] = []
        page = 1
        while True:
            batch = self.get_json(f"/orgs/{org}/repos", params={"per_page": 100, "page": page})
            if not batch:
                break
            repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return repos

    def get_tree(self, owner: str, repo: str, branch: str) -> Optional[dict]:
        """
        Recursive git tree for `branch`. Cached per (owner, repo, branch) so
        multiple checks share one round-trip. A 404 (repo/branch missing or
        no access) is an API failure for callers: they cannot distinguish
        "absent artifact" from "unreadable tree", so they degrade instead
        of scoring a fail.
        """
        key = f"{owner}/{repo}@{branch}"
        if key in self._tree_cache:
            return self._tree_cache[key]
        resp = self.get(f"/repos/{owner}/{repo}/git/trees/{branch}",
                        params={"recursive": "1"})
        if resp.status_code == 404:
            raise GitHubApiError(
                f"Git tree not found for {owner}/{repo}@{branch} "
                "(repo, branch, or access missing)", 404,
            )
        if not resp.ok:
            raise GitHubApiError(
                f"GitHub API error {resp.status_code} fetching tree for "
                f"{owner}/{repo}@{branch}: {resp.body}", resp.status_code,
            )
        self._tree_cache[key] = resp.body
        return resp.body

    def get_tree_paths(self, owner: str, repo: str, branch: str) -> List[str]:
        """Flat list of blob file paths on the branch (empty list if tree missing)."""
        tree = self.get_tree(owner, repo, branch) or {}
        paths = []
        for entry in tree.get("tree", []):
            if entry.get("type") == "blob" and entry.get("path"):
                paths.append(entry["path"])
        return paths

    def tree_truncated(self, owner: str, repo: str, branch: str) -> bool:
        tree = self.get_tree(owner, repo, branch) or {}
        return bool(tree.get("truncated", False))

    def get_file_content(self, owner: str, repo: str, branch: str, path: str) -> Optional[str]:
        """Raw file content via the contents API; None on 404."""
        resp = self.request(
            "GET",
            f"/repos/{owner}/{repo}/contents/{path}",
            params={"ref": branch},
            headers={"Accept": "application/vnd.github.raw"},
        )
        if resp.status_code == 404:
            return None
        if not resp.ok:
            raise GitHubApiError(
                f"GitHub API error {resp.status_code} fetching {path}: {resp.body}",
                resp.status_code,
            )
        return resp.body if isinstance(resp.body, str) else str(resp.body)

    def get_branch_protection(self, owner: str, repo: str, branch: str) -> Optional[dict]:
        """
        Branch protection settings. Returns:
        - dict on 200 (protection exists)
        - None on 404 (branch exists but is not protected, or repo/branch missing)
        Raises GitHubApiError on 403 (token lacks admin read) and other errors.
        """
        resp = self.get(f"/repos/{owner}/{repo}/branches/{branch}/protection")
        if resp.status_code == 200:
            return resp.body
        if resp.status_code == 404:
            return None
        raise GitHubApiError(
            f"GitHub API error {resp.status_code} reading branch protection for "
            f"{owner}/{repo}@{branch} (token may lack administration read scope): {resp.body}",
            resp.status_code,
        )

    def list_merged_pulls(self, owner: str, repo: str, since: datetime,
                          base_branch: Optional[str] = None, max_pages: int = 10) -> List[dict]:
        """
        Merged PRs with merged_at >= `since`. Walks closed PRs newest-first
        by updated_at and stops once a page is entirely older than `since`
        (updated_at >= merged_at always, so this is a safe cutoff).
        """
        results: List[dict] = []
        for page in range(1, max_pages + 1):
            batch = self.get_json(
                f"/repos/{owner}/{repo}/pulls",
                params={"state": "closed", "sort": "updated", "direction": "desc",
                        "per_page": 100, "page": page},
            )
            if not batch:
                break
            for pr in batch:
                merged_at = parse_github_timestamp(pr.get("merged_at"))
                if merged_at and merged_at >= since:
                    if base_branch and pr.get("base", {}).get("ref") != base_branch:
                        continue
                    results.append(pr)
            oldest_updated = parse_github_timestamp(batch[-1].get("updated_at"))
            if oldest_updated and oldest_updated < since:
                break
        return results

    def list_branch_commits(self, owner: str, repo: str, branch: str,
                             since: datetime, max_pages: int = 5) -> List[dict]:
        """Commits on `branch` since `since`, newest-first."""
        commits: List[dict] = []
        for page in range(1, max_pages + 1):
            batch = self.get_json(
                f"/repos/{owner}/{repo}/commits",
                params={"sha": branch, "since": since.isoformat() + "Z",
                        "per_page": 100, "page": page},
            )
            if not batch:
                break
            commits.extend(batch)
            if len(batch) < 100:
                break
        return commits

    def list_closed_issues(self, owner: str, repo: str, since: datetime,
                           max_pages: int = 10) -> List[dict]:
        """
        Issues (not PRs) closed at/after `since`. The issues list endpoint
        also returns PRs; those are filtered out via the `pull_request` key.
        """
        results: List[dict] = []
        for page in range(1, max_pages + 1):
            batch = self.get_json(
                f"/repos/{owner}/{repo}/issues",
                params={"state": "closed", "sort": "updated", "direction": "desc",
                        "per_page": 100, "page": page},
            )
            if not batch:
                break
            for issue in batch:
                if "pull_request" in issue:
                    continue
                closed_at = parse_github_timestamp(issue.get("closed_at"))
                if closed_at and closed_at >= since:
                    results.append(issue)
            oldest_updated = parse_github_timestamp(batch[-1].get("updated_at"))
            if oldest_updated and oldest_updated < since:
                break
        return results

    def get_issue(self, owner: str, repo: str, number: int) -> Optional[dict]:
        return self.get_json_or_none(f"/repos/{owner}/{repo}/issues/{number}")

    def get_pull_files(self, owner: str, repo: str, number: int) -> List[dict]:
        return self.get_json(f"/repos/{owner}/{repo}/pulls/{number}/files",
                             params={"per_page": 100})

    def list_releases(self, owner: str, repo: str, per_page: int = 30) -> List[dict]:
        return self.get_json(f"/repos/{owner}/{repo}/releases", params={"per_page": per_page})

    def list_tags(self, owner: str, repo: str, per_page: int = 100) -> List[dict]:
        return self.get_json(f"/repos/{owner}/{repo}/tags", params={"per_page": per_page})

    def get_commit(self, owner: str, repo: str, sha: str) -> Optional[dict]:
        return self.get_json_or_none(f"/repos/{owner}/{repo}/commits/{sha}")


def split_repo_id(repo_id: str) -> tuple:
    """'owner/repo' -> ('owner', 'repo'). Raises ValueError on malformed ids."""
    parts = repo_id.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Expected repo id in 'owner/repo' form, got: {repo_id!r}")
    return parts[0], parts[1]
