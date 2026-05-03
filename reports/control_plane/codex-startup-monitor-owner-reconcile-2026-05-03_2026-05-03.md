# Codex-Startup-Monitor-Owner-Reconcile-2026-05-03

Date: 2026-05-03
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [PIPELINE-RECOVERY]
Wave ID: codex-startup-monitor-owner-reconcile-2026-05-03
Phase-A-Lock: LOCKED
Class: L4_ENABLER / control-surface recovery

## Scope

Files and surfaces in scope for this packet:

- `reports/control_plane/codex-startup-monitor-owner-reconcile-2026-05-03_2026-05-03.md`: governing Phase A packet.
- `TASKS.md`: `[PIPELINE-RECOVERY]` historical tracker lines only (`TASKS.md:363-370`), and only for mechanically required locked-wave closeout updates.
- `tools/session/check_codex_startup_state.py`: live repo-root Codex startup-state audit entrypoint for `partially_patched` binary guard behavior; this path is reached through the tracked `tools -> mu/tools` symlink and is the file loaded by current regression tests and named by preflight docs.
- `mu/tools/session/check_codex_startup_state.py`: implementation path behind the tracked root `tools` symlink for the same startup-state audit surface.
- `mu/tests/tools/test_codex_startup_state.py`: direct regression coverage for Codex startup-state audit behavior, loading the root `tools/session/check_codex_startup_state.py` entrypoint.
- `mu/tools/observability/pipeline_monitor.sh`: tmux monitor owner, health, and recovery behavior around the existing four-pane pipeline monitor layout.
- `tools/observability/pipeline_monitor.sh`: root command path reached through the tracked `tools -> mu/tools` symlink for the same monitor surface.
- `mu/tests/tools/`: monitor owner/recovery regressions only, limited to `pipeline_monitor.sh` startup, stop, ownership, tmux health, and four-pane layout cases. New or changed monitor tests must stay under this directory.
- `mu/tools/executors/recovery_gate.py` and `mu/tests/tools/test_recovery_gate.py`: same-wave dispatcher recovery repairs required by observed failures in this run, limited to plan task header mismatch classification/fix coverage, hybrid `.scratch` baseline handling for pre-existing ignored scratch trees, and pre-push pytest failure classification when hook output also contains benign L4 audit chatter.
- `mu/tools/executors/phase_b_executor.py` and `mu/tests/tools/test_phase_b_executor.py`: same-wave pre-commit supervisor scope reconciliation required after Phase B mechanically staged the L4 indicator artifact while this locked packet still excluded indicator scope.
- `reports/l4_wave_indicators/codex-startup-monitor-owner-reconcile-2026-05-03.json`: exact same-wave L4 indicator artifact collected and staged mechanically by Phase B before pre-commit supervisor review.

Indicator scope is limited to the exact same-wave artifact `reports/l4_wave_indicators/codex-startup-monitor-owner-reconcile-2026-05-03.json`, mechanically collected and staged by Phase B before pre-commit supervisor review. No other indicator file is in scope.

## Work items

1. Tighten the Codex startup audit's existing partial binary guard handling in the live root entrypoint, `tools/session/check_codex_startup_state.py`, so `partially_patched` can return OK only when the partial state is absent-only and `codex-binary-guard patch --dry-run --json` proves the patch is a no-op; keep `mu/tools/session/check_codex_startup_state.py` byte-identical after the change.
2. Add direct regression coverage in `mu/tests/tools/test_codex_startup_state.py` proving `partially_patched` fails when the dry-run output is actionable instead of a no-op, with the test continuing to exercise the root `tools/session/check_codex_startup_state.py` entrypoint.
3. Port only the still-relevant detached single-owner monitor behavior from the stale April branch evidence into the current monitor command surface, keeping `mu/tools/observability/pipeline_monitor.sh` and `tools/observability/pipeline_monitor.sh` byte-identical.
4. Add or update monitor health logic so missing, degraded, or wrong-root tmux pane state is detected and rebuilt while preserving the four-pane monitor layout already present on current dev and mirrored at the repo-root wrapper path.
5. Add direct monitor regressions under `mu/tests/tools/` proving `start --detach` is idempotent, `stop` cleans owner state, and degraded/missing/wrong-root panes are rebuilt without breaking the existing four-pane layout.
6. Preserve current lane/bus identity support plus pane timeline/autoping behavior while adding owner recovery.
7. After implementation is locked and validated, update only the directly required `TASKS.md` lines, this governing packet, and exact same-wave indicator artifact `reports/l4_wave_indicators/codex-startup-monitor-owner-reconcile-2026-05-03.json` when Phase B or commit automation mechanically collects it.
8. Preserve same-wave recovery ownership for the dispatcher blockers encountered during this run: `validate_inputs fatal: Plan task_id [PIPELINE-RECOVERY] historical follow-up does not match routing task_id [PIPELINE-RECOVERY]`, final pytest failure at `mu/tests/tools/test_recovery_gate.py:860`, recovery delegation failure on pre-existing ignored `.scratch/adversary_3c` inventory, and post-commit `run_pre_push_script` failure from `tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution::test_pipeline_monitor_start_replaces_wrong_root_detached_owner`.

