# Packet L4 Autopopulate From Tracker Note 2026-06-09

Date: 2026-06-09
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: packet-l4-autopopulate-from-tracker-note-2026-06-08
Phase-A-Lock: LOCKED
Purpose: GOAL: eliminate the recurring DOC_ACCURACY drift between a wave's control-plane packet (reports/control_plane/<wave>.md) and its TASKS.md tracker note, by making the packet's L4-field block AUTO-DERIVE from the canonical tracker note rather than from independently-supplied scope values. CONTEXT (verified): the packet is rendered by phase_a_executor.create_plan_draft -> _render_plan_draft_content(plan_name, scope, date_str), where the L4-fields come from the `scope` dict; the tracker note (TASKS.md) carries the SAME L4-fields via tracker_sync_note.TrackerSyncNoteFields / render_tracker_sync_note, and the pre-commit supervisor + bot read the TRACKER NOTE as the source of truth (this session, waves #57 and #41 both ate DOC_ACCURACY/NEEDS_PHASE_B rounds when the packet/tracker note L4 wording diverged). The L4-field set: primary_blocker_class, primary_invariant_id, indicator_artifact_ref, indicator_collection_command, target_gate_id, evidence_command, evidence_delta, bootstrap_endgame_policy, boot0_track_id, boot0_progress_state, founder_override (the same fields TrackerSyncNoteFields validates). REQUIRED FIX (single-source derivation, narrow): make the packet renderer/refresh DERIVE the packet's L4-field block from the canonical tracker note for the wave -- i.e., parse the wave's TASKS.md tracker note via commit_executor's existing tracker-note marker extractors (the public `tracker_marker_value` seam over `_tracker_marker_value`, with `_extract_existing_canonical_tracker_note_from_tasks` supplying the canonical note text), keyed to the `tracker_sync_note.TrackerSyncNoteFields` field set, and render the packet's L4-field section FROM those parsed values, so the packet doc cannot declare an L4 value that differs from the tracker note. Apply at BOTH render points where the packet's L4-fields are written: phase_a_executor (create_plan_draft / _render_plan_draft_content) and commit_executor's packet-truth refresh (`refresh_commit_path_packet_truth`, Step 5c, step-id `refresh_commit_packet_truth`). Where the tracker note does not yet exist at initial render (create_plan_draft runs before the note in some flows), keep the supplied scope values BUT ensure the refresh path reconciles the packet to the note (note wins) before the supervisor reads it -- the invariant is: at supervisor time, packet L4-fields == tracker note L4-fields. Do NOT invent new L4 semantics; reuse the existing `tracker_sync_note.TrackerSyncNoteFields` field definitions plus commit_executor's tracker-note marker extractors as the single source. SCOPE: mu/tools/executors/phase_a_executor.py + mu/tools/executors/commit_executor.py (owns the tracker-note marker extractors + the refresh path) + (read-only field-set reuse of) mu/tools/executors/tracker_sync_note.py; the wave's regression test MUST go in the EXISTING mu/tests/tools/test_phase_a_executor.py (the file the declared evidence_command runs), NOT a new test file. Do NOT touch runtime dirs (mu/host, mu/substrate, mu/closures, mu/bridge, mu/programs, rcx_pi/selfhost, mu/tools/compilers). HARD CONSTRAINT: no masking; do not weaken existing packet/tracker tests. PROVE (regression in mu/tests/tools/test_phase_a_executor.py): given a wave whose tracker note declares L4 values X, the rendered/refreshed packet's L4-field block equals X (and a deliberately-divergent supplied value is overridden by the tracker note at refresh, never the reverse). L4_ENABLER.

## Scope

L4_ENABLER: stop packet-vs-tracker-note L4 DOC_ACCURACY drift by deriving the control-plane packet's L4-field block from the canonical TASKS.md tracker note (single source) at render + refresh. The supervisor/bot read the tracker note as truth; this session #57 and #41 ate DOC_ACCURACY/NEEDS_PHASE_B rounds when the packet/note L4 wording diverged. Fix: phase_a_executor (create_plan_draft/_render_plan_draft_content) + commit_executor (refresh_commit_path_packet_truth, Step 5c) derive the L4-field block from the parsed tracker note (parse via commit_executor's `tracker_marker_value` seam, keyed to tracker_sync_note.TrackerSyncNoteFields field-set), invariant = at supervisor time packet L4-fields == tracker note L4-fields (note wins on divergence). Regression in the EXISTING mu/tests/tools/test_phase_a_executor.py (no new test file; matches the declared evidence_command). No masking; tooling-only, NO runtime dirs.

