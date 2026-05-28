# N3-Stage0-Marker-Truth-Current-Path-Sync-2026-05-28

Date: 2026-05-28
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Class: L4_ENABLER
Category: /mu Stage0 marker-truth / source-lock correction
Target gate: G8
Wave ID: n3-stage0-marker-truth-current-path-sync-2026-05-28
Phase-A-Lock: LOCKED
FOUNDER_OVERRIDE:n3-stage0-marker-truth-current-path-sync-2026-05-28

Purpose: build the bounded Phase A plan for correcting stale Stage0 marker and
source-lock truth after the `step_kernel_mu` VM cutover. The wave must preserve
host-semantics marker counts unless current implementation truly eliminates the
engine/bootstrap host path. Expected host semantics delta is 0.

## Scope

In scope for this packet and its follow-on implementation wave:

- `reports/control_plane/n3-stage0-marker-truth-current-path-sync-2026-05-28_2026-05-28.md`
  as the governing same-wave Phase A packet.
- `TASKS.md` only for a detector-visible same-wave tracker entry or tracker
  sync tied to `[NEXT-CODEX-POST-REDTEAM]` and this wave id.
- `mu/host/python/rcx_pi/selfhost/eval_seed.py` comment, source-lock, and
  marker wording around `_stage0_match`; behavior is not in scope unless
  current code truth directly contradicts the reviewer evidence.
- Focused existing L4 gate/source-lock tests under `mu/tests/l4_gates/` needed
  to prove the two current-path facts: `step_kernel_mu` cutover does not call
  `_stage0_match`, while `run_engine_pipeline` still reaches `_stage0_match`
  through the engine/bootstrap trusted path.
- Existing Stage0 VM cutover coverage in
  `mu/tests/l4_gates/test_stage0_vm_cutover.py` as read-only grounding unless a
  focused assertion must be strengthened in place.
- `reports/l4_wave_indicators/n3-stage0-marker-truth-current-path-sync-2026-05-28.json`
  only as the same-wave generated indicator artifact if implementation lands.
- Any same-wave generated bridge nonblocker for this wave only, if the pipeline
  creates one.
- `mu/tools/executors/phase_b_executor.py` and
  `mu/tests/tools/test_phase_b_executor.py` only for a same-wave mechanical
  pipeline recovery if Phase B reclassifies this locked `L4_ENABLER` runtime
  text/source-lock packet as `L4_STRUCTURAL` before pre-commit packaging.

