# Contract: Confidentiality Record

**Date**: 2026-10-05 | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

Governs `CONFIDENTIALITY.md`. Enforced by FR-021, FR-022, FR-023, FR-024, FR-026, FR-027, and clarification Q1 and Q4.

---

## Purpose

The repository is public. This file records the deliberate decision that it stays public under a no-real-data policy, so that the exposure is a choice on the record rather than an accident nobody noticed.

The verifier checks this file for **presence and completeness only**. It never interprets its prose, evaluates its rationale, or judges whether an accepted exposure is reasonable. Reading and approving the content is a human act.

---

## Required sections

The verifier locates each section by heading text. Headings must appear in this order.

```markdown
# Confidentiality and Data-Handling Decision

## Decision
## Date
## Accountable Owner
## Rationale
## What This Repository Must Never Contain
## Accepted Exposures
## Revisit Triggers
## Related
```

| Section | Content | Enforced by |
| :--- | :--- | :--- |
| `Decision` | States the repository remains public. | FR-021, FR-026 |
| `Date` | ISO-8601 date the decision was taken. | FR-021 |
| `Accountable Owner` | A named person, **or** the role plus an explicit statement that the individual is not yet identified. FR-021 permits the role form; an unstated gap does not satisfy it. | FR-021 |
| `Rationale` | Why public-with-policy rather than private. Must reference the alternative that was rejected. | FR-021 |
| `What This Repository Must Never Contain` | Concrete exclusions, per FR-023: live run output, real project names with budgets, real headcount or salary-derived rates, live credential or token values, internal correspondence. Each must be specific enough for a contributor to act on without asking. | FR-023 |
| `Accepted Exposures` | One entry per deliberate exposure, each with identifier, category, and rationale. **Present even when empty.** | FR-024 |
| `Revisit Triggers` | Conditions forcing reconsideration. | FR-021 |
| `Related` | Links to the README section and, if written, the constitution. | FR-027 |

---

## Accepted Exposures format

Seeded from clarification Q4. Each entry uses this shape.

```markdown
| Identifier | Category | Rationale |
| :--- | :--- | :--- |
| `navadhiti` | Organisation name | Already disclosed by this repository's own address. Editing it out protects nothing and makes the tool unrunnable out of the box. |
| Zoho People | Vendor name | Identifies a supplier, not Navadhiti. Not re-identifying on its own. |
```

### Rules

1. **Every accepted exposure must correspond to an identifier actually present in tracked content.** The verifier cross-checks this and reports a stale exposure as a failure. An exposure for an identifier that is gone is a gap in the denylist masquerading as a decision.
2. **Every accepted exposure must carry a rationale that names why it cannot be protected.** "We decided it's fine" is not a rationale; "the repository address already discloses it" is.
3. **The section is never omitted.** An empty table means "nothing is deliberately exposed". A missing section means the record is incomplete, and the two are different statements.
4. **Adding an exposure is a reviewable diff.** It must not be done silently in the same change that introduces the identifier.

---

## Verified invariants

The `confidentiality-record` and `no-real-data` criteria together guarantee:

| Invariant | Source |
| :--- | :--- |
| No tracked file contains the real mailbox address | Denylist entry 1 |
| No tracked file contains the real external tenant domain | Denylist entry 2 |
| No tracked file under `reports/` | Structural rule |
| No uncommented budget, headcount, or timesheet code in `config/projects.yaml` | Structural rule |
| Every committed identifier is either a placeholder or a named accepted exposure | Denylist + stale-exposure cross-check |
| The repository's visibility was never changed by this milestone | FR-026 — no tooling touches repository settings |

---

## What this contract does not do

- It does not change repository visibility. FR-026 forbids any automated step from attempting it; no tooling in this milestone touches hosting settings.
- It does not create a mechanism for submitting real data. The exclusions are enforced by the `no-real-data` criterion, not by a form someone is asked to fill in (Constitution Principle 1).
- It does not transfer the decision. It records it. A human owns it, and the revisit triggers say when to look again.
- It does not hide the history. The committed virtual environment remains in the three existing commits (clarification Q2), and the README roadmap says so plainly (FR-010). A reader who finds 1,989 environment files in history learns it was a decision.