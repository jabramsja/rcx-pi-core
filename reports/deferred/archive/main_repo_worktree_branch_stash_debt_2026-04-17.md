# Main-Repo Worktree / Branch / Stash Debt (Deferred)

**Date:** 2026-04-17
**Wave:** Ad-hoc cleanup inventory during PR #781 session
**Status:** NON-BLOCKING — awaiting founder approval for main-repo destructive ops
**Classification:** DEBT — git hygiene / accumulated session-state residue

---

## Context

During diagnosis of a separate issue (PR #781's "only 2 tests" CI count) I enumerated the full git-state footprint shared across all worktrees on main repo `.git`. Inventory revealed accumulated residue from prior sessions that requires cleanup. Per founder directive 2026-04-11, documenting here rather than leaving un-actioned.

Per RCX hard rules ("Worktree only (never main repo)"), I cannot execute `git branch -D`, `git stash drop`, or `git worktree remove` against main-repo state without explicit founder authorization for each action. This deferred entry records what cleanup is pending.

## Inventory

### Worktrees (3)

| Path | HEAD | Branch | Status | Purpose |
|------|------|--------|--------|---------|
| `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX` | `f2fe2c2a` | `dev` | active, matches origin | Main working repo |
| `/private/tmp/rcx_ci_repro_781` | `34db5be7` (detached) | — | clean, inactive | Orphan from prior session — a CI-repro sandbox created 2026-04-17 14:23; HEAD points at PR #781's state before my merge. No scratch activity. |
| `/private/tmp/workingrcx_pipeline_agent_pager_20260416` | `92840aea` | `jabramsja/pipeline-agent-pager-2026-04-16` | clean, active | Current PR #781 worktree — KEEP until PR merges |

### Local branches (7)

| Branch | Ahead-of-dev | Disposition |
|--------|--------------|-------------|
| `dev` | — | KEEP (active) |
| `jabramsja/pipeline-agent-pager-2026-04-16` | active | KEEP (current PR #781) |
| `jabramsja/codex-startup-hardening-2026-04-14` | 0 | DELETE — merged via PR #777 |
| `jabramsja/learning-store-integration-2026-04-12` | 3 (pre-squash) | DELETE — squash-merged via PR #768 |
| `jabramsja/learning-store-warming-2026-04-12` | 2 (pre-squash) | DELETE — squash-merged via PR #771 |
| `jabramsja/zero-output-timeout-fix-2026-04-13` | 2 (pre-squash) | DELETE — squash-merged via PR #769 |
| `wip/park-codex-startup-hardening-2026-04-14` | 1 | DELETE — park-snapshot from Apr 14; codex-startup-hardening has since landed via PR #777 |

### Stashes (5) — ALL REDUNDANT (verified)

| Stash | Description | Verified-in-origin |
|-------|-------------|---------------------|
| `@{0}` | "refresh-pipeline-agent-pager-base-2026-04-17" on PR branch | TASKS.md + `reports/control_plane/pipeline_agent_pager_2026-04-16.md` confirmed in `origin/jabramsja/pipeline-agent-pager-2026-04-16` via `git cat-file -e` |
| `@{1}` | "phase-b-merge-resolution-buffer" on codex-startup-hardening | single `phase_b_executor.py` diff; branch merged via PR #777 |
| `@{2}` | "park startup-hardening wave while landing control-surface split" | wave split ancestor; codex-startup-hardening and control-surface-split both merged (PRs #776/#777) |
| `@{3}` | "park-codex-startup-hardening-wave-2026-04-14" | `check_codex_startup_state.py`, `founder_learning_snapshot.py`, `founder_session_guard.sh` all verified IN `origin/dev` via `git cat-file -e` |
| `@{4}` | "split-phase-b-routing-record-wave-2026-04-14" | same session scripts as @{3}; all in `origin/dev` |

### Loose commits

- `26e6fff0` "chore(curate): turbo wave1 archive high-confidence unused files" (2026-02-16): reachable from `refs/tags/round-24h-repo-curation-turbo1` — properly tagged, historical, KEEP.

## Byte-Level Verification — NOT YET PERFORMED

I verified file EXISTENCE (`git cat-file -e`) for stash-listed paths in origin. I did NOT verify byte-for-byte that every stash hunk is already applied in origin/dev. Before dropping stashes, a `git stash show -p stash@{N}` vs a diff against the corresponding path in `origin/dev` would give byte-level proof. Deferred to execution time.

## Cleanup Script (pending founder approval to execute)

```bash
cd /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX

# 1. Delete 4 merged branches
git branch -D jabramsja/codex-startup-hardening-2026-04-14
git branch -D jabramsja/learning-store-integration-2026-04-12
git branch -D jabramsja/learning-store-warming-2026-04-12
git branch -D jabramsja/zero-output-timeout-fix-2026-04-13

# 2. Delete obsolete wip branch
git branch -D wip/park-codex-startup-hardening-2026-04-14

# 3. Drop 5 redundant stashes (last-to-first to preserve indices)
git stash drop stash@{4}
git stash drop stash@{3}
git stash drop stash@{2}
git stash drop stash@{1}
git stash drop stash@{0}

# 4. Remove orphan worktree (after confirming no uncommitted work)
cd /private/tmp/rcx_ci_repro_781 && git status --short  # should be empty
cd /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX
git worktree remove /private/tmp/rcx_ci_repro_781

# 5. After PR #781 merges, also remove:
# git worktree remove /private/tmp/workingrcx_pipeline_agent_pager_20260416
```

## Severity

NON-BLOCKING. Nothing on the worktrees is:
- Blocking a commit / push / merge
- Holding unpushed wave work
- Interfering with the pipeline (verified: `_resolve_live_root.sh` correctly picks the PR worktree despite the orphan's presence, because `/private/tmp/rcx_ci_repro_781/.scratch/` is empty)

The only user-visible effect is that `git worktree list` shows 3 entries instead of 2, and `git branch` shows 7 local refs instead of 3. Cosmetic / hygiene.

## Recommendation

- Execute the cleanup script above in a single session when founder approves.
- After PR #781 merges, also prune `workingrcx_pipeline_agent_pager_20260416` worktree.
- Consider a periodic session-end hygiene hook that detects dangling worktrees with no scratch activity older than 24h and warns.
