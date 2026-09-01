# PR 1219 P0IBRRCP Provider-Neutral Bridge Context R4

Date: 2026-09-01
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [P0IBRRCP-PROVIDER-NEUTRAL-BRIDGE-CONTEXT-R4]
Wave ID: pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: ebdbf10ceaf104dde5270ce35f4736f7d3b7ce3e7fc88cb1718339d159ac31ec
Purpose: Land provider-neutral hybrid bridge context from the exact PR 1254 merge with a durable synthetic-execution marker, configured reader/reviewer rendering, repo-tracked evidence authority, and complete dispatcher test-double compatibility; preserve all stopped attempts as evidence only.

## Scope

From exact PR 1254 merge, land provider-neutral Phase A/B hybrid review context and durable synthetic-mode authority, including every affected dispatcher test double, then sync TASKS without widening behavior.

Files and surfaces in scope:

- mu/tools/agents/bridge_supervisor.py (MODIFY) -- accept configured synthetic-reader identity, persist a separate durable synthetic-reader execution-mode marker at job creation, consult it before adapter lookup on normal/recovery paths, and retain legacy compatibility fallback.
- mu/tools/agents/templates/bridge_reviewer_prompt.txt (MODIFY) -- render actual reader/reviewer identities and state repo-tracked evidence authority without provider-specific implementation claims.
- mu/tools/executors/phase_a_executor.py (MODIFY) -- pass the effective configured Phase A implementer identity as reader alongside the configured reviewer.
- mu/tools/executors/phase_b_executor.py (MODIFY) -- pass the effective configured Phase B implementer identity as reader alongside the configured reviewer on canonical and re-entry review paths.
- mu/tests/tools/test_agent_bridge_supervisor.py (MODIFY) -- prove durable pre-materialization synthetic detection with reader_agent=codex, no adapter lookup, configured alternate reader identity, legacy fallback, recovery, and PR 1254 terminality.
- mu/tests/tools/test_executor_dispatch.py (MODIFY) -- make every affected run_bridge_design_review test double accept reader_agent and assert configured implementer propagation.
- mu/tests/tools/test_phase_a_executor.py (MODIFY) -- prove configured reader/reviewer propagation.
- mu/tests/tools/test_phase_b_executor.py (MODIFY) -- prove configured reader/reviewer propagation and repo-tracked authority.
- mu/docs/agents/AgentBridgeProtocol.v0.md (MODIFY) -- document provider-neutral configured roles, durable synthetic execution mode, and repo-tracked authority.
- TASKS.md (MODIFY) -- preserve the stopped R3 record, mark R4 CURRENT/LANDED as appropriate, retain every queue/TODO item, and leave numbered row 23 normal-root cleanup NEXT.
- reports/control_plane/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01_2026-09-01.md (GENERATED) -- sole launcher-owned canonical packet.
- reports/l4_wave_indicators/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01.json (PHASE B GENERATED GOVERNANCE) -- same-wave indicator.
- reports/deferred/non_blocking/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- nonblocking findings only.
- TASKS.md -- tracker-sync authority. The 2026-09-01 tracker sync note for wave `pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Reconstruct only from exact merge b5d7199339e3eab482c5b6d367fdc8bfd2aa1964. Never resume, copy, mutate, stage, or source stopped R1-R3 code, packets, branches, buses, targets, or source worktrees.
2. Persist a job-level synthetic-reader execution-mode marker in the same durable operation that creates the hybrid job, independently of reader identity, and consult it before reader-adapter lookup after interruption or recovery.
3. Thread the configured implementer identity into canonical Phase A/B hybrid review and render actual reader/reviewer roles while retaining the legacy claude-session fallback only for unmarked historical jobs.
4. Update all affected dispatcher bridge-review doubles for reader_agent and assert propagation so the mandatory pre-push suite cannot rediscover this known compatibility failure.
5. Preserve PR 1254 REQUEST_CHANGES terminality, completed synthetic-turn recovery, decisions, findings, convergence, validation, receipts, candidate authority, pager behavior, and providerless commit behavior.
6. Update focused tests, protocol docs, and narrow TASKS truth; run the exact evidence command; complete normal dispatch, commit, CI, review clearance, merge, and postmerge cleanup.

## Constraints

- Do not modify executor_config.json, adapter commands, provider menus/defaults, decision parsing, finding classification, convergence, recovery, receipts, candidate authority, commit execution, pager behavior, runtime, substrate, seed, host semantics, or Mu semantics.
- Do not edit Claude-owned files or use provider-local memory as candidate evidence. Every model-bearing role is Codex and commit remains providerless.
- Do not fix inactive compatibility aliases, timeout spelling, filename edge cases, or other non-occurring nonblockers.
- Use launch_wave.py and immutable clean source/target worktrees only. No hand-authored packet, candidate patching, manual staging, commit, push, PR, merge, or stopped-lane folding.

## Stop conditions

- Stop before launch if source HEAD, target HEAD, origin/dev, or comparison_commit differs from b5d7199339e3eab482c5b6d367fdc8bfd2aa1964; if either launch worktree is dirty; if identity collides; or if Codex role pins/providerless commit are unavailable.
- Stop and preserve only if a reproduced blocking gate requires a functional path outside the allowlist; use a smaller fresh launch_wave.py prerequisite rather than widening in place.
- Do not stop or widen for non-occurring edge cases or nonblocking findings.
- If bounded review does not converge, preserve the lane and split the active blocker into fresh narrower builder-launched packets.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_phase_a_executor.py mu/tests/tools/test_phase_b_executor.py`

