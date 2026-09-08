# PR 1219 P0IBRRCP Phase B Evidence Handoff R4 Fresh After R3 Builder Stop

Date: 2026-09-08
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PR1219-P0IBRRCP-PHASE-B-EVIDENCE-HANDOFF-R2]
Wave ID: pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 54fbe3712c998b23a5ec430a6637ba401bfafbac92ebd64608b21407d224a440
Purpose: Land only the remaining generic Phase B evidence-authority transport prerequisite after buffered-stderr repair PR #1272: for a locked L4_ENABLER packet with one explicit evidence_command, preserve that exact builder-authored command through normal and re-entry pre-commit supervisor tracker/package finalization, the common final commit-ready handoff, and the existing receipt-backed commit reconstruction. Keep marker-gated restored launcher authority, packets without an explicit command, and non-L4-ENABLER classes unchanged.

## Scope

Fresh two-file generic Phase B control atom from exact buffered-stderr repair PR #1272 merge: preserve one unique explicit locked L4_ENABLER evidence command through normal, re-entry, final-handoff, and existing receipt-rebuild paths; retain marker-gated restore authority and advance TASKS exactly to fresh routing R4.

Files and surfaces in scope:

- `TASKS.md` — exact PR #1272 landed/current/next truth and preservation of the complete later queue.
- `mu/tools/executors/phase_b_executor.py` — generic Phase B locked-packet evidence resolution and normal/re-entry/final-handoff transport only.
- `mu/tests/tools/test_phase_b_executor.py` — compact normal, re-entry, final serialized handoff, existing receipt-backed reconstruction, packet-absent legacy, ambiguity, class-isolation, and marker-authority regressions only.
- `reports/control_plane/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08_2026-09-08.md` — the builder-rendered canonical Phase A packet.
- `reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08.json` — same-wave L4 indicator artifact.
- `reports/deferred/non_blocking/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08_bridge_nonblockers.md` — optional and allowlisted only if bridge review emits a real non-blocking finding.
- TASKS.md -- tracker-sync authority. The 2026-09-08 tracker sync note for wave `pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Treat the builder-rendered Markdown at the tracked packet path as the sole canonical Phase A plan from first render through lock and downstream consumption; there is no separate Markdown stub or later packet-authoring step.
2. On exact PR #1272 merge d2aead287522da8d24e52ab49396c71ef992604f, independently re-derive the smallest generic evidence-handoff implementation; do not copy or import candidate bytes from the preserved September 2 lane or unpushed commit aad0945f74b7f1780c72c1252fd19ba792ec3126.
3. Resolve one unique explicit evidence_command only from the validated active same-wave locked L4_ENABLER packet. Packet absence or no explicit command keeps current changed-test inference; ambiguity or conflicting explicit values fails closed without choosing one.
4. Thread the exact decoded value through generic normal and NEEDS_PHASE_B re-entry tracker-note construction, supervisor package evidence_command, and the common final commit-ready tracker/handoff without normalization or re-derivation, so the already-landed commit-time receipt reconstruction receives the same bytes.
5. Use the existing tracker-note construction and package/handoff seams rather than adding a persistent schema, second authority surface, packet digest, receipt field, provider-specific path, or commit-executor change.
6. Preserve the PR #1270/#1271 marker-gated restored-launcher authority path byte-for-byte and behavior-for-behavior. Do not make restored notes depend on or pass through the new generic packet-command resolver.
7. Add compact occurring-path regressions in the existing Phase B test module and run that entire canonical module before independent review. Do not create parser-format matrices, malformed Markdown suites, atomic-write scenarios, chmod/mode-only cases, or other non-occurring edge work.
8. Synchronize TASKS without loss: record buffered-stderr repair R4 landed through PR #1272 at exact merge d2aead287522da8d24e52ab49396c71ef992604f and preserve evidence-handoff R3 as stopped before executors because its operator WaveConfig entered candidate inventory; make this fresh evidence-handoff R4 wave the sole CURRENT baton; make fresh routing-authority bootstrap R4 the immediate NEXT baton; retain R3C5, R3C6, exact P0IBRRCP closure, all later PR1219 work, live PR census, never-behind carry-forward, PR disposition, preservation-first WorkingRCX fleet cleanup, builder-input hardening, Mu production, all stopped-lane records, and every TODO in serialized order.
9. Treat the primary root behind-dev signal as preservation truth only; no destructive sync, PR disposition, worktree cleanup, or unrelated queue work belongs in this wave.
10. Land normally through Phase B, staged L4, independent Codex review, providerless commit, pre-push, required CI, review policy, merge, and cleanup; then builder-launch fresh routing R4 from the exact merge.

## Constraints

- The external JSON WaveConfig is the operator input; the generated Markdown at the tracked packet path is the canonical governing Phase A packet. Do not describe the Markdown packet as an operator stub or require a second authoring step.
- All six authority paths use Git-canonical repo paths; do not use symlink aliases in candidate_allowlist, scope authority, or evidence commands.
- Production/test scope is exactly mu/tools/executors/phase_b_executor.py and mu/tests/tools/test_phase_b_executor.py, plus TASKS and exact same-wave generated governance.
- Every Phase A author, Phase A reviewer, Phase B implementer, and Phase B reviewer must remain foreground-only and single-agent: do not spawn or delegate to subagents, and do not call wait_agent, sleep, poll, or an equivalent wait surface. After bounded inspection, emit the required result immediately in the same turn.
- Do not change commit_executor.py, executor_dispatch.py, launch_wave.py, phase_a_executor.py, recovery_gate.py, candidate_authority.py, bridge supervisor/adapters, receipt schemas, executor or bridge config, runtime, substrate, hosts, seeds, projections, Mu, Claude-owned files, or the landed launch-tracker checkpoint/finalization contract.
- Do not copy, resume, mutate, cherry-pick, patch-transfer, or use implementation from any preserved evidence-handoff lane or commit; reconstruct only from d2aead28 current code and the locked packet.
- Do not address mode-only candidate drift unless reproduced in this wave's exact live launch-to-Phase-A-to-Phase-B path; synthetic chmod-only probes and other non-occurring mode cases are excluded and cannot block landing.
- Do not absorb parser-format variants, receipt atomicity, provider isolation, timeout tuning, post-merge selector aliases, PR/fleet cleanup implementation, wording polish, or any unrelated/non-occurring edge case.
- Do not weaken staged L4, candidate allowlist, supervisor, receipt, commit, CI, review, merge, launch-tracker byte identity, or generic fallback gates. Every model-bearing role and pager is Codex gpt-5.6-sol ultra; commit remains providerless.

## Stop conditions

- Stop before launch unless exact source, target, and comparison authority is d2aead287522da8d24e52ab49396c71ef992604f, the lane and bus are fresh, role overrides resolve to Codex, and commit execution is providerless.
- Stop only if closure requires a production/test path outside phase_b_executor.py and test_phase_b_executor.py or requires a new serialized authority/schema surface.
- Stop as DEFECT if one explicit supported L4_ENABLER command can differ across normal package, re-entry package, final serialized handoff, or existing receipt-backed reconstruction, or if ambiguity chooses a value instead of failing closed.
- Stop as DEFECT if packet-absent legacy inference, non-L4-ENABLER behavior, or marker-gated restored launch-tracker authority changes.
- Do not stop or widen for non-occurring parser, mode, receipt, provider, cleanup, runtime, or documentation edge cases; record real nonblockers and continue.
- If this fresh wave encounters a builder-input failure, preserve the lane and diagnose the exact builder validation defect rather than revising the packet in place.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`

