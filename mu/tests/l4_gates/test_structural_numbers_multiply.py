"""L4 gate: StructuralNumbers integer MULTIPLY — arithmetic as RCX projections.

Stage 3 prerequisite gate for ``mu/docs/core/StructuralNumbers.v0.md`` (Python-only
slice). Proves, without any runtime/substrate/seed change, that integer MULTIPLY on
the binary-positional structural numeral is **expressible as RCX projections** — as
**shift-and-add composing the already-landed binary ADD-with-carry** — driven by the
real kernel driver ``run_mu`` on the Python substrate. The governing obligation is
the cross-form equivalence of ``StructuralNumbers.v0.md`` §7 (the MULTIPLY analog of
the landed ADD gate's §7.3)::

    structural_mul(a, b)  ≡  host_to_structural( to_host(a) * to_host(b) )

i.e. the ``run_mu`` result must be a **valid canonical** StructuralNumbers numeral
that is **structurally / content-hash equal** to ``encode(a * b)``. A decode-to-host
check (``decode(result) == a * b``) is retained as a *supporting* assertion only — a
result that decodes correctly yet is non-canonical or not hash-equal to
``encode(a * b)`` is a gate **failure**.

Composition (NOT reimplementation): the binary ADD is **not** rebuilt here. The
landed ``ADD_PROJECTIONS`` table, the codec, and ``_v`` are **imported** from
``test_structural_numbers_add`` (single source of truth), and each ADD projection is
**lifted verbatim** into a ``_mul_add`` work-slot (carrying the multiplicand and the
remaining-multiplier registers through untouched). ``test_multiply_composes_landed_add``
locks this mechanically: every lifted work-slot **is** the corresponding landed ADD
projection. The engine performs the multiply; the only host arithmetic in this file
is the test *oracle* ``encode(a * b)`` and the imported codec construction (the
``check_host_semantics_ratchet.py`` scan covers only ``rcx_pi/selfhost`` and
``mu/host/js`` — never ``mu/tests/`` — so this test-only oracle is not a
host-authority site).

The MULTIPLY machine is a pure structural state machine over single-key Mu (every
intermediate state is valid ``is_mu``):

  * step  ``{"_mul_step": {p, m, r}}``  — peel the LSB of the remaining multiplier r:
      r == 0 -> emit the product p (the §7 fixpoint); r even (xO) -> double m;
      r odd (xI / xH) -> add m to p (sub-machine), then double m. (shift-and-add)
  * add   ``{"_mul_add": {work, m, r}}`` — run the lifted landed ADD on (p, m); when
      ``work`` reduces to ``{"_num": ...}`` the product resumes (double m).
  * double``{"_mul_dbl": {p, m, r}}``   — m *= 2 (prepend ``xO``; ``0`` stays ``0``).
  * fixpoint ``{"_num": ...}``          — natural stall (the §7 result).

Two REAL kernel constraints bound the corpus (documented, not worked around):
``run_mu`` → ``step_kernel_mu`` runs ``normalize_for_match`` (inflates dict depth ~3×)
and re-validates the whole state on each meta-circular VM micro-step. The MULTIPLY
state (loop registers + the lifted ADD sub-machine) is larger than ADD's, so the
per-step cost is higher and grows with operand size (measured ~1–3s/domain-step).
The corpus is therefore deliberately lean (small operands, 7 cases, ~140s locally) —
the engine-driving tests are ``@pytest.mark.slow`` + ``@pytest.mark.l4_expensive``
(run in the nightly l4_expensive lane at 900s, excluded from the fast green gate) per
``.claude/rules/test-classification.md``. This is the first wave of the Stage-3 tower;
JS cross-substrate parity and division / rationals are deferred to follow-up waves.

Wave: structural-numbers-arith-multiply-2026-06-18 (L4_ENABLER, target gate G8).
Encoding authority: ``mu/docs/core/StructuralNumbers.v0.md`` §3.1, §3.3, §7.
Composed artifact: ``test_structural_numbers_add.py`` (the landed ADD projections).
"""
from __future__ import annotations

