"""L4 gate: StructuralNumbers integer SUBTRACT — signed-result subtract-with-borrow
over non-negative operands, as RCX projections.

Stage 3 prerequisite gate for ``mu/docs/core/StructuralNumbers.v0.md`` (Python-only
slice). Proves, without any runtime/substrate/seed change, that integer SUBTRACT on
the binary-positional structural numeral is **expressible as RCX projections** — as a
**structural-compare sign decision composing the already-landed binary COMPARE**, plus
**binary subtract-with-borrow** on the operand magnitudes — driven by the real kernel
driver ``run_mu`` on the Python substrate.

Operand / result domain (the precise claim, matching the composed COMPARE): the
**operands are non-negative** integers ``a, b >= 0`` — the engine composes the
**N-only** COMPARE, exactly as the COMPARE gate scopes itself ("subtraction/negatives
are out of scope for this wave") — while the **result is signed**, ranging over the
``Z`` codec and **negative when ``a < b``**. Fully-signed *operands* (negative inputs)
are a deliberate **bounded non-closure** deferred to a follow-up wave: they would
additionally require composing the landed binary ADD for the sign-mixed cases
(``a - (-b) = a + b``, etc.), out of scope here just as JS cross-substrate parity is
deferred. ``run_subtract`` enforces this domain, so a negative operand is rejected
explicitly rather than silently stalling in the N-only compare or wrapping an
already-``neg`` operand into a non-canonical double-``neg`` numeral.

The governing obligation is the cross-form equivalence of ``StructuralNumbers.v0.md``
§3.3 (the SUBTRACT analog of the landed ADD gate's §7.3), for non-negative operands::

    structural_sub(a, b)  ≡  host_to_structural( to_host(a) - to_host(b) )   # a, b >= 0

i.e. the ``run_mu`` result must be a **valid canonical** ``Z`` numeral that is
**structurally / content-hash equal** to ``encode(a - b)``: the **negative (neg) form**
``{"_num": {"neg": p}}`` when ``a < b``, the **canonical zero** ``{"_num": null}`` when
``a == b``, and the **positive form** ``{"_num": p}`` when ``a > b``. A decode-to-host
check (``decode(result) == a - b``) is retained as a *supporting* assertion only — a
result that decodes correctly yet is non-canonical or not hash-equal to
``encode(a - b)`` is a gate **failure**.

Composition (NOT reimplementation): the binary COMPARE is **not** rebuilt here. The
landed ``COMPARE_PROJECTIONS`` table and the var-site helper ``_v`` are **imported**
from ``test_structural_numbers_compare`` (single source of truth), and each COMPARE
projection is **lifted verbatim** into a ``_sub_cmp`` work-slot that carries copies of
the two operands through the comparison untouched (so the operands survive for the
subtraction). ``test_subtract_composes_landed_compare`` locks this mechanically: every
lifted work-slot **is** the corresponding landed COMPARE projection. The signed ``Z``
codec is imported from the foundation gate (the encoding authority). The engine performs
the subtraction; the only host arithmetic in this file is the test *oracle*
``encode(a - b)`` and the imported codec construction (the
``check_host_semantics_ratchet.py`` scan covers only ``rcx_pi/selfhost`` and
``mu/host/js`` — never ``mu/tests/`` — so this test-only oracle is not a host-authority
site, and **no host ``-`` is introduced into the bootstrap**).

The SUBTRACT machine is a pure structural state machine over single-key Mu (every
intermediate state is valid ``is_mu``; the sign is decided **structurally** by the
composed COMPARE, never by a host comparison):

  * dispatch ``{"_sub": {a, b}}``          — zero arms first (``0-0=0``, ``a-0=a``,
      ``0-b=-b`` via the neg wrapper), else seed the compare carrying both operands.
  * compare  ``{"_sub_cmp": {work, a, b}}``— run the lifted landed COMPARE on ``work``
      while the operands ride along; when ``work`` reduces to ``{"_ord": tag}`` dispatch
      on the tag: EQ → canonical zero; GT → borrow ``a-b`` (positive); LT → borrow
      ``b-a`` (negative, ``minus`` sign).
  * borrow   ``{"_borrow": {x, y, c, acc, sign}}`` — full-subtractor truth table,
      LSB→MSB, emitting difference bits onto a single-key bit-stack (``{"o"|"i": rest}``);
      ``x >= y`` is guaranteed (the larger magnitude is ``x``) so the final borrow is 0.
  * fold     ``{"_subfold": {acc, num, sign}}`` — pop the bit-stack MSB-first, **strip
      leading zeros** (unlike ADD, a difference may have high zero bits), build the
      canonical positive, then wrap by ``sign`` → ``{"_num": p}`` / ``{"_num": {"neg": p}}``.
  * fixpoint ``{"_num": ...}``             — natural stall (the §3.3 result).

Two REAL kernel constraints bound the corpus (documented, not worked around):
``run_mu`` → ``step_kernel_mu`` runs ``normalize_for_match`` (inflates dict depth ~3×)
and re-validates the whole state on each meta-circular VM micro-step. The SUBTRACT state
(the lifted COMPARE sub-machine carrying both operands, then the borrow loop) makes the
per-step cost grow with operand size (measured ~1–2s/domain-step). The corpus is
therefore deliberately lean (small operands, 8 cases, ~135s locally) — the engine-driving
tests are ``@pytest.mark.slow`` + ``@pytest.mark.l4_expensive`` (run in the nightly
l4_expensive lane at 900s, excluded from the fast green gate) per
``.claude/rules/test-classification.md``. This is the third wave of the Stage-3 tower; it
unblocks the structural gcd (Euclidean) and the rational tower. JS cross-substrate parity
is deferred to a follow-up wave (mirroring the landed add/compare/codec/multiply parity waves).

Wave: structural-numbers-arith-subtract-2026-06-18 (L4_ENABLER, target gate G8).
Encoding authority: ``mu/docs/core/StructuralNumbers.v0.md`` §3.1, §3.3.
Composed artifact: ``test_structural_numbers_compare.py`` (the landed COMPARE projections).
Signed codec authority: ``test_structural_numbers_foundation.py`` (the ``Z`` codec).
"""
from __future__ import annotations