## Acceptance criteria

- Only the six explicitly enumerated Git-canonical allowlisted paths change; functional production/test changes are confined to phase_b_executor.py and test_phase_b_executor.py.
- A unique explicit L4_ENABLER locked-packet command remains byte-identical in generic normal and re-entry tracker notes and supervisor packages, the common final serialized handoff, and existing receipt-backed reconstruction.
- Packet absence or no explicit command retains current changed-test inference; ambiguity fails deterministically; non-L4-ENABLER behavior remains unchanged.
- The landed marker-gated restored launcher note path remains byte-identical and bypasses generic evidence-command reconstruction exactly as before.
- The exact whole-file evidence command passes the entire mu/tests/tools/test_phase_b_executor.py module before independent review; staged L4, providerless commit, pre-push, required CI, review policy, merge, and cleanup complete through the pipeline.
- TASKS records PR #1272/d2aead28 as landed, preserves the R3 pre-executor builder-input stop, and makes this fresh evidence-handoff R4 wave as sole current, fresh routing R4 as immediate next, and retains every later PR1219, PR/fleet, builder-hardening, Mu-production, stopped-lane, and TODO obligation.
- After merge, fresh routing R4 is builder-launched from the exact merge SHA; no preserved attempt is resumed.

## Grounding / Authorization

- Task: [PR1219-P0IBRRCP-PHASE-B-EVIDENCE-HANDOFF-R2]; wave id `pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08_2026-09-08.md`.
- TASKS.md authority: the 2026-09-08 tracker sync note for wave `pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08_2026-09-08.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08_2026-09-08.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08 --output reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08_2026-09-08.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08_2026-09-08.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08_2026-09-08.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `125a57a7efc4d42c14170eac9170819af95314fbdf2b3f3add013afef482b7f1`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08_2026-09-08.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08_2026-09-08.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08_2026-09-08.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-evidence-handoff-r4-2026-09-08.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