import pytest

from rcx_pi.selfhost.step_mu import run_mu
from rcx_pi.selfhost.mu_type import is_mu, mu_hash

# Single source of truth: compose the LANDED binary ADD. The projection table, the
# codec (encode/decode), and the var-site helper are imported (never re-derived) so
# this gate proves MULTIPLY over the SAME add-with-carry that the ADD gate locks.
from tests.l4_gates.test_structural_numbers_add import (
    ADD_PROJECTIONS,
    decode,
    encode,
    _v,
)


# =============================================================================
# MULTIPLY projection — test-local Mu projection scaffolding (the wave's structural
# artifact). Shift-and-add over the binary-positional numeral, composing the landed
# ADD. Every pattern is linear (each variable appears once) — required by ``run_mu``.
# =============================================================================

# Carry-register var names for the lifted ADD: chosen to NOT collide with any
# variable used inside an ADD pattern (a, b, pa, pb, ra, rb, acc, rest, n).
_MCARRY = "__mcarry"
_RCARRY = "__rcarry"


def _lift_add_into_mul(add_projs: list[dict]) -> list[dict]:
    """Lift each landed ADD projection into a ``_mul_add`` work-slot.

    The ADD pattern/body is placed verbatim in ``work``; the multiplicand ``m`` and
    the remaining-multiplier ``r`` registers ride through unchanged as carry
    variables. The ADD sub-machine therefore reduces ``work`` from ``{"_add": ...}``
    to ``{"_num": ...}`` exactly as it does standalone, while ``m`` / ``r`` are
    preserved for the surrounding shift-and-add loop. Linearity is preserved (the
    carry vars are disjoint from every ADD pattern variable).
    """
    lifted: list[dict] = []
    for proj in add_projs:
        lifted.append({
            "pattern": {"_mul_add": {"work": proj["pattern"],
                                     "m": _v(_MCARRY), "r": _v(_RCARRY)}},
            "body": {"_mul_add": {"work": proj["body"],
                                  "m": _v(_MCARRY), "r": _v(_RCARRY)}},
        })
    return lifted


