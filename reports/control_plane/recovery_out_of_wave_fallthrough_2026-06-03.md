# Recovery Out Of Wave Fallthrough 2026-06-03

Date: 2026-06-03
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: recovery-out-of-wave-fallthrough-2026-06-03
Phase-A-Lock: LOCKED
Purpose: Fix recovery_gate so a GENUINE supervisor NEEDS_PHASE_B is no longer mislabeled as the out-of-wave-tasks tracker-note class and failed closed; when the out-of-wave-tracker auto-fix is a NO-OP, route to Phase B re-entry instead of stranding the wave. READ FIRST in mu/tools/executors/recovery_gate.py: `classify_failure`, `_looks_like_commit_supervisor_out_of_wave_tasks_tracker_note`, `fix_commit_supervisor_out_of_wave_tasks_tracker_note`, the FailureClass values `COMMIT_SUPERVISOR_OUT_OF_WAVE_TASKS_TRACKER_NOTE` / `NEEDS_PHASE_B` / `POST_REENTRY_NEEDS_PHASE_B`, and the recovery orchestration that maps a FailureClass to its fix function and decides recovered-vs-failed AND how a `NEEDS_PHASE_B` classification routes to a Phase B re-entry. BUG (observed 2026-06-03 on the check-test-theater-ast wave, recovery_status failure_class=commit_supervisor_out_of_wave_tasks_tracker_note, last_action=no_out_of_wave_tasks_tracker_addition, recovered=False): `classify_failure` evaluates `_looks_like_commit_supervisor_out_of_wave_tasks_tracker_note` (tier 2) BEFORE the genuine NEEDS_PHASE_B check (tier 3). That matcher fires on INCIDENTAL summarized-signal text -- it requires only that a commit-supervisor step, `needs_phase_b`, `tasks.md`, an out-of-scope marker, a tracker marker, and a staged marker all appear ANYWHERE in the combined signal (reason + classifier signal + candidate JSON), NOT that an out-of-wave tracker note is the DRIVING finding. When the real driving finding is a code defect (here a fail-open test-theater gate wrapper that the pre-commit meta-review correctly blocked), the matcher still fires; then `fix_commit_supervisor_out_of_wave_tasks_tracker_note` parses the staged TASKS.md diff, finds NO proven out-of-wave addition, and returns its no-op result `no_out_of_wave_tasks_tracker_addition` -> recovered=False -> tier2_failed -> the wave STRANDS, even though the supervisor's request_for_claude was literally 'Re-enter Phase B'. PRECISE, BOUNDED FIX: when the out-of-wave-tracker auto-fix is a NO-OP (no proven out-of-wave staged TASKS.md addition -- the `no_out_of_wave_tasks_tracker_addition` result), the recovery must ROUTE TO NEEDS_PHASE_B (Phase B re-entry) instead of terminating tier2_failed/recovered=False. Implement at the CLEANEST point, your choice between: (a) in `classify_failure`, when `_looks_like_commit_supervisor_out_of_wave_tasks_tracker_note` matches BUT the staged TASKS.md diff has no proven out-of-wave addition, classify `NEEDS_PHASE_B`; or (b) in the recovery orchestration, when `fix_commit_supervisor_out_of_wave_tasks_tracker_note` returns the `no_out_of_wave_tasks_tracker_addition` no-op, re-route to the NEEDS_PHASE_B / Phase-B-re-entry path. This must fix BOTH the genuine-defect case (a real meta finding -> Phase B re-entry surfaces it for the implementer) and the earlier false-positive case (no real finding -> a clean Phase B re-dispatch re-converges). KEEP the genuine out-of-wave-tracker auto-fix UNCHANGED: when there IS a proven out-of-wave staged TASKS.md addition, remove it exactly as today. Do NOT change the matcher's marker lists, `fix_post_reentry_needs_phase_b`, the FailureClass enum, or any other classification/fix. HARD SCOPE: ONLY mu/tools/executors/recovery_gate.py + a regression test added to the EXISTING mu/tests/tools/test_recovery_gate.py (do NOT create a new test file -- growth cap). L4_ENABLER: executor tooling only, no runtime/substrate dir. Cite code by function name only; NO file:line in the plan.

