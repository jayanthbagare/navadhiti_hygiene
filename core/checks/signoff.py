"""
UAT sign-off check (A5) — repo-artifact tier.

The repo-artifact tier is the durable, high-confidence signal: signoff
files checked into source control matching a configured pattern
(default `docs/signoffs/*.md` from config/standard.yaml
`uat_signoff.artifact_pattern`). Each artifact must contain:

- a sprint identifier (`sprint_id: sprint-2026-09-05` — or any token the
  sprint calendar can resolve; a bare `date:` also maps to a sprint),
- a reviewer identity (`reviewer:` / `approved_by:`),
- a date (`date: 2026-09-04`).

Every parsed artifact becomes a `per_sprint` entry. Status rules:

- pass            : a well-formed artifact covers the current sprint
                    (method: repo_artifact).
- fail            : artifacts exist but none covers the current sprint,
                    or the current-sprint artifact is malformed
                    (method: repo_artifact); or no artifacts at all
                    (method: none — the standard is defined, the repo
                    just doesn't follow it).
- unverifiable    : GitHub API unavailable — cannot verify either way
                    (method: none).

The `email_parsed` tier (transitional, lower confidence) is a declared
fallback for repos with no artifact; the email-scanning path is NOT
built in this milestone — evidence says so explicitly rather than
pretending.

`discover_signoff_artifacts` is shared with `deploy_history.py`, which
needs the raw signoff dates to compute deploy/signoff gaps.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional

from core.checks.tree_utils import find_pattern_matches, tree_paths_for_repo
from core.github_client import GitHubApiError, GitHubClient, split_repo_id
from core.schema import UatSignoff, UatSprintSignoff
from core.sprint import SprintCalendar, normalize_sprint_id, sprint_id_matches

logger = logging.getLogger("hygiene.checks.signoff")

DEFAULT_ARTIFACT_PATTERN = "docs/signoffs/*.md"
MAX_ARTIFACT_FILES = 50

SPRINT_RE = re.compile(r"(?im)^\s*(?:[-*]\s*)?sprint(?:\s*_?\s*id)?\s*[:=]\s*(.+?)\s*$")
REVIEWER_RE = re.compile(
    r"(?im)^\s*(?:[-*]\s*)?(?:reviewer|approved[_\s-]?by|signed[_\s-]?off[_\s-]?by)\s*[:=]\s*(.+?)\s*$"
)
DATE_RE = re.compile(r"(?im)^\s*(?:[-*]\s*)?date\s*[:=]\s*(.+?)\s*$")

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d %B %Y", "%B %d, %Y")


@dataclass
class SignoffArtifact:
    path: str
    sprint_token: Optional[str] = None      # raw sprint reference from the file
    sprint_id: Optional[str] = None        # calendar-resolved sprint id (sprint-YYYY-MM-DD)
    reviewer: Optional[str] = None
    date: Optional[date] = None
    valid: bool = False
    problems: List[str] = field(default_factory=list)


def _parse_date_value(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    raw = raw.strip().strip('"\'')
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def parse_signoff_content(path: str, content: str,
                          calendar: SprintCalendar) -> SignoffArtifact:
    """Parse one signoff artifact. `valid` requires sprint + reviewer + date."""
    artifact = SignoffArtifact(path=path)

    sprint_match = SPRINT_RE.search(content)
    if sprint_match:
        artifact.sprint_token = sprint_match.group(1).strip()

    reviewer_match = REVIEWER_RE.search(content)
    if reviewer_match:
        artifact.reviewer = reviewer_match.group(1).strip()

    date_match = DATE_RE.search(content)
    artifact.date = _parse_date_value(date_match.group(1) if date_match else None)

    # Resolve the sprint: explicit token first, then the date via the calendar.
    if artifact.sprint_token:
        artifact.sprint_id = normalize_sprint_id(artifact.sprint_token)
    if artifact.sprint_id is None and artifact.date is not None:
        artifact.sprint_id = calendar.sprint_containing(artifact.date).sprint_id

    if artifact.sprint_id is None:
        artifact.problems.append("no sprint identifier that the sprint calendar can resolve")
    if not artifact.reviewer:
        artifact.problems.append("no reviewer identity field (reviewer:/approved_by:)")
    if artifact.date is None:
        artifact.problems.append("no parseable date field (date:)")

    artifact.valid = not artifact.problems
    return artifact


def discover_signoff_artifacts(repo_id: str, github: Optional[GitHubClient],
                                standard: dict, calendar: SprintCalendar,
                                default_branch: str = "main") -> Optional[List[SignoffArtifact]]:
    """
    Find and parse all signoff artifacts. Returns None when the tree is
    unreachable (API failure) — distinct from [] (pattern configured,
    repo has no artifacts).
    """
    if github is None or not github.authenticated:
        return None
    owner, repo = split_repo_id(repo_id)
    branch = default_branch or "main"
    pattern = (standard or {}).get("uat_signoff", {}).get("artifact_pattern",
                                                          DEFAULT_ARTIFACT_PATTERN)

    try:
        paths = tree_paths_for_repo(github, owner, repo, branch)
    except GitHubApiError as exc:
        logger.warning("Signoff artifact discovery API failure for %s: %s", repo_id, exc)
        return None

    matching = find_pattern_matches(paths, pattern)
    if len(matching) > MAX_ARTIFACT_FILES:
        logger.warning(
            "%s: %d signoff artifact files match '%s'; parsing first %d",
            repo_id, len(matching), pattern, MAX_ARTIFACT_FILES,
        )
        matching = matching[:MAX_ARTIFACT_FILES]

    artifacts: List[SignoffArtifact] = []
    for path in matching:
        try:
            content = github.get_file_content(owner, repo, branch, path)
        except GitHubApiError as exc:
            logger.warning("Failed fetching signoff artifact %s/%s: %s", repo_id, path, exc)
            artifacts.append(SignoffArtifact(path=path, problems=[f"unreadable: {exc}"]))
            continue
        if content is None:
            artifacts.append(SignoffArtifact(path=path, problems=["file listed in tree but not fetchable"]))
            continue
        artifacts.append(parse_signoff_content(path, content, calendar))
    return artifacts


def check_uat_signoff(repo_id: str, github: Optional[GitHubClient], standard: dict,
                      calendar: SprintCalendar, default_branch: str = "main",
                      now: Optional[datetime] = None) -> UatSignoff:
    artifacts = discover_signoff_artifacts(repo_id, github, standard, calendar, default_branch)
    return build_uat_signoff(repo_id, artifacts, standard, calendar, now=now)


def build_uat_signoff(repo_id: str, artifacts: Optional[List[SignoffArtifact]],
                      standard: dict, calendar: SprintCalendar,
                      now: Optional[datetime] = None) -> UatSignoff:
    pattern = (standard or {}).get("uat_signoff", {}).get("artifact_pattern",
                                                          DEFAULT_ARTIFACT_PATTERN)
    current_sprint = calendar.current_sprint(now)

    if artifacts is None:
        return UatSignoff(
            status="unverifiable",
            method="none",
            evidence=["GitHub API unavailable — could not search for signoff artifacts"],
        )

    # per_sprint entries, newest first
    per_sprint: List[UatSprintSignoff] = []
    for artifact in artifacts:
        if artifact.sprint_id is None and not artifact.sprint_token:
            sprint_id = "unresolved"
        elif artifact.sprint_id is not None:
            sprint_id = artifact.sprint_id
        else:
            sprint_id = artifact.sprint_token or "unresolved"
        entry = UatSprintSignoff(
            sprint_id=sprint_id,
            status="pass" if artifact.valid else "unverifiable",
            evidence=[f"artifact '{artifact.path}'"
                      + (f", reviewer: {artifact.reviewer}" if artifact.reviewer else "")
                      + (f", date: {artifact.date.isoformat()}" if artifact.date else "")
                      + (f" — {', '.join(artifact.problems)}" if artifact.problems else "")],
        )
        per_sprint.append(entry)
    per_sprint.sort(key=lambda e: e.sprint_id, reverse=True)
    del per_sprint[12:]  # keep the report bounded; artifacts themselves stay counted below

    if not artifacts:
        return UatSignoff(
            status="fail",
            method="none",
            evidence=[
                f"No UAT signoff artifacts found matching '{pattern}' — "
                "expected e.g. docs/signoffs/sprint-<date>.md with sprint id, "
                "reviewer, and date",
                "No repo artifact found; email-parsed fallback not implemented yet "
                "(transitional tier, not built in this milestone)",
            ],
            per_sprint=[],
        )

    evidence = [f"{len(artifacts)} signoff artifact(s) found matching '{pattern}'"]
    current = [a for a in artifacts if a.sprint_id and sprint_id_matches(a.sprint_id, current_sprint)]
    # A bare-date sprint token resolves via calendar already; also accept
    # artifacts whose date falls in the current sprint even if the token didn't.
    if not current:
        current = [a for a in artifacts if a.date and current_sprint.contains(a.date)]

    if current:
        artifact = current[0]
        if artifact.valid:
            evidence.append(
                f"Current sprint {current_sprint.sprint_id} covered by '{artifact.path}' "
                f"(reviewer: {artifact.reviewer}, date: {artifact.date.isoformat()})"
            )
            return UatSignoff(status="pass", method="repo_artifact",
                              evidence=evidence, per_sprint=per_sprint)
        evidence.append(
            f"Current-sprint artifact '{artifact.path}' is malformed: "
            + "; ".join(artifact.problems)
        )
        return UatSignoff(status="fail", method="repo_artifact",
                          evidence=evidence, per_sprint=per_sprint)

    latest = max(artifacts, key=lambda a: (a.date or date.min), default=None)
    latest_desc = (
        f"latest covers {latest.sprint_id or 'an unresolved sprint'}"
        if latest else "none parse cleanly"
    )
    evidence.append(
        f"No signoff artifact covers the current sprint {current_sprint.sprint_id} "
        f"({latest_desc})"
    )
    return UatSignoff(status="fail", method="repo_artifact",
                      evidence=evidence, per_sprint=per_sprint)
