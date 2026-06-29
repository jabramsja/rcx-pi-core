# executor_common bare/missing-config fallback imports menu-only agents' bridge_agent_defaults, not just role_agents

Date: 2026-06-29
Status: Phase B (locked, implementing)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: fallback-imports-agent-menu-defs-2026-06-29
Phase-A-Lock: LOCKED
Purpose: Close the P2 deferred from the #14 set-roles single-switch wave. GAP: the bare/missing-config fallback in executor_common that materializes an effective config from the committed role_agents + DEFAULT_EXECUTOR_CONFIG imports ONLY role_agents -- it does NOT import the agent-MENU definitions (the `bridge_agent_defaults` entries) for an agent that is MENU-ONLY (declared in the committed executor_config.json menu but ABSENT from DEFAULT_EXECUTOR_CONFIG, e.g. a provider like `fable` that the founder added to the menu). RESULT: when set_roles selects a menu-only agent and execution falls back to the bare/missing-config path, the config routes the executor backends/bridge_reviewers to that agent but LOSES its menu defs (model / effort / display_name / adapter command), so the agent can't be resolved correctly. FIX (additive, executor_common only): when the fallback materializes the effective config, for any agent referenced by the resolved role_agents/backends/bridge_reviewers that is present in the COMMITTED config's `bridge_agent_defaults` but absent from DEFAULT_EXECUTOR_CONFIG's `bridge_agent_defaults`, COPY that agent's menu definition into the materialized config's `bridge_agent_defaults` so the menu-only agent's defs survive the fallback. Preserve existing behavior for agents already in DEFAULT (claude/codex). Do NOT change role resolution precedence, set_roles, or any gate. Polymorphic: works for ANY menu-only provider, never hardcode one. Add a regression named exactly `test_bare_fallback_imports_menu_only_agent_menu_defs` (and a sibling for an agent already in DEFAULT staying unchanged) asserting that after the bare/missing-config fallback with a committed menu-only agent selected, the materialized config carries that agent's bridge_agent_defaults entry. No host semantics.

## Scope

Close the P2 deferred from the #14 set-roles single-switch wave. GAP: the bare/missing-config fallback in executor_common that materializes an effective config from the committed role_agents + DEFAULT_EXECUTOR_CONFIG imports ONLY role_agents -- it does NOT import the agent-MENU definitions (the `bridge_agent_defaults` entries) for an agent that is MENU-ONLY (declared in the committed executor_config.json menu but ABSENT from DEFAULT_EXECUTOR_CONFIG, e.g. a provider like `fable` that the founder added to the menu). RESULT: when set_roles selects a menu-only agent and execution falls back to the bare/missing-config path, the config routes the executor backends/bridge_reviewers to that agent but LOSES its menu defs (model / effort / display_name / adapter command), so the agent can't be resolved correctly. FIX (additive, executor_common only): when the fallback materializes the effective config, for any agent referenced by the resolved role_agents/backends/bridge_reviewers that is present in the COMMITTED config's `bridge_agent_defaults` but absent from DEFAULT_EXECUTOR_CONFIG's `bridge_agent_defaults`, COPY that agent's menu definition into the materialized config's `bridge_agent_defaults` so the menu-only agent's defs survive the fallback. Preserve existing behavior for agents already in DEFAULT (claude/codex). Do NOT change role resolution precedence, set_roles, or any gate. Polymorphic: works for ANY menu-only provider, never hardcode one. Add a regression named exactly `test_bare_fallback_imports_menu_only_agent_menu_defs` (and a sibling for an agent already in DEFAULT staying unchanged) asserting that after the bare/missing-config fallback with a committed menu-only agent selected, the materialized config carries that agent's bridge_agent_defaults entry. No host semantics.

Files and surfaces in scope:

- `mu/tools/executors/executor_common.py` -- implementation target (the ONLY runtime/tooling file changed). The change is confined to `merge_executor_config_overrides` (the bare/missing-config fallback materialization, the branch where `overrides` does not pin `role_agents`). It additively copies a committed menu-only agent's `bridge_agent_defaults` entry into the materialized config, sourcing the committed file through the existing `_committed_executor_config_path()` read seam already used by `_fallback_role_agents`. No other function's behavior changes.
- `mu/tests/tools/test_set_roles.py` -- regression home (one of the two `evidence_command` grep targets). Houses the new `test_bare_fallback_imports_menu_only_agent_menu_defs` and/or its DEFAULT-agent sibling.
- `mu/tests/tools/test_executor_config_alignment.py` -- regression home (the other `evidence_command` grep target). Same two named regressions may live here; `evidence_command` greps both files.
- TASKS.md -- tracker-sync authority. The 2026-06-29 tracker sync note for wave `fallback-imports-agent-menu-defs-2026-06-29` (TASKS.md current `[NEXT-CODEX-POST-REDTEAM]` line) is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. In `merge_executor_config_overrides` (`mu/tools/executors/executor_common.py`), on the bare/missing-config fallback branch only (`"role_agents" not in overrides`, where `role_agents` is currently sourced from `_fallback_role_agents()`), additively import menu definitions for menu-only agents. For any agent referenced by the resolved `role_agents` (and the `backends`/`bridge_reviewers` derived from them) that is present in the COMMITTED `executor_config.json`'s `bridge_agent_defaults` but ABSENT from `DEFAULT_EXECUTOR_CONFIG['bridge_agent_defaults']`, copy that agent's `bridge_agent_defaults` entry into the materialized config's `bridge_agent_defaults`. Read the committed file through the existing `_committed_executor_config_path()` seam (the same seam `_fallback_role_agents` uses); do not re-read by any other path. Copy is additive: never overwrite an entry already supplied by `DEFAULT_EXECUTOR_CONFIG` (claude/codex).
2. Add the regression named exactly `test_bare_fallback_imports_menu_only_agent_menu_defs` to one of the two `evidence_command` files (`mu/tests/tools/test_set_roles.py` or `mu/tests/tools/test_executor_config_alignment.py`). With a committed menu-only agent selected (an agent declared in the committed menu's `bridge_agent_defaults` but absent from `DEFAULT_EXECUTOR_CONFIG`), drive the bare/missing-config fallback and assert the materialized config's `bridge_agent_defaults` carries that agent's entry (its menu definition -- model / effort / display_name / adapter command -- intact). Construct the menu-only agent in-test; never hardcode a provider name.
3. Add the sibling regression asserting an agent already present in `DEFAULT_EXECUTOR_CONFIG` (claude / codex) is unchanged by the fallback: its `bridge_agent_defaults` entry is neither dropped nor overwritten by the new copy step. This is the "agent already in DEFAULT staying unchanged" case named in the tracker note.

## Constraints

- Additive change, `mu/tools/executors/executor_common.py` only. No other executor/tool/runtime file is modified (besides the two named test files, TASKS.md, this packet, and the generated indicator artifact).
- Do NOT change role-resolution precedence, `set_roles.py`, the `_fallback_role_agents` role selection, `resolve_committed_role_agent`, or any gate. Only the `bridge_agent_defaults` (menu-def) materialization on the bare/missing-config branch is touched.
- Scope is the bare/missing-config fallback branch ONLY. An override that DOES carry `role_agents` is authoritative and stays untouched (it already wins through `_materialize_role_agents`); the menu-defs import must not alter that path.
- Preserve existing behavior for agents already in `DEFAULT_EXECUTOR_CONFIG` (claude / codex): their `bridge_agent_defaults` entries are never dropped or overwritten by the copy.
- Polymorphic: never hardcode a provider name (e.g. `fable`). The copy keys off "present in committed `bridge_agent_defaults`, absent from DEFAULT" for ANY menu-only agent.
- L4_ENABLER bound: MUST NOT touch runtime dirs (`rcx_pi/selfhost/`, mu host substrate, `mu/host/js/`). No host semantics, no new host primitive, no L3-parity surface. The change is control-plane config materialization only.
- Do NOT alter the env-overrides re-materialization in `load_executor_config` (`use_env_overrides` precedence stays unchanged).

## Stop conditions

- STOP and re-scope if the menu-defs import cannot be done without changing role-resolution precedence, `set_roles.py`, `_fallback_role_agents`, or any gate -- that is out of scope for this wave.
- STOP if implementing the copy would require touching a runtime dir (`rcx_pi/selfhost/`, mu host substrate, `mu/host/js/`) or adding a host primitive -- the L4_ENABLER class forbids it.
- STOP if the override-pinned `role_agents` path (config that DOES carry `role_agents`) would be altered by the change -- the import must be confined to the bare/missing-config branch.
- STOP if the regression cannot construct a committed menu-only agent without hardcoding a provider name -- the test must be polymorphic.
- STOP and escalate if the exact test name `test_bare_fallback_imports_menu_only_agent_menu_defs` cannot satisfy the `evidence_command` grep additively -- the tracker note fixes the name; do not rename the gate.
- STOP at design boundary: this packet is Phase A. Do not implement, commit, push, or merge from here; hand off to the executor pipeline.

## Validation gates

- evidence_command: `grep -q test_bare_fallback_imports_menu_only_agent_menu_defs mu/tests/tools/test_set_roles.py mu/tests/tools/test_executor_config_alignment.py`

## Acceptance criteria

- `evidence_command` exits 0: `grep -q test_bare_fallback_imports_menu_only_agent_menu_defs mu/tests/tools/test_set_roles.py mu/tests/tools/test_executor_config_alignment.py` (the named regression is present).
- The full `mu/tests/tools/test_set_roles.py` and `mu/tests/tools/test_executor_config_alignment.py` suites pass (CI green-gate); the non-re-entrant grep is the in-band evidence because this wave modifies `executor_common`, which the supervisor `wave_evidence` would otherwise re-enter.
- `python3 -m py_compile mu/tools/executors/executor_common.py` succeeds.
- After the bare/missing-config fallback with a committed menu-only agent selected, the materialized config's `bridge_agent_defaults` contains that agent's entry with its menu definition (model / effort / display_name / adapter command) intact -- proven by `test_bare_fallback_imports_menu_only_agent_menu_defs`.
- An agent already in `DEFAULT_EXECUTOR_CONFIG` (claude / codex) is unchanged by the fallback (entry neither dropped nor overwritten) -- proven by the sibling regression.
- No diff outside `mu/tools/executors/executor_common.py`, the two named test files, TASKS.md, this packet, and the generated indicator artifact `reports/l4_wave_indicators/fallback-imports-agent-menu-defs-2026-06-29.json`. `git diff --check` is clean.
- Bootstrap-purity ratchet and host-authority baseline are unaffected: no new host primitive and no new host-authority site (additive config copy only).

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `fallback-imports-agent-menu-defs-2026-06-29`.
- Governing packet: this file, `reports/control_plane/fallback-imports-agent-menu-defs-2026-06-29_2026-06-29.md`.
- TASKS.md authority: the 2026-06-29 tracker sync note for wave `fallback-imports-agent-menu-defs-2026-06-29` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:fallback-imports-agent-menu-defs-2026-06-29
