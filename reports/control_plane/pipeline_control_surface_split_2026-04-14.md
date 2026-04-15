# Pipeline Control-Surface Split

Date: 2026-04-14
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [PIPELINE-RECOVERY]
Phase-A-Lock: LOCKED
Phase: B
Wave class: MAINTENANCE
Target gate: G8
Governing packet: This file

## Grounding / Authorization

This packet isolates the control-surface fixes that were incorrectly mixed into
the staged `[CODEX-STARTUP-HARDENING]` candidate.

Grounding sources:

1. `TASKS.md` active item `[PIPELINE-RECOVERY]`
2. Bridge review job `phase-b-r1-c1b15434`, which returned `NO_GO` on the
   mixed startup candidate
3. Live staged control-surface files already present in the dirty worktree

The blocking defects from that bridge review are controlling for this split:

1. `mu/tools/executors/executor_dispatch.py` was refreshing stale explicit
   routing records by mutating `state_sha` / `head_sha` in place instead of
   failing closed or recomputing authoritative routing.
2. `TASKS.md` and adjacent control-plane prompt surfaces still leaked the stale
   root packet path `reports/control_plane/meta_bridge_rollout_2026-03-20.md`
   into meta-review prompts.
3. The startup packet no longer matched the staged candidate because the stage
   also contained control-surface files outside startup-hardening scope.

## Consecutive Maintenance Bypass

This MAINTENANCE split is the bounded control-surface pass required before the
separate startup-hardening follow-up can rerun honestly. For tracker-note
generation and `enforce_l4_execution_contract.py`, the intended bypass linkage
is:

- `unblocks_wave_id: wave-codex-startup-hardening-2026-04-14`
- `unblocks_runtime_blocker: INV_STRUCTURAL_FORWARD_MOTION`

## Scope

This wave is limited to the control-surface files required to resolve those
blocking defects and commit the already-discovered pipeline/bridge fixes as a
separate honest unit:

1. tracker / packet truth:
   - `TASKS.md`
   - `reports/control_plane/README.md`
   - `reports/control_plane/pipeline_control_surface_split_2026-04-14.md`
2. prompt / control-plane truth surfaces:
   - `mu/tools/agents/templates/meta_bridge_task.txt`
   - `mu/tools/executors/dialectic_executor.py`
3. stale explicit routing handling:
   - `mu/tools/executors/executor_dispatch.py`
   - `mu/tests/tools/test_executor_dispatch.py`
4. tracked-packet routing / bridge convergence support already in the dirty
   control-surface bundle:
   - `mu/tools/executors/phase_b_executor.py`
   - `mu/tests/tools/test_phase_b_executor.py`
5. bridge adapter linger hardening:
   - `mu/tools/agents/bridge_adapters.py`
   - `mu/tests/tools/test_agent_bridge_supervisor.py`
6. control-plane truth tests:
   - `mu/tests/tools/test_meta_bridge_supervisor.py`
   - `mu/tests/docs/test_status_tasks_consistency.py`
7. commit-handoff / recovery repair:
   - `mu/tools/executors/commit_executor.py`
   - `mu/tools/executors/recovery_gate.py`
   - `mu/tests/tools/test_recovery_gate.py`
8. L4 checker / governance truth:
   - `mu/tools/checks/enforce_l4_execution_contract.py`
   - `mu/tests/tools/test_l4_execution_contract_enforcement.py`
9. recovery observability truth:
   - `mu/tools/observability/pipeline_dashboard.py`

## Work Items

**A. Explicit routing fail-closed**

- Stale noncanonical explicit routing records must NOT be refreshed in place.
- Stale inline routing records must auto-refresh only when they still match the
  canonical routing file; caller-owned inline records must fail closed.
- The dispatcher must return a stale/fail-closed result that tells the caller
  to regenerate authoritative routing.
- The dispatcher test must prove the record file is left untouched and that no
  executor is launched on the stale caller-owned payload.

**B. Archived control-plane path truth**

- All live prompt / tracker / README surfaces in this wave must reference the
  archived `meta_bridge_rollout_2026-03-20.md` path, not the stale root path.
- The tests must prove the prompt and README surfaces no longer advertise the
  missing root packet path.

**C. Bridge linger hardening**

- Preserve the buffered raw-transcript fallback fix in `bridge_adapters.py`
  together with its regression test, so a complete envelope in the raw
  transcript can terminate a lingering adapter subprocess tree promptly.

**D. Tracked-packet Phase B authority**

