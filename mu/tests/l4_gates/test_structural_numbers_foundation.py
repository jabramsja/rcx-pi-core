"""L4 gate: StructuralNumbers foundation — cross-substrate equivalence.

Stage-1 foundation gate for ``mu/docs/core/StructuralNumbers.v0.md``. Proves, in
isolation and without any runtime/substrate/seed change, that the binary-positional
structural numeral (Coq ``positive``/``N``/``Z`` shape) satisfies the four
foundation properties the staged numeric-representation program depends on:

1. **Valid Mu** — every integer's binary-positional numeral encoding is a
   well-formed Mu structure (``is_mu`` / JS ``isValidMu``), within ``MAX_MU_DEPTH``.
2. **Content-addressed equality** — ``mu_hash(encode(a)) == mu_hash(encode(b))``
   iff ``a == b`` (content hash is injective over the numeral domain). Equality is
   free via content-addressed hashing, exactly as the design specifies (§3.2).
3. **int/BigInt round-trip** — the host-accelerated codec is exact:
   ``decode(encode(n)) == n`` for every corpus value, using Python ``int`` and
   JS ``BigInt`` (both arbitrary-precision, no host float).
4. **Python/JS parity** — both substrates produce the SAME content hash for each
   numeral (L3 parity, ``INV_CROSS_SUBSTRATE_PARITY``).

Parity is safe **by construction**: the numeral is pure ``xI``/``xO``/``xH``/``neg``/
``null`` dict structure with exactly one key per node, so no host int/float string
ever enters the hash and no multi-key ordering can diverge. This is precisely the
property that the 2026-06-16 signed-zero collapse attempt lacked (cf.
``reference_stage0_signed_zero_divergence``): zero is the unique ``{"_num": null}``,
so signed-zero is not representable and needs no host canonicalization.

Scope: GATE-ONLY. The encode/decode codec is defined locally in this test (both
substrates) — it is test scaffolding, not runtime code. No ``_stage0_match``
cutover, no arithmetic-projection seed; those are later StructuralNumbers stages.

Wave: structural-numbers-foundation-gate-2026-06-17 (L4_ENABLER, target gate G8).
Encoding authority: ``mu/docs/core/StructuralNumbers.v0.md`` §3.1.
"""
from __future__ import annotations

import json
import subprocess

from tests.repo_root import REPO_ROOT
from rcx_pi.selfhost.mu_type import (
    MAX_MU_DEPTH,
    is_mu,
    mu_hash,
    mu_hash_cached,
)


# =============================================================================
# Python reference codec (StructuralNumbers.v0.md §3.1, binary LSB-first)
#
#   positive ::= xH                  -- 1
#              | xO positive         -- 2*p   (low bit 0)
#              | xI positive         -- 2*p+1 (low bit 1)
#   N        ::= N0 | Npos positive  -- 0, or a positive
#   Z        ::= Z0 | Zpos positive | Zneg positive
#
# As Mu (every node a single-key dict or null):
#   0  -> {"_num": null}
#   1  -> {"_num": {"xH": null}}
#   6  -> {"_num": {"xO": {"xI": {"xH": null}}}}        # 6 = 110b, LSB-first
#   -6 -> {"_num": {"neg": {"xO": {"xI": {"xH": null}}}}}
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
    """Encode a host int to the ``Z`` Mu numeral per StructuralNumbers.v0.md §3.1."""
    if n == 0:
        return {"_num": None}
    if n > 0:
        return {"_num": encode_positive(n)}
    return {"_num": {"neg": encode_positive(-n)}}


def decode_positive(node: dict) -> int:
    """Decode a ``positive`` numeral back to a host int (>= 1)."""
    value = 0
    weight = 1
    while True:
        key = next(iter(node))
        if key == "xH":
            value += weight
            return value
        if key == "xI":
            value += weight
        node = node[key]
        weight <<= 1


def decode(mu: dict) -> int:
    """Decode a ``Z`` Mu numeral back to a host int (inverse of ``encode``)."""
    inner = mu["_num"]
    if inner is None:
        return 0
    if "neg" in inner:
        return -decode_positive(inner["neg"])
    return decode_positive(inner)


def _mu_depth(value) -> int:
    """Structural depth of a Mu dict tree (matches is_mu depth accounting)."""
    if isinstance(value, dict):
        return 1 + max((_mu_depth(v) for v in value.values()), default=0)
    return 0


# =============================================================================
# Corpus — deterministic, spans the spec examples, power-of-two boundaries that
# exceed JS Number safe-integer range, mixed-bit large values, and negatives.
# MUST include 2**250 (Mu depth ~250 < MAX_MU_DEPTH=300) per the wave plan.
# =============================================================================

POW_250 = 2 ** 250