## Scope

One bounded recovery-gate fix (L4_ENABLER, no runtime dir): when recovery_gate's out-of-wave-tasks tracker-note auto-fix (`fix_commit_supervisor_out_of_wave_tasks_tracker_note`) is a NO-OP (`no_out_of_wave_tasks_tracker_addition` -- no proven out-of-wave staged TASKS.md addition), route the recovery to NEEDS_PHASE_B (Phase B re-entry) instead of terminating tier2_failed/recovered=False. ROOT: classify_failure checks `_looks_like_commit_supervisor_out_of_wave_tasks_tracker_note` (tier 2) before the genuine NEEDS_PHASE_B check (tier 3), and that matcher fires on INCIDENTAL signal text (needs_phase_b + tasks.md + out-of-scope + tracker + staged markers anywhere in the summarized signal) rather than on the DRIVING finding -- so a genuine NEEDS_PHASE_B with a real code defect (the fail-open test-theater wrapper, 2026-06-03) is captured into the tracker-note class, the auto-fix finds nothing, and the wave strands. #27 implemented the detection-scope-to-staged-diff half but not this fall-through. Fix handles BOTH the genuine-defect case (Phase B re-entry surfaces it) and the earlier false-positive case (clean re-converge). Genuine out-of-wave-tracker removals stay unchanged. Only recovery_gate.py + a regression test in the EXISTING test_recovery_gate.py. Validation gate: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py -k "classify or out_of_wave or needs_phase_b or tracker_note"`. Cite code by function name only; no file:line.

- `reports/deferred/non_blocking/recovery-out-of-wave-fallthrough-2026-06-03_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Concrete bounded tasks for this wave (from TASKS.md `[NEXT-CODEX-POST-REDTEAM]` and the 2026-06-03 tracker sync note for recovery-out-of-wave-fallthrough-2026-06-03):

1. In `recovery_gate.py`, make a NO-OP out-of-wave-tracker auto-fix route to NEEDS_PHASE_B (Phase B re-entry) instead of terminating tier2_failed/recovered=False. Implement at the CLEANEST single point (implementer's choice between):
   - (a) in `classify_failure`: when `_looks_like_commit_supervisor_out_of_wave_tasks_tracker_note` matches BUT the staged TASKS.md diff has no proven out-of-wave addition, classify `NEEDS_PHASE_B`; or
   - (b) in the recovery orchestration: when `fix_commit_supervisor_out_of_wave_tasks_tracker_note` returns the `no_out_of_wave_tasks_tracker_addition` no-op result, re-route to the NEEDS_PHASE_B / Phase-B-re-entry path.
2. Keep the genuine out-of-wave-tracker auto-fix UNCHANGED: when there IS a proven out-of-wave staged TASKS.md addition, `fix_commit_supervisor_out_of_wave_tasks_tracker_note` removes it exactly as today.
3. Add a regression test to the EXISTING `mu/tests/tools/test_recovery_gate.py` (no new file) covering both arms: (i) a genuine NEEDS_PHASE_B mis-captured by the incidental-text matcher with no proven staged out-of-wave addition routes to NEEDS_PHASE_B (not tier2_failed/recovered=False); (ii) a proven out-of-wave staged TASKS.md addition is still removed as before (no regression to the genuine path).

## Constraints

NOT in scope (do NOT touch):

- Any file other than `mu/tools/executors/recovery_gate.py` and `mu/tests/tools/test_recovery_gate.py`. HARD SCOPE: exactly these two files.
- The matcher's marker lists inside `_looks_like_commit_supervisor_out_of_wave_tasks_tracker_note`.
- `fix_post_reentry_needs_phase_b`, the `FailureClass` enum, and every other classification/fix function not named in Work items.
- No NEW test file (growth cap) -- the regression test goes into the existing `test_recovery_gate.py`.
- No runtime/substrate directory: this is L4_ENABLER executor tooling only.
- No file:line citations in this plan -- cite code by function name only.

## Stop conditions

- STOP after `recovery_gate.py` plus the regression test in `test_recovery_gate.py` are changed and the validation gate is green. Do NOT generalize to unrelated recovery classes.
- STOP and escalate if the fix would require editing any file outside the two in-scope files (scope breach).
- STOP if the fix would require changing the matcher marker lists, the `FailureClass` enum, or `fix_post_reentry_needs_phase_b` (forbidden surface) -- re-plan instead of widening.
- STOP if any runtime/substrate directory would be touched (L4_ENABLER violation).

## Acceptance criteria

- Validation gate passes: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py -k "classify or out_of_wave or needs_phase_b or tracker_note"`.
- A NO-OP out-of-wave-tracker auto-fix (`no_out_of_wave_tasks_tracker_addition`) routes to NEEDS_PHASE_B (Phase B re-entry): the genuine-defect case re-enters Phase B (surfacing the real finding for the implementer) and the earlier false-positive case re-converges cleanly -- neither strands at tier2_failed/recovered=False.
- Genuine out-of-wave-tracker removals (a proven out-of-wave staged TASKS.md addition) are unchanged.
- Regression test added to the existing `test_recovery_gate.py`; no new test file created; only the two in-scope files changed; no runtime/substrate dir touched.
- evidence_delta matches the 2026-06-03 TASKS.md tracker sync note for this wave.

