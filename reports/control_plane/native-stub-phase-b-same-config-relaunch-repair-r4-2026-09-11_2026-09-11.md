# Native Stub Phase B Same Config Relaunch Repair R4 2026-09-11

Date: 2026-09-11
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NATIVE-STUB-PHASE-B-SAME-CONFIG-RELAUNCH-REPAIR]
Wave ID: native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 345ccc57eea4633e96b38d8e4fd560aefca148cde7d48419baad13e0d685caf8
Purpose: Repair only the observed completed-failure same-config relaunch: persist and atomically claim an exact dispatcher-terminal receipt, validate the exact locked Phase B candidate, reconcile the declared bus-local bridge prerequisites, and resume through the existing Phase B surface without re-entering Phase A.

## Scope

Modify only launch_wave.py and test_launch_wave.py plus exact generated governance files; add a single-use terminal receipt for the observed completed dispatcher failure and the exact same-config Phase B continuation.

Files and surfaces in scope:

- Tracked candidate files: TASKS.md; CHANGELOG.md; mu/tools/executors/launch_wave.py; mu/tests/tools/test_launch_wave.py.
- Exact generated tracked packet: reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11_2026-09-11.md.
- Exact generated tracked indicator: reports/l4_wave_indicators/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11.json.
- Exact optional generated tracked nonblocker only: reports/deferred/non_blocking/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11_bridge_nonblockers.md.
- Exact external read-only input: /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11_wave_config.json.
- Exact active-bus launcher-owned runtime files: .agent_bus-native-stub-phase-b-same-config-relaunch-repair-r4-20260911/bridge_config.json; meta/launch_wave_dispatch_terminal.json; meta/launch_wave_dispatch_terminal.claimed.json; meta/post_merge_routing.json; and meta/candidate_authority/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11.spec.json under that same active bus.
- Committed read-only bridge inputs: mu/tools/executors/executor_config.json and mu/tools/agents/bridge_config.example.json.
- Read-only ordered bridge seed inputs: this carrier's .agent_bus/bridge_config.json; /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/.agent_bus-native-stub-phase-b-same-config-relaunch-repair-r4-20260911/bridge_config.json; and /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/.agent_bus/bridge_config.json.
- Read-only active-review evidence: active-bus bridge.db and this carrier's .scratch/phase_b_agent_review_*.status.json.
- After the launcher invokes the dispatcher, existing dispatcher/Phase B/commit authority—not this launcher mutation contract—owns outputs bounded to the candidate allowlist, Git index/branch/commit/PR lifecycle, this active bus directory, this carrier's .scratch directory, and existing same-wave pipeline receipts/reports.
- TASKS.md -- tracker-sync authority. The 2026-09-11 tracker sync note for wave `native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. When _maybe_launch_dispatcher_command receives a normal integer nonzero returncode, atomically write active-bus meta/launch_wave_dispatch_terminal.json before raising LaunchWaveError. Version 1 content must bind state=available, wave_id, task_id, tracked_packet, native packet contract digest, routing-record relative path and SHA-256, worktree and index packet SHA-256, candidate-authority spec relative path and SHA-256 when enabled, and the nonzero returncode. Do not mint this receipt for a still-running process, a zero return, a runner exception, or a missing/unhashable authority artifact.
2. For the Phase B continuation path only, require that exact available terminal receipt after every existing immutable authority validator succeeds and before bridge mutation. Recompute every bound identity/hash from current files and reject mismatch. Atomically rename available to meta/launch_wave_dispatch_terminal.claimed.json immediately before bridge reconciliation; if the rename loses a race, if a claimed receipt already exists, or if no valid available receipt exists, refuse without producer, bridge, or dispatcher mutation.
3. Keep the claimed receipt unavailable throughout the resumed dispatcher call. On normal zero return, remove the claimed receipt. On normal nonzero return, atomically replace it with the new available terminal receipt before raising. If execution is interrupted or raises unexpectedly, leave claimed in place and fail closed on later relaunch; do not add stale-claim recovery in this wave.
4. Select continuation only through this exact composition: _native_phase_b_route_matches_config; _require_native_stub_packet_contract_relaunch_safe; _same_wave_native_packet_sources with exactly one worktree and one index copy of config.tracked_packet whose bytes match; _native_phase_b_tracker_matches_config; _post_commit_candidate_authority_matches; verify_fail_closed_precondition; verify_three_guards; no phase_b_handoff.json; no commit continuation receipt; no _active_review_jobs result; and the matching available terminal receipt.
5. Accept only header Status: Phase B (locked, implementing) plus exactly one Phase-A-Lock: LOCKED. Accept only the canonical base H2 sections, optional single Non-normative review clarification, and exactly one balanced Phase B Indicator Scope Reconciliation block with its existing start marker, exact H2 heading, and end marker. Reject the pre-supervisor/implemented statuses and every commit-generated, deferred, L4 tracker, commit-path, duplicate, unknown, incomplete, or out-of-order post-lock machine block for this narrow continuation selector.
6. Before receipt claim, forbid phase_b_handoff.json, executors/commit_executor_<wave_id>.json, any active bridge job in READER_RUNNING or REVIEWER_RUNNING, and any phase_b_agent_review status=running. These are refusal evidence only and are never deleted or rewritten.
7. After claim and before dispatch, call only setup_bridge_config and setup_bridge_max_turns_override for the selected bus. A present active bridge config is the mutable starting invocation input and must parse as an object with agents. If absent, ensure_bridge_config_path may copy the entire first existing non-symlink source in its existing order: carrier default bus, linked primary matching bus, linked primary default bus. Present malformed state fails unchanged; no source fails before dispatch.
8. Use existing synchronization semantics unchanged: a missing default-declared agent may be seeded from committed bridge_config.example.json; agents present in both live config and bridge_agent_defaults may change only display_name plus model, reasoning-effort, and committed-example max-turn command tokens; every other command argument, mode, timeout_s, prompt_via_stdin, env, unknown agent, and unknown field remains from the live/copied seed. A non-null WaveConfig max_turns may then change only supported selected-agent max-turn tokens atomically; R4 max_turns is unset, so the live second builder is a no-op.
9. Invoke the existing recoverable dispatcher Phase B command with the exact tracked packet, routing-record path, namespaced bus, and Codex role/pager environment. Before this call, packet, index, TASKS, route, launch authority, candidate authority, indicator, and staged candidate bytes must remain unchanged except the receipt claim and declared bridge fields. After this call begins, assess mutations under existing dispatcher/Phase B/commit contracts and candidate allowlist, not the launcher pre-dispatch byte snapshot.
10. Add focused fresh-fixture tests proving terminal receipt emission only after nonzero runner return; exact hash/identity validation; single-use atomic claim; claimed state visible inside the runner; zero-success cleanup; nonzero replacement; interrupted/exception claimed fail-closed; exact accepted status/machine block tuple; forbidden handoff/commit/active-review artifacts; bridge field reconciliation order; no Phase A dispatch; no tracked producer rerun; and rejection before bridge mutation for every receipt or immutable-authority mismatch.
11. Keep initial unlocked launch, launch=false setup, prepare-review, post-commit continuation, and different buses on their existing behavior. Do not add any global/per-bus general lock or claim concurrency safety outside the exact terminal-receipt Phase B resumption path.
12. Update TASKS.md with PR #1285 landed, R2/R3 preserved noncomplete evidence, R4 current/landed truth as appropriate, and fresh fleet census R3 as the sole immediate next item after this repair.

## Constraints

- Do not modify executor_dispatch.py, executor_common.py, phase_a_executor.py, phase_b_executor.py, bridge code, recovery_gate.py, commit_executor.py, committed role/config files, runtime, substrate, PR disposition, or fleet code.
- Do not add a launcher-wide lock, cross-bus lock, PID scan, process kill, polling loop, stale-claim cleanup, or direct-dispatch singleton claim. Those unobserved cases are nonblocking/out of scope unless they occur later.
- Do not weaken any existing packet, route, tracker, candidate, indicator, staged-byte, or Phase A validator.
- Do not treat bridge_config as immutable candidate authority or change existing bridge seeding/synchronization behavior; only call it after exact terminal and immutable continuation authority is claimed.
- Preserve PR #1284 and corrected replacements R2/R3, including carriers and buses, unchanged as noncomplete evidence. Do not resume, copy, adopt, merge, close, delete, or mutate them.
- Do not repair timeouts, reviewer parsing, commit retry, fleet work, roles/models, runtime, Mu work, deferred findings, or hypothetical edges.

## Stop conditions

- If the exact terminal receipt, atomic claim, narrow selector, bridge reconciliation, and Phase B dispatch cannot be implemented only in launch_wave.py and test_launch_wave.py, stop rather than widen.
- If a receipt can be written before a dispatcher process has returned, reused after claim, accepted with any identity/hash mismatch, or silently recovered after an interrupted claim, stop fail-closed.
- If any forbidden lifecycle/machine/runtime artifact can select continuation, or any failed selector can mutate bridge/tracked/dispatcher state, stop fail-closed.
- If bridge reconciliation reads outside the declared existing sources or mutates outside the declared existing fields, stop.
- If any tracked candidate outside the exact allowlist is required, stop for narrower routing.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_launch_wave.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_executor_dispatch.py -k 'phase_b_surface_reads_routing_record_path or phase_b_surface_forwards_dispatcher_owned_routing_record or phase_b_surface_success_chains_to_commit' --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11 --wave-class L4_ENABLER`

