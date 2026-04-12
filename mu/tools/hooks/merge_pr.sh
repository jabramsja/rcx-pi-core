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
GH_REPO="${REPO_OWNER}/${REPO_NAME}"
SWEEP_COUNT=10
POST_MERGE_WAIT=75
# Derive repo root from script location (mu/tools/hooks/merge_pr.sh),
# not from cwd — the caller may set cwd outside the repo.
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BOT_LOGIN="chatgpt-codex-connector"
BOT_NO_ISSUES_RE='Codex Review: Didn'"'"'t find any major issues'

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
                            comments(first: 1) { nodes { author { login } body path } }
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

describe_latest_bot_issue_comment() {
    local pr_num="$1"
    local label="$2"
    local response=""
    local latest_kind=""
    local latest_excerpt=""

    response=$(gh api graphql -f query="{
        repository(owner: \"$REPO_OWNER\", name: \"$REPO_NAME\") {
            pullRequest(number: $pr_num) {
                comments(last: 20) {
                    nodes {
                        author { login }
                        body
                        createdAt
                    }
                }
            }
        }
    }" 2>/dev/null || true)

    [ -n "$response" ] || return 0

    latest_kind=$(echo "$response" | jq -r --arg bot "$BOT_LOGIN" --arg re "$BOT_NO_ISSUES_RE" '
        [
            .data.repository.pullRequest.comments.nodes[]
            | select(.author.login == $bot)
        ]
        | sort_by(.createdAt)
        | last
        | if . == null then
            ""
          elif (.body | test($re; "i")) then
            "clear"
          else
            "other"
          end
    ' 2>/dev/null || true)

    case "$latest_kind" in
        clear)
            echo "  ℹ️  PR #$pr_num ($label): latest top-level Codex comment says no major issues"
            echo "     This is historical record only, not a live unresolved thread."
            ;;
        other)
            latest_excerpt=$(echo "$response" | jq -r --arg bot "$BOT_LOGIN" '
                [
                    .data.repository.pullRequest.comments.nodes[]
                    | select(.author.login == $bot)
                ]
                | sort_by(.createdAt)
                | last
                | (.body // "")
                | split("\n")[0]
                | .[0:100]
            ' 2>/dev/null || true)
            if [ -n "$latest_excerpt" ]; then
                echo "  ℹ️  PR #$pr_num ($label): latest top-level Codex comment is still visible"
                echo "     \"$latest_excerpt\""
                echo "     Top-level comments are historical record, not live unresolved threads."
            fi
            ;;
    esac
}

extract_sweep_findings() {
    # Extract unresolved bot-authored finding content from a PR and append
    # to the sweep_findings.json file for pipeline remediation.
    local pr_num="$1"
    local output_file="$2"
    local cursor=""
    local has_next="true"

    while [ "$has_next" = "true" ]; do
        local after_clause=""
        [ -n "$cursor" ] && after_clause=", after: \"$cursor\""

        local response
        response=$(gh api graphql -f query="{
            repository(owner: \"$REPO_OWNER\", name: \"$REPO_NAME\") {
                pullRequest(number: $pr_num) {
                    reviewThreads(first: 100$after_clause) {
                        pageInfo { hasNextPage endCursor }
                        nodes {
                            id
                            isResolved
                            comments(first: 1) { nodes { author { login } body path } }
                        }
                    }
                }
            }
        }" 2>/dev/null || true)

        [ -z "$response" ] && break

        has_next=$(echo "$response" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage // false')
        cursor=$(echo "$response" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.endCursor // empty')

        # Extract unresolved bot findings with content
        echo "$response" | jq -c --arg bot "$BOT_LOGIN" --arg pr "$pr_num" '
            .data.repository.pullRequest.reviewThreads.nodes[]
            | select(.isResolved == false)
            | select(.comments.nodes[0].author.login == $bot)
            | {
                pr: ($pr | tonumber),
                path: .comments.nodes[0].path,
                body: .comments.nodes[0].body,
                thread_id: .id
              }
        ' 2>/dev/null >> "$output_file" || true
    done
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
    merged_prs=$(gh pr list --repo "$GH_REPO" --state merged --limit "$SWEEP_COUNT" --json number --jq '.[].number' 2>/dev/null || true)
    SWEEP_FILE="${REPO_ROOT}/.agent_bus/meta/sweep_findings.json"
    mkdir -p "$(dirname "$SWEEP_FILE")"
    : > "$SWEEP_FILE"  # truncate
    if [ -z "$merged_prs" ]; then
        echo "  No merged PRs found"
    else
        while IFS= read -r pr; do
            [ -z "$pr" ] && continue
            extract_sweep_findings "$pr" "$SWEEP_FILE"
            resolve_threads "$pr" "sweep"
            describe_latest_bot_issue_comment "$pr" "sweep"
        done <<< "$merged_prs"
    fi
    FINDING_COUNT=$(wc -l < "$SWEEP_FILE" | tr -d ' ')
    echo "  Extracted $FINDING_COUNT unresolved finding(s) to $SWEEP_FILE"
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
if ! gh pr merge "$PR_NUM" --repo "$GH_REPO" --merge --delete-branch --admin; then
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
describe_latest_bot_issue_comment "$PR_NUM" "post-merge"
echo ""

# Step 4: Sweep recent merged PRs (opt-in via --sweep)
if [ "$FLAG" = "--sweep" ]; then
    echo "--- Step 4: Sweeping last $SWEEP_COUNT merged PRs ---"
    SWEEP_FILE="${REPO_ROOT}/.agent_bus/meta/sweep_findings.json"
    mkdir -p "$(dirname "$SWEEP_FILE")"
    : > "$SWEEP_FILE"  # truncate
    merged_prs=$(gh pr list --repo "$GH_REPO" --state merged --limit "$SWEEP_COUNT" --json number --jq '.[].number' 2>/dev/null || true)
    if [ -z "$merged_prs" ]; then
        echo "  No merged PRs found"
    else
        while IFS= read -r pr; do
            [ -z "$pr" ] && continue
            extract_sweep_findings "$pr" "$SWEEP_FILE"
            resolve_threads "$pr" "sweep"
            describe_latest_bot_issue_comment "$pr" "sweep"
        done <<< "$merged_prs"
    fi
    FINDING_COUNT=$(wc -l < "$SWEEP_FILE" | tr -d ' ')
    echo "  Extracted $FINDING_COUNT unresolved finding(s) to $SWEEP_FILE"
    echo ""
else
    echo "--- Step 4: Skipped (use --sweep to sweep recent merged PRs) ---"
    echo ""
fi

echo "=== Done. PR #$PR_NUM merged + threads resolved ==="
