"""L4 gate: StructuralNumbers integer GCD as lifted RCX projections.

Stage 3 gate for ``mu/docs/core/StructuralNumbers.v0.md``. This test proves that
integer GCD over non-negative ``N`` operands is expressible as a test-local Mu
state machine driven by the real Python ``run_mu`` kernel, without adding any
runtime, substrate, seed, registry, or production semantic surface.

The GCD machine composes already-landed arithmetic gates rather than rebuilding
them:

* ``COMPARE_PROJECTIONS`` is imported from the landed compare gate and lifted into
  a ``_gcd_cmp`` work slot that carries the two operands.
* ``SUB_PROJECTIONS`` is imported from the landed subtract gate and lifted into a
  ``_gcd_sub`` work slot that carries the other Euclidean operand.
* ``_gcd`` uses zero dispatch, compares two positive operands structurally, runs
  subtract only for the strict larger-minus-smaller difference, and re-seeds
  ``_gcd`` from that positive difference.

The only host ``math.gcd`` use is the test oracle. The engine itself contains no
host gcd, mod, divide, comparison, or subtraction primitive.

Wave: structural-numbers-gcd-2026-06-19 (L4_ENABLER, target gate G8).
"""
from __future__ import annotations

import math

import pytest

from rcx_pi.selfhost.mu_type import is_mu, mu_hash
from rcx_pi.selfhost.step_mu import run_mu
from tests.l4_gates.test_structural_numbers_compare import COMPARE_PROJECTIONS, _v
from tests.l4_gates.test_structural_numbers_foundation import decode, encode
from tests.l4_gates.test_structural_numbers_subtract import SUB_PROJECTIONS


_GA = "__gcd_a"
_GB = "__gcd_b"
_GO = "__gcd_other"


def _lift_compare_into_gcd(cmp_projs: list[dict]) -> list[dict]:
    """Lift landed COMPARE projections into the ``_gcd_cmp`` work slot."""
    lifted: list[dict] = []
    for proj in cmp_projs:
        lifted.append({
            "pattern": {"_gcd_cmp": {"work": proj["pattern"], "a": _v(_GA), "b": _v(_GB)}},
            "body": {"_gcd_cmp": {"work": proj["body"], "a": _v(_GA), "b": _v(_GB)}},
        })
    return lifted


def _lift_subtract_into_gcd(sub_projs: list[dict]) -> list[dict]:
    """Lift landed SUBTRACT projections into the ``_gcd_sub`` work slot."""
    lifted: list[dict] = []
    for proj in sub_projs:
        lifted.append({
            "pattern": {"_gcd_sub": {"work": proj["pattern"], "other": _v(_GO)}},
            "body": {"_gcd_sub": {"work": proj["body"], "other": _v(_GO)}},
        })
    return lifted


def _positive_num_forms(var_name: str) -> list[tuple[dict, dict]]:
    """Positive ``N`` inner forms used to re-seed only strict positive differences."""
    return [
        ({"xH": None}, {"xH": None}),
        ({"xO": _v(var_name)}, {"xO": _v(var_name)}),
        ({"xI": _v(var_name)}, {"xI": _v(var_name)}),
    ]


def build_gcd_projections() -> list[dict]:
    """Construct the GCD projection table.

    Layout: 4 ``_gcd`` dispatch + 3 compare-result dispatch + 3 positive-difference
    re-seed rules + lifted COMPARE + lifted SUBTRACT.
    """
    projs: list[dict] = []

    # Zero dispatch. Order matters: the literal zero arms must run before the
    # positive/positive generic arm, because ``{"var": ...}`` can bind null.
    projs.append({"pattern": {"_gcd": {"a": {"_num": None}, "b": {"_num": None}}},
                  "body": {"_num": None}})
    projs.append({"pattern": {"_gcd": {"a": {"_num": None}, "b": {"_num": _v("pb")}}},
                  "body": {"_num": _v("pb")}})
    projs.append({"pattern": {"_gcd": {"a": {"_num": _v("pa")}, "b": {"_num": None}}},
                  "body": {"_num": _v("pa")}})
    projs.append({"pattern": {"_gcd": {"a": {"_num": _v("pa")},
                                       "b": {"_num": _v("pb")}}},
                  "body": {"_gcd_cmp": {"work": {"_cmp": {"a": {"_num": _v("pa")},
                                                          "b": {"_num": _v("pb")}}},
                                        "a": {"_num": _v("pa")},
                                        "b": {"_num": _v("pb")}}}})

    # The lifted COMPARE work reduces to a canonical ordering tag. Equality is the
    # Euclidean fixpoint; strict order seeds a lifted SUBTRACT for larger-smaller.
    projs.append({"pattern": {"_gcd_cmp": {"work": {"_ord": {"eq": None}},
                                           "a": _v(_GA), "b": _v(_GB)}},
                  "body": _v(_GA)})
    projs.append({"pattern": {"_gcd_cmp": {"work": {"_ord": {"gt": None}},
                                           "a": _v(_GA), "b": _v(_GB)}},
                  "body": {"_gcd_sub": {"work": {"_sub": {"a": _v(_GA), "b": _v(_GB)}},
                                        "other": _v(_GB)}}})
    projs.append({"pattern": {"_gcd_cmp": {"work": {"_ord": {"lt": None}},
                                           "a": _v(_GA), "b": _v(_GB)}},
                  "body": {"_gcd_sub": {"work": {"_sub": {"a": _v(_GB), "b": _v(_GA)}},
                                        "other": _v(_GA)}}})

    # A strict compare means the subtract result must be positive. Re-seed only on
    # positive numeral forms; a zero or neg subtract result would stall visibly.
    for index, (diff_pattern, diff_body) in enumerate(_positive_num_forms("pd")):
        var_name = f"pd{index}"
        diff_pattern, diff_body = _positive_num_forms(var_name)[index]
        projs.append({
            "pattern": {"_gcd_sub": {"work": {"_num": diff_pattern}, "other": _v(_GO)}},
            "body": {"_gcd": {"a": {"_num": diff_body}, "b": _v(_GO)}},
        })

    projs.extend(_lift_compare_into_gcd(COMPARE_PROJECTIONS))
    projs.extend(_lift_subtract_into_gcd(SUB_PROJECTIONS))
    return projs


