# Feature Specification: Navadhiti Hygiene System — Milestone 0 Own-Repository Baseline

**Feature Branch**: `001-fix-own-repo-hygiene`

**Created**: 2026-10-05

**Status**: Draft

**Input**: User description: "Navadhiti Hygiene System — Completion Spec, Milestone 0 — Fix the hygiene tool's own hygiene. The repository currently fails several of the checks it is built to enforce. Before it audits anyone, it should meet its own baseline."

**Milestone position**: First milestone of the completion spec. Milestone 2 capability already exists in the codebase; this milestone is a prerequisite for trusting anything it reports and for every milestone that follows. Section A of the completion spec (the constitution) is a separate, prior step and is not restated here.

---

## Problem Statement

The Navadhiti Hygiene System audits other engineering projects for governance
compliance. It scores projects, reports gaps, and — once promoted — can block
non-compliant merges. To be believed, it must first satisfy the standards it
enforces.

It currently does not. Measured against its own standards, the repository:

- Tracks **1,989 of 2,033 files** inside a committed Python virtual environment,
  including full copies of installed third-party libraries. There is no ignore
  file, so every developer's environment differences are versioned as source.
- Has **no automated test runner configuration**. Forty-four tests exist but the
  test tooling is not declared as a dependency, so a fresh clone cannot run them
  the way the documentation implies.
- Has **no licensing artifact**, despite a stated internal proprietary position.
- Has **no automated dependency update scanning**, despite checking other
  repositories for exactly this weakness.
- Has **no commit-time secret-pattern guard**, despite the system being designed
  around the principle that credentials never belong in configuration.
- **Makes the confidentiality decision implicitly, by default.** It is currently
  public, and it is the repository that will hold project names, organisation
  repository structure, and salary-derived cost figures. That decision has not
  been made deliberately or recorded.

The consequence is credibility, not function. The scanner runs; its verdict on
anyone else's discipline is only as credible as its own.

---

## Clarifications

### Session 2026-10-05

- Q: Should the repository be made private, or kept public under a documented
  no-real-data policy? → A: Keep it public, and document a policy that no real
  Navadhiti data is permitted in it.
- Q: Should the committed virtual environment be purged from recorded history,
  or only untracked going forward? → A: Correct forward history only; the
  environment files stay permanently visible in the three existing commits.
- Q: Should the internal proprietary position be a formal proprietary license
  file or an internal-use notice? → A: An internal-use notice that states
  authorship and restricted use, without granting or withholding formal license
  terms.
- Q: Which already-committed identifiers should be replaced with placeholders
  given that the repository stays public? → A: Replace the mailbox address and
  the external tenant domain. Keep the organisation name and the timesheet
  vendor name, and record those two as accepted exposures because the repository's
  own address already discloses the organisation.
- Q: What stops someone committing a live run's output or a real project budget
  later? → A: Add a deterministic check for it inside the single baseline
  verification command from FR-028, rather than relying on documentation or
  adding a second commit-time guard.
- Q: Should the baseline verification run only by hand, or automatically on pull
  requests? → A: Automatically on pull requests only. Nothing is forced on
  contributors locally, and the check reports rather than blocks.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A new engineer gets a clean, working checkout (Priority: P1)

A Navadhiti engineer follows the written installation instructions on a new
machine, from a fresh clone. The checkout is small and readable. Nothing in it
is another developer's environment. Every command in the instructions works as
written, and the documented test suite runs and reports success.

**Why this priority**: This is the first contact every contributor and every
reviewer has with the tool. A checkout dominated by 1,989 vendored files is not
reviewable and is the single most visible way the tool fails its own standard.

**Independent Test**: Clone the repository to an empty directory, follow the
written installation steps verbatim, and run the documented test command. Value
delivered: a working baseline, independent of every other story in this spec.

**Acceptance Scenarios**:

1. **Given** a fresh clone of the repository, **When** the engineer inspects the
   tracked file list, **Then** no virtual environment files are present and the
   tracked file count is under 100.
2. **Given** a fresh clone, **When** the engineer follows every command in the
   written installation section in order, **Then** each command succeeds without
   an undocumented prerequisite or a placeholder repository location.
3. **Given** a fresh clone with declared dependencies installed, **When** the
   engineer runs the single documented test command, **Then** the suite completes
   and the command reports success.
4. **Given** a developer who already has an environment directory created by a
   previous setup, **When** the ignore rules take effect, **Then** that directory
   is still present on disk and usable, but is no longer tracked as source.

