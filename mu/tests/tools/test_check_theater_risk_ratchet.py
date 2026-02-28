"""
MAINT-M2: Tests for tools/checks/check_theater_risk_ratchet.py.

Validates ratchet logic, allowlist schema validation, CLI modes, and safety guards.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

# Import the ratchet module directly for unit tests.
import importlib.util
_tool_path = REPO_ROOT / "tools" / "checks" / "check_theater_risk_ratchet.py"
_spec = importlib.util.spec_from_file_location("check_theater_risk_ratchet", _tool_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
validate_allowlist = _mod.validate_allowlist
validate_classifier_results = _mod.validate_classifier_results
extract_theater_risk_set = _mod.extract_theater_risk_set
check_ratchet = _mod.check_ratchet


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_allowlist(entries, schema_version=1):
    """Build a minimal allowlist dict."""
    return {
        "schema_version": schema_version,
        "generated_at": "2026-01-01T00:00:00Z",
        "total_theater_risk": len(entries),
        "entries": entries,
    }


def _make_entry(file="mu/tests/l4_gates/test_foo.py", cls="TestFoo",
                method="test_bar", classification="heuristic_false_positive",
                defer_reason="test", owner="founder",
                expires_on="2099-12-31", target_wave="X"):
    return {
        "file": file, "class": cls, "method": method,
        "classification": classification, "defer_reason": defer_reason,
        "owner": owner, "expires_on": expires_on, "target_wave": target_wave,
    }


def _make_classifier(theater_items, *, pad_to_minimum=True):
    """Build classifier JSON from list of (file, class, method) tuples.

    If pad_to_minimum is True, adds behavioral filler methods to satisfy the
    minimum method count (zero-scan guard).
    """
    files = {}
    for f, c, m in theater_items:
        if f not in files:
            files[f] = {"classes": {}}
        if c not in files[f]["classes"]:
            files[f]["classes"][c] = {}
        files[f]["classes"][c][m] = "theater_risk"
    if pad_to_minimum:
        # Add enough behavioral filler to clear the zero-scan guard
        pad_file = "mu/tests/l4_gates/test_pad.py"
        if pad_file not in files:
            files[pad_file] = {"classes": {}}
        if "TestPad" not in files[pad_file]["classes"]:
            files[pad_file]["classes"]["TestPad"] = {}
        for i in range(15):
            files[pad_file]["classes"]["TestPad"][f"test_pad_{i}"] = "behavioral"
    return {"files": files, "summary": {"theater_risk": len(theater_items)}}


# ---------------------------------------------------------------------------
# TestRatchetLogic
# ---------------------------------------------------------------------------

class TestRatchetLogic:
    """Core ratchet comparison logic."""

    def test_passes_when_current_equals_allowlist_not_expired(self):
        entry = _make_entry()
        allowlist = _make_allowlist([entry])
        current = {(entry["file"], entry["class"], entry["method"])}
        result = check_ratchet(current, allowlist)
        assert result["passed"] is True
        assert result["new"] == []
        assert result["expired"] == []
        assert result["removals"] == []

    def test_fails_on_new_unallowlisted_method(self):
        allowlist = _make_allowlist([])
        current = {("mu/tests/l4_gates/test_x.py", "TestX", "test_y")}
        result = check_ratchet(current, allowlist)
        assert result["passed"] is False
        assert len(result["new"]) == 1
        assert result["new"][0]["method"] == "test_y"

    def test_fails_on_expired_entry(self):
        entry = _make_entry(expires_on="2020-01-01")
        allowlist = _make_allowlist([entry])
        current = {(entry["file"], entry["class"], entry["method"])}
        result = check_ratchet(current, allowlist)
        assert result["passed"] is False
        assert len(result["expired"]) == 1

    def test_fails_if_entry_classified_real(self):
        entry = _make_entry(classification="real")
        allowlist = _make_allowlist([entry])
        current = {(entry["file"], entry["class"], entry["method"])}
        result = check_ratchet(current, allowlist)
        assert result["passed"] is False
        assert len(result["real"]) == 1

    def test_removal_reported_but_does_not_fail(self):
        entry = _make_entry()
        allowlist = _make_allowlist([entry])
        current: set = set()  # method no longer in classifier
        result = check_ratchet(current, allowlist)
        assert result["passed"] is True
        assert len(result["removals"]) == 1
        assert result["removals"][0]["method"] == entry["method"]

    def test_output_sorted_deterministically(self):
        """Items reported in (file, class, method) order regardless of input."""
        allowlist = _make_allowlist([])
        current = {
            ("mu/tests/l4_gates/z.py", "Z", "test_z"),
            ("mu/tests/l4_gates/a.py", "A", "test_a"),
            ("mu/tests/l4_gates/m.py", "M", "test_m"),
        }
        result = check_ratchet(current, allowlist)
        files = [item["file"] for item in result["new"]]
        assert files == sorted(files)


# ---------------------------------------------------------------------------
# TestAllowlistValidation
# ---------------------------------------------------------------------------

class TestAllowlistValidation:
    """Allowlist schema validation tests."""

    def test_valid_allowlist_passes(self):
        data = _make_allowlist([_make_entry()])
        errors = validate_allowlist(data)
        assert errors == []

    def test_rejects_real_classification(self):
        entry = _make_entry(classification="real")
        data = _make_allowlist([entry])
        errors = validate_allowlist(data)
        assert any("'real' is forbidden" in e for e in errors)

    def test_rejects_duplicate_entries(self):
        entry = _make_entry()
        data = _make_allowlist([entry, entry])
        errors = validate_allowlist(data)
        assert any("duplicate" in e for e in errors)

    def test_rejects_invalid_file_path(self):
        entry = _make_entry(file="src/tests/bad.py")
        data = _make_allowlist([entry])
        errors = validate_allowlist(data)
        assert any("mu/tests/" in e for e in errors)

    def test_rejects_path_traversal(self):
        entry = _make_entry(file="mu/tests/../host/evil.py")
        data = _make_allowlist([entry])
        errors = validate_allowlist(data)
        assert any(".." in e for e in errors)

    def test_rejects_missing_required_field(self):
        entry = _make_entry()
        del entry["expires_on"]
        data = _make_allowlist([entry])
        errors = validate_allowlist(data)
        assert any("missing" in e for e in errors)

    def test_rejects_wrong_schema_version(self):
        data = _make_allowlist([_make_entry()])
        data["schema_version"] = 99
        errors = validate_allowlist(data)
        assert any("schema_version" in e for e in errors)

    def test_rejects_unknown_classification(self):
        entry = _make_entry(classification="maybe")
        data = _make_allowlist([entry])
        errors = validate_allowlist(data)
        assert any("classification must be" in e for e in errors)


# ---------------------------------------------------------------------------
# TestExtractTheaterRisk
# ---------------------------------------------------------------------------

class TestExtractTheaterRisk:
    """Classifier result extraction."""

    def test_extracts_theater_risk_only(self):
        classifier = {
            "files": {
                "test_a.py": {"classes": {"A": {
                    "test_good": "behavioral",
                    "test_bad": "theater_risk",
                }}},
            },
        }
        result = extract_theater_risk_set(classifier)
        assert result == {("test_a.py", "A", "test_bad")}

    def test_empty_classifier(self):
        result = extract_theater_risk_set({"files": {}})
        assert result == set()


# ---------------------------------------------------------------------------
# TestRatchetCLI
# ---------------------------------------------------------------------------

class TestRatchetCLI:
    """CLI integration tests."""

    def test_default_passes(self):
        """Default invocation with real allowlist should pass."""
        result = subprocess.run(
            ["python3", str(_tool_path)],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_json_output_schema(self, tmp_path):
        """--json output has expected keys."""
        # Create fixture files
        entry = _make_entry()
        allowlist = _make_allowlist([entry])
        al_path = tmp_path / "allowlist.json"
        al_path.write_text(json.dumps(allowlist))

        classifier = _make_classifier([
            (entry["file"], entry["class"], entry["method"]),
        ])
        cl_path = tmp_path / "classifier.json"
        cl_path.write_text(json.dumps(classifier))

        result = subprocess.run(
            ["python3", str(_tool_path),
             "--json",
             "--classifier-json", str(cl_path),
             "--allowlist", str(al_path)],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "passed" in data
        assert "new" in data
        assert "expired" in data
        assert "removals" in data
        assert data["passed"] is True

    def test_fails_on_new_via_cli(self, tmp_path):
        """CLI exits non-zero when new theater_risk found."""
        allowlist = _make_allowlist([])
        al_path = tmp_path / "allowlist.json"
        al_path.write_text(json.dumps(allowlist))

        classifier = _make_classifier([
            ("mu/tests/l4_gates/test_x.py", "X", "test_new"),
        ])
        cl_path = tmp_path / "classifier.json"
        cl_path.write_text(json.dumps(classifier))

        result = subprocess.run(
            ["python3", str(_tool_path),
             "--classifier-json", str(cl_path),
             "--allowlist", str(al_path)],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 1
        assert "FAIL" in result.stdout

    def test_update_allowlist_blocked_in_ci(self, tmp_path):
        """--update-allowlist exits non-zero when RCX_CI=1."""
        al_path = tmp_path / "allowlist.json"
        al_path.write_text(json.dumps(_make_allowlist([])))

        env = {**os.environ, "RCX_CI": "1"}
        result = subprocess.run(
            ["python3", str(_tool_path),
             "--update-allowlist",
             "--allowlist", str(al_path)],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
            env=env,
        )
        assert result.returncode == 1
        assert "forbidden in CI" in result.stderr


# ---------------------------------------------------------------------------
# TestClassifierValidation (B2)
# ---------------------------------------------------------------------------

class TestClassifierValidation:
    """Classifier payload schema validation (B2 blocker)."""

    def test_valid_classifier_passes(self):
        classifier = _make_classifier([
            ("mu/tests/l4_gates/test_a.py", "A", "test_x"),
        ])
        errors = validate_classifier_results(classifier)
        assert errors == []

    def test_malformed_classifier_not_dict(self):
        errors = validate_classifier_results([1, 2, 3])
        assert any("must be a dict" in e for e in errors)

    def test_missing_files_key(self):
        errors = validate_classifier_results({"summary": {}})
        assert any("'files'" in e for e in errors)

    def test_missing_summary_key(self):
        errors = validate_classifier_results({"files": {}})
        assert any("'summary'" in e for e in errors)

    def test_zero_scan_payload_fails(self):
        classifier = _make_classifier([], pad_to_minimum=False)
        errors = validate_classifier_results(classifier)
        assert any("zero-scan guard" in e for e in errors)

    def test_invalid_classification_rejected(self):
        # Use pad_to_minimum=False to isolate the classification error
        classifier = _make_classifier([], pad_to_minimum=False)
        classifier["files"]["f.py"] = {"classes": {"C": {"test_x": "unknown_cat"}}}
        errors = validate_classifier_results(classifier)
        assert any("unknown classification" in e for e in errors)

    def test_non_test_method_name_rejected(self):
        classifier = _make_classifier([], pad_to_minimum=False)
        classifier["files"]["f.py"] = {"classes": {"C": {"helper_func": "behavioral"}}}
        errors = validate_classifier_results(classifier)
        assert any("test_" in e for e in errors)

    def test_files_not_dict_rejected(self):
        errors = validate_classifier_results({"files": "bad", "summary": {}})
        assert any("'files' must be a dict" in e for e in errors)


# ---------------------------------------------------------------------------
# TestInvocationPaths (B1)
# ---------------------------------------------------------------------------

class TestInvocationPaths:
    """Both tools/ and mu/tools/ paths must work (B1 blocker)."""

    def test_ratchet_via_tools_path(self):
        result = subprocess.run(
            ["python3", "tools/checks/check_theater_risk_ratchet.py"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_ratchet_via_mu_tools_path(self):
        result = subprocess.run(
            ["python3", "mu/tools/checks/check_theater_risk_ratchet.py"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_classifier_via_tools_path(self):
        result = subprocess.run(
            ["python3", "tools/checks/check_gate_behavioral_pairs.py", "--json"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "files" in data
        assert "summary" in data

    def test_classifier_via_mu_tools_path(self):
        result = subprocess.run(
            ["python3", "mu/tools/checks/check_gate_behavioral_pairs.py", "--json"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "files" in data
        assert "summary" in data