import pytest

from rcx_pi.selfhost.step_mu import run_mu
from rcx_pi.selfhost.mu_type import is_mu, mu_hash

# Single source of truth: the SIGNED Z codec (handles the neg form) is imported from
# the foundation gate (the documented encoding authority), and the binary COMPARE that
# decides the sign is COMPOSED from the landed compare gate (table + var-site helper),
# never re-derived. This proves SUBTRACT reuses the SAME compare the COMPARE gate locks.
from tests.l4_gates.test_structural_numbers_foundation import decode, encode
from tests.l4_gates.test_structural_numbers_compare import COMPARE_PROJECTIONS, _v


# =============================================================================
# SUBTRACT projection — test-local Mu projection scaffolding (the wave's structural
# artifact). Structural-compare sign decision (composing the landed COMPARE) +
# binary subtract-with-borrow on the magnitudes + a leading-zero-stripping fold.
# Every pattern is linear (each variable appears once) — required by ``run_mu``.
# =============================================================================

_B0 = {"borrow0": None}          # borrow-in / borrow-out markers (structural, not host int)
_B1 = {"borrow1": None}
_END = {"end": None}             # bit-stack base
_SEED = {"seed": None}           # fold: "no significant bit yet" (leading-zero zone)
_PLUS = {"plus": None}           # sign carried through borrow/fold (distinct from the
_MINUS = {"minus": None}         #   codec's ``neg`` numeral wrapper — avoids overloading)

# Operand-copy carry vars for the lifted COMPARE: chosen NOT to collide with any
# variable used inside a COMPARE pattern (pa, pb, r).
_SA = "__sub_a"
_SB = "__sub_b"


