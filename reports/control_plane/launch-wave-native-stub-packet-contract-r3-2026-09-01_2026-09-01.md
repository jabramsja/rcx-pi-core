# Launch Wave Native Stub Packet Contract R3 2026-09-01

Date: 2026-09-01
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [LAUNCH-WAVE-NATIVE-STUB-PACKET-CONTRACT-R1]
Wave ID: launch-wave-native-stub-packet-contract-r3-2026-09-01
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 9a892d6713b4227bc0571cf229090947f5b4fd76be29e0a13f7ee876cebd8b0f
Purpose: Land the complete native launcher-to-Phase-A packet contract with validation payload binding, durable packet-side provenance, exact same-attempt protection, bounded clarification top-level and sibling-authority rejection, and shared tracker-block adjacency preservation.

## Scope

Land the preserved native packet-contract implementation plus only the exact R1/R2 blockers reproduced on the live builder path, with the shared tracker insertion owner explicitly included and all semantic-review or unrelated edge work excluded.

Files and surfaces in scope:

- mu/tools/executors/launch_wave.py -- require complete native inputs, bind normative and validation payloads into one digest, render packet-side provenance, prevent same-attempt replacement before route-specific exits or writes, and preserve deterministic dated packet naming.
- mu/tools/executors/phase_a_executor.py -- strictly validate the marked aggregate contract and exact validation payload through load/edit/review/lock, bind plan_name to the tracked-packet stem, and reject ATX-H1/Setext-H1 plus Setext-H2 sibling authority inside clarification while preserving unmarked legacy routes.
- mu/tools/executors/tracker_sync_note.py -- make the shared upsert insert after an existing tracker note's entire logical continuation block, including intervening blank lines and indented evidence children.
- mu/tests/tools/test_launch_wave.py -- retain R1 coverage and add exact validation binding, packet marker/digest, packet-only route downgrade, dated identity, and pre-mutation regressions.
- mu/tests/tools/test_phase_a_executor.py -- retain R1 coverage and add validation payload tamper, tracked-packet-stem, packet provenance, ATX-H1, Setext-H1, and Setext-H2 sibling-authority regressions.
- mu/tests/tools/test_tracker_sync_note_generation.py -- add shared logical-block insertion regressions with zero, one, and multiple blank lines before indented evidence children.
- TASKS.md -- record R3 as the active corrected native-stub attempt and preserve every later PR census, never-behind, PR disposition, and preservation-first fleet-cleanup row.
- reports/control_plane/launch-wave-native-stub-packet-contract-r3-2026-09-01_2026-09-01.md -- builder-generated immutable packet for this attempt.
- reports/l4_wave_indicators/launch-wave-native-stub-packet-contract-r3-2026-09-01.json -- required wave indicator.
- reports/deferred/non_blocking/launch-wave-native-stub-packet-contract-r3-2026-09-01_bridge_nonblockers.md -- optional same-wave non-blocking ledger; it cannot widen this attempt.
- TASKS.md -- tracker-sync authority. The 2026-09-01 tracker sync note for wave `launch-wave-native-stub-packet-contract-r3-2026-09-01` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/launch-wave-native-stub-packet-contract-r3-2026-09-01_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Reject incomplete ROUTE_PHASE_A structured inputs before packet, TASKS, routing, indicator, bridge-config, or staging mutation.
2. Define one version-1 native contract whose digest covers exact wave/task/title/date/tracked-packet identity, purpose, scope summary, ordered scope/work/constraint/stop/acceptance lists, exact evidence_command, and the exact ordered slow_functions list including the empty-list case.
3. Render the complete independently reviewable packet with exact header provenance lines identifying required=true, producer=launch_wave.py, version=1, and the computed contract digest. Validate those lines against the routing envelope and contract on every strict Phase A check; malformed, duplicate, missing, or mismatched provenance fails closed.
4. Before every route-specific early return or artifact mutation, inspect both working-tree and staged-index packet sources for any reserved native provenance footprint, including exact, missing-counterpart, or malformed marker/digest forms, and then require the exact aggregate contract. If any same-wave native provenance footprint is present, a later config with a different/no native envelope, route downgrade, identity, normative item, validation payload, or digest must return corrected-config-relaunch-required without changing any artifact or staged path.
5. Preserve deterministic reports/control_plane/{wave_id}_{date}.md naming. In Phase A, require plan_name to equal Path(contract.identity.tracked_packet).stem, not wave_id; all existing path containment, routing wave/task/candidate, digest, and packet identity checks remain mandatory.
6. Validate marked native purpose, scope, work, constraints, stops, acceptance, validation payload, packet provenance, and reserved lanes at load, after any reviewer edit, before every later review, and immediately before lock. Unmarked legacy/direct routes retain existing behavior.
7. Allow only exact reserved non-normative clarification and machine-owned post-lock lanes. Reject ATX level-1 headings, Setext level-1 headings, and Setext level-2 sibling headings inside clarification, while leaving ordinary clarification prose untouched and avoiding a general Markdown parser.
8. In tracker_sync_note.upsert_tracker_sync_note, identify each existing top-level tracker note plus all immediately associated blank and indented continuation lines as one logical block and insert a new note only after that block. Preserve all unrelated text byte-for-byte.
9. Carry the preserved R1 source/test implementation into this fresh attempt as read-only evidence, implement only the declared deltas, run focused and unfiltered three-file tests, then continue through Phase B, supervisor, commit, PR, CI, bot review, and merge.

