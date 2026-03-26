# Commit Pipeline Automation Corrective Follow-On Plan

Date: 2026-03-25
Status: Phase B (bootstrap-exception corrective wave — SDK findings fixed, supervision helper landed, meta-supervisor/checker hardening active)
Phase-A-Lock: LOCKED
Execution mode: BOOTSTRAP_PHASE_B_EXCEPTION
Purpose: preserve the current dirty implementation wave, fix the concrete SDK-review findings it exposed, and add explicit long-run supervision so Phase B can get through its one-time SDK gate and reach the bridge loop honestly.

## Implementation Status (corrective pass)

All 6 critical/high SDK findings addressed:
- **962** (critical) FIXED: high severity now blocked before explicit disposition check; cannot be downgraded
- **963** (critical) FIXED: empty-findings envelopes filtered before conflict check; prepended decoys harmless
- **964** (critical) FIXED: `tracked_packet` path validated for traversal and repo-root containment before `--plan`
- **965** (critical) FIXED: `wave_id` verification after TASKS.md write now uses `_count_exact_wave_id_mentions`
- **954** (high) ALREADY FIXED: `lock_plan` uses `re.subn(..., count=1)` with exact-count assertion
- **955** (high) ALREADY FIXED: `create_plan_draft` validates `plan_name` against `PLAN_NAME_RE` + traversal check

SDK gate observability (Slice 2) ALREADY IMPLEMENTED in prior wave:
- `phase_b_executor.py:run_sdk_agents` uses Popen + poll loop with heartbeat, stale_run (-2), aggregation_hang (-3), timeout (-1)
- `run_review.py` supports `RCX_REVIEW_STATUS_PATH`, `RCX_REVIEW_HEARTBEAT_INTERVAL`, `RCX_REVIEW_SINGLE_TAIL_TIMEOUT`
- `executor_config.json` sets `"phase_b": "quick"` (not full) for bounded SDK gate

Long-run supervision (Slice 3):
- New: `mu/tools/executors/supervision_poll.py` — read-only poller for PID tree, artifact mtime/size, output growth, stale_run/aggregation_hang detection

## Current Reproduced Truth (post-corrective-pass)

1. The corrective wave preserves the prior wave's dirty worktree as baseline, and the current Phase B wave-owned scope is 41 files.
   - Current wave-owned baseline files:
     - `TASKS.md`
     - `mu/tests/tools/module_loader.py`
     - `mu/tests/tools/test_agent_bridge_supervisor.py`
     - `mu/tests/tools/test_agent_prompt_contract_injection.py`
     - `mu/tests/tools/test_agent_tooling_smoke.py`
     - `mu/tests/tools/test_closeout_attestation.py`
     - `mu/tests/tools/test_commit_executor_receipt.py`
     - `mu/tests/tools/test_control_surface_review.py`
     - `mu/tests/tools/test_executor_dispatch.py`
     - `mu/tests/tools/test_l4_execution_contract_enforcement.py`
     - `mu/tests/tools/test_meta_bridge_supervisor.py`
     - `mu/tests/tools/test_phase_b_executor.py`
     - `mu/tests/tools/test_pre_commit_receipt.py`
     - `mu/tests/tools/test_prompt_verdict_contracts.py`
     - `mu/tests/tools/test_reasoning_verdict_coverage.py`
     - `mu/tests/tools/test_run_review.py`
     - `mu/tests/tools/test_runbook_runtime_gate_sync.py`
     - `mu/tests/tools/test_supervision_poll.py`
     - `mu/tests/tools/test_validate_agent_compliance.py`
     - `mu/tools/agents/expert_prompt.md`
     - `mu/tools/agents/meta_bridge_supervisor.py`
     - `mu/tools/agents/structural_proof_prompt.md`
     - `mu/tools/checks/check_closeout_attestation.py`
     - `mu/tools/checks/check_control_surface_invariants.py`
     - `mu/tools/checks/enforce_l4_execution_contract.py`
     - `mu/tools/executors/commit_executor.py`
     - `mu/tools/executors/executor_common.py`
     - `mu/tools/executors/executor_config.json`
     - `mu/tools/executors/executor_dispatch.py`
     - `mu/tools/executors/phase_a_executor.py`
     - `mu/tools/executors/phase_b_executor.py`
     - `mu/tools/executors/phase_b_implementer.py`
     - `mu/tools/executors/supervision_poll.py`
     - `mu/tools/runners/run_review.py`
     - `mu/tools/runners/shared_agent_utils.py`
     - `mu/tools/runners/validate_agent_compliance.py`
     - `reports/control_plane/commit_pipeline_automation_plan_2026-03-22.md`
     - `reports/control_plane/commit_pipeline_automation_plan_2026-03-25.md`
     - `reports/deferred/non_blocking/commit-pipeline-automation-plan-2026-03-25_bridge_nonblockers.md`
     - `reports/deferred/non_blocking/post_merge_supervisor_phase_a_nonblockers_2026-03-21.md`
     - `reports/l4_wave_indicators/commit-pipeline-automation-plan-2026-03-25.json`

