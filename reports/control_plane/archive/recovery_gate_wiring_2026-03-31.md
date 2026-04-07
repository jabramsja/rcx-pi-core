# Recovery Gate Wiring — Wire recovery_gate.py into executor_dispatch.py

**Wave class:** L4_ENABLER
**Task:** [PIPELINE-RECOVERY]
**Priority:** #1 from session handoff
**Scope:** ~20 lines of glue in executor_dispatch.py + tests

---

## Problem

`recovery_gate.py` (Phase 1) is a library sitting on disk. It has a classifier, Tier 1 auto-fix functions, and a recovery log. But nothing calls it. The dispatcher's retry loop doesn't know about recovery.

## Solution

Wire `attempt_recovery()` into the dispatcher's retry loop so that failed dispatches get classified and Tier 1 fixes applied before retrying.

### Changes Required

#### 1. executor_dispatch.py — Import recovery_gate

Add import block (same pattern as existing executor_common import):
```python
try:
    from recovery_gate import attempt_recovery
except ImportError:
    # fallback importlib loading (same pattern as executor_common)
```

#### 2. executor_dispatch.py — Refactor retry loop (lines 1098-1144)

Convert `for attempt in range(1, max_attempts + 1)` to `while attempt < max_attempts` so recovery can extend the attempt budget.

Insert recovery gate call after terminal-outcome check, before max-attempts break:

```python
# After terminal check, before max_attempts check:
if result.get("status") == "failed":
    _wave_id = normalize_wave_id(record.get("wave_name", ""))
    recovery = attempt_recovery(repo_root, result, _wave_id)
    result["recovery"] = recovery
    if verbose:
        print(f"[dispatch] Recovery: class={recovery.get('failure_class')} "
              f"tier={recovery.get('tier')} recovered={recovery.get('recovered')}")
    if recovery.get("recovered"):
        # Recovery succeeded — grant one extra attempt (don't increment counter)
        _clear_phase_b_state_for_retry(repo_root, result, verbose=verbose)
        if not args.routing_record and not _is_chained_commit_failure(result):
            refreshed, refresh_record = _auto_refresh_routing(...)
            if refreshed and refresh_record is not None:
                record = refresh_record
        continue  # retry dispatch without counting against budget
    elif recovery.get("exhausted"):
        if verbose:
            print("[dispatch] Recovery exhausted — not retrying")
        break
```

#### 3. test_executor_dispatch.py — Add recovery integration tests

- `test_recovery_gate_wired_on_failure` — mock dispatch to fail with stale lock, verify attempt_recovery called
- `test_recovery_grants_extra_attempt` — verify recovery success grants one extra retry
- `test_recovery_exhausted_stops_retry` — verify exhausted recovery breaks the loop
- `test_recovery_not_called_on_success` — verify recovery skipped for successful dispatch
- `test_recovery_not_called_on_terminal` — verify terminal outcomes bypass recovery
- `test_recovery_result_in_dispatch_output` — verify recovery info attached to result

### Files touched
- `mu/tools/executors/executor_dispatch.py` (import + retry loop refactor)
- `mu/tests/tools/test_executor_dispatch.py` (6 new tests)

### Files also touched (Codex bridge + pre-commit findings)
- `mu/tools/executors/recovery_gate.py` — demoted STALE_GIT_INDEX_LOCK from Tier 1 to Tier 2 (no sound ownership check, Codex review), safe empty wave_id (noop instead of silent delete)
- `mu/tests/tools/test_recovery_gate.py` — updated tests for Tier 2 demotion + cross-file mock fix
- `mu/tools/executors/executor_dispatch.py` — also fixed task_id validation bypass (bidirectional check)

### Validation
- `pytest mu/tests/tools/test_executor_dispatch.py -v`
- `pytest mu/tests/tools/test_recovery_gate.py -v`
- `./tools/audit_fast.sh`
