# Broad Host-Surface Reduction Boundary

Date: 2026-05-13
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: broad-host-surface-reduction-boundary-2026-05-13
Phase-A-Lock: LOCKED
Class: L4_STRUCTURAL
Category: /mu structural host-surface reduction plus same-wave bridge package reconciliation
Source authorization: `TASKS.md:320` and `TASKS.md:566` keep N3 broad host-surface boundary active under `[NEXT-CODEX-POST-REDTEAM]`.
Authorization: `TASKS.md:320`; `TASKS.md:566`; active deferred N3 broad host-surface boundary.
FOUNDER_OVERRIDE:broad-host-surface-reduction-boundary-2026-05-13
Routing source: `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`

Purpose: record the dispatcher-first Phase A route for the last active deferred
non-blocker, N3 broad host-surface boundary, and the later Phase B structural
implementation plus bridge package reconciliation for that bounded route.

## Scope

This packet began as a Phase A routing boundary, not an implementation packet.
The current staged package is now L4 structural because Phase B includes a
runtime/substrate acceptance-boundary reduction in
`mu/host/js/engine/pipeline.js` plus focused L4 gate coverage.

In scope for this Phase A plan:

- Maintain this governing packet:
  `reports/control_plane/broad_host_surface_reduction_boundary_2026-05-13.md`.
- Use `TASKS.md` only as read-only authorization evidence for the current task,
  specifically `TASKS.md:320` and `TASKS.md:566`.
- Reproduce the governing deferred packet references named below:
  `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:150`
  through
  `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:164`,
  `reports/deferred/non_blocking/README.md:341` through
  `reports/deferred/non_blocking/README.md:349`, and
  `reports/deferred/README.md:46` through `reports/deferred/README.md:48`.
- Reproduce the current host-semantics ratchet, host-authority inventory
  ratchet, host-authority inventory JSON, and docs consistency evidence.
- Inspect only the candidate source surfaces listed in
  `## Candidate Evidence Surfaces` to choose a later bounded Phase B route.

Original Phase A write scope:

- The Phase A routing rewrite wrote only
  `reports/control_plane/broad_host_surface_reduction_boundary_2026-05-13.md`.
- Phase B runtime behavior writes only the exact runtime and L4 gate files
  locked by this Phase A plan after current source and ratchet evidence
  identify one honest bounded route.

Current Phase B and bridge reconciliation write scope:

- Runtime implementation:
  `mu/host/js/engine/pipeline.js`.
- Focused L4 gate coverage:
  `mu/tests/l4_gates/test_wave11_hardening_gate.py`.
- Same-wave executor and private-attr gate repair for stale staged-scope,
  tracker generation, checker resolution, and physical `mu/tests` coverage:
  `mu/tools/executors/phase_b_executor.py`,
  `mu/tools/executors/commit_executor.py`,
  `mu/tools/checks/linters/check_private_attr_access.py`,
  `mu/tests/tools/test_phase_b_executor.py`,
  `mu/tests/tools/test_commit_executor_receipt.py`, and
  `mu/tests/tools/test_check_private_attr_access.py`.
- Package authority and receipt artifacts:
  `TASKS.md`,
  `reports/control_plane/broad_host_surface_reduction_boundary_2026-05-13.md`,
  `reports/l4_wave_indicators/broad-host-surface-reduction-boundary-2026-05-13.json`,
  and
  `reports/deferred/non_blocking/broad-host-surface-reduction-boundary-2026-05-13_bridge_nonblockers.md`.

## Grounding / Authorization

TASKS.md authorization:

- `TASKS.md:320` records `[NEXT-CODEX-POST-REDTEAM]` structural work for
  transparent JS live container provenance and states that, after that closure,
  the active deferred non-blocking residue is N3 broad host-surface boundary
  only.
