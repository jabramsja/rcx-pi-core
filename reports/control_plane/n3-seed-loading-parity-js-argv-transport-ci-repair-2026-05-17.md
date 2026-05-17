# N3 Seed Loading Parity JS Argv Transport CI Repair

Date: 2026-05-17
Status: READY FOR COMMIT EXECUTOR
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-seed-loading-parity-js-argv-transport-ci-repair-2026-05-17
Class: L4_ENABLER
Lane: control-surface CI/test scaffold
Authorization: authorized control-surface L4_ENABLER; standing pipeline-bug-fix authorization for PR #976 CI wait failure.
Target branch: jabramsja/n3-projection-loader-numeric-domain-policy-2026-05-14
Governing repair packet: reports/control_plane/n3-seed-loading-parity-js-argv-transport-ci-repair-2026-05-17.md

## Purpose

Repair the PR #976 CI failure that blocked the already-committed N3 seed-image
numeric-domain structural wave. This is a test-harness transport repair only.
It does not change production Python or JavaScript seed loaders, seed-image
validation semantics, projection semantics, bootstrap primitives, or Mu runtime
behavior.

This packet also authorizes the minimal commit_executor root fix required to
route this repair through the pipeline: a distinct standalone L4_ENABLER repair
wave must be able to land on the existing PR branch when, and only when, the
same-wave packet declares control-surface authorization.

## Root Cause Evidence

- Commit executor reached `wait_ci` on PR #976 after validate, stage, indicator,
  supervisor, pre-commit, commit, pre-push, push, and PR creation steps.
- `.scratch/recovery_agent_n3-projection-loader-numeric-domain-policy-2026-05-14-wait-ci-1.txt`
  records failed required checks `test (CI)` and `green-gate (rcx-green-gate)`.
- The recorded CI excerpt names
  `tests/parity/test_seed_loading_parity.py::TestProductionLoaderBoundaryParity::test_canonical_seed_corpus_loads_integer_images_in_both_boundaries`
  and reports `OSError: [Errno 7] Argument list too long: 'node'`.
- The failing transport was in the parity test harness. The JS probe embedded
  seed bytes in the `node -e` source argument as a Python-expanded byte array.
  That made the command argv depend on canonical seed corpus size instead of a
  bounded script plus stdin payload.
- The first same-branch repair commit attempt used the original structural wave
  id and commit supervisor returned `NEEDS_PHASE_B` because the package
  declared `wave_class=L4_ENABLER` while TASKS and the packet declare the
  original wave `L4_STRUCTURAL`.
- A distinct repair wave is therefore required, but `commit_executor.py`
  accepted explicit target branches only when the branch suffix equaled the
  same wave id or a same-wave restart suffix. The root pipeline fix is to reuse
  existing control-surface packet authorization for standalone L4_ENABLER
  same-PR repair branches.

## Scope

Allowed write set for this repair:

- mu/tests/parity/test_seed_loading_parity.py
- mu/tools/executors/commit_executor.py
- mu/tests/tools/test_commit_executor_receipt.py
- TASKS.md, only for this same-wave L4_ENABLER tracker sync note
- reports/control_plane/n3-seed-loading-parity-js-argv-transport-ci-repair-2026-05-17.md
- reports/l4_wave_indicators/n3-seed-loading-parity-js-argv-transport-ci-repair-2026-05-17.json

No runtime, substrate, host loader, seed corpus, registry, bootstrap, or Mu
program files are in scope. The commit_executor change is pipeline routing
mechanization only.

## Implementation

The parity test helpers keep the existing `node -e` execution shape for the
bounded script, but move seed bytes and test parameters into stdin JSON:

- Python encodes seed bytes with base64.
- Node reads stdin with `fs.readFileSync(0, 'utf8')`.
- Node reconstructs bytes with `Buffer.from(input.seedBytesBase64, 'base64')`.
- The existing `loadVerifiedSeedImage` entry point remains the only JS loader
  under test.

This removes argv-size dependence from the parity probe without widening host
semantic authority.

