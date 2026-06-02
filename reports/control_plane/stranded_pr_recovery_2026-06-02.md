# Stranded Pr Recovery 2026-06-02

Date: 2026-06-02
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: stranded-pr-recovery-2026-06-02
Class: L4_ENABLER (tooling-only; no runtime dir)
target_gate_id: G8
Phase-A-Lock: LOCKED

Purpose: Add a standalone recovery mode to `commit_executor.py` that EXPOSES the existing post-commit continuation to a caller, so a stranded PR (already committed; receipt `COMMIT_GO`; continuation record written; its dispatcher process has exited) can finish its remaining post-commit steps through the NORMAL gates without re-running the early steps.

Background (why this is needed): the helper `_load_post_commit_continuation` loads a persisted continuation record (commit_sha, receipt_decision `COMMIT_GO`, steps_completed including git_commit, target_branch), and the EXISTING caller of `_load_post_commit_continuation` already drives the remaining post-commit steps -- CI-surface wait via `_wait_for_pr_ci`, the existing normal completion step, `_auto_defer_bot_findings` for deferrable findings, and the existing cleanup. Today that resume is reachable ONLY from inside the dispatcher process. A stranded PR whose dispatcher exited has a valid continuation record but nothing drives it, and a plain `--standalone` re-invoke restarts at the first step and dies at the 'Nothing staged' guard. The fix surfaces the same driver behind a new `--resume-continuation` flag on `main()`.

## Scope

In scope (tooling-only; touches NO runtime/substrate dirs):

- `mu/tools/executors/commit_executor.py` -- add a `--resume-continuation` standalone flag to `main()` that, in the current worktree, loads the existing post-commit continuation record via `_load_post_commit_continuation` and invokes the SAME existing dispatcher driver (the existing caller of that helper) to finish the remaining post-commit steps through the normal gates.
- `mu/tests/tools/test_commit_executor_receipt.py` -- add the regression test to this EXISTING test file (keeps the test-file count flat; no growth-cap bump; no new test file).
- This packet file (`reports/control_plane/stranded_pr_recovery_2026-06-02.md`) -- the governing Phase A plan.

Code is cited by function name only; the packet uses no file:line references.

## Work Items

1. Add a `--resume-continuation` flag to the `commit_executor.py` `main()` argument parser, gated so it changes behavior only when explicitly passed.
2. On that flag, in the current worktree, call `_load_post_commit_continuation` to load the existing continuation record.
3. When a valid record is returned, invoke the SAME existing driver (the existing caller of `_load_post_commit_continuation`) to run the remaining post-commit steps -- reused verbatim, including `_wait_for_pr_ci`, the existing normal completion step, and `_auto_defer_bot_findings`.
4. Fail-closed guard: when `_load_post_commit_continuation` returns `None` (no valid record / wrong branch / dirty tree / not committed), surface a clear error, take NO completion action, and exit non-zero.
5. Add a regression test to the existing `test_commit_executor_receipt.py` covering both branches: (a) a valid continuation record invokes the existing driver; (b) no/invalid record exits fail-closed without acting.

## Constraints

NOT in scope -- these are hard boundaries:

- NO new CI/completion/defer logic. Reuse the existing continuation driver, `_wait_for_pr_ci`, and `_auto_defer_bot_findings` verbatim.
- NO privileged / admin / branch-protection-skip option. Completion MUST go through the existing normal step the driver already calls (the standard non-privileged path); do not add, pass, or enable any privileged option.
- The normal dispatch path and the existing `--standalone` path MUST remain byte-for-byte unchanged. All new behavior is gated behind the new `--resume-continuation` flag only.
- NO new test file. The regression test is added to the existing `test_commit_executor_receipt.py` so the test-file count stays flat (no growth-cap bump).
- NO runtime/substrate dir changes (no `rcx_pi/selfhost/`, no `mu/host/`, no seeds/projections/scheduler). No L3 parity surface is touched; JS is unaffected.
- Do NOT solve or land the implementation in this Phase A turn; this packet is the plan only.

## Stop Conditions

- STOP and surface as POLICY_BOUND if the existing driver, `_load_post_commit_continuation`, `_wait_for_pr_ci`, or `_auto_defer_bot_findings` cannot be reused verbatim and would require new CI/completion/defer logic. Do not invent logic to route around this.
- STOP if the fail-closed guard cannot be implemented without a privileged / admin / branch-protection-skip path.
- STOP if the new flag cannot be gated without modifying the normal dispatch or `--standalone` paths.
- STOP if covering the change would require a NEW test file (growth-cap); the regression test must extend the existing `test_commit_executor_receipt.py`.
- STOP after this Phase A packet rewrite; do not begin implementation in this turn.

## Acceptance Criteria

- `main()` exposes a `--resume-continuation` flag; with a valid continuation record it invokes the existing driver and finishes the remaining post-commit steps through the normal gates.
- With no/invalid continuation record, the flag exits fail-closed with a surfaced error and takes no completion action.
- No privileged path is added; the normal dispatch and `--standalone` paths are unchanged.
- A regression test in `test_commit_executor_receipt.py` covers both the valid-record (driver invoked) and the fail-closed (no action) branches, with no new test file added.
- Validation gate passes: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`.
- Indicator collected: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id stranded-pr-recovery-2026-06-02 --output reports/l4_wave_indicators/stranded-pr-recovery-2026-06-02.json`.

## Grounding / Authorization

Governing packet: `reports/control_plane/stranded_pr_recovery_2026-06-02.md` (this file).

TASKS.md authorization: task `[NEXT-CODEX-POST-REDTEAM]`, tracker sync note (2026-06-02, stranded-pr-recovery-2026-06-02) in `TASKS.md`, which names this wave's governing Packet as `reports/control_plane/stranded_pr_recovery_2026-06-02.md`. That tracker note carries the L4 contract fields mirrored here:

- Class: L4_ENABLER
- target_gate_id: G8
- Packet: `reports/control_plane/stranded_pr_recovery_2026-06-02.md`
- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`
- primary_blocker_class: INTEGRATION
- primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION
- indicator_artifact_ref: `reports/l4_wave_indicators/stranded-pr-recovery-2026-06-02.json`
- indicator_collection_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id stranded-pr-recovery-2026-06-02 --output reports/l4_wave_indicators/stranded-pr-recovery-2026-06-02.json`
- bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP
- boot0_track_id: V1
- boot0_progress_state: HOLD

Authorization: standing pipeline-bug-fix authorization (per memory `feedback_autonomous_executor_fix.md`), wave-bound. The same-wave override is `FOUNDER_OVERRIDE:stranded-pr-recovery-2026-06-02`, so commit automation (build_commit_handoff) can derive the same-wave override mechanically for commit-gate and pre-push adjacency-cap clearance on this control-surface L4_ENABLER packet.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `stranded-pr-recovery-2026-06-02`
- Active packet: `reports/control_plane/stranded_pr_recovery_2026-06-02.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `815fa12ec594d17c52dc09f9ff5299da972dcb14a7d9702427f4200ca68005d8`
- Indicator artifact: `reports/l4_wave_indicators/stranded-pr-recovery-2026-06-02.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/stranded_pr_recovery_2026-06-02.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/stranded-pr-recovery-2026-06-02.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/stranded_pr_recovery_2026-06-02.md`
  - `reports/l4_wave_indicators/stranded-pr-recovery-2026-06-02.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
