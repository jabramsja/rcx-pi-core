"""L4 gate: StructuralNumbers binary COMPARE — cross-substrate L3 parity (Python ↔ JS).

Stage 2b-ii gate for ``mu/docs/core/StructuralNumbers.v0.md``. The Python-only slice
(``test_structural_numbers_compare.py``) proved binary COMPARE (the §3.3 three-way
EQ/LT/GT ordering) is expressible as RCX projections driven by the real Python kernel
(``run_mu``). This gate adds the **mandatory L3 parity** obligation for the ordering op
(``INV_CROSS_SUBSTRATE_PARITY``), mirroring the ADD parity gate
(``test_structural_numbers_add_js_parity.py``, PR #1111): the **same landed COMPARE
projection table** run through the **JS substrate**
(``mu/host/js/core/bootstrap_core.js`` ``run`` via ``node``) yields a verdict that is
**content-addressed-equal** to the Python ``run_mu`` verdict —

    muHashCached(js_bootstrap_core_run(cmp)) == mu_hash_cached(python_run_mu(cmp))

byte-identical — and both decode (``decode_ord``) to the host three-way ordering tag
``(a > b) - (a < b)`` ∈ {lt, eq, gt}. Content-addressed equality is the design's free
equality (``StructuralNumbers.v0.md`` §3.2): if the two engines converge to the same
canonical ordering tag, their content hashes are byte-identical.

Single source of truth: the projection table, codec, corpus, and Python driver are
**imported** from ``test_structural_numbers_compare`` rather than re-derived, so this
gate validates the **landed** projections (not a copy) and guarantees the *same* table
is fed to both substrates. The table is serialized to JSON in Python and rebuilt in JS
as **trusted** Mu containers via the existing ``container_factory`` (``list`` /
``record``) through the ``trustMu`` helper — JS ``isValidMu`` requires
``muContainers.has(value)``, and the factory adds each value to its private trusted set
at call time (the "registered" step). ``container_factory.js`` is USE-ONLY: imported and
called, never modified.

Imports mirror the ADD parity gate, adapted for the ordering op. The COMPARE result is
an ``{"_ord": {eq|lt|gt: null}}`` tag (not a numeral), so the result is decoded with the
landed ordering codec ``decode_ord`` (the numeral ``decode`` has no role here and is
intentionally not imported). The host oracle sign ``(a > b) - (a < b)`` is computed
inline — exactly as the ADD gate computes ``a + b`` inline — and encoded with the landed
``encode_ord``.

Scope: GATE-ONLY, additive. No runtime/substrate/seed change — the Python runtime,
``mu/host/js/eval_step.js``, and ``mu/host/js/core/`` (including ``container_factory.js``)
are EXECUTED for the comparison, not modified. No host comparison primitive and no
host-only canonicalization is added to force parity; per North Star semantics, parity
must hold structurally or be surfaced as a finding (it holds: the ordering tag is pure
single-key ``lt``/``eq``/``gt``/``null`` dict structure, so no host int/float string and
no multi-key ordering can diverge across substrates).

Two REAL kernel constraints bound the corpus (documented, not worked around): the Python
``run_mu`` path is meta-circular (~0.6s / domain-step) and inflates dict depth ~3× in
match-normalization, so the imported corpus is deliberately lean (≤ 4-bit operands, 20
pairs incl. swaps). The cross-substrate parity tests drive ``run_mu`` (Python) and
``node`` (JS), so they are ``@pytest.mark.l4_expensive`` + ``@pytest.mark.slow``:
excluded from the fast green gate, run in the nightly l4_expensive lane at 900s, per
``.claude/rules/test-classification.md``. The fast scaffolding checks (no engine) run in
every tier.

Wave: structural-numbers-compare-js-parity-2026-06-18 (L4_ENABLER, target gate G8).
Invariant: ``INV_CROSS_SUBSTRATE_PARITY``.
Precedents: ``test_structural_numbers_add_js_parity.py`` (the ADD cross-substrate parity
gate, PR #1111) and ``test_structural_numbers_compare.py`` (the landed Python COMPARE
projections).
"""
from __future__ import annotations

import json
import subprocess

import pytest

from tests.repo_root import REPO_ROOT
from rcx_pi.selfhost.mu_type import mu_hash, mu_hash_cached

# Single source of truth: reuse the LANDED compare projection table, codec, corpus, and
# Python driver. This gate proves those SAME projections run in the JS substrate
# content-addressed-equal to Python run_mu — so it must validate the landed objects, not
# a re-derived copy. The COMPARE result is an _ord tag, so the result decoder is
# decode_ord (the numeral decode has no role here); the host sign oracle is computed
# inline (a > b) - (a < b) and encoded with encode_ord, mirroring how the ADD gate
# inlines a + b and encodes with encode.
from tests.l4_gates.test_structural_numbers_compare import (
    COMPARE_PROJECTIONS,
    CORPUS,
    decode_ord,
    encode,
    encode_ord,
    run_compare,
)


