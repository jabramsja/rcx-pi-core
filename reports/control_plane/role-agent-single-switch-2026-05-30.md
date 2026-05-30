# Role-Agent Single Switch

Date: 2026-05-30
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: `[NEXT-CODEX-POST-REDTEAM]`
Wave ID: `role-agent-single-switch-2026-05-30`
Class: L4_ENABLER
Target Gate: G8
Lane: control-surface
Authorization: founder-directed (2026-05-30) — single LLM-role switch + drop the env shadow
Phase-A-Lock: BOOTSTRAP_PHASE_B_EXCEPTION
FOUNDER_OVERRIDE:role-agent-single-switch-2026-05-30

## Problem
Reviewer=codex is currently forced by `RCX_BRIDGE_REVIEWER_OVERRIDE=codex` in
`~/.claude/settings.json`, which silently shadows the committed JSON (which declared
reviewer=claude). Two control points produce "some surfaces show one thing, some another"
confusion, and there is no easy way to flip roles.

## Goal
Make `executor_config.json` `role_agents` the SINGLE switch. Pin reviewer=codex in the
committed config, add a one-line CLI to flip roles self-consistently, and remove the env
shadow (post-merge). Net runtime-effective behavior is unchanged
(implementer=claude, reviewer=codex) — this is a control-surface cleanup, not a behavior change.

## Scope (allowed product writes)
- `mu/tools/executors/set_roles.py`                     (NEW — one-line switch CLI; JSON-only writer)
- `mu/tools/executors/executor_common.py`               (extract apply_role_agents; flip DEFAULT reviewer to codex; self-consistent derived literals)
- `mu/tools/executors/executor_config.json`             (role_agents + derived backends/bridge_reviewers; written by set_roles)
- `mu/tests/tools/test_set_roles.py`                    (NEW)
- `mu/tests/tools/test_executor_config_alignment.py`    (de-brittle one raw equals-codex assertion to consistency-based)
- `mu/tests/docs/test_growth_caps.py`                   (bump CAP_TEST_FILES + CAP_TOOL_SCRIPTS +1 each for the two new files; FOUNDER_OVERRIDE)
- `reports/control_plane/role-agent-single-switch-2026-05-30.md`  (this packet)

No runtime, substrate, seed, scheduler, registry, projection, parity, or Mu-semantic
changes. tmux/dashboard labels were inspected and need no change (see Changes #6).

## Changes
1. `executor_common.py`: extracted `apply_role_agents(config, implementer, reviewer)` from the
   body of `_materialize_role_agents` (behavior-identical refactor; `_materialize_role_agents`
   now calls it after resolving roles) so the derivation rule (role_agents to backends and
   bridge_reviewers) has one definition shared by the runtime loader and the CLI.
2. `executor_common.py`: flipped `DEFAULT_EXECUTOR_CONFIG.role_agents.reviewer` claude to codex
   and set the `backends` literal to the materialized shape (phase_a_executor / phase_b_executor /
   bot_remediation to claude; post_merge_supervisor / dialectic_executor to codex; commit_executor
   None). DEFAULT is now a materialization fixed-point of its own role_agents (kept a pure literal
   for the AST-parse alignment test).
3. `set_roles.py`: `--implementer X --reviewer Y` / `--show`; validates names against
   `bridge_agent_defaults` plus default display names; reuses `apply_role_agents`; writes ONLY
   `executor_config.json` (per the 2026-04-21 config-only directive); prints written + derived +
   runtime-EFFECTIVE (env-aware) resolution + a WARNING when an env override shadows the JSON.
   Idempotent.
4. `executor_config.json`: `role_agents = {implementer: claude, reviewer: codex}` + derived
   backends/bridge_reviewers, written by `set_roles --implementer claude --reviewer codex`.
5. `test_executor_config_alignment.py`: the one breaking assertion
   (bot_remediation equals codex) de-brittled to consistency-based — present in both DEFAULT and
   live, the two agree, and the value equals the implementer role agent (robust across switches).
6. tmux/dashboard labels: VERIFIED no change needed — `_pane_processes.sh`, `_pane_timeline.sh`,
   and `pipeline_dashboard_web.py` already render `configured_role_agents(repo_root)`, which
   resolves the effective env-aware agent. After this wave + env-shadow removal they show
   implementer=Claude / reviewer=Codex correctly.
7. `test_growth_caps.py`: bumped CAP_TEST_FILES 123->124 and CAP_TOOL_SCRIPTS 48->49 (+1 each),
   each with a documented FOUNDER_OVERRIDE:role-agent-single-switch-2026-05-30 note, to account
   for the two files this wave adds (test_set_roles.py, set_roles.py) per the file's existing
   per-wave-cap convention. No other count changes.

## Local Evidence
- `python3 -m py_compile mu/tools/executors/executor_common.py mu/tools/executors/set_roles.py` -> OK
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_set_roles.py mu/tests/tools/test_executor_config_alignment.py` -> 26 passed
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py` -> 523 passed
- Collateral: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_agent_bus_namespacing.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py mu/tests/tools/test_commit_executor_receipt.py`
- `set_roles` round-trip: show (env shadow surfaced) -> write claude/codex -> flip codex/claude -> flip back; final `role_agents = {claude, codex}`; invalid agent rejected (exit 2)
- DEFAULT fixed-point check: `apply_role_agents(DEFAULT.role_agents)` reproduces DEFAULT backends/bridge_reviewers
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id role-agent-single-switch-2026-05-30 --wave-class L4_ENABLER`
- `git diff --check`

## Post-merge (env, not a repo file — manual)
Remove `RCX_BRIDGE_REVIEWER_OVERRIDE` from `~/.claude/settings.json` (reviewer stays codex via the
committed config); update memory (`feedback_codex_reviews_always.md`, `project_next_wave_context.md`).
