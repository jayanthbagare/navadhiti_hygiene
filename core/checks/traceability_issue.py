"""
Feature-to-issue traceability check (C2).

For merged PRs into the default branch within the current sprint window:

- `pass` (method: pr_linked): every merged PR links to a GitHub issue
  that actually exists — via a linking keyword in the title/body
  (`Closes #N`, `Fixes #N`, `Resolves #N`) or an explicit issue URL.
  A referenced issue that does not exist (404) does NOT count as a link.
- spec-kit route: if `config/standard.yaml` declares
  `traceability.spec_directory` (e.g. `specs/`), a PR that changes a spec
  file under that directory is accepted as linked when the spec file
  itself names/links its governing issue — equivalent evidence per
  spec-kit convention.
- commit-linked fallback (method: commit_linked): a PR whose title/body
  lack a reference still counts as linked when its merge commit message
  carries a linking keyword (`Closes #N`-style; the common squash-merge
  `(#N)` PR suffix is deliberately NOT treated as an issue link).
- `unlinked_count` / `total_checked` count merged PRs without/with
  evaluation. `fail` if any unlinked, `pass` if zero.
- `undefined_standard` when there is no PR history to evaluate. A repo
  with only direct-to-main commits is flagged as worth investigating in
  the evidence.
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from core.github_client import GitHubApiError, GitHubClient, parse_github_timestamp, split_repo_id
from core.schema import FeatureIssueTrace
from core.sprint import SprintCalendar

logger = logging.getLogger("hygiene.checks.traceability_issue")

ISSUE_KEYWORD_RE = re.compile(
    r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)"
)
ISSUE_URL_RE = re.compile(
    r"(?i)https?://(?:www\.)?github\.com/[^/\s]+/[^/\s]+/issues/(\d+)"
)

MAX_ISSUES_TO_VERIFY = 50
MAX_SPEC_FILES_TO_READ = 2
MAX_PRS_DETAILED_IN_EVIDENCE = 10


def _extract_issue_refs(text: str) -> List[int]:
    """Distinct issue numbers referenced with a linking keyword or URL."""
    refs: List[int] = []
    seen: Set[int] = set()
    for match in list(ISSUE_KEYWORD_RE.finditer(text or "")) + list(ISSUE_URL_RE.finditer(text or "")):
        num = int(match.group(1))
        if num not in seen:
            seen.add(num)
            refs.append(num)
    return refs


def _issue_exists(github: GitHubClient, owner: str, repo: str,
                  issue_number: int, cache: Dict[int, bool]) -> bool:
    if issue_number in cache:
        return cache[issue_number]
    try:
        issue = github.get_issue(owner, repo, issue_number)
        exists = issue is not None
    except GitHubApiError as exc:
        logger.warning("Could not verify issue #%s for link check: %s", issue_number, exc)
        exists = True  # API failure: don't punish the PR for a verification outage
    cache[issue_number] = exists
    return exists


def _spec_file_link(github: GitHubClient, owner: str, repo: str, branch: str,
                    spec_directory: str, pr_number: int,
                    issue_cache: Dict[int, bool]) -> Tuple[bool, Optional[str]]:
    """
    spec-kit route: the PR changes a spec file under spec_directory and
    that spec file names/links its governing issue.
    """
    try:
        files = github.get_pull_files(owner, repo, pr_number)
    except GitHubApiError as exc:
        logger.warning("Could not list files for PR #%s: %s", pr_number, exc)
        return False, None
    spec_files = [f.get("filename") for f in files
                  if (f.get("filename") or "").startswith(spec_directory.strip("/") + "/")]
    for filename in spec_files[:MAX_SPEC_FILES_TO_READ]:
        try:
            content = github.get_file_content(owner, repo, branch, filename)
        except GitHubApiError as exc:
            logger.warning("Could not read spec file %s: %s", filename, exc)
            continue
        if content is None:
            continue
        refs = _extract_issue_refs(content)
        for ref in refs[:MAX_ISSUES_TO_VERIFY]:
            if _issue_exists(github, owner, repo, ref, issue_cache):
                return True, f"spec file '{filename}' names issue #{ref}"
    return False, None


def _merge_commit_link(github: GitHubClient, owner: str, repo: str, pr: dict,
                       issue_cache: Dict[int, bool]) -> Tuple[bool, Optional[str]]:
    """commit-linked fallback: merge commit message carries a linking keyword."""
    sha = pr.get("merge_commit_sha")
    if not sha:
        return False, None
    try:
        commit = github.get_commit(owner, repo, sha) or {}
    except GitHubApiError as exc:
        logger.warning("Could not fetch merge commit %s: %s", sha, exc)
        return False, None
    message = ((commit.get("commit") or {}).get("message")) or ""
    for ref in _extract_issue_refs(message)[:MAX_ISSUES_TO_VERIFY]:
        if _issue_exists(github, owner, repo, ref, issue_cache):
            return True, f"merge commit message references issue #{ref}"
    return False, None


def check_feature_issue_trace(repo_id: str, github: Optional[GitHubClient],
                               standard: dict, calendar: SprintCalendar,
                               default_branch: str = "main",
                               now: Optional[datetime] = None) -> FeatureIssueTrace:
    trace_cfg = (standard or {}).get("traceability", {}) or {}
    spec_directory = trace_cfg.get("spec_directory")

    if github is None or not github.authenticated:
        return FeatureIssueTrace(
            status="undefined_standard",
            evidence=["GitHub API unavailable (GIT_TOKEN not set) — cannot evaluate feature-to-issue traceability"],
        )

    owner, repo = split_repo_id(repo_id)
    branch = default_branch or "main"
    sprint = calendar.current_sprint(now)
    since = sprint.window_start()

    try:
        merged_prs = github.list_merged_pulls(owner, repo, since, base_branch=branch)
    except GitHubApiError as exc:
        logger.warning("Feature-to-issue check API failure for %s: %s", repo_id, exc)
        return FeatureIssueTrace(
            status="undefined_standard",
            evidence=[f"GitHub API unavailable while listing merged PRs: {exc}"],
        )

    if not merged_prs:
        # No PR history to evaluate — distinguish direct-to-main activity
        # from a genuinely quiet repo; flag direct-to-main as suspicious.
        try:
            commits = github.list_branch_commits(owner, repo, branch, since)
        except GitHubApiError:
            commits = None
        if commits:
            return FeatureIssueTrace(
                status="undefined_standard",
                method="none",
                evidence=[
                    f"No merged PRs into '{branch}' in sprint window {sprint.sprint_id} "
                    f"({sprint.start.isoformat()}..{sprint.end.isoformat()}); "
                    f"{len(commits)} direct commit(s) to the default branch instead — "
                    "direct-to-main workflow; worth investigating (no PR-based traceability "
                    "standard is defined for this case yet)"
                ],
            )
        return FeatureIssueTrace(
            status="undefined_standard",
            method="none",
            evidence=[
                f"No merged PRs and no commits in sprint window {sprint.sprint_id} "
                f"({sprint.start.isoformat()}..{sprint.end.isoformat()}) — nothing to evaluate"
            ],
        )

    issue_cache: Dict[int, bool] = {}
    unlinked: List[int] = []
    evidence: List[str] = []
    linked_via_commit_msg = 0
    linked_via_spec = 0

    merged_prs.sort(key=lambda p: parse_github_timestamp(p.get("merged_at")) or since, reverse=True)
    for pr in merged_prs:
        number = pr.get("number")
        title_body = f"{pr.get('title') or ''}\n{pr.get('body') or ''}"
        linked = False
        how = None

        refs = _extract_issue_refs(title_body)
        for ref in refs[:MAX_ISSUES_TO_VERIFY]:
            if _issue_exists(github, owner, repo, ref, issue_cache):
                linked = True
                how = f"linked to issue #{ref}" + (
                    "" if len(refs) == 1 else f" (of {len(refs)} referenced)"
                )
                break
        if not linked and refs:
            evidence_detail = f"references issue(s) {refs} that do not exist in the repo"
        else:
            evidence_detail = "no issue reference (keyword 'Closes #N' / 'Fixes #N' / 'Resolves #N' or issue URL)"

        if not linked and spec_directory:
            linked, spec_note = _spec_file_link(github, owner, repo, branch,
                                                spec_directory, number, issue_cache)
            if linked:
                linked_via_spec += 1
                how = spec_note

        if not linked:
            linked, commit_note = _merge_commit_link(github, owner, repo, pr, issue_cache)
            if linked:
                linked_via_commit_msg += 1
                how = commit_note

        if len(evidence) < MAX_PRS_DETAILED_IN_EVIDENCE:
            if linked:
                evidence.append(f"PR #{number}: {how}")
            else:
                evidence.append(f"PR #{number}: UNLINKED — {evidence_detail}")

        if not linked:
            unlinked.append(number)

    total_linked = len(merged_prs) - len(unlinked)
    # Every link found came from merge-commit messages rather than PR text
    # -> commit_linked tier; otherwise the evidence route was PR-based.
    if linked_via_commit_msg > 0 and linked_via_commit_msg == total_linked:
        method = "commit_linked"
    else:
        method = "pr_linked"

    summary = (f"{len(merged_prs) - len(unlinked)}/{len(merged_prs)} merged PR(s) into '{branch}' "
               f"in sprint {sprint.sprint_id} traced to a GitHub issue")
    if unlinked:
        evidence.append(
            f"UNLINKED PRs in sprint {sprint.sprint_id}: #{', #'.join(str(n) for n in unlinked)}"
        )
    if linked_via_spec:
        evidence.append(f"{linked_via_spec} link(s) established via spec files under '{spec_directory}'")
    if linked_via_commit_msg:
        evidence.append(f"{linked_via_commit_msg} link(s) established via merge commit messages")
    if len(merged_prs) > MAX_PRS_DETAILED_IN_EVIDENCE:
        evidence.append(f"(evidence shows first {MAX_PRS_DETAILED_IN_EVIDENCE} PRs; "
                        f"{len(merged_prs)} evaluated in total)")
    evidence.append(summary)

    return FeatureIssueTrace(
        status="fail" if unlinked else "pass",
        method=method,
        evidence=evidence,
        unlinked_count=len(unlinked),
        total_checked=len(merged_prs),
    )
