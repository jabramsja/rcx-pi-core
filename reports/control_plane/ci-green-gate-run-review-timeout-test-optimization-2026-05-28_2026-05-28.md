# Ci-Green-Gate-Run-Review-Timeout-Test-Optimization-2026-05-28

Date: 2026-05-28
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: ci-green-gate-run-review-timeout-test-optimization-2026-05-28
Class: L4_ENABLER
Target gate: G8
Phase-A-Lock: LOCKED
Purpose: Build a bounded test-only Phase A packet for optimizing a proven green-gate regression-test timeout. Do not use `run_review.py` as an operator/review path. This wave is only about reducing the existing broad-suite cost of `tests/tools/test_run_review.py::test_adversary_timeout_blocks_merge` while preserving the fail-closed review verdict proof.
Authorization: standing pipeline-bug-fix authorization for ci-green-gate-run-review-timeout-test-optimization-2026-05-28; bounded to green-gate test harness cost reduction and no production runtime, substrate, dispatcher, commit executor, push, PR, or Claude-surface changes.
FOUNDER_OVERRIDE:ci-green-gate-run-review-timeout-test-optimization-2026-05-28

## Scope

Allowed write paths:
- Phase A packet rewrite: `reports/control_plane/ci-green-gate-run-review-timeout-test-optimization-2026-05-28_2026-05-28.md`.
- Phase B implementation after bridge lock: `tests/tools/test_run_review.py` only for the focused timeout-test heartbeat override.
- Phase B tracker sync after bridge lock: `TASKS.md` only for a same-wave `[NEXT-CODEX-POST-REDTEAM]` tracker entry binding `ci-green-gate-run-review-timeout-test-optimization-2026-05-28` to this governing packet and its validation evidence.

Allowed read/reference paths:
- `TASKS.md` only for the targeted `[NEXT-CODEX-POST-REDTEAM]` and standing pipeline-bug-fix authorization lines cited below.
- `tools/runners/run_review.py` cited lines are evidence only: `tools/runners/run_review.py:381-386` for `DEFAULT_REVIEW_HEARTBEAT_INTERVAL_S = 30` and `tools/runners/run_review.py:640` for `self.agent_timeout_s = max(self.heartbeat_interval_s, agent_timeout_s)`.
- The focused selector evidence is limited to `tests/tools/test_run_review.py::test_adversary_timeout_blocks_merge` and the cited existing test lines `tests/tools/test_run_review.py:223-230`.

No other files or directories are in write scope.

## Work items

1. Make this Phase A packet bridge-lockable as a bounded L4_ENABLER plan with explicit scope, constraints, stop conditions, acceptance criteria, and authorization.
2. In Phase B only, add the required `TASKS.md` tracker entry for this same wave under `[NEXT-CODEX-POST-REDTEAM]`, limited to the tracker note needed by `TASKS.md:658`.
3. In Phase B only, update `tests/tools/test_run_review.py::test_adversary_timeout_blocks_merge` so the existing one-second timeout intent is not floored by the default 30-second heartbeat interval. The expected smallest change is passing `heartbeat_interval_s=1` to the same orchestrator construction, or an equivalent in-file helper that affects only this focused test.
4. Preserve the fail-closed behavior proven by the current diagnostic: verdict remains `UNKNOWN`, merge remains blocked, and the regression continues to prove timeout handling rather than success-path behavior.
5. Run focused validation for the selector and record wall time. The focused command must pass in under 5 seconds.
6. Run the smallest adequate test/L4 validation set needed to prove this remains a test-only L4_ENABLER wave with no runtime, substrate, host-semantics, or host-authority delta.

## Constraints

- Do not edit `tools/runners/run_review.py` or any production runner/runtime path.
- Do not use `run_review.py` as an operator/review path for this wave; it is cited only as source evidence for the test cost.
- Do not edit Phase B executor, dispatcher, commit executor, recovery, pre-commit, push, PR, pager, or Claude-related surfaces.
- Do not edit `TASKS.md` for any purpose except the same-wave tracker entry required by `TASKS.md:658`.
- Do not weaken, skip, xfail, delete, or broaden the timeout regression test.
- Do not increase timeout budgets, change default heartbeat behavior, change the timeout clamp, or reduce fail-closed semantics.
- Do not edit ratchet baselines, runtime/substrate code, Stage0, scheduler, seed, registry, loader, parity, docs outside this packet, or unrelated tests.
- Do not inspect downstream implementation files during Phase A beyond the cited evidence; Phase B may inspect only the scoped test path needed for the allowed edit.

## Stop conditions

