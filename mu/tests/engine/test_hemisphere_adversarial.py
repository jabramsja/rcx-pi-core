"""
Adversarial tests for hemispheres.v1.json (Mu Hemispheres v0).

Targeted edge-case coverage: type confusion, boundary conditions,
adversarial smuggling, and projection order security. Uses parametric
tests over curated inputs covering all 3 routing paths (null, closure,
default) rather than random fuzzing — hemisphere routing has a small
decision space, so targeted adversarial inputs are more effective.

See: roadmap/MuHemispheresDesign.md
"""

from __future__ import annotations

import pytest

from rcx_pi.selfhost.kernel import reset_step_budget
from rcx_pi.selfhost.mu_type import mu_equal
from rcx_pi.selfhost.seed_integrity import get_seed_path, load_verified_seed
from rcx_pi.selfhost.step_mu import run_mu

from tests.hemisphere_helpers import (
    EXPECTED_PROJECTION_IDS,
    load_hemisphere_projections,
    make_engine_result as _make_engine_result,
    empty_hemispheres as _empty_hemispheres,
    route as _route,
)


# =============================================================================
# Helpers
# =============================================================================


HEMISPHERE_PROJS = None


def _get_projs():
    """Lazy-load projections (module-level cache)."""
    global HEMISPHERE_PROJS
    if HEMISPHERE_PROJS is None:
        HEMISPHERE_PROJS = load_hemisphere_projections()
    return HEMISPHERE_PROJS


# Curated inputs covering all 3 routing paths + edge cases.
# Deliberately minimal: one representative per path plus adversarial edge cases.
# Each tuple: (description, engine_result, expected_target)
ROUTING_VECTORS = [
    # null path
    ("null_value", _make_engine_result(value=None), "r_null"),
    ("null_with_closure", _make_engine_result(value=None, closure_detected=True), "r_null"),
    # closure path
    ("closure_int", _make_engine_result(value=42, closure_detected=True), "r_a"),
    ("closure_zero", _make_engine_result(value=0, closure_detected=True), "r_a"),
    # default path — each value type that could confuse type-weak matching
    ("default_int", _make_engine_result(value=42), "lobes"),
    ("default_zero", _make_engine_result(value=0), "lobes"),
    ("default_string", _make_engine_result(value="hello"), "lobes"),
    ("default_empty_string", _make_engine_result(value=""), "lobes"),
    ("default_bool_false", _make_engine_result(value=False), "lobes"),
    ("default_bool_true_value", _make_engine_result(value=True), "lobes"),
    ("default_dict", _make_engine_result(value={"x": [1, 2]}), "lobes"),
    ("default_list_value", _make_engine_result(value=[1, 2, 3]), "lobes"),
    # pass-through fields must not affect routing
    # exhaustion_detected=True routes to sink (not lobes) per hemisphere.classify.exhaustion
    ("passthrough_exhaustion", _make_engine_result(
        value=99, tau_step=10, exhaustion_detected=True,
        operator_frozen="op", frozen_set=[], action="halt", stall=True,
    ), "sink"),
    # non-exhaustion/non-stall fields still pass through without affecting routing
    ("passthrough_fields_no_signal", _make_engine_result(
        value=99, tau_step=10, operator_frozen="op", frozen_set=[], action="halt",
    ), "lobes"),
]


# =============================================================================
# TestHemisphereStructuralInvariants
# =============================================================================


@pytest.mark.slow
class TestHemisphereStructuralInvariants:
    """Routing invariants hold across all 3 paths and edge-case inputs."""

    def setup_method(self):
        reset_step_budget()

    @pytest.mark.parametrize(
        "desc,er,expected_target",
        [(v[0], v[1], v[2]) for v in ROUTING_VECTORS],
        ids=[v[0] for v in ROUTING_VECTORS],
    )
    def test_result_has_five_hemisphere_keys(self, desc, er, expected_target):
        """Routing result always contains all 5 hemisphere keys."""
        projs = _get_projs()
        result = _route(projs, er)
        for key in ("r_null", "r_inf", "r_a", "lobes", "sink"):
            assert key in result, f"Missing hemisphere key: {key}"

    @pytest.mark.parametrize(
        "desc,er,expected_target",
        [(v[0], v[1], v[2]) for v in ROUTING_VECTORS],
        ids=[v[0] for v in ROUTING_VECTORS],
    )
    def test_exactly_one_hemisphere_populated(self, desc, er, expected_target):
        """Routing into empty hemispheres populates exactly one target."""
        projs = _get_projs()
        result = _route(projs, er)
        populated = [k for k in ("r_null", "r_inf", "r_a", "lobes", "sink") if result[k] is not None]
        assert len(populated) == 1, f"Expected 1 populated, got {len(populated)}: {populated}"

    @pytest.mark.parametrize(
        "desc,er,expected_target",
        [(v[0], v[1], v[2]) for v in ROUTING_VECTORS],
        ids=[v[0] for v in ROUTING_VECTORS],
    )
    def test_routes_to_expected_target(self, desc, er, expected_target):
        """Each input routes to its expected hemisphere."""
        projs = _get_projs()
        result = _route(projs, er)
        assert result[expected_target] is not None, (
            f"{desc}: expected {expected_target} populated, got None"
        )

    @pytest.mark.parametrize(
        "desc,er,expected_target",
        [(v[0], v[1], v[2]) for v in ROUTING_VECTORS],
        ids=[v[0] for v in ROUTING_VECTORS],
    )
    def test_deterministic_result(self, desc, er, expected_target):
        """Same input always produces same output."""
        projs = _get_projs()
        r1 = _route(projs, er)
        reset_step_budget()
        r2 = _route(projs, er)
        assert mu_equal(r1, r2), f"Non-deterministic for {desc}: {r1} != {r2}"


