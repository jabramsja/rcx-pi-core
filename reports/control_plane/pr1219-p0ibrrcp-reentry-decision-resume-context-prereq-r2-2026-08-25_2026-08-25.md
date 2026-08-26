# PR 1219 P0IBRRCP Re-entry Decision Resume Context Prerequisite R2 2026-08-25

Date: 2026-08-25
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PBNOGO-INTEGRATION]
Wave ID: pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25
Phase-A-Lock: LOCKED
Purpose: Under the already-authorized PBNOGO-INTEGRATION task, land only durable propagation of an already-saved REQUEST_CHANGES or NO_GO decision and its findings into the first unchanged-scope NEEDS_PHASE_B resume correction prompt, including preservation across the pre-invocation checkpoint.

## Scope

Fresh R2 from exact PR 1244 merge authority under canonical PBNOGO-INTEGRATION. Preserve saved non-GO decision context in both re-entry correction prompt sites and through the pre-invocation checkpoint; change no convergence, deferral, process, provider, recovery, or terminal behavior.

Files and surfaces in scope:

- mu/tools/executors/phase_b_executor.py (MODIFY) -- add one shared re-entry correction prompt builder; name only recognized REQUEST_CHANGES or NO_GO decisions; use it in uninterrupted and unchanged-scope resumed paths; carry last_reentry_bridge_decision through the pre-invocation needs_phase_b_reentry checkpoint.
- mu/tests/tools/test_phase_b_executor.py (MODIFY) -- prove REQUEST_CHANGES and NO_GO plus exact saved findings survive into the first resumed correction prompt and its pre-invocation checkpoint; prove uninterrupted parity and generic supervisor-first or missing-field fallback.
- TASKS.md (MODIFY) -- use the existing [PBNOGO-INTEGRATION] alias without duplication; mark R4A2 landed through PR 1244 at exact f5bcbd0a64de9e385680ba8313de9ddfc01e9445; preserve stopped auto-defer R1/R2, stopped PBNOGO R1, and stopped resume-context R1 as noncomplete evidence; make this R2 sole CURRENT and normal-exit recorded-child cleanup sole immediate NEXT; retain fresh PBNOGO reconstruction, auto-defer timeout R3, recovery-timeout containment, provider-terminal R4B, root-exit R4C, and remaining envelope validation in that exact serialized order; preserve every task, all five TODO-bearing lines, and PR/fleet cleanup order.
- reports/control_plane/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25_2026-08-25.md (GENERATED) -- sole canonical prerequisite packet.
- reports/l4_wave_indicators/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25.json (PHASE B GENERATED GOVERNANCE) -- same-wave indicator collected and staged before review.
- reports/deferred/non_blocking/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- same-wave nonblocking findings only.
- TASKS.md -- tracker-sync authority. The 2026-08-25 tracker sync note for wave `pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Reconstruct only from exact merge f5bcbd0a64de9e385680ba8313de9ddfc01e9445; do not copy any stopped candidate. Preserve every stopped lane, bus, packet, render, raw transcript, staged candidate, and state unchanged.
2. Create one local prompt builder beside the existing bridge-fix prompt helper. Append a decision suffix only for exact REQUEST_CHANGES or NO_GO and keep the generic heading otherwise.
3. Use that helper at both duplicated re-entry implementer prompt sites so uninterrupted and resumed behavior match.
4. When a resume loaded last_reentry_bridge_decision, retain it in the pre-invocation needs_phase_b_reentry save so another interruption before implementer completion cannot erase the context. Do not alter state validation or post-implementer review checkpoints.
5. Add focused tests for both saved decisions, exact findings, prompt ordering, checkpoint carry-forward, uninterrupted parity, and legacy/generic fallback.
6. Atomically reconcile TASKS to the founder-authorized blocker-first serialization and complete the normal all-Codex builder pipeline with providerless terminal execution.

## Constraints

- Functional and test scope is exactly phase_b_executor.py and test_phase_b_executor.py, plus TASKS.md and same-wave generated governance. Add no other functional or test file.
- Do not change ordinary or re-entry GO, REQUEST_CHANGES, NO_GO, QUESTION, disposition, deferred-packet synchronization, max-round, repeat-cap, or bridge-review ordering semantics.
- Do not change bridge subprocess cleanup, broader process-tree behavior, implementer mutation exactly-once behavior, state shape validation, provider envelopes, commit_executor.py, recovery_gate.py, dispatcher, launcher, hooks, committed role defaults, runtime/substrate code, or Mu semantics.
- Provider-terminal R4B and root-exit R4C are delayed only behind the reproduced active prerequisites; they remain mandatory and explicitly serialized, not cancelled, deferred indefinitely, or dispositioned away.
- Use launch_wave.py and the normal immutable-source dispatcher, Phase A, Phase B, providerless terminal executor, PR checks, and merge chain. No manual candidate patch, staging, Git terminal action, or source substitution.
- Every model-bearing implementation, review, meta-review, pager, bot-remediation, and recovery role is Codex. Commit execution remains providerless; no Claude-backed role or fallback is authorized.

## Stop conditions

- Stop before launch if source HEAD, target HEAD, origin/dev, or comparison_commit differs from f5bcbd0a64de9e385680ba8313de9ddfc01e9445; if target is dirty; if identity collides; or if the all-Codex/providerless path is unavailable.
- Stop as NEEDS_RESCOPING if decision-context preservation requires a functional or test file outside phase_b_executor.py and test_phase_b_executor.py.
- Stop and preserve if review demands process-tree closure, PBNOGO convergence changes, auto-defer/resolver repair, mutation exactly-once semantics, provider changes, QUESTION durability, or another queued edge case.
- Stop and preserve if the same demonstrated context blocker repeats after one focused correction or a Phase B reviewer exits without a final verdict.
- Do not demote this packet to nonlaunchable or restore stale R4B-immediate-next wording: the founder explicitly authorized these narrower builder prerequisites to make the blocked landing chain converge.
- Do not stop or widen for malformed legacy state, receipt-root hardening, probabilistic filename collisions, spelling nits, or other nonblocking work already retained in TASKS.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`

