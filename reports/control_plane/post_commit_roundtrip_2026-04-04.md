# Post-Commit Round-Trip

Date: 2026-04-04
Status: In progress
Task: [PIPELINE-RECOVERY/post-commit-roundtrip-2026-04-04]
Wave ID: post-commit-roundtrip-2026-04-04

## Scope

1. keep the baked-in executor fallback config aligned with the checked-in live
   `executor_config.json`
2. route that fix through the real `commit` executor instead of a manual
   commit/push/merge path
3. use the merged result as the base for the next end-to-end recovery proof
4. keep stub-only Phase A packet rewrites from sitting on the full generic
   implementer timeout budget before they fail stale
5. retire the old direct `recovery_live_probe_2026-04-03` shortcut as the
   next-proof path, because current bridge review now rejects that ad hoc packet
   as an unauthorized tracked-plan surface

## Why this wave exists

The control plane already depends on long-running Phase A / Phase B / commit
surfaces. If a linked worktree or partial local config falls back to stale
baked-in defaults, the live pipeline can silently run with older budgets and
backend choices than the repo-tracked operational config claims.

## Changed surfaces

- `mu/tools/executors/executor_common.py`
- `mu/tools/executors/phase_a_executor.py`
- `mu/tests/tools/test_executor_dispatch.py`
- `reports/control_plane/post_commit_roundtrip_2026-04-04.md`
- `CHANGELOG.md`
- `TASKS.md`

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_executor_dispatch.py -k 'phase_a_implementer_prompt_stays_packet_scoped or deferred_agent_review_accepts_authorization_section_alias' -q --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_executor_dispatch.py -q`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -q`

## Current proof status

- The old direct probe command
  `env -u GIT_DIR -u GIT_WORK_TREE -u GIT_COMMON_DIR RCX_AGENT_PREFLIGHT_FORCE_FAIL=1 PYTHONHASHSEED=0 python3 mu/tools/executors/executor_dispatch.py phase-a --plan-name recovery_live_probe_2026-04-03 --json -v`
  is no longer a clean proof of routed recovery on current `dev`.
- On the current review contract, bridge review now correctly classifies
  `reports/control_plane/recovery_live_probe_2026-04-03_2026-04-05.md` as an
  ad hoc unauthorized packet instead of a valid tracked plan surface.
- The next end-to-end proof should therefore use the real routed
  post-merge/commit path, not the obsolete direct `phase-a --plan-name ...`
  shortcut.

## Invariant tuple

- runtime/substrate delta: none
- host semantics delta: none
- scope class: control-surface reliability only