2. All prior-wave slices 1-4 remain intact.
   - Planless/optional Phase B entry path in `phase_b_executor.py`.
   - Dispatcher routes tracker-only and embedded-handoff commit work via `--routing-record`.
   - `commit_executor.py` accepts `--routing-record`, but only `UPDATE_TRACKER_ONLY` may synthesize a handoff; `COMMIT_GO` and `COMMIT_GO_HOLD_PUSH` still require a pre-prepared or embedded Phase B handoff so the exact receipt chain is preserved.
   - `phase_a_executor.py` reuses tracked packets instead of always minting fresh dated drafts.

3. All 6 critical/high SDK findings are fixed and tested.
   - **962** FIXED: `_disposition_for_finding` checks critical/high severity BEFORE generic disposition, overrides `non_blocking` disposition on critical/high.
   - **963** FIXED: `_parse_findings_from_render` filters empty-findings envelopes (`{"findings": []}`) before conflict check; prepended decoys are harmless.
   - **964** FIXED: `dispatch()` validates `tracked_packet` for `..` traversal and `is_relative_to(repo.resolve())` before passing to `--plan`.
   - **965** FIXED: `_count_exact_wave_id_mentions` uses word-boundary regex (`(?<![a-z0-9-])...(?![a-z0-9-])`) instead of substring count.
   - **954** FIXED: `lock_plan` uses `re.subn(..., count=1)` with exact-count assertion `lock_replacements != 1`.
   - **955** FIXED: `create_plan_draft` validates `plan_name` against `PLAN_NAME_RE` + `Path(plan_name).name != plan_name` traversal check.

4. SDK gate observability is now built into `run_sdk_agents`.
   - Uses `Popen` + poll loop (not `subprocess.run` with bare timeout).
   - Heartbeat lines every 30s: step, child PIDs, stdout/stderr bytes, findings mtime, status phase, last-progress timestamp.
   - `stale_run` detection (exit -2): no output/artifact/child-state change for 300s.
   - `aggregation_hang` detection (exit -3): children exited but aggregator alive for 120s.
   - Hard timeout (exit -1): total elapsed exceeds configured timeout.
   - `executor_config.json` sets `"phase_b": "quick"` (not full) for bounded SDK gate.

5. Long-run supervision is now repo-tracked.
   - `mu/tools/executors/supervision_poll.py`: read-only poller for PID tree, artifact mtime/size, output growth, stale_run/aggregation_hang detection.
   - Supports `--pid`, `--once`, `--artifacts-only`, configurable `--interval` and `--stale` threshold.
   - 17 focused tests in `mu/tests/tools/test_supervision_poll.py`.

6. Validation results (current staged candidate):
   - Focused pre-commit control-surface suite:
     - `python3 -m pytest mu/tests/tools/test_control_surface_review.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_meta_bridge_supervisor.py mu/tests/tools/test_run_review.py mu/tests/tools/test_supervision_poll.py -q`
     - Result: `497 passed in 57.11s`
   - Additional focused corrective-pass suites:
     - `python3 -m pytest mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_meta_bridge_supervisor.py -q`
     - Result: `226 passed in 2.23s`
   - Post-SDK follow-on hardening suites:
     - `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_meta_bridge_supervisor.py -q`
     - Result: `61 passed in 1.66s`
     - `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_control_surface_review.py -q`
     - Result: `55 passed in 0.65s`
     - `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_phase_b_executor.py -q`
     - Result: `170 passed in 0.57s`
     - `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_agent_prompt_contract_injection.py mu/tests/tools/test_prompt_verdict_contracts.py mu/tests/tools/test_reasoning_verdict_coverage.py mu/tests/tools/test_closeout_attestation.py mu/tests/tools/test_pre_commit_receipt.py mu/tests/tools/test_runbook_runtime_gate_sync.py -q`
     - Result: `46 passed in 1.63s`
     - `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_agent_bridge_supervisor.py -q`
     - Result: `51 passed in 34.99s`
   - Current supervisor/checker hardening landed:
     - `meta_bridge_supervisor.py`: bounded `git` and validation subprocesses; multi-envelope parsing now rejects conflicting blocks instead of trusting the first match
     - `check_control_surface_invariants.py`: cached repo-root normalization; dead Claude-memory lookup removed
     - duplicated inline module loaders collapsed onto `mu/tests/tools/module_loader.py`
   - `./tools/checks/check_docs_consistency.sh`: pass
   - `python3 tools/checks/enforce_l4_execution_contract.py --files mu/tools/agents/meta_bridge_supervisor.py mu/tools/checks/check_control_surface_invariants.py mu/tests/tools/test_control_surface_review.py mu/tests/tools/test_meta_bridge_supervisor.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_agent_prompt_contract_injection.py mu/tests/tools/test_prompt_verdict_contracts.py mu/tests/tools/test_reasoning_verdict_coverage.py mu/tests/tools/test_closeout_attestation.py mu/tests/tools/test_pre_commit_receipt.py mu/tests/tools/test_agent_bridge_supervisor.py mu/tests/tools/test_runbook_runtime_gate_sync.py`: pass

