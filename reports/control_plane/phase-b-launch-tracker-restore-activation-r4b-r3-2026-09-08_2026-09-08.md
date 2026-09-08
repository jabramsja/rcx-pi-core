# Phase B Launch Tracker Restore Activation R4B R3

Date: 2026-09-08
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PHASE-B-LAUNCH-TRACKER-RESTORE-ACTIVATION-R4B]
Wave ID: phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: d6860ce06b4d60a776776a085a73fcdce23433f4a92165d1d50c3a391072fa14
Purpose: Exercise the now-landed marker-gated Phase B launch-tracker restore capability and authority-continuity repair on one fresh live pipeline path, prove the launcher-authored same-wave tracker note remains byte-identical through review, supervisors, final handoff, and commit, then advance immediately to a fresh evidence-handoff R2 wave. Preserve both earlier R4B activation attempts as immutable noncomplete evidence.

## Scope

Marker-bearing live activation only: exercise the landed restore and authority-continuity path, update TASKS queue truth, and emit same-wave packet/indicator governance without changing code or tests.

Files and surfaces in scope:

- `TASKS.md` — queue authority and the unique launcher-authored same-wave tracker note.
- `reports/control_plane/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08_2026-09-08.md` — the builder-authored canonical packet.
- `reports/l4_wave_indicators/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08.json` — the same-wave L4 indicator artifact.
- `reports/deferred/non_blocking/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08_bridge_nonblockers.md` — optional and allowlisted only if bridge review emits a real non-blocking finding.
- TASKS.md -- tracker-sync authority. The 2026-09-08 tracker sync note for wave `phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Phase-B-Launch-Tracker-Restore: required=true; producer=launch_wave.py; version=1
2. Have Phase A author the canonical packet from this operator stub on exact PR #1270 merge 296387dd36076d28e4883bbed2c62ce41e793ec4; use a fresh worktree, bus, branch, and Codex-only role overrides. Preserve both stopped R4B activation lanes and their packets unchanged as noncomplete evidence.
3. Exercise only the already-landed restore and continuity capability. The live Phase B path must capture the unique launcher-authored same-wave tracker note, remove it exactly around implementation, restore the captured bytes before SDK review, indicator collection, candidate-authority staged L4, bridge review, supervisors, and commit handoff, retain those exact bytes through normal finalization, re-entry-capable shared finalization, and final handoff, and finish with checkpoint status restored.
4. Make no production or test code change. The implementer may update only TASKS queue truth: record authority-continuity R4C landed through PR #1270 at exact merge 296387dd36076d28e4883bbed2c62ce41e793ec4, retain PR #1269 chronology, preserve the first R4B corrected-config stop and R4B-R2 Phase B NO_GO, make this R4B-R3 activation the sole CURRENT baton, and keep fresh evidence-handoff R2 as immediate NEXT.
5. Preserve every later PR1219 task, live PR census, never-behind repair, PR disposition, preservation-first WorkingRCX fleet cleanup, Mu production task, stopped-lane record, and TODO-bearing line without loss or reordering.
6. Review must bind its GO to the live restored checkpoint, one unique byte-identical same-wave tracker note in TASKS, supervisor packages, and final handoff, current candidate-authority receipt with staged L4 passed, the exact no-test indicator evidence command, and the four explicitly enumerated allowlisted paths.
7. Land through providerless commit, PR, required CI/review, merge, and cleanup. Only after the exact R4B-R3 merge exists, create and builder-launch fresh evidence-handoff R2 from that merge; never resume either stopped R4B activation lane or the stale stopped evidence-handoff generation.

## Constraints

- Tracked changes are limited to the four explicitly enumerated allowlisted governance paths; no Python, JavaScript, runtime, test, executor, launcher, dispatcher, recovery, commit, bridge, config, Claude-owned, or Mu implementation file may change.
- The marker must appear exactly once as the exact standalone native Work item supplied by this stub; do not paraphrase, duplicate, or add another reserved restore marker.
- Use only existing launch-bound authority and the already-landed R4A/R4C capability. Add no new durable field, bypass, relaxation, manual tracker repair, or candidate-authority exception.
- All model-bearing roles and pager routing are Codex gpt-5.6-sol ultra; commit remains providerless.
- Ignore deferred, non-occurring, parser/platform, performance, and other edge work that does not block this live activation.

## Stop conditions

- Stop before launch unless source, target, comparison, and loaded executor authority are exact PR #1270 merge 296387dd36076d28e4883bbed2c62ce41e793ec4 and the worktree, bus, branch, and role overrides are fresh.
- Stop as an active blocker if marker recognition, launch-bound capture, exact note removal, byte-exact restoration, restored checkpoint state, staged L4, downstream byte continuity, independent review, or commit authority fails on this occurring live path.
- Stop if any implementation or test file must change; preserve the lane and narrow the reproduced active blocker instead of revising the canonical packet in place.
- Do not stop, widen, or delay for a deferred or non-occurring edge case.

## Validation gates

- evidence_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08 --output reports/l4_wave_indicators/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08.json`

