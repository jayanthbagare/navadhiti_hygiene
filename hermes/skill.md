---
name: navadhiti-hygiene
description: Observes and (for promoted/new projects) enforces project hygiene across Navadhiti repos — environment separation, UAT signoff, cost variance, security baseline, deploy/signoff gaps. Invoke on schedule or when asked for a hygiene/cost/UAT status across projects.
---

# Navadhiti Hygiene Skill

## What this skill is, and what it is not

This skill is the **orchestration and judgment layer**. It decides which
repos matter this run, dispatches checks, interprets ambiguous results,
and writes the human-facing report. It does **not** itself compute
pass/fail on any dimension, and it does not compute cost variance or
parse dates by reasoning about them — those are deterministic and live in
scripts under `core/checks/`, built per `navadhiti-hygiene-agents-spec.md`.

If a required script is missing, say so explicitly and stop — do not
approximate a check by reasoning about the repo yourself. A skill that
quietly substitutes judgment for a missing deterministic check reintroduces
the exact problem this system exists to remove (see: why email-parsed
signoff is transitional, not the target, in the build spec).

**Dependency:** this skill assumes `core/checks/*` scripts and
`config/*.yaml` (standard.yaml, projects.yaml, integrations.yaml,
master.yaml) already exist, per the companion build spec. If they don't
exist yet, this skill cannot run — flag that instead of proceeding.

---

## Step 1 — Select in-scope repos (master agent role)

1. Query the configured git provider(s) (from `config/integrations.yaml`)
   for the full repo list and each repo's last-commit-date.
2. Filter to repos with `last_commit_date >= now - activity_window_days`
   (from `config/master.yaml`, default 60).
3. Log which repos were excluded and why (dormant vs archived vs no
   access) — this list matters as much as the included one; someone will
   ask why a project isn't showing up.

Do not hardcode a repo list. Do not carry forward last run's list. Recompute
this every invocation.

## Step 2 — Determine mode per repo

For each in-scope repo, check its promotion state (tracked in
`reports/promotion_state.yaml` or equivalent — the one piece of state this
system persists across runs):

- Not yet promoted → **Observer mode**.
- Promoted (per Phase 3 threshold in the build spec) → **Enforcer mode**,
  though in practice Enforcer runs as a CI gate at merge time, not from
  this scheduled skill — this skill still reports on promoted projects in
  read-only fashion between merges.
- New project (created after this system went live) → **Enforcer mode**
  from day one.

## Step 3 — Dispatch checks (sub-agent role, one per repo)

For each in-scope repo, run the deterministic checks by invoking the
scripts directly — do not reimplement their logic inline:

```
core/checks/environment.py   <repo>
core/checks/ci_gates.py      <repo>
core/checks/signoff.py       <repo> <sprint_id>
core/checks/cost.py          <repo> <timesheet_code>
core/checks/security.py      <repo>
core/checks/deploy_history.py <repo>
```

Each returns a JSON fragment matching the shared schema
(`core/schema.py` / `hygiene-schema.yaml`). Collect these into one
per-repo report.

This step can run in parallel across repos — sub-agents don't need to
know about each other.

## Step 4 — Judgment calls (this is where the skill, not the scripts, decides)

This is the part that's legitimately agent-native — use judgment here,
but stay inside these bounds:

- **`undefined_standard` or `unverifiable` results**: do not guess a
  pass/fail. Surface them plainly in the report as open items, and if a
  standard is missing (e.g. `standard.yaml` has no definition for a
  dimension a repo hit), name that as a blocking prerequisite, not a repo
  failure.
- **`email_parsed` signoff results**: report these as lower-confidence
  than `repo_artifact` results, visibly — don't average them into the
  same score with equal weight without flagging the method.
- **Enforcement-eligibility recommendation**: apply the Phase 3 threshold
  (N consecutive sprints of `environment_separation: pass` and
  `uat_signoff.method: repo_artifact`) and *recommend* promotion — do not
  auto-promote. A human flips the CI gate. Say this explicitly in the
  output so it isn't mistaken for an automatic action.
- **Narrative summary across the aggregate**: this is genuinely a job for
  reasoning, not a script — e.g. "3 of 11 in-scope projects account for
  most of the cost variance this run" or "gap_flag incidents cluster in
  the two weeks after a release." Say what the data shows; don't infer
  causes the data doesn't support.

## Step 5 — Compose and emit the report

One aggregate report per run:

- Table of in-scope repos with hygiene_score, gap_flag count, variance_pct.
- Explicit call-outs: any `gap_flag: true` (deploy with no signoff), any
  `enforcement_eligible: true` (promotion candidates), any
  `undefined_standard` blocking a dimension org-wide.
- Excluded-repo list from Step 1, with reason.
- Nothing about cost, signoff, or security should be phrased more
  confidently than the underlying script's `status` field supports.

Write to `reports/<date>-aggregate.md` (or `.json` if downstream tooling
needs it) and, if the harness supports it, surface the top-line summary
(gap flags + promotion candidates) directly in the response rather than
requiring someone to open the file.

---

## Explicit boundaries

- This skill never merges, blocks, or modifies a repo. Enforcement
  (blocking a merge) happens in CI, via the Enforcer script — this skill
  only reports, recommends, and dispatches.
- This skill never invents a cost figure, a budget, or a standard
  definition. Those come from config or they don't appear.
- This skill never treats an email-parsed signoff as equivalent evidence
  to a repo artifact, even when reporting summary statistics.
- If asked to run against a repo outside the activity window, say so and
  ask whether to override the window for that one repo rather than
  silently including it.
