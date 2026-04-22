# Pager Codex App Server Provisioning

Task: `[PIPELINE-AGENT-PAGER]`  
Wave ID: `pager-codex-app-server-provisioning`  
Date: `2026-04-22`  
Status: ACTIVE
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

Current staged corrective follow-up:

- `TASKS.md`
- `reports/control_plane/pager_codex_app_server_provisioning_2026-04-22.md`
- `reports/l4_wave_indicators/pager-codex-app-server-provisioning.json`

Already committed on this branch, but not restaged in the current corrective
follow-up:

- `mu/tests/tools/test_phase_b_executor.py`
- `mu/tests/tools/test_pipeline_agent_pager.py`
- `mu/tests/tools/test_recovery_gate.py`
- `mu/tools/executors/phase_b_executor.py`
- `mu/tools/executors/recovery_gate.py`
- `mu/tools/observability/pipeline_agent_pager.py`
- `reports/control_plane/pager_codex_app_server_transport_2026-04-22.md`

Branch-local implementation anchor:

- local commit `d6cc7b91` (`feat: Phase B implementation for
  pager-codex-app-server-provisioning`) carries the provisioning code/test
  changes listed above
- the current staged follow-up is narrower: it corrects founder-facing packet
  truth, records the newly diagnosed mechanization gap, and refreshes the
  indicator before push

Why `TASKS.md` changed:

- the canonical tracker sync note for this wave was already present before the
  current follow-up
- this staged correction updates the existing `[PIPELINE-AGENT-PAGER]`
  mechanization note with the newly reproduced packet-truth, status-line, and
  handoff-scope drift so the next automation wave is explicitly grounded

Why the indicator artifact changed:

- Step 5 refreshes and restages
  `reports/l4_wave_indicators/pager-codex-app-server-provisioning.json` on each
  commit attempt, so the indicator is part of the current 3-file staged diff

Why the packet changed:

- line 6 no longer claims `supervisor rerun pending` after
  `.scratch/commit_executor_live.log` already recorded `Step 6: supervisor
  COMMIT_GO`
- `Code Truth` and `Validation` now distinguish the earlier branch-local
  implementation commit from the current 3-file corrective follow-up, which is
  the actual staged diff at the commit gate

## Regression Coverage

The provisioning coverage below comes from the already-committed branch-local
implementation anchored at `d6cc7b91`. The current staged corrective follow-up
does not change runtime or test files; it keeps the packet aligned with that
implementation before push.

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

Previously executed for the branch-local implementation already on this branch:

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_pipeline_agent_pager.py`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py -k 'canonical_identity_headers_strip_markdown_ticks or markdown_wrapped_task_header_matches_plain_routing_task_id or validate_inputs_error_carries_plan_path'`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py -k 'missing_phase_a_lock_validation_error or unlocked_phase_a_lock_not_misclassified_as_missing or missing_phase_a_lock_repaired_and_stale_bridge_lock_cleared'`
- `python3 tools/checks/enforce_l4_execution_contract.py --files mu/tools/executors/phase_b_executor.py mu/tools/executors/recovery_gate.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py reports/control_plane/pager_codex_app_server_provisioning_2026-04-22.md`

Executed for the current staged corrective follow-up:

- `python3 tools/checks/enforce_l4_execution_contract.py --files TASKS.md reports/control_plane/pager_codex_app_server_provisioning_2026-04-22.md`
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id pager-codex-app-server-provisioning`
- `./tools/checks/check_docs_consistency.sh`

Results:

- branch-local implementation proofs preserved: phase-b executor targeted tests
  `3 passed, 289 deselected`; recovery-gate targeted tests
  `3 passed, 899 deselected`; pager test file `30 passed`; subset L4 execution
  contract `PASS` (`Wave class: (none)`, `Changed files: 5`, `Runtime files: 0`)
- current staged corrective follow-up: local file-scoped L4 `PASS` for
  `TASKS.md` + this packet (`Wave class: (none)`, `Changed files: 2`,
  `Runtime files: 0`)
- current staged corrective follow-up: staged L4 `PASS` via
  `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id pager-codex-app-server-provisioning`
  (`Wave class: L4_ENABLER`, `Changed files: 3`, `Runtime files: 0`,
  `FOUNDER_OVERRIDE active — allowing non-structural adjacency`,
  `FOUNDER_OVERRIDE active — allowing rolling window without STRUCTURAL`)
- current staged corrective follow-up: docs consistency `PASS` via
  `./tools/checks/check_docs_consistency.sh` (`42 passed in 0.68s`,
  `50 passed in 0.06s`, `8 passed in 0.01s`, `All checks passed. Docs are consistent.`)