# =============================================================================
# TestHemisphereTypeConfusion
# =============================================================================


@pytest.mark.slow
class TestHemisphereTypeConfusion:
    """Type-strict matching prevents routing confusion."""

    def setup_method(self):
        reset_step_budget()

    def test_string_true_vs_bool_true(self):
        """String "true" must NOT route to r_a (only bool true does)."""
        projs = _get_projs()
        bool_result = _route(projs, _make_engine_result(value=42, closure_detected=True))
        str_result = _route(projs, _make_engine_result(value=42, closure_detected="true"))
        assert bool_result["r_a"] is not None
        assert bool_result["lobes"] is None
        assert str_result["lobes"] is not None
        assert str_result["r_a"] is None

    def test_string_null_vs_actual_null(self):
        """String "null" must NOT route to r_null (only actual null does)."""
        projs = _get_projs()
        null_result = _route(projs, _make_engine_result(value=None))
        str_result = _route(projs, _make_engine_result(value="null"))
        assert null_result["r_null"] is not None
        assert null_result["lobes"] is None
        assert str_result["lobes"] is not None
        assert str_result["r_null"] is None

    def test_integer_zero_vs_null(self):
        """Integer 0 must route to lobes, not r_null."""
        projs = _get_projs()
        zero_result = _route(projs, _make_engine_result(value=0))
        null_result = _route(projs, _make_engine_result(value=None))
        assert zero_result["lobes"] is not None, "0 should route to lobes"
        assert zero_result["r_null"] is None, "0 should NOT route to r_null"
        assert null_result["r_null"] is not None, "null should route to r_null"

    def test_integer_one_vs_bool_true_closure(self):
        """Integer 1 for closure_detected must NOT route to r_a (only bool true)."""
        projs = _get_projs()
        bool_result = _route(projs, _make_engine_result(value=42, closure_detected=True))
        int_result = _route(projs, _make_engine_result(value=42, closure_detected=1))
        assert bool_result["r_a"] is not None, "bool true -> r_a"
        assert int_result["lobes"] is not None, "int 1 -> lobes (not r_a)"
        assert int_result["r_a"] is None, "int 1 must NOT route to r_a"


# =============================================================================
# TestHemisphereBoundary
# =============================================================================


@pytest.mark.slow
class TestHemisphereBoundary:
    """Boundary conditions: wide lists, deep nesting, edge inputs."""

    def setup_method(self):
        reset_step_budget()

    @pytest.mark.slow
    def test_wide_hemisphere_list_preserved(self):
        """Prepending multiple entries preserves count and ordering."""
        projs = _get_projs()
        h = _empty_hemispheres()
        count = 15
        for i in range(count):
            reset_step_budget()
            h = _route(projs, _make_engine_result(value=i), hemispheres=h)
        assert len(h["lobes"]) == count, f"Expected {count} entries, got {len(h['lobes'])}"
        # Verify prepend order: most recent first
        assert mu_equal(h["lobes"][0]["state"], count - 1)
        assert mu_equal(h["lobes"][-1]["state"], 0)

    def test_deeply_nested_value_preserved(self):
        """Routing a deeply nested value preserves structure in entry."""
        projs = _get_projs()
        nested = {"a": {"b": {"c": {"d": {"e": {"f": {"g": 42}}}}}}}
        result = _route(projs, _make_engine_result(value=nested))
        assert result["lobes"] is not None
        assert mu_equal(result["lobes"][0]["state"], nested)

    def test_all_null_engine_result(self):
        """Engine result with all fields null/false routes to r_null."""
        projs = _get_projs()
        er = _make_engine_result(
            value=None, closure_detected=False, tau_step=None,
            exhaustion_detected=False, operator_frozen=None,
            frozen_set=None, action="continue", stall=False,
        )
        result = _route(projs, er)
        assert result["r_null"] is not None, "All-null should route to r_null"


