"""L4 gate: StructuralNumbers exact-rational reduction cross-substrate parity.

Stage 3 follow-up for ``mu/docs/core/StructuralNumbers.v0.md``. The Python-only
rational gate (``test_structural_numbers_rationals.py``) proved that an exact
rational normalizer ``{"_rat": {"num", "den"}} -> {"num": Z, "den": positive}``
is expressible as test-local Mu projections. Every other StructuralNumbers
operation (add, compare, codec, multiply, subtract, gcd) already carries a
``test_structural_numbers_<op>_js_parity.py`` proving the landed Mu projection
table yields BYTE-IDENTICAL results in Python and JS (``bootstrap_core`` via
node); rationals was the only operation without it. This gate closes that gap.

Deliberate, code-grounded deviation from the gcd parity template
(``test_structural_numbers_gcd_js_parity.py``): the Python driver here is
``run_projections`` over ``RATIONAL_PROJECTIONS``, NOT ``run_mu``. The gcd
template uses ``run_mu`` because gcd does not blow up under the meta-kernel;
rationals COMPOSE the already-landed GCD rows, where ``run_mu`` is the documented
meta-kernel blowup path (see ``run_rational_reduce``'s inline rationale: "this
wrapper uses the repo's test stepper to avoid meta-kernel blowup on already-landed
GCD rows"). ``run_projections`` (Python direct root-rewriting) is in fact the
exact analog of the JS ``bootstrap_core.run`` (JS direct root-rewriting): both
do one root rewrite per step, so the cross-substrate claim is unweakened -- the
SAME landed table evaluated to fixpoint on each substrate yields byte-identical
``muHashCached`` and ``decode == expected``.

What this gate proves: ``RATIONAL_PROJECTIONS`` *fixpoint* parity across
substrates. What it does NOT additionally assert: ``run_mu`` meta-kernel
evaluation of the rational reduction (the landed quotient/exact-division subcases
exercise ``run_mu`` separately). The JS side never used ``run_mu``; confining the
Python driver to ``run_projections`` does not weaken the cross-substrate claim.

Scope: gate-only and additive. The JS runner rebuilds JSON as trusted Mu
containers through the existing ``container_factory`` API, then calls
``bootstrap_core.run``. No runtime, substrate, seed, registry, JS core, or
production semantic surface is modified or extended.

Wave: structural-numbers-rationals-js-parity-2026-06-21b (L4_ENABLER, gate G8).
Invariant: ``INV_CROSS_SUBSTRATE_PARITY``.
"""
from __future__ import annotations

import json
import math
import re
import subprocess

import pytest

from rcx_pi.selfhost.mu_type import mu_hash, mu_hash_cached
from tests.l4_gates.test_structural_numbers_foundation import encode, encode_positive
from tests.l4_gates.test_structural_numbers_rationals import (
    ONE_POS,
    RATIONAL_ENGINE_CORPUS,
    RATIONAL_MAX_STEPS,
    RATIONAL_PROJECTIONS,
    ZERO_N,
    _decode_rational,
    _oracle_rational,
    run_rational_reduce,
)
from tests.repo_root import REPO_ROOT


_JS_MAX_RUN_STEPS = 10000