## Acceptance criteria

- Only the four explicitly enumerated allowlisted governance paths change; no production or test code changes.
- The exact restore marker activates once, the bus-local checkpoint reaches restored, and TASKS contains exactly one byte-identical launcher-authored same-wave tracker note before every downstream review/authority boundary.
- The same launcher-authored note remains byte-identical in normal/re-entry-capable supervisor finalization packages and final commit handoff; no generic same-wave replacement occurs.
- Candidate authority remains launch-bound to exact merge 296387dd36076d28e4883bbed2c62ce41e793ec4 and its current receipt reports staged L4 passed before independent bridge review starts.
- The exact no-test indicator-collection evidence command succeeds and remains byte-identical across packet, TASKS, supervisor package, and handoff; no receipt or tracker-authority enforcement is weakened.
- TASKS records R4C landed at PR #1270/exact merge, both stopped R4B attempts, R4B-R3 CURRENT, fresh evidence-handoff R2 NEXT, and preserves the complete downstream cleanup and Mu-production queue plus every TODO.
- Providerless PR, all required CI, merge, and terminal cleanup complete before fresh evidence-handoff R2 is builder-launched from the exact R4B-R3 merge.

## Grounding / Authorization

- Task: [PHASE-B-LAUNCH-TRACKER-RESTORE-ACTIVATION-R4B]; wave id `phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08`.
- Governing packet: this file, `reports/control_plane/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08_2026-09-08.md`.
- TASKS.md authority: the 2026-09-08 tracker sync note for wave `phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08`
- Active packet: `reports/control_plane/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08_2026-09-08.md`
- Indicator artifact: `reports/l4_wave_indicators/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `reports/control_plane/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08_2026-09-08.md`
  - `reports/deferred/non_blocking/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08 --output reports/l4_wave_indicators/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08.json.
- `target_gate_id`: G8.
- `evidence_command`: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08 --output reports/l4_wave_indicators/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08.json`.
- `evidence_delta`: PR #1270 landed the restored launch-tracker authority-continuity repair at exact merge 296387dd36076d28e4883bbed2c62ce41e793ec4. The first R4B activation stopped in Phase A on incomplete exact-path enumeration; R4B-R2 then reached restored checkpoint and staged-L4 authority but stopped Phase B NO_GO because later finalization and handoff replaced the launcher note. This fresh R4B-R3 activates the repaired path only and preserves both stopped lanes unchanged..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08`
- Active packet: `reports/control_plane/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08_2026-09-08.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `c8a07bc98ed40cc40b4c80304d9e1f838de753aeba6d39015bce3f25580166a1`
- Indicator artifact: `reports/l4_wave_indicators/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08 --output reports/l4_wave_indicators/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08.json`.
- Evidence delta: PR #1270 landed the restored launch-tracker authority-continuity repair at exact merge 296387dd36076d28e4883bbed2c62ce41e793ec4. The first R4B activation stopped in Phase A on incomplete exact-path enumeration; R4B-R2 then reached restored checkpoint and staged-L4 authority but stopped Phase B NO_GO because later finalization and handoff replaced the launcher note. This fresh R4B-R3 activates the repaired path only and preserves both stopped lanes unchanged..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08_2026-09-08.md`
  - `reports/deferred/non_blocking/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/phase-b-launch-tracker-restore-activation-r4b-r3-2026-09-08.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