## Constraints

- Do not change Phase B, meta_bridge supervisor/client, recovery, commit executor, dispatcher decisions, runtime, substrate, providers, Claude-owned files, PR disposition, or fleet cleanup.
- Do not hand-author or repair the generated packet downstream; launch_wave.py remains the sole producer and any normative correction requires another fresh builder attempt.
- Do not infer strict applicability from ROUTE_PHASE_A alone or migrate unmarked legacy/direct Phase A callers; only the exact packet/routing marker activates strict validation.
- Do not omit, normalize, shell-parse, or semantically compare evidence_command or slow_functions; preserve their exact structured values in the digest and exact rendered validation section.
- Do not add amendments, supersession, revision history, reviewer receipts, serialized semantic authority, or checkpoint migration.
- Do not generalize beyond the reproduced packet-only same-attempt replacement, validation binding, provenance, tracked-stem identity, clarification top-level authority, and shared tracker logical-block insertion defects.
- Do not address synthetic, non-occurring, pre-existing, unrelated, or newly hypothesized edge cases. Record them non_blocking without implementation under the landed convergence policy.
- Do not mutate or delete any preserved R1, stopped R2, or stopped authority-design worktree; they are read-only evidence.
- Commit execution remains providerless/null and every model-bearing role and pager remains Codex gpt-5.6-sol ultra.

## Stop conditions

