# coinduction foundation gate: verify coinduction is a recognized structural item robustly (drop the brittle exact queue-position phrase)

Date: 2026-06-29
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: coinduction-gate-queue-phrase-robustness-2026-06-29
Phase-A-Lock: LOCKED
Purpose: Make the coinduction foundation gate ROBUST to queue-truth phrasing so it stops stranding queue-truth edits, WITHOUT making the check vacuous. PROBLEM (verified in current code): `mu/tests/l4_gates/test_coinduction_foundation_gate.py`, inside `test_coinduction_doc_is_discoverable_from_wave_authority`, hard-asserts THREE exact narrative position-phrases against `tasks_text` (TASKS.md): `assert "Coinduction is the next active structural item" in tasks_text`, `assert "Fixpoint follows" in tasks_text`, and `assert "Optimization is LAST" in tasks_text`. All three strings are co-located in ONE sentence of the TASKS.md queue-truth refresh (TASKS.md tracker line: "...recursive ordinals and W-types have landed on current dev, Coinduction is the next active structural item, Fixpoint follows, and Optimization is LAST"). Any rephrase of that single sentence breaks all three asserts together, and TASKS.md already marks Coinduction "NEXT" so the rephrase is imminent -- this is the exact stranding failure the wave exists to prevent (it stranded the 2026-06-27 control-plane-cleanup wave). FIX (gate-only; do NOT edit TASKS.md queue-truth -- founder-owned): retarget all THREE asserts from the brittle narrative sentence to the DURABLE active structural-program list. That list enumerates the program as bolded numbered entries (`N. **Item** ...`) terminated by the `**DROPPED (do not pursue):**` marker; the bolded entry PERSISTS through landing (siblings `**Recursive ordinals** ... LANDED`, `**W-types / inductive types** ... LANDED` prove this), so `**Coinduction**` survives the queued -> in-flight -> landed transition while the narrative sentence does not. The generalized check (a) slices the active-program region (between the first numbered bolded entry and the `**DROPPED` marker) and (b) asserts the bolded program entries `**Coinduction**`, `**Fixpoint**`, `**Optimization**` are present within that region, with `**Optimization**` still annotated LAST/out-of-scope. This is NOT a bare whole-file case-insensitive 'coinduction' token check: such a check stays green off historical/frozen tracker notes (lowercase wave-ids at the bottom of TASKS.md) even if Coinduction is dropped from the active program, defeating the gate's protective intent -- so the check MUST be region-bounded and fail-closed, and a permanent NEGATIVE-case test must prove the assert fails when `**Coinduction**` is removed from the active-program region. Add an inline `# QUEUE_PHRASE_ROBUST` marker comment at each generalized assertion (and the negative-case test). CODE-TRUTH CORRECTIONS vs the stub: (1) the `mu/tests/docs/` sibling gate exists but carries NO `in tasks_text` exact-phrase asserts -- it needs no edit; the sole edit target is the `mu/tests/l4_gates/` gate. (2) the line-84 assert (`"Optimization remains out of scope and LAST in TASKS.md."`) targets `packet_text` = the FROZEN `coinduction-non-termination-as-structure` packet, which does not advance with the queue -- it is NOT the brittleness class this wave fixes and is OUT of scope. Do NOT touch TASKS.md, the substrate, the frozen packet, the docs-sibling gate, or any other gate. No host semantics. Keep the full gate passing on current dev.

## Scope

Generalize the three co-located queue-position asserts in the coinduction foundation gate so a TASKS.md queue-truth rephrase no longer strands waves, while preserving (and provably NOT weakening) the gate's protective intent that Coinduction is not silently dropped from the active structural program. The only code edited is the L4 gate's `test_coinduction_doc_is_discoverable_from_wave_authority` membership logic plus one supporting helper/negative-case test in the same file.

Files and surfaces in scope:

- EDIT TARGET (the only modified source file): `mu/tests/l4_gates/test_coinduction_foundation_gate.py` -- generalize the three `tasks_text` queue-phrase asserts to the region-bounded durable-program-entry check, add the `# QUEUE_PHRASE_ROBUST` markers, and add the permanent negative-case test.

Read-only authorities (consulted, NEVER edited):

- `TASKS.md` -- founder-owned queue-truth and the 2026-06-29 tracker-sync authority for this wave's L4 fields. Read-only here; the constraint below forbids editing it.
- `reports/control_plane/coinduction-non-termination-as-structure-2026-06-27_2026-06-27.md` -- the FROZEN packet that the gate's `packet_text` line-84 assert targets. Read-only; out of scope (see Constraints).
- `mu/tests/docs/test_coinduction_foundation_gate.py` -- docs-sibling gate; verified to contain NO `in tasks_text` exact-phrase asserts, so it requires no change. Read-only.