def _operand_forms(rest_var: str) -> dict:
    """The four LSB forms of an operand: (match-pattern, body-rest, low-bit)."""
    return {
        "O": ({"xO": _v(rest_var)}, _v(rest_var), 0),  # low bit 0, rest = inner positive
        "I": ({"xI": _v(rest_var)}, _v(rest_var), 1),  # low bit 1, rest = inner positive
        "H": ({"xH": None}, None, 1),                  # top bit (=1); exhausted after
        "Z": (None, None, 0),                          # exhausted; contributes 0 forever
    }


def _lift_compare_into_sub(cmp_projs: list[dict]) -> list[dict]:
    """Lift each landed COMPARE projection into a ``_sub_cmp`` work-slot.

    The COMPARE pattern/body is placed verbatim in ``work``; copies of the two operands
    ``a`` / ``b`` ride through unchanged as carry variables so they survive the
    (operand-consuming) comparison and are available for the subtraction once the
    ordering is known. The COMPARE sub-machine therefore reduces ``work`` from
    ``{"_cmp": ...}`` to ``{"_ord": ...}`` exactly as it does standalone. Linearity is
    preserved (the carry vars are disjoint from every COMPARE pattern variable).
    """
    lifted: list[dict] = []
    for proj in cmp_projs:
        lifted.append({
            "pattern": {"_sub_cmp": {"work": proj["pattern"], "a": _v(_SA), "b": _v(_SB)}},
            "body": {"_sub_cmp": {"work": proj["body"], "a": _v(_SA), "b": _v(_SB)}},
        })
    return lifted


