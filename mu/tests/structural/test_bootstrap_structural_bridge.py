"""Tests for Bootstrap-Structural Bridge (non-linear pattern support).

This module tests the binding conflict detection mechanism that enables
recurrence.v1 and exhaustion.v1 to run through the meta-circular kernel.

Test vectors from mu/docs/core/BootstrapStructuralBridge.v0.md.
"""

import json
import pytest
from pathlib import Path

from rcx_pi.selfhost.eval_seed import match, step
from rcx_pi.selfhost.match_mu import normalize_for_match, denormalize_from_match, bindings_to_dict
from rcx_pi.selfhost.seed_integrity import load_verified_seed


# Load seeds
BRIDGE_SEED_PATH = Path(__file__).parents[2] / "mu" / "bridge" / "bootstrap_structural.v1.json"
MATCH_V2_PATH = Path(__file__).parents[2] / "mu" / "substrate" / "match.v2.json"


def load_bridge_projections():
    """Load bootstrap_structural bridge projections."""
    with open(BRIDGE_SEED_PATH) as f:
        seed = json.load(f)
    return seed["projections"]


def load_match_with_bridge_projections():
    """Load match.v2 + bridge projections (combined at runtime)."""
    with open(MATCH_V2_PATH) as f:
        match_seed = json.load(f)
    with open(BRIDGE_SEED_PATH) as f:
        bridge_seed = json.load(f)

    # Combine: bridge projections first, then match.v2
    # Order matters: bridge.var.check_existing must intercept before match.var
    return bridge_seed["projections"] + match_seed["projections"]


def run_match_with_bridge(pattern, value, projections):
    """Run match using projections (bridge-enabled or v3)."""
    # Normalize pattern and value to Mu linked lists
    norm_pattern = normalize_for_match(pattern)
    norm_value = normalize_for_match(value)

    # Create initial match state
    state = {
        "match": {
            "pattern": norm_pattern,
            "value": norm_value
        },
        "_match_ctx": {}
    }

    # Run until terminal
    max_steps = 1000
    for _ in range(max_steps):
        new_state = step(projections, state)  # NOTE: projections first, then state
        if new_state == state:
            # Stalled
            break
        state = new_state
        # Check for terminal state
        if isinstance(state, dict) and "_mode" in state:
            if state["_mode"] == "match_done":
                break

    return state


class TestLinearParity:
    """Tests that bridge gives same results as match.v2 for linear patterns."""

    @pytest.fixture
    def projections(self):
        return load_match_with_bridge_projections()

    def test_linear_ok(self, projections):
        """Simple linear pattern match."""
        pattern = {"a": {"var": "x"}}
        value = {"a": 1}
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"
        # Check bindings contain x=1
        bindings = result["_bindings"]
        assert bindings is not None
        assert bindings["name"] == "x"
        assert bindings["value"] == 1

    def test_linear_nested(self, projections):
        """Nested linear pattern match."""
        pattern = {"outer": {"inner": {"var": "x"}}}
        value = {"outer": {"inner": 42}}
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"
        bindings = result["_bindings"]
        assert bindings["name"] == "x"
        assert bindings["value"] == 42

    def test_linear_list(self, projections):
        """List pattern with two different variables."""
        pattern = [{"var": "h"}, {"var": "t"}]
        value = [1, 2]
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"

    def test_linear_catchall(self, projections):
        """Catch-all variable pattern."""
        pattern = {"var": "x"}
        value = {"complex": [1, 2, 3]}
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"
        bindings = result["_bindings"]
        assert bindings["name"] == "x"
        # Value is in normalized form - denormalize to compare
        assert denormalize_from_match(bindings["value"]) == {"complex": [1, 2, 3]}

    def test_linear_empty_dict(self, projections):
        """Matching empty dict value."""
        pattern = {"a": {"var": "x"}}
        value = {"a": {}}
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"
        bindings = result["_bindings"]
        assert bindings["name"] == "x"
        # Value is in normalized form - denormalize to compare
        assert denormalize_from_match(bindings["value"]) == {}


