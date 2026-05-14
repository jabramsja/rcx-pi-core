# Commit-Executor-Index-Lock-Classifier-Precedence-2026-05-14

Date: 2026-05-14
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: commit-executor-index-lock-classifier-precedence-2026-05-14
Class: L4_ENABLER
Phase-A-Lock: LOCKED
Purpose: Prevent direct git `index.lock` recovery diagnostics from being shadow-classified as stale-active tracker repair.

## Scope: Files/Directories In Scope

Implementation write scope if Phase B proceeds:
- `mu/tools/executors/recovery_gate.py`
- `mu/tests/tools/test_recovery_gate.py`
- `TASKS.md`
- `reports/control_plane/commit-executor-index-lock-classifier-precedence-2026-05-14_2026-05-14.md`
- `reports/l4_wave_indicators/commit-executor-index-lock-classifier-precedence-2026-05-14.json`

Read-only grounding/evidence scope:
- `TASKS.md:344`
- `TASKS.md:424`
- `.agent_bus/recovery/recovery_status.json`
- `.agent_bus/recovery/recovery_log.json:5413-5423`
- `.agent_bus/executors/commit_executor_n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14.json`
- `mu/tools/executors/recovery_gate.py:355-356`
- `mu/tools/executors/recovery_gate.py:378-379`
- `mu/tools/executors/recovery_gate.py:483-492`
- `mu/tools/executors/recovery_gate.py:1337-1353`
- `mu/tools/executors/recovery_gate.py:1508-1596`
- `mu/tools/executors/commit_executor.py:1940-1966`
- `mu/tools/executors/commit_executor.py:8200-8228`
- `mu/tests/tools/test_recovery_gate.py:1864-1871`

## Work Items

1. Reproduce or falsify the suspected classifier-precedence gap with a focused recovery-gate regression shape: direct `git_commit` reason/errors mention `index.lock` and `remove the file manually`, while broader stdout/stderr also contains stale-NEXT or `check_stale_next_items.sh` wording.
2. If the mixed-signal regression reproduces, make the smallest mechanical recovery-gate change so direct git-lock diagnostics from `stage_files`, `git_commit`, feature-branch restore/switch, or equivalent git-lock steps are classified as `STALE_GIT_INDEX_LOCK` before broad stale-active output can route to `fix_stale_active_items`.
3. Preserve existing behavior: permission-denied/live `index.lock` terminal handling remains fail-closed, real stale-active pre-push failures still route to `fix_stale_active_items`, and the already covered self-cleared `index.lock` retry behavior remains intact.
4. Add focused tests in `mu/tests/tools/test_recovery_gate.py` for the mixed-signal misclassification, real stale-active routing, and existing self-cleared `index.lock` recovery behavior.
5. If Phase B proceeds, update `TASKS.md`, keep this governing packet current, and collect the L4 indicator at `reports/l4_wave_indicators/commit-executor-index-lock-classifier-precedence-2026-05-14.json`.

## Constraints

- Do not implement manually outside the dispatcher/pipeline recovery path.
- Do not touch Claude-related files.
- Do not modify runtime, substrate, seed, scheduler, registry, production `/mu` semantics, Stage0, parity semantics, or host-oracle surfaces.
- Do not broaden commit-executor semantics beyond recovery classification for git-lock failures.
- Do not delete `.git` internals or add recovery behavior that removes a live lock file.
- Do not duplicate the prior self-cleared `index.lock` recovery work recorded at `TASKS.md:424`; this wave is only the classifier-precedence gap closure.
- Do not treat stale packet wording as proof that every listed work item remains unlanded; current code truth must remove already-implemented items from pending work and acceptance criteria when directly proven.

## Stop Conditions

- Stop with NO-GO if the focused mixed-signal regression does not reproduce; record exact evidence and write the next diagnostic packet instead of implementing a speculative fix.
- Stop if the required fix would move semantic authority into host runtime/substrate code or production `/mu` behavior.
- Stop if preserving direct `index.lock` classification would break real stale-active pre-push routing to `fix_stale_active_items`.
- Stop if the only apparent recovery path requires deleting `.git/index.lock` or relaxing permission-denied/live-lock fail-closed handling.
- Stop if Phase B requires files outside the in-scope list above.

## Acceptance Criteria

- Phase A packet contains an explicit in-scope file/directory list and detector-visible L4 authorization for this wave.
- Focused regression either reproduces the mixed `index.lock` plus stale-active signal and proves the fix, or falsifies it with a NO-GO and exact diagnostic evidence.
- Direct git-lock diagnostics from `stage_files`, `git_commit`, feature-branch restore/switch, or equivalent git-lock steps cannot be shadowed by broad stale-active output.
- Real stale-active pre-push failures still route to `fix_stale_active_items`.
- Existing self-cleared `index.lock` retry behavior remains covered and passing.
- If implemented, required validation passes: targeted `mu/tests/tools/test_recovery_gate.py` pytest, `python3 -m py_compile mu/tools/executors/recovery_gate.py`, staged L4 execution contract, host semantics ratchet, host authority inventory ratchet, docs consistency, and `git diff --check`.
- If implemented, `TASKS.md`, this packet, and the L4 indicator path all bind to `commit-executor-index-lock-classifier-precedence-2026-05-14`.

