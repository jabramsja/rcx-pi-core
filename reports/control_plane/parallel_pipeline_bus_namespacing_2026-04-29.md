# Parallel Pipeline Bus Namespacing

Date: 2026-04-29
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Phase-A-Lock: LOCKED
Task: [PARALLEL-PIPELINE]
Wave ID: parallel-pipeline-bus-namespacing-2026-04-29
Purpose: Plan the first parallel-pipeline slice: executor and bridge agent-bus namespacing without widening runtime/substrate semantics.

## Scope

- Add a namespaced agent-bus path mechanism for the executor and bridge control surfaces currently hardcoded to `.agent_bus`.
- Add repository ignore-rule coverage for repo-root namespaced bus runtime artifacts so `.agent_bus-*` remains untracked runtime state alongside `.agent_bus/`.
- Add commit-executor protection so repo-root namespaced bus runtime artifacts are blocked from commit paths even when a handoff tries to force-add them.
- Keep recovery status/log persistence bus-scoped, while preserving the recovery learned-pattern store as an explicit canonical shared default-bus exception.
- Production files in scope:
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/recovery_gate.py`
  - `mu/tools/executors/phase_a_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/agents/bridge_supervisor.py`
  - `mu/tools/agents/meta_bridge_client.py`
  - `mu/tools/agents/meta_bridge_supervisor.py`
  - `mu/tools/observability/pipeline_agent_pager.py`
  - `mu/tools/observability/pipeline_monitor.sh`
  - `mu/tools/observability/pipeline_dashboard.py`
- Repository ignore surface in scope:
  - `.gitignore` (only the minimal rule needed for repo-root `.agent_bus-*` namespaced bus directories)
- Test directories in scope, limited to tests that directly exercise the production files listed above:
  - `tests/`
  - `mu/tests/`
- No other files or directories are in scope for this Phase A packet.

## Work Items

1. Introduce a single resolver for the active agent bus directory, defaulting to `.agent_bus` and accepting an explicit executor-owned `--bus-dir` input only when it resolves to the repo-root bus directory `.agent_bus` or a repo-root namespaced bus directory matching `.agent_bus-<id>/`.
2. Add the minimal ignore-rule mechanism needed for repo-root `.agent_bus-*` directories so namespaced bus runtime artifacts stay out of normal git state; keep the existing `.agent_bus/` ignore behavior intact.
3. Update `commit_executor.py` force-add and commit/status protection so `.agent_bus-*` paths are treated as runtime bus state alongside `.agent_bus/` and cannot be added by `force_add_files`, selected from status, or committed as handoff artifacts.
4. Add CLI support for `--bus-dir` to executor/bridge entrypoints that launch or consume pipeline state; default behavior must remain byte-for-byte compatible with the current `.agent_bus` lane when no bus override is supplied.
5. Thread the resolved bus directory through the invocation-owned executor and bridge chain, including bridge paths, routing-record reads/writes, executor state/handoff paths, rendered/raw prompt paths, and the existing pre-commit receipt authority chain.
6. Thread the resolved bus directory through pager event persistence owned by `pipeline_agent_pager.py`, including observability event, delivery, state, and lock paths reached through `executor_common.emit_pipeline_agent_event()`.
7. Thread the resolved bus directory through recovery status/log persistence owned by `recovery_gate.py`, including the recovery status and recovery log paths reached through `executor_dispatch.py`.
8. Preserve `recovery_gate.py` learned-pattern persistence as a canonical shared default-bus exception: `.agent_bus/recovery/learned_patterns.json` and `.agent_bus/recovery/learned_patterns.inbox` remain shared across default and namespaced invocations, are not silently re-homed into `.agent_bus-*`, and are the only allowed default-bus recovery state touched by a namespaced recovery path.
9. Preserve current receipt authority semantics: `meta_bridge_client.run_meta_bridge_package()` must continue to consume the exact path returned by `meta_bridge_supervisor.write_pre_commit_receipt()`, while the receipt directory follows the active invocation bus instead of hardcoded default-bus state.
10. Keep path handling fail-closed: reject absolute paths, nested paths, `..` traversal, symlink escapes, and every resolved bus directory other than `.agent_bus` or `.agent_bus-<id>/`; arbitrary in-repo runtime directories are out of scope even when they do not collide with `.git`, `.scratch`, runtime source directories, or tracked report/doc paths.
11. Update observability consumers only enough to read the active bus path when explicitly configured; do not implement per-worktree tmux session naming or dashboard ports in this slice.
12. Add or update tests proving:
   - default `.agent_bus` remains the active bus without overrides
   - an explicit namespaced bus (for example `.agent_bus-test`) is used for bridge DB, locks, raw/rendered artifacts, routing, handoff, pager events/delivery/state/lock files, recovery status/log files, and receipt paths within the bounded path
   - `.agent_bus-*` paths are rejected by commit-executor force-add validation, commit/status selection protection, and any handoff path that would otherwise permit runtime bus artifacts to become tracked
   - recovery learned-pattern reads/writes remain explicitly tied to `.agent_bus/recovery/learned_patterns.json` and `.agent_bus/recovery/learned_patterns.inbox`, and namespaced recovery status/log tests do not create or consume `.agent_bus-<id>/recovery/learned_patterns*`
   - invalid bus paths, including arbitrary in-repo paths outside `.agent_bus` / `.agent_bus-<id>/`, fail before any runtime files are created
   - stale default-bus invocation-owned state is not read when a namespaced bus is explicitly supplied; the learned-pattern store is the only documented default-bus exception

## Constraints

- Do not implement agent teams, teammate-created worktrees, per-worktree dashboard ports, or tmux session-name allocation in this wave.
- Do not implement Recovery gate Tier 2 auto-retry in this wave; this packet covers bus isolation only.
- Do not change runtime, seed, substrate, host-semantics, or JS parity behavior.
- Do not make `.agent_bus-*` tracked content; namespaced bus directories remain runtime artifacts, and this wave must add both scoped ignore-rule coverage and commit-executor deny/status protection to keep them out of git state even when force-add paths are used.
- Do not treat ignore validation as sufficient protection for namespaced runtime state; commit executor must fail closed before `git add -f` can stage `.agent_bus-*` content.
- Do not silently mix default-bus and namespaced-bus state inside one executor chain. The sole allowed exception is the explicitly named recovery learned-pattern store at `.agent_bus/recovery/learned_patterns.json` plus `.agent_bus/recovery/learned_patterns.inbox`, which remains a canonical shared learning surface rather than invocation-owned runtime state.
- Do not bus-scope or duplicate the learned-pattern store in `.agent_bus-*` during this wave.
- Do not replace the current live receipt chain with directory sorting, heuristic discovery, or legacy aliases; bus threading must keep receipt authority invocation-bound.
- Do not manually bypass dispatcher, recovery, pre-commit, or commit executor authority if the automated path can continue.

## Stop Conditions

- Stop and split if bus namespacing requires a broad dashboard/tmux redesign rather than a narrow resolver + plumbing path.
- Stop and split if any runtime/substrate files under `mu/host/`, `rcx_pi/`, seeds, or core VM semantics need changes.
- Stop and report if the current dispatcher cannot run this packet through Phase A or Phase B without manual commit authority.
- Stop and file a follow-on if per-worktree ports/session names become necessary to test the bus resolver.
- Stop and split if commit-executor `.agent_bus-*` protection requires a broad commit authority redesign rather than extending the existing force-add/status runtime-artifact protections.
- Stop and split if recovery learned-pattern handling must become invocation-scoped; this packet treats learned patterns as an explicit shared default-bus exception.

## Acceptance Criteria

- A locked Phase A plan identifies the minimal bus-dir plumbing path, the ignore-rule path, the commit-executor deny/status protection path, the exact files/directories in scope, and tests needed for default and namespaced buses.
- Phase B implementation leaves no unqualified `.agent_bus` reads/writes in the executor, bridge, pager, recovery status/log, and receipt paths that should follow the invocation bus; remaining `.agent_bus/recovery/learned_patterns*` access is documented and tested as the explicit shared learning exception.
- Existing default-bus behavior remains compatible: current single-pipeline commands keep using `.agent_bus`.
- Namespaced-bus behavior is mechanically testable without launching multiple real model agents.
- Ignore validation proves both `git check-ignore -v .agent_bus-test/foo` and `git check-ignore -v .agent_bus/foo` match the intended ignore rules, so default and namespaced runtime bus artifacts stay out of git state.
- Commit-executor validation proves `.agent_bus-test/foo` and nested files under `.agent_bus-<id>/` are denied by force-add handoff validation and by commit/status artifact protection, so namespaced bus runtime state cannot become tracked through force-add commit paths.
- Recovery validation proves recovery status/log files follow the active invocation bus, while `check_learned_patterns()` and learned-pattern sync continue to use the shared `.agent_bus/recovery/learned_patterns.json` and `.agent_bus/recovery/learned_patterns.inbox` surfaces rather than namespaced bus state.
- Validation includes targeted pytest for executor/bridge/pager/recovery/receipt/commit-executor surfaces touched by the bus resolver, targeted ignore-rule checks for `.agent_bus/` and `.agent_bus-*`, plus the standard startup/doc/L4 checks required for control-surface changes.

## Grounding / Authorization

- `TASKS.md:232-237` marks `[PARALLEL-PIPELINE]` as queued/not implemented by code and stale historical prose as non-authoritative unless this active section marks the item open.
- `TASKS.md:350-356` authorizes `[PARALLEL-PIPELINE]` and lists agent bus namespacing, per-worktree dashboard ports/tmux session names, recovery Tier 2 auto-retry, and agent teams as the work items.
- `TASKS.md:354` records the code-truth search showing `--bus-dir`, agent bus namespacing, `.agent_bus-*`, dashboard ports, and tmux session-name work remains unimplemented by code.
- `git check-ignore -v .agent_bus-test/foo` currently returns no match / exit 1, while `git check-ignore -v .agent_bus/foo` matches `.gitignore:120:.agent_bus/`; `.gitignore:116-122` shows only the default `.agent_bus/` runtime directory is ignored today, so namespaced bus behavior is incomplete unless the implementation includes scoped ignore-rule work.
- `mu/tools/executors/commit_executor.py:99` includes `.agent_bus/` in `FORCE_ADD_DENYLIST` but does not include `.agent_bus-*`; `mu/tools/executors/commit_executor.py:2151-2155` only denies a path part exactly equal to `.agent_bus` or a string starting with `.agent_bus/`; `mu/tools/executors/commit_executor.py:4365-4367` relies on that deny match before accepting handoff `force_add_files`, so ignore-rule coverage alone does not protect namespaced bus runtime state from force-add commit paths.
- `mu/tools/agents/bridge_supervisor.py:30-38` hardcodes `.agent_bus` as the bridge bus and state-ignore prefix; `mu/tools/agents/bridge_supervisor.py:367-378` derives all bridge paths from `repo_root / BUS_DIR_NAME`.
- `mu/tools/agents/bridge_supervisor.py:191-195` documents the live receipt authority chain through `meta_bridge_supervisor.write_pre_commit_receipt()` to `meta_bridge_client.run_meta_bridge_package()` and downstream executor handoff; this plan must thread bus authority through that live path, not replace it.
- `mu/tools/agents/meta_bridge_client.py:84-91` defines `run_meta_bridge_package()` without a bus-dir parameter, and `mu/tools/agents/meta_bridge_client.py:152-176` calls `write_pre_commit_receipt(response, package_path)` and returns the exact repo-relative receipt path.
- `mu/tools/agents/meta_bridge_supervisor.py:1676-1731` writes pre-commit receipts under `repo_root / META_BUS_DIR_NAME`, so receipt persistence must be made bus-dir-aware while preserving the exact returned path.
- `mu/tools/executors/executor_common.py:22-23` hardcodes routing and bridge config under `.agent_bus`; `mu/tools/executors/executor_common.py:776-806` writes canonical routing to `repo_root/.agent_bus/meta/post_merge_routing.json`.
- `mu/tools/executors/executor_common.py:430-445` delegates pager emission to `pipeline_agent_pager.emit_transition_event()`, so pager persistence is not fully covered unless `pipeline_agent_pager.py` is in scope.
- `mu/tools/observability/pipeline_agent_pager.py:41-45` hardcodes observability event, delivery, state, and lock paths under `.agent_bus/observability`; `mu/tools/observability/pipeline_agent_pager.py:1631-1688` persists transition events through that owner path.
- `mu/tools/executors/executor_dispatch.py:64-75` imports `recovery_gate`, and `mu/tools/executors/executor_dispatch.py:2424-2426` calls recovery status cleanup through it.
- `mu/tools/executors/recovery_gate.py:4601-4603` hardcodes recovery status/log paths under `.agent_bus/recovery`; `mu/tools/executors/recovery_gate.py:6119-6149` loads/saves recovery status and `mu/tools/executors/recovery_gate.py:6581-6600` loads/saves recovery logs through those paths.
- `mu/tools/executors/recovery_gate.py:4611` and `:4621` hardcode the learned-pattern store and inbox under `.agent_bus/recovery`; `mu/tools/executors/recovery_gate.py:5078-5085`, `:5156-5157`, `:5217-5219`, and `:5337-5338` read, write, and lock those shared learned-pattern paths; `mu/tools/executors/recovery_gate.py:5794-5805` defines `check_learned_patterns()`, and `mu/tools/executors/recovery_gate.py:6653-6654` calls it before static recovery classification. This makes learned patterns a separate recovery surface from status/log persistence and requires an explicit shared default-bus exception in the bus namespacing design.
- `mu/tools/observability/pipeline_monitor.sh:30-35` hardcodes tmux session identity and live-log keying; `mu/tools/observability/pipeline_monitor.sh:385-405` hardcodes default bus locks.
- `mu/tools/observability/pipeline_dashboard.py:59-60`, `:228-234`, `:1135-1137`, and `:1213-1224` read recovery, routing, bridge DB, and executor state from `.agent_bus`.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `parallel-pipeline-bus-namespacing-2026-04-29`
- Active packet: `reports/control_plane/parallel_pipeline_bus_namespacing_2026-04-29.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `86af0b269581c61accb10f8a151a335bf021681e234146fbfb7457a480757e24`
- Indicator artifact: `reports/l4_wave_indicators/parallel-pipeline-bus-namespacing-2026-04-29.json`
- Pre-commit receipt handle: `.agent_bus/meta/pre_commit_receipts/receipt_2026-04-30T01-27-23p00-00_21ff5c9e.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bus_namespacing.py mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_meta_bridge_client.py mu/tests/tools/test_meta_bridge_supervisor.py mu/tests/tools/test_phase_a_executor.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/parallel_pipeline_bus_namespacing_2026-04-29.md. (2) Final pytest gate covered 8 test file(s) from the wave-owned diff. (3) Commit handoff carries explicit receipt authority at .agent_bus/meta/pre_commit_receipts/receipt_2026-04-30T01-27-23p00-00_21ff5c9e.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/parallel-pipeline-bus-namespacing-2026-04-29.json`
  - `pre_commit_receipt`: `.agent_bus/meta/pre_commit_receipts/receipt_2026-04-30T01-27-23p00-00_21ff5c9e.json`