In-scope files:
- `mu/tools/executors/phase_a_executor.py` (initial packet render: `create_plan_draft` / `_render_plan_draft_content`)
- `mu/tools/executors/commit_executor.py` (packet-truth refresh: `refresh_commit_path_packet_truth`, Step 5c / step-id `refresh_commit_packet_truth`; ALSO the home of the tracker-note marker extractors `tracker_marker_value` / `_tracker_marker_value` and the canonical-note reader `_extract_existing_canonical_tracker_note_from_tasks`)
- `mu/tools/executors/tracker_sync_note.py` (READ-ONLY field-set reuse: `TrackerSyncNoteFields` defines WHICH L4-fields exist and `render_tracker_sync_note` is the render/build direction; this module does NOT contain marker extractors — extraction/parse lives in `commit_executor.py`)
- the EXISTING `mu/tests/tools/test_phase_a_executor.py` for the regression (the one file the declared `evidence_command` runs) — NO new test file

L4-field set under single-source derivation (the same fields `TrackerSyncNoteFields` validates): `primary_blocker_class`, `primary_invariant_id`, `indicator_artifact_ref`, `indicator_collection_command`, `target_gate_id`, `evidence_command`, `evidence_delta`, `bootstrap_endgame_policy`, `boot0_track_id`, `boot0_progress_state`, `founder_override`.

