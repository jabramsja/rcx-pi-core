# Wave Packet: enable-pager-and-hybrid-recovery-2026-04-17

## Status: Phase B (locked, implementing)

## Goal

Flip four gated-off pipeline controls in a single MAINTENANCE wave:

1. `pipeline_agent_pager.enabled`: `false` → `true` (keeps `route: notify-only`
   for safe initial exposure — events log to `.agent_bus/observability/*.jsonl`,
   no external Codex/Claude dispatch yet).
2. `hybrid_recovery_enabled`: `false` → `true` (allows Tier 3 recovery to invoke
   the `delegate_implementer` hybrid path via bridge-backed phase_b_implementer
   when a recovery agent proposes that action; previously short-circuited at
   `recovery_gate.py:2950-2956`).
3. `backends.phase_a_executor`, `backends.phase_b_executor`,
   `backends.bot_remediation`: `codex` → `claude` (implementer roles move to
   Claude Opus 4.7 max-effort; non-implementer backends `post_merge_supervisor`
   + `dialectic_executor` stay on codex gpt-5.5 xhigh; `bridge_reviewers.phase_a`
   + `bridge_reviewers.phase_b` stay on codex gpt-5.5 xhigh).
4. `mu/tools/agents/bridge_config.example.json` claude adapter template: updated
   to explicit `--model claude-opus-4-7 --effort max --verbose --output-format
   stream-json --max-turns 50`, `timeout_s: 900`. Replaces the minimal
   `claude --print --dangerously-skip-permissions` template so fresh worktrees
   auto-heal with the explicit model+effort specification the live
   `.agent_bus/bridge_config.json` has been using.

