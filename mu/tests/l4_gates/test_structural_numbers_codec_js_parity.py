"""L4 gate: StructuralNumbers numeral CODEC — cross-substrate L3 parity (Python ↔ JS).

Stage 2c-ii gate for ``mu/docs/core/StructuralNumbers.v0.md``. The Python-only slice
(``test_structural_numbers_codec.py``) proved the nested<->flat numeral CODEC (the
§3.1 nested constructor tower <-> a uniform flat bit-list) is expressible as RCX
projections driven by the real Python kernel (``run_mu``), in BOTH conversion
directions. This gate adds the **mandatory L3 parity** obligation for the codec
(``INV_CROSS_SUBSTRATE_PARITY``), mirroring the ADD and COMPARE parity gates
(``test_structural_numbers_add_js_parity.py`` PR #1111,
``test_structural_numbers_compare_js_parity.py`` PR #1112): the **same landed CODEC
projection table** run through the **JS substrate**
(``mu/host/js/core/bootstrap_core.js`` ``run`` via ``node``) yields a result that is
**content-addressed-equal** to the Python ``run_mu`` result —

    muHashCached(js_bootstrap_core_run(codec)) == mu_hash_cached(python_run_mu(codec))

byte-identical — in **both** round-trip directions:

  * **Forward** ``nested -> flat``: the engine reduces ``{"_n2f": nested}`` to a flat
    ``{"_flat": ...}`` numeral, content-addressed-equal to ``encode_flat(n)``.
  * **Reverse** ``flat -> nested``: the engine reduces ``{"_f2n": flat}`` to a nested
    ``{"_num": ...}`` numeral, content-addressed-equal to ``encode_nested(n)``.

Content-addressed equality is the design's free equality (``StructuralNumbers.v0.md``
§3.2): if the two engines converge to the same canonical numeral, their content
hashes are byte-identical. Both substrate results are additionally anchored to the
host integer — ``decode_flat`` of the forward result and ``decode_nested`` of the
reverse result each equal the original ``n``.

Single source of truth: the projection table, the boundary codecs, the corpus, and
the Python drivers are **imported** from ``test_structural_numbers_codec`` rather than
re-derived, so this gate validates the **landed** projections (not a copy) and
guarantees the *same* table is fed to both substrates. The table is serialized to
JSON in Python and rebuilt in JS as **trusted** Mu containers via the existing
``container_factory`` (``list`` / ``record``) through the ``trustMu`` helper — JS
``isValidMu`` requires ``muContainers.has(value)``, and the factory adds each value to
its private trusted set at call time (the "registered" step). ``container_factory.js``
is USE-ONLY: imported and called, never modified.

Imports mirror the ADD/COMPARE parity gates, adapted for the two codec directions.
The forward result is a flat numeral, so it is decoded with the landed ``decode_flat``
and oracled with ``encode_flat``; the reverse result is a nested numeral, decoded with
``decode_nested`` and oracled with ``encode_nested``. There is no host nested<->flat
converter in this gate — the conversion is performed *only* by the landed projection
table driven by the two substrate engines; the boundary codecs merely supply the
inputs and the independent oracles and read the host value back out.

Scope: GATE-ONLY, additive. No runtime/substrate/seed change — the Python runtime,
``mu/host/js/eval_step.js``, and ``mu/host/js/core/`` (including ``container_factory.js``)
are EXECUTED for the comparison, not modified. No host conversion primitive and no
host-only canonicalization is added to force parity; per North Star semantics, parity
must hold structurally or be surfaced as a finding (it holds: both numeral forms are
pure single-key dict structure — ``xO``/``xI``/``xH``/``null`` nested,
``b0``/``b1``/``end``/``null`` flat — so no host int/float string and no multi-key
ordering can diverge across substrates).

Two REAL kernel constraints bound the corpus (documented, not worked around): the
Python ``run_mu`` path is meta-circular (~0.6s / domain-step) and inflates dict depth
~3× in match-normalization, so the imported corpus is deliberately lean (≤ 8-bit
operands, 8 values × 2 directions = 16 cross-substrate comparisons). The
cross-substrate parity tests drive ``run_mu`` (Python) and ``node`` (JS), so they are
``@pytest.mark.l4_expensive`` + ``@pytest.mark.slow``: excluded from the fast green
gate, run in the nightly l4_expensive lane at 900s, per
``.claude/rules/test-classification.md``. The fast scaffolding checks (no engine) run
in every tier.

Wave: structural-numbers-codec-js-parity-2026-06-18 (L4_ENABLER, target gate G8).
Invariant: ``INV_CROSS_SUBSTRATE_PARITY``.
Precedents: ``test_structural_numbers_add_js_parity.py`` (the ADD cross-substrate
parity gate, PR #1111), ``test_structural_numbers_compare_js_parity.py`` (the COMPARE
cross-substrate parity gate, PR #1112), and ``test_structural_numbers_codec.py`` (the
landed Python CODEC projections). Completes the Stage-2 cross-substrate trio
(add + compare + codec JS-parity) before Stage 3 and the matcher cutover.
"""
from __future__ import annotations

