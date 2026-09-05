"""
CI/CD gates check (A3).

Branch protection is repository settings, not a file — so this check
reads the GitHub Branch Protection API
(`GET /repos/{owner}/{repo}/branches/{branch}/protection`), not the file
tree.

Pass requires ALL of:
1. Protection enabled on the default branch (API returns a protection object).
2. Required reviews: required_pull_request_reviews with
   required_approving_review_count >= 1.
3. Required status checks present: non-empty `contexts` or non-empty
   `checks` in required_status_checks.

Otherwise fail, with evidence naming exactly which requirement is
missing. undefined_standard when the API is unavailable or the token
lacks administration read scope (a 403 — we cannot distinguish
"protected" from "not" without that scope, so we do not guess).
"""

import logging
from typing import Optional

from core.github_client import GitHubApiError, GitHubClient, split_repo_id
from core.schema import CiCdGates

logger = logging.getLogger("hygiene.checks.ci_gates")


def check_ci_gates(repo_id: str, github: Optional[GitHubClient],
                   default_branch: str = "main") -> CiCdGates:
    if github is None or not github.authenticated:
        return CiCdGates(
            status="undefined_standard",
            evidence=["GitHub API unavailable (GIT_TOKEN not set) — cannot read branch protection"],
        )

    owner, repo = split_repo_id(repo_id)
    branch = default_branch or "main"
    try:
        protection = github.get_branch_protection(owner, repo, branch)
    except GitHubApiError as exc:
        logger.warning("CI gates check API failure for %s: %s", repo_id, exc)
        return CiCdGates(
            status="undefined_standard",
            evidence=[f"GitHub API unavailable while reading branch protection: {exc}"],
        )

    if protection is None:
        return CiCdGates(
            status="fail",
            evidence=[
                f"Branch protection is not enabled on default branch '{branch}' "
                "(Branch Protection API returned no protection settings)"
            ],
        )

    evidence = [f"Branch protection enabled on default branch '{branch}'"]

    reviews = protection.get("required_pull_request_reviews") or {}
    review_count = reviews.get("required_approving_review_count") or 0
    if review_count >= 1:
        evidence.append(f"Required reviews enforced: {review_count} approving review(s) required before merge")
    else:
        return CiCdGates(
            status="fail",
            evidence=evidence + [
                "Missing requirement: no approving review is required before merge "
                "(required_approving_review_count < 1)"
            ],
        )

    status_checks = protection.get("required_status_checks") or {}
    contexts = status_checks.get("contexts") or []
    checks = status_checks.get("checks") or []
    if contexts or checks:
        names = [c if isinstance(c, str) else c.get("context", "?") for c in contexts]
        names += [c.get("context", "?") for c in checks if isinstance(c, dict)]
        evidence.append(
            "Required status checks present: " + ", ".join(names[:5])
            + (f" (+{len(names) - 5} more)" if len(names) > 5 else "")
        )
        return CiCdGates(status="pass", evidence=evidence)

    return CiCdGates(
        status="fail",
        evidence=evidence + [
            "Missing requirement: no required status checks configured "
            "(branches can merge without CI passing)"
        ],
    )
