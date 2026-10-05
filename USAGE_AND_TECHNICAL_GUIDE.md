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
5. [The Seven Hygiene Dimensions in Detail](#5-the-seven-hygiene-dimensions-in-detail)
   - [1. Environment Separation](#1-environment-separation)
   - [2. CI/CD Gates](#2-cicd-gates)
   - [3. UAT Sign-off](#3-uat-sign-off)
   - [4. Cost Tracking & Variance Analysis](#4-cost-tracking--variance-analysis)
   - [5. Security Baseline](#5-security-baseline)
   - [6. Deployment History & Gap Flag Detection](#6-deployment-history--gap-flag-detection)
   - [7. Traceability (Feature → Issue → Ticket)](#7-traceability-feature--issue--ticket)
6. [Scoring Engine & Promotion Mechanics](#6-scoring-engine--promotion-mechanics)
   - [Weighted Scoring Formula](#weighted-scoring-formula)
   - [Weight-Sum Validation](#weight-sum-validation)
   - [Sorting & Prioritization Matrix](#sorting--prioritization-matrix)
   - [Enforcement Eligibility, Promotion Streaks & Persisted State](#enforcement-eligibility-promotion-streaks--persisted-state)
   - [Sprint Calendar](#sprint-calendar)
   - [Report History Archive](#report-history-archive)
7. [Configuration System](#7-configuration-system)
   - [`config/master.yaml`](#configmasteryaml)
   - [`config/projects.yaml`](#configprojectsyaml)
   - [`config/standard.yaml`](#configstandardyaml)
   - [`config/integrations.yaml`](#configintegrationsyaml)
8. [End-to-End Execution Flow](#8-end-to-end-execution-flow)
9. [Implementation Status & Remaining Productionization](#9-implementation-status--remaining-productionization)
   - [Phase 3: Real Timesheet & Zoho People Integration](#phase-3-real-timesheet--zoho-people-integration)
   - [Phase 4: Office365 / Graph API Email Sign-off Scanning](#phase-4-office365--graph-api-email-sign-off-scanning)
   - [Phase 6: GitLab / Azure Repos Providers](#phase-6-gitlab--azure-repos-providers)
10. [Operations, Monitoring & Runbook](#10-operations-monitoring--runbook)
    - [10.1 Setting Up a Clone](#101-setting-up-a-clone)
    - [10.2 Running the Evaluation](#102-running-the-evaluation)
    - [10.3 Running on a Schedule (Cron)](#103-running-on-a-schedule-cron)
    - [10.4 Running the Test Suite](#104-running-the-test-suite)
    - [10.5 Verifying This Repository's Own Baseline](#105-verifying-this-repositorys-own-baseline)
    - [10.6 Running the Enforcer CI Gate](#106-running-the-enforcer-ci-gate)
    - [10.7 Adding a New Project](#107-adding-a-new-project)
    - [10.8 Modifying Hygiene Dimensions & Weights](#108-modifying-hygiene-dimensions--weights)
    - [10.9 Reading Promotion State](#109-reading-promotion-state)
11. [Troubleshooting & FAQ](#11-troubleshooting--faq)

---

## 1. Executive Summary & System Purpose

The **Navadhiti Project Hygiene System** is an automated governance and engineering health assessment framework. Modern software engineering organizations often face visibility gaps across projects:
- Untracked deployments released to production without verified User Acceptance Testing (UAT).
- Missing environment segregation between staging, development, and production.
- Security scanners neglected or not integrated into pull request pipelines.
- Labor cost overruns going undetected until accounting end-of-month reconciliations.
- Work merged or deployed with no recorded link back to why it was authorized (no issue, no ticket).

The Hygiene System solves these challenges through deterministic inspection scripts paired with an intelligent subagent architecture. It audits active repositories against engineering standards, detects compliance gaps, tracks budget-to-actual cost variance, verifies bidirectional traceability (feature → issue → ticket), and calculates a normalized 0–100 **Hygiene Score**.

The system operates under strict separation of concerns:
1. **Deterministic Inspection (`core/checks/`)**: Pure, reproducible code checks that evaluate objective criteria and emit structured data. Since Milestone 2, these checks read live systems of record (GitHub REST APIs) rather than mocks.
2. **Orchestration & Scoring (`MasterAgent` & `ObserverAgent`)**: Coordinates repository discovery, runs checks across active projects, and computes weighted metrics.
3. **Continuous Enforcement (`EnforcerAgent`)**: A gate that runs in pull-request / CI pipelines and blocks merges that violate baseline hygiene standards (exit code 0/1).
4. **Agentic Interpretation (`hermes/skill.md`)**: An AI agent layer that synthesizes aggregate findings into executive narratives without hallucinating or overriding deterministic check statuses.

**Milestone 2 status:** all six original dimensions read real GitHub state (Trees API, Branch Protection API, Releases/tags), UAT signoff has its durable repo-artifact tier, a seventh dimension (Traceability) is live, sprint boundaries are calendar-driven, promotion streaks persist across runs, and every run's aggregate report is archived for trend narrative.

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
             | Live repo discovery (A1)            | Output
             v                                     v
   +--------------------+                 +------------------------+
   | In-Scope Repos     |                 |  reports/              |
   | (Active, window)   |                 |  aggregate.json        |
   +---------+----------+                 |  history/<ts>-*.json   |
             |                            |  promotion_state.json  |
             +-------+                    +------------------------+
             |       |
             v       v (CI gate)
   +---------------+  +----------------+
   | ObserverAgent |  | EnforcerAgent  |
   +-------+-------+  +----------------+
           |  Runs 7 deterministic checks
           |
           +---> core/checks/environment.py      (Trees API)
           +---> core/checks/ci_gates.py         (Branch Protection API)
           +---> core/checks/signoff.py          (signoff artifacts)
           +---> core/checks/cost.py
           +---> core/checks/security.py         (Trees API, shared)
           +---> core/checks/deploy_history.py   (Releases/tags API)
           +---> core/checks/traceability_issue.py   (Pulls/Issues API)
           +---> core/checks/traceability_ticket.py  (Issues + ticket API)
```

Shared infrastructure the checks depend on:
- `core/git_providers.py` — provider-agnostic repo discovery (`discover_repos(provider_config) -> List[RepoInfo]`). GitHub is implemented; GitLab/Azure Repos can be added as new provider classes behind the same interface without touching `master_agent.py`.
- `core/github_client.py` — one authenticated REST client per run. The recursive git-tree call is cached per repo, so the environment, security, and signoff checks share a **single** Trees API round-trip per repo per run.
- `core/sprint.py` — the sprint calendar (B1). Every check that needs a sprint id or sprint window goes through it.
- `core/promotion.py` — the only cross-run state (`reports/promotion_state.json`).

### Observer Mode vs. Enforcer Mode

| Dimension | **Observer Mode (`ObserverAgent`)** | **Enforcer Mode (`EnforcerAgent`)** |
| :--- | :--- | :--- |
| **Execution Trigger** | Scheduled run (e.g. daily/weekly cron or CLI) | Git push / Pull Request CI trigger |
| **Target Scope** | All active repositories across the organization | Single repository in pull-request context |
| **System Impact** | Read-only; generates reports and metrics | Gating; exits with code `0` (pass) or `1` (fail) |
| **Promotion State** | Tracks streaks, recommends enforcement eligibility | Blocks merges for promoted projects and new repositories |
| **Output** | Detailed JSON reports per repo + aggregate | Status checks, PR comments, build logs |

### Hermes Agent Integration Layer

The Hermes skill (`hermes/skill.md`) serves as the orchestration and executive judgment layer when run inside an autonomous agent harness.
- **Strict Boundary**: The agent *never* guesses a pass/fail status, *never* fabricates cost figures or budgets, and *never* overrides deterministic script results.
- **Narrative Role**: The agent identifies macro trends (e.g., *"3 out of 10 active projects account for 85% of budget overruns"*, or *"gap flags clustered in the two weeks after the v2.4 cut"*). The `reports/history/` archive (B5) exists precisely for this: the skill compares snapshots at read time; this codebase only archives, never diffs.
- **Promotion Recommender**: Flags projects that meet the promotion threshold (streak in `reports/promotion_state.json`) to human leads for CI enforcement activation.

---

## 3. Repository Structure & Codebase Map

```
navadhiti_hygiene/
├── README.md                      # Quickstart and project summary
├── USAGE_AND_TECHNICAL_GUIDE.md   # Complete technical and operational guide (this file)
├── CONFIDENTIALITY.md             # Recorded data-handling decision and policy
├── NOTICE                         # Internal-use notice (no license terms)
├── master_agent.py                # Master orchestrator: discovery, dispatch, aggregation
├── requirements.txt               # Python dependencies: runtime + test tooling
├── pytest.ini                     # Declared test runner configuration
├── .gitignore                     # Environment, bytecode, credentials, caches, reports/
├── tools/
│   └── verify_baseline.py         # Repository's own baseline verifier (stdlib only)
├── .github/
│   ├── dependabot.yml             # Weekly pip dependency update scanning
│   └── workflows/
│       └── baseline.yml           # Advisory pull-request baseline run (non-blocking)
├── .pre-commit-config.yaml        # Commit-time detect-secrets hook, scoped to config/*.yaml
├── .secrets.baseline              # Reviewed suppressions + detector plugins
├── config/
│   ├── master.yaml                # Window, weights, sprint calendar, promotion thresholds
│   ├── projects.yaml              # Per-repo metadata + activity-window overrides
│   ├── standard.yaml              # Engineering rules (env artifacts, scanners, signoff, traceability)
│   └── integrations.yaml          # API endpoints & auth specs (git provider, ticketing, email)
├── core/
│   ├── __init__.py
│   ├── schema.py                  # Pydantic v2 schemas for all hygiene dimensions and reports
│   ├── git_providers.py           # Repo discovery: provider interface + GitHub implementation (A1)
│   ├── github_client.py           # Shared REST client; caches the recursive tree per repo
│   ├── sprint.py                  # Sprint calendar: date -> sprint_id (B1)
│   ├── promotion.py               # Promotion streak persistence (B2)
│   └── checks/                    # Deterministic check modules
│       ├── __init__.py
│       ├── tree_utils.py          # Glob/dir-prefix matching over the cached tree
│       ├── environment.py         # Env separation via Trees API (A2)
│       ├── ci_gates.py            # Branch Protection API (A3)
│       ├── signoff.py             # UAT signoff repo-artifact tier (A5)
│       ├── cost.py                # Headcount, sprint rate, budget variance
│       ├── security.py            # Scanner artifacts via shared tree (A4)
│       ├── deploy_history.py      # Releases/tags timestamps vs signoff gaps (B3)
│       ├── traceability_issue.py  # Feature -> issue traceability (C2)
│       └── traceability_ticket.py # Issue -> ticket traceability (C3)
├── sub_agents/
│   ├── __init__.py
│   ├── observer_agent.py          # Read-only evaluation sub-agent
│   └── enforcer_agent.py          # Active CI gating sub-agent (C4)
├── tests/
│   ├── test_hygiene.py            # Offline smoke tests (mocked GitHub API)
│   └── test_verify_baseline.py    # Baseline verifier tests (fixture git repositories)
├── hermes/
│   └── skill.md                   # Hermes agent skill definition & operational boundaries
└── reports/                       # Generated audit reports — gitignored, written at runtime
    ├── aggregate.json             # Cross-project aggregated dashboard summary
    ├── history/                   # B5: one archived aggregate per run
    ├── promotion_state.json       # B2: the only persisted cross-run state
    └── <sanitized_repo_id>.json   # Per-repo deep reports
```

---

## 4. Data Contracts & Schemas

The system uses **Pydantic v2** (`core/schema.py`) to guarantee strict typing, validation, and JSON serialization.

### Domain Schema (`core/schema.py`)

#### 1. Status Literals
- Standard checks: `Literal["pass", "fail", "undefined_standard"]`
- Signoff checks: `Literal["pass", "fail", "unverifiable"]`
- Signoff method: `Literal["repo_artifact", "email_parsed", "none"]`
- Deploy markers: `Literal["releases", "tags", "none"]`
- Feature-trace methods: `Literal["pr_linked", "commit_linked", "none"]`

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
    status: Literal["pass", "fail", "undefined_standard"] = "undefined_standard"
    method: Literal["releases", "tags", "none"] = "none"
    last_deploy: Optional[datetime] = None
    last_signoff_before_deploy: Optional[datetime] = None
    gap_flag: bool = False
    evidence: List[str] = Field(default_factory=list)

class FeatureIssueTrace(BaseModel):
    status: Literal["pass", "fail", "undefined_standard"] = "undefined_standard"
    method: Literal["pr_linked", "commit_linked", "none"] = "none"
    evidence: List[str] = Field(default_factory=list)
    unlinked_count: int = 0          # merged PRs/commits with no issue reference
    total_checked: int = 0

class IssueTicketTrace(BaseModel):
    status: Literal["pass", "fail", "undefined_standard"] = "undefined_standard"
    evidence: List[str] = Field(default_factory=list)
    unlinked_count: int = 0          # issues with no external ticket reference
    total_checked: int = 0

class Traceability(BaseModel):
    feature_to_issue: FeatureIssueTrace = Field(default_factory=FeatureIssueTrace)
    issue_to_ticket: IssueTicketTrace = Field(default_factory=IssueTicketTrace)
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
    traceability: Traceability = Field(default_factory=Traceability)

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
Illustrative output against a repo with real GitHub state (evidence truncated here; the real files carry it in full):

```json
{
  "id": "navadhiti/service-a",
  "repo_url": "https://github.com/navadhiti/service-a",
  "last_evaluated": "2026-09-05T18:13:57.061253",
  "dimensions": {
    "environment_separation": {
      "status": "pass",
      "evidence": [
        "Found environment artifact matching 'terraform/workspaces': terraform/workspaces/prod.tf",
        "No artifact matching required pattern 'k8s/namespaces'",
        "No artifact matching required pattern 'docker-compose.*.yml'"
      ]
    },
    "ci_cd_gates": {
      "status": "pass",
      "evidence": [
        "Branch protection enabled on default branch 'main'",
        "Required reviews enforced: 1 approving review(s) required before merge",
        "Required status checks present: ci"
      ]
    },
    "uat_signoff": {
      "status": "pass",
      "method": "repo_artifact",
      "evidence": [
        "1 signoff artifact(s) found matching 'docs/signoffs/*.md'",
        "Current sprint sprint-2026-08-24 covered by 'docs/signoffs/sprint-2026-08-24.md' (reviewer: Jane Doe (jane@navadhiti.com), date: 2026-09-03)"
      ],
      "per_sprint": [
        {
          "sprint_id": "sprint-2026-08-24",
          "status": "pass",
          "evidence": ["artifact 'docs/signoffs/sprint-2026-08-24.md', reviewer: Jane Doe (jane@navadhiti.com), date: 2026-09-03"]
        }
      ]
    },
    "cost_tracking": {
      "status": "undefined_standard",
      "headcount": 0,
      "sprint_duration_days": 14,
      "estimated_cost": 0.0,
      "budget": null,
      "variance_pct": null
    },
    "security_baseline": {
      "status": "pass",
      "evidence": ["Scanner 'dependabot' present: '.github/dependabot.yml' matches pattern '.github/dependabot.yml'"]
    },
    "deployment_history": {
      "status": "pass",
      "method": "releases",
      "last_deploy": "2026-09-04T12:00:00",
      "last_signoff_before_deploy": "2026-09-03T00:00:00",
      "gap_flag": false,
      "evidence": [
        "Last deploy from latest published GitHub release at 2026-09-04T12:00:00",
        "Deploy on 2026-09-04 covered by signoff 'docs/signoffs/sprint-2026-08-24.md' dated 2026-09-03 (sprint window sprint-2026-08-24: 2026-08-24..2026-09-06)"
      ]
    },
    "traceability": {
      "feature_to_issue": {
        "status": "fail",
        "method": "pr_linked",
        "evidence": [
          "PR #12: linked to issue #34",
          "PR #13: UNLINKED — no issue reference (keyword 'Closes #N' / 'Fixes #N' / 'Resolves #N' or issue URL)",
          "UNLINKED PRs in sprint sprint-2026-08-24: #13",
          "1/2 merged PR(s) into 'main' in sprint sprint-2026-08-24 traced to a GitHub issue"
        ],
        "unlinked_count": 1,
        "total_checked": 2
      },
      "issue_to_ticket": {
        "status": "undefined_standard",
        "evidence": ["No ticketing integration configured in config/integrations.yaml (add a ticketing_system section) — issue-to-ticket traceability standard is not yet defined org-wide"],
        "unlinked_count": 0,
        "total_checked": 0
      }
    }
  },
  "overall": {
    "hygiene_score": 90.0,
    "enforcement_eligible": false
  }
}
```

#### Aggregate Report (`reports/aggregate.json`)
```json
{
  "generated_at": "2026-09-05T18:13:57.080510",
  "total_evaluated": 2,
  "weight_warnings": [
    "Traceability dimension is live but has no configured weight; the scoring formula treats it as 0.0 until a human updates config/master.yaml. Suggested starting value: 0.10 (10%), taken proportionally from ci_cd_gates and cost_tracking (already the lowest-weighted dimensions). This requires explicit confirmation in config — the system never auto-rebalances weights."
  ],
  "projects": [
    {
      "id": "navadhiti/service-a",
      "score": 90.0,
      "gap_flag": false,
      "variance_pct": null,
      "eligible_for_enforcement": false,
      "qualifying_streak": 1,
      "traceability_unlinked": {
        "feature_to_issue": { "unlinked": 1, "total": 2 },
        "issue_to_ticket": { "unlinked": 0, "total": 0 }
      }
    }
  ],
  "excluded_repos": [
    { "id": "navadhiti/dormant-service", "reason": "dormant: last commit 100 days ago (window 60d)" }
  ]
}
```

Field notes:
- `weight_warnings` — surfaces config decisions requiring a human (see [Weight-Sum Validation](#weight-sum-validation)).
- `qualifying_streak` — consecutive qualifying sprints from `reports/promotion_state.json`.
- `traceability_unlinked` — real unlinked counts, per tier.
- `excluded_repos` — what discovery filtered out and why; as important as the included list.

---

## 5. The Seven Hygiene Dimensions in Detail

### 1. Environment Separation
- **Script**: `core/checks/environment.py` (live since Milestone 2)
- **Objective**: Ensure isolation between software execution stages (development, test/staging, production).
- **How it reads state**: GitHub Trees API (`GET /repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1`) — a presence check needs file paths, not a clone. The tree is cached on the shared client so this costs one round-trip per repo per run.
- **Matching**: each pattern in `standard.yaml` `environment_separation.required_artifacts` matches a tree path via glob semantics (`fnmatch`) **or** as a directory prefix (`terraform/workspaces` matches `terraform/workspaces/prod.tf`).
- **Pass criteria**: at least one required artifact pattern matched.
- **Evidence**: lists every pattern searched, what matched, and an explicit confirmation when a pattern was searched for and missing.
- **Degradation**: no `required_artifacts` configured, GitHub API failure, or a truncated tree listing (GitHub caps very large trees) → `undefined_standard`, never a guessed `fail`.

### 2. CI/CD Gates
- **Script**: `core/checks/ci_gates.py` (live since Milestone 2)
- **Objective**: Verify that merges to the default branch are protected by reviews and CI.
- **How it reads state**: GitHub Branch Protection API (`GET /repos/{owner}/{repo}/branches/{branch}/protection`) — branch protection is repo settings, not a file, so a file-tree check would be meaningless here.
- **Pass criteria** (all three required):
  1. Protection enabled on the default branch.
  2. `required_approving_review_count >= 1`.
  3. Required status checks present (non-empty `contexts` or `checks`).
- **Evidence** names exactly which requirement is missing on a fail.
- **Degradation**: the protection endpoint requires a token with administration read scope. A 403 → `undefined_standard` (we cannot distinguish "protected" from "not" without that scope, so we do not guess). A 404 → the branch is not protected → `fail`.

### 3. UAT Sign-off
- **Script**: `core/checks/signoff.py` (repo-artifact tier live since Milestone 2)
- **Objective**: Verify business acceptance testing was formally approved, from a durable artifact in source control.
- **Confidence Tiers**:
  - `repo_artifact` (highest confidence, **live**): signoff files matching `standard.yaml`'s `uat_signoff.artifact_pattern` (default `docs/signoffs/*.md`). Each artifact must contain a sprint reference the sprint calendar can resolve (`sprint_id: sprint-2026-08-24`, or a bare `date:` that maps to a sprint), a reviewer identity (`reviewer:` / `approved_by:`), and a date (`date: YYYY-MM-DD`). Every parsed artifact populates a `per_sprint` entry.
  - `email_parsed` (transitional confidence, **not built** — declared fallback only): approval email in the release mailbox matching `mailbox_pattern` in `config/projects.yaml`. When no repo artifact is found, the evidence explicitly states the email tier is not implemented yet; the system never pretends an email tier ran.
  - `none`: no artifact found.
- **Status rules**:
  - `pass` — a well-formed artifact covers the current sprint.
  - `fail` — artifacts exist but none covers the current sprint; or the current-sprint artifact is malformed; or no artifacts at all (the standard is defined, the repo doesn't follow it).
  - `unverifiable` — GitHub API unavailable; cannot verify either way.
- **Signoff artifact format** (documented for teams committing these files):
  ```markdown
  # UAT Signoff

  sprint_id: sprint-2026-08-24
  reviewer: Jane Doe (jane@navadhiti.com)
  date: 2026-09-03
  ```

### 4. Cost Tracking & Variance Analysis
- **Script**: `core/checks/cost.py`
- **Objective**: Monitor project labor burn rate against assigned budget.
- **Implementation**:
  $$\text{Estimated Cost} = \text{Headcount} \times \text{Sprint Duration (Days)} \times \text{Average Daily Rate (\$800)}$$
  $$\text{Variance \%} = \frac{\text{Estimated Cost} - \text{Budget}}{\text{Budget}} \times 100$$
- **Behavior**:
  - Sprint duration now comes from the sprint calendar (B1) — per-project cadence, else the global default.
  - If `headcount > 0` (from `config/projects.yaml`): `status="pass"`.
  - If `headcount == 0` or missing: `status="undefined_standard"`.
  - Live timesheet integration (Zoho People) is still a roadmap item — see Section 9, Phase 3.

### 5. Security Baseline
- **Script**: `core/checks/security.py` (live since Milestone 2)
- **Objective**: Guarantee SAST/dependency/container scanning is configured.
- **How it reads state**: the **same cached Trees API call** as the environment check — no second round-trip per repo.
- **Scanner artifacts** (built-in defaults, overridable via `standard.yaml` `security_baseline.scanner_artifacts`):
  - dependabot → `.github/dependabot.yml`, `.github/dependabot.yaml`
  - snyk → `.snyk`, `.github/workflows/*snyk*`
  - trivy → `.trivy.yaml`, `.trivy.yml`, `.github/workflows/*trivy*`
- **Pass criteria**: at least one configured scanner discovered.
- **Evidence** confirms, per scanner, which patterns were searched and that it is missing when not found.

### 6. Deployment History & Gap Flag Detection
- **Script**: `core/checks/deploy_history.py` (live since Milestone 2)
- **Objective**: Catch production deploys that happened without a verified preceding UAT signoff.
- **`last_deploy` source** (B3 — a real system of record, never commit history):
  - **GitHub Releases API** (default): latest published, non-draft, non-prerelease release.
  - **Deployment tags** matching `deployment_history.tag_pattern` in `standard.yaml`: newest matching tag's commit date. Used when the repo has no releases, or when `deploy_marker: tags`.
  - **Neither exists** → `status: undefined_standard` ("no deployment evidence; not guessing from commit history"), `gap_flag: false`.
- **Gap rule**:
  $$\text{gap\_flag} = \text{True} \iff \text{deploy exists AND no signoff artifact is dated in } [\text{sprint start of the deploy},\ \text{deploy}]$$
  A signoff dated *after* the deploy does not clear the gap — deploying before signoff is exactly what this flag catches.
- **Honesty guard**: if signoff artifacts could not be fetched (API failure), the dimension reports `undefined_standard` and does **not** raise a gap flag it cannot prove.
- **Status**: `pass` (deploy covered), `fail` (gap flagged), `undefined_standard` (no deploy evidence / unverifiable signoff side).

### 7. Traceability (Feature → Issue → Ticket)
New dimension added in Milestone 2 (C1–C4). Same category of problem as UAT signoff — work happening with no recorded link back to why it was authorized — so it follows the same rules: read from systems of record, tiered confidence, no self-reported form.

#### 7a. Feature → Issue (`core/checks/traceability_issue.py`)
For merged PRs into the default branch within the current sprint window:
- `pass` (`method: pr_linked`): every merged PR links to a GitHub issue that **exists** (verified via the Issues API — a reference to a deleted/never-existing issue does not count). Links are recognized as:
  - linking keywords in title/body: `Closes #N`, `Fixes #N`, `Resolves #N` (case-insensitive), or
  - an explicit issue URL.
- **spec-kit route**: if `standard.yaml` declares `traceability.spec_directory` (e.g. `specs/`), a PR changing a spec file is accepted as linked when the spec file itself names/links its governing issue.
- **commit-linked fallback** (`method: commit_linked`): a PR whose title/body lack a reference still counts when its **merge commit message** carries a linking keyword. (The common squash-merge suffix `(#N)` references the *PR number*, not an issue, and is deliberately not treated as an issue link.)
- `fail` if `unlinked_count > 0`; `pass` if zero (out of `total_checked`).
- `undefined_standard` when there is no PR history to evaluate. A repo with only direct-to-main commits is explicitly flagged in evidence as worth investigating.

#### 7b. Issue → Ticket (`core/checks/traceability_ticket.py`)
Only runs when `config/integrations.yaml` declares a `ticketing_system` (analogous to `timesheet_system`). While it is not configured, the check reports `undefined_standard` — repos are never failed for a standard the org hasn't defined yet.
- For issues **closed** within the current sprint window, looks for an external ticket reference:
  - in the issue body: regex from `traceability.ticket_ref_pattern` (default `[A-Z][A-Z0-9]*-\d+` — Jira-shaped keys), or
  - in a label with prefix `traceability.ticket_label_prefix` (e.g. `ticket:NAV-101`).
- **Best-effort existence verification**: when the ticketing API is configured (`api_url` + token env var), each reference is verified with a Jira-shaped REST call (`GET {api_url}/issue/{key}`). A 404 marks the issue unlinked — a stale or typo'd reference is not a link. If the ticket API is unreachable, the check degrades to pattern-match only and notes the degraded confidence in evidence; an API outage never fails the whole check.
- Scoring shape matches 7a: `unlinked_count` / `total_checked`, `fail` if any unlinked, `pass` if zero, `undefined_standard` if no issues closed in the window.

#### Scoring & enforcement
- `traceability` is deliberately **not** in `config/master.yaml` weights yet — see [Weight-Sum Validation](#weight-sum-validation).
- The Enforcer blocks on traceability **failures for new projects only** — see Section 6.

---

## 6. Scoring Engine & Promotion Mechanics

### Weighted Scoring Formula

The overall project hygiene score is calculated in `sub_agents/observer_agent.py`:

$$\text{Score} = \sum (\text{Dimension Score} \times \text{Configured Weight})$$

Where each dimension yields $100.0$ for `pass` and $0.0$ for `fail`, `undefined_standard`, or `unverifiable`.

| Dimension | Default Weight (`config/master.yaml`) | Max Contribution |
| :--- | :---: | :---: |
| **UAT Sign-off** | 0.4 (40%) | 40.0 pts |
| **Environment Separation** | 0.2 (20%) | 20.0 pts |
| **Security Baseline** | 0.2 (20%) | 20.0 pts |
| **CI/CD Gates** | 0.1 (10%) | 10.0 pts |
| **Cost Tracking** | 0.1 (10%) | 10.0 pts |
| **Traceability** | *unset → 0.0* | 0.0 pts until configured |
| **Deployment History** | *risk flag* | unweighted; `gap_flag` drives prioritization |

### Weight-Sum Validation

On startup, the MasterAgent sums the configured weights and **fails loudly** (`SystemExit`) if they don't equal 1.0 within a small epsilon. This prevents a silently wrong score (B6).

Traceability is handled specially (C1): the tool does **not** auto-rebalance weights and does **not** edit config on its own. While `traceability` is absent from the weights, it scores as `0.0`, and every aggregate report carries a `weight_warnings` entry stating this and suggesting a starting value (0.10, taken proportionally from `ci_cd_gates` and `cost_tracking`, already the lowest-weighted). A human must confirm it in `config/master.yaml`; the moment they add `traceability: 0.10` without rebalancing, the sum becomes 1.1 and the startup validation fails loudly until the other weights are adjusted.

### Sorting & Prioritization Matrix

In `master_agent.py`, aggregate reports sort projects using a triple-priority key:

```python
aggregate["projects"].sort(key=lambda x: (
    -int(x["gap_flag"]),             # 1. Projects with gap_flag=True come first
    -(x["variance_pct"] or 0),       # 2. Highest budget overrun percentage
    x["score"]                       # 3. Lowest hygiene score
))
```

### Enforcement Eligibility, Promotion Streaks & Persisted State

`reports/promotion_state.json` (via `core/promotion.py`) is **the only state persisted across runs** — everything else stays stateless and idempotent. Per repo it tracks the consecutive **qualifying-sprint streak**:

A repo **qualifies** in a sprint when:
1. `environment_separation.status == "pass"`, AND
2. `uat_signoff.method == "repo_artifact"` with a passing current-sprint artifact, AND
3. (only when `require_traceability_for_promotion: true`) both traceability checks pass.

On each run:
- New sprint → streak increments on a qualifying run, resets to 0 otherwise.
- Same sprint re-run → recomputed idempotently from the streak as of the sprint's first evaluation (`streak_before_sprint`); a mid-sprint re-run can neither double-count nor double-reset.
- `enforcement_eligible = true` once the streak reaches `promotion_threshold_sprints` (default 3).
- The master agent flips each report's `overall.enforcement_eligible` from this persisted streak (not just the current sprint's snapshot) before reports are written.

**The Enforcer (C4).** `sub_agents/enforcer_agent.py` runs the full observer evaluation for one repo and exits 0/1 for CI. Blocking criteria: environment separation pass, CI/CD gates pass, UAT signoff pass, no deployment gap flag. **Traceability blocks new projects only**: repos created at/after `enforcement.new_project_cutoff_date` (config). Existing projects are never retroactively blocked on traceability — they take the same observe-then-promote path as everything else. A traceability check reporting `undefined_standard` never blocks (the org hasn't defined that standard yet); only a definite `fail` does. If "new project" can't be determined (no cutoff configured, API unavailable), traceability is reported but not blocking.

### Sprint Calendar

`core/sprint.py` (B1) defines sprint boundaries: a start-date anchor plus a sprint length in days. Given any date it returns the sprint it falls in. Sprint ids are date-anchored and stable: the sprint beginning 2026-08-24 is `sprint-2026-08-24`. Every check that references `sprint_id` (signoff, per-sprint history, traceability windows, promotion streaks) resolves it through this utility — none invents its own boundary logic.

Resolution order (first match wins):
1. Per-project: `config/projects.yaml` → `repos.<repo_id>.sprint_calendar.{sprint_length_days, sprint_start_date}` (teams on different cadences).
2. Global: `config/master.yaml` → `sprint_calendar.{sprint_length_days, sprint_start_date}`.
3. Fallback: `default_sprint_duration_days` (14) anchored at 2020-01-06.

Signoff artifacts may reference sprints as `sprint-2026-08-24`, `S-2026-08-24`, `Sprint 2026-08-24`, or a bare date — all normalize to the same id.

### Report History Archive

`reports/history/` is an append-only run log: each run's aggregate is snapshotted under its own `generated_at` (`reports/history/<timestamp>-aggregate.json`), and the previous run's aggregate is additionally preserved before `reports/aggregate.json` is overwritten (B5 — a belt-and-suspenders guard against deleted history or manual edits). After two runs the archive holds two snapshots; the Hermes skill's narrative layer compares them at read time — this codebase only archives, never diffs. This is what makes statements like *"gap flags clustered after the v2.4 cut"* data-grounded rather than guessed.

---

## 7. Configuration System

### `config/master.yaml`
Controls system-wide evaluation bounds, scoring weights, sprint boundaries, and promotion mechanics:
```yaml
activity_window_days: 60          # Repos with no commits in 60 days are dormant
parallelism: 4
default_sprint_duration_days: 14

weights:                          # Must sum to exactly 1.0 (validated on startup)
  environment_separation: 0.2     # traceability intentionally absent until a
  ci_cd_gates: 0.1                # human confirms its weight; scored 0.0 and
  uat_signoff: 0.4                # flagged in the report until then
  security_baseline: 0.2
  cost_tracking: 0.1

sprint_calendar:                  # B1: global default sprint boundaries
  sprint_length_days: 14
  sprint_start_date: "2026-08-24" # anchor on a real sprint-start date

promotion_threshold_sprints: 3    # B2: streak needed for enforcement eligibility
require_traceability_for_promotion: false   # C4 toggle (observe before enforcing)

enforcement:                      # C4: Enforcer CI gate
  traceability_gate_for_new_projects: true
  new_project_cutoff_date: "2026-09-01"   # repos created after this are "new"
```

### `config/projects.yaml`
Per-repo metadata plus the per-repo activity-window override section (B4):
```yaml
repos:
  "navadhiti/web-frontend":
    timesheet_code: "WEB-UI-01"
    mailbox_pattern: "subject:WEB-UI sprint signoff"
    budget: 150000.0
    headcount: 5
    sprint_calendar:              # optional per-project cadence override
      sprint_length_days: 10
      sprint_start_date: "2026-08-24"

overrides:                        # B4: per-repo activity window override
  "navadhiti/legacy-maintenance":
    activity_window_days: 120
```
For one-off ad-hoc checks, prefer `python master_agent.py --include org/repo` over editing config — it force-includes that repo for a single run regardless of the window.

### `config/standard.yaml`
Defines verifiable technical standards:
```yaml
environment_separation:
  required_artifacts:             # glob or directory-prefix patterns
    - "terraform/workspaces"
    - "k8s/namespaces"
    - "docker-compose.*.yml"

security_baseline:
  required_scanners: [dependabot, snyk, trivy]
  # scanner_artifacts:            # optional per-scanner pattern override
  #   snyk: [".snyk", ".github/workflows/*snyk*"]

uat_signoff:                      # A5: repo-artifact tier
  artifact_pattern: "docs/signoffs/*.md"

deployment_history:               # B3: deploy markers
  deploy_marker: "releases"        # "releases" (default) or "tags"
  tag_pattern: '^v\d+\.\d+\.\d+$'

traceability:                     # C2/C3
  spec_directory: "specs/"         # spec-kit route; remove if not using spec-kit
  ticket_ref_pattern: '[A-Z][A-Z0-9]*-\d+'
  ticket_label_prefix: "ticket:"
```

### `config/integrations.yaml`
Endpoint configurations for enterprise tools. Any address below that names a
real organisation, mailbox or tenant is a **placeholder**; the operator supplies
the real value in their own environment and never commits it
(see [`CONFIDENTIALITY.md`](CONFIDENTIALITY.md)).
```yaml
git_provider:
  type: "github"                  # "github"; gitlab/azure_repos are roadmap providers
  api_url: "https://api.github.com"
  org: "navadhiti"                # org-wide discovery target (A1)
  # Authentication via environment variable: GIT_TOKEN

# ticketing_system:               # C3: uncomment when the tool is decided; while
#   type: "jira"                  # absent, issue-to-ticket reports undefined_standard
#   api_url: "https://example-tenant.atlassian.net/rest/api/3"
#   token_env: "TICKETING_TOKEN"

timesheet_system:
  type: "zoho_people"
  api_url: "https://people.zoho.com/api"
  # Authentication via environment variable: TIMESHEET_TOKEN

email_scanner:
  type: "office365"
  # `.invalid` is reserved by RFC 2606 and can never resolve. Until an operator
  # supplies a real mailbox in their own configuration, the email sign-off tier
  # reports `method: none` honestly rather than pretending it read a mailbox.
  mailbox: "signoffs@example.invalid"
  # Authentication via environment variable: EMAIL_CLIENT_SECRET
```

---

## 8. End-to-End Execution Flow

When executing `python master_agent.py [--include org/repo ...]`:

```
+--------------------------------------------------------------------------+
| 1. MASTER AGENT INITIALIZATION                                           |
|    - Load config/master.yaml, projects.yaml, integrations.yaml           |
|    - B6: validate weights sum == 1.0 (fail loudly otherwise)             |
+--------------------------------------------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
| 2. LIVE REPOSITORY DISCOVERY & FILTERING (A1, B4)                        |
|    - discover_repos() via the configured git provider: GitHub org       |
|      listing, paginated, pushed_at as last_commit_date                   |
|    - Archived repos excluded (logged)                                   |
|    - Per-repo activity_window_days override (projects.yaml overrides)   |
|    - --include repos force-included for this run                        |
|    - Excluded repos recorded with reason in the aggregate report        |
+--------------------------------------------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
| 3. SUBAGENT DISPATCH (ObserverAgent per in-scope repo)                   |
|    - One shared GitHubClient; recursive tree cached (1 round-trip)       |
|    - Sprint calendar resolved per repo (per-project, then global)       |
|    - environment (Trees API) + security (same cached tree)               |
|    - ci_gates (Branch Protection API)                                   |
|    - signoff artifacts discovered once; parsed per_sprint                |
|    - deploy_history (Releases/tags) vs parsed signoff dates              |
|    - traceability: merged PRs -> issues; closed issues -> tickets        |
|    - cost (calendar sprint duration)                                    |
|    - Weighted hygiene_score (traceability at 0.0 until weighted)         |
+--------------------------------------------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
| 4. PROMOTION STATE UPDATE (B2)                                           |
|    - Load reports/promotion_state.json (the only cross-run state)       |
|    - Recompute qualifies-this-sprint; advance/reset streak per sprint   |
|    - Flip overall.enforcement_eligible from the persisted streak        |
|    - Persist state file                                                 |
+--------------------------------------------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
| 5. REPORT PERSISTENCE & AGGREGATION (B5)                                |
|    - Preserve previous aggregate (pre-overwrite guard)                 |
|    - Write per-repo reports (Pydantic model_dump_json)                   |
|    - Write per-repo reports (Pydantic model_dump_json)                   |
|    - Aggregate: score, gap_flag, variance, streak, traceability counts, |
|      weight_warnings, excluded repos; sorted (gap > variance > score)   |
|    - Write reports/aggregate.json; snapshot it to reports/history/     |
+--------------------------------------------------------------------------+
```

---

## 9. Implementation Status & Remaining Productionization

Milestones 1 and 2 are complete. What was mock or stubbed in Milestone 1 and is now live:

| Component | Milestone 1 | Milestone 2 |
| :--- | :--- | :--- |
| Repo discovery | mocked 3 repos | live GitHub org discovery (A1) |
| Environment / Security checks | stubs | live via shared Trees API (A2/A4) |
| CI/CD gates | stub | live via Branch Protection API (A3) |
| UAT signoff | stub | live repo-artifact tier with per_sprint parsing (A5) |
| Deploy timestamps | simulated | live via Releases/tags (B3) |
| Sprint boundaries | none | calendar-driven (B1) |
| Promotion eligibility | current-sprint snapshot only | persisted qualifying streaks (B2) |
| Traceability | did not exist | live 7th dimension (C1–C3) |
| Enforcer agent | stub | implemented CI gate with new-project traceability (C4) |

Milestone 0 brought the tool's own repository to the baseline it enforces on
others. It changed **no check logic** — nothing about what the system measures,
scores, or blocks. An audit finding and a simultaneous change to the auditing
tool must never be confusable, which is why they are separate milestones.

| Control | Where | Verified by |
| :--- | :--- | :--- |
| Ignore rules | `.gitignore` | `no-env-tracked` |
| Test runner declared | `requirements.txt`, `pytest.ini` | `test-suite` |
| Internal-use notice | `NOTICE` | `licensing-artifact` |
| Dependency update scanning | `.github/dependabot.yml` | `dependency-scanning` |
| Commit-time secret guard | `.pre-commit-config.yaml`, `.secrets.baseline` | `secret-guard` |
| Baseline verification | `tools/verify_baseline.py` | itself, exit `0` |
| Advisory CI run | `.github/workflows/baseline.yml` | not a required status check |
| Confidentiality decision | `CONFIDENTIALITY.md` | `confidentiality-record` |
| No real data committed | verifier denylist + structural rules | `no-real-data` |

Known residue, stated rather than hidden: the committed virtual environment
remains in the three existing commits, **by decision**, because rewriting
history would break existing clones and any open pull request. Forward tracking
is corrected; the past is left alone.

Still remaining:

### Phase 3: Real Timesheet & Zoho People Integration

`core/checks/cost.py` still derives headcount from `config/projects.yaml` metadata. Wiring the live timesheet API:

```python
import os
import requests
from core.schema import CostTracking

def check_cost_live(repo_id: str, project_meta: dict, sprint_duration_days: int = 14) -> CostTracking:
    timesheet_code = project_meta.get("timesheet_code")
    budget = project_meta.get("budget")
    token = os.getenv("TIMESHEET_TOKEN")

    if not timesheet_code or not token:
        headcount = project_meta.get("headcount", 0)
        return CostTracking(
            status="undefined_standard" if headcount == 0 else "pass",
            headcount=headcount,
            sprint_duration_days=sprint_duration_days,
            budget=budget,
        )

    resp = requests.get(
        f"https://people.zoho.com/api/timetracker/gettimesheetentries",
        params={"jobCode": timesheet_code},
        headers={"Authorization": f"Zoho-oauthtoken {token}"},
    )
    # Parse total recorded hours and distinct active heads for the sprint window
    # (resolve the window via core/sprint.py, never ad-hoc date math) ...
```

### Phase 4: Office365 / Graph API Email Sign-off Scanning

The `email_parsed` UAT signoff tier is declared in the schema but not implemented. When a repo has no signoff artifact, the check says so explicitly. To build it: acquire an OAuth2 token via MSAL (`EMAIL_CLIENT_SECRET`), query `/v1.0/users/{mailbox}/messages?$search="{mailbox_pattern}"`, and look for a positive approval keyword ("Approved", "UAT Sign-off Granted"). Until then, `method` never claims `email_parsed`.

### Phase 6: GitLab / Azure Repos Providers

`core/git_providers.py` exposes the `GitProvider` interface and a registry (`PROVIDERS`). Adding GitLab or Azure Repos means implementing a `GitProvider` subclass and registering it — `master_agent.py` never changes. The checks currently call the GitHub client directly; porting to another provider's API is a larger follow-up and should be scoped when a second provider is actually needed.

---

## 10. Operations, Monitoring & Runbook

### 10.1 Setting Up a Clone

These commands run in the order given, on a fresh clone, with no undocumented
step. `requirements.txt` declares the runtime dependencies **and** the test
tooling, so there is no separate install step.

```bash
git clone https://github.com/jayanthbagare/navadhiti_hygiene.git
cd navadhiti_hygiene
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

The environment directory is created locally and is never tracked — a fresh
clone tracks 69 files, not the 2,033 this repository once carried. A clone made
before the ignore rules existed needs the one-command recovery in the README
("If you have an existing clone"); it removes the environment from the index
only, leaving the working copy intact.

Note: the committed environment remains in the three existing commits, by
decision. History was not rewritten so that no contributor's clone or open pull
request breaks.

### 10.2 Running the Evaluation

```bash
export GIT_TOKEN="ghp_..."   # PAT with repo read access (admin read for full CI-gate fidelity)
python master_agent.py                       # full org run
python master_agent.py --include org/repo    # force one repo in regardless of window
```

### 10.3 Running on a Schedule (Cron)
```bash
0 0 * * * cd /opt/hygiene && GIT_TOKEN=$GIT_TOKEN /opt/hygiene/venv/bin/python master_agent.py >> /var/log/hygiene.log 2>&1
```

### 10.4 Running the Test Suite
```bash
pytest
```
One command, non-zero exit on any failure. The suite is fully offline: all
GitHub and ticketing HTTP traffic is mocked at the `requests.Session` layer. It
is also date-independent — the end-to-end fixtures freeze the clock they assert
against, so the suite passes on any run date rather than only inside one sprint.

`pytest` is declared in `requirements.txt`, so `pip install -r requirements.txt`
is all a new clone needs. See §10.1 for the setup commands.

### 10.5 Verifying This Repository's Own Baseline
```bash
python tools/verify_baseline.py
```
Seven criteria, one verdict, exit `0` healthy / `1` baseline not met / `2` the
verifier itself could not run. Stdlib-only, read-only, offline, and identical
locally and in CI — the same command and the same criterion list produce the
same verdict for the same commit, so the two paths cannot disagree.

The `2` matters: it separates "the repository is wrong" from "I could not look",
so a broken verifier is never read as a healthy repository. Findings name a
path, line number, count, or pattern — never the value found. The run is
advisory: it reports rather than blocks, and `.github/workflows/baseline.yml`
runs it on pull requests only, without being a required status check.

### 10.6 Running the Enforcer CI Gate
```bash
python -m sub_agents.enforcer_agent "navadhiti/service-a" "https://github.com/navadhiti/service-a"
# exit 0 = merge allowed, exit 1 = blocked
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
        env:
          GIT_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          python -m sub_agents.enforcer_agent "${{ github.repository }}" "${{ github.server_url }}/${{ github.repository }}"
```

### 10.7 Adding a New Project
1. Repos are discovered live — nothing to register. Only add metadata where the repo needs it (`config/projects.yaml`):
   ```yaml
   repos:
     "org/my-new-service":
       timesheet_code: "SRV-042"
       mailbox_pattern: "subject:SRV-042 signoff"
       budget: 120000.0
       headcount: 4
   ```
2. Run `python master_agent.py` to trigger immediate evaluation.

### 10.8 Modifying Hygiene Dimensions & Weights
Edit `config/master.yaml` under `weights`:
- Weights must sum to exactly `1.0` — startup fails loudly otherwise.
- To weight traceability (recommended start): `traceability: 0.10` and rebalance (e.g. `ci_cd_gates: 0.05`, `cost_tracking: 0.05`, or take proportionally from the two lowest-weighted dimensions). This is a human decision; the system surfaces the need but never makes it.

### 10.9 Reading Promotion State
`reports/promotion_state.json` shows each repo's `qualifying_streak`, `last_sprint_id`, `last_qualifying_sprint`, and `enforcement_eligible`. Streaks advance once per sprint (idempotent within a sprint). To confirm the counting logic run over run, diff this file between runs — the streak should step up only after a sprint boundary.

---

## 11. Troubleshooting & FAQ

#### Q1: Why is my project not showing up in `reports/aggregate.json`?
**A**: It's either dormant (last commit older than the activity window — check `excluded_repos` in the aggregate for the exact reason) or archived. Use `python master_agent.py --include org/repo` for a one-off check, or add an `overrides` entry in `config/projects.yaml` to extend that repo's window permanently.

#### Q2: Why did the run exit immediately with a weights error?
**A**: `config/master.yaml` weights must sum to exactly 1.0. This is a deliberate hard failure (B6): a mis-weighted score would be silently wrong. If you just added `traceability`, you must rebalance the other dimensions in the same commit.

#### Q3: Why is traceability scoring 0 even when it passes?
**A**: `traceability` has no configured weight yet, so it's treated as 0.0 and every aggregate report carries a `weight_warnings` entry asking a human to confirm a value. The system never auto-rebalances weights.

#### Q4: What is the difference between `undefined_standard` and `fail`?
**A**: `undefined_standard` means the organization has not defined a measurable standard for that dimension (no `required_artifacts`, no ticketing integration configured, nothing to evaluate in the window) **or** the API needed to verify is unavailable — the system refuses to guess. `fail` means the standard exists, the check ran against real state, and the repository did not meet it.

#### Q5: How is a gap flag triggered?
**A**: A deploy marker exists (published GitHub release, or a tag matching `tag_pattern`) but no valid signoff artifact is dated between the start of the deploy's sprint and the deploy itself. Signoffs dated after the deploy don't count. If the repo has no deploy markers at all, the dimension is `undefined_standard`, not a gap.

#### Q6: Why does CI/CD gates report `undefined_standard` on some repos even though I have branch protection?
**A**: Reading the Branch Protection API requires a token with administration read scope. A 403 means we can't distinguish "protected" from "not" with that token, so the check refuses to guess. Use a PAT with `repo` scope (or an administration-read fine-grained token).

#### Q7: My signoff artifact exists but the check says fail. What's wrong?
**A**: The artifact must contain all three fields — a sprint reference the calendar can resolve (`sprint_id: sprint-YYYY-MM-DD` or a `date:`), a `reviewer:`, and a `date:` — and it must cover the **current** sprint. Check `per_sprint` in the repo report to see what was parsed. Also verify the sprint calendar anchor (`sprint_calendar.sprint_start_date`) matches the team's actual sprint start.

#### Q8: Direct-to-main repos report `undefined_standard` for traceability — why not `fail`?
**A**: The PR-based linking standard isn't defined for repos with no PR history, so there is nothing to evaluate against — but the evidence explicitly flags direct-to-main activity as worth investigating, because bypassing the PR workflow usually also bypasses review gates.

#### Q9: When does the Enforcer block on traceability?
**A**: Only for new projects (created at/after `enforcement.new_project_cutoff_date`), only on a definite `fail` (`undefined_standard` never blocks), and only while `traceability_gate_for_new_projects: true`. Existing projects report traceability without being blocked, per the observe-then-promote philosophy.

#### Q10: How do I verify the promotion streak is counting correctly?
**A**: Run `python master_agent.py` twice in the same sprint — `reports/promotion_state.json` should show the same `qualifying_streak` both times (same-sprint runs are idempotent). After a sprint boundary, a qualifying repo's streak steps up by exactly one. A non-qualifying sprint resets it to 0.
