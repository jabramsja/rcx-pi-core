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
validate_split_allowances = _mod.validate_split_allowances
compare_inventories = _mod.compare_inventories
format_human = _mod.format_human
scan_inventories = _mod.scan_inventories
_scan_python_file = _mod._scan_python_file  # ANTICHEAT_OK: tool unit test
_scan_js_file = _mod._scan_js_file  # ANTICHEAT_OK: tool unit test


def _make_baseline(
    total_entries: list[dict],
    authority_entries: list[dict] | None = None,
    schema_version: int = 2,
) -> dict:
    authority_entries = authority_entries if authority_entries is not None else list(total_entries)
    py_total = sum(1 for e in total_entries if e["substrate"] == "python")
    js_total = sum(1 for e in total_entries if e["substrate"] == "javascript")
    py_auth = sum(1 for e in authority_entries if e["substrate"] == "python")
    js_auth = sum(1 for e in authority_entries if e["substrate"] == "javascript")
    return {
        "schema_version": schema_version,
        "generated_at": "2026-03-12T00:00:00Z",
        "inventories": {
            "total": {
                "site_counts": {"python": py_total, "javascript": js_total, "total": py_total + js_total},
                "entries": total_entries,
            },
            "authority": {
                "site_counts": {"python": py_auth, "javascript": js_auth, "total": py_auth + js_auth},
                "entries": authority_entries,
            },
        },
    }


def _write_fake_source(tmp_path: Path, rel_name: str, content: str) -> Path:
    path = tmp_path / rel_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _site(substrate: str, file: str, name: str, signals: list[str] | None = None, line: int = 1) -> dict:
    return {
        "file": file,
        "line": line,
        "name": name,
        "signals": list(signals or []),
        "substrate": substrate,
    }


def _split_allowances(entries: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "kind": "host_authority_inventory_split_allowances",
        "split_allowances": entries,
    }


def _split_entry(
    allowance_id: str,
    substrate: str,
    old_file: str,
    old_name: str,
    new_file: str,
    new_name: str,
    moved_signals: list[str],
) -> dict:
    return {
        "id": allowance_id,
        "old": {"substrate": substrate, "file": old_file, "name": old_name},
        "new": {"substrate": substrate, "file": new_file, "name": new_name},
        "moved_signals": moved_signals,
    }


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
        assert "Current total inventory" in result.stdout
        assert "Current authority subset" in result.stdout

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
        assert "current_total_counts" in data
        assert "baseline_total_counts" in data
        assert "current_authority_counts" in data
        assert "baseline_authority_counts" in data
        assert "new_total_sites" in data
        assert "new_authority_sites" in data
        assert data["passed"] is True

    def test_detects_new_site_against_baseline(self):
        baseline_total_entries = [
            {
                "file": "rcx_pi/selfhost/eval_seed.py",
                "line": 1,
                "name": "step",
                "signals": ["loop"],
                "substrate": "python",
            }
        ]
        baseline_authority_entries = list(baseline_total_entries)
        current_total_entries = baseline_total_entries + [
            {
                "file": "rcx_pi/selfhost/eval_seed.py",
                "line": 2,
                "name": "assert_not_lambda_calculus",
                "signals": ["loop"],
                "substrate": "python",
            }
        ]
        current_authority_entries = list(current_total_entries)
        result = compare_inventories(
            {
                "total_sites": current_total_entries,
                "authority_sites": current_authority_entries,
            },
            _make_baseline(baseline_total_entries, baseline_authority_entries),
        )
        assert result["passed"] is False
        assert len(result["new_total_sites"]) == 1
        assert len(result["new_authority_sites"]) == 1
        assert result["new_total_sites"][0]["name"] == "assert_not_lambda_calculus"

    def test_generic_new_total_site_still_fails_without_split_policy(self):
        baseline_total_entries = [
            _site("python", "rcx_pi/selfhost/seed_integrity.py", "load_verified_seed")
        ]
        current_total_entries = baseline_total_entries + [
            _site("python", "rcx_pi/selfhost/seed_integrity.py", "load_verified_seed_image")
        ]
        result = compare_inventories(
            {
                "total_sites": current_total_entries,
                "authority_sites": [],
            },
            _make_baseline(baseline_total_entries, []),
        )
        assert result["passed"] is False
        assert [site["name"] for site in result["new_total_sites"]] == ["load_verified_seed_image"]
        assert result["new_authority_sites"] == []

    def test_generic_new_authority_site_still_fails_without_split_policy(self):
        old = _site(
            "python",
            "rcx_pi/selfhost/seed_integrity.py",
            "load_verified_seed",
            ["builtin:len"],
        )
        new_total = _site(
            "python",
            "rcx_pi/selfhost/seed_integrity.py",
            "load_verified_seed_image",
            ["builtin:len"],
        )
        result = compare_inventories(
            {
                "total_sites": [old, new_total],
                "authority_sites": [old, new_total],
            },
            _make_baseline([old, new_total], [old]),
        )
        assert result["passed"] is False
        assert result["new_total_sites"] == []
        assert [site["name"] for site in result["new_authority_sites"]] == [
            "load_verified_seed_image"
        ]

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
        total_sites, authority_sites = _scan_python_file(fake_py)
        total_names = {site["name"] for site in total_sites}
        authority_names = {site["name"] for site in authority_sites}
        assert "outer.inner" in total_names
        assert "outer.inner" in authority_names

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
        total_sites, authority_sites = _scan_js_file(fake_js)
        total_names = {site["name"] for site in total_sites}
        authority_names = {site["name"] for site in authority_sites}
        assert "inner" in total_names
        assert "inner" in authority_names

    def test_current_codebase_contains_known_nested_sites(self):
        py_files, js_files = _mod._collect_files()  # ANTICHEAT_OK: tool unit test
        inventories = scan_inventories(py_files, js_files)
        total_keys = {(site["file"], site["name"]) for site in inventories["total_sites"]}
        authority_keys = {(site["file"], site["name"]) for site in inventories["authority_sites"]}
        assert ("rcx_pi/selfhost/eval_seed.py", "assert_not_lambda_calculus._collect_pattern_vars") in authority_keys  # ANTICHEAT_OK: string literal test data
        assert ("mu/host/js/core/bootstrap_core.js", "safeHash") in authority_keys
        assert ("rcx_pi/selfhost/engine_pipeline.py", "run_engine_pipeline._emit") in authority_keys  # ANTICHEAT_OK: string literal test data
        assert ("mu/host/js/engine/pipeline.js", "emit") in authority_keys
        assert ("rcx_pi/selfhost/eval_seed.py", "match") in total_keys
        assert len(inventories["total_sites"]) >= len(inventories["authority_sites"])

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