def build_subtract_projections() -> list[dict]:
    """Construct the signed-SUBTRACT projection table (57 linear projections).

    Layout: 4 dispatch + 3 sign-dispatch + 13 lifted COMPARE + 31 borrow + 6 fold.
    """
    projs: list[dict] = []

    # -- dispatch: zero arms first (order matters — the literal ``{"_num": None}`` arms
    #    must catch zeros before the generic ``{"_num": {var}}`` capture binds null).
    #    Operand domain is non-negative (``run_subtract`` enforces a, b >= 0), so the
    #    captured ``pa``/``pb`` are positive magnitudes — never a ``neg`` wrapper.
    projs.append({"pattern": {"_sub": {"a": {"_num": None}, "b": {"_num": None}}},
                  "body": {"_num": None}})                              # 0 - 0 = 0
    projs.append({"pattern": {"_sub": {"a": {"_num": None}, "b": {"_num": _v("pb")}}},
                  "body": {"_num": {"neg": _v("pb")}}})                 # 0 - b = -b (neg)
    projs.append({"pattern": {"_sub": {"a": {"_num": _v("pa")}, "b": {"_num": None}}},
                  "body": {"_num": _v("pa")}})                          # a - 0 = a
    projs.append({"pattern": {"_sub": {"a": {"_num": _v("pa")},
                                       "b": {"_num": _v("pb")}}},
                  "body": {"_sub_cmp": {"work": {"_cmp": {"a": {"_num": _v("pa")},
                                                          "b": {"_num": _v("pb")}}},
                                        "a": {"_num": _v("pa")},
                                        "b": {"_num": _v("pb")}}}})     # both positive -> compare

    # -- sign dispatch: the lifted COMPARE has reduced ``work`` to a canonical ordering
    #    tag. EQ -> canonical zero (operands discarded). GT (a > b) -> borrow a - b,
    #    positive. LT (a < b) -> borrow b - a, negative. The ``_ord`` shapes are disjoint
    #    from the in-flight ``_cmp``/``_cc`` work shapes, so these never race the lifted
    #    COMPARE rules. The larger magnitude is always ``x`` so the borrow never underflows.
    projs.append({"pattern": {"_sub_cmp": {"work": {"_ord": {"eq": None}},
                                           "a": _v(_SA), "b": _v(_SB)}},
                  "body": {"_num": None}})                              # a == b -> 0
    projs.append({"pattern": {"_sub_cmp": {"work": {"_ord": {"gt": None}},
                                           "a": {"_num": _v("pa")},
                                           "b": {"_num": _v("pb")}}},
                  "body": {"_borrow": {"x": _v("pa"), "y": _v("pb"),
                                       "c": _B0, "acc": _END, "sign": _PLUS}}})
    projs.append({"pattern": {"_sub_cmp": {"work": {"_ord": {"lt": None}},
                                           "a": {"_num": _v("pa")},
                                           "b": {"_num": _v("pb")}}},
                  "body": {"_borrow": {"x": _v("pb"), "y": _v("pa"),
                                       "c": _B0, "acc": _END, "sign": _MINUS}}})

    # -- lifted COMPARE sub-machine: composes the LANDED ordering decision (verbatim).
    projs.extend(_lift_compare_into_sub(COMPARE_PROJECTIONS))

    # -- borrow machine: full-subtractor over (x-form × y-form × borrow). All 4×4×2 = 32
    #    combinations are enumerated except the two (exhausted, exhausted) cases: the
    #    (Z, Z, borrow0) combination is the terminate -> fold step, and (Z, Z, borrow1)
    #    is an underflow that ``x >= y`` makes UNREACHABLE (omitted so any stray reach
    #    stalls visibly rather than looping). diff = x_bit - y_bit - borrow_in ∈ {-2..1};
    #    diff < 0 borrows (out = diff mod 2, borrow_out = 1), else (out = diff, borrow 0).
    forms_x = _operand_forms("rx")
    forms_y = _operand_forms("ry")
    borrows = {"0": (_B0, 0), "1": (_B1, 1)}
    for xf, (x_pat, x_rest, x_bit) in forms_x.items():
        for yf, (y_pat, y_rest, y_bit) in forms_y.items():
            for _bf, (b_pat, b_in) in borrows.items():
                if xf == "Z" and yf == "Z" and b_in == 0:
                    # nothing left and no borrow -> fold the bit-stack (carry the sign).
                    projs.append({
                        "pattern": {"_borrow": {"x": None, "y": None, "c": _B0,
                                                "acc": _v("acc"), "sign": _v("sgn")}},
                        "body": {"_subfold": {"acc": _v("acc"), "num": _SEED,
                                              "sign": _v("sgn")}}})
                    continue
                if xf == "Z" and yf == "Z" and b_in == 1:
                    continue  # unreachable underflow (x >= y guaranteed) -> no rule
                diff = x_bit - y_bit - b_in
                out_bit, borrow_out = diff % 2, (1 if diff < 0 else 0)
                emit = "i" if out_bit else "o"
                projs.append({
                    "pattern": {"_borrow": {"x": x_pat, "y": y_pat, "c": b_pat,
                                            "acc": _v("acc"), "sign": _v("sgn")}},
                    "body": {"_borrow": {"x": x_rest, "y": y_rest,
                                         "c": (_B1 if borrow_out else _B0),
                                         "acc": {emit: _v("acc")}, "sign": _v("sgn")}}})

    # -- fold: pop the bit-stack (MSB first) into a canonical numeral, STRIPPING leading
    #    zeros (a difference's high bits may be 0). The first ``i`` bit seeds the ``xH``
    #    terminal; ``x > y`` (strict — EQ is handled before the borrow) guarantees at
    #    least one set bit, so ``num`` is positive by the time ``end`` is reached. Order:
    #    the ``{seed}`` arms (1,2) must precede the ``{var: n}`` arms (3,4) — first-match-wins.
    projs.append({"pattern": {"_subfold": {"acc": {"o": _v("rest")}, "num": _SEED, "sign": _v("sgn")}},
                  "body": {"_subfold": {"acc": _v("rest"), "num": _SEED, "sign": _v("sgn")}}})       # skip leading 0
    projs.append({"pattern": {"_subfold": {"acc": {"i": _v("rest")}, "num": _SEED, "sign": _v("sgn")}},
                  "body": {"_subfold": {"acc": _v("rest"), "num": {"xH": None}, "sign": _v("sgn")}}})  # first 1 -> xH
    projs.append({"pattern": {"_subfold": {"acc": {"o": _v("rest")}, "num": _v("n"), "sign": _v("sgn")}},
                  "body": {"_subfold": {"acc": _v("rest"), "num": {"xO": _v("n")}, "sign": _v("sgn")}}})  # prepend 0
    projs.append({"pattern": {"_subfold": {"acc": {"i": _v("rest")}, "num": _v("n"), "sign": _v("sgn")}},
                  "body": {"_subfold": {"acc": _v("rest"), "num": {"xI": _v("n")}, "sign": _v("sgn")}}})  # prepend 1
    projs.append({"pattern": {"_subfold": {"acc": {"end": None}, "num": _v("n"), "sign": _PLUS}},
                  "body": {"_num": _v("n")}})                                                          # +p -> fixpoint
    projs.append({"pattern": {"_subfold": {"acc": {"end": None}, "num": _v("n"), "sign": _MINUS}},
                  "body": {"_num": {"neg": _v("n")}}})                                                 # -p -> fixpoint
    return projs


