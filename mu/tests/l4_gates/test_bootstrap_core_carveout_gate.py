"""
Gate test: Bootstrap Core Carve-out (Wave 23)

Enforces:
1. bootstrap_core.js LOC budget (<=400 non-blank non-comment lines)
2. Export allowlist (only allowed symbols exported)
3. No inline tests in runtime modules (core/ and engine/)
4. Primitive marker named set (BOOTSTRAP_PRIMITIVE for exactly {eval_step, max_steps, stack_guard, projection_loader})
5. Matcher depth guard parity (Python _match_inner and JS match both enforce MAX_MU_DEPTH)
6. Shim LOC budget (eval_step.js <= 50 lines)
"""

import re
import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT
JS_DIR = REPO_ROOT / "mu" / "host" / "js"
BOOTSTRAP_CORE = JS_DIR / "core" / "bootstrap_core.js"
EVAL_STEP_SHIM = JS_DIR / "eval_step.js"


def _read_all_js_source() -> str:
    parts = []
    for f in sorted(JS_DIR.rglob("*.js")):
        parts.append(f.read_text())
    return "\n".join(parts)


def _count_code_lines(path: Path) -> int:
    """Count non-blank, non-comment lines in a JS file."""
    lines = path.read_text().splitlines()
    count = 0
    in_block_comment = False
    for line in lines:
        stripped = line.strip()
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("/*"):
            if "*/" not in stripped:
                in_block_comment = True
            continue
        if stripped.startswith("//") or stripped.startswith("*") or stripped == "":
            continue
        count += 1
    return count


# ---------------------------------------------------------------------------
# 1. Bootstrap core LOC budget
# ---------------------------------------------------------------------------

class TestBootstrapCoreLOCBudget:
    """bootstrap_core.js must stay within 400 non-blank non-comment lines."""

    def test_bootstrap_core_loc_budget(self):
        assert BOOTSTRAP_CORE.exists(), f"bootstrap_core.js not found at {BOOTSTRAP_CORE}"
        loc = _count_code_lines(BOOTSTRAP_CORE)
        assert loc <= 400, (
            f"bootstrap_core.js has {loc} code lines, exceeds 400 LOC budget. "
            f"Move non-TCB code to engine/ or core/ modules."
        )


# ---------------------------------------------------------------------------
# 2. Export allowlist
# ---------------------------------------------------------------------------

ALLOWED_EXPORTS = {
    "match", "substitute", "applyProjection", "step", "run",
    "isKernelTerminal", "isKernelIntermediate", "makeUndefinedMotif",
    "NO_MATCH",
}

class TestBootstrapCoreExportAllowlist:
    """bootstrap_core.js exports only the allowed symbols."""

    def test_export_allowlist(self):
        source = BOOTSTRAP_CORE.read_text()
        # Extract module.exports block
        m = re.search(r"module\.exports\s*=\s*\{([^}]+)\}", source)
        assert m, "Could not find module.exports in bootstrap_core.js"
        exports_block = m.group(1)
        # Extract exported names
        exported = set(re.findall(r"(\w+)", exports_block))
        extra = exported - ALLOWED_EXPORTS
        missing = ALLOWED_EXPORTS - exported
        assert not extra, f"bootstrap_core.js exports unauthorized symbols: {extra}"
        assert not missing, f"bootstrap_core.js missing required exports: {missing}"


# ---------------------------------------------------------------------------
# 3. No inline tests in runtime modules
# ---------------------------------------------------------------------------

class TestNoInlineTestsInRuntime:
    """No test output patterns in core/ or engine/ directories."""

    def test_no_console_log_test_patterns(self):
        violations = []
        for subdir in ["core", "engine"]:
            dir_path = JS_DIR / subdir
            if not dir_path.exists():
                continue
            for f in dir_path.rglob("*.js"):
                source = f.read_text()
                if "console.log('===" in source or 'console.log("===' in source:
                    violations.append(str(f.relative_to(REPO_ROOT)))
        assert not violations, (
            f"Runtime modules must not contain inline test patterns "
            f"(console.log('===')): {violations}"
        )


# ---------------------------------------------------------------------------
# 4. Primitive marker named set
# ---------------------------------------------------------------------------

EXPECTED_PRIMITIVES = {"eval_step", "max_steps", "stack_guard", "projection_loader"}

class TestPrimitiveMarkerNamedSet:
    """BOOTSTRAP_PRIMITIVE markers exist for exactly the named set."""

    def test_primitive_markers_exact_set(self):
        source = _read_all_js_source()
        # Find all BOOTSTRAP_PRIMITIVE: <name> markers
        markers = set(re.findall(r"BOOTSTRAP_PRIMITIVE:\s*(\w+)", source))
        missing = EXPECTED_PRIMITIVES - markers
        extra = markers - EXPECTED_PRIMITIVES
        assert not missing, f"Missing BOOTSTRAP_PRIMITIVE markers: {missing}"
        assert not extra, f"Extra BOOTSTRAP_PRIMITIVE markers: {extra}"


# ---------------------------------------------------------------------------
# 5. Matcher depth guard parity
# ---------------------------------------------------------------------------

class TestMatcherDepthGuardParity:
    """Python _match_inner and JS match both enforce MAX_MU_DEPTH."""

    def test_python_match_inner_has_depth_guard(self):
        py_path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "eval_seed.py"
        source = py_path.read_text()
        assert "_depth" in source and "MAX_MU_DEPTH" in source, (
            "Python _match_inner must have _depth parameter and MAX_MU_DEPTH guard"
        )
        # Verify _match_inner signature includes _depth
        assert re.search(r"def _match_inner\(.*_depth", source), (
            "Python _match_inner must accept _depth parameter"
        )

    def test_js_match_has_depth_guard(self):
        source = BOOTSTRAP_CORE.read_text()
        assert re.search(r"function match\(.*_depth", source), (
            "JS match must accept _depth parameter"
        )
        assert "MAX_DEPTH" in source, (
            "JS match must enforce MAX_DEPTH guard"
        )


# ---------------------------------------------------------------------------
# 6. Shim LOC budget
# ---------------------------------------------------------------------------

class TestShimLOCBudget:
    """eval_step.js shim must stay within 50 lines."""

    def test_shim_loc_budget(self):
        assert EVAL_STEP_SHIM.exists(), f"eval_step.js not found at {EVAL_STEP_SHIM}"
        lines = EVAL_STEP_SHIM.read_text().splitlines()
        assert len(lines) <= 50, (
            f"eval_step.js has {len(lines)} lines, exceeds 50 line shim budget. "
            f"All logic should be in core/, engine/, api/, cli/ modules."
        )
