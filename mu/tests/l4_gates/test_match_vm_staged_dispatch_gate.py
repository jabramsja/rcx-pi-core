"""
Wave 3C gate test: match_mu staged bridge->match per-step VM dispatch.

Verifies that match_mu() now executes via staged dispatch using
stage0_vm_step with compiled match_v2 + bootstrap_structural_v1 bundles.
Bridge gets first-match priority every step; match bundle fires second.
This mirrors the kernel dispatch strategy for non-linear conflict detection.
"""

from __future__ import annotations

import json

import pytest

from rcx_pi.selfhost.match_mu import match_mu
from rcx_pi.selfhost.match_mu import _load_match_bundle  # ANTICHEAT_OK: test-only — gate test for bundle loading + provenance
from rcx_pi.selfhost.match_mu import _clear_match_bundle  # ANTICHEAT_OK: test-only — cache clear for provenance test
from rcx_pi.selfhost.match_mu import _load_bridge_bundle  # ANTICHEAT_OK: test-only — gate test for bridge bundle loading
from rcx_pi.selfhost.match_mu import _clear_bridge_bundle  # ANTICHEAT_OK: test-only — cache clear for bridge provenance test
from rcx_pi.selfhost.match_mu import _validate_match_bridge_ordering  # ANTICHEAT_OK: test-only — ordering invariant negative control
from rcx_pi.selfhost.eval_seed import NO_MATCH