SUB_PROJECTIONS = build_subtract_projections()


# =============================================================================
# Corpus — lean (each engine subtract is meta-circular and grows with operand size),
# covering every SUBTRACT path: zero/identity dispatch (0-0, a-0, 0-b neg), equal
# operands (compare EQ -> canonical zero), a > b with NO borrow, the sign-flip swap
# (a < b -> neg form), a full borrow cascade with leading-zero strip (8-7=1), and a
# larger borrow cascade (100-1=99).
# =============================================================================

CORPUS: list[tuple[int, int]] = [
    (0, 0),     # zero - zero -> 0 (dispatch)
    (6, 0),     # subtractive identity: a - 0 = a (dispatch)
    (0, 6),     # 0 - b = -b: the neg-form dispatch arm
    (5, 5),     # equal operands -> canonical zero (compare EQ, no borrow)
    (6, 2),     # a > b, NO borrow: 110 - 010 = 100 (positive difference, 4)
    (2, 6),     # a < b: neg form -4 (sign-flip swap of (6, 2))
    (8, 7),     # full borrow cascade + leading-zero strip: 1000 - 0111 = 0001 (1)
    (100, 1),   # larger borrow cascade: 1100100 - 1 = 1100011 (99)
]

# Required paths must actually be present (guards against silent corpus drift).
assert (0, 0) in CORPUS, "corpus must include zero - zero"
assert (6, 0) in CORPUS and (0, 6) in CORPUS, (
    "corpus must include both dispatch directions (a-0=a and 0-b=-b)"
)
assert (5, 5) in CORPUS, "corpus must include equal operands (canonical zero via compare EQ)"
assert any(a > b for a, b in CORPUS), "corpus must include a > b (positive difference)"
assert any(a < b for a, b in CORPUS), "corpus must include a < b (negative / neg-form difference)"
assert (6, 2) in CORPUS and (2, 6) in CORPUS, "corpus must include a sign-flip pair (a,b) and (b,a)"
assert (8, 7) in CORPUS, "corpus must include a full borrow cascade with leading-zero strip (8-7=1)"
assert (100, 1) in CORPUS, "corpus must include a larger borrow cascade (100-1=99)"


def run_subtract(a: int, b: int) -> tuple[dict, int, bool]:
    """Subtract ``b`` from ``a`` via the test-local SUBTRACT projection driven by ``run_mu``.

    The ENGINE performs the subtraction: the only inputs are the encoded numerals
    ``encode(a)`` / ``encode(b)``; ``run_mu`` compares them (lifted landed COMPARE),
    borrows, and folds them structurally. Returns ``(result_numeral, step_count, stalled)``.

    Operand domain: ``a, b >= 0`` (the engine composes the N-only COMPARE; the result is
    signed). This guard makes the domain explicit — a negative operand is rejected here
    rather than silently entering the N-only compare (where it stalls) or the ``0 - b``
    dispatch arm (where it would wrap an already-``neg`` operand into a non-canonical
    double-``neg``). Fully-signed operands are a deferred follow-up wave (they require
    composing the landed ADD for the sign-mixed cases).
    """
    assert a >= 0 and b >= 0, (
        "SUBTRACT operand domain is non-negative (a, b >= 0): the engine composes the "
        "N-only COMPARE and yields a signed result. Fully-signed operands are deferred "
        "to a follow-up wave (they require composing the landed ADD for sign-mixed cases)."
    )
    state = {"_sub": {"a": encode(a), "b": encode(b)}}
    result, trace, stalled = run_mu(SUB_PROJECTIONS, state, max_steps=4000)
    return result, len(trace), stalled