- `reports/deferred/non_blocking/n3-stage0-marker-truth-current-path-sync-2026-05-28_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Replace stale `eval_seed.py` wording that treats `_stage0_match` as the sole
   production Stage0 path. The corrected wording must distinguish the
   `step_kernel_mu` Stage0 VM cutover path from the remaining engine/bootstrap
   trusted-helper path.
2. Preserve `_stage0_match` as a host-builtin marker while
   `_apply_projection_trusted` / `_step_trusted` and `run_engine_pipeline` still
   call through it. Do not reduce host-semantics ratchet counts for this wave.
3. Add or strengthen focused L4 gate coverage proving both facts in one bounded
   evidence surface:
   - `step_kernel_mu` cutover does not call `_stage0_match`,
     `_step_trusted`, or `_apply_projection_trusted`.
   - `run_engine_pipeline` still reaches `_stage0_match` through the current
     engine/bootstrap trusted path.
4. Update only source-lock or marker-truth test expectations that encode the
   stale "sole production path" claim. Keep the change as wording/proof-class
   alignment, not runtime behavior change.
5. Add the same-wave `TASKS.md` tracker sync before implementation closeout so
   the founder-ordered queue invariant remains detector-visible: every wave
   needs a control-plane packet plus a tracker entry.
6. Collect the same-wave L4 indicator only if Phase B implementation lands.
7. Resolve only same-wave generated bridge nonblockers, if any are created by
   this packet's pipeline path.
8. If the pipeline itself regenerates contradictory wave-class metadata for this
   packet, repair the Phase B class-preservation path with focused regression
   coverage before commit handoff.

## Constraints

- Do not use `run_review.py`.
- Do not perform baseline edits, marker-only deletion, or broad N3 closure.
- Do not remove `@host_builtin` from `_stage0_match` unless current
  implementation evidence proves the engine/bootstrap trusted path no longer
  uses it.
- Do not reduce host-semantics ratchet counts unless implementation actually
  eliminates the engine/bootstrap host path. Expected host semantics delta is 0.
- Do not change Stage0 VM, `step_kernel_mu`, `run_engine_pipeline`,
  `_step_trusted`, `_apply_projection_trusted`, scheduler, seed, registry,
  loader, binary/checksum/integrity, JS parity, dispatcher, commit, push, PR, or
  Claude surfaces from this wave.
- Recovery exception: a narrowly scoped Phase B executor/test change is allowed
  only to prevent this locked `L4_ENABLER` comment/source-lock runtime-text
  packet from being repackaged as `L4_STRUCTURAL`; it must not alter dispatcher,
  commit, push, PR, or runtime semantics.
- Do not inspect or modify unrelated dirty files, broad executor/test changes,
  or unrelated implementation while this packet is being repaired.
- Prefer current code truth over stale packet wording in Phase B. If focused
  evidence proves a listed work item has already landed, remove it from pending
  work and acceptance criteria instead of relisting it as unresolved.

## Stop conditions

Stop and return for a new packet or rewritten Phase A scope if any condition
fires:

1. The proposed change requires baseline movement, marker-only deletion, or
   broad N3 closure.
2. Focused code evidence proves `step_kernel_mu` still calls `_stage0_match`;
   that contradicts the governing premise and requires a different defect
   packet.
3. Focused code evidence proves `run_engine_pipeline` no longer reaches
   `_stage0_match`; the marker and ratchet expectation must be re-scoped before
   any host-builtin removal.
4. The change requires runtime behavior edits in Stage0 VM, engine pipeline,
   scheduler, seed/registry, loader, binary/checksum/integrity, or JS parity
   code.
5. The wave cannot add a detector-visible same-wave `TASKS.md` tracker sync
   before implementation closeout.
6. Pipeline execution generates bridge findings outside this same wave's
   packet, tracker, indicator, or focused L4 gate scope.

## Acceptance criteria

This Phase A packet is acceptable when:

1. It contains the required sections: Scope, Work items, Constraints, Stop
   Conditions, Acceptance Criteria, and Grounding / Authorization.
2. It is locked with `Phase-A-Lock: LOCKED` and carries the wave-bound token
   `FOUNDER_OVERRIDE:n3-stage0-marker-truth-current-path-sync-2026-05-28`.
3. It grounds the wave in `[NEXT-CODEX-POST-REDTEAM]`, the active governing
   queue packet, and the reviewer-supplied current-path evidence.

The follow-on implementation is acceptable only when:

1. `_stage0_match` wording no longer claims sole production-path authority for
   `step_kernel_mu`; it instead describes the remaining engine/bootstrap
   trusted-helper path accurately.
2. `_stage0_match` remains marked as host-builtin while the
   engine/bootstrap path still calls it.
3. Focused L4 evidence proves both path facts: `step_kernel_mu` cutover has zero
   `_stage0_match` calls, and `run_engine_pipeline` still has positive
   `_stage0_match` reachability through `_step_trusted`.
4. Existing Stage0 VM cutover proof remains intact; the wave does not weaken the
   current evidence that `_step_trusted` and `_apply_projection_trusted` do not
   fire on the `step_kernel_mu` cutover path.
5. Host-semantics ratchet output has no count reduction or increase from this
   wording/proof-class correction.
6. `TASKS.md` carries a same-wave tracker sync for this packet before
   implementation closeout.
7. The same-wave indicator artifact is collected if implementation lands, and
   any same-wave generated bridge nonblocker is handled without widening scope.
8. If the recovery exception is used, focused Phase B executor regressions prove
   the locked `L4_ENABLER` runtime text/source-lock packet shape remains
   `L4_ENABLER` and emits `no_op_proof` before supervisor packaging.

## Grounding / Authorization

TASKS.md: lines 650-658 authorize `[NEXT-CODEX-POST-REDTEAM]` as the
founder-authorized open queue, require Phase A through Phase D sequencing, and
state that every wave requires both a control-plane packet and a `TASKS.md`
tracker entry.

post_redteam_structural_queue_2026-03-20: the governing queue packet is
`reports/control_plane/post_redteam_structural_queue_2026-03-20.md`; it keeps
the post-red-team structural queue open only for separate bounded packets not
already proven by landed work.

- Authorization: `TASKS.md:650` records `[NEXT-CODEX-POST-REDTEAM]` as
  UNPARKED and founder-authorized.
- Authorization: `TASKS.md:651` names
  `reports/control_plane/post_redteam_structural_queue_2026-03-20.md` as the
  tracked packet for the current queue.
- Authorization: `TASKS.md:652-653` keeps the sequence open at Phase A for
  separate bounded packets after already-landed work.
- Authorization: `TASKS.md:658` requires every wave to have a control-plane
  packet plus `TASKS.md` tracker entry and authorizes dispatcher/pipeline
  progression for the founder-ordered red-team wave queue.
- Same-wave authorization token:
  `FOUNDER_OVERRIDE:n3-stage0-marker-truth-current-path-sync-2026-05-28`.
- Governing packet reference:
  `reports/control_plane/post_redteam_structural_queue_2026-03-20.md` records
  the active queue controller, the requirement that future structural work use
  separate bounded packets, and the packet/tracker discipline for the open
  queue.
- Same-wave governing packet:
  `reports/control_plane/n3-stage0-marker-truth-current-path-sync-2026-05-28_2026-05-28.md`.
- Reviewer evidence treated as authoritative for this Phase A rewrite:
  `step_mu.py` lines 1052 and 2230-2235 show `step_kernel_mu` cutover uses
  `_step_kernel_with_vm` / Stage0 VM; `test_stage0_vm_cutover.py` lines 392-430
  prove `_step_trusted` / `_apply_projection_trusted` do not fire on the
  `step_kernel_mu` cutover path; `eval_seed.py` lines 524-529 currently marks
  `_stage0_match` as `@host_builtin` and says sole production path;
  `eval_seed.py` lines 870 and 899-902 show `_apply_projection_trusted` /
  `_step_trusted` still call `_stage0_match`; `engine_pipeline.py` lines 1094
  and 1330 call `_step_trusted`; the diagnostic monkeypatch run reported
  `step_kernel_mu_result b`, `stage0_match_calls_after_step_kernel_mu 0`,
  `run_engine_pipeline_status RcxEngineError`, and
  `stage0_match_calls_after_run_engine_pipeline 24`.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-stage0-marker-truth-current-path-sync-2026-05-28`