---

### User Story 2 - A reviewer can verify the tool meets its own baseline (Priority: P2)

An auditor — internal or external — wants to confirm the hygiene tool is not
exempt from the standards it enforces. They want to answer three questions
without reading source: is there a working test suite, is the project licensed,
and are known weaknesses in its own dependencies surfaced automatically.

**Why this priority**: This is what converts "we believe it is fine" into "we
verified it." It is the difference between a claim and evidence, and it is what
makes every future audit finding defensible.

**Independent Test**: Reviewer inspects the repository for a runnable test suite,
a licensing artifact, an active dependency-update configuration, and a
commit-time secret guard, and confirms each is present and current. Value
delivered independently of Stories 1 and 3.

**Acceptance Scenarios**:

1. **Given** the repository, **When** the auditor looks for a licensing artifact,
   **Then** one exists and states the internal proprietary position.
2. **Given** the repository, **When** the auditor looks for automated dependency
   update scanning, **Then** it is configured and active for this repository.
3. **Given** the repository, **When** a commit containing a token-shaped string
   in a configuration file is attempted, **Then** the commit is stopped with a
   message identifying the file and the pattern, and the failure is not silent.
4. **Given** the auditor, **When** the auditor runs the test suite, **Then** at
   least one test exercises schema validation and at least one exercises the
   score calculation, so the two core claims of the tool are covered.

---

### User Story 3 - The confidentiality decision is recorded, not inherited (Priority: P3)

The person accountable for the repository discovers that its public status was
never chosen — it was inherited from how the repository was created. They now
have the facts: what sensitive categories this repository will hold, what the
policy therefore forbids from being committed, and which identifiers are already
committed today. They record a decision and a rationale. The tool does not make
this decision for them, and does not change the repository's visibility.

**Why this priority**: The repository is the one place in the system where cost
figures, project names, and organisational structure will accumulate. Choosing
that exposure by accident is the failure mode this milestone exists to prevent.
It ranks below Stories 1 and 2 because the hygiene controls are useful under
either visibility setting, whereas this decision governs what may ever be
committed here.

**Independent Test**: Locate the recorded decision, read the rationale, confirm
that every currently-tracked identifier is either scrubbed or listed as an
accepted exposure, and confirm no automated action was taken to change visibility.
Value delivered independently of Stories 1 and 2.

**Acceptance Scenarios**:

1. **Given** the repository, **When** the accountable owner looks for a record of
   the confidentiality decision, **Then** they find a human-readable document
   stating the decision, the date, the rationale, the categories of data
   excluded, and the conditions that trigger revisiting the decision.
2. **Given** a tracked configuration file that names a real organisation
   identifier, mailbox address, or external tenant, **When** the record is read,
   **Then** that identifier has either been replaced with an obvious placeholder
   or appears in the record as a named accepted exposure with a rationale.
3. **Given** the repository stays public, **When** this milestone completes,
   **Then** no automated step changed its visibility — the decision is recorded
   and stands.
4. **Given** the policy forbids real data, **When** a contributor inspects what
   the rules permit them to commit, **Then** the exclusions are listed concretely
   enough to act on without asking anyone.
5. **Given** a contributor with a live run's output, **When** they attempt to
   commit it, **Then** the exclusion rules stop them, and the tool's own run still
   writes that output successfully on disk.

---

### Edge Cases

- **Removing environment files from history was rejected.** Forward tracking is
  corrected only. The consequence is that the 1,989 environment files remain
  permanently visible in the three existing commits. A future contributor who
  inspects history will find them; FR-010 exists so they are told this was a
  choice, not a failed task.
- **Existing clones already contain the environment files.** Untracking them must
  not delete them from a working copy or break a contributor's local environment;
  FR-011 provides the documented path back to a clean state.
- **The public-with-no-real-data policy is already violated on day one by tracked
  configuration.** The repository stays public, but a tracked configuration file
  names the real organisation, a real Office365 mailbox address that a mailbox
  grant would be scoped to, the timesheet vendor, and — in a comment — an external
  tenant domain. FR-024 sorts these into two placeholders and two accepted
  exposures, so the policy is true on day one rather than aspirational.
- **Replacing the mailbox address must not silently disable the email sign-off
  path.** The mailbox is what the transitional sign-off tier reads. A placeholder
  must be obviously non-functional, and the documentation must state that a real
  mailbox is configured by whoever operates the system — not committed.
- **The ignore rules must not break the tool's own output.** The scanner writes
  reports to a directory that is now excluded from tracking. FR-025 requires that
  a run can still create and write there.
