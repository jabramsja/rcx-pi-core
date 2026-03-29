# Deferred Cleanup

Date: 2026-03-29
Status: Phase A (design -- bridge-converged)
Phase-A-Lock: LOCKED
Purpose: Resolve all blocking reports, archive resolved deferred reports, add hook proof tests, fix tmux PR/CI pane

## Scope

### 1. Resolve and archive 3 blocker reports
- B1 (missing agent_type bypass): already FIXED (PR #682)
- B2 (closeout proof coverage): add 4 hook execution tests
- B3 (telegram plugin): STALE (not in settings)
- Adversarial hardening #2: proven by 6 live pipeline runs (#682-#687)
- Archive all 3 to reports/deferred/archive/

### 2. Archive 12 fully-resolved non-blocking reports
Move to reports/deferred/archive/

### 3. Add hook execution tests (B2 proof)
TestHookExecutionAgainstMalformedPayloads in test_validate_agent_compliance.py:
- test_missing_agent_type_blocks
- test_unknown_agent_type_blocks
- test_empty_payload_blocks
- test_valid_agent_type_does_not_block

### 4. Fix tmux PR/CI pane
_pane_prci.sh: gh pr list fallback, bot comment display, review thread count

## Files to Modify

1. mu/tests/tools/test_validate_agent_compliance.py — add 4 execution tests
2. mu/tools/observability/_pane_prci.sh — smarter PR detection
3. reports/deferred/blocking/*.md — mark resolved, move to archive
4. reports/deferred/non_blocking/*.md — archive 12 resolved reports

## Constraints

- No runtime changes, no seed changes
- Hook tests execute the actual shell script
- MAINTENANCE wave (cleanup only)

## Evidence

- Before: 3 open blocker reports, 24 unreviewed non-blocking reports, tmux pane broken
- After: 0 open blockers, 12 archived, 14 remaining with documented open items, pane works
- Verify: `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_validate_agent_compliance.py::TestHookExecutionAgainstMalformedPayloads -v`

## Lane

Post-redteam structural (NEXT-CODEX-POST-REDTEAM).
