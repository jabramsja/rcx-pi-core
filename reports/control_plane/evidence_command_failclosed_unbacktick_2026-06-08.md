# Evidence Command Failclosed Unbacktick 2026-06-08

Date: 2026-06-08
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: evidence-command-failclosed-unbacktick-2026-06-08
Phase-A-Lock: LOCKED
Class: L4_ENABLER
target_gate_id: G8
Purpose: GOAL: close the residual fail-open in tracker-note evidence_command extraction WITHOUT adding another fragile free-text boundary heuristic. CONTEXT (verified): the pre-commit supervisor (#52) RUNS a wave's tracker-declared evidence_command and, before running, compares two values extracted by `_tracker_marker_value` (commit_executor.py) / its byte-identical mirror in meta_bridge_supervisor.py. PR #1086 made extraction code-span-aware for BACKTICK-WRAPPED values (correct, keep it), but for an UN-BACKTICK-wrapped value a codex bot P2 showed the boundary check still truncates at an embedded marker-name substring: e.g. an un-backtick evidence_command `echo ok. evidence_delta:foo && false. evidence_delta: real.` stops at the embedded `. evidence_delta:` and both extractors return only `echo ok`; since both sides truncate identically the compare PASSES and the supervisor runs the truncated (passing) `echo ok` instead of the full (failing) command -- a fail-open for manually-authored or legacy unwrapped tracker notes. There is NO reliable text-only way to tell an embedded `. marker:` inside a shell command from a real next-field boundary, so do NOT extend the heuristic (that is the open-ended-surface trap that diverges). REQUIRED FIX (narrow, fail-closed): the canonical builder (tracker_sync_note.render_tracker_sync_note) ALWAYS backtick-wraps the evidence_command value, so a NON-backtick-wrapped evidence_command is non-canonical. Make `_tracker_marker_value`/`_tracker_evidence_command_value`/`_strip_tracker_inline_code` (and the byte-identical meta_bridge_supervisor copies) treat an un-backtick-wrapped evidence_command as INVALID: return a sentinel/empty that causes the supervisor's evidence-command path to FAIL-CLOSED (reject the note / route NEEDS_PHASE_B) rather than silently truncating at an embedded marker substring. Keep the existing backtick-wrapped (code-span-aware) extraction behavior byte-for-byte (it is the canonical path and is already pinned). L4_ENABLER.

## Scope

In scope (tooling only -- exactly three files):

- `mu/tools/executors/commit_executor.py` -- extractor copy 1 (`_tracker_marker_value` / `_tracker_evidence_command_value` / `_strip_tracker_inline_code`).
- `mu/tools/agents/meta_bridge_supervisor.py` -- extractor copy 2, byte-identical mirror of the above helpers (a test pins byte-identity; both copies change together).
- `mu/tests/tools/test_tracker_marker_codespan_extraction.py` -- regression coverage for the bot P2 counterexample + canonical-path-unchanged assertions.

Goal of the change: an un-backtick-wrapped `evidence_command` value is treated as non-canonical and the extractor returns a sentinel/empty so the supervisor's evidence-command path FAILS CLOSED (reject -> NEEDS_PHASE_B) instead of silently truncating at an embedded `. marker:` substring. The backtick-wrapped (code-span-aware) canonical path is unchanged byte-for-byte. Supersedes the blocked PR #1086.

- `reports/deferred/non_blocking/evidence-command-failclosed-unbacktick-2026-06-08_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Concrete bounded tasks (none proven landed by the blocking-finding evidence; progress_proof_before in TASKS.md:513 confirms the un-backtick fail-open is still OPEN, PR #1086 OPEN+DIRTY and superseded):

1. **Fail-closed on un-backtick `evidence_command`.** Update `_tracker_marker_value` / `_tracker_evidence_command_value` / `_strip_tracker_inline_code` so that when the `evidence_command` field value is NOT backtick-wrapped, the extractor returns a sentinel/empty that routes the supervisor's evidence-command path to FAIL-CLOSED (reject the note / NEEDS_PHASE_B) rather than truncating at an embedded marker-name substring. No new free-text boundary heuristic.
2. **Apply the identical change to both byte-identical copies.** Make the same edit in `mu/tools/executors/commit_executor.py` and `mu/tools/agents/meta_bridge_supervisor.py` together so the byte-identity invariant (pinned by the regression test) stays green.
3. **Preserve the canonical backtick-wrapped path byte-for-byte.** Do not alter the existing code-span-aware extraction for backtick-wrapped values; it is the canonical builder's output (`tracker_sync_note.render_tracker_sync_note` always backtick-wraps) and is already pinned.
4. **Add the regression test** in `mu/tests/tools/test_tracker_marker_codespan_extraction.py` covering the bot P2 counterexample (`echo ok. evidence_delta:foo && false. evidence_delta: real.` un-backtick -> fail-closed, NOT truncated-to-`echo ok`) AND asserting the canonical backtick-wrapped path is unchanged.

## Constraints

NOT in scope / forbidden:

- **No runtime dirs.** Do NOT touch `mu/host`, `mu/substrate`, `mu/closures`, `mu/bridge`, `mu/programs`, `rcx_pi/selfhost`, or `mu/tools/compilers`. This wave is tooling-only (L4_ENABLER MUST NOT touch runtime dirs).
- **No new boundary heuristic.** Do NOT extend the embedded-`. marker:` boundary guessing in free shell text; fail-closed instead. (That open-ended surface is what diverges.)
- **No masking.** No retry / skip / xfail; do not weaken or delete the existing pinned code-span tests.
- **No canonical-path drift.** The backtick-wrapped extraction must stay byte-for-byte identical to current behavior.
- **No copy divergence.** The two extractor copies must remain byte-identical; never edit one without the other.
- **Builder out of scope.** Do NOT modify `tracker_sync_note.render_tracker_sync_note`; it already always backtick-wraps and is the reason un-backtick is non-canonical. The fix is in the extractor + test only.
- **Phase A is plan-only.** No implementation in this phase; implementation belongs to Phase B under this locked plan.

## Stop conditions

Halt and report (do not work around) if any of the following holds during Phase B:

- The fail-closed change cannot be made without altering the canonical backtick-wrapped path's bytes.
- Closing the un-backtick case appears to require touching any runtime dir (out of scope).
- The byte-identity test between the two extractor copies cannot be kept green with the intended edit.
- A candidate fix requires a new free-text boundary heuristic rather than a fail-closed rejection (explicitly forbidden -- this is the divergence trap).
- The new regression does NOT fail on the pre-fix extractor (would mean the fail-open is not actually reproduced and the premise needs re-grounding).

## Acceptance criteria

- New regression test FAILS on the current (pre-fix) extractor and PASSES after the fix (proves the un-backtick fail-open is real and closed -- not truncated-to-`echo ok`).
- Existing `test_tracker_marker_codespan_extraction.py` byte-identity assertion (both copies byte-identical) still passes.
- Existing canonical backtick-wrapped code-span assertions still pass, unchanged.
- evidence_command passes: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_tracker_marker_codespan_extraction.py`.
- `audit_fast` green; diff limited to the three in-scope files; no runtime dir touched.

## Grounding / Authorization

- **Task:** `[NEXT-CODEX-POST-REDTEAM]` (TASKS.md:740) -- UNPARKED 2026-03-28, founder-authorized; Sequence Phase A -> Phase B -> Phase C -> Phase D; current phase OPEN. This queue is the standing task-id anchor for bounded control-surface waves; each lands under its own packet plus a wave-bound `FOUNDER_OVERRIDE`.
- **Wave authorization (same-wave override):** `FOUNDER_OVERRIDE:evidence-command-failclosed-unbacktick-2026-06-08` (declared in the wave's tracker sync note at TASKS.md:513). This is the wave-bound override commit automation / review derives mechanically for this packet.
- **Authorization: standing pipeline-bug-fix authorization** -- this wave fixes a residual fail-open in the pre-commit supervisor's `evidence_command` extractor (a pipeline/control-surface defect), covered by the founder's standing authorization for autonomous pipeline-bug fixes; the wave-bound `FOUNDER_OVERRIDE` above is the same-wave override of record.
- **Governing packet:** this file, `reports/control_plane/evidence_command_failclosed_unbacktick_2026-06-08.md`, is the governing packet for the wave (named as the wave's Packet in TASKS.md:513).
- **L4 classification (from TASKS.md:513):** Class L4_ENABLER; target_gate_id G8; primary_blocker_class INTEGRATION; primary_invariant_id INV_TYPED_FAIL_CLOSED_OUTCOMES; bootstrap_endgame_policy SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP; boot0_track_id V1; boot0_progress_state HOLD.
- **evidence_command:** `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_tracker_marker_codespan_extraction.py`.
- **evidence_delta:** Un-backtick-wrapped evidence_command values are rejected fail-closed by the tracker-note marker extractor (both byte-identical commit_executor + meta_bridge_supervisor copies) instead of being truncated at an embedded `. marker:` substring, so the pre-commit supervisor can no longer run a truncated-but-matching prefix in place of a full declared command; the canonical backtick-wrapped code-span path is unchanged (byte-identical, still pinned), with a regression test covering the bot counterexample.
- **indicator_artifact_ref:** `reports/l4_wave_indicators/evidence-command-failclosed-unbacktick-2026-06-08.json`.
- **indicator_collection_command:** `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id evidence-command-failclosed-unbacktick-2026-06-08 --output reports/l4_wave_indicators/evidence-command-failclosed-unbacktick-2026-06-08.json`.
- **Predecessor / supersession:** PR #1086 (branch `jabramsja/evidence-command-extraction-codespan-2026-06-08`) holds the validated backtick-wrapped code-span fix as reference; it is OPEN+DIRTY and cannot merge over the bot P2 finding. This wave lands the complete hardening on hardened dev and supersedes it.

## Request from Post-Merge Supervisor (provenance)

GOAL: close the residual fail-open in tracker-note evidence_command extraction WITHOUT adding another fragile free-text boundary heuristic. CONTEXT (verified): the pre-commit supervisor (#52) RUNS a wave's tracker-declared evidence_command and, before running, compares two values extracted by `_tracker_marker_value` (commit_executor.py) / its byte-identical mirror in meta_bridge_supervisor.py. PR #1086 made extraction code-span-aware for BACKTICK-WRAPPED values (correct, keep it), but for an UN-BACKTICK-wrapped value a codex bot P2 showed the boundary check still truncates at an embedded marker-name substring: e.g. an un-backtick evidence_command `echo ok. evidence_delta:foo && false. evidence_delta: real.` stops at the embedded `. evidence_delta:` and both extractors return only `echo ok`; since both sides truncate identically the compare PASSES and the supervisor runs the truncated (passing) `echo ok` instead of the full (failing) command -- a fail-open for manually-authored or legacy unwrapped tracker notes. There is NO reliable text-only way to tell an embedded `. marker:` inside a shell command from a real next-field boundary, so do NOT extend the heuristic (that is the open-ended-surface trap that diverges). REQUIRED FIX (narrow, fail-closed): the canonical builder (tracker_sync_note.render_tracker_sync_note) ALWAYS backtick-wraps the evidence_command value, so a NON-backtick-wrapped evidence_command is non-canonical. Make `_tracker_marker_value`/`_tracker_evidence_command_value`/`_strip_tracker_inline_code` (and the byte-identical meta_bridge_supervisor copies) treat an un-backtick-wrapped evidence_command as INVALID: return a sentinel/empty that causes the supervisor's evidence-command path to FAIL-CLOSED (reject the note / route NEEDS_PHASE_B) rather than silently truncating at an embedded marker substring. Keep the existing backtick-wrapped (code-span-aware) extraction behavior byte-for-byte (it is the canonical path and is already pinned). SCOPE: the two byte-identical extractor copies (mu/tools/executors/commit_executor.py + mu/tools/agents/meta_bridge_supervisor.py) MUST stay byte-identical (a test pins this); update both together. Add a regression test in mu/tests/tools/test_tracker_marker_codespan_extraction.py covering the bot counterexample (un-backtick value with an embedded `. evidence_delta:` -> fail-closed, NOT truncated-to-`echo ok`) AND confirming the canonical backtick-wrapped path is unchanged. HARD CONSTRAINT: no masking, no retry/skip/xfail; do NOT weaken the existing pinned code-span tests. Do NOT touch any runtime dir (mu/host, mu/substrate, mu/closures, mu/bridge, mu/programs, rcx_pi/selfhost, mu/tools/compilers) -- this is tooling-only. PROVE: the new regression test fails on the current (pre-fix) extractor and passes after; the existing test_tracker_marker_codespan_extraction.py byte-identity + canonical-path assertions still pass. L4_ENABLER. (Note: PR #1086 on branch jabramsja/evidence-command-extraction-codespan-2026-06-08 holds the validated code-span work as a reference; this wave lands the complete hardening on hardened dev and supersedes it.)

Routed next-candidate:
evidence-command-failclosed-unbacktick-2026-06-08

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `evidence-command-failclosed-unbacktick-2026-06-08`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/evidence-command-failclosed-unbacktick-2026-06-08_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `evidence-command-failclosed-unbacktick-2026-06-08`
- Active packet: `reports/control_plane/evidence_command_failclosed_unbacktick_2026-06-08.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `49a0bf47b032ceb4a2a702ce1435a06ed66a6570cf8dcfa665131f58c9d358f2`
- Indicator artifact: `reports/l4_wave_indicators/evidence-command-failclosed-unbacktick-2026-06-08.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/tools/test_tracker_marker_codespan_extraction.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/evidence_command_failclosed_unbacktick_2026-06-08.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/evidence-command-failclosed-unbacktick-2026-06-08.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_tracker_marker_codespan_extraction.py`
  - `mu/tools/agents/meta_bridge_supervisor.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/evidence_command_failclosed_unbacktick_2026-06-08.md`
  - `reports/deferred/non_blocking/evidence-command-failclosed-unbacktick-2026-06-08_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/evidence-command-failclosed-unbacktick-2026-06-08.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