# Computed once per process (each run_mu subtract is meta-circular and costly).
_SUB_CACHE: dict[tuple[int, int], tuple[dict, int, bool]] | None = None


def _sub_results() -> dict[tuple[int, int], tuple[dict, int, bool]]:
    global _SUB_CACHE
    if _SUB_CACHE is None:
        _SUB_CACHE = {(a, b): run_subtract(a, b) for (a, b) in CORPUS}
    return _SUB_CACHE


def _numeral_nodes_all_single_key(value) -> bool:
    """Every node of a StructuralNumbers numeral is a single-key dict (or null).

    Holds for the positive chain (xO/xI/xH) AND the signed ``neg`` wrapper, which is
    itself a single-key node over a positive chain.
    """
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
# genuinely composes the landed COMPARE, and the imported codec matches the spec.
# These run in every tier (not slow).
# =============================================================================

class TestProjectionScaffolding:
    """The SUBTRACT projection table is linear and composes the landed COMPARE verbatim."""

    def test_projection_count(self):
        # 4 dispatch + 3 sign-dispatch + 13 lifted COMPARE + 31 borrow + 6 fold = 57.
        assert len(SUB_PROJECTIONS) == 4 + 3 + len(COMPARE_PROJECTIONS) + 31 + 6
        assert len(SUB_PROJECTIONS) == 57
        assert len(COMPARE_PROJECTIONS) == 13  # the composed (landed) COMPARE table

    def test_every_projection_has_pattern_and_body(self):
        for proj in SUB_PROJECTIONS:
            assert set(proj) == {"pattern", "body"}

    def test_all_projections_are_linear(self):
        """``run_mu`` rejects non-linear patterns; assert it up front (fast lane)."""
        for proj in SUB_PROJECTIONS:
            names: list[str] = []
            _collect_vars(proj["pattern"], names)
            assert len(names) == len(set(names)), (
                f"non-linear pattern (variable repeated): {proj['pattern']}"
            )

    def test_subtract_composes_landed_compare(self):
        """SUBTRACT composes the LANDED compare (not a copy): every landed COMPARE
        projection, lifted into the ``_sub_cmp`` work-slot, appears verbatim in
        SUB_PROJECTIONS, and each lifted work-slot IS the corresponding landed COMPARE
        pattern/body, with the two operands riding through as carry registers."""
        lifted = _lift_compare_into_sub(COMPARE_PROJECTIONS)
        for cmp_proj, lifted_proj in zip(COMPARE_PROJECTIONS, lifted):
            assert lifted_proj["pattern"]["_sub_cmp"]["work"] == cmp_proj["pattern"]
            assert lifted_proj["body"]["_sub_cmp"]["work"] == cmp_proj["body"]
            assert lifted_proj in SUB_PROJECTIONS, (
                "a lifted landed-COMPARE projection is missing from SUB_PROJECTIONS"
            )
        # The operand copies ride through every lifted COMPARE step untouched.
        for lifted_proj in lifted:
            for side in ("pattern", "body"):
                wrap = lifted_proj[side]["_sub_cmp"]
                assert wrap["a"] == _v(_SA) and wrap["b"] == _v(_SB)

    def test_sign_decided_structurally_not_by_host(self):
        """The sign is decided by the composed COMPARE tag, never a host comparison:
        the three sign-dispatch bodies route purely on the structural ``{"_ord": tag}``
        work value and emit only canonical zero or a ``_borrow`` seed carrying a
        structural ``plus``/``minus`` sign marker."""
        sign_dispatch = [p for p in SUB_PROJECTIONS
                         if "_sub_cmp" in p["pattern"]
                         and "_ord" in p["pattern"]["_sub_cmp"]["work"]]
        assert len(sign_dispatch) == 3  # eq, gt, lt
        seen_tags = set()
        for proj in sign_dispatch:
            tag = next(iter(proj["pattern"]["_sub_cmp"]["work"]["_ord"]))
            seen_tags.add(tag)
            body = proj["body"]
            if tag == "eq":
                assert body == {"_num": None}
            else:
                assert set(body) == {"_borrow"}
                assert body["_borrow"]["sign"] in (_PLUS, _MINUS)
        assert seen_tags == {"eq", "lt", "gt"}

    def test_codec_matches_spec_and_round_trips(self):
        """The imported signed ``Z`` codec reproduces the documented shapes and
        round-trips every operand AND every signed difference in the corpus."""
        assert encode(0) == {"_num": None}
        assert encode(1) == {"_num": {"xH": None}}
        assert encode(6) == {"_num": {"xO": {"xI": {"xH": None}}}}      # 6 = 110b LSB-first
        assert encode(-6) == {"_num": {"neg": {"xO": {"xI": {"xH": None}}}}}
        operands = {x for pair in CORPUS for x in pair}
        diffs = {a - b for a, b in CORPUS}
        for n in operands | diffs:
            assert decode(encode(n)) == n, f"signed codec round-trip failed for {n}"

    def test_corpus_is_non_negative_operands(self):
        """Operands are non-negative (the corpus subtracts non-negative inputs; the
        RESULT may be negative). The neg form arises only in the result."""
        for a, b in CORPUS:
            assert a >= 0 and b >= 0

    def test_negative_operands_are_out_of_domain(self):
        """Bounded non-closure (the precise claim): the OPERAND domain is the
        non-negative integers (the engine composes the N-only COMPARE); only the RESULT
        is signed. A negative operand is explicitly rejected by ``run_subtract`` — it is
        NOT silently routed into the N-only compare (where it stalls) nor into the
        ``0 - b`` arm (where it would wrap an already-``neg`` operand into a
        non-canonical double-``neg``). Fully-signed operands are a deferred follow-up
        wave (they would require composing the landed ADD for the sign-mixed cases),
        exactly as JS cross-substrate parity is deferred. (Fast: the guard raises before
        ``run_mu`` is ever entered.)"""
        # SPEED_OK: bounded — run_subtract asserts a, b >= 0 and raises AssertionError
        # before run_mu is ever entered (see run_subtract's domain guard above), so this
        # negative-operand rejection test never executes the meta-circular kernel. It is
        # genuinely fast and must stay in the green-gate fast lane to keep verifying the
        # operand-domain guard; the transitive run_mu reference is unreachable here.
        for a, b in [(-2, 1), (2, -1), (-5, -2), (0, -6)]:
            with pytest.raises(AssertionError):
                run_subtract(a, b)


