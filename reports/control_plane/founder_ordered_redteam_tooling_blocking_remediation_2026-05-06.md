# Founder Ordered Redteam Tooling Blocking Remediation

Date: 2026-05-06
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-tooling-blocking-remediation-2026-05-06
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Category: tooling/control-plane
Severity: BLOCKING
Source audit packet: `reports/deferred/blocking/founder_ordered_redteam_tooling_audit_2026-05-05_blocking.md`
Governing packet: `reports/control_plane/founder_ordered_redteam_tooling_blocking_remediation_2026-05-06.md`
Queue order: non-`/mu` blocking remediation, after tests blocking remediation and before non-blocking remediation.
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-tooling-blocking-remediation-2026-05-06
Source authorization: FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05

This packet governs and implements the blocking tooling/control-plane
follow-ups from the founder ordered redteam audit output plus same-wave
pipeline repair follow-ups discovered during the queue-organization and
tooling-blocking remediation waves.
## Scope: Files And Directories In Scope

Implementation is limited to the following control-plane surfaces and focused
regressions needed to prove the blocker fixes:

- `mu/tools/executors/commit_executor.py`
- `mu/tools/executors/phase_b_executor.py`
- `mu/tools/checks/enforce_tracker_sync.sh`
- `mu/tools/checks/enforce_l4_execution_contract.py`
- `tools/checks/enforce_l4_execution_contract.py` as the repo invocation path
  for the same checked surface.
- `tools/checks/enforce_tracker_sync.sh` as the repo invocation path for the
  same checked surface.
- `mu/tools/executors/`
- `mu/tools/checks/`
- `mu/tools/hooks/`
- `mu/tools/observability/`
- `mu/tools/recovery/`
- `.github/workflows/`
- `mu/tests/tools/` for focused regressions covering the changed
  control-plane tooling behavior.
- `TASKS.md` only for the implementation-wave tracker update for this
  remediation wave.

Evidence-only references that may be read but must not be edited for this
remediation are:

- `reports/deferred/blocking/founder_ordered_redteam_tooling_audit_2026-05-05_blocking.md`
- `.scratch/phase_b_supervisor_package.json`

## Work Items

1. Fix `B1 - Commit Executor Exposes A Direct Supervisor And Receipt Bypass`.
   Remove the direct operator path that lets `--skip-supervisor` synthesize
   supervisor and receipt success, or constrain it to an explicitly governed
   recovery-only path with fail-closed receipt semantics. The direct CLI path
   must not be able to mark `build_and_run_supervisor` and `validate_receipt`
   complete, set `receipt_decision = "COMMIT_GO"`, clear the receipt path, or
   export `RCX_SKIP_RECEIPT_CHECK=1` without a mechanically authorized recovery
   contract.

2. Fix `B2 - Governance Checks Treat Critical Control-Plane Tooling Changes As
   No-Class Compliant`. Extend tracker-sync and L4 execution-contract
   governance so critical control-plane tooling surfaces are classified instead
   of passing as no-class compliant when they avoid runtime file paths. The
   governed surface must include the dispatcher/commit/recovery executor
   surfaces, checks, hooks, observability tooling, and workflow surfaces called
   out by the audit.

3. Fix `B3 - Phase B Tracker Note Can Reach Pre-Commit Supervisor Without Final
   Same-Wave Override And Scope`. Mechanize Phase B so the pre-supervisor
   tracker note is rendered or verified after L4 indicator scope
   reconciliation, carries the authoritative same-wave founder override when
   the locked packet authorizes one, and fails closed before supervisor review
   if the final staged scope and top tracker note disagree.

4. Add focused regression coverage for the three blockers. The regression set
   must reproduce the audited direct bypass, no-class compliance, and Phase B
   tracker-note/L4 indicator ordering risk before the fix and prove the repaired
   behavior after the fix.

5. Update the `[FOUNDER-ORDERED-REDTEAM-TOOLING-BLOCKING-REMEDIATION]` tracker
   entry under `[NEXT-CODEX-POST-REDTEAM]` with implementation status and
   command evidence after the future implementation wave lands.

