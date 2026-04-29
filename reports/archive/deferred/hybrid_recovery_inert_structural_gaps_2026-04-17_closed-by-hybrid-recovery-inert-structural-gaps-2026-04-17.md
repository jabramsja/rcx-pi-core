# BLOCKING: hybrid recovery is inert — 3 remaining structural gaps

**Date filed**: 2026-04-17
**Status**: CLOSED (2026-04-29; closed by `hybrid-recovery-inert-structural-gaps-2026-04-17`)
**Observed on**: commit-executor-ci-poll-timeout-fix wave (PR #787) phase_b attempts
**Severity**: BLOCKING (hybrid recovery flag enabled in PR #786 but has never productively delegated)

**Archive note**: The remaining three structural gaps were closed by the
bounded Phase B implementation recorded in
`reports/control_plane/hybrid_recovery_inert_structural_gaps_2026-04-17.md`.

## Summary

PR #778 (2026-04-16) landed the hybrid recovery code. PR #786 (2026-04-17) flipped
`hybrid_recovery_enabled: true`. But across all observed invocations since then,
the hybrid `delegate_implementer` action has NEVER been executed — the recovery
agent consistently escalates instead. Three structural gaps prevent hybrid from
being useful:

1. `files_in_scope` whitelist too narrow
2. Phase B swallows claude's stderr / stop_reason before recovery sees it
3. Recovery trigger conditions in commit_executor too narrow (only fires on
   `bot_findings_pending` status in standalone mode)

Gap 4 (MISSING_BRIDGE_CONFIG chicken-and-egg) is fixed in THIS wave's
`recovery_gate.py` change. The remaining 3 gaps are filed here for follow-up
waves.

## Gap 1: hybrid delegate_implementer scope whitelist too narrow

**Root cause (file:line):** `mu/tools/executors/recovery_gate.py:~2150-2160`
(the `delegate_implementer` prompt's `files_in_scope` allowlist).

**Evidence (observed 2026-04-17, PR #787 wave):** the recovery agent explicitly
reasoned:

> "A blind delegate_implementer retargeting recovery_gate.py/executor_common.py
> would also be out-of-scope: the modified files (commit_executor.py,
> test_commit_executor_receipt.py) are not in the allowed files_in_scope
> whitelist, so delegate_implementer cannot legally repair them."

The allowlist restricts hybrid to repairing `recovery_gate.py` itself and a
handful of adjacent files. Any failure involving `commit_executor.py`,
`phase_b_executor.py`, test modules, or scratch artifacts is out-of-scope for
delegation, even if the fix is mechanically bounded.

**Structural fix candidate:** widen `files_in_scope` to include the full
executor surface (`mu/tools/executors/**/*.py`, `mu/tests/tools/test_*.py`,
`reports/deferred/**`, `reports/control_plane/**`). Keep runtime paths
(`mu/host/**`, `rcx_pi/**`, kernel/projection/seed) explicitly excluded. This
matches the L4_ENABLER class scope that the executors themselves target.

**Acceptance criteria:** recovery agent proposes and executes
`delegate_implementer` for a failure in `commit_executor.py` or
`phase_b_executor.py`; regression test in `test_recovery_gate.py` verifies a
widened scope example is accepted by `_validate_delegate_implementer_payload`.

## Gap 2: Phase B swallows claude adapter's exit reason before recovery sees it

**Root cause (file:line):** `mu/tools/executors/phase_b_executor.py:~2470`
(implementer invocation error handling). When the claude adapter exits 1 with
`{"type":"result","subtype":"error_max_turns","num_turns":51,"stop_reason":"tool_use"}`,
phase_b wraps the failure as `error (exit=-1): Adapter 'claude' exited 1.` —
the specific `error_max_turns` subtype + `stop_reason` are lost.

**Evidence (observed 2026-04-17, PR #787 wave):** claude completed the fix code
+ tests + archived the deferred within its 50-turn budget but hit max_turns at
turn 51 during wrap-up. phase_b reported the failure with no diagnostic
signal. The recovery agent (claude via fallback backend) saw empty stderr +
stdout and reasoned:

> "Both STDERR and STDOUT are empty, providing zero diagnostic evidence of what
> the implementer step actually failed on... Per hard rules I must not
> conjecture about errors, and this turn forbids running diagnostic commands,
> so I cannot responsibly pick shell/edit/delegate_implementer without
> inventing a hypothesis. Human intervention is needed to surface the real
> failure signal."

With the real failure class exposed (`max_turns_reached`), the recovery agent
could have chosen to re-invoke the implementer with a higher `--max-turns`
budget — a concrete, actionable fix that matches the diagnosed cause.

**Structural fix candidate:** parse the claude adapter's final `"type":"result"`
envelope in `phase_b_implementer.py` / `phase_b_executor.py` invocation error
handling. Extract `subtype`, `stop_reason`, `num_turns`, `error_max_turns`,
etc. Propagate into the `result` dict as `error_subtype: "error_max_turns"` so
the recovery classifier can match on it.

**Acceptance criteria:** new `FailureClass.MAX_TURNS_REACHED` in
recovery_gate.py classifier; regression test asserts phase_b_executor result
on max_turns failure includes `error_subtype: "error_max_turns"`.

## Gap 3: Recovery trigger in commit_executor standalone too narrow

**Root cause (file:line):** `mu/tools/executors/commit_executor.py:3989`:
```python
if result.get("status") == "bot_findings_pending" and args.standalone:
    ...attempt_recovery(...)
```

Only `bot_findings_pending` routes to recovery in standalone mode. Other error
classes (`pre_push_failed`, `l4_contract_violation`, `stage_failed`,
`implementer_error`) bypass recovery entirely and exit with error.

**Evidence (observed 2026-04-17, enable-pager-hybrid wave):** the wave's 1st
attempt hit an L4 consecutive-MAINTENANCE cap violation at step 11
pre-push-fast. The failure was a deterministic classification issue
(MAINTENANCE needs `unblocks_wave_id` OR reclassification). A reasonable Tier
1 or Tier 3 recovery could have either (a) proposed the FOUNDER_OVERRIDE +
unblocks_wave_id fix, or (b) suggested reclassifying to L4_ENABLER. Neither
ran — commit_executor just exited 1 and left the rollback-and-retry work to
the human.

**Structural fix candidate:** widen the trigger at
`commit_executor.py:3989` to route MORE failure classes through
`attempt_recovery`:
- `pre_push_failed` (many sub-causes; Tier 3 diagnosis)
- `stage_failed` (Tier 1 index-lock class)
- `implementer_error` / `bridge_error` (routes to hybrid)
- `l4_contract_violation` (Tier 3 proposes override / reclassify / unblocks)

Alternatively: route ALL non-`success`/`held` statuses through `attempt_recovery`
(universal gate) and let the classifier decide what's recoverable.

**Acceptance criteria:** regression test in `test_commit_executor_receipt.py`
verifies `attempt_recovery` is invoked for each of the widened failure
classes; recovery_gate's classifier has explicit class for each.

## Gap 4 (closed in THIS wave): MISSING_BRIDGE_CONFIG chicken-and-egg

Closed by `recovery_gate.py` changes in the
`pipeline-hardening-bundle-2026-04-17` wave:
- New `FailureClass.MISSING_BRIDGE_CONFIG` Tier 1 classifier
- `fix_missing_bridge_config()` deterministic fixer (walks from worktree `.git`
  pointer to main repo, copies `bridge_config.json`)
- Registered in `_TIER1_FIXES`
- 7 regression tests (3 classifier + 4 fixer)

## Related deferreds (same session)

- `commit_executor_step15_ci_poll_timeout_2026-04-17.md` — CLOSED by PR #787
- `commit_executor_bot_findings_false_positive_2026-04-17.md` — open
- `recovery_gate_tier3_unactionable_exhaust_2026-04-17.md` — open
- `commit_executor_step16_cascade_block_2026-04-17.md` — open
- `pipeline_monitor_watcher_staleness_2026-04-17.md` — open (from PR #783)

## Why this is BLOCKING (not non_blocking)

Hybrid recovery was founder-directed as a pipeline-hardening investment
(PR #778) and enabled in PR #786. Without these 3 gap fixes, the enablement is
symbolic — hybrid has never productively delegated. Each of the 3 fixes is a
small bounded wave (~30-100 LOC each) that unlocks material pipeline
resilience.
