"""L4 gate: StructuralNumbers binary COMPARE — ordering as RCX projections.

Stage 2b gate for ``mu/docs/core/StructuralNumbers.v0.md`` (Python-only slice).
Proves, without any runtime/substrate/seed change, that binary COMPARE (``<``/``=``
in §3.3, the three-way EQ/LT/GT ordering) on the binary-positional structural
numeral is **expressible as RCX projections**: the COMPARE machine is defined here
as **test-local Mu projection scaffolding** and executed via the real kernel driver
``run_mu`` on the Python substrate. The governing obligation is the cross-form
equivalence of the §3.3 ordering operation::

    structural_compare(a, b)  ≡  host_to_ord( (to_host(a) > to_host(b))
                                             - (to_host(a) < to_host(b)) )

i.e. the ``run_mu`` result must be a **canonical ordering tag** (exactly one of
EQ/LT/GT) that is **structurally / content-hash equal** to ``encode_ord(sign)``,
where ``sign = (a > b) - (a < b)`` is the host three-way comparison. A
decode-to-host check (``decode_ord(result) == sign``) is retained as a *supporting*
assertion only — a result that decodes correctly yet is non-canonical or not
hash-equal to ``encode_ord(sign)`` is a gate **failure**.

Scope: GATE-ONLY (mirrors the Stage 2a ADD gate ``test_structural_numbers_add.py``).
The encode/decode codec AND the COMPARE projection are defined locally in this test
— they are test scaffolding, not runtime code. This wave introduces **no**
``mu/seeds/numerals.v1.json`` (the runtime arithmetic-projection seed of
``StructuralNumbers.v0.md`` §3.3 / §8 Stage 2); it proves COMPARE is *expressible*
as a projection on a minimal Python-only slice first. No ``_stage0_match`` cutover,
no host-authority delta, and **no host comparison primitive** — the ordering is
decided **structurally** by the projection (most-significant-difference-decides);
the only host comparison in this file is the test *oracle* ``(a > b) - (a < b)``.

The COMPARE machine is the direct analogue of Coq ``Pos.compare_cont``: a running
ordering accumulator is carried LSB→MSB so that the **most-significant differing
bit** decides, and a length difference (one operand's leading ``xH`` outranks the
other's bits) is itself the most-significant difference. Every intermediate state
is valid single-key ``is_mu``; every pattern is linear (each variable appears once)
— required by ``run_mu``:

  * dispatch ``{"_cmp": {a, b}}``  — zero/zero → EQ, zero/positive → LT,
    positive/zero → GT, else enter the bit loop seeded with EQ.
  * bit loop ``{"_cc": {a, b, r}}`` — peel the LSB of a and b (full 3×3 form table):
    equal bits keep the running tag ``r``; a differing bit *overwrites* ``r`` with
    its local decision (so a higher differing bit always wins); a length mismatch
    (one side reaches ``xH`` first) terminates immediately with GT/LT; both reaching
    ``xH`` together emits the accumulated ``r``.
  * fixpoint ``{"_ord": {eq|lt|gt}}`` — natural stall (the §3.3 ordering result).

Two REAL kernel constraints bound the corpus (documented, not worked around):
``run_mu`` → ``step_kernel_mu`` runs ``normalize_for_match`` which inflates every
dict level ~3× (depth), and each meta-circular VM micro-step re-validates the whole
state (~0.6s / domain-step). So the corpus is deliberately lean (≤ 4-bit operands,
~18 ``run_mu`` evaluations incl. swaps) and the engine-driving tests are
``@pytest.mark.slow`` + ``@pytest.mark.l4_expensive`` (the run_mu meta-circular cost
exceeds the green-gate slow-lane 300s timeout, so they run in the slow_tests/nightly
lane at 900s) per ``.claude/rules/test-classification.md``. JS cross-substrate parity
for COMPARE is deferred to a follow-up wave (mirrors the ADD wave).

Wave: structural-numbers-arith-compare-2026-06-18 (L4_ENABLER, target gate G8).
Encoding authority: ``mu/docs/core/StructuralNumbers.v0.md`` §3.1, §3.3.
Predecessor (Stage 2a ADD-as-projections): ``test_structural_numbers_add.py``.
"""
from __future__ import annotations

