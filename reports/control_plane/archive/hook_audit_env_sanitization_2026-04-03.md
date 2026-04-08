# Hook Audit Env Sanitization

Date: 2026-04-03
Status: Implementation ready for routed supervisor
Task: [PIPELINE-RECOVERY/hook-audit-env-sanitization-2026-04-03]
Wave ID: hook-audit-env-sanitization-2026-04-03

## Scope

Clear inherited Git hook-local environment variables in the routed audit
entrypoints before they spawn deeper pipeline checks, so nested git-aware tests
rediscover the active linked worktree instead of inheriting hook-only state.

## Changed surfaces

- `dev.sh`
- `mu/tools/audits/audit_all.sh`
- `mu/tools/audits/audit_fast.sh`
- `mu/tools/hooks/pre-push-fast`
- `mu/tests/structural/test_subtree_root_guard.py`

## Proof points

1. `mu/tools/hooks/pre-push-fast`, `dev.sh`,
   `mu/tools/audits/audit_fast.sh`, and `mu/tools/audits/audit_all.sh` now
   centralize `sanitize_local_git_env()` and call it before they hand control
   to deeper audits.
2. That helper uses `git rev-parse --local-env-vars`, so the entrypoints clear
   only git-local hook variables such as `GIT_DIR`, `GIT_WORK_TREE`, and
   `GIT_COMMON_DIR` instead of guessing which variables to unset.
3. Structural regression coverage in
   `mu/tests/structural/test_subtree_root_guard.py` locks that sanitization
   contract directly for the hook and audit entrypoints.
4. A simulated hook-env proof reproduces the old failure class and then proves
   that representative untracked-artifact, meta-bridge, and
   ensure_feature_branch checks return to green once the inherited git-local
   variables are cleared.

## Validation

- `bash -n mu/tools/hooks/pre-push-fast dev.sh mu/tools/audits/audit_fast.sh mu/tools/audits/audit_all.sh`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/structural/test_subtree_root_guard.py::TestUntrackedArtifactChecker::test_pre_push_sanitizes_hook_git_env mu/tests/structural/test_subtree_root_guard.py::TestUntrackedArtifactChecker::test_dev_and_audit_fast_sanitize_hook_git_env -q --tb=short`
- `GIT_DIR=$(git rev-parse --git-dir) GIT_WORK_TREE=$(git rev-parse --show-toplevel) GIT_COMMON_DIR=$(git rev-parse --git-common-dir) bash -lc 'set -e; git_local_env="$(git rev-parse --local-env-vars 2>/dev/null || true)"; if [ -n "$git_local_env" ]; then unset $git_local_env; fi; PYTHONHASHSEED=0 python3 -m pytest -q --tb=short mu/tests/structural/test_subtree_root_guard.py::TestUntrackedArtifactChecker::test_checker_fails_on_violation mu/tests/tools/test_meta_bridge_supervisor.py::TestRunMetaBridgeLiveRouting::test_all_passed_commit_go_succeeds mu/tests/tools/test_executor_dispatch.py::TestEnsureFeatureBranch::test_9_already_on_target_continues'`
