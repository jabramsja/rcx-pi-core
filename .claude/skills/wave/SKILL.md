---
name: wave
description: RCX Wave Protocol Executor
---

# /wave — RCX Wave Protocol Executor

Executes the Phase A/B wave protocol via repo-local executors.

## Usage
- `/wave plan <name>` — Start Phase A via phase_a_executor
- `/wave implement <plan-path>` — Start Phase B via phase_b_executor
- `/wave dispatch` — Read post-merge routing record and dispatch to correct executor
- `/wave status` — Show current wave state

## Executor Dispatch (preferred path)

### `/wave dispatch`
Read the post-merge routing record and dispatch to the correct executor:
```bash
python3 mu/tools/executors/executor_dispatch.py --json --skip-freshness
```
This reads `.agent_bus/meta/post_merge_routing.json` and invokes:
- `CONTINUE_DIALECTIC` → `dialectic_executor.py`
- `ROUTE_PHASE_A` → `phase_a_executor.py`
- `ROUTE_PHASE_B` → `phase_b_executor.py`
- `COMMIT_GO` → `commit_executor.py`
- `STOP_FOR_FOUNDER` / `STOP_FOR_TRIAGE_DISCUSSION` → report and stop

## Phase A: Design via Executor

### `/wave plan <name>`
Invoke the Phase A executor:
```bash
python3 mu/tools/executors/phase_a_executor.py --plan-name <name> -v --json
```
The executor:
1. Creates a plan packet draft in `reports/control_plane/`
2. Skips SDK agent review when `executor_config.json` sets
   `agent_review_enabled=false`
3. Loops bridge until only non-blockers remain
4. Sets Phase-A-Lock: LOCKED

## Phase B: Implementation via Executor

### `/wave implement <plan-path>`
Invoke the Phase B executor:
```bash
python3 mu/tools/executors/phase_b_executor.py --plan <plan-path> -v --json
```
The executor:
1. Reads the locked plan
2. Detects code changes
3. Skips SDK agents when `executor_config.json` sets
   `agent_review_enabled=false`; uses the bridge convergence loop
4. Prepares commit handoff

## Commit Pipeline via Executor

After Phase B converges and pre-commit supervisor approves:
```bash
python3 mu/tools/executors/commit_executor.py --handoff <path> -v --json
```

## Post-Merge Supervisor

After merge, run the post-merge supervisor to route the next step:
```bash
python3 mu/tools/agents/meta_bridge_supervisor.py --mode post-merge --package <path> --json -v
```

## Bootstrap Exception Boundary

The executor pipeline is the normal wave path. `BOOTSTRAP_PHASE_B_EXCEPTION`
is the only exception, and only when a wave directly changes the
executor/implementer surfaces that would otherwise validate or dispatch that
same wave.

When the exception applies:
1. Cite the self-dependency that prevents normal executor validation.
2. Keep the exception packet-bound to the named wave and touched surfaces.
3. Use the narrowest repo-local executor or supervisor entrypoint still
   available.
4. Stop for founder direction if the exception cannot be proven from code
   truth.

## Critical Rules
- **Never collapse the loop**: Bridge loop must converge before commit.
- **Bridge sees the diff**: Phase B bridge reviews get the actual diff.
- **Pre-commit supervisor before every commit**: No skipping receipt check.
- **Post-merge supervisor after every merge**: Route the next step.
- **Use executors as the wave path**: `BOOTSTRAP_PHASE_B_EXCEPTION` is narrow,
  packet-bound, and limited to executor/implementer self-dependency cases.
