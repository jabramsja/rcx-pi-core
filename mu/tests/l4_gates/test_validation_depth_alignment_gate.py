"""L4 gate test: validation depth must cover full MAX_MU_DEPTH.

Evidence for wave 4i non-blocker sweep:
- Validation depth in step_mu.py must equal MAX_MU_DEPTH (was 100, now 300)
- JS MAX_VALIDATION_DEPTH must equal MAX_DEPTH
- Structures between old limit (100) and MAX_MU_DEPTH (300) must be validated

This gate prevents regression of the security gap where structures nested
100-300 levels deep could bypass reserved-field validation.
"""
import pytest

from tests.repo_root import REPO_ROOT


class TestValidationDepthAlignment:
    """Verify validation depth covers full MAX_MU_DEPTH in both substrates."""

    def test_python_validation_covers_max_mu_depth(self):
        """Validation accepts structures at MAX_MU_DEPTH-1 (proves limit >= MAX_MU_DEPTH)."""
        from rcx_pi.selfhost.mu_type import MAX_MU_DEPTH
        from rcx_pi.selfhost.step_mu import validate_algorithm_runtime_fields

        # Build structure at MAX_MU_DEPTH - 1 levels — must be accepted
        value = "leaf"
        for _ in range(MAX_MU_DEPTH - 1):
            value = {"safe_key": value}
        validate_algorithm_runtime_fields(value, "test")

    def test_python_rejects_beyond_max_mu_depth(self):
        """Structures deeper than MAX_MU_DEPTH are rejected by validator."""
        from rcx_pi.selfhost.mu_type import MAX_MU_DEPTH
        from rcx_pi.selfhost.step_mu import validate_algorithm_runtime_fields

        value = "leaf"
        for _ in range(MAX_MU_DEPTH + 5):
            value = {"safe_key": value}
        with pytest.raises(ValueError, match="maximum validation depth"):
            validate_algorithm_runtime_fields(value, "test")

    def test_python_depth_200_accepted(self):
        """Structures at depth 200 are accepted (regression: old limit was 100)."""
        from rcx_pi.selfhost.step_mu import validate_algorithm_runtime_fields

        value = "leaf"
        for _ in range(200):
            value = {"safe_key": value}
        # This would fail with the old hardcoded limit of 100
        validate_algorithm_runtime_fields(value, "test")

    def test_js_validation_depth_equals_max_depth(self):
        """JS MAX_VALIDATION_DEPTH must equal MAX_DEPTH (not a smaller constant)."""
        js_path = REPO_ROOT / "mu" / "host" / "js" / "core" / "constants.js"
        source = js_path.read_text()

        assert "MAX_VALIDATION_DEPTH = MAX_DEPTH" in source, (
            "JS MAX_VALIDATION_DEPTH must be assigned from MAX_DEPTH, "
            "not a hardcoded constant."
        )

    def test_reserved_field_rejected_at_depth_200(self):
        """Reserved field at depth 200 must be caught (was missed with old limit=100)."""
        from rcx_pi.selfhost.step_mu import (
            KERNEL_RESERVED_FIELDS,
            validate_no_kernel_reserved_fields,
        )

        reserved = sorted(KERNEL_RESERVED_FIELDS)[0]
        value = {reserved: "injected"}
        for _ in range(200):
            value = {"safe_key": value}
        with pytest.raises(ValueError, match="SECURITY"):
            validate_no_kernel_reserved_fields(value, "test")
