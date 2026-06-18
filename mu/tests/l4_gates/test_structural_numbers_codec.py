"""L4 gate: StructuralNumbers numeral CODEC — nested<->flat as RCX projections.

Stage 2c gate for ``mu/docs/core/StructuralNumbers.v0.md`` (Python-only slice).
Proves, without any runtime/substrate/seed change, that the conversion between the
two structural representations of a binary numeral — the **nested** constructor
tower (the canonical ``positive``/``N`` form of §3.1) and a **flat** uniform
bit-list — is **expressible as RCX projections**: the CODEC machine is defined here
as **test-local Mu projection scaffolding** and executed via the real kernel driver
``run_mu`` on the Python substrate. Both directions are driven by the engine; there
is **no host nested<->flat converter** (that is explicitly forbidden this wave).

The two representations of a non-negative integer ``n``:

  * **Nested** (canonical, §3.1; LSB-outermost constructor tower)::

        0  -> {"_num": null}
        1  -> {"_num": {"xH": null}}
        6  -> {"_num": {"xO": {"xI": {"xH": null}}}}      # 6 = 110b, LSB-first

    The leading ``1`` is fused into the ``xH`` terminator (heterogeneous: ``xH``
    is both "the bit 1" and "the end").

  * **Flat** (uniform bit-list; MSB-first cons of ``b0``/``b1`` cells)::

        0  -> {"_flat": null}
        1  -> {"_flat": {"b1": {"end": null}}}
        6  -> {"_flat": {"b1": {"b1": {"b0": {"end": null}}}}}   # bits 1,1,0 MSB-first

    Every bit is an ordinary ``b0``/``b1`` cell (homogeneous), the leading ``1`` is
    a plain ``b1``, and a dedicated ``end`` marker terminates the list. This is the
    "serialized" / streamable shape of a numeral — the StructuralNumbers analogue of
    Coq ``Pos`` ↔ a list of bits — and a prerequisite for bit-level I/O and for the
    matcher's structural bit operations (Stage 4). It is genuinely a DIFFERENT Mu
    structure (different top tag, different node vocabulary), so the CODEC does real
    structural work — it is not an identity.

Governing obligations (all decided by ``run_mu`` on the Python substrate):

  1. **Forward** ``nested -> flat`` is the engine reduction of ``{"_n2f": nested}``
     to ``{"_flat": ...}``, structurally / content-hash equal to the independently
     constructed ``encode_flat(n)``.
  2. **Reverse** ``flat -> nested`` is the engine reduction of ``{"_f2n": flat}`` to
     ``{"_num": ...}``, structurally / content-hash equal to ``encode_nested(n)``.
  3. **Round-trip identity in BOTH directions**, content-addressed:
     ``reverse(forward(nested)) == nested`` and ``forward(reverse(flat)) == flat``
     (the engine's own output fed back through the engine's other direction).
  4. **Valid-Mu** of each converted form (``is_mu``).
  5. **Same-host-value anchoring**: ``decode_flat(forward(nested)) == n`` and
     ``decode_nested(reverse(flat)) == n`` — the host integer value is preserved
     across the structural conversion.

``encode_flat`` / ``decode_flat`` (and ``encode_nested`` / ``decode_nested``) are
**boundary codecs** between a host ``int`` and a structural numeral — the same class
of test scaffolding as the foundation/add/compare gates' ``encode``/``decode`` — NOT
the forbidden nested<->flat converter. The nested<->flat transform is performed
*only* by the projection table driven by ``run_mu``; the host codecs merely supply
the inputs and the independent oracles, and read the host value back out for the
anchoring check.

The CODEC is built from the binary constructor table so the transition relation is
TOTAL over every reachable state, and every pattern is linear (each variable appears
once) — required by ``run_mu``. The forward and reverse machines share a single
projection table (``CODEC_PROJECTIONS``) and are proven non-interfering: each phase
owns a disjoint state tag (``_n2f``/``_n2fb`` forward, ``_f2n``/``_f2nb`` reverse),
and each result tag (``_flat``/``_num``) is a natural stall fixpoint of the whole
table.

Two REAL kernel constraints bound the corpus (documented, not worked around):
``run_mu`` → ``step_kernel_mu`` runs ``normalize_for_match`` which inflates every
dict level ~3× (depth), and each meta-circular VM micro-step re-validates the whole
state (~0.6s / domain-step). So the corpus is deliberately lean (≤ 8-bit operands,
~8 values × 4 ``run_mu`` runs each) and the engine-driving tests are
``@pytest.mark.slow`` + ``@pytest.mark.l4_expensive`` (the run_mu meta-circular cost
exceeds the green-gate slow-lane 300s timeout, so they run in the slow_tests/nightly
lane at 900s) per ``.claude/rules/test-classification.md``. JS cross-substrate parity
for the CODEC is deferred to a follow-up wave (mirrors the ADD/COMPARE waves).

Wave: structural-numbers-codec-2026-06-18 (L4_ENABLER, target gate G8).
Encoding authority: ``mu/docs/core/StructuralNumbers.v0.md`` §3.1.
Predecessors (Stage 2 arithmetic-as-projections): ``test_structural_numbers_add.py``
(§7.3 ADD) and ``test_structural_numbers_compare.py`` (§3.3 COMPARE). This gate
completes the Stage-2 trio (add + compare + codec) before JS parity and the Stage-4
matcher cutover.
"""
from __future__ import annotations

