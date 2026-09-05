import argparse
import json
import logging
import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional

import yaml

from core.git_providers import RepoInfo, discover_repos
from core.promotion import DEFAULT_STATE_PATH, load_state, update_promotion_state
from core.sprint import calendar_from_config
from core.schema import ProjectHygieneReport
from sub_agents.observer_agent import ObserverAgent

logger = logging.getLogger("hygiene.master")

WEIGHT_EPSILON = 1e-6

TRACEABILITY_WEIGHT_ADVICE = (
    "Traceability dimension is live but has no configured weight; the scoring formula "
    "treats it as 0.0 until a human updates config/master.yaml. Suggested starting "
    "value: 0.10 (10%), taken proportionally from ci_cd_gates and cost_tracking "
    "(already the lowest-weighted dimensions). This requires explicit confirmation "
    "in config — the system never auto-rebalances weights."
)


class MasterAgent:
    def __init__(self):
        self.config = self._load_yaml("config/master.yaml")
        self.activity_window_days = self.config.get("activity_window_days", 60)
        self.projects_config = self._load_yaml("config/projects.yaml")
        self.projects_meta = self.projects_config.get("repos", {}) or {}
        self.overrides = self.projects_config.get("overrides", {}) or {}
        self.integrations = self._load_yaml("config/integrations.yaml")

    def _load_yaml(self, path: str) -> dict:
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            return {}

    # ------------------------------------------------------------------
    # B6 — weight-sum validation
    # ------------------------------------------------------------------

    def validate_weights(self) -> List[str]:
        """
        Configured weights must sum to 1.0 (within a small epsilon). An
        unset traceability weight is fine (treated as 0.0 and flagged in
        the report); any configured set that doesn't sum to 1.0 fails
        loudly rather than producing a silently wrong score.
        """
        weights = self.config.get("weights", {})
        total = sum(float(w) for w in weights.values()) if weights else 0.0
        if not weights or abs(total - 1.0) > WEIGHT_EPSILON:
            raise SystemExit(
                f"CONFIG ERROR: weights in config/master.yaml sum to {round(total, 6)}, "
                "expected exactly 1.0. A mis-weighted score would be silently wrong; "
                "fix the weights before running."
            )
        warnings = []
        if "traceability" not in weights:
            warnings.append(TRACEABILITY_WEIGHT_ADVICE)
        return warnings

    # ------------------------------------------------------------------
    # A1 — repository discovery via the configured git provider
    # ------------------------------------------------------------------

    def discover_repos(self) -> List[RepoInfo]:
        """
        Query the configured git provider (config/integrations.yaml
        git_provider) for the org-wide repo list with last-commit dates.
        Provider-specific code lives behind core/git_providers.discover_repos.
        """
        return discover_repos(self.integrations.get("git_provider", {}))

    def filter_in_scope(self, repos: List[RepoInfo],
                        include_ids: Optional[List[str]] = None) -> tuple:
        """
        Activity-window filter (B4): config/projects.yaml `overrides`
        can set activity_window_days per-repo; --include force-includes
        a repo for a single run regardless of window.

        Returns (in_scope_repos, excluded) where excluded entries carry
        the reason they were left out.
        """
        include_ids = include_ids or []
        now = datetime.now()
        in_scope: List[RepoInfo] = []
        excluded: List[dict] = []

        for repo in repos:
            window = self._window_for_repo(repo.id)
            forced = repo.id in include_ids
            if repo.last_commit_date is None:
                in_scope.append(repo)
                logger.info("Including %s: last commit date unknown (cannot prove dormancy)", repo.id)
                continue
            days_since_commit = (now - repo.last_commit_date).days
            if days_since_commit <= window:
                in_scope.append(repo)
            elif forced:
                in_scope.append(repo)
                logger.info("Force-including %s via --include "
                            "(last commit %d days ago > window %d)", repo.id, days_since_commit, window)
            else:
                excluded.append({
                    "id": repo.id,
                    "reason": f"dormant: last commit {days_since_commit} days ago "
                              f"(window {window}d"
                              + (" overridden" if window != self.activity_window_days else "")
                              + ")",
                })

        for repo_id in include_ids:
            if repo_id not in {r.id for r in in_scope}:
                logger.warning("--include %s did not match any discovered repo", repo_id)
        return in_scope, excluded

    def _window_for_repo(self, repo_id: str) -> int:
        repo_override = (self.overrides.get(repo_id) or {}).get("activity_window_days")
        if repo_override:
            return int(repo_override)
        return int(self.activity_window_days)

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self, include_ids: Optional[List[str]] = None):
        print(f"Starting Hygiene Master Agent (Activity Window: {self.activity_window_days} days)")

        weight_warnings = self.validate_weights()

        try:
            repos = self.discover_repos()
        except ValueError as exc:
            raise SystemExit(f"REPOSITORY DISCOVERY FAILED: {exc}")

        in_scope, excluded = self.filter_in_scope(repos, include_ids)
        print(f"Discovered {len(repos)} repos, {len(in_scope)} in scope.")
        for item in excluded:
            logger.info("Excluding %s: %s", item['id'], item['reason'])

        reports: List[ProjectHygieneReport] = []

        # Dispatch sub-agents
        for repo in in_scope:
            print(f"Dispatching ObserverAgent for {repo.id}...")
            agent = ObserverAgent(repo.id, repo.url, self.config, repo_meta=repo.model_dump())
            reports.append(agent.run())

        # B2 — promotion-state persistence (the only cross-run state).
        # Flips each report's enforcement_eligible from the persisted
        # streak, not just this sprint's snapshot.
        sprint_ids: Dict[str, Optional[str]] = {}
        for repo in in_scope:
            calendar = calendar_from_config(self.config, self.projects_meta.get(repo.id, {}))
            sprint_ids[repo.id] = calendar.current_sprint().sprint_id
        promotion_state = load_state(DEFAULT_STATE_PATH)
        update_promotion_state(
            reports, promotion_state, sprint_ids,
            threshold=int(self.config.get("promotion_threshold_sprints", 3)),
            require_traceability=bool(self.config.get("require_traceability_for_promotion", False)),
            path=DEFAULT_STATE_PATH,
        )

        self.generate_aggregate_report(reports, excluded, weight_warnings)

    def generate_aggregate_report(self, reports: List[ProjectHygieneReport],
                                  excluded: List[dict], weight_warnings: List[str]):
        os.makedirs("reports", exist_ok=True)

        # B5 — archive the previous run's aggregate before overwriting.
        self._archive_previous_aggregate()

        # Generate individual reports
        for report in reports:
            file_path = f"reports/{report.id.replace('/', '_')}.json"
            with open(file_path, 'w') as f:
                f.write(report.model_dump_json(indent=2))

        promotion_state = load_state(DEFAULT_STATE_PATH).get("repos", {})

        # Generate aggregate
        aggregate = {
            "generated_at": datetime.now().isoformat(),
            "total_evaluated": len(reports),
            "weight_warnings": weight_warnings,
            "projects": []
        }

        for r in reports:
            streak = promotion_state.get(r.id, {}).get("qualifying_streak", 0)
            aggregate["projects"].append({
                "id": r.id,
                "score": r.overall.hygiene_score,
                "gap_flag": r.dimensions.deployment_history.gap_flag,
                "variance_pct": r.dimensions.cost_tracking.variance_pct,
                "eligible_for_enforcement": r.overall.enforcement_eligible,
                "qualifying_streak": streak,
                "traceability_unlinked": {
                    "feature_to_issue": {
                        "unlinked": r.dimensions.traceability.feature_to_issue.unlinked_count,
                        "total": r.dimensions.traceability.feature_to_issue.total_checked,
                    },
                    "issue_to_ticket": {
                        "unlinked": r.dimensions.traceability.issue_to_ticket.unlinked_count,
                        "total": r.dimensions.traceability.issue_to_ticket.total_checked,
                    },
                },
            })

        # Sort by gap flag count (desc), variance pct (desc), score (asc)
        aggregate["projects"].sort(key=lambda x: (
            -int(x["gap_flag"]),
            -(x["variance_pct"] or 0),
            x["score"]
        ))

        aggregate["excluded_repos"] = excluded

        with open('reports/aggregate.json', 'w') as f:
            json.dump(aggregate, f, indent=2)

        # B5 — snapshot this run into history too, so the archive is a
        # complete run log and the Hermes layer can diff any two runs.
        self._archive_aggregate(aggregate["generated_at"])

        print("Reports generated in reports/ directory. Aggregate view:")
        print(json.dumps(aggregate, indent=2))

    def _archive_aggregate(self, generated_at: str):
        """B5 — copy reports/aggregate.json to reports/history/ under its own timestamp."""
        if not os.path.exists("reports/aggregate.json"):
            return
        history_dir = "reports/history"
        os.makedirs(history_dir, exist_ok=True)
        safe_ts = str(generated_at).replace(":", "-").replace("/", "-")
        dest = os.path.join(history_dir, f"{safe_ts}-aggregate.json")
        try:
            shutil.copy2("reports/aggregate.json", dest)
            logger.info("Archived aggregate to %s", dest)
        except OSError as exc:
            logger.warning("Could not archive aggregate: %s", exc)

    def _archive_previous_aggregate(self):
        """
        B5 — before overwriting, preserve the previous run's aggregate.
        Belt-and-suspenders: the previous run already snapshotted itself,
        but this guards against deleted history files or manual edits.
        """
        if not os.path.exists("reports/aggregate.json"):
            return
        timestamp = None
        try:
            with open("reports/aggregate.json", 'r') as f:
                timestamp = json.load(f).get("generated_at")
        except (json.JSONDecodeError, OSError):
            timestamp = None
        if not timestamp:
            timestamp = datetime.fromtimestamp(
                os.path.getmtime("reports/aggregate.json")
            ).isoformat()
        self._archive_aggregate(timestamp)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Navadhiti Hygiene Master Agent")
    parser.add_argument(
        "--include", action="append", default=[], metavar="REPO_ID",
        help="Force-include a repo for this run regardless of the activity "
             "window (e.g. --include org/repo); repeatable",
    )
    args = parser.parse_args()
    master = MasterAgent()
    master.run(include_ids=args.include or None)


if __name__ == "__main__":
    main()