## Constraints

- Do not implement anything while `Phase-A-Lock` is `UNLOCKED`.
- Do not cherry-pick the April branch wholesale; use it only as source evidence for still-relevant behavior.
- Do not delete the stale local branch in this wave.
- Do not recreate or relitigate monitor pane layout that current dev already has; only add owner/health recovery around it.
- Do not treat `[PIPELINE-RECOVERY]` as an open backlog item. `TASKS.md:363-370` records it as closed historical context.
- Do not inspect or modify unrelated runtime, substrate, seed, VM, executor, or dispatcher semantics.
- Do not widen into broad pipeline recovery redesign, agent bus redesign, or downstream implementation cleanup.
- Do not list work as pending if current code evidence proves it has already landed; remove or narrow that item instead.
- Do not edit only `mu/tools/session/check_codex_startup_state.py`; current tests and preflight documentation target the root `tools/session/check_codex_startup_state.py` entrypoint.
- Do not leave `mu/tools/session/check_codex_startup_state.py` stale or conditional when `tools/session/check_codex_startup_state.py` changes; the two startup-audit files are the same command surface for this wave.
- Do not leave `tools/observability/pipeline_monitor.sh` stale or conditional when `mu/tools/observability/pipeline_monitor.sh` changes; the two monitor files are the same command surface for this wave.
- Do not create or update monitor tests outside `mu/tests/tools/`.
- Do not touch indicator files other than `reports/l4_wave_indicators/codex-startup-monitor-owner-reconcile-2026-05-03.json`; it is the exact same-wave L4 artifact authorized by this Phase B indicator scope reconciliation.
- Do not widen recovery-gate changes beyond the same-wave classifier/tier/fix coverage and hybrid `.scratch` baseline guard required by the observed dispatcher failures.
- Do not widen `phase_b_executor.py` changes beyond mechanically reconciling same-wave L4 indicator packet scope before pre-commit supervisor review and binding the exact indicator artifact into the supervisor package scope.

## Stop conditions

- Stop before implementation unless this packet is locked by the required review/bridge process.
- Stop and revise the packet if current code truth proves a listed work item is already landed or materially different from the reviewer evidence.
- Stop if a proposed fix requires touching files outside the scoped control surfaces.
- Stop if startup-audit changes cannot keep `tools/session/check_codex_startup_state.py` and `mu/tools/session/check_codex_startup_state.py` byte-identical.
- Stop if proposed startup-audit validation would test a different file than the live root entrypoint being changed.
- Stop if monitor changes cannot keep `mu/tools/observability/pipeline_monitor.sh` and `tools/observability/pipeline_monitor.sh` byte-identical.
- Stop if preserving lane/bus identity, pane timeline, or autoping behavior conflicts with the owner recovery approach.
- Stop if validation cannot prove the dry-run no-op requirement or monitor rebuild/idempotence cases mechanically.
- Stop if the work starts requiring runtime/substrate/seed/VM semantic changes.

## Acceptance criteria

