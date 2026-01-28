"""
Projection Order Security Tests - Phase 7a

These tests verify that projection order enforcement works correctly.
Projection order is SECURITY-CRITICAL: kernel projections MUST run before
domain projections to prevent domain data from forging kernel state.

See docs/core/MetaCircularKernel.v0.md for design.
"""

import pytest

from rcx_pi.selfhost.step_mu import (
    is_kernel_projection,
    validate_kernel_projections_first,
)
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seeds_dir


# =============================================================================
# is_kernel_projection Tests
# =============================================================================

class TestIsKernelProjection:
    """Test kernel projection detection."""

    def test_kernel_projection_by_id(self):
        """Projections with kernel.* ID are kernel projections."""
        proj = {"id": "kernel.wrap", "pattern": {}, "body": {}}
        assert is_kernel_projection(proj) is True

    def test_kernel_projection_by_mode_pattern(self):
        """Projections with _mode in pattern are kernel projections."""
        proj = {
            "id": "some.projection",
            "pattern": {"_mode": "kernel", "_phase": "try"},
            "body": {}
        }
        assert is_kernel_projection(proj) is True

    def test_domain_projection(self):
        """Projections without kernel.* ID or _mode pattern are domain projections."""
        proj = {"id": "match.done", "pattern": {"mode": "match"}, "body": {}}
        assert is_kernel_projection(proj) is False

    def test_domain_projection_no_id(self):
        """Projections without ID field are domain projections (unless _mode pattern)."""
        proj = {"pattern": {"x": {"var": "v"}}, "body": {"result": {"var": "v"}}}
        assert is_kernel_projection(proj) is False

    def test_invalid_projection_type(self):
        """Non-dict projections are not kernel projections."""
        assert is_kernel_projection("not a dict") is False
        assert is_kernel_projection(123) is False
        assert is_kernel_projection(None) is False


# =============================================================================
# validate_kernel_projections_first Tests
# =============================================================================

class TestValidateKernelProjectionsFirst:
    """Test projection order validation."""

    def test_kernel_only_passes(self):
        """List with only kernel projections passes validation."""
        kernel_projs = [
            {"id": "kernel.wrap", "pattern": {"_step": {"var": "x"}}, "body": {}},
            {"id": "kernel.stall", "pattern": {"_mode": "kernel"}, "body": {}},
        ]
        # Should not raise
        validate_kernel_projections_first(kernel_projs)

    def test_domain_only_passes(self):
        """List with only domain projections passes validation."""
        domain_projs = [
            {"id": "match.done", "pattern": {"mode": "match"}, "body": {}},
            {"id": "match.wrap", "pattern": {"x": {"var": "v"}}, "body": {}},
        ]
        # Should not raise
        validate_kernel_projections_first(domain_projs)

    def test_kernel_then_domain_passes(self):
        """Kernel projections before domain projections passes validation."""
        mixed_projs = [
            {"id": "kernel.wrap", "pattern": {"_step": {"var": "x"}}, "body": {}},
            {"id": "kernel.stall", "pattern": {"_mode": "kernel"}, "body": {}},
            {"id": "match.done", "pattern": {"mode": "match"}, "body": {}},
            {"id": "subst.done", "pattern": {"mode": "subst"}, "body": {}},
        ]
        # Should not raise
        validate_kernel_projections_first(mixed_projs)

    def test_domain_then_kernel_fails(self):
        """Domain projection before kernel projection fails validation."""
        bad_order = [
            {"id": "match.done", "pattern": {"mode": "match"}, "body": {}},
            {"id": "kernel.wrap", "pattern": {"_step": {"var": "x"}}, "body": {}},
        ]
        with pytest.raises(ValueError, match="SECURITY"):
            validate_kernel_projections_first(bad_order)

    def test_interleaved_fails(self):
        """Interleaved kernel and domain projections fails validation."""
        interleaved = [
            {"id": "kernel.wrap", "pattern": {"_step": {"var": "x"}}, "body": {}},
            {"id": "match.done", "pattern": {"mode": "match"}, "body": {}},
            {"id": "kernel.stall", "pattern": {"_mode": "kernel"}, "body": {}},
        ]
        with pytest.raises(ValueError, match="SECURITY"):
            validate_kernel_projections_first(interleaved)

    def test_empty_list_passes(self):
        """Empty projection list passes validation."""
        validate_kernel_projections_first([])

    def test_error_message_includes_projection_ids(self):
        """Error message identifies the problematic projections."""
        bad_order = [
            {"id": "domain.first", "pattern": {}, "body": {}},
            {"id": "kernel.second", "pattern": {"_mode": "x"}, "body": {}},
        ]
        with pytest.raises(ValueError) as exc_info:
            validate_kernel_projections_first(bad_order)

        error_msg = str(exc_info.value)
        assert "kernel.second" in error_msg
        assert "domain.first" in error_msg


