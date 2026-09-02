# PR 1219 P0IBRRCP Bridge Envelope Validation Prerequisite R3

Date: 2026-09-02
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCP-BRIDGE-ENVELOPE-VALIDATION-PREREQ-R3]
Wave ID: pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 034af2cf491172a2d62b43326dc8756903df651db0196ed100320f6640b29c04
Purpose: Land only the remaining malformed nested-envelope boundary after shared framing and adapter finality landed: reject a complete live envelope or persisted envelope whose top level, findings container, or finding members cannot be safely consumed, before persistence, rendering, printing, registry use, or recovery decision application.

## Scope

Fresh two-file envelope-shape prerequisite from exact PR #1263 merge: one shared live/persisted structural validator, focused malformed-shape regressions, and exact TASKS baton advancement to reviewer-causality R4.

Files and surfaces in scope:

- Exact permitted path 1: TASKS.md for same-wave landed/current/next and urgent PR/fleet/Mu queue synchronization only.
- Exact permitted path 2: mu/tools/agents/bridge_supervisor.py for one shared live-and-persisted envelope container-shape boundary only.
- Exact permitted path 3: mu/tests/tools/test_agent_bridge_supervisor.py for focused live persistence and persisted render/recovery malformed-shape regressions plus valid controls only.
- Exact permitted path 4: reports/control_plane/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25_2026-09-02.md for the Phase-A-authored canonical packet.
- Exact permitted path 5: reports/l4_wave_indicators/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25.json for Phase-B-generated L4 governance.
- Exact permitted path 6, conditional only on real findings: reports/deferred/non_blocking/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25_bridge_nonblockers.md.
- TASKS.md -- tracker-sync authority. The 2026-09-02 tracker sync note for wave `pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Have Phase A author the canonical bounded packet from this operator stub; preserve envelope R1/R2 and every other stopped candidate unchanged as noncomplete evidence.
2. Add one bridge-owned structural validator used for both authoritative complete live envelopes and decoded persisted envelopes. It requires a Mapping/object envelope, a list findings container, and Mapping/object finding members, and raises bounded deterministic BridgeError without coercing, dropping, repairing, or rewriting malformed values.
3. In parse_envelope, retain current shared extraction, stdout authority, incomplete-draft skipping, required-key, placeholder, decision, and duplicate-envelope behavior. Apply full nested validation only once a Mapping candidate has all required top-level keys and before it enters envelopes or canonical_payloads.
4. Route every persisted-envelope decode that can render, print, report status, build the finding registry, or apply an interrupted-review decision through the same validator before envelope.get, finding.get, len(findings), or decision authority is consumed. Invalid JSON normalization or migration is outside this atom.
5. Add focused tests proving a complete live envelope with non-list findings or a scalar/list finding member fails with BridgeError and leaves the turn FAILED/ERROR with no envelope_json; prove persisted non-object, non-list findings, and non-object member shapes fail with BridgeError before render or recovered decision application. Retain valid empty and object-member findings controls.
6. Synchronize TASKS: record retained-pipe R4C1 LANDED through PR #1263 at dae6d97473288dcf6eed6a0146464e3e28228df6; make this exact R3 the sole CURRENT baton; make pr1219-p0ibrrcp-reviewer-candidate-causality-authority-r4-2026-08-25 and [ROLES-ALL-CODEX-PR1219-P0IBRRCP-REVIEWER-CANDIDATE-CAUSALITY-AUTHORITY-R4] the immediate NEXT baton; preserve the remaining serialized and urgent PR/fleet/Mu order.
7. Land normally through Phase B, providerless commit, PR, CI, review, merge, and cleanup, then advance exactly to fresh reviewer-causality R4.

## Constraints

- Do not change extract_agent_envelope_candidates, delimiter or marker framing, bridge_adapters.py, adapter early-stop, provider-terminal behavior, reader protocol, process cleanup, or any executor surface; shared framing and adapter finality are landed prerequisites.
- Validate only container shape: envelope object, findings list, and finding object members. Do not add per-field or per-finding semantic typing, required-label rules, severity/status normalization, identity binding, generic JSON Schema, migration, or invalid persisted JSON wrapping.
- Numeric touched_files/evidence, list titles/decisions, missing legacy required keys, unauthorized persisted decisions, wrong envelope identity without a live replay, and all other historical reviewer probes are excluded nonblocking edge cases and cannot be promoted into this atom.
- Do not absorb reviewer-causality R4, commit-evidence R2, Phase-B evidence handoff R2, routing R4, R3C5/R3C6, PR census, never-behind application, PR disposition, fleet cleanup, or Mu production.
- Do not copy, resume, mutate, or import either preserved envelope R1/R2 candidate; their evidence may ground a fresh implementation only.
- Every model-bearing role is Codex gpt-5.6-sol ultra; commit remains providerless; do not edit Claude-owned files or hand-author the canonical packet.

## Stop conditions

- Stop only if the exact nested-shape defect cannot be closed inside bridge_supervisor.py and its focused test or if a required edit falls outside the six explicit paths.
- A reviewer demand for framing changes, semantic schema completeness, migration, invalid-JSON policy, identity binding, or any excluded historical probe is a nonblocking deferred edge, not authorization to widen this packet.
- If one packet-only correction fails to converge, preserve the attempt and create a narrower successor; do not enter another same-packet rewrite loop.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`

## Acceptance criteria

- One shared bridge-owned validator protects complete live candidates and every persisted-envelope consumer in scope, requiring an object envelope, findings list, and object finding members before persistence or use.
- Malformed owned shapes raise deterministic BridgeError, never TypeError/AttributeError, never enter a completed turn envelope, never produce poisoned rendered findings, and never authorize a recovered terminal decision.
- Valid empty findings and valid object-member findings remain compatible; existing marker-bearing JSON, draft, stdout/stderr authority, duplicate-identical/conflicting-envelope, placeholder, and decision controls remain green without framing changes.
- The full focused bridge-supervisor test file passes and only the six explicit paths are present in the wave-owned package.
- TASKS records R4C1 landed at PR #1263/dae6d974, R3 as sole current, exact reviewer-causality R4 as immediate next, and retains commit-evidence, evidence-handoff, routing, PR census, never-behind, PR disposition, fleet cleanup, and Mu production.
- Providerless commit, push, PR, required CI, merge, and post-merge cleanup complete through the normal pipeline, after which reviewer-causality R4 is freshly builder-launched from the exact merge.

## Grounding / Authorization

- Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCP-BRIDGE-ENVELOPE-VALIDATION-PREREQ-R3]; wave id `pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25_2026-09-02.md`.
- TASKS.md authority: the 2026-09-02 tracker sync note for wave `pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25_2026-09-02.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tools/agents/bridge_supervisor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25_2026-09-02.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25 --output reports/l4_wave_indicators/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25_2026-09-02.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tools/agents/bridge_supervisor.py`, `reports/control_plane/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25_2026-09-02.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25_2026-09-02.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `73d9588715c6af5ecdb30249ac51df9cd087aa1e1b9d9ff3017b12469af2d10c`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25_2026-09-02.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tools/agents/bridge_supervisor.py`, `reports/control_plane/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25_2026-09-02.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tools/agents/bridge_supervisor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25_2026-09-02.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
