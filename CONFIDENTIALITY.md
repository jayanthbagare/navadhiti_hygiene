# Confidentiality and Data-Handling Decision

> This file records a human decision. It is an input to no automated check.
> `tools/verify_baseline.py` reads it for **presence and required headings
> only** — it never interprets this prose, evaluates this rationale, or judges
> whether an accepted exposure below is reasonable. Approving that content is
> your act, not the tool's.

## Decision

**This repository remains public, and no real Navadhiti data is permitted inside
it.**

Its public status was inherited from the way the repository was created, not
chosen. That is being corrected here: the exposure is now a decision on the
record, with a policy attached, rather than an accident nobody had looked at.

This milestone did not change the repository's visibility, and nothing in it
attempted to. No tooling in this repository touches hosting settings. Changing
visibility remains a human action, and the Revisit Triggers below say when to
consider it.

## Date

2026-10-05

## Accountable Owner

**Role:** Navadhiti Engineering — owner of the Project Hygiene System.

**The individual holding that role is not yet identified, and that gap is
recorded here rather than papered over.** Until a name is filled in, no named
person is accountable for this decision, and anyone reviewing it should treat
the absence as an open item. The same gap applies to the review of this record.

Filling the name is a human action, not a tooling step.

## Rationale

Public-with-a-written-policy was chosen over making the repository private.

Private was considered and rejected. The tool's entire purpose is to audit
engineering repositories against a standard Navadhiti defines. If the tool's
own repository is private, every external reviewer and auditor who needs to
evaluate whether the findings are fair cannot see the evidence — and a finding
whose evidence cannot be inspected is indistinguishable from an opinion. The
credibility cost of private outweighs the confidentiality cost of public.

Public is acceptable **because** the policy below is enforced by a deterministic
check rather than by good intentions, and because the categories that matter —
real project names, cost figures, headcount, credentials, correspondence — are
excluded categorically rather than trusted to stay out.

The known cost of this choice is stated plainly: the two accepted exposures
below stay public, and history keeps what it keeps (see Revisit Triggers).

## What This Repository Must Never Contain

Real Navadhiti data. Concretely, none of the following may ever be committed
here. Each entry is written so a contributor can act on it without asking
anyone.

| Never commit | Why | What to do instead |
| :--- | :--- | :--- |
| **Live run output** — anything under `reports/`, including `aggregate.json`, per-project reports, `history/`, `promotion_state.json` | Output accumulates project names, cost figures and headcount across runs. One committed run leaks many projects at once. | Let the tool write to `reports/` locally; it is gitignored. Run output belongs in the audited organisation, not in this tool. |
| **Real project names with budgets** | A real name plus a budget identifies internal financial planning. | Keep sample entries commented out, as `config/projects.yaml` does. A commented budget is a sample; an uncommented one is a violation. |
| **Real headcount and salary-derived rates** | Cost variance is computed as headcount × duration × rate; a live headcount is one step from a live payroll figure. | Same as above — commented sample values only. |
| **Live credential or token values** — API keys, PATs, mail client secrets, webhook URLs | A credential in git is a credential in every clone and in history. | Set them in your environment. The configuration names the variable to use, e.g. `GIT_TOKEN`, `TIMESHEET_TOKEN`, `TICKETING_TOKEN`, `EMAIL_CLIENT_SECRET`. `.env` files are gitignored. |
| **Internal correspondence** — mailboxes, meeting notes, internal hostnames, tenant domains | A mailbox address is the exact target a mailbox grant would be scoped to; a tenant domain names the vendor *and* the organisation at once. | Use obvious placeholders. `config/integrations.yaml` uses `example.invalid` and `example-tenant` for exactly this reason. |

A committed identifier is acceptable only if it is an obvious placeholder, or if
it appears in Accepted Exposures below with a rationale.

## Accepted Exposures

Identifiers deliberately committed despite the policy above. **An empty section
would mean nothing is deliberately exposed; a missing section means the record
is incomplete. Those are different statements, which is why the table is
required even when it is short.**

Each entry must name why the identifier cannot be protected. "We decided it's
fine" is not a rationale.

| Identifier | Category | Rationale |
| :--- | :--- | :--- |
| `navadhiti` | Organisation name | Already disclosed by this repository's own address, which appears in the clone URL in the README. Editing it out of `config/integrations.yaml` protects nothing and makes the tool unrunnable out of the box, because `git_provider.org` is the one setting every operator must change anyway. |
| `zoho_people` | Vendor name | Names a supplier, not Navadhiti, and is not re-identifying on its own. It is the value of `timesheet_system.type`, and a scanner that cannot name its own timesheet integration is harder to trust, not easier. |

The real mailbox address and the real external tenant domain are **not** accepted
exposures. Both were replaced with obvious placeholders on 2026-10-05; see
`config/integrations.yaml`.

### Activation, Observed Rather Than Assumed

Dependency scanning is *configured* in `.github/dependabot.yml`, and the verifier
reports `configured` and never `active` — activation is a hosting-side fact with
no evidence in the repository, and a criterion must not claim what it cannot see.

A human observer can supply that evidence, and did. About 90 seconds after this
configuration reached `main` on 2026-10-05, Dependabot opened its first update
pull requests against `main`, and by the end of the day had opened five:
`requests`, `pydantic`, `PyYAML`, `pytest` and `pre-commit`. Version updates are
therefore **demonstrably active**, not merely configured.

The distinction is worth keeping. The verifier's line stays `configured` forever,
because a future clone that reads the file cannot see whether any of this remains
true. The evidence above is a dated observation in a document a human maintains,
which is the right place for a fact like that.

## Revisit Triggers

Any one of these forces this decision to be reconsidered:

- **An accepted exposure is added.** The gap is a deliberate widening of the
  policy, and it needs the same scrutiny as the decision itself.
- **A real identifier is found in tracked content or in history.** One occurrence
  means the policy is not being followed and the record is not describing reality.
- **The tool gains access to live organisation data** — a real Zoho People
  credential, a real mailbox grant, or ticketing configuration switched on. Those
  were deliberately excluded when the integrations were left unconfigured.
- **The confidentiality consequences change** — a customer, an audit, or a
  regulatory obligation attaches to this repository's contents.
- **The virtual environment residue in history is ever purged**, or is ever
  joined by any other history rewrite. Rewriting history is itself a decision
  with confidentiality consequences and needs the accountable owner's sign-off.
- **A year passes.** Re-confirming that public is still correct is cheap;
  noticing it stopped being correct is not.
- **A credential ever appears in history.** Push protection is enabled, but it
  guards future pushes only. Purging history then becomes a decision with its
  own confidentiality consequences and its own owner sign-off.

## Related

- [README.md](README.md) — installation, the secret guard, and the baseline
  verification command.
- [NOTICE](NOTICE) — the internal-use notice. Distinct from this file: licensing
  position and data-handling policy are two different decisions, and neither
  substitutes for the other.
- [.github/dependabot.yml](.github/dependabot.yml) and
  [.pre-commit-config.yaml](.pre-commit-config.yaml) — dependency scanning and the
  commit-time secret guard.
- [tools/verify_baseline.py](tools/verify_baseline.py) — the `confidentiality-record`
  and `no-real-data` criteria that hold this policy in place.
- The constitution (`.specify/memory/constitution.md`) is still an unratified
  template. It is listed here for completeness and must not be cited as an
  authority until it is ratified.