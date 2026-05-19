# N3-Stage0-Worklist-Recursion-Marker-Truth-Ratchet-2026-05-19

Date: 2026-05-19
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-stage0-worklist-recursion-marker-truth-ratchet-2026-05-19
Class: L4_STRUCTURAL
Target gate: G8
Phase-A-Lock: LOCKED
Purpose: Remove stale Stage0 `host_recursion` markers after already-landed worklist traversal and align ratchet/gate truth without adding host semantics.

## Scope

This packet is the governing packet for wave `n3-stage0-worklist-recursion-marker-truth-ratchet-2026-05-19`.

This Phase A rewrite edits only:
- `reports/control_plane/n3-stage0-worklist-recursion-marker-truth-ratchet-2026-05-19_2026-05-19.md`

Phase B write scope, after same-wave tracker authority is detector-visible:
- `TASKS.md`
- `reports/control_plane/n3-stage0-worklist-recursion-marker-truth-ratchet-2026-05-19_2026-05-19.md`
- `reports/l4_wave_indicators/n3-stage0-worklist-recursion-marker-truth-ratchet-2026-05-19.json`
- `mu/host/python/rcx_pi/selfhost/eval_seed.py`
- `mu/host/js/core/bootstrap_core.js`
- `mu/host/js/core/constants.js`
- `tools/checks/check_js_debt.sh`
- `mu/tools/audits/audit_semantic_purity.sh`
- `mu/tests/structural/test_execution_layer_truth_contract.py`
- `mu/tests/l4_gates/test_p7_mutation_elimination_gate.py`
- `STATUS.md`
- `archive/status_debt_history.md`
- `mu/tools/checks/host_semantics_baseline.json`
- `tools/checks/host_semantics_baseline.json`

No other Phase B write paths are in scope for this packet. If Phase B evidence shows any path outside the explicit list above must change, stop and route that exact prerequisite or follow-up instead of widening this wave.

## Work items

1. Before any Phase B runtime, test, tooling, status, or baseline edit, verify same-wave `TASKS.md` tracker authority for `n3-stage0-worklist-recursion-marker-truth-ratchet-2026-05-19`.
2. Reproduce the cited Stage0 source evidence before editing: PR #995 replaced selected Stage0 self-recursive traversal with explicit worklist/value-stack structure; `_stage0_substitute`, `stage0Match`, and `stage0Substitute` must have no self-recursive calls beyond declarations before stale markers are removed.
3. Remove only stale `@host_recursion` markers/comments from the cited Stage0 functions whose self-recursive traversal is already absent.
4. Update `tools/checks/check_js_debt.sh` so Stage0 match/substitute no longer require `@host_recursion`; prefer a worklist/no-self-call or boundary/truth check if practical.
5. Update focused tests so they assert the stale markers are absent and Stage0 worklist/no-self-call behavior remains true.
6. Update only `mu/host/js/core/constants.js`, `mu/tools/audits/audit_semantic_purity.sh`, `STATUS.md`, `archive/status_debt_history.md`, `mu/tools/checks/host_semantics_baseline.json`, and `tools/checks/host_semantics_baseline.json` after same-wave source marker removal has happened and the ratchet evidence supports the lower truth.
7. Collect the same-wave indicator artifact and route commit/receipt surfaces through the normal pipeline path after focused validations pass.

## Constraints

- This turn is a packet rewrite only; do not solve the implementation here.
- Do not add Python or JavaScript host semantics.
- Do not implement or relist the already-landed Stage0 worklist traversal as pending work; only remove stale marker/gate truth after re-verifying current source.
- Do not remove `@host_builtin` or `@host_iteration` markers.
- Do not touch `mu/host/js/core/bootstrap_core.js:293`.
- Do not lower ratchet/status/baseline truth before source marker removal in the same wave.
- Do not use baseline, status, or documentation edits as standalone proof of host-debt reduction.
- Do not widen into D010, seed/registry migration, scheduler work, production default flips, host-oracle work, Claude files, unrelated executor changes, unrelated tests, or broad docs cleanup.