## Constraints: Not In Scope

- Do not implement runtime, substrate, Stage0, scheduler, seed-registration, or
  `/mu` structural remediation in this wave.
- Do not edit Claude-related files.
- Do not relist already landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work as unresolved.
- Do not convert this packet into a broad tooling audit. Use the preserved
  source finding evidence and current code truth for the scoped blocker paths.
- Do not edit `.scratch/phase_b_supervisor_package.json`; it is cited as
  evidence for the Phase B ordering risk, not as a durable control surface.
- Do not modify workflows beyond the minimum needed to classify or gate the
  audited control-plane surfaces.
- Do not widen into non-blocking tooling findings; those remain in the
  non-blocking remediation lane.

## Stop Conditions

- Stop if current source truth proves any listed blocking tooling finding has
  already been remediated; update the tracker instead of implementing stale
  work.
- Stop if a proposed fix requires runtime, tests-only, docs-only, or `/mu`
  structural changes outside the tooling/control-plane remediation category.
- Stop if the pipeline cannot represent the repair without a same-wave
  mechanical fix or a precise follow-up automation packet.
- Stop if the Phase B fix cannot be proven by a regression that reproduces the
  pre-supervisor tracker-note/L4 indicator ordering risk.
- Stop if any Claude-related file would need to be edited.
- Stop if the implementation would require edits outside the explicit
  file/directory scope above, except for narrowing the scope because current
  code truth proves a work item is already landed.

## Acceptance Criteria

- A direct commit-executor invocation can no longer synthesize supervisor and
  receipt success through the audited bypass path.
- Critical control-plane tooling changes cannot pass as no-class compliant
  solely because they avoid runtime file paths.
- Phase B queue-organization-style L4_ENABLER handoff with an authorized
  same-wave founder override passes
  `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id <wave>`
  after indicator scope reconciliation, without manual tracker-note edits.
- Phase B fails closed before supervisor review when the final staged scope,
  same-wave L4 indicator path, and top tracker note disagree.
- Focused command evidence demonstrates the bypass closure, governance
  classification behavior, and Phase B tracker-note ordering behavior.
- The wave does not relist already landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work as unresolved.
- The matching `TASKS.md` entry is updated with implementation and evidence
  status after the future implementation wave lands.

## Grounding / Authorization

- `TASKS.md:430` authorizes
  `[FOUNDER-ORDERED-REDTEAM-TOOLING-BLOCKING-REMEDIATION]` under
  `[NEXT-CODEX-POST-REDTEAM]` with Wave ID
  `founder-ordered-redteam-tooling-blocking-remediation-2026-05-06`, Class
  `L4_ENABLER`, Category `tooling/control-plane`, this packet path, and the
  blocking tooling/control-plane finding inventory.
- `TASKS.md:430` preserves the source queue authorization
  `FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05`.
- This governing packet supplies the wave-bound mechanical authorization token
  required for control-surface L4_ENABLER commit automation:
  `FOUNDER_OVERRIDE:founder-ordered-redteam-tooling-blocking-remediation-2026-05-06`.
- The source audit packet is
  `reports/deferred/blocking/founder_ordered_redteam_tooling_audit_2026-05-05_blocking.md`.
- The queue source is
  `founder-ordered-redteam-remediation-queue-organization-2026-05-05`; this
  packet is the governing packet for the later remediation wave and must be the
  source for same-wave override derivation during that wave.

## Source Findings

### B1 - Commit Executor Exposes A Direct Supervisor And Receipt Bypass

Classification: BLOCKING DEFECT

Surfaces: commit executor, pre-commit supervisor authority, receipt validation,
manual workaround residue.

Source evidence preserved from
`reports/deferred/blocking/founder_ordered_redteam_tooling_audit_2026-05-05_blocking.md`:

- Lines 48-51: `mu/tools/executors/commit_executor.py:7583` through
  `mu/tools/executors/commit_executor.py:7594` define "Modular bypass flags"
  and expose `--skip-supervisor` with help text stating it skips steps 6-7:
  no Codex meta-review and no receipt validation.