import pytest

from rcx_pi.selfhost.step_mu import run_mu
from rcx_pi.selfhost.mu_type import is_mu, mu_hash


# =============================================================================
# Numeral codec — test-local, mirrors StructuralNumbers.v0.md §3.1 and the
# ADD/foundation gates' codec (binary, least-significant-bit outermost):
#   {"xH": null} = 1 ,  {"xO": r} = 2·r ,  {"xI": r} = 2·r+1
#   0 -> {"_num": null} ,  +p -> {"_num": p}
# COMPARE is over non-negative integers only (subtraction/negatives are out of
# scope for this wave per StructuralNumbers Stage 2), so the ``neg`` arm is unused.
# =============================================================================


def encode_positive(p: int) -> dict:
    """Encode a host int ``p >= 1`` to a binary-positional ``positive`` numeral."""
    assert p >= 1
    lower_bits = []
    while p > 1:
        lower_bits.append(p & 1)
        p >>= 1
    node: dict = {"xH": None}  # the highest set bit terminates the recursion
    for bit in reversed(lower_bits):
        node = {"xI": node} if bit else {"xO": node}
    return node


def encode(n: int) -> dict:
    """Encode a non-negative host int to the ``N`` Mu numeral (§3.1)."""
    assert n >= 0, "COMPARE gate corpus is non-negative (no subtraction this wave)"
    if n == 0:
        return {"_num": None}
    return {"_num": encode_positive(n)}


def decode_positive(node: dict) -> int:
    """Decode a ``positive`` numeral back to a host int (>= 1)."""
    value = 0
    weight = 1
    while True:
        key = next(iter(node))
        if key == "xH":
            return value + weight
        if key == "xI":
            value += weight
        node = node[key]
        weight <<= 1


def decode(mu: dict) -> int:
    """Decode an ``N`` Mu numeral back to a host int (inverse of ``encode``)."""
    inner = mu["_num"]
    if inner is None:
        return 0
    return decode_positive(inner)


# =============================================================================
# Ordering-tag codec — the COMPARE analogue of the numeral codec. The three-way
# comparison result is a canonical single-key Mu tag wrapped in ``_ord`` (mirrors
# the ``_num`` wrapper). The host three-way sign is ``(a > b) - (a < b)``:
#   -1 (a < b) -> {"_ord": {"lt": null}}
#    0 (a = b) -> {"_ord": {"eq": null}}
#   +1 (a > b) -> {"_ord": {"gt": null}}
# =============================================================================

_ORD_TAG_BY_SIGN = {-1: "lt", 0: "eq", 1: "gt"}
_SIGN_BY_ORD_TAG = {tag: sign for sign, tag in _ORD_TAG_BY_SIGN.items()}


def encode_ord(sign: int) -> dict:
    """Encode a host three-way sign (-1/0/+1) to the canonical ``_ord`` Mu tag."""
    assert sign in _ORD_TAG_BY_SIGN, f"sign must be -1/0/+1, got {sign}"
    return {"_ord": {_ORD_TAG_BY_SIGN[sign]: None}}


def decode_ord(mu: dict) -> int:
    """Decode an ``_ord`` Mu tag back to the host three-way sign (inverse of encode_ord)."""
    inner = mu["_ord"]
    return _SIGN_BY_ORD_TAG[next(iter(inner))]


def host_sign(a: int, b: int) -> int:
    """The host three-way comparison oracle: (a > b) - (a < b) ∈ {-1, 0, +1}."""
    return (a > b) - (a < b)


# =============================================================================
# Binary COMPARE projection — test-local Mu projection scaffolding (the wave's
# structural artifact). Built mechanically from the full 3×3 LSB-form table so the
# transition relation is provably TOTAL over every reachable state. Every pattern
# is linear (each variable appears once) — required by ``run_mu``. The ordering is
# decided STRUCTURALLY (no host comparison primitive inside any projection).
# =============================================================================


