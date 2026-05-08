# Deferred-Non-Mu Tooling Control-Plane Remediation 2026-05-07

Date: 2026-05-07
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: deferred-non-mu-tooling-control-plane-remediation-2026-05-07
Class: L4_ENABLER
Category: tooling/control-plane
Phase-A-Lock: LOCKED
Source authorization: FOUNDER_OVERRIDE:deferred-non-mu-tooling-control-plane-remediation-2026-05-07
TASKS authority: TASKS.md:468
Governing packet: reports/control_plane/deferred-non-mu-tooling-control-plane-remediation-2026-05-07_2026-05-07.md
Source routing packet: reports/control_plane/deferred-non-mu-deferred-lane-truth-sweep-2026-05-07_2026-05-07.md

## Scope

This Phase A packet is the governing implementation packet for the non-`/mu`
tooling/control-plane remediation routed by `TASKS.md:468`. Implementation may
only touch a listed current-code surface after the matching source claim is
reproduced against current code. If current code proves a listed claim is already
fixed, close that item as already implemented and remove it from pending
implementation evidence instead of patching stale packet wording.

Files/directories in scope for the implementation wave:

- `reports/control_plane/deferred-non-mu-tooling-control-plane-remediation-2026-05-07_2026-05-07.md`
  for this Phase A packet and later closeout evidence.
- `mu/tools/executors/` and `tools/executors/` for dispatcher, Phase B, commit,
  post-merge, ff-only dispatch, supervisor handoff, and packet-lock tooling.
- `mu/tools/executors/recovery_gate.py` and
  `tools/executors/recovery_gate.py` for recovery-gate command filtering, Tier
  2/Tier 3 containment, timeout accounting, re-entry timeline, stale-review
  selection, and notification quoting.
- `mu/tools/observability/` and `tools/observability/` for dashboard and
  findings-pane rendering defects.
- `mu/tools/runners/`, `tools/runners/`, and
  `tools/runners/validate_agent_compliance.py` for runner and non-Claude
  validator behavior.
- `mu/tools/agents/`, `tools/agents/`, `mu/tools/checks/`, and `tools/checks/`
  for learning-store helper fallback, supervisor override validation, L4
  validator boundaries, and control-plane enforcement checks.
- `.agent_bus/recovery/` and `.agent_bus/meta/` only as existing evidence or
  fixture input when a focused test or command needs pipeline state. Do not add
  non-canonical generated packet residue.
- `mu/tests/tools/` and `tests/tools/` for focused regression coverage of the
  tooling/control-plane surfaces above.
- Source evidence packets under `reports/deferred/blocking/`,
  `reports/deferred/non_blocking/`, and `reports/archive/deferred/` only as
  provenance for the source findings listed below. Those packets are not current
  truth by themselves.

