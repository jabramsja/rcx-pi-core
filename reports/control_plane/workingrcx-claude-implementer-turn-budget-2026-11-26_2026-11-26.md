# WorkingRCX Claude Implementer Turn Budget 2026-11-26

Date: 2026-11-26
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-NATIVE-LIFECYCLE-PREVENTION]
Wave ID: workingrcx-claude-implementer-turn-budget-2026-11-26
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 080582da5f6a40a7bf8784dda1b3bb0a3b325a90d392c602c08fb22950789cc9
Purpose: Raise the committed Claude implementer turn budget so heavy Phase B waves can finish natively. The bridge-config seed mu/tools/agents/bridge_config.example.json gives the claude and fable agent commands --max-turns 100, and the bridge-config sync propagates that seed value into every lane bus. Throughput R8, the first heavy wave after the founder moved implementers to Claude, stopped on error_max_turns at 100. The per-wave max_turns override cannot be used under the current roles because launch_wave applies it to the codex reviewer too, which has no turn flag (separate BLOCKING finding, fixed after the throughput delivery because that delivery also edits launch_wave). This wave changes only the seed's claude and fable --max-turns value from 100 to 400 and pins it with a regression.

## Scope

Fresh lane from exact dev cefb858900baedba467647a8186c48e5f8fc65a6: the bridge-config seed's claude and fable --max-turns 100 -> 400, plus a regression pinning the committed value and its propagation into an existing lane bus.

Files and surfaces in scope:

- mu/tools/agents/bridge_config.example.json (MODIFY) -- only the value after --max-turns in the claude and fable agent commands, 100 -> 400; no other field, agent or ordering change.
- mu/tests/tools/test_bridge_config_model_sync.py (MODIFY) -- add a regression asserting the committed seed's claude and fable commands carry --max-turns 400 and that sync_bridge_config_agents_from_defaults propagates it into a pre-existing lane bus adapter; keep every existing assertion unchanged.
- TASKS.md (MODIFY) -- body equals the preserved PRIMARY checkpoint (sha256 070f4861e513f4b241cf042a6ed8871f6fbdb89a4bc7c2caba5d4c1aadaedc18) plus only this wave's tracker note.
- reports/control_plane/workingrcx-claude-implementer-turn-budget-2026-11-26_2026-11-26.md, reports/l4_wave_indicators/workingrcx-claude-implementer-turn-budget-2026-11-26.json, reports/deferred/non_blocking/workingrcx-claude-implementer-turn-budget-2026-11-26_bridge_nonblockers.md (wave-owned artifacts).
- reports/deferred/non_blocking/workingrcx-claude-implementer-turn-budget-2026-11-26_bridge_nonblockers.md
- TASKS.md -- tracker-sync authority. The 2026-11-26 tracker sync note for wave `workingrcx-claude-implementer-turn-budget-2026-11-26` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Start from exact dev cefb858900baedba467647a8186c48e5f8fc65a6; comparison_commit is that SHA.
2. Change only the claude and fable --max-turns values in the seed from 100 to 400.
3. Add the regression and show it fails on the 100 seed and passes on 400; run the whole bridge-config model-sync module.
4. Show that a freshly synced lane bridge config carries --max-turns 400 for claude and fable and leaves the codex command unchanged.

## Constraints

- Exact candidate allowlist; halt NEEDS_RESCOPING if any other path is required.
- Do not touch launch_wave, executor_common, executor_config.json, bridge adapters or any other executor surface; the override-targeting fix is a separate wave after the throughput delivery.
- Do not change the seed's model, effort, display or codex entries (the sync converges model and effort from the committed bridge agent defaults; stale seed model strings are a separate DOC_ACCURACY item).
- No file:line citations in packet, tracker note or reports.
- Founder usage-stop policy at TASKS.md top applies: stop immediately, preserving files/index/journals, if any observed Codex account window is at or above 70% used.
- This wave carries the founder tracker checkpoint (TASKS.md) verbatim. Its historical observation lines are records, not claims of this wave; findings against their historical wording are non-blocking DOC_ACCURACY, deferred, and never rewritten here.
- Founder authorization (immutable): the 2026-11-26 live directive moving every implementer to the best Claude model and the standing instruction to execute the recommended option autonomously; this wave is the recommended structural fix recorded in PRIMARY reports/deferred/blocking/claude-implementer-max-turns-default-2026-11-26.md.
- Never add a non-README file under reports/deferred/blocking/.
- This wave runs with the native phase_a bridge turn-budget override (RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY=phase_a, 1500s) applied from the launch environment; tracked executor timeouts are unchanged.
- Tests outside this wave's allowlist that fail in CI but pass locally on the same head are owner-40 findings filed separately; do not edit them in this wave.

