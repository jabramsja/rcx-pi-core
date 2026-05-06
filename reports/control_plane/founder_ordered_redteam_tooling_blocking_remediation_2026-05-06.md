# Founder Ordered Redteam Tooling Blocking Remediation

Date: 2026-05-06
Status: QUEUED - BLOCKING REMEDIATION PACKET
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-tooling-blocking-remediation-2026-05-06
Class: L4_ENABLER
Category: tooling/control-plane
Severity: BLOCKING
Source audit packet: `reports/deferred/blocking/founder_ordered_redteam_tooling_audit_2026-05-05_blocking.md`
Queue order: non-`/mu` blocking remediation, after tests blocking remediation and before non-blocking remediation.
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05

This packet queues the blocking tooling/control-plane follow-ups from the
founder ordered redteam audit output plus the same-wave pipeline repair
follow-up discovered during this queue-organization wave. It does not
implement remediation.

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

## Remediation Scope For Future Wave

- Close the direct commit-executor supervisor/receipt bypass or constrain it to
  an explicitly governed recovery path with fail-closed receipt semantics.
- Extend tracker-sync and L4 execution-contract governance to the critical
  control-plane tooling surfaces identified by the audit.
- Mechanize Phase B so its pre-supervisor tracker note is re-rendered or
  verified after same-wave L4 indicator scope reconciliation, carries the
  authoritative same-wave founder override when the locked packet authorizes
  one, and fails closed before supervisor review if the final staged scope and
  top tracker note disagree.
- Preserve dispatcher, recovery, commit, pre-commit, check, hook, and
  observability authority without implementing runtime or `/mu` structural
  remediation.

## Stop Conditions

- Stop if current source truth proves either blocking tooling finding has
  already been remediated; update the tracker instead of implementing stale
  work.
- Stop if a proposed fix requires runtime, tests-only, docs-only, or `/mu`
  structural changes outside the control-plane tooling remediation category.
- Stop if the pipeline cannot represent the repair without a same-wave
  mechanical fix or a precise follow-up automation packet.
- Stop if the Phase B fix cannot be proven by a regression that reproduces the
  pre-supervisor tracker-note/L4 indicator ordering risk.
- Stop if any Claude-related file would need to be edited.

## Acceptance Criteria

- A direct commit-executor invocation can no longer synthesize supervisor and
  receipt success through the audited bypass path.
- Critical control-plane tooling changes cannot pass as no-class compliant
  solely because they avoid runtime file paths.
- Phase B queue-organization-style L4_ENABLER handoff with an authorized
  same-wave founder override passes
  `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id <wave>`
  after indicator scope reconciliation, without manual tracker-note edits.
- Focused command evidence demonstrates the bypass closure and governance
  classification behavior.
- The wave does not relist already landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work as unresolved.
- The matching `TASKS.md` entry is updated with implementation and evidence
  status.

## Tracker Update Note

Add or update the `[FOUNDER-ORDERED-REDTEAM-TOOLING-BLOCKING-REMEDIATION]`
entry under `[NEXT-CODEX-POST-REDTEAM]` with this packet path, this wave ID,
category `tooling/control-plane`, severity `blocking`, source audit packet
path, and the acceptance evidence once implemented.
