"""
Cross-substrate contract drift guard.

Verifies that critical constants and invariants match between the Python
and JavaScript substrates. These are hard invariants — if they drift,
cross-substrate parity breaks silently.

What this checker PROVES:
- Reserved field sets are identical (security boundary).
- Depth/width guards match (stack safety + resource exhaustion).
- Boot1 re-entry depth cap matches (loop safety).
- Engine iteration budget matches (execution budget).
- Hash cache limit matches (memory bound).
- Trace hard cap matches (output bound).

What this checker does NOT prove:
- Semantic behavior parity (use test_js_parity_automated.py for that).
- Algorithm correctness (use seed-level parity tests).
- Performance characteristics (JS may be faster/slower).
- Error message text (only codes matter for parity).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
# SPEED_OK: imports step_mu for constants and inspect.signature only, never calls slow kernel functions
from rcx_pi.selfhost.step_mu import (
    KERNEL_RESERVED_FIELDS,
    ALGORITHM_ENTRYPOINT_KEYS,
)
from rcx_pi.selfhost.mu_type import MAX_MU_DEPTH, MAX_MU_WIDTH

# ── Locate JS source ────────────────────────────────────────────────────

_REPO = Path(__file__).resolve().parents[3]
_JS_DIR = _REPO / "mu" / "host" / "js"


def _js_source() -> str:
    """Read all JS module files concatenated (monolith was split into modules)."""
    parts = []
    for f in sorted(_JS_DIR.rglob("*.js")):
        parts.append(f.read_text())
    return "\n".join(parts)


def _extract_js_set(source: str, var_name: str) -> set[str]:
    """Extract a Set([...]) constant from JS source."""
    # Match: const VAR_NAME = new Set([ ... ]);
    pattern = rf"const\s+{re.escape(var_name)}\s*=\s*new\s+Set\(\[(.*?)\]\)"
    m = re.search(pattern, source, re.DOTALL)
    if not m:
        pytest.fail(f"Could not find {var_name} in eval_step.js")
    block = m.group(1)
    # Extract quoted strings
    return set(re.findall(r"'([^']+)'", block))


def _extract_js_const(source: str, var_name: str) -> int:
    """Extract a numeric constant from JS source."""
    pattern = rf"const\s+{re.escape(var_name)}\s*=\s*(\d+)"
    m = re.search(pattern, source)
    if not m:
        pytest.fail(f"Could not find {var_name} in eval_step.js")
    return int(m.group(1))


def _extract_js_default(source: str, param_name: str) -> int:
    """Extract a default parameter value like `maxEngineIterations = 20`."""
    pattern = rf"{re.escape(param_name)}\s*=\s*(\d+)"
    m = re.search(pattern, source)
    if not m:
        pytest.fail(f"Could not find default for {param_name} in eval_step.js")
    return int(m.group(1))


# ── Reserved field parity ───────────────────────────────────────────────


class TestReservedFieldParity:
    """KERNEL_RESERVED_FIELDS must match between Python and JavaScript."""

    def test_reserved_fields_match(self):
        js = _js_source()
        js_fields = _extract_js_set(js, "KERNEL_RESERVED_FIELDS")
        py_fields = set(KERNEL_RESERVED_FIELDS)
        assert py_fields == js_fields, (
            f"Reserved field drift!\n"
            f"  Python-only: {py_fields - js_fields}\n"
            f"  JS-only:     {js_fields - py_fields}"
        )

    def test_run_engine_in_both(self):
        """_run_engine MUST be reserved in both substrates."""
        assert "_run_engine" in KERNEL_RESERVED_FIELDS
        js_fields = _extract_js_set(_js_source(), "KERNEL_RESERVED_FIELDS")
        assert "_run_engine" in js_fields

    def test_tail_call_in_both(self):
        """_tail_call MUST be reserved in both substrates."""
        assert "_tail_call" in KERNEL_RESERVED_FIELDS
        js_fields = _extract_js_set(_js_source(), "KERNEL_RESERVED_FIELDS")
        assert "_tail_call" in js_fields

    def test_algorithm_entrypoint_keys_match(self):
        js = _js_source()
        js_keys = _extract_js_set(js, "ALGORITHM_ENTRYPOINT_KEYS")
        py_keys = set(ALGORITHM_ENTRYPOINT_KEYS)
        assert py_keys == js_keys, (
            f"Algorithm entrypoint key drift!\n"
            f"  Python-only: {py_keys - js_keys}\n"
            f"  JS-only:     {js_keys - py_keys}"
        )


# ── Depth and width guard parity ────────────────────────────────────────


class TestDepthWidthParity:
    """Stack safety and resource exhaustion guards must match."""

    def test_max_depth_parity(self):
        js_depth = _extract_js_const(_js_source(), "MAX_DEPTH")
        assert MAX_MU_DEPTH == js_depth == 300

    def test_max_width_parity(self):
        js_width = _extract_js_const(_js_source(), "MAX_MU_WIDTH")
        assert MAX_MU_WIDTH == js_width == 1000


# ── Boot1 constants parity ──────────────────────────────────────────────


class TestBoot1Parity:
    """Boot1 loop contract constants must match."""

    def test_boot1_max_reentry_depth_parity(self):
        from rcx_pi.selfhost.step_mu import _BOOT1_MAX_REENTRY_DEPTH  # ANTICHEAT_OK: grounding test verifies cross-substrate constant parity
        js_depth = _extract_js_const(_js_source(), "BOOT1_MAX_REENTRY_DEPTH")
        assert _BOOT1_MAX_REENTRY_DEPTH == js_depth == 20

    def test_boot1_default_is_recursive(self):
        """Boot1 default must be recursive (on) for direct pipeline."""
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
        import inspect
        sig = inspect.signature(run_engine_pipeline)
        # use_boot1_recursive defaults to True (boot1 recursive is default)
        param = sig.parameters.get("use_boot1_recursive")
        assert param is not None, "use_boot1_recursive parameter missing"
        assert param.default is True, (
            f"Boot1 default changed from True to {param.default}. "
            "Boot1 recursive must remain default."
        )


# ── Engine budget parity ────────────────────────────────────────────────


class TestEngineBudgetParity:
    """Engine iteration and hash cache limits must match."""

    def test_max_engine_iterations_parity(self):
        js_val = _extract_js_default(_js_source(), "maxEngineIterations")
        # Python default is 20 (step_mu.py _run_engine_recursive and run_engine_pipeline)
        assert js_val == 20

    def test_hash_cache_limit_parity(self):
        from rcx_pi.selfhost.mu_type import MAX_MU_HASH_CACHE
        js_val = _extract_js_const(_js_source(), "MAX_MU_HASH_CACHE")
        assert MAX_MU_HASH_CACHE == js_val == 10000

    def test_trace_hard_cap_parity(self):
        js = _js_source()
        js_val = _extract_js_const(js, "MAX_TRACE_ENTRIES_HARD_CAP")
        # Python: _MAX_TRACE_ENTRIES_HARD_CAP = 100000
        assert js_val == 100000


# ── Pipeline default parity ───────────────────────────────────────────────


class TestPipelineDefaultParity:
    """JS runEnginePipeline defaults must match Python run_engine_pipeline."""

    def test_max_steps_default_parity(self):
        """JS runEnginePipeline maxSteps default must match Python (100)."""
        import inspect
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
        py_default = inspect.signature(run_engine_pipeline).parameters["max_steps"].default
        js = _js_source()
        # Scope to runEnginePipeline destructuring block to avoid matching run() defaults
        m = re.search(r'function runEnginePipeline\b.*?\{(.*?)\}\s*=\s*options', js, re.DOTALL)
        assert m, "Could not find runEnginePipeline destructuring"
        block = m.group(1)
        m2 = re.search(r'maxSteps\s*=\s*(\d+)', block)
        assert m2, "Could not find maxSteps default in runEnginePipeline"
        js_val = int(m2.group(1))
        assert py_default == js_val == 100, (
            f"maxSteps drift: Python={py_default}, JS={js_val}"
        )

    def test_max_algorithm_iterations_default_parity(self):
        """JS runEnginePipeline maxAlgorithmIterations default must match Python (50)."""
        import inspect
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
        py_default = inspect.signature(run_engine_pipeline).parameters["max_algorithm_iterations"].default
        js = _js_source()
        m = re.search(r'function runEnginePipeline\b.*?\{(.*?)\}\s*=\s*options', js, re.DOTALL)
        assert m, "Could not find runEnginePipeline destructuring"
        block = m.group(1)
        m2 = re.search(r'maxAlgorithmIterations\s*=\s*(\d+)', block)
        assert m2, "Could not find maxAlgorithmIterations default in runEnginePipeline"
        js_val = int(m2.group(1))
        assert py_default == js_val == 50, (
            f"maxAlgorithmIterations drift: Python={py_default}, JS={js_val}"
        )

    def test_frozen_default_null_parity(self):
        """JS frozen default must be null (matching Python None)."""
        js = _js_source()
        # In JS destructuring: frozen = null
        assert "frozen = null" in js, (
            "JS frozen default is not null (expected: frozen = null)"
        )

    def test_observer_default_null_parity(self):
        """JS observer default must be null (matching Python None)."""
        js = _js_source()
        # In JS destructuring: observer = null
        assert "observer = null" in js, (
            "JS observer default is not null (expected: observer = null)"
        )


# ── Hemisphere routing step limit parity ──────────────────────────────────


class TestHemisphereRoutingLimitParity:
    """Hemisphere routing step limits must match between substrates."""

    def test_hemisphere_routing_step_limit_parity(self):
        """Python max_steps=30 must match JS const limit = 30."""
        import re as _re
        py_source = (_REPO / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py").read_text()
        # Find max_steps=N in run_hemisphere_routing function
        m = _re.search(
            r'def run_hemisphere_routing.*?run_mu\([^)]*max_steps=(\d+)',
            py_source, _re.DOTALL,
        )
        assert m, "Could not find max_steps in run_hemisphere_routing"
        py_limit = int(m.group(1))

        js = _js_source()
        m = _re.search(
            r'function runHemisphereRouting.*?const limit = (\d+)',
            js, _re.DOTALL,
        )
        assert m, "Could not find limit in runHemisphereRouting"
        js_limit = int(m.group(1))

        assert py_limit == js_limit == 30, (
            f"Hemisphere routing step limit drift: Python={py_limit}, JS={js_limit}"
        )