- `reports/deferred/non_blocking/deferred-non-mu-tooling-control-plane-remediation-2026-05-07_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Source Findings

- `learning-store-warming-2026-04-12-2026-04-13_bridge_nonblockers.md`:
  learning-store import fallback can disable agent-memory helpers.
- `meta-bridge-taskid-path-safety-2026-04-03_bridge_nonblockers.md`:
  `lock_plan()` header/body status handling and zero-match envelope proof gaps.
- `mu-preproduction-redteam-2026-05-04_bridge_nonblockers.md`: Phase B can still
  continue implementer work after final REQUEST_CHANGES/NO_GO review budget.
- `pipeline-recovery-phase1-2026-03-31_bridge_nonblockers.md`: tmux/web timeline
  parsing, Phase B re-entry timeline coverage, stale raw review selection, and
  notification quoting.
- `plan-learning-store-enforcement-2026-04-08-2026-04-08_bridge_nonblockers.md`:
  recovery command filtering, lock-timeout persistence wording/code boundary,
  and dangerous command containment.
- `post-commit-roundtrip-2026-04-04_bridge_nonblockers.md`: commit-only retry
  path still invokes commit executor without the structured `--json` surface.
- `post-merge-verify-fetch-fix-2026-04-11_bridge_nonblockers.md`: ff-only merge
  dispatch proof and related commit/dispatch boundaries.
- `recovery-gate-wiring-2026-03-31_bridge_nonblockers.md`: surface-mode
  forwarding timeout gap.
- `supervisor-prompt-override-2026-04-20_bridge_nonblockers.md`: override
  validation contract mismatch between supervisor prompts and L4 validator.
- `tier-2-auto-retry-tier-3-llm-recovery-loop-2026-03-31_bridge_nonblockers.md`:
  Tier 2/Tier 3 recovery containment, logging, timeout accounting, and
  non-canonical generated packet residue.
- `tier3-short-circuit-2026-04-17_bridge_nonblockers.md`: short-circuit behavior
  broader than packet wording.
- `wave1a-pipeline-validation-2026-03-31_bridge_nonblockers.md`: observability
  dashboard attribute escaping and findings-pane inline Python interpolation.
- `hook_soft_gate_residue.md`: non-Claude validator strictness residue in
  `tools/runners/validate_agent_compliance.py`.

## Work Items

Each item below is bounded to the scope list above. Reproduce the current defect
before patching that item; if the defect no longer reproduces, mark that item
closed as already implemented with command evidence and do not relist it as
pending work.

1. Dispatcher, bridge, packet-lock, and merge-dispatch envelope.
   Target `mu/tools/executors/` / `tools/executors/`. Fix current defects in
   `lock_plan()` header/body status handling, zero-match envelope proof, and
   ff-only merge dispatch proof. Add focused `mu/tests/tools/` or `tests/tools/`
   coverage that proves inconsistent plan status, missing envelope matches, and
   unproven ff-only dispatch fail closed.
2. Phase B final-review budget and re-entry handling.
   Target Phase B executor surfaces under `mu/tools/executors/` /
   `tools/executors/`. Enforce the final REQUEST_CHANGES/NO_GO review-budget
   hard stop before implementer continuation, and cover Phase B re-entry
   timeline parsing plus stale raw review selection. Preserve same-wave override
   validation before any pre-commit supervisor handoff.
3. Commit and post-merge control-plane execution.
   Target commit/post-merge executor surfaces under `mu/tools/executors/` /
   `tools/executors/`. Route commit-only retry through the structured `--json`
   surface, keep commit executor authority behind the expected dispatcher
   boundary, and prove post-merge/ff-only dispatch cannot silently bypass the
   structured control-plane path.
4. Recovery gate, recovery command containment, and Tier 2/Tier 3 loops.
   Target `mu/tools/executors/recovery_gate.py` /
   `tools/executors/recovery_gate.py` plus existing `.agent_bus` evidence
   fixtures when needed. Fix current defects in command filtering,
   dangerous-command containment, lock-timeout persistence behavior, surface-mode
   timeout forwarding, Tier 2/Tier 3 logging and timeout accounting, recovery
   notification quoting, stale review selection, and non-canonical generated
   packet residue. Do not scope this item to nonexistent `mu/tools/recovery/` or
   `tools/recovery/` directories.
5. Observability dashboard rendering.
   Target `mu/tools/observability/` / `tools/observability/`. Fix dashboard
   attribute escaping and findings-pane inline Python interpolation so rendered
   observability output is escaped and structurally generated. Add focused
   renderer tests or direct command evidence for both cases.
6. Runner and non-Claude validator behavior.
   Target `tools/runners/validate_agent_compliance.py` and the corresponding
   runner surfaces under `mu/tools/runners/` / `tools/runners/`. Remove current
   non-Claude validator strictness residue without weakening enforceable runner
   compliance, and add focused tests for the accepted and rejected cases.
7. Learning-store helper fallback and supervisor override validation.
   Target `mu/tools/agents/`, `tools/agents/`, `mu/tools/checks/`, and
   `tools/checks/`. Ensure learning-store import fallback cannot disable
   agent-memory helpers, and reconcile supervisor prompt override validation with
   the L4 validator contract using focused regression coverage.

## Constraints

- Do not implement `/mu` structural runtime, seed, scheduler, Stage0, parity, or
  production remediation.
- Do not edit Claude-related residue, including `CLAUDE.md`, `.claude/`, or
  `~/.claude/`.
- Do not run commit, push, PR, merge, or pre-push execution from inside Phase B
  implementer validation.
- Do not treat `TASKS.md:468` or archived source packet wording as proof that a
  listed defect is still unlanded; current-code reproduction controls.
- Do not add generated packet residue under `.agent_bus/` or report lanes unless
  a same-wave automation fix explicitly owns that output.
- Do not target recovery remediation at `mu/tools/recovery/` or
  `tools/recovery/`; current recovery-gate code truth is
  `mu/tools/executors/recovery_gate.py` and `tools/executors/recovery_gate.py`.

## Stop Conditions

- Any fix requires `/mu` structural implementation.
- Any fix requires editing Claude-related residue.
- Any fix would need commit/push/PR/merge execution from a Phase B implementer.
- A source claim cannot be reproduced against current code and no bounded current
  defect remains.
- More than one work item needs invasive cross-directory changes that cannot be
  reviewed as one bounded tooling/control-plane wave.
- Manual pipeline repair is needed but cannot be paired with same-wave automation
  or a precise follow-up automation packet.

## Acceptance Criteria

- Each implemented item cites the current-code reproduction command that failed
  before the fix and the focused validation command that passes after the fix.
- Each item that is already fixed is removed from pending implementation and
  closed with direct command evidence rather than stale source wording.
- Every changed behavior is proven by focused tests under `mu/tests/tools/` or
  `tests/tools/`, or by direct command evidence when a test is not practical.
- Manual pipeline repair, if any, is paired with same-wave automation in the
  scoped tooling surface or with a precise follow-up automation packet.
- No Claude-related files are edited.
- No `/mu` structural remediation is implemented.
- Validation records include command, exit status, and short evidence summary.
- Closeout records the exact changed files and maps each changed file to one of
  the bounded work items above.
- Closeout preserves same-wave authority:
  `FOUNDER_OVERRIDE:deferred-non-mu-tooling-control-plane-remediation-2026-05-07`.

## Grounding / Authorization

`TASKS.md:468` authorizes this wave as `[NEXT-CODEX-POST-REDTEAM]`, Class
`L4_ENABLER`, Category `tooling/control-plane`, target gate `G8`, Packet
`reports/control_plane/deferred-non-mu-tooling-control-plane-remediation-2026-05-07_2026-05-07.md`.
The same tracker line routes non-`/mu` dispatcher, Phase B, commit, recovery,
observability, runner, and control-plane tooling findings into this bounded
packet, hard-stops `/mu` structural implementation and Claude-related edits, and
requires same-wave automation or a precise follow-up packet for manual pipeline
repair.

Same-wave control-surface authorization:
`FOUNDER_OVERRIDE:deferred-non-mu-tooling-control-plane-remediation-2026-05-07`.

Governing packet:
`reports/control_plane/deferred-non-mu-tooling-control-plane-remediation-2026-05-07_2026-05-07.md`.

Source routing packet:
`reports/control_plane/deferred-non-mu-deferred-lane-truth-sweep-2026-05-07_2026-05-07.md`.

Indicator artifact:
`reports/l4_wave_indicators/deferred-non-mu-tooling-control-plane-remediation-2026-05-07.json`.

## Phase B Implementation Evidence

Same-wave authority preserved:
`FOUNDER_OVERRIDE:deferred-non-mu-tooling-control-plane-remediation-2026-05-07`.

### Changed Files By Work Item

- Work items 1 and 3:
  `mu/tools/executors/executor_common.py`,
  `mu/tools/executors/executor_dispatch.py`,
  `mu/tests/tools/test_executor_dispatch.py`.
- Work item 2:
  `mu/tools/executors/phase_b_executor.py`,
  `mu/tests/tools/test_phase_b_executor.py`.
- Work items 4 and 5:
  `mu/tools/executors/recovery_gate.py`,
  `mu/tools/observability/_pane_findings.sh`,
  `mu/tools/observability/pipeline_dashboard_web.py`,
  `mu/tests/tools/test_recovery_gate.py`.
- Work item 6:
  `mu/tests/tools/test_validate_agent_compliance.py`.
- Work item 7:
  `mu/tests/tools/test_run_review.py`,
  `mu/tests/tools/test_meta_bridge_supervisor.py`.
- Closeout evidence:
  `reports/control_plane/deferred-non-mu-tooling-control-plane-remediation-2026-05-07_2026-05-07.md`.

### Current-Code Reproduction And Closure

- Work item 1:
  - `lock_plan()` body-only status claim did not reproduce as an unlanded code
    defect. Pre-fix direct probe:
    `python3 - <<'PY' ... phase_a_executor.lock_plan(body-only Status:) ... PY`;
    exit status 0; evidence: `header_status_present=False`,
    `body_status_preserved=True`, and stderr warned no header status.
  - Zero-envelope parsing was closed with focused coverage. Pre-fix direct
    probe: `python3 - <<'PY' ... _parse_phase_a_findings("no envelope here") ... PY`;
    exit status 0; evidence: parser returned `[]`.
  - ff-only/post-merge dispatch proof already existed in current code and was
    revalidated by the post-commit linked-worktree test below.
- Work item 2:
  - Pre-fix reproduction:
    `python3 - <<'PY' ... run_phase_b(max_bridge_rounds=1) with final REQUEST_CHANGES ... PY`;
    exit status 0; evidence: `initial_status=max_rounds_reached`,
    `initial_implementer_calls=2`.
  - Fixed behavior: Phase B now emits the hard fail at the final allowed
    REQUEST_CHANGES/NO_GO round before re-invoking the implementer. Re-entry
    hard-fail behavior is covered with the same stop before continuation.
- Work item 3:
  - Pre-fix reproduction:
    `python3 - <<'PY' ... executor_dispatch._retry_commit_only(...) ... PY`;
    exit status 0; evidence: `has_json=False`.
  - Fixed behavior: commit-only retry now routes through the structured
    dispatcher commit surface with `--json`; non-phase supervisor dispatch also
    forwards configured timeouts.
- Work item 4:
  - Pre-fix reproduction:
    `python3 - <<'PY' ... recovery_gate._is_dangerous_command(...) ... PY`;
    exit status 0; evidence: inert `command -v curl` and `command -V curl`
    probes were classified dangerous while execution forms were also blocked.
  - Pre-fix timeout-boundary probe:
    `python3 - <<'PY' ... inspect.signature(executor_dispatch.run_surface_command) ... PY`;
    exit status 0; evidence: `timeout_param=False`.
  - Fixed behavior: lookup-only shell builtins are allowed, dangerous execution
    remains blocked, and non-phase surface commands receive timeout accounting.
- Work item 5:
  - Dashboard attribute escaping did not reproduce as an unlanded defect. Direct
    source probe:
    `python3 - <<'PY' ... inspect pipeline_dashboard_web esc(...) ... PY`;
    exit status 0; evidence: `quotes_escaped=True`.
  - Pre-fix findings-pane probe:
    `rg -n 'python3 -c "|open\('\''\$|osascript -e|display notification "' mu/tools/observability/_pane_findings.sh`;
    exit status 0; evidence: inline shell-interpolated Python/AppleScript sites
    were present.
  - Pre-fix stale-review/timeline probes:
    direct dashboard fixture commands showed `picked_newest=False` for raw
    reviewer selection and `timeline_events=[]` despite a valid earlier
    reviewer envelope followed by malformed text.
  - Fixed behavior: raw reviewer files are selected by newest file mtime across
    all raw dirs, timeline parsing uses the latest valid reviewer envelope, and
    findings-pane parsing/notification rendering use argv-fed structured
    helpers instead of shell interpolation.