- `TASKS.md:566` records the post-JS pipeline governance deferred cleanup and
  states that deferred inventory notes keep N3 broad host-surface boundary
  active while the cleanup itself does not authorize runtime, Stage0, seed,
  scheduler, registry, parity, production `/mu`, host-oracle, or
  Claude-related changes.
- TASKS.md authorizes this Phase A routing wave. It does not prove that every
  candidate source surface below still contains unlanded work. If current code
  truth proves a listed item already landed, Phase A must remove that item from
  pending work and acceptance criteria instead of relisting it as unresolved.

Active deferred evidence:

- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:150`
  names N3 as "P7-d is execution-path progress, not broad host-surface
  reduction."
- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:152`
  through `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:164`
  classifies N3 as a retained architectural boundary, requires a separate
  bounded control-plane packet before implementation, and forbids moving more
  semantic authority into Python or JavaScript host code.
- `reports/deferred/non_blocking/README.md:341` through
  `reports/deferred/non_blocking/README.md:349` records that the active
  deferred non-blocking lane now contains only this README plus
  `repo_truth_non_blockers_2026-03-14.md`, with N3 as the only open work inside
  that packet.
- `reports/deferred/README.md:46` through `reports/deferred/README.md:48`
  records N3 as the retained active `/mu` structural advisory.

Current command evidence:

```text
$ python3 mu/tools/checks/check_host_semantics_ratchet.py --json
"passed": true
current == baseline:
  JavaScript host_builtin=2 host_iteration=2 host_mutation=0 host_recursion=2
  Python host_builtin=1 host_iteration=3 host_mutation=0 host_recursion=2

$ python3 tools/checks/check_host_authority_inventory_ratchet.py
Scanned: 12 Python runtime files + 16 JS runtime files
Current total inventory: 311 total (181 Python + 130 JS)
Baseline total inventory: 312 total (181 Python + 131 JS)
Current authority subset: 217 total (120 Python + 97 JS)
Baseline authority subset: 217 total (120 Python + 97 JS)
PASS: No new total-inventory or authority-subset sites detected.
NOTE: baseline site removals detected - baseline can be updated after review.
NOTE: 9 existing authority site(s) changed signal shape.

$ ./tools/checks/check_docs_consistency.sh
All checks passed. Docs are consistent.
```

Interpretation:

- N3 is not closed. One non-authority total inventory site was removed, but the
  authority subset remains flat at 217.
- Updating the baseline or archiving N3 would be false closure unless a bounded
  implementation or explicit architecture decision proves a real authority or
  bootstrap-bound reduction.
- The next wave must choose a narrow host-surface reduction slice, not claim
  broad host-surface elimination.
- Transparent JS live container provenance and N5 JS pipeline governance are
  predecessor closures, not pending N3 work items.

## Phase A Work Items

1. Reproduce the TASKS.md authorization at `TASKS.md:320` and `TASKS.md:566`
   and the retained N3 deferred evidence from
   `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`.
2. Reproduce the current host-semantics ratchet, host-authority inventory
   ratchet, host-authority inventory JSON, and docs consistency evidence.
3. Inspect the current authority inventory JSON and the locked candidate source
   scope below. Select exactly one bounded candidate slice where Phase B can
   reduce host authority or narrow a bootstrap assumption without adding host
   semantics.
4. Prefer paired Python/JavaScript runtime surfaces when the behavior is
   semantically shared. If a single-substrate slice is selected, Phase A must
   justify why the slice is boundary-local and does not create parity debt.
5. Define the exact later Phase B write set, focused tests, ratchet
   expectations, proof class, and expected authority/host-semantics delta before
   implementation starts.
6. Remove any candidate from pending work and acceptance criteria if current
   code truth proves it already landed.
7. If no honest bounded implementation slice is available, leave N3 active and
   emit a precise next-wave task that states the missing evidence, candidate
   files, and required proof.

## Candidate Evidence Surfaces

The locked candidate source scope for read-only Phase A selection is:

