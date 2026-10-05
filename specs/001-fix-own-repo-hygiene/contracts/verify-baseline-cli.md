# Contract: Baseline Verifier CLI

**Date**: 2026-10-05 | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

Governs `tools/verify_baseline.py`. Enforced by FR-013, FR-028, FR-029, FR-031, FR-032, FR-034.

---

## Invocation

```bash
python tools/verify_baseline.py
```

Stdlib only. No arguments required, no arguments accepted. The contract is deliberately fixed: FR-034 requires one command whose result is identical locally and in CI, and every optional flag is a chance for the two paths to disagree.

The verifier resolves the repository root from its own location, so it works from any working directory. It must not depend on `cwd`.

---

## Exit codes

| Code | Meaning | When |
| :--- | :--- | :--- |
| `0` | Baseline holds | Every criterion returned `pass`. |
| `1` | Baseline does not hold | Any criterion returned `fail` **or** `unverifiable`. |
| `2` | The verifier could not run | Not a repository finding. The verifier itself failed to start — unreadable config, no git, Python too old. |

**The `1` / `2` distinction is the contract's most important guarantee.** A broken verifier must never be reported as a healthy repository. A caller can trust `0`; a caller can distinguish "the repo is wrong" from "I could not look" without parsing text.

This is the tool applying Constitution Principle 6 to itself: fail closed, and say which failure it was.

---

## Output format

One line per criterion, then a verdict. Stable order — the declared criterion order, never sorted at runtime.

```text
navadhiti hygiene — repository baseline
commit: 1e2d98e4f0a3c2b1d8e9f0a1b2c3d4e5f6a7b8c

  pass  no-env-tracked        no virtual environment files are tracked (0 found, was 1989)
  pass  test-suite            44 tests passed
  pass  licensing-artifact    NOTICE present, internal-use notice
  pass  dependency-scanning   .github/dependabot.yml configured (activation not verifiable from the repository)
  pass  secret-guard          .pre-commit-config.yaml configures detect-secrets over config/*.yaml
  pass  confidentiality-record CONFIDENTIALITY.md present and linked from README
  fail  no-real-data          tracked file contains a denied identifier
         config/integrations.yaml:25  mailbox address

verdict: FAIL (1 of 7 criteria failed)
this run reports only; it does not prevent merges
```

### Rules

| Rule | Reason |
| :--- | :--- |
| Status word is exactly `pass`, `fail`, or `unverifiable` | Machine-greppable, and distinct from any prose. |
| Every criterion produces a line, always | A silently skipped criterion is indistinguishable from a passing one. |
| Evidence is indented beneath its criterion | A failure's evidence is never on the status line. |
| The verdict line states the failing count explicitly | `FAIL (1 of 7 criteria failed)` — not `FAIL`. |
| The non-blocking disclaimer always prints | FR-033. A reader must never infer that a green run stopped a merge. |
| **No credential value is ever printed** | Constitution Principle 7. Evidence is a path, a line number, a count, or a pattern name. |
| Commit SHA prints as absent outside a repository | No fake value, no placeholder. |

`unverifiable` lines print the same shape as `fail` plus what was missing:

```text
  unverifiable  dependency-scanning   .github/dependabot.yml present but unreadable
```

---

## Criterion list

The fixed criterion set. FR-028 names the minimum; this is it.

| id | Enforces | Behaviour |
| :--- | :--- | :--- |
| `no-env-tracked` | FR-001, FR-003 | Any path matching environment-directory patterns in `git ls-files` → fail, listing each offending path. |
| `test-suite` | FR-012, FR-013, FR-015 | Run the suite via the declared runner. Non-zero exit, or runner missing → fail naming the runner. |
| `licensing-artifact` | Q3 / FR-021 | `NOTICE` exists and is non-empty → pass. |
| `dependency-scanning` | FR-016 | `.github/dependabot.yml` exists, parses as YAML, and declares a `pip` ecosystem → pass. Detail always states activation is not verifiable from the repository. |
| `secret-guard` | FR-017, FR-020 | `.pre-commit-config.yaml` exists and configures a secret-detection hook scoped to config files → pass. |
| `confidentiality-record` | FR-021, FR-027 | `CONFIDENTIALITY.md` exists, contains every required section heading, and is referenced from `README.md` → pass. |
| `no-real-data` | FR-023, FR-024, FR-025 | Denylist match against tracked content, plus structural rules. See below. |

A criterion the verifier cannot evaluate at all returns `unverifiable`, which fails the run (FR-031).

---

## `no-real-data` rules

Two parts, both deterministic (D7). Neither infers whether arbitrary content is real.

**Part 1 — identifier denylist.** Exact-string match of each denied identifier against tracked text files, skipping `.git`, `venv`, `__pycache__`, and binary files. Match → fail, reporting path and line number only.

Seeded from FR-024 with two entries: the real Office365 mailbox address and the real external tenant domain. The denylist is a module-level literal, reviewable in a diff. Adding an identifier is a deliberate edit.

**Part 2 — structural rules.**

| Rule | Fail condition |
| :--- | :--- |
| Generated output | Any tracked path under `reports/`. |
| Live project metadata | Any uncommented `budget`, `headcount`, or `timesheet_code` anywhere in `config/projects.yaml`. |
| Stale exposure | An `AcceptedExposure` listed in `CONFIDENTIALITY.md` whose identifier no longer appears in tracked content. |

> **Amended 2026-10-05 (issue #44), approved by the contract owner.** The live
> project metadata rule previously read "any uncommented entry under `repos:`
> …". Implemented literally, that left a live `budget:` under `overrides:` passing
> — narrower than FR-023, which forbids real project names with budgets without
> qualification. The rule is now scoped to the file rather than to one block
> within it. No false positive is introduced: `overrides:` legitimately holds
> `activity_window_days`, which is not one of the three keys. The rule still asks
> whether a key is *commented*, never which file it sits in, so FR-030 compliance
> is unchanged.

The stale-exposure rule exists because an accepted exposure is a gap in the denylist. If the identifier it covers disappears, the exposure should disappear too — otherwise the record claims protection it no longer provides.

**FR-030 compliance**: part 1 cannot match a placeholder (`signoffs@example.invalid` ≠ any denylisted entry); part 2 tests whether a YAML key is commented, not which file it sits in. The test suite's fixtures are Python dict literals in `tests/`, never commented YAML, so they trip neither rule.

**Storage note, settled during implementation**: the denylist entries are stored base64-encoded in the module-level literal rather than in plaintext. `tools/verify_baseline.py` is itself tracked content that the check scans, so a plaintext entry would make the check match its own source and fail forever. Tests read the decoded values from the module rather than hardcoding them, for the same reason. Adding an identifier remains a deliberate, reviewable edit to that literal.

---

## Read-only guarantee

The verifier MUST NOT write, create, modify, or delete any file. It runs `git ls-files` and reads files; it never mutates the repository.

This is Constitution Principle 8 — stateless and idempotent — and it is also why the tool can be run on a colleague's checkout without asking.

---

## Automation contract

`.github/workflows/baseline.yml` must:

- Trigger on `pull_request` only (FR-032).
- Install `requirements.txt` before running the verifier, since the `test-suite` criterion needs the runner.
- Run `python tools/verify_baseline.py`.
- **Not gate the merge** (FR-033). The job must not be a required status check, and the workflow must not use a job that fails the pull request's mergeability.
- Print the non-blocking disclaimer in its own summary, so the disclaimer survives even if someone later truncates the verifier's stdout.

A workflow that is silently a required check is the failure mode FR-033 exists to prevent.