# =============================================================================
# JS substrate runner — drives the SAME projection table through the real JS
# engine (bootstrap_core.run) via `node`, mirroring the cross-substrate pattern in
# test_structural_numbers_add_js_parity.py. Projections + input states are serialized
# to JSON in Python and rebuilt as TRUSTED Mu containers in JS via the existing
# container_factory (list/record) through trustMu. container_factory.js is
# USE-ONLY (imported + called, never edited): list/record add each constructed
# value to the factory's private trusted-Mu set at call time, which is what JS
# isValidMu requires — that call-time trusting is the "registered" step, not a
# source change.
# =============================================================================

_JS_COMPARE_PARITY_SRC = r"""
const bc = require('./mu/host/js/core/bootstrap_core');
const t = require('./mu/host/js/core/types');
const mc = require('./mu/host/js/core/container_factory');

// Rebuild plain JSON as TRUSTED Mu containers using the existing factory API.
// (JS isValidMu requires muContainers.has(value); list/record add to the trusted
// set at call time. USE-ONLY — container_factory.js is not modified.)
function trustMu(value) {
  if (Array.isArray(value)) return mc.list(value.map(trustMu));
  if (value !== null && typeof value === 'object') {
    return mc.record(Object.keys(value).map(key => [key, trustMu(value[key])]));
  }
  return value;
}

// Run the SAME projection table through bootstrap_core.run for every input state.
function emit(projections, states) {
  const projs = trustMu(projections);
  const out = {};
  for (const [key, state] of Object.entries(states)) {
    const r = bc.run(projs, trustMu(state), 2000);
    out[key] = {
      result: r.result,
      hash: t.muHash(r.result),
      hashCached: t.muHashCached(r.result),
      stalled: r.stalled,
      steps: r.steps,
    };
  }
  console.log(JSON.stringify(out));
}
"""


def _corpus_key(a: int, b: int) -> str:
    """Stable JSON-safe key for a corpus pair (JS object keys are strings)."""
    return f"{a},{b}"


def _host_sign(a: int, b: int) -> int:
    """Host three-way comparison oracle: (a > b) - (a < b) ∈ {-1, 0, +1}.

    The COMPARE analogue of the ADD gate's inline ``a + b`` oracle — the only host
    comparison in this gate (the ordering itself is decided structurally by the engine).
    """
    return (a > b) - (a < b)


def _run_js_compare(projections: list[dict], states: dict) -> dict:
    """Run the projection table through JS bootstrap_core over every state."""
    code = (
        _JS_COMPARE_PARITY_SRC
        + "\nemit("
        + json.dumps(projections)
        + ", "
        + json.dumps(states)
        + ");\n"
    )
    result = subprocess.run(
        ["node", "-e", code],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=300,
    )
    assert result.returncode == 0, f"JS compare parity eval failed:\n{result.stderr}"
    return json.loads(result.stdout.strip())


# Both substrates are costly to drive (Python run_mu is meta-circular; JS is a
# subprocess), so each side is computed once per process and cached.
_JS_CACHE: dict | None = None
_PY_CACHE: dict | None = None


def _js_results() -> dict:
    """JS bootstrap_core compare results, keyed by ``"a,b"`` (computed once)."""
    global _JS_CACHE
    if _JS_CACHE is None:
        states = {
            _corpus_key(a, b): {"_cmp": {"a": encode(a), "b": encode(b)}}
            for (a, b) in CORPUS
        }
        _JS_CACHE = _run_js_compare(COMPARE_PROJECTIONS, states)
    return _JS_CACHE


def _py_results() -> dict:
    """Python run_mu compare results, keyed by ``(a, b)`` (computed once)."""
    global _PY_CACHE
    if _PY_CACHE is None:
        cache: dict = {}
        for (a, b) in CORPUS:
            result, steps, stalled = run_compare(a, b)
            cache[(a, b)] = {"result": result, "steps": steps, "stalled": stalled}
        _PY_CACHE = cache
    return _PY_CACHE


# =============================================================================
# Fast scaffolding (no engine): the source of truth is the landed table and the JS
# runner drives the REAL substrate. These run in every tier (not slow).
# =============================================================================

class TestParityScaffolding:
    """Cheap drift guards: shared landed source of truth + real-substrate wiring."""

    def test_uses_landed_compare_projection_table(self):
        """The table under test is the landed 13-projection compare table."""
        # 13 = 4 dispatch + 9 compare_cont (3×3 LSB-form table).
        assert len(COMPARE_PROJECTIONS) == 13
        assert all(set(proj) == {"pattern", "body"} for proj in COMPARE_PROJECTIONS)

    def test_uses_landed_corpus(self):
        """The corpus is the landed lean compare corpus: 20 pairs, ≤ 4-bit operands,
        covering all three verdicts (2 EQ incl. the mandatory 0==0, 9 GT, 9 LT swaps)."""
        assert len(CORPUS) == 20
        assert (0, 0) in CORPUS  # mandatory zero equality
        signs = [_host_sign(a, b) for (a, b) in CORPUS]
        assert signs.count(0) == 2, "corpus must have exactly 2 EQ pairs (0==0 and 5==5)"
        assert signs.count(1) == 9, "corpus must have exactly 9 GT pairs"
        assert signs.count(-1) == 9, "corpus must have exactly 9 LT pairs (the GT swaps)"

    def test_js_runner_drives_real_substrate(self):
        """The parity runner uses the REAL JS engine + factory, not a reimpl."""
        assert "core/bootstrap_core" in _JS_COMPARE_PARITY_SRC
        assert "core/container_factory" in _JS_COMPARE_PARITY_SRC
        assert "core/types" in _JS_COMPARE_PARITY_SRC
        assert "bc.run(" in _JS_COMPARE_PARITY_SRC


