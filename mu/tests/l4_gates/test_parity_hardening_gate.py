"""L4 gate: Parity hardening (agent-review-parity-hardening).

Proves that agent review findings are fixed:
1. JS ALGORITHM_INTERNAL_UNRESERVED_FIELDS parity with Python (16 fields)
2. JS stepKernel rejects kernel-projection IDs (parity with Python)
3. Engine pipeline entry validates reserved fields (both substrates)
4. Boundary handler dedup — shared helper exists in both substrates
5. JS validation unified via _walkAndValidate callback pattern
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

from rcx_pi.selfhost.step_mu import (
    ALGORITHM_INTERNAL_UNRESERVED_FIELDS as PY_UNRESERVED,
    KERNEL_RESERVED_FIELDS,
    run_engine_pipeline,
    validate_no_kernel_reserved_fields,
)

PY_RUNTIME = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
JS_RUNTIME = REPO_ROOT / "mu" / "host" / "js" / "eval_step.js"


# ===========================================================================
# 1. ALGORITHM_INTERNAL_UNRESERVED_FIELDS Parity
# ===========================================================================
class TestUnreservedFieldsParity:
    """JS and Python must have identical ALGORITHM_INTERNAL_UNRESERVED_FIELDS."""

    def test_python_has_exhaustion_sentinel_fields(self):
        """Python must include _m, _s, _st, _stl."""
        for field in ("_m", "_s", "_st", "_stl"):
            assert field in PY_UNRESERVED, f"Python missing {field}"

    def test_js_has_exhaustion_sentinel_fields(self):
        """JS must include _m, _s, _st, _stl."""
        src = JS_RUNTIME.read_text()
        for field in ("_m", "_s", "_st", "_stl"):
            assert f"'{field}'" in src or f'"{field}"' in src, f"JS missing {field}"

    def test_field_count_parity(self):
        """Both substrates must have same field count."""
        src = JS_RUNTIME.read_text()
        # Extract JS set contents
        match = re.search(
            r"const ALGORITHM_INTERNAL_UNRESERVED_FIELDS = new Set\(\[(.*?)\]\)",
            src, re.DOTALL,
        )
        assert match, "JS ALGORITHM_INTERNAL_UNRESERVED_FIELDS not found"
        js_fields = set(re.findall(r"'(_\w+)'", match.group(1)))
        assert len(js_fields) == len(PY_UNRESERVED), (
            f"Field count mismatch: Python={len(PY_UNRESERVED)}, JS={len(js_fields)}"
        )

    def test_field_set_exact_parity(self):
        """Both substrates must have identical field sets."""
        src = JS_RUNTIME.read_text()
        match = re.search(
            r"const ALGORITHM_INTERNAL_UNRESERVED_FIELDS = new Set\(\[(.*?)\]\)",
            src, re.DOTALL,
        )
        assert match
        js_fields = set(re.findall(r"'(_\w+)'", match.group(1)))
        assert js_fields == PY_UNRESERVED, (
            f"Field set mismatch: Python-only={PY_UNRESERVED - js_fields}, "
            f"JS-only={js_fields - PY_UNRESERVED}"
        )


# ===========================================================================
# 2. Kernel Projection ID Rejection Parity
# ===========================================================================
class TestKernelProjectionIDRejection:
    """Both substrates must reject kernel projection IDs in domain projections."""

    def test_python_rejects_kernel_projection_id(self):
        proj = {"id": "kernel.fake", "pattern": {"x": 1}, "body": {"x": 1}}
        with pytest.raises(ValueError, match="kernel projection"):
            step_kernel_mu = __import__(
                "rcx_pi.selfhost.step_mu", fromlist=["step_kernel_mu"]
            ).step_kernel_mu
            step_kernel_mu([proj], {"x": 1})

    def test_js_source_has_kernel_id_check(self):
        """JS stepKernel must check for kernel.* projection IDs."""
        src = JS_RUNTIME.read_text()
        assert "startsWith('kernel.')" in src, (
            "JS stepKernel missing kernel-projection-ID rejection"
        )


# ===========================================================================
# 3. Engine Pipeline Reserved Field Validation
# ===========================================================================
class TestEnginePipelineReservedFieldValidation:
    """Engine pipeline entry must reject reserved fields in user input."""

    def test_python_engine_pipeline_rejects_reserved_field(self):
        """Python run_engine_pipeline rejects input with _mode."""
        with pytest.raises(ValueError, match="kernel-reserved field"):
            run_engine_pipeline([], {"_mode": "forged"})

    def test_python_source_has_validation_at_entry(self):
        """Python run_engine_pipeline calls validate_no_kernel_reserved_fields."""
        src = PY_RUNTIME.read_text()
        # Find validate call between function def and engine loop
        fn_start = src.index("def run_engine_pipeline(")
        fn_body = src[fn_start:fn_start + 3500]
        assert "validate_no_kernel_reserved_fields(input_value" in fn_body

    def test_js_source_has_validation_at_entry(self):
        """JS runEnginePipeline calls validateNoKernelReservedFields."""
        src = JS_RUNTIME.read_text()
        fn_start = src.index("function runEnginePipeline(")
        fn_body = src[fn_start:fn_start + 2000]
        assert "validateNoKernelReservedFields(inputValue" in fn_body


# ===========================================================================
# 4. Shared Boundary Handler Source Lock
# ===========================================================================
class TestBoundaryHandlerDedup:
    """Boundary handlers must use shared helper (not duplicated)."""

    def test_python_has_service_boundary_effect(self):
        src = PY_RUNTIME.read_text()
        assert "def _service_boundary_effect(" in src

    def test_python_engine_calls_shared_handler(self):
        src = PY_RUNTIME.read_text()
        assert "_service_boundary_effect(" in src
        # Should appear at least twice (called from both engine paths)
        count = src.count("_service_boundary_effect(")
        assert count >= 3, f"Expected >=3 refs (def + 2 calls), got {count}"

    def test_js_has_service_boundary_effect(self):
        src = JS_RUNTIME.read_text()
        assert "function serviceBoundaryEffect(" in src

    def test_js_engine_calls_shared_handler(self):
        src = JS_RUNTIME.read_text()
        count = src.count("serviceBoundaryEffect(")
        assert count >= 3, f"Expected >=3 refs (def + 2 calls), got {count}"


# ===========================================================================
# 5. JS Validation Unification Source Lock
# ===========================================================================
class TestJSValidationUnification:
    """JS validation must use shared _walkAndValidate (not duplicated)."""

    def test_js_has_walk_and_validate(self):
        src = JS_RUNTIME.read_text()
        assert "function _walkAndValidate(" in src

    def test_js_validators_delegate_to_walk(self):
        """Both validators must call _walkAndValidate, not duplicate traversal."""
        src = JS_RUNTIME.read_text()
        # Find validateNoKernelReservedFields body
        fn_start = src.index("function validateNoKernelReservedFields(")
        fn_body = src[fn_start:fn_start + 500]
        assert "_walkAndValidate(" in fn_body

        # Find validateAlgorithmRuntimeFields body
        fn_start = src.index("function validateAlgorithmRuntimeFields(")
        fn_body = src[fn_start:fn_start + 500]
        assert "_walkAndValidate(" in fn_body