class TestHostAuthorityInventorySplitAllowances:
    """Exact-pair split allowance behavior."""

    PY_FILE = "rcx_pi/selfhost/seed_integrity.py"
    JS_FILE = "mu/host/js/core/seed_loader.js"
    PY_OLD = "load_verified_seed"
    PY_NEW = "load_verified_seed_image"
    JS_OLD = "loadVerifiedSeed"
    JS_NEW = "loadVerifiedSeedImage"

    def _baseline_and_policy(self) -> tuple[dict, dict]:
        py_old = _site("python", self.PY_FILE, self.PY_OLD, ["builtin:len", "loop"], 10)
        js_old = _site("javascript", self.JS_FILE, self.JS_OLD, ["builtin:JSON.parse", "loop"], 20)
        baseline = _make_baseline([py_old, js_old], [py_old, js_old])
        policy = _split_allowances(
            [
                _split_entry(
                    "py-seed-image-boundary",
                    "python",
                    self.PY_FILE,
                    self.PY_OLD,
                    self.PY_FILE,
                    self.PY_NEW,
                    ["builtin:len"],
                ),
                _split_entry(
                    "js-seed-image-boundary",
                    "javascript",
                    self.JS_FILE,
                    self.JS_OLD,
                    self.JS_FILE,
                    self.JS_NEW,
                    ["builtin:JSON.parse"],
                ),
            ]
        )
        return baseline, policy

    def _accepted_current(self) -> dict[str, list[dict]]:
        py_old_current = _site("python", self.PY_FILE, self.PY_OLD, [], 10)
        py_new_current = _site("python", self.PY_FILE, self.PY_NEW, ["builtin:len"], 40)
        js_old_current = _site("javascript", self.JS_FILE, self.JS_OLD, [], 20)
        js_new_current = _site(
            "javascript", self.JS_FILE, self.JS_NEW, ["builtin:JSON.parse"], 50
        )
        return {
            "total_sites": [py_old_current, py_new_current, js_old_current, js_new_current],
            "authority_sites": [py_new_current, js_new_current],
        }

    def test_accepts_exact_split_pairs_and_reports_human_and_json_output(self):
        baseline, policy = self._baseline_and_policy()
        result = compare_inventories(self._accepted_current(), baseline, policy)
        assert result["passed"] is True
        assert result["new_total_sites"] == []
        assert result["new_authority_sites"] == []
        assert result["removed_authority_sites"] == []
        assert len(result["accepted_split_pairs"]) == 2
        human = format_human(result, py_files=1, js_files=1)
        as_json = json.dumps(result, sort_keys=True)
        assert "ACCEPTED SPLITS: 2 exact host-authority split pair(s)" in human
        assert "load_verified_seed -> rcx_pi/selfhost/seed_integrity.py::load_verified_seed_image" in human
        assert '"accepted_split_pairs"' in as_json
        assert "py-seed-image-boundary" in as_json

    def test_malformed_split_policy_fails_closed(self):
        baseline, _policy = self._baseline_and_policy()
        result = compare_inventories(
            self._accepted_current(),
            baseline,
            {"schema_version": 1, "kind": "host_authority_inventory_split_allowances", "split_allowances": [{}]},
        )
        assert result["passed"] is False
        assert any("missing fields" in error for error in result["split_policy_errors"])

    def test_stale_split_policy_fails_closed_when_no_split_is_present(self):
        baseline, policy = self._baseline_and_policy()
        current = {
            "total_sites": list(baseline["inventories"]["total"]["entries"]),
            "authority_sites": list(baseline["inventories"]["authority"]["entries"]),
        }
        result = compare_inventories(current, baseline, policy)
        assert result["passed"] is False
        assert any("new site is missing from current total inventory" in error for error in result["split_policy_errors"])

    def test_incomplete_split_pair_fails_closed(self):
        baseline, policy = self._baseline_and_policy()
        current = self._accepted_current()
        current["total_sites"] = [
            site for site in current["total_sites"] if site["name"] != self.JS_NEW
        ]
        current["authority_sites"] = [
            site for site in current["authority_sites"] if site["name"] != self.JS_NEW
        ]
        result = compare_inventories(current, baseline, policy)
        assert result["passed"] is False
        assert any("new site is missing from current total inventory" in error for error in result["split_policy_errors"])

    def test_wrong_name_and_one_substrate_policy_fail_closed(self):
        baseline, _policy = self._baseline_and_policy()
        policy = _split_allowances(
            [
                _split_entry(
                    "py-wrong-new-name",
                    "python",
                    self.PY_FILE,
                    self.PY_OLD,
                    self.PY_FILE,
                    "wrong_seed_image_name",
                    ["builtin:len"],
                )
            ]
        )
        result = compare_inventories(self._accepted_current(), baseline, policy)
        assert result["passed"] is False
        assert any("new site is missing from current total inventory" in error for error in result["split_policy_errors"])
        assert {site["name"] for site in result["new_total_sites"]} == {self.PY_NEW, self.JS_NEW}

    def test_wrong_substrate_policy_fails_schema_validation(self):
        errors = validate_split_allowances(
            _split_allowances(
                [
                    {
                        "id": "cross-substrate-split",
                        "old": {"substrate": "python", "file": self.PY_FILE, "name": self.PY_OLD},
                        "new": {"substrate": "javascript", "file": self.JS_FILE, "name": self.JS_NEW},
                        "moved_signals": ["builtin:len"],
                    }
                ]
            )
        )
        assert any("old/new substrates must match" in error for error in errors)

    def test_one_old_site_to_multiple_new_sites_fails_schema_validation(self):
        errors = validate_split_allowances(
            _split_allowances(
                [
                    _split_entry(
                        "py-split-a",
                        "python",
                        self.PY_FILE,
                        self.PY_OLD,
                        self.PY_FILE,
                        self.PY_NEW,
                        ["builtin:len"],
                    ),
                    _split_entry(
                        "py-split-b",
                        "python",
                        self.PY_FILE,
                        self.PY_OLD,
                        self.PY_FILE,
                        "load_verified_seed_image_alt",
                        ["builtin:len"],
                    ),
                ]
            )
        )
        assert any("old site maps to multiple new sites" in error for error in errors)

    def test_multiple_old_sites_to_one_new_site_fails_schema_validation(self):
        errors = validate_split_allowances(
            _split_allowances(
                [
                    _split_entry(
                        "py-split-a",
                        "python",
                        self.PY_FILE,
                        self.PY_OLD,
                        self.PY_FILE,
                        self.PY_NEW,
                        ["builtin:len"],
                    ),
                    _split_entry(
                        "py-split-b",
                        "python",
                        self.PY_FILE,
                        "load_verified_seed_alt",
                        self.PY_FILE,
                        self.PY_NEW,
                        ["builtin:len"],
                    ),
                ]
            )
        )
        assert any("new site maps from multiple old sites" in error for error in errors)

    def test_wrong_signal_shape_fails_closed(self):
        baseline, policy = self._baseline_and_policy()
        current = self._accepted_current()
        for site in current["total_sites"] + current["authority_sites"]:
            if site["name"] == self.PY_NEW:
                site["signals"] = ["mutation:.push("]
        result = compare_inventories(current, baseline, policy)
        assert result["passed"] is False
        assert any("are not bounded by moved_signals" in error for error in result["split_policy_errors"])

    def test_one_substrate_accepted_split_is_not_enough(self):
        baseline, _policy = self._baseline_and_policy()
        policy = _split_allowances(
            [
                _split_entry(
                    "py-only",
                    "python",
                    self.PY_FILE,
                    self.PY_OLD,
                    self.PY_FILE,
                    self.PY_NEW,
                    ["builtin:len"],
                )
            ]
        )
        current = self._accepted_current()
        current["total_sites"] = [
            site for site in current["total_sites"] if site["substrate"] == "python"
        ]
        current["authority_sites"] = [
            site for site in current["authority_sites"] if site["substrate"] == "python"
        ]
        baseline["inventories"]["total"]["entries"] = [
            site for site in baseline["inventories"]["total"]["entries"] if site["substrate"] == "python"
        ]
        baseline["inventories"]["authority"]["entries"] = [
            site for site in baseline["inventories"]["authority"]["entries"] if site["substrate"] == "python"
        ]
        result = compare_inventories(current, baseline, policy)
        assert result["passed"] is False
        assert any("both substrates" in error for error in result["split_policy_errors"])


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
        errors = validate_baseline({"schema_version": 2, "inventories": {"total": {}, "authority": {}}})
        assert any("missing fields" in err for err in errors)
        assert any("site_counts must be a dict" in err for err in errors)
        assert any("entries must be a list" in err for err in errors)

    def test_rejects_mismatched_site_counts_vs_entries(self):
        """Fail-closed: declared site_counts must match actual entry counts."""
        entry = {
            "file": "rcx_pi/selfhost/eval_seed.py",
            "line": 1,
            "name": "step",
            "signals": ["loop"],
            "substrate": "python",
        }
        # Declare python=999 but only 1 actual python entry
        data = {
            "schema_version": 2,
            "generated_at": "2026-03-12T00:00:00Z",
            "inventories": {
                "total": {
                    "site_counts": {"python": 999, "javascript": 0, "total": 999},
                    "entries": [entry],
                },
                "authority": {
                    "site_counts": {"python": 1, "javascript": 0, "total": 1},
                    "entries": [entry],
                },
            },
        }
        errors = validate_baseline(data)
        assert any("does not match actual python entries" in err for err in errors)
        assert any("does not match actual total entries" in err for err in errors)


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

    def test_tools_and_mu_tools_json_split_behavior_matches(self):
        tools_result = subprocess.run(
            ["python3", "tools/checks/check_host_authority_inventory_ratchet.py", "--json"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(REPO_ROOT),
        )
        mu_result = subprocess.run(
            ["python3", "mu/tools/checks/check_host_authority_inventory_ratchet.py", "--json"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(REPO_ROOT),
        )
        assert tools_result.returncode == 0
        assert mu_result.returncode == 0
        tools_payload = json.loads(tools_result.stdout)
        mu_payload = json.loads(mu_result.stdout)
        assert tools_payload["passed"] is True
        assert mu_payload["passed"] is True
        assert tools_payload["accepted_split_pairs"] == mu_payload["accepted_split_pairs"] == []
        assert tools_payload["split_policy_errors"] == mu_payload["split_policy_errors"] == []
