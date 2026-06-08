# Harden Js Parity Evidence Restore Isolation 2026-06-08

Date: 2026-06-08
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: harden-js-parity-evidence-restore-isolation-2026-06-08
Class: L4_ENABLER
Phase-A-Lock: LOCKED
Purpose: GOAL: fix the audit_fast parallel-load test flakiness at its ROOT by ISOLATION, with NO masking. PINNED ROOT CAUSE (reproduced, not conjecture): the wave-evidence tests in mu/tests/tools/test_meta_bridge_supervisor.py exercise the pre-commit supervisor's wave_evidence gate against the REAL repository root. The test helper `_run_validation_gates_for_wave_evidence` defaults its `repo_root` parameter to the live REPO_ROOT, and several `TestWaveEvidenceGate` tests call it WITHOUT an isolated repo_root (the matching-declared-and-provided-shell-command test, the marker-text-preservation test, the nonzero-forces-needs-phase-b test, and the non-control-surface-package test). When the tracker-declared and package evidence_command match, `meta_bridge_supervisor.run_validation_gates` invokes `_run_wave_evidence_with_restore(repo_root, ...)`, whose `_restore_worktree_snapshots` performs unlink + shutil.copyfile of EVERY tracked file in repo_root (enumerated by `git ls-files`) -- including mu/host/js/core/seed_loader.js and mu/host/js/eval_step.js -- and acquires repo_root's meta_bridge.lock. Run against the live worktree under `pytest -n auto`, this (a) transiently unlinks the JS source files so any concurrent node-spawning test fails with `node:fs ENOENT` (tests/parity/test_exhaustion_parity.py and the l4_gates JS-parity helpers), (b) leaves the repo mid-restore so concurrent repo-state checkers fail (tests/tools/test_docs_sync_report.py, tests/tools/test_check_host_authority_inventory_ratchet.py, tests/structural/test_subtree_root_guard.py), and (c) makes the wave-evidence tests themselves fail with `MetaBridgeError: Another meta-bridge supervisor is running` from contending on REPO_ROOT's lock. That is the observed 'a different test fails each parallel run, all pass standalone' flakiness. EVIDENCE (reproduced): `PYTHONHASHSEED=0 pytest -n auto mu/tests/tools/test_meta_bridge_supervisor.py::TestWaveEvidenceGate` fails 3 tests with MetaBridgeError on REPO_ROOT's lock; an inode poll over mu/host/js during `pytest -n auto mu/tests/tools` catches seed_loader.js+eval_step.js unlink+recreate (new inode, identical bytes); structural-alone and l4_gates-alone -n auto show ZERO swaps (the writer is in mu/tests/tools, not production). The existing concurrency test `test_evidence_restore_preserves_unstaged_tracked_and_preexisting_untracked` ALREADY uses an isolated tmp git repo (git init + config + commit one tracked file, passing repo_root=that repo) -- that is the correct pattern; #54 applied it to that one test but the sibling TestWaveEvidenceGate tests were missed. This is a TEST-HARNESS isolation bug, not a production bug: `_run_wave_evidence_with_restore` correctly restores whatever repo_root it is given; the defect is the TEST passing the live REPO_ROOT.

## Scope

In scope -- test-harness only, under `mu/tests/**`:

- `mu/tests/tools/test_meta_bridge_supervisor.py` -- the `TestWaveEvidenceGate` tests and the `_run_validation_gates_for_wave_evidence` helper that drives them. This is the writer that runs the supervisor wave_evidence restore against the live REPO_ROOT.
- A shared per-test tmp-git-repo fixture/helper (in that test module or an appropriate `mu/tests/**` conftest), built to mirror the existing isolated pattern in `test_evidence_restore_preserves_unstaged_tracked_and_preexisting_untracked`.
- Any additional `mu/tests/**` caller of `run_validation_gates`, `run_meta_bridge`, or `_run_wave_evidence_with_restore` that the Work-item-4 audit surfaces as passing the live REPO_ROOT together with a matching `evidence_command`.

