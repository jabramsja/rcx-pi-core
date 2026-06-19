"""L4 gate: StructuralNumbers signed integer SUBTRACT — cross-substrate L3 parity (Python ↔ JS).

Stage 3 (the arithmetic tower) wave 3. The Python-only slice
(``test_structural_numbers_subtract.py``, PR #1116) proved signed integer SUBTRACT is
expressible as RCX projections — a **structural-compare sign decision composing the
already-landed binary COMPARE**, plus **binary subtract-with-borrow** on the operand
magnitudes, plus a **leading-zero-stripping fold** — driven by the real Python kernel
(``run_mu``). This gate adds the **mandatory L3 parity** obligation for the op
(``INV_CROSS_SUBSTRATE_PARITY``), mirroring the ADD / COMPARE / CODEC / MULTIPLY parity
gates (``test_structural_numbers_add_js_parity.py`` PR #1111,
``test_structural_numbers_compare_js_parity.py`` PR #1112,
``test_structural_numbers_codec_js_parity.py`` PR #1113,
``test_structural_numbers_multiply_js_parity.py`` PR #1115): the **same landed SUBTRACT
projection table** run through the **JS substrate**
(``mu/host/js/core/bootstrap_core.js`` ``run`` via ``node``) yields a result that is
**content-addressed-equal** to the Python ``run_mu`` result —

    muHashCached(js_bootstrap_core_run(sub)) == mu_hash_cached(python_run_mu(sub))

byte-identical — and both decode to host ``a - b``. Content-addressed equality is the
design's free equality (``StructuralNumbers.v0.md`` §3.2): if the two engines converge
to the same canonical numeral, their content hashes are byte-identical.

The SUBTRACT result is **signed** (unlike the always-non-negative ADD / MULTIPLY
numeral): the **negative (neg) form** ``{"_num": {"neg": p}}`` when ``a < b``, the
**canonical zero** ``{"_num": null}`` when ``a == b``, and the **positive form**
``{"_num": p}`` when ``a > b``. Parity is asserted byte-identical across all three
shapes — including the ``neg`` wrapper, which is itself a single-key node over a positive
chain, so no host int/float string and no multi-key ordering can diverge across
substrates (the same property the ADD / MULTIPLY parity gates and the foundation gate
rely on).

Single source of truth: the projection table, the signed ``Z`` codec, the corpus, and
the Python driver are **imported** from ``test_structural_numbers_subtract`` rather than
re-derived, so this gate validates the **landed** projections (not a copy) and
guarantees the *same* table is fed to both substrates — and, transitively, the *same*
landed binary COMPARE that SUBTRACT lifts into its ``_sub_cmp`` work-slot. The table is
serialized to JSON in Python and rebuilt in JS as **trusted** Mu containers via the
existing ``container_factory`` (``list`` / ``record``) through the ``trustMu`` helper —
JS ``isValidMu`` requires ``muContainers.has(value)``, and the factory adds each value
to its private trusted set at call time (the "registered" step). ``container_factory.js``
is USE-ONLY: imported and called, never modified.

The SUBTRACT result is a numeral, so it is decoded with the landed ``decode`` and oracled
with ``encode`` (exactly as the ADD / MULTIPLY gates do); the host difference ``a - b`` is
computed inline — the only host arithmetic in this gate, exactly as those gates inline
``a + b`` / ``a * b`` — and encoded with the landed ``encode``. The engine performs the
subtraction; the host ``-`` appears only in the test oracle (``mu/tests/`` is outside the
``check_host_semantics_ratchet.py`` scan surface — only ``rcx_pi/selfhost`` and
``mu/host/js`` are scanned — so this test-only oracle is not a host-authority site).

Both substrates are driven with a **non-binding** step budget. The Python
``run_subtract`` driver drives ``run_mu`` with ``max_steps=4000``; the JS
``bootstrap_core.run`` primitive **hard-caps** at ``MAX_RUN_STEPS=10000`` and clamps any
larger request down to it (``mu/host/js/core/bootstrap_core.js``), so the JS runner
drives it at exactly that **honored** cap (``10000``) rather than a nominal larger value
it would silently clamp. These two ceilings differ, but the difference is immaterial to
parity: the lean corpus converges in ``<=`` ~20 domain steps on *both* substrates (max
observed: 20 for ``100-1``; most cases 1–16), so neither ceiling is ever reached and the
resulting fixpoint — and its content hash — is **ceiling-independent**. The comparison
therefore stays apples-to-apples: the same projection table fed to both engines, each
with a budget that dwarfs the actual step count (the landed Python gate and this gate
both assert ``stalled is True``, i.e. the fixpoint is reached before the ceiling).

Scope: GATE-ONLY, additive. No runtime/substrate/seed change — the Python runtime,
``mu/host/js/eval_step.js``, and ``mu/host/js/core/`` (including ``container_factory.js``)
are EXECUTED for the comparison, not modified. No host subtract primitive and no
host-only canonicalization is added to force parity; per North Star semantics, parity
must hold structurally or be surfaced as a finding (it holds: the signed numeral is pure
single-key ``xI``/``xO``/``xH``/``neg``/``null`` dict structure, so no host int/float
string and no multi-key ordering can diverge across substrates).

Two REAL kernel constraints bound the corpus (documented, not worked around): the Python
``run_mu`` path is meta-circular and inflates dict depth ~3× in match-normalization, and
the SUBTRACT state (the lifted COMPARE sub-machine carrying both operands, then the
borrow loop and fold) makes the per-step cost grow with operand size (~1–2s / domain-step).
The imported corpus is therefore deliberately lean (small operands, 8 cases, ~135s
locally for the engine lane). The cross-substrate parity tests drive ``run_mu`` (Python)
and ``node`` (JS), so they are ``@pytest.mark.l4_expensive`` + ``@pytest.mark.slow``:
excluded from the fast green gate, run in the nightly l4_expensive lane at 900s, per
``.claude/rules/test-classification.md``. The fast scaffolding checks (no engine) run in
every tier.

Wave: structural-numbers-subtract-js-parity-2026-06-18 (L4_ENABLER, target gate G8).
Invariant: ``INV_CROSS_SUBSTRATE_PARITY``.
Precedents: ``test_structural_numbers_add_js_parity.py`` (the ADD cross-substrate parity
gate, PR #1111), ``test_structural_numbers_compare_js_parity.py`` (PR #1112),
``test_structural_numbers_codec_js_parity.py`` (PR #1113),
``test_structural_numbers_multiply_js_parity.py`` (PR #1115), and
``test_structural_numbers_subtract.py`` (the landed Python signed SUBTRACT projections,
PR #1116).
"""
from __future__ import annotations

