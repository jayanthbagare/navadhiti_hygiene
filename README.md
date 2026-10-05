# Navadhiti Project Hygiene System

> Automated governance, compliance auditing, and CI gating across engineering repositories.

The **Navadhiti Project Hygiene System** evaluates software engineering repositories against organizational standards across seven critical dimensions: infrastructure separation, CI/CD gates, UAT sign-offs, labor cost variance, security baselines, deployment integrity, and bidirectional traceability (feature → issue → ticket).

---

## Key Highlights

- **Master-Subagent Architecture**: A centralized `MasterAgent` handles organization-wide repo discovery and filtering, dispatching isolated sub-agents per project.
- **Dual Operating Modes**:
  - **Observer (Read-Only)**: Audits active projects, calculates a 0–100 weighted Hygiene Score, detects unapproved deployment gaps, and monitors budget variance.
  - **Enforcer (CI Gate)**: Built and tested — blocks merges that violate baseline hygiene requirements. **Not yet wired into this repository's CI**; enforcement is switched on by an explicit human decision, not by automation.
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

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (runtime and test tooling)
pip install -r requirements.txt
```

Every command above runs in the order given, on a fresh clone, with no
undocumented step. The environment directory is created locally and is never
tracked — you will never see another contributor's copy of it.

#### If you have an existing clone

Clones made before the ignore rules existed still have a virtual environment
under version control, and an ignore rule alone does not untrack anything.
Reach a clean state in one command, without losing your working environment:

```bash
git rm -r --cached venv core/__pycache__ core/checks/__pycache__ \
                  sub_agents/__pycache__ tests/__pycache__
git status --porcelain
```

This removes those paths from the index only. Your `venv/` directory stays on
disk and keeps working — `source venv/bin/activate` still works immediately
afterwards. Then `git pull` and continue; the tracked file count drops from
2,033 to under 100 with no other action.

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

## Verifying This Repository

The system audits other repositories for hygiene. It also holds itself to the
same standard, and one command checks every part of that:

```bash
python tools/verify_baseline.py
```

It prints one line per criterion, a verdict, and the count behind it, then exits
`0` if every criterion passed, `1` if any failed, or `2` if the verifier itself
could not run. That last code matters: it means "I could not look", so a broken
verifier is never mistaken for a healthy repository.

Seven criteria are checked: no environment files tracked, the test suite green,
a licensing artefact present, dependency scanning configured, a commit-time
secret guard configured, the confidentiality record present and linked, and no
real Navadhiti data committed.

```text
Captured output — 2026-10-05, at the merge of the milestone that introduced it.
The counts move; run the command above for current figures. The criterion shapes
below do not.

