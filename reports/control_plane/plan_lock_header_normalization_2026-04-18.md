# Phase A Plan: plan-lock-header-normalization-2026-04-18

wave_id: plan-lock-header-normalization-2026-04-18
Task: [PIPELINE-AGENT-PAGER]
Phase-A-Lock: UNLOCKED
Governing packet: reports/control_plane/pipeline_agent_pager_2026-04-16.md
Tracked packet entry: TASKS.md:194-200

## Status

Phase A Rev 1. Narrow pipeline-hardening fix blocking Wave K-1 (pager-ping-delivery-2026-04-18): packets with duplicate `Phase-A-Lock:` header lines (e.g. line-1 PLACEHOLDER stub + line-6 implementer-added LOCKED) cause Phase B `validate_inputs` to fail because `load_plan_packet` returns the first-match value (PLACEHOLDER) even though a LOCKED line exists. Fix: `load_plan_packet` resolves `phase_a_lock` by preferring `LOCKED` when multiple `Phase-A-Lock:` values are present. Single-line and canonical plans unaffected.

## 1. Scope

Files in scope:
- `mu/tools/executors/phase_b_executor.py` (`load_plan_packet` only)
- `mu/tests/tools/test_phase_b_executor.py` (three new regression tests in `TestLoadPlanPacketPathTraversal`)

## 2. Work items

1. `load_plan_packet` at `mu/tools/executors/phase_b_executor.py:927`: replace the first-match `if clean.startswith("Phase-A-Lock:") and "phase_a_lock" not in result` guard with a `phase_a_lock_values: list[str]` accumulator. After the parsing loop, resolve preference: if any value equals `LOCKED`, use `LOCKED`; else if any equals `ROUTING_RECORD_AUTHORITY`, use that; else use the first value. Other field extractions (`status`, `task_id`, `founder_override`, `unblocks_*`) retain existing first-match semantics.
2. Three new regression tests in `TestLoadPlanPacketPathTraversal` in `mu/tests/tools/test_phase_b_executor.py`:
   - `test_duplicate_phase_a_lock_prefers_locked`: PLACEHOLDER + LOCKED → resolves LOCKED
   - `test_duplicate_phase_a_lock_prefers_routing_record_authority`: PLACEHOLDER + ROUTING_RECORD_AUTHORITY → resolves ROUTING_RECORD_AUTHORITY
   - `test_single_non_canonical_phase_a_lock_preserved`: single PLACEHOLDER (no LOCKED present) → preserved as PLACEHOLDER (first-match fallback)

## 3. Constraints (NOT in scope)

No change to `phase_a_executor.lock_plan()` (its PLACEHOLDER handling is a separate follow-up). No change to `validate_inputs` semantics (still rejects non-LOCKED/non-ROUTING values). No change to runtime dirs (`mu/host/python/rcx_pi/selfhost/`). No other `phase_b_executor` functions touched. No other test classes modified.

## 4. Stop conditions

STOP if root cause implicates any file outside §1.

## 5. Acceptance criteria

`PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py::TestLoadPlanPacketPathTraversal` exits 0 on the post-fix tree with 11 passed (8 existing + 3 new). Existing test `test_header_metadata_wins_over_later_narrative_bullets` (which relies on header-LOCKED winning over body-bullet-UNLOCKED) continues to pass unchanged.

## 6. Grounding / Authorization

TASKS.md:194-200 authorizes `[PIPELINE-AGENT-PAGER]` (QUEUED 2026-04-16, founder-directed post-merge follow-up) with `FOUNDER_OVERRIDE:pipeline-agent-pager-2026-04-17-followup` for the pager-slice family. This wave is a pager-slice prerequisite: it unblocks the K-1 pager-ping-delivery wave whose plan packet carries the PLACEHOLDER + LOCKED duplicate header state.

Class: L4_ENABLER. The fix enables Phase B to proceed on packets with the observed duplicate-header state without changing runtime semantics.
target_gate_id: G8.
evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py::TestLoadPlanPacketPathTraversal`.
evidence_delta: 3 new regression tests covering the prefer-LOCKED, prefer-ROUTING_RECORD_AUTHORITY, and single-non-canonical-preserved code paths introduced by the fix.
primary_blocker_class: INTEGRATION.
primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION.
indicator_artifact_ref: reports/l4_wave_indicators/plan-lock-header-normalization-2026-04-18.json.
indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id plan-lock-header-normalization-2026-04-18 --output reports/l4_wave_indicators/plan-lock-header-normalization-2026-04-18.json.
bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
boot0_track_id: V1.
boot0_progress_state: HOLD.
FOUNDER_OVERRIDE:pipeline-agent-pager-2026-04-17-followup.
