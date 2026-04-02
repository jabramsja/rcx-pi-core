# Deferred Clean Replay Hardening

Date: 2026-04-02
Parent task: `[DEFERRED-CONSOLIDATION]`
Lane: control-surface
Classification: L4_ENABLER
Status: LANDED

## Why This Slice Exists

The first truly clean E5/E6 replay still surfaced control-surface gaps before the
deferred-consolidation work itself could proceed honestly:

1. Stub rewrite prompts were still permissive enough to let the implementer
   spelunk downstream implementation files instead of rewriting the packet first.
2. Packet-review prompts were still broad enough to waste review budget on
   governing packets and prior replay notes even when the packet state alone was
   sufficient.
3. Direct interruption of `executor_dispatch.py` could leave child Phase A /
   bridge processes alive, which in turn stranded stale bridge locks across
   replays.
4. The commit gate's targeted pytest run still used pytest's default import
   mode, so a single gate invocation across mirrored `mu/tests/` and `tests/`
   files with the same basename could fail at collection time instead of
   reporting real test regressions.
5. The same targeted pytest gate still used a fixed 120 second timeout, which
   was too small for the real five-file mirrored control-surface suite.

This slice hardens those three surfaces, records the live replay proof, and
keeps the actual E5/E6 rerun deferred until the repo baseline is clean again.

## Files Changed

- `conftest.py`
- `mu/tools/agents/bridge_supervisor.py`
- `mu/tools/executors/commit_executor.py`
- `mu/tools/executors/executor_dispatch.py`
- `mu/tools/executors/phase_a_executor.py`
- `mu/tests/tools/test_agent_bridge_supervisor.py`
- `mu/tests/tools/test_commit_executor_receipt.py`
- `mu/tests/tools/test_executor_dispatch.py`

## What Landed

- Stub-specific Phase A implementer guidance:
  - when the current packet is still an obvious stub, the implementer is now
    told to stay packet-scoped, use the cited `TASKS.md` and governing-plan
    evidence, and stop after rewriting the packet into the first real plan
  - it is explicitly forbidden from spelunking unrelated downstream
    implementation files just to decide whether work already landed
- Bounded packet-review scope:
  - packet-review prompts now tell the reviewer to read only the exact
    `TASKS.md` block needed for authorization
  - for obvious stubs, the reviewer is explicitly told not to open governing
    packets, prior replay notes, or downstream implementation files before
    issuing `REQUEST_CHANGES`
- Dispatcher interrupt cleanup:
  - `_run_executor_in_group()` now installs temporary `SIGINT` / `SIGTERM`
    handlers and a broad exception cleanup path that reap the child executor
    process tree before re-raising
  - this prevents orphaned `phase_a_executor.py` / `bridge_supervisor.py`
    processes from leaving stale bridge locks behind when a replay is aborted
- Commit gate pytest isolation:
  - `_run_pytest_on_files()` now invokes pytest with `--import-mode=importlib`
    for targeted file runs
  - this lets the commit gate run mirrored legacy and modern test files with
    the same basename in one invocation without tripping pytest's import-file
    mismatch trap
  - a repo-root fallback `mock_routing_record` fixture now keeps the mirrored
    dispatcher suites sharing the same routing stub when the combined gate runs
    both trees together
  - the targeted pytest timeout now scales with the number of affected test
    files instead of failing at a fixed 120 second ceiling

## Live Replay Proof

Clean-worktree replay against the deferred E5/E6 packet:

1. Phase A created the stub packet.
2. Bridge round 1 rejected the stub from packet + `TASKS.md` evidence.
3. The implementer rewrote the same canonical packet into a real plan.
4. Bridge round 2 performed a bounded packet review instead of widening into
   prior replay state.
5. That round returned `REQUEST_CHANGES` for a real policy-bound reason:
   `git status --short` was already dirty because this hardening slice itself
   was now present in the replay worktree.

That stop is correct. It means the clean rerun must restart from a fresh
baseline after this slice lands, rather than pretending E5/E6 can continue from
a worktree already contaminated by new control-surface edits.

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_executor_dispatch.py -q --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_agent_bridge_supervisor.py -q --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_commit_executor_receipt.py -q --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_agent_bridge_supervisor.py mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_executor_dispatch.py tests/tools/test_commit_executor_receipt.py tests/tools/test_executor_dispatch.py -q --tb=short`
- `./tools/checks/check_docs_consistency.sh`
- `./tools/session/founder_session_guard.sh closeout --run`
- `./tools/session/founder_session_attest.sh closeout`

## Invariant Tuple

- debt before/after: unchanged
- host semantics before/after: unchanged
- runtime/substrate delta: none; control-surface only

## Next Step

Rerun the E5/E6 deferred-consolidation wave from a fresh clean worktree on top
of this slice. Do not continue the current replay lane, because the bridge has
already proved that its baseline is no longer clean.
