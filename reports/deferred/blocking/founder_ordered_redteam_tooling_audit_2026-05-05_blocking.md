# Founder Ordered Redteam Tooling Audit - Blocking Findings

Date: 2026-05-06
Status: CLASSIFIED - BLOCKING
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-tooling-audit-2026-05-05
Class: L4_ENABLER
Target gate: G8
Governing packet: `reports/control_plane/founder_ordered_redteam_tooling_audit_2026-05-05.md`
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-tooling-audit-2026-05-05

This packet records blocking tooling-audit findings only. The audit wave did
not implement remediation.

## Scope Executed

- Explicit tracked target inventory command:
  `git ls-files tools scripts mu/tools dev.sh doctor.sh pyproject.toml .github/CODEOWNERS .github/pull_request_template.md .github/workflows/agent-review.yml .github/workflows/audit_all.yml .github/workflows/ci.yml .github/workflows/fixture_gates.yml .github/workflows/green_gate.yml .github/workflows/pr_verification_reminder.yml .github/workflows/slow_tests.yml .github/workflows/weekly_deep_fuzz.yml`
- Inventory result: 158 tracked entries: 143 tracked `mu/tools` entries,
  `dev.sh`, `doctor.sh`, the tracked `tools` symlink, the tracked `scripts`
  symlink, `pyproject.toml`, 2 listed `.github` files, and 8 listed workflows.
- `tools` is a tracked symlink to `mu/tools`, so it was treated as the same byte
  surface as explicit `mu/tools`, not as a separate implementation.
- `scripts` is a tracked symlink to `mu/scripts`; the symlink target has 23
  tracked entries reachable through the explicit `scripts/` path and was
  inspected as the scripts surface without counting the symlink as a separate
  implementation.
- Root command surfaces were included: `dev.sh:34` through `dev.sh:42`
  dispatch the fast/full audit entrypoints, and `doctor.sh:24` through
  `doctor.sh:103` verify developer environment dependencies and CLI presence.
- Scoped search for already-landed engine-state/scheduler residue produced no
  matches for `rcx_engine_state`, `rcx_engine_scheduler`,
  `post-redteam-engine-state`, `scheduler-parity`, `engine-state`, or
  `scheduler` in the explicit target set.

Already landed engine-state/scheduler seed, fixture, structural-test,
scheduler-parity, and seed-registration work was not relisted as unresolved.

## B1 - Commit Executor Exposes A Direct Supervisor And Receipt Bypass

Classification: BLOCKING DEFECT

Surfaces: commit executor, pre-commit supervisor authority, receipt validation,
manual workaround residue.

Evidence:

- `mu/tools/executors/commit_executor.py:7583` through
  `mu/tools/executors/commit_executor.py:7594` define "Modular bypass flags"
  and expose `--skip-supervisor` with help text stating it skips steps 6-7:
  no Codex meta-review and no receipt validation.
- `mu/tools/executors/commit_executor.py:7608` through
  `mu/tools/executors/commit_executor.py:7612` block `--standalone` and
  `--skip-supervisor` only when `RCX_EXECUTOR_DISPATCH_PID` is present, so the
  direct CLI path remains open.
- `mu/tools/executors/commit_executor.py:7657` through
  `mu/tools/executors/commit_executor.py:7662` pass
  `skip_supervisor=args.skip_supervisor` directly into `run_commit_pipeline`.
- `mu/tools/executors/commit_executor.py:7065` through
  `mu/tools/executors/commit_executor.py:7075` mark
  `build_and_run_supervisor` and `validate_receipt` as completed, set
  `receipt_decision = "COMMIT_GO"`, clear the supervisor receipt path, and set
  `RCX_SKIP_RECEIPT_CHECK=1` when `skip_supervisor` is true.
- `mu/tools/executors/commit_executor.py:7341` through
  `mu/tools/executors/commit_executor.py:7346` explicitly propagate the
  receipt-skip environment into the pre-commit hook when supervisor review is
  skipped.
