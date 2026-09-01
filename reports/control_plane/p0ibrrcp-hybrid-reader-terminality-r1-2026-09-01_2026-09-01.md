# P0IBRRCP Hybrid Reader Terminality R1 2026-09-01

Date: 2026-09-01
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [P0IBRRCP-HYBRID-READER-TERMINALITY-R1]
Wave ID: p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 1794e3cc52ffff4362f5e003ed003b132327134b7c198d7424f4faf7b44228f8
Purpose: Land the queued executable-reader recovery and terminality prerequisite by preventing a hybrid review's synthetic reader identity from entering generic executable-reader dispatch after interruption or REQUEST_CHANGES, without widening bridge decisions, adapters, provider routing, or downstream queue work.

## Scope

Bound only the declared hybrid-review synthetic-reader recovery/terminality defect and synchronize the completed R4 and next provider-neutral queue truth.

Files and surfaces in scope:

- mu/tools/agents/bridge_supervisor.py (MODIFY) -- make hybrid synthetic-reader jobs terminal or resumable only through an explicitly supported non-provider path; generic reader execution must never invoke the synthetic reader identity.
- mu/tests/tools/test_agent_bridge_supervisor.py (MODIFY) -- reproduce the occurring REQUEST_CHANGES/recovery transition and prove terminal reviewer outcomes plus interrupted synthetic-reader recovery without a reader adapter invocation.
- TASKS.md (MODIFY) -- record provider-isolation R4 LANDED through PR #1253 at eb897fa51256a9e945a283becebe8863fad1c8a8, make this hybrid-reader wave current, keep provider-neutral reconstruction next, and preserve all unrelated tasks/TODOs.
- reports/control_plane/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01_2026-09-01.md (GENERATED) -- sole canonical builder-owned packet.
- reports/l4_wave_indicators/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01.json (PHASE B GENERATED GOVERNANCE) -- sole same-wave indicator.
- reports/deferred/non_blocking/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- unrelated nonblocking evidence only.
- TASKS.md -- tracker-sync authority. The 2026-09-01 tracker sync note for wave `p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Reproduce from comparison_commit the hybrid review path where a completed synthetic reader plus reviewer REQUEST_CHANGES leaves executable READY_READER authority for reader_agent=claude-session.
2. Implement the smallest explicit lifecycle distinction so generic run/recovery never dispatches a synthetic reader through a provider adapter. Preserve normal executable-reader jobs and all existing reviewer decision meanings.
3. Add focused regressions for the reproduced transition, completed synthetic-reader recovery, terminal GO/NO_GO/QUESTION/ERROR persistence, and unchanged normal reader recovery. Do not add speculative lifecycle cases.
4. Synchronize TASKS without deleting, renumbering, or absorbing any downstream packet, then land through normal Codex review, providerless commit, push, required CI, and merge.

## Constraints

- Functional scope is exactly bridge_supervisor.py and its existing test module; no bridge adapter, prompt, config default, executor, recovery gate, provider route, or Claude-owned file may change.
- Do not make claude-session or any synthetic identity executable and do not add a provider fallback.
- Preserve normal reader/reviewer jobs, pause/continue behavior, reviewer decisions, validation storage, and crash recovery outside the reproduced hybrid boundary.
- Every model-bearing role and pager remains Codex; terminal commit execution remains null/providerless.
- Defer unrelated bridge edge cases, naming cleanup, provider-neutral prose, open PR disposition, fleet retirement, and all downstream P0IBRRCP work.
- Use launch_wave.py from exact comparison_commit; no manual packet, implementation edit, staging, commit, push, PR, or merge.

## Stop conditions

- Stop before launch unless origin/dev and clean source HEAD equal comparison_commit.
- Stop before launch on packet identity collision, dirty source, non-Codex model role, or non-providerless commit executor.
- If the declared defect no longer reproduces on comparison_commit, do not invent broader behavior; land only truthful no-op/TASKS closure if pipeline governance permits it.
- Do not stop or widen for unrelated nonblocking findings.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`

## Acceptance criteria

- Only the six allowlisted paths change and exactly one canonical builder-owned packet exists.
- A hybrid reviewer REQUEST_CHANGES cannot leave a state that generic run/recovery interprets as permission to execute reader_agent=claude-session.
- Interrupted hybrid jobs with a completed synthetic reader resume only validation/reviewer work needed by the existing lifecycle and never invoke a reader adapter.
- Terminal GO, NO_GO, QUESTION, and ERROR outcomes remain durable and idempotent; normal executable-reader recovery tests retain their meaning.
- TASKS records R4 landed, this wave current/landed truth, provider-neutral reconstruction next, and preserves every unrelated task/TODO.
- Focused evidence, staged L4, pre-push-fast, fresh Codex review, providerless terminal execution, required CI, PR, and merge complete through the pipeline.

## Grounding / Authorization

- Task: [P0IBRRCP-HYBRID-READER-TERMINALITY-R1]; wave id `p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01`.
- Governing packet: this file, `reports/control_plane/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01_2026-09-01.md`.
- TASKS.md authority: the 2026-09-01 tracker sync note for wave `p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01`
- Active packet: `reports/control_plane/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01_2026-09-01.md`
- Indicator artifact: `reports/l4_wave_indicators/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tools/agents/bridge_supervisor.py`
  - `reports/control_plane/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01_2026-09-01.md`
  - `reports/l4_wave_indicators/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01 --output reports/l4_wave_indicators/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01_2026-09-01.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tools/agents/bridge_supervisor.py`, `reports/control_plane/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01_2026-09-01.md`, `reports/l4_wave_indicators/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01`
- Active packet: `reports/control_plane/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01_2026-09-01.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `bab768acbe451dec580df4e71d638da67bf4efcedda5d63f32d25ea6e121dd5b`
- Indicator artifact: `reports/l4_wave_indicators/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01_2026-09-01.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tools/agents/bridge_supervisor.py`, `reports/control_plane/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01_2026-09-01.md`, `reports/l4_wave_indicators/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tools/agents/bridge_supervisor.py`
  - `reports/control_plane/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01_2026-09-01.md`
  - `reports/l4_wave_indicators/p0ibrrcp-hybrid-reader-terminality-r1-2026-09-01.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
