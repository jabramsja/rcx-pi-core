"""L4 gate: StructuralNumbers binary ADD — cross-substrate L3 parity (Python ↔ JS).

Stage 2a-ii gate for ``mu/docs/core/StructuralNumbers.v0.md``. The Python-only
slice (``test_structural_numbers_add.py``) proved binary ADD is expressible as RCX
projections driven by the real Python kernel (``run_mu``). This gate adds the
**mandatory L3 parity** obligation for the first arithmetic op
(``INV_CROSS_SUBSTRATE_PARITY``): the **same landed ADD projection table** run
through the **JS substrate** (``mu/host/js/core/bootstrap_core.js`` ``run`` via
``node``) yields a result that is **content-addressed-equal** to the Python
``run_mu`` result —

    muHashCached(js_bootstrap_core_run(add)) == mu_hash_cached(python_run_mu(add))

byte-identical — and both decode to host ``a + b``. Content-addressed equality is
the design's free equality (``StructuralNumbers.v0.md`` §3.2): if the two engines
converge to the same canonical numeral, their content hashes are byte-identical.

Single source of truth: the projection table, codec, and corpus are **imported**
from ``test_structural_numbers_add`` rather than re-derived, so this gate validates
the **landed** projections (not a copy) and guarantees the *same* table is fed to
both substrates. The table is serialized to JSON in Python and rebuilt in JS as
**trusted** Mu containers via the existing ``container_factory`` (``list`` /
``record``) through the ``trustMu`` helper — JS ``isValidMu`` requires
``muContainers.has(value)``, and the factory adds each value to its private trusted
set at call time (the "registered" step). ``container_factory.js`` is USE-ONLY:
imported and called, never modified.

Scope: GATE-ONLY, additive. No runtime/substrate/seed change — the Python runtime,
``mu/host/js/eval_step.js``, and ``mu/host/js/core/`` (including
``container_factory.js``) are EXECUTED for the comparison, not modified. No
host-only canonicalization is added to force parity; per North Star semantics,
parity must hold structurally or be surfaced as a finding (it holds: the numeral is
pure single-key ``xI``/``xO``/``xH``/``null`` dict structure, so no host int/float
string and no multi-key ordering can diverge across substrates).

Two REAL kernel constraints bound the corpus (documented, not worked around): the
Python ``run_mu`` path is meta-circular (~0.6s / domain-step) and inflates dict
depth ~3× in match-normalization, so the corpus is deliberately lean (≤ 8-bit
operands, 10 cases). The cross-substrate parity tests drive ``run_mu`` (Python) and
``node`` (JS), so they are ``@pytest.mark.l4_expensive`` + ``@pytest.mark.slow``:
excluded from the fast green gate, run in the nightly l4_expensive lane at 900s, per
``.claude/rules/test-classification.md``. The fast scaffolding checks (no engine)
run in every tier.

Wave: structural-numbers-add-js-parity-2026-06-18 (L4_ENABLER, target gate G8).
Invariant: ``INV_CROSS_SUBSTRATE_PARITY``.
Precedents: ``test_structural_numbers_foundation.py`` (numeral cross-substrate hash
parity) and ``test_structural_numbers_add.py`` (the landed Python ADD projections).
"""
from __future__ import annotations

import json
import subprocess

import pytest

from tests.repo_root import REPO_ROOT
from rcx_pi.selfhost.mu_type import mu_hash, mu_hash_cached

# Single source of truth: reuse the LANDED add projection table, codec, corpus, and
# Python driver. This gate proves those SAME projections run in the JS substrate
# content-addressed-equal to Python run_mu — so it must validate the landed objects,
# not a re-derived copy.
from tests.l4_gates.test_structural_numbers_add import (
    ADD_PROJECTIONS,
    CORPUS,
    decode,
    encode,
    run_add,
)


# =============================================================================
# JS substrate runner — drives the SAME projection table through the real JS
# engine (bootstrap_core.run) via `node`, mirroring the cross-substrate pattern in
# test_structural_numbers_foundation.py. Projections + input states are serialized
# to JSON in Python and rebuilt as TRUSTED Mu containers in JS via the existing
# container_factory (list/record) through trustMu. container_factory.js is
# USE-ONLY (imported + called, never edited): list/record add each constructed
# value to the factory's private trusted-Mu set at call time, which is what JS
# isValidMu requires — that call-time trusting is the "registered" step, not a
# source change.
# =============================================================================

