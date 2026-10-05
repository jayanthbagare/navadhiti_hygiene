# Phase 1 Data Model: Milestone 0 Own-Repository Baseline

**Date**: 2026-10-05 | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

These entities describe the *repository's own health baseline*. They are **not** part of `core/schema.py` and are not consumed by the hygiene scanner — this milestone does not touch check logic (spec Out of Scope). They exist only to give `tools/verify_baseline.py` a stable internal shape and to give a reviewer something to check the implementation against.

---

## Criterion

A single baseline assertion the verifier evaluates.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `id` | str | yes | Stable machine identifier, kebab-case. Never renumbered; a renamed criterion breaks history comparisons. |
| `label` | str | yes | Human-readable one-line description, printed in output. |
| `requirements` | list[str] | yes | Spec FRs this criterion enforces. Every criterion traces to at least one. |
| `determination` | enum | yes | `observed` — the verifier reads repository state and reaches a verdict. No other value is permitted in this milestone. |
| `cannot_determine_action` | enum | yes | What to report when the criterion cannot be evaluated: `report_unverifiable` or `fail`. |

**Why `determination` exists as a field**: Constitution Principle 3 — undefined is not failed. Encoding this as data rather than as scattered `if` branches means the distinction between "I checked and it is wrong" and "I could not check" is visible in the criterion list itself, and a new criterion cannot be added without deciding which it is.

**Validation rules**:
- `id` matches `^[a-z0-9-]+$`, unique within the run.
- `requirements` is non-empty. A criterion traceable to no requirement is scope creep and must be rejected.
- A criterion whose `determination` is not `observed` is rejected at startup, not at evaluation time.

---

## CriterionResult

The outcome of evaluating one Criterion against the working tree.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `criterion_id` | str | yes | Foreign key to `Criterion.id`. |
| `status` | enum | yes | `pass`, `fail`, or `unverifiable`. |
| `detail` | str | yes | One line of plain language. For `fail`, what is wrong. For `unverifiable`, what could not be determined and why. |
| `evidence` | list[str] | no | Repository-relative paths that evidence the verdict. Empty on `pass` unless a path is genuinely informative. |
| `observed` | dict | no | Machine-readable values behind the verdict. Free-form per criterion. |

**Security rule — binding**: no field may ever contain a detected credential value, token fragment, or live identifier. `detail` and `observed` reference a *path*, a *count*, a *line number*, or a *pattern name*. This is Constitution Principle 7 and is not negotiable per criterion.

**Validation rules**:
- `status: fail` requires non-empty `detail`.
- `status: unverifiable` requires `detail` to name what was missing, so that the output distinguishes "not checked" from "checked and fine".
- `status: pass` with a non-empty `evidence` list is permitted but must not imply a defect was found.

---

## BaselineReport

The complete result of one verifier run.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `criteria` | list[CriterionResult] | yes | One per Criterion, in declared order. |
| `verdict` | enum | yes | `pass` only if every result is `pass`. Any `fail` → `fail`. Any `unverifiable` → `fail`. |
| `commit` | str | no | Git commit SHA the run evaluated. Absent outside a repository. |
| `generated_at` | str | yes | ISO-8601 UTC timestamp. Informational only. |
| `blocking` | bool | yes | Always `false` in this milestone, per FR-033. Present so that the value is stated rather than implied, and so a later milestone can change it deliberately. |

**Verdict rule — why `unverifiable` fails the run**: FR-031 requires a partially-passing baseline to be reported as a failure, and a check that cannot run is not a check that passed. Since FR-033 keeps the run non-blocking, a verdict of `fail` is informative rather than obstructive — which is exactly the "observe before enforcing" posture Principle 5 requires.

**Idempotence**: two runs against the same commit MUST produce identical `criteria`. `generated_at` is excluded from that guarantee by design, being the only intentionally varying field (FR-034, Principle 8).

---

## ConfidentialityRecord

The human-readable decision record at `CONFIDENTIALITY.md`. Parsed only for *presence and required sections* — the verifier never interprets its content as data.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `decision` | str | yes | Public. Fixed by clarification Q1. |
| `date` | date | yes | When the decision was taken. |
| `owner` | str | yes | Accountable person, or the role plus an explicit gap flag when unknown. |
| `rationale` | str | yes | Why this decision rather than the alternative. |
| `excluded_categories` | list[str] | yes | Concrete, actionable exclusions per FR-023. |
| `accepted_exposures` | list[AcceptedExposure] | yes | Deliberate exposures with rationale. May be empty, never unstated. |
| `revisit_triggers` | list[str] | yes | Conditions that force reconsideration. |

**Validation rules**:
- The verifier checks that each required section heading is present. It does **not** parse prose, evaluate the rationale, or judge whether an accepted exposure is reasonable. Reading and approving the content is a human act; automating that judgement is the failure mode Principle 1 describes.
- `accepted_exposures` and `revisit_triggers` must be present even when empty. A missing section and an empty section mean different things: the first is an incomplete record, the second is a decision that nothing qualifies.

---

## AcceptedExposure

An identifier deliberately committed despite the no-real-data policy.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `identifier` | str | yes | What is exposed. For `navadhiti`, the literal string — it is already public via the repository address. |
| `category` | str | yes | What kind of thing it is, e.g. organisation name, vendor name. |
| `rationale` | str | yes | Why protecting it is impossible or not worthwhile. |

**Seeded from clarification Q4**:

| Identifier | Category | Rationale |
| :--- | :--- | :--- |
| `navadhiti` | Organisation name | Already disclosed by this repository's own address. Editing it out protects nothing and makes the tool unrunnable out of the box. |
| Zoho People | Vendor name | Identifies a supplier, not Navadhiti. Not re-identifying on its own. |

**Validation rule**: an AcceptedExposure is only meaningful if the identifier is *actually present* in tracked content. The verifier cross-checks: an exposure listed for an identifier that is no longer committed is reported as stale, because a stale exposure hides the fact that a real identifier could now be committed without tripping any check.

---

## Relationships

```text
Criterion 1 ────< CriterionResult          (one result per criterion, always)
CriterionResult >──── Criterion             (result references criterion by id)
CriterionResult * ──── BaselineReport       (report aggregates all results)

ConfidentialityRecord 1 ────< AcceptedExposure   (record lists its exposures)
BaselineReport * ──────────── ConfidentialityRecord
        (verifier reports on the record's presence and completeness,
         never on its content)
```

---

## Explicit non-entities

Named to prevent scope drift. None of these exists, and creating one during implementation is a scope violation:

- **No `Compliance` score.** This milestone produces a pass/fail verdict on a fixed criterion list. It does not produce a number, a grade, or a trend. Numbers invite comparison between runs, and a baseline that improves is not more correct than one that merely differs.
- **No `RiskLevel`.** Consistent with the spec's prohibition on risk ratings the data does not support.
- **No `Policy` model encoding rules the verifier infers.** The no-real-data policy is an explicit denylist plus structural rules (D7). It is never inferred from the record's prose.