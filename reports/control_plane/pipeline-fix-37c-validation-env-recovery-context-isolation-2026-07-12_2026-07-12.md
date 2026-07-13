# Pipeline Fix 37C Validation Environment And Recovery Context Isolation

Date: 2026-07-12
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PIPELINE-FIX-37C]
Wave ID: pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12
Phase-A-Lock: LOCKED
Purpose: Replace failed FIX37B with one integrated control-plane root fix. Preserve its local source commit b02aadbb without publishing it directly; make commit-owned validation children hermetic against live bus, role, and pager routing overrides; and prevent recovery bootstrap classification from treating incidental bridge_config path text in broad test output as an adapter bootstrap fault.

## Scope

Allowed write scope:
- TASKS.md
- mu/tools/executors/commit_executor.py
- mu/tools/executors/recovery_gate.py
- mu/tests/tools/test_commit_executor_receipt.py
- mu/tests/tools/test_recovery_gate.py
- reports/control_plane/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12_2026-07-12.md
- reports/deferred/non_blocking/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12_bridge_nonblockers.md
- reports/l4_wave_indicators/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12.json

Files and surfaces in scope:

- TASKS.md (MODIFY) -- builder-owned tracker authority and failed FIX37B preservation truth only.
- mu/tools/executors/commit_executor.py (MODIFY) -- preserve b02aadbb validation-child bus isolation and remove all invocation-owned role/pager overrides from validation children only.
- mu/tools/executors/recovery_gate.py (MODIFY) -- prevent incidental stdout mentions of bridge_config support state from being classified as adapter bootstrap faults.
- mu/tests/tools/test_commit_executor_receipt.py (MODIFY) -- preserve FIX37B tests and add live pager/role override isolation regressions through production validation call sites.
- mu/tests/tools/test_recovery_gate.py (MODIFY) -- prove real adapter errors remain blocked while incidental broad-test stdout and support-state text do not block bounded delegation.
- reports/control_plane/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12_2026-07-12.md (GENERATED) -- governing packet.
- reports/deferred/non_blocking/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12_bridge_nonblockers.md (CREATE ONLY IF NEEDED) -- durable lower-severity dispositions.
- reports/l4_wave_indicators/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12.json (GENERATED) -- same-wave indicator.
- TASKS.md -- tracker-sync authority. The 2026-07-12 tracker sync note for wave `pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Read b02aadbb as immutable source evidence and reproduce its useful commit_executor.py and receipt-test delta without cherry-picking, publishing, or reusing the failed branch, bus, packet, receipt, or wave identity.
2. Reproduce tests/tools/test_agent_bus_namespacing.py::test_pager_persists_event_delivery_state_and_lock_in_namespaced_bus passing with a clean environment and failing when RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE=codex leaks into the child.
3. Build validation child environments from the parent without RCX_SKIP_ keys, RCX_AGENT_BUS_DIR, the repo-root role-override guard, any role override named by canonical role configuration, or RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE. Apply caller overrides before final protected-key removal so callers cannot re-inject them. Preserve unrelated environment byte-for-byte and never mutate os.environ.
4. Exercise targeted pytest, bot-remediation pre-push, and ordinary Step 11 call sites. Prove live commit, hook, adapter, pager, supervisor, push, merge, and recovery children retain existing invocation authority.
5. Reproduce _hybrid_bootstrap_fault_detected rejecting a bounded delegate solely because run_pre_push_script stdout contains incidental .agent_bus/bridge_config.json text. Narrow classification to actual adapter/bootstrap error evidence while preserving fail-closed detection for real missing/config/import/selection errors.
6. Add negative controls for actual bridge adapter failures and symlink/type/source drift, plus a regression matching the failed FIX37B recovery context. Require ordinary pre-push-fast under the namespaced live lane before publication.

## Constraints

- Builders only; no manual tracked edits, commits, pushes, PRs, merges, closes, conflict resolution, or hook bypasses.
- Do not cherry-pick or publish b02aadbb; it is immutable source evidence for a fresh-identity reconstruction.
- Do not weaken, skip, xfail, deselect, wait-around, or serialize the failing pager test as a substitute for environment isolation.
- Do not remove invocation authority from live commit, hook, adapter, pager, supervisor, push, merge, or recovery subprocesses.
- Do not make recovery ignore real adapter errors, support-state symlink/type drift, Git-control drift, undeclared source edits, or bridge bootstrap failures.
- Do not touch runtime, substrate, seed, projection, scheduler, parity, host semantic, FOUNDER_SESSION_BOOTSTRAP.md, Claude-private, or local Codex surfaces.

## Stop conditions

- Halt on scope expansion, any live non-validation authority regression, os.environ mutation, or failure to reproduce both deterministic root causes.
- Halt if focused tests select zero cases, Phase B is not GO, a fresh COMMIT_GO receipt is absent, ordinary Step 11 pre-push is not green, CI is not green, or overlap with the failed branch is not explicitly preserved.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_recovery_gate.py`

## Acceptance criteria

- The exact pager receipt test passes through every commit-owned validation path even when the parent exports RCX_AGENT_BUS_DIR, RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE, implementer/reviewer overrides, and the repo-root override guard.
- Validation sanitization follows canonical role override truth so the later independent supervisor role can be added without reopening the leak; malicious caller overrides cannot restore protected keys.
- Actual adapter/bootstrap failures remain fail-closed, but incidental bridge_config path text in run_pre_push_script stdout cannot block an otherwise valid bounded delegate.
- b02aadbb useful behavior is preserved by fresh implementation, all focused suites pass, and ordinary full pre-push-fast passes without bypass flags before push.

## Grounding / Authorization

- Task: [PIPELINE-FIX-37C]; wave id `pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12`.
- Governing packet: this file, `reports/control_plane/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12_2026-07-12.md`.
- TASKS.md authority: the 2026-07-12 tracker sync note for wave `pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12` is canonical for this packet's L4 fields.
- Authorization: Founder-authorized fresh-identity integrated successor after FIX37B reached a real commit but deterministically failed Step 11 and exhausted recovery. The failed worktree, branch, commit, bus, receipts, and recovery artifacts remain preserved and unpushed.

FOUNDER_OVERRIDE:pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12`
- Active packet: `reports/control_plane/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12_2026-07-12.md`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12_2026-07-12.md`
  - `reports/deferred/non_blocking/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12 --output reports/l4_wave_indicators/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_recovery_gate.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12_2026-07-12.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tests/tools/test_recovery_gate.py`, `mu/tools/executors/commit_executor.py`, `mu/tools/executors/recovery_gate.py`, `reports/control_plane/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12_2026-07-12.md`, `reports/deferred/non_blocking/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12_bridge_nonblockers.md`, `reports/l4_wave_indicators/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12`
- Active packet: `reports/control_plane/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12_2026-07-12.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `76fde01e869ebd1170baa3c3e4965c85b8b485bcbc4f9014e5ffdb72b6373700`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12_2026-07-12.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tests/tools/test_recovery_gate.py`, `mu/tools/executors/commit_executor.py`, `mu/tools/executors/recovery_gate.py`, `reports/control_plane/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12_2026-07-12.md`, `reports/deferred/non_blocking/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12_bridge_nonblockers.md`, `reports/l4_wave_indicators/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12_2026-07-12.md`
  - `reports/deferred/non_blocking/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pipeline-fix-37c-validation-env-recovery-context-isolation-2026-07-12.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
