# Plan Deferred Consolidation E5 E6 2026 04 02

Date: 2026-04-06
Status: COMPLETED (merged PR #843; C1 sanitizer closeout in deferred-consolidation-e5-e6-closeout-2026-04-30)
Task: [DEFERRED-CONSOLIDATION]
Wave ID: plan-deferred-consolidation-e5-e6-2026-04-02-2026-04-06
Phase-A-Lock: LOCKED
Task-ID: [DEFERRED-CONSOLIDATION]
Wave-ID: deferred-consolidation-e5-e6-2026-04-02
Class: L4_ENABLER
Lane: control-surface (deferred cleanup)
Purpose: Create a bounded Phase A plan for the Wave 1B E5/E6 observability/hooks slice under [DEFERRED-CONSOLIDATION]. The slice is limited to the tmux PR/CI pane and adjacent observability behavior needed to fix jq tail selection, sanitize terminal escape sequences in displayed bot comment text, and add defense-in-depth numeric validation before gh API PR comment calls. Do not expand into broader Cluster C or D items unless Phase A proves a direct dependency.
## Scope

Files and directories in scope:

- `reports/control_plane/plan_deferred_consolidation_e5_e6_2026_04_02_2026-04-06.md`: governing Phase A packet for this E5/E6 slice.
- `mu/tools/observability/_pane_prci.sh`: only implementation target named by current TASKS.md code truth for E5/E6 residue; scope is limited to the tmux PR/CI observability path that selects recent bot comments and calls `gh api "repos/{owner}/{repo}/pulls/$PR/comments"`.
- `mu/tests/tools/`: targeted tests for the tmux PR/CI observability behavior, including jq tail selection, terminal escape sanitization in displayed bot comment text, and numeric PR validation before PR comment API calls.

Governing references:

- `TASKS.md` `[DEFERRED-CONSOLIDATION]` entry, including the 2026-04-30 code-truth refresh that keeps D1 open while closing E5/E6 against current source and tests.
- Upstream Wave 1B cleanup plan listed by TASKS.md: `reports/control_plane/wave1b_pipeline_cleanup_2026-03-31.md`.

## Work Items

1. E5 jq tail selection: replace the jq `last(3)` misuse in `mu/tools/observability/_pane_prci.sh` with deterministic selection of the last three relevant PR comment records. The fix must handle empty, one-item, two-item, and three-or-more-item inputs without relying on unsupported jq arity.
2. E5 terminal display sanitization: sanitize terminal escape and control sequences from displayed bot comment text before rendering it in the tmux PR/CI pane. Preserve readable comment content while preventing escape sequences from affecting the operator terminal.
3. E6 PR number validation: add a numeric guard before the `gh api "repos/{owner}/{repo}/pulls/$PR/comments"` path in `mu/tools/observability/_pane_prci.sh`. Non-numeric or empty PR values must not reach `gh api`; the pane should degrade with a bounded visible status instead of building an unsafe request path.
4. Test coverage: add or update targeted `mu/tests/tools/` coverage for the three behaviors above. Tests must prove that jq tail selection no longer depends on `last(3)`, displayed comment text is escape-sanitized, and non-numeric PR values do not invoke the PR comments API path.

## Constraints

- Do not include D1 in this packet. TASKS.md keeps D1 open separately for `mu/tools/executors/dialectic_executor.py` max-rounds documentation, but this E5/E6 packet does not authorize that work.
- Do not reopen items TASKS.md marks landed by current code truth: C1/C2, C3, C6, or D2.
- Do not expand into broader Cluster C or D cleanup, bridge reviewer policy, executor routing, recovery, commit handoff, pager, or runtime/substrate semantics unless a stop condition proves a direct dependency.
- Do not edit outside `mu/tools/observability/_pane_prci.sh` and targeted `mu/tests/tools/` tests during the implementation phase without returning to Phase A for scope revision.
- Do not treat TASKS.md as proof that every historical Wave 1B item remains unlanded. Future implementation must prefer current code truth over stale packet wording and remove already-landed items from pending work instead of duplicating them.
- This Phase A rewrite itself changes only this packet.

## Stop Conditions

- Stop if code inspection during implementation proves any E5/E6 work item is already implemented in current code; update the pending list and acceptance criteria instead of re-listing that item as unresolved.
- Stop if the jq tail, terminal sanitization, or PR validation fix requires edits outside `mu/tools/observability/_pane_prci.sh` plus targeted tests under `mu/tests/tools/`.
- Stop if terminal escape sanitization requires a global pane-rendering policy or shared sanitizer used by other observability panes; split that into a separate plan instead of widening this packet.
- Stop if the PR identifier source cannot be validated locally in the pane script without changing executor, dispatcher, bridge, or routing-record contracts.
- Stop if the necessary test harness change is broader than targeted observability tests or needs a separate growth-cap/governance exception.

## Acceptance Criteria

- This packet contains explicit Scope, Work Items, Constraints, Stop Conditions, Acceptance Criteria, and Grounding / Authorization sections.
- Scope lists the concrete implementation file, governing packet, upstream plan reference, and test directory instead of describing only a general feature area.
- `mu/tools/observability/_pane_prci.sh` no longer uses jq `last(3)` for recent comment selection; targeted tests cover empty, short, and three-or-more comment inputs.
- Displayed bot comment text is sanitized before pane rendering; targeted tests include at least one terminal escape/control-sequence payload.
- PR comment API calls are guarded by numeric PR validation; targeted tests prove non-numeric and empty PR values do not invoke `gh api "repos/{owner}/{repo}/pulls/$PR/comments"`.
- The implementation remains bounded to E5/E6 tmux PR/CI observability and does not claim closure for D1 or any broader [DEFERRED-CONSOLIDATION] residue.
- Reviewer required-section search finds every required section plus a control-surface authorization token or line in this packet.

## Grounding / Authorization

TASKS.md authorization: `[DEFERRED-CONSOLIDATION]` remains OPEN under NEXT for D1 only after the 2026-04-30 code-truth reconciliation. This E5/E6 packet is closed against current source and tests: `mu/tools/observability/_pane_prci.sh` no longer uses jq `last(3)`, validates numeric PR identifiers before the review-comments API path, and sanitizes displayed bot comment text before pane rendering.

Governing packet refs:

- This packet: `reports/control_plane/plan_deferred_consolidation_e5_e6_2026_04_02_2026-04-06.md`.
- Upstream plan listed in TASKS.md: `reports/control_plane/wave1b_pipeline_cleanup_2026-03-31.md`.

FOUNDER_OVERRIDE:deferred-consolidation-e5-e6-2026-04-02
Authorization: standing pipeline-bug-fix authorization for the [DEFERRED-CONSOLIDATION] Wave 1B E5/E6 control-surface L4_ENABLER slice. This authorization is bounded to tmux PR/CI observability jq tail selection, displayed-comment terminal escape sanitization, and numeric PR validation before gh API PR comment calls; it does not authorize D1, broader Cluster C/D cleanup, or runtime/substrate semantic changes.

## Authorized Commit-Path Structural Follow-On

After Phase B completed the E5/E6 implementation, the commit path exposed two direct dependencies covered by the stop-condition escape in this packet's Constraints section: `git add` failed on the symlink alias `tests/docs/test_growth_caps.py`, and the pre-commit supervisor saw stale staged tracker truth after commit packet refresh. The bounded follow-on scope is limited to the commit-path mechanics needed to make the same failure class recover automatically:

- `mu/tools/executors/commit_executor.py`: canonicalize symlink stage aliases in the handoff builder and Step 4, then re-stage the refreshed handoff scope after packet truth refresh before supervisor packaging.
- `mu/tools/executors/recovery_gate.py`: classify `pathspec ... is beyond a symbolic link` as a Tier 1 deterministic recovery case and rewrite the active handoff/current-wave tracker line to canonical repo paths.
- `mu/tests/tools/test_commit_executor_receipt.py` and `mu/tests/tools/test_recovery_gate.py`: cover the builder canonicalization and Tier 1 recovery behavior.
- `mu/tools/executors/executor_dispatch.py`: bind recovery-seeded `RCX_RECOVERY_PHASE_B_PLAN_PATH` hints to a real recovering wave id, ignore unmarked or stale plan hints, and clear the matching wave marker during dispatcher cleanup.
- `mu/tests/tools/test_executor_dispatch.py`: cover stale, unmarked, and wave-unknown recovery-env isolation so a leftover Phase B recovery plan cannot force an unrelated first-run Phase B command into `--plan` mode.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `plan-deferred-consolidation-e5-e6-2026-04-02-2026-04-06`
- Active packet: `reports/control_plane/plan_deferred_consolidation_e5_e6_2026_04_02_2026-04-06.md`
- Commit status: merged PR #843 (`92049ef014b130b9596aafb1e1b94b4c22fee632`) plus `deferred-consolidation-e5-e6-closeout-2026-04-30` C1 sanitizer follow-up.
- Tracker note sha256: refreshed by `deferred-consolidation-e5-e6-closeout-2026-04-30`
- Indicator artifact: `reports/l4_wave_indicators/plan-deferred-consolidation-e5-e6-2026-04-02-2026-04-06.json`; closeout indicator: `reports/l4_wave_indicators/deferred-consolidation-e5-e6-closeout-2026-04-30.json`
- Pre-commit receipt handle: `.agent_bus/meta/pre_commit_receipts/receipt_2026-04-30T16-34-15p00-00_885a864b.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_pane_prci_observability.py mu/tests/docs/test_growth_caps.py::TestGrowthCaps::test_test_file_count_within_cap mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_recovery_gate.py::TestClassifyFailure mu/tests/tools/test_recovery_gate.py::TestStagePathSymlinkAliasRecovery mu/tests/tools/test_recovery_gate.py::TestTierMapping mu/tests/tools/test_executor_dispatch.py::TestModularSurfaceEntrypoints::test_phase_b_surface_rebuilds_command_after_recovery_updates_routing mu/tests/tools/test_executor_dispatch.py::TestModularSurfaceEntrypoints::test_phase_b_surface_plan_required_recovery_affects_no_routing_retry mu/tests/tools/test_executor_dispatch.py::TestDispatcherPlanlessPhaseB::test_phase_b_recovery_plan_env_retries_with_plan mu/tests/tools/test_executor_dispatch.py::TestDispatcherPlanlessPhaseB::test_phase_b_recovery_plan_env_ignored_without_wave_marker mu/tests/tools/test_executor_dispatch.py::TestDispatcherPlanlessPhaseB::test_phase_b_recovery_plan_env_ignored_without_record_wave mu/tests/tools/test_recovery_gate.py::TestNeedsPhaseB_Tier3::test_attempt_recovery_retries_phase_b_with_plan_after_planless_stop mu/tests/tools/test_recovery_gate.py::TestNeedsPhaseB_Tier3::test_plan_required_recovery_derives_wave_binding_from_plan_path mu/tests/tools/test_recovery_gate.py::TestNeedsPhaseB_Tier3::test_plan_required_fallback_reads_namespaced_routing_record`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/plan_deferred_consolidation_e5_e6_2026_04_02_2026-04-06.md and merged as PR #843. (2) Final PR #843 pytest gate covered the E5/E6 pane test, the growth-cap guard, the commit-executor receipt module, recovery classifier/fixer/tier slices, and dispatcher recovery-env isolation. (3) The closeout follow-up extends `sanitize_pane_text()` to strip C1 controls (`U+0080..U+009F`) and adds targeted regression coverage for the deferred non-blocking finding. (4) Commit path canonicalizes symlink stage aliases in the builder and Step 4, re-stages refreshed packet scope before supervisor packaging, and has Tier 1 recovery for pathspec aliases beyond repo symlinks. (5) Dispatcher now requires matching real wave ids for recovery-seeded Phase B plan env hints, and recovery binds plan-required retries either to the active wave or the existing control-plane plan path, so stale recovery env cannot force unrelated planless Phase B runs into --plan mode.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/plan-deferred-consolidation-e5-e6-2026-04-02-2026-04-06.json`
  - `closeout_indicator`: `reports/l4_wave_indicators/deferred-consolidation-e5-e6-closeout-2026-04-30.json`
  - `pre_commit_receipt`: `.agent_bus/meta/pre_commit_receipts/receipt_2026-04-30T16-34-15p00-00_885a864b.json`
- Closed implementation and closeout files:
  - `TASKS.md`
  - `mu/tests/tools/test_pane_prci_observability.py`
  - `mu/tools/observability/_pane_prci.sh`
  - `reports/control_plane/plan_deferred_consolidation_e5_e6_2026_04_02_2026-04-06.md`
  - `reports/deferred/archive/plan-deferred-consolidation-e5-e6-2026-04-02-2026-04-06_bridge_nonblockers_CLOSED_by_deferred-consolidation-e5-e6-closeout-2026-04-30.md`
  - `reports/l4_wave_indicators/plan-deferred-consolidation-e5-e6-2026-04-02-2026-04-06.json`
  - `reports/l4_wave_indicators/deferred-consolidation-e5-e6-closeout-2026-04-30.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