- `mu/host/python/rcx_pi/selfhost/step_mu.py`
- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py`
- `mu/host/python/rcx_pi/selfhost/stage0_vm.py`
- `mu/host/js/engine/pipeline.js`
- `mu/host/js/core/stage0_vm.js`
- `mu/host/js/core/terminal_classification.js`
- `mu/host/js/core/types.js`

Phase A must choose based on current source and current ratchet JSON, not on
the existence of this list alone. The current JSON ratchet output also reports
one removed non-authority total site,
`mu/host/js/api/json_handlers.js::runRecurrence`, plus nine authority
signal-shape changes. Those are review inputs only; they do not themselves
close N3 or authorize baseline-only cleanup as a reduction.

## Phase A Current Evidence

TASKS and deferred-lane reproduction:

- `TASKS.md:320` binds
  `transparent-js-live-container-provenance-implementation-2026-05-13` to the
  active `[NEXT-CODEX-POST-REDTEAM]` structural lane and records that active
  deferred non-blocking residue is N3 broad host-surface boundary only.
- `TASKS.md:566` binds
  `post-js-pipeline-governance-deferred-cleanup-2026-05-12` and states that
  deferred inventory notes keep N3 broad host-surface boundary active without
  authorizing runtime, Stage0, seed, scheduler, registry, parity, production
  `/mu`, host-oracle, or Claude-related changes.
- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:150`
  through `:164` retains N3, requires a bounded successor packet before
  implementation, and forbids moving more semantic authority into Python or
  JavaScript host code.
- `reports/deferred/non_blocking/README.md:341` through `:349` records that
  the active non-blocking lane contains only that README plus
  `repo_truth_non_blockers_2026-03-14.md`, with N3 as the only open work inside
  the source packet.
- `reports/deferred/README.md:46` through `:48` records N3 as the retained
  active `/mu` structural advisory.

Ratchet and docs reproduction:

```text
$ python3 mu/tools/checks/check_host_semantics_ratchet.py --json
"passed": true
"decreases": []
"increases": []
current == baseline:
  JavaScript host_builtin=2 host_iteration=2 host_mutation=0 host_recursion=2
  Python host_builtin=1 host_iteration=3 host_mutation=0 host_recursion=2

$ python3 tools/checks/check_host_authority_inventory_ratchet.py
Scanned: 12 Python runtime files + 16 JS runtime files
Current total inventory: 311 total (181 Python + 130 JS)
Baseline total inventory: 312 total (181 Python + 131 JS)
Current authority subset: 217 total (120 Python + 97 JS)
Baseline authority subset: 217 total (120 Python + 97 JS)
PASS: No new total-inventory or authority-subset sites detected.
NOTE: baseline site removals detected - baseline can be updated after review.
NOTE: 9 existing authority site(s) changed signal shape.

$ ./tools/checks/check_docs_consistency.sh
All checks passed. Docs are consistent.
```

Authority inventory JSON reproduction:

```json
{
  "passed": true,
  "baseline_authority_counts": {"javascript": 97, "python": 120, "total": 217},
  "current_authority_counts": {"javascript": 97, "python": 120, "total": 217},
  "baseline_total_counts": {"javascript": 131, "python": 181, "total": 312},
  "current_total_counts": {"javascript": 130, "python": 181, "total": 311},
  "new_authority_sites": [],
  "new_total_sites": [],
  "removed_authority_sites": [],
  "removed_total_sites": [
    {
      "file": "mu/host/js/api/json_handlers.js",
      "line": 92,
      "name": "runRecurrence",
      "signals": [],
      "substrate": "javascript"
    }
  ],
  "authority_signal_changes": [
    "mu/host/js/core/stage0_vm.js::_stage0VmStepTrusted",
    "mu/host/js/core/stage0_vm.js::muCopy",
    "mu/host/js/core/terminal_classification.js::_loadTcProjections",
    "mu/host/js/core/types.js::isValidMu",
    "mu/host/js/core/types.js::muHash",
    "mu/host/js/core/types.js::muHashCached",
    "mu/host/js/engine/pipeline.js::hashTraceForRecurrence",
    "mu/host/js/engine/pipeline.js::serviceBoundaryEffect",
    "rcx_pi/selfhost/stage0_vm.py::_stage0_vm_step_trusted"
  ]
}
```

