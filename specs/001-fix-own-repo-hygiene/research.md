# Phase 0 Research: Milestone 0 Own-Repository Baseline

**Date**: 2026-10-05 | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

All `NEEDS CLARIFICATION` markers are resolved by `/speckit.clarify`. The unknowns below were technical and are resolved here.

---

## D1 — Test runner

**Decision**: `pytest`, configured through `pytest.ini`, added to `requirements.txt`.

**Rationale**: FR-012 requires a declared test runner; the completion spec named pytest explicitly. The decisive practical point is that pytest collects and runs `unittest.TestCase` subclasses natively — all 44 existing tests run unmodified. FR-015 is satisfied trivially because nothing has to be rewritten.

**Alternatives considered**:
- *Keep `unittest` only* — rejected. Zero new dependencies is attractive, but FR-013 requires one documented command that runs the whole suite and FR-012 requires the runner be declared; `python -m unittest` satisfies the letter of both, yet the completion spec asked for pytest and pytest's assertion output and failure detail are what make a 44-test governance suite reviewable.
- *`unittest` + a Makefile wrapper* — rejected. Adds indirection without adding capability.

---

## D2 — Where the test configuration lives

**Decision**: `pytest.ini` at the repository root.

**Rationale**: The project has `requirements.txt` and no `pyproject.toml`. Introducing `pyproject.toml` implies a build-system and packaging decision — whether this tool is installable, what its distribution name is, who consumes it as a library. None of that is in scope for a repository-hygiene milestone, and getting it half-right is worse than not having it.

**Alternatives considered**:
- *`pyproject.toml` with `[tool.pytest.ini_options]`* — rejected. Correct long-term home, but drags in packaging decisions this milestone must not make.
- *Config in `pytest.ini` plus `[tool:pytest]` in `setup.cfg`* — rejected. Two files for one setting.

---

## D3 — How development dependencies are declared

**Decision**: Everything in the single existing `requirements.txt`, under a commented section separating runtime from test tooling.

**Rationale**: This is the only option where Dependabot is guaranteed to see the new packages. Dependabot's `pip` ecosystem is configured against `directory: "/"` and its file discovery for a flat requirements file is unambiguous; whether it also picks up a sibling `requirements-dev.txt` is not something this milestone can verify from the repository, and configuring dependency scanning on an unverified assumption would be a silent gap in FR-016.

The usual objection — that a production install should not pull test tooling — does not apply here. This tool has no production install profile. It is run from a checkout inside a virtual environment, by an operator, against someone else's organisation. There is no `pip install navadhiti-hygiene` in the documented workflow, so there is no environment in which pytest's presence is unwanted.

**Alternatives considered**:
- *`requirements-dev.txt`* — rejected. Cleaner separation, but puts FR-016's completeness behind an assumption about Dependabot's file discovery.
- *`pyproject.toml` optional-dependencies* — rejected by D2.

**Cost of this decision, stated honestly**: the file conflates two dependency classes. If this tool ever gains a production install profile, this decision must be revisited. Recorded in `plan.md` so it is not forgotten.

---

## D4 — Secret guard implementation

**Decision**: `detect-secrets` (v1.5.0) driven by the `pre-commit` framework, configured through `.pre-commit-config.yaml` and `.secrets.baseline`.

**Rationale**: Four properties map directly onto requirements:

| Requirement | How `detect-secrets` satisfies it |
| :--- | :--- |
| FR-017 — commit-time, config files | pre-commit hook, `files:` scoped to `config/*.yaml` |
| FR-019 — documented bypass | inline `# pragma: allowlist secret`, or recording the finding in `.secrets.baseline` |
| FR-020 — extensible by configuration | plugins and filters are declared in `.secrets.baseline`, not in code |
| FR-018 — identifies file and pattern | default hook output names file, line and detector |