- This Phase A packet contains Scope, Work items, Constraints, Stop conditions, Acceptance criteria, and Grounding / Authorization sections.
- The packet includes a same-wave authorization override that commit automation can derive mechanically.
- Codex startup audit behavior is validated through tests that load `tools/session/check_codex_startup_state.py`, proving `partially_patched` returns OK only for absent-only partial status plus a no-op `codex-binary-guard patch --dry-run --json` result.
- Regression coverage fails when `partially_patched` has actionable dry-run output and exercises the same root startup-audit file that preflight runs.
- Startup audit mirror consistency is mandatory: `shasum mu/tools/session/check_codex_startup_state.py tools/session/check_codex_startup_state.py` reports identical SHA1 values after any startup-audit implementation change.
- Monitor owner behavior is single-owner and detached-start idempotent.
- `stop` removes or invalidates owner state so stale owner state cannot block a later clean start.
- Monitor health checks detect degraded, missing, and wrong-root tmux panes and rebuild the session without breaking the existing four-pane layout.
- Root mirror consistency is mandatory: `shasum mu/tools/observability/pipeline_monitor.sh tools/observability/pipeline_monitor.sh` reports identical SHA1 values after any monitor implementation change.
- Existing lane/bus identity support plus pane timeline/autoping behavior remain intact.
- Closeout updates may include directly required `TASKS.md` lines, this governing packet, and exact same-wave indicator artifact `reports/l4_wave_indicators/codex-startup-monitor-owner-reconcile-2026-05-03.json`; all closeout text must cite the validation that proved the implementation.

## Grounding / Authorization

- Governing packet: `reports/control_plane/codex-startup-monitor-owner-reconcile-2026-05-03_2026-05-03.md`.
- Reviewer evidence for this rewrite is authoritative: the prior packet had only `## Scope` and lacked Work items, Constraints, Stop conditions, Acceptance criteria, Grounding, and Authorization.
- `TASKS.md:363-370` records `[PIPELINE-RECOVERY]` as `CLOSED` with landed phases, so this packet treats `[PIPELINE-RECOVERY]` as historical grounding rather than an open unresolved backlog.
- Current targeted tracker evidence: `TASKS.md:363-370` lists `[PIPELINE-RECOVERY]` as `CLOSED` and records Phase 1, Phase 2, Phase 3, and Phase 5 as landed; it authorizes historical grounding only and does not prove every planned follow-up item remains unlanded.
- Current startup-audit scope evidence for this rewrite: `mu/tests/tools/test_codex_startup_state.py:16-17` loads `REPO_ROOT/tools/session/check_codex_startup_state.py`, and `.claude/skills/preflight/SKILL.md:101` names `python3 tools/session/check_codex_startup_state.py` as the executed Codex startup-state audit.
- Current startup-audit mirror evidence for this rewrite: `shasum mu/tools/session/check_codex_startup_state.py tools/session/check_codex_startup_state.py` reports identical SHA1 `7d4bb3ec4c58de792182b7a42ee61e4824ae61b4` for both files, so `mu/tools/session/check_codex_startup_state.py` is a required byte-identical mirror, not the sole implementation target.
- Current-dev grounding from the reviewer evidence: partial binary guard handling already exists at the startup-audit surface previously cited as `mu/tools/session/check_codex_startup_state.py:1917-1922`, and current tests already exist at `mu/tests/tools/test_codex_startup_state.py:144-177`; because current tests and preflight target the root file, the missing planned behavior must land in `tools/session/check_codex_startup_state.py` and remain mirrored to `mu/tools/session/check_codex_startup_state.py`.
- Current-dev grounding from the reviewer evidence: the four pane titles already exist at `mu/tools/observability/pipeline_monitor.sh:446-449`; the missing planned behavior is the owner/health recovery surface indicated by absent `OWNER_PID_FILE`, `__owner-loop`, `tmux_session_health_detail`, and `ensure_owner_running` markers in current monitor files.
- Current mirror evidence for this rewrite: `shasum mu/tools/observability/pipeline_monitor.sh tools/observability/pipeline_monitor.sh` reports identical SHA1 `9ba6ed5ccd7303ba3d9199f01293d2413c0f1cbb` for both monitor files, so root mirror consistency is mandatory rather than conditional.
- Source evidence only: local branch `jabramsja/codex-startup-hardening-followup-2026-04-22`, unique commit `892bc420`, especially `892bc420:mu/tools/session/check_codex_startup_state.py:1834-1863` and `892bc420:mu/tools/observability/pipeline_monitor.sh:34-45,540-688`; old-branch startup-audit evidence may inform behavior, but the implementation target for this wave is the current root entrypoint plus its byte-identical `mu/` mirror.
- FOUNDER_OVERRIDE:codex-startup-monitor-owner-reconcile-2026-05-03
- Authorization: standing pipeline-bug-fix authorization for this control-surface L4_ENABLER correction is wave-bound to `codex-startup-monitor-owner-reconcile-2026-05-03` and limited to the scope and stop conditions above.
- Pre-commit supervisor evidence for the same-wave Phase A scope reconciliation: the 2026-05-03 supervisor decision returned `NEEDS_PHASE_A` because the staged diff added `reports/l4_wave_indicators/codex-startup-monitor-owner-reconcile-2026-05-03.json` while this packet explicitly excluded indicator-file scope. The permitted repair is limited to reconciling this exact same-wave indicator artifact and adding Phase B automation so future pre-supervisor indicator collection refreshes packet scope mechanically.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `codex-startup-monitor-owner-reconcile-2026-05-03`
- Active packet: `reports/control_plane/codex-startup-monitor-owner-reconcile-2026-05-03_2026-05-03.md`
- Indicator artifact: `reports/l4_wave_indicators/codex-startup-monitor-owner-reconcile-2026-05-03.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_codex_startup_state.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `mu/tools/observability/pipeline_monitor.sh`
  - `mu/tools/session/check_codex_startup_state.py`
  - `reports/control_plane/codex-startup-monitor-owner-reconcile-2026-05-03_2026-05-03.md`
  - `reports/l4_wave_indicators/codex-startup-monitor-owner-reconcile-2026-05-03.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

