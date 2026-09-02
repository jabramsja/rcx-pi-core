# PR 1219 P0IBRRCP Provider Terminal Authority R4B

Date: 2026-08-25
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCP-PROVIDER-TERMINAL-R4B]
Wave ID: pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 63ba26683c1d2e267fd2a3d24675acd49485ae9095a94536797fd464ec8b1c59
Purpose: Require a complete agent envelope plus the matching parsed provider terminal event before pre-EOF adapter termination, while preserving natural EOF as a separate success path.

## Scope

Land only provider-bound terminal-event authority for pre-EOF adapter termination from exact PR 1259 merge; keep root-exit cleanup and remaining envelope validation serialized behind R4B.

Files and surfaces in scope:

- Bind complete-envelope pre-EOF termination to the matching recognized Claude or Codex terminal event in buffered and streaming adapter paths, with focused existing-file proof.
- Update TASKS through builder-owned same-wave governance without losing the open-PR, never-behind, fleet-cleanup, or Mu-production queue.
- TASKS.md -- tracker-sync authority. The 2026-08-25 tracker sync note for wave `pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Have Phase A author the canonical bounded packet from this operator stub, then implement only the reproduced provider-terminal authority gap.
2. Land through normal Phase B, providerless commit, PR, CI, review, merge, and cleanup; then advance to the separately queued root-exit R4C wave.

## Constraints

- Do not absorb root-exit descendant cleanup, nested-shape/persistence envelope validation, provider refusal policy, recovery routing, or unrelated adapter behavior.
- Every model-bearing role is Codex gpt-5.6-sol ultra; commit execution remains providerless; do not edit Claude-owned files or hand-author the canonical packet.

## Stop conditions

- Stop only for a reproduced in-scope blocker requiring a file outside the allowlist or failed exact candidate authority; do not widen for non-occurring edge cases.
- Do not revise this same admitted config or packet; if the active blocker proves nonconvergent, preserve it and use a fresh narrower builder wave.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`

## Acceptance criteria

- For recognized structured providers, pre-EOF termination requires a complete envelope and the matching top-level terminal event: Claude result for Claude and Codex turn.completed for Codex, followed by final drain/rescan.
- Cross-provider, nested, tool-result, marker-string, and plain/unknown lookalikes cannot supply terminal authority; natural EOF, exact-byte capture, meta-envelope compatibility, watchdog failure behavior, cleanup, and buffered/streaming parity remain intact.

## Grounding / Authorization

- Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCP-PROVIDER-TERMINAL-R4B]; wave id `pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25_2026-08-25.md`.
- TASKS.md authority: the 2026-08-25 tracker sync note for wave `pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25

## Non-normative review clarification

This trailing section resolves the bridge review's three blocking ambiguities only. It does not amend, reorder, replace, or supersede the native launcher packet contract above.

- **Exhaustive file allowlist.** The allowlist referenced by the native Scope and Stop conditions comprises exactly these files:
  1. `mu/tools/agents/bridge_adapters.py` -- provider-terminal implementation in the buffered and streaming adapter paths.
  2. `mu/tests/tools/test_agent_bridge_supervisor.py` -- focused existing-file proof for that implementation.
  3. `TASKS.md` -- builder-owned same-wave tracker sync only.
  4. `reports/control_plane/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25_2026-08-25.md` -- governing packet and this review clarification only.
  No directory, wildcard, or other repository path is allowlisted.

- **Concrete bounded design-task mapping.** Without changing the order or landing sequence of the native Work items, their implementation and proof are bounded to:
  1. In `mu/tools/agents/bridge_adapters.py`, require both a complete envelope and the matching parsed top-level provider terminal event before either buffered or streaming `stop_after_envelope` logic may terminate a recognized provider before EOF: Claude `type=result` for Claude and Codex `type=turn.completed` for Codex. Retain the final drain/rescan and preserve natural EOF as an independent success path.
  2. In `mu/tests/tools/test_agent_bridge_supervisor.py`, add focused buffered/streaming proof for both matching provider cases; reject cross-provider, nested, tool-result, marker-string, and plain/unknown lookalikes; and preserve exact-byte capture, meta-envelope compatibility, watchdog failure behavior, cleanup, natural EOF, and buffered/streaming parity.
  3. Limit `TASKS.md` work to the builder-owned same-wave tracker sync, then apply the native Work item 2 providerless landing and cleanup sequence to only the adapter and focused-test changes above.

- **Exact predecessor grounding.** The actual recovery-timeout containment merge SHA required by TASKS.md is `86593e5b4e25cbdd940cb28c4abbd1c4b237c946`. The native Scope phrase "exact PR 1259 merge" refers to this exact authority: the R4B candidate must be built fresh from and pinned to that SHA. The existing same-wave `FOUNDER_OVERRIDE` remains unchanged.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25_2026-08-25.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tools/agents/bridge_adapters.py`
  - `reports/control_plane/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25_2026-08-25.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25 --output reports/l4_wave_indicators/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25_2026-08-25.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tools/agents/bridge_adapters.py`, `reports/control_plane/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25_2026-08-25.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25_2026-08-25.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `f335161461f085f96f957793a474a2589955cf099b923ea8aced27585f15c060`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25_2026-08-25.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tools/agents/bridge_adapters.py`, `reports/control_plane/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25_2026-08-25.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tools/agents/bridge_adapters.py`
  - `reports/control_plane/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25_2026-08-25.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-provider-terminal-r4b-2026-08-25.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