def _v(name: str) -> dict:
    """A pattern/​body variable site ``{"var": name}``."""
    return {"var": name}


_LT = {"lt": None}              # running/terminal ordering markers (structural tags)
_EQ = {"eq": None}
_GT = {"gt": None}


def build_compare_projections() -> list[dict]:
    """Construct the binary-COMPARE projection table (13 linear projections)."""
    projs: list[dict] = []

    # -- dispatch: zero cases first (0 vs 0 = EQ, 0 vs +b = LT, +a vs 0 = GT), then
    #    the both-positive entry which seeds the running ordering accumulator with EQ.
    #    Order matters — the literal ``{"_num": None}`` arms catch zeros before the
    #    generic ``{"_num": {var}}`` capture binds a positive.
    projs.append({"pattern": {"_cmp": {"a": {"_num": None}, "b": {"_num": None}}},
                  "body": {"_ord": _EQ}})                                   # 0 vs 0 = EQ
    projs.append({"pattern": {"_cmp": {"a": {"_num": None}, "b": {"_num": _v("pb")}}},
                  "body": {"_ord": _LT}})                                   # 0 vs +b = LT
    projs.append({"pattern": {"_cmp": {"a": {"_num": _v("pa")}, "b": {"_num": None}}},
                  "body": {"_ord": _GT}})                                   # +a vs 0 = GT
    projs.append({"pattern": {"_cmp": {"a": {"_num": _v("pa")},
                                       "b": {"_num": _v("pb")}}},
                  "body": {"_cc": {"a": _v("pa"), "b": _v("pb"), "r": _EQ}}})  # both positive

    # -- bit loop (compare_cont): peel the LSB of a and b. Coq Pos.compare_cont,
    #    expressed structurally. ``r`` is the ordering decided by the bits seen so
    #    far (lower bits); a higher differing bit OVERWRITES it, so the
    #    most-significant difference wins. A length mismatch (one side at ``xH``
    #    while the other still has bits) is itself the most-significant difference
    #    and terminates immediately. The 9 (a-form × b-form) combinations are all
    #    enumerated so no reachable state stalls early.
    #
    #    (xI, xI): low bits equal (1==1) -> keep r, recurse to higher bits.
    projs.append({"pattern": {"_cc": {"a": {"xI": _v("pa")}, "b": {"xI": _v("pb")},
                                      "r": _v("r")}},
                  "body": {"_cc": {"a": _v("pa"), "b": _v("pb"), "r": _v("r")}}})
    #    (xI, xO): a's low bit 1 > b's low bit 0 -> set GT, recurse (higher bits override).
    projs.append({"pattern": {"_cc": {"a": {"xI": _v("pa")}, "b": {"xO": _v("pb")},
                                      "r": _v("r")}},
                  "body": {"_cc": {"a": _v("pa"), "b": _v("pb"), "r": _GT}}})
    #    (xI, xH): a has more bits than b -> a is longer -> GT (length is decisive).
    projs.append({"pattern": {"_cc": {"a": {"xI": _v("pa")}, "b": {"xH": None},
                                      "r": _v("r")}},
                  "body": {"_ord": _GT}})
    #    (xO, xI): a's low bit 0 < b's low bit 1 -> set LT, recurse.
    projs.append({"pattern": {"_cc": {"a": {"xO": _v("pa")}, "b": {"xI": _v("pb")},
                                      "r": _v("r")}},
                  "body": {"_cc": {"a": _v("pa"), "b": _v("pb"), "r": _LT}}})
    #    (xO, xO): low bits equal (0==0) -> keep r, recurse.
    projs.append({"pattern": {"_cc": {"a": {"xO": _v("pa")}, "b": {"xO": _v("pb")},
                                      "r": _v("r")}},
                  "body": {"_cc": {"a": _v("pa"), "b": _v("pb"), "r": _v("r")}}})
    #    (xO, xH): a longer than b -> GT.
    projs.append({"pattern": {"_cc": {"a": {"xO": _v("pa")}, "b": {"xH": None},
                                      "r": _v("r")}},
                  "body": {"_ord": _GT}})
    #    (xH, xI): b longer than a -> LT.
    projs.append({"pattern": {"_cc": {"a": {"xH": None}, "b": {"xI": _v("pb")},
                                      "r": _v("r")}},
                  "body": {"_ord": _LT}})
    #    (xH, xO): b longer than a -> LT.
    projs.append({"pattern": {"_cc": {"a": {"xH": None}, "b": {"xO": _v("pb")},
                                      "r": _v("r")}},
                  "body": {"_ord": _LT}})
    #    (xH, xH): both terminate together (equal length) -> emit accumulated r.
    projs.append({"pattern": {"_cc": {"a": {"xH": None}, "b": {"xH": None},
                                      "r": _v("r")}},
                  "body": {"_ord": _v("r")}})
    return projs


