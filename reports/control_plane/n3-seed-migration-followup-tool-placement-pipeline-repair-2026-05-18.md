<!-- DOC_STATUS: ACTIVE -->
# N3 Seed Migration Follow-Up: Tool Placement And Package-Class Repair

Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-seed-migration-followup-tool-placement-pipeline-repair-2026-05-18
Status: committed follow-up scope correction
Class: L4_STRUCTURAL
Authorization: FOUNDER_OVERRIDE:n3-seed-migration-followup-tool-placement-pipeline-repair-2026-05-18
Authorization: corrected committed-package scope: structural runtime review required when runtime/substrate seed-loader files are present

## Scope

This is the post-structural follow-up for
`n3-projection-loader-seed-migration-integrity-chain-2026-05-14`.

The parent structural commit carried the intended runtime/substrate seed-loader
work, but the committed follow-up package is not zero-runtime. Reviewer
reproduction for committed package `a52e4eb` shows
`git diff-tree --name-only a52e4eb` includes both
`mu/host/js/core/seed_loader.js` and
`mu/host/python/rcx_pi/selfhost/seed_integrity.py` alongside the tool, test,
and report files. The committed package therefore requires `L4_STRUCTURAL`
treatment; the earlier `L4_ENABLER` premise was staged-snapshot-only and is not
valid committed-package scope proof.

In scope:

- Move the bounded migration tool from `mu/tools/seed_binary_migration.py` to
  `mu/tools/util/seed_binary_migration.py` so the tools-root structural guard
  stays closed.
- Update parity and boundary tests to import and execute the tool from the
  allowed `mu/tools/util/` location.
- Refresh the parent packet/deferred/indicator surfaces so they reference the
  allowed tool path.
- Correct the follow-up package record so the committed runtime/substrate
  seed-loader deltas are in scope for structural review.

Out of scope:

- Additional runtime loader behavior beyond the committed seed-loader deltas.
- Production binary-default flips.
- New host authority or host semantics.
- Reopening the already-created parent structural commit.

## Evidence

- Committed-package review evidence reports
  `git diff-tree --name-only a52e4eb` includes:
  - `mu/host/js/core/seed_loader.js`
  - `mu/host/python/rcx_pi/selfhost/seed_integrity.py`
- The previously recorded `git diff --cached --name-status` and
  `enforce_l4_execution_contract.py --staged ... --wave-class L4_ENABLER`
  evidence was a staged-snapshot check only. It cannot justify committed-package
  `L4_ENABLER` classification once the committed diff includes runtime files.
- The focused tool, parity, and boundary tests previously recorded still support
  the tool-placement repair, but they do not replace structural review of the
  committed runtime/substrate seed-loader deltas.

## Closeout Criteria

- The tools-root guard passes with no unallowed `mu/tools/` root script.
- Focused parity and boundary tests pass from the new utility path.
- Committed-package L4 review treats the wave as `L4_STRUCTURAL` whenever
  runtime/substrate files are present.
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
- Evidence command: superseded for committed-package classification. The prior
  staged-only command ended with
  `tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-seed-migration-followup-tool-placement-pipeline-repair-2026-05-18 --wave-class L4_ENABLER`,
  but committed-package review must use the committed diff and structural
  classification when runtime/substrate files are present.
- Evidence delta: (1) The committed package `a52e4eb` includes runtime/substrate
  seed-loader files, so `Runtime files: 0` is not valid committed-package
  evidence. (2) The migration tool moved from `mu/tools/seed_binary_migration.py`
  to `mu/tools/util/seed_binary_migration.py` so the tools-root guard remains
  closed. (3) Parity and boundary tests execute the tool from the allowed
  utility path while production JSON loaders remain the default. (4) Structural
  review remains required for the committed runtime/substrate deltas.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-seed-migration-followup-tool-placement-pipeline-repair-2026-05-18.json`
- Corrected committed-package runtime/substrate files:
  - `mu/host/js/core/seed_loader.js`
  - `mu/host/python/rcx_pi/selfhost/seed_integrity.py`
- Previously recorded staged files, not sufficient for committed-package
  classification:
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