# =============================================================================
# Integration Tests with Real Seeds
# =============================================================================

class TestRealSeedProjectionOrder:
    """Test projection order with real seed files."""

    def test_kernel_seed_all_kernel_projections(self):
        """All kernel.v1.json projections are kernel projections."""
        seed = load_verified_seed(get_seeds_dir() / "kernel.v1.json")
        projections = seed["projections"]

        for proj in projections:
            assert is_kernel_projection(proj), f"{proj['id']} should be kernel projection"

    def test_match_seed_all_domain_projections(self):
        """All match.v1.json projections are domain projections."""
        seed = load_verified_seed(get_seeds_dir() / "match.v1.json")
        projections = seed["projections"]

        for proj in projections:
            assert not is_kernel_projection(proj), f"{proj['id']} should be domain projection"

    def test_subst_seed_all_domain_projections(self):
        """All subst.v1.json projections are domain projections."""
        seed = load_verified_seed(get_seeds_dir() / "subst.v1.json")
        projections = seed["projections"]

        for proj in projections:
            assert not is_kernel_projection(proj), f"{proj['id']} should be domain projection"

    def test_combined_kernel_match_subst_valid_order(self):
        """Kernel + match + subst in correct order passes validation."""
        kernel_seed = load_verified_seed(get_seeds_dir() / "kernel.v1.json")
        match_seed = load_verified_seed(get_seeds_dir() / "match.v1.json")
        subst_seed = load_verified_seed(get_seeds_dir() / "subst.v1.json")

        # Correct order: kernel first, then domain
        combined = (
            kernel_seed["projections"] +
            match_seed["projections"] +
            subst_seed["projections"]
        )

        # Should not raise
        validate_kernel_projections_first(combined)

    def test_combined_match_kernel_invalid_order(self):
        """Match + kernel in wrong order fails validation."""
        kernel_seed = load_verified_seed(get_seeds_dir() / "kernel.v1.json")
        match_seed = load_verified_seed(get_seeds_dir() / "match.v1.json")

        # Wrong order: domain first
        combined = (
            match_seed["projections"] +
            kernel_seed["projections"]
        )

        with pytest.raises(ValueError, match="SECURITY"):
            validate_kernel_projections_first(combined)


# =============================================================================
# Attack Simulation Tests
# =============================================================================

class TestProjectionOrderAttackPrevention:
    """Test that projection order enforcement prevents attacks."""

    def test_malicious_entry_interceptor_blocked(self):
        """Malicious projection intercepting entry point is blocked."""
        kernel_seed = load_verified_seed(get_seeds_dir() / "kernel.v1.json")

        # Attacker tries to inject projection before kernel.wrap
        # This projection matches the kernel entry point signature
        malicious_proj = {
            "id": "attack.intercept_entry",
            "pattern": {"_step": {"var": "x"}, "_projs": {"var": "y"}},
            "body": {"pwned": True}
        }

        # If attacker puts malicious projection first, validation should fail
        bad_order = [malicious_proj] + kernel_seed["projections"]

        # Validation should pass because malicious_proj doesn't have kernel.* ID
        # or _mode pattern - it looks like a domain projection
        # The issue is it's BEFORE kernel projections
        # Actually, in this case malicious_proj is "domain" and kernel is after
        # So validation should FAIL
        with pytest.raises(ValueError, match="SECURITY"):
            validate_kernel_projections_first(bad_order)

    def test_forged_kernel_state_blocked(self):
        """Projection that outputs kernel-like state doesn't bypass validation."""
        kernel_seed = load_verified_seed(get_seeds_dir() / "kernel.v1.json")

        # Attacker tries to forge kernel done state
        # This is a domain projection that outputs kernel-like structure
        forging_proj = {
            "id": "attack.forge_done",
            "pattern": {"trigger": {"var": "x"}},
            "body": {"_mode": "done", "_result": "pwned", "_stall": False}
        }

        # Correct order: kernel first, forging_proj after
        good_order = kernel_seed["projections"] + [forging_proj]

        # Should pass validation (domain projection is after kernel)
        validate_kernel_projections_first(good_order)

        # Note: The forging_proj can still produce kernel-like output,
        # but that's handled by kernel.unwrap matching first (first-match-wins)
        # The ORDER enforcement ensures kernel projections match first
