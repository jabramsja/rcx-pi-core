# Vm Cutover Coverage Trace Prepush Repair 2026-05-12

Date: 2026-05-12
Status: Routed - commit repair in progress
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: vm-cutover-coverage-trace-prepush-repair-2026-05-12
Class: L4_ENABLER
Category: control-plane pipeline repair
Target gate: G8
Unblocks wave: vm-cutover-coverage-trace-implementation-2026-05-12

## Purpose

Repair the pre-push failure on the VM cutover coverage trace branch without
adding runtime or host semantic debt. The structural implementation commit is
already local; this repair is limited to the tracked config drift and the
mechanical dispatcher guard that prevents the same drift from recurring.

## Reproduced Evidence

- Pre-push-fast rejected the previous package at
  `tests/tools/test_executor_dispatch.py::TestDispatcherConfig::test_load_default_config`.
- The guarded assertion is `config["timeouts"]["commit_executor"] == 3600`.
- The tracked file had drifted to `"commit_executor": 5400`.
- Direct repair evidence after patch:
  `PYTHONHASHSEED=0 python3 -m pytest -q tests/tools/test_executor_dispatch.py::TestDispatcherConfig::test_load_default_config tests/tools/test_executor_dispatch.py::TestRecoveryGateWiring::test_tier2_commit_timeout_uses_correct_key tests/tools/test_executor_dispatch.py::TestRecoveryGateWiring::test_tier2_commit_timeout_override_stays_in_memory tests/tools/test_executor_dispatch.py::TestRecoveryGateWiring::test_apply_overrides_writes_to_disk --tb=short`
  exits `0` with `4 passed in 0.07s`.

## Scope

- `TASKS.md` - detector-visible repair tracker authority and evidence binding.
- `reports/control_plane/vm-cutover-coverage-trace-implementation-2026-05-12_2026-05-12.md` - predecessor packet append naming the bounded pre-push repair.
- `reports/control_plane/vm-cutover-coverage-trace-prepush-repair-2026-05-12.md` - governing repair packet.
- `reports/l4_wave_indicators/vm-cutover-coverage-trace-prepush-repair-2026-05-12.json` - same-wave indicator artifact.
- `mu/tools/executors/executor_config.json` - restore `timeouts.commit_executor` default to `3600`.
- `mu/tools/executors/executor_dispatch.py` - keep dispatcher-owned `commit_executor` timeout recovery overrides in memory rather than writing the tracked config default.
- `mu/tests/tools/test_executor_dispatch.py` - regression coverage for in-memory `commit_executor` timeout recovery and default-config drift.

## Constraints

- Do not edit Claude-related files.
- Do not touch runtime, Stage0, seed, scheduler, registry, parity, production `/mu`, transparent JS Proxy provenance, N3 broad host-surface boundary, pager, autoping, recovery, or commit executor surfaces.
- Do not change the default `commit_executor` timeout away from `3600`.
- Do not write `commit_executor` recovery timeout overrides to tracked config; the dispatcher enforces that subprocess timeout from its in-memory retry config.
- Do not add Python or JS host semantics.

## Acceptance Criteria

- `mu/tools/executors/executor_config.json` keeps `timeouts.commit_executor` at `3600`.
- `RCX_RECOVERY_TIMEOUT_KEY=commit_executor` updates the retry config in memory and leaves disk config unchanged.
- Existing disk-write behavior for non-dispatcher-owned recovery overrides is preserved.
- Same-wave tracker note, packet, and indicator artifact are staged for the repair wave.
- Required validation before commit executor closeout passes:
  - `PYTHONHASHSEED=0 python3 -m pytest -q tests/tools/test_executor_dispatch.py::TestDispatcherConfig::test_load_default_config tests/tools/test_executor_dispatch.py::TestRecoveryGateWiring::test_tier2_commit_timeout_uses_correct_key tests/tools/test_executor_dispatch.py::TestRecoveryGateWiring::test_tier2_commit_timeout_override_stays_in_memory tests/tools/test_executor_dispatch.py::TestRecoveryGateWiring::test_apply_overrides_writes_to_disk --tb=short`
  - `./tools/checks/check_docs_consistency.sh`
  - `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
  - `python3 tools/checks/check_host_authority_inventory_ratchet.py`
  - `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id vm-cutover-coverage-trace-prepush-repair-2026-05-12`

## Authorization

FOUNDER_OVERRIDE:vm-cutover-coverage-trace-prepush-repair-2026-05-12

Founder-facing handoff: Questions? Concerns? Thoughts? -- Think hard

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `vm-cutover-coverage-trace-prepush-repair-2026-05-12`
- Active packet: `reports/control_plane/vm-cutover-coverage-trace-prepush-repair-2026-05-12.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `2976627c1110712ba1fe61c1ee5deff5ab781ea3e8b44d46665557100d39c8a6`
- Indicator artifact: `reports/l4_wave_indicators/vm-cutover-coverage-trace-prepush-repair-2026-05-12.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: (1) Routed commit handoff scopes 5 wave-owned file(s). (2) Evidence gate exercises 1 wave-owned test module(s). (3) Indicator artifact binds the wave to reports/l4_wave_indicators/vm-cutover-coverage-trace-prepush-repair-2026-05-12.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/vm-cutover-coverage-trace-prepush-repair-2026-05-12.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `reports/control_plane/vm-cutover-coverage-trace-prepush-repair-2026-05-12.md`
  - `reports/l4_wave_indicators/vm-cutover-coverage-trace-prepush-repair-2026-05-12.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
