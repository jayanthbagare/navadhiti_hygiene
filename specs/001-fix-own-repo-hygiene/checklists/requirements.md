# Specification Quality Checklist: Navadhiti Hygiene System — Milestone 0 Own-Repository Baseline

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-05
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] CHK001 No implementation details (languages, frameworks, APIs)
- [x] CHK002 Focused on user value and business needs
- [x] CHK003 Written for non-technical stakeholders
- [x] CHK004 All mandatory sections completed

## Requirement Completeness

- [x] CHK005 No [NEEDS CLARIFICATION] markers remain
- [x] CHK006 Requirements are testable and unambiguous
- [x] CHK007 Success criteria are measurable
- [x] CHK008 Success criteria are technology-agnostic (no implementation details)
- [x] CHK009 All acceptance scenarios are defined
- [x] CHK010 Edge cases are identified
- [x] CHK011 Scope is clearly bounded
- [x] CHK012 Dependencies and assumptions identified

## Feature Readiness

- [x] CHK013 All functional requirements have clear acceptance criteria
- [x] CHK014 User scenarios cover primary flows
- [x] CHK015 Feature meets measurable outcomes defined in Success Criteria
- [x] CHK016 No implementation details leak into specification

## Requirement-to-Evidence Traceability

- [x] CHK017 Every functional requirement maps to at least one measurable outcome
- [x] CHK018 Every measurable outcome is produced by at least one requirement
- [x] CHK019 Baseline figures cited in the problem statement are verifiable against the repository
- [x] CHK020 Each user story is independently testable without the others

## Findings and Notes

**CHK005 fails** — three clarifications remain open, presented to the user below.
They are confined to scope and confidentiality decisions that only a human can
make; none of them blocks the rest of the milestone.

### Baseline figures verified against the repository

| Claim in spec | Verified value | Source |
| :--- | :--- | :--- |
| Environment files tracked | 1,989 | `git ls-files` under `venv/` |
| Total tracked files | 2,033 | `git ls-files \| wc -l` |
| Ignore file present | No | no `.gitignore` at repository root |
| Test runner declared | No | `requirements.txt` lists only `pydantic`, `PyYAML`, `requests` |
| Existing tests | 44 | `tests/test_hygiene.py` |
| Licensing artifact | No | no `LICENSE*` file at repository root |
| Dependency scanning | No | no `.github/` directory |
| Secret guard | No | no pre-commit configuration |
| Clone URL in README | Already correct | `https://github.com/jayanthbagare/navadhiti_hygiene.git` |
| Placeholder URL remaining | None found | no `mock-org` reference in any tracked file |

**Correction carried into the spec**: the completion spec describes the README
clone URL as pointing at a placeholder. It does not — it already references the
real repository. FR-006 is retained because it also covers the general rule
(no placeholder may remain anywhere in the documentation), but the acceptance
scenario is written so it passes on the current state rather than claiming credit
for a fix that was never needed.

### Clarification sessions

**Session 2026-10-05** — six questions answered, all recorded in the spec's
`## Clarifications` section. No `[NEEDS CLARIFICATION]` markers remain.

| # | Decision | Answer |
| :--- | :--- | :--- |
| 1 | Repository visibility | Stays public, under a documented no-real-data policy |
| 2 | Committed environment in history | Forward history corrected only; no rewrite |
| 3 | Licensing form | Internal-use notice, no formal license terms |
| 4 | Which committed identifiers to scrub | Mailbox address and tenant domain replaced; organisation and vendor recorded as accepted exposures |
| 5 | What enforces the no-real-data policy | Deterministic check inside the single baseline verification command |
| 6 | When the baseline check runs | Automatically on pull requests; reports, does not block |

### Deliberate scope boundaries

- FR-025's baseline verification command is a single repeatable command, which the
  completion spec lists under acceptance criteria as "visibility decision
  recorded". Making it explicit keeps "keep the docs true" testable rather than
  aspirational.
- FR-033 fixes the automated baseline run as **non-blocking**. Switching
  enforcement on by automation is forbidden by the governing principles, and
  merge-blocking enforcement is a later milestone with its own human decision.
  If the accountable owner wants this repository gated, that is a one-line change
  and a deliberate act — not a default.
- FR-030 forbids the no-real-data check from failing on the test suite's own
  sample budgets and report fixtures, and requires any exemption to be written
  down. A check that cries wolf on fixtures gets disabled.
- The milestone makes no change to check logic, scoring, or enforcement
  activation, so that an audit finding can never be confused with a simultaneous
  change to the auditing tool.

### Remaining open item for a human, outside the spec

The constitution has not been ratified — `.specify/memory/constitution.md` is
still the unmodified template. Milestone 0 changes no check logic so it does not
depend on ratified principles, but the completion spec requires the constitution
to be established before the milestone loop begins.

Items marked incomplete require spec updates before `/speckit.clarify` or
`/speckit.plan`.