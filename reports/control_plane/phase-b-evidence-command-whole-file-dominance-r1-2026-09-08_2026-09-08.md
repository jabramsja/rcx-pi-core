# Phase B Evidence Command Whole File Dominance R1

Date: 2026-09-08
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PHASE-B-EVIDENCE-COMMAND-WHOLE-FILE-DOMINANCE-R1]
Wave ID: phase-b-evidence-command-whole-file-dominance-r1-2026-09-08
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: e47583e070c2826de1da7b87eab40aaae33fd4710d5a618d2b7475ea87050963
Purpose: Land the smallest deterministic repair for the PR #1268 commit blocker: when Phase B selects a whole pytest file, selectors targeting that same file must be suppressed so exact-string deduplication cannot expand the packet's evidence command and strand commit.

## Scope

Markerless Phase B producer repair only: whole-file pytest candidates dominate same-file selectors, with one focused regression and atomic TASKS queue sync.

Files and surfaces in scope:

- One order-preserving whole-file dominance rule in _select_pytest_gate_files.
- One regression beside the existing Phase B selector tests, plus preservation of the existing production-only seven-selector behavior.
- TASKS truth recording PR #1268 landed, this repair CURRENT, activation R4B NEXT, and the complete downstream queue.
- TASKS.md -- tracker-sync authority. The 2026-09-08 tracker sync note for wave `phase-b-evidence-command-whole-file-dominance-r1-2026-09-08` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Have Phase A author the canonical packet from this operator stub on exact PR #1268 merge 03298468de64156c0663b10f0f735a78e901c81f; do not hand-author or repeatedly revise the full packet.
2. In _select_pytest_gate_files, collect exact-unique candidates as today, then preserve order while removing every selector whose _pytest_selector_path is already present as a whole-file candidate. Do not change the runtime-targeted selector registry.
3. Add one compact regression with a name and diff hunk outside the special selector-hint markers proving [test_phase_b_executor.py, phase_b_executor.py] selects only the whole test file. Retain the existing production-only test proving all seven targeted selectors remain selected.
4. Use this stub's exact 1030-byte evidence command unchanged for the one-time self-bootstrap because the loaded predecessor executor will still generate the whole file plus seven selectors. After merge, the new dominance rule must generate the 88-byte whole-file command for the same combined edit shape.
5. Synchronize TASKS atomically: mark R4A landed through PR #1268 at exact merge 03298468de64156c0663b10f0f735a78e901c81f; make this repair sole CURRENT; keep marker-bearing activation R4B immediate NEXT and fresh Phase-B evidence-handoff R2 after it; preserve every later PR1219 task, live PR census, never-behind repair, PR disposition, preservation-first WorkingRCX fleet cleanup, Mu production, and every existing TODO-bearing line.
6. Land through providerless commit, PR, required CI/review, merge, and cleanup. Only then builder-launch marker-bearing activation R4B fresh from this wave's exact merge SHA.

## Constraints

- Functional changes are limited to phase_b_executor.py and test_phase_b_executor.py; TASKS and same-wave governance are the only additional tracked surfaces.
- Do not edit commit_executor.py: its packet/TASKS/handoff byte-identity refusal is correct. Do not redesign generic packet authority or edit launch_wave.py, phase_a_executor.py, dispatcher, recovery, bridge code/config, runtime, substrate, hosts, seeds, projections, Mu, or Claude-owned files.
- Keep this wave markerless; it does not activate or claim live use of launch-tracker restoration.
- Use Codex gpt-5.6-sol ultra for every model-bearing role and Codex pager routing; commit remains providerless.
- Do not absorb deferred, non-occurring, parser/platform, or merely efficiency-related edge work.

## Stop conditions

