# Recovery Hybrid Support-State Drift 2026-06-30

Date: 2026-06-30
Status: READY FOR STANDALONE COMMIT EXECUTOR
Task: [PIPELINE-RECOVERY]
Wave ID: recovery-hybrid-support-state-drift-2026-06-30
Class: L4_ENABLER
Lane: control-surface pipeline/recovery hardening
Authorization: standing pipeline-bug-fix authorization
Target gate: G8
Unblocks wave id: nightly-nr2-recurrence-numeral-2026-06-30
Unblocks runtime blocker: NR-2 commit pre-push recovery exhausted after support-state content churn in `.agent_bus*/bridge_config.json` and `.agent_bus*/recovery/learned_patterns.json`, then live pager receiver churn in `.agent_bus*/observability/claude_pager_receiver/active_drainer.json`.

## Scope

Repair the hybrid recovery gate so live repo-local support-state content churn
and exact pager receiver runtime-state churn do not cause valid bounded
recovery delegates to exhaust, while preserving fail-closed behavior for
support-state creation/deletion/type/readlink drift, git-control drift,
undeclared source edits, shape drift, and symlink escapes.

## Files

- `mu/tools/executors/recovery_gate.py`
- `mu/tests/tools/test_recovery_gate.py`
- `TASKS.md`
- `reports/l4_wave_indicators/recovery-hybrid-support-state-drift-2026-06-30.json`
- `reports/control_plane/recovery-hybrid-support-state-drift-2026-06-30_2026-06-30.md`

## Evidence

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py --tb=short
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py -k 'support_state or pager_receiver' --tb=short
python3 tools/checks/enforce_l4_execution_contract.py --files TASKS.md mu/tools/executors/recovery_gate.py mu/tests/tools/test_recovery_gate.py reports/control_plane/recovery-hybrid-support-state-drift-2026-06-30_2026-06-30.md reports/l4_wave_indicators/recovery-hybrid-support-state-drift-2026-06-30.json --wave-id recovery-hybrid-support-state-drift-2026-06-30 --wave-class L4_ENABLER
git diff --check -- TASKS.md mu/tools/executors/recovery_gate.py mu/tests/tools/test_recovery_gate.py reports/control_plane/recovery-hybrid-support-state-drift-2026-06-30_2026-06-30.md reports/l4_wave_indicators/recovery-hybrid-support-state-drift-2026-06-30.json
```

## Guardrails

- Do not modify product runtime semantics in this repair wave.
- Do not weaken hybrid recovery inventory drift checks.
- Do not admit broad `.agent_bus` churn; keep the pager receiver allowance exact.
- Do not route implementation, review, pager, commit, or receipt handling to Claude.

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/recovery-hybrid-support-state-drift-2026-06-30.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id recovery-hybrid-support-state-drift-2026-06-30 --output reports/l4_wave_indicators/recovery-hybrid-support-state-drift-2026-06-30.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- `evidence_delta`: (1) Routed commit handoff scopes 5 wave-owned file(s). (2) Evidence gate exercises 1 wave-owned test module(s). (3) Indicator artifact binds the wave to reports/l4_wave_indicators/recovery-hybrid-support-state-drift-2026-06-30.json..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: recovery-hybrid-support-state-drift-2026-06-30 (standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md; auto-appended by build_commit_handoff for commit-gate + pre-push adjacency-cap clearance)
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `recovery-hybrid-support-state-drift-2026-06-30`
- Active packet: `reports/control_plane/recovery-hybrid-support-state-drift-2026-06-30_2026-06-30.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `effb3b6da19df6a600006b74fa728284b284605981f278f436a607b9201799a1`
- Indicator artifact: `reports/l4_wave_indicators/recovery-hybrid-support-state-drift-2026-06-30.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Routed commit handoff scopes 5 wave-owned file(s). (2) Evidence gate exercises 1 wave-owned test module(s). (3) Indicator artifact binds the wave to reports/l4_wave_indicators/recovery-hybrid-support-state-drift-2026-06-30.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/recovery-hybrid-support-state-drift-2026-06-30.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/recovery-hybrid-support-state-drift-2026-06-30_2026-06-30.md`
  - `reports/l4_wave_indicators/recovery-hybrid-support-state-drift-2026-06-30.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
