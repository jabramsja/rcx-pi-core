# N3-Step-Kernel-VM-Iteration-Marker-Truth-Ratchet-2026-05-19

Date: 2026-05-19
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-step-kernel-vm-iteration-marker-truth-ratchet-2026-05-19
Class: L4_STRUCTURAL
Commit-amendment repair class: L4_ENABLER for the staged same-wave
commit/push repair only; the complete `origin/dev...HEAD` wave remains
L4_STRUCTURAL because it includes the runtime marker-removal diff.
Target gate: G8
Phase-A-Lock: LOCKED
Purpose: Remove the stale `_step_kernel_with_vm` `@host_iteration` marker only if direct current source and gate evidence prove that S1-C moved projection execution into Stage0 VM and the remaining host loops are coverage bookkeeping, not semantic projection dispatch.

## Scope

This packet governs exactly one bounded marker-truth reduction:

- Targeted marker: `mu/host/python/rcx_pi/selfhost/step_mu.py:1035`, the
  `_step_kernel_with_vm` `@host_iteration` decorator.
- Current positive source evidence:
  - `mu/host/python/rcx_pi/selfhost/step_mu.py:1035` says the annotation was
    preserved for baseline compatibility after S1-C.
  - `mu/host/python/rcx_pi/selfhost/step_mu.py:1044-1050` says the kernel step
    executes all projections via Stage0 VM and preserves first-match ordering
    across the fixed seed-group sequence.
  - `mu/tests/l4_gates/test_stage0_vm_cutover.py:392-430` proves
    `_step_trusted` and `_apply_projection_trusted` do not fire on the
    `step_kernel_mu` cutover path.
  - `mu/tests/l4_gates/test_stage0_vm_cutover.py:451-545` proves coverage
    bookkeeping consumes VM-emitted attempt traces rather than host bundle order.

Allowed Phase B write set, after same-wave `TASKS.md` tracker authority exists:

- `TASKS.md`
- `reports/control_plane/n3-step-kernel-vm-iteration-marker-truth-ratchet-2026-05-19_2026-05-19.md`
- `reports/l4_wave_indicators/n3-step-kernel-vm-iteration-marker-truth-ratchet-2026-05-19.json`
- `mu/host/python/rcx_pi/selfhost/step_mu.py`
- `mu/tests/l4_gates/test_stage0_vm_cutover.py`
- `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
- `STATUS.md`
- `archive/status_debt_history.md`
- `mu/tools/audits/audit_semantic_purity.sh`
- `mu/tools/checks/host_semantics_baseline.json`
- `tools/checks/host_semantics_baseline.json`
- `mu/tools/executors/commit_executor.py`
- `mu/tests/tools/test_commit_executor_receipt.py`

No other files are in scope. Commit-executor/test writes are allowed only as the
same-wave mechanical repair for the observed post-commit pre-push anti-cheat
miss: Step 8c caught private attribute access but not the paired underscored
`rcx_pi` import checker before local commit creation.

## Work Items

1. Add detector-visible same-wave `TASKS.md` tracker authority for this wave ID,
   this packet path, and
   `FOUNDER_OVERRIDE:n3-step-kernel-vm-iteration-marker-truth-ratchet-2026-05-19`
   before any runtime, test, status, baseline, or audit-threshold edit.
2. Re-open the exact current source and test lines named in Scope. Do not rely
   on historical packet line numbers if code moved.
3. Classify `_step_kernel_with_vm` honestly:
   - removable-now only if the function no longer performs host projection
     dispatch and the remaining loops are coverage bookkeeping over VM traces;
   - irreducible if current code still uses host iteration for semantic
     projection selection; or
   - prerequisite-needed if proof cannot distinguish bookkeeping from semantic
     host dispatch.
4. If removable-now, remove only the `_step_kernel_with_vm` `@host_iteration`
   decorator and update focused tests to lock that this marker is absent while
   `step_kernel_mu`, Python `list_to_linked`, JS `step`, and JS `listToLinked`
   remain marked.
5. Update marker baselines, `STATUS.md`, `archive/status_debt_history.md`, and
   `audit_semantic_purity.sh` only after source marker removal and ratchet output
   prove the lower truth. Do not use baseline edits as proof.
6. Preserve bootstrap honesty: `step_kernel_mu` remains the irreducible kernel
   loop marker, Python `list_to_linked` remains on-kernel data-prep debt, JS
   `step` remains the first-match projection loop marker, and JS `listToLinked`
   remains the parity data-conversion marker.
7. Route validation, indicator collection, commit, receipt, push, and PR through
   the normal pipeline surfaces.
8. If post-commit pre-push anti-cheat rejects a wave-owned test for underscored
   `rcx_pi` imports, repair the test through public/file-source inspection and
   tighten commit Step 8c so the same checker fails before future local commits.

## Constraints

- Do not touch `mu/host/js/core/bootstrap_core.js:293`.
- Do not remove `step_kernel_mu`, Python `list_to_linked`, JS `step`, JS
  `listToLinked`, `_stage0_match`, or any JS/Python builtin marker.
- Do not add host exception tables, host-only semantic inference, Python-only
  behavior, JavaScript-only behavior, or smarter host interpretation.
- Do not claim full L4, full self-hosting, complete host-semantics removal, or
  closure of unrelated N3 surfaces.
- Do not update ratchet baselines, `STATUS.md`, or audit thresholds unless the
  source marker is removed in the same wave and focused proof remains green.
- Do not alter authority inventory baselines unless the authority ratchet itself
  requires a reviewed accepted split; no such split is expected for this wave.

## Stop Conditions

Stop with NO-GO or route the exact prerequisite if any of these conditions holds:

- `TASKS.md` lacks detector-visible same-wave tracker authority for this wave ID,
  packet path, and founder override before runtime or baseline edits.
- Current source evidence shows `_step_kernel_with_vm` still uses host iteration
  for semantic projection dispatch rather than fixed seed-group VM calls and
  coverage bookkeeping.
- Focused negative controls no longer prove that `_step_trusted` and
  `_apply_projection_trusted` are absent from the `step_kernel_mu` cutover path.
- Removing the marker trips L4 Rule A4.2 because the remaining loops are judged
  semantic instead of coverage-only; in that case, route a prerequisite to split
  coverage bookkeeping out of `_step_kernel_with_vm` before marker removal.
- Any required edit falls outside the scoped write set.
- Focused tests, `node mu/host/js/eval_step.js`, host-semantics ratchet,
  host-authority inventory ratchet, `audit_semantic_purity.sh`, docs
  consistency, indicator collection, or strict L4 structural enforcement fail.

## Acceptance Criteria

- Same-wave `TASKS.md` tracker authority exists before implementation edits.
- The packet is locked by Phase A and remains the governing packet for the wave.
- `_step_kernel_with_vm` no longer has an `@host_iteration` decorator only if
  current code/test proof establishes that semantic projection dispatch is via
  Stage0 VM.
- `step_kernel_mu`, Python `list_to_linked`, JS `step`, and JS `listToLinked`
  remain marked as current bootstrap/semantic host-iteration debt.
- Host-semantics ratchet shows Python `host_iteration` decreases by 1 and no
  category increases. The expected final marker truth is 7 total tracked markers:
  Python 3 and JavaScript 4.
- `audit_semantic_purity.sh` and `STATUS.md` semantic ceiling lower from 10 to 9
  only after the source marker is removed.
- Wave-owned tests have no private attribute access and no underscored
  `rcx_pi` imports, and commit Step 8c runs both corresponding AST checkers
  before local commit creation.
- Required focused proof passes:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q \
  mu/tests/l4_gates/test_stage0_vm_cutover.py::TestCutoverIntegration \
  mu/tests/l4_gates/test_stage0_vm_cutover.py::TestVmCutoverCoverageFromAttemptTrace \
  mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py \
  mu/tests/structural/test_status_md_grounding.py \
  --tb=short
node mu/host/js/eval_step.js
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
python3 tools/checks/check_host_authority_inventory_ratchet.py
bash mu/tools/audits/audit_semantic_purity.sh
./tools/checks/check_docs_consistency.sh
python3 tools/checks/linters/check_private_attr_access.py
python3 tools/checks/linters/check_underscore_imports.py
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestCommitExecutorPytestGate::test_run_commit_pipeline_blocks_private_attr_gate_before_git_commit mu/tests/tools/test_commit_executor_receipt.py::TestCommitExecutorPytestGate::test_run_commit_pipeline_blocks_underscore_import_gate_before_git_commit --tb=short -p no:cacheprovider
python3 tools/metrics/collect_l4_wave_indicators.py --wave-id n3-step-kernel-vm-iteration-marker-truth-ratchet-2026-05-19 --output reports/l4_wave_indicators/n3-step-kernel-vm-iteration-marker-truth-ratchet-2026-05-19.json
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-step-kernel-vm-iteration-marker-truth-ratchet-2026-05-19 --wave-class L4_ENABLER
python3 tools/checks/enforce_l4_execution_contract.py --range origin/dev...HEAD --wave-id n3-step-kernel-vm-iteration-marker-truth-ratchet-2026-05-19 --wave-class L4_STRUCTURAL
```

