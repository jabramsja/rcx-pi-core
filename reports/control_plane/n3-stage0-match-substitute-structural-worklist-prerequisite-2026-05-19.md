# N3-Stage0-Match-Substitute-Structural-Worklist-Prerequisite-2026-05-19

Date: 2026-05-19
Status: IMPLEMENTED / LOCAL EVIDENCE
Class: L4_ENABLER route only; later implementation, if authorized, must be L4_STRUCTURAL.
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19
Parent wave: n3-stage0-match-substitute-host-semantics-reduction-2026-05-19
Parent packet: reports/control_plane/n3-stage0-match-substitute-host-semantics-reduction-2026-05-19_2026-05-19.md
Phase-A-Lock: LOCKED
FOUNDER_OVERRIDE:n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19

## Purpose

Materialize the precise prerequisite route required by the parent Stage0
match/substitute host-semantics reduction packet after that parent packet found
no selected marker honestly removable inside its bounded wave.

This packet is a route-only prerequisite. It does not authorize Python,
JavaScript, seed, ratchet, baseline, test, executor, pipeline, or successor
implementation edits. The only indicator write authorized by this route is the
same-wave L4_ENABLER artifact at
`reports/l4_wave_indicators/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.json`.
Its first required successor action is tracker synchronization for this exact
wave and packet path.

## Scope

This routed prerequisite packet covers only the structural route for replacing
the selected Stage0 match/substitute host-recursive tree walks and the selected
Python builtin/type-dispatch marker with a parity-preserving structural
worklist or self-hosted match/substitute default-path reduction.

Held future implementation scope, after tracker authority exists:

- `mu/host/python/rcx_pi/selfhost/eval_seed.py:524-533` for `_stage0_match`
  `@host_recursion` and `@host_builtin`.
- `mu/host/python/rcx_pi/selfhost/eval_seed.py:603-609` for
  `_stage0_substitute` `@host_recursion`.
- `mu/host/js/core/bootstrap_core.js:441-445` for `stage0Match`
  `@host_recursion`.
- `mu/host/js/core/bootstrap_core.js:515-518` for `stage0Substitute`
  `@host_recursion`.
- Focused Stage0/parity negative controls only when they directly prove the
  selected behavior and marker reduction.
- A later implementation `reports/l4_wave_indicators/` artifact only when a
  successor implementation packet is authorized; this prerequisite route has only
  its own same-wave L4_ENABLER artifact at
  `reports/l4_wave_indicators/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.json`.

Explicitly out of scope for this routed prerequisite:

- `mu/host/js/core/bootstrap_core.js:293` projection-loop dispatch.
- Runtime, substrate, seed, registry, scheduler, loader, executor, commit,
  pre-commit, recovery, ratchet baseline, generated-manifest, pipeline, test, or
  successor implementation edits.
- Any broad repository cleanup or documentation rewrite beyond this route.

## Work Items

1. Before any Phase A decision beyond this route, add a detector-visible
   `TASKS.md` tracker entry for the exact wave ID
   `n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19`,
   this packet path, and
   `FOUNDER_OVERRIDE:n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19`.
   The tracker entry must also include this route's same-wave
   `indicator_artifact_ref` and `indicator_collection_command` metadata required
   by the current L4_ENABLER execution contract.
2. Prove the tracker entry with this TASKS-only command before inspecting or
   editing implementation files:

   ```bash
   rg -n "n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19|FOUNDER_OVERRIDE:n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19" TASKS.md
   ```

3. Re-open only the held Python and JavaScript line windows listed in Scope and
   reconstruct the current Stage0 match/substitute host-recursive tree walks and
   Python builtin/type-dispatch behavior from current file:line evidence.
4. Decide whether a parity-preserving structural worklist, explicit stack, or
   self-hosted Mu/Stage0 default-path reduction can replace the selected host
   recursion and builtin/type-dispatch markers without making Python or
   JavaScript semantically smarter.
5. If a reduction route is viable, lock a later L4_STRUCTURAL write set, focused
   negative controls, parity proof, host-semantics ratchet proof, host-authority
   inventory proof, strict L4 contract command, indicator collection command,
   rollback limits, and proof limits before implementation.