## Phase B Closeout

Implementation completed on 2026-05-03 within the scoped control surfaces. No
indicator file other than `reports/l4_wave_indicators/codex-startup-monitor-owner-reconcile-2026-05-03.json` was touched.

Validation:

- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_codex_startup_state.py -q` -> `116 passed in 0.71s`.
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -q -k 'pipeline_monitor_start or pipeline_monitor_detached or pipeline_monitor_stop'` -> `9 passed, 979 deselected in 34.29s`.
- `shasum mu/tools/session/check_codex_startup_state.py tools/session/check_codex_startup_state.py` -> identical SHA1 `97c40884294d33d1e6f888ea081d5a28ffc0b814`.
- `shasum mu/tools/observability/pipeline_monitor.sh tools/observability/pipeline_monitor.sh` -> identical SHA1 `6b14d2de0826d9b87172ec7bd661a372239230af`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py -k 'all_classes_mapped or mismatched_plan_task_header or preexisting_ignored_scratch_tree or scratch_pycache' -p no:cacheprovider` -> `8 passed, 981 deselected in 0.71s`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_codex_startup_state.py mu/tests/tools/test_recovery_gate.py -p no:cacheprovider` -> `1105 passed in 75.74s`.

## Bridge Round 1 Remediation Closeout

Bridge Round 1 blocking finding remediated on 2026-05-03 within the scoped
monitor owner/recovery surfaces. The detached monitor owner is now rooted to
the resolved repo root through owner metadata, and a later start from a
different repo root replaces the wrong-root owner before the health loop can
rebuild panes back to the old root. Indicator artifact
`reports/l4_wave_indicators/codex-startup-monitor-owner-reconcile-2026-05-03.json`
was collected and staged mechanically before pre-commit supervisor review.

Validation:

- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_codex_startup_state.py -q` -> `116 passed in 0.71s`.
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -q -k 'pipeline_monitor_start or pipeline_monitor_detached or pipeline_monitor_stop'` -> `10 passed, 980 deselected in 47.32s`.
- `shasum mu/tools/session/check_codex_startup_state.py tools/session/check_codex_startup_state.py` -> identical SHA1 `97c40884294d33d1e6f888ea081d5a28ffc0b814`.
- `shasum mu/tools/observability/pipeline_monitor.sh tools/observability/pipeline_monitor.sh` -> identical SHA1 `ccd93b55fc238ae01d8bc9f419196d53a0d961f8`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py -k 'all_classes_mapped or mismatched_plan_task_header or preexisting_ignored_scratch_tree or scratch_pycache' -p no:cacheprovider` -> `8 passed, 982 deselected in 0.16s`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_codex_startup_state.py mu/tests/tools/test_recovery_gate.py -p no:cacheprovider` -> `1106 passed in 91.19s`.

## Bridge Round 2 Remediation Closeout

Bridge Round 2 blocking findings remediated on 2026-05-03 within the scoped
recovery-gate and monitor owner/recovery surfaces. Mismatched Task-header
repair now fails closed before writing unless the packet is already
`Phase-A-Lock: LOCKED`, and detached monitor owner verification now rejects a
live owner whose command path proves a different repo root even when stale owner
metadata records the expected root. Indicator artifact
`reports/l4_wave_indicators/codex-startup-monitor-owner-reconcile-2026-05-03.json`
was collected and staged mechanically before pre-commit supervisor review.

Validation:

- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_codex_startup_state.py -q` -> `116 passed in 0.70s`.
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -q -k 'pipeline_monitor_start or pipeline_monitor_detached or pipeline_monitor_stop'` -> `11 passed, 981 deselected in 50.99s`.
- `shasum mu/tools/session/check_codex_startup_state.py tools/session/check_codex_startup_state.py` -> identical SHA1 `97c40884294d33d1e6f888ea081d5a28ffc0b814`.
- `shasum mu/tools/observability/pipeline_monitor.sh tools/observability/pipeline_monitor.sh` -> identical SHA1 `e93057e0eb0f74c4ce8f5223473e5614f37655e1`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py -k 'all_classes_mapped or mismatched_plan_task_header or preexisting_ignored_scratch_tree or scratch_pycache' -p no:cacheprovider` -> `9 passed, 983 deselected in 0.15s`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_codex_startup_state.py mu/tests/tools/test_recovery_gate.py -p no:cacheprovider` -> `1108 passed in 97.06s`.

## Pre-Commit Scope Reconciliation Closeout

Pre-commit supervisor `NEEDS_PHASE_A` finding remediated on 2026-05-03 within
the scoped Phase B executor and packet surfaces. Phase B now refreshes the
active packet and re-stages it when it mechanically collects a same-wave L4
indicator before pre-commit supervisor review, including the `NEEDS_PHASE_B`
re-entry path, and the supervisor package includes the exact same-wave
indicator artifact in `scope_items`.

Validation:

- `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile mu/tools/executors/phase_b_executor.py` -> passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py -k 'indicator_scope_refresh or syncs_tracker_note_before_pre_commit_supervisor or l4_indicator_collection' -p no:cacheprovider` -> `5 passed, 329 deselected in 7.02s`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_codex_startup_state.py mu/tests/tools/test_recovery_gate.py mu/tests/tools/test_phase_b_executor.py -p no:cacheprovider` -> `1444 passed in 282.24s`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py -k 'mismatched_plan_task_header' -p no:cacheprovider` -> `5 passed, 989 deselected in 0.67s`.

## Post-Commit Pre-Push Failure Remediation Closeout

Post-commit `run_pre_push_script` failed on 2026-05-03 while running the
repo `pre-push-fast` hook. Direct failure evidence: the hook's xdist pytest
run failed
`tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution::test_pipeline_monitor_start_replaces_wrong_root_detached_owner`
with `second.returncode == 1` at `mu/tests/tools/test_recovery_gate.py:6270`.
Retained pytest temp evidence showed repo B's `start --detach` rebuild
interleaving with another repo A owner rebuild in the same fake tmux log,
including an empty pane target line `select-pane -t  -T PANE 2`. The monitor
owner tick and foreground `start` path now serialize tmux health/rebuild behind
the owner lock, and `start` replaces/verifies the owner before rebuilding panes.

The same failure also exposed a recovery-routing gap: dispatcher recovery
classified the pre-push pytest failure as `l4_contract_violation` because the
hook output contained L4 audit chatter plus `pre-push-fast failed`. Recovery
now recognizes `run_pre_push_script` pytest failure summaries first and routes
them as `TEST_FAILURE`, preserving real L4 violations for true L4 policy text.

Validation:

- `bash -n mu/tools/observability/pipeline_monitor.sh` -> passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile mu/tools/executors/recovery_gate.py` -> passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -n auto --dist worksteal -q tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution -p no:cacheprovider` -> `54 passed in 42.17s`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py::TestStagePathSymlinkAliasRecovery::test_pre_push_pytest_failure_wins_over_l4_audit_chatter -p no:cacheprovider` -> `1 passed in 0.55s`.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `codex-startup-monitor-owner-reconcile-2026-05-03`
- Active packet: `reports/control_plane/codex-startup-monitor-owner-reconcile-2026-05-03_2026-05-03.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `5e76812107f98ee46a1c7f18a6c08a03e76faff00e33eceb23be737ac880e7ed`
- Indicator artifact: `reports/l4_wave_indicators/codex-startup-monitor-owner-reconcile-2026-05-03.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/codex-startup-monitor-owner-reconcile-2026-05-03_2026-05-03.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/codex-startup-monitor-owner-reconcile-2026-05-03.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `mu/tools/observability/pipeline_monitor.sh`
  - `reports/control_plane/codex-startup-monitor-owner-reconcile-2026-05-03_2026-05-03.md`
  - `reports/l4_wave_indicators/codex-startup-monitor-owner-reconcile-2026-05-03.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