- `reports/deferred/non_blocking/coinduction-gate-queue-phrase-robustness-2026-06-29_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Refactor the membership logic in `test_coinduction_doc_is_discoverable_from_wave_authority` into a small pure helper (e.g. `_active_program_region(tasks_text) -> str` that returns the active structural-program slice: from the first `N. **Item** ...` numbered bolded entry up to, but excluding, the `**DROPPED (do not pursue):**` marker line). The helper MUST fail-closed: if the program list or the `**DROPPED` terminator cannot be located, it raises (or returns a value that makes the asserts fail) rather than yielding the whole file.
2. Replace `assert "Coinduction is the next active structural item" in tasks_text` with a region-bounded assert that the bolded program entry `**Coinduction**` appears in `_active_program_region(tasks_text)`. Position-agnostic: it must pass whether the entry reads `**Coinduction** ... NEXT`, in-flight, or `**Coinduction** ... LANDED in PR #...`. Tag with `# QUEUE_PHRASE_ROBUST`.
3. Replace `assert "Fixpoint follows" in tasks_text` with a region-bounded assert that `**Fixpoint**` appears in the active-program region (recognized program item, not pinned to the word "follows"). Tag with `# QUEUE_PHRASE_ROBUST`.
4. Replace `assert "Optimization is LAST" in tasks_text` with a region-bounded assert that `**Optimization**` appears in the active-program region AND that its entry still carries the LAST / out-of-scope annotation (preserve the "Optimization stays last" invariant without pinning the exact narrative sentence). Tag with `# QUEUE_PHRASE_ROBUST`.
5. Add a permanent negative-case test (e.g. `test_coinduction_gate_fails_when_dropped_from_active_program`) that feeds a mutated `tasks_text` with the `**Coinduction**` entry removed from the active-program region through the helper/assert path and asserts it RAISES `AssertionError`. This locks non-vacuity: a historical-note-only ('coinduction' lowercase, outside the region) mention must NOT satisfy the check. Tag with `# QUEUE_PHRASE_ROBUST`.
6. Run the full gate (both files) on current dev and confirm GREEN; confirm `grep -q QUEUE_PHRASE_ROBUST mu/tests/l4_gates/test_coinduction_foundation_gate.py` exits 0.

## Constraints

- Do NOT touch `TASKS.md` (queue-truth and program list are founder-owned; this wave fixes the gate, not the tracker).
- Do NOT edit the frozen packet `reports/control_plane/coinduction-non-termination-as-structure-2026-06-27_2026-06-27.md`; the line-84 `packet_text` assert targets it and is out of scope (it does not advance with the queue, so it is not the brittleness class fixed here).
- Do NOT edit `mu/tests/docs/test_coinduction_foundation_gate.py` (verified to carry no exact-phrase `tasks_text` asserts) or any other gate.
- Do NOT touch the substrate (`mu/host/`, `rcx_pi/selfhost/`) or any runtime/production code. No L3-parity surface is involved (JS untouched).
- No host semantics added. This is a test-assertion robustness change only.
- Do NOT replace the region-bounded check with a bare whole-file case-insensitive `'coinduction'` substring test -- that is vacuous against historical/frozen tracker notes and is explicitly rejected by finding 2.
- Keep the other asserts in `test_coinduction_doc_is_discoverable_from_wave_authority` (PACKET_REF, TEST_PATH, DOCS_TEST_PATH, WAVE_ID, `Class: L4_ENABLER`, the packet_text asserts) unchanged.

## Stop conditions