- **No report directory is currently tracked.** The exclusion must hold whether or
  not that directory has ever been committed.
- **Legitimate token-shaped strings exist in documentation.** Placeholder examples
  of the form `ghp_...` appear in the written setup instructions. The secret guard
  must not permanently block correct documentation, so FR-019 requires a
  documented bypass rather than one discovered by trial.
- **Secret-pattern false positives.** A file may contain a word that matches a
  pattern without containing a credential. FR-020 requires the pattern set to be
  adjustable without editing source.
- **A fresh clone has no test runner installed.** The dependency manifest is the
  only place a new contributor learns what to install; if the runner is not
  listed there, the documented test command fails on a clean machine.
- **Ignored does not mean untracked.** A file that was tracked before ignore
  rules existed stays tracked. Removing tracking is a separate action from adding
  ignore rules, and FR-003 requires both.
- **A policy that is only written down is not a control.** FR-023 states the rule;
  FR-029 checks it inside the baseline verification command (clarified
  2026-10-05). The check must not mistake the test suite's sample budgets and
  report fixtures for real data — FR-030 requires it to distinguish by content,
  and requires any exemption to be written down rather than assumed.
- **The baseline check could pass by checking the wrong things.** It must fail
  loudly and exit non-zero on a partially-passing baseline (FR-031), because a
  check that reports success while quietly skipping a criterion is worse than no
  check at all.
- **The check lives in the repository it checks, so a broken check can silently
  pass everything.** If the verification logic crashes, is skipped, or is deleted
  in the same pull request that should have tripped it, the automated run must not
  read as healthy. The run must distinguish "all criteria passed" from "the check
  did not run", and the second must be reported as a failure.
- **Automated and local runs can drift apart.** They share one command and one
  criterion list, so a criterion added to one and not the other is a defect rather
  than a configuration difference (FR-034).
- **The check reports but does not block, and a contributor may read "green" as
  "enforced".** The report MUST state plainly that the run is advisory, so that
  nobody assumes a merge was prevented when it was not (FR-033).
- **Cross-platform paths.** Contributors work on Windows and macOS/Linux;
  ignore patterns must behave consistently on both.

### Out of Scope

- Any change to check logic, scoring weights, dimensions, or the seven-dimension
  model. Milestone 2 capability exists and is not modified here.
- Activating merge-blocking enforcement anywhere. That is a later milestone and
  requires an explicit human decision.
- Building the reporting dashboard, notifications, or trend analysis.
- Changing what the system measures. This milestone changes only the health of
  the tool, never its judgement.

---

## Requirements *(mandatory)*

### Functional Requirements

**Repository hygiene baseline**

- **FR-001**: The repository MUST NOT track any file belonging to a Python
  virtual environment or package environment directory. Baseline to correct:
  1,989 tracked files under `venv/`.
- **FR-002**: The repository MUST contain a version-control ignore file covering,
  at minimum: Python virtual environment directories, Python bytecode caches and
  compiled artifacts, local environment and credential files, editor/tooling
  caches, and generated report output.
- **FR-003**: Adding ignore rules MUST be accompanied by explicitly removing any
  already-tracked matching paths from tracking. Ignore rules alone MUST NOT be
  treated as satisfying FR-001.
- **FR-004**: Removing environment files from tracking MUST NOT delete them from
  existing working copies, and MUST NOT break a developer's existing local
  environment.
- **FR-005**: Recorded history MUST NOT be rewritten. The environment files are
  untracked and covered by ignore rules; they remain permanently present in the
  three existing commits. This residue is accepted knowingly, MUST be stated in
  the project status table (FR-008), and MUST NOT be presented as removed. No
  existing clone or open pull request is invalidated by this milestone.

**Documentation truthfulness**

- **FR-006**: The written installation instructions MUST reference the actual
  location of this repository. No placeholder organisation or repository name
  may remain anywhere in the documentation.
- **FR-007**: Every command shown in the installation section MUST be executable
  in the order given, on a fresh clone, with no undocumented prerequisite.
- **FR-008**: The project status / roadmap table MUST describe the state of the
  system after this milestone, not the state it was planned to reach. Any
  capability described as present MUST be verifiable in the repository.
- **FR-009**: The project status / roadmap table MUST gain rows for the controls
  this milestone introduces, so that a later reader can see they exist.
- **FR-010**: The project status / roadmap table MUST state that the virtual
  environment remains in recorded history, so that a reader who inspects history
  and finds it is not misled into thinking the removal was incomplete.
