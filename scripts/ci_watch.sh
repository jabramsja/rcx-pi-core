#!/usr/bin/env bash
set -euo pipefail
export HISTTIMEFORMAT="${HISTTIMEFORMAT-}"

REPO="${REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
WF_ID="${WF_ID:-}"
SHA="$(git rev-parse HEAD)"
SHORT="$(git rev-parse --short HEAD)"

if [ -z "$WF_ID" ]; then
  # Find the workflow id for "CI" by name (fallback to path match if needed)
  WF_ID="$(gh api "repos/$REPO/actions/workflows" --jq '
    .workflows[]
    | select(.name=="CI" or .path==".github/workflows/ci.yml")
    | .id' | head -n 1)"
fi

echo "REPO=$REPO"
echo "HEAD=$SHORT ($SHA)"
echo "WF_ID=$WF_ID"
echo

echo "-- locate run for HEAD --"
RUN_ID="$(gh api "repos/$REPO/actions/workflows/$WF_ID/runs?per_page=50" --jq \
  ".workflow_runs[] | select(.head_sha==\"$SHA\") | .id" | head -n 1 || true)"

if [ -z "${RUN_ID:-}" ]; then
  echo "No run found yet for this SHA."
  echo
  echo "-- recent runs (top 10) --"
  gh api "repos/$REPO/actions/workflows/$WF_ID/runs?per_page=10" --jq \
    '.workflow_runs[] | "\(.id)\t\(.conclusion // "null")\t\(.status)\t\(.head_sha[0:7])\t\(.created_at)\t\(.display_title)"' || true
  exit 0
fi

echo "RUN_ID=$RUN_ID"
echo

echo "-- run header --"
gh api "repos/$REPO/actions/runs/$RUN_ID" --jq \
  '{id,status,conclusion,head_sha,event,created_at,updated_at,html_url,message,path,run_attempt}'
echo

echo "-- jobs (name / status / conclusion / job_id) --"
gh api "repos/$REPO/actions/runs/$RUN_ID/jobs?per_page=100" --jq \
  '.jobs[] | "\(.name)\t\(.status)\t\(.conclusion // "null")\tjob_id=\(.id)"'
echo

STATUS="$(gh api "repos/$REPO/actions/runs/$RUN_ID" --jq .status)"
if [ "$STATUS" != "completed" ]; then
  echo "-- watching until completion --"
  gh run watch "$RUN_ID" || true
  echo
fi

CONCLUSION="$(gh api "repos/$REPO/actions/runs/$RUN_ID" --jq '.conclusion // ""')"
if [ "$CONCLUSION" = "success" ]; then
  echo "CI: success ✅"
  exit 0
fi

echo "CI: conclusion=$CONCLUSION"
echo
echo "-- fetching failed job logs (if any) --"

# Download logs for failed/cancelled jobs into /tmp
FAIL_IDS="$(gh api "repos/$REPO/actions/runs/$RUN_ID/jobs?per_page=100" --jq \
  '.jobs[] | select((.conclusion // "") != "success") | .id' || true)"

if [ -z "${FAIL_IDS:-}" ]; then
  echo "No non-success jobs found (may be a workflow-file issue)."
  exit 0
fi

OUT_DIR="/tmp/rcx_ci_logs_${RUN_ID}"
mkdir -p "$OUT_DIR"

i=0
for J in $FAIL_IDS; do
  i=$((i+1))
  F="$OUT_DIR/job_${J}.log"
  echo "[$i] downloading job log: $J -> $F"
  gh api "repos/$REPO/actions/jobs/$J/logs" > "$F" || true
done

echo
echo "Saved logs to: $OUT_DIR"