- Active packet: `reports/control_plane/n3-stage0-marker-truth-current-path-sync-2026-05-28_2026-05-28.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-stage0-marker-truth-current-path-sync-2026-05-28.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/python/rcx_pi/selfhost/eval_seed.py`
  - `mu/tests/l4_gates/test_stage0_vm_cutover.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/n3-stage0-marker-truth-current-path-sync-2026-05-28_2026-05-28.md`
  - `reports/deferred/non_blocking/n3-stage0-marker-truth-current-path-sync-2026-05-28_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/n3-stage0-marker-truth-current-path-sync-2026-05-28_decorator-metadata-followup.md`
  - `reports/l4_wave_indicators/n3-stage0-marker-truth-current-path-sync-2026-05-28.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `n3-stage0-marker-truth-current-path-sync-2026-05-28`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/n3-stage0-marker-truth-current-path-sync-2026-05-28_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-stage0-marker-truth-current-path-sync-2026-05-28`
- Active packet: `reports/control_plane/n3-stage0-marker-truth-current-path-sync-2026-05-28_2026-05-28.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `0542229e82069c0ed0598d48b9de094781f05770eff1ce7ecafb9e59b206dec5`
- Indicator artifact: `reports/l4_wave_indicators/n3-stage0-marker-truth-current-path-sync-2026-05-28.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_stage0_vm_cutover.py mu/tests/tools/test_phase_b_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-stage0-marker-truth-current-path-sync-2026-05-28_2026-05-28.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-stage0-marker-truth-current-path-sync-2026-05-28.json`
- Current staged files:
  - `TASKS.md`
  - `mu/host/python/rcx_pi/selfhost/eval_seed.py`
  - `mu/tests/l4_gates/test_stage0_vm_cutover.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/n3-stage0-marker-truth-current-path-sync-2026-05-28_2026-05-28.md`
  - `reports/deferred/non_blocking/n3-stage0-marker-truth-current-path-sync-2026-05-28_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/n3-stage0-marker-truth-current-path-sync-2026-05-28_decorator-metadata-followup.md`
  - `reports/l4_wave_indicators/n3-stage0-marker-truth-current-path-sync-2026-05-28.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
