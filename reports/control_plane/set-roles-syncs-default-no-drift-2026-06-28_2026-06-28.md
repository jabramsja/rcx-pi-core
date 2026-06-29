# set_roles is the single-spot switch: keep DEFAULT/fallback role_agents in sync (no drift)

Date: 2026-06-28
Status: Phase B (locked, implementing)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: set-roles-syncs-default-no-drift-2026-06-28
Phase-A-Lock: LOCKED
Purpose: Make set_roles.py the TRUE single-spot role switch so the bare/missing-config fallback can NEVER drift and no manual DEFAULT_EXECUTOR_CONFIG edit is ever needed again (this session a manual DEFAULT.role_agents.reviewer codex->claude hand-edit was required because set_roles does not sync it). The linchpin already made DEFAULT derive its BACKENDS from role_agents and made load_config materialize on every path; the remaining gap is that DEFAULT_EXECUTOR_CONFIG.role_agents itself is a hardcoded literal set_roles does NOT update, so the bare-config fallback uses whatever literal is hardcoded. FIX (implementer picks the cleaner after reading load_config + set_roles + DEFAULT_EXECUTOR_CONFIG): (a) set_roles.py also writes DEFAULT_EXECUTOR_CONFIG.role_agents to match the selected implementer/reviewer, OR (b) the bare/missing-config fallback in executor_common derives role_agents from the committed executor_config.json when present, falling to the literal only when truly absent. Ensure: after set_roles --implementer X --reviewer Y, BOTH the committed config AND the fallback resolve X/Y with no hardcoded drift, for ANY provider (claude or codex). Add regressions to test_set_roles and test_executor_config_alignment covering a switch in both directions exercising the fallback path. STRICT: polymorphic (never hardcode a provider); no host semantics; no runtime/substrate/seed changes.

## Scope

Make set_roles.py the TRUE single-spot role switch so the bare/missing-config fallback can NEVER drift and no manual DEFAULT_EXECUTOR_CONFIG edit is ever needed again (this session a manual DEFAULT.role_agents.reviewer codex->claude hand-edit was required because set_roles does not sync it). The linchpin already made DEFAULT derive its BACKENDS from role_agents and made load_config materialize on every path; the remaining gap is that DEFAULT_EXECUTOR_CONFIG.role_agents itself is a hardcoded literal set_roles does NOT update, so the bare-config fallback uses whatever literal is hardcoded. FIX (implementer picks the cleaner after reading load_config + set_roles + DEFAULT_EXECUTOR_CONFIG): (a) set_roles.py also writes DEFAULT_EXECUTOR_CONFIG.role_agents to match the selected implementer/reviewer, OR (b) the bare/missing-config fallback in executor_common derives role_agents from the committed executor_config.json when present, falling to the literal only when truly absent. Ensure: after set_roles --implementer X --reviewer Y, BOTH the committed config AND the fallback resolve X/Y with no hardcoded drift, for ANY provider (claude or codex). Add regressions to test_set_roles and test_executor_config_alignment covering a switch in both directions exercising the fallback path. STRICT: polymorphic (never hardcode a provider); no host semantics; no runtime/substrate/seed changes.

Files and surfaces in scope:

- `mu/tools/executors/set_roles.py` -- the single role-switch CLI. Implementation surface under option (a): the switch also propagates the selected implementer/reviewer into the DEFAULT fallback. (See Work items.)
- `mu/tools/executors/executor_common.py` -- `load_config` + the `DEFAULT_EXECUTOR_CONFIG` bare/missing-config fallback (currently a hardcoded `role_agents` literal `set_roles` does not update). Implementation surface under option (b): the fallback derives `role_agents` from the committed `executor_config.json`.
- `mu/tests/tools/test_set_roles.py` -- both-direction switch regression (touched regardless of option a/b).
- `mu/tests/tools/test_executor_config_alignment.py` -- fallback-path alignment regression (touched regardless of option a/b).
- TASKS.md -- tracker-sync authority. The 2026-06-28 tracker sync note for wave `set-roles-syncs-default-no-drift-2026-06-28` is the single source of truth for this packet's L4 fields; the packet derives from it.

