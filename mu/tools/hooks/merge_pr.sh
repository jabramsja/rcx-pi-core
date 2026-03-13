#!/usr/bin/env bash
# merge_pr.sh — Resolve bot threads, merge, post-merge sweep.
#
# Usage:
#   ./tools/hooks/merge_pr.sh <PR_NUM>
#   ./tools/hooks/merge_pr.sh <PR_NUM> --sweep-only   # Skip merge, just sweep recent PRs
#
# What it does:
#   1. Pre-merge: resolve all unresolved review threads on the target PR
#   2. Merge: gh pr merge --merge --delete-branch --admin
#   3. Post-merge: wait 30s, re-check for late-arriving bot threads, resolve them
#   4. Sweep: check last 10 merged PRs for any unresolved threads, resolve them
#
# Requires: gh CLI authenticated with repo access

set -euo pipefail

REPO_OWNER="jabramsja"
REPO_NAME="rcx-pi-core"
SWEEP_COUNT=10
POST_MERGE_WAIT=30

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

resolve_threads() {
    local pr_num="$1"
    local label="$2"

    local unresolved
    unresolved=$(gh api graphql -f query="{
        repository(owner: \"$REPO_OWNER\", name: \"$REPO_NAME\") {
            pullRequest(number: $pr_num) {
                reviewThreads(first: 50) {
                    nodes { id isResolved }
                }
            }
        }
    }" --jq '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false) | .id' 2>/dev/null || true)

    if [ -z "$unresolved" ]; then
        echo "  PR #$pr_num ($label): no unresolved threads"
        return 0
    fi

    local count=0
    while IFS= read -r thread_id; do
        [ -z "$thread_id" ] && continue
        gh api graphql -f query="mutation { resolveReviewThread(input: {threadId: \"$thread_id\"}) { thread { isResolved } } }" > /dev/null 2>&1
        count=$((count + 1))
    done <<< "$unresolved"

    echo "  PR #$pr_num ($label): resolved $count thread(s)"
    return 0
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if [ $# -lt 1 ]; then
    echo "Usage: $0 <PR_NUM> [--sweep-only]"
    exit 1
fi

PR_NUM="$1"
SWEEP_ONLY="${2:-}"

if [ "$SWEEP_ONLY" = "--sweep-only" ]; then
    echo "=== Sweep-only mode ==="
    echo ""
    echo "--- Sweeping last $SWEEP_COUNT merged PRs ---"
    merged_prs=$(gh pr list --state merged --limit "$SWEEP_COUNT" --json number --jq '.[].number' 2>/dev/null || true)
    if [ -z "$merged_prs" ]; then
        echo "  No merged PRs found"
    else
        while IFS= read -r pr; do
            [ -z "$pr" ] && continue
            resolve_threads "$pr" "sweep"
        done <<< "$merged_prs"
    fi
    echo ""
    echo "=== Sweep complete ==="
    exit 0
fi

echo "=== Merge PR #$PR_NUM ==="
echo ""

# Step 1: Pre-merge — resolve unresolved threads
echo "--- Step 1: Pre-merge thread resolution ---"
resolve_threads "$PR_NUM" "pre-merge"
echo ""

# Step 2: Merge
echo "--- Step 2: Merging ---"
if ! gh pr merge "$PR_NUM" --merge --delete-branch --admin; then
    echo ""
    echo "❌ Merge failed. Check for remaining blockers:"
    echo "   gh pr checks $PR_NUM"
    echo "   gh pr view $PR_NUM --json reviewDecision,statusCheckRollup"
    exit 1
fi
echo "  ✅ PR #$PR_NUM merged"
echo ""

# Step 3: Post-merge sweep (late-arriving bot threads)
echo "--- Step 3: Post-merge sweep (waiting ${POST_MERGE_WAIT}s for bot) ---"
sleep "$POST_MERGE_WAIT"
resolve_threads "$PR_NUM" "post-merge"
echo ""

# Step 4: Sweep recent merged PRs
echo "--- Step 4: Sweeping last $SWEEP_COUNT merged PRs ---"
merged_prs=$(gh pr list --state merged --limit "$SWEEP_COUNT" --json number --jq '.[].number' 2>/dev/null || true)
if [ -z "$merged_prs" ]; then
    echo "  No merged PRs found"
else
    while IFS= read -r pr; do
        [ -z "$pr" ] && continue
        resolve_threads "$pr" "sweep"
    done <<< "$merged_prs"
fi
echo ""

echo "=== Done. PR #$PR_NUM merged + all threads resolved ==="
