"""
Environment separation check (A2).

Verifies the repository defines distinct deployment environments by
checking the default branch's file tree (GitHub Trees API, recursive)
against `config/standard.yaml`'s
`environment_separation.required_artifacts` patterns.

No cloning: a recursive git-trees call per repo is enough for a
presence check, and the tree is cached on the shared GitHubClient so
the security check (A4) reuses the same round-trip.

Status rules:
- pass  : at least one required artifact pattern matched.
- fail  : check ran, no pattern matched (evidence lists every pattern
          searched and confirms none was found).
- undefined_standard : no required_artifacts configured, GitHub API
          unavailable, or the tree listing was truncated by GitHub
          (presence cannot be proven reliably).
"""

import logging
from typing import List, Optional

from core.checks.tree_utils import find_pattern_matches, tree_paths_for_repo
from core.github_client import GitHubApiError, GitHubClient, split_repo_id
from core.schema import EnvironmentSeparation

logger = logging.getLogger("hygiene.checks.environment")


def check_environment_separation(repo_id: str, github: Optional[GitHubClient],
                                  standard: dict, default_branch: str = "main") -> EnvironmentSeparation:
    patterns: List[str] = (standard or {}).get("environment_separation", {}).get(
        "required_artifacts", []
    ) or []

    if not patterns:
        return EnvironmentSeparation(
            status="undefined_standard",
            evidence=["No environment_separation.required_artifacts configured in config/standard.yaml"],
        )
    if github is None or not github.authenticated:
        return EnvironmentSeparation(
            status="undefined_standard",
            evidence=["GitHub API unavailable (GIT_TOKEN not set) — cannot inspect repository tree"],
        )

    owner, repo = split_repo_id(repo_id)
    branch = default_branch or "main"
    try:
        paths = tree_paths_for_repo(github, owner, repo, branch)
        truncated = github.tree_truncated(owner, repo, branch)
    except GitHubApiError as exc:
        logger.warning("Environment check API failure for %s: %s", repo_id, exc)
        return EnvironmentSeparation(
            status="undefined_standard",
            evidence=[f"GitHub API unavailable while checking environment separation: {exc}"],
        )

    evidence = []
    matched_any = False
    for pattern in patterns:
        matches = find_pattern_matches(paths, pattern)
        if matches:
            matched_any = True
            evidence.append(
                f"Found environment artifact matching '{pattern}': {matches[0]}"
                + (f" (+{len(matches) - 1} more)" if len(matches) > 1 else "")
            )
        else:
            evidence.append(f"No artifact matching required pattern '{pattern}'")

    if truncated:
        evidence.append(
            "GitHub returned a truncated file tree for this repo — presence check "
            "is not exhaustive; treating result as undefined rather than failing"
        )
        return EnvironmentSeparation(status="undefined_standard", evidence=evidence)

    if matched_any:
        return EnvironmentSeparation(status="pass", evidence=evidence)
    return EnvironmentSeparation(
        status="fail",
        evidence=evidence + [
            "Searched for the required environment separation artifacts listed in "
            "config/standard.yaml; none of them is present on the default branch"
        ],
    )