# =============================================================================
# Governing assertion (StructuralNumbers.v0.md §3.3): the run_mu SUBTRACT result is a
# valid canonical signed numeral, structurally / hash-equal to encode(a - b).
# =============================================================================

@pytest.mark.l4_expensive
@pytest.mark.slow
class TestStructuralSubtractEquivalence:
    """structural_sub(a,b) ≡ host_to_structural(to_host(a) - to_host(b)) for a, b >= 0."""

    def test_canonical_structural_equality(self):
        """GOVERNING: run_mu(sub) result is structurally identical to encode(a-b)
        — positive form for a>b, canonical zero for a==b, neg form for a<b."""
        results = _sub_results()
        for a, b in CORPUS:
            result, _, _ = results[(a, b)]
            assert result == encode(a - b), (
                f"structural SUBTRACT diverged from encode({a}-{b}={a - b}): got {result}"
            )

    def test_content_hash_equality(self):
        """The result is content-addressed equal to encode(a-b) (free equality)."""
        results = _sub_results()
        for a, b in CORPUS:
            result, _, _ = results[(a, b)]
            assert mu_hash(result) == mu_hash(encode(a - b)), (
                f"content-hash divergence for {a}-{b}"
            )

    def test_result_is_valid_canonical_numeral(self):
        """Result is well-formed Mu, single-key numeral nodes (incl. the neg wrapper),
        in canonical form.

        Canonicality is asserted oracle-independently: a canonical signed numeral is a
        fixed point of encode∘decode (no spurious leading-zero bits, and the neg wrapper
        appears iff the value is negative).
        """
        results = _sub_results()
        for a, b in CORPUS:
            result, _, _ = results[(a, b)]
            assert is_mu(result), f"result for {a}-{b} is not valid Mu: {result}"
            assert "_num" in result and len(result) == 1, (
                f"result for {a}-{b} is not a Z numeral wrapper: {result}"
            )
            assert _numeral_nodes_all_single_key(result["_num"]), (
                f"result for {a}-{b} has a non-single-key numeral node"
            )
            assert result == encode(decode(result)), (
                f"result for {a}-{b} is non-canonical: {result}"
            )

    def test_engine_reaches_stall_fixpoint(self):
        """run_mu converged to the {"_num": ...} fixpoint (not max_steps), and the
        result carries no in-flight SUBTRACT marker — proving the engine transformed it."""
        results = _sub_results()
        for a, b in CORPUS:
            result, steps, stalled = results[(a, b)]
            assert stalled is True, f"run_mu did not stall for {a}-{b} (steps={steps})"
            for state_key in ("_sub", "_sub_cmp", "_borrow", "_subfold"):
                assert state_key not in result, (
                    f"result for {a}-{b} is still an unprocessed {state_key} state"
                )

    def test_decode_to_host_supporting(self):
        """SUPPORTING ONLY (not sufficient): the result decodes to host a - b."""
        results = _sub_results()
        for a, b in CORPUS:
            result, _, _ = results[(a, b)]
            assert decode(result) == a - b, (
                f"decode(run_mu sub) = {decode(result)} != {a}-{b} = {a - b}"
            )