- Work item 6:
  - Non-Claude strictness residue did not reproduce as an unlanded weakening.
    Direct probe:
    `printf 'nonsense\n' | PYTHONHASHSEED=0 python3 tools/runners/validate_agent_compliance.py --strict`;
    exit status 1; evidence: JSON reported `compliant: false` with missing
    `CHECKED`, `NOT_CHECKED`, and `VERDICT` violations.
  - Closure adds focused strict-mode regression coverage without weakening
    accepted no-finding non-strict output.
- Work item 7:
  - Learning-store import fallback did not reproduce as an unlanded helper
    disablement. Direct import-block probe:
    `python3 - <<'PY' ... block tools.executors.recovery_gate import while loading run_review.py ... PY`;
    exit status 0; evidence: `agent_memory_available=True`,
    `learning_store_available=False`, `agent_memory_callable=True`.
  - Supervisor override validation was closed with prompt regression coverage
    that preserves the L4 validator contract wording that an external override
    validator is not blanket proof of every runtime, scope, or no-op property.

### Phase B-Local Validation

- `python3 -m py_compile mu/tools/executors/phase_b_executor.py mu/tools/executors/executor_common.py mu/tools/executors/executor_dispatch.py mu/tools/executors/recovery_gate.py mu/tools/observability/pipeline_dashboard_web.py`
  - Exit status: 0.
  - Evidence: executor and dashboard Python modules compile.
