# Validation Record — Milestone 0 Own-Repository Baseline

**Date**: 2026-10-05 | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)
**Branch**: `001-fix-own-repo-hygiene` at `ff417dc` | **Task**: T035, T036

Every scenario in [quickstart.md](./quickstart.md) was executed. Results below
are what actually happened, including two places where the quickstart itself was
wrong and is annotated as such.

---

## Summary

| # | Scenario | Expectation | Result |
| :--- | :--- | :--- | :--- |
| 1 | Fresh clone is small and clean | < 100 tracked, 0 under `venv/` | **PASS** — 68 tracked, 0 environment files |
| 2 | Test suite runs green | success status, zero failures | **PASS** — 107 passed, exit 0, on a fresh clone |
| 3 | Baseline verification passes | 7 `pass`, `verdict: PASS`, exit 0 | **PASS** |
| 4 | The check fails loudly | 1 `fail` on `no-real-data`, names the line, hides the value, exit 1 | **PASS** |
| 5 | A broken verifier is not a healthy repository | exit `2` | **PASS**, but the quickstart's procedure was wrong — see below |
| 6 | Secret guard blocks a token | blocked, and the documented bypass works | **PASS with a correction** — the `nextline` bypass does not work |
| 7 | Existing clone reaches a clean state | clean, environment intact | **PASS** — 2,033 → 68 tracked, `venv/` untouched |
| 8 | Documentation tells the truth | no placeholder names, real URL, record linked | **PASS** |
| 9 | Automated run, no local setup | job runs, same verdict, does not block | **Verified after push** — see below |
| 10 | Dependency scanning configured | `version: 2`, `pip` present, reports `configured` | **PASS** |

**Definition of done** (T036): `verdict: PASS (7 of 7 criteria passed)`, exit
`0`, 68 tracked files.

---

## 1 — Fresh clone is small and clean

```text
git ls-files | wc -l             68      (was 2,033; requirement is < 100)
git ls-files | grep -c '^venv/'   0      (was 1,989)
git ls-files | grep -c '__pycache__'  0
git ls-files | grep -c '^reports/'    0
ls venv/                     No such file or directory   (correct: a fresh clone has none)
```

Satisfies SC-001, FR-001, FR-002, FR-003.

## 2 — Test suite runs green

Executed on the fresh clone, following the README installation section verbatim
with no undocumented step:

```text
python3 -m venv venv                 venv created
pip install -r requirements.txt      ok — no separate test-tooling install step
pytest                               107 passed, exit 0
```

Satisfies SC-002, FR-012, FR-013, FR-015.

The count is **107, not 44**. The plan assumed 44; the suite actually contained
**48** tests at HEAD. No test was removed or weakened — the 48 pre-existing tests
are intact and 59 verifier tests were added. FR-015's disclosure is a
correction to the plan's figure, not a loss.

## 3 — Baseline verification passes

```text
verdict: PASS (7 of 7 criteria passed)
exit=0
```

Satisfies SC-015, FR-028, FR-029, FR-031. Full output in the PR description.

## 4 — The check fails loudly

```text
  fail         no-real-data   1 no-real-data violation(s) in tracked content: ...
                              config/integrations.yaml:37  denied identifier (22 chars)
verdict: FAIL (1 of 7 criteria failed)
exit=1
```

Occurrences of the identifier anywhere in stdout+stderr: **0**. The output names a
path, a line number and a length, never the value.

Idempotence confirmed: after reverting, `exit=0` again. Same commit, same verdict.

Satisfies SC-003, SC-014, FR-029, FR-031, Principle 7.

## 5 — A broken verifier is not a healthy repository

**The quickstart's procedure cannot produce the result it expects.** It runs
`cd /tmp && python /path/to/repo/tools/verify_baseline.py` and expects `exit=2`.

The verifier resolves the repository root from its own location, because the CLI
contract requires it to work from any working directory. Pointing it at the real
checkout from `/tmp` therefore correctly succeeds:

| Invocation | Exit | Correct? |
| :--- | :---: | :--- |
| `cd /tmp && python <repo>/tools/verify_baseline.py` | `0` | Yes — cwd must not matter |
| script copied outside a git repository | `2` | Yes — "I could not look" |

```text
$ python /tmp/nh_outside/tools/verify_baseline.py
verifier could not run: /private/tmp/nh_outside is not a git repository
this says nothing about the repository's health; exit 2 means 'I could not look', not 'it is fine'
exit=2
```

**Recorded as a quickstart defect**, not a verifier defect. The contract's
"must not depend on `cwd`" and the scenario's expectation are in direct conflict;
the contract wins, because a verifier whose verdict depends on where you ran it
would make local and CI runs disagree (FR-034). `quickstart.md` should be amended
to copy the script out before running it.

## 6 — Secret guard blocks a token, and the bypass works

| Case | Exit | Correct? |
| :--- | :---: | :--- |
| token committed to `config/standard.yaml`, no pragma | `1` blocked | Yes |
| `# pragma: allowlist secret` on the same line | `0` allowed | Yes — FR-019 satisfied |
| finding recorded in `.secrets.baseline` | `0` allowed | Yes |
| `# pragma: allowlist nextline secret` on the line above | **`1` blocked** | **No** |

