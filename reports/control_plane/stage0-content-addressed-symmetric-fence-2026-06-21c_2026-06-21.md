# NEXT-CODEX-POST-REDTEAM - Stage0 content-addressed collapse (symmetric-fence resolution): relax Python P7W4 to JS scope + input-side raw-list fail-close

Date: 2026-06-21
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: stage0-content-addressed-symmetric-fence-2026-06-21c
Phase-A-Lock: LOCKED
Purpose: STAGE0-CONTENT-ADDRESSED-TYPEDISPATCH recovery, FOUNDER-DECIDED 2026-06-20 (option 1 of the blocking contradiction report). GOAL: collapse the host scalar TYPE-DISPATCH in Stage0 match (`_stage0_match` in eval_seed.py + `stage0Match` in bootstrap_core.js) by replacing the four scalar `isinstance(bool/int/float/str)` branches with a single content-addressed `mu_hash_cached` equality, so host-semantics DECREASE. THE BLOCKER (command-verified): with the scalar branches replaced, a raw Python list reaches the content-hash branch and `mu_hash_cached([1,2])` does NOT raise (mu_type.is_mu accepts raw lists), so equal raw lists wrongly MATCH in Python (was NO_MATCH) and diverge from JS `stage0Match` (NO_MATCH). Restoring NO_MATCH needs a list distinction, but the current Python P7W4 fence forbids the analog that JS already PERMITS: JS `test_js_stage0_match_no_array_branch` forbids only the PATTERN-side `Array.isArray(pattern)` element branch and PERMITS the input-side `Array.isArray(input)` fail-close that `stage0Match` relies on; the Python fence (`test_stage0_match_no_isinstance_list` + `test_stage0_match_no_list_type_dispatch`) forbids the input-side analog too -- an ASYMMETRY holding Python to a stricter standard than the substrate it must stay in parity with. FOUNDER-APPROVED FIX (option 1, symmetric fence): (a) RELAX the Python P7W4 fence to the JS fence's scope -- forbid ONLY the pattern-side list/element dispatch, PERMIT exactly one input-side raw-list reject-guard; (b) add that ONE input-side `isinstance(input_value, list)` fail-close in `_stage0_match` (the analog of the JS input-side `Array.isArray(input)` fail-close), THEN the content-addressed equality. Result: raw lists -> NO_MATCH in BOTH substrates; scalars/signed-zero/cross-type/tuple unchanged; the host-semantics ratchet still DECREASES (4 scalar isinstance branches -> 1 input-side list fail-close + content hash). This reverses the prior bridge round-2 list-token ban -- FOUNDER-AUTHORIZED gate-modification.

## Scope

Collapse Stage0 scalar type-dispatch to content-addressed equality + one input-side raw-list fail-close; relax the Python P7W4 fence to the JS fence's scope (FOUNDER-APPROVED gate-mod). Parity-preserving; host-debt reduction; bounded to the named runtime + gate files. TASKS.md is tracker-sync authority.

Files and surfaces in scope:

- mu/host/python/rcx_pi/selfhost/eval_seed.py (MODIFY) -- `_stage0_match`: replace the 4 scalar isinstance branches with one `mu_hash_cached` equality; add ONE input-side `isinstance(input_value, list)` fail-close (return NO_MATCH) before/at the content-hash; NO pattern-side list branch; keep None/null + compound(dict) branch + worklist + depth guard + non-linear conflict UNCHANGED.
- INVALID-MU FAIL-CLOSE (Phase-A r1 DEFECT fix): in `_stage0_match`/`stage0Match`, the content-addressed equality must be guarded so unsupported/invalid host values (tuple, non-Mu, etc.) return NO_MATCH and NEVER reach mu_hash_cached/assert_mu (Python `mu_type` rejects tuple/unsupported; JS muHashCached throws on non-valid-Mu). Reach NO_MATCH via the existing fall-through (eval_seed.py _stage0_match fall-through to NO_MATCH; JS analog) BEFORE the hash, OR a validity check; do NOT let assert_mu/muHashCached raise -- a non-scalar non-dict input must fall through to NO_MATCH exactly as dev does.
- mu/host/js/core/bootstrap_core.js (MODIFY) -- `stage0Match`: mirror the scalar->content-addressed collapse; KEEP the existing input-side `Array.isArray(input)` fail-close; no pattern-side array element branch.
- mu/tests/l4_gates/test_p7w4_structural_reduction_gate.py (MODIFY) -- relax `test_stage0_match_no_isinstance_list` + `test_stage0_match_no_list_type_dispatch` to forbid ONLY the PATTERN-side list dispatch (mirror `test_js_stage0_match_no_array_branch` scope); PERMIT exactly one input-side `isinstance(input_value, list)` reject-guard. Prove the no-scalar-isinstance reduction thesis via the NEW AST assertion in test_stage0_content_addressed_collapse_gate.py (do NOT reference a pre-existing `test_no_scalar_isinstance_in_stage0_match` -- it is absent).
- mu/tests/l4_gates/test_stage0_content_addressed_collapse_gate.py (CREATE) -- gate: raw lists ([1,2]/[]) NO_MATCH both substrates; equal scalars MATCH via content hash; signed-zero (+0 vs -0) NO_MATCH both; cross-type/tuple unchanged; AST-assert `_stage0_match` has the content-hash + the single input-side list fail-close + NO scalar isinstance + NO pattern-side list branch.
- reports/l4_wave_indicators/stage0-content-addressed-symmetric-fence-2026-06-21c.json (GENERATED).
- TASKS.md -- tracker-sync authority. The 2026-06-21 tracker sync note for wave `stage0-content-addressed-symmetric-fence-2026-06-21c` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Read dev `_stage0_match` (eval_seed.py) + `stage0Match` (bootstrap_core.js, esp. the existing input-side Array.isArray(input) fail-close) + the current P7W4 fence tests + the blocking contradiction report's verified minimal fix (input-side fail-close then content hash).
2. Relax the Python P7W4 fence (`test_stage0_match_no_isinstance_list` + `test_stage0_match_no_list_type_dispatch`) to forbid ONLY the pattern-side list dispatch, mirroring the JS fence `test_js_stage0_match_no_array_branch`; PERMIT one input-side `isinstance(input_value, list)` reject-guard. This is the founder-approved gate-modification.
3. Modify `_stage0_match`: collapse the 4 scalar isinstance branches to one `mu_hash_cached` equality; add ONE input-side `isinstance(input_value, list): return NO_MATCH` fail-close (the JS-analog); do NOT add a pattern-side list branch, list-length, or zip.
4. Mirror in `stage0Match` (JS): scalar branches -> content-addressed equality; KEEP the existing `Array.isArray(input)` fail-close.
5. Create `test_stage0_content_addressed_collapse_gate.py` proving raw-list NO_MATCH (both substrates), scalar content-hash MATCH, signed-zero NO_MATCH (both), and the `_stage0_match` AST shape (content hash + single input-side list fail-close + no scalar isinstance + no pattern-side list branch).
6. Set the L4_STRUCTURAL tracker-note fields the launcher does not pre-fill: workload_target=host_debt_reduction and host_semantics_delta (the net host-dispatch DECREASE: 4 scalar isinstance branches -> 1 content-addressed mu_hash equality + 1 input-side list fail-close); the staged L4 contract requires both.
7. Run evidence_command + post_gate_contract_sweep; confirm host-semantics ratchet DECREASES, authority inventory unchanged, node eval_step clean, parity gates green; emit the indicator.

## Constraints

- Use the pipeline launcher + dispatcher Phase A and Phase B path; no manual implementation or commit path.
- Parity-preserving ONLY: NO_MATCH-vs-bind results identical per substrate; raw lists NO_MATCH in BOTH; signed-zero NO_MATCH in BOTH (pure content-addressed equality, NO -0->+0 canonicalization -- that needs a host primitive, rejected).
- Add EXACTLY ONE input-side `isinstance(input_value, list)` fail-close in `_stage0_match`; do NOT add a pattern-side list branch, `type(pattern) is list`, `x.__class__ is list`, `len(`, or `zip(` (the relaxed fence still forbids pattern-side list dispatch; the round-2 lesson: no pattern-side list handling).
- NO new host primitive (no hash()/json string-inspection/Object.is/str()); NO host recursion; NO helper-delegation gate-evasion (do not call normalize_for_match/is_head_tail_structure to relocate the dispatch); NO ratchet-baseline edit to mask a change; NO authority-inventory increase.
- Host-semantics ratchet must DECREASE (net), never increase; keep None/null + compound(dict) branch + worklist + depth guard + non-linear conflict UNCHANGED; bounded to the named files.
- FAIL-CLOSE for invalid host values: unsupported/non-Mu inputs (tuple, etc.) must return NO_MATCH via the existing fall-through, never raise from mu_hash_cached/assert_mu/muHashCached. Guard the content-hash so only valid scalars reach it; everything else falls through to NO_MATCH as dev does.