- **FR-011**: Because existing working copies already have the environment
  directory tracked, the documentation MUST contain a short procedure that lets a
  contributor with an existing clone reach a clean state without deleting their
  working environment. The procedure MUST be verifiable on an existing clone.

**Test suite**

- **FR-012**: The repository MUST declare a test runner as a first-class
  dependency. Baseline to correct: the test runner is currently absent from the
  dependency manifest, so a fresh clone cannot run the documented test command.
- **FR-013**: The repository MUST document exactly one command that runs the
  entire suite, and that command MUST exit with a failure status when any test
  fails.
- **FR-014**: The suite MUST contain at least one test covering report schema
  validation and at least one covering the score calculation, asserting real
  values rather than merely that a call returns.
- **FR-015**: Existing tests MUST continue to pass. Any test removed or weakened
  as part of this milestone MUST be called out explicitly with its reason.

**Dependency and secret protection**

- **FR-016**: Automated dependency update scanning MUST be active for this
  repository, at the same level of diligence the system applies to the
  repositories it scans.
- **FR-017**: A commit-time **secret guard** MUST prevent a credential-shaped
  string from being committed into any configuration file.
- **FR-018**: When the secret guard blocks a commit, it MUST identify the
  offending file and the pattern that matched, and MUST explain how to proceed if
  the match is a false positive.
- **FR-019**: The secret guard MUST be bypassable for a legitimate case without
  being removed or disabled permanently, and the bypass procedure MUST be
  documented.
- **FR-020**: The secret guard MUST be extensible by configuration, so that a new
  pattern is added without modifying source.

**Confidentiality decision**

The recorded decision is: **the repository remains public, and no real Navadhiti
data is permitted inside it.**

- **FR-021**: The repository MUST contain a human-readable record of the
  confidentiality decision, stating: the decision, the date, the accountable
  owner, the rationale, the categories of data the policy protects, and the
  conditions that trigger revisiting the decision.
- **FR-022**: The record MUST state the exposure categories explicitly —
  salary-derived cost figures, project names, and organisational repository
  structure — rather than describing them in general terms.
- **FR-023**: The record MUST state plainly that real Navadhiti data is not
  permitted in this repository, and MUST list what that excludes in concrete
  terms: live run output, real project names with budgets, real headcount and
  salary-derived rates, live credential or token values, and internal
  correspondence.
- **FR-024**: Every tracked configuration file MUST conform to the policy in
  FR-023 at the moment the record is written. Specifically:
  - The Office365 mailbox address MUST be replaced with an obvious placeholder.
    It is the exact target a mailbox grant would be scoped to, so it is the
    identifier with the most direct path to real correspondence.
  - The external tenant domain appearing in the ticketing integration comment
    MUST be replaced with an obvious placeholder. It names both the ticketing
    vendor and the organisation's tenant.
  - The organisation name and the timesheet vendor name MAY remain, and MUST
    then be listed in the record as accepted exposures with the rationale that
    the organisation name is already disclosed by this repository's own address,
    so editing it protects nothing while making the tool unrunnable out of the box.
  - Any further identifier found during implementation MUST be classified the
    same way — replaced or recorded — rather than left undecided.
- **FR-025**: Generated run output MUST be excluded from tracking, consistent
  with FR-023. The record MUST state this, and the exclusion MUST not prevent the
  system from writing to that location during a run.
- **FR-026**: This milestone MUST NOT change the repository's visibility, and no
  automated step may attempt to. The decision to keep the repository public is
  recorded and stands; any future change is a human action requiring the revisit
  triggers in the record to fire.
- **FR-027**: The record MUST be linked from the primary documentation so it is
  findable, not buried.

**Verification**

- **FR-028**: The milestone MUST provide a repeatable check that the baseline
  holds. It MUST verify, at minimum: no environment files tracked, test suite
  green, licensing artifact present, dependency scanning configured, secret guard
  configured, the confidentiality record present and linked, and the no-real-data
  policy in FR-023 upheld by tracked content.
- **FR-029**: The no-real-data check MUST be deterministic and part of the same
  command as every other baseline criterion. It MUST detect committed live run
  output and real project metadata, name the offending path, and it MUST NOT be
  satisfied by the absence of a written rule. This is deliberate: the policy is
  enforced by a check rather than by documentation alone, and a separate
  commit-time guard is explicitly out of scope for this milestone.