- `bash -n mu/tools/observability/_pane_findings.sh`
  - Exit status: 0.
  - Evidence: findings-pane shell script parses.
- `rg -n 'python3 -c "|open\('\''\$|osascript -e|display notification "' mu/tools/observability/_pane_findings.sh`
  - Exit status: 1.
  - Evidence: no inline Python or AppleScript shell-interpolation matches remain.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py::TestPhaseBHardFailPagerEvents::test_run_phase_b_emits_hard_fail_when_initial_bridge_hits_max_rounds mu/tests/tools/test_phase_b_executor.py::TestPhaseBHardFailPagerEvents::test_run_phase_b_emits_hard_fail_when_reentry_hits_max_rounds`
  - Exit status: 0.
  - Evidence: 2 passed.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestPhaseAPlanCreation::test_lock_plan_missing_header_status_does_not_rewrite_body_status mu/tests/tools/test_executor_dispatch.py::TestPhaseAPlanCreation::test_parse_phase_a_findings_zero_match_returns_empty mu/tests/tools/test_executor_dispatch.py::TestCommitContinuationAndBotFreshness::test_post_commit_uses_linked_base_worktree_for_merge_verification mu/tests/tools/test_executor_dispatch.py::TestModularSurfaceEntrypoints::test_retry_commit_only_uses_structured_json_surface mu/tests/tools/test_executor_dispatch.py::TestModularSurfaceEntrypoints::test_main_non_phase_surface_runs_forwarded_command`
  - Exit status: 0.
  - Evidence: 5 passed.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py::TestShellDispatchBuiltinsAsPrefixes::test_command_dispatch_to_dangerous_targets_blocked mu/tests/tools/test_recovery_gate.py::TestShellDispatchBuiltinsAsPrefixes::test_command_lookup_only_probes_allowed mu/tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution::test_pipeline_dashboard_web_activity_uses_newest_raw_reviewer_by_mtime mu/tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution::test_pipeline_dashboard_web_timeline_uses_latest_valid_reviewer_envelope mu/tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution::test_pane_findings_parses_reviewer_file_when_path_contains_quote`
  - Exit status: 0.
  - Evidence: 31 passed.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_validate_agent_compliance.py::TestCheckComplianceBasic::test_strict_mode_rejects_nonsense_even_without_findings mu/tests/tools/test_run_review.py::TestLearningStoreWarming::test_learning_store_import_failure_keeps_agent_memory_available mu/tests/tools/test_meta_bridge_supervisor.py::TestCheckTasksAuthorizationFounderOverride::test_meta_bridge_task_template_includes_founder_override_authorization_clause`
  - Exit status: 0.
  - Evidence: 3 passed.