7. Latest live rerun reached bridge convergence and stopped only on founder-facing truth-sync residue.
   - `phase_b_executor.py --plan reports/control_plane/commit_pipeline_automation_plan_2026-03-25.md --bootstrap-exception -v --json`
   - One-time SDK gate: completed on `quick` depth with `expert=COULD_SIMPLIFY`, `adversary=SECURE`, `structural-proof=PROVEN`, `verifier=UNKNOWN`; executor continued to bridge for contextual classification.
   - Bridge round 1 (`phase-b-r1-18d09148`): `GO`
   - Final pytest gate: pass
   - Pre-commit supervisor: stopped at `NEEDS_PHASE_B` because (a) this packet was stale against the actual 41-file candidate, (b) `TASKS.md` overclaimed closure relative to the deferred lane, and (c) the supervisor package emitted `deferred_items: []` despite the active non-blocking packet in `changed_files`.

## Goal

Use the current dirty wave as baseline, not throwaway residue, and close the next smallest honest set of gaps:

1. Fix the concrete critical/high findings emitted by the one-time Phase B SDK pass.
2. Preserve the already-landed slices 1-4 instead of redoing them blindly.
3. Add explicit long-run supervision rules so executor/reviewer liveness is observable and stale states are surfaced honestly.
4. Get the next live Phase B run through the single SDK gate and into the bridge loop, or fail closed with a sharper, mechanically diagnosed reason.

## In Scope

### Slice 1: Fix concrete SDK blockers in touched executors

Files:
- `mu/tools/executors/phase_b_executor.py`
- `mu/tools/executors/executor_dispatch.py`
- `mu/tools/executors/commit_executor.py`
- `mu/tools/executors/phase_a_executor.py`
- relevant focused tests

Required outcomes:
- `phase_b_executor.py`
  - critical severity cannot be downgraded merely because a finding carries an explicit disposition field
  - envelope parsing cannot be spoofed by a prepended empty/decoy envelope
- `executor_dispatch.py`
  - path traversal in plan-name derivation from routing record candidate text is blocked fail-closed
- `commit_executor.py`
  - wave_id duplicate detection uses exact matching, not substring count
- `phase_a_executor.py`
  - `plan_name` is sanitized/validated before deriving a path
  - `lock_plan` does not use unsafe global replacement that can mutate multiple unrelated tokens

Design constraints:
- Do not revert the already-landed planless/dispatcher/commit-routing/packet-reuse changes unless direct code truth forces it.
- Preserve the current dirty worktree wave as the baseline under correction.

### Slice 2: Make the one-time Phase B SDK gate bounded and observable

Files:
- `mu/tools/executors/phase_b_executor.py`
- `tools/runners/run_review.py`
- `mu/tools/runners/run_review.py`
- `mu/tools/executors/executor_config.json`
- focused tests or executor-level supervision tests if needed

Required outcomes:
- Keep the architecture truth:
  - SDK review runs once before bridge
  - bridge/implementer loop happens only after that one SDK pass succeeds
- But make the SDK gate honest and operable:
  - if it is still intended to be `--depth full`, it must return within the configured bound for this wave size
  - if `--depth full` is not actually the right hard-gate mode for Phase B, tighten it honestly and document the phase-specific contract
- Add explicit supervision behavior:
  - heartbeat lines with current step, child pid(s), and last-progress timestamp
  - stale-run detection when output/artifacts/child-state stop moving past threshold
  - explicit failure reporting if reviewer children exit but the aggregator remains alive past threshold

### Slice 3: Operator / Claude observability must become repo-tracked protocol

Files:
- repo-tracked protocol surface as needed
- optionally a thin helper under `tools/` or `mu/tools/agents/`

