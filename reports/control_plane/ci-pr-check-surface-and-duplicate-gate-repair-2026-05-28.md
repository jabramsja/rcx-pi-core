# CI PR Check Surface And Duplicate Gate Repair 2026-05-28

Date: 2026-05-28
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28
Class: L4_ENABLER
Category: CI/control-plane check-surface enforcement and duplicate gate removal
Lane: control-surface
target_gate_id: G8
Phase-A-Lock: LOCKED
Purpose: Restore `CI/test` to bounded feature-branch feedback, keep `rcx-green-gate/green-gate` as the single authoritative full green-gate runner, and mechanize the expected seven-check PR surface so commit automation cannot merge when GitHub only reports the branch-protection subset.

## Scope

Files and directories in scope:

- Governing packet: `reports/control_plane/ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28.md`
- CI workflows:
  - `.github/workflows/ci.yml`
  - `.github/workflows/green_gate.yml` only if a naming/comment change is strictly required to keep the contract clear
- Gate scripts only if Phase B needs a shared bounded branch-feedback mode instead of inline workflow commands:
  - `scripts/green_gate.sh`
  - `tools/audits/audit_fast.sh`
- Commit executor CI waiting/surface enforcement:
  - `tools/executors/commit_executor.py`
  - corresponding focused tests under `tests/tools/` or `mu/tests/tools/`
- Workflow/docs contract tests, limited to existing workflow/root-file test modules under `tests/docs/`, `tests/tools/`, `mu/tests/docs/`, or `mu/tests/tools/`
- `TASKS.md`, report indexes, and L4 indicator artifacts only if strict L4/docs consistency requires them

Out of scope:

- Production runtime, seed, Stage0, Python/JS substrate semantics, ratchet baselines, branch protection settings, and Claude surfaces.
- Any skip, xfail, delete, or mark-slow change that reduces the authoritative full green-gate evidence.
- Runtime/projection optimization; route that as a separate L4_STRUCTURAL profiling wave after this CI-control wave.

- `reports/deferred/non_blocking/ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Direct Grounding

- `.github/workflows/ci.yml:3-5` says CI is a light feature-branch feedback gate and PRs to `dev` are handled by `green_gate.yml`.
- `.github/workflows/ci.yml:93-102` currently runs `scripts/green_gate.sh python-only` inside the `test` job.
- `.github/workflows/green_gate.yml:147-153` also runs `scripts/green_gate.sh python-only` inside the `green-gate` job.
- `gh pr view 1030 --json statusCheckRollup` on 2026-05-28 showed the expected seven-check PR surface on the final merged head `cac4b559ddd8cfdfa4d0da6f0e85ece31484d1a7`: `test`, `green-gate`, `orbit-dot`, `orbit-provenance`, `engine-run-schema`, `orbit-svg`, and `orbit-index`.
- That same PR rollup showed `test` ran from `2026-05-28T00:26:00Z` to `2026-05-28T00:42:18Z`, while `green-gate` ran from `2026-05-28T00:26:03Z` to `2026-05-28T00:41:53Z`, proving the two long contexts consumed nearly the same wall interval.
- `gh run list --limit 12 --json ...` on 2026-05-28 showed the same head had a push-triggered `CI` run `26546883274` completing at `00:42:18Z` and a PR-triggered `rcx-green-gate` run `26546884892` completing at `00:41:53Z`.
- `tools/executors/commit_executor.py:5826-5934` waits on `gh pr checks --watch --required` and then verifies required checks; `tools/executors/commit_executor.py:6024-6073` treats an all-green required-check subset as pass. This does not mechanically require the full seven-check PR surface.

## Work Items

1. Remove the duplicate full green-gate invocation from `CI/test`. After the fix, `CI/test` must not invoke `scripts/green_gate.sh python-only` or another mode that runs the full authoritative green gate.
2. Keep `CI/test` non-vacuous. It must still run bounded branch-feedback evidence appropriate for a required `test` context, including the existing docs consistency, tracker sync, and L4 contract steps plus a focused fast smoke or shared branch-feedback mode.
3. Preserve `rcx-green-gate/green-gate` as the authoritative full green-gate runner for PRs to `dev`, pushes to `dev`, manual runs, and nightly schedule.
4. Add a mechanical commit-executor PR-surface guard. Before Step 14 records `wait_ci`, commit automation must verify that the current PR status rollup contains the expected seven check names and that all present checks are passing. Missing expected checks must remain pending until timeout, then fail closed with the missing names.
5. Add focused tests proving:
   - `CI/test` no longer calls the full green gate.
   - `green_gate.yml` still calls the full green gate.
   - commit-executor CI waiting rejects a rollup with only `test` and `green-gate`.
   - commit-executor CI waiting accepts a completed seven-check green rollup.

## Constraints

- Use dispatcher, Phase B, pre-commit supervisor, and commit executor. Do not use `run_review.py`.
- Do not rely on branch protection contexts as the whole CI contract.
- Do not change branch protection settings in this wave.
- Do not weaken or remove the five Fixture Gates.
- Do not claim CI duration improvement from local workflow text alone; final acceptance must include GitHub Actions evidence from the PR that lands this wave.
- If GitHub Actions fails to register any part of the expected seven-check surface, stop before merge and report the exact missing check names.

## Acceptance Criteria

- Static/focused tests pass for the workflow duplicate-gate contract and commit-executor seven-check surface guard.
- `CI/test` remains present as the required context name, but no longer runs the full `scripts/green_gate.sh python-only` command.
- `rcx-green-gate/green-gate` remains present and continues to run the full green gate.
- Commit executor cannot mark Step 14 complete when `statusCheckRollup` contains only the branch-protection subset.
- Strict L4 execution contract passes as `L4_ENABLER` with zero runtime/substrate files.
- Host-semantics and host-authority ratchets remain unchanged.
- Final PR validation shows the full seven-check surface and records the `test` and `green-gate` wall intervals separately.

FOUNDER_OVERRIDE:ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28

Authorization: bounded L4_ENABLER repair for CI workflow duplication and commit-executor PR check-surface enforcement. Production runtime or Mu projection optimization is not authorized in this packet.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28`
- Active packet: `reports/control_plane/ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28.md`
- Indicator artifact: `reports/l4_wave_indicators/ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28.md`
  - `reports/deferred/non_blocking/ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28`
- Active packet: `reports/control_plane/ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `ac9a33dd04364a1e7949daaee10fec6cbe2607d435cdde9131f4c901a5b63703`
- Indicator artifact: `reports/l4_wave_indicators/ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28.md`
  - `reports/deferred/non_blocking/ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/ci-pr-check-surface-and-duplicate-gate-repair-2026-05-28.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
