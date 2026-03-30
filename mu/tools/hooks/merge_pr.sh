#!/usr/bin/env bash
# merge_pr.sh — Resolve bot threads, merge, post-merge sweep.
#
# Usage:
#   ./tools/hooks/merge_pr.sh <PR_NUM>              # Merge + post-merge check (target PR only)
#   ./tools/hooks/merge_pr.sh <PR_NUM> --sweep      # Merge + sweep last 10 merged PRs
#   ./tools/hooks/merge_pr.sh <PR_NUM> --sweep-only # Skip merge, just sweep recent PRs
#
# What it does:
#   1. Pre-merge: resolve bot-authored unresolved threads (warns on human threads)
#   2. Merge: gh pr merge --merge --delete-branch --admin
#   3. Post-merge: wait 30s, re-check for late-arriving bot threads, resolve them
#   4. Sweep (opt-in via --sweep): check last 10 merged PRs for bot threads
#
# POLICY NOTE: The sweep (Step 4) resolves bot threads on PRs beyond the target.
# This is safe under the repo policy that merged bot threads are clerical residue.
# Use --sweep explicitly; without it, only the target PR is touched.
#
# Only resolves threads authored by chatgpt-codex-connector[bot].
# Human-authored threads are reported but left unresolved for manual review.
# Paginates through all threads (handles PRs with 50+ review threads).
#
# Requires: gh CLI authenticated with repo access

set -euo pipefail

REPO_OWNER="jabramsja"
REPO_NAME="rcx-pi-core"
SWEEP_COUNT=10
POST_MERGE_WAIT=75

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BOT_LOGIN="chatgpt-codex-connector"

resolve_threads() {
    local pr_num="$1"
    local label="$2"

    # Paginate through ALL review threads (not just first 50)
    local bot_ids=""
    local human_count=0
    local cursor=""
    local has_next="true"

    while [ "$has_next" = "true" ]; do
        local after_clause=""
        if [ -n "$cursor" ]; then
            after_clause=", after: \"$cursor\""
        fi

        local response
        response=$(gh api graphql -f query="{
            repository(owner: \"$REPO_OWNER\", name: \"$REPO_NAME\") {
                pullRequest(number: $pr_num) {
                    reviewThreads(first: 100$after_clause) {
                        pageInfo { hasNextPage endCursor }
                        nodes {
                            id
                            isResolved
                            comments(first: 1) { nodes { author { login } } }
                        }
                    }
                }
            }
        }" 2>/dev/null || true)

        if [ -z "$response" ]; then
            break
        fi

        # Extract pagination info
        has_next=$(echo "$response" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage // false')
        cursor=$(echo "$response" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.endCursor // empty')

        # Collect bot-authored unresolved thread IDs
        local page_bot_ids
        page_bot_ids=$(echo "$response" | jq -r "
            .data.repository.pullRequest.reviewThreads.nodes[]
            | select(.isResolved == false)
            | select(.comments.nodes[0].author.login == \"$BOT_LOGIN\")
            | .id
        ")
        if [ -n "$page_bot_ids" ]; then
            bot_ids="${bot_ids}${bot_ids:+$'\n'}${page_bot_ids}"
        fi

        # Count human-authored unresolved threads (warn, don't resolve)
        local page_human
        page_human=$(echo "$response" | jq "[
            .data.repository.pullRequest.reviewThreads.nodes[]
            | select(.isResolved == false)
            | select(.comments.nodes[0].author.login != \"$BOT_LOGIN\")
        ] | length")
        human_count=$((human_count + page_human))
    done

    if [ -z "$bot_ids" ] && [ "$human_count" -eq 0 ]; then
        echo "  PR #$pr_num ($label): no unresolved threads"
        return 0
    fi

    # Resolve only bot-authored threads
    local bot_count=0
    if [ -n "$bot_ids" ]; then
        while IFS= read -r thread_id; do
            [ -z "$thread_id" ] && continue
            gh api graphql -f query="mutation { resolveReviewThread(input: {threadId: \"$thread_id\"}) { thread { isResolved } } }" > /dev/null 2>&1
            bot_count=$((bot_count + 1))
        done <<< "$bot_ids"
    fi

    echo "  PR #$pr_num ($label): resolved $bot_count bot thread(s)"
    if [ "$human_count" -gt 0 ]; then
        echo "  ⚠️  PR #$pr_num ($label): $human_count HUMAN thread(s) left unresolved (review manually)"
    fi
    return 0
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if [ $# -lt 1 ]; then
    echo "Usage: $0 <PR_NUM> [--sweep | --sweep-only]"
    exit 1
fi

PR_NUM="$1"
FLAG="${2:-}"

if [ "$FLAG" = "--sweep-only" ]; then
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

# Step 4: Sweep recent merged PRs (opt-in via --sweep)
if [ "$FLAG" = "--sweep" ]; then
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
else
    echo "--- Step 4: Skipped (use --sweep to sweep recent merged PRs) ---"
    echo ""
fi

echo "=== Done. PR #$PR_NUM merged + threads resolved ==="
