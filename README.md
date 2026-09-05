# Navadhiti Project Hygiene System

> Automated governance, compliance auditing, and CI gating across engineering repositories.

The **Navadhiti Project Hygiene System** evaluates software engineering repositories against organizational standards across six critical dimensions: infrastructure separation, CI/CD gates, UAT sign-offs, labor cost variance, security baselines, and deployment integrity.

---

## Key Highlights

- **Master-Subagent Architecture**: A centralized `MasterAgent` handles organization-wide repo discovery and filtering, dispatching isolated sub-agents per project.
- **Dual Operating Modes**:
  - **Observer (Read-Only)**: Audits active projects, calculates a 0–100 weighted Hygiene Score, detects unapproved deployment gaps, and monitors budget variance.
  - **Enforcer (CI Gate)**: Runs on pull requests to prevent merges that violate baseline hygiene requirements.
- **Pydantic v2 Typed Schemas**: Complete typing and validation across all dimensions and serialized reports.
- **AI Agent Skill Ready**: Includes a native Hermes orchestration skill (`hermes/skill.md`) for automated analysis and executive reporting.
- **Detailed Technical Guide**: Complete implementation blueprint available in [`USAGE_AND_TECHNICAL_GUIDE.md`](USAGE_AND_TECHNICAL_GUIDE.md).

---

## Architecture at a Glance

```
                         ┌───────────────────────┐
                         │      MasterAgent      │
                         │   (master_agent.py)   │
                         └──────────┬────────────┘
                                    │
               ┌────────────────────┴────────────────────┐
               │ Filter: Dormant Repos (> 60 days)       │
               ▼                                         ▼
      ┌─────────────────┐                       ┌──────────────────┐
      │  In-Scope Repos │                       │ Individual &     │
      └────────┬────────┘                       │ Aggregate Reports│
               │ Dispatches                     │ (reports/*.json) │
               ▼                                └──────────────────┘
      ┌─────────────────┐
      │  ObserverAgent  │
      └────────┬────────┘
               │ Executes 6 Deterministic Checks
               ├─► core/checks/environment.py     (Environment Separation)
               ├─► core/checks/ci_gates.py        (CI/CD Branch Protection)
               ├─► core/checks/signoff.py         (UAT Sign-off Verification)
               ├─► core/checks/cost.py            (Headcount & Budget Variance)
               ├─► core/checks/security.py        (SAST & Supply Chain Scanners)
               └─► core/checks/deploy_history.py  (Deploy vs. Sign-off Gap Flag)
```

---

## The 6 Hygiene Dimensions

| Dimension | Default Weight | Description | Pass Criteria |
| :--- | :---: | :--- | :--- |
| **UAT Sign-off** | **40%** | Formal acceptance before deployment | Verified repository artifact (`docs/signoffs/*.md`) or approval email |
| **Environment Separation** | **20%** | Isolation of dev, stage, and prod | Presence of Terraform workspaces, K8s namespaces, or Docker overrides |
| **Security Baseline** | **20%** | Vulnerability scanning in CI/CD | Active Dependabot, Snyk, or Trivy configuration |
| **CI/CD Gates** | **10%** | Pipeline merge protection | Branch protection, PR review requirements, and status checks |
| **Cost Tracking** | **10%** | Labor burn vs. project budget | Headcount registered, sprint duration mapped, variance calculated |
| **Deployment History** | *Risk Flag* | Release audit & gap detection | Deployments must have a preceding approved sign-off (`gap_flag: false`) |

---

## Quick Start

### 1. Prerequisites
- Python 3.10 or higher (Python 3.11 recommended)
- `pip` or virtual environment manager

### 2. Installation
Clone the repository and set up a virtual environment:

