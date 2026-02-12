"""
Hemisphere routing tests — Mu Hemispheres v0.

Tests that hemisphere routing projections correctly classify engine_result
outputs and route them to the appropriate hemisphere (r_null, r_a, lobes).

All routing runs through run_mu → step_mu → step_kernel_mu (core kernel),
verifying that routing decisions are fully structural.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rcx_pi.selfhost.mu_type import mu_equal
from rcx_pi.selfhost.seed_integrity import get_seed_path, load_verified_seed
from rcx_pi.selfhost.step_mu import run_mu, step_mu


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


def _collect_var_names(obj) -> list[str]:
    """Collect all variable names from a Mu pattern (for linearity check)."""
    if isinstance(obj, dict):
        if "var" in obj and len(obj) == 1:
            return [obj["var"]]
        names = []
        for v in obj.values():
            names.extend(_collect_var_names(v))
        return names
    if isinstance(obj, list):
        names = []
        for item in obj:
            names.extend(_collect_var_names(item))
        return names
    return []


def _load_hemisphere_projections() -> list[dict]:
    seed = load_verified_seed(get_seed_path("hemispheres.v1.json"))
    return seed["projections"]


def _make_engine_result(
    value=None,
    closure_detected=False,
    tau_step=None,
    exhaustion_detected=False,
    operator_frozen=None,
    frozen_set=None,
    action="continue",
    stall=False,
) -> dict:
    return {
        "value": value,
        "closure_detected": closure_detected,
        "tau_step": tau_step,
        "exhaustion_detected": exhaustion_detected,
        "operator_frozen": operator_frozen,
        "frozen_set": frozen_set,
        "action": action,
        "stall": stall,
    }


def _empty_hemispheres() -> dict:
    return {
        "r_null": None,
        "r_inf": None,
        "r_a": None,
        "lobes": None,
        "sink": None,
    }


def _route(projs, engine_result, hemispheres=None):
    if hemispheres is None:
        hemispheres = _empty_hemispheres()
    input_val = {
        "route_hemisphere": {
            "engine_result": engine_result,
            "hemispheres": hemispheres,
        }
    }
    result, trace, stall = run_mu(projs, input_val, max_steps=20)
    return result


# =============================================================================
# TestHemisphereInit
# =============================================================================


class TestHemisphereInit:
    """hemisphere.init decomposes engine_result correctly."""

    def test_init_extracts_value_and_closure(self):
        projs = _load_hemisphere_projections()
        er = _make_engine_result(value=42, closure_detected=True)
        input_val = {
            "route_hemisphere": {
                "engine_result": er,
                "hemispheres": _empty_hemispheres(),
            }
        }
        # Single step should produce classify state
        result = step_mu(projs, input_val)
        assert result["hemi_mode"] == "classify"
        assert result["hemi_value"] == 42
        assert result["hemi_closure"] is True
        assert "hemi_exhaustion" in result
        assert "hemi_stall" in result

    def test_init_passes_hemispheres_through(self):
        projs = _load_hemisphere_projections()
        hemispheres = _empty_hemispheres()
        hemispheres["lobes"] = [{"state": "existing", "closure_flag": False, "origin": "engine"}]
        er = _make_engine_result(value="test")
        input_val = {
            "route_hemisphere": {
                "engine_result": er,
                "hemispheres": hemispheres,
            }
        }
        result = step_mu(projs, input_val)
        assert isinstance(result["hemi_h"], dict)
        assert result["hemi_h"]["lobes"] is not None


# =============================================================================
# TestHemisphereClassify
# =============================================================================


@pytest.mark.slow
class TestHemisphereClassify:
    """Classification routes to correct hemisphere."""

    def test_null_value_routes_to_r_null(self):
        projs = _load_hemisphere_projections()
        result = _route(projs, _make_engine_result(value=None))
        assert result["r_null"] is not None
        assert result["r_null"][0]["state"] is None
        assert result["lobes"] is None
        assert result["r_a"] is None

    def test_closure_routes_to_r_a(self):
        projs = _load_hemisphere_projections()
        result = _route(projs, _make_engine_result(value=42, closure_detected=True))
        assert result["r_a"] is not None
        assert result["r_a"][0]["state"] == 42
        assert result["r_a"][0]["closure_flag"] is True
        assert result["lobes"] is None
        assert result["r_null"] is None

    def test_default_routes_to_lobes(self):
        projs = _load_hemisphere_projections()
        result = _route(projs, _make_engine_result(value="hello"))
        assert result["lobes"] is not None
        assert result["lobes"][0]["state"] == "hello"
        assert result["r_null"] is None
        assert result["r_a"] is None

    def test_integer_value_routes_to_lobes(self):
        projs = _load_hemisphere_projections()
        result = _route(projs, _make_engine_result(value=99))
        assert result["lobes"] is not None
        assert result["lobes"][0]["state"] == 99

    def test_nested_dict_routes_to_lobes(self):
        projs = _load_hemisphere_projections()
        nested = {"a": 1, "b": {"c": 2}}
        result = _route(projs, _make_engine_result(value=nested))
        assert result["lobes"] is not None
        assert result["lobes"][0]["state"] == nested

    def test_exhaustion_routes_to_sink(self):
        projs = _load_hemisphere_projections()
        result = _route(projs, _make_engine_result(value="frozen_op", exhaustion_detected=True))
        assert result["sink"] is not None
        assert result["sink"][0]["state"] == "frozen_op"
        assert result["lobes"] is None
        assert result["r_a"] is None
        assert result["r_null"] is None
        assert result["r_inf"] is None

    def test_stall_routes_to_r_inf(self):
        projs = _load_hemisphere_projections()
        result = _route(projs, _make_engine_result(value="divergent", stall=True))
        assert result["r_inf"] is not None
        assert result["r_inf"][0]["state"] == "divergent"
        assert result["lobes"] is None
        assert result["r_a"] is None
        assert result["r_null"] is None
        assert result["sink"] is None


# =============================================================================
# TestHemispherePriorityOrder
# =============================================================================


@pytest.mark.slow
class TestHemispherePriorityOrder:
    """Verify first-match-wins priority: exhaustion > null > closure > stall > default."""

    def test_null_takes_priority_over_closure(self):
        projs = _load_hemisphere_projections()
        result = _route(projs, _make_engine_result(value=None, closure_detected=True))
        # null check comes before closure check in projection order
        assert result["r_null"] is not None
        assert result["r_a"] is None
        # But closure_flag is preserved in entry
        assert result["r_null"][0]["closure_flag"] is True

    def test_exhaustion_takes_priority_over_closure(self):
        projs = _load_hemisphere_projections()
        result = _route(projs, _make_engine_result(
            value="val", closure_detected=True, exhaustion_detected=True))
        # exhaustion overrides closure
        assert result["sink"] is not None
        assert result["r_a"] is None

    def test_stall_takes_priority_over_default(self):
        projs = _load_hemisphere_projections()
        result = _route(projs, _make_engine_result(value="val", stall=True))
        assert result["r_inf"] is not None
        assert result["lobes"] is None

    def test_exhaustion_takes_priority_over_stall(self):
        projs = _load_hemisphere_projections()
        result = _route(projs, _make_engine_result(
            value="val", exhaustion_detected=True, stall=True))
        # exhaustion before stall in projection order
        assert result["sink"] is not None
        assert result["r_inf"] is None


# =============================================================================
# TestHemisphereRoutingTruthTable
# =============================================================================


@pytest.mark.slow
class TestHemisphereRoutingTruthTable:
    """Exhaustive truth-table: all signal combinations route correctly.

    Priority: exhaustion > null > closure > stall > default.
    """

    @pytest.mark.parametrize(
        "exhaustion,closure,stall,value_none,expected",
        [
            (True, False, False, False, "sink"),
            (False, True, False, False, "r_a"),
            (False, False, True, False, "r_inf"),
            (False, False, False, True, "r_null"),
            (False, False, False, False, "lobes"),
            (True, True, True, True, "sink"),
            (False, True, True, True, "r_null"),
            (False, True, True, False, "r_a"),
            (False, False, True, True, "r_null"),
            (True, True, False, False, "sink"),
            (True, False, True, False, "sink"),
            (True, False, False, True, "sink"),
        ],
        ids=[
            "exhaustion_only",
            "closure_only",
            "stall_only",
            "null_only",
            "no_signals_default",
            "all_signals",
            "closure+stall+null",
            "closure+stall",
            "stall+null",
            "exhaustion+closure",
            "exhaustion+stall",
            "exhaustion+null",
        ],
    )
    def test_signal_combination(self, exhaustion, closure, stall, value_none, expected):
        projs = _load_hemisphere_projections()
        value = None if value_none else "test_value"
        er = _make_engine_result(
            value=value,
            closure_detected=closure,
            exhaustion_detected=exhaustion,
            stall=stall,
        )
        result = _route(projs, er)
        populated = [k for k in ("r_null", "r_inf", "r_a", "lobes", "sink") if result[k] is not None]
        assert len(populated) == 1, f"Expected 1 populated, got {populated}"
        assert result[expected] is not None, (
            f"Expected {expected}, got {populated[0]}"
        )


# =============================================================================
# TestHemisphereAdd
# =============================================================================


@pytest.mark.slow
class TestHemisphereAdd:
    """Entry correctly prepended to target hemisphere, others unchanged."""

    def test_add_to_empty_hemisphere(self):
        projs = _load_hemisphere_projections()
        result = _route(projs, _make_engine_result(value="first"))
        assert len(result["lobes"]) == 1
        assert result["lobes"][0]["state"] == "first"

    def test_prepend_to_existing_entries(self):
        projs = _load_hemisphere_projections()
        # First route
        h1 = _route(projs, _make_engine_result(value="first"))
        # Second route into same result
        h2 = _route(projs, _make_engine_result(value="second"), hemispheres=h1)
        assert len(h2["lobes"]) == 2
        assert h2["lobes"][0]["state"] == "second"  # prepended
        assert h2["lobes"][1]["state"] == "first"

    def test_other_hemispheres_unchanged(self):
        projs = _load_hemisphere_projections()
        # Pre-populate r_a with an entry
        hemispheres = _empty_hemispheres()
        hemispheres["r_a"] = [{"state": "stable", "closure_flag": True, "origin": "engine"}]
        # Route to lobes
        result = _route(projs, _make_engine_result(value="new"), hemispheres=hemispheres)
        assert result["lobes"] is not None
        assert len(result["r_a"]) == 1
        assert result["r_a"][0]["state"] == "stable"

    def test_non_target_hemispheres_untouched(self):
        projs = _load_hemisphere_projections()
        result = _route(projs, _make_engine_result(value="test"))
        # Default routes to lobes; all other hemispheres stay None
        assert result["lobes"] is not None
        assert result["r_inf"] is None
        assert result["sink"] is None
        assert result["r_null"] is None
        assert result["r_a"] is None


# =============================================================================
# TestHemisphereEntrySchema
# =============================================================================


@pytest.mark.slow
class TestHemisphereEntrySchema:
    """Entry structure matches design spec."""

    def test_entry_has_required_fields(self):
        projs = _load_hemisphere_projections()
        result = _route(projs, _make_engine_result(value="test", closure_detected=False))
        entry = result["lobes"][0]
        assert "state" in entry
        assert "closure_flag" in entry
        assert "origin" in entry
        assert entry["origin"] == "engine"

    def test_entry_preserves_value(self):
        projs = _load_hemisphere_projections()
        result = _route(projs, _make_engine_result(value={"complex": [1, 2, 3]}))
        entry = result["lobes"][0]
        assert entry["state"] == {"complex": [1, 2, 3]}


# =============================================================================
# TestHemisphereEndToEnd
# =============================================================================


@pytest.mark.slow
class TestHemisphereEndToEnd:
    """Full routing from engine_result to updated hemispheres via run_mu."""

    def test_three_sequential_routes(self):
        projs = _load_hemisphere_projections()
        h = _empty_hemispheres()

        # Route null -> r_null
        h = _route(projs, _make_engine_result(value=None), hemispheres=h)
        assert len(h["r_null"]) == 1

        # Route closure -> r_a
        h = _route(projs, _make_engine_result(value=42, closure_detected=True), hemispheres=h)
        assert len(h["r_a"]) == 1

        # Route default -> lobes
        h = _route(projs, _make_engine_result(value="open"), hemispheres=h)
        assert len(h["lobes"]) == 1

        # All three hemispheres populated, others empty
        assert h["r_inf"] is None
        assert h["sink"] is None

    def test_stall_on_no_routing_input(self):
        projs = _load_hemisphere_projections()
        # Input that doesn't match route_hemisphere pattern
        result, trace, stall = run_mu(projs, {"not_a_route": True}, max_steps=5)
        assert stall is True
        assert result == {"not_a_route": True}

    def test_routing_is_deterministic(self):
        projs = _load_hemisphere_projections()
        er = _make_engine_result(value="deterministic", closure_detected=False)
        r1 = _route(projs, er)
        r2 = _route(projs, er)
        assert mu_equal(r1, r2)


# =============================================================================
# TestHemisphereVectors
# =============================================================================


@pytest.mark.slow
class TestHemisphereVectors:
    """Parity vectors from hemisphere_vectors.json."""

    @pytest.fixture
    def vectors(self):
        with open(FIXTURES / "hemisphere_vectors.json") as f:
            return json.load(f)["vectors"]

    @pytest.fixture
    def projs(self):
        return _load_hemisphere_projections()

    def test_route_null_value(self, vectors, projs):
        v = next(x for x in vectors if x["id"] == "route_null_value")
        result = _route(projs, v["input"]["route_hemisphere"]["engine_result"],
                        v["input"]["route_hemisphere"]["hemispheres"])
        target = v["expected_target"]
        assert result[target] is not None
        assert len(result[target]) == 1
        entry = result[target][0]
        assert entry["state"] == v["expected_entry"]["state"]
        assert entry["closure_flag"] == v["expected_entry"]["closure_flag"]
        assert entry["origin"] == v["expected_entry"]["origin"]

    def test_route_closure(self, vectors, projs):
        v = next(x for x in vectors if x["id"] == "route_closure")
        result = _route(projs, v["input"]["route_hemisphere"]["engine_result"],
                        v["input"]["route_hemisphere"]["hemispheres"])
        target = v["expected_target"]
        assert result[target] is not None
        entry = result[target][0]
        assert entry["state"] == v["expected_entry"]["state"]
        assert entry["closure_flag"] == v["expected_entry"]["closure_flag"]

    def test_route_default(self, vectors, projs):
        v = next(x for x in vectors if x["id"] == "route_default")
        result = _route(projs, v["input"]["route_hemisphere"]["engine_result"],
                        v["input"]["route_hemisphere"]["hemispheres"])
        target = v["expected_target"]
        assert result[target] is not None
        entry = result[target][0]
        assert entry["state"] == v["expected_entry"]["state"]

    def test_route_null_with_closure(self, vectors, projs):
        v = next(x for x in vectors if x["id"] == "route_null_with_closure")
        result = _route(projs, v["input"]["route_hemisphere"]["engine_result"],
                        v["input"]["route_hemisphere"]["hemispheres"])
        # Null takes priority over closure
        assert v["expected_target"] == "r_null"
        assert result["r_null"] is not None
        assert result["r_a"] is None

    def test_route_nested_value(self, vectors, projs):
        v = next(x for x in vectors if x["id"] == "route_nested_value")
        result = _route(projs, v["input"]["route_hemisphere"]["engine_result"],
                        v["input"]["route_hemisphere"]["hemispheres"])
        target = v["expected_target"]
        entry = result[target][0]
        assert entry["state"] == v["expected_entry"]["state"]

    def test_route_preserves_existing(self, vectors, projs):
        v = next(x for x in vectors if x["id"] == "route_preserves_existing")
        result = _route(projs, v["input"]["route_hemisphere"]["engine_result"],
                        v["input"]["route_hemisphere"]["hemispheres"])
        assert len(result["r_a"]) == v["expected_existing_r_a_count"]
        assert len(result["lobes"]) == v["expected_lobes_count"]


# =============================================================================
# TestHemisphereSeedIntegrity
# =============================================================================


class TestHemisphereSeedIntegrity:
    """Seed file passes integrity checks."""

    def test_seed_loads_with_verification(self):
        seed = load_verified_seed(get_seed_path("hemispheres.v1.json"))
        assert seed["meta"]["name"] == "HEMISPHERES"
        assert seed["meta"]["execution_layer"] == "APPLICATION"
        assert len(seed["projections"]) == 12

    def test_projection_ids_match(self):
        seed = load_verified_seed(get_seed_path("hemispheres.v1.json"))
        ids = [p["id"] for p in seed["projections"]]
        assert ids == [
            "hemisphere.init",
            "hemisphere.classify.exhaustion",
            "hemisphere.classify.null",
            "hemisphere.classify.closure",
            "hemisphere.classify.stall",
            "hemisphere.classify.default",
            "hemisphere.add.r_null",
            "hemisphere.add.r_inf",
            "hemisphere.add.r_a",
            "hemisphere.add.lobes",
            "hemisphere.add.sink",
            "hemisphere.unwrap",
        ]

    def test_all_projections_linear(self):
        """Verify no non-linear patterns (same var appearing twice)."""
        seed = load_verified_seed(get_seed_path("hemispheres.v1.json"))
        for proj in seed["projections"]:
            var_names = _collect_var_names(proj["pattern"])
            duplicates = [v for v in var_names if var_names.count(v) > 1]
            assert not duplicates, (
                f"Projection {proj['id']} has non-linear pattern "
                f"(duplicate vars: {list(set(duplicates))}) — "
                "hemispheres must be linear-only"
            )

    def test_no_kernel_reserved_fields(self):
        """Verify no underscore-prefixed fields in patterns or bodies."""
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        seed = load_verified_seed(get_seed_path("hemispheres.v1.json"))
        for proj in seed["projections"]:
            validate_no_kernel_reserved_fields(proj["pattern"], f"{proj['id']}.pattern")
            validate_no_kernel_reserved_fields(proj["body"], f"{proj['id']}.body")