## Grounding / Authorization

- TASKS.md task: `[NEXT-CODEX-POST-REDTEAM]` -- OPEN, UNPARKED (2026-03-28, founder-authorized); confirmed OPEN-by-code in the NEXT section's 2026-04-30 code-truth reconciliation. Tracked parent packet: `reports/control_plane/post_redteam_structural_queue_2026-03-20.md` (Sequence: Phase A -> B -> C -> D).
- Wave authorization (TASKS.md tracker sync note, 2026-06-03, recovery-out-of-wave-fallthrough-2026-06-03): Class L4_ENABLER; target_gate_id G8; primary_blocker_class INTEGRATION; primary_invariant_id INV_TYPED_FAIL_CLOSED_OUTCOMES; indicator_artifact_ref `reports/l4_wave_indicators/recovery-out-of-wave-fallthrough-2026-06-03.json`.
- Governing packet: this file (`reports/control_plane/recovery_out_of_wave_fallthrough_2026-06-03.md`).
- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py -k "classify or out_of_wave or needs_phase_b or tracker_note"`.
- indicator_collection_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id recovery-out-of-wave-fallthrough-2026-06-03 --output reports/l4_wave_indicators/recovery-out-of-wave-fallthrough-2026-06-03.json`.
- bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP; boot0_track_id: V1; boot0_progress_state: HOLD.
- Same-wave override for commit automation: FOUNDER_OVERRIDE:recovery-out-of-wave-fallthrough-2026-06-03
- Authorization: standing pipeline-bug-fix authorization (recovery_gate is executor pipeline tooling; founder standing auth for autonomous executor/pipeline bug fixes), bounded to wave recovery-out-of-wave-fallthrough-2026-06-03.

## Request from Post-Merge Supervisor