6. If no such reduction route is viable, return NO-GO and do not relist the
   selected markers as removable.

## Phase B Tracker Sync And Route Decision

Tracker proof after the same-wave `TASKS.md` sync:

```bash
rg -n "n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19|FOUNDER_OVERRIDE:n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19" TASKS.md
```

Result: exits `0` and matches `TASKS.md:636`, which now binds this exact wave
ID, this packet path, and the same-wave `FOUNDER_OVERRIDE` token outside the
parent packet.

Current held evidence, reopened only after that TASKS proof:

- `mu/host/python/rcx_pi/selfhost/eval_seed.py:524-533` still marks
  `_stage0_match` with `@host_recursion` and `@host_builtin`; the marker text
  identifies `isinstance` dispatch, recursive dict traversal, `.keys()`,
  `.get()`, and `in` as the selected Python host builtin/type-dispatch surface.
- `mu/host/python/rcx_pi/selfhost/eval_seed.py:603-609` still marks
  `_stage0_substitute` with `@host_recursion` for recursive dict/list
  traversal.
- `mu/host/js/core/bootstrap_core.js:441-445` still marks `stage0Match` as
  Stage0 recursive pattern matching.
- `mu/host/js/core/bootstrap_core.js:515-518` still marks `stage0Substitute`
  as recursive tree-walk substitution.

Route decision: GO only for later `L4_STRUCTURAL` packetization of a
parity-preserving structural worklist/default-path reduction. This is not
implementation authority. A recursion-only explicit-worklist route can target
the selected Python and JavaScript `@host_recursion` markers without touching
`mu/host/js/core/bootstrap_core.js:293`. The Python `@host_builtin`
type-dispatch marker must not be claimed removed by a recursion-only rewrite; a
successor may claim that marker only if it also proves a self-hosted
Mu/Stage0 default-path match reduction or equivalent structural dispatch with
no Python-only or JavaScript-only semantic inference.

Later `L4_STRUCTURAL` write set, if authorized by a successor packet, must be a
subset of:

- `TASKS.md`
- `reports/control_plane/n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19.md`
- `reports/l4_wave_indicators/n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19.json`
- `mu/host/python/rcx_pi/selfhost/eval_seed.py`
- `mu/host/js/core/bootstrap_core.js`
- `mu/tests/l4_gates/test_stage0_production_pilot_gate.py`
- `mu/tests/l4_gates/test_w3_crash_guards_gate.py`
- `mu/tests/parity/test_js_vm_bridge_parity.py`
- `mu/tests/structural/test_execution_layer_truth_contract.py`

Focused successor controls and parity proof must include the direct Stage0
canonical/negative controls and Python/JS compiled match/substitute parity:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q \
  mu/tests/l4_gates/test_stage0_production_pilot_gate.py::TestStage0CanonicalVectors \
  mu/tests/l4_gates/test_stage0_production_pilot_gate.py::TestParityWithMatchInner \
  mu/tests/l4_gates/test_w3_crash_guards_gate.py::TestF11EmptyVarNameNoMatch \
  mu/tests/l4_gates/test_w3_crash_guards_gate.py::TestF25JsStage0MatchEmptyVar \
  mu/tests/parity/test_js_vm_bridge_parity.py::TestMatchVmBridgeParity \
  mu/tests/parity/test_js_vm_bridge_parity.py::TestSubstVmBridgeParity \
  mu/tests/structural/test_execution_layer_truth_contract.py::TestD005Stage0Contract \
  --tb=short
