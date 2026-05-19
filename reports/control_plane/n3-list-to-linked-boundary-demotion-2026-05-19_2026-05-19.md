# N3-List-To-Linked-Boundary-Demotion-2026-05-19

Date: 2026-05-19
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-list-to-linked-boundary-demotion-2026-05-19
Class: L4_STRUCTURAL
Target Gate: G8
Phase-A-Lock: LOCKED
FOUNDER_OVERRIDE:n3-list-to-linked-boundary-demotion-2026-05-19

## Scope

This packet rewrite is limited to `reports/control_plane/n3-list-to-linked-boundary-demotion-2026-05-19_2026-05-19.md`.

The successor implementation scope, after Phase A review and bridge convergence, is the locked bounded boundary-demotion write set from `reports/control_plane/n3-list-to-linked-iteration-marker-source-lock-2026-05-19_2026-05-19.md:170-193`:

- `mu/host/python/rcx_pi/selfhost/step_mu.py`
- `mu/host/js/core/normalize.js`
- `mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py`
- `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
- `mu/tests/structural/test_l2_cursor_grounding.py`
- `mu/tests/parity/test_js_parity_automated.py`
- `mu/tools/checks/check_host_semantics_ratchet.py`
- `tools/checks/host_semantics_baseline.json`
- `STATUS.md`
- `archive/status_debt_history.md`, only if the repo debt truth gate requires the debt-history entry
- `reports/control_plane/n3-list-to-linked-boundary-demotion-2026-05-19_2026-05-19.md`
- `reports/l4_wave_indicators/n3-list-to-linked-boundary-demotion-2026-05-19.json`
- `TASKS.md`, successor tracker sync note only after implementation evidence exists

## Work Items

1. Demote the Python converter marker in `mu/host/python/rcx_pi/selfhost/step_mu.py` by replacing the `list_to_linked` inline `@host_iteration` marker with a bounded boundary-normalization comment. Do not change converter behavior or call sites.

2. Demote the JavaScript converter marker in `mu/host/js/core/normalize.js` by replacing the `listToLinked` JSDoc `@host_iteration` marker with a bounded boundary-normalization comment. Do not change converter behavior, exports, or call sites.

3. Update marker-truth gates so the converters remain visible as boundary-normalization evidence but no longer count as tracked `@host_iteration` debt:
   - `mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py`: require Python `list_to_linked` to be boundary-normalization evidence, not tracked `@host_iteration`.
   - `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`: update Python and JS converter marker assertions, kernel-path wording, and ratchet evidence so `list_to_linked` and `listToLinked` are permitted only as boundary-normalization conversion loops while irreducible kernel execution loops remain tracked.
   - `mu/tests/structural/test_l2_cursor_grounding.py`: preserve Python construction and shared Mu cursor tests; add an explicit note or assertion that these tests prove cursor semantics after boundary construction and are not direct JS converter parity coverage.

4. Add focused Python/JavaScript converter parity coverage in `mu/tests/parity/test_js_parity_automated.py` for empty, single-item, multi-item, and nested Mu values by comparing Python `list_to_linked` output with JavaScript `listToLinked` output through a focused Node bridge. Keep the coverage consolidated in this existing parity file so the pre-commit growth-cap gate remains under its file-count ceiling.

5. Update ratchet and current-state documentation only for the directly proven marker decrease:
   - `mu/tools/checks/check_host_semantics_ratchet.py`
   - `tools/checks/host_semantics_baseline.json`
   - `STATUS.md`
   - `archive/status_debt_history.md`, only if required by the debt truth gate

6. Emit the successor evidence artifacts only after implementation proof exists:
   - `reports/l4_wave_indicators/n3-list-to-linked-boundary-demotion-2026-05-19.json`
   - `TASKS.md` successor tracker sync note

## Constraints

- Do not implement the successor wave in this packet rewrite turn.
- Do not inspect downstream implementation files just to decide whether the work is already landed; this Phase A rewrite uses the current stub, TASKS lines for `[NEXT-CODEX-POST-REDTEAM]`, and the cited source-lock packet.
- Do not change converter behavior, converter return shape, exports, production call sites, kernel projections, seed registries, scheduler code, or production `/mu` semantics.
- Do not add host-only behavior or make Python or JavaScript smarter. The only allowed direction is narrower bootstrap-boundary evidence.
- Do not perform baseline-only cleanup. Ratchet and status updates are allowed only after direct proof that the two converter markers were demoted and no host-authority inventory increased.
- Do not widen the write set beyond the files listed in Scope without returning to Phase A/bridge review.
- Do not edit Claude-related files, unrelated control-plane files, unrelated executor/test changes, or unrelated dirty workspace files.

## Stop Conditions

- Stop with NO-GO if demoting either converter marker requires changing converter behavior, call sites, exports, production `/mu` semantics, kernel projections, seed registries, or scheduler behavior.
- Stop with NO-GO if the implementation would add host-only behavior, add host exception tables, or make either host substrate interpret Mu data more intelligently instead of only reclassifying bounded boundary-normalization evidence.
- Stop with NO-GO if focused Python/JavaScript converter parity cannot cover empty, single-item, multi-item, and nested Mu values without production-path changes.
- Stop with NO-GO if ratchet evidence does not show the exact expected decrease from the locked source: total tracked host-semantics markers `7` to `5`, Python `host_iteration` `2` to `1`, JavaScript `host_iteration` `2` to `1`, Python total markers `3` to `2`, and JavaScript total markers `4` to `3`.
- Stop with NO-GO if host-authority inventory increases or the implementation needs a new accepted authority site.
- Stop with NO-GO if L4 execution-contract, tracker-sync, or bridge review cannot mechanically derive same-wave authority for `n3-list-to-linked-boundary-demotion-2026-05-19`.

## Acceptance Criteria

- This Phase A packet has concrete Scope, Work Items, Constraints, Stop Conditions, Acceptance Criteria, and Grounding / Authorization sections.
- Same-wave authority is detector-visible in this packet through `FOUNDER_OVERRIDE:n3-list-to-linked-boundary-demotion-2026-05-19`, while TASKS provenance and the predecessor source-lock remain cited without claiming the successor edits are already landed.
- Phase A bridge review can decide GO/NO-GO from this packet without downstream implementation inspection.
- Implementation, after Phase A lock, touches only the scoped files and only for bounded boundary demotion, focused parity coverage, ratchet/status evidence, required debt-history sync, indicator output, and tracker sync.
- Focused tests prove Python/JavaScript `list_to_linked` / `listToLinked` parity for empty, single-item, multi-item, and nested Mu values.
- Marker-truth gates prove the two converter loops are boundary-normalization evidence, not tracked `@host_iteration`, while irreducible kernel execution loops remain tracked.
- Host-semantics ratchet proof shows only the locked decrease: total tracked markers `7` to `5`, Python `host_iteration` `2` to `1`, JavaScript `host_iteration` `2` to `1`, Python total `3` to `2`, JavaScript total `4` to `3`.
- Host-authority inventory remains unchanged.
- L4 execution contract, tracker-sync checks, docs consistency, focused parity tests, focused marker-truth tests, host-semantics ratchet, host-authority inventory ratchet, and L4 wave indicator collection pass for the successor implementation package.

## Grounding / Authorization

- Current task queue authority: `TASKS.md:389-390` contains the `[NEXT-CODEX-POST-REDTEAM]` tracker sync note for predecessor wave `n3-list-to-linked-iteration-marker-source-lock-2026-05-19`, including `FOUNDER_OVERRIDE:n3-list-to-linked-iteration-marker-source-lock-2026-05-19`. That tracker note proves predecessor/source-lock authority and does not prove the successor implementation is already landed.
- Governing source-lock packet: `reports/control_plane/n3-list-to-linked-iteration-marker-source-lock-2026-05-19_2026-05-19.md:170-193` locks successor wave id `n3-list-to-linked-boundary-demotion-2026-05-19`, exact write set, and expected ratchet effect.
- Governing successor packet: this file, `reports/control_plane/n3-list-to-linked-boundary-demotion-2026-05-19_2026-05-19.md`, is the Phase A plan for the successor boundary-demotion wave.
- Same-wave authorization for this successor packet and later implementation after Phase A GO: `FOUNDER_OVERRIDE:n3-list-to-linked-boundary-demotion-2026-05-19`.

## Phase B Implementation Result

Status: **PASS after Bridge Round 3 blocker repair and staged validation.**

Implemented within the locked write set:

- Python `list_to_linked` marker comment demoted from tracked `@host_iteration` to bounded `BOUNDARY` boundary-normalization evidence without behavior or call-site changes.
- JavaScript `listToLinked` JSDoc marker demoted from tracked `@host_iteration` to bounded `BOUNDARY` boundary-normalization evidence without behavior, export, or call-site changes.
- Marker-truth gates now require the converters as boundary-normalization evidence while preserving tracked kernel execution loop assertions.
- Focused Python/JavaScript converter parity coverage now covers empty, single-item, multi-item, and nested Mu values through a Node bridge consolidated into `mu/tests/parity/test_js_parity_automated.py`.
- Host-semantics ratchet baseline/status/debt-history truth lowered from 7 tracked markers to 5 tracked markers.

Phase B-local validation completed before Bridge Round 3 repair:

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py mu/tests/structural/test_l2_cursor_grounding.py --tb=short` -> PASS, 36 passed.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_js_parity_automated.py --tb=short` -> PASS after growth-cap repair; focused list-to-linked converter cases are consolidated in this existing parity file.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/engine/test_structural_trace.py mu/tests/fuzz/test_kernel_bridge_fuzzer.py --tb=short` -> PASS, 38 passed.
- `node mu/host/js/eval_step.js` -> PASS, all JS self-tests passed.
- `python3 mu/tools/checks/check_host_semantics_ratchet.py --json` -> PASS, current and baseline both report Python `host_iteration=1`, JavaScript `host_iteration=1`, total tracked markers `5`.
- `python3 tools/checks/check_host_authority_inventory_ratchet.py` -> PASS, no unaccepted new total-inventory or authority-subset sites detected.
- `./tools/checks/check_docs_consistency.sh` -> PASS.