## Grounding / Authorization

- `STATUS.md:84-96` records the current tracked-marker ledger and says tracked
  markers monotonically decrease through `check_host_semantics_ratchet.py`.
- `archive/status_debt_history.md:17-19` says the post-S1-C kernel path goes
  through `_step_kernel_with_vm` and Stage0 VM for all 33 projections.
- `archive/status_debt_history.md:25-27` currently lists `_step_kernel_with_vm`
  as a tracked host-iteration marker alongside `step_kernel_mu` and
  `list_to_linked`.
- `mu/tools/checks/check_host_semantics_ratchet.py:46-49` defines the marker
  scan as direct `@host_*` source markers, and `:165-204` accepts decreases
  while failing increases.
- `mu/tools/executors/tracker_sync_note.py:51-219` provides the structured
  tracker note builder used for same-wave tracker authority.
- `mu/tools/executors/executor_common.py:1125-1172` provides the routing-record
  builder used for the dispatcher handoff.
- Same-wave authorization: FOUNDER_OVERRIDE:n3-step-kernel-vm-iteration-marker-truth-ratchet-2026-05-19

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-step-kernel-vm-iteration-marker-truth-ratchet-2026-05-19`
- Active packet: `reports/control_plane/n3-step-kernel-vm-iteration-marker-truth-ratchet-2026-05-19_2026-05-19.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-step-kernel-vm-iteration-marker-truth-ratchet-2026-05-19.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `STATUS.md`
  - `TASKS.md`
  - `archive/status_debt_history.md`
  - `mu/host/python/rcx_pi/selfhost/step_mu.py`
  - `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
  - `mu/tools/audits/audit_semantic_purity.sh`
  - `mu/tools/checks/host_semantics_baseline.json`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `reports/control_plane/n3-step-kernel-vm-iteration-marker-truth-ratchet-2026-05-19_2026-05-19.md`
  - `reports/deferred/non_blocking/n3-step-kernel-vm-iteration-marker-truth-ratchet-2026-05-19_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-step-kernel-vm-iteration-marker-truth-ratchet-2026-05-19.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