def build_mul_projections() -> list[dict]:
    """Construct the shift-and-add MULTIPLY projection table (46 linear projections).

    Layout: 4 step (dispatch) + 1 add-resume + 39 lifted ADD + 2 double.
    """
    projs: list[dict] = []

    # -- step: peel the LSB of the remaining multiplier r and dispatch (shift-and-add).
    #    r forms are disjoint ({"_num": null} vs xO/xI/xH), so step order is free.
    # r == 0  -> done: emit the accumulated product p as the canonical numeral (fixpoint).
    projs.append({"pattern": {"_mul_step": {"p": {"_num": _v("pp")}, "m": _v("m"),
                                            "r": {"_num": None}}},
                  "body": {"_num": _v("pp")}})                          # product
    # r even (xO): low bit 0 -> no add; double m; continue with r >> 1.
    projs.append({"pattern": {"_mul_step": {"p": _v("p"), "m": _v("m"),
                                            "r": {"_num": {"xO": _v("rr")}}}},
                  "body": {"_mul_dbl": {"p": _v("p"), "m": _v("m"),
                                        "r": {"_num": _v("rr")}}}})
    # r odd (xI): low bit 1 -> add m to p (sub-machine); carry m + r >> 1.
    projs.append({"pattern": {"_mul_step": {"p": _v("p"), "m": _v("m"),
                                            "r": {"_num": {"xI": _v("rr")}}}},
                  "body": {"_mul_add": {"work": {"_add": {"a": _v("p"), "b": _v("m")}},
                                        "m": _v("m"), "r": {"_num": _v("rr")}}}})
    # r == 1 (xH): low bit 1, last bit -> add m to p; carry m + r >> 1 (= 0).
    projs.append({"pattern": {"_mul_step": {"p": _v("p"), "m": _v("m"),
                                            "r": {"_num": {"xH": None}}}},
                  "body": {"_mul_add": {"work": {"_add": {"a": _v("p"), "b": _v("m")}},
                                        "m": _v("m"), "r": {"_num": None}}}})

    # -- add-resume: the lifted ADD has reduced work to {"_num": ...}; the product is
    #    updated -> resume the loop by doubling m. (work shapes {"_add"/"_bits"/"_fold"}
    #    are disjoint from {"_num"}, so this never races the lifted ADD rules.)
    projs.append({"pattern": {"_mul_add": {"work": {"_num": _v("pp")},
                                           "m": _v("m"), "r": _v("r")}},
                  "body": {"_mul_dbl": {"p": {"_num": _v("pp")},
                                        "m": _v("m"), "r": _v("r")}}})

    # -- lifted ADD sub-machine: composes the LANDED add-with-carry (verbatim).
    projs.extend(_lift_add_into_mul(ADD_PROJECTIONS))

    # -- double: m *= 2, then back to step. The zero rule MUST precede the positive
    #    rule: {"_num": {"var": "mm"}} also matches {"_num": null} (mm <- null), which
    #    would mint a malformed {"_num": {"xO": null}}. First-match-wins -> zero first.
    projs.append({"pattern": {"_mul_dbl": {"p": _v("p"), "m": {"_num": None},
                                           "r": _v("r")}},
                  "body": {"_mul_step": {"p": _v("p"), "m": {"_num": None},
                                         "r": _v("r")}}})               # 2*0 = 0
    projs.append({"pattern": {"_mul_dbl": {"p": _v("p"), "m": {"_num": _v("mm")},
                                           "r": _v("r")}},
                  "body": {"_mul_step": {"p": _v("p"), "m": {"_num": {"xO": _v("mm")}},
                                         "r": _v("r")}}})               # 2*m: prepend xO
    return projs


MUL_PROJECTIONS = build_mul_projections()


# =============================================================================
# Corpus — lean (the engine cost grows with operand size), non-negative, covers every
# MULTIPLY path: zero-terminate, ×0, 0× (multiplicand stays 0 across shifts), unit×unit,
# ×1 (single iteration), adjacent set bits with a composed bit-add carry, and an
# interior zero bit (xO skip) with a composed bit-add carry.
# =============================================================================

CORPUS: list[tuple[int, int]] = [
    (0, 0),   # zero × zero
    (6, 0),   # × zero (b = 0): immediate terminate, product 0
    (0, 6),   # zero × (a = 0): multiplicand stays 0 across the shifts
    (1, 1),   # unit × unit (single xH add)
    (7, 1),   # × one (b = 1): single iteration, product = a
    (3, 3),   # adjacent set bits; composed bit-add with carry (3 + 6 = 9)
    (5, 5),   # interior zero bit (xO skip) + composed bit-add with carry (5 + 20 = 25)
]

# Required paths must actually be present (guards against silent corpus drift).
assert (0, 0) in CORPUS, "corpus must include zero × zero"
assert (6, 0) in CORPUS, "corpus must include × zero (b = 0 early terminate)"
assert (0, 6) in CORPUS, "corpus must include zero × (a = 0 shift-through)"
assert (1, 1) in CORPUS, "corpus must include unit × unit"
assert (5, 5) in CORPUS, "corpus must include an interior-zero-bit (xO skip) product"


def run_multiply(a: int, b: int) -> tuple[dict, int, bool]:
    """Multiply ``a`` and ``b`` via the test-local MULTIPLY projection driven by ``run_mu``.

    The ENGINE performs the multiplication: the only inputs are the encoded numerals
    ``encode(a)`` / ``encode(b)``; ``run_mu`` shifts, adds (via the lifted landed ADD),
    and folds them structurally. Returns ``(result_numeral, step_count, stalled)``.
    """
    state = {"_mul_step": {"p": encode(0), "m": encode(a), "r": encode(b)}}
    result, trace, stalled = run_mu(MUL_PROJECTIONS, state, max_steps=20000)
    return result, len(trace), stalled


