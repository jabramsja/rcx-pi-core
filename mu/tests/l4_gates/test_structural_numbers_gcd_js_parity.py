"""L4 gate: StructuralNumbers integer GCD cross-substrate parity.

Stage 3 follow-up for ``mu/docs/core/StructuralNumbers.v0.md``. The Python-only
GCD gate proved that the Euclidean GCD machine is expressible as test-local Mu
projections driven by the real Python ``run_mu`` path. This gate adds the JS
substrate proof: the same landed GCD projection table, over the same bounded GCD
corpus, converges to content-addressed-equal results through
``mu/host/js/core/bootstrap_core.js``.

Scope: gate-only and additive. The JS runner rebuilds JSON as trusted Mu
containers through the existing ``container_factory`` API, then calls
``bootstrap_core.run``. No runtime, substrate, seed, registry, JS core, or
production semantic surface is modified or extended.

Wave: structural-numbers-gcd-js-parity-2026-06-19 (L4_ENABLER, target gate G8).
Invariant: ``INV_CROSS_SUBSTRATE_PARITY``.
"""
from __future__ import annotations

import json
import math
import re
import subprocess

import pytest

from rcx_pi.selfhost.mu_type import mu_hash, mu_hash_cached
from tests.l4_gates.test_structural_numbers_foundation import decode, encode
from tests.l4_gates.test_structural_numbers_gcd import (
    CORPUS,
    GCD_PROJECTIONS,
    run_gcd,
)
from tests.repo_root import REPO_ROOT


_JS_MAX_RUN_STEPS = 10000