_JS_ADD_PARITY_SRC = r"""
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


def _run_js_add(projections: list[dict], states: dict) -> dict:
    """Run the projection table through JS bootstrap_core over every state."""
    code = (
        _JS_ADD_PARITY_SRC
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
    assert result.returncode == 0, f"JS add parity eval failed:\n{result.stderr}"
    return json.loads(result.stdout.strip())


# Both substrates are costly to drive (Python run_mu is meta-circular; JS is a
# subprocess), so each side is computed once per process and cached.
_JS_CACHE: dict | None = None
_PY_CACHE: dict | None = None


def _js_results() -> dict:
    """JS bootstrap_core add results, keyed by ``"a,b"`` (computed once)."""
    global _JS_CACHE
    if _JS_CACHE is None:
        states = {
            _corpus_key(a, b): {"_add": {"a": encode(a), "b": encode(b)}}
            for (a, b) in CORPUS
        }
        _JS_CACHE = _run_js_add(ADD_PROJECTIONS, states)
    return _JS_CACHE


def _py_results() -> dict:
    """Python run_mu add results, keyed by ``(a, b)`` (computed once)."""
    global _PY_CACHE
    if _PY_CACHE is None:
        cache: dict = {}
        for (a, b) in CORPUS:
            result, steps, stalled = run_add(a, b)
            cache[(a, b)] = {"result": result, "steps": steps, "stalled": stalled}
        _PY_CACHE = cache
    return _PY_CACHE


# =============================================================================
# Fast scaffolding (no engine): the source of truth is the landed table and the JS
# runner drives the REAL substrate. These run in every tier (not slow).
# =============================================================================

class TestParityScaffolding:
    """Cheap drift guards: shared landed source of truth + real-substrate wiring."""

    def test_uses_landed_add_projection_table(self):
        """The table under test is the landed 39-projection add table."""
        # 39 = 3 dispatch + 32 full-adder (incl. terminate) + 4 fold.
        assert len(ADD_PROJECTIONS) == 39
        assert all(set(proj) == {"pattern", "body"} for proj in ADD_PROJECTIONS)

    def test_uses_landed_corpus(self):
        """The corpus is the landed lean add corpus (covers the carry classes)."""
        assert len(CORPUS) == 10
        assert (0, 0) in CORPUS
        assert (7, 0) in CORPUS and (0, 7) in CORPUS
        assert (255, 1) in CORPUS and (255, 255) in CORPUS

    def test_js_runner_drives_real_substrate(self):
        """The parity runner uses the REAL JS engine + factory, not a reimpl."""
        assert "core/bootstrap_core" in _JS_ADD_PARITY_SRC
        assert "core/container_factory" in _JS_ADD_PARITY_SRC
        assert "core/types" in _JS_ADD_PARITY_SRC
        assert "bc.run(" in _JS_ADD_PARITY_SRC


# =============================================================================
# Governing assertion (INV_CROSS_SUBSTRATE_PARITY): the SAME landed ADD projections
# run through Python run_mu and JS bootstrap_core produce content-addressed-equal
# results, both decoding to host a + b.
# =============================================================================

@pytest.mark.l4_expensive
@pytest.mark.slow
class TestStructuralAddCrossSubstrateParity:
    """structural_add via Python run_mu  ≡  structural_add via JS bootstrap_core."""

    def test_content_hash_parity(self):
        """GOVERNING: muHashCached(JS run) == mu_hash_cached(Python run_mu),
        byte-identical, for every corpus case (and equal to the encode(a+b) oracle).

        This is the L3 cross-substrate parity claim for the first arithmetic op:
        two independent engines, driven by the same projection table, converge to
        the same canonical numeral and therefore the same content address.
        """
        js = _js_results()
        py = _py_results()
        for (a, b) in CORPUS:
            py_result = py[(a, b)]["result"]
            js_entry = js[_corpus_key(a, b)]
            py_hash = mu_hash_cached(py_result)
            js_hash = js_entry["hashCached"]
            assert py_hash == js_hash, (
                f"cross-substrate content-hash divergence for {a}+{b}: "
                f"python run_mu={py_hash} js bootstrap_core={js_hash}"
            )
            oracle = mu_hash_cached(encode(a + b))
            assert py_hash == oracle, (
                f"add result for {a}+{b} diverged from encode({a + b}) oracle "
                f"(both substrates): {py_hash} != {oracle}"
            )

    def test_results_are_structurally_identical(self):
        """The two substrate results are the SAME canonical numeral (structural ==).

        Supporting: hash parity already implies this (the content hash is injective
        over canonical numerals — see the foundation gate), but assert it directly.
        """
        js = _js_results()
        py = _py_results()
        for (a, b) in CORPUS:
            py_result = py[(a, b)]["result"]
            js_result = js[_corpus_key(a, b)]["result"]
            assert py_result == js_result, (
                f"structural divergence for {a}+{b}: "
                f"python={py_result} js={js_result}"
            )

    def test_both_engines_decode_to_host_sum(self):
        """SUPPORTING: both substrate results decode to host a + b."""
        js = _js_results()
        py = _py_results()
        for (a, b) in CORPUS:
            py_dec = decode(py[(a, b)]["result"])
            js_dec = decode(js[_corpus_key(a, b)]["result"])
            assert py_dec == a + b, (
                f"python run_mu add for {a}+{b} decoded to {py_dec}, not {a + b}"
            )
            assert js_dec == a + b, (
                f"js bootstrap_core add for {a}+{b} decoded to {js_dec}, not {a + b}"
            )

    def test_both_engines_reach_stall_fixpoint(self):
        """Both engines converged to the {"_num": ...} fixpoint (not max_steps), and
        neither result is still an unprocessed _add/_bits/_fold state."""
        js = _js_results()
        py = _py_results()
        for (a, b) in CORPUS:
            py_entry = py[(a, b)]
            js_entry = js[_corpus_key(a, b)]
            assert py_entry["stalled"] is True, (
                f"python run_mu did not stall for {a}+{b}"
            )
            assert js_entry["stalled"] is True, (
                f"js bootstrap_core did not stall for {a}+{b}"
            )
            for label, result in (("python", py_entry["result"]),
                                  ("js", js_entry["result"])):
                assert "_num" in result and len(result) == 1, (
                    f"{label} result for {a}+{b} is not an N numeral wrapper: {result}"
                )

    def test_js_self_coherence(self):
        """JS muHash and muHashCached agree (no JS-internal cache divergence)."""
        js = _js_results()
        for (a, b) in CORPUS:
            entry = js[_corpus_key(a, b)]
            assert entry["hash"] == entry["hashCached"], (
                f"JS muHash != muHashCached for {a}+{b}"
            )

    def test_python_self_coherence(self):
        """Python mu_hash and mu_hash_cached agree for each run_mu result."""
        py = _py_results()
        for (a, b) in CORPUS:
            result = py[(a, b)]["result"]
            assert mu_hash(result) == mu_hash_cached(result), (
                f"Python mu_hash != mu_hash_cached for {a}+{b}"
            )
