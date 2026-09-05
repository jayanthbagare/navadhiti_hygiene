# Navadhiti Project Hygiene System

> Automated governance, compliance auditing, and CI gating across engineering repositories.

The **Navadhiti Project Hygiene System** evaluates software engineering repositories against organizational standards across seven critical dimensions: infrastructure separation, CI/CD gates, UAT sign-offs, labor cost variance, security baselines, deployment integrity, and bidirectional traceability (feature → issue → ticket).

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
                │ Live GitHub org discovery (A1)          │
                │ Filter: Dormant Repos (> 60 days)       │
                ▼                                         ▼
       ┌─────────────────┐                       ┌───────────────────────┐
       │  In-Scope Repos │                       │ Individual &          │
       └────────┬────────┘                       │ Aggregate Reports     │
                │ Dispatches                     │ + history archive     │
                ▼                                │ + promotion state     │
       ┌─────────────────┐                       │ (reports/)           │
       │  ObserverAgent  │                       └───────────────────────┘
       └────────┬────────┘
                │ Executes 7 Deterministic Checks
                ├─► core/checks/environment.py        (Trees API)
                ├─► core/checks/ci_gates.py           (Branch Protection API)
                ├─► core/checks/signoff.py            (repo signoff artifacts)
                ├─► core/checks/cost.py               (Headcount & Budget Variance)
                ├─► core/checks/security.py          (shared Trees API)
                ├─► core/checks/deploy_history.py     (Releases/tags vs signoff gaps)
                └─► core/checks/traceability_*.py     (PRs → issues → tickets)