- Current staged files:
  - `.gitignore`
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_agent_bus_namespacing.py`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_meta_bridge_client.py`
  - `mu/tests/tools/test_meta_bridge_supervisor.py`
  - `mu/tests/tools/test_phase_a_executor.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/agents/bridge_adapters.py`
  - `mu/tools/agents/bridge_supervisor.py`
  - `mu/tools/agents/meta_bridge_client.py`
  - `mu/tools/agents/meta_bridge_supervisor.py`
  - `mu/tools/agents/verify_pre_commit_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/dialectic_executor.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/phase_a_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/phase_b_implementer.py`
  - `mu/tools/executors/recovery_gate.py`
  - `mu/tools/observability/_pane_findings.sh`
  - `mu/tools/observability/_pane_processes.sh`
  - `mu/tools/observability/_pane_timeline.sh`
  - `mu/tools/observability/_resolve_live_root.sh`
  - `mu/tools/observability/pipeline_agent_pager.py`
  - `mu/tools/observability/pipeline_dashboard.py`
  - `mu/tools/observability/pipeline_monitor.sh`
  - `mu/tools/observability/pipeline_status.sh`
  - `reports/control_plane/parallel_pipeline_bus_namespacing_2026-04-29.md`
  - `reports/deferred/non_blocking/parallel-pipeline-bus-namespacing-2026-04-29_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/parallel-pipeline-bus-namespacing-2026-04-29.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