## Acceptance criteria

- A normal nonzero dispatcher return emits one exact available terminal receipt before LaunchWaveError; zero, exception, running, or unhashable cases emit none.
- Only the exact Status: Phase B (locked, implementing), LOCKED, one-indicator-block candidate with matching worktree/index bytes, route/tracker/candidate authority, absent handoff/commit/active-review state, and matching available receipt can select continuation.
- Exactly one continuation atomically moves available to claimed before bridge mutation; the runner observes claimed; competing/repeated calls refuse; zero removes claimed; nonzero replaces it with a new available receipt; interruption leaves claimed fail-closed.
- The eligible regression reconciles only declared bus-local bridge fields, calls the explicit recoverable Phase B surface once, never invokes Phase A, and never reruns packet/TASKS/routing/candidate/indicator producers.
- All tracked/index/authority bytes are identical at the dispatcher boundary except declared bridge and terminal-receipt runtime files; downstream outputs are governed by existing dispatcher contracts and the exact candidate allowlist.
- Initial unlocked, launch=false, prepare-review, post-commit, and different-bus behavior remains unchanged; no general concurrency feature is introduced.
- The complete launcher test file, focused existing dispatcher Phase B tests, and staged L4 contract pass through the pipeline.
- TASKS.md truthfully records R2/R3 stopped evidence, R4 current/landed state, and fleet census R3 immediately next.

