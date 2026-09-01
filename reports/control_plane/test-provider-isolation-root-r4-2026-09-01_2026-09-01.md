# Test Provider Isolation Root R4 2026-09-01

Date: 2026-09-01
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [TEST-PROVIDER-ISOLATION-ROOT-R4]
Wave ID: test-provider-isolation-root-r4-2026-09-01
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 84d5df01f9198ab3ec362b1201c17c84c026cef888d7635e8b453920b94673fb
Purpose: Freshly reconstruct on current origin/dev a repository-root pytest provider boundary that remains fail closed across pytest teardown and blocks both provider CLI execution and the Codex app-server WebSocket transport without changing production routing or implementation.

## Scope

Freshly reconstruct the root pytest provider boundary from current dev, retain provider guards across teardown for inherited descendants, block the current Node global-WebSocket Codex transport before TCP connection, and preserve all downstream queue authority.

Files and surfaces in scope:

- conftest.py (MODIFY) -- install process-unique Claude and Codex CLI stubs plus a Node WebSocket preload guard before collection; restore the owning process environment exactly while retaining guard files required by already-detached descendants.
- mu/tests/tools/test_pipeline_agent_pager.py (MODIFY) -- add focused current-process, safe-loopback, post-teardown descendant, supported-root, xdist, and exact-restoration proofs in the existing test file.
- TASKS.md (MODIFY) -- preserve every task and TODO, record R3 as preserved noncomplete and R4 as current, and keep the hybrid-reader/provider-neutral/normal-exit chain unchanged.
- reports/control_plane/test-provider-isolation-root-r4-2026-09-01_2026-09-01.md (GENERATED) -- sole canonical builder-owned packet.
- reports/l4_wave_indicators/test-provider-isolation-root-r4-2026-09-01.json (PHASE B GENERATED GOVERNANCE) -- sole same-wave indicator.
- reports/deferred/non_blocking/test-provider-isolation-root-r4-2026-09-01_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- unrelated nonblocking evidence only.
- TASKS.md -- tracker-sync authority. The 2026-09-01 tracker sync note for wave `test-provider-isolation-root-r4-2026-09-01` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Reconstruct only from comparison_commit. Do not copy, resume, cherry-pick, diff-apply, source, stage, or mutate any preserved provider-isolation candidate, packet, tracker edit, bus, branch, target, or source.
2. Install process-private fail-closed Claude/Codex CLI stubs and an inherited CommonJS WebSocket guard before collection; restore the owning process environment exactly while retaining files needed by already-detached descendants.
3. Prove both provider basenames and production Codex transport remain blocked after nested pytest teardown using only safe fake providers and a loopback listener.
4. Refresh TASKS as tracker truth without deleting or renumbering unrelated queue work, then run the normal pipeline through review, providerless commit, push, PR, CI, and merge.

## Constraints

- Functional scope is exactly conftest.py and mu/tests/tools/test_pipeline_agent_pager.py; no production or Claude-owned file may change.
- Every live model-bearing role must resolve to Codex; commit execution remains null/providerless.
- Do not use real provider processes, authentication, WebSocket services, or model network calls in tests.
- Defer synthetic teardown atomicity, retained-directory garbage collection, TMPDIR variants, style-only findings, and every unrelated nonblocking edge.
- Do not fix hybrid-reader identity, provider-neutral context, normal-exit cleanup, open PR disposition, fleet retirement, runtime, substrate, seed, host, Mu, docs, or unrelated cleanup.
- Use launch_wave.py with the clean immutable source at comparison_commit; no manual packet, candidate patch, staging, commit, push, PR, or merge.

## Stop conditions

- Stop before launch unless origin/dev and clean source HEAD equal comparison_commit and the old R3 lane remains untouched.
- Stop before launch on dirty source, identity collision, packet alias, non-Codex model role, or non-providerless commit executor.
- Stop and preserve if closure requires production, routing, provider-default, app-server URL, or Claude-owned changes.
- Do not stop, widen, or remediate for explicitly deferred or unrelated nonblocking cases.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_pipeline_agent_pager.py`

## Acceptance criteria

- Only the six allowlisted paths change and exactly one canonical builder-owned packet exists.
- Provider CLI basenames and the production Codex app-server exchange fail closed before any safe loopback connection, including for a detached descendant released after pytest teardown.
- The owning pytest process restores exact inherited PATH, NODE_OPTIONS, and provider-binary environment state.
- Supported roots and xdist controller/worker forms load the boundary without topology-specific activation.
- TASKS preserves every unrelated task and records the R3 preservation and R4 landing chain truth.
- Focused evidence, required CI, fresh Codex review, providerless terminal execution, push, PR, and merge complete through the pipeline.

## Grounding / Authorization

- Task: [TEST-PROVIDER-ISOLATION-ROOT-R4]; wave id `test-provider-isolation-root-r4-2026-09-01`.
- Governing packet: this file, `reports/control_plane/test-provider-isolation-root-r4-2026-09-01_2026-09-01.md`.
- TASKS.md authority: the 2026-09-01 tracker sync note for wave `test-provider-isolation-root-r4-2026-09-01` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:test-provider-isolation-root-r4-2026-09-01

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `test-provider-isolation-root-r4-2026-09-01`
- Active packet: `reports/control_plane/test-provider-isolation-root-r4-2026-09-01_2026-09-01.md`
- Indicator artifact: `reports/l4_wave_indicators/test-provider-isolation-root-r4-2026-09-01.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `conftest.py`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `reports/control_plane/test-provider-isolation-root-r4-2026-09-01_2026-09-01.md`
  - `reports/l4_wave_indicators/test-provider-isolation-root-r4-2026-09-01.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/test-provider-isolation-root-r4-2026-09-01.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id test-provider-isolation-root-r4-2026-09-01 --output reports/l4_wave_indicators/test-provider-isolation-root-r4-2026-09-01.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_pipeline_agent_pager.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/test-provider-isolation-root-r4-2026-09-01_2026-09-01.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `conftest.py`, `mu/tests/tools/test_pipeline_agent_pager.py`, `reports/control_plane/test-provider-isolation-root-r4-2026-09-01_2026-09-01.md`, `reports/l4_wave_indicators/test-provider-isolation-root-r4-2026-09-01.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: test-provider-isolation-root-r4-2026-09-01.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `test-provider-isolation-root-r4-2026-09-01`
- Active packet: `reports/control_plane/test-provider-isolation-root-r4-2026-09-01_2026-09-01.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `9883102de1b3df54232363db3f41cbf61de4b9ed898f3f269bfc171ace7d085c`
- Indicator artifact: `reports/l4_wave_indicators/test-provider-isolation-root-r4-2026-09-01.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_pipeline_agent_pager.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/test-provider-isolation-root-r4-2026-09-01_2026-09-01.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `conftest.py`, `mu/tests/tools/test_pipeline_agent_pager.py`, `reports/control_plane/test-provider-isolation-root-r4-2026-09-01_2026-09-01.md`, `reports/l4_wave_indicators/test-provider-isolation-root-r4-2026-09-01.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/test-provider-isolation-root-r4-2026-09-01.json`
- Current staged files:
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `reports/control_plane/test-provider-isolation-root-r4-2026-09-01_2026-09-01.md`
  - `reports/l4_wave_indicators/test-provider-isolation-root-r4-2026-09-01.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
