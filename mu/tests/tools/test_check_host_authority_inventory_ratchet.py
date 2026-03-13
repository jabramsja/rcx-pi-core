"""
Tests for tools/checks/check_host_authority_inventory_ratchet.py.

Validates:
- baseline schema validation
- Python nested helper detection
- JS nested helper detection
- ratchet failure on new sites
- real-code invocation paths and known nested-site coverage
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from tests.repo_root import REPO_ROOT

_tool_path = REPO_ROOT / "tools" / "checks" / "check_host_authority_inventory_ratchet.py"
_spec = importlib.util.spec_from_file_location("check_host_authority_inventory_ratchet", _tool_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

validate_baseline = _mod.validate_baseline
compare_inventory = _mod.compare_inventory
scan_sites = _mod.scan_sites
_scan_python_file = _mod._scan_python_file  # ANTICHEAT_OK: tool unit test
_scan_js_file = _mod._scan_js_file  # ANTICHEAT_OK: tool unit test


def _make_baseline(entries: list[dict], schema_version: int = 1) -> dict:
    py = sum(1 for e in entries if e["substrate"] == "python")
    js = sum(1 for e in entries if e["substrate"] == "javascript")
    return {
        "schema_version": schema_version,
        "generated_at": "2026-03-12T00:00:00Z",
        "site_counts": {"python": py, "javascript": js, "total": py + js},
        "entries": entries,
    }


def _write_fake_source(tmp_path: Path, rel_name: str, content: str) -> Path:
    path = tmp_path / rel_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


class TestHostAuthorityInventoryRatchet:
    """Core scanner and ratchet behavior."""

    def test_passes_on_current_codebase(self):
        result = subprocess.run(
            ["python3", str(_tool_path)],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            "checker failed on current codebase:\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_json_output_has_expected_keys(self):
        result = subprocess.run(
            ["python3", str(_tool_path), "--json"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "current_counts" in data
        assert "baseline_counts" in data
        assert "new_sites" in data
        assert "current_sites" in data
        assert data["passed"] is True

    def test_detects_new_site_against_baseline(self):
        baseline_entries = [
            {
                "file": "rcx_pi/selfhost/eval_seed.py",
                "line": 1,
                "name": "step",
                "signals": ["loop"],
                "substrate": "python",
            }
        ]
        current_entries = baseline_entries + [
            {
                "file": "rcx_pi/selfhost/eval_seed.py",
                "line": 2,
                "name": "assert_not_lambda_calculus",
                "signals": ["loop"],
                "substrate": "python",
            }
        ]
        result = compare_inventory(current_entries, _make_baseline(baseline_entries))
        assert result["passed"] is False
        assert len(result["new_sites"]) == 1
        assert result["new_sites"][0]["name"] == "assert_not_lambda_calculus"

    def test_scan_python_catches_nested_helper(self, tmp_path):
        fake_py = _write_fake_source(
            tmp_path,
            "pkg/sample.py",
            "\n".join(
                [
                    "def outer():",
                    "    def inner(x):",
                    "        if isinstance(x, list):",
                    "            return inner(x[0])",
                    "        return x",
                    "    return inner([])",
                    "",
                ]
            ),
        )
        sites = _scan_python_file(fake_py)
        names = {site["name"] for site in sites}
        assert "outer.inner" in names

    def test_scan_js_catches_nested_helper(self, tmp_path):
        fake_js = _write_fake_source(
            tmp_path,
            "pkg/sample.js",
            "\n".join(
                [
                    "function outer() {",
                    "  function inner(x) {",
                    "    if (Array.isArray(x)) {",
                    "      return inner(x[0]);",
                    "    }",
                    "    return x;",
                    "  }",
                    "  return inner([]);",
                    "}",
                    "",
                ]
            ),
        )
        sites = _scan_js_file(fake_js)
        names = {site["name"] for site in sites}
        assert "inner" in names

    def test_current_codebase_contains_known_nested_sites(self):
        py_files, js_files = _mod._collect_files()  # ANTICHEAT_OK: tool unit test
        sites = scan_sites(py_files, js_files)
        keys = {(site["file"], site["name"]) for site in sites}
        assert ("rcx_pi/selfhost/eval_seed.py", "assert_not_lambda_calculus._collect_pattern_vars") in keys  # ANTICHEAT_OK: string literal test data
        assert ("mu/host/js/core/bootstrap_core.js", "safeHash") in keys
        assert ("rcx_pi/selfhost/engine_pipeline.py", "run_engine_pipeline._emit") in keys  # ANTICHEAT_OK: string literal test data
        assert ("mu/host/js/engine/pipeline.js", "emit") in keys

    def test_update_blocked_in_ci(self):
        env = {**os.environ, "RCX_CI": "1"}
        result = subprocess.run(
            ["python3", str(_tool_path), "--update-baseline"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(REPO_ROOT),
            env=env,
        )
        assert result.returncode == 1
        assert "forbidden in CI" in result.stderr


class TestHostAuthorityInventoryBaselineValidation:
    """Baseline schema validation tests."""

    def test_valid_baseline_passes(self):
        data = _make_baseline(
            [
                {
                    "file": "rcx_pi/selfhost/eval_seed.py",
                    "line": 1,
                    "name": "step",
                    "signals": ["loop"],
                    "substrate": "python",
                }
            ]
        )
        assert validate_baseline(data) == []

    def test_rejects_bad_schema_version(self):
        data = _make_baseline([], schema_version=99)
        errors = validate_baseline(data)
        assert any("schema_version" in err for err in errors)

    def test_rejects_duplicate_entries(self):
        entry = {
            "file": "rcx_pi/selfhost/eval_seed.py",
            "line": 1,
            "name": "step",
            "signals": ["loop"],
            "substrate": "python",
        }
        errors = validate_baseline(_make_baseline([entry, dict(entry)]))
        assert any("duplicate" in err for err in errors)

    def test_rejects_missing_required_fields(self):
        errors = validate_baseline({"schema_version": 1, "entries": [{"file": "x"}]})
        assert any("missing fields" in err for err in errors)


class TestHostAuthorityInventoryInvocationPaths:
    """Both tools/ and mu/tools/ paths must work."""

    def test_via_tools_path(self):
        result = subprocess.run(
            ["python3", "tools/checks/check_host_authority_inventory_ratchet.py"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_via_mu_tools_path(self):
        result = subprocess.run(
            ["python3", "mu/tools/checks/check_host_authority_inventory_ratchet.py"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        assert "PASS" in result.stdout