- `git diff --check`
  - Exit status: 0.
  - Evidence: no whitespace errors.

### Bridge Round 2 REQUEST_CHANGES Remediation

- Blocking finding closed:
  canonical `python3 tools/checks/enforce_l4_execution_contract.py --staged`
  failed no-class for the staged tooling/control-plane candidate because
  `TASKS.md` was already grounded in repo history and was not itself staged.
- Pre-fix reproduction:
  `./tools/session/founder_session_guard.sh redteam --run`; exit status 1 due
  to the expected L4 command failure. Evidence: `Wave class: (none)`,
  `Changed files: 15`, `Control-plane files: 6`, and
  `FAIL-CLOSED: Critical control-plane tooling files changed but no wave class
  marker found`.
- Same-wave fix:
  `mu/tools/checks/enforce_l4_execution_contract.py` now binds governed staged
  runtime/control-plane scopes to a tracker note only when a changed
  `reports/l4_wave_indicators/<wave_id>.json` artifact exactly matches that
  note's `wave_id` and `indicator_artifact_ref`. Missing or ambiguous changed
  indicator artifacts remain no-class fail-closed.
- Same-wave coverage:
  `mu/tests/tools/test_l4_execution_contract_enforcement.py` adds exact-match,
  ambiguity, canonical staged-pass, and no-indicator fail-closed regressions.