_JS_RATIONAL_PARITY_SRC = r"""
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


# Internal work-slot keys enumerated from RATIONAL_PROJECTIONS (every
# underscore-prefixed marker that appears anywhere in a pattern or body), MINUS
# ``_num`` -- the legitimate Z/N codec wrapper that is present inside the ``num``
# field of the clean ``{"num", "den"}`` reduced result. The presence of ANY of
# these in a result tree means the projection table did NOT run to fixpoint (an
# in-progress quotient/gcd/compare/subtract/add work-slot survived). This is the
# rationals analog of the GCD forbidden set;
# ``test_forbidden_set_enumerated_from_landed_table`` re-derives it from the table
# so it cannot silently drift.
_FORBIDDEN_STATE_KEYS = frozenset({
    "_add",
    "_bits",
    "_borrow",
    "_cc",
    "_cmp",
    "_fold",
    "_gcd",
    "_gcd_cmp",
    "_gcd_sub",
    "_ord",
    "_quot",
    "_quot_add",
    "_quot_cmp",
    "_quot_loop",
    "_quot_non_exact",
    "_quot_sub",
    "_rat",
    "_rat_gcd",
    "_rat_quot",
    "_sub",
    "_sub_cmp",
    "_subfold",
})


def _corpus_key(num: int, den: int) -> str:
    """Stable JSON-safe key for a corpus (num, den) pair."""
    return f"{num},{den}"


def _enumerate_rational_state_keys() -> set[str]:
    """Every underscore-prefixed key appearing in RATIONAL_PROJECTIONS."""
    keys: set[str] = set()

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                if isinstance(key, str) and key.startswith("_"):
                    keys.add(key)
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    for proj in RATIONAL_PROJECTIONS:
        walk(proj["pattern"])
        walk(proj["body"])
    return keys


def _contains_state_key(value, state_keys) -> bool:
    """True if any forbidden work-slot key appears anywhere in the result tree."""
    if isinstance(value, dict):
        if any(key in state_keys for key in value):
            return True
        return any(_contains_state_key(child, state_keys) for child in value.values())
    return False


def _expected_reduced_pair(num: int, den: int) -> tuple[int, int]:
    """Independent host oracle for the reduced (num, den) pair."""
    assert den > 0
    if num == 0:
        return 0, 1
    gcd_value = math.gcd(abs(num), den)
    return num // gcd_value, den // gcd_value


def _run_js_rational(projections: list, states: dict) -> dict:
    """Run the rational projection table through JS bootstrap_core."""
    code = (
        _JS_RATIONAL_PARITY_SRC
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
    assert result.returncode == 0, f"JS rational parity eval failed:\n{result.stderr}"
    return json.loads(result.stdout.strip())


_JS_CACHE: dict | None = None
_PY_CACHE: dict | None = None


def _js_results() -> dict:
    """JS bootstrap_core rational results, keyed by ``"num,den"``."""
    global _JS_CACHE
    if _JS_CACHE is None:
        states = {
            _corpus_key(num, den): {
                "_rat": {"num": encode(num), "den": encode_positive(den)}
            }
            for (num, den) in RATIONAL_ENGINE_CORPUS
        }
        _JS_CACHE = _run_js_rational(RATIONAL_PROJECTIONS, states)
    return _JS_CACHE


def _py_results() -> dict:
    """Python run_projections rational results, keyed by ``(num, den)``."""
    global _PY_CACHE
    if _PY_CACHE is None:
        cache: dict = {}
        for (num, den) in RATIONAL_ENGINE_CORPUS:
            # SPEED_OK: run_rational_reduce wraps the bounded run_projections stepper
            # (not run_mu); the only callers are slow+l4_expensive tests.
            result, steps, stalled = run_rational_reduce(num, den)
            cache[(num, den)] = {"result": result, "steps": steps, "stalled": stalled}
        _PY_CACHE = cache
    return _PY_CACHE


class TestParityScaffolding:
    """Cheap drift guards: landed rational table/corpus plus real JS runner wiring."""

    def test_uses_landed_rational_projection_table(self):
        assert len(RATIONAL_PROJECTIONS) == 120
        assert all(set(proj) == {"pattern", "body"} for proj in RATIONAL_PROJECTIONS)

    def test_uses_landed_exact_reducible_corpus(self):
        assert RATIONAL_ENGINE_CORPUS == [(0, 2), (1, 2), (2, 2), (-2, 4), (2, 1)]
        # Exact-reducible family (each reduces to the clean {"num","den"} fixpoint),
        # NOT the deliberately stalling raw _quot / _quot_non_exact control cases.
        # Bound by MAX_STRUCTURAL_QUOTIENT == 6 so the corpus converges under both
        # RATIONAL_MAX_STEPS (Python) and the JS MAX_RUN_STEPS cap.
        assert all(den > 0 for _num, den in RATIONAL_ENGINE_CORPUS)
        assert all(abs(num) <= 6 and den <= 6 for num, den in RATIONAL_ENGINE_CORPUS)
        # Documented envelope shape: zero numerator canonicalizes the denominator.
        assert _oracle_rational(0, 2) == {"num": ZERO_N, "den": ONE_POS}

    def test_forbidden_set_enumerated_from_landed_table(self):
        enumerated = _enumerate_rational_state_keys()
        # _num is the legitimate Z/N codec wrapper carried inside the clean result;
        # every OTHER underscore key in the table is an in-progress work-slot.
        assert "_num" in enumerated
        assert _FORBIDDEN_STATE_KEYS == enumerated - {"_num"}
        assert "_num" not in _FORBIDDEN_STATE_KEYS
        assert {"_rat", "_gcd", "_quot"} <= _FORBIDDEN_STATE_KEYS

    def test_js_runner_drives_real_substrate(self):
        assert "core/bootstrap_core" in _JS_RATIONAL_PARITY_SRC
        assert "core/container_factory" in _JS_RATIONAL_PARITY_SRC
        assert "core/types" in _JS_RATIONAL_PARITY_SRC
        assert "bc.run(" in _JS_RATIONAL_PARITY_SRC

    def test_python_driver_is_run_projections_not_run_mu(self):
        # The deliberate, code-grounded deviation from the gcd template: rationals
        # compose the landed GCD rows where run_mu is the documented blowup path.
        # Guard the namespace so no run_mu call is reintroduced over the table.
        assert "run_rational_reduce" in globals()
        assert "run_mu" not in globals()

    def test_js_step_budget_is_honored_not_clamped(self):
        m = re.search(r"bc\.run\(projs, trustMu\(state\), (\d+)\)", _JS_RATIONAL_PARITY_SRC)
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
class TestStructuralRationalCrossSubstrateParity:
    """Rational reduction via Python run_projections equals JS bootstrap_core."""

    def test_content_hash_parity(self):
        js = _js_results()
        py = _py_results()
        for (num, den) in RATIONAL_ENGINE_CORPUS:
            py_result = py[(num, den)]["result"]
            js_entry = js[_corpus_key(num, den)]
            py_hash = mu_hash_cached(py_result)
            js_hash = js_entry["hashCached"]
            assert py_hash == js_hash, (
                f"cross-substrate content-hash divergence for rational {num}/{den}: "
                f"python run_projections={py_hash} js bootstrap_core={js_hash}"
            )
            oracle = mu_hash_cached(_oracle_rational(num, den))
            assert py_hash == oracle, (
                f"rational result for {num}/{den} diverged from the canonical envelope "
                f"oracle (both substrates): {py_hash} != {oracle}"
            )

    def test_results_are_structurally_identical(self):
        js = _js_results()
        py = _py_results()
        for (num, den) in RATIONAL_ENGINE_CORPUS:
            py_result = py[(num, den)]["result"]
            js_result = js[_corpus_key(num, den)]["result"]
            assert py_result == js_result, (
                f"structural divergence for rational {num}/{den}: "
                f"python={py_result} js={js_result}"
            )
            assert py_result == _oracle_rational(num, den)

    def test_both_engines_decode_to_expected_rational(self):
        js = _js_results()
        py = _py_results()
        for (num, den) in RATIONAL_ENGINE_CORPUS:
            expected = _expected_reduced_pair(num, den)
            py_dec = _decode_rational(py[(num, den)]["result"])
            js_dec = _decode_rational(js[_corpus_key(num, den)]["result"])
            assert py_dec == expected, (
                f"python run_projections rational for {num}/{den} decoded to {py_dec}, not {expected}"
            )
            assert js_dec == expected, (
                f"js bootstrap_core rational for {num}/{den} decoded to {js_dec}, not {expected}"
            )

    def test_both_engines_reach_stall_fixpoint(self):
        js = _js_results()
        py = _py_results()
        for (num, den) in RATIONAL_ENGINE_CORPUS:
            py_entry = py[(num, den)]
            js_entry = js[_corpus_key(num, den)]
            # JS bootstrap_core.run returns stalled:true ONLY on a genuine fixpoint
            # (nextHash === currentHash); stalled:false signals maxSteps exhaustion.
            assert js_entry["stalled"] is True, (
                f"js bootstrap_core did not reach a fixpoint for rational {num}/{den} "
                f"(steps={js_entry['steps']}; stalled=False means maxSteps exhaustion)"
            )
            # Python run_projections returns is_stall=True for a genuine stall AND for
            # budget exhaustion (steps == max_steps); only steps < max proves a
            # genuine fixpoint rather than exhaustion.
            assert py_entry["stalled"] is True, (
                f"python run_projections did not stall for rational {num}/{den}"
            )
            assert py_entry["steps"] < RATIONAL_MAX_STEPS, (
                f"python run_projections exhausted its {RATIONAL_MAX_STEPS}-step budget for "
                f"rational {num}/{den} (steps={py_entry['steps']}) rather than reaching a fixpoint"
            )
            for label, result in (("python", py_entry["result"]), ("js", js_entry["result"])):
                assert set(result) == {"num", "den"}, (
                    f"{label} result for rational {num}/{den} is not the clean "
                    f"{{'num','den'}} reduced wrapper: {sorted(result)}"
                )
                assert not _contains_state_key(result, _FORBIDDEN_STATE_KEYS), (
                    f"{label} result for rational {num}/{den} still carries an "
                    f"in-progress work-slot key: {result}"
                )

    def test_js_self_coherence(self):
        js = _js_results()
        for (num, den) in RATIONAL_ENGINE_CORPUS:
            entry = js[_corpus_key(num, den)]
            assert entry["hash"] == entry["hashCached"], (
                f"JS muHash != muHashCached for rational {num}/{den}"
            )

    def test_python_self_coherence(self):
        py = _py_results()
        for (num, den) in RATIONAL_ENGINE_CORPUS:
            result = py[(num, den)]["result"]
            assert mu_hash(result) == mu_hash_cached(result), (
                f"Python mu_hash != mu_hash_cached for rational {num}/{den}"
            )