- Keep the routed tracked-packet support already in the dirty control-surface
  bundle together with its tests, so Phase B uses the packet-owned routing/task
  authority instead of falling back to stale canonical routing.

**E. Commit-handoff / recovery contract truth**

- Phase B must emit a contract-complete `MAINTENANCE` tracker note when the
  routed wave class is `MAINTENANCE`; it must not silently coerce the note body
  to `L4_ENABLER`.
- The commit executor must surface the actionable tail of `pre-commit-doc-check`
  output even when the hook writes noisy stdout and no stderr.
- The recovery gate must classify the resulting tracker-note marker mismatch as
  a deterministic repair path, rebuild the canonical Phase B handoff note, and
  retry the commit surface without relying on a human.
- Tier 3 recovery must route through the configured bridge-backed agent backend
  already used by the control-plane, not a hardcoded `claude --print` path.
- Recovery observability must describe the actor generically as the recovery
  agent so the operator surfaces stop leaking stale Claude-only truth.
- The L4 tracker-note parser must evaluate the newest appended tracker notes,
  not the oldest historical notes, before enforcing the consecutive
  `MAINTENANCE` cap.
- Recovery classifier signal extraction must anchor on the terminal structured
  commit error instead of Codex JSONL stream chatter, so a `run_pre_push_script`
  failure cannot be mislabeled as `mixed_staging`.

## Constraints

1. Do not include the startup-hardening docs, startup-state audit, founder guard
   integration, tmux/web observability enforcement, or the startup packet
   itself in this wave.
2. Do not widen into parallel-pipeline or unrelated deferred cleanup beyond the
   narrow commit-handoff / recovery / observability repair required to keep
   this split wave routable.
3. Keep this wave commit-ready on its own so the startup-hardening packet can
   be rerun afterward against a clean stage.

## Stop Conditions

1. Stale explicit noncanonical routing records fail closed and are not mutated
   in place.
2. Archived control-plane packet paths are the only live packet references in
   the scoped tracker/prompt/README surfaces.
3. The buffered bridge adapter keeps the raw-transcript envelope fallback and
   its regression proof.
4. The routed Phase B tracked-packet fixes stay bundled with their tests as a
   separate control-surface wave.
5. The startup-hardening packet is no longer required to carry these
   control-surface files in its stage.
6. A Phase B `MAINTENANCE` handoff produces a valid tracker note that the
   commit executor accepts without manual repair.
7. Tier 3 recovery uses the configured control-plane backend instead of a
   hardcoded Claude path, and deterministic tracker-note mismatch repair is
   available before the loop falls back to generic LLM diagnosis.
8. The L4 `MAINTENANCE` cadence check reads current tracker history
   newest-first.
9. Recovery fingerprints and mixed-staging classification reflect the terminal
   commit failure, not adapter-stream noise.

## Acceptance Criteria

1. `mu/tests/tools/test_executor_dispatch.py` proves stale explicit routing
   records fail closed without rewriting the record, and that stale inline
   records only auto-refresh when they still match canonical routing truth.
2. `mu/tests/tools/test_meta_bridge_supervisor.py` proves the prompt uses
   `reports/control_plane/archive/meta_bridge_rollout_2026-03-20.md`.
3. `mu/tests/docs/test_status_tasks_consistency.py` proves
   `reports/control_plane/README.md` references existing canonical packet paths.
4. `mu/tests/tools/test_agent_bridge_supervisor.py` keeps the buffered
   raw-transcript envelope fallback regression green.
5. `mu/tests/tools/test_phase_b_executor.py` proves a `MAINTENANCE` Phase B
   handoff emits `no_op_proof:` / `defer_reason_code:` and rejects runtime
   paths.
6. `mu/tests/tools/test_recovery_gate.py` proves tracker-note contract drift is
   classified deterministically, repaired from the Phase B handoff, and that
   Tier 3 recovery no longer exposes a Claude-only waiting state.
7. `mu/tests/tools/test_l4_execution_contract_enforcement.py` proves appended
   tracker notes are parsed newest-first before cadence checks inspect
   `notes[0]`.
8. `mu/tests/tools/test_recovery_gate.py` proves noisy Codex JSONL preceding a
   `run_pre_push_script` failure still fingerprints and classifies the real
   pre-push error instead of collapsing to `mixed_staging`.
9. `mu/tests/tools/test_executor_dispatch.py` proves Step 8 still surfaces the
   real `pre-commit-doc-check` stdout failure when stderr is empty.