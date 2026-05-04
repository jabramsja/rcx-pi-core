# Merge-Pr-Sweep-Count-And-Packet-Truth-2026-05-03

Date: 2026-05-03
Status: Phase B (implementation-complete, bridge-converged)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: merge-pr-sweep-count-and-packet-truth-2026-05-03
Phase-A-Lock: LOCKED
Class: L4_ENABLER
target_gate_id: G8
Governing packet: reports/control_plane/merge-pr-sweep-count-and-packet-truth-2026-05-03_2026-05-03.md
Authorization: standing pipeline-bug-fix authorization for control-surface merge_pr sweep-count support and packet-truth remediation, mechanically bound to this wave and not a structural task closure.
FOUNDER_OVERRIDE:merge-pr-sweep-count-and-packet-truth-2026-05-03

Purpose: Lock a bounded Phase A control-surface packet for the merge_pr sweep-count and packet-truth follow-up discovered during the founder-requested 15-PR merge sweep. This packet is an L4 enabler for pipeline correctness only; it does not claim to complete the structural/post-control-surface lane of `[NEXT-CODEX-POST-REDTEAM]`.

## Scope

- Authorized files/directories for this packet and its implementation phase are explicit and closed.
- `reports/control_plane/merge-pr-sweep-count-and-packet-truth-2026-05-03_2026-05-03.md`: governing Phase A packet and same-wave closeout evidence for this control-surface enabler.
- `mu/tools/hooks/merge_pr.sh`: sweep-count option behavior, including explicit positive-integer count parsing, preserved default sweep behavior, and any in-script usage/help text needed for the option.
- `mu/tests/tools/`: existing focused tool tests only for `merge_pr` sweep-count/default behavior; no new test files are authorized by this packet.
- `reports/control_plane/tasks-deferred-code-truth-cleanup-2026-05-03_2026-05-03.md`: PR #860 packet-truth reconciliation against the cited 20-versus-21 file-count evidence.
- `reports/control_plane/deferred-report-truth-doc-accuracy-closeout-2026-05-03_2026-05-03.md`: conditional PR #860 remediation-context truth update only if needed by the cited omitted-file evidence.
- `TASKS.md`: conditional minimal tracker note only if the repo gate requires one for this same-wave control-surface enabler.
- `reports/control_plane/README.md`: conditional minimal report tracker note only if the repo gate requires one for this same-wave control-surface enabler.
- `mu/tools/executors/commit_executor.py`: conditional inspection/update only if PR #860 packet-truth reconciliation produces narrow file:line evidence of a recurrence gap in packet-truth refresh behavior.
- `mu/tests/tools/test_commit_executor_receipt.py`: conditional focused receipt test update only if the `commit_executor` recurrence surface above is activated.
- No other files or directories are in scope.