Bridge Round 3 blocker repair:

- `mu/host/js/core/constants.js` now declares JavaScript iteration debt `1`, total JS debt `3`, and cross-substrate tracked marker total `5`.
- `mu/tools/checks/check_js_debt.sh` now requires `listToLinked` to carry `BOUNDARY` boundary-normalization evidence instead of a tracked iteration marker.
- `reports/l4_wave_indicators/n3-list-to-linked-boundary-demotion-2026-05-19.json` was generated after the debt checker passed.
- `TASKS.md` carries same-wave tracker authority for `n3-list-to-linked-boundary-demotion-2026-05-19` with the Bridge Round 3 repair files and indicator evidence.

Bridge Round 3 validation:

- `bash mu/tools/checks/check_js_debt.sh` -> PASS, JS debt `3` = `1` iteration + `0` recursion + `2` builtin.
- `python3 mu/tools/checks/check_host_semantics_ratchet.py --json` -> PASS, current and baseline both report Python `host_iteration=1`, JavaScript `host_iteration=1`, total tracked markers `5`.
- `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-list-to-linked-boundary-demotion-2026-05-19 --output reports/l4_wave_indicators/n3-list-to-linked-boundary-demotion-2026-05-19.json` -> PASS, indicator artifact written.
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-list-to-linked-boundary-demotion-2026-05-19 --wave-class L4_STRUCTURAL` -> PASS, `L4_STRUCTURAL compliant` with 16 staged changed files.

Commit executor growth-cap repair:

- Commit executor `run_pre_commit_script` initially failed because `tests/docs/test_growth_caps.py::TestGrowthCaps::test_test_file_count_within_cap` reported `Test file count (313) exceeds baseline (190) + cap (122) = 312` after the standalone `mu/tests/parity/test_list_to_linked_converter_parity.py` file was added.
- Same-wave repair consolidated the focused list-to-linked converter parity cases into existing `mu/tests/parity/test_js_parity_automated.py` and removed the standalone added test file. This preserves the Python/JavaScript parity proof without requesting a growth exception.
- `PYTHONHASHSEED=0 python3 -m pytest -q tests/docs/test_growth_caps.py::TestGrowthCaps::test_test_file_count_within_cap --tb=short` -> PASS, 1 passed.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_js_parity_automated.py -k list_to_linked --tb=short` -> PASS, 4 passed.
- `RCX_SKIP_RECEIPT_CHECK=1 .git/hooks/pre-commit` -> PASS through doc consistency, doc governance growth cap, seed police, speed enforcer, tracker sync, and boot-layer boundary checks; receipt check intentionally skipped before fresh supervisor receipt.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py mu/tests/parity/test_js_parity_automated.py mu/tests/structural/test_l2_cursor_grounding.py --tb=short` -> PASS, 347 passed.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-list-to-linked-boundary-demotion-2026-05-19`
- Active packet: `reports/control_plane/n3-list-to-linked-boundary-demotion-2026-05-19_2026-05-19.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-list-to-linked-boundary-demotion-2026-05-19.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `STATUS.md`
  - `TASKS.md`
  - `archive/status_debt_history.md`
  - `mu/host/js/core/constants.js`
  - `mu/host/js/core/normalize.js`
- `mu/host/python/rcx_pi/selfhost/step_mu.py`
- `mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py`
- `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
- `mu/tests/parity/test_js_parity_automated.py`
  - `mu/tests/structural/test_l2_cursor_grounding.py`
  - `mu/tools/checks/check_host_semantics_ratchet.py`
  - `mu/tools/checks/check_js_debt.sh`
  - `mu/tools/checks/host_semantics_baseline.json`
  - `reports/control_plane/n3-list-to-linked-boundary-demotion-2026-05-19_2026-05-19.md`
  - `reports/deferred/non_blocking/n3-list-to-linked-boundary-demotion-2026-05-19_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-list-to-linked-boundary-demotion-2026-05-19.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