GCD_PROJECTIONS = build_gcd_projections()


CORPUS: list[tuple[int, int]] = [
    (0, 0),
    (5, 0),
    (0, 4),
]

EUCLIDEAN_SHAPE_CORPUS: list[tuple[int, int]] = [
    (2, 1),
    (4, 2),
    (6, 4),
    (6, 3),
]

assert CORPUS == [(0, 0), (5, 0), (0, 4)]
assert all(a >= 0 and b >= 0 and a <= 6 and b <= 6 for a, b in CORPUS)
assert EUCLIDEAN_SHAPE_CORPUS == [(2, 1), (4, 2), (6, 4), (6, 3)]
assert all(a > 0 and b > 0 and a <= 6 and b <= 6 for a, b in EUCLIDEAN_SHAPE_CORPUS)
assert any(math.gcd(a, b) > 1 for a, b in EUCLIDEAN_SHAPE_CORPUS)


def run_gcd(a: int, b: int) -> tuple[dict, int, bool]:
    """Run structural GCD through ``run_mu`` over non-negative operands."""
    assert a >= 0 and b >= 0, "GCD gate operand domain is non-negative N"
    state = {"_gcd": {"a": encode(a), "b": encode(b)}}
    result, trace, stalled = run_mu(GCD_PROJECTIONS, state, max_steps=12000)
    return result, len(trace), stalled


_GCD_CACHE: dict[tuple[int, int], tuple[dict, int, bool]] = {}


def _gcd_result(a: int, b: int) -> tuple[dict, int, bool]:
    pair = (a, b)
    if pair not in _GCD_CACHE:
        _GCD_CACHE[pair] = run_gcd(a, b)
    return _GCD_CACHE[pair]


def _collect_vars(node, out: list[str]) -> None:
    if isinstance(node, dict):
        if set(node) == {"var"} and isinstance(node["var"], str):
            out.append(node["var"])
            return
        for child in node.values():
            _collect_vars(child, out)


def _positive_nodes_all_single_key(value) -> bool:
    if value is None:
        return True
    if not isinstance(value, dict) or len(value) != 1:
        return False
    key = next(iter(value))
    if key == "neg":
        return False
    if key not in {"xH", "xO", "xI"}:
        return False
    return _positive_nodes_all_single_key(value[key])


def _is_canonical_n_numeral(value) -> bool:
    if not isinstance(value, dict) or len(value) != 1 or "_num" not in value:
        return False
    if not _positive_nodes_all_single_key(value["_num"]):
        return False
    decoded = decode(value)
    return decoded >= 0 and value == encode(decoded)


def _contains_state_key(value, state_keys: set[str]) -> bool:
    if isinstance(value, dict):
        if any(key in state_keys for key in value):
            return True
        return any(_contains_state_key(child, state_keys) for child in value.values())
    return False