# Computed once per process (each run_mu multiply is meta-circular and costly).
_MUL_CACHE: dict[tuple[int, int], tuple[dict, int, bool]] | None = None


def _mul_results() -> dict[tuple[int, int], tuple[dict, int, bool]]:
    global _MUL_CACHE
    if _MUL_CACHE is None:
        _MUL_CACHE = {(a, b): run_multiply(a, b) for (a, b) in CORPUS}
    return _MUL_CACHE


def _numeral_nodes_all_single_key(value) -> bool:
    """Every node of a StructuralNumbers numeral is a single-key dict (or null)."""
    if value is None:
        return True
    if not isinstance(value, dict) or len(value) != 1:
        return False
    return _numeral_nodes_all_single_key(next(iter(value.values())))


def _collect_vars(node, out: list[str]) -> None:
    """Collect variable names from a pattern (``{"var": name}`` sites)."""
    if isinstance(node, dict):
        if set(node) == {"var"} and isinstance(node["var"], str):
            out.append(node["var"])
            return
        for child in node.values():
            _collect_vars(child, out)


# =============================================================================
# Fast scaffolding sanity (no run_mu) — the projection table is well-formed, linear,
# and genuinely composes the landed ADD. These run in every tier (not slow).
# =============================================================================

class TestProjectionScaffolding:
    """The MULTIPLY projection table is linear and composes the landed ADD verbatim."""

    def test_projection_count(self):
        # 4 step + 1 add-resume + 39 lifted ADD + 2 double = 46.
        assert len(MUL_PROJECTIONS) == 46
        assert len(ADD_PROJECTIONS) == 39  # the composed (landed) ADD table

    def test_every_projection_has_pattern_and_body(self):
        for proj in MUL_PROJECTIONS:
            assert set(proj) == {"pattern", "body"}

    def test_all_projections_are_linear(self):
        """``run_mu`` rejects non-linear patterns; assert it up front (fast lane)."""
        for proj in MUL_PROJECTIONS:
            names: list[str] = []
            _collect_vars(proj["pattern"], names)
            assert len(names) == len(set(names)), (
                f"non-linear pattern (variable repeated): {proj['pattern']}"
            )

    def test_multiply_composes_landed_add(self):
        """MULTIPLY composes the LANDED add (not a copy): every landed ADD projection,
        lifted into the ``_mul_add`` work-slot, appears verbatim in MUL_PROJECTIONS,
        and each lifted work-slot IS the corresponding landed ADD pattern/body."""
        lifted = _lift_add_into_mul(ADD_PROJECTIONS)
        for add_proj, lifted_proj in zip(ADD_PROJECTIONS, lifted):
            assert lifted_proj["pattern"]["_mul_add"]["work"] == add_proj["pattern"]
            assert lifted_proj["body"]["_mul_add"]["work"] == add_proj["body"]
            assert lifted_proj in MUL_PROJECTIONS, (
                "a lifted landed-ADD projection is missing from MUL_PROJECTIONS"
            )
        # The carry registers ride through every lifted ADD step untouched.
        for lifted_proj in lifted:
            for side in ("pattern", "body"):
                wrap = lifted_proj[side]["_mul_add"]
                assert wrap["m"] == _v(_MCARRY) and wrap["r"] == _v(_RCARRY)

    def test_codec_round_trips_corpus(self):
        operands = {x for pair in CORPUS for x in pair}
        products = {a * b for a, b in CORPUS}
        for n in operands | products:
            assert decode(encode(n)) == n, f"codec round-trip failed for {n}"

    def test_corpus_is_non_negative(self):
        for a, b in CORPUS:
            assert a >= 0 and b >= 0


# =============================================================================
# Governing assertion (StructuralNumbers.v0.md §7): the run_mu MULTIPLY result is a
# valid canonical numeral, structurally / hash-equal to encode(a * b).
# =============================================================================