- **FR-030**: The no-real-data check MUST NOT report a failure for fixture or
  sample data that the test suite legitimately requires. It distinguishes a
  committed sample from committed real data by what it is, not by which directory
  it sits in, and any exemption it applies MUST be listed in the record.
- **FR-031**: The verification check MUST fail loudly, not warn and continue. A
  partially-passing baseline MUST be reported as a failure, and the command MUST
  exit with a failure status.
- **FR-032**: The baseline verification MUST run automatically on every pull
  request to this repository (clarified 2026-10-05). This is the repository's
  first automated workflow, and it MUST NOT require contributors to install or run
  anything locally.
- **FR-033**: The automated run MUST report rather than block. It MUST NOT gate
  merges on this repository. Activating merge-blocking enforcement is a later
  milestone and a separate human decision; adding a blocking gate here would
  switch enforcement on by automation, which the governing principles forbid.
- **FR-034**: A contributor MUST still be able to run the same verification
  locally with one command, and both paths MUST report the same verdict for the
  same repository state. An automated run that disagrees with the local run is a
  defect.

---

### Key Entities

- **Ignore Rule**: A pattern plus its intent. Attributes: the pattern, the class
  of artefact it covers (environment, bytecode, credential file, generated
  output), whether paths matching it were already tracked. Relationships: one
  rule may cover many paths; a path is matched by at most one rule in practice.

- **Tracked Path**: A single file or directory currently under version control.
  Attributes: path, category (source, environment, generated output, bytecode).
  Key property: **tracked and ignored are independent** — a path can be ignored
  yet still tracked, and that inconsistency is the specific failure FR-003
  addresses.

- **Dependency Declaration**: A third-party package the project needs to run or
  to be tested. Attributes: package, purpose (runtime or test-only), declared
  version constraint. The test runner is currently missing from this set.

- **Secret Guard**: The commit-time protection against credential leakage.
  Attributes: the set of credential patterns applied, the paths it applies to,
  the bypass procedure. Relationships: one guard covers many patterns; patterns
  are configuration, not source (FR-018).

- **Licensing Artifact**: An internal-use notice stating that the software is
  proprietary to Navadhiti and that use is restricted. It records authorship and
  restricted use. It deliberately does **not** grant, withhold, or define formal
  license terms — that is a legal position Navadhiti has not taken, and inventing
  it here would be fabricating a standard (Constitution Principle 3).

- **Confidentiality Decision Record**: The deliberate, dated statement governing
  what may be committed to this repository. Attributes: decision (remains public),
  date, accountable owner, rationale, categories of data excluded, list of
  accepted exposures with rationale, revisit triggers. Relationships: governs how
  configuration files and generated reports are handled (FR-024, FR-025); is
  recorded, never executed automatically (FR-026).

- **Accepted Exposure**: An identifier that is deliberately committed despite the
  no-real-data policy, recorded with its rationale so a reviewer sees a decision
  rather than an oversight. Two are accepted (clarified 2026-10-05): the
  organisation name, which is already disclosed by this repository's own address,
  and the timesheet vendor name, which identifies a vendor rather than Navadhiti
  and is not re-identifying on its own.

- **Baseline Verification Result**: The outcome of the repeatable check in FR-028.
  Attributes: each criterion's pass/fail state — tracked environment files, test
  suite, licensing artifact, dependency scanning, secret guard, confidentiality
  record, no-real-data check (FR-029) — the overall verdict (pass or fail), the
  offending path where a criterion failed, and a timestamp. Key properties:
  **fail loudly** (FR-031) and **one command, every criterion** (FR-029), so that
  "is this repository healthy?" has exactly one answer source.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Tracked files inside any environment directory fall from 1,989 to
  zero, and total tracked files fall from 2,033 to fewer than 100.
- **SC-002**: The documented test command completes with a success status on a
  fresh clone after installing declared dependencies, with zero failures.
- **SC-003**: The baseline verification check reports a pass on a fresh clone and
  reports a failure when any single criterion is deliberately broken.
- **SC-004**: A reviewer's compliance questions — is there a test suite, is it
  licensed, are its own dependencies watched, can a credential be committed — are
  each answerable by locating one file, with no more than three files to read in
  total.
- **SC-005**: Every command in the written installation section executes
  successfully, in order, on a fresh clone, with zero undocumented steps.
- **SC-006**: Zero occurrences of a placeholder organisation or repository name
  remain anywhere in the repository's documentation.
- **SC-007**: A commit containing a credential-shaped string in a configuration
  file is rejected 100% of the time when the guard is active, and the legitimate
  bypass works as documented when a match is a false positive.
