"""L4 gate tests for red-team hardening wave (substitute depth guard + Boot1 re-entry validation).

Evidence for: substitute() depth parity with JS, Boot1 reserved-field defense-in-depth.
"""
import sys
from pathlib import Path

# Canonical repo root resolution (shared helper)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from repo_root import REPO_ROOT  # noqa: E402

sys.path.insert(0, str(REPO_ROOT))

import pytest


class TestSubstituteDepthGuard:
    """Verify Python substitute() has MAX_MU_DEPTH guard matching JS."""

    def test_substitute_rejects_beyond_max_depth(self):
        """substitute() must raise TypeError when _depth exceeds MAX_MU_DEPTH."""
        from rcx_pi.selfhost.eval_seed import substitute
        from rcx_pi.selfhost.mu_type import MAX_MU_DEPTH

        # Call substitute with _depth already at the limit — triggers guard
        # before assert_mu (which is only called at _depth==0)
        body = {"nested": "leaf"}
        with pytest.raises(TypeError, match="Max depth exceeded"):
            substitute(body, {}, _depth=MAX_MU_DEPTH + 1)

    def test_substitute_accepts_within_depth(self):
        """substitute() must work for values within MAX_MU_DEPTH."""
        from rcx_pi.selfhost.eval_seed import substitute

        # Depth 10 is well within bounds
        body = {"var": "x"}
        for _ in range(10):
            body = {"nested": body}

        result = substitute(body, {"x": 42})
        # Unwind to verify substitution happened
        for _ in range(10):
            assert "nested" in result
            result = result["nested"]
        assert result == 42

    def test_substitute_depth_guard_source_lock(self):
        """Python substitute must reference MAX_MU_DEPTH (not hardcoded)."""
        src = (REPO_ROOT / "mu/host/python/rcx_pi/selfhost/eval_seed.py").read_text()
        assert "MAX_MU_DEPTH" in src, "substitute must use MAX_MU_DEPTH constant"
        assert "_depth" in src, "substitute must track recursion depth"


class TestBoot1ReentryValidation:
    """Verify Boot1 re-entry validates reserved fields on new input."""

    def test_python_reentry_validates_reserved_fields(self):
        """Python _run_engine_recursive must call validate_no_kernel_reserved_fields on re-entry."""
        src = (REPO_ROOT / "mu/host/python/rcx_pi/selfhost/step_mu.py").read_text()
        # Both re-entry paths must validate
        assert 'validate_no_kernel_reserved_fields(cur_input, "Boot1 re-entry input")' in src
        assert 'validate_no_kernel_reserved_fields(cur_input, "Boot1 tail_call input")' in src

    def test_js_reentry_validates_reserved_fields(self):
        """JS runEnginePipelineRecursive must call validateNoKernelReservedFields on re-entry."""
        src = (REPO_ROOT / "mu/host/js/eval_step.js").read_text()
        assert "validateNoKernelReservedFields(curInput, 'Boot1 re-entry input')" in src
        assert "validateNoKernelReservedFields(curInput, 'Boot1 tail_call input')" in src

    def test_cross_substrate_reentry_validation_parity(self):
        """Both substrates must validate reserved fields at both re-entry points."""
        py_src = (REPO_ROOT / "mu/host/python/rcx_pi/selfhost/step_mu.py").read_text()
        js_src = (REPO_ROOT / "mu/host/js/eval_step.js").read_text()
        # Count validation sites — must be 2 in each substrate (re-entry + tail_call)
        py_count = py_src.count("validate_no_kernel_reserved_fields(cur_input")
        js_count = js_src.count("validateNoKernelReservedFields(curInput")
        assert py_count == 2, f"Python must have 2 Boot1 re-entry validation sites, got {py_count}"
        assert js_count == 2, f"JS must have 2 Boot1 re-entry validation sites, got {js_count}"