import pytest

from rcx_pi.selfhost.step_mu import run_mu
from rcx_pi.selfhost.mu_type import is_mu, mu_hash


# =============================================================================
# Nested numeral codec (the canonical §3.1 form) — test-local boundary codec,
# identical to the foundation/add/compare gates (binary, LSB outermost):
#   {"xH": null} = 1 ,  {"xO": r} = 2·r ,  {"xI": r} = 2·r+1
#   0 -> {"_num": null} ,  +p -> {"_num": p}
# The CODEC corpus is non-negative (no subtraction/negatives this wave), so the
# ``neg`` arm is unused.
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


def encode_nested(n: int) -> dict:
    """Encode a non-negative host int to the nested ``N`` Mu numeral (§3.1)."""
    assert n >= 0, "CODEC gate corpus is non-negative (no subtraction this wave)"
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


def decode_nested(mu: dict) -> int:
    """Decode a nested ``N`` Mu numeral back to a host int (inverse of encode_nested)."""
    inner = mu["_num"]
    if inner is None:
        return 0
    return decode_positive(inner)


# =============================================================================
# Flat numeral codec — the uniform bit-list form. Test-local boundary codec
# between a host int and the flat structural numeral (NOT a nested<->flat
# converter). MSB-first cons of single-key bit cells:
#   {"b1": rest} / {"b0": rest} = a bit (rest = the lower bits)
#   {"end": null}                = end of the bit list
#   0 -> {"_flat": null} ,  +p -> {"_flat": <chain>}  (outermost cell = MSB)
# A canonical flat positive has its MOST-significant cell = b1 (no leading zero),
# exactly as a canonical nested positive terminates in xH (= leading 1).
# =============================================================================


def encode_flat(n: int) -> dict:
    """Encode a non-negative host int to the flat (uniform bit-list) Mu numeral."""
    assert n >= 0, "CODEC gate corpus is non-negative"
    if n == 0:
        return {"_flat": None}
    # Collect bits LSB-first, then build the chain inside-out so the MSB ends up
    # outermost (MSB-first) and the LSB sits just inside ``end``.
    bits = []
    m = n
    while m > 0:
        bits.append(m & 1)
        m >>= 1
    node: dict = {"end": None}
    for bit in bits:                       # LSB -> MSB, each wrap moves outward
        node = {"b1": node} if bit else {"b0": node}
    return {"_flat": node}


def decode_flat(flat: dict) -> int:
    """Decode a flat Mu numeral back to a host int (inverse of encode_flat)."""
    node = flat["_flat"]
    if node is None:
        return 0
    value = 0
    while True:
        key = next(iter(node))             # outermost cell first = MSB-first read
        if key == "end":
            return value
        value = (value << 1) | (1 if key == "b1" else 0)
        node = node[key]