- **SC-008**: The accountable owner can locate the confidentiality decision and
  its rationale within 2 minutes of deciding to look for it.
- **SC-009**: Zero tracked file contains the real mailbox address or the external
  tenant domain. Every identifier that remains is either an obvious placeholder or
  one of the two named accepted exposures in the record.
- **SC-010**: A reader of the project status table can tell, for every row,
  whether the capability is real, partial, or planned — with no row describing a
  plan as though it were shipped.
- **SC-011**: A contributor with a pre-existing clone follows the documented
  recovery procedure and reaches a clean state without recreating their working
  environment, in under 2 minutes.
- **SC-012**: The record states plainly that the virtual environment remains in
  recorded history, so that a reader who finds 1,989 environment files in the
  three existing commits learns it was a decision.
- **SC-013**: Zero existing tests are lost or weakened without an explicit,
  written reason.
- **SC-014**: Committing a live run's output, or a real project name with a
  budget, into this repository is detected by the baseline verification command,
  which names the offending path and exits non-zero.
- **SC-015**: Running the baseline verification command on an unmodified fresh
  clone passes every criterion, including the no-real-data check, with zero false
  failures on the test suite's own sample data.
- **SC-016**: Opening a pull request against this repository runs the baseline
  verification with no local setup by the contributor, and the run reports the
  same verdict as running the command locally on the same commit.
- **SC-017**: A pull request that breaks any single baseline criterion is reported
  as failing, and the automated run does not prevent the merge — a merge that
  proceeds after a failed check is visibly reported, not silently accepted.

---

## Assumptions

- The forty-four existing tests remain the correct specification of current
  behaviour; this milestone configures how they run, it does not rewrite what
  they assert, except where a test encodes an expectation about a file that this
  milestone deliberately removes.
- Milestone 2 capability (live repository discovery, the seven dimensions, sprint
  calendar, promotion streaks, report history archive) is accepted as existing.
  This milestone does not re-verify or modify it.
- The repository's owner can be identified and named in the confidentiality
  record. If not identifiable at implementation time, the record names the role
  rather than a person and flags the gap.
- The repository stays public (clarified 2026-10-05). Generated run output is
  therefore treated as sensitive and excluded from tracking, because it is the
  artefact that accumulates project names and cost figures.
- The organisation name `navadhiti` is treated as already public — it appears in
  this repository's own address — so editing it out of configuration would protect
  nothing while making the tool unrunnable out of the box (clarified
  2026-10-05).
- The real mailbox address and external tenant domain are replaced with obvious
  placeholders (clarified 2026-10-05). Whatever a real operator needs is supplied
  outside the repository, so the committed configuration is safe to read but not
  functional as-is.
- The recorded history is never rewritten (clarified 2026-10-05). The cost is a
  permanently large clone for anyone who cares about size; the benefit is that no
  collaborator's clone or open pull request breaks. With three commits this was
  cheap to accept and would not stay cheap indefinitely.
- The no-real-data policy is enforced by one deterministic check inside the
  baseline verification command, not by a second commit-time guard (clarified
  2026-10-05). Two mechanisms covering one rule would be two things to maintain
  and two places for them to disagree.
- The tool never writes to a repository it scans, and that property is unaffected
  by this milestone — everything here happens to the hygiene tool's own
  repository.
- Readers of the documentation are Navadhiti engineers and leadership who are not
  all familiar with version control, so installation and confidentiality
  statements are written in plain language.
- Windows contributors exist; ignore patterns and documented commands are expected
  to work on both Windows and macOS/Linux.

---

## Dependencies

- A decision-maker accountable for the repository's confidentiality — required
  to confirm the recorded decision in FR-021 through FR-027, not to resolve the
  rest of the milestone.
record. The offline path remains available for contributors who prefer it.
- Repository hosting administrator — required to activate dependency scanning
  (FR-016). This is the only criterion that cannot be satisfied purely by files
  in the repository.
- The test runner must be obtainable from the same package index as existing
  dependencies.
- The constitution (Section A of the completion spec) has not yet been ratified.
  Milestone 0 changes no check logic, so it does not depend on ratified principles,
  but every milestone after it does.

---

## Out of Scope Confirmation

Nothing in this milestone may change what the system measures, how it scores, or
whether it blocks anything. A milestone that also adjusted check logic would
make it impossible to tell whether an audit finding reflects the audited project
or the audited tool being modified at the same time.