class TestNonLinearDetection:
    """Tests for non-linear pattern (same variable twice) binding conflict detection."""

    @pytest.fixture
    def projections(self):
        return load_match_with_bridge_projections()

    def test_nonlinear_same(self, projections):
        """Same variable twice with matching values -> match."""
        pattern = {"a": {"var": "x"}, "b": {"var": "x"}}
        value = {"a": 1, "b": 1}
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"

    def test_nonlinear_diff(self, projections):
        """Same variable twice with different values -> NO_MATCH."""
        pattern = {"a": {"var": "x"}, "b": {"var": "x"}}
        value = {"a": 1, "b": 2}
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "no_match"

    def test_nested_nonlinear(self, projections):
        """Nested structure with non-linear pattern."""
        pattern = {"outer": {"inner": {"var": "x"}, "check": {"var": "x"}}}
        value = {"outer": {"inner": 5, "check": 5}}
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"

    def test_triple_same(self, projections):
        """Three occurrences of same variable with matching values."""
        pattern = {"a": {"var": "x"}, "b": {"var": "x"}, "c": {"var": "x"}}
        value = {"a": 1, "b": 1, "c": 1}
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"

    def test_triple_one_diff(self, projections):
        """Three occurrences with one different -> NO_MATCH."""
        pattern = {"a": {"var": "x"}, "b": {"var": "x"}, "c": {"var": "x"}}
        value = {"a": 1, "b": 1, "c": 2}
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "no_match"

    def test_nonlinear_list(self, projections):
        """List with same variable twice - matching values."""
        pattern = [{"var": "x"}, {"var": "x"}]
        value = [42, 42]
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"

    def test_nonlinear_list_diff(self, projections):
        """List with same variable twice - different values -> NO_MATCH."""
        pattern = [{"var": "x"}, {"var": "x"}]
        value = [42, 43]
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "no_match"

    def test_nonlinear_complex(self, projections):
        """Non-linear with complex nested values (structural equality)."""
        pattern = {"a": {"var": "x"}, "b": {"var": "x"}}
        value = {"a": {"nested": [1]}, "b": {"nested": [1]}}
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"


class TestEdgeCases:
    """Edge case tests for the bridge."""

    @pytest.fixture
    def projections(self):
        return load_match_with_bridge_projections()

    def test_empty_bindings_first(self, projections):
        """First variable with empty bindings."""
        pattern = {"var": "x"}
        value = 5
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"
        assert result["_bindings"]["name"] == "x"
        assert result["_bindings"]["value"] == 5

    def test_null_value_binding(self, projections):
        """Non-linear with null values - should match."""
        pattern = {"a": {"var": "x"}, "b": {"var": "x"}}
        value = {"a": None, "b": None}
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"

    def test_empty_list_match(self, projections):
        """Non-linear with empty list values."""
        pattern = {"a": {"var": "x"}, "b": {"var": "x"}}
        value = {"a": [], "b": []}
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"

    def test_type_mismatch(self, projections):
        """Different types for same variable -> NO_MATCH."""
        pattern = {"a": {"var": "x"}, "b": {"var": "x"}}
        # List vs dict with same "shape" but different types
        value = {"a": [1], "b": {"0": 1}}
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "no_match"


class TestSecurityVectors:
    """Security-focused tests for the bridge."""

    @pytest.fixture
    def projections(self):
        return load_match_with_bridge_projections()

    def test_reserved_var_ok(self, projections):
        """Variable named like reserved field - should work (var name is user data)."""
        pattern = {"a": {"var": "_mode"}}
        value = {"a": "test"}
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"
        assert result["_bindings"]["name"] == "_mode"
        assert result["_bindings"]["value"] == "test"

    def test_ordering_critical(self, projections):
        """Verify ordering: found_same before found_different."""
        # If ordering is wrong, this would incorrectly NO_MATCH
        pattern = {"a": {"var": "x"}, "b": {"var": "x"}}
        value = {"a": 1, "b": 1}
        result = run_match_with_bridge(pattern, value, projections)

        # Should match because values are equal
        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"

    def test_lookup_injection_rejected(self):
        """Domain data with _lookup_name is rejected at kernel boundary."""
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        # Vector from BootstrapStructuralBridge.v0.md - domain input with bridge reserved field
        malicious = {"_lookup_name": "x", "data": 1}

        with pytest.raises(ValueError, match="SECURITY.*_lookup_name"):
            validate_no_kernel_reserved_fields(malicious, "domain input")

    def test_lookup_value_injection_rejected(self):
        """Domain data with _lookup_value is rejected at kernel boundary."""
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        malicious = {"_lookup_value": 42, "data": 1}

        with pytest.raises(ValueError, match="SECURITY.*_lookup_value"):
            validate_no_kernel_reserved_fields(malicious, "domain input")

    def test_lookup_bindings_injection_rejected(self):
        """Domain data with _lookup_bindings is rejected at kernel boundary."""
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        malicious = {"_lookup_bindings": None, "data": 1}

        with pytest.raises(ValueError, match="SECURITY.*_lookup_bindings"):
            validate_no_kernel_reserved_fields(malicious, "domain input")

    def test_original_bindings_injection_rejected(self):
        """Domain data with _original_bindings is rejected at kernel boundary."""
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        malicious = {"_original_bindings": {"fake": "binding"}, "data": 1}

        with pytest.raises(ValueError, match="SECURITY.*_original_bindings"):
            validate_no_kernel_reserved_fields(malicious, "domain input")


