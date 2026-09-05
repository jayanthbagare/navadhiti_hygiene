import yaml
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sub_agents.observer_agent import ObserverAgent
from core.schema import ProjectHygieneReport
import os

class MasterAgent:
    def __init__(self):
        self.config = self._load_yaml("config/master.yaml")
        self.activity_window_days = self.config.get("activity_window_days", 60)
        
    def _load_yaml(self, path: str) -> dict:
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            return {}

    def discover_repos(self) -> List[Dict[str, Any]]:
        """
        Query git provider(s) for repo list + last-commit-date.
        For milestone 1, we will mock this discovery to return 3 repos.
        """
        now = datetime.now()
        return [
            {
                "id": "mock-org/active-project-1",
                "url": "https://github.com/mock-org/active-project-1",
                "last_commit_date": now - timedelta(days=10) # 10 days ago (In scope)
            },
            {
                "id": "mock-org/active-project-2",
                "url": "https://github.com/mock-org/active-project-2",
                "last_commit_date": now - timedelta(days=2) # 2 days ago (In scope)
            },
            {
                "id": "mock-org/dormant-project",
                "url": "https://github.com/mock-org/dormant-project",
                "last_commit_date": now - timedelta(days=100) # 100 days ago (Out of scope)
            }
        ]

    def run(self):
        print(f"Starting Hygiene Master Agent (Activity Window: {self.activity_window_days} days)")
        repos = self.discover_repos()
        
        in_scope_repos = []
        now = datetime.now()
        
        for repo in repos:
            days_since_commit = (now - repo["last_commit_date"]).days
            if days_since_commit <= self.activity_window_days:
                in_scope_repos.append(repo)
                
        print(f"Discovered {len(repos)} repos, {len(in_scope_repos)} in scope.")
        
        reports: List[ProjectHygieneReport] = []
        
        # Dispatch sub-agents
        for repo in in_scope_repos:
            print(f"Dispatching ObserverAgent for {repo['id']}...")
            # Here we would check if project is promoted and dispatch Enforcer if so
            # For Phase 1, we only dispatch Observer
            agent = ObserverAgent(repo["id"], repo["url"], self.config)
            report = agent.run()
            reports.append(report)
            
        self.generate_aggregate_report(reports)
        
    def generate_aggregate_report(self, reports: List[ProjectHygieneReport]):
        os.makedirs("reports", exist_ok=True)
        
        # Generate individual reports
        for report in reports:
            # We use model_dump_json for Pydantic v2
            # Handle datetime serialization correctly
            file_path = f"reports/{report.id.replace('/', '_')}.json"
            with open(file_path, 'w') as f:
                f.write(report.model_dump_json(indent=2))
        
        # Generate aggregate
        aggregate = {
            "generated_at": datetime.now().isoformat(),
            "total_evaluated": len(reports),
            "projects": []
        }
        
        for r in reports:
            aggregate["projects"].append({
                "id": r.id,
                "score": r.overall.hygiene_score,
                "gap_flag": r.dimensions.deployment_history.gap_flag,
                "variance_pct": r.dimensions.cost_tracking.variance_pct,
                "eligible_for_enforcement": r.overall.enforcement_eligible
            })
            
        # Sort by gap flag count (desc), variance pct (desc), score (asc)
        aggregate["projects"].sort(key=lambda x: (
            -int(x["gap_flag"]), 
            -(x["variance_pct"] or 0), 
            x["score"]
        ))
        
        with open("reports/aggregate.json", 'w') as f:
            json.dump(aggregate, f, indent=2)
            
        print(f"Reports generated in reports/ directory. Aggregate view:")
        print(json.dumps(aggregate, indent=2))

if __name__ == "__main__":
    master = MasterAgent()
    master.run()