- Stop before implementation if bridge review does not accept this Phase A packet as bounded L4_ENABLER scope.
- Stop if Phase B cannot add a same-wave `TASKS.md` tracker entry without widening beyond the `[NEXT-CODEX-POST-REDTEAM]` tracker note required by `TASKS.md:658`.
- Stop if the focused test cannot be reduced below 5 seconds with a test-only heartbeat override.
- Stop if the change requires editing `tools/runners/run_review.py` or changing default heartbeat/clamp behavior.
- Stop if preserving `UNKNOWN`/blocks-merge fail-closed proof would require weakening assertions.
- Stop if validation indicates runtime/substrate changes, ratchet baseline changes, or host-authority inventory changes are needed.
- Stop if Phase B discovers the target test already has an equivalent scoped heartbeat override and the focused selector already runs below 5 seconds; convert to no-op evidence instead of making cosmetic edits.

## Acceptance criteria

- The packet contains all required Phase A sections and a mechanically detectable same-wave authorization line: `FOUNDER_OVERRIDE:ci-green-gate-run-review-timeout-test-optimization-2026-05-28`.
- Phase B changes are limited to `tests/tools/test_run_review.py` plus the required same-wave `TASKS.md` tracker entry, and preserve this packet as the governing control-plane packet.
- `TASKS.md` contains a same-wave `[NEXT-CODEX-POST-REDTEAM]` tracker entry for `ci-green-gate-run-review-timeout-test-optimization-2026-05-28` before the wave is treated as complete.
- Focused command passes and records `real` wall time below 5 seconds:
  `env PYTHONHASHSEED=0 /usr/bin/time -p python3 -m pytest -q tests/tools/test_run_review.py::test_adversary_timeout_blocks_merge --tb=short -p no:cacheprovider`.
- `tests/tools/test_run_review.py` remains green, or Phase B records a narrower adequate focused subset if the full file is not required for this test-only change.
- L4 contract validates the staged/file set as `L4_ENABLER` with no runtime or substrate delta.
- Host-semantics ratchet and host-authority inventory checks show no increases and no baseline edits.
- No file outside the explicit scope is modified.

## Grounding / Authorization

- Governing packet: `reports/control_plane/ci-green-gate-run-review-timeout-test-optimization-2026-05-28_2026-05-28.md`.
- `TASKS.md:650-654` grounds `[NEXT-CODEX-POST-REDTEAM]` as unparked, founder-authorized, open, and requiring separate bounded packets for future work not already proven landed.
- `TASKS.md:658` grounds the active founder-ordered queue rule that every wave requires a control-plane packet plus tracker entry, and that manual pipeline repair is allowed only as a bounded unblocker paired with same-wave mechanical/automated fix or precise follow-up automation packet.
- `TASKS.md:153` records the standing autonomous pipeline bug-fix authorization precedent for bridge/pipeline defects.
- This packet explicitly authorizes the missing same-wave `TASKS.md` tracker entry as a Phase B write path; no broader `TASKS.md` cleanup or unrelated tracker rewrite is authorized.
- This packet provides the same-wave control-surface token required for mechanical derivation: `FOUNDER_OVERRIDE:ci-green-gate-run-review-timeout-test-optimization-2026-05-28`.
- This Phase A rewrite relies only on the current packet, the targeted `TASKS.md` lines above, and the bridge reviewer evidence. It does not inspect downstream implementation files to decide whether implementation work is already landed.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `ci-green-gate-run-review-timeout-test-optimization-2026-05-28`
- Active packet: `reports/control_plane/ci-green-gate-run-review-timeout-test-optimization-2026-05-28_2026-05-28.md`
- Indicator artifact: `reports/l4_wave_indicators/ci-green-gate-run-review-timeout-test-optimization-2026-05-28.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_run_review.py`
  - `reports/control_plane/ci-green-gate-run-review-timeout-test-optimization-2026-05-28_2026-05-28.md`
  - `reports/l4_wave_indicators/ci-green-gate-run-review-timeout-test-optimization-2026-05-28.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `ci-green-gate-run-review-timeout-test-optimization-2026-05-28`
- Active packet: `reports/control_plane/ci-green-gate-run-review-timeout-test-optimization-2026-05-28_2026-05-28.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `0b16e9fea6fa775a9d7e5689294993697d18b43dd363c7a9593367753806ce86`
- Indicator artifact: `reports/l4_wave_indicators/ci-green-gate-run-review-timeout-test-optimization-2026-05-28.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_run_review.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/ci-green-gate-run-review-timeout-test-optimization-2026-05-28_2026-05-28.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/ci-green-gate-run-review-timeout-test-optimization-2026-05-28.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_run_review.py`
  - `reports/control_plane/ci-green-gate-run-review-timeout-test-optimization-2026-05-28_2026-05-28.md`
  - `reports/l4_wave_indicators/ci-green-gate-run-review-timeout-test-optimization-2026-05-28.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
