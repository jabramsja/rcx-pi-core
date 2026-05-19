<!-- DOC_STATUS: ACTIVE -->
# N3 Seed Migration Follow-Up: Tool Placement And Package-Class Repair

Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-seed-migration-followup-tool-placement-pipeline-repair-2026-05-18
Status: commit-ready follow-up
Class: L4_ENABLER
Authorization: FOUNDER_OVERRIDE:n3-seed-migration-followup-tool-placement-pipeline-repair-2026-05-18
Authorization: authorized control-surface L4_ENABLER for bounded pipeline package repair

## Scope

This is the post-structural follow-up for
`n3-projection-loader-seed-migration-integrity-chain-2026-05-14`.

The parent structural commit already carries the runtime/substrate seed-loader
changes. This follow-up has zero runtime/substrate changed files in its staged
diff, so the commit package is intentionally `L4_ENABLER`.

In scope:

- Move the bounded migration tool from `mu/tools/seed_binary_migration.py` to
  `mu/tools/util/seed_binary_migration.py` so the tools-root structural guard
  stays closed.
- Update parity and boundary tests to import and execute the tool from the
  allowed `mu/tools/util/` location.
- Refresh the parent packet/deferred/indicator surfaces so they reference the
  allowed tool path.
- Bind the follow-up package to `L4_ENABLER` authority because the staged diff
  contains no runtime/substrate delta.

Out of scope:

- Runtime loader behavior changes.
- Production binary-default flips.
- New host authority or host semantics.
- Reopening the already-created parent structural commit.

## Evidence

- `git diff --cached --name-status` includes
  `R100 mu/tools/seed_binary_migration.py -> mu/tools/util/seed_binary_migration.py`.
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-projection-loader-seed-migration-integrity-chain-2026-05-14 --wave-class L4_STRUCTURAL`
  exits `1` with `Runtime files: 0`.
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-projection-loader-seed-migration-integrity-chain-2026-05-14 --wave-class L4_ENABLER`
  exits `0` with `L4_ENABLER compliant`.
- `PYTHONHASHSEED=0 python3 -m pytest -q tests/structural/test_subtree_root_guard.py::TestToolsRootGuard::test_no_unallowed_root_files mu/tests/parity/test_seed_loading_parity.py::TestProjectionLoaderSeedMigrationIntegrityChain::test_seed_binary_migration_tool_generate_validate_round_trip mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py::TestProjectionLoaderSeedMigrationIntegrityChainBoundary::test_binary_migration_integrity_chain_not_production_loader --tb=short`
  exits `0` with `3 passed`.

## Closeout Criteria

- The tools-root guard passes with no unallowed `mu/tools/` root script.
- Focused parity and boundary tests pass from the new utility path.
- Staged L4 validation passes as `L4_ENABLER`.
- The parent structural packet continues to state that production JSON loading
  remains the default and binary migration remains a bounded sidecar/tooling
  surface.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-seed-migration-followup-tool-placement-pipeline-repair-2026-05-18`
- Active packet: `reports/control_plane/n3-seed-migration-followup-tool-placement-pipeline-repair-2026-05-18.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `05761538880af5d0b0ec5ca5222fc685bbd6f831616d00cdaf8cd6cb6d240144`
- Indicator artifact: `reports/l4_wave_indicators/n3-seed-migration-followup-tool-placement-pipeline-repair-2026-05-18.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q tests/structural/test_subtree_root_guard.py::TestToolsRootGuard::test_no_unallowed_root_files mu/tests/parity/test_seed_loading_parity.py::TestProjectionLoaderSeedMigrationIntegrityChain::test_seed_binary_migration_tool_generate_validate_round_trip mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py::TestProjectionLoaderSeedMigrationIntegrityChainBoundary::test_binary_migration_integrity_chain_not_production_loader --tb=short && python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-seed-migration-followup-tool-placement-pipeline-repair-2026-05-18 --output reports/l4_wave_indicators/n3-seed-migration-followup-tool-placement-pipeline-repair-2026-05-18.json && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-seed-migration-followup-tool-placement-pipeline-repair-2026-05-18 --wave-class L4_ENABLER`.
- Evidence delta: (1) The parent structural commit for `n3-projection-loader-seed-migration-integrity-chain-2026-05-14` already carries runtime/substrate loader changes, while this staged follow-up has `Runtime files: 0`. (2) The migration tool moved from `mu/tools/seed_binary_migration.py` to `mu/tools/util/seed_binary_migration.py` so the tools-root guard remains closed. (3) Parity and boundary tests execute the tool from the allowed utility path while production JSON loaders remain the default.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-seed-migration-followup-tool-placement-pipeline-repair-2026-05-18.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
  - `mu/tests/parity/test_seed_loading_parity.py`
  - `mu/tools/util/seed_binary_migration.py`
  - `reports/control_plane/n3-projection-loader-seed-migration-integrity-chain-2026-05-14_2026-05-18.md`
  - `reports/control_plane/n3-seed-migration-followup-tool-placement-pipeline-repair-2026-05-18.md`
  - `reports/deferred/non_blocking/n3-projection-loader-seed-migration-integrity-chain-2026-05-14_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-projection-loader-seed-migration-integrity-chain-2026-05-14.json`
  - `reports/l4_wave_indicators/n3-seed-migration-followup-tool-placement-pipeline-repair-2026-05-18.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