CORPUS: list[int] = [
    # spec / small-magnitude
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 16, 17, 31, 32,
    255, 256, 257, 1023, 1024,
    # power-of-two boundaries and neighbours (cross the JS 2**53 safe-int wall)
    2 ** 32, 2 ** 32 - 1,
    2 ** 53, 2 ** 53 + 1,
    2 ** 64, 2 ** 64 - 1,
    2 ** 128, 2 ** 128 + 1,
    POW_250,
    # mixed-bit large values
    2 ** 100 + 2 ** 50 + 7,
    2 ** 200 - 1,
    1234567890123456789012345678901234567890,
    # negatives (mirror the magnitude space, incl. deepest)
    -1, -2, -6, -255, -256, -(2 ** 64), -(2 ** 128), -POW_250,
]

# Distinct ints -> the corpus must itself contain no duplicates, otherwise the
# "distinct hashes" injectivity assertion would be vacuously checking equals.
assert len(CORPUS) == len(set(CORPUS)), "corpus must contain distinct integers"


# =============================================================================
# JS reference codec — independent BigInt implementation of the SAME spec.
# Embedded here (single gate file, no new module) and driven via `node -e`,
# mirroring the established cross-substrate test pattern in this directory.
# Building via container_factory yields trusted Mu containers directly.
# =============================================================================

_JS_NUMERAL_SRC = r"""
const t = require('./mu/host/js/core/types');
const mc = require('./mu/host/js/core/container_factory');

function encodePositive(p) {            // p: BigInt >= 1n
  const lower = [];
  while (p > 1n) { lower.push(p & 1n); p >>= 1n; }
  let node = mc.record([["xH", null]]);
  for (let i = lower.length - 1; i >= 0; i--) {
    node = mc.record([[lower[i] === 1n ? "xI" : "xO", node]]);
  }
  return node;
}
function encode(n) {                    // n: BigInt
  if (n === 0n) return mc.record([["_num", null]]);
  if (n > 0n) return mc.record([["_num", encodePositive(n)]]);
  return mc.record([["_num", mc.record([["neg", encodePositive(-n)]])]]);
}
function decodePositive(node) {
  let value = 0n, weight = 1n;
  while (true) {
    const key = Object.keys(node)[0];
    if (key === "xH") { value += weight; return value; }
    if (key === "xI") value += weight;
    node = node[key];
    weight <<= 1n;
  }
}
function decode(mu) {
  const inner = mu["_num"];
  if (inner === null) return 0n;
  if ("neg" in inner) return -decodePositive(inner["neg"]);
  return decodePositive(inner);
}
function emit(corpus) {
  const out = {};
  for (const s of corpus) {
    const n = BigInt(s);
    const e = encode(n);
    out[s] = {
      hash: t.muHash(e),
      hashCached: t.muHashCached(e),
      valid: t.isValidMu(e),
      roundtrip: decode(e) === n,
    };
  }
  console.log(JSON.stringify(out));
}
"""


def _run_js_numerals(corpus: list[int]) -> dict:
    """Run the JS reference codec over the corpus; return {decimal-str: result}."""
    corpus_strs = [str(n) for n in corpus]
    code = _JS_NUMERAL_SRC + "\nemit(" + json.dumps(corpus_strs) + ");\n"
    result = subprocess.run(
        ["node", "-e", code],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=60,
    )
    assert result.returncode == 0, f"JS numeral eval failed:\n{result.stderr}"
    return json.loads(result.stdout.strip())


# Computed once per session: the JS side is a subprocess, so cache its output.
_JS_RESULTS_CACHE: dict | None = None


def _js_results() -> dict:
    global _JS_RESULTS_CACHE
    if _JS_RESULTS_CACHE is None:
        _JS_RESULTS_CACHE = _run_js_numerals(CORPUS)
    return _JS_RESULTS_CACHE


# =============================================================================
# Property 0: the encoder matches StructuralNumbers.v0.md §3.1 literally.
# =============================================================================

class TestEncodingMatchesSpec:
    """The local encoder reproduces the documented numeral shapes exactly."""

    def test_zero_is_num_null(self):
        assert encode(0) == {"_num": None}

    def test_one_is_xh(self):
        assert encode(1) == {"_num": {"xH": None}}

    def test_six_matches_doc_example(self):
        # 6 = 110b, bits 0,1,1 LSB-first  ->  xO xI xH
        assert encode(6) == {"_num": {"xO": {"xI": {"xH": None}}}}

    def test_negative_six_matches_doc_example(self):
        assert encode(-6) == {"_num": {"neg": {"xO": {"xI": {"xH": None}}}}}

    def test_two_and_three(self):
        assert encode(2) == {"_num": {"xO": {"xH": None}}}
        assert encode(3) == {"_num": {"xI": {"xH": None}}}

    def test_every_numeral_node_is_single_key(self):
        """Single-key nodes are why hashing is ordering-immune across substrates."""
        def walk(v):
            if isinstance(v, dict):
                assert len(v) == 1, f"numeral node must be single-key, got {v.keys()}"
                for child in v.values():
                    walk(child)
        for n in CORPUS:
            walk(encode(n))


# =============================================================================
# Property 1: valid Mu.
# =============================================================================

