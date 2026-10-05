# Implementation Plan: Navadhiti Hygiene System — Milestone 0 Own-Repository Baseline

**Branch**: `001-fix-own-repo-hygiene` | **Date**: 2026-10-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/speckit.specify` → `/speckit.clarify`

**Position in the completion spec**: Milestone 0 of 11. Milestone 2 capability already exists in the codebase and is **not modified here**.

---

## Summary

Bring the hygiene tool's own repository up to the baseline it enforces on others. Concretely: untrack a committed 1,989-file Python virtual environment, add a proper ignore file, declare and configure a test runner (44 tests exist but pytest is absent from the dependency manifest), add an internal-use notice, enable automated dependency scanning, add a commit-time secret guard, scrub two real identifiers from tracked configuration, record the confidentiality decision in writing, and provide one command that verifies all of it and fails loudly.

This milestone adds **no check logic**. It changes nothing about what the system measures, how it scores, or whether it blocks anything. An audit finding must never be confusable with a simultaneous change to the auditing tool.

---

## Technical Context

**Language/Version**: Python 3.11 (minimum 3.10 per existing README; repo venv is 3.11)

**Primary Dependencies**: Runtime — `pydantic>=2.0.0`, `PyYAML>=6.0`, `requests>=2.0.0` (all existing, all unchanged). New — `pytest` (test runner, FR-012), `pre-commit` (secret-guard runner, FR-017), `detect-secrets` (secret detection, FR-017)

**Storage**: Files. Git-tracked YAML configuration (`config/*.yaml`); generated JSON run output (`reports/`, untracked). No database.

**Testing**: pytest (new). The existing 44 tests are `unittest.TestCase` subclasses, which pytest collects and runs natively — no test rewrites required.

**Target Platform**: macOS/Linux primary; Windows contributors must be supported (ignore patterns, documented commands). Baseline verifier must be stdlib-only so it runs even when dependencies are broken.

**Project Type**: CLI governance scanner + library

**Performance Goals**: Baseline verification completes in under 60 seconds on a developer machine, including running the full test suite.

**Constraints**:
- The verifier MUST run offline (no network calls). Dependency-scanning *activation* is a hosting-side fact the verifier cannot observe.
- The verifier MUST be read-only and idempotent: two runs against the same commit produce identical output.
- The verifier MUST never print a detected credential value (Constitution Principle 7).
- Stdlib-only for the verifier, so that a broken `pip install` cannot disable the check that would catch it.
- Cross-platform: no bash-only behaviour in the verifier; `subprocess` invocations must work on Windows.

**Scale/Scope**: 1 repository. Tracked files drop 2,033 → under 100. 44 existing tests, unchanged in count and intent.

---

## Constitution Check

*GATE: evaluated before Phase 0. Re-checked after Phase 1 design.*

**Gate status: PASS WITH RECORDED FINDINGS.**

> **The constitution is not ratified.** `.specify/memory/constitution.md` is still the unmodified Spec Kit template — Section A of the completion spec has never been fed to `/speckit.constitution`. This gate was therefore evaluated against **Section A of the completion spec**, which is the intended constitution content. The gate is **provisional**: it must be re-run once the constitution is written. This is recorded as an outstanding human action, not treated as satisfied.

### Gate results

| # | Principle | Verdict | Notes |
| :--- | :--- | :--- | :--- |
| 1 | Read from systems of record, never self-reported forms | **FINDING** | The confidentiality record is a written document. See Complexity Tracking entry 1. |
| 2 | Deterministic checks decide; agents narrate | PASS | FR-029 puts the no-real-data policy in a deterministic check, not in prose. |
| 3 | Undefined is not failed | **FINDING** | FR-016 requires dependency scanning be "active", which a repo file cannot verify. See Complexity Tracking entry 2. |
| 4 | Tiered evidence, honestly labelled | PASS | The verifier labels each criterion with what it verified vs. what it could not. |
| 5 | Observe before enforcing | PASS | FR-033 fixes the automated run as non-blocking. |
| 6 | Fail closed at gates, fail open at scans | PASS | FR-031 fails loudly and exits non-zero; FR-033 keeps it from gating merges. |
| 7 | Minimize what is stored and shared | PASS | The verifier reports file, line and pattern — never the matched value. |
| 8 | Stateless and idempotent | PASS | The verifier writes nothing and reads only git-tracked state. |

### Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **1. A written confidentiality record exists, in tension with Principle 1** (read from systems of record, never self-reported forms) | Principle 1 forbids *fabricating an audit input*. It does not forbid recording a governance decision. A decision about repository visibility has no system of record to read it from — it is a decision, not a measurement. | Omitting the record was rejected because the current state (public repo holding salary-derived cost figures) was itself an undocumented accident. An undocumented accident is the exact failure this milestone exists to prevent. The record is an **input to no check**: the verifier reads the config and git state, and reads the record only to confirm it exists and is linked. |
| **2. The verifier cannot confirm dependency scanning is "active", only that it is configured** (in tension with Principle 3, undefined is not failed) | Dependabot activation is a hosting-side fact. GitHub exposes no repo-file evidence of it. Claiming "active" from the presence of `.github/dependabot.yml` would be exactly the guessing Principle 2 forbids. | The alternative — reading it from the GitHub API — was rejected: it would make the verifier require network access and a token, contradicting the offline and read-only constraints. The criterion therefore reports **configured** with activation explicitly marked unverifiable from the repository, and the confidentiality record carries the manual activation step as a named human action. This is `unverifiable`, not `pass` and not `fail`. |
| **3. This milestone introduces its first CI workflow** | FR-032 requires the baseline check to run on pull requests. The repository has no CI today. | A manual-only check was rejected by clarification (it lets a bad commit land and rely on memory). A merge-blocking gate was rejected by FR-033, because that would switch enforcement on by automation. |

### Re-check after Phase 1 design

Design does not change the gate outcomes. Two additions confirmed sound:

- The verifier is **stdlib-only**, which means Principle 6's "fail closed" survives a broken dependency install rather than being silently skipped.
- The no-real-data check is an **explicit denylist of known identifiers plus structural rules**, not a heuristic classifier. This is the direct application of Principle 3: it detects the categories the record enumerates and never guesses at categories it cannot define.

---

## Project Structure

### Documentation (this feature)

```text
specs/001-fix-own-repo-hygiene/
├── plan.md              # This file
├── spec.md              # /speckit.specify + /speckit.clarify output
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── verify-baseline-cli.md      # CLI surface, exit codes, output format
│   └── confidentiality-record.md   # Record structure the verifier expects
├── checklists/
│   └── requirements.md # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (repository root)

```text
navadhiti_hygiene/
├── master_agent.py              # unchanged — no check logic touched
├── core/                        # unchanged — no check logic touched
│   ├── checks/
│   ├── schema.py
│   ├── sprint.py
│   └── ...
├── sub_agents/                  # unchanged
├── hermes/skill.md              # unchanged
├── config/                      # TWO values scrubbed (mailbox, tenant domain)
│   ├── integrations.yaml
│   ├── master.yaml
│   ├── projects.yaml
│   └── standard.yaml
├── tools/
│   └── verify_baseline.py       # NEW — stdlib-only baseline verifier (FR-028..FR-034)
├── tests/
│   └── test_hygiene.py          # existing 44 tests, unchanged in count and intent
├── reports/                     # NEW dir, gitignored (FR-025); tool writes here at runtime
├── .github/
│   ├── dependabot.yml           # NEW — pip ecosystem (FR-016)
│   └── workflows/
│       └── baseline.yml         # NEW — PR-triggered, NON-BLOCKING (FR-032, FR-033)
├── .pre-commit-config.yaml      # NEW — secret guard hook (FR-017..FR-020)
├── .secrets.baseline            # NEW — detect-secrets config + accepted findings
├── .gitignore                   # NEW — FR-002
├── NOTICE                       # NEW — internal-use notice, no license terms (FR-021 via Q3)
├── CONFIDENTIALITY.md           # NEW — the decision record (FR-021..FR-027)
├── requirements.txt             # MODIFIED — add pytest, pre-commit, detect-secrets
├── pytest.ini                   # NEW — test runner config (FR-012)
├── README.md                    # MODIFIED — roadmap rows, recovery procedure, record link
└── USAGE_AND_TECHNICAL_GUIDE.md # MODIFIED — reflect post-milestone reality (FR-008)
```

**Structure Decision**: Single project, flat layout, unchanged. The existing `core/` + `sub_agents/` + `master_agent.py` arrangement is kept exactly as-is because this milestone forbids touching check logic. One new top-level `tools/` directory is added for the verifier, keeping governance-of-the-repo code separate from the code that governs other repos — a future reader should not have to look in `core/` to find out whether the tool polices itself. No `src/`, `backend/`, `frontend/`, or `ios/`.

---

## Phase Summary

| Phase | Artifact | Contents |
| :--- | :--- | :--- |
| 0 | `research.md` | 10 decisions with rationale and rejected alternatives |
| 1 | `data-model.md` | Criterion, CriterionResult, BaselineReport, ConfidentialityRecord, AcceptedExposure |
| 1 | `contracts/verify-baseline-cli.md` | CLI surface, exit codes, output format |
| 1 | `contracts/confidentiality-record.md` | Record structure the verifier checks for |
| 1 | `quickstart.md` | Runnable end-to-end validation scenarios |