class TestProjectionScaffolding:
    """The GCD table is linear and composes landed COMPARE/SUBTRACT verbatim."""

    def test_projection_count(self):
        assert len(COMPARE_PROJECTIONS) == 13
        assert len(SUB_PROJECTIONS) == 57
        assert len(GCD_PROJECTIONS) == 4 + 3 + 3 + len(COMPARE_PROJECTIONS) + len(SUB_PROJECTIONS)
        assert len(GCD_PROJECTIONS) == 80

    def test_every_projection_has_pattern_and_body(self):
        for proj in GCD_PROJECTIONS:
            assert set(proj) == {"pattern", "body"}

    def test_all_projections_are_linear(self):
        for proj in GCD_PROJECTIONS:
            names: list[str] = []
            _collect_vars(proj["pattern"], names)
            assert len(names) == len(set(names)), (
                f"non-linear pattern (variable repeated): {proj['pattern']}"
            )

    def test_gcd_composes_landed_compare(self):
        lifted = _lift_compare_into_gcd(COMPARE_PROJECTIONS)
        for cmp_proj, lifted_proj in zip(COMPARE_PROJECTIONS, lifted):
            assert lifted_proj["pattern"]["_gcd_cmp"]["work"] == cmp_proj["pattern"]
            assert lifted_proj["body"]["_gcd_cmp"]["work"] == cmp_proj["body"]
            assert lifted_proj in GCD_PROJECTIONS
        for lifted_proj in lifted:
            for side in ("pattern", "body"):
                wrap = lifted_proj[side]["_gcd_cmp"]
                assert wrap["a"] == _v(_GA)
                assert wrap["b"] == _v(_GB)

    def test_gcd_composes_landed_subtract(self):
        lifted = _lift_subtract_into_gcd(SUB_PROJECTIONS)
        for sub_proj, lifted_proj in zip(SUB_PROJECTIONS, lifted):
            assert lifted_proj["pattern"]["_gcd_sub"]["work"] == sub_proj["pattern"]
            assert lifted_proj["body"]["_gcd_sub"]["work"] == sub_proj["body"]
            assert lifted_proj in GCD_PROJECTIONS
        for lifted_proj in lifted:
            for side in ("pattern", "body"):
                assert lifted_proj[side]["_gcd_sub"]["other"] == _v(_GO)

    def test_positive_difference_reseeds_gcd(self):
        reseed = [
            proj for proj in GCD_PROJECTIONS
            if "_gcd_sub" in proj["pattern"] and "_num" in proj["pattern"]["_gcd_sub"]["work"]
        ]
        assert len(reseed) == 3
        seen = {next(iter(proj["pattern"]["_gcd_sub"]["work"]["_num"])) for proj in reseed}
        assert seen == {"xH", "xO", "xI"}
        for proj in reseed:
            body = proj["body"]
            assert set(body) == {"_gcd"}
            assert body["_gcd"]["b"] == _v(_GO)

    def test_corpus_is_locked_and_bounded(self):
        assert CORPUS == [(0, 0), (5, 0), (0, 4)]
        assert all(a >= 0 and b >= 0 for a, b in CORPUS)
        assert max(max(a, b) for a, b in CORPUS) == 5

    def test_euclidean_shape_corpus_is_locked_outside_run_mu_corpus(self):
        assert EUCLIDEAN_SHAPE_CORPUS == [(2, 1), (4, 2), (6, 4), (6, 3)]
        assert all(a > 0 and b > 0 and a != b for a, b in EUCLIDEAN_SHAPE_CORPUS)
        assert any(math.gcd(a, b) == 1 for a, b in EUCLIDEAN_SHAPE_CORPUS)
        assert any(math.gcd(a, b) > 1 for a, b in EUCLIDEAN_SHAPE_CORPUS)
        assert (6, 4) in EUCLIDEAN_SHAPE_CORPUS
        assert all(pair not in CORPUS for pair in EUCLIDEAN_SHAPE_CORPUS)


@pytest.mark.l4_expensive
@pytest.mark.slow
@pytest.mark.parametrize(("a", "b"), CORPUS)
class TestStructuralGcdEquivalence:
    """structural_gcd(a,b) equals encode(math.gcd(a,b)) over the lean corpus."""

    def test_canonical_structural_equality(self, a: int, b: int):
        result, _, _ = _gcd_result(a, b)
        expected = encode(math.gcd(a, b))
        assert result == expected, (
            f"structural GCD diverged for ({a}, {b}): got {result}, expected {expected}"
        )

    def test_content_hash_equality(self, a: int, b: int):
        result, _, _ = _gcd_result(a, b)
        expected = encode(math.gcd(a, b))
        assert mu_hash(result) == mu_hash(expected), (
            f"content-hash divergence for GCD({a}, {b})"
        )

    def test_result_is_valid_canonical_n_numeral(self, a: int, b: int):
        result, _, _ = _gcd_result(a, b)
        assert is_mu(result), f"result for GCD({a}, {b}) is not valid Mu: {result}"
        assert _is_canonical_n_numeral(result), (
            f"result for GCD({a}, {b}) is not a canonical N numeral: {result}"
        )

    def test_engine_reaches_stall_fixpoint(self, a: int, b: int):
        result, steps, stalled = _gcd_result(a, b)
        forbidden = {"_gcd", "_gcd_cmp", "_gcd_sub", "_cmp", "_cc", "_sub", "_sub_cmp", "_borrow", "_subfold"}
        assert stalled is True, f"run_mu did not stall for GCD({a}, {b}) (steps={steps})"
        assert not _contains_state_key(result, forbidden), (
            f"result for GCD({a}, {b}) still carries an in-flight state: {result}"
        )
        assert result != {"_gcd": {"a": encode(a), "b": encode(b)}}, (
            f"result for GCD({a}, {b}) is the unprocessed input state"
        )

    def test_decode_to_host_supporting(self, a: int, b: int):
        result, _, _ = _gcd_result(a, b)
        assert decode(result) == math.gcd(a, b), (
            f"decode(run_mu gcd) = {decode(result)} != math.gcd({a}, {b})"
        )
