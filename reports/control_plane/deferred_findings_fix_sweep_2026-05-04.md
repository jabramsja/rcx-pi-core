# Deferred Findings Fix Sweep

Date: 2026-05-04
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: deferred-findings-fix-sweep-2026-05-04
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Target gate: G8
FOUNDER_OVERRIDE:deferred-findings-fix-sweep-2026-05-04

## Purpose

Fix or explicitly route the blocker and non-blocker findings that remain in the
report surfaces before any production-forward runtime work continues.

This packet is the immediate pre-production cleanup gate before the full `/mu`
runtime red-team packet.

## Scope

Required inventory surfaces:

- `reports/deferred/blocking/`
- `reports/deferred/non_blocking/`
- `reports/l4_wave_indicators/`
- `reports/control_plane/`
- `TASKS.md`

Allowed write surfaces:

- the report surfaces above
- existing archive/resolved destinations for stale or closed findings:
  `reports/deferred/archive/`, `reports/deferred/resolved/`,
  `reports/control_plane/archive/`, and `reports/archive/deferred/`
- `TASKS.md`
- code, test, tooling, or doc files named by an active finding, only when the
  fix is bounded and directly resolves that finding

If a finding requires broad runtime, substrate, seed, parity, or production
semantics work, split it into the `/mu` red-team packet or a narrower structural
implementation packet instead of hiding it in this cleanup wave.