# =============================================================================
# nested<->flat CODEC projection — test-local Mu projection scaffolding (the
# wave's structural artifact). A single table holds both directions; they share no
# state tag and never interfere. Every pattern is linear (each variable appears
# once) — required by ``run_mu``. No host conversion primitive: the bit vocabulary
# is rewritten purely by structural pattern matching.
#
# Forward  nested -> flat  (entry tag ``_n2f``, loop tag ``_n2fb``):
#   peel the LSB-outermost constructor, PREPEND the matching bit cell to the
#   accumulator (so the accumulator grows MSB-first), finish at ``xH`` by
#   prepending the leading ``b1`` and wrapping in ``_flat``.
# Reverse  flat -> nested  (entry tag ``_f2n``, loop tag ``_f2nb``):
#   consume the flat chain MSB-first, building the nested numeral by WRAPPING:
#   the first (MS) bit seeds the ``xH`` terminal (it is always 1), each subsequent
#   bit wraps with ``xO``/``xI`` so the LSB ends up outermost, finish at ``end``.
# =============================================================================


def _v(name: str) -> dict:
    """A pattern/body variable site ``{"var": name}``."""
    return {"var": name}


_END = {"end": None}            # flat bit-list terminator
_SEED = {"seed": None}          # reverse: "no nested numeral yet, awaiting the MSB"


def build_codec_projections() -> list[dict]:
    """Construct the nested<->flat CODEC projection table (11 linear projections)."""
    projs: list[dict] = []

    # -- FORWARD: nested -> flat ------------------------------------------------
    # dispatch (zero literal must precede the generic positive capture).
    projs.append({"pattern": {"_n2f": {"_num": None}},
                  "body": {"_flat": None}})                              # 0 -> flat 0
    projs.append({"pattern": {"_n2f": {"_num": _v("p")}},
                  "body": {"_n2fb": {"p": _v("p"), "acc": _END}}})       # +p -> enter loop
    # loop: peel LSB-outermost constructor, prepend the bit cell (MSB-first acc).
    projs.append({"pattern": {"_n2fb": {"p": {"xO": _v("rest")}, "acc": _v("acc")}},
                  "body": {"_n2fb": {"p": _v("rest"), "acc": {"b0": _v("acc")}}}})
    projs.append({"pattern": {"_n2fb": {"p": {"xI": _v("rest")}, "acc": _v("acc")}},
                  "body": {"_n2fb": {"p": _v("rest"), "acc": {"b1": _v("acc")}}}})
    #   xH = the leading 1: prepend a final b1 and finish (acc is now the full chain).
    projs.append({"pattern": {"_n2fb": {"p": {"xH": None}, "acc": _v("acc")}},
                  "body": {"_flat": {"b1": _v("acc")}}})

    # -- REVERSE: flat -> nested ------------------------------------------------
    # dispatch (zero literal must precede the generic chain capture).
    projs.append({"pattern": {"_f2n": {"_flat": None}},
                  "body": {"_num": None}})                               # flat 0 -> 0
    projs.append({"pattern": {"_f2n": {"_flat": _v("chain")}},
                  "body": {"_f2nb": {"f": _v("chain"), "num": _SEED}}})  # enter loop
    # loop: consume MSB-first, build the nested numeral by wrapping. Rule A (the MS
    # bit, seeding xH) must precede rule C (a b1 over an existing numeral) since both
    # match a ``b1`` cell — the seed literal disambiguates the first bit.
    projs.append({"pattern": {"_f2nb": {"f": {"b1": _v("rest")}, "num": {"seed": None}}},
                  "body": {"_f2nb": {"f": _v("rest"), "num": {"xH": None}}}})        # A
    projs.append({"pattern": {"_f2nb": {"f": {"b1": _v("rest")}, "num": _v("n")}},
                  "body": {"_f2nb": {"f": _v("rest"), "num": {"xI": _v("n")}}}})     # C
    projs.append({"pattern": {"_f2nb": {"f": {"b0": _v("rest")}, "num": _v("n")}},
                  "body": {"_f2nb": {"f": _v("rest"), "num": {"xO": _v("n")}}}})     # B
    projs.append({"pattern": {"_f2nb": {"f": {"end": None}, "num": _v("n")}},
                  "body": {"_num": _v("n")}})                                        # T
    return projs


