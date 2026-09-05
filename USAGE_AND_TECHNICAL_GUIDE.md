# Navadhiti Hygiene System: Technical & Usage Guide

## Table of Contents
1. [Executive Summary & System Purpose](#1-executive-summary--system-purpose)
2. [Architectural Overview](#2-architectural-overview)
   - [Master-Subagent Design Pattern](#master-subagent-design-pattern)
   - [Observer Mode vs. Enforcer Mode](#observer-mode-vs-enforcer-mode)
   - [Hermes Agent Integration Layer](#hermes-agent-integration-layer)
3. [Repository Structure & Codebase Map](#3-repository-structure--codebase-map)
4. [Data Contracts & Schemas](#4-data-contracts--schemas)
   - [Domain Schema (`core/schema.py`)](#domain-schema-coreschemapy)
   - [Report JSON Specifications](#report-json-specifications)
5. [The Six Hygiene Dimensions in Detail](#5-the-six-hygiene-dimensions-in-detail)
   - [1. Environment Separation](#1-environment-separation)
   - [2. CI/CD Gates](#2-cicd-gates)
   - [3. UAT Sign-off](#3-uat-sign-off)
   - [4. Cost Tracking & Variance Analysis](#4-cost-tracking--variance-analysis)
   - [5. Security Baseline](#5-security-baseline)
   - [6. Deployment History & Gap Flag Detection](#6-deployment-history--gap-flag-detection)
6. [Scoring Engine & Promotion Mechanics](#6-scoring-engine--promotion-mechanics)
   - [Weighted Scoring Formula](#weighted-scoring-formula)
   - [Sorting & Prioritization Matrix](#sorting--prioritization-matrix)
   - [Enforcement Eligibility & Promotion Criteria](#enforcement-eligibility--promotion-criteria)
7. [Configuration System](#7-configuration-system)
   - [`config/master.yaml`](#configmasteryaml)
   - [`config/projects.yaml`](#configprojectsyaml)
   - [`config/standard.yaml`](#configstandardyaml)
   - [`config/integrations.yaml`](#configintegrationsyaml)
8. [End-to-End Execution Flow](#8-end-to-end-execution-flow)
9. [Step-by-Step Implementation & Productionization Guide](#9-step-by-step-implementation--productionization-guide)
   - [Phase 1: Real Git Provider Integration](#phase-1-real-git-provider-integration)
   - [Phase 2: Implementing Real File/Tree Checks](#phase-2-implementing-real-filetree-checks)
   - [Phase 3: Real Timesheet & Zoho People Integration](#phase-3-real-timesheet--zoho-people-integration)
   - [Phase 4: Office365 / Graph API Email Sign-off Scanning](#phase-4-office365--graph-api-email-sign-off-scanning)
   - [Phase 5: Implementing `EnforcerAgent` as a CI/CD Gate](#phase-5-implementing-enforceragent-as-a-cicd-gate)
10. [Operations, Monitoring & Runbook](#10-operations-monitoring--runbook)
11. [Troubleshooting & FAQ](#11-troubleshooting--faq)

---

## 1. Executive Summary & System Purpose

The **Navadhiti Project Hygiene System** is an automated governance and engineering health assessment framework. Modern software engineering organizations often face visibility gaps across projects:
- Untracked deployments released to production without verified User Acceptance Testing (UAT).
- Missing environment segregation between staging, development, and production.
- Security scanners neglected or not integrated into pull request pipelines.
- Labor cost overruns going undetected until accounting end-of-month reconciliations.
- Dormant or stale repositories cluttering organizational dashboards.

The Hygiene System solves these challenges through deterministic inspection scripts paired with an intelligent subagent architecture. It audits active repositories against engineering standards, detects compliance gaps, tracks budget-to-actual cost variance, and calculates a normalized 0–100 **Hygiene Score**.

The system operates under strict separation of concerns:
1. **Deterministic Inspection (`core/checks/`)**: Pure, reproducible code checks that evaluate objective criteria and emit structured data.
2. **Orchestration & Scoring (`MasterAgent` & `ObserverAgent`)**: Coordinates repository discovery, runs checks across active projects, and computes weighted metrics.
3. **Continuous Enforcement (`EnforcerAgent`)**: A gate designed for pull-request / CI pipelines to block merges that violate baseline hygiene standards.
4. **Agentic Interpretation (`hermes/skill.md`)**: An AI agent layer that synthesizes aggregate findings into executive narratives without hallucinating or overriding deterministic check statuses.

---

## 2. Architectural Overview

### Master-Subagent Design Pattern

The system follows a hierarchical Master-Subagent orchestration pattern:

```
                      +-------------------+
                      |   MasterAgent     |
                      | (master_agent.py) |
                      +---------+---------+
                                |
             +------------------+------------------+
             | Query & Filter                     | Output
             v                                     v
   +--------------------+                 +------------------+
   | In-Scope Repos     |                 |  reports/        |
   | (Active <= 60d)    |                 |  aggregate.json  |
   +---------+----------+                 +------------------+
             |
             +-----------------------+
             | Dispatches            | Dispatches (CI Gate)
             v                       v
   +--------------------+  +--------------------+
   |   ObserverAgent    |  |   EnforcerAgent    |
   | (sub_agents/)      |  | (sub_agents/)      |
   +---------+----------+  +--------------------+
             |
             | Evaluates 6 Deterministic Dimensions
             |
             +---> core/checks/environment.py
             +---> core/checks/ci_gates.py
             +---> core/checks/signoff.py
             +---> core/checks/cost.py
             +---> core/checks/security.py
             +---> core/checks/deploy_history.py
```

### Observer Mode vs. Enforcer Mode

| Dimension | **Observer Mode (`ObserverAgent`)** | **Enforcer Mode (`EnforcerAgent`)** |
| :--- | :--- | :--- |
| **Execution Trigger** | Scheduled run (e.g. daily/weekly cron or CLI) | Git push / Pull Request CI trigger |
| **Target Scope** | All active repositories across the organization | Single repository in pull-request context |
| **System Impact** | Read-only; generates reports and metrics | Gating; exits with code `0` (pass) or `1` (fail) |
| **Promotion State** | Targets all unpromoted and promoted projects | Activated for promoted projects and all new repositories |
| **Output** | Detailed JSON reports per repo + aggregate | Status checks, PR comments, build logs |

### Hermes Agent Integration Layer

The Hermes skill (`hermes/skill.md`) serves as the orchestration and executive judgment layer when run inside an autonomous agent harness.
- **Strict Boundary**: The agent *never* guesses a pass/fail status, *never* fabricates cost figures or budgets, and *never* overrides deterministic script results.
- **Narrative Role**: The agent identifies macro trends (e.g., *"3 out of 10 active projects account for 85% of budget overruns"*, or *"deployment gap flags clustered following the v2.4 sprint cut"*).
- **Promotion Recommender**: Flag projects that meet Phase 3 thresholds to human leads for CI enforcement activation.

---

## 3. Repository Structure & Codebase Map

```
hygiene/
├── README.md                      # Quickstart and project summary
├── USAGE_AND_TECHNICAL_GUIDE.md   # Complete technical and operational guide (this file)
├── master_agent.py                # Master orchestrator: repo discovery, dispatch, aggregation
├── requirements.txt               # Python package dependencies
├── config/
│   ├── master.yaml                # Global execution parameters, activity window, scoring weights
│   ├── projects.yaml              # Per-repository metadata (budgets, headcount, timesheet codes)
│   ├── standard.yaml              # Engineering rules (required env artifacts, required scanners)
│   └── integrations.yaml          # API endpoint settings & auth specifications
├── core/
│   ├── __init__.py                # Core package initialization
│   ├── schema.py                  # Pydantic v2 schemas for all hygiene dimensions and reports
│   └── checks/                    # Deterministic check modules
│       ├── __init__.py            # Checks package initialization
│       ├── environment.py         # Infrastructure & environment separation checks
│       ├── ci_gates.py            # CI/CD branch protection & pipeline gate checks
│       ├── signoff.py             # UAT signoff verification (repo artifact & email scan)
│       ├── cost.py                # Headcount, sprint rate, and budget variance calculation
│       ├── security.py            # Security tooling and static scanner inspection
│       └── deploy_history.py      # Production deployment audit vs. signoff timestamp gaps
├── sub_agents/
│   ├── __init__.py                # Sub-agents package initialization
│   ├── observer_agent.py          # Read-only evaluation sub-agent
│   └── enforcer_agent.py          # Active CI gating sub-agent
├── hermes/
│   └── skill.md                   # Hermes agent skill definition & operational boundaries
└── reports/                       # Generated audit reports
    ├── aggregate.json             # Cross-project aggregated dashboard summary
    ├── mock-org_active-project-1.json
    └── mock-org_active-project-2.json
```

---

## 4. Data Contracts & Schemas

The system uses **Pydantic v2** (`core/schema.py`) to guarantee strict typing, validation, and JSON serialization.

### Domain Schema (`core/schema.py`)

#### 1. Status Literals
- Standard checks: `Literal["pass", "fail", "undefined_standard"]`
- Signoff checks: `Literal["pass", "fail", "unverifiable"]`
- Signoff method: `Literal["repo_artifact", "email_parsed", "none"]`

#### 2. Dimension Models
```python
class EnvironmentSeparation(BaseModel):
    status: Literal["pass", "fail", "undefined_standard"] = "undefined_standard"
    evidence: List[str] = Field(default_factory=list)

class CiCdGates(BaseModel):
    status: Literal["pass", "fail", "undefined_standard"] = "undefined_standard"
    evidence: List[str] = Field(default_factory=list)

class UatSprintSignoff(BaseModel):
    sprint_id: str
    status: Literal["pass", "fail", "unverifiable"] = "unverifiable"
    evidence: List[str] = Field(default_factory=list)

class UatSignoff(BaseModel):
    status: Literal["pass", "fail", "unverifiable"] = "unverifiable"
    method: Literal["repo_artifact", "email_parsed", "none"] = "none"
    evidence: List[str] = Field(default_factory=list)
    per_sprint: List[UatSprintSignoff] = Field(default_factory=list)

class CostTracking(BaseModel):
    status: Literal["pass", "fail", "undefined_standard"] = "undefined_standard"
    headcount: int = 0
    sprint_duration_days: int = 14
    estimated_cost: float = 0.0
    budget: Optional[float] = None
    variance_pct: Optional[float] = None

class SecurityBaseline(BaseModel):
    status: Literal["pass", "fail", "undefined_standard"] = "undefined_standard"
    evidence: List[str] = Field(default_factory=list)

class DeploymentHistory(BaseModel):
    last_deploy: Optional[datetime] = None
    last_signoff_before_deploy: Optional[datetime] = None
    gap_flag: bool = False
```

#### 3. Container & Report Models
```python
class Dimensions(BaseModel):
    environment_separation: EnvironmentSeparation = Field(default_factory=EnvironmentSeparation)
    ci_cd_gates: CiCdGates = Field(default_factory=CiCdGates)
    uat_signoff: UatSignoff = Field(default_factory=UatSignoff)
    cost_tracking: CostTracking = Field(default_factory=CostTracking)
    security_baseline: SecurityBaseline = Field(default_factory=SecurityBaseline)
    deployment_history: DeploymentHistory = Field(default_factory=DeploymentHistory)

class Overall(BaseModel):
    hygiene_score: float = 0.0
    enforcement_eligible: bool = False

class ProjectHygieneReport(BaseModel):
    id: str
    repo_url: str
    last_evaluated: datetime
    dimensions: Dimensions = Field(default_factory=Dimensions)
    overall: Overall = Field(default_factory=Overall)
```

### Report JSON Specifications

#### Per-Project Report (`reports/<sanitized_repo_id>.json`)
```json
{
  "id": "mock-org/active-project-1",
  "repo_url": "https://github.com/mock-org/active-project-1",
  "last_evaluated": "2026-09-05T17:41:04.729055",
  "dimensions": {
    "environment_separation": {
      "status": "undefined_standard",
      "evidence": ["Environment standards check not implemented yet (stubbed)"]
    },
    "ci_cd_gates": {
      "status": "undefined_standard",
      "evidence": ["CI/CD gates check not implemented yet (stubbed)"]
    },
    "uat_signoff": {
      "status": "unverifiable",
      "method": "none",
      "evidence": ["UAT signoff check not implemented yet (stubbed)"],
      "per_sprint": []
    },
    "cost_tracking": {
      "status": "pass",
      "headcount": 5,
      "sprint_duration_days": 14,
      "estimated_cost": 56000.0,
      "budget": 150000.0,
      "variance_pct": -62.66666666666667
    },
    "security_baseline": {
      "status": "undefined_standard",
      "evidence": ["Security baseline check not implemented yet (stubbed)"]
    },
    "deployment_history": {
      "last_deploy": "2026-09-03T17:41:04.729055",
      "last_signoff_before_deploy": "2026-08-31T17:41:04.729055",
      "gap_flag": true
    }
  },
  "overall": {
    "hygiene_score": 10.0,
    "enforcement_eligible": false
  }
}
```

#### Aggregate Report (`reports/aggregate.json`)
```json
{
  "generated_at": "2026-09-05T17:41:04.729055",
  "total_evaluated": 2,
  "projects": [
    {
      "id": "mock-org/active-project-1",
      "score": 10.0,
      "gap_flag": true,
      "variance_pct": -62.66666666666667,
      "eligible_for_enforcement": false
    },
    {
      "id": "mock-org/active-project-2",
      "score": 10.0,
      "gap_flag": false,
      "variance_pct": -57.99999999999999,
      "eligible_for_enforcement": false
    }
  ]
}
```

---

## 5. The Six Hygiene Dimensions in Detail

### 1. Environment Separation
- **Script**: `core/checks/environment.py`
- **Objective**: Ensure isolation between software execution stages (e.g., development, test/staging, and production) to prevent accidental data contamination or configuration leaks.
- **Current Behavior**: Emits `status="undefined_standard"` until file tree inspection is wired to `config/standard.yaml`.
- **Target Standards**:
  - `terraform/workspaces` or environment directories (e.g. `envs/prod`, `envs/stage`)
  - `k8s/namespaces` manifests
  - Docker Compose environment overrides (`docker-compose.staging.yml`, `docker-compose.prod.yml`)
- **Pass Criteria**: Presence of verified infrastructure configuration defining distinct target environments.

### 2. CI/CD Gates
- **Script**: `core/checks/ci_gates.py`
- **Objective**: Verify that repository merges are protected by automated CI pipelines and mandatory status checks.
- **Current Behavior**: Emits `status="undefined_standard"` stub.
- **Target Standards**:
  - Repository has branch protection rules on `main` / `master`.
  - Required reviews (minimum 1 approval).
  - Status checks must pass before merging (linting, automated test suites, build completion).

### 3. UAT Sign-off
- **Script**: `core/checks/signoff.py`
- **Objective**: Verify business acceptance testing was performed and formally approved before code is deployed.
- **Current Behavior**: Emits `status="unverifiable"`, `method="none"`.
- **Confidence Tiers**:
  - `repo_artifact` (Highest Confidence): An explicit sign-off artifact checked into source control (e.g. `docs/signoffs/sprint-12.md` containing sign-off metadata, reviewer IDs, and dates).
  - `email_parsed` (Transitional Confidence): An approved sign-off email detected in the release mailbox matching `mailbox_pattern` from `config/projects.yaml`.
  - `none`: No signoff evidence found.

### 4. Cost Tracking & Variance Analysis
- **Script**: `core/checks/cost.py`
- **Objective**: Monitor project labor burn rate against assigned budget.
- **Implementation**:
  $$\text{Estimated Cost} = \text{Headcount} \times \text{Sprint Duration (Days)} \times \text{Average Daily Rate (\$800)}$$
  $$\text{Variance \%} = \frac{\text{Estimated Cost} - \text{Budget}}{\text{Budget}} \times 100$$
- **Behavior**:
  - If `headcount > 0`: `status="pass"`
  - If `headcount == 0` or missing: `status="undefined_standard"`
  - Calculates variance percentage against the project budget defined in `config/projects.yaml`.

### 5. Security Baseline
- **Script**: `core/checks/security.py`
- **Objective**: Guarantee static application security testing (SAST) and software supply chain dependency scanning are active.
- **Target Standards** (defined in `config/standard.yaml`):
  - Dependabot (`.github/dependabot.yml`)
  - Snyk (`.snyk` or GitHub Action workflow)
  - Trivy container scanning (`trivy.yaml` or CI workflow step)
- **Pass Criteria**: At least one configured scanner discovered in the repository tree.

### 6. Deployment History & Gap Flag Detection
- **Script**: `core/checks/deploy_history.py`
- **Objective**: Compare production deployment timestamps with UAT sign-off timestamps to catch unapproved releases.
- **Logic**:
  $$\text{gap\_flag} = \text{True} \iff \text{Deploy occurred without verified preceding sign-off in the sprint window}$$
- **Severity**: Repositories with `gap_flag: true` represent critical compliance and governance risks.

---

## 6. Scoring Engine & Promotion Mechanics

### Weighted Scoring Formula

The overall project hygiene score is calculated as a normalized value out of 100 in `sub_agents/observer_agent.py`:

$$\text{Score} = \sum (\text{Dimension Score} \times \text{Configured Weight})$$

Where each dimension yields $100.0$ for `pass` and $0.0$ for `fail`, `undefined_standard`, or `unverifiable`.

| Dimension | Default Weight (`config/master.yaml`) | Max Contribution |
| :--- | :---: | :---: |
| **UAT Sign-off** | 0.4 (40%) | 40.0 pts |
| **Environment Separation** | 0.2 (20%) | 20.0 pts |
| **Security Baseline** | 0.2 (20%) | 20.0 pts |
| **CI/CD Gates** | 0.1 (10%) | 10.0 pts |
| **Cost Tracking** | 0.1 (10%) | 10.0 pts |
| **Total** | **1.0 (100%)** | **100.0 pts** |

### Sorting & Prioritization Matrix

In `master_agent.py`, aggregate reports sort projects using a triple-priority key:

```python
aggregate["projects"].sort(key=lambda x: (
    -int(x["gap_flag"]),             # 1. Projects with gap_flag=True come first
    -(x["variance_pct"] or 0),       # 2. Highest budget overrun percentage
    x["score"]                       # 3. Lowest hygiene score
))
```

This guarantees that projects posing immediate governance risks (unauthorized deployments or massive budget overruns) immediately float to the top of executive reporting.

### Enforcement Eligibility & Promotion Criteria

The system supports gradual organizational adoption via **Phase 3 Promotion Rules**:
- **Eligibility Threshold**:
  1. `environment_separation.status == "pass"`
  2. `uat_signoff.method == "repo_artifact"`
  3. Maintained across consecutive sprint cycles without regressions.
- **Workflow**:
  - The `ObserverAgent` evaluates eligibility and marks `eligible_for_enforcement = True`.
  - The Hermes agent or human lead reviews the candidate.
  - Once approved, the project is enrolled in `EnforcerAgent` CI gating.

---

## 7. Configuration System

### `config/master.yaml`
Controls system-wide evaluation bounds and scoring weights:
```yaml
activity_window_days: 60       # Repos with no commits in 60 days are marked dormant
parallelism: 4                 # Concurrency pool for subagent execution
default_sprint_duration_days: 14 # Standard sprint length for cost estimation
weights:
  environment_separation: 0.2
  ci_cd_gates: 0.1
  uat_signoff: 0.4
  security_baseline: 0.2
  cost_tracking: 0.1
```

### `config/projects.yaml`
Stores per-project metadata required for external system correlation:
```yaml
repos:
  "mock-org/active-project-1":
    timesheet_code: "PRJ-001"
    mailbox_pattern: "subject:PRJ-001 signoff"
    budget: 150000.0
    headcount: 5
  "mock-org/active-project-2":
    timesheet_code: "PRJ-002"
    mailbox_pattern: "subject:PRJ-002 signoff"
    budget: 80000.0
    headcount: 3
```

### `config/standard.yaml`
Defines verifiable technical standards:
```yaml
environment_separation:
  required_artifacts:
    - "terraform/workspaces"
    - "k8s/namespaces"
    - "docker-compose.*.yml"

security_baseline:
  required_scanners:
    - "dependabot"
    - "snyk"
    - "trivy"
```

### `config/integrations.yaml`
Contains endpoint configurations for enterprise tools:
```yaml
git_provider:
  type: "github"               # "github", "gitlab", or "azure_repos"
  api_url: "https://api.github.com"
  # Authentication via environment variable: GIT_TOKEN

timesheet_system:
  type: "zoho_people"
  api_url: "https://people.zoho.com/api"
  # Authentication via environment variable: TIMESHEET_TOKEN

email_scanner:
  type: "office365"
  mailbox: "releases@navadhiti.com"
  # Authentication via environment variable: EMAIL_CLIENT_SECRET
```

---

## 8. End-to-End Execution Flow

When executing `python master_agent.py`:

```
+--------------------------------------------------------------------------+
| 1. MASTER AGENT INITIALIZATION                                           |
|    - Load config/master.yaml                                             |
|    - Set activity_window_days (default: 60)                              |
+--------------------------------------------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
| 2. REPOSITORY DISCOVERY & FILTERING                                      |
|    - discover_repos() fetches repo catalog with last_commit_date         |
|    - Calculate: days_since_commit = (now - last_commit_date).days        |
|    - If days_since_commit <= activity_window_days: In Scope              |
|    - Else: Excluded (logged as dormant)                                  |
+--------------------------------------------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
| 3. SUBAGENT DISPATCH (ObserverAgent per In-Scope Repo)                   |
|    - Load project metadata from config/projects.yaml                     |
|    - Load standards from config/standard.yaml                            |
|    - Run check_environment_separation()                                 |
|    - Run check_ci_gates()                                                |
|    - Run check_uat_signoff()                                             |
|    - Run check_cost()                                                    |
|    - Run check_security_baseline()                                       |
|    - Run check_deploy_history()                                          |
|    - Compute weighted hygiene_score                                      |
|    - Evaluate enforcement_eligible flag                                  |
+--------------------------------------------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
| 4. REPORT PERSISTENCE & AGGREGATION                                      |
|    - Write reports/<repo_id>.json via Pydantic model_dump_json()         |
|    - Form aggregate list with gap_flag, variance_pct, score              |
|    - Sort aggregate list (Gap flags first, High variance, Low score)     |
|    - Write reports/aggregate.json                                        |
+--------------------------------------------------------------------------+
```

---

## 9. Step-by-Step Implementation & Productionization Guide

The repository currently provides a functional Milestone 1 baseline with simulated live checks (`cost`, `deploy_history`) and stubbed checks. Here is how to implement each component for full production deployment.

### Phase 1: Real Git Provider Integration

Replace the mock `discover_repos()` in `master_agent.py` with real API calls using `requests`:

```python
import os
import requests
from datetime import datetime

def discover_github_repos(api_url: str, token: str, org: str):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    repos = []
    page = 1
    while True:
        resp = requests.get(
            f"{api_url}/orgs/{org}/repos?per_page=100&page={page}",
            headers=headers
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        for item in batch:
            # Parse pushed_at date
            pushed_at = datetime.fromisoformat(item["pushed_at"].replace("Z", "+00:00"))
            repos.append({
                "id": item["full_name"],
                "url": item["html_url"],
                "last_commit_date": pushed_at.replace(tzinfo=None)
            })
        page += 1
    return repos
```

### Phase 2: Implementing Real File/Tree Checks

Update `core/checks/environment.py` and `core/checks/security.py` to inspect repository contents:

#### Option A: Local Clones
```python
import os
import glob
from core.schema import EnvironmentSeparation

def check_environment_separation(repo_id: str, local_repo_dir: str, standard: dict) -> EnvironmentSeparation:
    evidence = []
    patterns = standard.get("environment_separation", {}).get("required_artifacts", [])
    
    for pat in patterns:
        matches = glob.glob(os.path.join(local_repo_dir, pat))
        if matches:
            evidence.append(f"Found artifact matching '{pat}': {matches[0]}")
            
    if evidence:
        return EnvironmentSeparation(status="pass", evidence=evidence)
    return EnvironmentSeparation(
        status="fail",
        evidence=["No environment separation artifacts found matching standards"]
    )
```

#### Option B: Remote GitHub Git Tree API
Use GitHub's Trees API (`GET /repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1`) to evaluate file paths without cloning the full repository to disk.

### Phase 3: Real Timesheet & Zoho People Integration

In `core/checks/cost.py`, wire live API calls:
```python
import os
import requests
from core.schema import CostTracking

def check_cost_live(repo_id: str, project_meta: dict, sprint_duration_days: int = 14) -> CostTracking:
    timesheet_code = project_meta.get("timesheet_code")
    budget = project_meta.get("budget")
    token = os.getenv("TIMESHEET_TOKEN")
    
    if not timesheet_code or not token:
        # Fall back to metadata or undefined
        headcount = project_meta.get("headcount", 0)
        return CostTracking(
            status="undefined_standard" if headcount == 0 else "pass",
            headcount=headcount,
            budget=budget
        )
        
    # Example Zoho People API query:
    resp = requests.get(
        f"https://people.zoho.com/api/timetracker/gettimesheetentries",
        params={"jobCode": timesheet_code},
        headers={"Authorization": f"Zoho-oauthtoken {token}"}
    )
    # Parse total recorded hours and distinct active heads
    # ...
```

### Phase 4: Office365 / Graph API Email Sign-off Scanning

In `core/checks/signoff.py`, implement Microsoft Graph API scanning for transitional UAT signoffs:
```python
import os
import requests
from core.schema import UatSignoff

def scan_signoff_mailbox(mailbox_pattern: str) -> bool:
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("EMAIL_CLIENT_SECRET")
    tenant_id = os.getenv("AZURE_TENANT_ID")
    
    # 1. Acquire OAuth2 Token via MSAL
    # 2. Query /v1.0/users/{mailbox}/messages?$search="{mailbox_pattern}"
    # 3. Check for positive approval keyword in message body ("Approved", "UAT Sign-off Granted")
    pass
```

### Phase 5: Implementing `EnforcerAgent` as a CI/CD Gate

Implement `sub_agents/enforcer_agent.py` with exit codes for CI:
```python
import sys
from sub_agents.observer_agent import ObserverAgent

class EnforcerAgent:
    def __init__(self, repo_id: str, repo_url: str, config: dict):
        self.repo_id = repo_id
        self.repo_url = repo_url
        self.config = config
        
    def run(self) -> int:
        observer = ObserverAgent(self.repo_id, self.repo_url, self.config)
        report = observer.run()
        
        failures = []
        # Check blocking criteria:
        if report.dimensions.environment_separation.status != "pass":
            failures.append("Environment separation check failed.")
        if report.dimensions.ci_cd_gates.status != "pass":
            failures.append("CI/CD gates check failed.")
        if report.dimensions.uat_signoff.status != "pass":
            failures.append("UAT sign-off missing or invalid.")
        if report.dimensions.deployment_history.gap_flag:
            failures.append("Deployment history gap flag detected.")
            
        if failures:
            print(f"❌ ENFORCER GATE REJECTED MERGE for {self.repo_id}:")
            for f in failures:
                print(f"  - {f}")
            return 1
            
        print(f"✅ ENFORCER GATE PASSED for {self.repo_id}.")
        return 0

if __name__ == "__main__":
    agent = EnforcerAgent(sys.argv[1], sys.argv[2], {})
    sys.exit(agent.run())
```

#### GitHub Action Workflow Example (`.github/workflows/hygiene-gate.yml`):
```yaml
name: Hygiene Enforcer Gate
on:
  pull_request:
    branches: [main, master]

jobs:
  enforce:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install Hygiene Dependencies
        run: pip install -r requirements.txt
      - name: Run Enforcer
        run: |
          python -m sub_agents.enforcer_agent "${{ github.repository }}" "${{ github.server_url }}/${{ github.repository }}"
```

---

## 10. Operations, Monitoring & Runbook

### Running on a Schedule (Cron)
To run the evaluation daily at midnight and pipe output to a log file:
```bash
0 0 * * * cd /opt/hygiene && /opt/hygiene/venv/bin/python master_agent.py >> /var/log/hygiene.log 2>&1
```

### Adding a New Project
1. Open `config/projects.yaml`.
2. Add the repository identifier under `repos`:
   ```yaml
   repos:
     "org/my-new-service":
       timesheet_code: "SRV-042"
       mailbox_pattern: "subject:SRV-042 signoff"
       budget: 120000.0
       headcount: 4
   ```
3. Run `python master_agent.py` to trigger immediate evaluation.

### Modifying Hygiene Dimensions & Weights
Edit `config/master.yaml` under `weights`:
- Weights must sum to `1.0`.
- To increase the penalty for missing security scans, increase `security_baseline` (e.g., from `0.2` to `0.35`) and adjust other dimensions accordingly.

---

## 11. Troubleshooting & FAQ

#### Q1: Why is my project not showing up in `reports/aggregate.json`?
**A**: Check the project's last commit timestamp. If the last commit is older than `activity_window_days` (default 60 days in `config/master.yaml`), it is filtered out as dormant. You can increase `activity_window_days` or pass an override.

#### Q2: Why are scores capped at 10.0 in Milestone 1?
**A**: In the Milestone 1 baseline, 4 out of the 5 weighted dimensions (`environment_separation`, `ci_cd_gates`, `uat_signoff`, `security_baseline`) are stubbed as `undefined_standard` or `unverifiable` (yielding 0 points). Only `cost_tracking` (10% weight) passes with 100 points, yielding $100 \times 0.1 = 10.0$ points. As checks are implemented in Phases 1–4, scores will reflect real evaluation results.

#### Q3: What is the difference between `undefined_standard` and `fail`?
**A**: `undefined_standard` indicates that the organization has not defined measurable criteria for that dimension in `config/standard.yaml`, or that the check has not yet been implemented. `fail` means the standard exists, the check ran, and the repository did not meet the requirement.

#### Q4: How is a gap flag triggered?
**A**: A gap flag (`gap_flag: true`) is raised when a deployment to production is recorded in CI/CD or release tags, but no preceding approved UAT signoff artifact was found within the sprint deployment window.