- `reports/deferred/non_blocking/deferred-findings-fix-sweep-2026-05-04_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work Items

1. Inventory blocker and non-blocker findings in the required surfaces.
2. Classify every finding against current code, tests, or direct command output
   as fixed-by-code, stale/historical, active blocker, active non-blocker, or
   needs split authorization.
3. Fix active blockers first when the code/test/doc surface is bounded and named
   by the finding.
4. Fix non-blockers when the repair is bounded; otherwise leave them in
   `reports/deferred/non_blocking/` with concrete evidence and a next packet.
5. Move stale or closed findings out of active folders after code-truth
   verification, using the existing archive/resolved destination that matches the
   source lane.
6. Update report indexes, TASKS, and packet truth so closed parent lanes do not
   get reopened by stale generated advisory text.
7. If manual intervention is needed for pipeline/recovery/builder behavior,
   mechanize the repair in this wave when bounded or add an explicit follow-up
   packet with file:line or command evidence.

## Constraints

- Do not mark a finding closed from report prose alone; use current code, tests,
  or direct command evidence.
- Do not leave stale or code-closed findings in active blocking/non-blocking
  folders after they have been proven closed; archive or resolve them.
- Do not move a blocker into non-blocking just to clear the blocking lane.
- Do not widen this wave into a full `/mu` runtime red-team; that is owned by
  `reports/control_plane/mu_preproduction_redteam_2026-05-04.md`.
- Do not move production forward while active blockers remain unresolved.

## Stop Conditions

Stop and split the work if:

1. A finding requires broad runtime or parity semantics beyond a bounded repair.
2. A blocker cannot be reproduced or dismissed with direct file:line or command
   evidence.
3. The correct fix needs a builder/recovery mechanism not yet represented by a
   bounded work item.
4. The wave would need to edit outside the allowed surfaces without a finding
   naming that file.

## Acceptance Criteria

- `reports/deferred/blocking/` contains only active blockers with current
  evidence, or only its README when no active blockers remain.
- `reports/deferred/non_blocking/` contains only active advisories or follow-ups
  with concrete evidence; stale or code-closed items have been moved to an
  archive/resolved destination.
- Blocker/non-blocker references in `reports/l4_wave_indicators/` and
  `reports/control_plane/` are either fixed, routed, or moved/marked historical
  with code-truth evidence.
- `TASKS.md` points to the next required packet after this sweep.
- Validation includes `git diff --check`, docs consistency, stale NEXT checks,
  and an L4 execution-contract check for the changed files.

## Phase B Implementation Summary

### Inventory Result

- Direct inventory command: `rg --files reports/deferred/blocking reports/deferred/non_blocking | sort | nl -ba`.
- Blocking lane result: `reports/deferred/blocking/` contains only `README.md`.
- Non-blocking lane result after this sweep: `reports/deferred/non_blocking/`
  contains `README.md` plus 27 active advisory/follow-up packets with concrete
  evidence targets.
- L4 indicator artifacts under `reports/l4_wave_indicators/` remain provenance
  artifacts; this sweep did not rewrite historical indicator JSON. Active
  finding truth now lives in the deferred lane and this control-plane packet.

### Bounded Fixes

- `mu/tools/hooks/merge_pr.sh` now resolves sweep PR bot threads before extracting
  sweep findings, so `sweep_findings.json` is populated only with bot findings
  that remain unresolved after the resolver runs.
- `mu/tools/executors/commit_executor.py` now normalizes `target_gate_id` to
  `G1`-`G8`, derives it from the same-wave tracked packet when routing metadata
  is invalid or missing, defaults to `G8` only after those sources fail, and
  rejects invalid handoff target gates before commit execution.
- `reports/control_plane/parallel_pipeline_bus_namespacing_2026-04-29.md` and
  `reports/control_plane/parallel_pipeline_monitor_identity_2026-04-30.md` now
  mark their status as historical/landed instead of commit-ready after the parent
  lane closed.
- `reports/control_plane/parallel_pipeline_agent_teams_2026-04-30.md` no longer
  carries stale TASKS.md line-number citations in its grounding section.
- `reports/control_plane/post_redteam_engine_state_scheduler_reduction_2026-04-30_2026-04-30.md`
  now points at the current Phase A sweep file lines for F-1/F-2 and the
  historical status summary.

### Archived Code-Closed Or Stale Packets

Moved from `reports/deferred/non_blocking/` to `reports/archive/deferred/`:

- `autoping-owner-health-selfheal-2026-05-03_bridge_nonblockers.md` ->
  `autoping-owner-health-selfheal-2026-05-03_bridge_nonblockers_closed-by-deferred-findings-fix-sweep-2026-05-04.md`
- `deferred-report-truth-active-closeout-2026-05-03_bridge_nonblockers.md` ->
  `deferred-report-truth-active-closeout-2026-05-03_bridge_nonblockers_closed-by-deferred-findings-fix-sweep-2026-05-04.md`
- `merge-pr-sweep-count-and-packet-truth-2026-05-03_bridge_nonblockers.md` ->
  `merge-pr-sweep-count-and-packet-truth-2026-05-03_bridge_nonblockers_closed-by-deferred-findings-fix-sweep-2026-05-04.md`
- `phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02_bridge_nonblockers.md` ->
  `phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02_bridge_nonblockers_closed-by-deferred-findings-fix-sweep-2026-05-04.md`
- `post-redteam-engine-state-scheduler-reduction-2026-04-30_bridge_nonblockers.md` ->
  `post-redteam-engine-state-scheduler-reduction-2026-04-30_bridge_nonblockers_closed-by-deferred-findings-fix-sweep-2026-05-04.md`
- `tasks-deferred-code-truth-cleanup-2026-05-03_bridge_nonblockers.md` ->
  `tasks-deferred-code-truth-cleanup-2026-05-03_bridge_nonblockers_closed-by-deferred-findings-fix-sweep-2026-05-04.md`

### Retained Active Non-Blocking Packets

The remaining active non-blocking files are intentionally retained because this
bounded sweep did not reproduce closeout proof for them, or because the finding
requires a follow-up packet broader than this cleanup wave. They stay in
`reports/deferred/non_blocking/` with current evidence targets.

Retained paths:

- `reports/deferred/non_blocking/codex-autoping-window-watchdog-selfheal-2026-05-01_bridge_nonblockers.md`
- `reports/deferred/non_blocking/deferred-report-truth-cleanup-2026-05-02_bridge_nonblockers.md`
- `reports/deferred/non_blocking/hook_soft_gate_residue.md`
- `reports/deferred/non_blocking/hybrid-recovery-agent-2026-04-16_bridge_nonblockers.md`
- `reports/deferred/non_blocking/learning-store-warming-2026-04-12-2026-04-13_bridge_nonblockers.md`
- `reports/deferred/non_blocking/meta-bridge-taskid-path-safety-2026-04-03_bridge_nonblockers.md`
- `reports/deferred/non_blocking/pager-deterministic-session-2026-04-18_bridge_nonblockers.md`
- `reports/deferred/non_blocking/pager-lifecycle-event-coverage-2026-04-23_bridge_nonblockers.md`
- `reports/deferred/non_blocking/parallel-pipeline-bus-namespacing-2026-04-29_bridge_nonblockers.md`
- `reports/deferred/non_blocking/phase-b-tracked-packet-routing-record-2026-04-14_bridge_nonblockers.md`
- `reports/deferred/non_blocking/phase-b-validate-inputs-task-id-leniency-2026-04-20_bridge_nonblockers.md`
- `reports/deferred/non_blocking/pipeline-agent-pager-2026-04-16_bridge_nonblockers.md`
- `reports/deferred/non_blocking/pipeline-recovery-phase1-2026-03-31_bridge_nonblockers.md`
- `reports/deferred/non_blocking/plan-learning-store-enforcement-2026-04-08-2026-04-08_bridge_nonblockers.md`
- `reports/deferred/non_blocking/post-commit-roundtrip-2026-04-04_bridge_nonblockers.md`
- `reports/deferred/non_blocking/post-merge-verify-fetch-fix-2026-04-11_bridge_nonblockers.md`
- `reports/deferred/non_blocking/pr820_bot_auto_deferred_post-reentry-reroute-and-notification-truth-2026-04-23.md`
- `reports/deferred/non_blocking/recovery-gate-pr-conflicting-2026-04-20_bridge_nonblockers.md`
- `reports/deferred/non_blocking/recovery-gate-wiring-2026-03-31_bridge_nonblockers.md`
- `reports/deferred/non_blocking/redteam_2026-03-14_repo_non_blockers.md`
- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
- `reports/deferred/non_blocking/routing-api-plus-write-gate-2026-04-20_bridge_nonblockers.md`
- `reports/deferred/non_blocking/supervisor-prompt-override-2026-04-20_bridge_nonblockers.md`
- `reports/deferred/non_blocking/tier-2-auto-retry-tier-3-llm-recovery-loop-2026-03-31_bridge_nonblockers.md`
- `reports/deferred/non_blocking/tier3-short-circuit-2026-04-17_bridge_nonblockers.md`
- `reports/deferred/non_blocking/w5a_reentry_gate_coverage.md`
- `reports/deferred/non_blocking/wave1a-pipeline-validation-2026-03-31_bridge_nonblockers.md`

### Packet Truth

- `reports/deferred/README.md` and `reports/deferred/non_blocking/README.md`
  now record the 2026-05-04 inventory and archive movement.
- `reports/control_plane/README.md` now lists both immediate pre-production
  control-plane packets.
- `TASKS.md` now points to
  `reports/control_plane/mu_preproduction_redteam_2026-05-04.md` as the next
  required packet after this sweep lands.

## Phase B Validation

Phase B-local validation completed on 2026-05-04:

- `git diff --check` - PASS.
- `./tools/checks/check_docs_consistency.sh` - PASS. The command retained the
  existing advisory warning that `STATUS.md` was last updated 26 days ago
  (`2026-04-08`), but all consistency checks passed.
- `bash tools/checks/check_stale_next_items.sh` - PASS. The command checked 17
  PR references in the NEXT section and found all merged PRs properly marked.
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id deferred-findings-fix-sweep-2026-05-04`
  - PASS. The staged set is L4_ENABLER compliant under the packet's
  `FOUNDER_OVERRIDE`.