CODEC_PROJECTIONS = build_codec_projections()


# =============================================================================
# Canonicality / shape helpers (host-side, no run_mu).
# =============================================================================


def _is_canonical_nested(value) -> bool:
    """A canonical nested numeral: ``{"_num": null}`` (zero) or a single-key
    ``xO``/``xI`` tower terminated by ``{"xH": null}`` (no residual markers)."""
    if not isinstance(value, dict) or len(value) != 1 or "_num" not in value:
        return False
    node = value["_num"]
    if node is None:
        return True
    while True:
        if not isinstance(node, dict) or len(node) != 1:
            return False
        key = next(iter(node))
        if key == "xH":
            return node[key] is None
        if key not in ("xO", "xI"):
            return False
        node = node[key]


def _is_canonical_flat(value) -> bool:
    """A canonical flat numeral: ``{"_flat": null}`` (zero) or a single-key
    ``b0``/``b1`` chain terminated by ``{"end": null}`` whose MOST-significant cell
    (outermost) is ``b1`` (no leading zero); no residual markers."""
    if not isinstance(value, dict) or len(value) != 1 or "_flat" not in value:
        return False
    node = value["_flat"]
    if node is None:
        return True
    first = True
    while True:
        if not isinstance(node, dict) or len(node) != 1:
            return False
        key = next(iter(node))
        if key == "end":
            return node[key] is None and not first  # must hold >= 1 bit
        if key not in ("b0", "b1"):
            return False
        if first and key != "b1":
            return False  # leading zero -> non-canonical
        first = False
        node = node[key]


# =============================================================================
# Corpus — lean (engine cost ~0.6s/step), non-negative, ≤ 8-bit, covering the
# mandatory shapes: zero (both dispatch arms), a single bit (MSB-only), powers of
# two (long b0/xO runs), all-ones (all b1/xI), and mixed/alternating bit patterns.
# =============================================================================

CORPUS: list[int] = [
    0,      # zero — drives both zero-dispatch arms (forward rule + reverse rule)
    1,      # single bit: nested {xH} <-> flat {b1,end}
    2,      # 10b: one xO then xH  <->  b1,b0
    6,      # 110b: mixed interior bits
    8,      # 1000b: power of two — long low-zero run (xO chain / b0 chain)
    21,     # 10101b: 5-bit alternating
    170,    # 10101010b: 8-bit alternating
    255,    # 11111111b: 8-bit all-ones (all xI / all b1)
]

# Mandatory shapes must actually be present (guards against silent corpus drift).
assert 0 in CORPUS, "corpus must include 0 (drives both zero-dispatch arms)"
assert 1 in CORPUS, "corpus must include 1 (single-bit / MSB-only)"
assert any(n > 0 and (n & (n - 1)) == 0 for n in CORPUS), "corpus must include a power of two"
assert 255 in CORPUS, "corpus must include an all-ones operand (255 = 11111111b)"


def run_forward(nested: dict) -> tuple[dict, int, bool]:
    """nested -> flat via the test-local CODEC driven by ``run_mu`` (Python)."""
    state = {"_n2f": nested}
    result, trace, stalled = run_mu(CODEC_PROJECTIONS, state, max_steps=2000)
    return result, len(trace), stalled


def run_reverse(flat: dict) -> tuple[dict, int, bool]:
    """flat -> nested via the test-local CODEC driven by ``run_mu`` (Python)."""
    state = {"_f2n": flat}
    result, trace, stalled = run_mu(CODEC_PROJECTIONS, state, max_steps=2000)
    return result, len(trace), stalled


# Computed once per process (each run_mu codec run is meta-circular and costly).
# Per n: forward(encode_nested) and reverse(encode_flat) are the governing runs;
# the round-trips CHAIN the engine's own output back through the other direction
# (a genuine second run_mu execution, not a host re-derivation).
_CODEC_CACHE: dict[int, dict] | None = None


