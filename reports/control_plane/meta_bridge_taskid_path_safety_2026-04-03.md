# Meta-Bridge Task-ID Path Safety

Date: 2026-04-03
Status: Implementation ready for routed supervisor
Task: [META-BRIDGE-BOUNDED-REVIEW-FIX]
Wave ID: meta-bridge-taskid-path-safety-2026-04-03

## Scope

Make the pre-commit and post-merge meta-bridge reviewers safe for exact tracker
task IDs that contain `/`, so task-bound package identity can stay honest
without crashing prompt/raw filename creation under `.agent_bus/meta/`.

## Changed surfaces

- `mu/tools/agents/meta_bridge_supervisor.py`
- `mu/tests/tools/test_meta_bridge_supervisor.py`

## Proof points

1. The meta-bridge now sanitizes `task_id` before embedding it in the reviewer
   `job_id` / `turn_id`, so prompt and raw-output paths stay inside the
   expected `.agent_bus/meta/prompts/` and `.agent_bus/meta/raw/` directories.
2. Exact tracker IDs like
   `[PIPELINE-RECOVERY/pipeline-monitor-worktree-rebind-2026-04-03]` no longer
   raise `FileNotFoundError` before the reviewer can emit a decision.
3. Regression coverage proves slash-bearing task IDs for both the pre-commit
   and post-merge reviewer entrypoints, plus the shared filename token helper.

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_meta_bridge_supervisor.py -q --tb=short`
- `./tools/checks/check_docs_consistency.sh`
- `./tools/session/founder_session_attest.sh redteam`
- `python3 tools/checks/enforce_l4_execution_contract.py --staged`
- `env -u GIT_DIR -u GIT_WORK_TREE -u GIT_COMMON_DIR PYTHONHASHSEED=0 python3 mu/tools/executors/executor_dispatch.py pre-commit-supervisor --package .scratch/auto_supervisor_package.json --json -v`