> **Correction from the validation run of 2026-10-05.** This decision originally
> listed the inline pragma *and* `# pragma: allowlist nextline secret` as the
> FR-019 bypass. The `nextline` form does not work through the pre-commit hook:
> `detect-secrets` v1.5.0's regex matches it and `is_line_allowlisted()` returns
> `True` when called with that line as `previous_line`, but `detect-secrets-hook`
> still blocks the commit. Verified across five placements. FR-019 is met by the
> two bypasses listed above; the `nextline` form must not be offered to a
> contributor.

Two further reasons: it is pure Python, so CI needs no binary download (relevant because the verifier must also run in CI and the tool has no deployment profile to keep slim); and `.secrets.baseline` is a reviewable diff, so a PR that adds a suppression shows the reviewer exactly what was suppressed and why.

**Alternatives considered**:
- *`gitleaks`* — stronger entropy detection and a good `.gitleaks.toml`, but it is a compiled Go binary. Adds a download step to every contributor's first commit and a second config file. Its advantage over detect-secrets is not needed: this repository's secret exposure surface is three small YAML files, not a large codebase.
- *GitHub native secret scanning* — free on public repositories and genuinely good, but it is **post-push**, not commit-time, so it cannot satisfy FR-017. It also does nothing for a local contributor who has not pushed. Kept as a complement worth enabling later, not as this milestone's control.
- *Hand-rolled regex script* — rejected. FR-020 requires extensibility without touching code; a bespoke script would be code, and it would be worse at detection.

**Known limitation, recorded rather than hidden**: `detect-secrets` documents that it will not catch multi-line secrets or default passwords that do not trip its keyword detector. It is a guard against the obvious case, not a guarantee.

---

## D5 — Dependency scanning

**Decision**: GitHub Dependabot via `.github/dependabot.yml`, `package-ecosystem: "pip"`, `directory: "/"`, `schedule.interval: "weekly"`.

**Rationale**: FR-016 requires dependency scanning at the same level of diligence the tool applies elsewhere — and the tool's own `security_baseline` check looks for exactly Dependabot. Consistency argues for it. `weekly` matches the size of this dependency set (three runtime packages); `daily` would generate noise, not signal.

**Alternatives considered**:
- *Renovate* — more configurable, but a second tool to introduce alongside Dependabot on a repository with no CI history.
- *`pip-audit` in CI* — a genuinely good complement, because it catches *known CVEs* in installed packages while Dependabot only proposes upgrades. Not selected here because FR-016 asks for dependency update scanning and Milestone 7 owns real vulnerability findings. Noted as a candidate for Milestone 7.

**Honest limitation**: presence of `.github/dependabot.yml` proves configuration, not activation. See Complexity Tracking entry 2 in `plan.md`. The verifier reports `configured`, never `active`.

---

## D6 — Shape of the baseline verifier

**Decision**: A standalone `tools/verify_baseline.py`, stdlib only, exit 0/1, one line per criterion.

**Rationale**: FR-034 requires the same command locally and in CI, and FR-028 requires one command covering every criterion. A single script is the only shape that guarantees they cannot drift.

The stdlib-only constraint is the load-bearing part. One criterion is "test suite green" (FR-028). If the verifier imported `pydantic` or `yaml`, then a broken `pip install` would make the verifier crash — and the one check that would have caught the broken install would be the thing that broke. Stdlib-only means the verifier can still run, still report, and still fail loudly. This is Constitution Principle 6 applied to the tool's own gate.

**Alternatives considered**:
- *`Makefile` target* — rejected. Introduces a build tool, and `make` is not present on Windows by default.
- *A pytest plugin* — rejected. Would put the verifier inside the thing it verifies, and would make it unavailable when pytest is the thing that is broken.
- *Shell script* — rejected by the cross-platform constraint.

---

## D7 — What the no-real-data check actually checks

**Decision**: An explicit denylist of known-real identifiers, plus structural rules. **Not** a classifier that tries to decide whether arbitrary content is real.

