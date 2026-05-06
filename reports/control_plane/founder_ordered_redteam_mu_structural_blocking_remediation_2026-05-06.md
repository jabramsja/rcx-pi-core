# Founder Ordered Redteam Mu Structural Blocking Remediation

Date: 2026-05-06
Status: QUEUED - HARD STOP BEFORE IMPLEMENTATION
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06
Class: L4_ENABLER
Category: /mu structural
Severity: BLOCKING
Source audit packet: `reports/deferred/blocking/founder_ordered_redteam_repo_code_audit_2026-05-05_blocking.md`
Queue order: `/mu` structural remediation, ordered last after all non-`/mu` blocking and non-blocking remediation packets.
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05

This packet queues the blocking `/mu` structural follow-up from the founder
ordered redteam audit output. It is a hard stop before implementation. The
queue-organization wave may create this packet and its tracker entry, but must
not dispatch or implement the `/mu` structural remediation.

## Source Finding

### B1 - JavaScript Mu Validation Admits Host Objects

Classification: BLOCKING DEFECT

Surfaces: Python/JavaScript substrate sync, host-authority drift, Mu boundary
validation, content-addressed hashing.

Source evidence preserved from
`reports/deferred/blocking/founder_ordered_redteam_repo_code_audit_2026-05-05_blocking.md`:

- Lines 36-43: `mu/host/js/core/types.js:87` documents `isValidMu` as a Mu type
  validator, while `mu/host/js/core/types.js:122` and
  `mu/host/js/core/types.js:161` accept any JavaScript value whose `typeof` is
  `object`; `mu/host/js/core/types.js:162` through
  `mu/host/js/core/types.js:171` validate only enumerable string keys and
  recursively valid values, with no plain-object or prototype restriction.
- Lines 44-51: `mu/host/python/rcx_pi/selfhost/mu_type.py:95` defines Mu as
  JSON-compatible; `mu/host/python/rcx_pi/selfhost/mu_type.py:203` through
  `mu/host/python/rcx_pi/selfhost/mu_type.py:207` require exact compound types;
  `mu/host/python/rcx_pi/selfhost/mu_type.py:209`,
  `mu/host/python/rcx_pi/selfhost/mu_type.py:238`, and
  `mu/host/python/rcx_pi/selfhost/mu_type.py:251` reject anything other than an
  exact `list` or exact `dict` after primitive checks.
- Lines 55-76 preserve direct JS output where `Date`, `Map`, an empty class
  instance, a class instance with an enumerable key, and a plain object all
  report `valid=true`; empty host objects hash the same as `{}`, and the class
  instance with key `a = 1` hashes the same as a plain Mu object with that field.
- Lines 78-98 preserve direct Python output where an arbitrary object and a
  `dict` subclass are rejected by `is_mu`/`mu_hash`, while a plain dict is
  accepted and hashed.

## Remediation Scope For Future Wave

- Align JavaScript Mu validation/hash boundary behavior with the portable
  JSON-compatible Mu contract and Python exact-compound-type boundary.
- Preserve Python/JavaScript substrate parity and host-authority containment at
  the validator/hash boundary.
- Add or update parity/fail-closed proof that host objects, class instances,
  Maps, Dates, prototype-bearing objects, and object subclasses cannot be
  treated as portable Mu values unless a narrower current source packet proves
  that scope has changed.

## Hard Stop

Do not implement this `/mu` structural remediation from the queue-organization
wave. Stop after creating this packet and the matching tracker entry. A later
founder-authorized implementation wave must explicitly re-enter the dispatcher
pipeline before editing `/mu` structural code or tests.

## Stop Conditions

- Stop if current code truth proves the JS boundary already rejects the audited
  host object cases; update the tracker instead of implementing stale work.
- Stop if a proposed fix would add host-only semantics rather than shrinking or
  tightening the Mu boundary in a parity-preserving way.
- Stop if Python/JS substrate parity cannot be preserved by the proposed
  remediation.
- Stop if any Claude-related file would need to be edited.

## Acceptance Criteria

- JavaScript Mu validation and hashing no longer accept the audited host object
  cases as portable Mu values.
- Python/JavaScript substrate behavior remains parity-preserving for portable
  Mu values and rejection cases.
- Focused direct-output evidence proves the formerly accepted JS host object
  cases fail closed.
- The wave does not relist already landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work as unresolved.
- The matching `TASKS.md` entry is updated with implementation and evidence
  status.

## Tracker Update Note

Add or update the `[FOUNDER-ORDERED-REDTEAM-MU-STRUCTURAL-BLOCKING-REMEDIATION]`
entry under `[NEXT-CODEX-POST-REDTEAM]` with this packet path, this wave ID,
category `/mu structural`, severity `blocking`, source audit packet path, the
hard-stop marker, and the acceptance evidence once a later authorized
implementation wave runs.
