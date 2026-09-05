"""
Issue-to-ticket traceability check (C3).

Only runs when `config/integrations.yaml` declares a `ticketing_system`
(analogous to `timesheet_system`). If none is configured, the check
emits `undefined_standard` — repos are never failed for a standard the
org has not defined yet, consistent with how every other dimension
treats undefined standards.

Where configured: for issues closed within the current sprint window,
look for an external ticket reference in the issue body (regex from
`config/standard.yaml` `traceability.ticket_ref_pattern`, e.g.
`[A-Z]+-\d+` for Jira keys) or in a label with a configured prefix
(`traceability.ticket_label_prefix`, e.g. `ticket:`).

Optional best-effort existence verification: when the ticketing system
exposes an API (api_url + token env var, e.g. TICKETING_TOKEN), each
referenced ticket is checked with a Jira-shaped REST call
(`GET {api_url}/issue/{key}`). A 404 marks the issue unlinked — a stale
or typo'd reference is not a link. If the ticket API fails, the check
falls back to pattern-match only and notes the degraded confidence in
evidence; an API outage never fails the whole check.

Scoring shape matches C2: `unlinked_count` / `total_checked`, `fail` if
any unlinked, `pass` if zero, `undefined_standard` if no issues were
closed in the window to evaluate.
"""

import logging
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

from core.github_client import GitHubApiError, GitHubClient, split_repo_id
from core.schema import IssueTicketTrace
from core.sprint import SprintCalendar

logger = logging.getLogger("hygiene.checks.traceability_ticket")

DEFAULT_TICKET_REF_PATTERN = r"[A-Z][A-Z0-9]*-\d+"
MAX_TICKETS_TO_VERIFY = 50
MAX_ISSUES_DETAILED_IN_EVIDENCE = 10


def _extract_ticket_ref(issue: dict, ref_pattern: re.Pattern,
                         label_prefix: Optional[str]) -> Optional[str]:
    """First ticket reference found: body regex, then a matching label."""
    body = issue.get("body") or ""
    match = ref_pattern.search(body)
    if match:
        return match.group(0)
    if label_prefix:
        for label in issue.get("labels") or []:
            name = label.get("name") if isinstance(label, dict) else str(label)
            if name and name.lower().startswith(label_prefix.lower()):
                ref = name[len(label_prefix):].strip()
                if ref:
                    return ref
    return None


def _verify_ticket_exists(api_url: str, token: str, ticket_ref: str,
                          timeout: int = 15) -> Optional[bool]:
    """
    Best-effort Jira-shaped verification: GET {api_url}/issue/{key}.
    True/False = verified exists/missing; None = API unreachable
    (caller degrades to pattern-match only).
    """
    url = f"{api_url.rstrip('/')}/issue/{ticket_ref}"
    try:
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"},
                            timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("Ticket API unreachable (%s): %s", url, exc)
        return None
    if resp.status_code == 200:
        return True
    if resp.status_code == 404:
        return False
    logger.warning("Ticket API error %s for %s — falling back to pattern match",
                   resp.status_code, ticket_ref)
    return None


def check_issue_ticket_trace(repo_id: str, github: Optional[GitHubClient],
                              standard: dict, integrations: dict,
                              calendar: SprintCalendar,
                              default_branch: str = "main",
                              now: Optional[datetime] = None) -> IssueTicketTrace:
    ticketing = (integrations or {}).get("ticketing_system")
    if not ticketing:
        return IssueTicketTrace(
            status="undefined_standard",
            evidence=[
                "No ticketing integration configured in config/integrations.yaml "
                "(add a ticketing_system section) — issue-to-ticket traceability "
                "standard is not yet defined org-wide"
            ],
        )

    trace_cfg = (standard or {}).get("traceability", {}) or {}
    ref_pattern = re.compile(trace_cfg.get("ticket_ref_pattern", DEFAULT_TICKET_REF_PATTERN))
    label_prefix = trace_cfg.get("ticket_label_prefix")

    if github is None or not github.authenticated:
        return IssueTicketTrace(
            status="undefined_standard",
            evidence=["GitHub API unavailable (GIT_TOKEN not set) — cannot list closed issues"],
        )

    owner, repo = split_repo_id(repo_id)
    sprint = calendar.current_sprint(now)
    since = sprint.window_start()

    try:
        closed_issues = github.list_closed_issues(owner, repo, since)
    except GitHubApiError as exc:
        logger.warning("Issue-to-ticket check API failure for %s: %s", repo_id, exc)
        return IssueTicketTrace(
            status="undefined_standard",
            evidence=[f"GitHub API unavailable while listing closed issues: {exc}"],
        )

    if not closed_issues:
        return IssueTicketTrace(
            status="undefined_standard",
            evidence=[
                f"No issues closed in sprint window {sprint.sprint_id} "
                f"({sprint.start.isoformat()}..{sprint.end.isoformat()}) — nothing to evaluate"
            ],
        )

    # Optional best-effort ticket existence verification.
    api_url = ticketing.get("api_url")
    token = os.getenv(ticketing.get("token_env", "TICKETING_TOKEN"))
    can_verify = bool(api_url and token)
    verified_missing: int = 0
    degraded = False

    unlinked: List[int] = []
    evidence: List[str] = []
    if can_verify:
        evidence.append(
            f"Verifying ticket references against {ticketing.get('type', 'ticketing system')} "
            "API (best-effort; pattern-match fallback on API failure)"
        )
    else:
        evidence.append(
            "Ticket API not reachable (api_url or token env var not set) — "
            "pattern-match only, degraded confidence"
        )

    verified = 0
    for issue in closed_issues:
        number = issue.get("number")
        ref = _extract_ticket_ref(issue, ref_pattern, label_prefix)
        problem = None

        if ref is None:
            problem = (f"no ticket reference matching '{ref_pattern.pattern}' in body"
                       + (f" or label prefix '{label_prefix}'" if label_prefix else ""))
        elif can_verify and verified < MAX_TICKETS_TO_VERIFY:
            exists = _verify_ticket_exists(api_url, token, ref)
            if exists is None:
                degraded = True
            else:
                verified += 1
                if not exists:
                    problem = f"references ticket '{ref}' which does not exist in the ticketing system"
                    verified_missing += 1

        issue_lines = sum(1 for e in evidence if e.startswith("issue #"))
        if issue_lines < MAX_ISSUES_DETAILED_IN_EVIDENCE:
            if problem:
                evidence.append(f"issue #{number} ({issue.get('title') or ''}): UNLINKED — {problem}")
            elif ref:
                evidence.append(f"issue #{number}: ticket '{ref}'")

        if problem:
            unlinked.append(number)

    if degraded:
        evidence.append(
            "Ticket API unavailable for some references — those issues were judged by "
            "pattern match only; degraded confidence"
        )
    evidence.append(
        f"{len(closed_issues) - len(unlinked)}/{len(closed_issues)} issue(s) closed in "
        f"sprint {sprint.sprint_id} trace to a {ticketing.get('type', 'ticketing system')} ticket"
    )
    if unlinked:
        evidence.append(
            f"UNLINKED issues in sprint {sprint.sprint_id}: "
            f"#{', #'.join(str(n) for n in unlinked)}"
        )
    if verified_missing:
        evidence.append(
            f"{verified_missing} reference(s) pointed at tickets that do not exist "
            "(stale or typo'd refs count as unlinked)"
        )

    return IssueTicketTrace(
        status="fail" if unlinked else "pass",
        evidence=evidence,
        unlinked_count=len(unlinked),
        total_checked=len(closed_issues),
    )