navadhiti hygiene — repository baseline
commit: 1e2d98eba80c81501a5ffe193af455155b2e2bb4

  pass         no-env-tracked          no environment files are tracked (0 found, was 1989)
  pass         test-suite              107 tests passed via pytest
  pass         licensing-artifact      NOTICE present, internal-use notice
  pass         dependency-scanning     .github/dependabot.yml configured for pip (activation not verifiable from the repository)
  pass         secret-guard            .pre-commit-config.yaml configures detect-secrets over config/*.yaml with a reviewed baseline (.secrets.baseline)
  pass         confidentiality-record  CONFIDENTIALITY.md present and linked from README.md
  pass         no-real-data            no denied identifiers, live run output, or live project metadata in 68 tracked files

verdict: PASS (7 of 7 criteria passed)
this run reports only; it does not prevent merges
```

**This run reports; it does not block.** It runs automatically on every pull
request and is deliberately *not* a required status check. A green result never
means a merge was prevented, and a red one never prevents one.

Findings name a path, a line number, a count, or a pattern — never the value
found. A report can be pasted into a ticket without re-exporting the secret it
found.

### Running the Tests

```bash
pytest
```

That is the whole command, and it exits non-zero if any test fails. It runs
offline: all GitHub and ticketing traffic is mocked at the HTTP layer. The suite
does not depend on the calendar's position relative to today, so it passes on
any run date.

### The Commit-Time Secret Guard

A credential-shaped string must never reach a configuration file. The guard is
`detect-secrets`, run through `pre-commit`, scoped to `config/*.yaml`:

```bash
pre-commit install          # once per clone
```

Committing a token into a configuration file is blocked, and the message names
the file, the line, and the pattern that matched.

**When the match is a false positive.** A documented placeholder token is a false
positive, and it is not a reason to disable the guard. Two bypasses work, and
both keep the guard running for everything else.

*Suppress the one line* with an inline pragma on the same line as the value:

```yaml
# Example placeholder for docs, not a credential: ghp_example0000000000000000000000000000  # pragma: allowlist secret
```

*Or record it as an accepted finding*, which is the better choice when the line
is genuinely part of the configuration:

```bash
detect-secrets scan > .secrets.baseline    # review the diff, then: git add .secrets.baseline
```

Both leave a trace: the pragma is in the committed line, and a recorded finding
appears in the `.secrets.baseline` diff for a reviewer to approve.

> **The `nextline` form does not work.** `detect-secrets` documents
> `# pragma: allowlist nextline secret` and its own regex matches that string,
> but the pre-commit hook path still blocks the commit. Verified against
> `v1.5.0` on 2026-10-05. Put the pragma on the same line as the value.

Every suppression is recorded in [`.secrets.baseline`](.secrets.baseline), and
adding a detector or a pattern is a change to that file rather than to source.

### Confidentiality

This repository is public, and that is a recorded decision with a written policy
behind it, not an accident of how it was created. Read
[`CONFIDENTIALITY.md`](CONFIDENTIALITY.md) for the decision, the categories of
data that must never be committed here, the exposures that were accepted on
purpose, and the conditions that force revisiting the choice.

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
| **Enforcer CI Subagent** | 🟡 Built, not wired | `sub_agents/enforcer_agent.py` implements the gate (exit 0/1) and is covered by tests, but **no workflow runs it on a pull request today**. Enforcement is a separate decision, not a side effect of this repository's CI. |
| **Cost & Variance Check** | 🟡 Metadata-based | Headcount $\times$ duration $\times$ rate vs. budget from `config/projects.yaml`; live Zoho People API is the next milestone |
| **UAT Signoff (email tier)** | 🟡 Declared, not built | `email_parsed` fallback is schema-declared but unimplemented; missing artifacts are reported honestly as `method: none` |
| **Ticketing Verification** | 🟡 Config-gated | Runs once `ticketing_system` is configured in `config/integrations.yaml`; until then reports `undefined_standard` |
| **GitLab / Azure Repos Providers** | 🟡 Roadmap | `GitProvider` interface is ready; new providers add classes to `core/git_providers.py` without touching the master agent |

### Repository's Own Hygiene

Every row below is checked by `python tools/verify_baseline.py`, which exits
non-zero if any of them stops being true. A row marked ✅ here is a row the
command confirms, not a claim.

| Control | Status | Details |
| :--- | :---: | :--- |
| **Ignore Rules** | ✅ Live | `.gitignore` covers environment directories, Python bytecode, credential files, editor/tooling caches, Spec Kit local state, and generated run output |
| **Test Runner Declared** | ✅ Live | `pytest` + `pytest.ini`; the whole suite runs with one command, no test rewrites, offline, and date-independent |
| **Internal-Use Notice** | ✅ Live | [`NOTICE`](NOTICE) states authorship and restricted use without inventing license terms |
| **Dependency Update Scanning** | ✅ Active | `.github/dependabot.yml` covers the `pip` ecosystem weekly, and Dependabot is opening update PRs. **The verifier still reports `configured`, never `active`** — activation is a hosting-side fact with no evidence in the repository, so the criterion does not claim it. See [`CONFIDENTIALITY.md`](CONFIDENTIALITY.md) for the dated observation that it is on |
| **Commit-Time Secret Guard** | ✅ Live | `detect-secrets` via `pre-commit`, scoped to `config/*.yaml`, with suppressions reviewed in `.secrets.baseline` and a documented inline bypass |
| **Baseline Verification** | ✅ Live | `tools/verify_baseline.py` — seven criteria, one verdict, exit 0/1/2, read-only, stdlib-only, advisory only |
| **Automated Baseline Run** | ✅ Live, non-blocking | `.github/workflows/baseline.yml` runs on `pull_request` only and **must not be configured as a required status check** |
| **Confidentiality Record** | ✅ Live | [`CONFIDENTIALITY.md`](CONFIDENTIALITY.md) — decision, date, accountable role, rationale, concrete exclusions, accepted exposures, revisit triggers |
| **No Real Data Enforced** | ✅ Live | `no-real-data` criterion: denied-identifier denylist plus structural rules, by content rather than by directory |
| **Environment Untracked** | ✅ Live, with history residue | **The committed virtual environment remains in the three existing commits, by decision.** A fresh clone tracks 69 files instead of 2,033, but `git log --stat` still shows 1,989 environment files, and that was a choice — see the next section |

#### Why the environment is still in history

History was not rewritten. A contributor's clone, and any pull request opened
against those three commits, would break if it were. With three commits the cost
was small; it would not stay small indefinitely, and that is what a later
decision needs to weigh.

So: the files are untracked going forward and covered by `.gitignore`, and they
are still there if you look. `git log --stat` showing 1,989 environment files is
the expected result of this decision, not an incomplete task.

### Outstanding Human Actions

Not automated, and not quietly assumed:

- **Review the Dependabot update pull requests.** Version updates turned out to be
  **active** rather than configured-only: about 90 seconds after the config reached
  `main` on 2026-10-05, Dependabot opened its first update PRs, and it has since
  opened five (`requests`, `pydantic`, `PyYAML`, `pytest`, `pre-commit`). They are
  ordinary dependency bumps and each carries a passing `baseline` check, but a
  human decides what merges. The verifier will still only ever say `configured`,
  because a criterion cannot see this.
- **Confirm `main` stays unprotected** whenever someone adds branch protection. It
  has no protection and no rulesets today, which is what keeps the advisory
  `baseline` job non-gating. Adding a required status check on this job would
  silently switch enforcement on, which FR-033 forbids.
- **Name the accountable owner** in `CONFIDENTIALITY.md`. The role is recorded;
  the individual is an open item.
- **Ratify the constitution.** `.specify/memory/constitution.md` is still the
  unratified template, so the plan's constitution gate ran provisionally.

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
