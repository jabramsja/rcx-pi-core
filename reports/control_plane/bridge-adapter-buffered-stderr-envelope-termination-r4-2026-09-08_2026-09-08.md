# Bridge Adapter Buffered Stderr Envelope Termination R4

Date: 2026-09-08
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [BRIDGE-ADAPTER-BUFFERED-STDERR-ENVELOPE-TERMINATION-R1]
Wave ID: bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 49d0d6732b5e20fbf4b80017546cdf9d130a938627fe8e9e0103ed5cd6e9846a
Purpose: Land the buffered stop-after-envelope repair without regressing either existing authority path. Behind the existing matching structured provider-terminal gate, retain authoritative normalized output and the shared raw-transcript fallback, and add intact independent stderr recognition so stdout interleaving cannot corrupt the only complete envelope view.

## Scope

Fresh narrow successor for the occurring R3 whole-module failure; retain both baseline authority sources and add independent stderr in the same two buffered checks.

Files and surfaces in scope:

- `TASKS.md` — preserve R1, R2, R3, and the evidence-handoff commit; make R4 current; retain the complete later queue.
- `mu/tools/agents/bridge_adapters.py` — the two buffered stop-after-envelope checks only.
- `mu/tests/tools/test_agent_bridge_supervisor.py` — Git-canonical black-box interleaving proof plus the complete existing module compatibility gate.
- `reports/control_plane/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08_2026-09-08.md` — the sole same-path canonical Phase A plan rendered from this immutable contract and consumed after Phase A lock.
- `reports/l4_wave_indicators/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08.json` — same-wave L4 indicator artifact.
- `reports/deferred/non_blocking/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08_bridge_nonblockers.md` — optional only for a real non-blocking finding that does not fail any mandatory gate.
- TASKS.md -- tracker-sync authority. The 2026-09-08 tracker sync note for wave `bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Treat the builder-rendered Markdown at the tracked packet path as the sole canonical Phase A plan from first render through lock and downstream consumption; there is no separate Markdown stub or later packet-authoring step.
2. On exact dev cdb54cea00c4b18182900f7fe8ca5e68c0869d54, independently re-derive the smallest buffered-only additive implementation; do not copy or import candidate bytes from preserved R1, R2, R3, or evidence-handoff lanes.
3. In both the buffered callback and buffered polling predicates, and only behind the existing matching structured provider-terminal gate, preserve all baseline authority terms unchanged and add complete authorized independent stderr as an additional OR term. The resulting authority set must remain normalized authoritative output OR intact stderr OR shared raw-transcript fallback.
4. Add a black-box deterministic primary regression using only public AdapterSpec/run_adapter behavior. Force stderr-prefix, matching Codex terminal, stderr-suffix ordering in the real raw sink; assert byte-exact interleaving, intact stderr authority, and completion under two seconds without private-helper access or test-only production seams.
5. Retain the buffered negative integration proof: a complete authorized stderr envelope without a matching provider terminal must not terminate early. Preserve incomplete, malformed, unauthorized, prose-only, terminal-lookalike, existing normalized-output, and both existing raw-transcript fallback behaviors.
6. Run the entire canonical mu/tests/tools/test_agent_bridge_supervisor.py module as the Phase B-local evidence command before independent review; a known or newly observed failure in that module is blocking regardless of a prior deferred disposition.
7. Synchronize TASKS without loss: preserve R1 pre-review-stopped, R2 Phase-A-stopped, R3 final-pytest/recovery-loop-stopped, and evidence-handoff commit aad0945f74b7f1780c72c1252fd19ba792ec3126 unpushed/unlanded; make R4 the sole CURRENT baton; make a fresh evidence handoff from the exact R4 merge immediate NEXT; retain routing R4, R3C5, R3C6, exact P0IBRRCP closure, PR census/disposition, never-behind carry-forward, preservation-first fleet cleanup, builder-input hardening, Mu production, stopped lanes, and every TODO in order.
8. Land normally through staged L4, independent Codex review, providerless commit, pre-push, required CI, review policy, merge, and cleanup; then builder-launch fresh evidence handoff from the exact merge.

## Constraints

- The external JSON WaveConfig is the operator stub; the generated Markdown at the tracked packet path is the canonical governing Phase A packet. Do not describe the Markdown packet as an operator stub or require a second authoring step.
- All six authority paths use Git-canonical repo paths; do not name the tests symlink in candidate_allowlist, scope authority, or evidence commands.
- Production/test scope is exactly mu/tools/agents/bridge_adapters.py and mu/tests/tools/test_agent_bridge_supervisor.py, plus TASKS and exact same-wave generated governance.
- Every Phase A author, Phase A reviewer, Phase B implementer, and Phase B reviewer must remain foreground-only and single-agent: do not spawn or delegate to subagents, and do not call wait_agent, sleep, poll, or an equivalent wait surface. After bounded inspection, emit the required result immediately in the same turn.
- Do not change phase_a_executor.py, phase_b_executor.py, commit_executor.py, executor_dispatch.py, launch_wave.py, recovery_gate.py, supervisor/client receipt code, executor or bridge configuration, runtime, substrate, hosts, seeds, projections, Mu, or Claude-owned files.
- Do not bypass pre-push, use --no-verify, manually push, amend any preserved candidate, widen a locked packet, or copy/import candidate bytes from a preserved lane.
- Do not delete or replace either baseline normalized-output or raw-transcript authority term; independent stderr is additive. Do not tune timeouts, add sleeps as the fix, weaken terminal matching, accept malformed or unauthorized envelopes, change raw transcript format, or alter streaming behavior.
- Do not weaken, delete, skip, xfail, or reclassify a failing existing test. Do not add private-helper access, ANTICHEAT exceptions, or a test-only production seam.
- Do not absorb unrelated bridge cleanup, parser variants, provider behavior, packet wording, PR/fleet work, or any non-occurring edge case.
- Every model-bearing role and pager is Codex gpt-5.6-sol ultra; commit remains providerless.

## Stop conditions

- Stop before launch unless source, target, and comparison authority are exact cdb54cea00c4b18182900f7fe8ca5e68c0869d54, the linked worktree and bus are fresh, all model roles resolve to Codex, and commit is providerless.
- Stop only if the occurring failure cannot be fixed within the two canonical production/test paths or requires a new envelope, receipt, provider, or transcript schema.
- Stop as DEFECT if any mandatory test in the canonical bridge-supervisor module fails, early termination can occur without a matching structured provider terminal event, or incomplete, malformed, unauthorized, or prose-only stderr becomes authoritative.
- Do not stop or widen for non-occurring provider, parser, timeout, streaming, receipt, mode, or documentation edge cases; record real nonblockers and continue.
- If R4 encounters a builder-input failure, preserve the lane and diagnose the exact builder validation defect rather than revising the packet in place.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`