COMPARE_PROJECTIONS = build_compare_projections()


# =============================================================================
# Corpus — lean (engine cost ~0.6s/step), non-negative, covering the mandatory
# minimum matrix: equality (incl. 0==0), LT/GT symmetry (every unequal pair and
# its swap), prefix/length differences (incl. length as the most-significant
# difference), and the first differing bit at multiple depths (LSB, interior, MSB)
# on equal-length operands.
# =============================================================================

# Equal pairs decide EQ — must include the mandatory ``0 == 0``.
EQ_PAIRS: list[tuple[int, int]] = [
    (0, 0),       # zero vs zero
    (5, 5),       # equal positives (3-bit; exercises the cc loop returning EQ)
]

# Ordered pairs with a > b (each decides GT); the swap (b, a) must decide LT.
# Annotated by the mandatory-matrix row each covers.
GT_PAIRS: list[tuple[int, int]] = [
    (2, 1),       # length: longer operand (10b) is greater than (1b)
    (4, 3),       # length: 3-bit (100b) greater than 2-bit (11b)
    (8, 7),       # length is the MOST-significant difference: lower bits 000 vs 111 favour 7, 8 still wins
    (9, 8),       # equal length(4): first differing bit at the LSB (bit 0): 1001 vs 1000
    (10, 8),      # equal length(4): first differing bit at an interior bit (bit 1): 1010 vs 1000
    (12, 8),      # equal length(4): first differing bit at the MSB-below-leading (bit 2): 1100 vs 1000
    (12, 11),     # equal length(4): MS differing bit (bit 2) decides despite lower bits favouring 11
    (6, 5),       # equal length(3): MS differing bit (bit 1) decides despite bit 0 favouring 5
]

# Full evaluation set: equal pairs + GT pairs + their LT swaps (deduped, ordered).
CORPUS: list[tuple[int, int]] = sorted(
    set(EQ_PAIRS) | set(GT_PAIRS) | {(b, a) for (a, b) in GT_PAIRS}
)

# Required matrix rows must actually be present (guards against silent corpus drift).
assert (0, 0) in EQ_PAIRS, "corpus must include 0 == 0 (zero equality)"
assert any(a == b and a != 0 for a, b in EQ_PAIRS), "corpus must include a nonzero equality"
assert (2, 1) in GT_PAIRS, "corpus must include a length difference where the longer operand is greater"
assert (8, 7) in GT_PAIRS, "corpus must prove length is the most-significant difference (8 > 7)"
assert {(9, 8), (10, 8), (12, 8)} <= set(GT_PAIRS), (
    "corpus must cover the first differing bit at LSB, interior, and MSB depths"
)


def _ms_differing_bit(a: int, b: int) -> int:
    """Position of the most-significant differing bit between a and b (a != b)."""
    assert a != b
    return (a ^ b).bit_length() - 1


def _is_canonical_ord_tag(value) -> bool:
    """A canonical ordering result: ``{"_ord": {eq|lt|gt: null}}`` — single-key at
    both levels, no residual operands (no ``a``/``b``/``_cmp``/``_cc`` anywhere)."""
    if not isinstance(value, dict) or len(value) != 1 or "_ord" not in value:
        return False
    inner = value["_ord"]
    if not isinstance(inner, dict) or len(inner) != 1:
        return False
    key = next(iter(inner))
    return key in {"lt", "eq", "gt"} and inner[key] is None