_JS_GCD_PARITY_SRC = r"""
const bc = require('./mu/host/js/core/bootstrap_core');
const t = require('./mu/host/js/core/types');
const mc = require('./mu/host/js/core/container_factory');

// Rebuild plain JSON as TRUSTED Mu containers using the existing factory API.
// container_factory.js is use-only: list/record register each compound container
// in the trusted Mu set consumed by JS isValidMu.
function trustMu(value) {
  if (Array.isArray(value)) return mc.list(value.map(trustMu));
  if (value !== null && typeof value === 'object') {
    return mc.record(Object.keys(value).map(key => [key, trustMu(value[key])]));
  }
  return value;
}

function emit(projections, states) {
  const projs = trustMu(projections);
  const out = {};
  for (const [key, state] of Object.entries(states)) {
    const r = bc.run(projs, trustMu(state), 10000);
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
    """Stable JSON-safe key for a corpus pair."""
    return f"{a},{b}"


def _run_js_gcd(projections: list[dict], states: dict) -> dict:
    """Run the GCD projection table through JS bootstrap_core."""
    code = (
        _JS_GCD_PARITY_SRC
        + "\nemit("
        + json.dumps(projections)
        + ", "
        + json.dumps(states)
        + ");\n"
    )
    # SPEED_OK: node subprocess is bounded by pytest slow+l4_expensive plus timeout.
    result = subprocess.run(
        ["node", "-e", code],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=300,
    )
    assert result.returncode == 0, f"JS GCD parity eval failed:\n{result.stderr}"
    return json.loads(result.stdout.strip())


_JS_CACHE: dict | None = None
_PY_CACHE: dict | None = None


def _js_results() -> dict:
    """JS bootstrap_core GCD results, keyed by ``"a,b"``."""
    global _JS_CACHE
    if _JS_CACHE is None:
        states = {
            _corpus_key(a, b): {"_gcd": {"a": encode(a), "b": encode(b)}}
            for (a, b) in CORPUS
        }
        _JS_CACHE = _run_js_gcd(GCD_PROJECTIONS, states)
    return _JS_CACHE


def _py_results() -> dict:
    """Python run_mu GCD results, keyed by ``(a, b)``."""
    global _PY_CACHE
    if _PY_CACHE is None:
        cache: dict = {}
        for (a, b) in CORPUS:
            # SPEED_OK: run_gcd wraps run_mu; the only callers are slow+l4_expensive tests.
            result, steps, stalled = run_gcd(a, b)
            cache[(a, b)] = {"result": result, "steps": steps, "stalled": stalled}
        _PY_CACHE = cache
    return _PY_CACHE


class TestParityScaffolding:
    """Cheap drift guards: landed GCD table/corpus plus real JS runner wiring."""

    def test_uses_landed_gcd_projection_table(self):
        assert len(GCD_PROJECTIONS) == 80
        assert all(set(proj) == {"pattern", "body"} for proj in GCD_PROJECTIONS)

    def test_uses_landed_bounded_corpus(self):
        assert CORPUS == [(0, 0), (5, 0), (0, 4), (4, 2), (6, 4), (6, 3)]
        assert all(a >= 0 and b >= 0 and a <= 6 and b <= 6 for a, b in CORPUS)

    def test_js_runner_drives_real_substrate(self):
        assert "core/bootstrap_core" in _JS_GCD_PARITY_SRC
        assert "core/container_factory" in _JS_GCD_PARITY_SRC
        assert "core/types" in _JS_GCD_PARITY_SRC
        assert "bc.run(" in _JS_GCD_PARITY_SRC

    def test_js_step_budget_is_honored_not_clamped(self):
        m = re.search(r"bc\.run\(projs, trustMu\(state\), (\d+)\)", _JS_GCD_PARITY_SRC)
        assert m, "JS driver must call bc.run(projs, trustMu(state), <budget>)"
        js_budget = int(m.group(1))
        assert js_budget == _JS_MAX_RUN_STEPS

        core_src = (REPO_ROOT / "mu" / "host" / "js" / "core" / "bootstrap_core.js").read_text()
        cap_m = re.search(r"const MAX_RUN_STEPS\s*=\s*(\d+)", core_src)
        assert cap_m, "could not locate `const MAX_RUN_STEPS = <n>` in bootstrap_core.js"
        substrate_cap = int(cap_m.group(1))
        assert js_budget <= substrate_cap
        assert _JS_MAX_RUN_STEPS == substrate_cap


@pytest.mark.l4_expensive
@pytest.mark.slow
class TestStructuralGcdCrossSubstrateParity:
    """structural_gcd via Python run_mu is equivalent to JS bootstrap_core."""

    def test_content_hash_parity(self):
        js = _js_results()
        py = _py_results()
        for (a, b) in CORPUS:
            py_result = py[(a, b)]["result"]
            js_entry = js[_corpus_key(a, b)]
            py_hash = mu_hash_cached(py_result)
            js_hash = js_entry["hashCached"]
            assert py_hash == js_hash, (
                f"cross-substrate content-hash divergence for gcd({a}, {b}): "
                f"python run_mu={py_hash} js bootstrap_core={js_hash}"
            )
            oracle = mu_hash_cached(encode(math.gcd(a, b)))
            assert py_hash == oracle, (
                f"GCD result for ({a}, {b}) diverged from encode(math.gcd) oracle "
                f"(both substrates): {py_hash} != {oracle}"
            )

    def test_results_are_structurally_identical(self):
        js = _js_results()
        py = _py_results()
        for (a, b) in CORPUS:
            py_result = py[(a, b)]["result"]
            js_result = js[_corpus_key(a, b)]["result"]
            assert py_result == js_result, (
                f"structural divergence for gcd({a}, {b}): "
                f"python={py_result} js={js_result}"
            )

    def test_both_engines_decode_to_host_gcd(self):
        js = _js_results()
        py = _py_results()
        for (a, b) in CORPUS:
            expected = math.gcd(a, b)
            py_dec = decode(py[(a, b)]["result"])
            js_dec = decode(js[_corpus_key(a, b)]["result"])
            assert py_dec == expected, (
                f"python run_mu gcd for ({a}, {b}) decoded to {py_dec}, not {expected}"
            )
            assert js_dec == expected, (
                f"js bootstrap_core gcd for ({a}, {b}) decoded to {js_dec}, not {expected}"
            )

    def test_both_engines_reach_stall_fixpoint(self):
        js = _js_results()
        py = _py_results()
        forbidden = (
            "_gcd",
            "_gcd_cmp",
            "_gcd_sub",
            "_cmp",
            "_cc",
            "_sub",
            "_sub_cmp",
            "_borrow",
            "_subfold",
        )
        for (a, b) in CORPUS:
            py_entry = py[(a, b)]
            js_entry = js[_corpus_key(a, b)]
            assert py_entry["stalled"] is True, (
                f"python run_mu did not stall for gcd({a}, {b})"
            )
            assert js_entry["stalled"] is True, (
                f"js bootstrap_core did not stall for gcd({a}, {b})"
            )
            for label, result in (("python", py_entry["result"]), ("js", js_entry["result"])):
                assert "_num" in result and len(result) == 1, (
                    f"{label} result for gcd({a}, {b}) is not an N numeral wrapper: {result}"
                )
                for state_key in forbidden:
                    assert state_key not in result, (
                        f"{label} result for gcd({a}, {b}) is still an unprocessed "
                        f"{state_key} state"
                    )

    def test_js_self_coherence(self):
        js = _js_results()
        for (a, b) in CORPUS:
            entry = js[_corpus_key(a, b)]
            assert entry["hash"] == entry["hashCached"], (
                f"JS muHash != muHashCached for gcd({a}, {b})"
            )

    def test_python_self_coherence(self):
        py = _py_results()
        for (a, b) in CORPUS:
            result = py[(a, b)]["result"]
            assert mu_hash(result) == mu_hash_cached(result), (
                f"Python mu_hash != mu_hash_cached for gcd({a}, {b})"
            )