class TestCrossSubstrateParity:
    """Tests for Python/JS parity vectors."""

    @pytest.fixture
    def projections(self):
        return load_match_with_bridge_projections()

    def test_parity_unicode(self, projections):
        """Unicode values with non-linear pattern."""
        pattern = {"a": {"var": "x"}, "b": {"var": "x"}}
        value = {"a": "🎉", "b": "🎉"}
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"

    def test_parity_float(self, projections):
        """Float values with non-linear pattern."""
        pattern = {"a": {"var": "x"}, "b": {"var": "x"}}
        value = {"a": 3.14159, "b": 3.14159}
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"

    def test_parity_deep(self, projections):
        """Deep nesting with non-linear pattern."""
        pattern = {
            "level1": {
                "level2": {
                    "first": {"var": "x"},
                    "second": {"var": "x"}
                }
            }
        }
        value = {
            "level1": {
                "level2": {
                    "first": {"deep": "value"},
                    "second": {"deep": "value"}
                }
            }
        }
        result = run_match_with_bridge(pattern, value, projections)

        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"


class TestBridgeSeedStructure:
    """Tests for bridge seed file structure."""

    def test_bridge_seed_exists(self):
        """Bridge seed file exists."""
        assert BRIDGE_SEED_PATH.exists()

    def test_bridge_seed_valid_json(self):
        """Bridge seed is valid JSON."""
        with open(BRIDGE_SEED_PATH) as f:
            seed = json.load(f)
        assert "meta" in seed
        assert "projections" in seed

    def test_bridge_seed_projection_count(self):
        """Bridge seed has expected number of projections."""
        with open(BRIDGE_SEED_PATH) as f:
            seed = json.load(f)
        # 5 projections per design doc
        assert len(seed["projections"]) == 5

    def test_bridge_seed_projection_ids(self):
        """Bridge projections have correct IDs."""
        projections = load_bridge_projections()
        ids = [p["id"] for p in projections]

        expected = [
            "bridge.var.check_existing",
            "bridge.lookup.found_same",
            "bridge.lookup.found_different",
            "bridge.lookup.not_found_yet",
            "bridge.lookup.not_found"
        ]
        assert ids == expected

    def test_combined_projections_count(self):
        """Combined projections have expected count (bridge + match.v2)."""
        projections = load_match_with_bridge_projections()
        # 5 (bridge) + 8 (match.v2) = 13
        assert len(projections) == 13

    def test_combined_has_bridge_projections(self):
        """Combined projections include all bridge projections."""
        projections = load_match_with_bridge_projections()
        ids = [p["id"] for p in projections]
        assert "bridge.var.check_existing" in ids
        assert "bridge.lookup.found_same" in ids
        assert "bridge.lookup.found_different" in ids
        assert "bridge.lookup.not_found_yet" in ids
        assert "bridge.lookup.not_found" in ids

    def test_bridge_before_match_var(self):
        """Bridge projections come before match.var for proper interception."""
        projections = load_match_with_bridge_projections()
        ids = [p["id"] for p in projections]
        bridge_idx = ids.index("bridge.var.check_existing")
        match_var_idx = ids.index("match.var")
        assert bridge_idx < match_var_idx, "bridge.var.check_existing must come before match.var"


class TestProjectionOrdering:
    """Tests that verify security-critical projection ordering."""

    def test_found_same_before_found_different(self):
        """bridge.lookup.found_same must come before bridge.lookup.found_different."""
        projections = load_bridge_projections()
        ids = [p["id"] for p in projections]

        same_idx = ids.index("bridge.lookup.found_same")
        diff_idx = ids.index("bridge.lookup.found_different")

        assert same_idx < diff_idx, "found_same must come before found_different"

    def test_combined_projection_order(self):
        """Combined projections maintain security-critical ordering."""
        projections = load_match_with_bridge_projections()
        ids = [p["id"] for p in projections]

        same_idx = ids.index("bridge.lookup.found_same")
        diff_idx = ids.index("bridge.lookup.found_different")
        fail_idx = ids.index("match.fail")
        wrap_idx = ids.index("match.wrap")

        # found_same before found_different
        assert same_idx < diff_idx
        # match.fail before match.wrap (wrap is entry point, must be last)
        assert fail_idx < wrap_idx