- Stop before launch unless source, target, and comparison authority are exact PR #1268 merge 03298468de64156c0663b10f0f735a78e901c81f and the worktree, bus, branch, and Codex overrides are fresh.
- Stop if the repair needs a production path outside the two Phase B files or weakens the commit executor's existing byte-identity gate.
- Stop if the candidate changes actual test coverage for production-only Phase B edits, L4 semantics, runtime/substrate behavior, or provider authority.
- If this exact whole-file/selector blocker recurs, preserve the lane and narrow from reproduced evidence; do not revise the canonical packet in place.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_phase_b_pytest_gate_timeout_allows_pre_push_budget mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_phase_b_pytest_gate_timeout_keeps_floor_for_invalid_values mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_max_steps_guard_matrix_diff mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_max_steps_mixed_diff_falls_back_to_file_gate mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_executor_test_context_only_marker_falls_back_to_file mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_gate_diff_text_includes_staged_and_unstaged_diff mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_select_pytest_gate_files_uses_targeted_executor_timeout_selectors`

## Acceptance criteria

- Only the six allowlisted paths change; functional changes remain in the two Phase B files.
- The self-bootstrap run retains this stub's exact 1030-byte command byte-identically in the locked packet, TASKS tracker note, supervisor package, and final handoff under the predecessor executor.
- A combined edit of phase_b_executor.py and its test file selects only the whole test file; a production-only edit retains all seven existing targeted selectors in their current order.
- The implementation is order-preserving, does not alter the selector registry, and does not weaken downstream byte-identity enforcement.
- TASKS records R4A landed, this wave CURRENT, R4B NEXT, and retains the complete PR/never-behind/fleet/Mu queue and every existing TODO.
- Providerless PR, CI, review, merge, and cleanup complete before R4B is bound and launched.

## Grounding / Authorization

- Task: [PHASE-B-EVIDENCE-COMMAND-WHOLE-FILE-DOMINANCE-R1]; wave id `phase-b-evidence-command-whole-file-dominance-r1-2026-09-08`.
- Governing packet: this file, `reports/control_plane/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08_2026-09-08.md`.
- TASKS.md authority: the 2026-09-08 tracker sync note for wave `phase-b-evidence-command-whole-file-dominance-r1-2026-09-08` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:phase-b-evidence-command-whole-file-dominance-r1-2026-09-08

## Non-normative review clarification

For avoidance of doubt, the six allowlisted repo-relative paths referenced by the immutable acceptance criterion are exactly:

1. `mu/tools/executors/phase_b_executor.py`
2. `mu/tests/tools/test_phase_b_executor.py`
3. `TASKS.md`
4. `reports/control_plane/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08_2026-09-08.md`
5. `reports/deferred/non_blocking/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08_bridge_nonblockers.md`
6. `reports/l4_wave_indicators/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08.json`

This enumeration clarifies, and does not replace, supersede, or expand, the immutable native launcher packet contract. No other path is allowlisted.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `phase-b-evidence-command-whole-file-dominance-r1-2026-09-08`
- Active packet: `reports/control_plane/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08_2026-09-08.md`
- Indicator artifact: `reports/l4_wave_indicators/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08_2026-09-08.md`
  - `reports/l4_wave_indicators/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id phase-b-evidence-command-whole-file-dominance-r1-2026-09-08 --output reports/l4_wave_indicators/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_phase_b_pytest_gate_timeout_allows_pre_push_budget mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_phase_b_pytest_gate_timeout_keeps_floor_for_invalid_values mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_max_steps_guard_matrix_diff mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_max_steps_mixed_diff_falls_back_to_file_gate mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_executor_test_context_only_marker_falls_back_to_file mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_gate_diff_text_includes_staged_and_unstaged_diff mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_select_pytest_gate_files_uses_targeted_executor_timeout_selectors`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08_2026-09-08.md. (2) Final pytest gate covered 8 pytest selector(s) across 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08_2026-09-08.md`, `reports/l4_wave_indicators/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: phase-b-evidence-command-whole-file-dominance-r1-2026-09-08.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `phase-b-evidence-command-whole-file-dominance-r1-2026-09-08`
- Active packet: `reports/control_plane/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08_2026-09-08.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `034e6e883b0528fd5f82d3e92a3734ad456145be3a5793fad186ee428815d417`
- Indicator artifact: `reports/l4_wave_indicators/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_phase_b_pytest_gate_timeout_allows_pre_push_budget mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_phase_b_pytest_gate_timeout_keeps_floor_for_invalid_values mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_max_steps_guard_matrix_diff mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_max_steps_mixed_diff_falls_back_to_file_gate mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_executor_test_context_only_marker_falls_back_to_file mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_gate_diff_text_includes_staged_and_unstaged_diff mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_select_pytest_gate_files_uses_targeted_executor_timeout_selectors`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08_2026-09-08.md. (2) Final pytest gate covered 8 pytest selector(s) across 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08_2026-09-08.md`, `reports/l4_wave_indicators/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08_2026-09-08.md`
  - `reports/l4_wave_indicators/phase-b-evidence-command-whole-file-dominance-r1-2026-09-08.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