- Lines 52-55: `mu/tools/executors/commit_executor.py:7608` through
  `mu/tools/executors/commit_executor.py:7612` block `--standalone` and
  `--skip-supervisor` only when `RCX_EXECUTOR_DISPATCH_PID` is present, so the
  direct CLI path remains open.
- Lines 56-58: `mu/tools/executors/commit_executor.py:7657` through
  `mu/tools/executors/commit_executor.py:7662` pass
  `skip_supervisor=args.skip_supervisor` directly into `run_commit_pipeline`.
- Lines 59-63: `mu/tools/executors/commit_executor.py:7065` through
  `mu/tools/executors/commit_executor.py:7075` mark
  `build_and_run_supervisor` and `validate_receipt` as completed, set
  `receipt_decision = "COMMIT_GO"`, clear the supervisor receipt path, and set
  `RCX_SKIP_RECEIPT_CHECK=1` when `skip_supervisor` is true.
- Lines 64-67: `mu/tools/executors/commit_executor.py:7341` through
  `mu/tools/executors/commit_executor.py:7346` propagate the receipt-skip
  environment into the pre-commit hook when supervisor review is skipped.
- Lines 70-79 preserve direct help output showing the operator-facing
  `--skip-supervisor` flag and help text: `Skip steps 6-7 (no Codex
  meta-review, no receipt validation)`.

### B2 - Governance Checks Treat Critical Control-Plane Tooling Changes As No-Class Compliant

Classification: BLOCKING DEFECT

Surfaces: L4 execution contract, tracker sync gate, dispatcher/commit/recovery
tooling governance, G8 package truth.

Source evidence preserved from
`reports/deferred/blocking/founder_ordered_redteam_tooling_audit_2026-05-05_blocking.md`:

- Lines 102-107: `mu/tools/checks/enforce_tracker_sync.sh:81` builds
  `CORE_CHANGED` from `mu/` and `rcx_pi/selfhost/` but excludes `mu/tools/`;
  line 82 adds only `mu/tools/agents/` and omits `mu/tools/executors/`,
  `mu/tools/checks/`, `mu/tools/hooks/`, `mu/tools/observability/`, and
  `.github/workflows/`.
- Lines 111-115 preserve direct command output:
  `bash tools/checks/enforce_tracker_sync.sh --files mu/tools/executors/commit_executor.py`
  prints `Tracker sync OK: no core changes detected.` and exits `0`.
- Lines 117-120: `mu/tools/checks/enforce_l4_execution_contract.py:60`
  through `mu/tools/checks/enforce_l4_execution_contract.py:69` include only
  `mu/tools/compilers/` from `mu/tools`, not dispatcher, commit, recovery,
  hook, check, or observability surfaces.
- Lines 121-124: `mu/tools/checks/enforce_l4_execution_contract.py:1499`
  through `mu/tools/checks/enforce_l4_execution_contract.py:1558` fail closed
  only for unclassified runtime files; when no runtime files are present and no
  wave class is bound, the function returns success.
- Lines 128-135 preserve direct command output:
  `python3 tools/checks/enforce_l4_execution_contract.py --files mu/tools/executors/commit_executor.py`
  reports `Wave class: (none)`, `Runtime files: 0`,
  `L4 Execution Contract v2: no-class compliant`, and exits `0`.

### B3 - Phase B Tracker Note Can Reach Pre-Commit Supervisor Without Final Same-Wave Override And Scope

Classification: BLOCKING PIPELINE AUTOMATION FOLLOW-UP

Surfaces: Phase B pre-supervisor tracker-note builder, same-wave founder
override propagation, L4 indicator scope reconciliation, pre-commit supervisor
handoff package.

Same-wave failure evidence from
`founder-ordered-redteam-remediation-queue-organization-2026-05-05`:

- Direct reproduced command before the tracker-note repair:
  `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id founder-ordered-redteam-remediation-queue-organization-2026-05-05; printf 'exit=%s\n' $?`
  printed `Wave class: L4_ENABLER`, `Changed files: 10`, `Runtime files: 0`,
  then failed with `Non-structural adjacency cap violated: last 2 waves are
  L4_ENABLER and L4_ENABLER`, `Rolling structural quota violated: last 3
  waves have no L4_STRUCTURAL. Classes: ['L4_ENABLER', 'L4_ENABLER',
  'L4_ENABLER']`, and `exit=1`.