# =============================================================================
# Governing assertion (INV_CROSS_SUBSTRATE_PARITY): the SAME landed COMPARE projections
# run through Python run_mu and JS bootstrap_core produce content-addressed-equal
# verdicts, both decoding to the host three-way ordering (a > b) - (a < b).
# =============================================================================

@pytest.mark.l4_expensive
@pytest.mark.slow
class TestStructuralCompareCrossSubstrateParity:
    """structural_compare via Python run_mu  ≡  structural_compare via JS bootstrap_core."""

    def test_content_hash_parity(self):
        """GOVERNING: muHashCached(JS run) == mu_hash_cached(Python run_mu),
        byte-identical, for every corpus case (and equal to the encode_ord(sign) oracle).

        This is the L3 cross-substrate parity claim for the ordering op: two independent
        engines, driven by the same projection table, converge to the same canonical
        ordering tag and therefore the same content address.
        """
        js = _js_results()
        py = _py_results()
        for (a, b) in CORPUS:
            py_result = py[(a, b)]["result"]
            js_entry = js[_corpus_key(a, b)]
            py_hash = mu_hash_cached(py_result)
            js_hash = js_entry["hashCached"]
            assert py_hash == js_hash, (
                f"cross-substrate content-hash divergence for compare({a}, {b}): "
                f"python run_mu={py_hash} js bootstrap_core={js_hash}"
            )
            oracle = mu_hash_cached(encode_ord(_host_sign(a, b)))
            assert py_hash == oracle, (
                f"compare verdict for ({a}, {b}) diverged from encode_ord(sign) oracle "
                f"(both substrates): {py_hash} != {oracle}"
            )

    def test_results_are_structurally_identical(self):
        """The two substrate results are the SAME canonical ordering tag (structural ==).

        Supporting: hash parity already implies this (the content hash is injective over
        canonical tags), but assert it directly.
        """
        js = _js_results()
        py = _py_results()
        for (a, b) in CORPUS:
            py_result = py[(a, b)]["result"]
            js_result = js[_corpus_key(a, b)]["result"]
            assert py_result == js_result, (
                f"structural divergence for compare({a}, {b}): "
                f"python={py_result} js={js_result}"
            )

    def test_both_engines_decode_to_host_ordering(self):
        """SUPPORTING: both substrate results decode to the host three-way sign."""
        js = _js_results()
        py = _py_results()
        for (a, b) in CORPUS:
            sign = _host_sign(a, b)
            py_dec = decode_ord(py[(a, b)]["result"])
            js_dec = decode_ord(js[_corpus_key(a, b)]["result"])
            assert py_dec == sign, (
                f"python run_mu compare for ({a}, {b}) decoded to {py_dec}, not {sign}"
            )
            assert js_dec == sign, (
                f"js bootstrap_core compare for ({a}, {b}) decoded to {js_dec}, not {sign}"
            )

    def test_both_engines_reach_stall_fixpoint(self):
        """Both engines converged to the {"_ord": ...} fixpoint (not max_steps), and
        neither result is still an unprocessed _cmp/_cc state."""
        js = _js_results()
        py = _py_results()
        for (a, b) in CORPUS:
            py_entry = py[(a, b)]
            js_entry = js[_corpus_key(a, b)]
            assert py_entry["stalled"] is True, (
                f"python run_mu did not stall for compare({a}, {b})"
            )
            assert js_entry["stalled"] is True, (
                f"js bootstrap_core did not stall for compare({a}, {b})"
            )
            for label, result in (("python", py_entry["result"]),
                                  ("js", js_entry["result"])):
                assert "_ord" in result and len(result) == 1, (
                    f"{label} result for compare({a}, {b}) is not an _ord tag wrapper: {result}"
                )

    def test_js_self_coherence(self):
        """JS muHash and muHashCached agree (no JS-internal cache divergence)."""
        js = _js_results()
        for (a, b) in CORPUS:
            entry = js[_corpus_key(a, b)]
            assert entry["hash"] == entry["hashCached"], (
                f"JS muHash != muHashCached for compare({a}, {b})"
            )

    def test_python_self_coherence(self):
        """Python mu_hash and mu_hash_cached agree for each run_mu result."""
        py = _py_results()
        for (a, b) in CORPUS:
            result = py[(a, b)]["result"]
            assert mu_hash(result) == mu_hash_cached(result), (
                f"Python mu_hash != mu_hash_cached for compare({a}, {b})"
            )