- `reports/deferred/non_blocking/packet-l4-autopopulate-from-tracker-note-2026-06-08_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. **phase_a_executor render** — In `create_plan_draft` / `_render_plan_draft_content`, when the wave's TASKS.md tracker note already exists, derive the packet's L4-field block from it by parsing the note with `commit_executor`'s public `tracker_marker_value` marker-extraction seam (keyed to the `tracker_sync_note.TrackerSyncNoteFields` field set), and render the L4-field block FROM those parsed values. Reusing that public seam here is import-safe: `commit_executor` does not import `phase_a_executor`, so the dependency is one-way with no cycle. When the tracker note does not yet exist at initial render (create_plan_draft can run before the note in some flows), keep the supplied `scope` values as the initial draft — the refresh path reconciles later.
2. **commit_executor refresh** — In `refresh_commit_path_packet_truth` (Step 5c; step-id `refresh_commit_packet_truth`), reconcile the packet's L4-field block to the canonical tracker note before the pre-commit supervisor reads the packet. This path already receives the canonical `tracker_note_text` and already owns the in-module marker extractors (`tracker_marker_value` / `_tracker_marker_value`), so derivation here needs no new dependency. Note wins on divergence; never the reverse. This establishes the invariant: at supervisor time, packet L4-fields == tracker note L4-fields.
3. **tracker_sync_note reuse (read-only)** — Reuse `tracker_sync_note.TrackerSyncNoteFields` as the single definition of WHICH L4-fields exist (the field set the derived block must cover — no more, no less). The marker EXTRACTORS that parse field VALUES out of the note are NOT in this module — they live in `commit_executor.py` (`tracker_marker_value` / `_tracker_marker_value`). Do NOT add new L4 fields or new L4 semantics; no behavioral edits to `tracker_sync_note.py`.
4. **Regression test (existing file)** — Add a regression to the EXISTING `mu/tests/tools/test_phase_a_executor.py` (the one file the declared `evidence_command` runs), with test names discoverable by `-k 'packet and (l4 or tracker)'`. The test may `import commit_executor` to exercise the refresh path while physically residing in `test_phase_a_executor.py`, so the proof command actually collects it. Prove: given a wave whose tracker note declares L4 values X, the rendered AND refreshed packet's L4-field block equals X; a deliberately-divergent supplied value is overridden by the tracker note at refresh (note wins, never the reverse).

## Constraints

- MUST NOT touch runtime dirs: `mu/host`, `mu/substrate`, `mu/closures`, `mu/bridge`, `mu/programs`, `rcx_pi/selfhost`, `mu/tools/compilers` (L4_ENABLER requirement).
- NO new test file — the regression MUST live in the existing `mu/tests/tools/test_phase_a_executor.py` (the file the declared `evidence_command` runs), so the proof command actually collects it.
- Do NOT invent new L4 semantics or add fields beyond the existing `TrackerSyncNoteFields` set; `tracker_sync_note.py` is read-only field-set reuse only (no marker extractor lives there to modify).
- No masking: do NOT weaken, skip, or delete existing packet/tracker tests to make the new test pass.
- Tooling-only: no runtime/substrate semantic change, so no L3 (Python/JS) parity surface is touched.

## Stop conditions

- STOP when the evidence_command passes AND the packet's L4-field block provably derives from the canonical tracker note at BOTH render (phase_a_executor) and refresh (commit_executor), with note-wins-on-divergence.
- STOP and request a founder/reviewer decision if single-source derivation cannot be done without touching a runtime dir or without adding a new `tracker_sync_note` field — that would mean the narrow scope is wrong; do NOT widen scope unilaterally.
- STOP and escalate if making the new test pass would require weakening an existing packet/tracker test (masking).
- Do NOT proceed past the three named source files + the one existing test file (`mu/tests/tools/test_phase_a_executor.py`).

## Acceptance criteria

- `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_a_executor.py` passes (the wave's declared evidence_command).
- Given a tracker note declaring L4 values X, the phase_a render path and the commit_executor refresh path each produce a packet L4-field block equal to X.
- A deliberately-divergent supplied `scope` value is overridden by the tracker note at refresh (note wins; the reverse never occurs).
- Pre-existing packet/tracker regression tests remain green (no weakening/masking).
- No file under a runtime dir is modified; no new test file is created.

## Grounding / Authorization

- Task `[NEXT-CODEX-POST-REDTEAM]`, authorized by the TASKS.md tracker sync note (2026-06-09, `packet-l4-autopopulate-from-tracker-note-2026-06-08`).
- Governing packet: this file (`reports/control_plane/packet_l4_autopopulate_from_tracker_note_2026-06-09.md`).
- Class: `L4_ENABLER`.
- Same-wave override (control-surface `L4_ENABLER` requirement): the wave's canonical TASKS.md tracker note (2026-06-09, `packet-l4-autopopulate-from-tracker-note-2026-06-08`) carries no per-note `FOUNDER_OVERRIDE:packet-l4-autopopulate-from-tracker-note-2026-06-08 (standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md; auto-appended by build_commit_handoff for commit-gate + pre-push adjacency-cap clearance)` token, so the auto-derived `founder_override` L4 field below intentionally stays empty — that field mirrors the note (note wins; no packet/note drift) and is a distinct surface from the packet-level standing authorization in the next bullet.
- Authorization: standing pipeline-bug-fix authorization (per memory `feedback_autonomous_executor_fix.md` — standing auth for autonomous executor pipeline bug fixes). This wave qualifies: it is a tooling-only `L4_ENABLER` fix to the phase_a/commit executor packet-vs-tracker-note L4 derivation, touching no runtime dirs. From this standing authorization, commit automation derives the wave-bound same-wave override token FOUNDER_OVERRIDE:packet-l4-autopopulate-from-tracker-note-2026-06-08 for commit-gate + pre-push adjacency-cap clearance (the same build_commit_handoff mechanism that annotated the sibling evidence-command-failclosed-unbacktick-2026-06-08 tracker note).
- L4 authority fields, single-sourced from the canonical TASKS.md tracker note for this wave (this packet is itself an instance of the drift the wave fixes, so its L4 block AUTO-DERIVES from the note; note wins on any divergence):

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/packet-l4-autopopulate-from-tracker-note-2026-06-08.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id packet-l4-autopopulate-from-tracker-note-2026-06-08 --output reports/l4_wave_indicators/packet-l4-autopopulate-from-tracker-note-2026-06-08.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_a_executor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/packet_l4_autopopulate_from_tracker_note_2026-06-09.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: packet-l4-autopopulate-from-tracker-note-2026-06-08 (standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md; auto-appended by build_commit_handoff for commit-gate + pre-push adjacency-cap clearance)
<!-- L4_FIELDS_FROM_TRACKER:end -->

## Request from Post-Merge Supervisor

_NOTE (Phase-A design reconciliation): the routed request below is reproduced verbatim as received. Where its implementation pointers conflict with current code truth, the Scope / Work items above govern: tracker-note marker EXTRACTION lives in `commit_executor.py` (`tracker_marker_value` / `_tracker_marker_value`, `_extract_existing_canonical_tracker_note_from_tasks`), NOT in `tracker_sync_note.py` (which owns only the `TrackerSyncNoteFields` field-set and the `render_tracker_sync_note` render direction); the refresh function is `refresh_commit_path_packet_truth` (Step 5c); and the single regression file is `mu/tests/tools/test_phase_a_executor.py`, matching the declared `evidence_command`._

GOAL: eliminate the recurring DOC_ACCURACY drift between a wave's control-plane packet (reports/control_plane/<wave>.md) and its TASKS.md tracker note, by making the packet's L4-field block AUTO-DERIVE from the canonical tracker note rather than from independently-supplied scope values. CONTEXT (verified): the packet is rendered by phase_a_executor.create_plan_draft -> _render_plan_draft_content(plan_name, scope, date_str), where the L4-fields come from the `scope` dict; the tracker note (TASKS.md) carries the SAME L4-fields via tracker_sync_note.TrackerSyncNoteFields / render_tracker_sync_note, and the pre-commit supervisor + bot read the TRACKER NOTE as the source of truth (this session, waves #57 and #41 both ate DOC_ACCURACY/NEEDS_PHASE_B rounds when the packet/tracker note L4 wording diverged). The L4-field set: primary_blocker_class, primary_invariant_id, indicator_artifact_ref, indicator_collection_command, target_gate_id, evidence_command, evidence_delta, bootstrap_endgame_policy, boot0_track_id, boot0_progress_state, founder_override (the same fields TrackerSyncNoteFields validates). REQUIRED FIX (single-source derivation, narrow): make the packet renderer/refresh DERIVE the packet's L4-field block from the canonical tracker note for the wave -- i.e., parse the wave's TASKS.md tracker note (via the existing tracker_sync_note marker extractors / TrackerSyncNoteFields) and render the packet's L4-field section FROM those parsed values, so the packet doc cannot declare an L4 value that differs from the tracker note. Apply at BOTH render points where the packet's L4-fields are written: phase_a_executor (create_plan_draft / _render_plan_draft_content) and commit_executor's packet-truth refresh (refresh_commit_packet_truth, Step 5c). Where the tracker note does not yet exist at initial render (create_plan_draft runs before the note in some flows), keep the supplied scope values BUT ensure the refresh path reconciles the packet to the note (note wins) before the supervisor reads it -- the invariant is: at supervisor time, packet L4-fields == tracker note L4-fields. Do NOT invent new L4 semantics; reuse the existing tracker_sync_note field definitions + extractors as the single source. SCOPE: mu/tools/executors/phase_a_executor.py + mu/tools/executors/commit_executor.py + (read-only reuse of) mu/tools/executors/tracker_sync_note.py; the wave's regression test MUST go in an EXISTING mu/tests/tools test file (e.g. an existing test_phase_a_executor.py or test_commit_executor_*.py), NOT a new test file. Do NOT touch runtime dirs (mu/host, mu/substrate, mu/closures, mu/bridge, mu/programs, rcx_pi/selfhost, mu/tools/compilers). HARD CONSTRAINT: no masking; do not weaken existing packet/tracker tests. PROVE (regression in an existing test file): given a wave whose tracker note declares L4 values X, the rendered/refreshed packet's L4-field block equals X (and a deliberately-divergent supplied value is overridden by the tracker note at refresh, never the reverse). L4_ENABLER.

Routed next-candidate:
packet-l4-autopopulate-from-tracker-note-2026-06-08

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `packet-l4-autopopulate-from-tracker-note-2026-06-08`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/packet-l4-autopopulate-from-tracker-note-2026-06-08_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `packet-l4-autopopulate-from-tracker-note-2026-06-08`
- Active packet: `reports/control_plane/packet_l4_autopopulate_from_tracker_note_2026-06-09.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `f17392220332392f1526e446394e6e1229734c5843c1a54cdab85e87f9f9e067`
- Indicator artifact: `reports/l4_wave_indicators/packet-l4-autopopulate-from-tracker-note-2026-06-08.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_a_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/packet_l4_autopopulate_from_tracker_note_2026-06-09.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/packet-l4-autopopulate-from-tracker-note-2026-06-08.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_a_executor.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/phase_a_executor.py`
  - `reports/control_plane/packet_l4_autopopulate_from_tracker_note_2026-06-09.md`
  - `reports/deferred/non_blocking/packet-l4-autopopulate-from-tracker-note-2026-06-08_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/packet-l4-autopopulate-from-tracker-note-2026-06-08.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