**Rationale**: FR-029 requires the check be deterministic, and Constitution Principle 3 forbids inventing a standard that Navadhiti has not defined. A general "is this real project data?" classifier would have to guess what real looks like — which is guessing, and would produce false positives that train people to ignore it.

The check is therefore two parts, both auditable:

1. **Identifier denylist** — the real mailbox address and the real tenant domain (FR-024). Exact-match against tracked file contents. Zero false positives by construction, because a denylist entry is a specific known string.
2. **Structural rules** — `reports/` contains no tracked files (FR-025); `config/projects.yaml` contains no uncommented repository entries carrying budgets or headcount (FR-023).

**FR-030 compliance**: FR-030 requires the check distinguish real from sample *by content, not by directory*. Both parts satisfy this. Part 1 is exact-string, so it cannot match `signoffs@example.com`. Part 2 inspects whether a YAML key is commented out, not which file it sits in — a live budget in `tests/` is still a violation, and a commented example in `config/` is still a sample. The test suite's own fixtures live in `tests/test_hygiene.py` as Python dict literals, not as commented YAML, so they do not trip part 2.

**Alternatives considered**:
- *ML or entropy-based classification* — rejected. Guessing, and unauditable.
- *Directory-scoped check only* — rejected. Violates FR-030 directly.

---

## D8 — CI workflow shape

**Decision**: `.github/workflows/baseline.yml`, triggered on `pull_request` only, running the verifier and reporting the result without gating the merge.

**Rationale**: FR-032 mandates the pull-request trigger; FR-033 mandates non-blocking. `pull_request` rather than `push` means the run also covers branches from forks, and means the check never appears on the default branch's history as noise.

**Alternatives considered**:
- *Also trigger on `push` to main* — rejected. Pull-request coverage already catches every change before it lands; a push trigger adds duplicate runs.
- *Separate `pytest` job alongside the verifier* — rejected. FR-034 requires one verdict, and the verifier's test criterion already runs the suite. Two jobs means two verdicts.
- *Blocking job* — rejected by FR-033, which resolves the tension with Constitution Principle 5: enforcement is a later milestone and a human decision, and this milestone must not switch it on by adding a YAML file.

---

## D9 — Licensing artifact form and filename

**Decision**: A root-level `NOTICE` file containing an internal-use notice. No `LICENSE` file.

**Rationale**: Clarification Q3 chose "an internal-use notice that states authorship and restricted use, without granting or withholding formal license terms". A file named `LICENSE` asserts that license terms exist. Naming it `NOTICE` keeps the artefact honest about what it is, and matches the widespread convention where `NOTICE` carries attribution and `LICENSE` carries terms.

**Alternatives considered**:
- *`LICENSE` containing "All rights reserved"* — rejected. It is a license term, and inventing one is precisely what Q3 declined to do.
- *Putting the notice in the README only* — rejected. FR-021's artifact needs to be a file that is present or absent, so FR-028 can verify it.

---

## D10 — Where the confidentiality record lives

**Decision**: Root-level `CONFIDENTIALITY.md`, linked from the README.

**Rationale**: SC-008 requires the accountable owner to find it within 2 minutes. A root file is visible in the repository listing; a nested `docs/` file requires knowing to look. The repository has no `docs/` directory today, so creating one for a single file adds a path segment and no value.

**Alternatives considered**:
- *`SECURITY.md`* — rejected. GitHub surfaces that file specially and treats it as a vulnerability-disclosure policy, which would misdescribe a data-handling decision record.
- *Appending to the README* — rejected. FR-027 requires it be a distinct, linkable artefact so FR-028 can verify its presence independently of the README.

---

## Unresolved

None. No `NEEDS CLARIFICATION` remains in the Technical Context or the spec.

Two items remain outside this plan's authority and are recorded as human actions, not as unknowns:

1. **The constitution is unratified.** The Constitution Check gate was evaluated against Section A of the completion spec as a proxy and is marked provisional.
2. **The account owner's name is unknown.** `CONFIDENTIALITY.md` names the role and flags the gap, per the spec's stated assumption.