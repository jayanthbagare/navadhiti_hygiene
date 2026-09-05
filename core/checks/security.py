"""
Security baseline check (A4).

File-tree check against `config/standard.yaml`'s
`security_baseline.required_scanners`. A scanner counts as present when
one of its known artifact patterns matches the default branch's file
tree — e.g. Dependabot config, `.snyk`, or a Trivy workflow step.

Reuses the same cached recursive Trees API call as the environment check
(one round-trip per repo per run, shared via GitHubClient).

Pass: at least one configured scanner discovered.
Fail: check ran, none of the required scanners' artifacts found
      (evidence names each scanner searched for and confirms it is
      missing).
undefined_standard: no scanners configured / API unavailable / truncated tree.

Scanner artifact patterns can be overridden in config/standard.yaml:
    security_baseline:
      required_scanners: [dependabot, snyk, trivy]
      scanner_artifacts:
        snyk: [".snyk", ".github/workflows/*snyk*"]
"""

import logging
from typing import Dict, List, Optional

from core.checks.tree_utils import find_pattern_matches, tree_paths_for_repo
from core.github_client import GitHubApiError, GitHubClient, split_repo_id
from core.schema import SecurityBaseline

logger = logging.getLogger("hygiene.checks.security")

DEFAULT_SCANNER_ARTIFACTS: Dict[str, List[str]] = {
    "dependabot": [".github/dependabot.yml", ".github/dependabot.yaml"],
    "snyk": [".snyk", ".github/workflows/*snyk*"],
    "trivy": [".trivy.yaml", ".trivy.yml", ".github/workflows/*trivy*"],
}


def check_security_baseline(repo_id: str, github: Optional[GitHubClient],
                            standard: dict, default_branch: str = "main") -> SecurityBaseline:
    security_cfg = (standard or {}).get("security_baseline", {}) or {}
    scanners: List[str] = security_cfg.get("required_scanners", []) or []
    overrides: Dict[str, List[str]] = security_cfg.get("scanner_artifacts", {}) or {}

    if not scanners:
        return SecurityBaseline(
            status="undefined_standard",
            evidence=["No security_baseline.required_scanners configured in config/standard.yaml"],
        )
    if github is None or not github.authenticated:
        return SecurityBaseline(
            status="undefined_standard",
            evidence=["GitHub API unavailable (GIT_TOKEN not set) — cannot inspect repository tree"],
        )

    owner, repo = split_repo_id(repo_id)
    branch = default_branch or "main"
    try:
        paths = tree_paths_for_repo(github, owner, repo, branch)
        truncated = github.tree_truncated(owner, repo, branch)
    except GitHubApiError as exc:
        logger.warning("Security check API failure for %s: %s", repo_id, exc)
        return SecurityBaseline(
            status="undefined_standard",
            evidence=[f"GitHub API unavailable while checking security baseline: {exc}"],
        )

    evidence = []
    found_scanner = None
    for scanner in scanners:
        patterns = overrides.get(scanner) or DEFAULT_SCANNER_ARTIFACTS.get(scanner)
        if patterns is None:
            evidence.append(
                f"Scanner '{scanner}': no artifact patterns configured and no "
                "built-in patterns known — cannot verify"
            )
            continue
        for pattern in patterns:
            matches = find_pattern_matches(paths, pattern)
            if matches:
                found_scanner = scanner
                evidence.append(
                    f"Scanner '{scanner}' present: '{matches[0]}' matches pattern '{pattern}'"
                )
                break
        if found_scanner:
            break
        evidence.append(
            f"Scanner '{scanner}' not found (searched for: {', '.join(patterns)})"
        )

    if truncated:
        evidence.append(
            "GitHub returned a truncated file tree for this repo — scanner presence "
            "check is not exhaustive; treating result as undefined rather than failing"
        )
        return SecurityBaseline(status="undefined_standard", evidence=evidence)

    if found_scanner:
        return SecurityBaseline(status="pass", evidence=evidence)
    return SecurityBaseline(
        status="fail",
        evidence=evidence + [
            "Searched for all required security scanners listed in config/standard.yaml; "
            "none is configured on the default branch"
        ],
    )
