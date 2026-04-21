# Role-Agent Switch Control Surface

Date: 2026-04-21
Status: Phase B (founder-authorized manual control-plane landing)
Task: [PIPELINE-ROLE-AGENT-SWITCH]
Wave ID: role-agent-switch-2026-04-21
Phase-A-Lock: LOCKED
Wave class: L4_ENABLER
Target gate: G8
Governing packet: This file

## Grounding / Authorization

- Founder explicitly authorized this wave in-session on 2026-04-21 as the one
  allowed manual parallel wave while the active pipeline wave continues.
- The operational trigger is reproduced in live repo truth:
  - main checkout dirty control-plane config already points implementer and
    reviewer defaults at Codex 5.4 xhigh
  - fresh worktrees still inherit committed `dev` truth, which remained
    Claude-backed for `phase_a_executor`, `phase_b_executor`, and
    `bot_remediation`
  - the active Wave 9 worktree at
    `/private/tmp/workingrcx_phase_b_validate_inputs_task_id_leniency_2026_04_21`
    confirms that drift in `mu/tools/executors/executor_config.json`
- The goal is to replace multi-file provider retargeting with one durable
  switch surface so future waves do not require another manual sweep across
  tmux, dashboard, and executor code.

## Purpose

Make provider switching mechanical for the control plane:

1. persistent defaults live in `executor_config.json`
2. session overrides use environment variables instead of code edits
3. legacy executor/bridge keys are materialized from role intent instead of
   being patched independently
4. operator-facing truth surfaces derive display labels from bridge config,
   not hard-coded provider names

This wave is not a runtime or substrate change. It is a control-plane routing
and observability hardening pass.

## Scope

Only these files are in scope:

1. `mu/tools/executors/executor_common.py`
2. `mu/tools/executors/executor_config.json`
3. `mu/tools/agents/bridge_config.example.json`
4. `mu/tools/agents/meta_bridge_supervisor.py`
5. `mu/tools/observability/pipeline_dashboard.py`
6. `mu/tools/observability/pipeline_dashboard_web.py`
7. `mu/tools/observability/_pane_timeline.sh`
8. `mu/tools/observability/_pane_processes.sh`
9. `mu/tests/tools/test_executor_dispatch.py`
10. `mu/tests/tools/test_executor_config_alignment.py`
11. `mu/tests/tools/test_phase_b_executor.py`
12. `mu/tests/tools/test_meta_bridge_supervisor.py`
13. `reports/control_plane/role_agent_switch_2026-04-21.md`

## Work Items

**A. Canonical role switch**

- Add `role_agents.implementer` and `role_agents.reviewer` as the persistent
  repo-tracked provider switch in `executor_config.json`
- Add session overrides:
  - `RCX_IMPLEMENTER_AGENT_OVERRIDE`
  - `RCX_REVIEWER_AGENT_OVERRIDE`
  - keep `RCX_BRIDGE_REVIEWER_OVERRIDE` as reviewer-compatible legacy alias
- Materialize legacy `backends` and `bridge_reviewers` from those role-level
  settings in `executor_common.py`

**B. Operator-facing truth**

- Make tmux panes, dashboard text, and post-merge reviewer logs render the
  configured role display names instead of hard-coded `Claude` / `Codex`
  strings
- Use `.agent_bus/bridge_config.json` catalog metadata (via the example schema)
  as provider/model/display-name truth for labels

**C. Future switch ergonomics**

- Keep implementer/reviewer switching config-only for both Codex and Claude
- Preserve backward compatibility for older config shapes that only set
  `backends` / `bridge_reviewers`
- Keep recovery truthful without widening the wave: Tier 3 recovery already
  resolves `backends.recovery_gate` or falls back to `backends.phase_b_executor`,
  so the committed implementer role switch continues to govern recovery through
  existing code paths

**D. Regression coverage**

- Extend the executor config and dispatch tests so role-agent defaults,
  overrides, and legacy reviewer alias behavior cannot silently regress

**E. Pre-commit worktree heal**

- Auto-heal missing linked-worktree `.agent_bus/bridge_config.json` inside
  meta-bridge before reviewer launch by copying the file from the main
  checkout when available
- Lock that catch-22 path with a meta-bridge regression so manual worktree
  bridge-config copying stops being required for clean control-plane waves

## Constraints

1. Do not touch `.claude/*` files in this wave.
2. Do not touch runtime or substrate files under `mu/host/` or `rcx_pi/`.
3. Do not restart or patch the active Wave 9 worktree from this wave.
4. Do not widen into startup-hook, founder-bootstrap, or pager-app-server work.
5. Do not require manual tmux/dashboard string edits for future provider flips.

## Stop Conditions

1. A fresh worktree from committed `dev` no longer defaults implementer paths
   to Claude.
2. Reviewer display text and process labels come from the configured role agent
   identity, not hard-coded provider names.
3. Session-level implementer/reviewer overrides work without retargeting the
   wrong role family.
4. Existing legacy config shapes still resolve cleanly.

## Acceptance Criteria

1. `executor_common.py` and `executor_config.json` agree on the committed
   default role-agent truth.
2. Implementer defaults are Codex 5.4 xhigh in fresh worktrees, and reviewer
   defaults are Codex 5.4 xhigh in fresh worktrees.
3. Setting `RCX_IMPLEMENTER_AGENT_OVERRIDE=claude` changes implementer paths
   without retargeting reviewer paths.
4. Setting `RCX_REVIEWER_AGENT_OVERRIDE=claude` or the legacy
   `RCX_BRIDGE_REVIEWER_OVERRIDE=claude` changes reviewer paths without
   retargeting implementer paths.
5. Dashboard/tmux/post-merge labels follow the selected provider display names.
6. Pre-commit meta-review no longer fails in a fresh linked worktree solely
   because `.agent_bus/bridge_config.json` has not yet been copied in.
7. The candidate diff stays confined to the scoped control-plane files above.
