# Launch Wave Override Authority Producer R1

Date: 2026-09-02
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [LAUNCH-WAVE-OVERRIDE-AUTHORITY-PRODUCER-R1]
Wave ID: launch-wave-override-authority-producer-r1-2026-09-02
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 6bf870b09290239f4130a632a7d322c99e8db35a4382dc958619ee32801a8f38
Purpose: Persist exact launch-time role, pager, and max-turn override authority in every newly produced native routing record before adding any consumer that depends on that field.

## Scope

Land only the immutable launch-override authority producer, record the post-merge continuation consumer as the immediate next prerequisite before R4C, and preserve every existing PR-census, never-behind, PR-disposition, fleet-cleanup, and Mu-production queue item.

Files and surfaces in scope:

- Add a fixed-shape versioned launch_wave_override_authority sibling to every newly generated native routing record during initial launch setup.
- Synchronize TASKS with the producer-first split and the immediately queued consumer wave without deleting, renumbering, or weakening any existing queue item.
- TASKS.md -- tracker-sync authority. The 2026-09-02 tracker sync note for wave `launch-wave-override-authority-producer-r1-2026-09-02` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Have Phase A author the canonical bounded packet from this operator stub and implement only the routing-record producer plus focused tests.
2. Bind implementer_agent, reviewer_agent, pager_route, and max_turns exactly, including deliberate null/default values, so omission cannot be confused with a pre-field route.
3. Prove fresh native initial setup writes the same deterministic authority into every expected routing identity and that changed config values change the record; do not add a reader, validator, fast path, continuation consumer, or legacy migration.
4. Update TASKS to place [LAUNCH-WAVE-POST-COMMIT-CONTINUATION-CONSUMER-R2] immediately after this producer and before PR1219 R4C, while preserving the urgent PR census, never-behind, PR disposition, and WorkingRCX fleet cleanup chain.

## Constraints

- Producer-only split: do not implement post-commit continuation admission, dispatcher resume, handoff validation, candidate-spec recovery, or any compatibility path for existing pre-field routes.
- Do not mutate or retrofit an existing routing record; only newly generated native routes may receive the authority field.
- The canonical packet and candidate authority must describe exactly the six allowlisted paths, including the generated non-blocker report and L4 indicator; defer all synthetic or non-occurring edge cases.
- Do not absorb R4C, envelope validation, recovery policy, open-PR disposition, never-behind application, fleet cleanup, or unrelated launcher behavior.
- Every model-bearing role is Codex gpt-5.6-sol ultra; commit execution remains providerless; do not edit Claude-owned files or hand-author the canonical packet.

## Stop conditions

- Stop only for a reproduced producer-path blocker requiring a file outside the six-path allowlist or failed exact candidate authority; defer non-occurring edge cases.
- Do not add a consumer to make this wave self-resumable; the explicit purpose of this split is to let the producer land through the normal path first.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py`

## Acceptance criteria

- A fresh native launch writes a versioned fixed-shape launch_wave_override_authority sibling before Phase A dispatch, containing exact implementer_agent, reviewer_agent, pager_route, and max_turns values including explicit null/default values.
- Every launcher-generated expected native routing identity carries byte-equivalent authority for the same WaveConfig, while changing any bound value changes the authority record deterministically.
- No resume reader, post-commit fast path, legacy-route inference, routing retrofit, or mutation of existing partial state is introduced; existing launch behavior remains otherwise unchanged.
- The canonical packet, TASKS note, candidate authority, staged candidate, and bridge artifacts consistently name exactly the same six allowed paths and queue the consumer wave immediately next.

## Grounding / Authorization

- Task: [LAUNCH-WAVE-OVERRIDE-AUTHORITY-PRODUCER-R1]; wave id `launch-wave-override-authority-producer-r1-2026-09-02`.
- Governing packet: this file, `reports/control_plane/launch-wave-override-authority-producer-r1-2026-09-02_2026-09-02.md`.
- TASKS.md authority: the 2026-09-02 tracker sync note for wave `launch-wave-override-authority-producer-r1-2026-09-02` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:launch-wave-override-authority-producer-r1-2026-09-02

## Non-normative review clarification

The immutable contract's references to the six-path allowlist expand to exactly these repo-relative paths:

1. `TASKS.md`
2. `mu/tests/tools/test_launch_wave.py`
3. `mu/tools/executors/launch_wave.py`
4. `reports/control_plane/launch-wave-override-authority-producer-r1-2026-09-02_2026-09-02.md`
5. `reports/deferred/non_blocking/launch-wave-override-authority-producer-r1-2026-09-02_bridge_nonblockers.md`
6. `reports/l4_wave_indicators/launch-wave-override-authority-producer-r1-2026-09-02.json`

This enumeration only makes the existing allowlist mechanically explicit; it does not replace, supersede, reorder, or otherwise modify the native launcher packet contract. Packet authority, candidate authority, staged files, and bridge artifacts therefore compare against these six literal path strings and no others.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `launch-wave-override-authority-producer-r1-2026-09-02`
- Active packet: `reports/control_plane/launch-wave-override-authority-producer-r1-2026-09-02_2026-09-02.md`
- Indicator artifact: `reports/l4_wave_indicators/launch-wave-override-authority-producer-r1-2026-09-02.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/launch-wave-override-authority-producer-r1-2026-09-02_2026-09-02.md`
  - `reports/l4_wave_indicators/launch-wave-override-authority-producer-r1-2026-09-02.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/launch-wave-override-authority-producer-r1-2026-09-02.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id launch-wave-override-authority-producer-r1-2026-09-02 --output reports/l4_wave_indicators/launch-wave-override-authority-producer-r1-2026-09-02.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/launch-wave-override-authority-producer-r1-2026-09-02_2026-09-02.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_launch_wave.py`, `mu/tools/executors/launch_wave.py`, `reports/control_plane/launch-wave-override-authority-producer-r1-2026-09-02_2026-09-02.md`, `reports/l4_wave_indicators/launch-wave-override-authority-producer-r1-2026-09-02.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: launch-wave-override-authority-producer-r1-2026-09-02.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `launch-wave-override-authority-producer-r1-2026-09-02`
- Active packet: `reports/control_plane/launch-wave-override-authority-producer-r1-2026-09-02_2026-09-02.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `450ab27a1adbc6dbe911801eba2ee791fe121d4138c5aab567b5a14e0c5a0cbf`
- Indicator artifact: `reports/l4_wave_indicators/launch-wave-override-authority-producer-r1-2026-09-02.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/launch-wave-override-authority-producer-r1-2026-09-02_2026-09-02.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_launch_wave.py`, `mu/tools/executors/launch_wave.py`, `reports/control_plane/launch-wave-override-authority-producer-r1-2026-09-02_2026-09-02.md`, `reports/l4_wave_indicators/launch-wave-override-authority-producer-r1-2026-09-02.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/launch-wave-override-authority-producer-r1-2026-09-02.json`
- Current staged files:
  - `reports/control_plane/launch-wave-override-authority-producer-r1-2026-09-02_2026-09-02.md`
  - `reports/l4_wave_indicators/launch-wave-override-authority-producer-r1-2026-09-02.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