The implementer picks (a) or (b) after reading `load_config` + `set_roles` + `DEFAULT_EXECUTOR_CONFIG`; exactly one of `set_roles.py` / `executor_common.py` is the chosen implementation surface, the other a read surface. Both test files are touched either way.

## Work items

1. Close the DEFAULT/fallback `role_agents` drift by implementing exactly ONE of (implementer picks the cleaner after reading `load_config` + `set_roles` + `DEFAULT_EXECUTOR_CONFIG`):
   - (a) Extend `set_roles.py` so a switch also writes the selected implementer/reviewer through to `DEFAULT_EXECUTOR_CONFIG.role_agents` (the bare/missing-config fallback literal in `executor_common.py`), keeping the fallback in sync with the committed config.
   - (b) Change the bare/missing-config fallback in `executor_common` so it derives `role_agents` from the committed `executor_config.json` when present, falling back to the hardcoded literal only when the committed config is truly absent.
2. Add both-direction regressions exercising the fallback path:
   - `mu/tests/tools/test_set_roles.py`: a switch in each direction leaves the committed config AND the fallback resolving the same selected implementer/reviewer.
   - `mu/tests/tools/test_executor_config_alignment.py`: the bare/missing-config fallback path resolves the selected implementer/reviewer with no hardcoded drift.

## Constraints

- Polymorphic only: never hardcode a provider. The sync path must resolve whatever implementer/reviewer was selected (claude, codex, or any future provider) -- no provider literal baked in.
- No host semantics added.
- No runtime/substrate/seed changes. This is a control-plane `L4_ENABLER`; per the L4 contract it MUST NOT touch runtime dirs. Out of scope: `mu/host/`, `rcx_pi/selfhost/`, seeds, and any projection/eval behavior.
- Do not change the role-derivation rule (`role_agents` -> backends/bridge_reviewers, shared via `apply_role_agents`); only the DEFAULT/fallback `role_agents` source is in scope.

## Stop conditions

- Stop if the bare/missing-config fallback cannot be made provider-agnostic without a runtime/substrate/seed change -- surface as POLICY_BOUND rather than touch runtime dirs.
- Stop if the chosen option (a/b) can only be made to work by hardcoding a specific provider into the sync path.
- Stop if the `evidence_command` tests cannot pass without weakening the polymorphic (no-provider-hardcode) guarantee.
- Stop if neither option (a) nor (b) keeps the committed config AND the fallback resolving the same selection after a switch.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_set_roles.py mu/tests/tools/test_executor_config_alignment.py mu/tests/tools/test_executor_dispatch.py`

## Acceptance criteria

- After `set_roles.py --implementer X --reviewer Y` for ANY provider pair (claude, codex, or any other), BOTH the committed `executor_config.json` AND the bare/missing-config fallback resolve implementer=X and reviewer=Y -- no hardcoded DEFAULT drift.
- No manual `DEFAULT_EXECUTOR_CONFIG.role_agents` hand-edit is required after a switch (the drift this wave exists to eliminate; one was needed this session).
- Both-direction regressions in `mu/tests/tools/test_set_roles.py` and `mu/tests/tools/test_executor_config_alignment.py` pass, exercising the fallback path.
- The fix is polymorphic (no provider hardcoded) and touches no runtime/substrate/seed surface.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `set-roles-syncs-default-no-drift-2026-06-28`.
- Governing packet: this file, `reports/control_plane/set-roles-syncs-default-no-drift-2026-06-28_2026-06-28.md`.
- TASKS.md authority: the 2026-06-28 tracker sync note for wave `set-roles-syncs-default-no-drift-2026-06-28` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:set-roles-syncs-default-no-drift-2026-06-28