## Acceptance criteria

- Phase A recognizes [PBNOGO-INTEGRATION] as the existing canonical launch authorization and the founder override as authority for the reproduced prerequisite serialization.
- Only the six allowlisted candidate paths change and no packet alias is created.
- Saved REQUEST_CHANGES and NO_GO decisions each appear verbatim with exact saved findings in the first unchanged-scope resumed correction prompt.
- The pre-invocation needs_phase_b_reentry checkpoint retains the loaded saved decision before the implementer is invoked.
- The uninterrupted correction path uses the same decision-aware prompt builder; supervisor-first and missing/legacy decision cases retain the generic heading.
- No bridge review runs before the resumed correction prompt, and existing post-implementer checkpoint behavior remains unchanged.
- No convergence, deferral, process-lifecycle, provider, recovery, commit, runtime, or substrate behavior changes beyond durable prompt context propagation.
- TASKS marks R4A2 landed, preserves every stopped attempt, selects this R2 as sole CURRENT, and serializes normal-exit cleanup, fresh PBNOGO, auto-defer, recovery containment, R4B, R4C, and remaining envelope validation without losing any task, TODO, or cleanup row.
- Focused tests, the full Phase B executor test file, staged L4 enforcement, providerless terminal execution, required CI, review clearance, and merge complete normally.

## Grounding / Authorization

- Task: [PBNOGO-INTEGRATION]; wave id `pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25_2026-08-25.md`.
- TASKS.md authority: the 2026-08-25 tracker sync note for wave `pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25` is canonical for this packet's L4 fields.
- Authorization: Canonical TASKS already authorizes [PBNOGO-INTEGRATION] to preserve REQUEST_CHANGES and NO_GO. The stopped PBNOGO R1 reviewer reproduced this narrower prerequisite as a high blocker. The founder's current explicit instructions authorize multiple narrower packets via launch_wave.py when the wave diverges, make landing the prime directive, require Codex for every model-bearing role, and direct that active blockers precede edge work. This authority temporarily inserts resume-context R2, normal-exit recorded-child cleanup, fresh PBNOGO, auto-defer timeout R3, and recovery-timeout containment before the already-required R4B then R4C sequence; it does not cancel R4B/R4C or any later task.

FOUNDER_OVERRIDE:pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25_2026-08-25.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25_2026-08-25.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25 --output reports/l4_wave_indicators/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25_2026-08-25.md. (2) Final pytest gate covered 8 pytest selector(s) across 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25_2026-08-25.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25_2026-08-25.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `f7855283dce31e1837592811b6f8afdd31ed0739a43ef1328e20cb02297705c3`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25_2026-08-25.md. (2) Final pytest gate covered 8 pytest selector(s) across 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25_2026-08-25.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25_2026-08-25.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-reentry-decision-resume-context-prereq-r2-2026-08-25.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
