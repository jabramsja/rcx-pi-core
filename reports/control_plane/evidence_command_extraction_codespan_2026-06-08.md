# Evidence Command Extraction Codespan 2026-06-08

Date: 2026-06-08
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: evidence-command-extraction-codespan-2026-06-08
Phase-A-Lock: LOCKED
Purpose: Harden tracker-note marker extraction against a latent fail-open in the UN-backtick-wrapped case. CONTEXT (verified): _tracker_marker_value is DUPLICATED in mu/tools/executors/commit_executor.py and mu/tools/agents/meta_bridge_supervisor.py (mu/tools/executors/phase_b_executor.py._tracker_evidence_command_value delegates to commit_executor's). BOTH track backtick inline-code spans, so a backtick-wrapped evidence_command extracts in FULL (verified OK: `grep -q "evidence_delta: x" f && grep -q boot0_track_id g` extracts intact). BUG (verified by direct call): for an UN-backtick-wrapped value that contains a marker-name substring like evidence_delta:, both extractors TRUNCATE the value at that substring -- e.g. note text `evidence_command: python3 x.py --note evidence_delta:foo done. evidence_delta: real.` extracts `python3 x.py --note` (TRUNCATED, dropping the rest of the real command); and for `evidence_command: python3 -m pytest -q && echo ok. evidence_delta: real.` the trailing sentence period is included (`... && echo ok.`). This is a LATENT FAIL-OPEN: the #52 pre-merge supervisor path (meta_bridge_supervisor._extract_tracker_note_evidence_command -> _run_wave_evidence_with_restore) RUNS the extracted evidence_command, so a truncated command can PASS where the full command would FAIL, letting a broken wave merge. REQUIRED FIX: harden BOTH duplicated _tracker_marker_value implementations identically (prefer unifying onto ONE shared helper imported by both, if that does not create an import cycle; otherwise fix both with identical logic and a test asserting they agree) so that (1) an un-backtick-wrapped value is NOT truncated at an embedded marker-name substring -- only a GENUINE next-marker boundary (the documented note structure) ends the value; (2) a trailing sentence period on the final marker value is stripped; (3) backtick-wrapped extraction behavior is preserved unchanged. Consider whether the most robust structural fix is to also have the tracker-note BUILDER (tracker_sync_note.render_tracker_sync_note) guarantee backtick-wrapping of evidence_command (so the parser never sees an un-wrapped command) -- if so, implement BOTH the parser hardening and the builder guarantee. ADD regression tests at mu/tests/tools/test_tracker_marker_codespan_extraction.py covering: backtick-wrapped command with embedded marker text and && chain (full extract), un-backtick-wrapped command with embedded marker-name substring (no truncation), trailing-period strip, genuine next-marker boundary still splits, and (if unified) both extractors agree. SCOPE: mu/tools/executors/commit_executor.py + mu/tools/agents/meta_bridge_supervisor.py (+ mu/tools/executors/phase_b_executor.py and mu/tools/executors/tracker_sync_note.py ONLY if unifying/adding the builder guarantee) + the new test file. Do NOT touch any runtime dir (mu/host, rcx_pi/selfhost, etc.). L4_ENABLER.

## Scope

L4_ENABLER: harden duplicated `_tracker_marker_value` (commit_executor + meta_bridge_supervisor) against the un-backtick-wrapped evidence_command fail-open -- proven truncation at an embedded marker-name substring + trailing-period inclusion; the #52 supervisor RUNS the extracted command so truncation is a latent fail-open. Pipeline tooling only; no runtime dirs.

Files/directories in scope:
- `mu/tools/executors/commit_executor.py` -- one of the two duplicated `_tracker_marker_value` implementations (the canonical one; `phase_b_executor` delegates here).
- `mu/tools/agents/meta_bridge_supervisor.py` -- the second duplicated `_tracker_marker_value`; this is the surface the #52 pre-merge supervisor uses to extract and RUN the evidence_command.
- `mu/tests/tools/test_tracker_marker_codespan_extraction.py` -- NEW regression test file.
- Conditional, ONLY if unifying onto a shared helper or adding the builder guarantee:
  - `mu/tools/executors/phase_b_executor.py` -- delegates to commit_executor's extractor; touched only if the delegation target moves to a shared helper.
  - `mu/tools/executors/tracker_sync_note.py` -- `render_tracker_sync_note` builder; touched only to guarantee backtick-wrapping of evidence_command.

- `reports/deferred/non_blocking/evidence-command-extraction-codespan-2026-06-08_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Harden the duplicated `_tracker_marker_value` extraction in `mu/tools/executors/commit_executor.py` and `mu/tools/agents/meta_bridge_supervisor.py` so that, for an UN-backtick-wrapped value, the value is NOT truncated at an embedded marker-name substring (e.g. a literal `evidence_delta:` inside the command text). Only a GENUINE next-marker boundary, per the documented tracker-note structure, ends the value.
2. Strip a trailing sentence period from the final marker value so `... && echo ok.` does not carry the closing `.` into the executed command.
3. Preserve backtick-wrapped extraction behavior UNCHANGED: a backtick-wrapped command with embedded marker text and an `&&` chain must still extract in full, byte-identical to current output.
4. Apply the fix to BOTH implementations identically. Prefer unifying onto ONE shared helper imported by both, IF that does not create an import cycle; otherwise fix both with identical logic and add a test asserting the two extractors agree on the same input.
5. (Conditional, structural-robustness) Evaluate having the tracker-note BUILDER `tracker_sync_note.render_tracker_sync_note` guarantee backtick-wrapping of evidence_command so the parser never sees an un-wrapped command. If adopted, implement BOTH the parser hardening (items 1-4) AND the builder guarantee.
6. Add regression tests at `mu/tests/tools/test_tracker_marker_codespan_extraction.py` covering: (a) backtick-wrapped command with embedded marker text and `&&` chain extracts in full; (b) un-backtick-wrapped command with an embedded marker-name substring is NOT truncated; (c) trailing-period strip; (d) a genuine next-marker boundary still splits the value; (e) if unified, both extractors agree.

## Constraints

What is NOT in scope:
- Do NOT touch any runtime directory: `mu/host`, `rcx_pi/selfhost`, Stage0/lowering paths, seeds, registries, parity, host-oracle, or any other substrate/runtime surface. L4_ENABLER MUST NOT touch runtime dirs.
- Do NOT touch `mu/tools/executors/phase_b_executor.py` or `mu/tools/executors/tracker_sync_note.py` UNLESS the chosen approach unifies onto a shared helper (phase_b_executor) or adds the builder backtick-wrapping guarantee (tracker_sync_note). Absent those, leave both untouched.
- Do NOT change the extraction output for any existing backtick-wrapped case (parity-preserving boundary tightening only).
- Do NOT widen scope beyond the files listed in Scope plus the new test file.
- No Claude-related file edits; no docs/governance restructuring beyond this packet.

## Stop conditions

- If unifying onto a shared helper would create an import cycle, STOP unifying and fall back to fixing both implementations with identical logic plus an agreement test.
- If any proposed change alters the extraction output of an existing backtick-wrapped case, STOP and revise -- constraint (work item 3) is non-negotiable.
- If the fix cannot be achieved without editing a runtime directory, STOP and escalate; do not proceed (L4_ENABLER runtime-dir prohibition).
- If the builder-guarantee path would change the emitted tracker-note format in a way that breaks parsing of already-committed notes, STOP and keep parser-only hardening.
- Phase A boundary: STOP after this packet carries the required Phase A sections and the bridge converges. Do NOT implement the parser/builder/test changes in Phase A; implementation belongs to Phase B via the executor pipeline.

## Acceptance criteria

- The wave evidence_command passes (exit 0): `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_tracker_marker_codespan_extraction.py`.
- An un-backtick-wrapped value containing an embedded marker-name substring extracts in FULL (no truncation at the substring).
- A trailing sentence period on the final marker value is stripped from the extracted command.
- Backtick-wrapped extraction output is unchanged for all pre-existing cases (full extract of embedded-marker + `&&` chain commands).
- A genuine next-marker boundary still ends the current marker value (no over-reading into the next marker).
- Both `_tracker_marker_value` implementations behave identically; if unified, a test asserts they agree; if not unified, both carry identical logic plus an agreement test.
- L4_ENABLER contract holds: no runtime directories touched; `target_gate_id` G8; `evidence_command` and `evidence_delta` present and satisfied.
- `./tools/audit_fast.sh` is green.

## Grounding / Authorization

- Task authority: `[NEXT-CODEX-POST-REDTEAM]` in `TASKS.md` -- UNPARKED (2026-03-28, founder-authorized) structural queue.
- Same-wave authorization: the `TASKS.md` tracker sync note "(2026-06-08, evidence-command-extraction-codespan-2026-06-08)" authorizes this wave and carries its full L4 metadata; this packet's Grounding mirrors that note (the blocking finding required this packet to reference that TASKS.md authorization in its own grounding section).
- Governing packet: this file, `reports/control_plane/evidence_command_extraction_codespan_2026-06-08.md`, named by the tracker note's `Packet:` field.
- Semantic/contract policy: L4 Execution Contract (`roadmap/L4ExecutionContract.v2.md`); L4_ENABLER must not touch runtime dirs and requires `target_gate_id` + `evidence_command` + `evidence_delta`.

L4_ENABLER metadata (mirrored from the same-wave TASKS.md tracker note):
- Class: L4_ENABLER
- target_gate_id: G8
- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_tracker_marker_codespan_extraction.py`
- evidence_delta: Both `_tracker_marker_value` implementations (commit_executor.py + meta_bridge_supervisor.py) no longer truncate an un-backtick-wrapped evidence_command at an embedded marker-name substring and strip a trailing sentence period, so the #52 pre-merge supervisor runs the FULL declared command instead of a silently-truncated one. New regression suite mu/tests/tools/test_tracker_marker_codespan_extraction.py covers the adversarial cases.
- progress_proof_before: Both `_tracker_marker_value` extractors truncate an un-backtick-wrapped evidence_command at an embedded marker-name substring (verified: `python3 x.py --note evidence_delta:foo done` extracts `python3 x.py --note`); the #52 supervisor would run the truncated command (latent fail-open).
- progress_proof_after: The extractors handle un-backtick-wrapped values without truncating at embedded marker substrings and strip a trailing period; a regression suite proves the adversarial cases; the #52 supervisor runs the full declared evidence_command.
- primary_blocker_class: INTEGRATION
- primary_invariant_id: INV_TYPED_FAIL_CLOSED_OUTCOMES
- indicator_artifact_ref: reports/l4_wave_indicators/evidence-command-extraction-codespan-2026-06-08.json
- indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id evidence-command-extraction-codespan-2026-06-08 --output reports/l4_wave_indicators/evidence-command-extraction-codespan-2026-06-08.json
- bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP
- boot0_track_id: V1
- boot0_progress_state: HOLD

FOUNDER_OVERRIDE:evidence-command-extraction-codespan-2026-06-08
Authorization: standing pipeline-bug-fix authorization -- this wave fixes a latent fail-open in pipeline control tooling (tracker-note evidence_command extraction shared by commit_executor and the #52 pre-merge supervisor); the wave-bound FOUNDER_OVERRIDE above is the authoritative same-wave override commit automation derives mechanically.

## Request from Post-Merge Supervisor

Harden tracker-note marker extraction against a latent fail-open in the UN-backtick-wrapped case. CONTEXT (verified): _tracker_marker_value is DUPLICATED in mu/tools/executors/commit_executor.py and mu/tools/agents/meta_bridge_supervisor.py (mu/tools/executors/phase_b_executor.py._tracker_evidence_command_value delegates to commit_executor's). BOTH track backtick inline-code spans, so a backtick-wrapped evidence_command extracts in FULL (verified OK: `grep -q "evidence_delta: x" f && grep -q boot0_track_id g` extracts intact). BUG (verified by direct call): for an UN-backtick-wrapped value that contains a marker-name substring like evidence_delta:, both extractors TRUNCATE the value at that substring -- e.g. note text `evidence_command: python3 x.py --note evidence_delta:foo done. evidence_delta: real.` extracts `python3 x.py --note` (TRUNCATED, dropping the rest of the real command); and for `evidence_command: python3 -m pytest -q && echo ok. evidence_delta: real.` the trailing sentence period is included (`... && echo ok.`). This is a LATENT FAIL-OPEN: the #52 pre-merge supervisor path (meta_bridge_supervisor._extract_tracker_note_evidence_command -> _run_wave_evidence_with_restore) RUNS the extracted evidence_command, so a truncated command can PASS where the full command would FAIL, letting a broken wave merge. REQUIRED FIX: harden BOTH duplicated _tracker_marker_value implementations identically (prefer unifying onto ONE shared helper imported by both, if that does not create an import cycle; otherwise fix both with identical logic and a test asserting they agree) so that (1) an un-backtick-wrapped value is NOT truncated at an embedded marker-name substring -- only a GENUINE next-marker boundary (the documented note structure) ends the value; (2) a trailing sentence period on the final marker value is stripped; (3) backtick-wrapped extraction behavior is preserved unchanged. Consider whether the most robust structural fix is to also have the tracker-note BUILDER (tracker_sync_note.render_tracker_sync_note) guarantee backtick-wrapping of evidence_command (so the parser never sees an un-wrapped command) -- if so, implement BOTH the parser hardening and the builder guarantee. ADD regression tests at mu/tests/tools/test_tracker_marker_codespan_extraction.py covering: backtick-wrapped command with embedded marker text and && chain (full extract), un-backtick-wrapped command with embedded marker-name substring (no truncation), trailing-period strip, genuine next-marker boundary still splits, and (if unified) both extractors agree. SCOPE: mu/tools/executors/commit_executor.py + mu/tools/agents/meta_bridge_supervisor.py (+ mu/tools/executors/phase_b_executor.py and mu/tools/executors/tracker_sync_note.py ONLY if unifying/adding the builder guarantee) + the new test file. Do NOT touch any runtime dir (mu/host, rcx_pi/selfhost, etc.). L4_ENABLER.

Routed next-candidate:
evidence-command-extraction-codespan-2026-06-08

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `evidence-command-extraction-codespan-2026-06-08`
- Active packet: `reports/control_plane/evidence_command_extraction_codespan_2026-06-08.md`
- Indicator artifact: `reports/l4_wave_indicators/evidence-command-extraction-codespan-2026-06-08.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_tracker_marker_codespan_extraction.py`
  - `mu/tools/agents/meta_bridge_supervisor.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/evidence_command_extraction_codespan_2026-06-08.md`
  - `reports/deferred/non_blocking/evidence-command-extraction-codespan-2026-06-08_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/evidence-command-extraction-codespan-2026-06-08.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `evidence-command-extraction-codespan-2026-06-08`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/evidence-command-extraction-codespan-2026-06-08_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `evidence-command-extraction-codespan-2026-06-08`
- Active packet: `reports/control_plane/evidence_command_extraction_codespan_2026-06-08.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `53b4b698fd82336f3754107a81cc9d55c96833b993024b64941d430b5bd18c78`
- Indicator artifact: `reports/l4_wave_indicators/evidence-command-extraction-codespan-2026-06-08.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/tools/test_tracker_marker_codespan_extraction.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/evidence_command_extraction_codespan_2026-06-08.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/evidence-command-extraction-codespan-2026-06-08.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_tracker_marker_codespan_extraction.py`
  - `mu/tools/agents/meta_bridge_supervisor.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/evidence_command_extraction_codespan_2026-06-08.md`
  - `reports/deferred/non_blocking/evidence-command-extraction-codespan-2026-06-08_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/evidence-command-extraction-codespan-2026-06-08.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