## Acceptance criteria

- Only allowlisted paths change, with exactly one launcher-owned canonical packet and no hand-authored packet alias.
- Launch metadata proves exact base b5d7199339e3eab482c5b6d367fdc8bfd2aa1964, implementer/reviewer/pager Codex, and providerless commit execution.
- An unmaterialized hybrid job with reader_agent=codex remains durably synthetic after interruption and fails closed before adapter lookup; legacy unmarked jobs retain compatibility behavior.
- Canonical Phase A/B records and renders configured reader/reviewer identities without invoking a reader provider, and dispatcher tests accept/assert reader_agent at every affected bridge double.
- Prompt/protocol authority is repo-tracked and provider-neutral; PR 1254 terminality and all unrelated functional behavior remain unchanged.
- All four focused test files, staged L4 enforcement, pre-push-fast, and required CI pass.
- TASKS preserves all queue/TODO/stopped-attempt truth, marks R4 accurately, and leaves numbered row 23 normal-root cleanup NEXT.
- Fresh review clearance, normal merge, and terminal postmerge cleanup complete.

## Grounding / Authorization

- Task: [P0IBRRCP-PROVIDER-NEUTRAL-BRIDGE-CONTEXT-R4]; wave id `pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01_2026-09-01.md`.
- TASKS.md authority: the 2026-09-01 tracker sync note for wave `pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01_2026-09-01.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/docs/agents/AgentBridgeProtocol.v0.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_phase_a_executor.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/agents/bridge_supervisor.py`
  - `mu/tools/agents/templates/bridge_reviewer_prompt.txt`
  - `mu/tools/executors/phase_a_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01_2026-09-01.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01 --output reports/l4_wave_indicators/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_phase_a_executor.py mu/tests/tools/test_phase_b_executor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01_2026-09-01.md. (2) Final pytest gate covered 11 pytest selector(s) across 4 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/docs/agents/AgentBridgeProtocol.v0.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_phase_a_executor.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/agents/bridge_supervisor.py`, `mu/tools/agents/templates/bridge_reviewer_prompt.txt`, `mu/tools/executors/phase_a_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01_2026-09-01.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01_2026-09-01.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `059b317c401c3ae63e47b63feab898e3abc74d26b511b9a8892b6015f54f79af`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_phase_a_executor.py mu/tests/tools/test_phase_b_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01_2026-09-01.md. (2) Final pytest gate covered 11 pytest selector(s) across 4 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/docs/agents/AgentBridgeProtocol.v0.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_phase_a_executor.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/agents/bridge_supervisor.py`, `mu/tools/agents/templates/bridge_reviewer_prompt.txt`, `mu/tools/executors/phase_a_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01_2026-09-01.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01.json`
- Current staged files:
  - `TASKS.md`
  - `mu/docs/agents/AgentBridgeProtocol.v0.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_phase_a_executor.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/agents/bridge_supervisor.py`
  - `mu/tools/agents/templates/bridge_reviewer_prompt.txt`
  - `mu/tools/executors/phase_a_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01_2026-09-01.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-provider-neutral-r4-2026-09-01.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