Occurrences of the token in the guard's message: **0**. The block names the file,
the line, and the detector (`GitHub Token`, `Base64 High Entropy String`), and
explains the pragma mitigation.

**The `nextline` bypass does not work**, and the quickstart and research both
document it as available. `detect-secrets` v1.5.0 ships a regex that matches
`# pragma: allowlist nextline secret`, and `is_line_allowlisted()` returns `True`
when called with that line as `previous_line` — but the pre-commit hook path
(`detect-secrets-hook`) still blocks the commit. Verified against v1.5.0 by
running the hook directly against five placements (no blank line, blank line,
indented, hyphenated variant, and same-line).

FR-019 requires *a* documented bypass that works without disabling the guard. Two
do, and the README now documents those two and states plainly that the
`nextline` form does not work, so nobody spends an afternoon on it.

Satisfies SC-007, FR-017, FR-018, FR-019, FR-020.

## 7 — Existing clone reaches a clean state

Run against a clone checked out at the pre-milestone commit `1e2d98e`, with a
contributor's own `venv/` on disk, using the README's documented procedure
verbatim:

| | Tracked files | `venv/` tracked | `venv/` on disk |
| :--- | ---: | ---: | :--- |
| before | 2,033 | 1,989 | yes |
| after `git rm -r --cached` | 29 | 0 | **yes, 12 binaries intact** |
| after pulling this branch | 68 | 0 | **yes** |

`git status --porcelain` is empty at the end. `source venv/bin/activate` still
works immediately after the `git rm`. Time taken: well under the 2 minutes
SC-011 allows.

Satisfies SC-011, FR-004, FR-011.

## 8 — Documentation tells the truth

| Check | Result |
| :--- | :--- |
| `mock-org` anywhere in the docs | 0 |
| `cd hygiene` in the README | 0 — there is no `hygiene/` directory; this was a real bug |
| Real clone URL present | yes |
| `CONFIDENTIALITY.md` referenced from the README | 4 references |
| History residue stated | 8 mentions of "history"; the 1,989 figure is stated |
| Installation commands, in order | `git clone` → `cd` → `python3 -m venv` → `source` → `pip install -r requirements.txt` — all executed on a fresh clone, in that order |

Satisfies SC-005, SC-006, SC-008, SC-009, SC-010, SC-012, FR-006, FR-007, FR-008.

## 9 — Automated run, no local setup

Verified after the pull request was opened; see the record appended to the PR.
The finding relevant to FR-033:

```text
GET /repos/jayanthbagare/navadhiti_hygiene/branches/main/protection
  → 404 "Branch not protected"

GET /repos/jayanthbagare/navadhiti_hygiene/rulesets
  → []

GET /repos/jayanthbagare/navadhiti_hygiene
  → visibility: public, default_branch: main
  → security_and_analysis.dependabot_security_updates: enabled
  → security_and_analysis.secret_scanning: enabled
```

`main` carries **no protection** and the repository has **no rulesets**, so there
are zero required status checks and the advisory `baseline` job cannot be gating.
That satisfies FR-033 for T034 — a workflow that is silently a required check is
the failure that requirement exists to prevent, and it is not the case.

Two further facts fall out of the same query:

- The repository is still **public**. FR-026 holds: nothing in this milestone
  touched visibility.
- Dependabot **security** updates are already enabled. Dependabot **version**
  updates from `.github/dependabot.yml` are a separate switch, and GitHub exposes
  no API field for it. That is the concrete reason the verifier reports
  `configured` rather than `active`, and it is recorded as a human action.

## 10 — Dependency scanning is configured

```text
version:    2
ecosystems: ['pip']
directory:  ['/']
interval:   ['weekly']
```

And what the verifier claims:

```text
status   : pass
detail   : .github/dependabot.yml configured for pip (activation not verifiable from the repository)
observed : {'ecosystems': ['pip'], 'activation': 'not_verifiable'}
```

Satisfies FR-016, and the honesty requirement of Principle 3.

---

## Findings carried forward

Not fixed here, because fixing either would mean inventing a standard or a scope
that this milestone does not hold. Recorded so they are decisions rather than
accidents.

1. **`quickstart.md` Scenario 5 conflicts with the CLI contract.** The scenario's
   procedure cannot produce exit `2` while the contract requires cwd-independence.
   Amendment needed; the contract is correct as written.

2. **The `nextline` allowlist pragma does not work through the pre-commit hook**
   (§6). Documented in the README as a non-working form. If `detect-secrets` fixes
   it, the README note should be removed.

3. **`no-real-data` part 2 is scoped to the `repos:` block of
   `config/projects.yaml`,** exactly as `contracts/verify-baseline-cli.md`
   specifies. A `budget:` uncommented under the `overrides:` block would therefore
   pass. Widening the check to every mapping in the file would close the gap with
   no false positives, but it is a change to a signed contract and needs the
   contract's owner, not an implementer.

4. **The constitution is still unratified.** `.specify/memory/constitution.md` is
   the unmodified template, so the plan's constitution gate ran provisionally
   against Section A of the completion spec as a proxy.

5. **The accountable owner is not yet a named person.** `CONFIDENTIALITY.md` names
   the role and flags the gap explicitly, as FR-021 permits.