Required outcomes:
- Long-running executor/reviewer runs must no longer rely on memory or ad hoc operator habits.
- Introduce explicit protocol/helper support for:
  - `ps` / child process polling
  - artifact `mtime` and size polling
  - output-growth polling
  - bridge DB inspection before/after bridge-related runs
- The target rules to institutionalize are:
  - every long-running executor/reviewer run must be polled for process state, artifact `mtime`, and output growth every 30-60s
  - executor heartbeat lines must show step, child pid, and last-progress timestamp
  - if no output growth and no child-state change for N seconds, surface `stale_run`
  - if reviewer children exit but aggregator stays alive past threshold, fail closed with `aggregation_hang`

Smallest honest path is acceptable:
- protocol text only is not enough unless the run surface also becomes easier to inspect
- a thin read-only helper/script is acceptable if it is actually used by the workflow

### Slice 4: Truth sync for the actual corrective wave packet and directly touched deferred truth

Files:
- `reports/control_plane/commit_pipeline_automation_plan_2026-03-25.md`
- `reports/control_plane/commit_pipeline_automation_plan_2026-03-22.md`
- `reports/deferred/non_blocking/post_merge_supervisor_phase_a_nonblockers_2026-03-21.md`
- only directly relevant deferred packets if current code truth genuinely resolves or reframes them

Required outcomes:
- This Mar 25 packet must remain accurate to the live wave and no longer describe already-fixed pre-implementation truth.
- Locked Mar 22 plan wording must not drift behind current runtime truth.
- Deferred truth should be touched only where this corrective wave actually changes the state of a listed issue.

## Conditionally In Scope

If the SDK gate hardening work directly exposes the need for it, include:
- a thin inspection helper for bridge/reviewer status
- a bounded phase-specific `run_review.py` mode or argument for Phase B hard-gate use

Only do this if:
- it is narrower than a general wrapper
- it is directly testable
- it does not change the bridge loop architecture dishonestly

## Out of Scope

- Top-level one-command wrapper for the whole pipeline
- Commit executor end-to-end remote push/merge proof
- Post-merge supervisor trigger after merge unless directly required by the above fixes
- Broad deferred packet cleanup unrelated to these exact code/doc changes
- Re-architecting Phase B so SDK review runs more than once

## Required Validations

Focused suites:
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_phase_b_executor.py -q`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_executor_dispatch.py -q`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_commit_executor_receipt.py -q`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_meta_bridge_client.py -q`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_meta_bridge_supervisor.py -q`
- any new focused tests for stale-run / aggregation-hang / plan-name sanitization

Governance:
- `python3 tools/checks/enforce_l4_execution_contract.py --files <actual changed tracked files>`
- `./tools/checks/check_docs_consistency.sh`

Commit/pre-push stage only:
- `./tools/pre-push-fast`
- This is not a Phase B implementer-local validation command.
- It belongs to commit/pre-push execution because it shells into `dev.sh -> audit_fast.sh`,
  which is broader than the intended inner-loop validation tier for this wave.

Direct pipeline proof:
- rerun the real Phase B executor on this wave packet
- prove that the one-time SDK gate either:
  - completes and hands off into bridge, or
  - fails closed with a sharper, mechanically diagnosed non-timeout reason
- if SDK passes, continue to bridge and inspect the exact bridge job/state

## Stop Conditions

- `NO-GO` if the same single Phase B SDK pass still times out on this corrected 9-file scope
- `NO-GO` if the critical/high findings above remain unresolved
- `NO-GO` if long-run supervision still depends on operator memory rather than observable protocol/helper behavior
- `NO-GO` if the current dirty wave scope is discarded, rewritten from scratch, or obscured instead of treated as the baseline under correction
- `NO-GO` if the next run again leaves us unable to tell whether the gate is slow, stale, or hung

## Manual / Mechanical Split

Manual in this wave:
- authoring this corrective packet from the failed live Phase B run
- supervising the already-running long SDK pass while the repo lacks built-in heartbeat/stale-run behavior

Mechanical after that:
- code fixes should go through the real Phase B implementer/executor path
- the next Phase B run should own:
  - one-time SDK gate
  - bridge loop
  - blocker/non-blocker handling
  - pre-commit transition if it gets that far

## Desired Closeout

At closeout, prove:
- which critical/high findings from `.agent_memory/findings.json` were fixed
- whether the one-time SDK gate is now bounded and observable
- whether the next live Phase B run reaches bridge
- whether the long-run supervision rules are now repo-tracked and mechanically usable
- whether this Mar 25 packet accurately matches current repo truth instead of acting as stale residue
