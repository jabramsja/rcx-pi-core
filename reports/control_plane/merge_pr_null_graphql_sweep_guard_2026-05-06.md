# Merge PR Null GraphQL Sweep Guard

Status: IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: merge-pr-null-graphql-sweep-guard-2026-05-06
Class: L4_ENABLER
Target Gate: G8
Tracked packet: reports/control_plane/merge_pr_null_graphql_sweep_guard_2026-05-06.md

## Problem

PR #888 merged, but the commit executor stopped at the merge step before
post-merge package refresh. Direct pipeline evidence is recorded in
`.agent_bus/observability/pipeline_agent_events.jsonl`: event 2553 reports
`[commit-executor] Error: merge_pr.sh failed: jq: error (at <stdin>:1): Cannot iterate over null (null)`.

The hook path that can produce that exact jq class was the direct array
iteration in `mu/tools/hooks/merge_pr.sh` over
`reviewThreads.nodes[]` and `comments.nodes[]`. A GitHub GraphQL response with
null or incomplete thread/comment containers should be treated as no actionable
threads, not as a post-merge failure after the PR has already merged.

## Mechanical Fix

- `merge_pr.sh` now treats missing/null GraphQL `reviewThreads.nodes` arrays as
  empty during bot-thread resolution, human-thread counting, and sweep-finding
  extraction.
- `merge_pr.sh` now treats missing/null top-level PR comment arrays as empty
  during informational Codex-comment description.
- `mu/tests/tools/test_executor_dispatch.py` now runs the copied hook through a
  fake `gh` where `gh pr list` returns a merged PR and GraphQL returns null
  thread/comment containers. The expected outcome is a clean sweep with no jq
  null-iteration failure.

## Evidence

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestMergePrSweepCount --tb=short`
  exited `0` with `8 passed`.
- `bash -n mu/tools/hooks/merge_pr.sh` exited `0`.

## Files

- `mu/tools/hooks/merge_pr.sh`
- `mu/tests/tools/test_executor_dispatch.py`
- `reports/control_plane/merge_pr_null_graphql_sweep_guard_2026-05-06.md`
- `reports/l4_wave_indicators/merge-pr-null-graphql-sweep-guard-2026-05-06.json`

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `merge-pr-null-graphql-sweep-guard-2026-05-06`
- Active packet: `reports/control_plane/merge_pr_null_graphql_sweep_guard_2026-05-06.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `8b8af0d7560251e8c50ab5d82d1f290ebbf7efb834b6c5eef4f554240bd2b182`
- Indicator artifact: `reports/l4_wave_indicators/merge-pr-null-graphql-sweep-guard-2026-05-06.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestMergePrSweepCount --tb=short && bash -n mu/tools/hooks/merge_pr.sh`.
- Evidence delta: (1) `merge_pr.sh` treats null/missing GitHub GraphQL `reviewThreads.nodes` as an empty thread list during bot resolution, human-thread counting, and sweep-finding extraction. (2) `merge_pr.sh` treats null/missing GitHub GraphQL PR `comments.nodes` as an empty top-level comment list during informational Codex-comment description. (3) The dispatcher test harness now exercises a fake merged PR whose GraphQL thread/comment containers are null and requires a clean sweep without `Cannot iterate over null`.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/merge-pr-null-graphql-sweep-guard-2026-05-06.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/hooks/merge_pr.sh`
  - `reports/control_plane/merge_pr_null_graphql_sweep_guard_2026-05-06.md`
  - `reports/l4_wave_indicators/merge-pr-null-graphql-sweep-guard-2026-05-06.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
