"""L4 gate: StructuralNumbers binary ADD — arithmetic as RCX projections.

Stage 2a-i gate for ``mu/docs/core/StructuralNumbers.v0.md`` (Python-only slice).
Proves, without any runtime/substrate/seed change, that binary ADD (with carry)
on the binary-positional structural numeral is **expressible as RCX projections**:
the ADD machine is defined here as **test-local Mu projection scaffolding** and
executed via the real kernel driver ``run_mu`` on the Python substrate. The
governing obligation is the cross-form equivalence of ``StructuralNumbers.v0.md``
§7.3::

    structural_add(a, b)  ≡  host_to_structural( to_host(a) + to_host(b) )

i.e. the ``run_mu`` result must be a **valid canonical** StructuralNumbers numeral
that is **structurally / content-hash equal** to ``encode(a + b)``. A decode-to-host
check (``decode(result) == a + b``) is retained as a *supporting* assertion only —
a result that decodes correctly yet is non-canonical or not hash-equal to
``encode(a + b)`` is a gate **failure**.

Scope: GATE-ONLY (mirrors the foundation gate). The encode/decode codec AND the
binary ADD projection are defined locally in this test — they are test scaffolding,
not runtime code. This wave introduces **no** ``mu/seeds/numerals.v1.json`` (the
runtime arithmetic-projection seed of ``StructuralNumbers.v0.md`` §3.3 / §8 Stage 2);
it proves ADD is *expressible* as a projection on a minimal Python-only slice first.
No ``_stage0_match`` cutover, no host-authority delta.

The ADD machine is a pure structural state machine over single-key Mu (every
intermediate state is valid ``is_mu``; the only host ``+`` in this file is the test
*oracle* ``encode(a + b)`` and codec construction — the engine does the actual add):

  * dispatch ``{"_add": {a, b}}``     — handle zero / additive identity, else enter
  * bit machine ``{"_bits": {a,b,c,acc}}`` — peel LSB of a,b, full-adder truth table,
    emit result bits onto a single-key bit-stack (``{"o"|"i": rest}``)
  * fold ``{"_fold": {acc, num}}``    — rebuild the canonical numeral, MSB → ``xH``
  * fixpoint ``{"_num": ...}``        — natural stall (the §7.3 result)

Two REAL kernel constraints bound the corpus (documented, not worked around):
``run_mu`` → ``step_kernel_mu`` runs ``normalize_for_match`` which inflates every
dict level ~3× (depth), and each meta-circular VM micro-step re-validates the whole
state (~0.6s / domain-step). So the corpus is deliberately lean (≤ 8-bit operands,
~10 cases) and the engine-driving tests are ``@pytest.mark.slow`` +
``@pytest.mark.l4_expensive`` (the run_mu meta-circular cost exceeds the
green-gate slow-lane 300s timeout, so they run in the slow_tests/nightly lane
at 900s) per ``.claude/rules/test-classification.md``. JS cross-substrate parity and
compare/multiply/codec are deferred to follow-up waves.

Wave: structural-numbers-arith-add-2026-06-17c (L4_ENABLER, target gate G8).
Encoding authority: ``mu/docs/core/StructuralNumbers.v0.md`` §3.1, §3.3, §7.3.
Foundation gate (numeral + codec precedent): ``test_structural_numbers_foundation.py``.
"""
from __future__ import annotations

import pytest

from rcx_pi.selfhost.step_mu import run_mu
from rcx_pi.selfhost.mu_type import is_mu, mu_hash


# =============================================================================
# Numeral codec — test-local, mirrors StructuralNumbers.v0.md §3.1 and the
# foundation gate's codec (binary, least-significant-bit outermost):
#   {"xH": null} = 1 ,  {"xO": r} = 2·r ,  {"xI": r} = 2·r+1
#   0 -> {"_num": null} ,  +p -> {"_num": p}
# ADD is over non-negative integers only (subtraction/negatives are out of scope
# for this wave per StructuralNumbers Stage 2a-i), so the ``neg`` arm is unused.
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
    assert n >= 0, "ADD gate corpus is non-negative (no subtraction this wave)"
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
# Binary ADD projection — test-local Mu projection scaffolding (the wave's
# structural artifact). Built mechanically from the full-adder truth table so the
# transition relation is provably TOTAL over every reachable state. Every pattern
# is linear (each variable appears once) — required by ``run_mu``.
# =============================================================================