## Stop conditions

- Stop before Phase B implementation if `TASKS.md` lacks detector-visible same-wave authority or the packet is not the governing packet for this wave.
- Stop if direct current source evidence shows any targeted Stage0 function still performs self-recursive traversal.
- Stop if honest marker removal would require new host semantics, Python/JavaScript parity divergence, or a semantic behavior change instead of truth cleanup.
- Stop if the required edit would touch outside the Phase B write scope or would touch `mu/host/js/core/bootstrap_core.js:293`.
- Stop if ratchet/status/baseline lowering would precede source marker removal or rely on baseline-only proof.
- Stop if focused validation exposes a broader prerequisite; route the precise prerequisite automatically instead of widening this wave.

## Acceptance criteria

- The packet remains locked and contains `Scope`, `Work items`, `Constraints`, `Stop conditions`, `Acceptance criteria`, and `Grounding / Authorization` sections.
- Detector-visible Phase A packet-repair authorization is present through the grounding below: broad `[NEXT-CODEX-POST-REDTEAM]` `TASKS.md` lane authority, this governing packet, and a wave-bound authorization line in this packet.
- Same-wave `TASKS.md` tracker authority exists before any Phase B runtime, test, tooling, status, or baseline edits are committed.
- The only removed `@host_recursion` markers/comments are the stale Stage0 markers whose corresponding self-recursive traversal is absent by direct current source evidence.
- Stage0 worklist/no-self-call proof remains covered for Python match/substitute and JS match/substitute, and stale marker expectations are removed from focused gates.
- `tools/checks/check_js_debt.sh` no longer requires `@host_recursion` on worklist-based Stage0 match/substitute.
- Ratchet/status/baseline totals are lowered only after same-wave source marker removal and are consistent across mirrors/status/debt history.
- Required Phase B validation includes `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/structural/test_execution_layer_truth_contract.py mu/tests/l4_gates/test_p7_mutation_elimination_gate.py`, JS debt check, `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`, `python3 tools/checks/check_host_authority_inventory_ratchet.py`, strict L4 execution-contract validation for this wave, indicator collection for this wave id, and docs consistency.
- A reproduction check equivalent to the bridge reviewer query finds the required sections, broad `[NEXT-CODEX-POST-REDTEAM]` `TASKS.md` lane authority, this `governing packet`, this packet's wave-bound authorization text, and same-wave `TASKS.md` tracker authority.

## Grounding / Authorization

- `TASKS.md:443-450` marks `[NEXT-CODEX-POST-REDTEAM]` as the open code-truth follow-up bucket.
- `TASKS.md:560-568` marks `[NEXT-CODEX-POST-REDTEAM]` as unparked and founder-authorized, says the current phase remains open for separate bounded packets, and requires every wave to have a control-plane packet plus `TASKS.md` tracker entry.
- `TASKS.md` now contains a same-wave tracker sync note for `n3-stage0-worklist-recursion-marker-truth-ratchet-2026-05-19` with `FOUNDER_OVERRIDE:n3-stage0-worklist-recursion-marker-truth-ratchet-2026-05-19`.
- The targeted lookup for `n3-stage0-worklist-recursion-marker-truth-ratchet-2026-05-19` and `FOUNDER_OVERRIDE:n3-stage0-worklist-recursion-marker-truth-ratchet-2026-05-19` in `TASKS.md` returned no output before this packet repair; the same-wave tracker sync note is the detector-visible repair.
- Governing packet: `reports/control_plane/n3-stage0-worklist-recursion-marker-truth-ratchet-2026-05-19_2026-05-19.md`.
- Authorization: standing pipeline-bug-fix authorization for same-wave Phase A packet repair and tracker-authority derivation under `[NEXT-CODEX-POST-REDTEAM]`; FOUNDER_OVERRIDE:n3-stage0-worklist-recursion-marker-truth-ratchet-2026-05-19.

Questions? Concerns? Thoughts? -- Think hard
