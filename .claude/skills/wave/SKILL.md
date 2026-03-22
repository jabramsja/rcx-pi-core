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
2. Runs SDK agent review
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
3. Runs SDK agents + bridge convergence loop
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

## Fallback: Manual Protocol

During transition (rollout step 5), the manual protocol is still available:
1. Design the plan manually
2. Run agents: `python tools/runners/run_review.py --pr --depth full`
3. Bridge: `python3 tools/agents/bridge_supervisor.py review --task-file <file> --reviewer codex -v`
4. Loop until converged
5. Pre-commit supervisor → commit → push → PR → CI → merge_pr.sh --sweep
6. Post-merge supervisor → next step

## Critical Rules
- **Never collapse the loop**: Bridge loop must converge before commit.
- **Bridge sees the diff**: Phase B bridge reviews get the actual diff.
- **Pre-commit supervisor before every commit**: No skipping receipt check.
- **Post-merge supervisor after every merge**: Route the next step.
- **Use executors when available**: Manual fallback only when needed.