- `reports/deferred/non_blocking/merge-pr-sweep-count-and-packet-truth-2026-05-03_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Lock this Phase A packet as an `L4_ENABLER` under same-wave authorization, with `FOUNDER_OVERRIDE:merge-pr-sweep-count-and-packet-truth-2026-05-03`, a `target_gate_id`, and this governing packet path so commit automation can derive the override mechanically.
2. Resolve the task-lane mismatch explicitly: `[NEXT-CODEX-POST-REDTEAM]` remains OPEN for structural/post-control-surface work, while this packet authorizes only a bounded control-surface pipeline-bug-fix support slice.
3. Validate or complete `merge_pr` sweep-count support only against current code truth during implementation. The requested behavior is positive-integer `--sweep-count` support for sweep modes and preserved default sweep behavior of 10; if code truth proves this is already implemented, record it as landed instead of re-listing it as unresolved.
4. Reconcile PR #860 packet truth against the cited sweep finding: the supervisor evidence says the final merged PR #860 diff has 21 files while `reports/control_plane/tasks-deferred-code-truth-cleanup-2026-05-03_2026-05-03.md:218` records 20 wave-owned files and lines 221-241 omit `reports/control_plane/deferred-report-truth-doc-accuracy-closeout-2026-05-03_2026-05-03.md`.
5. Close or preserve the extracted P2 sweep finding with direct code/doc evidence. If the current code or report state proves any listed item is already landed, remove it from pending acceptance rather than treating stale packet wording as unresolved work.
6. Inspect `mu/tools/executors/commit_executor.py` and `mu/tests/tools/test_commit_executor_receipt.py` only if the packet-truth reconciliation yields narrow file:line evidence of a recurrence gap. If the issue requires broader executor architecture, stop and split into a separate bounded packet.

## Constraints

- Do not touch runtime, substrate, seed, VM, scheduler, parity, or structural engine-state work.
- Do not use this packet to claim closure of `[NEXT-CODEX-POST-REDTEAM]`; TASKS.md marks that lane as structural/post-control-surface with remaining work requiring separate bounded packets.
- Do not broaden from the PR #860 packet-truth issue into unrelated report cleanup.
- Do not inspect or modify unrelated dirty files, unrelated executor/test changes, or unrelated reports.
- Do not create new files for this packet.
- Do not expand authorized write surfaces beyond the files/directories listed in Scope; any repo-gate tracker note is limited to `TASKS.md` or `reports/control_plane/README.md`.
- Do not re-implement work that current code truth proves already landed; update the packet or closeout evidence instead.

## Stop conditions

- Stop if the work requires runtime, substrate, seed, VM, scheduler, parity, or structural reduction changes.
- Stop if control-surface work cannot be kept within the authorized write surfaces above.
- Stop if the only available grounding is stale packet prose rather than current code/doc evidence.
- Stop if `TASKS.md` lane binding would make this packet appear to close the structural `[NEXT-CODEX-POST-REDTEAM]` work.
- Stop and split if `commit_executor` recurrence repair needs broader design or more files than the narrow executor/test pair named in Scope.
- Stop before commit if L4 automation cannot mechanically derive `Class: L4_ENABLER`, `target_gate_id`, the governing packet path, and `FOUNDER_OVERRIDE:merge-pr-sweep-count-and-packet-truth-2026-05-03` from this packet.

## Acceptance criteria

- The packet contains standalone Scope, Work items, Constraints, Stop conditions, Acceptance criteria, Grounding, and Authorization sections, with no duplicated supervisor-request echo.
- L4 authorization is mechanically derivable from the packet metadata: `Class: L4_ENABLER`, `target_gate_id`, governing packet path, explicit standing pipeline-bug-fix authorization, and `FOUNDER_OVERRIDE:merge-pr-sweep-count-and-packet-truth-2026-05-03`.
- The task-lane mismatch is resolved in writing: this is a control-surface enabler under an open structural task id, not substantive structural closure.
- `--sweep-count` behavior is either validated as already landed or completed with focused evidence; accepted behavior is positive-integer count support for sweep modes and preserved default sweep behavior of 10.
- PR #860 packet truth is reconciled to the committed file scope, or the remediation-scope exception is explicitly recorded with file:line evidence.
- The extracted P2 sweep finding is closed or preserved with direct code/doc evidence.
- Validation for the implementation phase includes `bash -n mu/tools/hooks/merge_pr.sh`, focused pytest limited to touched tests under `mu/tests/tools/`, docs consistency only if `TASKS.md`, `reports/control_plane/README.md`, or scoped report packets are touched, and `python3 tools/checks/enforce_l4_execution_contract.py --staged`.

## Grounding

- `TASKS.md:278-284` marks `[NEXT-CODEX-POST-REDTEAM]` OPEN by code while warning that stale packet headers or old "in progress" prose are historical unless the code-truth split marks the item open.
- `TASKS.md:393-398` marks `[NEXT-CODEX-POST-REDTEAM]` UNPARKED and founder-authorized, but identifies the lane as structural/post-control-surface; the current phase remains OPEN and remaining structural reduction requires separate bounded packets.
- The governing packet is this file: `reports/control_plane/merge-pr-sweep-count-and-packet-truth-2026-05-03_2026-05-03.md`.
- Supervisor sweep evidence reproduced before this rewrite: `bash mu/tools/hooks/merge_pr.sh 860 --sweep-only --sweep-count 15` swept merged PRs #860 through #846, resolved bot thread `PRRT_kwDOQvy8bs5_OcQg` on PR #860, and wrote one extracted P2 finding to `.agent_bus/meta/sweep_findings.json`.
- Cited packet-truth evidence: `reports/control_plane/tasks-deferred-code-truth-cleanup-2026-05-03_2026-05-03.md:218` records 20 wave-owned files, while lines 221-241 list 20 files and omit `reports/control_plane/deferred-report-truth-doc-accuracy-closeout-2026-05-03_2026-05-03.md`; the supervisor evidence says the final merged PR #860 diff has 21 files.
- Cited tool evidence: pre-patch `mu/tools/hooks/merge_pr.sh` hard-coded `SWEEP_COUNT=10` and documented only `--sweep` / `--sweep-only` for the default recent PR count; an operator-local patch may already add `MERGE_PR_SWEEP_COUNT` and `--sweep-count`, so implementation must verify current code truth before listing that item as pending.

## Authorization

- Authorization source: `TASKS.md:393` marks `[NEXT-CODEX-POST-REDTEAM]` founder-authorized; `TASKS.md:396-398` keeps the current structural lane open and requires future bounded packets.
- Lane resolution: this packet is a same-wave control-surface `L4_ENABLER` for pipeline-bug-fix and packet-truth support. It is not a structural reduction packet and must not close `[NEXT-CODEX-POST-REDTEAM]`.
- Authorization: standing pipeline-bug-fix authorization for control-surface merge_pr sweep-count support and PR #860 packet-truth remediation.
- FOUNDER_OVERRIDE:merge-pr-sweep-count-and-packet-truth-2026-05-03
- target_gate_id: G8
- Governing packet: reports/control_plane/merge-pr-sweep-count-and-packet-truth-2026-05-03_2026-05-03.md

## Phase B Implementation Evidence

Implementation status: complete inside the authorized control-surface/report
scope. No runtime, substrate, seed, VM, scheduler, parity, or structural
engine-state files were inspected or changed.

Changed implementation/test/report surfaces:

- `mu/tools/hooks/merge_pr.sh`
- `mu/tests/tools/test_executor_dispatch.py`
- `reports/control_plane/tasks-deferred-code-truth-cleanup-2026-05-03_2026-05-03.md`
- `reports/control_plane/merge-pr-sweep-count-and-packet-truth-2026-05-03_2026-05-03.md`

Direct code truth for `merge_pr` sweep-count support:

- `mu/tools/hooks/merge_pr.sh:31` keeps the preserved default as
  `SWEEP_COUNT="${MERGE_PR_SWEEP_COUNT:-10}"`.
- `mu/tools/hooks/merge_pr.sh:245-282` parses `--sweep`, `--sweep-only`,
  `--sweep-count N`, and `--sweep-count=N` without changing the target-only
  merge path.
- `mu/tools/hooks/merge_pr.sh:284-294` rejects empty, non-numeric, and
  non-positive sweep counts.
- `mu/tools/hooks/merge_pr.sh:299-300` and `mu/tools/hooks/merge_pr.sh:350-354`
  pass the selected count to `gh pr list --limit` in both sweep-only and
  post-merge sweep modes.
- `mu/tools/hooks/merge_pr.sh:5-14` documents the default 10 behavior and the
  explicit `--sweep-count` example.

Focused test evidence:

- `mu/tests/tools/test_executor_dispatch.py:63-155` copies `merge_pr.sh` into a
  temporary repo, installs a fake `gh`, and verifies default count 10,
  `--sweep-count N`, `--sweep-count=N`, `MERGE_PR_SWEEP_COUNT`, and rejection
  of invalid counts without touching the real `.agent_bus` sweep output.

PR #860 packet-truth reconciliation:

- Direct GitHub connector evidence for PR #860 returned 21 changed filenames and
  included `reports/control_plane/deferred-report-truth-doc-accuracy-closeout-2026-05-03_2026-05-03.md`.
- `reports/control_plane/tasks-deferred-code-truth-cleanup-2026-05-03_2026-05-03.md:178`
  and `:225` now include the omitted control-plane packet in the current staged
  file lists.
- `reports/control_plane/tasks-deferred-code-truth-cleanup-2026-05-03_2026-05-03.md:219`
  now records 21 wave-owned files and names the included omitted packet.

Extracted P2 sweep finding disposition:

- Closed as `DOC_ACCURACY` for this packet: the stale 20-file count/list is now
  reconciled to reproduced PR #860 diff truth with direct file-list evidence.
- No `commit_executor` recurrence surface was activated. The reproduced defect
  was stale packet text in the PR #860 control-plane packet, not narrow
  executor file:line evidence; the conditional
  `mu/tools/executors/commit_executor.py` and
  `mu/tests/tools/test_commit_executor_receipt.py` scope was therefore left
  untouched.
- `reports/control_plane/deferred-report-truth-doc-accuracy-closeout-2026-05-03_2026-05-03.md`,
  `TASKS.md`, and `reports/control_plane/README.md` did not require changes for
  this same-wave reconciliation.

Validation results:

- `bash -n mu/tools/hooks/merge_pr.sh` -> passed with no output.
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_executor_dispatch.py::TestMergePrSweepCount -q`
  -> passed, `7 passed in 1.55s`.