def run_compare(a: int, b: int) -> tuple[dict, int, bool]:
    """Compare ``a`` and ``b`` via the test-local COMPARE projection driven by ``run_mu``.

    The ENGINE performs the comparison: the only inputs are the encoded numerals
    ``encode(a)`` / ``encode(b)``; ``run_mu`` peels them structurally and decides the
    ordering. Returns ``(result_tag, step_count, stalled)``.
    """
    state = {"_cmp": {"a": encode(a), "b": encode(b)}}
    result, trace, stalled = run_mu(COMPARE_PROJECTIONS, state, max_steps=2000)
    return result, len(trace), stalled


# Computed once per process (each run_mu compare is meta-circular and costly).
_CMP_CACHE: dict[tuple[int, int], tuple[dict, int, bool]] | None = None


def _cmp_results() -> dict[tuple[int, int], tuple[dict, int, bool]]:
    global _CMP_CACHE
    if _CMP_CACHE is None:
        _CMP_CACHE = {(a, b): run_compare(a, b) for (a, b) in CORPUS}
    return _CMP_CACHE


# =============================================================================
# Fast scaffolding sanity (no run_mu) — codecs match the spec and the projection
# table is well-formed and linear. These run in every tier (not slow).
# =============================================================================

class TestProjectionScaffolding:
    """The local codecs match the spec and the COMPARE projection table is linear."""

    def test_numeral_codec_matches_spec(self):
        assert encode(0) == {"_num": None}
        assert encode(1) == {"_num": {"xH": None}}
        assert encode(2) == {"_num": {"xO": {"xH": None}}}
        assert encode(6) == {"_num": {"xO": {"xI": {"xH": None}}}}  # 6 = 110b LSB-first

    def test_numeral_codec_round_trips_corpus(self):
        for n in {x for pair in CORPUS for x in pair}:
            assert decode(encode(n)) == n, f"numeral codec round-trip failed for {n}"

    def test_ord_codec_matches_spec_and_round_trips(self):
        assert encode_ord(-1) == {"_ord": {"lt": None}}
        assert encode_ord(0) == {"_ord": {"eq": None}}
        assert encode_ord(1) == {"_ord": {"gt": None}}
        for sign in (-1, 0, 1):
            assert decode_ord(encode_ord(sign)) == sign
            assert _is_canonical_ord_tag(encode_ord(sign))

    def test_projection_count(self):
        # 4 dispatch + 9 compare_cont (3×3 LSB-form table) = 13.
        assert len(COMPARE_PROJECTIONS) == 13

    def test_every_projection_has_pattern_and_body(self):
        for proj in COMPARE_PROJECTIONS:
            assert set(proj) == {"pattern", "body"}

    def test_all_projections_are_linear(self):
        """``run_mu`` rejects non-linear patterns; assert it up front (fast lane)."""
        def collect_vars(node, out):
            if isinstance(node, dict):
                if set(node) == {"var"} and isinstance(node["var"], str):
                    out.append(node["var"])
                    return
                for child in node.values():
                    collect_vars(child, out)
        for proj in COMPARE_PROJECTIONS:
            names: list[str] = []
            collect_vars(proj["pattern"], names)
            assert len(names) == len(set(names)), (
                f"non-linear pattern (variable repeated): {proj['pattern']}"
            )

    def test_no_host_comparison_inside_projections(self):
        """The ordering is decided structurally: projection bodies emit only literal
        ``_cc`` recursion or ``_ord`` tags — never a host-comparison sentinel. Every
        emitted ordering marker is one of the three canonical structural tags."""
        allowed_markers = ({"lt": None}, {"eq": None}, {"gt": None})
        for proj in COMPARE_PROJECTIONS:
            body = proj["body"]
            assert set(body) <= {"_cc", "_ord"}, f"unexpected body shape: {body}"
            if "_ord" in body:
                inner = body["_ord"]
                # Either a literal tag or the variable carrying the accumulated tag.
                assert inner in allowed_markers or inner == {"var": "r"}, (
                    f"_ord body must emit a canonical tag or the carried r: {inner}"
                )

    def test_corpus_is_non_negative_and_covers_matrix(self):
        for a, b in CORPUS:
            assert a >= 0 and b >= 0
        # LT/GT symmetry coverage: every GT pair's swap is present in the corpus.
        for a, b in GT_PAIRS:
            assert (b, a) in CORPUS, f"swap of GT pair ({a},{b}) missing from corpus"
        # The first-differing-bit spotlights sit at distinct depths on equal-length operands.
        assert _ms_differing_bit(9, 8) == 0     # LSB
        assert _ms_differing_bit(10, 8) == 1    # interior
        assert _ms_differing_bit(12, 8) == 2    # MSB-below-leading
        # ...and all below the shared leading bit (bit 3 for the length-4 operands).
        for a, b in ((9, 8), (10, 8), (12, 8)):
            assert a.bit_length() == b.bit_length() == 4
            assert _ms_differing_bit(a, b) < 3