The commit_executor validator now accepts a non-wave target branch only for a
standalone L4_ENABLER handoff when the indexed same-wave control-plane packet
declares control-surface authorization. Existing malformed, cross-prefix, and
target branches without packet authority continue to fail validation.

## Constraints

- Do not alter `mu/host/js/core/seed_loader.js`.
- Do not alter `mu/host/python/rcx_pi/selfhost/seed_integrity.py`.
- Do not add host interpretation, parser fallback, or semantic recovery logic.
- Do not claim this moves JSON seed-image validation into Mu.
- Do not change the original structural wave indicator artifact.
- Do not use this repair to relabel the original structural wave as L4_ENABLER.
- Do not make generic branch override support. The branch exception is limited
  to authorized standalone control-surface L4_ENABLER repair handoffs.

## Acceptance

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_seed_loading_parity.py::TestProductionLoaderBoundaryParity::test_canonical_seed_corpus_loads_integer_images_in_both_boundaries --tb=short` passes.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/engine/test_seed_integrity.py mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py mu/tests/parity/test_seed_loading_parity.py --tb=short` passes.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestWaveIdBounds::test_validate_handoff_accepts_authorized_standalone_same_pr_repair_target_branch mu/tests/tools/test_commit_executor_receipt.py::TestWaveIdBounds::test_validate_handoff_rejects_unauthorized_standalone_same_pr_repair_target_branch --tb=short` passes.
- `git diff --check` passes.
- The staged package contains no production loader diff.
- The same-wave tracker note and indicator artifact bind this repair as
  `Class: L4_ENABLER`.

## Proof Limits

This repair proves only that the JS parity probe can pass large canonical seed
bytes without exceeding argv limits. It does not prove new Mu self-hosting
coverage, D010 closure, N3 closure, binary/TLV readiness, or movement of JSON
seed-image validation semantics into Mu.

Required override token for this bounded control-surface repair:

FOUNDER_OVERRIDE:n3-seed-loading-parity-js-argv-transport-ci-repair-2026-05-17

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-seed-loading-parity-js-argv-transport-ci-repair-2026-05-17`
- Active packet: `reports/control_plane/n3-seed-loading-parity-js-argv-transport-ci-repair-2026-05-17.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `953ecea4badf72e3433f9decbeb99df7f0360f54ae0d6949fed98c3412c3a1c1`
- Indicator artifact: `reports/l4_wave_indicators/n3-seed-loading-parity-js-argv-transport-ci-repair-2026-05-17.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_seed_loading_parity.py::TestProductionLoaderBoundaryParity::test_canonical_seed_corpus_loads_integer_images_in_both_boundaries --tb=short && PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/engine/test_seed_integrity.py mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py mu/tests/parity/test_seed_loading_parity.py --tb=short && PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestWaveIdBounds --tb=short`.
- Evidence delta: (1) PR #976 required checks recorded OSError Errno 7 Argument list too long node in tests/parity/test_seed_loading_parity.py::TestProductionLoaderBoundaryParity::test_canonical_seed_corpus_loads_integer_images_in_both_boundaries. (2) JS seed-image parity byte probes now pass seed bytes through stdin/base64 instead of embedding byte arrays in node -e argv. (3) commit_executor now allows a non-wave target branch only for standalone L4_ENABLER handoffs whose indexed same-wave control-plane packet declares control-surface authorization; branch override without packet authority fails validation under regression coverage. (4) Production Python/JS seed loaders are unchanged.
- Evidence handles:
  - `ci_failure`: `.scratch/recovery_agent_n3-projection-loader-numeric-domain-policy-2026-05-14-wait-ci-1.txt`
  - `commit_executor_validation`: `47 passed in 11.38s`
  - `indicator`: `reports/l4_wave_indicators/n3-seed-loading-parity-js-argv-transport-ci-repair-2026-05-17.json`
  - `local_seed_suite`: `148 passed in 4.28s`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/parity/test_seed_loading_parity.py`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/n3-seed-loading-parity-js-argv-transport-ci-repair-2026-05-17.md`
  - `reports/l4_wave_indicators/n3-seed-loading-parity-js-argv-transport-ci-repair-2026-05-17.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