def _v(name: str) -> dict:
    """A pattern/​body variable site ``{"var": name}``."""
    return {"var": name}


_C0 = {"carry0": None}          # carry-in / carry-out markers (structural, not host int)
_C1 = {"carry1": None}
_END = {"end": None}            # bit-stack base
_SEED = {"seed": None}          # fold: "empty numeral, awaiting the MSB"


def _operand_forms(rest_var: str) -> dict:
    """The four LSB forms of an operand: (match-pattern, body-rest, low-bit)."""
    return {
        "O": ({"xO": _v(rest_var)}, _v(rest_var), 0),  # low bit 0, rest = inner positive
        "I": ({"xI": _v(rest_var)}, _v(rest_var), 1),  # low bit 1, rest = inner positive
        "H": ({"xH": None}, None, 1),                  # top bit (=1); exhausted after
        "Z": (None, None, 0),                          # exhausted; contributes 0 forever
    }


def build_add_projections() -> list[dict]:
    """Construct the binary-ADD projection table (39 linear projections)."""
    projs: list[dict] = []

    # -- dispatch: zero / additive identity first, then the both-positive entry.
    #    Order matters — a==0 and b==0 must be caught before the generic capture.
    projs.append({"pattern": {"_add": {"a": {"_num": None}, "b": _v("b")}},
                  "body": _v("b")})                                  # 0 + b = b
    projs.append({"pattern": {"_add": {"a": _v("a"), "b": {"_num": None}}},
                  "body": _v("a")})                                  # a + 0 = a
    projs.append({"pattern": {"_add": {"a": {"_num": _v("pa")},
                                       "b": {"_num": _v("pb")}}},
                  "body": {"_bits": {"a": _v("pa"), "b": _v("pb"),
                                     "c": _C0, "acc": _END}}})        # both positive

    # -- bit machine: full-adder over (a-form × b-form × carry).  All 4×4×2 = 32
    #    combinations are enumerated so no reachable state stalls early. The single
    #    (exhausted, exhausted, carry0) combination is the terminate → fold step.
    forms_a = _operand_forms("ra")
    forms_b = _operand_forms("rb")
    carries = {"0": (_C0, 0), "1": (_C1, 1)}
    for af, (a_pat, a_rest, a_bit) in forms_a.items():
        for bf, (b_pat, b_rest, b_bit) in forms_b.items():
            for _cf, (c_pat, c_in) in carries.items():
                if af == "Z" and bf == "Z" and c_in == 0:
                    # nothing left to add and no carry -> fold the bit-stack
                    projs.append({
                        "pattern": {"_bits": {"a": None, "b": None,
                                              "c": _C0, "acc": _v("acc")}},
                        "body": {"_fold": {"acc": _v("acc"), "num": _SEED}}})
                    continue
                total = a_bit + b_bit + c_in
                out_bit, carry_out = total & 1, total >> 1
                emit = "i" if out_bit else "o"
                projs.append({
                    "pattern": {"_bits": {"a": a_pat, "b": b_pat,
                                          "c": c_pat, "acc": _v("acc")}},
                    "body": {"_bits": {"a": a_rest, "b": b_rest,
                                       "c": (_C1 if carry_out else _C0),
                                       "acc": {emit: _v("acc")}}}})

    # -- fold: pop the bit-stack (MSB first) into a canonical numeral. The first
    #    bit popped is the MSB (always 1) and seeds the ``xH`` terminal; rule A must
    #    precede rule C since both match an ``i`` bit.
    projs.append({"pattern": {"_fold": {"acc": {"i": _v("rest")}, "num": _SEED}},
                  "body": {"_fold": {"acc": _v("rest"), "num": {"xH": None}}}})  # A
    projs.append({"pattern": {"_fold": {"acc": {"i": _v("rest")}, "num": _v("n")}},
                  "body": {"_fold": {"acc": _v("rest"), "num": {"xI": _v("n")}}}})  # C
    projs.append({"pattern": {"_fold": {"acc": {"o": _v("rest")}, "num": _v("n")}},
                  "body": {"_fold": {"acc": _v("rest"), "num": {"xO": _v("n")}}}})  # B
    projs.append({"pattern": {"_fold": {"acc": {"end": None}, "num": _v("n")}},
                  "body": {"_num": _v("n")}})                          # T -> fixpoint
    return projs


