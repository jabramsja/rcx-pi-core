# Plan Deferred Consolidation E5 E6 2026 04 02

Date: 2026-04-06
Status: Phase A (design -- not yet agent-reviewed or bridge-converged)
Phase-A-Lock: UNLOCKED
Purpose: Create a bounded Phase A plan for the Wave 1B E5+E6 observability/hooks slice under [DEFERRED-CONSOLIDATION]. The slice is limited to the tmux PR/CI pane and adjacent observability helpers needed to fix jq last(3) misuse, sanitize terminal escape sequences in displayed bot comment text, and add defense-in-depth numeric validation before gh API PR comment calls. Do not expand into broader Cluster C or D items unless Phase A proves a direct dependency. Use the pipeline packet plus TASKS.md as governing scope.

## Scope

DEFERRED-CONSOLIDATION Wave 1B follow-on slice: E5 jq tail logic plus terminal escape sanitization, and E6 PR number numeric validation in the gh API path for tmux PR/CI observability.

## Request from Post-Merge Supervisor

Create a bounded Phase A plan for the Wave 1B E5+E6 observability/hooks slice under [DEFERRED-CONSOLIDATION]. The slice is limited to the tmux PR/CI pane and adjacent observability helpers needed to fix jq last(3) misuse, sanitize terminal escape sequences in displayed bot comment text, and add defense-in-depth numeric validation before gh API PR comment calls. Do not expand into broader Cluster C or D items unless Phase A proves a direct dependency. Use the pipeline packet plus TASKS.md as governing scope.