- Current `tools/checks/enforce_l4_execution_contract.py:1019` stores
  `founder_override` from tracker-note text; `tools/checks/enforce_l4_execution_contract.py:1181`
  through `tools/checks/enforce_l4_execution_contract.py:1186` allow the
  rolling-window bypass only from `notes[0].get("founder_override")`; and
  `tools/checks/enforce_l4_execution_contract.py:1267` through
  `tools/checks/enforce_l4_execution_contract.py:1270` allow the
  non-structural adjacency bypass only from `notes[0].get("founder_override")`.
- Current `mu/tools/executors/phase_b_executor.py:5979` through
  `mu/tools/executors/phase_b_executor.py:5995` build the pre-supervisor
  tracker note before the L4 indicator collection and packet-scope refresh
  path at `mu/tools/executors/phase_b_executor.py:6050` through
  `mu/tools/executors/phase_b_executor.py:6088`; current
  `mu/tools/executors/phase_b_executor.py:6071` through
  `mu/tools/executors/phase_b_executor.py:6072` can append the indicator path
  after the note already counted `changed_files`.
- Current `.scratch/phase_b_supervisor_package.json:6` through
  `.scratch/phase_b_supervisor_package.json:16` list 10 changed files for this
  wave after Phase B indicator reconciliation, including
  `reports/l4_wave_indicators/founder-ordered-redteam-remediation-queue-organization-2026-05-05.json`.
- Current `TASKS.md:256` now contains the manual repair: the same-wave
  `FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05`
  token and 10 wave-owned file count were added to the top tracker note before
  resuming the failed pre-commit supervisor point.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `founder-ordered-redteam-tooling-blocking-remediation-2026-05-06`
- Active packet: `reports/control_plane/founder_ordered_redteam_tooling_blocking_remediation_2026-05-06.md`
- Indicator artifact: `reports/l4_wave_indicators/founder-ordered-redteam-tooling-blocking-remediation-2026-05-06.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_l4_execution_contract_enforcement.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_tracker_sync_enforcement.py`
  - `mu/tools/checks/enforce_l4_execution_contract.py`
  - `mu/tools/checks/enforce_tracker_sync.sh`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/founder_ordered_redteam_tooling_blocking_remediation_2026-05-06.md`
  - `reports/deferred/non_blocking/founder-ordered-redteam-tooling-blocking-remediation-2026-05-06_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/founder-ordered-redteam-tooling-blocking-remediation-2026-05-06.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `founder-ordered-redteam-tooling-blocking-remediation-2026-05-06`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/founder-ordered-redteam-tooling-blocking-remediation-2026-05-06_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `founder-ordered-redteam-tooling-blocking-remediation-2026-05-06`
- Active packet: `reports/control_plane/founder_ordered_redteam_tooling_blocking_remediation_2026-05-06.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `818c7ac10b5f5282ff604323607d4be63e9bc5f8d0845ba3ea982dec9755fa1b`
- Indicator artifact: `reports/l4_wave_indicators/founder-ordered-redteam-tooling-blocking-remediation-2026-05-06.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_l4_execution_contract_enforcement.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_tracker_sync_enforcement.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/founder_ordered_redteam_tooling_blocking_remediation_2026-05-06.md. (2) Final pytest gate covered 4 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/founder-ordered-redteam-tooling-blocking-remediation-2026-05-06.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_l4_execution_contract_enforcement.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_tracker_sync_enforcement.py`
  - `mu/tools/checks/enforce_l4_execution_contract.py`
  - `mu/tools/checks/enforce_tracker_sync.sh`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/founder_ordered_redteam_tooling_blocking_remediation_2026-05-06.md`
  - `reports/deferred/non_blocking/founder-ordered-redteam-tooling-blocking-remediation-2026-05-06_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/founder-ordered-redteam-tooling-blocking-remediation-2026-05-06.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
