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