@pytest.mark.l4_expensive
@pytest.mark.slow
class TestStructuralMultiplyEquivalence:
    """structural_mul(a,b) ≡ host_to_structural(to_host(a) * to_host(b))."""

    def test_canonical_structural_equality(self):
        """GOVERNING: run_mu(mul) result is structurally identical to encode(a*b)."""
        results = _mul_results()
        for a, b in CORPUS:
            result, _, _ = results[(a, b)]
            assert result == encode(a * b), (
                f"structural MULTIPLY diverged from encode({a}*{b}={a * b}): got {result}"
            )

    def test_content_hash_equality(self):
        """The result is content-addressed equal to encode(a*b) (free equality)."""
        results = _mul_results()
        for a, b in CORPUS:
            result, _, _ = results[(a, b)]
            assert mu_hash(result) == mu_hash(encode(a * b)), (
                f"content-hash divergence for {a}*{b}"
            )

    def test_result_is_valid_canonical_numeral(self):
        """Result is well-formed Mu, single-key numeral nodes, in canonical form.

        Canonicality is asserted oracle-independently: a canonical numeral is a fixed
        point of encode∘decode (no spurious leading-zero bits could survive).
        """
        results = _mul_results()
        for a, b in CORPUS:
            result, _, _ = results[(a, b)]
            assert is_mu(result), f"result for {a}*{b} is not valid Mu: {result}"
            assert "_num" in result and len(result) == 1, (
                f"result for {a}*{b} is not an N numeral wrapper: {result}"
            )
            assert _numeral_nodes_all_single_key(result["_num"]), (
                f"result for {a}*{b} has a non-single-key numeral node"
            )
            assert result == encode(decode(result)), (
                f"result for {a}*{b} is non-canonical: {result}"
            )

    def test_engine_reaches_stall_fixpoint(self):
        """run_mu converged to the {"_num": ...} fixpoint (not max_steps), and the
        result is NOT an unprocessed MULTIPLY state — proving the engine transformed it."""
        results = _mul_results()
        for a, b in CORPUS:
            result, steps, stalled = results[(a, b)]
            assert stalled is True, f"run_mu did not stall for {a}*{b} (steps={steps})"
            for state_key in ("_mul_step", "_mul_add", "_mul_dbl"):
                assert state_key not in result, (
                    f"result for {a}*{b} is still an unprocessed {state_key} state"
                )

    def test_decode_to_host_supporting(self):
        """SUPPORTING ONLY (not sufficient): the result decodes to host a * b."""
        results = _mul_results()
        for a, b in CORPUS:
            result, _, _ = results[(a, b)]
            assert decode(result) == a * b, (
                f"decode(run_mu mul) = {decode(result)} != {a}*{b} = {a * b}"
            )


# =============================================================================
# Shift-and-add spotlight — explicit checks on the representative products (same
# cached runs): ×0, 0×, ×1, and the two composed-bit-add (carry) cases.
# =============================================================================

@pytest.mark.l4_expensive
@pytest.mark.slow
class TestShiftAndAdd:
    """MULTIPLY exercises the shift-and-add loop end-to-end, composing the ADD."""

    def test_times_zero_terminates(self):
        result, _, _ = _mul_results()[(6, 0)]
        assert result == encode(0)                  # b = 0 -> immediate terminate

    def test_zero_times_shifts_through(self):
        result, _, _ = _mul_results()[(0, 6)]
        assert result == encode(0)                  # a = 0 -> multiplicand stays 0

    def test_times_one_is_identity(self):
        result, _, _ = _mul_results()[(7, 1)]
        assert result == encode(7)                  # b = 1 -> single iteration

    def test_adjacent_bits_with_add_carry(self):
        result, _, _ = _mul_results()[(3, 3)]
        assert result == encode(9)                  # 3 + 6 = 9 (composed ADD carry)

    def test_interior_zero_bit_skip_with_add_carry(self):
        result, _, _ = _mul_results()[(5, 5)]
        assert result == encode(25)                 # 5 + 20 = 25 (xO skip + ADD carry)