import json
import re
import subprocess

import pytest

from tests.repo_root import REPO_ROOT
from rcx_pi.selfhost.mu_type import mu_hash, mu_hash_cached

# Single source of truth: reuse the LANDED signed-subtract projection table, codec, corpus,
# and Python driver. This gate proves those SAME projections run in the JS substrate
# content-addressed-equal to Python run_mu — so it must validate the landed objects, not a
# re-derived copy. The SUBTRACT result is a signed numeral, so it is decoded with decode and
# oracled with encode (mirroring how the ADD/MULTIPLY gates oracle their result with encode);
# the host difference a - b is computed inline.
from tests.l4_gates.test_structural_numbers_subtract import (
    CORPUS,
    SUB_PROJECTIONS,
    decode,
    encode,
    run_subtract,
)


# JS step budget. bootstrap_core.run hard-caps at MAX_RUN_STEPS (10000) and clamps any
# larger request down to it, so the JS runner drives it at exactly that honored cap (a
# nominal larger value would be silently clamped). The Python run_subtract driver uses
# max_steps=4000; the two ceilings differ but NEITHER binds — the lean corpus converges in
# <=~20 domain steps on both substrates, so the fixpoint is ceiling-independent and the
# comparison stays apples-to-apples on the same table. Mirrors bootstrap_core.js
# MAX_RUN_STEPS; test_js_step_budget_is_honored_not_clamped re-checks it against the live
# substrate so the asserted budget is the one JS actually honors.
_JS_MAX_RUN_STEPS = 10000


