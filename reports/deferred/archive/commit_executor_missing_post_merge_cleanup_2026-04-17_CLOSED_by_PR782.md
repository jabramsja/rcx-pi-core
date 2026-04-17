# commit_executor.py — Missing Post-Merge Cleanup (Blocking Structural Debt)

**Date:** 2026-04-17
**Wave:** Ad-hoc diagnosis during PR #781 session
**Status:** BLOCKING — pipeline-affecting, causes silent regressions
**Classification:** DEBT / STRUCTURAL — missing feature in commit_executor

---

## Issue

`mu/tools/executors/commit_executor.py` has **no post-merge cleanup step**. After `gh pr merge` succeeds in the `ensure_review_clear_and_merge` step (step 14), the pipeline ends without:
- Deleting the just-merged local branch
- Dropping wave-local stashes
- Removing the wave's linked worktree

Local branch refs, stashes from merge-resolution buffers, and orphan worktrees therefore accumulate across every wave that lands.

## Root-Cause File:Line Citation

Verified via `grep -nE 'branch -D|branch --delete|git worktree remove|stash drop' mu/tools/executors/commit_executor.py`:

- Zero matches for `branch -D` or `branch --delete` — local-branch cleanup is not in the file.
- Zero matches for `stash drop` — stash cleanup is not in the file.
- Only matches for `git worktree` are **READ-only** (line 322 `_parse_worktree_list` and lines 1741/1743 auto-heal comments about consuming `git worktree list --porcelain`) — no `git worktree remove` anywhere.

So the defect is by absence: the code path ends after step 14 (`ensure_review_clear_and_merge` at line 1509+ invoking `_merge_pr` — the PR is merged; nothing is done to clean up the now-redundant local state).

## Pipeline Impact Verified

**(1) commit_executor.py IS a pipeline executor AND calls hooks:**
- Lives in `mu/tools/executors/`, implements step 8 `run_pre_commit_script` (explicit `pre-commit-doc-check` run) and step 11 `run_pre_push_script` (`pre-push-fast`).
- Control-surface invariants file (`mu/tools/checks/check_control_surface_invariants.py`) references it.
- Closeout attestation check (`mu/tools/checks/check_closeout_attestation.py`) references it.
- Meta-bridge supervisor (`mu/tools/agents/meta_bridge_supervisor.py`) references it.
- Bridge supervisor, executor dispatch, shared agent utils all reference it (7+ dependents verified via `grep -rlE 'commit_executor\.py|commit_executor\.run_commit_pipeline'`).

**(2) Silent regression evidence (empirical):** this session directly observed and cleaned up 11h of uncontrolled accumulation on a single developer's machine:
- 4 merged local branches not deleted (`codex-startup-hardening-2026-04-14` from PR #777, `learning-store-integration-2026-04-12` from PR #768, `learning-store-warming-2026-04-12` from PR #771, `zero-output-timeout-fix-2026-04-13` from PR #769).
- 5 stashes from merge-resolution / wave-park scenarios that were never dropped.
- 1 wip branch (`wip/park-codex-startup-hardening-2026-04-14`) from mid-wave snapshotting.
- 1 orphan linked worktree (`/private/tmp/rcx_ci_repro_781`) created during CI-repro work.

**(3) Adjacent pipeline-impact surface:**
- `mu/tools/observability/_resolve_live_root.sh` walks `git worktree list --porcelain` scoring by freshest `.scratch/` mtime (lines 9-33, 42-67). Orphan worktrees with no scratch activity score 0 and do not dethrone a live worktree today, but accumulation widens the search space and increases mis-resolution risk if an orphan acquires stale scratch content (e.g., someone runs `touch` for debugging).
- `mu/tools/executors/executor_dispatch.py` handles branch names during dispatch. Stale local branches with the same `{branch_prefix}/{wave_id}` pattern as a new wave's expected branch create naming collisions when `git checkout -b` would otherwise succeed.

## Why This Is BLOCKING (per founder directive 2026-04-11)

The directive says: if a file affects hooks/executors/checks/preflight AND failure causes silent regressions → BLOCKING regardless of P-level. This finding meets both conditions:
- Affects executors (is one) — hooks (invokes them) — checks (referenced by them).
- Accumulation is a silent regression — nothing fails immediately; debt compounds invisibly until someone enumerates it.

## Fix Plan (requires a separate wave)

Proposed new step 15 after `ensure_review_clear_and_merge`:

```python
# Step 15 (new): post_merge_cleanup
if merge_result.merged:
    # Delete the local branch (we're on dev now after merge)
    _run(["git", "checkout", "dev"], cwd=repo_root, timeout=30)
    _run(["git", "branch", "-D", target_branch], cwd=repo_root, timeout=30)
    # Remove the wave worktree if it exists and is this PR's
    try:
        wt_list = _run(["git", "worktree", "list", "--porcelain"], cwd=repo_root).stdout
        for entry in _parse_worktree_list(wt_list):
            if entry.get("branch", "").endswith(target_branch):
                _run(["git", "worktree", "remove", entry["worktree"]], cwd=repo_root, timeout=30)
    except Exception as exc:
        log(f"Step 15 worktree cleanup warning: {exc}")
    # Stashes are wave-local; clean up any with the wave_id in the description
    stash_list = _run(["git", "stash", "list"], cwd=repo_root).stdout
    for line in stash_list.splitlines():
        if wave_id in line:
            stash_ref = line.split(":", 1)[0]
            _run(["git", "stash", "drop", stash_ref], cwd=repo_root, timeout=30)
    result["steps_completed"].append("post_merge_cleanup")
```

Safety considerations for the implementing wave:
- `git checkout dev` only after verifying working-tree clean (don't lose uncommitted work).
- Stash drop MUST be scoped to wave_id in message — do NOT blanket-drop stashes with unrelated topics.
- Worktree remove only if `git status --short` shows clean + no conflicts.
- Hard-fail on any unexpected state; this is a safety-critical path.

## Current-Session Mitigation (manual cleanup executed 2026-04-17)

Per founder authorization "I would like to do the cleanup, actually", this session's accumulated debt was manually cleaned:
- 5 stashes dropped (verified byte-level redundant first).
- 4 merged branches deleted (`git branch -D`).
- 1 wip branch deleted.
- 1 orphan worktree removed (`git worktree remove`).
- `git worktree list` → 2 entries; `git branch` → 2 entries; `git stash list` → empty. Verified.

This does NOT close the structural defect — it only cleared the accumulated state. Next merge will start accumulating again.

## Severity

BLOCKING — must be implemented in a future wave, not left as "follow-up".
Impact: without it, every merged PR silently leaks local state. Catches humans eventually (observed: 11h of accumulation on one machine).

## Next Action Required

Open a wave tracked in TASKS.md under `[PIPELINE-RECOVERY]` or a new `[COMMIT-EXECUTOR-POST-MERGE-CLEANUP]` entry. Implement step 15 per the fix plan above. Must go through the normal pipeline (Phase A → Phase B → commit_executor → merge).