def _codec_results() -> dict[int, dict]:
    global _CODEC_CACHE
    if _CODEC_CACHE is None:
        cache: dict[int, dict] = {}
        for n in CORPUS:
            fwd, fwd_steps, fwd_stall = run_forward(encode_nested(n))
            rev, rev_steps, rev_stall = run_reverse(encode_flat(n))
            # Round-trips: feed the engine's OWN output back through the engine.
            rt_nfn, _, rt_nfn_stall = run_reverse(fwd)   # nested -> flat -> nested
            rt_fnf, _, rt_fnf_stall = run_forward(rev)   # flat -> nested -> flat
            cache[n] = {
                "fwd": fwd, "fwd_steps": fwd_steps, "fwd_stall": fwd_stall,
                "rev": rev, "rev_steps": rev_steps, "rev_stall": rev_stall,
                "rt_nfn": rt_nfn, "rt_nfn_stall": rt_nfn_stall,
                "rt_fnf": rt_fnf, "rt_fnf_stall": rt_fnf_stall,
            }
        _CODEC_CACHE = cache
    return _CODEC_CACHE


# =============================================================================
# Fast scaffolding sanity (no run_mu) — codecs match the spec and the CODEC
# projection table is well-formed, linear, and the two representations are genuinely
# distinct. These run in every tier (not slow).
# =============================================================================

class TestProjectionScaffolding:
    """The local codecs match the spec and the CODEC projection table is linear."""

    def test_nested_codec_matches_spec(self):
        assert encode_nested(0) == {"_num": None}
        assert encode_nested(1) == {"_num": {"xH": None}}
        assert encode_nested(2) == {"_num": {"xO": {"xH": None}}}
        assert encode_nested(6) == {"_num": {"xO": {"xI": {"xH": None}}}}

    def test_flat_codec_matches_spec(self):
        assert encode_flat(0) == {"_flat": None}
        assert encode_flat(1) == {"_flat": {"b1": {"end": None}}}
        assert encode_flat(2) == {"_flat": {"b1": {"b0": {"end": None}}}}      # 10b MSB-first
        assert encode_flat(6) == {"_flat": {"b1": {"b1": {"b0": {"end": None}}}}}  # 110b

    def test_both_codecs_round_trip_corpus(self):
        for n in CORPUS:
            assert decode_nested(encode_nested(n)) == n, f"nested codec round-trip failed for {n}"
            assert decode_flat(encode_flat(n)) == n, f"flat codec round-trip failed for {n}"

    def test_canonicality_helpers_accept_codec_output(self):
        for n in CORPUS:
            assert _is_canonical_nested(encode_nested(n))
            assert _is_canonical_flat(encode_flat(n))
        # ...and reject a leading-zero flat (the non-canonical shape) and residue.
        assert not _is_canonical_flat({"_flat": {"b0": {"b1": {"end": None}}}})
        assert not _is_canonical_nested({"_n2fb": {"p": None, "acc": None}})

    def test_representations_are_distinct(self):
        """The flat form is a genuinely different Mu structure than the nested form
        (different top tag and node vocabulary) — so the CODEC does real work."""
        for n in CORPUS:
            nested, flat = encode_nested(n), encode_flat(n)
            assert nested != flat, f"nested and flat must differ for {n}"
            assert mu_hash(nested) != mu_hash(flat), f"nested/flat must not hash-collide for {n}"

    def test_projection_count(self):
        # 5 forward (2 dispatch + 3 loop) + 6 reverse (2 dispatch + 4 loop) = 11.
        assert len(CODEC_PROJECTIONS) == 11

    def test_every_projection_has_pattern_and_body(self):
        for proj in CODEC_PROJECTIONS:
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
        for proj in CODEC_PROJECTIONS:
            names: list[str] = []
            collect_vars(proj["pattern"], names)
            assert len(names) == len(set(names)), (
                f"non-linear pattern (variable repeated): {proj['pattern']}"
            )

    def test_no_host_conversion_inside_projections(self):
        """The conversion is structural: every projection's state tags are drawn
        only from the CODEC's own vocabulary — no host arithmetic/conversion sentinel
        leaks into a pattern or body."""
        allowed_tags = {
            "_n2f", "_n2fb", "_f2n", "_f2nb", "_flat", "_num",
            "xO", "xI", "xH", "b0", "b1", "end", "seed",
            "p", "acc", "f", "num", "rest", "chain", "var",
        }

        def walk_keys(node):
            if isinstance(node, dict):
                for key, child in node.items():
                    assert key in allowed_tags, f"unexpected tag in projection: {key}"
                    walk_keys(child)

        for proj in CODEC_PROJECTIONS:
            walk_keys(proj["pattern"])
            walk_keys(proj["body"])

    def test_corpus_is_non_negative(self):
        for n in CORPUS:
            assert n >= 0


