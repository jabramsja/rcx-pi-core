"""
A20.3: Tests for tools/checks/check_host_semantics_ratchet.py.

Validates scanning, baseline schema validation, ratchet logic,
fail-closed guards, CLI modes, and dual invocation paths.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

# Import the checker module directly for unit tests.
import importlib.util
_tool_path = REPO_ROOT / "tools" / "checks" / "check_host_semantics_ratchet.py"
_spec = importlib.util.spec_from_file_location("check_host_semantics_ratchet", _tool_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
validate_baseline = _mod.validate_baseline
scan_markers = _mod.scan_markers
check_ratchet = _mod.check_ratchet


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_baseline(py_counts=None, js_counts=None, schema_version=1):
    py = py_counts or {"host_iteration": 3, "host_recursion": 2, "host_builtin": 1, "host_mutation": 1}
    js = js_counts or {"host_iteration": 10, "host_recursion": 5, "host_builtin": 4, "host_mutation": 0}
    return {
        "schema_version": schema_version,
        "generated_at": "2026-01-01T00:00:00Z",
        "counts": {"python": py, "javascript": js},
        "total_python": sum(py.values()),
        "total_javascript": sum(js.values()),
        "total": sum(py.values()) + sum(js.values()),
    }


def _write_fake_source(tmp_path, filename, content):
    p = tmp_path / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# TestHostSemanticsRatchet
# ---------------------------------------------------------------------------

class TestHostSemanticsRatchet:
    """Core scanning and ratchet logic."""

    def test_passes_on_current_codebase(self):
        """Default invocation with real codebase should pass."""
        result = subprocess.run(
            ["python3", str(_tool_path)],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"check_host_semantics_ratchet.py failed:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_detects_increase(self):
        """Mock baseline with lower count triggers ratchet failure."""
        current = {
            "python": {"host_iteration": 5, "host_recursion": 2, "host_builtin": 1, "host_mutation": 1},
            "javascript": {"host_iteration": 10, "host_recursion": 5, "host_builtin": 4, "host_mutation": 0},
        }
        baseline = _make_baseline(
            py_counts={"host_iteration": 3, "host_recursion": 2, "host_builtin": 1, "host_mutation": 1},
        )
        result = check_ratchet(current, baseline)
        assert not result["passed"]
        assert len(result["increases"]) == 1
        assert result["increases"][0]["category"] == "host_iteration"
        assert result["increases"][0]["substrate"] == "python"

    def test_allows_decrease(self):
        """Mock baseline with higher count allows decrease (good progress)."""
        current = {
            "python": {"host_iteration": 2, "host_recursion": 1, "host_builtin": 1, "host_mutation": 0},
            "javascript": {"host_iteration": 8, "host_recursion": 3, "host_builtin": 2, "host_mutation": 0},
        }
        baseline = _make_baseline(
            py_counts={"host_iteration": 3, "host_recursion": 2, "host_builtin": 1, "host_mutation": 1},
            js_counts={"host_iteration": 10, "host_recursion": 5, "host_builtin": 4, "host_mutation": 0},
        )
        result = check_ratchet(current, baseline)
        assert result["passed"]
        assert len(result["decreases"]) > 0

    def test_scan_detects_py_decorators(self, tmp_path):
        """Scanner detects @host_* decorators in Python files."""
        fake_py = _write_fake_source(tmp_path, "test.py",
            '@host_iteration("loop")\n'
            'def foo(): pass\n'
            '@host_recursion("tree")\n'
            'def bar(): pass\n'
        )
        counts = scan_markers([fake_py], [])
        assert counts["python"]["host_iteration"] == 1
        assert counts["python"]["host_recursion"] == 1

    def test_scan_detects_py_inline_markers(self, tmp_path):
        """Scanner detects # @host_* inline comments in Python files."""
        fake_py = _write_fake_source(tmp_path, "test.py",
            'while stack:  # @host_iteration: boundary\n'
            '    pass\n'
        )
        counts = scan_markers([fake_py], [])
        assert counts["python"]["host_iteration"] == 1

    def test_scan_detects_js_markers(self, tmp_path):
        """Scanner detects * @host_* and // @host_* comments in JS files."""
        fake_js = _write_fake_source(tmp_path, "test.js",
            '/**\n'
            ' * @host_iteration — step loop\n'
            ' */\n'
            'function step() {}\n'
            '// @host_builtin: type check\n'
            'function isValid() {}\n'
        )
        counts = scan_markers([], [fake_js])
        assert counts["javascript"]["host_iteration"] == 1
        assert counts["javascript"]["host_builtin"] == 1

    def test_json_output_mode(self):
        """--json output has expected keys."""
        result = subprocess.run(
            ["python3", str(_tool_path), "--json"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "passed" in data
        assert "increases" in data
        assert "current" in data
        assert "baseline_counts" in data
        assert data["passed"] is True

    def test_update_blocked_in_ci(self):
        """--update-baseline exits non-zero when RCX_CI=1."""
        env = {**os.environ, "RCX_CI": "1"}
        result = subprocess.run(
            ["python3", str(_tool_path), "--update-baseline"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
            env=env,
        )
        assert result.returncode == 1
        assert "forbidden in CI" in result.stderr


# ---------------------------------------------------------------------------
# TestBaselineValidation
# ---------------------------------------------------------------------------

class TestBaselineValidation:
    """Baseline schema validation tests."""

    def test_valid_baseline_passes(self):
        data = _make_baseline()
        errors = validate_baseline(data)
        assert errors == []

    def test_rejects_wrong_schema_version(self):
        data = _make_baseline(schema_version=99)
        errors = validate_baseline(data)
        assert any("schema_version" in e for e in errors)

    def test_rejects_missing_counts(self):
        data = {"schema_version": 1}
        errors = validate_baseline(data)
        assert any("counts" in e for e in errors)

    def test_rejects_unknown_category(self):
        data = _make_baseline()
        data["counts"]["python"]["host_magic"] = 5
        errors = validate_baseline(data)
        assert any("unknown category" in e for e in errors)

    def test_rejects_negative_count(self):
        data = _make_baseline()
        data["counts"]["python"]["host_iteration"] = -1
        errors = validate_baseline(data)
        assert any("non-negative" in e for e in errors)

    def test_rejects_not_dict(self):
        errors = validate_baseline([1, 2, 3])
        assert any("must be a dict" in e for e in errors)


# ---------------------------------------------------------------------------
# TestFailClosedGuards
# ---------------------------------------------------------------------------

class TestFailClosedGuards:
    """Fail-closed on zero-scan, malformed input, etc."""

    def test_malformed_baseline_exits_nonzero(self, tmp_path):
        """Malformed baseline JSON causes exit 1."""
        bl_path = tmp_path / "bad.json"
        bl_path.write_text('{"schema_version": 99, "counts": {}}')
        result = subprocess.run(
            ["python3", str(_tool_path), "--baseline", str(bl_path)],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 1
        assert "schema_version" in result.stderr


# ---------------------------------------------------------------------------
# TestInvocationPaths
# ---------------------------------------------------------------------------

class TestHostSemanticsInvocationPaths:
    """Both tools/ and mu/tools/ paths must work."""

    def test_via_tools_path(self):
        result = subprocess.run(
            ["python3", "tools/checks/check_host_semantics_ratchet.py"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_via_mu_tools_path(self):
        result = subprocess.run(
            ["python3", "mu/tools/checks/check_host_semantics_ratchet.py"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        assert "PASS" in result.stdout
