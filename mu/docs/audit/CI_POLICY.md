<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-02-03
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_contracts.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# RCX CI Policy (Green Gate)

This repository treats CI as a hard gate, not a suggestion.

## Definition of GREEN
A change is considered GREEN only when all required checks pass on the PR:

- green-gate (rcx-green-gate workflow)
- test (CI workflow)

These checks are required by branch protection on dev.

## Branch rules
- No direct pushes to dev (PRs only).
- dev must be up to date before merge.
- Branch protection cannot be bypassed, including by admins.

## Local verification
Before opening a PR (or when debugging CI), run:

    bash scripts/green_gate_local.sh

This must end with:

    ✅ ALL GREEN

## If CI fails
- Fix the cause. Do not paper over failures.
- If a test is flaky, treat it as a bug:
  - reproduce locally,
  - stabilize or quarantine with an explicit issue and follow-up PR.
- If snapshots are involved:
  - update them intentionally,
  - review diffs carefully before committing.

CI exists to protect correctness, not velocity.