Pager (PR #781) and hybrid recovery (PR #778) are code-landed with test coverage
(`mu/tests/tools/test_pipeline_agent_pager.py`, hybrid tests in
`mu/tests/tools/test_recovery_gate.py`). This wave only flips enablement flags +
routes implementer backends to Claude + explicit-ifies the bridge_config
template.

## Scope

Control-surface / config only. 2 file edits + 1 wave packet.

**Files (3 total):**

- `mu/tools/executors/executor_config.json` — flips `hybrid_recovery_enabled`,
  `pipeline_agent_pager.enabled`, and three `backends.*` entries. No other
  fields changed.
- `mu/tools/agents/bridge_config.example.json` — claude adapter cmd updated to
  explicit model + effort + verbose + stream-json + max-turns; timeout_s
  adjusted to 900.
- `reports/control_plane/enable_pager_and_hybrid_recovery_2026-04-17.md` —
  this packet.

**Files NOT touched:** any `mu/host/**`, `rcx_pi/selfhost/**`, kernel, projection,
seed, runtime, or any `*.py` / `*.js` / `*.sh` source file. No test file changes
either — existing coverage is sufficient to gate the flag flips.

## L4 Contract Fields

- **Class:** MAINTENANCE
- **Target gate:** G8 (indirect — enables observability + recovery + Claude
  implementer ergonomics for future waves)
- **Primary blocker class:** INTEGRATION
- **Primary invariant:** INV_STRUCTURAL_FORWARD_MOTION
- **No-op proof:** 2 boolean field flips + 3 string field flips in
  `executor_config.json`, plus adapter cmd + timeout adjustments in
  `bridge_config.example.json`. No source-code path, no test path, no runtime
  path, no projection path. Existing test suites cover the `enabled=true`
  path for pager (`test_pipeline_agent_pager.py`) and the
  `hybrid_recovery_enabled=true` branches for hybrid recovery
  (`test_recovery_gate.py`). Adapter spec changes are reflected only in the
  tracked template and live runtime config which are both ingested by
  `bridge_adapters.load_bridge_config`.
- **Defer reason code:** POST_WAVE_CLEANUP
- **Evidence command:** `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id enable-pager-and-hybrid-recovery-2026-04-17 --output reports/l4_wave_indicators/enable-pager-and-hybrid-recovery-2026-04-17.json`
- **Evidence delta:**
  1. Flips `pipeline_agent_pager.enabled` from `false` to `true`: the existing
     6 pager event types (`phase_b_reviewer_started`, `commit_ready`, 3
     recovery states, `pipeline_hard_fail`) now emit to
     `.agent_bus/observability/pipeline_agent_events.jsonl` on subsequent
     waves.
  2. Flips `hybrid_recovery_enabled` from `false` to `true`: the
     `_run_delegate_implementer_action` handler at `recovery_gate.py:2939-2956`
     stops short-circuiting with `"hybrid_recovery_enabled is false;
     delegate_implementer is disabled"` when a Tier 3 recovery agent proposes
     the `delegate_implementer` action.
  3. Flips the three implementer backends from `codex` to `claude`:
     `backends.phase_a_executor` (read at `phase_a_executor.py:1098`),
     `backends.phase_b_executor` (read at `phase_b_executor.py:2457`), and
     `backends.bot_remediation` (read at `commit_executor.py:189`). Next waves
     dispatched through these executors invoke the Claude adapter instead of
     the Codex adapter for code-writing actions.
  4. Rewrites the `bridge_config.example.json` claude adapter cmd to the
     explicit `claude-opus-4-7` model + `max` effort spec, replacing the
     minimal three-arg placeholder. Fresh worktrees auto-heal from this
     template plus the runtime main-repo copy.
- **Indicator artifact:** `reports/l4_wave_indicators/enable-pager-and-hybrid-recovery-2026-04-17.json`
- **Bootstrap endgame policy:** SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP
- **Boot0 track:** V1 / HOLD
- **Founder override:** FOUNDER_OVERRIDE:enable-pager-and-hybrid-recovery-2026-04-17
  (founder authorized in-session via "yes" to the combined enable-both proposal
  + the subsequent implementer-to-claude-opus-4.7-max directive. MAINTENANCE
  class with 2 consecutive non-structural waves (#785 post-wave-housekeeping
  + this) requires FOUNDER_OVERRIDE for the rolling-window non-structural
  adjacency cap.)

## Verification Plan

Pre-push-fast (commit_executor step 11) runs the full ratchet sweep and
`enforce_l4_execution_contract.py`. MAINTENANCE + FOUNDER_OVERRIDE should
clear.

No Step 8b pytest because wave-owned scope contains no test files — existing
test suites continue to cover the now-enabled paths and the unchanged backend
resolution logic.

## Stop Conditions

- Abort if `enforce_l4_execution_contract.py` rejects MAINTENANCE classification
  even with `FOUNDER_OVERRIDE`.
- Abort if ratchet sweep detects any file beyond the 3 in scope.
- Abort if the new `bridge_config.example.json` fails the JSON schema
  validation inherent to `bridge_adapters.load_bridge_config`.

## Live-Fire Test After Merge

This wave's own commit path uses standalone commit_executor + `--skip-supervisor`,
so the `commit_ready` pager emit at `commit_executor.py:3734` is bypassed for
this wave. The NEXT substantive wave (planned: one of the 4 pipeline-hardening
defects filed in PR #785, run through full dispatcher with Phase A + Phase B)
will be the live-fire test bed:

- `phase_b_reviewer_started` should emit at `phase_b_executor.py:3058` or
  `:3563` when Phase B enters bridge review.
- `commit_ready` should emit at `commit_executor.py:3734` after supervisor
  receipt validation.
- `recovery_*` events should emit if Tier 3 recovery activates during that
  wave's pipeline.
- Hybrid `delegate_implementer` path should now execute at
  `recovery_gate.py:2939` if any recovery agent proposes it, instead of
  short-circuiting.
- Phase B's claude implementer invocation should show in bridge logs with
  `--model claude-opus-4-7 --effort max`.

## Closeout

On merge, `commit_executor` step 16 runs post-merge cleanup (wave worktree +
branch removal). Main repo is clean at merge time (verified in-session).

The next substantive wave is the first live-fire test for both pager + hybrid
and for Claude-as-implementer. Observe `.agent_bus/observability/pipeline_agent_events.jsonl`
on that wave to confirm pager events; observe `.agent_bus/recovery/recovery_log.json`
for `hybrid_recovery_enabled=true` attempts if Tier 3 recovery fires; observe
the phase_b log for the claude adapter invocation.