# =============================================================================
# Governing assertion (StructuralNumbers.v0.md §3.3): the run_mu COMPARE result is
# a canonical ordering tag, structurally / hash-equal to encode_ord(host sign).
# =============================================================================

@pytest.mark.l4_expensive
@pytest.mark.slow
class TestStructuralCompareEquivalence:
    """structural_compare(a,b) ≡ host_to_ord((a>b)-(a<b)) over the corpus."""

    def test_canonical_structural_equality(self):
        """GOVERNING: run_mu(compare) result is structurally identical to encode_ord(sign)."""
        results = _cmp_results()
        for a, b in CORPUS:
            result, _, _ = results[(a, b)]
            expected = encode_ord(host_sign(a, b))
            assert result == expected, (
                f"structural COMPARE diverged for ({a}, {b}): got {result}, expected {expected}"
            )

    def test_content_hash_equality(self):
        """The result is content-addressed equal to encode_ord(sign) (free equality)."""
        results = _cmp_results()
        for a, b in CORPUS:
            result, _, _ = results[(a, b)]
            expected = encode_ord(host_sign(a, b))
            assert mu_hash(result) == mu_hash(expected), (
                f"content-hash divergence for COMPARE({a}, {b})"
            )

    def test_result_is_canonical_ord_tag(self):
        """Result is well-formed Mu and exactly one canonical EQ/LT/GT tag.

        Canonicality is asserted oracle-independently: a canonical tag is a single-key
        ``_ord`` wrapper over a single-key {eq|lt|gt: null} (no residual operands), and
        a fixed point of ``encode_ord ∘ decode_ord`` (no non-canonical tag survives).
        """
        results = _cmp_results()
        for a, b in CORPUS:
            result, _, _ = results[(a, b)]
            assert is_mu(result), f"result for COMPARE({a}, {b}) is not valid Mu: {result}"
            assert _is_canonical_ord_tag(result), (
                f"result for COMPARE({a}, {b}) is not a canonical ordering tag: {result}"
            )
            assert result == encode_ord(decode_ord(result)), (
                f"result for COMPARE({a}, {b}) is non-canonical: {result}"
            )

    def test_engine_reaches_stall_fixpoint(self):
        """run_mu converged to the {"_ord": ...} fixpoint (not max_steps), and the
        compare marker is fully reduced out — proving the engine actually decided it."""
        results = _cmp_results()
        for a, b in CORPUS:
            result, steps, stalled = results[(a, b)]
            assert stalled is True, f"run_mu did not stall for COMPARE({a}, {b}) (steps={steps})"
            assert "_cmp" not in result, (
                f"result for COMPARE({a}, {b}) still carries the unprocessed compare marker"
            )
            assert "_cc" not in result, (
                f"result for COMPARE({a}, {b}) still carries an in-flight bit-loop marker"
            )
            assert result != {"_cmp": {"a": encode(a), "b": encode(b)}}, (
                f"result for COMPARE({a}, {b}) is the unprocessed input state"
            )

    def test_decode_to_host_supporting(self):
        """SUPPORTING ONLY (not sufficient): the result decodes to the host three-way sign."""
        results = _cmp_results()
        for a, b in CORPUS:
            result, _, _ = results[(a, b)]
            assert decode_ord(result) == host_sign(a, b), (
                f"decode_ord(run_mu compare) = {decode_ord(result)} != "
                f"sign({a}, {b}) = {host_sign(a, b)}"
            )


