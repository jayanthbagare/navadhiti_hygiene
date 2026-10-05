---

description: "Task list for Milestone 0 — Navadhiti Hygiene System own-repository baseline"
---

# Tasks: Navadhiti Hygiene System — Milestone 0 Own-Repository Baseline

**Input**: Design documents from `/specs/001-fix-own-repo-hygiene/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included. The completion spec's standing constraints require tests with every milestone, and this milestone builds a tool — a governance tool with no test suite is not credible (FR-015).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**⚠️ Out of scope reminder**: No task in this file may modify `core/checks/*`, `core/schema.py`, `sub_agents/*`, or `master_agent.py`. This milestone changes nothing about what the system measures, scores, or blocks. An audit finding must never be confusable with a simultaneous change to the auditing tool.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repository-level declarations every story depends on

- [X] T001 [P] Create `.gitignore` covering six rule classes: virtual-environment directories (`venv/`, `.venv/`), Python bytecode (`__pycache__/`, `*.pyc`), local credential files (`.env`, `.env.*`), editor and tooling caches (`.DS_Store`, `.pytest_cache/`, `.idea/`, `.vscode/`), Spec Kit local state (`.specify/feature.json`), and generated run output (`reports/`) — satisfies FR-002
- [X] T002 [P] Append a commented `# development / test tooling` section to `requirements.txt` adding `pytest`, `pre-commit`, and `detect-secrets` alongside the three existing runtime packages — satisfies FR-012, per research.md D3 (single file, no separate dev-requirements file, so Dependabot discovery is unambiguous)
- [X] T003 [P] Create `pytest.ini` with `testpaths = tests` and `python_files = test_*.py` so `pytest` discovers the 44 existing tests without rewriting them — satisfies FR-012, per research.md D1/D2
- [X] T004 [P] Create empty directory `tools/` to hold the baseline verifier, keeping governance-of-this-repo code separate from code that governs other repositories — per plan.md Structure Decision

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The verifier framework that User Stories 2 and 3 both extend

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

The verifier is split across stories deliberately: the framework lands here, each story adds its own criteria to the registry. FR-029 requires all criteria in **one command with one verdict** — so the registry must exist before two stories can add to it, but each story's criteria stay independently testable.

- [X] T005 Implement `Criterion`, `CriterionResult`, and `BaselineReport` dataclasses in `tools/verify_baseline.py` with the validation rules from `data-model.md` verbatim: `id` matches `^[a-z0-9-]+$` and is unique; `requirements` is non-empty; a criterion whose `determination` is not `observed` is rejected at startup; `verdict` is `pass` only if every result is `pass`, and any `fail` or `unverifiable` yields `fail`
- [X] T006 Implement the criterion registry, the output formatter, and exit-code mapping in `tools/verify_baseline.py` per `contracts/verify-baseline-cli.md`: one line per criterion in declared order (never runtime-sorted), status word exactly `pass`/`fail`/`unverifiable`, evidence indented beneath its criterion, verdict line stating the failing count explicitly (`FAIL (1 of 7 criteria failed)`), the non-blocking disclaimer always printed, and exit `0` pass / `1` any failure or unverifiable / `2` the verifier itself could not start
- [X] T007 [P] Implement read-only git helpers in `tools/verify_baseline.py`: tracked-file listing, commit SHA (printing as absent outside a repository, never a placeholder), and text-file reading that skips `.git`, `venv`, `__pycache__`, and binary files — satisfies the read-only and idempotence guarantees in `contracts/verify-baseline-cli.md`
- [X] T008 Write tests in `tests/test_verify_baseline.py` asserting the exit-code split (`0` healthy, `1` repository non-compliant, `2` verifier cannot start) and asserting that no output field ever contains a credential value, token fragment, or live identifier — output references a path, line number, count, or pattern name only, per the binding security rule in `data-model.md`
- [X] T009 Run `pytest` and confirm exit code 0 with the 44 pre-existing tests plus the new verifier tests, and confirm the test count is exactly 44 plus whatever T008 added — a lower count means a test was lost without FR-015's written reason

**Checkpoint**: Verifier framework runs, reports, and exits correctly with an empty criterion registry. Foundation ready.

---

## Phase 3: User Story 1 - A new engineer gets a clean, working checkout (Priority: P1) 🎯 MVP

**Goal**: A fresh clone is under 100 tracked files with no environment files, every documented setup command works in order, and the test suite runs from a clean machine.

**Independent Test**: Clone to an empty directory, follow the README installation section verbatim, run `pytest`. Value delivered independently of US2 and US3.

### Tests for User Story 1 ⚠️

> Write first, confirm it fails, then implement.

- [X] T010 [US1] Write a failing test in `tests/test_verify_baseline.py` for the `no-env-tracked` criterion: build a temporary git repository containing a tracked `venv/bin/python`, assert the criterion returns `fail` and lists that path; then remove it and assert `pass` — satisfies FR-001, FR-003
- [X] T011 [US1] Implement the `no-env-tracked` criterion in `tools/verify_baseline.py`: any path matching environment-directory patterns in the tracked-file list yields `fail`, listing each offending path

### Implementation for User Story 1

- [X] T012 [P] [US1] Untrack the committed environment: run `git rm -r --cached venv core/__pycache__ core/checks/__pycache__ sub_agents/__pycache__ tests/__pycache__`, confirming `venv/` still exists on disk afterwards — satisfies FR-001, FR-004
- [X] T013 [P] [US1] Fix the installation section in `README.md`: remove the stray `cd hygiene` line, which is a real bug — the repository has no `hygiene/` subdirectory, so the documented flow currently fails on its third command — and confirm the clone URL is `https://github.com/jayanthbagare/navadhiti_hygiene.git`; verify every command in the section runs in the order given on a fresh clone — satisfies FR-006, FR-007
- [X] T014 [US1] Add an "If you have an existing clone" recovery section to `README.md` giving the one-command path to a clean state without deleting the contributor's working environment, matching what T012 actually did — satisfies FR-004, FR-011, SC-011

**Checkpoint**: A fresh clone is clean, documented setup works end to end, `pytest` is green.

---

## Phase 4: User Story 2 - A reviewer can verify the tool meets its own baseline (Priority: P2)

**Goal**: Each of the reviewer's four questions — is there a test suite, is it licensed, are its own dependencies watched, can a credential be committed — is answerable by locating one file, and the secret guard actually blocks.

**Independent Test**: Locate each of the four artefacts; run the baseline verifier; commit a credential-shaped string to a config file and observe the block, then observe the documented bypass working. Value delivered independently of US1 and US3.

### Tests for User Story 2 ⚠️

> Write first, confirm they fail, then implement.

- [X] T015 [P] [US2] Write failing tests in `tests/test_verify_baseline.py`, one per criterion, each asserting a compliant fixture passes and a non-compliant fixture fails: `licensing-artifact` (missing `NOTICE` → fail), `dependency-scanning` (missing `dependabot.yml` → fail; `dependabot.yml` without a `pip` ecosystem → fail; present and valid → pass with detail stating activation is **not verifiable from the repository**, never `active`), `secret-guard` (missing `.pre-commit-config.yaml` → fail; present without a secret-detection hook scoped to config files → fail), `test-suite` (runner absent → fail naming the runner; suite non-zero → fail)

### Implementation for User Story 2

- [X] T016 [P] [US2] Create `NOTICE` at the repository root: an internal-use notice stating Navadhiti authorship and restricted internal use, granting no license terms and withholding none — satisfies Q3, FR-021, per research.md D9
- [X] T017 [P] [US2] Create `.github/dependabot.yml` with `version: 2` and a single `pip` ecosystem update at `directory: "/"`, `schedule.interval: "weekly"` — satisfies FR-016, per research.md D5
- [X] T018 [P] [US2] Create `.pre-commit-config.yaml` and `.secrets.baseline` configuring the `detect-secrets` hook (rev `v1.5.0`) with `args: ['--baseline', '.secrets.baseline']` and `files:` scoped to `^config/.*\.ya?ml$`; generate the baseline so it is a reviewable diff rather than a snapshot of noise — satisfies FR-017, FR-020, per research.md D4
- [X] T019 [US2] Implement the `licensing-artifact`, `dependency-scanning`, and `secret-guard` criteria in `tools/verify_baseline.py`, registering each in the criterion registry; the `dependency-scanning` detail line MUST state that activation is not verifiable from the repository — satisfies FR-016 and Principle 3, per plan.md Complexity Tracking entry 2
- [X] T020 [US2] Implement the `test-suite` criterion in `tools/verify_baseline.py`: invoke the declared runner as a subprocess, capture exit status, and report the count; a missing runner and a failing suite are distinct failures — satisfies FR-012, FR-013
- [X] T021 [P] [US2] Document the secret-guard bypass in `README.md`: the inline `# pragma: allowlist secret` pragma and recording the finding in `.secrets.baseline`, with a worked false-positive example showing a placeholder token that commits successfully — satisfies FR-018, FR-019. ⚠️ **This task as written also required documenting `# pragma: allowlist nextline secret`. That form does not work through the pre-commit hook** (verified against v1.5.0, five placements); documenting it would have sent a contributor to a bypass that fails. The README documents the two that work and warns about the one that does not — see research.md D4 and validation.md §6.
- [X] T022 [P] [US2] Create `.github/workflows/baseline.yml` triggered on `pull_request` only, installing `requirements.txt` before invoking `python tools/verify_baseline.py`, printing the non-blocking disclaimer in the job summary, and using no job that fails pull-request mergeability — satisfies FR-032, FR-033, FR-034

**Checkpoint**: US1 and US2 both work independently. Verifier reports six of seven criteria; `confidentiality-record` and `no-real-data` are not yet registered, which is expected until US3.

---

## Phase 5: User Story 3 - The confidentiality decision is recorded, not inherited (Priority: P3)

**Goal**: The two real identifiers are gone, the decision is written down with rationale and accepted exposures, and a deterministic check prevents real data landing in a public repository.

**Independent Test**: Locate `CONFIDENTIALITY.md`, confirm each committed identifier is either a placeholder or a named accepted exposure, confirm the tool never attempted to change repository visibility, and confirm `python tools/verify_baseline.py` reports `PASS` with all seven criteria.

### Tests for User Story 3 ⚠️

> Write first, confirm they fail, then implement.

- [X] T023 [P] [US3] Write failing tests in `tests/test_verify_baseline.py` for `no-real-data`: the denylist catches a denied identifier and the failure output names the path and line number **without printing the identifier**; a placeholder such as `signoffs@example.com` does **not** match; commented budget entries in `config/projects.yaml` pass; an uncommented `budget:` entry fails; any tracked path under `reports/` fails; an accepted exposure whose identifier is absent from tracked content fails as stale — satisfies FR-023, FR-024, FR-030
- [X] T024 [P] [US3] Write failing tests in `tests/test_verify_baseline.py` for `confidentiality-record`: missing `CONFIDENTIALITY.md` fails; a record missing any of the eight required section headings fails; a record not referenced from `README.md` fails; a complete linked record passes — satisfies FR-021, FR-027, per `contracts/confidentiality-record.md`

### Implementation for User Story 3

- [X] T025 [US3] Replace the real Office365 mailbox address in `config/integrations.yaml` with an obvious non-functional placeholder, and add a comment that a real mailbox is supplied by whoever operates the system and is never committed — satisfies FR-024
- [X] T026 [US3] Replace the external tenant domain in the commented ticketing integration block in `config/integrations.yaml` with an obvious placeholder — satisfies FR-024
- [X] T027 [P] [US3] Confirm `reports/` is covered by `.gitignore` from T001 and verify the tool still creates and writes `reports/` and `reports/history/` at runtime, since `master_agent.py` calls `os.makedirs("reports", exist_ok=True)` — satisfies FR-025
- [X] T028 [US3] Create `CONFIDENTIALITY.md` with all eight required sections in order — Decision, Date, Accountable Owner, Rationale, What This Repository Must Never Contain, Accepted Exposures, Revisit Triggers, Related — naming the accountable **role** and explicitly flagging that the individual is not yet identified, listing the two seeded accepted exposures (`navadhiti` organisation name, Zoho People vendor name) each with a rationale naming why it cannot be protected, and stating that Dependabot activation remains a manual human action — satisfies FR-021, FR-022, FR-023, FR-026, per `contracts/confidentiality-record.md`
- [X] T029 [US3] Implement the `confidentiality-record` criterion in `tools/verify_baseline.py`: check the file exists, contains every required section heading, and is referenced from `README.md`. It MUST NOT parse the record's prose, evaluate its rationale, or judge any accepted exposure — per `contracts/confidentiality-record.md`
- [X] T030 [US3] Implement the `no-real-data` criterion in `tools/verify_baseline.py` with the module-level denylist literal seeded from FR-024 (mailbox address, tenant domain) plus the three structural rules (no tracked path under `reports/`, no uncommented `budget`/`headcount`/`timesheet_code` under `repos:` in `config/projects.yaml`, no stale accepted exposure). It MUST NOT implement a classifier that infers whether arbitrary content is real — per research.md D7

**Checkpoint**: All three stories work independently. Verifier registers all seven criteria and reports `PASS`.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T031 Update the "Project Status & Implementation Roadmap" table in `README.md`: add rows for every control this milestone introduced (ignore rules, test runner, internal-use notice, dependency scanning, secret guard, baseline verification, confidentiality record) and correct any row that misstates current reality — satisfies FR-008, FR-009
- [X] T032 [P] Add a row to the `README.md` roadmap table stating plainly that the committed virtual environment **remains in the three existing commits** by decision, so a reader who inspects history and finds 1,989 environment files learns it was a choice — satisfies FR-005, FR-010, SC-012
- [X] T033 [P] Update `USAGE_AND_TECHNICAL_GUIDE.md` to reflect post-milestone reality, including the setup section and the new baseline verification command — satisfies FR-008
- [X] T034 [P] Verify in repository settings that `.github/workflows/baseline.yml` is **not** a required status check on the default branch, and record the finding — satisfies FR-033; a workflow that is silently gating is the exact failure this task exists to catch
- [X] T035 Run all ten validation scenarios in `quickstart.md` and record the result of each, including Scenario 5 (verifier run outside a repository exits `2`, not `0` and not `1`) and Scenario 9 (a pull request with a failing job still merges) — satisfies SC-001 through SC-017
- [X] T036 Run `python tools/verify_baseline.py` on the final tree and confirm `verdict: PASS (7 of 7 criteria passed)` with exit code 0, then confirm the tracked-file count is under 100 — satisfies SC-001, SC-015

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on T001–T004 — BLOCKS US2 and US3
- **User Story 1 (Phase 3)**: Depends on Phase 2. Depends on no other story.
- **User Story 2 (Phase 4)**: Depends on Phase 2. Depends on no other story.
- **User Story 3 (Phase 5)**: Depends on Phase 2. Depends on no other story — its config scrub and record are independent of US1 and US2.
- **Polish (Phase 6)**: Depends on all three stories

### User Story Dependencies

- **User Story 1 (P1)**: After Phase 2. No story dependencies.
- **User Story 2 (P2)**: After Phase 2. No story dependencies. Its criteria are registered alongside US3's in the same registry; whoever finishes second simply adds to a list that already exists.
- **User Story 3 (P3)**: After Phase 2. No story dependencies.

All three stories are independently completable and independently testable. US3 does not require US2's criteria to exist, and US2 does not require `CONFIDENTIALITY.md`.

### Within Each User Story

- Tests MUST be written and confirmed failing before implementation
- Criterion implementation after its test, not before
- Registry entries added last within a story, so the criterion count is the visible progress signal
- Story complete before moving to the next priority

### Parallel Opportunities

- All four Setup tasks marked [P] run together
- T007 runs alongside T005/T006 — different concern, same file, sequential within the file
- After Phase 2, US1, US2, and US3 can proceed in parallel
- Within US2: T016, T017, T018, T021, T022 all touch distinct files and run together
- Within US3: T023, T024, T027, T028 all touch distinct files and run together

---

## Parallel Example: User Story 2

```bash
# Launch together — five distinct files, no shared state:
Task: "T016 [P] [US2] Create NOTICE at the repository root"
Task: "T017 [P] [US2] Create .github/dependabot.yml with pip ecosystem"
Task: "T018 [P] [US2] Create .pre-commit-config.yaml and .secrets.baseline"
Task: "T021 [P] [US2] Document the secret-guard bypass in README.md"
Task: "T022 [P] [US2] Create .github/workflows/baseline.yml"
```

T019 and T020 both edit `tools/verify_baseline.py` and are therefore **not** parallel.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T004)
2. Complete Phase 2: Foundational (T005–T009)
3. Complete Phase 3: User Story 1 (T010–T014)
4. **STOP and VALIDATE**: fresh clone, follow the README verbatim, `pytest` green
5. Demo the clean checkout

### Incremental Delivery

1. Setup + Foundational → verifier framework runs
2. US1 → clean checkout and working documented setup (MVP)
3. US2 → reviewer's four questions answerable; secret guard live
4. US3 → confidentiality recorded and enforced; verifier reaches `PASS (7 of 7)`
5. Polish → documentation tells the truth

### Parallel Team Strategy

1. Team completes Setup + Foundational together
2. Then in parallel:
   - Developer A: US1 (checkout hygiene and documentation)
   - Developer B: US2 (licensing, dependency scanning, secret guard)
   - Developer C: US3 (confidentiality record, config scrub, data check)
3. US2 and US3 both edit `tools/verify_baseline.py` — coordinate those two, or sequence their criterion tasks

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps each task to its user story for traceability
- Every user story is independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate the story independently
- **T034 requires manual confirmation in repository settings and cannot be automated from the command line.** It is the one task that must be done by a person with repository admin access, alongside enabling Dependabot if the file alone does not activate it
- ⚠️ **The constitution is still unratified.** `.specify/memory/constitution.md` remains the unmodified template, so the Constitution Check in `plan.md` ran against Section A of the completion spec as a proxy and is marked provisional. This does not block these tasks — none of them touch check logic — but the gate must be re-run once `/speckit.constitution` is fed Section A