## Grounding / Authorization

- Task: [NATIVE-STUB-PHASE-B-SAME-CONFIG-RELAUNCH-REPAIR]; wave id `native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11`.
- Governing packet: this file, `reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11_2026-09-11.md`.
- TASKS.md authority: the 2026-09-11 tracker sync note for wave `native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11`
- Active packet: `reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11_2026-09-11.md`
- Indicator artifact: `reports/l4_wave_indicators/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11_2026-09-11.md`
  - `reports/l4_wave_indicators/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11 --output reports/l4_wave_indicators/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_launch_wave.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_executor_dispatch.py -k 'phase_b_surface_reads_routing_record_path or phase_b_surface_forwards_dispatcher_owned_routing_record or phase_b_surface_success_chains_to_commit' --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11 --wave-class L4_ENABLER`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11_2026-09-11.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_launch_wave.py`, `mu/tools/executors/launch_wave.py`, `reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11_2026-09-11.md`, `reports/l4_wave_indicators/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11`
- Active packet: `reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11_2026-09-11.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `422f8cf72033e27a08dcc918461460672a1066c3fd0d7edcae71e4fddd9ae805`
- Indicator artifact: `reports/l4_wave_indicators/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_launch_wave.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_executor_dispatch.py -k 'phase_b_surface_reads_routing_record_path or phase_b_surface_forwards_dispatcher_owned_routing_record or phase_b_surface_success_chains_to_commit' --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11 --wave-class L4_ENABLER`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11_2026-09-11.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_launch_wave.py`, `mu/tools/executors/launch_wave.py`, `reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11_2026-09-11.md`, `reports/l4_wave_indicators/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11_2026-09-11.md`
  - `reports/l4_wave_indicators/native-stub-phase-b-same-config-relaunch-repair-r4-2026-09-11.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
