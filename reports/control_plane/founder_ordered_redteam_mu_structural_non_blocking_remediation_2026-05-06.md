# Founder Ordered Redteam Mu Structural Non-Blocking Remediation

Date: 2026-05-06
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Category: /mu structural
Severity: NON-BLOCKING
Source audit packet: `reports/deferred/non_blocking/founder_ordered_redteam_repo_code_audit_2026-05-05_non_blocking.md`
Queue order: `/mu` structural remediation, ordered last after all non-`/mu` blocking and non-blocking remediation packets and after `/mu` structural blocking packet creation.
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06
Source authorization: FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05

This Phase B implementation wave re-verified the non-blocking `/mu` structural
follow-up from the founder ordered redteam audit output and selected the bounded
N1 outcome: intentionally Python-only evidence-walker runtime with JS
source-lock-only registry proof. It does not widen JS runtime parity claims or
stage JavaScript runtime edits.
## Source Finding

### N1 - JS Ontology Evidence Collection Is Source-Locked, Not Structurally Executed

Classification: NON-BLOCKING PROOF-CLASS MISMATCH

Surfaces: JavaScript engine pipeline, evidence-walker seed wiring, ontology
promotion evidence collection.

Source evidence preserved from
`reports/deferred/non_blocking/founder_ordered_redteam_repo_code_audit_2026-05-05_non_blocking.md`:

- Lines 36-45: `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:597`
  through `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:600` state trace
  walking is structural via `evidence_walker.v1.json`;
  `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:609` through
  `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:614` load the seed and
  execute it through `run_mu`; `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:619`
  through `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:653` retain a
  boundary fallback for walker stalls and boundary post-processing.
- Lines 46-49: `mu/host/js/engine/pipeline.js:785` defines
  `collectOntologyEvidence`, and `mu/host/js/engine/pipeline.js:792` through
  `mu/host/js/engine/pipeline.js:811` drain the trace with host `while`, `Set`,
  and `sort` operations.
- Lines 50-53: `mu/host/js/cli/main.js:39` registers
  `evidence_walker.v1.json` with the note that it is "registered but not
  loaded at runtime"; the projection ID entry at `mu/host/js/cli/main.js:154`
  repeats that it is registered but not loaded at runtime.
- Lines 54-56: `mu/tests/l4_gates/test_evidence_walker_gate.py:46` through
  `mu/tests/l4_gates/test_evidence_walker_gate.py:47` classify the JS gate as
  registry source-lock, not runtime parity.
- Lines 57-59: `mu/docs/core/L3SubstrateArchitecture.v0.md:47` marks
  `evidence_walker.v1` as Python-only, so current repository documentation does
  not claim JS runtime parity for this seed.

## Phase B Outcome (2026-05-09)

Selected bounded outcome: intentionally Python-only evidence-walker runtime with
JS source-lock-only proof.

Fresh verification:

- `TASKS.md:465` authorizes only N1:
  `JS Ontology Evidence Collection Is Source-Locked, Not Structurally Executed`.
- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:597` through
  `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:653` remain the Python
  structural baseline: Python loads `evidence_walker.v1.json`, executes it
  through `run_mu`, and boundary-post-processes walker output.
- `mu/host/js/engine/pipeline.js:785` remains a JS boundary-effect helper; JS
  host drains the boundary trace and does not execute `evidence_walker.v1`.
- `mu/host/js/cli/main.js` keeps the checksum and projection ID registries for
  JS source-lock proof but does not load `evidence_walker.v1` into
  `seedProjectionMap`.

Implementation:

- JS runtime source was left unchanged after fresh verification showed the
  existing code already keeps `evidence_walker.v1.json` out of the JS runtime
  seed map and retains host-boundary trace drainage.
- `mu/tests/l4_gates/test_evidence_walker_gate.py` now distinguishes Python
  structural runtime proof from JS source-lock proof and locks the JS
  `seedProjectionMap` non-load behavior.
- `mu/docs/core/L3SubstrateArchitecture.v0.md` now states that
  `evidence_walker.v1` has JS source-lock only while structural runtime remains
  Python-only.
- `TASKS.md` records the selected proof-class outcome, canonical tracker sync
  note, same-wave authorization, evidence command, L4 indicator artifact, and
  proof limit.

Local evidence:

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_evidence_walker_gate.py`
  exits `0` with `10 passed in 0.13s`.