import json
import subprocess

import pytest

from tests.repo_root import REPO_ROOT
from rcx_pi.selfhost.mu_type import mu_hash, mu_hash_cached

# Single source of truth: reuse the LANDED codec projection table, boundary codecs,
# corpus, and Python drivers. This gate proves those SAME projections run in the JS
# substrate content-addressed-equal to Python run_mu — so it must validate the landed
# objects, not a re-derived copy. The CODEC has two directions: the forward result is
# a flat numeral (decoded with decode_flat, oracled with encode_flat) and the reverse
# result is a nested numeral (decoded with decode_nested, oracled with encode_nested),
# mirroring how the ADD gate oracles with encode and the COMPARE gate with encode_ord.
from tests.l4_gates.test_structural_numbers_codec import (
    CODEC_PROJECTIONS,
    CORPUS,
    decode_flat,
    decode_nested,
    encode_flat,
    encode_nested,
    run_forward,
    run_reverse,
)


# =============================================================================
# JS substrate runner — drives the SAME projection table through the real JS
# engine (bootstrap_core.run) via `node`, mirroring the cross-substrate pattern in
# test_structural_numbers_add_js_parity.py / test_structural_numbers_compare_js_parity.py.
# Projections + input states are serialized to JSON in Python and rebuilt as TRUSTED
# Mu containers in JS via the existing container_factory (list/record) through trustMu.
# container_factory.js is USE-ONLY (imported + called, never edited): list/record add
# each constructed value to the factory's private trusted-Mu set at call time, which is
# what JS isValidMu requires — that call-time trusting is the "registered" step, not a
# source change.
# =============================================================================