## Stop conditions

- Stop done when evidence_command + post_gate_contract_sweep pass, the ratchet DECREASES, and the indicator is collected.
- Halt as POLICY_BOUND if NO_MATCH/parity for raw lists or signed-zero cannot be restored without a forbidden pattern-side list branch or a new host primitive.
- If the fix would require a pattern-side list branch or a host primitive, re-scope rather than relaxing more than the founder-approved input-side reject-guard.
- Do not commit without a real handoff artifact and gate-green evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_stage0_production_pilot_gate.py mu/tests/l4_gates/test_p7w4_structural_reduction_gate.py mu/tests/l4_gates/test_stage0_content_addressed_collapse_gate.py mu/tests/l4_gates/test_w3_crash_guards_gate.py mu/tests/parity/test_js_vm_bridge_parity.py --tb=short && node mu/host/js/eval_step.js && python3 mu/tools/checks/check_host_semantics_ratchet.py --json && python3 tools/checks/check_host_authority_inventory_ratchet.py`

## Acceptance criteria

- `_stage0_match` + `stage0Match`: scalar branches collapsed to content-addressed equality; exactly one input-side raw-list fail-close each; raw lists NO_MATCH both substrates; signed-zero NO_MATCH both.
- Python P7W4 fence relaxed to JS scope (pattern-side dispatch forbidden, one input-side reject-guard permitted); `test_no_scalar_isinstance_in_stage0_match` still passes.
- host-semantics ratchet DECREASES; authority inventory unchanged; node eval_step clean; parity + crash gates green.
- test_stage0_content_addressed_collapse_gate.py proves the behavior + AST shape and passes.
- evidence_command + post_gate_contract_sweep clean; indicator emitted.
- Invalid/unsupported host values (tuple, non-Mu) return NO_MATCH in both substrates without raising (no assert_mu/muHashCached exception); proven in the collapse gate.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `stage0-content-addressed-symmetric-fence-2026-06-21c`.
- Governing packet: this file, `reports/control_plane/stage0-content-addressed-symmetric-fence-2026-06-21c_2026-06-21.md`.
- TASKS.md authority: the 2026-06-21 tracker sync note for wave `stage0-content-addressed-symmetric-fence-2026-06-21c` is canonical for this packet's L4 fields.
- Authorization: Founder-approved 2026-06-20 (AskUserQuestion: 'Make Python match JS (Recommended)'): relax the Python P7W4 fence to the JS fence's scope + add the input-side raw-list fail-close, reversing the prior bridge round-2 list-token ban. This is the gate-modification the blocking contradiction report flagged as needing founder sign-off. Stage0 reduction is a founder-priority queue item; re-dispatched fresh off dev (lane1 was 80-92 behind). SIGNED-ZERO DELTA -- founder-DECIDED 2026-06-16 (cite to resolve the Phase-A r1 POLICY_BOUND): the content-addressed collapse FLIPS +0/-0 from MATCH to NO_MATCH in BOTH Python and JS (a parity-preserving behavior change, both substrates identical). The founder ACCEPTED pure content-addressed equality and REJECTED canonicalizing -0->+0 (needs a host primitive). The packet does NOT claim signed-zero is unchanged; it is an authorized behavior delta.

FOUNDER_OVERRIDE:stage0-content-addressed-symmetric-fence-2026-06-21c

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `stage0-content-addressed-symmetric-fence-2026-06-21c`
- Active packet: `reports/control_plane/stage0-content-addressed-symmetric-fence-2026-06-21c_2026-06-21.md`
- Indicator artifact: `reports/l4_wave_indicators/stage0-content-addressed-symmetric-fence-2026-06-21c.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/host/js/core/bootstrap_core.js`
  - `mu/host/python/rcx_pi/selfhost/eval_seed.py`
  - `mu/tests/l4_gates/test_p7w4_structural_reduction_gate.py`
  - `mu/tests/l4_gates/test_stage0_content_addressed_collapse_gate.py`
  - `reports/control_plane/stage0-content-addressed-symmetric-fence-2026-06-21c_2026-06-21.md`
  - `reports/deferred/non_blocking/stage0-content-addressed-symmetric-fence-2026-06-21c_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/stage0-content-addressed-symmetric-fence-2026-06-21c.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