## Follow-On

After this packet lands, run `reports/control_plane/mu_preproduction_redteam_2026-05-04.md`
before any production-forward movement.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `deferred-findings-fix-sweep-2026-05-04`
- Active packet: `reports/control_plane/deferred_findings_fix_sweep_2026-05-04.md`
- Indicator artifact: `reports/l4_wave_indicators/deferred-findings-fix-sweep-2026-05-04.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/hooks/merge_pr.sh`
  - `reports/archive/deferred/autoping-owner-health-selfheal-2026-05-03_bridge_nonblockers_closed-by-deferred-findings-fix-sweep-2026-05-04.md`
  - `reports/archive/deferred/deferred-report-truth-active-closeout-2026-05-03_bridge_nonblockers_closed-by-deferred-findings-fix-sweep-2026-05-04.md`
  - `reports/archive/deferred/merge-pr-sweep-count-and-packet-truth-2026-05-03_bridge_nonblockers_closed-by-deferred-findings-fix-sweep-2026-05-04.md`
  - `reports/archive/deferred/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02_bridge_nonblockers_closed-by-deferred-findings-fix-sweep-2026-05-04.md`
  - `reports/archive/deferred/post-redteam-engine-state-scheduler-reduction-2026-04-30_bridge_nonblockers_closed-by-deferred-findings-fix-sweep-2026-05-04.md`
  - `reports/archive/deferred/tasks-deferred-code-truth-cleanup-2026-05-03_bridge_nonblockers_closed-by-deferred-findings-fix-sweep-2026-05-04.md`
  - `reports/control_plane/README.md`
  - `reports/control_plane/deferred_findings_fix_sweep_2026-05-04.md`
  - `reports/control_plane/mu_preproduction_redteam_2026-05-04.md`
  - `reports/control_plane/parallel_pipeline_agent_teams_2026-04-30.md`
  - `reports/control_plane/parallel_pipeline_bus_namespacing_2026-04-29.md`
  - `reports/control_plane/parallel_pipeline_monitor_identity_2026-04-30.md`
  - `reports/control_plane/post_redteam_engine_state_scheduler_reduction_2026-04-30_2026-04-30.md`
  - `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`
  - `reports/deferred/README.md`
  - `reports/deferred/non_blocking/README.md`
  - `reports/deferred/non_blocking/deferred-findings-fix-sweep-2026-05-04_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/deferred-findings-fix-sweep-2026-05-04.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `deferred-findings-fix-sweep-2026-05-04`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/deferred-findings-fix-sweep-2026-05-04_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `deferred-findings-fix-sweep-2026-05-04`
- Active packet: `reports/control_plane/deferred_findings_fix_sweep_2026-05-04.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `65b76ef9f506e449421218624f3234441297971911dd6c154f0bbb4b686fc351`
- Indicator artifact: `reports/l4_wave_indicators/deferred-findings-fix-sweep-2026-05-04.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id deferred-findings-fix-sweep-2026-05-04 --output reports/l4_wave_indicators/deferred-findings-fix-sweep-2026-05-04.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/deferred_findings_fix_sweep_2026-05-04.md. (2) Commit handoff carries 21 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/deferred-findings-fix-sweep-2026-05-04.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/hooks/merge_pr.sh`
  - `reports/archive/deferred/autoping-owner-health-selfheal-2026-05-03_bridge_nonblockers_closed-by-deferred-findings-fix-sweep-2026-05-04.md`
  - `reports/archive/deferred/deferred-report-truth-active-closeout-2026-05-03_bridge_nonblockers_closed-by-deferred-findings-fix-sweep-2026-05-04.md`
  - `reports/archive/deferred/merge-pr-sweep-count-and-packet-truth-2026-05-03_bridge_nonblockers_closed-by-deferred-findings-fix-sweep-2026-05-04.md`
  - `reports/archive/deferred/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02_bridge_nonblockers_closed-by-deferred-findings-fix-sweep-2026-05-04.md`
  - `reports/archive/deferred/post-redteam-engine-state-scheduler-reduction-2026-04-30_bridge_nonblockers_closed-by-deferred-findings-fix-sweep-2026-05-04.md`
  - `reports/archive/deferred/tasks-deferred-code-truth-cleanup-2026-05-03_bridge_nonblockers_closed-by-deferred-findings-fix-sweep-2026-05-04.md`
  - `reports/control_plane/README.md`
  - `reports/control_plane/deferred_findings_fix_sweep_2026-05-04.md`
  - `reports/control_plane/mu_preproduction_redteam_2026-05-04.md`
  - `reports/control_plane/parallel_pipeline_agent_teams_2026-04-30.md`
  - `reports/control_plane/parallel_pipeline_bus_namespacing_2026-04-29.md`
  - `reports/control_plane/parallel_pipeline_monitor_identity_2026-04-30.md`
  - `reports/control_plane/post_redteam_engine_state_scheduler_reduction_2026-04-30_2026-04-30.md`
  - `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`
  - `reports/deferred/README.md`
  - `reports/deferred/non_blocking/README.md`
  - `reports/deferred/non_blocking/deferred-findings-fix-sweep-2026-05-04_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/deferred-findings-fix-sweep-2026-05-04.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
