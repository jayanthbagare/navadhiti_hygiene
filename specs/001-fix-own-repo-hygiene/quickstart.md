# Quickstart: Validating Milestone 0

**Date**: 2026-10-05 | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

Runnable scenarios proving the feature works end to end. Each maps to an acceptance scenario or success criterion. Implementation detail lives in `tasks.md`; this is the validation runbook.

Reference documents: [verify-baseline-cli.md](./contracts/verify-baseline-cli.md) · [confidentiality-record.md](./contracts/confidentiality-record.md) · [data-model.md](./data-model.md)

---

## Prerequisites

```bash
git clone https://github.com/jayanthbagare/navadhiti_hygiene.git
cd navadhiti_hygiene
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` MUST now include the test runner, so no separate install step is needed (research D3).

---

## Scenario 1 — Fresh clone is small and clean

*Validates SC-001, FR-001, FR-003, FR-002*

```bash
git ls-files | wc -l                              # expect: < 100
git ls-files | grep -c "^venv/"                  # expect: 0
ls venv/                                         # expect: exists (local only)
```

A fresh clone has no `venv/` on disk. Your own `venv/` exists after the steps above and is not tracked — that is the point.

---

## Scenario 2 — Test suite runs green

*Validates SC-002, FR-012, FR-013, FR-015*

```bash
pytest
```

Expect **44 passed** and exit code 0. The 44 tests are the pre-existing ones, unmodified (D1). A count other than 44 means a test was lost without FR-015's written reason.

---

## Scenario 3 — Baseline verification passes

*Validates SC-015, FR-028, FR-029, FR-031*

```bash
python tools/verify_baseline.py; echo "exit=$?"
```

Expect seven `pass` lines, `verdict: PASS`, `exit=0`, and the non-blocking disclaimer.

---

## Scenario 4 — The check fails loudly

*Validates SC-003, SC-014, FR-029, FR-031*

Introduce a violation, observe it, revert.

```bash
cp config/integrations.yaml /tmp/integrations.yaml.bak

# The denied identifier is read from the verifier's own denylist rather than
# written here: this file is tracked content the same check scans, so a
# plaintext copy in the runbook would make the check match its own
# documentation.
DENIED_ID=$(python3 -c "import sys; sys.path.insert(0, 'tools'); \
import verify_baseline as v; print(v.DENIED_IDENTIFIERS[0])")
printf '\nmailbox: "%s"\n' "$DENIED_ID" >> config/integrations.yaml

python tools/verify_baseline.py; echo "exit=$?"

cp /tmp/integrations.yaml.bak config/integrations.yaml
```

Expect exactly one `fail` on `no-real-data`, naming `config/integrations.yaml` and a line number. **The printed output must not contain the address itself** (Principle 7). Then `exit=1`.

Re-run and confirm `exit=0` again — the check is idempotent (FR-034).

---

## Scenario 5 — A broken verifier is not a healthy repository

*Validates the exit `1` / `2` split — the contract's core guarantee*

> **Amended after the validation run of 2026-10-05.** This scenario originally
> read `cd /tmp && python /path/to/repo/tools/verify_baseline.py` and expected
> `exit=2`. That procedure cannot produce that result, because the CLI contract
> requires the verifier to resolve the repository root from its own location and
> to work from any working directory. Run that way against a real checkout, it
> correctly exits `0`. The contract is right and this scenario was wrong — a
> verifier whose verdict depended on where you ran it would make local and CI
> runs disagree, which FR-034 forbids. To get "outside a repository", copy the
> script out:

```bash
mkdir -p /tmp/nh-outside/tools
cp tools/verify_baseline.py /tmp/nh-outside/tools/
python /tmp/nh-outside/tools/verify_baseline.py; echo "exit=$?"
```

Expect `exit=2`, not `0` and not `1`. A caller must be able to tell "the repo is wrong" from "I could not look" without reading prose.

For completeness, the cwd-independence case is its own check:

```bash
cd /tmp && python /path/to/navadhiti_hygiene/tools/verify_baseline.py >/dev/null; echo "exit=$?"
# expect 0 — cwd must not change the verdict
```

---

## Scenario 6 — Secret guard blocks a token in config

*Validates SC-007, FR-017, FR-018, FR-019*