- `reports/deferred/non_blocking/harden-js-parity-evidence-restore-isolation-2026-06-08_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Bounded, concrete tasks (derived from the REQUIRED FIX in the governing directive; the blocking findings do not prove any item is already landed, and the tracker `progress_proof_before` confirms the flake is still live, so all items remain pending):

1. **Stop the live-REPO_ROOT default.** In `mu/tests/tools/test_meta_bridge_supervisor.py`, change `_run_validation_gates_for_wave_evidence` so its `repo_root` parameter no longer defaults to the live REPO_ROOT -- require an isolated repo, or default to a freshly-created per-call tmp git repo (auto-cleaned via a `tmp_path`-based fixture). No wave-evidence test may run the restore against the live worktree.
2. **Add a shared isolated-repo fixture/helper.** Provide a per-test fixture/helper that builds a minimal tmp git repo (`git init` + user config + commit one tracked file), mirroring the existing `test_evidence_restore_preserves_unstaged_tracked_and_preexisting_untracked` pattern, with its own `repo_root` and its own `meta_bridge.lock`.
3. **Route the four omitting tests through it.** Wire the `TestWaveEvidenceGate` tests that currently omit `repo_root` -- the matching-declared-and-provided-shell-command test, the marker-text-preservation test, the nonzero-forces-needs-phase-b test, and the non-control-surface-package test -- through the isolated fixture. Preserve every existing assertion; the tests must still run the real wave_evidence gate logic, only against the isolated repo.
4. **Audit and isolate every other live-REPO_ROOT caller.** Sweep `mu/tests/**` for every caller of `run_validation_gates`, `run_meta_bridge`, and `_run_wave_evidence_with_restore` that passes the live REPO_ROOT together with a matching `evidence_command`; isolate each one the same way, assertions preserved.
5. **Prove isolation, no masking.** Run the evidence_command (`TestWaveEvidenceGate` under `-n auto`) plus `pytest -n auto mu/tests/tools` and the JS-heavy parity/l4_gates set repeatedly (>=10 iterations), confirming zero `MetaBridgeError`, zero transient failures, and zero `mu/host/js` inode swaps; collect the wave indicator artifact.

## Constraints

NOT in scope (hard boundaries):

- Do **NOT** modify the restore logic in `mu/tools/agents/meta_bridge_supervisor.py` (`_run_wave_evidence_with_restore` / `_restore_worktree_snapshots`). The production restore is correct for whatever repo_root it is given; the defect is the TEST passing the live REPO_ROOT.
- Do **NOT** touch any runtime dir: `mu/host`, `mu/substrate`, `mu/closures`, `mu/bridge`, `mu/programs`, `rcx_pi/selfhost`, `mu/tools/compilers`.
- **NO masking.** Do not add retry-to-pass, `pytest.mark.skip`, `xfail`, `try/except`-swallow, or move any flaky test to `'expected'`. The fix MUST be isolation only; every pre-existing assertion preserved (a real probabilistic production bug must still be catchable -- masking would hide exactly that).
- Change set is limited to `mu/tests/**` (test files + conftest/fixtures) only.

## Stop conditions

- If a SECOND path is discovered that mutates the live worktree from **production code** (not the test harness), STOP and report it as a blocking finding for a separate runtime wave -- do not mask it and do not fix it inside this test-only wave.
- If isolating any test would require dropping or weakening an assertion, STOP -- the real probabilistic production bug must remain catchable; surface it rather than proceed.
- If the only way to make a test pass is a forbidden masking construct, STOP -- masking is non-negotiably out of bounds.

## Acceptance criteria

- `PYTHONHASHSEED=0 python3 -m pytest -q -p no:cacheprovider -n auto mu/tests/tools/test_meta_bridge_supervisor.py::TestWaveEvidenceGate` passes with zero `MetaBridgeError` (this is the tracker-declared `evidence_command`).
- `pytest -n auto mu/tests/tools` plus the JS-heavy parity/l4_gates set run repeatedly (>=10 iterations) with zero transient failures and zero `mu/host/js` inode swaps.
- Every pre-existing assertion preserved; zero masking constructs present (no skip / xfail / retry-to-pass / try-except-swallow / move-to-`'expected'`).
- No change to runtime dirs and no change to the restore logic in `mu/tools/agents/meta_bridge_supervisor.py`.
- Wave indicator artifact collected at `reports/l4_wave_indicators/harden-js-parity-evidence-restore-isolation-2026-06-08.json`.

## Grounding / Authorization

- **Task:** `[NEXT-CODEX-POST-REDTEAM]` -- UNPARKED, founder-authorized (per TASKS.md). Tracked parent packet: `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`. This wave is a bounded downstream test-harness-isolation item under that still-open queue.
- **Governing packet (this file):** `reports/control_plane/harden_js_parity_evidence_restore_isolation_2026-06-08.md`.
- **Authorizing tracker note:** TASKS.md tracker note (2026-06-08, `harden-js-parity-evidence-restore-isolation-2026-06-08`).
- **Class:** L4_ENABLER. **target_gate_id:** G8.
- **FOUNDER_OVERRIDE:harden-js-parity-evidence-restore-isolation-2026-06-08** (wave-bound same-wave override, mirrors the tracker note; lets commit automation derive the override mechanically).
- **Authorization: standing pipeline-bug-fix authorization** -- this wave fixes audit_fast `-n auto` flakiness that strands pipeline waves at Step-11 pre-push (a pipeline-bug fix), test-harness only, every assertion preserved, no masking.
- **evidence_command:** `PYTHONHASHSEED=0 python3 -m pytest -q -p no:cacheprovider -n auto mu/tests/tools/test_meta_bridge_supervisor.py::TestWaveEvidenceGate`.
- **primary_blocker_class:** INTEGRATION. **primary_invariant_id:** INV_TYPED_FAIL_CLOSED_OUTCOMES.
- **indicator_artifact_ref:** `reports/l4_wave_indicators/harden-js-parity-evidence-restore-isolation-2026-06-08.json`.
- **indicator_collection_command:** `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id harden-js-parity-evidence-restore-isolation-2026-06-08 --output reports/l4_wave_indicators/harden-js-parity-evidence-restore-isolation-2026-06-08.json`.
- **bootstrap_endgame_policy:** SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. **boot0_track_id:** V1. **boot0_progress_state:** HOLD.

## Request from Post-Merge Supervisor

GOAL: fix the audit_fast parallel-load test flakiness at its ROOT by ISOLATION, with NO masking. PINNED ROOT CAUSE (reproduced, not conjecture): the wave-evidence tests in mu/tests/tools/test_meta_bridge_supervisor.py exercise the pre-commit supervisor's wave_evidence gate against the REAL repository root. The test helper `_run_validation_gates_for_wave_evidence` defaults its `repo_root` parameter to the live REPO_ROOT, and several `TestWaveEvidenceGate` tests call it WITHOUT an isolated repo_root (the matching-declared-and-provided-shell-command test, the marker-text-preservation test, the nonzero-forces-needs-phase-b test, and the non-control-surface-package test). When the tracker-declared and package evidence_command match, `meta_bridge_supervisor.run_validation_gates` invokes `_run_wave_evidence_with_restore(repo_root, ...)`, whose `_restore_worktree_snapshots` performs unlink + shutil.copyfile of EVERY tracked file in repo_root (enumerated by `git ls-files`) -- including mu/host/js/core/seed_loader.js and mu/host/js/eval_step.js -- and acquires repo_root's meta_bridge.lock. Run against the live worktree under `pytest -n auto`, this (a) transiently unlinks the JS source files so any concurrent node-spawning test fails with `node:fs ENOENT` (tests/parity/test_exhaustion_parity.py and the l4_gates JS-parity helpers), (b) leaves the repo mid-restore so concurrent repo-state checkers fail (tests/tools/test_docs_sync_report.py, tests/tools/test_check_host_authority_inventory_ratchet.py, tests/structural/test_subtree_root_guard.py), and (c) makes the wave-evidence tests themselves fail with `MetaBridgeError: Another meta-bridge supervisor is running` from contending on REPO_ROOT's lock. That is the observed 'a different test fails each parallel run, all pass standalone' flakiness. EVIDENCE (reproduced): `PYTHONHASHSEED=0 pytest -n auto mu/tests/tools/test_meta_bridge_supervisor.py::TestWaveEvidenceGate` fails 3 tests with MetaBridgeError on REPO_ROOT's lock; an inode poll over mu/host/js during `pytest -n auto mu/tests/tools` catches seed_loader.js+eval_step.js unlink+recreate (new inode, identical bytes); structural-alone and l4_gates-alone -n auto show ZERO swaps (the writer is in mu/tests/tools, not production). The existing concurrency test `test_evidence_restore_preserves_unstaged_tracked_and_preexisting_untracked` ALREADY uses an isolated tmp git repo (git init + config + commit one tracked file, passing repo_root=that repo) -- that is the correct pattern; #54 applied it to that one test but the sibling TestWaveEvidenceGate tests were missed. REQUIRED FIX (isolation, integrity-preserving): make EVERY test that exercises the wave_evidence gate / `_run_wave_evidence_with_restore` operate on a PER-TEST isolated tmp git repo (its own repo_root and its own meta_bridge.lock), NEVER the live REPO_ROOT. Concretely: (1) stop `_run_validation_gates_for_wave_evidence` from defaulting repo_root to REPO_ROOT -- require an isolated repo or default to a freshly-created per-call tmp git repo, auto-cleaned via a tmp_path-based fixture; (2) provide a shared fixture/helper that builds a minimal tmp git repo (git init + user config + commit one tracked file), mirroring the existing test_evidence_restore_preserves_... test; (3) route the TestWaveEvidenceGate tests that currently omit repo_root through it; (4) AUDIT every other caller of `run_validation_gates`, `run_meta_bridge`, and `_run_wave_evidence_with_restore` across mu/tests/** for any that pass the live REPO_ROOT together with a matching evidence_command, and isolate those too. PRESERVE every assertion -- the tests must still run the real wave_evidence gate logic, only against the isolated repo. HARD CONSTRAINT (non-negotiable): NO masking. Do NOT add retry-to-pass, pytest.mark.skip, xfail, try/except-swallow, or move any flaky test to 'expected'. The fix MUST be isolation only; every assertion preserved (a real probabilistic production bug must still be caught -- masking would hide exactly that). SCOPE: mu/tests/** (test files + conftest/fixtures) ONLY. This is a TEST-HARNESS isolation bug, not a production bug: `_run_wave_evidence_with_restore` correctly restores whatever repo_root it is given; the defect is the TEST passing the live REPO_ROOT. Do NOT modify the restore logic in mu/tools/agents/meta_bridge_supervisor.py and do NOT touch any runtime dir (mu/host, mu/substrate, mu/closures, mu/bridge, mu/programs, rcx_pi/selfhost, mu/tools/compilers). If you discover a SECOND path that mutates the live worktree from production code, STOP and report it as a blocking finding for a separate runtime wave -- do not mask it. PROVE: `PYTHONHASHSEED=0 pytest -n auto mu/tests/tools/test_meta_bridge_supervisor.py::TestWaveEvidenceGate` passes with zero MetaBridgeError, and `pytest -n auto mu/tests/tools` plus the JS-heavy parity/l4_gates set run repeatedly (>=10 iterations) with zero transient failures and zero mu/host/js inode swaps, every assertion preserved, zero masking constructs. L4_ENABLER.

Routed next-candidate:
harden-js-parity-evidence-restore-isolation-2026-06-08

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `harden-js-parity-evidence-restore-isolation-2026-06-08`
- Active packet: `reports/control_plane/harden_js_parity_evidence_restore_isolation_2026-06-08.md`
- Indicator artifact: `reports/l4_wave_indicators/harden-js-parity-evidence-restore-isolation-2026-06-08.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_meta_bridge_supervisor.py`
  - `reports/control_plane/harden_js_parity_evidence_restore_isolation_2026-06-08.md`
  - `reports/deferred/non_blocking/harden-js-parity-evidence-restore-isolation-2026-06-08_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/harden-js-parity-evidence-restore-isolation-2026-06-08.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `harden-js-parity-evidence-restore-isolation-2026-06-08`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/harden-js-parity-evidence-restore-isolation-2026-06-08_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `harden-js-parity-evidence-restore-isolation-2026-06-08`
- Active packet: `reports/control_plane/harden_js_parity_evidence_restore_isolation_2026-06-08.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `311dbf002724e003820f825379bb141f59dbd5a9c6d442db9ce4b641a3134598`
- Indicator artifact: `reports/l4_wave_indicators/harden-js-parity-evidence-restore-isolation-2026-06-08.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_meta_bridge_supervisor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/harden_js_parity_evidence_restore_isolation_2026-06-08.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/harden-js-parity-evidence-restore-isolation-2026-06-08.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_meta_bridge_supervisor.py`
  - `reports/control_plane/harden_js_parity_evidence_restore_isolation_2026-06-08.md`
  - `reports/deferred/non_blocking/harden-js-parity-evidence-restore-isolation-2026-06-08_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/harden-js-parity-evidence-restore-isolation-2026-06-08.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
