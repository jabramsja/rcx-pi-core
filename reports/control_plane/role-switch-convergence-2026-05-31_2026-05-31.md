# Role-Switch-Convergence-2026-05-31 2026-05-31

Date: 2026-05-31
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: role-switch-convergence-2026-05-31
Lane: control-surface (agent role defaults / observability)
Class: L4_ENABLER (target_gate_id: G8) — touches NO runtime dirs
Phase-A-Lock: LOCKED
Purpose: Variant A2 (founder-approved) — make the live `mu/tools/executors/executor_config.json` `role_agents` the single source of truth so `set_roles.py` alone is a complete role switch (no manual scanning, no test breakage), and reflect role changes in the tmux/dashboard labels. `DEFAULT_EXECUTOR_CONFIG` in `executor_common.py` stays a fallback that need NOT equal live.

## Scope (files / directories in scope)

- `mu/tests/tools/test_executor_config_alignment.py` — relax `TestRoleAgentConfigAlignment::test_role_agents_match_between_default_and_live_config` to assert LIVE-internal consistency, not `DEFAULT==live`. *(existing file — edit)*
- `mu/tools/executors/set_roles.py` — confirm/document it is the complete single switch (writes live + materializes backends via `executor_common.apply_role_agents`). *(confirm/document; edit only if a doc/usage gap is found)*
- `mu/tools/executors/executor_common.py` — `DEFAULT_EXECUTOR_CONFIG` (fallback) + the `apply_role_agents` materialization path; reference/confirm. *(confirm/document; edit only if the consistency check needs a derivation helper)*
- `mu/tools/executors/executor_config.json` — the authoritative live `role_agents` source. *(reference only; not expected to change in this wave)*
- `mu/tools/observability/` — tmux/dashboard label-refresh surface; labels derive from `role_agents` per the 2026-04-21 role-agent-switch design. Specific script confirmed in Phase B. *(verify; wire only if labels don't already refresh)*
- `mu/tests/tools/test_set_roles.py` — existing single-switch coverage; extend if W2/W3 need an assertion. *(existing file — edit)*
- `mu/tests/docs/test_growth_caps.py` — CONDITIONAL: edit ONLY if a new test file is unavoidable (see Constraints / W-CAP).

## Work items (bounded checklist)

- [ ] **W1 — Relax the alignment test.** Change `test_role_agents_match_between_default_and_live_config` so it asserts the LIVE config is internally consistent — its derived `backends` and `bridge_reviewers` match its own `role_agents` — instead of asserting `DEFAULT_EXECUTOR_CONFIG == live`. A `set_roles.py` flip (which edits only the live file) must no longer break this test.
- [ ] **W2 — Confirm / document the single switch.** Confirm `set_roles.py` is the complete role switch: it writes the live `executor_config.json` and materializes `backends`/`bridge_reviewers` via `executor_common.apply_role_agents`. Document the contract (DEFAULT is fallback; live is authoritative). Add/extend a `test_set_roles.py` assertion only if that contract is not already locked by a test.
- [ ] **W3 — Verify / wire the tmux-label refresh.** Verify the rcx-pipeline tmux/dashboard implementer/reviewer labels derive from live `role_agents` and refresh on a role change (2026-04-21 design). Wire the refresh only if verification shows the labels are stale after a flip.
- [ ] **W-CAP (conditional) — Growth-cap.** Zero headroom: the test-file count is exactly at `CAP_TEST_FILES` (learning.md 2026-05-30). If — and only if — W1/W2/W3 add ANY new test file, bump `CAP_TEST_FILES` by 1 in `mu/tests/docs/test_growth_caps.py` with an inline comment citing `FOUNDER_OVERRIDE:role-switch-convergence-2026-05-31`, and stage that file with the wave. Editing only the existing `test_executor_config_alignment.py` / `test_set_roles.py` needs NO cap bump.

## Constraints (NOT in scope)

- **No runtime dirs.** L4_ENABLER MUST NOT touch `mu/host/**` or `rcx_pi/selfhost/**`. No host-semantics change, no L3 parity surface. (TASKS.md OPEN wave: "Touches NO runtime dirs.")
- **Do NOT make DEFAULT equal live.** A2 explicitly keeps `DEFAULT_EXECUTOR_CONFIG` as a fallback that need NOT equal live; reintroducing a `DEFAULT==live` assertion is forbidden — that equality is exactly what the 2026-05-30 role-flip saga proved brittle.
- **No new parallel mechanism.** Work within the existing `role_agents` + `apply_role_agents` control surface; do not introduce a second role-config path.
- **No new test files unless unavoidable** (zero growth-cap headroom). Prefer editing existing tests; if unavoidable, apply W-CAP in the same wave.
- **No go-live / `settings.json` changes.** Reviewer-shadow override removal and any `~/.claude/settings.json` edits are a separate post-merge go-live step, not this wave.
- **No commit / push / merge this turn.** This is a Phase A plan; implementation and the pipeline run come after agent + bridge convergence.

## Stop conditions

- Stop and request a founder decision (POLICY_BOUND) if making the live config authoritative would require touching a runtime dir, or if a real consumer is found that depends on `DEFAULT_EXECUTOR_CONFIG` equalling live.
- Stop and apply W-CAP (with the `FOUNDER_OVERRIDE` comment) before proceeding if any work item forces a new test file; do not silently exceed `CAP_TEST_FILES`.
- Stop and re-scope if W3 cannot be satisfied by reading `role_agents` and would instead need a new label mechanism (that exceeds "verify or wire").
- Halt at Phase-A-Lock for commit/push/merge: proceed only after agents + bridge converge on this packet, then run the standard executor pipeline.

## Acceptance criteria

- `test_role_agents_match_between_default_and_live_config` asserts LIVE-internal consistency (derived `backends` + `bridge_reviewers` match the live `role_agents`), NOT `DEFAULT==live`; a `set_roles.py` live-only flip no longer breaks it.
- Evidence command passes:
  `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_config_alignment.py mu/tests/tools/test_set_roles.py -q --tb=short && python3 -m py_compile mu/tools/executors/executor_common.py mu/tools/executors/set_roles.py`
- `set_roles.py` is documented/confirmed as the complete single switch (writes live + materializes backends via `executor_common.apply_role_agents`).
- tmux/dashboard implementer/reviewer labels reflect the active `role_agents` after a role change (verified, or wired if they did not).
- No runtime dirs touched; L4 indicator artifact collected:
  `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id role-switch-convergence-2026-05-31 --output reports/l4_wave_indicators/role-switch-convergence-2026-05-31.json`
- If any new test file was added, `CAP_TEST_FILES` was bumped by 1 with the inline `FOUNDER_OVERRIDE:role-switch-convergence-2026-05-31` comment and staged with the wave.

## Grounding / Authorization

- **TASKS.md authorization:** OPEN wave `[ROLE-SWITCH-CONVERGENCE]` (2026-05-31 founder-directed primary wave; founder-approved variant A2), whose **Tracked packet** is this file (`reports/control_plane/role-switch-convergence-2026-05-31_2026-05-31.md`) and whose **Lane** is control-surface (agent role defaults / observability). The OPEN-wave statement defines W1–W3 and asserts the wave touches NO runtime dirs.
- **Governing packet:** this file (self-governing Phase A packet for wave `role-switch-convergence-2026-05-31`).
- **Canonical L4_ENABLER tracker note** (TASKS.md, wave `role-switch-convergence-2026-05-31`, detector-visible per `_tasks_tracker_note_wave_exists`):
  - Class: L4_ENABLER · target_gate_id: G8
  - primary_blocker_class: INTEGRATION · primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION
  - evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_config_alignment.py mu/tests/tools/test_set_roles.py -q --tb=short && python3 -m py_compile mu/tools/executors/executor_common.py mu/tools/executors/set_roles.py`
  - indicator_artifact_ref: `reports/l4_wave_indicators/role-switch-convergence-2026-05-31.json`
  - indicator_collection_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id role-switch-convergence-2026-05-31 --output reports/l4_wave_indicators/role-switch-convergence-2026-05-31.json`
  - bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP · boot0_track_id: V1 · boot0_progress_state: HOLD
- **Founder override (wave-bound):** `FOUNDER_OVERRIDE:role-switch-convergence-2026-05-31` — founder-directed primary-wave authorization for this control-surface L4_ENABLER convergence; required to clear Gate 8 non-structural adjacency / rolling-window enforcement while hardening the role-switch surface and tests without widening runtime semantics. Commit automation derives the same-wave override from this token.
- **Authorization:** standing pipeline-bug-fix authorization for this active `[ROLE-SWITCH-CONVERGENCE]` control-surface L4_ENABLER wave — it repairs the `set_roles.py` / alignment-test gap exposed by the 2026-05-30 role-flip saga (`set_roles.py` edits the live file only while the test asserted `DEFAULT==live`). No runtime semantics change.

## Request from Post-Merge Supervisor

A2 (founder-approved): the live mu/tools/executors/executor_config.json role_agents is authoritative; DEFAULT_EXECUTOR_CONFIG in executor_common.py is a fallback that need NOT equal live. (1) Relax mu/tests/tools/test_executor_config_alignment.py::TestRoleAgentConfigAlignment::test_role_agents_match_between_default_and_live_config so it asserts the LIVE config is internally CONSISTENT (its derived backends + bridge_reviewers match its role_agents) rather than asserting DEFAULT==live -- so a set_roles.py flip (which edits only the live file) no longer breaks it. (2) Confirm/document set_roles.py is the complete single switch (it already writes live + materializes backends via executor_common.apply_role_agents). (3) Wire or verify a tmux-label refresh so changing roles reflects the active implementer/reviewer in the rcx-pipeline monitor (labels derive from role_agents per the 2026-04-21 design). Add/adjust tests. RATIONALE: set_roles editing live-only (not DEFAULT) is exactly the gap that broke the alignment test in the 2026-05-30 role-flip saga; A2 makes live authoritative so the single switch works. GROWTH-CAP (zero headroom -- test count is exactly at CAP_TEST_FILES, per learning.md 2026-05-30): if you add ANY new test file, you MUST also bump CAP_TEST_FILES +1 in mu/tests/docs/test_growth_caps.py with an inline comment citing FOUNDER_OVERRIDE:role-switch-convergence-2026-05-31, and stage mu/tests/docs/test_growth_caps.py with the wave. If you only edit existing test files (test_executor_config_alignment.py, test_set_roles.py), no cap bump is needed.

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `role-switch-convergence-2026-05-31`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/role-switch-convergence-2026-05-31_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `role-switch-convergence-2026-05-31`
- Active packet: `reports/control_plane/role-switch-convergence-2026-05-31_2026-05-31.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `4c944e7f402c55856a74d571a73d9d37e2185d32dfefa6953c7c076069630425`
- Indicator artifact: `reports/l4_wave_indicators/role-switch-convergence-2026-05-31.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_config_alignment.py mu/tests/tools/test_set_roles.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/role-switch-convergence-2026-05-31_2026-05-31.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/role-switch-convergence-2026-05-31.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_config_alignment.py`
  - `mu/tests/tools/test_set_roles.py`
  - `mu/tools/executors/set_roles.py`
  - `reports/control_plane/role-switch-convergence-2026-05-31_2026-05-31.md`
  - `reports/deferred/non_blocking/role-switch-convergence-2026-05-31_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/role-switch-convergence-2026-05-31.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