ADD_PROJECTIONS = build_add_projections()


# =============================================================================
# Corpus — lean (engine cost ~0.6s/step), non-negative, covers every required
# carry class: zero, additive identity (both directions), single-bit, multi-bit
# non-carry, and full-carry cascades (all-ones + 1, large all-ones + all-ones).
# =============================================================================

CORPUS: list[tuple[int, int]] = [
    (0, 0),       # zero + zero
    (7, 0),       # additive identity (b = 0)
    (0, 7),       # additive identity (a = 0)
    (1, 1),       # single-bit, produces a carry -> 2
    (4, 2),       # multi-bit, NO carry propagation (100 + 010 = 110)
    (3, 5),       # unequal bit-length operands, with carry (011 + 101 = 1000)
    (7, 1),       # full-carry cascade: all-ones(3) + 1 = 1000 (8)
    (170, 85),    # alternating bits -> all-ones, no carry (10101010 + 01010101 = 255)
    (255, 1),     # full 8-bit carry cascade: all-ones(8) + 1 = 256
    (255, 255),   # large all-ones + all-ones = 510
]

# Required carry classes must actually be present (guards against silent corpus drift).
assert (0, 0) in CORPUS, "corpus must include zero + zero"
assert (7, 0) in CORPUS and (0, 7) in CORPUS, "corpus must include identity both ways"
assert (255, 1) in CORPUS, "corpus must include all-ones + 1 (full carry cascade)"
assert (255, 255) in CORPUS, "corpus must include large all-ones + all-ones"


def run_add(a: int, b: int) -> tuple[dict, int, bool]:
    """Add ``a`` and ``b`` via the test-local ADD projection driven by ``run_mu``.

    The ENGINE performs the addition: the only inputs are the encoded numerals
    ``encode(a)`` / ``encode(b)``; ``run_mu`` peels and folds them structurally.
    Returns ``(result_numeral, step_count, stalled)``.
    """
    state = {"_add": {"a": encode(a), "b": encode(b)}}
    result, trace, stalled = run_mu(ADD_PROJECTIONS, state, max_steps=2000)
    return result, len(trace), stalled


# Computed once per process (each run_mu add is meta-circular and costly).
_ADD_CACHE: dict[tuple[int, int], tuple[dict, int, bool]] | None = None


def _add_results() -> dict[tuple[int, int], tuple[dict, int, bool]]:
    global _ADD_CACHE
    if _ADD_CACHE is None:
        _ADD_CACHE = {(a, b): run_add(a, b) for (a, b) in CORPUS}
    return _ADD_CACHE


def _numeral_nodes_all_single_key(value) -> bool:
    """Every node of a StructuralNumbers numeral is a single-key dict (or null)."""
    if value is None:
        return True
    if not isinstance(value, dict) or len(value) != 1:
        return False
    return _numeral_nodes_all_single_key(next(iter(value.values())))


# =============================================================================
# Fast scaffolding sanity (no run_mu) — codec matches the spec and the projection
# table is well-formed and linear. These run in every tier (not slow).
# =============================================================================

class TestProjectionScaffolding:
    """The local codec matches the spec and the ADD projection table is linear."""

    def test_codec_matches_spec(self):
        assert encode(0) == {"_num": None}
        assert encode(1) == {"_num": {"xH": None}}
        assert encode(2) == {"_num": {"xO": {"xH": None}}}
        assert encode(6) == {"_num": {"xO": {"xI": {"xH": None}}}}  # 6 = 110b LSB-first

    def test_codec_round_trips_corpus(self):
        for n in {x for pair in CORPUS for x in pair} | {sum(p) for p in CORPUS}:
            assert decode(encode(n)) == n, f"codec round-trip failed for {n}"

    def test_projection_count(self):
        # 3 dispatch + 32 full-adder (incl. terminate) + 4 fold.
        assert len(ADD_PROJECTIONS) == 39

    def test_every_projection_has_pattern_and_body(self):
        for proj in ADD_PROJECTIONS:
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
        for proj in ADD_PROJECTIONS:
            names: list[str] = []
            collect_vars(proj["pattern"], names)
            assert len(names) == len(set(names)), (
                f"non-linear pattern (variable repeated): {proj['pattern']}"
            )

    def test_corpus_is_non_negative(self):
        for a, b in CORPUS:
            assert a >= 0 and b >= 0