```bash
pre-commit install                 # once per clone
cp config/standard.yaml /tmp/standard.yaml.bak
printf '\napi_token: "ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"\n' >> config/standard.yaml
git add config/standard.yaml
git commit -m "should be blocked"
cp /tmp/standard.yaml.bak config/standard.yaml
git reset
```

Expect the commit to be **blocked**, naming the file, the line and the detector. Expect the literal token **not** to be echoed back.

**False-positive bypass** (FR-019) — the inline pragma, on the **same line** as
the value:

```bash
printf '\n# example only, not a credential: ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8  # pragma: allowlist secret\n' >> config/standard.yaml
git add config/standard.yaml && git commit -m "allowlisted placeholder"
```

> **Amended after the validation run of 2026-10-05.** This scenario also
> offered `# pragma: allowlist nextline secret` on the line above the value.
> **That form does not work.** `detect-secrets` v1.5.0 ships a regex that matches
> it and `is_line_allowlisted()` returns `True` when handed that line as
> `previous_line`, but the pre-commit hook path still blocks the commit. Verified
> against five placements — no blank line above, blank line above, indented
> inside a mapping, hyphenated spelling, and same-line — all blocked. Two bypasses
> do work: the inline pragma above, and recording the finding in
> `.secrets.baseline` via `detect-secrets scan > .secrets.baseline`.

Expect the commit to **succeed**. That inline pragma is the documented bypass.

---

## Scenario 7 — Existing clone reaches a clean state

*Validates SC-011, FR-004, FR-011*

Simulates a contributor whose working copy still has the environment tracked:

```bash
git rm -r --cached venv >/dev/null 2>&1
git commit -m "untrack local environment" >/dev/null
git status --porcelain
```

Expect the `venv/` directory still present on disk (`ls venv/` works) and clean status. The documented recovery procedure in the README must get a contributor here without recreating their environment.

---

## Scenario 8 — Documentation tells the truth

*Validates SC-005, SC-006, SC-008, SC-009, SC-010, SC-012, FR-006, FR-007, FR-008*

```bash
grep -rn "mock-org" README.md USAGE_AND_TECHNICAL_GUIDE.md   # expect: no matches
grep -c "ghp_\.\.\." README.md                               # expect: >= 1 (real repo URL present)
grep -n "CONFIDENTIALITY.md" README.md                        # expect: >= 1 (record linked)
grep -n "history" README.md                                   # expect: the residue is stated
```

Then walk every command in the README installation section in order. Each must run without an undocumented step (FR-007).

---

## Scenario 9 — Automated run, no local setup

*Validates SC-016, SC-017, FR-032, FR-033*

Open a pull request touching any file.

Expect:
- The `baseline` job runs with no local setup.
- Its verdict matches Scenario 3 on the same commit.
- **The pull request merges even when the job reports failure** — the run is advisory (FR-033).

Confirm the workflow is not a required status check on the default branch. A workflow that is silently gating is the failure this requirement exists to prevent.

---

## Scenario 10 — Dependency scanning is configured

*Validates FR-016, and the honesty requirement of Principle 3*

```bash
python -c "import yaml,sys; d=yaml.safe_load(open('.github/dependabot.yml')); \
print('version:', d['version']); \
print('ecosystems:', [u['package-ecosystem'] for u in d['updates']])"
```

Expect `version: 2` and `pip` present. **The verifier reports `configured`, never `active`** — activation is a hosting-side fact with no evidence in the repository (Complexity Tracking entry 2).

---

## Definition of done

| # | Scenario | Spec requirement |
| :--- | :--- | :--- |
| 1 | Fresh clone is small and clean | SC-001, FR-001, FR-003 |
| 2 | Test suite green, 44 tests | SC-002, FR-012, FR-013 |
| 3 | Baseline verification passes | SC-015, FR-028, FR-031 |
| 4 | Fails loudly, names the file, hides the value | SC-003, SC-014, FR-029 |
| 5 | Broken verifier ≠ healthy repository | exit `1`/`2` split |
| 6 | Secret guard blocks, bypass works | SC-007, FR-017, FR-019 |
| 7 | Existing clone recovers | SC-011, FR-004, FR-011 |
| 8 | Documentation is true | SC-005, SC-006, SC-008, SC-012 |
| 9 | PR run matches local, blocks nothing | SC-016, SC-017, FR-033 |
| 10 | Dependency scanning configured | FR-016 |