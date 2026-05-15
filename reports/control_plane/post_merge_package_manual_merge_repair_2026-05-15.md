# Post-Merge Package Manual Merge Repair

Date: 2026-05-15
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: post-merge-package-manual-merge-repair-2026-05-15
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Category: dispatcher/control-plane repair
Founder override: FOUNDER_OVERRIDE:post-merge-package-manual-merge-repair-2026-05-15

## Scope

- `mu/tools/executors/executor_dispatch.py`
  - Repair the missed post-merge package refresh when an operator-visible manual
    GitHub PR merge is used after commit executor recovery exhausts.
  - Keep stale package replay fail-closed unless the stale package merge is an
    ancestor of current `HEAD` and current `HEAD` is a GitHub pull-request merge
    commit.
- `mu/tests/tools/test_executor_dispatch.py`
  - Preserve the rejection path for non-repairable stale packages.
  - Add regression coverage for stale package repair after a manual GitHub merge.

## Root Cause Evidence

- PR #966 merged manually after commit executor recovery exhausted on
  `bot_findings_pending`.
- After the manual merge, `git rev-parse HEAD` returned
  `5720b1ad93653927e5010f8d0878e56d85af587e`.
- `.agent_bus/meta/post_merge_package.json` still carried PR `965` and
  `merge_sha` `837b81a148027ad9043a1d374934d5c7a12dc9ce`.
- `.agent_bus/meta/post_merge_routing.json` still carried `state_sha`
  `d8603e76d325f14547d1d974aecf396be1b6b3266941896bd26eb124cf581cce` and
  `merge_sha` `837b81a148027ad9043a1d374934d5c7a12dc9ce`.
- `python3 mu/tools/executors/executor_dispatch.py --routing-record .agent_bus/meta/post_merge_routing.json --loop --max-waves 1 --json`
  exited `1` with `status: stale` and
  `Auto-refresh failed — re-run post-merge supervisor manually.`
- Code readback showed package refresh lives in
  `mu/tools/executors/commit_executor.py` Step 15b after executor-managed merge,
  while dispatcher auto-refresh refuses to reuse a package whose `merge_sha` does
  not equal current `HEAD`.

## Mechanical Fix

Dispatcher auto-refresh now attempts a bounded package repair before invoking
the post-merge supervisor when the canonical package is stale. The repair only
runs when:

- the stale package `merge_sha` is an ancestor of current `HEAD`;
- current `HEAD` is a multi-parent GitHub merge commit with a parseable PR
  number in the subject; and
- the existing commit-executor package refresher is available.

If any condition fails, dispatcher keeps the prior fail-closed stale-package
behavior and does not invoke the supervisor.

## Validation

```text
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_auto_refresh_rejects_stale_post_merge_package_before_supervisor mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_stale_post_merge_package_repairs_after_manual_github_merge --tb=short
```

Result: exit `0`; `2 passed in 1.04s`.

## Stop Boundary

This is a bounded pipeline-control repair. It does not implement `/mu`
structural runtime work, does not add Python or JavaScript core semantics, and
does not authorize host-debt expansion.