# =============================================================================
# Governing assertion (StructuralNumbers.v0.md §7.3): the run_mu ADD result is a
# valid canonical numeral, structurally/​hash-equal to encode(a + b).
# =============================================================================

@pytest.mark.l4_expensive
@pytest.mark.slow
class TestStructuralAddEquivalence:
    """structural_add(a,b) ≡ host_to_structural(to_host(a) + to_host(b))."""

    def test_canonical_structural_equality(self):
        """GOVERNING: run_mu(add) result is structurally identical to encode(a+b)."""
        results = _add_results()
        for a, b in CORPUS:
            result, _, _ = results[(a, b)]
            assert result == encode(a + b), (
                f"structural ADD diverged from encode({a}+{b}={a + b}): got {result}"
            )

    def test_content_hash_equality(self):
        """The result is content-addressed equal to encode(a+b) (free equality)."""
        results = _add_results()
        for a, b in CORPUS:
            result, _, _ = results[(a, b)]
            assert mu_hash(result) == mu_hash(encode(a + b)), (
                f"content-hash divergence for {a}+{b}"
            )

    def test_result_is_valid_canonical_numeral(self):
        """Result is well-formed Mu, single-key numeral nodes, in canonical form.

        Canonicality is asserted oracle-independently: a canonical numeral is a
        fixed point of decode∘encode (no spurious leading-zero bits could survive).
        """
        results = _add_results()
        for a, b in CORPUS:
            result, _, _ = results[(a, b)]
            assert is_mu(result), f"result for {a}+{b} is not valid Mu: {result}"
            assert "_num" in result and len(result) == 1, (
                f"result for {a}+{b} is not an N numeral wrapper: {result}"
            )
            assert _numeral_nodes_all_single_key(result["_num"]), (
                f"result for {a}+{b} has a non-single-key numeral node"
            )
            assert result == encode(decode(result)), (
                f"result for {a}+{b} is non-canonical: {result}"
            )

    def test_engine_reaches_stall_fixpoint(self):
        """run_mu converged to the {"_num": ...} fixpoint (not max_steps), and the
        result is NOT the input state — proving the engine actually transformed it."""
        results = _add_results()
        for a, b in CORPUS:
            result, steps, stalled = results[(a, b)]
            assert stalled is True, f"run_mu did not stall for {a}+{b} (steps={steps})"
            assert "_add" not in result, (
                f"result for {a}+{b} is still the unprocessed input state"
            )

    def test_decode_to_host_supporting(self):
        """SUPPORTING ONLY (not sufficient): the result decodes to host a + b."""
        results = _add_results()
        for a, b in CORPUS:
            result, _, _ = results[(a, b)]
            assert decode(result) == a + b, (
                f"decode(run_mu add) = {decode(result)} != {a}+{b} = {a + b}"
            )


# =============================================================================
# Carry propagation — explicit spotlight on the cascade cases (same cached runs).
# =============================================================================

@pytest.mark.l4_expensive
@pytest.mark.slow
class TestCarryPropagation:
    """ADD exercises carry end-to-end, including full multi-bit cascades."""

    def test_single_bit_carry(self):
        result, _, _ = _add_results()[(1, 1)]
        assert result == encode(2)                  # 1 + 1 = 10b

    def test_multi_bit_without_carry(self):
        result, _, _ = _add_results()[(4, 2)]
        assert result == encode(6)                  # 100 + 010 = 110, no carry

    def test_three_bit_full_carry_cascade(self):
        result, _, _ = _add_results()[(7, 1)]
        assert result == encode(8)                  # 111 + 1 = 1000

    def test_eight_bit_all_ones_plus_one(self):
        result, _, _ = _add_results()[(255, 1)]
        assert result == encode(256)                # 11111111 + 1 = 100000000

    def test_large_all_ones_plus_all_ones(self):
        result, _, _ = _add_results()[(255, 255)]
        assert result == encode(510)                # 11111111 + 11111111 = 111111110