- `PYTHONDONTWRITEBYTECODE=1 python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06`
  exits `0`.
- `PYTHONDONTWRITEBYTECODE=1 python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-class L4_ENABLER`
  exits `0`.

Proof limit: this wave intentionally does not add JS structural execution. Any
future JS runtime parity claim for `evidence_walker.v1` must add behavioral or
structural execution proof rather than relying on registry source-lock.

## Scope: Files And Directories In Scope

No directory-wide scope is granted. Scope is limited to the exact paths below.

Current Phase A packet-rewrite write scope:

- `reports/control_plane/founder_ordered_redteam_mu_structural_non_blocking_remediation_2026-05-06.md`

Later implementation-wave candidate write scope, only after dispatcher re-entry
and fresh verification:

- `mu/host/js/engine/pipeline.js`
- `mu/host/js/cli/main.js`
- `mu/tests/l4_gates/test_evidence_walker_gate.py`
- `mu/docs/core/L3SubstrateArchitecture.v0.md`
- `TASKS.md` tracker entry for
  `[FOUNDER-ORDERED-REDTEAM-MU-STRUCTURAL-NON-BLOCKING-REMEDIATION]`

Phase B implementation-wave write scope used:

- `reports/control_plane/founder_ordered_redteam_mu_structural_non_blocking_remediation_2026-05-06.md`
- `mu/tests/l4_gates/test_evidence_walker_gate.py`
- `mu/docs/core/L3SubstrateArchitecture.v0.md`
- `TASKS.md`
- `reports/l4_wave_indicators/founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06.json`

Later implementation-wave read-only grounding scope:

- `TASKS.md:456` through `TASKS.md:465`, especially `TASKS.md:465`
- `reports/deferred/non_blocking/founder_ordered_redteam_repo_code_audit_2026-05-05_non_blocking.md`
- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:597` through
  `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:653`

`mu/host/python/rcx_pi/selfhost/engine_pipeline.py` is the Python structural
baseline for this finding, not a default write target.

## Work Items: Concrete Bounded Tasks From TASKS.md Current Phase

1. Re-verify the single TASKS-authorized finding inventory at `TASKS.md:465`:
   `N1 - JS Ontology Evidence Collection Is Source-Locked, Not Structurally
   Executed`. Do not add findings from other packets or categories.
2. Re-check only the cited N1 surfaces and classify the current state into one
   of three bounded outcomes:
   source-lock-only JS proof, intentionally Python-only evidence-walker runtime,
   or JS structural execution with proof.
3. If current truth remains source-lock-only or intentionally Python-only, bound
   the claim without adding JS runtime execution: align
   `mu/host/js/cli/main.js`, `mu/tests/l4_gates/test_evidence_walker_gate.py`,
   and `mu/docs/core/L3SubstrateArchitecture.v0.md` so they state the same
   proof class and do not imply JS runtime parity for `evidence_walker.v1`.
4. If current truth requires JS structural execution, implement only the
   `evidence_walker.v1` ontology-evidence path in
   `mu/host/js/engine/pipeline.js` and `mu/host/js/cli/main.js`, then update
   `mu/tests/l4_gates/test_evidence_walker_gate.py` with a runtime structural
   execution proof and update `mu/docs/core/L3SubstrateArchitecture.v0.md` to
   match that proof class.
5. Preserve the non-blocking proof-class mismatch classification unless fresh
   source evidence proves a live JS production parity contradiction.
6. Update the matching `TASKS.md` tracker entry only in the later
   implementation wave, with implementation status, evidence command(s), proof
   class, and same-wave authorization for
   `founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06`.

## Constraints: Not In Scope

- No implementation was authorized by the earlier Phase A packet; this Phase B
  implementation is same-wave authorized by
  `FOUNDER_OVERRIDE:founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06`.
- No broad `/mu` structural remediation is authorized.
- No edits are authorized outside the exact files listed in the scope section
  and the canonical L4 indicator artifact named above.
- No Claude-related files are in scope.
- No non-`/mu` docs, tests, or tooling remediation is in scope.
- No rework of the closed `/mu` structural blocking host-object remediation at
  `TASKS.md:463` through `TASKS.md:464` is in scope.
- No relisting of already landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work is allowed.
- No widening of JS production parity claims is allowed without matching runtime
  structural execution proof.
- No host-only shortcut may replace structural seed execution proof.

## Stop Conditions

- Stop if current docs/tests/source truth proves the proof-class mismatch has
  already been resolved or intentionally scoped; update the tracker instead of
  implementing stale work.
- Stop if remediation would widen JS production claims without adding matching
  structural execution proof.
- Stop if Python/JS substrate parity or proof-class honesty cannot be preserved.
- Stop if any Claude-related file would need to be edited.
- Stop if the work requires files outside the exact scoped paths in this packet.
- Stop if the implementation would need to change the Python structural baseline
  instead of using it as grounding evidence.

## Acceptance Criteria

- Phase A packet authority is same-wave bound by
  `FOUNDER_OVERRIDE:founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06`.
- The packet lists the exact current Phase A write scope, later implementation
  candidate write scope, and read-only grounding scope.
- The later implementation wave chooses exactly one bounded N1 outcome:
  source-lock-only JS proof, intentionally Python-only runtime, or JS structural
  execution with proof.
- JS ontology evidence collection claims, tests, docs, and source behavior are
  aligned as source-lock-only, Python-only, or structurally executed in JS with
  proof.
- Any future runtime parity claim is backed by behavioral or structural
  execution evidence rather than registry source-lock alone.
- The wave does not relist already landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work as unresolved.
- The matching `TASKS.md` entry is updated with implementation and evidence
  status during the later implementation wave.

## Grounding / Authorization

- Governing task authority: `[NEXT-CODEX-POST-REDTEAM]`.
- Current TASKS implementation status: `TASKS.md:465` records
  `[FOUNDER-ORDERED-REDTEAM-MU-STRUCTURAL-NON-BLOCKING-REMEDIATION]` as
  `IMPLEMENTED / LOCAL EVIDENCE` with this packet path, this wave ID, class
  `L4_ENABLER`, category `/mu structural`, and the single N1 finding inventory.
- Current ordering and exclusion grounding: `TASKS.md:456` through
  `TASKS.md:464` establish predecessor remediation status, preserve the order
  placing this `/mu` structural non-blocking item last, and exclude already
  landed engine-state/scheduler and `/mu` structural blocking work from this
  packet.
- Governing packet: `reports/control_plane/founder_ordered_redteam_mu_structural_non_blocking_remediation_2026-05-06.md`.
- Source audit packet: `reports/deferred/non_blocking/founder_ordered_redteam_repo_code_audit_2026-05-05_non_blocking.md`.
- Authorization:
  `FOUNDER_OVERRIDE:founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06`.
- Source authorization preserved for queue provenance only:
  `FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05`.

## Tracker Update Note

Updated the
`[FOUNDER-ORDERED-REDTEAM-MU-STRUCTURAL-NON-BLOCKING-REMEDIATION]` entry under
`[NEXT-CODEX-POST-REDTEAM]` with this packet path, this wave ID, category
`/mu structural`, severity `non-blocking`, source audit packet path, the
Phase-A hard-stop provenance, same-wave `FOUNDER_OVERRIDE`, selected proof-class
outcome, canonical tracker sync note, L4 indicator artifact, and acceptance
evidence.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06`
- Active packet: `reports/control_plane/founder_ordered_redteam_mu_structural_non_blocking_remediation_2026-05-06.md`
- Indicator artifact: `reports/l4_wave_indicators/founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/docs/core/L3SubstrateArchitecture.v0.md`
  - `mu/tests/l4_gates/test_evidence_walker_gate.py`
  - `reports/control_plane/founder_ordered_redteam_mu_structural_non_blocking_remediation_2026-05-06.md`
  - `reports/deferred/non_blocking/founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06`
- Active packet: `reports/control_plane/founder_ordered_redteam_mu_structural_non_blocking_remediation_2026-05-06.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `4102cc17d2f383e1566abbc2861ce673464048ccd0dfcfe09af8494c6c7d9c33`
- Indicator artifact: `reports/l4_wave_indicators/founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_evidence_walker_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/founder_ordered_redteam_mu_structural_non_blocking_remediation_2026-05-06.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06.json`
- Current staged files:
  - `TASKS.md`
  - `mu/docs/core/L3SubstrateArchitecture.v0.md`
  - `mu/tests/l4_gates/test_evidence_walker_gate.py`
  - `reports/control_plane/founder_ordered_redteam_mu_structural_non_blocking_remediation_2026-05-06.md`
  - `reports/deferred/non_blocking/founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
