# Structural-Numbers-Arith-Subtract-2026-06-18 2026-06-18

Date: 2026-06-18
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: structural-numbers-arith-subtract-2026-06-18
Phase-A-Lock: LOCKED
Purpose: StructuralNumbers Stage 3 prereq (Python-only subtract): L4_ENABLER gate proving integer SUBTRACT as RCX binary subtract-with-borrow projections via run_mu, signed result (neg form for a<b, canonical zero for a==b), structurally equal to encode(a-b) + decoding to the host difference; run_mu classes l4_expensive, growth cap pre-bumped. Stage 3 tower wave 3. JS parity deferred.

## Scope

Files/directories in scope (additive, gate-only `L4_ENABLER`; no runtime/substrate change):

**Primary edit surface**
- `mu/tests/l4_gates/test_structural_numbers_subtract.py` (NEW) — the wave's `structural_artifact_ref`. A `run_mu` (Python) L4 gate proving integer SUBTRACT as RCX binary subtract-with-borrow projections plus a structural-compare sign decision (linear patterns).
- `mu/tests/docs/test_growth_caps.py` (EDIT) — pre-bump the `CAP_TEST_FILES` growth cap by +1 (141 -> 142) with a wave-attributed comment, accounting for the one new gate file above.

**Pipeline-managed / generated (not hand-authored runtime code)**
- `reports/control_plane/structural-numbers-arith-subtract-2026-06-18_2026-06-18.md` (THIS packet) — the Phase A plan authored here.
- `TASKS.md` — the wave's tracker sync note already exists under `[NEXT-CODEX-POST-REDTEAM]`; the pipeline updates wave status on completion.
- `reports/l4_wave_indicators/structural-numbers-arith-subtract-2026-06-18.json` (GENERATED) — produced by the `indicator_collection_command`; not hand-edited.

Out-of-scope directories are enumerated under Constraints below.