- Stop before mutation on incomplete native input or any existing same-attempt packet whose marker, digest, route, identity, validation payload, or normative contract differs from the proposed config.
- Stop before review or lock on missing/duplicate/malformed/mismatched packet provenance, contract envelope, digest, validation payload, tracked-packet identity, or canonical section content; preserve unmarked legacy behavior.
- Stop rather than widening if any fix requires Phase B, meta review, recovery, commit, dispatcher, runtime, provider, or generalized Markdown/route changes.
- Stop and report without implementation for synthetic, not-occurring, unrelated, or newly hypothesized findings outside the explicitly reproduced blockers.
- Stop without commit-ready status if the exact evidence command fails or any path outside the allowlist changes.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py`

## Acceptance criteria

- Incomplete native structured input fails before all artifact and staging mutation; a valid config renders a complete packet before dispatch.
- The version-1 digest binds exact identity, purpose, scope summary, all five ordered normative lists, evidence_command, and ordered slow_functions; mutation of any bound value invalidates both builder and Phase A validation.
- The packet itself carries exactly one required/producer/version marker and exactly one digest marker matching the routing envelope, so packet-only interrupted attempts are mechanically distinguishable before routing exists.
- Any packet-only reserved native provenance footprint, including a missing-counterpart or malformed marker/digest form, followed by same-wave ROUTE_PHASE_B, missing native metadata, changed identity/normative/validation data, or another digest is rejected before packet, TASKS, routing, indicator, bridge-config, dispatch, or staging mutation; original bytes and staged paths remain unchanged.
- Dispatcher-derived plan_name equal to the canonical tracked-packet stem is accepted, any other plan_name fails before side effects, and deterministic dated packet naming remains unchanged.
- Marked aggregate validation reruns through load/edit/review/lock and rejects canonical content, validation payload, packet provenance, ATX-H1, Setext-H1, and Setext-H2 sibling-authority drift; ordinary reserved clarification and machine blocks remain allowed; unmarked routes remain compatible.
- Shared tracker upsert inserts after the complete existing tracker logical block across zero, one, or multiple intervening blank lines and indented evidence children, eliminating the reproduced TASKS reparenting without launch-specific duplication.
- Focused and unfiltered launch_wave, phase_a_executor, and tracker_sync_note_generation tests pass; L4 and exact staged-scope gates pass; no out-of-scope path changes.
- No synthetic or unrelated finding widens the candidate, and the normal commit executor merges the PR into dev while retaining all later PR/fleet queue rows in TASKS.md.

## Grounding / Authorization

- Task: [LAUNCH-WAVE-NATIVE-STUB-PACKET-CONTRACT-R1]; wave id `launch-wave-native-stub-packet-contract-r3-2026-09-01`.
- Governing packet: this file, `reports/control_plane/launch-wave-native-stub-packet-contract-r3-2026-09-01_2026-09-01.md`.
- TASKS.md authority: the 2026-09-01 tracker sync note for wave `launch-wave-native-stub-packet-contract-r3-2026-09-01` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:launch-wave-native-stub-packet-contract-r3-2026-09-01

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `launch-wave-native-stub-packet-contract-r3-2026-09-01`
- Active packet: `reports/control_plane/launch-wave-native-stub-packet-contract-r3-2026-09-01_2026-09-01.md`
- Indicator artifact: `reports/l4_wave_indicators/launch-wave-native-stub-packet-contract-r3-2026-09-01.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tests/tools/test_phase_a_executor.py`
  - `mu/tests/tools/test_tracker_sync_note_generation.py`
  - `mu/tools/executors/launch_wave.py`
  - `mu/tools/executors/phase_a_executor.py`
  - `mu/tools/executors/tracker_sync_note.py`
  - `reports/control_plane/launch-wave-native-stub-packet-contract-r3-2026-09-01_2026-09-01.md`
  - `reports/deferred/non_blocking/launch-wave-native-stub-packet-contract-r3-2026-09-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/launch-wave-native-stub-packet-contract-r3-2026-09-01.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `launch-wave-native-stub-packet-contract-r3-2026-09-01`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/launch-wave-native-stub-packet-contract-r3-2026-09-01_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/launch-wave-native-stub-packet-contract-r3-2026-09-01.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id launch-wave-native-stub-packet-contract-r3-2026-09-01 --output reports/l4_wave_indicators/launch-wave-native-stub-packet-contract-r3-2026-09-01.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/launch-wave-native-stub-packet-contract-r3-2026-09-01_2026-09-01.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_launch_wave.py`, `mu/tests/tools/test_phase_a_executor.py`, `mu/tests/tools/test_tracker_sync_note_generation.py`, `mu/tools/executors/launch_wave.py`, `mu/tools/executors/phase_a_executor.py`, `mu/tools/executors/tracker_sync_note.py`, `reports/control_plane/launch-wave-native-stub-packet-contract-r3-2026-09-01_2026-09-01.md`, `reports/deferred/non_blocking/launch-wave-native-stub-packet-contract-r3-2026-09-01_bridge_nonblockers.md`, `reports/l4_wave_indicators/launch-wave-native-stub-packet-contract-r3-2026-09-01.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: launch-wave-native-stub-packet-contract-r3-2026-09-01.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `launch-wave-native-stub-packet-contract-r3-2026-09-01`
- Active packet: `reports/control_plane/launch-wave-native-stub-packet-contract-r3-2026-09-01_2026-09-01.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `682f80346e5457a35d8ce5bc3523146b3e80ebad3485a1f787f1856198a2237b`
- Indicator artifact: `reports/l4_wave_indicators/launch-wave-native-stub-packet-contract-r3-2026-09-01.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/launch-wave-native-stub-packet-contract-r3-2026-09-01_2026-09-01.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_launch_wave.py`, `mu/tests/tools/test_phase_a_executor.py`, `mu/tests/tools/test_tracker_sync_note_generation.py`, `mu/tools/executors/launch_wave.py`, `mu/tools/executors/phase_a_executor.py`, `mu/tools/executors/tracker_sync_note.py`, `reports/control_plane/launch-wave-native-stub-packet-contract-r3-2026-09-01_2026-09-01.md`, `reports/deferred/non_blocking/launch-wave-native-stub-packet-contract-r3-2026-09-01_bridge_nonblockers.md`, `reports/l4_wave_indicators/launch-wave-native-stub-packet-contract-r3-2026-09-01.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/launch-wave-native-stub-packet-contract-r3-2026-09-01.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/launch-wave-native-stub-packet-contract-r3-2026-09-01_2026-09-01.md`
  - `reports/l4_wave_indicators/launch-wave-native-stub-packet-contract-r3-2026-09-01.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