node mu/host/js/eval_step.js
```

Successor ratchet, indicator, and strict contract proof must be named before
implementation and must not update baselines:

```bash
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
python3 tools/checks/check_host_authority_inventory_ratchet.py
python3 tools/metrics/collect_l4_wave_indicators.py --wave-id n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19 --output reports/l4_wave_indicators/n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19.json
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19 --wave-class L4_STRUCTURAL
./tools/checks/check_docs_consistency.sh
```

Rollback limit: revert only the successor packet's bounded write set above and
leave runtime/substrate behavior unchanged if parity, marker-ratchet, authority,
strict L4, or docs consistency proof fails.

Proof limit: a successor may claim only the specifically proven selected marker
reduction and preserved Stage0/parity behavior. It must not claim full
self-hosting, broad host-semantics reduction, production readiness, baseline
cleanup, `bootstrap_core.js:293` reduction, or closure of unrelated N3 surfaces.

## Constraints

- This packet is route-only and must not be used as implementation authority.
- No runtime, substrate, seed, registry, scheduler, loader, executor, commit,
  pre-commit, recovery, ratchet baseline, generated-manifest, pipeline, or test
  edit is authorized by this packet.
- No host exception tables, host-only accepted sets, substrate-only semantic
  inference, smarter Python or JavaScript behavior, or baseline-only proof may
  satisfy this prerequisite.
- Any later reduction must preserve Python/JavaScript parity or explicitly
  route a substrate-specific proof before implementation.
- Any later marker reduction must be proven by current marker evidence and
  ratchet output, not by doc wording or packet intent.
- The parent wave remains a no-runtime-edit, no-marker-removal outcome.

## Stop Conditions

Stop with NO-GO/HOLD if any of these conditions holds:

- `TASKS.md` lacks detector-visible tracker authority for this exact wave ID,
  packet path, and `FOUNDER_OVERRIDE`.
- The candidate reduction touches files outside the held future implementation
  scope.
- The candidate reduction requires `bootstrap_core.js:293`.
- The candidate reduction adds host semantics, host exception tables, smarter
  substrate behavior, baseline updates, or parity skew.
- Current code evidence shows the selected markers have already changed enough
  that the held line windows are no longer the real implementation surface.
- Focused Stage0/parity proof, host-semantics ratchet, host-authority inventory
  ratchet, strict L4 execution contract, indicator collection, or docs
  consistency cannot be named before implementation.

## Acceptance Criteria

- This packet exists at the exact successor route named by the parent packet:
  `reports/control_plane/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.md`.
- The successor route is detector-visible outside the parent packet and
  therefore no longer exists only as a textual path in the parent route.
- This prerequisite route carries the same-wave L4_ENABLER indicator artifact at
  `reports/l4_wave_indicators/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.json`
  and the matching tracker `indicator_collection_command`.
- This packet does not claim host-semantics reduction, marker removal, runtime
  edits, or implementation readiness.
- A later successor packet can proceed only after the TASKS-only tracker proof
  for this exact route exits `0`.
- Any later GO must prove a parity-preserving structural reduction of at least
  one selected marker with focused negative controls, no new host authority,
  passing host-semantics and host-authority ratchets, strict L4 structural
  contract compliance, and indicator collection.
- Any later NO-GO must leave runtime/substrate surfaces unchanged and record the
  next precise prerequisite instead of claiming false reduction.

## Grounding / Authorization

Parent packet route:

- `reports/control_plane/n3-stage0-match-substitute-host-semantics-reduction-2026-05-19_2026-05-19.md:103-108`
  classifies the parent outcome as a precise prerequisite route with no runtime
  code edits, no selected marker removal, and no host-semantics reduction claim.
- The parent classification table records every selected marker as
  `structurally-reducible-with-prerequisite`, not `removable-now`.

Parent same-wave tracker authority:

- `TASKS.md` carries the parent wave
  `n3-stage0-match-substitute-host-semantics-reduction-2026-05-19`; that
  authority remains parent authority only and does not authorize this successor
  implementation.

Successor control-surface token:

`FOUNDER_OVERRIDE:n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19`

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19`
- Active packet: `reports/control_plane/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.md`
  - `reports/l4_wave_indicators/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19`
- Active packet: `reports/control_plane/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `315802592264b07e1377380bba69b8fc20852f87ef2124d05f6bfe592b035225`
- Indicator artifact: `reports/l4_wave_indicators/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19 --output reports/l4_wave_indicators/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.md`
  - `reports/l4_wave_indicators/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