# =============================================================================
# Mandatory ordering matrix — explicit spotlight on each required row (same cached
# runs): equality, LT/GT symmetry, prefix/length differences, and the first
# differing bit at multiple depths (the COMPARE analog of the ADD carry spotlights).
# =============================================================================

@pytest.mark.l4_expensive
@pytest.mark.slow
class TestOrderingMatrix:
    """COMPARE decides EQ/LT/GT correctly across every mandatory matrix row."""

    def test_equality_including_zero(self):
        results = _cmp_results()
        for a, b in EQ_PAIRS:
            result, _, _ = results[(a, b)]
            assert result == encode_ord(0), f"COMPARE({a}, {b}) must be EQ, got {result}"

    def test_lt_gt_symmetry_and_never_eq(self):
        """For each unequal pair, the swap yields the opposite tag — and never EQ."""
        results = _cmp_results()
        for a, b in GT_PAIRS:
            forward, _, _ = results[(a, b)]
            backward, _, _ = results[(b, a)]
            assert forward == encode_ord(1), f"COMPARE({a}, {b}) must be GT, got {forward}"
            assert backward == encode_ord(-1), f"COMPARE({b}, {a}) must be LT, got {backward}"
            assert forward != encode_ord(0) and backward != encode_ord(0), (
                f"unequal operands ({a}, {b}) must never decide EQ"
            )

    def test_prefix_length_difference(self):
        """A longer operand is greater; length is the most-significant difference."""
        results = _cmp_results()
        # Longer operand greater (2 = 10b vs 1 = 1b).
        assert results[(2, 1)][0] == encode_ord(1)
        # Length dominates even when the shorter operand's lower bits would "win":
        # 8 = 1000b vs 7 = 0111b — the low 3 bits favour 7, but 8 is longer, so 8 > 7.
        assert results[(8, 7)][0] == encode_ord(1)
        assert results[(7, 8)][0] == encode_ord(-1)

    def test_first_differing_bit_at_lsb(self):
        """Equal-length operands differing only at the LSB (bit 0): 9 = 1001b > 8 = 1000b."""
        assert _ms_differing_bit(9, 8) == 0
        assert _cmp_results()[(9, 8)][0] == encode_ord(1)
        assert _cmp_results()[(8, 9)][0] == encode_ord(-1)

    def test_first_differing_bit_at_interior(self):
        """Equal-length operands differing at an interior bit (bit 1): 10 = 1010b > 8 = 1000b."""
        assert _ms_differing_bit(10, 8) == 1
        assert _cmp_results()[(10, 8)][0] == encode_ord(1)
        assert _cmp_results()[(8, 10)][0] == encode_ord(-1)

    def test_first_differing_bit_at_msb(self):
        """Equal-length operands whose most-significant differing bit decides, despite
        lower bits favouring the other: 12 = 1100b > 11 = 1011b (bit 2 decides; bits 0,1
        favour 11), and the isolated MSB case 12 = 1100b > 8 = 1000b (bit 2)."""
        assert _ms_differing_bit(12, 8) == 2
        assert _cmp_results()[(12, 8)][0] == encode_ord(1)
        assert _cmp_results()[(12, 11)][0] == encode_ord(1)   # bit 2 overrides bits 0,1
        assert _cmp_results()[(11, 12)][0] == encode_ord(-1)
        assert _cmp_results()[(6, 5)][0] == encode_ord(1)     # 3-bit: bit 1 overrides bit 0
