# Canonical Routing Post-Merge Refresh Fallback

Date: 2026-05-15
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: canonical-routing-post-merge-refresh-fallback-2026-05-15
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Category: dispatcher/control-plane repair
Founder override: FOUNDER_OVERRIDE:canonical-routing-post-merge-refresh-fallback-2026-05-15

## Scope

- `mu/tools/executors/executor_dispatch.py`
  - When an explicit canonical `--routing-record .agent_bus/meta/post_merge_routing.json`
    rebind cannot refresh stale routing, fall back to the canonical
    post-merge package refresh path.
  - Preserve caller-owned explicit noncanonical routing refusal.
- `mu/tests/tools/test_executor_dispatch.py`
  - Add regression coverage proving the explicit canonical path reaches the
    package refresh fallback after the builder path fails.
- `mu/tools/observability/_pane_findings.sh`
  - Keep `RCX_PANE_ONESHOT=1` renders side-effect free by suppressing desktop
    notification dispatch and allowing a test-local notification marker.
- `tests/tools/test_recovery_gate.py`
  - Add regression coverage proving oneshot findings renders do not invoke a
    fake `osascript` notifier.

## Root Cause Evidence

- After PR #967 landed, local `dev` was clean at merge commit
  `4c8e59a85419af1bc39374a4f4d73dd16604b50a`.
- `.agent_bus/meta/post_merge_package.json` and
  `.agent_bus/meta/post_merge_routing.json` still carried old merge
  `837b81a148027ad9043a1d374934d5c7a12dc9ce`.
- Running
  `python3 mu/tools/executors/executor_dispatch.py --routing-record .agent_bus/meta/post_merge_routing.json --loop --max-waves 1 --json`
  exited `1` with `status: stale` and
  `Auto-refresh failed — re-run post-merge supervisor manually.`
- Code readback showed `dispatch()` sent explicit canonical records through
  `_refresh_canonical_routing_record_state(...)` and only the implicit path used
  `_auto_refresh_routing(...)`, so the newly merged stale-package repair was not
  reached by the documented explicit canonical dispatcher command.
- During the first push attempt for this repair, pre-push failed in
  `tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution::test_pane_findings_uses_active_worktree_when_current_root_is_quiet`
  with `subprocess.TimeoutExpired` after `_pane_findings.sh` had already printed
  the expected `REQUEST_CHANGES` render.
- Code readback showed `_pane_findings.sh` called `notify` before its
  `RCX_PANE_ONESHOT=1` exit. `notify` launched an asynchronous `osascript`
  desktop notification. The reproducible defect is that automation oneshot
  reads had a live desktop-notification side effect.

## Mechanical Fix

If canonical routing rebind fails for an explicit canonical routing record,
dispatcher now falls back to `_auto_refresh_routing(...)`. That path owns the
stale post-merge package repair and post-merge supervisor invocation. The
noncanonical explicit path remains caller-owned and fail-closed.

The pre-push observability blocker is fixed by making findings-pane oneshot
renders skip notification dispatch. Normal dashboard loop renders still notify.

## Validation

```text
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_explicit_canonical_rebind_falls_back_to_post_merge_package_refresh mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_stale_post_merge_package_repairs_after_manual_github_merge --tb=short
```

Result: exit `0`; `2 passed in 1.00s`.

```text
PYTHONHASHSEED=0 python3 -m pytest -q tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution --tb=short
```

Result: exit `0`; `69 passed in 95.24s`.

## Stop Boundary

This is a bounded pipeline-control repair. It does not implement `/mu`
structural runtime work, does not add Python or JavaScript core semantics, and
does not authorize host-debt expansion.