Interpretation:

- The removed `runRecurrence` total site is non-authority and cannot close N3.
- No new authority or total sites are present.
- The retained authority subset remains flat at 217, so the honest next step is
  a narrow acceptance-boundary reduction, not broad host-surface closure.

## Phase A Candidate Disposition

Removed from pending N3 implementation scope:

- Transparent JS live-container provenance is predecessor work already closed
  by `TASKS.md:320` and its archived deferred advisory. The signal-shape changes
  in `mu/host/js/core/types.js` and related JS live-container paths are review
  inputs only, not pending N3 work.
- JS pipeline module-shape governance is predecessor work already closed by
  `TASKS.md:566` and the N5 archive. Current
  `mu/host/js/engine/pipeline.js` derives boundary operation authority from
  `_ensureBoundaryOps()` and the engine seed, while
  `mu/host/python/rcx_pi/selfhost/engine_pipeline.py` derives the same operation
  set through `_load_boundary_ops()`. Re-routing generic boundary dispatch would
  duplicate already-landed N5/A10 work.
- Terminal classification already uses seed-derived projection paths in both
  substrates: JS `_loadTcProjections()` deep-copies and freezes
  `terminal_classify.v1.json` projections before `step()`, while Python derives
  terminal key sets from `_load_tc_projections()`. The current source evidence
  does not justify treating terminal-classification displacement itself as
  unlanded N3 work.
- Stage0 VM copy/trusted-step signal-shape changes are tied to earlier
  provenance and Stage0 repair work. Changing only their ratchet accounting or
  baseline would be false closure.

Selected bounded route:

- Route ID:
  `js-hash-trace-invalid-state-fail-closed-2026-05-13`.
- Boundary:
  `hash_trace` boundary operation invalid-state acceptance in the JS engine
  pipeline.
- Direct source evidence:
  - `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:940` through `:992`
    walks each linked-list trace entry, requires an entry dict with `state`, and
    unconditionally computes `state_hash` through
    `mu_hash_control(entry["state"], "hash_trace_for_recurrence")`.
  - `mu/host/js/engine/pipeline.js:175` through `:211` walks the equivalent
    linked-list trace, requires an entry object with `state`, but only computes
    `state_hash` when `isValidMu(entry.state)` is true. If `state` is not valid
    Mu, current JS source preserves the entry without adding `state_hash`.
  - Existing focused tests in
    `mu/tests/l4_gates/test_wave11_hardening_gate.py:34` through `:140` cover
    missing or non-object entries and JS parity for those malformed entries, but
    do not cover the invalid-`state` acceptance boundary.
- Why this is an honest N3 slice:
  This route does not move semantic authority into either host. It narrows a
  JS-only bootstrap acceptance gap at an existing boundary operation so JS
  rejects an invalid trace state instead of rebuilding a host-shaped trace entry
  without a `state_hash`. Python is the read-only parity reference because its
  current source already takes the strict path.
- Why this does not create parity debt:
  The selected implementation is single-substrate only because the paired
  Python path is already strict. Phase B must add cross-substrate behavioral
  tests so the JS path matches Python rejection behavior for invalid trace
  state.

## Locked Phase B Implementation Scope

Phase B runtime behavior may write only:

- `mu/host/js/engine/pipeline.js`
- `mu/tests/l4_gates/test_wave11_hardening_gate.py`

Same-wave bridge package reconciliation may also write only:

- `TASKS.md`
- `mu/tools/executors/phase_b_executor.py`
- `mu/tools/executors/commit_executor.py`
- `mu/tools/checks/linters/check_private_attr_access.py`
- `mu/tests/tools/test_phase_b_executor.py`
- `mu/tests/tools/test_commit_executor_receipt.py`
- `mu/tests/tools/test_check_private_attr_access.py`
- `reports/control_plane/broad_host_surface_reduction_boundary_2026-05-13.md`
- `reports/l4_wave_indicators/broad-host-surface-reduction-boundary-2026-05-13.json`
- `reports/deferred/non_blocking/broad-host-surface-reduction-boundary-2026-05-13_bridge_nonblockers.md`

Read-only parity reference:

- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py`

Required implementation shape:

- In `hashTraceForRecurrence`, reject an entry whose `state` is not valid Mu
  before rebuilding the trace, instead of returning an entry without
  `state_hash`.
- Preserve the existing malformed-entry, cycle, cap, and valid-entry behavior.
- Do not add new public constructors, trust mutators, host oracles, seed data,
  Stage0 changes, Python runtime changes, ratchet-baseline edits,
  retained deferred source edits, unrelated generated indicators, or
  Claude-related changes.
- Bridge package reconciliation may update `TASKS.md`, this packet, the exact
  same-wave indicator artifact, Phase B/commit executor private-attr gate
  surfaces and tests, and the same-wave generated bridge non-blocker receipt
  only to make staged scope, L4 class, and tracker evidence match the actual
  Phase B package.

Focused tests to add:

- Python parity/negative-control test showing
  `hash_trace_for_recurrence({"head": {"state": <invalid Mu>}, "tail": None})`
  rejects invalid `state`.
- JS behavioral test showing `hashTraceForRecurrence(...)` rejects the same
  invalid `state` instead of returning `OK:false` / an un-hashed entry.
- JS positive control preserving the existing valid-entry path and
  `state_hash` production.

Later Phase B-local validation commands:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_wave11_hardening_gate.py::TestR5HashTraceFailClosed mu/tests/l4_gates/test_wave11_hardening_gate.py::TestR5HashTraceJsParity --tb=short -p no:cacheprovider
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py::TestBehaviorPreservation::test_hash_trace_produces_result --tb=short -p no:cacheprovider
node mu/host/js/eval_step.js
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
python3 tools/checks/check_host_authority_inventory_ratchet.py
python3 tools/checks/check_host_authority_inventory_ratchet.py --json
./tools/checks/check_docs_consistency.sh
```

Expected proof class and deltas:

- Proof class: source-lock plus behavioral positive control plus negative
  control.
- Host-semantics ratchet: no increase.
- Authority inventory: no new total-inventory or authority-subset sites.
- Real reduction class: JS boundary acceptance is narrowed; this is not
  baseline-only cleanup and does not claim broad N3 closure.
- N3 status after Phase B: remains active unless the implementation plus later
  executor/closeout evidence explicitly routes or closes the retained broader
  advisory.

## Constraints

- Use dispatcher pipeline: routing record -> Phase A -> Phase B -> commit
  executor.
- Do not hand-implement runtime changes before Phase A locks a bounded route.
- Do not edit Claude-related files.
- Runtime source/test edits are limited to
  `mu/host/js/engine/pipeline.js` and
  `mu/tests/l4_gates/test_wave11_hardening_gate.py`.
- Same-wave bridge package reconciliation edits are limited to `TASKS.md`,
  `mu/tools/executors/phase_b_executor.py`,
  `mu/tools/executors/commit_executor.py`,
  `mu/tools/checks/linters/check_private_attr_access.py`,
  `mu/tests/tools/test_phase_b_executor.py`,
  `mu/tests/tools/test_commit_executor_receipt.py`,
  `mu/tests/tools/test_check_private_attr_access.py`, this packet, the exact
  same-wave indicator artifact
  `reports/l4_wave_indicators/broad-host-surface-reduction-boundary-2026-05-13.json`,
  and the same-wave generated bridge non-blocker receipt
  `reports/deferred/non_blocking/broad-host-surface-reduction-boundary-2026-05-13_bridge_nonblockers.md`.