# =============================================================================
# JS substrate runner — drives the SAME projection table through the real JS
# engine (bootstrap_core.run) via `node`, mirroring the cross-substrate pattern in
# test_structural_numbers_multiply_js_parity.py. Projections + input states are serialized
# to JSON in Python and rebuilt as TRUSTED Mu containers in JS via the existing
# container_factory (list/record) through trustMu. container_factory.js is
# USE-ONLY (imported + called, never edited): list/record add each constructed
# value to the factory's private trusted-Mu set at call time, which is what JS
# isValidMu requires — that call-time trusting is the "registered" step, not a
# source change. The run budget is bootstrap_core's honored cap (MAX_RUN_STEPS=10000;
# see _JS_MAX_RUN_STEPS) — neither substrate's ceiling binds (corpus converges in <=~20).
# =============================================================================

_JS_SUB_PARITY_SRC = r"""
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
// maxSteps is bootstrap_core's honored cap (MAX_RUN_STEPS = 10000); the corpus converges
// in <=~20 domain steps, far within it, so the ceiling never binds (see _JS_MAX_RUN_STEPS).
// A larger value would be silently clamped to 10000 — so we pass the cap.
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
    """Stable JSON-safe key for a corpus pair (JS object keys are strings)."""
    return f"{a},{b}"


def _run_js_sub(projections: list[dict], states: dict) -> dict:
    """Run the projection table through JS bootstrap_core over every state."""
    code = (
        _JS_SUB_PARITY_SRC
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
    assert result.returncode == 0, f"JS subtract parity eval failed:\n{result.stderr}"
    return json.loads(result.stdout.strip())


# Both substrates are costly to drive (Python run_mu is meta-circular; JS is a
# subprocess), so each side is computed once per process and cached.
_JS_CACHE: dict | None = None
_PY_CACHE: dict | None = None


def _js_results() -> dict:
    """JS bootstrap_core subtract results, keyed by ``"a,b"`` (computed once).

    The input state mirrors the landed ``run_subtract`` driver exactly: the engine
    receives only the encoded operands (``a = encode(a)``, ``b = encode(b)``) and
    performs the compare-based-sign + borrow + fold subtraction itself.
    """
    global _JS_CACHE
    if _JS_CACHE is None:
        states = {
            _corpus_key(a, b): {"_sub": {"a": encode(a), "b": encode(b)}}
            for (a, b) in CORPUS
        }
        _JS_CACHE = _run_js_sub(SUB_PROJECTIONS, states)
    return _JS_CACHE


def _py_results() -> dict:
    """Python run_mu subtract results, keyed by ``(a, b)`` (computed once)."""
    global _PY_CACHE
    if _PY_CACHE is None:
        cache: dict = {}
        for (a, b) in CORPUS:
            result, steps, stalled = run_subtract(a, b)
            cache[(a, b)] = {"result": result, "steps": steps, "stalled": stalled}
        _PY_CACHE = cache
    return _PY_CACHE


# =============================================================================
# Fast scaffolding (no engine): the source of truth is the landed table and the JS
# runner drives the REAL substrate. These run in every tier (not slow).
# =============================================================================

class TestParityScaffolding:
    """Cheap drift guards: shared landed source of truth + real-substrate wiring."""

    def test_uses_landed_subtract_projection_table(self):
        """The table under test is the landed 57-projection signed-subtract table."""
        # 57 = 4 dispatch + 3 sign-dispatch + 13 lifted COMPARE + 31 borrow + 6 fold.
        assert len(SUB_PROJECTIONS) == 57
        assert all(set(proj) == {"pattern", "body"} for proj in SUB_PROJECTIONS)

    def test_uses_landed_corpus(self):
        """The corpus is the landed lean subtract corpus (covers every SUBTRACT path)."""
        assert len(CORPUS) == 8
        assert (0, 0) in CORPUS                        # zero - zero -> 0 (dispatch)
        assert (6, 0) in CORPUS and (0, 6) in CORPUS   # a-0=a / 0-b=-b (dispatch arms)
        assert (5, 5) in CORPUS                        # equal operands -> canonical zero (EQ)
        assert (6, 2) in CORPUS and (2, 6) in CORPUS   # sign-flip pair (positive / neg form)
        assert (8, 7) in CORPUS                        # full borrow cascade + leading-zero strip
        assert (100, 1) in CORPUS                      # larger borrow cascade

    def test_js_runner_drives_real_substrate(self):
        """The parity runner uses the REAL JS engine + factory, not a reimpl."""
        assert "core/bootstrap_core" in _JS_SUB_PARITY_SRC
        assert "core/container_factory" in _JS_SUB_PARITY_SRC
        assert "core/types" in _JS_SUB_PARITY_SRC
        assert "bc.run(" in _JS_SUB_PARITY_SRC

    def test_js_step_budget_is_honored_not_clamped(self):
        """The JS run budget is one bootstrap_core HONORS verbatim — not a larger value it
        silently clamps — so the budget the gate drives JS with is the budget JS runs.

        bootstrap_core.run hard-caps at MAX_RUN_STEPS and clamps any request whose maxSteps
        exceeds it down to the cap (passing exactly MAX_RUN_STEPS is honored — the clamp is
        a strict ``>``). This re-reads the LIVE substrate cap and asserts the budget fed to
        bc.run is ``<=`` it, so the asserted budget can never be a silently-clamped fiction.
        (Python run_subtract uses a smaller 4000 budget; the two ceilings differ but neither
        binds — the corpus converges in ``<=`` ~20 steps on both substrates, see
        test_both_engines_reach_stall_fixpoint — so the result is ceiling-independent.)
        """
        # The literal budget actually fed to bc.run in the JS driver.
        m = re.search(r"bc\.run\(projs, trustMu\(state\), (\d+)\)", _JS_SUB_PARITY_SRC)
        assert m, "JS driver must call bc.run(projs, trustMu(state), <budget>)"
        js_budget = int(m.group(1))
        assert js_budget == _JS_MAX_RUN_STEPS, (
            f"JS driver budget {js_budget} != _JS_MAX_RUN_STEPS {_JS_MAX_RUN_STEPS}"
        )
        # The LIVE substrate hard cap — re-read so this guard tracks the real bootstrap_core,
        # not a stale copy of the number. A budget > this is silently clamped (the defect).
        core_src = (REPO_ROOT / "mu" / "host" / "js" / "core" / "bootstrap_core.js").read_text()
        cap_m = re.search(r"const MAX_RUN_STEPS\s*=\s*(\d+)", core_src)
        assert cap_m, "could not locate `const MAX_RUN_STEPS = <n>` in bootstrap_core.js"
        substrate_cap = int(cap_m.group(1))
        assert js_budget <= substrate_cap, (
            f"JS budget {js_budget} exceeds bootstrap_core MAX_RUN_STEPS {substrate_cap}; "
            "bootstrap_core would silently clamp it, making the asserted budget fictitious"
        )
        assert _JS_MAX_RUN_STEPS == substrate_cap, (
            f"_JS_MAX_RUN_STEPS ({_JS_MAX_RUN_STEPS}) drifted from the live bootstrap_core "
            f"MAX_RUN_STEPS ({substrate_cap}); update the constant"
        )


# =============================================================================
# Governing assertion (INV_CROSS_SUBSTRATE_PARITY): the SAME landed SUBTRACT projections
# run through Python run_mu and JS bootstrap_core produce content-addressed-equal
# results, both decoding to host a - b (signed: neg form / canonical zero / positive).
# =============================================================================

@pytest.mark.l4_expensive
@pytest.mark.slow
class TestStructuralSubtractCrossSubstrateParity:
    """structural_sub via Python run_mu  ≡  structural_sub via JS bootstrap_core."""

    def test_content_hash_parity(self):
        """GOVERNING: muHashCached(JS run) == mu_hash_cached(Python run_mu),
        byte-identical, for every corpus case (and equal to the encode(a-b) oracle).

        This is the L3 cross-substrate parity claim for signed SUBTRACT: two independent
        engines, driven by the same compare-based-sign + borrow + fold projection table
        (which composes the same landed COMPARE), converge to the same canonical signed
        numeral and therefore the same content address — across the positive, canonical
        zero, AND neg-form result shapes.
        """
        js = _js_results()
        py = _py_results()
        for (a, b) in CORPUS:
            py_result = py[(a, b)]["result"]
            js_entry = js[_corpus_key(a, b)]
            py_hash = mu_hash_cached(py_result)
            js_hash = js_entry["hashCached"]
            assert py_hash == js_hash, (
                f"cross-substrate content-hash divergence for {a}-{b}: "
                f"python run_mu={py_hash} js bootstrap_core={js_hash}"
            )
            oracle = mu_hash_cached(encode(a - b))
            assert py_hash == oracle, (
                f"subtract result for {a}-{b} diverged from encode({a - b}) oracle "
                f"(both substrates): {py_hash} != {oracle}"
            )

    def test_results_are_structurally_identical(self):
        """The two substrate results are the SAME canonical signed numeral (structural ==).

        Supporting: hash parity already implies this (the content hash is injective
        over canonical numerals — see the foundation gate), but assert it directly.
        Covers the neg wrapper, the canonical zero, and the positive form.
        """
        js = _js_results()
        py = _py_results()
        for (a, b) in CORPUS:
            py_result = py[(a, b)]["result"]
            js_result = js[_corpus_key(a, b)]["result"]
            assert py_result == js_result, (
                f"structural divergence for {a}-{b}: "
                f"python={py_result} js={js_result}"
            )

    def test_both_engines_decode_to_host_difference(self):
        """SUPPORTING: both substrate results decode to host a - b (possibly negative)."""
        js = _js_results()
        py = _py_results()
        for (a, b) in CORPUS:
            py_dec = decode(py[(a, b)]["result"])
            js_dec = decode(js[_corpus_key(a, b)]["result"])
            assert py_dec == a - b, (
                f"python run_mu sub for {a}-{b} decoded to {py_dec}, not {a - b}"
            )
            assert js_dec == a - b, (
                f"js bootstrap_core sub for {a}-{b} decoded to {js_dec}, not {a - b}"
            )

    def test_both_engines_reach_stall_fixpoint(self):
        """Both engines converged to the {"_num": ...} fixpoint (not max_steps), and
        neither result is still an unprocessed _sub/_sub_cmp/_borrow/_subfold state."""
        js = _js_results()
        py = _py_results()
        for (a, b) in CORPUS:
            py_entry = py[(a, b)]
            js_entry = js[_corpus_key(a, b)]
            assert py_entry["stalled"] is True, (
                f"python run_mu did not stall for {a}-{b}"
            )
            assert js_entry["stalled"] is True, (
                f"js bootstrap_core did not stall for {a}-{b}"
            )
            for label, result in (("python", py_entry["result"]),
                                  ("js", js_entry["result"])):
                assert "_num" in result and len(result) == 1, (
                    f"{label} result for {a}-{b} is not a Z numeral wrapper: {result}"
                )
                for state_key in ("_sub", "_sub_cmp", "_borrow", "_subfold"):
                    assert state_key not in result, (
                        f"{label} result for {a}-{b} is still an unprocessed "
                        f"{state_key} state"
                    )

    def test_js_self_coherence(self):
        """JS muHash and muHashCached agree (no JS-internal cache divergence)."""
        js = _js_results()
        for (a, b) in CORPUS:
            entry = js[_corpus_key(a, b)]
            assert entry["hash"] == entry["hashCached"], (
                f"JS muHash != muHashCached for {a}-{b}"
            )

    def test_python_self_coherence(self):
        """Python mu_hash and mu_hash_cached agree for each run_mu result."""
        py = _py_results()
        for (a, b) in CORPUS:
            result = py[(a, b)]["result"]
            assert mu_hash(result) == mu_hash_cached(result), (
                f"Python mu_hash != mu_hash_cached for {a}-{b}"
            )
