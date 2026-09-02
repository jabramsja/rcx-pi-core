# PR 1219 P0IBRRCP Reviewer Candidate Causality Authority R4

Date: 2026-09-02
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCP-REVIEWER-CANDIDATE-CAUSALITY-AUTHORITY-R4]
Wave ID: pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 91d1a76c5e3699792928c758da04156f211b8c45aa617b9c658cafd37f9d77c0
Purpose: Land only the remaining reviewer-prompt causality atom after the current-impact disposition contract and nested-envelope validation are already landed: require each code-review finding to record candidate relationship, technical impact class, lifecycle status, and merge disposition independently before emitting the original envelope, without widening blocking eligibility or rewriting reviewer output.

## Scope

Fresh two-file reviewer-prompt atom from exact PR #1264 merge: independent four-fact finding classification, minimal composed-prompt regressions, and exact TASKS baton advancement to commit-evidence R2.

Files and surfaces in scope:

- Exact permitted path 1: TASKS.md for same-wave landed/current/next and preserved urgent PR/fleet/Mu queue synchronization only.
- Exact permitted path 2: mu/tools/agents/bridge_supervisor.py for the code-review prompt's independent classification-and-recording instructions only.
- Exact permitted path 3: mu/tests/tools/test_agent_bridge_supervisor.py for minimal composed-prompt contract regressions only; these prove prompt text, not model compliance.
- Exact permitted path 4: reports/control_plane/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25_2026-09-02.md for the Phase-A-authored canonical packet.
- Exact permitted path 5: reports/l4_wave_indicators/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25.json for Phase-B-generated L4 governance.
- Exact permitted path 6, conditional only on real findings: reports/deferred/non_blocking/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25_bridge_nonblockers.md.
- TASKS.md -- tracker-sync authority. The 2026-09-02 tracker sync note for wave `pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Have Phase A author the canonical bounded packet from this operator stub; preserve stopped reviewer-causality R2/R3 unchanged as noncomplete evidence.
2. For code review only, require each finding to determine and record candidate relationship, technical impact class, lifecycle status, and merge disposition independently before the original envelope is emitted. Reuse the existing finding status, disposition, and evidence surface; do not add a sidecar or rewrite output after emission.
3. Preserve the landed current-impact disposition authority exactly: a blocker still requires a candidate-introduced/worsened current-path regression or direct failure of an exact locked acceptance criterion, while synthetic-only, interruption-injected, theoretical/not-occurring, pre-existing-unworsened, and unrelated-adjacent findings remain absolute nonblockers regardless of severity.
4. State explicitly that candidate causality establishes accountability and relevance, technical impact establishes behavioral consequence, lifecycle records new/persisting/addressed state, and disposition follows the existing authoritative current-impact contract; none is a proxy for another.
5. Add a compact parameterized composed-prompt regression covering independent labels, candidate-current mandatory blocking, and the absolute nonblocking cases. Tests prove prompt composition only and must not claim deterministic model compliance.
6. Synchronize TASKS: record envelope-validation R3 LANDED through PR #1264 at 88cd4035ee9eb5d2e86c96199a2b262f69747a21; make this R4 the sole CURRENT baton; make fresh commit-evidence R2 the immediate NEXT baton; retain Phase-B evidence handoff, routing, PR census, never-behind, PR disposition, fleet cleanup, and Mu production in their existing serialized order.
7. Land normally through Phase B, providerless commit, PR, CI, review, merge, and cleanup, then builder-launch fresh commit-evidence R2 from the exact merge.

## Constraints

- Do not copy or recreate the stopped R3 candidate's obsolete four-quadrant rule that allowed pre-existing or synthetic/non-occurring findings to block; current dev's current-impact contract is authoritative.
- Do not change the JSON envelope parser or container validator, JSON schema shape, phase_b_executor.py, recovery_gate.py, commit_executor.py, executor_common.py, bridge adapters/templates, launch_wave.py, executor_dispatch.py, receipt code, runtime, substrate, or Claude-owned files.
- Do not add post-review normalization, disposition/severity rewriting, a named-finding allowlist, a baseline fingerprint registry, sidecars, or enforcement that invents missing labels after the reviewer responds.
- Do not reproduce or absorb wrong-identity replay, invalid semantic fields, selector/parser aliases, stale fleet counts, missing future configs, crash permutations, or other stopped-review edge cases. Record any observed survivor nonblocking unless it directly violates this packet's exact current candidate or locked criterion.
- Every model-bearing role is Codex gpt-5.6-sol ultra; commit remains providerless; Phase A owns the canonical packet.

## Stop conditions

- Stop only if the independent prompt classification cannot be completed inside bridge_supervisor.py and its focused test, or if a required edit falls outside the six explicit paths.
- A reviewer demand to widen Phase B classification, parsing, recovery, launcher selection, queue implementation, identity validation, or semantic schemas is a separate later atom or nonblocking edge and cannot widen or hold this wave.
- If one packet-only correction fails to converge, preserve the attempt and create a narrower successor; do not enter another same-packet rewrite loop.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`

## Acceptance criteria

- The composed code-review prompt requires candidate relationship, technical impact class, lifecycle status, and merge disposition to be independently determined and recorded before the original envelope is emitted.
- The landed current-impact blocking eligibility and absolute nonblocking categories remain textually and behaviorally unchanged; candidate relationship alone never promotes or suppresses a finding.
- The implementation reuses existing finding evidence/status/disposition fields and adds no output mutation, sidecar, parser/schema enforcement, Phase B classifier change, or design-review behavior change.
- Compact focused tests prove composed prompt content only, the full bridge-supervisor test file passes, and only the six explicit paths are in the wave-owned package.
- TASKS records PR #1264/88cd4035 as landed, R4 as sole current, commit-evidence R2 as immediate next, and retains all later serialized PR/fleet/Mu obligations.
- Providerless commit, push, PR, required CI, merge, and post-merge cleanup complete through the normal pipeline, after which commit-evidence R2 is freshly builder-launched from the exact merge.

## Grounding / Authorization

- Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCP-REVIEWER-CANDIDATE-CAUSALITY-AUTHORITY-R4]; wave id `pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25_2026-09-02.md`.
- TASKS.md authority: the 2026-09-02 tracker sync note for wave `pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25_2026-09-02.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tools/agents/bridge_supervisor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25_2026-09-02.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25 --output reports/l4_wave_indicators/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25_2026-09-02.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tools/agents/bridge_supervisor.py`, `reports/control_plane/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25_2026-09-02.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25_2026-09-02.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `08636c8355aa451faf4310b37fccd4d1f5fe1a24c32dfd25c6dc952d5c912a06`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25_2026-09-02.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tools/agents/bridge_supervisor.py`, `reports/control_plane/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25_2026-09-02.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25.json`
- Current staged files:
  - `reports/control_plane/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25_2026-09-02.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