- Direct help output proves the bypass flag is operator-facing:

```text
$ python3 mu/tools/executors/commit_executor.py --help | sed -n '1,80p'
usage: commit_executor.py [-h] [--handoff HANDOFF]
                          [--routing-record ROUTING_RECORD] [-v] [--json]
                          [--standalone] [--skip-supervisor]
                          [--task-id TASK_ID] [--bus-dir BUS_DIR]
...
  --skip-supervisor     Skip steps 6-7 (no Codex meta-review, no receipt
                        validation)
```

Why this blocks:

- The commit path's trusted authority is supposed to be the pre-commit
  supervisor receipt for the staged state. A direct CLI invocation can suppress
  that authority and synthesize `COMMIT_GO`.
- The dispatcher guard is useful but incomplete: it prevents the bypass only
  through dispatcher-owned invocations, while the exposed direct commit
  executor remains a manual workaround path.
- This is not a request to remove standalone recovery or implement a fix in the
  audit wave. It is a blocking control-plane defect to route for tooling
  remediation after classification ordering is complete.

## B2 - Governance Checks Treat Critical Control-Plane Tooling Changes As No-Class Compliant

Classification: BLOCKING DEFECT

Surfaces: L4 execution contract, tracker sync gate, dispatcher/commit/recovery
tooling governance, G8 package truth.

Evidence:

- `mu/tools/checks/enforce_tracker_sync.sh:81` builds `CORE_CHANGED` from
  `mu/` and `rcx_pi/selfhost/` but explicitly excludes `mu/tools/`.
- `mu/tools/checks/enforce_tracker_sync.sh:82` adds only
  `mu/tools/agents/` as control-plane tooling; it does not include
  `mu/tools/executors/`, `mu/tools/checks/`, `mu/tools/hooks/`,
  `mu/tools/observability/`, or `.github/workflows/`.
- Direct command evidence shows a commit-executor change is accepted as
  "no core changes" with no tracker requirement:

```text
$ bash tools/checks/enforce_tracker_sync.sh --files mu/tools/executors/commit_executor.py; printf 'exit=%s\n' $?
Tracker sync OK: no core changes detected.
exit=0
```

- `mu/tools/checks/enforce_l4_execution_contract.py:60` through
  `mu/tools/checks/enforce_l4_execution_contract.py:69` define runtime
  directories and include only `mu/tools/compilers/` from `mu/tools`, not the
  dispatcher, commit, recovery, hook, check, or observability surfaces.
- `mu/tools/checks/enforce_l4_execution_contract.py:1499` through
  `mu/tools/checks/enforce_l4_execution_contract.py:1558` fail closed only for
  unclassified runtime files; when no runtime files are present and no wave
  class is bound, the function returns success.
- Direct command evidence shows the same commit-executor surface passes the L4
  contract as no-class compliant:

```text
$ python3 tools/checks/enforce_l4_execution_contract.py --files mu/tools/executors/commit_executor.py; printf 'exit=%s\n' $?
Wave class: (none)
Changed files: 1
Runtime files: 0
✅ L4 Execution Contract v2: no-class compliant
exit=0
```

Why this blocks:

- Dispatcher, recovery, commit, pre-commit, check, and observability tooling are
  the control plane that enforces Phase A/B and commit authority. They can
  change the effective governance path without touching runtime files.
- The two local governance surfaces allow those critical tooling changes to
  proceed without a packet, tracker note, wave class, evidence command, or
  founder override when no other changed file happens to trigger the contract.
- This undermines G8/L4_ENABLER package truth for the exact tooling surfaces
  this audit was ordered to red-team.

Remediation is not authorized in this audit wave. Follow-up remediation must be
ordered by the founder remediation rule after all four audit waves classify
findings, with tooling blockers before tooling non-blockers and any `/mu`
structural remediation ordered last with a hard stop before implementation.
