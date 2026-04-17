# Wave Packet: observability-pane-and-deferred-doc-cleanup-2026-04-17

## Status: Phase B (locked, implementing)

## Goal

Commit accumulated uncommitted state in main repo discovered during the
PR #781/#782 session: (1) two modified observability helper scripts that
add Codex role inference + pipeline PID dedup, (2) three uncommitted
deferred-tracking documents in `reports/deferred/` from this session's
blocking/non-blocking filings.

## Scope

Control-surface only. No runtime, substrate, host, projection, or seed changes.

**Files (5):**
- `mu/tools/observability/_pane_processes.sh` (modified): adds
  `pid_ppid`, `pid_command`, `pid_has_ancestor_matching`,
  `codex_role_for_pid` helper functions that walk PID ancestry to
  distinguish Codex-reviewer from Codex-implementer roles, plus pane
  logic to categorize into `codex_review` / `codex_impl` / `codex_unknown`
  instead of the single-bucket `codex` label.
- `mu/tools/observability/pipeline_status.sh` (modified): adds
  `collect_active_pipeline_pids` function that deduplicates PIDs across
  six executor keywords (executor_dispatch, commit_executor,
  phase_b_executor, phase_a_executor, meta_bridge_supervisor,
  bridge_supervisor) instead of a single pgrep pattern.
- `reports/deferred/archive/commit_executor_missing_post_merge_cleanup_2026-04-17_CLOSED_by_PR782.md`
  (new): archived blocking deferred entry closed by PR #782.
- `reports/deferred/archive/main_repo_worktree_branch_stash_debt_2026-04-17.md`
  (new): archived inventory entry from 2026-04-17 cleanup session.
- `reports/deferred/blocking/pipeline_monitor_watcher_staleness_2026-04-17.md`
  (new): open blocking deferred entry tracking tmux watcher stuck state
  (root cause pending live-recurrence capture).

**Files NOT touched:** any `mu/host/**`, `rcx_pi/selfhost/**`, kernel,
projection, seed, or test runtime file.

## L4 Contract Fields

- **Class:** L4_ENABLER
- **Target gate:** G8
- **Primary blocker class:** INTEGRATION
- **Primary invariant:** INV_STRUCTURAL_FORWARD_MOTION
- **Evidence command:** `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_doc_contracts.py`
- **Evidence delta:**
  1. Commits the previously-uncommitted observability helper
     improvements that distinguish Codex roles in the monitor status
     pane (fixes status-rendering ambiguity noted during PR #781/#782
     pipeline monitoring).
  2. Commits the three in-session deferred-tracking docs so blocking
     items are preserved in git history, not lost when the session
     ends.
  3. Leaves `reports/deferred/archive/` and
     `reports/deferred/blocking/` consistent with the actual deferred
     state.
- **Indicator artifact:** `reports/l4_wave_indicators/observability-pane-and-deferred-doc-cleanup-2026-04-17.json`
- **Bootstrap endgame policy:** SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP
- **Boot0 track:** V1 / HOLD
- **Founder override:** FOUNDER_OVERRIDE:observability-pane-and-deferred-doc-cleanup-2026-04-17
  (founder authorized in-session via "fix the issues, as long as you
  watch the pipeline while it's running that's fine. are there still
  dirty files, waves that are still not committed?")

## Verification Plan

Pre-push-fast ratchet sweep (automatic via commit_executor step 11):
- host semantics ratchet, authority inventory ratchet, anti-theater
  ratchet, bootstrap purity ratchet, boot layer boundary, doc
  consistency, test theater, JS parity.
- enforce_l4_execution_contract.py: classification + tracker note
  format + non-structural adjacency.

Targeted pytest (step 8b): no wave-owned test files in this diff, so
step 8b will no-op. Doc-governance tests will cover the new deferred/
docs under their existing contracts.

## Stop Conditions

- Abort if any ratchet regresses.
- Abort if doc-consistency fails for the new reports/ files.
- Abort if the observability script changes introduce a shell-syntax
  break (pre-push-fast includes shell syntax check).

## Closeout

On merge, the wave branch + worktree are automatically cleaned up by
commit_executor's new step 16 (`_post_merge_cleanup`) landed in PR
#782. This wave is a self-test of that cleanup step.
