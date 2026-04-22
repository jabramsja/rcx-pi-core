# Pager Codex App Server Provisioning

Task: `[PIPELINE-AGENT-PAGER]`  
Wave ID: `pager-codex-app-server-provisioning`  
Date: `2026-04-22`  
Status: ACTIVE (commit-path packet refresh applied; supervisor rerun pending)
Phase-A-Lock: LOCKED

## Outcome

This is the derived provisioning follow-up under the already-authorized
`[PIPELINE-AGENT-PAGER]` lane and its active 2026-04-22 parent slice
`reports/control_plane/pager_codex_app_server_transport_2026-04-22.md`. It
does not create a new tracker item and it does not reopen the landed transport
cleanup.

The landed split remains unchanged and explicit:

- `mu/tools/executors/executor_config.json` continues to own only pager
  enablement and route selection through
  `pipeline_agent_pager.enabled` / `pipeline_agent_pager.route`
- `RCX_CODEX_APP_SERVER_URL` remains the sole authoritative pager-side Codex
  App Server listener surface, and it must include an explicit websocket port

This follow-up hardens only provisioning-owned fail-closed behavior around that
split:

- `_codex_app_server_url()` now rejects websocket listener values that omit a
  port or use an invalid port before any websocket exchange is attempted
- Codex-routed pager delivery remains pending and reportable when
  `RCX_CODEX_APP_SERVER_URL` is malformed, violates the loopback `ws://`
  contract, or points to an unavailable listener
- provisioning failures do not synthesize delivery receipts and do not clear a
  previously stored `codex_thread_id` unless the failure is the already-owned
  transport stale-thread path
- same-wave Phase B re-entry now also strips Markdown backticks from the
  authoritative `Wave ID` and `Task` headers in this packet shape, so the
  canonical identity tuple remains
  `pager-codex-app-server-provisioning` / `[PIPELINE-AGENT-PAGER]` instead of
  failing `validate_inputs()` before the pager provisioning follow-up can run
- recovery now treats this packet's missing canonical `Phase-A-Lock` header as
  a deterministic repair, uses `phase_a_executor.lock_plan()` to insert and
  lock the header, and clears a dead `.agent_bus/bridge.lock` before retrying
  Phase B from dispatch

## Code Truth

Changed files:

- `TASKS.md`
- `mu/tests/tools/test_phase_b_executor.py`
- `mu/tests/tools/test_pipeline_agent_pager.py`
- `mu/tests/tools/test_recovery_gate.py`
- `mu/tools/executors/phase_b_executor.py`
- `mu/tools/executors/recovery_gate.py`
- `mu/tools/observability/pipeline_agent_pager.py`
- `reports/control_plane/pager_codex_app_server_provisioning_2026-04-22.md`
- `reports/control_plane/pager_codex_app_server_transport_2026-04-22.md`
- `reports/l4_wave_indicators/pager-codex-app-server-provisioning.json`

Why `TASKS.md` changed:

- the existing `[PIPELINE-AGENT-PAGER]` entry still authorizes this work as a
  derived same-lane follow-up under the live 2026-04-22 transport slice, but
  the commit-ready handoff path auto-appended the canonical tracker sync note
  for `pager-codex-app-server-provisioning`, so this staged wave does touch
  `TASKS.md` without creating a new task id

Why the indicator artifact changed:

- the handoff path also staged
  `reports/l4_wave_indicators/pager-codex-app-server-provisioning.json`, so the
  indicator belongs in the wave-owned file list for this packet
- commit-path tracker-note / indicator injection is still not mechanically
  reflected back into this packet before Step 6 meta review, so this evidence
  refresh is manual in the current wave and the mechanization follow-on is
  recorded in `TASKS.md`

Why the Phase B / recovery support files are still part of this bounded packet:

- this packet's own canonical headers are rendered as
  `Wave ID: \`pager-codex-app-server-provisioning\`` and
  `Task: \`[PIPELINE-AGENT-PAGER]\``
- `phase_b_executor.load_plan_packet()` / `validate_inputs()` consume those
  exact authoritative headers on re-entry, so stripping Markdown backticks is a
  narrow prerequisite for this derived same-wave packet to preserve its
  canonical identity tuple and bridge attribution