- All three narrative queue-position asserts (`"Coinduction is the next active structural item"`, `"Fixpoint follows"`, `"Optimization is LAST"`) no longer exist as `in tasks_text` membership tests, and are replaced by the region-bounded durable-entry checks.
- The full coinduction gate (`mu/tests/l4_gates/` and `mu/tests/docs/` files) is GREEN on current dev.
- The negative-case test proves the coinduction check fails-closed when the entry is dropped from the active-program region.
- STOP and surface to the founder if making the gate robust would require editing TASKS.md, the frozen packet, the substrate, or another gate -- that signals scope creep beyond this wave.
- STOP if the active-program region or `**DROPPED` terminator cannot be reliably located in current TASKS.md (the fail-closed helper would make the gate red); re-scope rather than loosen to a whole-file check.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_coinduction_foundation_gate.py`
- gate (green-on-dev): `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_coinduction_foundation_gate.py mu/tests/docs/test_coinduction_foundation_gate.py`
- anti-stranding probe: `grep -n 'next active structural item\|Fixpoint follows\|Optimization is LAST' mu/tests/l4_gates/test_coinduction_foundation_gate.py` returns NO `in tasks_text` assertion line.

## Acceptance criteria

- AC1 (green on dev): the full coinduction gate passes on current dev unchanged-TASKS.md, where the active-program list has `**Coinduction**` (NEXT), `**Fixpoint**`, and `**Optimization** — LAST`.
- AC2 (marker / evidence): `grep -q QUEUE_PHRASE_ROBUST mu/tests/l4_gates/test_coinduction_foundation_gate.py` exits 0; a `# QUEUE_PHRASE_ROBUST` marker sits on each of the three generalized asserts and on the negative-case test.
- AC3 (anti-stranding, finding 1): none of the three exact narrative phrases remain as `in tasks_text` asserts; a rephrase of the TASKS.md queue-truth sentence (e.g. "Coinduction landed; Fixpoint is next") leaves the gate GREEN. All three siblings are covered, not just the first.
- AC4 (NON-VACUITY negative case, finding 2): with a `tasks_text` fixture whose active-program region omits the `**Coinduction**` entry, the gate's coinduction assert RAISES `AssertionError` (proven by the permanent negative-case test). A 'coinduction' mention that appears ONLY in a historical/frozen tracker note (outside the active-program region) does NOT satisfy the check.
- AC5 (region bound, fail-closed, finding 2): the check operates on the bounded active-program region (first `N. **Item**` entry through the `**DROPPED (do not pursue):**` marker), and the helper fails-closed (gate red) if that region cannot be located -- it never falls back to a whole-file token scan.
- AC6 (scope containment, finding 4): the only modified source file is `mu/tests/l4_gates/test_coinduction_foundation_gate.py`; TASKS.md, the substrate, the frozen `coinduction-non-termination-as-structure` packet, the docs-sibling gate, and the line-84 `packet_text` assert are all unchanged.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `coinduction-gate-queue-phrase-robustness-2026-06-29`.
- Governing packet: this file, `reports/control_plane/coinduction-gate-queue-phrase-robustness-2026-06-29_2026-06-29.md`.
- TASKS.md authority: the 2026-06-29 tracker sync note for wave `coinduction-gate-queue-phrase-robustness-2026-06-29` is canonical for this packet's L4 fields (Class: L4_ENABLER, target_gate_id: G8, evidence_command above).
- Authorization: standing pipeline-bug-fix authorization (control-surface gate-robustness fix; commit automation derives the same-wave override from the line below).

FOUNDER_OVERRIDE:coinduction-gate-queue-phrase-robustness-2026-06-29

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `coinduction-gate-queue-phrase-robustness-2026-06-29`
- Active packet: `reports/control_plane/coinduction-gate-queue-phrase-robustness-2026-06-29_2026-06-29.md`
- Indicator artifact: `reports/l4_wave_indicators/coinduction-gate-queue-phrase-robustness-2026-06-29.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/test_coinduction_foundation_gate.py`
  - `reports/control_plane/coinduction-gate-queue-phrase-robustness-2026-06-29_2026-06-29.md`
  - `reports/deferred/non_blocking/coinduction-gate-queue-phrase-robustness-2026-06-29_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/coinduction-gate-queue-phrase-robustness-2026-06-29.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `coinduction-gate-queue-phrase-robustness-2026-06-29`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/coinduction-gate-queue-phrase-robustness-2026-06-29_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/coinduction-gate-queue-phrase-robustness-2026-06-29.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id coinduction-gate-queue-phrase-robustness-2026-06-29 --output reports/l4_wave_indicators/coinduction-gate-queue-phrase-robustness-2026-06-29.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_coinduction_foundation_gate.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/coinduction-gate-queue-phrase-robustness-2026-06-29_2026-06-29.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/l4_gates/test_coinduction_foundation_gate.py`, `reports/control_plane/coinduction-gate-queue-phrase-robustness-2026-06-29_2026-06-29.md`, `reports/deferred/non_blocking/coinduction-gate-queue-phrase-robustness-2026-06-29_bridge_nonblockers.md`, `reports/l4_wave_indicators/coinduction-gate-queue-phrase-robustness-2026-06-29.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: coinduction-gate-queue-phrase-robustness-2026-06-29.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `coinduction-gate-queue-phrase-robustness-2026-06-29`
- Active packet: `reports/control_plane/coinduction-gate-queue-phrase-robustness-2026-06-29_2026-06-29.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `236952376637096cd876c44210d18f4b909c787b9f421c6f7c2320b578e154ed`
- Indicator artifact: `reports/l4_wave_indicators/coinduction-gate-queue-phrase-robustness-2026-06-29.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_coinduction_foundation_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/coinduction-gate-queue-phrase-robustness-2026-06-29_2026-06-29.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/l4_gates/test_coinduction_foundation_gate.py`, `reports/control_plane/coinduction-gate-queue-phrase-robustness-2026-06-29_2026-06-29.md`, `reports/deferred/non_blocking/coinduction-gate-queue-phrase-robustness-2026-06-29_bridge_nonblockers.md`, `reports/l4_wave_indicators/coinduction-gate-queue-phrase-robustness-2026-06-29.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/coinduction-gate-queue-phrase-robustness-2026-06-29.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/test_coinduction_foundation_gate.py`
  - `reports/control_plane/coinduction-gate-queue-phrase-robustness-2026-06-29_2026-06-29.md`
  - `reports/deferred/non_blocking/coinduction-gate-queue-phrase-robustness-2026-06-29_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/coinduction-gate-queue-phrase-robustness-2026-06-29.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
