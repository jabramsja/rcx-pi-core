# Pane Review History 2026-06-02

Date: 2026-06-02
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pane-review-history-2026-06-02
Phase-A-Lock: LOCKED
Purpose: Make the REVIEW FINDINGS tmux pane (mu/tools/observability/_pane_findings.sh) keep the reviewer's work visible AFTER a wave converges to a clean GO. TODAY the main render loop shows ONLY the latest bridge round (it renders the Decision + the BLK|/NB| finding lines, then breaks with the comment 'Only show the latest round'); so when the latest round is a clean GO with zero findings, the pane shows 'GO 0B 0NB' and the blocking/non-blocking findings from the earlier REQUEST_CHANGES rounds are no longer visible -- the reviewer's actual work disappears once the wave passes. READ THESE FIRST (do not deviate): the main render loop (the block that prints Decision/BLK|/NB| and then breaks 'Only show the latest round'), the embedded `_markdown_envelope` python parser, the `parse_agent_envelope_file` helper, and the EXISTING `test_pane_findings_*` tests in mu/tests/tools/test_recovery_gate.py (they install the script and run it with RCX_PANE_ONESHOT=1). PRECISE, BOUNDED CHANGE -- when AND ONLY WHEN the latest round's decision is GO or COMMIT_GO AND its blocking+non-blocking finding count is 0, additionally render, BELOW the existing latest-round block: (a) a one-line 'Review arc:' summary across ALL rendered rounds of the SAME PHASE as the latest round -- read the same-phase rendered round files under <bus>/rendered/ (match the latest round's phase prefix, e.g. phase-a- or phase-b-), parse each with the EXISTING envelope parser, order by round number, and format each round as 'rN <DECISION>.<blocking-count>B' joined by ' -> '; and (b) a 'Last findings (rN, addressed):' block that reuses the EXISTING BLK|/NB| render formatting to show the blocking/non-blocking finding titles from the most-recent PRIOR round whose finding count > 0. If no prior round had findings, omit block (b) but still show the arc. HARD SCOPE: change ONLY the clean-GO display path. When the latest round HAS findings OR is not GO/COMMIT_GO, the existing pane output must be UNCHANGED. Reuse the existing `_markdown_envelope`/`parse_agent_envelope_file` (do NOT add a second parser). SAME-PHASE rounds only (match the latest round's phase prefix). Do NOT change bus-dir resolution, the desktop-notification logic, the in-progress / ERROR branches, or the no-rounds meta fallback. ADD THE REGRESSION TEST as a NEW METHOD in the EXISTING mu/tests/tools/test_recovery_gate.py (do NOT create a new test file -- avoids the growth cap) following the existing test_pane_findings_* pattern: install the script, write synthetic same-phase rendered rounds (r1-r3 REQUEST_CHANGES each with findings, r4 GO with none), run with RCX_PANE_ONESHOT=1, and assert the output contains 'Review arc:' AND the r3 finding title.

## Scope

One bounded observability change, tooling-only (L4_ENABLER, no runtime dir): extend mu/tools/observability/_pane_findings.sh so that WHEN the latest bridge round is a clean GO/COMMIT_GO with zero findings, the pane ALSO renders (a) a one-line 'Review arc:' across all same-phase rendered rounds (rN DECISION.B-count, joined ' -> ', parsed via the EXISTING _markdown_envelope) and (b) the blocking/non-blocking titles of the most-recent prior round that HAD findings ('Last findings (rN, addressed):', reusing the existing BLK|/NB| render). When the latest round has findings or is not GO, the output is UNCHANGED. Same-phase rounds only; no second parser; bus resolution / notifications / in-progress / ERROR / no-rounds branches untouched. Regression test added as a NEW METHOD in the EXISTING mu/tests/tools/test_recovery_gate.py (no new test file) mirroring the existing test_pane_findings_* pattern: synthetic rounds r1-r3 (REQUEST_CHANGES + findings) and r4 (GO, none), RCX_PANE_ONESHOT=1, assert 'Review arc:' and the r3 finding title appear. Validation gate: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py -k pane_findings`. Cite code by function/marker name only; no file:line in the packet.

## Request from Post-Merge Supervisor

Make the REVIEW FINDINGS tmux pane (mu/tools/observability/_pane_findings.sh) keep the reviewer's work visible AFTER a wave converges to a clean GO. TODAY the main render loop shows ONLY the latest bridge round (it renders the Decision + the BLK|/NB| finding lines, then breaks with the comment 'Only show the latest round'); so when the latest round is a clean GO with zero findings, the pane shows 'GO 0B 0NB' and the blocking/non-blocking findings from the earlier REQUEST_CHANGES rounds are no longer visible -- the reviewer's actual work disappears once the wave passes. READ THESE FIRST (do not deviate): the main render loop (the block that prints Decision/BLK|/NB| and then breaks 'Only show the latest round'), the embedded `_markdown_envelope` python parser, the `parse_agent_envelope_file` helper, and the EXISTING `test_pane_findings_*` tests in mu/tests/tools/test_recovery_gate.py (they install the script and run it with RCX_PANE_ONESHOT=1). PRECISE, BOUNDED CHANGE -- when AND ONLY WHEN the latest round's decision is GO or COMMIT_GO AND its blocking+non-blocking finding count is 0, additionally render, BELOW the existing latest-round block: (a) a one-line 'Review arc:' summary across ALL rendered rounds of the SAME PHASE as the latest round -- read the same-phase rendered round files under <bus>/rendered/ (match the latest round's phase prefix, e.g. phase-a- or phase-b-), parse each with the EXISTING envelope parser, order by round number, and format each round as 'rN <DECISION>.<blocking-count>B' joined by ' -> '; and (b) a 'Last findings (rN, addressed):' block that reuses the EXISTING BLK|/NB| render formatting to show the blocking/non-blocking finding titles from the most-recent PRIOR round whose finding count > 0. If no prior round had findings, omit block (b) but still show the arc. HARD SCOPE: change ONLY the clean-GO display path. When the latest round HAS findings OR is not GO/COMMIT_GO, the existing pane output must be UNCHANGED. Reuse the existing `_markdown_envelope`/`parse_agent_envelope_file` (do NOT add a second parser). SAME-PHASE rounds only (match the latest round's phase prefix). Do NOT change bus-dir resolution, the desktop-notification logic, the in-progress / ERROR branches, or the no-rounds meta fallback. ADD THE REGRESSION TEST as a NEW METHOD in the EXISTING mu/tests/tools/test_recovery_gate.py (do NOT create a new test file -- avoids the growth cap) following the existing test_pane_findings_* pattern: install the script, write synthetic same-phase rendered rounds (r1-r3 REQUEST_CHANGES each with findings, r4 GO with none), run with RCX_PANE_ONESHOT=1, and assert the output contains 'Review arc:' AND the r3 finding title.

Routed next-candidate:
pane-review-history-2026-06-02

## Work items

Concrete bounded tasks for Phase B (one tooling file + one new test method):

1. In `mu/tools/observability/_pane_findings.sh`, after the existing latest-round render block (the loop that prints `Decision`/`BLK|`/`NB|` and then breaks with the `Only show the latest round` comment), add a clean-GO display path guarded by: latest round decision is `GO` or `COMMIT_GO` AND latest round blocking+non-blocking finding count == 0. The new output renders BELOW the existing latest-round block.
2. In that path, render (a) a one-line `Review arc:` summary across ALL same-phase rendered rounds: enumerate the same-phase rendered round files under `<bus>/rendered/` (match the latest round's phase prefix, e.g. `phase-a-`/`phase-b-`), parse each with the EXISTING `_markdown_envelope` / `parse_agent_envelope_file`, order by round number, and format each round as `rN <DECISION>.<blocking-count>B` joined by ` -> `.
3. In that path, render (b) a `Last findings (rN, addressed):` block reusing the EXISTING `BLK|`/`NB|` render formatting, showing the blocking/non-blocking finding titles from the most-recent PRIOR round whose finding count > 0. If no prior round had findings, omit block (b) but still render the arc.
4. Add the regression test as a NEW METHOD in the EXISTING `mu/tests/tools/test_recovery_gate.py` (no new file -- growth cap), following the existing `test_pane_findings_*` pattern: install the script, write synthetic same-phase rendered rounds (r1-r3 `REQUEST_CHANGES`, each with findings; r4 `GO`, none), run with `RCX_PANE_ONESHOT=1`, and assert the output contains `Review arc:` AND the r3 finding title.

## Constraints

NOT in scope:

- Behavior for any latest round that HAS findings OR is not `GO`/`COMMIT_GO` -- that path stays byte-for-byte UNCHANGED. Only the clean-GO display path may change.
- A second parser -- reuse only the existing `_markdown_envelope` / `parse_agent_envelope_file`.
- Cross-phase rounds -- match the latest round's phase prefix only (same-phase rounds only).
- Bus-dir resolution, the desktop-notification logic, the in-progress / ERROR branches, and the no-rounds meta fallback -- all untouched.
- A new test file -- the regression test is a new method in the existing `mu/tests/tools/test_recovery_gate.py`.
- Runtime dirs (`mu/host/`, `rcx_pi/selfhost/`, seeds/registries) -- this is tooling-only (`L4_ENABLER`); no host-semantics change.
- file:line citations in this packet -- cite code by function/marker name only.

## Stop conditions

Hard stop and report if any of the following hold:

- Making the validation gate green would require touching an out-of-scope branch (bus resolution, notifications, in-progress/ERROR, no-rounds fallback) or a runtime dir.
- The clean-GO arc cannot be produced without a second parser, or without altering non-GO / has-findings output (existing `test_pane_findings_*` would regress).
- The regression test cannot be expressed as a new method in the existing `test_recovery_gate.py` and would require a new test file (growth cap).
- The change would need to grow beyond `mu/tools/observability/_pane_findings.sh` plus the one new test method -- re-scope via a new packet rather than widening this wave.

## Acceptance criteria

- On a clean-GO latest round (`GO`/`COMMIT_GO` + 0 findings), the pane renders, below the existing latest-round block: (a) a `Review arc:` line across same-phase rounds formatted `rN <DECISION>.<blocking-count>B` joined by ` -> `, and (b) when a prior round had findings, a `Last findings (rN, addressed):` block with that round's blocking/non-blocking titles via the existing `BLK|`/`NB|` render.
- When no prior round had findings, block (b) is omitted but the arc still renders.
- Non-GO / has-findings latest-round output is byte-for-byte unchanged (existing `test_pane_findings_*` still pass).
- Only the existing `_markdown_envelope` / `parse_agent_envelope_file` parser is used; same-phase rounds only; bus resolution / notifications / in-progress / ERROR / no-rounds branches unchanged.
- A new regression-test method in the existing `mu/tests/tools/test_recovery_gate.py` writes synthetic same-phase rounds (r1-r3 `REQUEST_CHANGES` with findings, r4 `GO` with none), runs with `RCX_PANE_ONESHOT=1`, and asserts the output contains `Review arc:` AND the r3 finding title.
- Validation gate green: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py -k pane_findings`.

## Grounding / Authorization

- Task: `[NEXT-CODEX-POST-REDTEAM]` -- UNPARKED 2026-03-28, founder-authorized (TASKS.md). Tracked parent packet: `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`.
- Wave authorization (TASKS.md tracker sync note, 2026-06-02, `pane-review-history-2026-06-02`): Class `L4_ENABLER`; `target_gate_id: G8`; governing packet `reports/control_plane/pane_review_history_2026-06-02.md` (this file); `evidence_command: PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py -k pane_findings`.
- evidence_delta: on a clean-GO latest round, `_pane_findings.sh` additionally renders the same-phase `Review arc:` line plus the most-recent prior findings round's `Last findings (rN, addressed):` titles, reusing the existing parser and `BLK|`/`NB|` render; non-GO / has-findings output unchanged; covered by a new regression method in the existing `test_recovery_gate.py`.
- L4 contract metadata (from the same tracker note): `primary_blocker_class: INTEGRATION`; `primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION`; `indicator_artifact_ref: reports/l4_wave_indicators/pane-review-history-2026-06-02.json`; `indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pane-review-history-2026-06-02 --output reports/l4_wave_indicators/pane-review-history-2026-06-02.json`; `bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP`; `boot0_track_id: V1`; `boot0_progress_state: HOLD`.
- Same-wave L4 authorization for commit automation (control-surface `L4_ENABLER`, tooling-only, no runtime dirs): the wave-bound override below mirrors the TASKS.md tracker note so commit-gate + pre-push adjacency-cap clearance derive the same-wave override mechanically.

FOUNDER_OVERRIDE:pane-review-history-2026-06-02

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `pane-review-history-2026-06-02`
- Active packet: `reports/control_plane/pane_review_history_2026-06-02.md`
- Indicator artifact: `reports/l4_wave_indicators/pane-review-history-2026-06-02.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/observability/_pane_findings.sh`
  - `reports/control_plane/pane_review_history_2026-06-02.md`
  - `reports/l4_wave_indicators/pane-review-history-2026-06-02.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pane-review-history-2026-06-02`
- Active packet: `reports/control_plane/pane_review_history_2026-06-02.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `ce396c149f246a062d947b176ddee65bd27bc6bf8dd1c4897f67d1be847bb26d`
- Indicator artifact: `reports/l4_wave_indicators/pane-review-history-2026-06-02.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pane_review_history_2026-06-02.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pane-review-history-2026-06-02.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/observability/_pane_findings.sh`
  - `reports/control_plane/pane_review_history_2026-06-02.md`
  - `reports/l4_wave_indicators/pane-review-history-2026-06-02.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