- `reports/deferred/non_blocking/structural-numbers-arith-subtract-2026-06-18_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Request from Post-Merge Supervisor

StructuralNumbers Stage 3 prereq (Python-only subtract): L4_ENABLER gate proving integer SUBTRACT as RCX binary subtract-with-borrow projections via run_mu, signed result (neg form for a<b, canonical zero for a==b), structurally equal to encode(a-b) + decoding to the host difference; run_mu classes l4_expensive, growth cap pre-bumped. Stage 3 tower wave 3. JS parity deferred.

Routed next-candidate:
structural-numbers-arith-subtract-2026-06-18

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/structural-numbers-arith-subtract-2026-06-18.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id structural-numbers-arith-subtract-2026-06-18 --output reports/l4_wave_indicators/structural-numbers-arith-subtract-2026-06-18.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_subtract.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-arith-subtract-2026-06-18_2026-06-18.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: structural-numbers-arith-subtract-2026-06-18) (standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md; auto-appended by build_commit_handoff for commit-gate + pre-push adjacency-cap clearance)
<!-- L4_FIELDS_FROM_TRACKER:end -->


## Work items

Concrete bounded tasks for this wave (from the canonical TASKS.md tracker sync note `2026-06-18, structural-numbers-arith-subtract-2026-06-18`):

1. **WI-1 -- Author the SUBTRACT gate.** Create `mu/tests/l4_gates/test_structural_numbers_subtract.py`: a `run_mu` (Python) gate proving integer SUBTRACT is expressible as RCX projections -- binary subtract-with-borrow plus a structural-compare sign decision, using linear (non-nesting) patterns in the established StructuralNumbers style. The projected result must be structurally identical to `encode(a-b)`: the negative (neg) form for `a < b`, canonical zero for `a == b`, the positive form for `a > b`; decoding the projected result must equal the host difference `a - b`. Cover a corpus that exercises borrow cascades (e.g. `100-1`, `1000-1`, equal operands, and `a < b` sign flips).
2. **WI-2 -- Cost-classify the run_mu cases.** Mark the run_mu-driven test classes `l4_expensive` + `slow` so they are green-gate-excluded and run nightly under the 900s timeout, matching the ADD / COMPARE / MULTIPLY sibling gates.
3. **WI-3 -- Pre-bump the file growth cap.** In `mu/tests/docs/test_growth_caps.py`, raise `CAP_TEST_FILES` from 141 to 142 (+1 for the single new gate file) and append a wave-attributed `+1 for test_structural_numbers_subtract.py (... FOUNDER_OVERRIDE:structural-numbers-arith-subtract-2026-06-18)` note to the cap comment, matching the existing sibling-wave entries.

## Constraints (NOT in scope)

- **`L4_ENABLER` boundary.** This is a tooling/gate prerequisite. It MUST NOT touch runtime/substrate dirs -- no edits to `mu/host/python/rcx_pi/selfhost/`, `mu/host/js/`, or any seed/runtime/substrate sources. Test file + growth-cap doc only.
- **No host subtraction primitive.** SUBTRACT must be expressed as RCX subtract-with-borrow projections. No host `-` operator may be introduced into the bootstrap; net host-semantics delta must be 0 (enforced by `check_host_semantics_ratchet.py` and the bootstrap purity ratchet). A solution requiring a host primitive is a POLICY_BOUND escalation, not an implementation choice.
- **No ratchet or authority increase.** No growth in host-authority inventory; no bootstrap purity regression; no new seeds.
- **Python-only; JS parity DEFERRED.** This wave proves SUBTRACT in the Python `run_mu` substrate only. JS cross-substrate parity is a separate downstream wave (mirroring the landed add/compare/codec/multiply JS-parity waves) and is explicitly NOT in scope here.
- **Additive, not a refactor.** Does not modify the landed ADD / COMPARE / CODEC / MULTIPLY projections or their gates.
- **Does not implement downstream consumers.** The structural gcd (Euclidean) and the Stage-3 rational tower are *unblocked* by this gate but are NOT implemented in this wave.

## Stop conditions

- **Phase A (this turn).** Stop once this packet carries the six required sections (Scope, Work items, Constraints, Stop conditions, Acceptance criteria, Grounding / Authorization) and clears bridge review. Do NOT begin implementing the gate test in Phase A.
- **Phase B (implementation).** Stop when the `evidence_command` passes green, the host-semantics ratchet is clean, and the growth-cap gate passes at `CAP_TEST_FILES = 142`, with no runtime/substrate/seed/host-authority change.
- **Escalate, do NOT bypass, if:** (a) integer SUBTRACT cannot be expressed without a host `-` (escalate to founder as POLICY_BOUND -- the North Star forbids adding host capability to the bootstrap); (b) the run_mu corpus exceeds the nightly 900s budget (lean the corpus rather than weaken the assertion); (c) the cap bump or gate would require touching a runtime dir (re-scope -- do not relax the `L4_ENABLER` boundary).
- Never use `--no-verify` or hand-edit `mu/` runtime files; commits go through the executor pipeline only.

## Acceptance criteria

- **Evidence command passes** (the wave's `evidence_command`): `PYTHONHASHSEED=0 python3 -m pytest -q -m l4_expensive mu/tests/l4_gates/test_structural_numbers_subtract.py --timeout=900 --tb=short && python3 mu/tools/checks/check_host_semantics_ratchet.py`.
- **Structural identity proven over the borrow-cascade corpus.** For each `(a, b)` case, the `run_mu` subtract projection yields a result structurally identical to `encode(a-b)` -- neg form for `a < b`, canonical zero for `a == b`, positive form for `a > b` -- and decoding the projected result equals the host difference `a - b`.
- **Host-semantics ratchet clean.** `check_host_semantics_ratchet.py` reports net host-semantics delta 0 (no host `-` introduced); the bootstrap purity ratchet is unchanged.
- **Cost classification honored.** The run_mu cases are marked `l4_expensive` + `slow` (excluded from the green gate; run nightly under 900s).
- **Growth-cap gate green.** `mu/tests/docs/test_growth_caps.py` passes with `CAP_TEST_FILES = 142` and a wave-attributed comment for the new gate file.
- **Indicator artifact present.** `reports/l4_wave_indicators/structural-numbers-arith-subtract-2026-06-18.json` is (re)generated via the `indicator_collection_command`.
- **No runtime/substrate/seed change.** The diff touches only the new gate test, the growth-cap doc, this packet, and pipeline-managed tracker/indicator artifacts.

## Grounding / Authorization

- **TASKS.md authorization.** Tracker sync note `(2026-06-18, structural-numbers-arith-subtract-2026-06-18)` under `[NEXT-CODEX-POST-REDTEAM]` -- Class `L4_ENABLER`, `target_gate_id: G8`, `primary_blocker_class: INTEGRATION`, `primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION`. The note names this file as the governing `Packet:` and `mu/tests/l4_gates/test_structural_numbers_subtract.py` as the `structural_artifact_ref`.
- **Governing packet.** `reports/control_plane/structural-numbers-arith-subtract-2026-06-18_2026-06-18.md` (this file). The auto-derived L4 fields block above is the single source of truth and is not hand-edited.
- **Wave-bound override.** `FOUNDER_OVERRIDE:structural-numbers-arith-subtract-2026-06-18) (standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md; auto-appended by build_commit_handoff for commit-gate + pre-push adjacency-cap clearance)` -- present in the TASKS.md tracker note and mirrored here so commit automation derives the same-wave override mechanically.
- **Precedent (Stage 3 tower wave 3).** Follows the landed sibling gates whose attributions already appear in the `CAP_TEST_FILES` comment trail -- `test_structural_numbers_add.py`, `test_structural_numbers_compare.py`, `test_structural_numbers_codec.py`, `test_structural_numbers_multiply.py` (and their `*_js_parity.py` waves). SUBTRACT unblocks the structural gcd (Euclidean) and the Stage-3 rational tower.

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `structural-numbers-arith-subtract-2026-06-18`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/structural-numbers-arith-subtract-2026-06-18_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `structural-numbers-arith-subtract-2026-06-18`
- Active packet: `reports/control_plane/structural-numbers-arith-subtract-2026-06-18_2026-06-18.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `0c005161e97d5e9598775cdfcd7d70ec68990493151d42e047b720ee891e2240`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-arith-subtract-2026-06-18.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_subtract.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-arith-subtract-2026-06-18_2026-06-18.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/structural-numbers-arith-subtract-2026-06-18.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_structural_numbers_subtract.py`
  - `reports/control_plane/structural-numbers-arith-subtract-2026-06-18_2026-06-18.md`
  - `reports/deferred/non_blocking/structural-numbers-arith-subtract-2026-06-18_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/structural-numbers-arith-subtract-2026-06-18.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