```

---

## The 7 Hygiene Dimensions

| Dimension | Default Weight | Description | Pass Criteria |
| :--- | :---: | :--- | :--- |
| **UAT Sign-off** | **40%** | Formal acceptance before deployment | Well-formed repo artifact (`docs/signoffs/*.md`) covering the current sprint |
| **Environment Separation** | **20%** | Isolation of dev, stage, and prod | File tree contains Terraform workspaces, K8s namespaces, or Docker overrides |
| **Security Baseline** | **20%** | Vulnerability scanning in CI/CD | Active Dependabot, Snyk, or Trivy configuration in the file tree |
| **CI/CD Gates** | **10%** | Pipeline merge protection | Branch protection + ≥1 required review + required status checks |
| **Cost Tracking** | **10%** | Labor burn vs. project budget | Headcount registered, sprint duration mapped, variance calculated |
| **Traceability** | *unweighted (0%)* | Work traceable in both directions | Merged PRs link to existing issues; closed issues link to external tickets |
| **Deployment History** | *Risk Flag* | Release audit & gap detection | Deployments must have a preceding approved sign-off (`gap_flag: false`) |

> Traceability is live but deliberately unweighted until a human confirms its weight in `config/master.yaml` (suggested start: 10%, from the lowest-weighted dimensions). The report surfaces this decision; the system never auto-rebalances.

---

## Quick Start

### 1. Prerequisites
- Python 3.10 or higher (Python 3.11 recommended)
- `pip` or virtual environment manager

### 2. Installation
Clone the repository and set up a virtual environment:

```bash
git clone https://github.com/jayanthbagare/navadhiti_hygiene.git
cd navadhiti_hygiene
cd hygiene

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run the Evaluation
Set a GitHub token (PAT with repo read access; administration read gives full CI-gate fidelity) and execute the master agent:

```bash
export GIT_TOKEN="ghp_..."
python master_agent.py                       # full org run
python master_agent.py --include org/repo    # force one repo in regardless of window
```

The org is configured via `config/integrations.yaml` (`git_provider.org`).

### 4. Sample Output
```
Starting Hygiene Master Agent (Activity Window: 60 days)
Discovered 3 repos, 2 in scope.
Dispatching ObserverAgent for navadhiti/service-a...
Dispatching ObserverAgent for navadhiti/service-b...
Reports generated in reports/ directory. Aggregate view:
{
  "generated_at": "2026-09-05T18:13:57.080510",
  "total_evaluated": 2,
  "weight_warnings": [
    "Traceability dimension is live but has no configured weight; ..."
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
    },
    ...
  ],
  "excluded_repos": [
    { "id": "navadhiti/dormant-service", "reason": "dormant: last commit 100 days ago (window 60d)" }
  ]
}
```
Scores now vary across repos based on real repository state — a repo that keeps its signoffs current, protects its default branch, and links its PRs to issues scores high; one that doesn't scores low.

### 5. Inspect Generated Reports
The evaluation produces individual JSON records and an aggregate summary in the `reports/` folder:
- `reports/aggregate.json` — Prioritized cross-project governance overview (with weight warnings and excluded-repo reasons).
- `reports/navadhiti_service-a.json` — Deep breakdown of all 7 dimensions and evidence logs.
- `reports/history/` — One archived aggregate per previous run (for trend narratives).
- `reports/promotion_state.json` — Per-repo qualifying-sprint streaks (the only persisted state).

---

## Configuration Files

The behavior of the hygiene system is entirely data-driven via four YAML files in `config/`:

| File | Purpose | Key Parameters |
| :--- | :--- | :--- |
| [`config/master.yaml`](config/master.yaml) | Engine execution parameters, scoring weights, sprint calendar, promotion thresholds | `activity_window_days` (default 60), `parallelism`, `weights`, `sprint_calendar`, `promotion_threshold_sprints`, `require_traceability_for_promotion`, `enforcement` |
| [`config/projects.yaml`](config/projects.yaml) | Project metadata mapping + per-repo overrides | `timesheet_code`, `mailbox_pattern`, `budget`, `headcount`, per-repo `sprint_calendar`, `overrides.activity_window_days` |
| [`config/standard.yaml`](config/standard.yaml) | Verifiable technical baselines | `required_artifacts`, `required_scanners`, `uat_signoff.artifact_pattern`, `deployment_history` markers, `traceability` patterns |
| [`config/integrations.yaml`](config/integrations.yaml) | Connection settings for SaaS tools | GitHub API (`org`), optional `ticketing_system`, Zoho People timesheets, Office365 email scanner |

---

## Project Status & Implementation Roadmap

| Milestone / Component | Status | Details |
| :--- | :---: | :--- |
| **Master Agent Discovery** | ✅ Live | GitHub org-wide discovery with pagination, archived-repo exclusion, per-repo window overrides, `--include` flag (`core/git_providers.py`) |
| **Schema & Validation** | ✅ Live | Pydantic v2 schemas for all 7 dimensions in `core/schema.py` |
| **Environment Check** | ✅ Live | Recursive Trees API against `standard.yaml` artifact patterns; shared cached round-trip (`core/checks/environment.py`) |
| **CI/CD Gates Check** | ✅ Live | Branch Protection API: protection + required reviews + required status checks (`core/checks/ci_gates.py`) |
| **Security Scanners Check** | ✅ Live | Scanner artifacts via the same cached tree — Dependabot / Snyk / Trivy (`core/checks/security.py`) |
| **UAT Signoff (repo-artifact tier)** | ✅ Live | Parses `docs/signoffs/*.md` artifacts (sprint id, reviewer, date) into `per_sprint` entries (`core/checks/signoff.py`) |
| **Deployment Gap Check** | ✅ Live | GitHub Releases / tag-pattern timestamps vs. signoff dates; `undefined_standard` when no deploy markers exist (`core/checks/deploy_history.py`) |
| **Traceability (7th dimension)** | ✅ Live | Merged PRs → existing issues (keyword/URL/spec-kit/commit tiers); closed issues → external tickets with best-effort verification (`core/checks/traceability_*.py`) |
| **Sprint Calendar** | ✅ Live | Per-project and global cadences; every sprint window resolves through `core/sprint.py` |
| **Promotion Streaks** | ✅ Live | `reports/promotion_state.json` — consecutive qualifying sprints, sprint-idempotent, threshold-gated eligibility (`core/promotion.py`) |
| **Report History Archive** | ✅ Live | `reports/history/<timestamp>-aggregate.json` written before every aggregate overwrite |
| **Weight Validation** | ✅ Live | Startup fails loudly unless configured weights sum to exactly 1.0 |
| **Aggregate Reporting** | ✅ Live | Multi-key sorting (Gap flag $\rightarrow$ Variance % $\rightarrow$ Score), weight warnings, excluded-repo reasons |
| **Enforcer CI Subagent** | ✅ Live | PR blocking gate (exit 0/1); traceability blocks new projects only, `undefined_standard` never blocks |
| **Cost & Variance Check** | 🟡 Metadata-based | Headcount $\times$ duration $\times$ rate vs. budget from `config/projects.yaml`; live Zoho People API is the next milestone |
| **UAT Signoff (email tier)** | 🟡 Declared, not built | `email_parsed` fallback is schema-declared but unimplemented; missing artifacts are reported honestly as `method: none` |
| **Ticketing Verification** | 🟡 Config-gated | Runs once `ticketing_system` is configured in `config/integrations.yaml`; until then reports `undefined_standard` |
| **GitLab / Azure Repos Providers** | 🟡 Roadmap | `GitProvider` interface is ready; new providers add classes to `core/git_providers.py` without touching the master agent |

For details and the remaining productionization phases, consult [`USAGE_AND_TECHNICAL_GUIDE.md`](USAGE_AND_TECHNICAL_GUIDE.md).

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
