"""
Deployment history & gap flag check (B3).

`last_deploy` comes from a real system of record, not commit history:
- GitHub Releases API (`GET /repos/{owner}/{repo}/releases`) — latest
  published, non-draft, non-prerelease release. Default source.
- Deployment tags matching `deployment_history.tag_pattern` in
  config/standard.yaml (e.g. `^prod-` or `^v\\d+\\.\\d+\\.\\d+$`) —
  newest matching tag's commit date. Used when the repo has no
  releases, or when `deployment_history.deploy_marker: tags`.

If neither exists for a repo, the dimension reports
`status: undefined_standard` — never a guess from commit history.

Gap flag (deploy without verified preceding signoff):
    gap_flag = last_deploy exists AND no signoff artifact is dated in
    [start of the sprint containing the deploy, deploy]

A signoff dated after the deploy does not clear the gap — deploying
before signoff is exactly what this flag exists to catch. If signoff
artifacts could not be fetched (API failure), the dimension degrades to
`undefined_standard` rather than accusing the repo of a gap it cannot
prove.
"""

import logging
import re
from datetime import datetime
from typing import List, Optional

from core.checks.signoff import SignoffArtifact
from core.github_client import GitHubApiError, GitHubClient, parse_github_timestamp, split_repo_id
from core.schema import DeploymentHistory
from core.sprint import SprintCalendar

logger = logging.getLogger("hygiene.checks.deploy_history")

MAX_TAG_COMMITS = 20


def _latest_release_deploy(github: GitHubClient, owner: str, repo: str) -> Optional[datetime]:
    releases = github.list_releases(owner, repo)
    for release in releases:
        if release.get("draft") or release.get("prerelease"):
            continue
        published = parse_github_timestamp(release.get("published_at"))
        if published:
            return published
    return None


def _latest_tag_deploy(github: GitHubClient, owner: str, repo: str,
                       pattern: Optional[str]) -> Optional[datetime]:
    if not pattern:
        return None
    compiled = re.compile(pattern)
    try:
        tags = github.list_tags(owner, repo)
    except GitHubApiError:
        return None
    matching = [t for t in tags if compiled.match(t.get("name") or "")]
    latest: Optional[datetime] = None
    checked = 0
    for tag in matching:
        if checked >= MAX_TAG_COMMITS:
            break
        sha = (tag.get("commit") or {}).get("sha")
        if not sha:
            continue
        checked += 1
        try:
            commit = github.get_commit(owner, repo, sha) or {}
        except GitHubApiError:
            continue
        commit_info = (commit.get("commit") or {}).get("committer") or {}
        ts = parse_github_timestamp(commit_info.get("date"))
        if ts and (latest is None or ts > latest):
            latest = ts
    return latest


def check_deploy_history(repo_id: str, github: Optional[GitHubClient], standard: dict,
                         signoff_artifacts: Optional[List[SignoffArtifact]],
                         calendar: SprintCalendar,
                         default_branch: str = "main") -> DeploymentHistory:
    deploy_cfg = (standard or {}).get("deployment_history", {}) or {}
    marker = deploy_cfg.get("deploy_marker", "releases")
    tag_pattern = deploy_cfg.get("tag_pattern")

    if github is None or not github.authenticated:
        return DeploymentHistory(
            status="undefined_standard",
            evidence=["GitHub API unavailable (GIT_TOKEN not set) — cannot determine last deploy"],
        )

    owner, repo = split_repo_id(repo_id)
    evidence: List[str] = []
    last_deploy: Optional[datetime] = None
    method = "none"

    try:
        if marker == "tags" and tag_pattern:
            last_deploy = _latest_tag_deploy(github, owner, repo, tag_pattern)
            if last_deploy:
                method = "tags"
                evidence.append(
                    f"Last deploy from newest tag matching '{tag_pattern}' at {last_deploy.isoformat()}"
                )
        else:
            last_deploy = _latest_release_deploy(github, owner, repo)
            if last_deploy:
                method = "releases"
                evidence.append(f"Last deploy from latest published GitHub release at {last_deploy.isoformat()}")
            elif tag_pattern:
                tag_deploy = _latest_tag_deploy(github, owner, repo, tag_pattern)
                if tag_deploy:
                    last_deploy = tag_deploy
                    method = "tags"
                    evidence.append(
                        f"No releases found; last deploy from newest tag matching '{tag_pattern}' "
                        f"at {last_deploy.isoformat()}"
                    )
    except GitHubApiError as exc:
        logger.warning("Deploy history API failure for %s: %s", repo_id, exc)
        return DeploymentHistory(
            status="undefined_standard",
            evidence=[f"GitHub API unavailable while reading deploy history: {exc}"],
        )

    if last_deploy is None:
        return DeploymentHistory(
            status="undefined_standard",
            method="none",
            evidence=[
                "No deployment evidence found: no published GitHub releases"
                + (f" and no tags matching '{tag_pattern}'" if tag_pattern else " (tag_pattern not configured)"),
                "Reporting undefined_standard rather than guessing a deploy date from commit history",
            ],
        )

    # --- Signoff side --------------------------------------------------
    if signoff_artifacts is None:
        return DeploymentHistory(
            status="undefined_standard",
            method=method,
            last_deploy=last_deploy,
            gap_flag=False,
            evidence=evidence + [
                "Signoff artifacts could not be fetched — cannot verify whether the deploy "
                "had a preceding UAT signoff; not raising a gap flag on unverifiable data"
            ],
        )

    deploy_sprint = calendar.sprint_for_datetime(last_deploy)
    prior_signoffs = [
        a for a in signoff_artifacts
        if a.valid and a.date is not None
        and deploy_sprint.start <= a.date <= last_deploy.date()
    ]
    before_deploy = [
        a for a in signoff_artifacts
        if a.valid and a.date is not None and a.date <= last_deploy.date()
    ]
    if prior_signoffs:
        latest = max(prior_signoffs, key=lambda a: a.date)
        evidence.append(
            f"Deploy on {last_deploy.date().isoformat()} covered by signoff '{latest.path}' "
            f"dated {latest.date.isoformat()} (sprint window {deploy_sprint.sprint_id}: "
            f"{deploy_sprint.start.isoformat()}..{deploy_sprint.end.isoformat()})"
        )
        last_signoff = latest.date
    else:
        last_signoff = (
            max(before_deploy, key=lambda a: a.date).date if before_deploy else None
        )
        if last_signoff:
            evidence.append(
                f"Newest signoff before deploy is dated {last_signoff.isoformat()} "
                f"('{max(before_deploy, key=lambda a: a.date).path}') — before the sprint "
                f"window containing the deploy ({deploy_sprint.sprint_id}); no signoff covers "
                "this deploy"
            )
        else:
            evidence.append(
                f"No UAT signoff artifact precedes the deploy on {last_deploy.date().isoformat()} "
                f"(sprint window {deploy_sprint.sprint_id}: "
                f"{deploy_sprint.start.isoformat()}..{deploy_sprint.end.isoformat()})"
            )

    gap = not prior_signoffs
    status = "pass" if not gap else "fail"
    if gap:
        evidence.append(
            "gap_flag: deploy to production occurred without a verified preceding UAT signoff "
            "in its sprint window"
        )

    return DeploymentHistory(
        status=status,
        method=method,
        last_deploy=last_deploy,
        last_signoff_before_deploy=(
            datetime.combine(last_signoff, datetime.min.time()) if last_signoff else None
        ),
        gap_flag=gap,
        evidence=evidence,
    )