- `./tools/checks/check_docs_consistency.sh` -> passed. Output summary:
  `All checks passed. Docs are consistent.` The command also printed the
  standing STATUS freshness warning for `STATUS.md` last updated on
  2026-04-08.
- `python3 tools/checks/enforce_l4_execution_contract.py --staged` -> passed
  after staging the four scoped files. Output: `Wave class: (none)`,
  `Changed files: 4`, `Runtime files: 0`,
  `L4 Execution Contract v2: no-class compliant`.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `merge-pr-sweep-count-and-packet-truth-2026-05-03`
- Active packet: `reports/control_plane/merge-pr-sweep-count-and-packet-truth-2026-05-03_2026-05-03.md`
- Indicator artifact: `reports/l4_wave_indicators/merge-pr-sweep-count-and-packet-truth-2026-05-03.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/hooks/merge_pr.sh`
  - `reports/control_plane/merge-pr-sweep-count-and-packet-truth-2026-05-03_2026-05-03.md`
  - `reports/control_plane/tasks-deferred-code-truth-cleanup-2026-05-03_2026-05-03.md`
  - `reports/deferred/non_blocking/merge-pr-sweep-count-and-packet-truth-2026-05-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/merge-pr-sweep-count-and-packet-truth-2026-05-03.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `merge-pr-sweep-count-and-packet-truth-2026-05-03`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/merge-pr-sweep-count-and-packet-truth-2026-05-03_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `merge-pr-sweep-count-and-packet-truth-2026-05-03`
- Active packet: `reports/control_plane/merge-pr-sweep-count-and-packet-truth-2026-05-03_2026-05-03.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `19c27d18e471a63ad4f3b53625da7de8608278faeaa2640f5d725f6a0c11def0`
- Indicator artifact: `reports/l4_wave_indicators/merge-pr-sweep-count-and-packet-truth-2026-05-03.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/merge-pr-sweep-count-and-packet-truth-2026-05-03_2026-05-03.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor package is staged at .scratch/phase_b_supervisor_package.json; commit handoff receipt remains pending the supervisor decision..
- Evidence handles:
  - `bash_n`: `bash -n mu/tools/hooks/merge_pr.sh`
  - `docs`: `./tools/checks/check_docs_consistency.sh`
  - `indicator`: `reports/l4_wave_indicators/merge-pr-sweep-count-and-packet-truth-2026-05-03.json`
  - `l4`: `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id merge-pr-sweep-count-and-packet-truth-2026-05-03`
  - `pytest`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py::TestMergePrSweepCount -q`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/hooks/merge_pr.sh`
  - `reports/control_plane/merge-pr-sweep-count-and-packet-truth-2026-05-03_2026-05-03.md`
  - `reports/control_plane/tasks-deferred-code-truth-cleanup-2026-05-03_2026-05-03.md`
  - `reports/deferred/non_blocking/merge-pr-sweep-count-and-packet-truth-2026-05-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/merge-pr-sweep-count-and-packet-truth-2026-05-03.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