Fix recovery_gate so a GENUINE supervisor NEEDS_PHASE_B is no longer mislabeled as the out-of-wave-tasks tracker-note class and failed closed; when the out-of-wave-tracker auto-fix is a NO-OP, route to Phase B re-entry instead of stranding the wave. READ FIRST in mu/tools/executors/recovery_gate.py: `classify_failure`, `_looks_like_commit_supervisor_out_of_wave_tasks_tracker_note`, `fix_commit_supervisor_out_of_wave_tasks_tracker_note`, the FailureClass values `COMMIT_SUPERVISOR_OUT_OF_WAVE_TASKS_TRACKER_NOTE` / `NEEDS_PHASE_B` / `POST_REENTRY_NEEDS_PHASE_B`, and the recovery orchestration that maps a FailureClass to its fix function and decides recovered-vs-failed AND how a `NEEDS_PHASE_B` classification routes to a Phase B re-entry. BUG (observed 2026-06-03 on the check-test-theater-ast wave, recovery_status failure_class=commit_supervisor_out_of_wave_tasks_tracker_note, last_action=no_out_of_wave_tasks_tracker_addition, recovered=False): `classify_failure` evaluates `_looks_like_commit_supervisor_out_of_wave_tasks_tracker_note` (tier 2) BEFORE the genuine NEEDS_PHASE_B check (tier 3). That matcher fires on INCIDENTAL summarized-signal text -- it requires only that a commit-supervisor step, `needs_phase_b`, `tasks.md`, an out-of-scope marker, a tracker marker, and a staged marker all appear ANYWHERE in the combined signal (reason + classifier signal + candidate JSON), NOT that an out-of-wave tracker note is the DRIVING finding. When the real driving finding is a code defect (here a fail-open test-theater gate wrapper that the pre-commit meta-review correctly blocked), the matcher still fires; then `fix_commit_supervisor_out_of_wave_tasks_tracker_note` parses the staged TASKS.md diff, finds NO proven out-of-wave addition, and returns its no-op result `no_out_of_wave_tasks_tracker_addition` -> recovered=False -> tier2_failed -> the wave STRANDS, even though the supervisor's request_for_claude was literally 'Re-enter Phase B'. PRECISE, BOUNDED FIX: when the out-of-wave-tracker auto-fix is a NO-OP (no proven out-of-wave staged TASKS.md addition -- the `no_out_of_wave_tasks_tracker_addition` result), the recovery must ROUTE TO NEEDS_PHASE_B (Phase B re-entry) instead of terminating tier2_failed/recovered=False. Implement at the CLEANEST point, your choice between: (a) in `classify_failure`, when `_looks_like_commit_supervisor_out_of_wave_tasks_tracker_note` matches BUT the staged TASKS.md diff has no proven out-of-wave addition, classify `NEEDS_PHASE_B`; or (b) in the recovery orchestration, when `fix_commit_supervisor_out_of_wave_tasks_tracker_note` returns the `no_out_of_wave_tasks_tracker_addition` no-op, re-route to the NEEDS_PHASE_B / Phase-B-re-entry path. This must fix BOTH the genuine-defect case (a real meta finding -> Phase B re-entry surfaces it for the implementer) and the earlier false-positive case (no real finding -> a clean Phase B re-dispatch re-converges). KEEP the genuine out-of-wave-tracker auto-fix UNCHANGED: when there IS a proven out-of-wave staged TASKS.md addition, remove it exactly as today. Do NOT change the matcher's marker lists, `fix_post_reentry_needs_phase_b`, the FailureClass enum, or any other classification/fix. HARD SCOPE: ONLY mu/tools/executors/recovery_gate.py + a regression test added to the EXISTING mu/tests/tools/test_recovery_gate.py (do NOT create a new test file -- growth cap). L4_ENABLER: executor tooling only, no runtime/substrate dir. Cite code by function name only; NO file:line in the plan.

Routed next-candidate:
recovery-out-of-wave-fallthrough-2026-06-03

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `recovery-out-of-wave-fallthrough-2026-06-03`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/recovery-out-of-wave-fallthrough-2026-06-03_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `recovery-out-of-wave-fallthrough-2026-06-03`
- Active packet: `reports/control_plane/recovery_out_of_wave_fallthrough_2026-06-03.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `8ca2252d45f977ac299489c28b854aabe2ae1fce038e480a626d1518edad20f4`
- Indicator artifact: `reports/l4_wave_indicators/recovery-out-of-wave-fallthrough-2026-06-03.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/recovery_out_of_wave_fallthrough_2026-06-03.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/recovery-out-of-wave-fallthrough-2026-06-03.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/recovery_out_of_wave_fallthrough_2026-06-03.md`
  - `reports/deferred/non_blocking/recovery-out-of-wave-fallthrough-2026-06-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/recovery-out-of-wave-fallthrough-2026-06-03.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