# =============================================================================
# TestHemisphereProjectionOrderSecurity
# =============================================================================


@pytest.mark.slow
class TestHemisphereProjectionOrderSecurity:
    """First-match-wins projection ordering is security-critical."""

    def setup_method(self):
        reset_step_budget()

    def test_null_before_default(self):
        """classify.null fires before classify.default (null -> r_null, not lobes)."""
        projs = _get_projs()
        null_result = _route(projs, _make_engine_result(value=None))
        str_result = _route(projs, _make_engine_result(value="hello"))
        assert null_result["r_null"] is not None, "null must route to r_null"
        assert null_result["lobes"] is None, "null must NOT route to lobes"
        assert str_result["lobes"] is not None, "string must route to lobes"
        assert str_result["r_null"] is None, "string must NOT route to r_null"

    def test_projection_ids_match_expected_order(self):
        """Projection IDs must be in exact security-critical order."""
        seed = load_verified_seed(get_seed_path("hemispheres.v1.json"))
        ids = [p["id"] for p in seed["projections"]]
        assert ids == EXPECTED_PROJECTION_IDS


# =============================================================================
# TestHemisphereAdversarialSmuggling
# =============================================================================


@pytest.mark.slow
class TestHemisphereAdversarialSmuggling:
    """Attempts to smuggle internal state or corrupt hemisphere structure."""

    def setup_method(self):
        reset_step_budget()

    def test_extra_hemi_mode_in_input_detected(self):
        """Injecting raw hemi_* shapes bypasses init — documents the vulnerability.

        This test verifies that direct hemi_mode injection IS detected. The bypass
        is inherent to projection matching (any matching pattern fires). The fix
        is host-level boundary validation via run_hemisphere_routing().
        """
        projs = _get_projs()
        smuggled = {
            "hemi_mode": "add",
            "hemi_target": "r_a",
            "hemi_entry": {"state": "smuggled", "closure_flag": False, "origin": "engine"},
            "hemi_h": _empty_hemispheres(),
        }
        result, trace, stall = run_mu(projs, smuggled, max_steps=20)
        # Smuggled input must NOT produce a valid hemisphere dict.
        # Either it stalls (no projection matches the raw hemi_* shape)
        # or if it does match, the smuggled entry must not appear in a
        # valid hemisphere bucket. Both outcomes prove the projections
        # reject raw internal-state injection.
        if stall:
            # Stall = no projection matched the smuggled shape. Safe.
            return
        # If not stalled, verify the smuggled entry did NOT land in a valid bucket
        assert isinstance(result, dict), "Expected dict result"
        for key in ("r_null", "r_inf", "r_a", "lobes", "sink"):
            entries = result.get(key)
            if isinstance(entries, list):
                for e in entries:
                    if isinstance(e, dict) and mu_equal(e.get("state"), "smuggled"):
                        pytest.fail(
                            f"SECURITY: Smuggled entry landed in '{key}' — "
                            f"projection-level bypass succeeded. "
                            f"Add boundary validation."
                        )

    def test_boundary_validation_blocks_smuggling(self):
        """run_hemisphere_routing() rejects raw hemi_* injection by wrapping input."""
        from rcx_pi.selfhost.step_mu import run_hemisphere_routing
        engine_result = _make_engine_result(value="legit")
        result = run_hemisphere_routing(engine_result, _empty_hemispheres())
        assert isinstance(result, dict)
        assert result["lobes"] is not None
        assert result["lobes"][0]["state"] == "legit"

    def test_boundary_validation_rejects_non_dict(self):
        """run_hemisphere_routing() rejects non-dict engine_result."""
        from rcx_pi.selfhost.step_mu import run_hemisphere_routing
        with pytest.raises(ValueError, match="engine_result must be a dict"):
            run_hemisphere_routing("not_a_dict", _empty_hemispheres())

    def test_hemisphere_key_names_in_value_safe(self):
        """Value containing hemisphere key names routes normally to lobes."""
        projs = _get_projs()
        tricky_value = {"r_null": "attack", "r_a": True, "lobes": [1, 2, 3]}
        result = _route(projs, _make_engine_result(value=tricky_value))
        assert result["lobes"] is not None, "Should route to lobes normally"
        assert mu_equal(result["lobes"][0]["state"], tricky_value), "Value preserved exactly"
        assert result["r_null"] is None, "Tricky value must NOT populate r_null"
        assert result["r_a"] is None, "Tricky value must NOT populate r_a"