## Grounding / Authorization

- `TASKS.md:344` grounds the incident source: the `n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14` L4_ENABLER handoff reached commit execution with pre-commit supervisor receipt pending.
- `TASKS.md:424` records prior pipeline recovery work that already handled self-cleared `.git/index.lock` and embedded `stage_files` classification. This wave must remain a narrow gap closure for classifier precedence, not a duplicate broad redesign.
- Governing packet: `reports/control_plane/commit-executor-index-lock-classifier-precedence-2026-05-14_2026-05-14.md`.
- FOUNDER_OVERRIDE:commit-executor-index-lock-classifier-precedence-2026-05-14
- Authorization: standing pipeline-bug-fix authorization for bounded control-plane/pipeline recovery L4_ENABLER wave `commit-executor-index-lock-classifier-precedence-2026-05-14`.

## Phase B Implementation Evidence

- Reproduction: before the classifier change, a focused mixed signal with embedded `git_commit` errors naming `.git/index.lock` and `remove the file manually to continue`, plus broader stale-NEXT / `check_stale_next_items.sh --fix` chatter, returned `stale_active_items` tier 2.
- Code change: `recovery_gate.py` now evaluates permission-denied index-lock diagnostics fail-closed, then direct git-step index-lock diagnostics, before the broad stale-active checker route. The existing self-cleared index-lock retry/demotion behavior remains in `fix_stale_git_index_lock`; no `.git/index.lock` deletion path was added.
- Direct git-lock precedence covers structured `stage_files`, `git_commit`, `ensure_feature_branch`, bridge staging, reentry staging, and equivalent staging/rebind git-lock steps without changing commit-executor semantics.
- Regression coverage added in `mu/tests/tools/test_recovery_gate.py` for mixed-signal precedence, permission-denied plus stale-active fail-closed precedence, real pre-push stale-active routing to `fix_stale_active_items`, and the already covered self-cleared index-lock retry path.
- Same-wave tracker binding: `TASKS.md` now carries detector-visible `commit-executor-index-lock-classifier-precedence-2026-05-14` L4_ENABLER authority, packet path, evidence command, and indicator artifact binding.
- Indicator artifact: `reports/l4_wave_indicators/commit-executor-index-lock-classifier-precedence-2026-05-14.json`.

## Required Validation Set

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py --tb=short -p no:cacheprovider`
- `python3 -m py_compile mu/tools/executors/recovery_gate.py`
- `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id commit-executor-index-lock-classifier-precedence-2026-05-14 --output reports/l4_wave_indicators/commit-executor-index-lock-classifier-precedence-2026-05-14.json`
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id commit-executor-index-lock-classifier-precedence-2026-05-14`
- `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
- `python3 tools/checks/check_host_authority_inventory_ratchet.py`
- `./tools/checks/check_docs_consistency.sh`
- `git diff --check`

## Validation Results

- Focused pre-fix reproduction returned `stale_active_items` tier 2, confirming the classifier-precedence gap.
- Focused new regression subset: `4 passed in 2.05s`.
- Targeted recovery-gate file: `1027 passed in 134.80s (0:02:14)`.
- `python3 -m py_compile mu/tools/executors/recovery_gate.py`: passed.
- Indicator collection wrote `reports/l4_wave_indicators/commit-executor-index-lock-classifier-precedence-2026-05-14.json`.
- Staged L4 execution contract: `L4_ENABLER compliant` for 5 changed files, 0 runtime files.
- Host semantics ratchet: passed with no increases.
- Host authority inventory ratchet: passed with no new total-inventory or authority-subset sites.
- Docs consistency: passed.
- `git diff --check`: passed.

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `commit-executor-index-lock-classifier-precedence-2026-05-14`
- Active packet: `reports/control_plane/commit-executor-index-lock-classifier-precedence-2026-05-14_2026-05-14.md`
- Indicator artifact: `reports/l4_wave_indicators/commit-executor-index-lock-classifier-precedence-2026-05-14.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/commit-executor-index-lock-classifier-precedence-2026-05-14_2026-05-14.md`
  - `reports/l4_wave_indicators/commit-executor-index-lock-classifier-precedence-2026-05-14.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `commit-executor-index-lock-classifier-precedence-2026-05-14`
- Active packet: `reports/control_plane/commit-executor-index-lock-classifier-precedence-2026-05-14_2026-05-14.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `86102802843d921bdafaf2112e6c83bc8743f086969e35e66765e5b436c77a41`
- Indicator artifact: `reports/l4_wave_indicators/commit-executor-index-lock-classifier-precedence-2026-05-14.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/commit-executor-index-lock-classifier-precedence-2026-05-14_2026-05-14.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/commit-executor-index-lock-classifier-precedence-2026-05-14.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/commit-executor-index-lock-classifier-precedence-2026-05-14_2026-05-14.md`
  - `reports/l4_wave_indicators/commit-executor-index-lock-classifier-precedence-2026-05-14.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