## Acceptance criteria

- Only the six Git-canonical allowlisted paths change; functional changes are confined to bridge_adapters.py and test_agent_bridge_supervisor.py.
- The executable canonical evidence command passes the entire mu/tests/tools/test_agent_bridge_supervisor.py module before independent review.
- Both buffered termination predicates retain normalized authoritative output and raw-transcript fallback and add intact independent stderr as a third OR authority source behind the unchanged matching-terminal gate.
- The deterministic raw transcript is byte-exactly stderr-prefix, matching stdout terminal, stderr-suffix while the intact independent stderr envelope remains authorized and terminates under two seconds through public seams only.
- The two existing raw-transcript fallback tests, existing normalized-output path, and the complete authorized stderr envelope without matching-terminal negative test all pass.
- Incomplete, malformed, unauthorized, prose-only, and terminal-mismatched inputs remain fail-closed; timeout values, raw transcript format, streaming behavior, provider routing, and envelope authorization vocabulary remain unchanged.
- Staged L4, independent Codex review, providerless commit, pre-push, required CI, review policy, merge, and cleanup complete through the pipeline.
- TASKS preserves all four noncomplete repair candidates and the complete later queue, and a fresh evidence-handoff wave is builder-launched from the exact R4 merge after landing.

## Grounding / Authorization

- Task: [BRIDGE-ADAPTER-BUFFERED-STDERR-ENVELOPE-TERMINATION-R1]; wave id `bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08`.
- Governing packet: this file, `reports/control_plane/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08_2026-09-08.md`.
- TASKS.md authority: the 2026-09-08 tracker sync note for wave `bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08`
- Active packet: `reports/control_plane/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08_2026-09-08.md`
- Indicator artifact: `reports/l4_wave_indicators/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tools/agents/bridge_adapters.py`
  - `reports/control_plane/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08_2026-09-08.md`
  - `reports/l4_wave_indicators/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08 --output reports/l4_wave_indicators/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08_2026-09-08.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tools/agents/bridge_adapters.py`, `reports/control_plane/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08_2026-09-08.md`, `reports/l4_wave_indicators/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08`
- Active packet: `reports/control_plane/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08_2026-09-08.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `c119f91a31126b137ef0cc715534177acad912358e195ed1a3a66e8571070e3d`
- Indicator artifact: `reports/l4_wave_indicators/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08_2026-09-08.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tools/agents/bridge_adapters.py`, `reports/control_plane/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08_2026-09-08.md`, `reports/l4_wave_indicators/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tools/agents/bridge_adapters.py`
  - `reports/control_plane/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08_2026-09-08.md`
  - `reports/l4_wave_indicators/bridge-adapter-buffered-stderr-envelope-termination-r4-2026-09-08.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