_JS_CODEC_PARITY_SRC = r"""
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


def _dir_key(direction: str, n: int) -> str:
    """Stable JSON-safe key for a (direction, value) case (JS object keys are strings).

    ``direction`` is ``"fwd"`` (nested -> flat) or ``"rev"`` (flat -> nested).
    """
    return f"{direction},{n}"


def _run_js_codec(projections: list[dict], states: dict) -> dict:
    """Run the projection table through JS bootstrap_core over every state."""
    code = (
        _JS_CODEC_PARITY_SRC
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
    assert result.returncode == 0, f"JS codec parity eval failed:\n{result.stderr}"
    return json.loads(result.stdout.strip())


# Both substrates are costly to drive (Python run_mu is meta-circular; JS is a
# subprocess), so each side is computed once per process and cached.
_JS_CACHE: dict | None = None
_PY_CACHE: dict | None = None


def _js_results() -> dict:
    """JS bootstrap_core codec results, keyed by ``"fwd,n"`` / ``"rev,n"`` (once).

    Each corpus value is driven in BOTH directions through the one shared landed
    table: forward from ``{"_n2f": encode_nested(n)}`` and reverse from
    ``{"_f2n": encode_flat(n)}``.
    """
    global _JS_CACHE
    if _JS_CACHE is None:
        states: dict = {}
        for n in CORPUS:
            states[_dir_key("fwd", n)] = {"_n2f": encode_nested(n)}
            states[_dir_key("rev", n)] = {"_f2n": encode_flat(n)}
        _JS_CACHE = _run_js_codec(CODEC_PROJECTIONS, states)
    return _JS_CACHE


def _py_results() -> dict:
    """Python run_mu codec results, keyed by ``n`` with ``fwd``/``rev`` sub-keys (once)."""
    global _PY_CACHE
    if _PY_CACHE is None:
        cache: dict = {}
        for n in CORPUS:
            fwd, fwd_steps, fwd_stall = run_forward(encode_nested(n))
            rev, rev_steps, rev_stall = run_reverse(encode_flat(n))
            cache[n] = {
                "fwd": fwd, "fwd_steps": fwd_steps, "fwd_stall": fwd_stall,
                "rev": rev, "rev_steps": rev_steps, "rev_stall": rev_stall,
            }
        _PY_CACHE = cache
    return _PY_CACHE


# =============================================================================
# Fast scaffolding (no engine): the source of truth is the landed table and the JS
# runner drives the REAL substrate. These run in every tier (not slow).
# =============================================================================

class TestParityScaffolding:
    """Cheap drift guards: shared landed source of truth + real-substrate wiring."""

    def test_uses_landed_codec_projection_table(self):
        """The table under test is the landed 11-projection codec table."""
        # 11 = 5 forward (2 dispatch + 3 loop) + 6 reverse (2 dispatch + 4 loop).
        assert len(CODEC_PROJECTIONS) == 11
        assert all(set(proj) == {"pattern", "body"} for proj in CODEC_PROJECTIONS)

    def test_uses_landed_corpus(self):
        """The corpus is the landed lean codec corpus: 8 non-negative ≤ 8-bit values,
        pinning the mandatory structural shapes (guards against silent corpus drift)."""
        assert len(CORPUS) == 8
        assert set(CORPUS) == {0, 1, 2, 6, 8, 21, 170, 255}
        assert 0 in CORPUS          # both zero-dispatch arms (forward + reverse)
        assert 1 in CORPUS          # single bit: nested {xH} <-> flat {b1,end}
        assert any(n > 0 and (n & (n - 1)) == 0 for n in CORPUS)  # power of two (8)
        assert 255 in CORPUS        # 8-bit all-ones (all xI / all b1)

    def test_corpus_drives_sixteen_cross_substrate_comparisons(self):
        """Each value is exercised in BOTH directions: 8 × 2 = 16 comparisons (no fewer)."""
        assert len(CORPUS) * 2 == 16

    def test_js_runner_drives_real_substrate(self):
        """The parity runner uses the REAL JS engine + factory, not a reimpl."""
        assert "core/bootstrap_core" in _JS_CODEC_PARITY_SRC
        assert "core/container_factory" in _JS_CODEC_PARITY_SRC
        assert "core/types" in _JS_CODEC_PARITY_SRC
        assert "bc.run(" in _JS_CODEC_PARITY_SRC


# =============================================================================
# Governing assertion (INV_CROSS_SUBSTRATE_PARITY): the SAME landed CODEC projections
# run through Python run_mu and JS bootstrap_core produce content-addressed-equal
# results in BOTH directions, each anchored to the host integer (decode_* == n).
# =============================================================================

@pytest.mark.l4_expensive
@pytest.mark.slow
class TestStructuralCodecCrossSubstrateParity:
    """structural_codec via Python run_mu  ≡  structural_codec via JS bootstrap_core."""

    def test_content_hash_parity(self):
        """GOVERNING: muHashCached(JS run) == mu_hash_cached(Python run_mu),
        byte-identical, for every corpus value in BOTH directions — and equal to the
        independent encode_flat(n) / encode_nested(n) oracle.

        This is the L3 cross-substrate parity claim for the codec: two independent
        engines, driven by the same projection table, converge to the same canonical
        numeral (flat for forward, nested for reverse) and therefore the same content
        address. Counts comparisons and asserts exactly 16 (= 8 values × 2 directions),
        so a silently-shrunk corpus cannot pass.
        """
        js = _js_results()
        py = _py_results()
        comparisons = 0
        for n in CORPUS:
            # Forward: nested -> flat, oracle encode_flat(n).
            py_fwd_hash = mu_hash_cached(py[n]["fwd"])
            js_fwd_hash = js[_dir_key("fwd", n)]["hashCached"]
            assert py_fwd_hash == js_fwd_hash, (
                f"cross-substrate content-hash divergence for forward CODEC({n}): "
                f"python run_mu={py_fwd_hash} js bootstrap_core={js_fwd_hash}"
            )
            fwd_oracle = mu_hash_cached(encode_flat(n))
            assert py_fwd_hash == fwd_oracle, (
                f"forward CODEC({n}) diverged from encode_flat({n}) oracle "
                f"(both substrates): {py_fwd_hash} != {fwd_oracle}"
            )
            comparisons += 1

            # Reverse: flat -> nested, oracle encode_nested(n).
            py_rev_hash = mu_hash_cached(py[n]["rev"])
            js_rev_hash = js[_dir_key("rev", n)]["hashCached"]
            assert py_rev_hash == js_rev_hash, (
                f"cross-substrate content-hash divergence for reverse CODEC({n}): "
                f"python run_mu={py_rev_hash} js bootstrap_core={js_rev_hash}"
            )
            rev_oracle = mu_hash_cached(encode_nested(n))
            assert py_rev_hash == rev_oracle, (
                f"reverse CODEC({n}) diverged from encode_nested({n}) oracle "
                f"(both substrates): {py_rev_hash} != {rev_oracle}"
            )
            comparisons += 1
        assert comparisons == 16, f"expected 16 cross-substrate comparisons, ran {comparisons}"

    def test_results_are_structurally_identical(self):
        """The two substrate results are the SAME canonical numeral (structural ==),
        in both directions.

        Supporting: hash parity already implies this (the content hash is injective
        over canonical numerals — see the foundation gate), but assert it directly.
        """
        js = _js_results()
        py = _py_results()
        for n in CORPUS:
            assert py[n]["fwd"] == js[_dir_key("fwd", n)]["result"], (
                f"structural divergence for forward CODEC({n}): "
                f"python={py[n]['fwd']} js={js[_dir_key('fwd', n)]['result']}"
            )
            assert py[n]["rev"] == js[_dir_key("rev", n)]["result"], (
                f"structural divergence for reverse CODEC({n}): "
                f"python={py[n]['rev']} js={js[_dir_key('rev', n)]['result']}"
            )

    def test_both_engines_decode_to_host_value(self):
        """SUPPORTING: both substrate results decode to the original host value n —
        forward via decode_flat, reverse via decode_nested."""
        js = _js_results()
        py = _py_results()
        for n in CORPUS:
            py_fwd_dec = decode_flat(py[n]["fwd"])
            js_fwd_dec = decode_flat(js[_dir_key("fwd", n)]["result"])
            assert py_fwd_dec == n, (
                f"python run_mu forward CODEC for {n} decoded to {py_fwd_dec}, not {n}"
            )
            assert js_fwd_dec == n, (
                f"js bootstrap_core forward CODEC for {n} decoded to {js_fwd_dec}, not {n}"
            )
            py_rev_dec = decode_nested(py[n]["rev"])
            js_rev_dec = decode_nested(js[_dir_key("rev", n)]["result"])
            assert py_rev_dec == n, (
                f"python run_mu reverse CODEC for {n} decoded to {py_rev_dec}, not {n}"
            )
            assert js_rev_dec == n, (
                f"js bootstrap_core reverse CODEC for {n} decoded to {js_rev_dec}, not {n}"
            )

    def test_both_engines_reach_stall_fixpoint(self):
        """Both engines converged to the result fixpoint (not max_steps), and neither
        result is still an unprocessed codec state: forward -> {"_flat": ...}, reverse
        -> {"_num": ...}, each a single-key wrapper with no residual marker."""
        js = _js_results()
        py = _py_results()
        for n in CORPUS:
            py_fwd_entry = py[n]
            js_fwd_entry = js[_dir_key("fwd", n)]
            js_rev_entry = js[_dir_key("rev", n)]
            assert py_fwd_entry["fwd_stall"] is True, (
                f"python run_mu did not stall for forward CODEC({n})"
            )
            assert py_fwd_entry["rev_stall"] is True, (
                f"python run_mu did not stall for reverse CODEC({n})"
            )
            assert js_fwd_entry["stalled"] is True, (
                f"js bootstrap_core did not stall for forward CODEC({n})"
            )
            assert js_rev_entry["stalled"] is True, (
                f"js bootstrap_core did not stall for reverse CODEC({n})"
            )
            for label, result in (("python", py_fwd_entry["fwd"]),
                                  ("js", js_fwd_entry["result"])):
                assert "_flat" in result and len(result) == 1, (
                    f"{label} forward result for {n} is not a flat numeral wrapper: {result}"
                )
            for label, result in (("python", py_fwd_entry["rev"]),
                                  ("js", js_rev_entry["result"])):
                assert "_num" in result and len(result) == 1, (
                    f"{label} reverse result for {n} is not an N numeral wrapper: {result}"
                )

    def test_js_self_coherence(self):
        """JS muHash and muHashCached agree (no JS-internal cache divergence)."""
        js = _js_results()
        for n in CORPUS:
            for direction in ("fwd", "rev"):
                entry = js[_dir_key(direction, n)]
                assert entry["hash"] == entry["hashCached"], (
                    f"JS muHash != muHashCached for {direction} CODEC({n})"
                )

    def test_python_self_coherence(self):
        """Python mu_hash and mu_hash_cached agree for each run_mu result."""
        py = _py_results()
        for n in CORPUS:
            for key in ("fwd", "rev"):
                result = py[n][key]
                assert mu_hash(result) == mu_hash_cached(result), (
                    f"Python mu_hash != mu_hash_cached for {key} CODEC({n})"
                )