- `recovery_gate` is part of the same bounded surface because this packet's
  missing `Phase-A-Lock` header and stale `bridge.lock` were the exact
  structural reasons the dispatcher died instead of retrying Phase B
- this does not create a second task, a second listener surface, or a broader
  startup-hardening packet; it only lets the existing locked packet parse as
  itself

## Regression Coverage

`mu/tests/tools/test_pipeline_agent_pager.py` now adds provisioning-owned
coverage adjacent to the pager adapter:

- missing or malformed `RCX_CODEX_APP_SERVER_URL` port values fail closed
  before any websocket exchange
- non-loopback `RCX_CODEX_APP_SERVER_URL` values fail closed and leave the
  Codex target pending/reportable
- unavailable loopback listeners fail closed, preserve the stored
  `codex_thread_id`, and do not claim delivery

`mu/tests/tools/test_phase_b_executor.py` adds the matching packet-identity
support coverage:

- authoritative `Wave ID` / `Task` headers wrapped in Markdown backticks are
  normalized before canonical identity is recorded
- the normalized `[PIPELINE-AGENT-PAGER]` task header still matches the plain
  routing `task_id`, so same-wave Phase B validation does not reject this
  packet on formatting alone
- `run_phase_b()` now preserves `plan_path` on `validate_inputs` failure so
  recovery can deterministically repair the exact packet that failed

`mu/tests/tools/test_recovery_gate.py` adds the matching dispatcher recovery
coverage:

- missing `Phase-A-Lock` on a Phase B packet now classifies as a deterministic
  Tier 1 repair instead of generic `unknown_error`
- genuine `Phase-A-Lock: UNLOCKED` packets are not auto-upgraded by that
  classifier
- the bounded repair inserts `Phase-A-Lock: LOCKED` and clears a dead
  `.agent_bus/bridge.lock` before retry

The parent transport packet continues to own websocket JSON-RPC sequencing,
accepted-turn `turn.id` requirements, requested-or-created thread-id fallback,
explicit thread-id mismatch rejection, and stale-thread reseed behavior. Those
cases were not re-listed here.

## Validation

Executed:

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_pipeline_agent_pager.py`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py -k 'canonical_identity_headers_strip_markdown_ticks or markdown_wrapped_task_header_matches_plain_routing_task_id or validate_inputs_error_carries_plan_path'`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py -k 'missing_phase_a_lock_validation_error or unlocked_phase_a_lock_not_misclassified_as_missing or missing_phase_a_lock_repaired_and_stale_bridge_lock_cleared'`
- `python3 tools/checks/enforce_l4_execution_contract.py --files mu/tools/executors/phase_b_executor.py mu/tools/executors/recovery_gate.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py reports/control_plane/pager_codex_app_server_provisioning_2026-04-22.md`

Scope notes:

- the recorded `enforce_l4_execution_contract.py` run above covered only the
  Phase B / recovery repair subset named in that command
- the current staged wave also includes `TASKS.md`,
  `mu/tools/observability/pipeline_agent_pager.py`,
  `mu/tests/tools/test_pipeline_agent_pager.py`,
  `reports/control_plane/pager_codex_app_server_transport_2026-04-22.md`, and
  `reports/l4_wave_indicators/pager-codex-app-server-provisioning.json`
- commit-ready staged validation now runs against the full 10-file staged wave
  after the packet text and tracker override were refreshed

Results:

- phase-b executor targeted tests: `3 passed, 289 deselected`
- recovery-gate targeted tests: `3 passed, 899 deselected`
- pager test file: `30 passed`
- subset L4 execution contract: `PASS` (`Wave class: (none)`, `Changed files: 5`,
  `Runtime files: 0`)
- full staged L4 execution contract: `PASS` via `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id pager-codex-app-server-provisioning` (`Wave class: L4_ENABLER`, `Changed files: 10`, `Runtime files: 0`, `FOUNDER_OVERRIDE active — allowing non-structural adjacency`, `FOUNDER_OVERRIDE active — allowing rolling window without STRUCTURAL`)
- docs consistency: `PASS` via `./tools/checks/check_docs_consistency.sh` (`42 passed in 0.59s`, `50 passed in 0.06s`, `8 passed in 0.01s`, `All checks passed. Docs are consistent.`)