class TestMatchVMStagedDispatchGate:
    """Evidence that match_mu uses staged bridge->match VM dispatch."""

    # ------------------------------------------------------------------
    # 1. Simple success — match.done + match.equal (literal match)
    # ------------------------------------------------------------------

    def test_literal_match_returns_empty_bindings(self):
        """Literal equality (no vars) returns empty bindings dict."""
        result = match_mu(42, 42)
        assert result == {}

    def test_string_literal_match(self):
        """String literal match returns empty bindings."""
        result = match_mu("hello", "hello")
        assert result == {}

    def test_bool_literal_match(self):
        """Boolean literal match returns empty bindings."""
        assert match_mu(True, True) == {}
        assert match_mu(False, False) == {}

    def test_null_literal_match(self):
        """Null literal match returns empty bindings."""
        assert match_mu(None, None) == {}

    # ------------------------------------------------------------------
    # 2. Variable binding — bridge.var.check_existing produces bindings
    # ------------------------------------------------------------------

    def test_single_variable_binding(self):
        """Single var pattern binds value through bridge dispatch."""
        result = match_mu({"var": "x"}, 42)
        assert result == {"x": 42}

    def test_dict_with_variable_binding(self):
        """Dict pattern with var produces correct bindings."""
        result = match_mu({"a": {"var": "x"}, "b": 2}, {"a": 1, "b": 2})
        assert result == {"x": 1}

    def test_multiple_variable_bindings(self):
        """Multiple distinct vars bind correctly through bridge."""
        result = match_mu(
            {"x": {"var": "a"}, "y": {"var": "b"}},
            {"x": 1, "y": 2},
        )
        assert result == {"a": 1, "b": 2}

    def test_nested_dict_variable_binding(self):
        """Nested dict pattern binds correctly through staged dispatch."""
        result = match_mu(
            {"outer": {"inner": {"var": "v"}}},
            {"outer": {"inner": 99}},
        )
        assert result == {"v": 99}

    # ------------------------------------------------------------------
    # 3. NO_MATCH — match.fail (pattern doesn't match value)
    # ------------------------------------------------------------------

    def test_literal_mismatch_returns_no_match(self):
        """Different literals produce NO_MATCH via match.fail."""
        assert match_mu(42, 43) is NO_MATCH

    def test_string_mismatch_returns_no_match(self):
        """Different strings produce NO_MATCH."""
        assert match_mu("hello", "world") is NO_MATCH

    def test_structure_mismatch_returns_no_match(self):
        """Dict pattern vs scalar value produces NO_MATCH."""
        assert match_mu({"a": 1}, 42) is NO_MATCH

    def test_bool_mismatch_returns_no_match(self):
        """Boolean mismatch produces NO_MATCH."""
        assert match_mu(True, False) is NO_MATCH

    # ------------------------------------------------------------------
    # 4. Non-linear conflict rejection — bridge.lookup.found_different
    #    Same var bound to different values -> NO_MATCH
    # ------------------------------------------------------------------

    def test_nonlinear_conflict_rejection(self):
        """Same var, different values -> NO_MATCH via bridge conflict detection."""
        result = match_mu(
            {"a": {"var": "x"}, "b": {"var": "x"}},
            {"a": 1, "b": 2},
        )
        assert result is NO_MATCH

    def test_nonlinear_nested_conflict_rejection(self):
        """Nested non-linear conflict -> NO_MATCH via bridge.lookup.found_different."""
        result = match_mu(
            {"x": {"var": "v"}, "y": {"nested": {"var": "v"}}},
            {"x": 1, "y": {"nested": 2}},
        )
        assert result is NO_MATCH

    # ------------------------------------------------------------------
    # 5. Non-linear agreement success — bridge.lookup.found_same
    #    Same var bound to same value -> success
    # ------------------------------------------------------------------

    def test_nonlinear_agreement_success(self):
        """Same var, same values -> success via bridge.lookup.found_same."""
        result = match_mu(
            {"a": {"var": "x"}, "b": {"var": "x"}},
            {"a": 1, "b": 1},
        )
        assert result == {"x": 1}

    def test_nonlinear_agreement_complex_value(self):
        """Non-linear agreement with complex (dict) values succeeds."""
        result = match_mu(
            {"a": {"var": "x"}, "b": {"var": "x"}},
            {"a": {"nested": 42}, "b": {"nested": 42}},
        )
        assert result == {"x": {"nested": 42}}

    # ------------------------------------------------------------------
    # 6. match.sibling coverage — list matching exercises sibling traversal
    # ------------------------------------------------------------------

    def test_var_matches_empty_list(self):
        """Variable binds to empty list (sibling traversal boundary case)."""
        result = match_mu({"var": "x"}, [])
        assert result == {"x": []}

    def test_list_structure_mismatch(self):
        """Empty list vs empty dict produces NO_MATCH (type distinction)."""
        assert match_mu([], {}) is NO_MATCH

    def test_dict_with_list_value(self):
        """Dict containing list value matches through sibling traversal."""
        result = match_mu(
            {"items": {"var": "xs"}},
            {"items": [1, 2, 3]},
        )
        assert result == {"xs": [1, 2, 3]}

    # ------------------------------------------------------------------
    # 7. Bridge ordering negative control
    # ------------------------------------------------------------------

    def test_validate_bridge_ordering_rejects_wrong_order(self):
        """_validate_match_bridge_ordering raises on bridge after match.var."""
        # Construct projections with wrong ordering: match.var BEFORE bridge
        wrong_order = [
            {"id": "match.done"},
            {"id": "match.var"},  # match.var at index 1
            {"id": "bridge.var.check_existing"},  # bridge at index 2 (wrong!)
        ]
        with pytest.raises(ValueError, match="INVARIANT VIOLATION.*must come before"):
            _validate_match_bridge_ordering(wrong_order)

    def test_validate_bridge_ordering_rejects_missing_bridge(self):
        """_validate_match_bridge_ordering raises when bridge projection is missing."""
        missing_bridge = [
            {"id": "match.done"},
            {"id": "match.var"},
        ]
        with pytest.raises(ValueError, match="bridge.var.check_existing not found"):
            _validate_match_bridge_ordering(missing_bridge)

    def test_validate_bridge_ordering_rejects_missing_match_var(self):
        """_validate_match_bridge_ordering raises when match.var is missing."""
        missing_match_var = [
            {"id": "match.done"},
            {"id": "bridge.var.check_existing"},
        ]
        with pytest.raises(ValueError, match="match.var not found"):
            _validate_match_bridge_ordering(missing_match_var)

    def test_validate_bridge_ordering_accepts_correct_order(self):
        """_validate_match_bridge_ordering passes with correct ordering."""
        correct_order = [
            {"id": "match.done"},
            {"id": "bridge.var.check_existing"},  # bridge at index 1
            {"id": "match.var"},  # match.var at index 2 (correct!)
        ]
        # Should not raise
        _validate_match_bridge_ordering(correct_order)

    # ------------------------------------------------------------------
    # 8. Compiled match bundle loads and validates
    # ------------------------------------------------------------------

    def test_match_bundle_loads_and_validates(self):
        """Compiled match_v2 bundle loads and validates."""
        bundle = _load_match_bundle()
        assert isinstance(bundle, dict)
        assert "programs" in bundle
        assert len(bundle["programs"]) > 0

    def test_bridge_bundle_loads_and_validates(self):
        """Compiled bootstrap_structural_v1 bundle loads and validates."""
        bundle = _load_bridge_bundle()
        assert isinstance(bundle, dict)
        assert "programs" in bundle
        assert len(bundle["programs"]) > 0

    def test_both_bundles_have_program_order(self):
        """Both bundles have program_order for staged dispatch."""
        match_bundle = _load_match_bundle()
        bridge_bundle = _load_bridge_bundle()
        assert "program_order" in match_bundle
        assert "program_order" in bridge_bundle
        assert len(match_bundle["program_order"]) > 0
        assert len(bridge_bundle["program_order"]) > 0

    # ------------------------------------------------------------------
    # 9. Bundle provenance rejects wrong digest
    # ------------------------------------------------------------------

    def test_match_bundle_provenance_rejects_wrong_digest(self):
        """N15: wrong source_digest raises ValueError for match bundle."""
        from rcx_pi.selfhost.seed_integrity import SEED_CHECKSUMS
        import rcx_pi.selfhost.match_mu as match_mod  # ANTICHEAT_OK: test-only — module-level access for provenance test

        bundle = _load_match_bundle()
        source_seed = bundle.get("source_seed", "")
        seed_filename = source_seed if source_seed.endswith(".json") else source_seed + ".json"
        assert seed_filename in SEED_CHECKSUMS, f"{seed_filename} must be in SEED_CHECKSUMS"

        # Tamper with digest and verify rejection
        tampered = dict(bundle)
        tampered["source_digest"] = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        match_mod._clear_match_bundle()  # ANTICHEAT_OK: test-only — clear factory cache

        import unittest.mock
        with unittest.mock.patch("builtins.open", unittest.mock.mock_open(read_data=json.dumps(tampered))):
            with pytest.raises(ValueError, match="SECURITY.*provenance mismatch"):
                match_mod._load_match_bundle()  # ANTICHEAT_OK: test-only — verifying provenance rejection

        # Restore cache
        match_mod._clear_match_bundle()  # ANTICHEAT_OK: test-only — clear for reload
        match_mod._load_match_bundle()  # ANTICHEAT_OK: test-only — restore valid bundle

    def test_bridge_bundle_provenance_rejects_wrong_digest(self):
        """N15: wrong source_digest raises ValueError for bridge bundle."""
        from rcx_pi.selfhost.seed_integrity import SEED_CHECKSUMS
        import rcx_pi.selfhost.match_mu as match_mod  # ANTICHEAT_OK: test-only — module-level access for provenance test

        bundle = _load_bridge_bundle()
        source_seed = bundle.get("source_seed", "")
        seed_filename = source_seed if source_seed.endswith(".json") else source_seed + ".json"
        assert seed_filename in SEED_CHECKSUMS, f"{seed_filename} must be in SEED_CHECKSUMS"

        tampered = dict(bundle)
        tampered["source_digest"] = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        match_mod._clear_bridge_bundle()  # ANTICHEAT_OK: test-only — clear factory cache

        import unittest.mock
        with unittest.mock.patch("builtins.open", unittest.mock.mock_open(read_data=json.dumps(tampered))):
            with pytest.raises(ValueError, match="SECURITY.*provenance mismatch"):
                match_mod._load_bridge_bundle()  # ANTICHEAT_OK: test-only — verifying provenance rejection

        # Restore cache
        match_mod._clear_bridge_bundle()  # ANTICHEAT_OK: test-only — clear for reload
        match_mod._load_bridge_bundle()  # ANTICHEAT_OK: test-only — restore valid bundle

    # ------------------------------------------------------------------
    # 10. VM fault propagation (staged dispatch path)
    # ------------------------------------------------------------------

    def test_vm_fault_propagates_from_staged_dispatch(self):
        """Stage0VMError from stage0_vm_step must propagate, not be swallowed."""
        from rcx_pi.selfhost.stage0_vm import Stage0VMError  # ANTICHEAT_OK: test-only — error class for fault test
        import unittest.mock

        fake_error = Stage0VMError("Op limit exceeded (test)")
        with unittest.mock.patch(
            "rcx_pi.selfhost.stage0_vm.stage0_vm_step",
            side_effect=fake_error,
        ):
            with pytest.raises(Stage0VMError, match="Op limit exceeded"):
                match_mu(42, 42)