```bash
git clone https://github.com/mock-org/hygiene.git
cd hygiene

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run the Evaluation
Execute the master agent:

```bash
python master_agent.py
```

### 4. Sample Output
```
Starting Hygiene Master Agent (Activity Window: 60 days)
Discovered 3 repos, 2 in scope.
Dispatching ObserverAgent for mock-org/active-project-1...
Dispatching ObserverAgent for mock-org/active-project-2...
Reports generated in reports/ directory. Aggregate view:
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

### 5. Inspect Generated Reports
The evaluation produces individual JSON records and an aggregate summary in the `reports/` folder:
- `reports/aggregate.json` — Prioritized cross-project governance overview.
- `reports/mock-org_active-project-1.json` — Deep breakdown of all 6 dimensions and evidence logs for project 1.
- `reports/mock-org_active-project-2.json` — Deep breakdown for project 2.

---

## Configuration Files

The behavior of the hygiene system is entirely data-driven via four YAML files in `config/`:

| File | Purpose | Key Parameters |
| :--- | :--- | :--- |
| [`config/master.yaml`](config/master.yaml) | Engine execution parameters & scoring weights | `activity_window_days` (default 60), `parallelism`, `weights` |
| [`config/projects.yaml`](config/projects.yaml) | Project metadata mapping | `timesheet_code`, `mailbox_pattern`, `budget`, `headcount` |
| [`config/standard.yaml`](config/standard.yaml) | Verifiable technical baselines | `required_artifacts` (Terraform, K8s), `required_scanners` |
| [`config/integrations.yaml`](config/integrations.yaml) | Connection stubs for SaaS tools | GitHub API, Zoho People timesheets, Office365 email scanner |

---

## Project Status & Implementation Roadmap

| Milestone / Component | Status | Details |
| :--- | :---: | :--- |
| **Master Agent Discovery** | ✅ Completed | Mock discovery of 3 repos with automated activity window filtering (60 days) |
| **Schema & Validation** | ✅ Completed | Comprehensive Pydantic v2 schemas in `core/schema.py` |
| **Cost & Variance Check** | ✅ Live Demo | Headcount $\times$ duration $\times$ rate vs. budget calculation in `core/checks/cost.py` |
| **Deployment Gap Check** | ✅ Live Demo | Audits release dates vs. sign-off dates in `core/checks/deploy_history.py` |
| **Aggregate Reporting** | ✅ Completed | Multi-key sorting (Gap flag $\rightarrow$ Variance % $\rightarrow$ Score) |
| **Live Git Provider API** | 🟡 In Roadmap | Query GitHub / GitLab REST APIs for real repository activity (see Guide) |
| **Environment Check** | 🟡 Stubbed | Inspect repo file trees for Terraform / K8s manifests (see Guide) |
| **CI Gate & Security Scanners** | 🟡 Stubbed | Inspect branch protection rules and security scanner configs (see Guide) |
| **Enforcer CI Subagent** | 🟡 Stubbed | Pull request blocking gate in `sub_agents/enforcer_agent.py` |

For code snippets and step-by-step instructions on implementing each roadmap phase, consult [`USAGE_AND_TECHNICAL_GUIDE.md`](USAGE_AND_TECHNICAL_GUIDE.md).

---

## Running with Hermes AI Agent

This repository contains a ready-to-run Hermes Skill specification in [`hermes/skill.md`](hermes/skill.md).

When running under an AI agent harness:
1. The skill dispatches deterministic Python checks (`core/checks/*`).
2. It respects explicit boundaries: **the AI agent never guesses check results or invents budgets**.
3. It performs human-level synthesis, such as identifying risk clusters, recommending projects for enforcement promotion, and drafting executive summaries.

---

## Documentation

- **[Technical & Usage Guide](USAGE_AND_TECHNICAL_GUIDE.md)**: Deep dive into architecture, scoring math, promotion rules, productionization phases, and operational runbook.
- **[Hermes Skill Specification](hermes/skill.md)**: Autonomous agent guidelines and execution prompt.

---

## License

Internal proprietary governance software developed for Navadhiti.