class TestValidMu:
    """Every numeral is a well-formed Mu structure within the depth bound."""

    def test_all_corpus_is_mu(self):
        for n in CORPUS:
            assert is_mu(encode(n)), f"encode({n}) is not valid Mu"

    def test_pow_250_within_depth_bound(self):
        """2**250 must encode within MAX_MU_DEPTH (the decisive O(log n) property)."""
        assert POW_250 in CORPUS, "corpus must include 2**250 per the wave plan"
        depth = _mu_depth(encode(POW_250))
        assert depth < MAX_MU_DEPTH, (
            f"encode(2**250) depth {depth} must be < MAX_MU_DEPTH {MAX_MU_DEPTH}"
        )
        # And it is genuinely accepted by is_mu (which enforces MAX_MU_DEPTH).
        assert is_mu(encode(POW_250))

    def test_deepest_negative_within_depth_bound(self):
        """The negative wrapper adds one level; the deepest corpus value still fits."""
        deepest = min(CORPUS, key=lambda n: -_mu_depth(encode(n)))
        assert is_mu(encode(deepest))
        assert _mu_depth(encode(deepest)) < MAX_MU_DEPTH

    def test_hash_accepts_every_numeral(self):
        """mu_hash internally asserts validity; it must not raise on any numeral."""
        for n in CORPUS:
            h = mu_hash(encode(n))
            assert isinstance(h, str) and len(h) == 64


# =============================================================================
# Property 2: content-addressed equality (hash equal IFF int equal).
# =============================================================================

class TestContentAddressedEquality:
    """mu_hash(encode(a)) == mu_hash(encode(b))  <=>  a == b."""

    def test_distinct_ints_have_distinct_hashes(self):
        """Injectivity: no two distinct corpus ints collide (no leading-zero
        ambiguity in the binary-positional form)."""
        hashes = {n: mu_hash(encode(n)) for n in CORPUS}
        assert len(set(hashes.values())) == len(CORPUS), (
            "content hash must be injective over distinct integers"
        )

    def test_equality_iff_int_equality_all_pairs(self):
        """The full biconditional across every ordered pair in the corpus."""
        hashes = {n: mu_hash(encode(n)) for n in CORPUS}
        for a in CORPUS:
            for b in CORPUS:
                assert (hashes[a] == hashes[b]) == (a == b), (
                    f"hash-equality must match int-equality for ({a}, {b})"
                )

    def test_independent_constructions_hash_equal(self):
        """Equal ints reached by different host computations hash identically."""
        assert mu_hash(encode(6)) == mu_hash(encode(2 * 3))
        assert mu_hash(encode(2 ** 64)) == mu_hash(encode(2 ** 32 * 2 ** 32))
        assert mu_hash(encode(0)) == mu_hash(encode(POW_250 - POW_250))

    def test_cached_and_uncached_hash_agree(self):
        """mu_hash and mu_hash_cached are the same content hash (design §3.2)."""
        for n in CORPUS:
            e = encode(n)
            assert mu_hash(e) == mu_hash_cached(e)


# =============================================================================
# Property 3: int/BigInt round-trip (exact host-accelerated codec).
# =============================================================================

class TestIntBigIntRoundTrip:
    """decode(encode(n)) == n on both substrates (Python int, JS BigInt)."""

    def test_python_int_round_trip(self):
        for n in CORPUS:
            assert decode(encode(n)) == n, f"Python round-trip failed for {n}"

    def test_js_bigint_round_trip(self):
        js = _js_results()
        for n in CORPUS:
            entry = js[str(n)]
            assert entry["roundtrip"] is True, f"JS BigInt round-trip failed for {n}"


# =============================================================================
# Property 4: Python/JS parity (INV_CROSS_SUBSTRATE_PARITY, L3).
# =============================================================================

class TestCrossSubstrateParity:
    """Python and JS substrates produce the SAME content hash for each numeral."""

    def test_js_reports_all_valid(self):
        js = _js_results()
        for n in CORPUS:
            assert js[str(n)]["valid"] is True, f"JS isValidMu failed for {n}"

    def test_content_hash_parity(self):
        """Python mu_hash == JS muHash for every numeral (the core L3 gate)."""
        js = _js_results()
        for n in CORPUS:
            py = mu_hash(encode(n))
            assert py == js[str(n)]["hash"], (
                f"cross-substrate content-hash divergence for {n}: "
                f"py={py} js={js[str(n)]['hash']}"
            )

    def test_cached_content_hash_parity(self):
        """Python mu_hash_cached == JS muHashCached for every numeral."""
        js = _js_results()
        for n in CORPUS:
            py = mu_hash_cached(encode(n))
            assert py == js[str(n)]["hashCached"], (
                f"cross-substrate cached-hash divergence for {n}"
            )

    def test_js_self_coherence(self):
        """JS muHash and muHashCached agree (no JS-internal cache divergence)."""
        js = _js_results()
        for n in CORPUS:
            assert js[str(n)]["hash"] == js[str(n)]["hashCached"], (
                f"JS muHash != muHashCached for {n}"
            )