## Stop conditions

- Halt before launch if origin/dev is not cefb858900baedba467647a8186c48e5f8fc65a6.
- Halt as NEEDS_RESCOPING if the change requires any path outside the allowlist.
- Halt on the founder usage-stop threshold.
- Halt before launch if the lane contains any non-README file under reports/deferred/blocking/.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_bridge_config_model_sync.py --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-claude-implementer-turn-budget-2026-11-26 --wave-class L4_ENABLER`

## Acceptance criteria

- The seed's claude and fable commands carry --max-turns 400; nothing else in the seed changes.
- The new regression fails on the old seed value and passes on the new one; the bridge-config model-sync module passes.
- A synced lane bridge config carries --max-turns 400 for claude and fable and an unchanged codex command.
- The local pre-push gate passes; independent review, CI and providerless commit/merge pass.
- TASKS.md equals the preserved PRIMARY checkpoint plus only this wave's tracker note.

## Grounding / Authorization

- Task: [FLEET-NATIVE-LIFECYCLE-PREVENTION]; wave id `workingrcx-claude-implementer-turn-budget-2026-11-26`.
- Governing packet: this file, `reports/control_plane/workingrcx-claude-implementer-turn-budget-2026-11-26_2026-11-26.md`.
- TASKS.md authority: the 2026-11-26 tracker sync note for wave `workingrcx-claude-implementer-turn-budget-2026-11-26` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-claude-implementer-turn-budget-2026-11-26

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-claude-implementer-turn-budget-2026-11-26`
- Active packet: `reports/control_plane/workingrcx-claude-implementer-turn-budget-2026-11-26_2026-11-26.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-claude-implementer-turn-budget-2026-11-26.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_bridge_config_model_sync.py`
  - `mu/tools/agents/bridge_config.example.json`
  - `reports/control_plane/workingrcx-claude-implementer-turn-budget-2026-11-26_2026-11-26.md`
  - `reports/l4_wave_indicators/workingrcx-claude-implementer-turn-budget-2026-11-26.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-claude-implementer-turn-budget-2026-11-26.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-claude-implementer-turn-budget-2026-11-26 --output reports/l4_wave_indicators/workingrcx-claude-implementer-turn-budget-2026-11-26.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_bridge_config_model_sync.py --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-claude-implementer-turn-budget-2026-11-26 --wave-class L4_ENABLER`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-claude-implementer-turn-budget-2026-11-26_2026-11-26.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_bridge_config_model_sync.py`, `mu/tools/agents/bridge_config.example.json`, `reports/control_plane/workingrcx-claude-implementer-turn-budget-2026-11-26_2026-11-26.md`, `reports/l4_wave_indicators/workingrcx-claude-implementer-turn-budget-2026-11-26.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-claude-implementer-turn-budget-2026-11-26.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-claude-implementer-turn-budget-2026-11-26`
- Active packet: `reports/control_plane/workingrcx-claude-implementer-turn-budget-2026-11-26_2026-11-26.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `3fba176216f9e6c0df4de8b45eef5f4d2e094e50e76d6279e3fbbcf2055ff843`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-claude-implementer-turn-budget-2026-11-26.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_bridge_config_model_sync.py --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-claude-implementer-turn-budget-2026-11-26 --wave-class L4_ENABLER`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-claude-implementer-turn-budget-2026-11-26_2026-11-26.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_bridge_config_model_sync.py`, `mu/tools/agents/bridge_config.example.json`, `reports/control_plane/workingrcx-claude-implementer-turn-budget-2026-11-26_2026-11-26.md`, `reports/l4_wave_indicators/workingrcx-claude-implementer-turn-budget-2026-11-26.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/workingrcx-claude-implementer-turn-budget-2026-11-26.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_bridge_config_model_sync.py`
  - `mu/tools/agents/bridge_config.example.json`
  - `reports/control_plane/workingrcx-claude-implementer-turn-budget-2026-11-26_2026-11-26.md`
  - `reports/l4_wave_indicators/workingrcx-claude-implementer-turn-budget-2026-11-26.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