# =============================================================================
# Sign + borrow spotlight — explicit checks on each representative path (same cached
# runs): zero/identity dispatch, equal operands, positive/negative differences, the
# sign-flip symmetry, and the borrow cascades (incl. leading-zero stripping).
# =============================================================================

@pytest.mark.l4_expensive
@pytest.mark.slow
class TestSignAndBorrow:
    """SUBTRACT decides the sign structurally and borrows end-to-end."""

    def test_equal_operands_canonical_zero(self):
        result, _, _ = _sub_results()[(5, 5)]
        assert result == encode(0) == {"_num": None}     # a == b -> canonical zero

    def test_subtract_zero_identity(self):
        result, _, _ = _sub_results()[(6, 0)]
        assert result == encode(6)                       # a - 0 = a

    def test_zero_minus_positive_is_neg_form(self):
        result, _, _ = _sub_results()[(0, 6)]
        assert result == encode(-6)                      # 0 - b = -b
        assert "neg" in result["_num"]                   # the neg wrapper is present

    def test_positive_difference_no_borrow(self):
        result, _, _ = _sub_results()[(6, 2)]
        assert result == encode(4)                       # 110 - 010 = 100 (no borrow)

    def test_negative_difference_neg_form(self):
        result, _, _ = _sub_results()[(2, 6)]
        assert result == encode(-4)                      # a < b -> neg form
        assert "neg" in result["_num"]

    def test_full_borrow_cascade_with_leading_zero_strip(self):
        result, _, _ = _sub_results()[(8, 7)]
        assert result == encode(1)                       # 1000 - 0111 = 0001 (strip 3 zeros)

    def test_larger_borrow_cascade(self):
        result, _, _ = _sub_results()[(100, 1)]
        assert result == encode(99)                      # 1100100 - 1 = 1100011

    def test_sign_flip_symmetry(self):
        """Swapping operands negates the result: (a-b) and (b-a) are opposite-signed."""
        results = _sub_results()
        forward, _, _ = results[(6, 2)]
        backward, _, _ = results[(2, 6)]
        assert forward == encode(4) and backward == encode(-4)
        assert decode(forward) == -decode(backward)
        # The magnitudes are the same positive numeral; only the neg wrapper differs.
        assert forward["_num"] == backward["_num"]["neg"]