# =============================================================================
# Forward (nested -> flat) — governing equivalence + valid-Mu + value anchoring.
# =============================================================================

@pytest.mark.l4_expensive
@pytest.mark.slow
class TestNestedToFlat:
    """run_mu(nested -> flat) == encode_flat(n), canonical, value-preserving."""

    def test_canonical_structural_equality(self):
        """GOVERNING: the engine's forward result is identical to encode_flat(n)."""
        results = _codec_results()
        for n in CORPUS:
            fwd = results[n]["fwd"]
            assert fwd == encode_flat(n), (
                f"forward CODEC diverged for {n}: got {fwd}, expected {encode_flat(n)}"
            )

    def test_content_hash_equality(self):
        """The forward result is content-addressed equal to encode_flat(n)."""
        results = _codec_results()
        for n in CORPUS:
            assert mu_hash(results[n]["fwd"]) == mu_hash(encode_flat(n)), (
                f"content-hash divergence for forward CODEC({n})"
            )

    def test_result_is_valid_canonical_flat(self):
        """Forward result is valid Mu and a canonical flat numeral (no residue)."""
        results = _codec_results()
        for n in CORPUS:
            fwd = results[n]["fwd"]
            assert is_mu(fwd), f"forward result for {n} is not valid Mu: {fwd}"
            assert _is_canonical_flat(fwd), f"forward result for {n} is not canonical flat: {fwd}"
            assert fwd == encode_flat(decode_flat(fwd)), f"forward result for {n} is non-canonical"

    def test_same_host_value(self):
        """Same-host-value anchoring: the flat form decodes to the original n."""
        results = _codec_results()
        for n in CORPUS:
            assert decode_flat(results[n]["fwd"]) == n, (
                f"forward CODEC did not preserve host value for {n}"
            )

    def test_engine_reaches_stall_fixpoint(self):
        """run_mu converged to the {"_flat": ...} fixpoint and fully reduced the
        forward markers — proving the engine actually performed the conversion."""
        results = _codec_results()
        for n in CORPUS:
            fwd, steps, stall = results[n]["fwd"], results[n]["fwd_steps"], results[n]["fwd_stall"]
            assert stall is True, f"run_mu did not stall for forward CODEC({n}) (steps={steps})"
            assert "_n2f" not in fwd and "_n2fb" not in fwd, (
                f"forward result for {n} still carries an unprocessed forward marker"
            )
            assert fwd != {"_n2f": encode_nested(n)}, f"forward result for {n} is the input state"


# =============================================================================
# Reverse (flat -> nested) — governing equivalence + valid-Mu + value anchoring.
# =============================================================================