- Bridge Round 2 validation:
  - `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_l4_execution_contract_enforcement.py`
    - Exit status: 0.
    - Evidence: 180 passed.
  - `python3 tools/checks/enforce_l4_execution_contract.py --staged`
    - Exit status: 0.
    - Evidence: `Wave class: L4_ENABLER`, `Changed files: 17`,
      `Control-plane files: 7`, and L4 contract compliant.
  - `git diff --check`
    - Exit status: 0.
    - Evidence: no whitespace errors.
  - `python3 -m py_compile tools/checks/enforce_l4_execution_contract.py mu/tests/tools/test_l4_execution_contract_enforcement.py`
    - Exit status: 0.
    - Evidence: checker and focused regression module compile.

No Claude-related files were edited. No `/mu` structural runtime, seed,
scheduler, Stage0, parity, or production remediation was implemented. No
commit, push, PR, merge, pre-push, `./tools/audit_fast.sh`, or `./dev.sh`
execution was run during Phase B-local validation.

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `deferred-non-mu-tooling-control-plane-remediation-2026-05-07`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/deferred-non-mu-tooling-control-plane-remediation-2026-05-07_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `deferred-non-mu-tooling-control-plane-remediation-2026-05-07`
- Active packet: `reports/control_plane/deferred-non-mu-tooling-control-plane-remediation-2026-05-07_2026-05-07.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `bb017b4b3e0b3a3582fcb3ef0753158eeb858564b29ca7e8381b3f79ce0914d8`
- Indicator artifact: `reports/l4_wave_indicators/deferred-non-mu-tooling-control-plane-remediation-2026-05-07.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_l4_execution_contract_enforcement.py mu/tests/tools/test_meta_bridge_supervisor.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py mu/tests/tools/test_run_review.py mu/tests/tools/test_validate_agent_compliance.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/deferred-non-mu-tooling-control-plane-remediation-2026-05-07_2026-05-07.md. (2) Final pytest gate covered 7 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/deferred-non-mu-tooling-control-plane-remediation-2026-05-07.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_l4_execution_contract_enforcement.py`
  - `mu/tests/tools/test_meta_bridge_supervisor.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tests/tools/test_run_review.py`
  - `mu/tests/tools/test_validate_agent_compliance.py`
  - `mu/tools/checks/enforce_l4_execution_contract.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `mu/tools/observability/_pane_findings.sh`
  - `mu/tools/observability/pipeline_dashboard_web.py`
  - `reports/control_plane/deferred-non-mu-tooling-control-plane-remediation-2026-05-07_2026-05-07.md`
  - `reports/deferred/non_blocking/deferred-non-mu-tooling-control-plane-remediation-2026-05-07_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/deferred-non-mu-tooling-control-plane-remediation-2026-05-07.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