- Do not edit retained deferred source docs, ratchet baselines, unrelated
  generated indicators, or Claude-related files as part of this Phase B
  package.
- Do not reduce counts by renaming, hiding, inlining, deleting ratchet signals,
  or baseline-only accounting.
- Do not add semantic host debt. Future `/mu` changes must program in Mu,
  narrow bootstrap assumptions, or shrink host authority.
- Preserve Python/JavaScript parity for any semantically shared runtime path.
- Do not treat `TASKS.md:566` cleanup authority as runtime implementation
  authority. Runtime or substrate edits require the locked Phase A route plus a
  later same-wave Phase B/commit authorization path.
- Any manual pipeline repair must include a same-wave mechanical fix in builder,
  dispatcher, recovery, commit, or pre-commit automation, or leave a precise
  next-wave automation packet.

## Stop Conditions

- Stop if Phase A cannot name an exact bounded implementation slice with direct
  source evidence and a validation plan.
- Stop if the proposed change merely moves semantic authority between host
  helper functions.
- Stop if the proposed route would increase host-semantics ratchet counts,
  authority inventory, or parity debt without explicit founder authorization.
- Stop if dispatcher, builder, recovery, or commit automation selects a
  completed packet or stale wrong-wave packet.
- Stop if current source proves the selected pending item already landed; remove
  it from the pending plan instead of routing duplicate work.

## Acceptance Criteria

- This packet contains explicit Scope, Phase A Work Items, Constraints, Stop
  Conditions, Acceptance Criteria, and Grounding / Authorization sections.
- This packet cites `TASKS.md:320` and `TASKS.md:566` as current
  `[NEXT-CODEX-POST-REDTEAM]` authorization for routing the retained N3 broad
  host-surface boundary.
- Phase A records current command evidence for host semantics and authority
  inventory, including JSON inventory evidence.
- Phase A selects one bounded route or explicitly keeps N3 active with a
  precise next-wave task.
- Phase B runtime behavior changes only the files named by the locked Phase A
  plan; same-wave bridge package reconciliation is limited to the explicit
  tracker, packet, indicator, executor, private-attr checker, focused
  executor/checker tests, and generated bridge non-blocker receipt named above.
- Any implementation demonstrates no host-semantics increase and no authority
  inventory increase; a real reduction must be distinguished from baseline-only
  cleanup.
- Already implemented predecessor work is not relisted as unresolved N3 work.
- The active deferred lane is updated only when code or locked architecture
  evidence proves a section closed or was routed into a bounded successor packet.

## Validation Required

Minimum Phase A validation:

```bash
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
python3 tools/checks/check_host_authority_inventory_ratchet.py
python3 tools/checks/check_host_authority_inventory_ratchet.py --json
./tools/checks/check_docs_consistency.sh
```

Any later Phase B implementation must add focused tests for the selected
runtime/control-plane surface and rerun the relevant Python/JavaScript parity,
L4, ratchet, and docs checks named by the locked Phase A plan.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `broad-host-surface-reduction-boundary-2026-05-13`
- Active packet: `reports/control_plane/broad_host_surface_reduction_boundary_2026-05-13.md`
- Indicator artifact: `reports/l4_wave_indicators/broad-host-surface-reduction-boundary-2026-05-13.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/js/engine/pipeline.js`
  - `mu/tests/l4_gates/test_wave11_hardening_gate.py`
  - `mu/tests/tools/test_check_private_attr_access.py`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/checks/linters/check_private_attr_access.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/broad_host_surface_reduction_boundary_2026-05-13.md`
  - `reports/l4_wave_indicators/broad-host-surface-reduction-boundary-2026-05-13.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