@pytest.mark.l4_expensive
@pytest.mark.slow
class TestFlatToNested:
    """run_mu(flat -> nested) == encode_nested(n), canonical, value-preserving."""

    def test_canonical_structural_equality(self):
        """GOVERNING: the engine's reverse result is identical to encode_nested(n)."""
        results = _codec_results()
        for n in CORPUS:
            rev = results[n]["rev"]
            assert rev == encode_nested(n), (
                f"reverse CODEC diverged for {n}: got {rev}, expected {encode_nested(n)}"
            )

    def test_content_hash_equality(self):
        """The reverse result is content-addressed equal to encode_nested(n)."""
        results = _codec_results()
        for n in CORPUS:
            assert mu_hash(results[n]["rev"]) == mu_hash(encode_nested(n)), (
                f"content-hash divergence for reverse CODEC({n})"
            )

    def test_result_is_valid_canonical_nested(self):
        """Reverse result is valid Mu and a canonical nested numeral (no residue)."""
        results = _codec_results()
        for n in CORPUS:
            rev = results[n]["rev"]
            assert is_mu(rev), f"reverse result for {n} is not valid Mu: {rev}"
            assert _is_canonical_nested(rev), f"reverse result for {n} is not canonical nested: {rev}"
            assert rev == encode_nested(decode_nested(rev)), f"reverse result for {n} is non-canonical"

    def test_same_host_value(self):
        """Same-host-value anchoring: the nested form decodes to the original n."""
        results = _codec_results()
        for n in CORPUS:
            assert decode_nested(results[n]["rev"]) == n, (
                f"reverse CODEC did not preserve host value for {n}"
            )

    def test_engine_reaches_stall_fixpoint(self):
        """run_mu converged to the {"_num": ...} fixpoint and fully reduced the
        reverse markers — proving the engine actually performed the conversion."""
        results = _codec_results()
        for n in CORPUS:
            rev, steps, stall = results[n]["rev"], results[n]["rev_steps"], results[n]["rev_stall"]
            assert stall is True, f"run_mu did not stall for reverse CODEC({n}) (steps={steps})"
            assert "_f2n" not in rev and "_f2nb" not in rev, (
                f"reverse result for {n} still carries an unprocessed reverse marker"
            )
            assert rev != {"_f2n": encode_flat(n)}, f"reverse result for {n} is the input state"


# =============================================================================
# Round-trip identity in BOTH directions — content-addressed. The engine's OWN
# output is fed back through the engine's OTHER direction (a genuine second run_mu
# execution), and must reproduce the original structure exactly.
# =============================================================================

@pytest.mark.l4_expensive
@pytest.mark.slow
class TestRoundTripIdentity:
    """reverse(forward(nested)) == nested  and  forward(reverse(flat)) == flat."""

    def test_nested_flat_nested_identity(self):
        """nested -> flat -> nested reproduces the original nested numeral."""
        results = _codec_results()
        for n in CORPUS:
            original = encode_nested(n)
            rt = results[n]["rt_nfn"]
            assert rt == original, (
                f"nested->flat->nested broke identity for {n}: got {rt}, expected {original}"
            )
            assert mu_hash(rt) == mu_hash(original), (
                f"nested->flat->nested content-hash divergence for {n}"
            )
            assert is_mu(rt) and _is_canonical_nested(rt)

    def test_flat_nested_flat_identity(self):
        """flat -> nested -> flat reproduces the original flat numeral."""
        results = _codec_results()
        for n in CORPUS:
            original = encode_flat(n)
            rt = results[n]["rt_fnf"]
            assert rt == original, (
                f"flat->nested->flat broke identity for {n}: got {rt}, expected {original}"
            )
            assert mu_hash(rt) == mu_hash(original), (
                f"flat->nested->flat content-hash divergence for {n}"
            )
            assert is_mu(rt) and _is_canonical_flat(rt)

    def test_round_trips_reached_stall_fixpoint(self):
        """Both round-trip chains converged (the second leg also stalled cleanly)."""
        results = _codec_results()
        for n in CORPUS:
            assert results[n]["rt_nfn_stall"] is True, f"nested->flat->nested did not stall for {n}"
            assert results[n]["rt_fnf_stall"] is True, f"flat->nested->flat did not stall for {n}"

    def test_host_value_preserved_through_both_round_trips(self):
        """Same-host-value across both full round-trips (host integer anchor)."""
        results = _codec_results()
        for n in CORPUS:
            assert decode_nested(results[n]["rt_nfn"]) == n, f"n->f->n lost host value for {n}"
            assert decode_flat(results[n]["rt_fnf"]) == n, f"f->n->f lost host value for {n}"
