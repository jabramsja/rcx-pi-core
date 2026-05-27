# Commit Executor Behind-Base Autorefresh

Date: 2026-05-27
Status: Phase B (implemented; commit pending)
Phase-A-Lock: LOCKED
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: commit-executor-behind-base-autorefresh-2026-05-27
Class: L4_ENABLER
Target Gate: G8
Lane: control-surface (commit executor / recovery / operator prompt truth)
Founder authorization: in-session direction to use the pipeline, avoid `run_review.py`, repair contradictions, and mechanize the #1022 behind-base miss.
Founder override: FOUNDER_OVERRIDE:commit-executor-behind-base-autorefresh-2026-05-27

## Problem

PR #1022 became stale after PR #1026 merged. Direct REST evidence captured in
the operator session showed `mergeable_state=behind`, while the commit
executor's Step 14 pre-check only inspected `gh pr view --json
mergeable,mergeStateStatus` for `mergeable=CONFLICTING` and
`mergeStateStatus=DIRTY`.

The local reproduction before this wave returned `None` from
`_check_pr_conflict_state(...)` for a payload shaped as
`{"mergeable":"MERGEABLE","mergeStateStatus":"CLEAN","mergeable_state":"behind"}`.
That proved the executor did not route the behind-base state into its existing
merge-base refresh path.

## Scope

- `mu/tools/executors/commit_executor.py`
- `mu/tests/tools/test_commit_executor_step14_conflict_precheck.py`
- `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
- `mu/tools/executors/recovery_gate.py`
- `mu/tests/tools/test_recovery_gate.py`
- `mu/docs/agents/AgentRunbook.v0.md`
- `.claude/rules/agents.md`
- `.claude/skills/wave/SKILL.md`
- `TASKS.md`
- `reports/control_plane/commit-executor-behind-base-autorefresh-2026-05-27.md`
- `reports/l4_wave_indicators/commit-executor-behind-base-autorefresh-2026-05-27.json`

No runtime, substrate, seed, scheduler, registry, projection, or production
Mu semantic file is in scope.

## Mechanical Fix

- Step 14 now treats GraphQL `mergeStateStatus=BEHIND` and REST
  `mergeable_state=behind` as stale-base states that need the same base-branch
  merge and push path as `CONFLICTING` and `DIRTY`.
- The REST fallback uses the origin owner/repo and fails open on lookup or JSON
  errors, preserving the pre-check's performance-optimization role.
- Recovery classification now recognizes `mergeStateStatus=BEHIND` and
  `mergeable_state=behind` signatures as `FailureClass.PR_CONFLICTING`, so
  routed recovery reaches the existing stale-base fixer family instead of
  falling through to an unknown failure class.
- Visible operator guidance now reflects the active executor config:
  `agent_review_enabled=false` means Codex waves use dispatcher, Phase B,
  pre-commit supervisor, and commit executor, not `run_review.py`.

## Evidence

- `codex-rcx-preflight redteam` completed successfully, including founder
  guard and founder attestation.
- `gh pr view 1022 --json number,state,mergedAt,headRefOid,mergeCommit,statusCheckRollup`
  showed PR #1022 merged at `2026-05-27T07:27:35Z`, head `360b0d7e`, merge
  commit `a1483780`, and all seven expected checks successful.
- Pre-fix diagnostic command with a REST-behind payload returned `None` from
  `_check_pr_conflict_state(...)`.
- Focused post-fix tests:
  `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_step14_conflict_precheck.py mu/tests/tools/test_commit_executor_step14_autoresolve.py mu/tests/tools/test_recovery_gate.py -q --tb=short`
  exited 0.
- `python3 -m py_compile mu/tools/executors/commit_executor.py mu/tools/executors/recovery_gate.py`
  exited 0.
- `git diff --check` exited 0.

## Proof Limit

This wave proves the executor and recovery classifier now recognize the
behind-base state and route it through the already-existing merge-base refresh
mechanism. It does not change branch protection, GitHub workflow triggers, CI
test selection, or production Mu runtime semantics.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `commit-executor-behind-base-autorefresh-2026-05-27`
- Active packet: `reports/control_plane/commit-executor-behind-base-autorefresh-2026-05-27.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `52827ebe832f38793375494ee04348c7b8ed725ac59f66c4c0580ab0f0857d9a`
- Indicator artifact: `reports/l4_wave_indicators/commit-executor-behind-base-autorefresh-2026-05-27.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_step14_conflict_precheck.py mu/tests/tools/test_commit_executor_step14_autoresolve.py mu/tests/tools/test_recovery_gate.py -q --tb=short && python3 -m py_compile mu/tools/executors/commit_executor.py mu/tools/executors/recovery_gate.py && git diff --check`.
- Evidence delta: (1) `commit_executor._check_pr_conflict_state()` now treats GraphQL `mergeStateStatus=BEHIND` and REST `mergeable_state=behind` as stale-base states that take the existing fetch/merge/push auto-refresh path. (2) `recovery_gate.classify_failure()` recognizes behind-base signatures as `FailureClass.PR_CONFLICTING`, preserving routed recovery for the same stale-base family. (3) Visible Codex/Claude operator guidance now records that the current Codex path uses dispatcher, Phase B, pre-commit supervisor, and commit executor while `agent_review_enabled=false`, instead of directing Codex sessions to `run_review.py`.
- Evidence handles:
  - `control_packet`: `reports/control_plane/commit-executor-behind-base-autorefresh-2026-05-27.md`
  - `indicator`: `reports/l4_wave_indicators/commit-executor-behind-base-autorefresh-2026-05-27.json`
- Current staged files:
  - `.claude/rules/agents.md`
  - `.claude/skills/wave/SKILL.md`
  - `TASKS.md`
  - `mu/docs/agents/AgentRunbook.v0.md`
  - `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
  - `mu/tests/tools/test_commit_executor_step14_conflict_precheck.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/commit-executor-behind-base-autorefresh-2026-05-27.md`
  - `reports/l4_wave_indicators/commit-executor-behind-base-autorefresh-2026-05-27.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
