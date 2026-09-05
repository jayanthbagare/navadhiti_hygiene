import yaml
from datetime import datetime
from core.schema import ProjectHygieneReport, Dimensions, Overall
from core.checks.environment import check_environment_separation
from core.checks.ci_gates import check_ci_gates
from core.checks.signoff import check_uat_signoff
from core.checks.cost import check_cost
from core.checks.security import check_security_baseline
from core.checks.deploy_history import check_deploy_history

class ObserverAgent:
    def __init__(self, repo_id: str, repo_url: str, config: dict):
        self.repo_id = repo_id
        self.repo_url = repo_url
        self.config = config
        
        # Load standards and project meta
        self.standard = self._load_yaml("config/standard.yaml")
        self.projects_meta = self._load_yaml("config/projects.yaml").get("repos", {})
        self.project_meta = self.projects_meta.get(repo_id, {})
        self.master_config = self._load_yaml("config/master.yaml")
        
    def _load_yaml(self, path: str) -> dict:
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            return {}

    def run(self) -> ProjectHygieneReport:
        # 1. Environment separation
        env_sep = check_environment_separation(self.repo_id, self.repo_url, self.standard)
        
        # 2. CI/CD gates
        ci_gates = check_ci_gates(self.repo_id, self.repo_url)
        
        # 3. UAT signoff
        signoff = check_uat_signoff(self.repo_id, self.repo_url, self.project_meta)
        
        # 4. Cost tracking
        sprint_duration = self.master_config.get("default_sprint_duration_days", 14)
        cost = check_cost(self.repo_id, self.project_meta, sprint_duration)
        
        # 5. Security baseline
        security = check_security_baseline(self.repo_id, self.repo_url, self.standard)
        
        # 6. Deployment history
        deploy = check_deploy_history(self.repo_id, self.repo_url)
        
        dimensions = Dimensions(
            environment_separation=env_sep,
            ci_cd_gates=ci_gates,
            uat_signoff=signoff,
            cost_tracking=cost,
            security_baseline=security,
            deployment_history=deploy
        )
        
        # Calculate overall score based on weights
        weights = self.master_config.get("weights", {})
        score = self._calculate_score(dimensions, weights)
        
        # Enforcement eligibility (Phase 3 logic)
        # Threshold: environment_separation pass AND uat_signoff repo_artifact for N sprints
        # Currently we just check the current status since we aren't tracking history deeply yet
        eligible = (env_sep.status == "pass" and signoff.method == "repo_artifact")
        
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
        # Simple scoring logic: 100 for pass, 0 for fail/undefined
        score = 0.0
        
        def get_val(status: str) -> float:
            return 100.0 if status == "pass" else 0.0
            
        score += get_val(dimensions.environment_separation.status) * weights.get("environment_separation", 0.2)
        score += get_val(dimensions.ci_cd_gates.status) * weights.get("ci_cd_gates", 0.1)
        score += get_val(dimensions.uat_signoff.status) * weights.get("uat_signoff", 0.4)
        score += get_val(dimensions.security_baseline.status) * weights.get("security_baseline", 0.2)
        score += get_val(dimensions.cost_tracking.status) * weights.get("cost_tracking", 0.1)
        
        return score
