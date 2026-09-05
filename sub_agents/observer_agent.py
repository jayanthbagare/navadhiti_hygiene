import yaml
from datetime import datetime
from core.schema import ProjectHygieneReport, Dimensions, Overall, Traceability
from core.checks.environment import check_environment_separation
from core.checks.ci_gates import check_ci_gates
from core.checks.signoff import check_uat_signoff, build_uat_signoff, discover_signoff_artifacts
from core.checks.cost import check_cost
from core.checks.security import check_security_baseline
from core.checks.deploy_history import check_deploy_history
from core.checks.traceability_issue import check_feature_issue_trace
from core.checks.traceability_ticket import check_issue_ticket_trace
from core.github_client import GitHubClient
from core.sprint import calendar_from_config


class ObserverAgent:
    def __init__(self, repo_id: str, repo_url: str, config: dict, repo_meta: dict = None):
        self.repo_id = repo_id
        self.repo_url = repo_url
        self.config = config
        self.repo_meta = repo_meta or {}

        # Load standards and project meta
        self.standard = self._load_yaml("config/standard.yaml")
        self.integrations = self._load_yaml("config/integrations.yaml")
        self.projects_meta = self._load_yaml("config/projects.yaml").get("repos") or {}
        self.project_meta = self.projects_meta.get(repo_id, {})
        self.master_config = self._load_yaml("config/master.yaml")

        # Shared GitHub API client (one session; the recursive tree is
        # cached per repo so environment + security + signoff checks
        # share a single round-trip).
        self.github = GitHubClient.from_config(self.integrations.get("git_provider", {}))

        # Sprint calendar: per-project override, else global default.
        self.calendar = calendar_from_config(self.master_config, self.project_meta)

    def _load_yaml(self, path: str) -> dict:
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            return {}

    def run(self) -> ProjectHygieneReport:
        default_branch = self.repo_meta.get("default_branch") or "main"

        # 1. Environment separation
        env_sep = check_environment_separation(
            self.repo_id, self.github, self.standard, default_branch
        )

        # 2. CI/CD gates
        ci_gates = check_ci_gates(self.repo_id, self.github, default_branch)

        # 3. UAT signoff (repo-artifact tier). Discovery happens once so the
        # deploy-history check reuses the parsed artifacts.
        signoff_artifacts = discover_signoff_artifacts(
            self.repo_id, self.github, self.standard, self.calendar, default_branch
        )
        signoff = build_uat_signoff(
            self.repo_id, signoff_artifacts, self.standard, self.calendar
        )

        # 4. Cost tracking — sprint duration comes from the calendar (B1),
        #    falling back to default_sprint_duration_days.
        sprint_duration = self.calendar.sprint_length_days
        cost = check_cost(self.repo_id, self.project_meta, sprint_duration)

        # 5. Security baseline (shares the cached tree with check 1)
        security = check_security_baseline(
            self.repo_id, self.github, self.standard, default_branch
        )

        # 6. Deployment history (uses the real release/tag timestamps and the
        # parsed signoff artifacts)
        deploy = check_deploy_history(
            self.repo_id, self.github, self.standard, signoff_artifacts,
            self.calendar, default_branch
        )

        # 7. Traceability (feature -> issue, issue -> ticket)
        feature_issue = check_feature_issue_trace(
            self.repo_id, self.github, self.standard, self.calendar, default_branch
        )
        issue_ticket = check_issue_ticket_trace(
            self.repo_id, self.github, self.standard, self.integrations,
            self.calendar, default_branch
        )

        dimensions = Dimensions(
            environment_separation=env_sep,
            ci_cd_gates=ci_gates,
            uat_signoff=signoff,
            cost_tracking=cost,
            security_baseline=security,
            deployment_history=deploy,
            traceability=Traceability(
                feature_to_issue=feature_issue, issue_to_ticket=issue_ticket
            ),
        )

        # Calculate overall score based on weights
        weights = self.master_config.get("weights", {})
        score = self._calculate_score(dimensions, weights)

        # Current-sprint promotion qualification. The MasterAgent overrides
        # this with the persisted streak (B2) before reports are written;
        # this flag alone means "qualifies this sprint".
        eligible = (env_sep.status == "pass"
                    and signoff.method == "repo_artifact"
                    and signoff.status == "pass")

        overall = Overall(
            hygiene_score=score,
            enforcement_eligible=eligible
        )

        return ProjectHygieneReport(
            id=self.repo_id,
            repo_url=self.repo_url,
            last_evaluated=datetime.now(),
            dimensions=dimensions,
            overall=overall
        )

    def _calculate_score(self, dimensions: Dimensions, weights: dict) -> float:
        # Simple scoring logic: 100 for pass, 0 for fail/undefined.
        # Unset weights count as 0.0 (e.g. traceability until rebalanced).
        score = 0.0

        def get_val(status: str) -> float:
            return 100.0 if status == "pass" else 0.0

        score += get_val(dimensions.environment_separation.status) * weights.get("environment_separation", 0.2)
        score += get_val(dimensions.ci_cd_gates.status) * weights.get("ci_cd_gates", 0.1)
        score += get_val(dimensions.uat_signoff.status) * weights.get("uat_signoff", 0.4)
        score += get_val(dimensions.security_baseline.status) * weights.get("security_baseline", 0.2)
        score += get_val(dimensions.cost_tracking.status) * weights.get("cost_tracking", 0.1)
        score += get_val(dimensions.traceability.feature_to_issue.status) * weights.get("traceability", 0.0)
        # issue_to_ticket is reported inside the traceability dimension; it
        # only affects the score through the feature_to_issue tier above
        # unless a weight split is configured later.

        return score
