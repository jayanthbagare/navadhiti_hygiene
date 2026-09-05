"""
Enforcer Agent — the CI merge gate.

Runs the full deterministic evaluation for a single repo (via the
ObserverAgent) and exits 0 (pass) or 1 (fail) so CI can block merges.

Blocking criteria:
- environment_separation: pass required
- ci_cd_gates: pass required
- uat_signoff: pass required
- deployment_history.gap_flag: must be false

Traceability (C4): both traceability checks block merges for NEW
projects only — repos created at/after
`enforcement.new_project_cutoff_date` in config/master.yaml. Existing
projects are not retroactively blocked on traceability; they go through
the same observe-then-promote path as every other dimension. A traceability
check reporting `undefined_standard` never blocks (the org hasn't defined
that standard yet — consistent with how undefined standards are treated
everywhere else); only a definite `fail` blocks. If "new project" cannot
be determined (no cutoff configured / API unavailable), traceability is
reported but not blocking.

CLI (CI usage): python -m sub_agents.enforcer_agent <owner/repo> [repo_url]
"""

import logging
import sys
from datetime import date
from typing import Optional

import yaml

from core.github_client import GitHubApiError, GitHubClient, parse_github_timestamp, split_repo_id
from sub_agents.observer_agent import ObserverAgent

logger = logging.getLogger("hygiene.enforcer")


class EnforcerAgent:
    def __init__(self, repo_id: str, repo_url: str, config: dict = None):
        self.repo_id = repo_id
        self.repo_url = repo_url
        self.config = config or self._load_yaml("config/master.yaml")
        self.integrations = self._load_yaml("config/integrations.yaml")

    def _load_yaml(self, path: str) -> dict:
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            return {}

    def _repo_created_at(self) -> Optional[object]:
        """Best-effort repo creation date from the GitHub API."""
        github = GitHubClient.from_config(self.integrations.get("git_provider", {}))
        if not github.authenticated:
            return None
        try:
            owner, repo = split_repo_id(self.repo_id)
            return parse_github_timestamp(github.get_repo(owner, repo).get("created_at"))
        except (GitHubApiError, ValueError) as exc:
            logger.warning("Could not determine repo creation date for %s: %s", self.repo_id, exc)
            return None

    def traceability_gate_applies(self) -> bool:
        """
        Traceability blocks only new projects: created at/after the
        configured cutoff. When the cutoff is not configured or the
        creation date is unknown, the gate stays off (never
        retroactively block existing projects).
        """
        enforcement = self.config.get("enforcement", {}) or {}
        if not enforcement.get("traceability_gate_for_new_projects", True):
            return False
        cutoff_raw = enforcement.get("new_project_cutoff_date")
        if not cutoff_raw:
            return False
        try:
            cutoff = date.fromisoformat(str(cutoff_raw))
        except ValueError:
            logger.warning("Invalid enforcement.new_project_cutoff_date: %r", cutoff_raw)
            return False
        created_at = self._repo_created_at()
        if created_at is None:
            return False
        return created_at.date() >= cutoff

    def run(self) -> int:
        observer = ObserverAgent(self.repo_id, self.repo_url, self.config)
        report = observer.run()

        failures = []
        dims = report.dimensions

        if dims.environment_separation.status != "pass":
            failures.append("Environment separation check failed.")
        if dims.ci_cd_gates.status != "pass":
            failures.append("CI/CD gates check failed.")
        if dims.uat_signoff.status != "pass":
            failures.append("UAT sign-off missing or invalid.")
        if dims.deployment_history.gap_flag:
            failures.append("Deployment history gap flag detected.")

        trace = dims.traceability
        if self.traceability_gate_applies():
            if trace.feature_to_issue.status == "fail":
                failures.append(
                    f"Traceability (feature-to-issue) failed: "
                    f"{trace.feature_to_issue.unlinked_count}/{trace.feature_to_issue.total_checked} "
                    "merged PR(s) unlinked to an issue."
                )
            if trace.issue_to_ticket.status == "fail":
                failures.append(
                    f"Traceability (issue-to-ticket) failed: "
                    f"{trace.issue_to_ticket.unlinked_count}/{trace.issue_to_ticket.total_checked} "
                    "closed issue(s) unlinked to an external ticket."
                )

        if failures:
            print(f"ENFORCER GATE REJECTED MERGE for {self.repo_id}:")
            for failure in failures:
                print(f"  - {failure}")
            return 1

        print(f"ENFORCER GATE PASSED for {self.repo_id}.")
        return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if len(sys.argv) < 2:
        print("Usage: python -m sub_agents.enforcer_agent <owner/repo> [repo_url]")
        sys.exit(2)
    _repo_url = sys.argv[2] if len(sys.argv) > 2 else f"https://github.com/{sys.argv[1]}"
    agent = EnforcerAgent(sys.argv[1], _repo_url)
    sys.exit(agent.run())
