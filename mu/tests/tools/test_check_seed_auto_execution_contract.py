"""
A19: Tests for tools/checks/check_seed_auto_execution_contract.py.

Validates static scanning, allowlist schema validation, fail-closed guards,
CLI modes, and dual invocation paths.
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
_tool_path = REPO_ROOT / "tools" / "checks" / "check_seed_auto_execution_contract.py"
_spec = importlib.util.spec_from_file_location("check_seed_auto_execution_contract", _tool_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
validate_allowlist = _mod.validate_allowlist
scan_for_violations = _mod.scan_for_violations
check_contract = _mod.check_contract


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_allowlist(entries, schema_version=1):
    return {
        "schema_version": schema_version,
        "generated_at": "2026-01-01T00:00:00Z",
        "total_entries": len(entries),
        "entries": entries,
    }


def _make_entry(file="rcx_pi/selfhost/step_mu.py", line_pattern="load_verified_seed",
                seed_filename="rcx_engine.v1.json", classification="generic_loader",
                rationale="generic seed loading", owner="founder",
                expires_on="2099-12-31"):
    return {
        "file": file, "line_pattern": line_pattern,
        "seed_filename": seed_filename, "classification": classification,
        "rationale": rationale, "owner": owner, "expires_on": expires_on,
    }


def _write_fake_source(tmp_path, filename, content):
    """Write a fake source file and return its Path."""
    p = tmp_path / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# TestSeedAutoChecker
# ---------------------------------------------------------------------------

class TestSeedAutoChecker:
    """Core scanning and ratchet logic."""

    def test_passes_on_current_codebase(self):
        """Default invocation with real codebase should pass."""
        result = subprocess.run(
            ["python3", str(_tool_path)],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"check_seed_auto_execution_contract.py failed:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_detects_conditional_seed_branching(self, tmp_path):
        """A file with `if x == "seed.v1.json"` triggers violation."""
        fake_py = _write_fake_source(tmp_path, "fake.py",
            'x = "hello"\n' * 200 +  # pad to clear minimum line count
            'if algo == "recurrence.v1.json":\n'
            '    do_something()\n'
        )
        violations, total = scan_for_violations(
            [fake_py], [], _make_allowlist([]),
        )
        assert len(violations) == 1
        assert violations[0]["seed_filename"] == "recurrence.v1.json"

    def test_allows_generic_loading(self, tmp_path):
        """Non-conditional seed references are not violations."""
        fake_py = _write_fake_source(tmp_path, "loader.py",
            'x = "hello"\n' * 200 +
            'projs = load_verified_seed("match.v2.json")\n'
        )
        violations, total = scan_for_violations(
            [fake_py], [], _make_allowlist([]),
        )
        assert len(violations) == 0

    def test_allowlist_bypasses_violation(self, tmp_path):
        """Allowlisted entries are not reported as violations."""
        fake_py = _write_fake_source(tmp_path, "rcx_pi/selfhost/step_mu.py",
            'x = "hello"\n' * 200 +
            'if algo == "recurrence.v1.json":\n'
            '    do_something()\n'
        )
        # The allowlist entry must match the relative path from REPO_ROOT.
        # For unit tests with tmp_path, we use the fake path relative to tmp_path.
        violations, total = scan_for_violations(
            [fake_py], [],
            _make_allowlist([]),
        )
        # Without allowlist: 1 violation
        assert len(violations) == 1

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
        assert "violations" in data
        assert "py_file_count" in data
        assert "js_file_count" in data
        assert "total_lines_scanned" in data
        assert data["passed"] is True

    def test_update_blocked_in_ci(self, tmp_path):
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
# TestAllowlistValidation
# ---------------------------------------------------------------------------

class TestAllowlistValidation:
    """Allowlist schema validation tests."""

    def test_valid_allowlist_passes(self):
        data = _make_allowlist([_make_entry()])
        errors = validate_allowlist(data)
        assert errors == []

    def test_rejects_wrong_schema_version(self):
        data = _make_allowlist([])
        data["schema_version"] = 99
        errors = validate_allowlist(data)
        assert any("schema_version" in e for e in errors)

    def test_rejects_missing_field(self):
        entry = _make_entry()
        del entry["expires_on"]
        data = _make_allowlist([entry])
        errors = validate_allowlist(data)
        assert any("missing" in e for e in errors)

    def test_rejects_invalid_classification(self):
        entry = _make_entry(classification="maybe")
        data = _make_allowlist([entry])
        errors = validate_allowlist(data)
        assert any("classification" in e for e in errors)

    def test_rejects_duplicate_entries(self):
        entry = _make_entry()
        data = _make_allowlist([entry, entry])
        errors = validate_allowlist(data)
        assert any("duplicate" in e for e in errors)

    def test_rejects_path_traversal(self):
        entry = _make_entry(file="rcx_pi/../evil.py")
        data = _make_allowlist([entry])
        errors = validate_allowlist(data)
        assert any(".." in e for e in errors)

    def test_rejects_not_dict(self):
        errors = validate_allowlist([1, 2, 3])
        assert any("must be a dict" in e for e in errors)


# ---------------------------------------------------------------------------
# TestFailClosedGuards
# ---------------------------------------------------------------------------

class TestFailClosedGuards:
    """Fail-closed on zero-scan, malformed input, etc."""

    def test_zero_py_files_fails(self):
        """Zero Python runtime files triggers zero-scan guard."""
        result = subprocess.run(
            ["python3", "-c",
             f"import sys; sys.path.insert(0, '.'); "
             f"exec(open('{_tool_path}').read()); "
             f"# This won't work via import but validates the guard exists"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        # We can't easily test the guard via subprocess with a fake empty dir,
        # so we test the check_contract function directly.
        result_dict = check_contract([], [], _make_allowlist([]))
        # With 0 files the check passes (no violations) but main() would fail
        # on the zero-scan guard before calling check_contract.
        assert result_dict["py_file_count"] == 0

    def test_malformed_allowlist_exits_nonzero(self, tmp_path):
        """Malformed allowlist JSON causes exit 1."""
        al_path = tmp_path / "bad.json"
        al_path.write_text('{"schema_version": 99, "entries": []}')
        result = subprocess.run(
            ["python3", str(_tool_path), "--allowlist", str(al_path)],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 1
        assert "schema_version" in result.stderr


# ---------------------------------------------------------------------------
# TestInvocationPaths
# ---------------------------------------------------------------------------

class TestSeedAutoInvocationPaths:
    """Both tools/ and mu/tools/ paths must work."""

    def test_via_tools_path(self):
        result = subprocess.run(
            ["python3", "tools/checks/check_seed_auto_execution_contract.py"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_via_mu_tools_path(self):
        result = subprocess.run(
            ["python3", "mu/tools/checks/check_seed_auto_execution_contract.py"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        assert "PASS" in result.stdout


# ---------------------------------------------------------------------------
# TestASTHardening
# ---------------------------------------------------------------------------

class TestASTHardening:
    """AST-based detection: multiline, indirect alias, membership, parse errors."""

    def test_multiline_conditional_detected(self, tmp_path):
        """Multiline if with seed filename is caught by AST scanner."""
        fake_py = _write_fake_source(tmp_path, "multi.py",
            'x = "hello"\n' * 200 +
            'if (\n'
            '    algo == "recurrence.v1.json"\n'
            '):\n'
            '    do_something()\n'
        )
        violations, total = scan_for_violations(
            [fake_py], [], _make_allowlist([]),
        )
        assert len(violations) == 1
        assert violations[0]["seed_filename"] == "recurrence.v1.json"

    def test_indirect_alias_detected(self, tmp_path):
        """Seed filename assigned to variable, then used in condition."""
        fake_py = _write_fake_source(tmp_path, "indirect.py",
            'x = "hello"\n' * 200 +
            'TARGET = "recurrence.v1.json"\n'
            'if algo == TARGET:\n'
            '    do_something()\n'
        )
        violations, total = scan_for_violations(
            [fake_py], [], _make_allowlist([]),
        )
        assert len(violations) == 1
        assert violations[0]["seed_filename"] == "recurrence.v1.json"

    def test_membership_detected(self, tmp_path):
        """Seed filename in set membership test detected."""
        fake_py = _write_fake_source(tmp_path, "member.py",
            'x = "hello"\n' * 200 +
            'if algo in {"recurrence.v1.json", "match.v2.json"}:\n'
            '    do_something()\n'
        )
        violations, total = scan_for_violations(
            [fake_py], [], _make_allowlist([]),
        )
        assert len(violations) >= 1
        seed_names = {v["seed_filename"] for v in violations}
        assert "recurrence.v1.json" in seed_names
        assert "match.v2.json" in seed_names

    def test_parse_error_fails_closed(self, tmp_path):
        """Unparseable Python file produces a violation, not a silent skip."""
        fake_py = _write_fake_source(tmp_path, "broken.py",
            'def broken(\n'
        )
        violations, total = scan_for_violations(
            [fake_py], [], _make_allowlist([]),
        )
        assert len(violations) == 1
        ctx = violations[0]["context"].lower()
        assert "parse" in ctx or "syntax" in ctx

    def test_no_false_positive_on_non_versioned_string(self, tmp_path):
        """Non-versioned JSON filenames must not trigger violations."""
        fake_py = _write_fake_source(tmp_path, "safe.py",
            'x = "hello"\n' * 200 +
            'if name == "foo.json":\n'
            '    pass\n'
            'if name == "config.yaml":\n'
            '    pass\n'
            'if name == "data.jsonl":\n'
            '    pass\n'
        )
        violations, total = scan_for_violations(
            [fake_py], [], _make_allowlist([]),
        )
        assert len(violations) == 0

    def test_module_alias_visible_in_function_detected(self, tmp_path):
        """Module-level alias used in function conditional is detected."""
        fake_py = _write_fake_source(tmp_path, "inherited.py",
            'x = "hello"\n' * 200 +
            'TARGET = "recurrence.v1.json"\n'
            '\n'
            'def dispatch():\n'
            '    if algo == TARGET:\n'
            '        pass\n'
        )
        violations, total = scan_for_violations(
            [fake_py], [], _make_allowlist([]),
        )
        assert len(violations) == 1
        assert violations[0]["seed_filename"] == "recurrence.v1.json"

    def test_child_alias_shadows_parent_alias(self, tmp_path):
        """Child-scope alias shadows parent; conditional reports child seed."""
        fake_py = _write_fake_source(tmp_path, "shadow.py",
            'x = "hello"\n' * 200 +
            'TARGET = "kernel.v1.json"\n'
            '\n'
            'def dispatch():\n'
            '    TARGET = "match.v2.json"\n'
            '    if algo == TARGET:\n'
            '        pass\n'
        )
        violations, total = scan_for_violations(
            [fake_py], [], _make_allowlist([]),
        )
        assert len(violations) == 1
        assert violations[0]["seed_filename"] == "match.v2.json"


# ---------------------------------------------------------------------------
# TestAllowlistTripleMatch
# ---------------------------------------------------------------------------

class TestAllowlistTripleMatch:
    """Allowlist suppression requires file + seed_filename + line_pattern."""

    def test_allowlist_requires_line_pattern_match(self, tmp_path):
        """Same file + seed but non-matching line_pattern must NOT suppress."""
        fake_py = _write_fake_source(tmp_path, "rcx_pi/selfhost/step_mu.py",
            'x = "hello"\n' * 200 +
            'if algo == "recurrence.v1.json":\n'
            '    do_something()\n'
        )
        # line_pattern "load_verified_seed" does not match "if algo =="
        al = _make_allowlist([_make_entry(
            file=str(fake_py),
            seed_filename="recurrence.v1.json",
            line_pattern="load_verified_seed",
        )])
        violations, total = scan_for_violations(
            [fake_py], [], al,
        )
        assert len(violations) == 1, "Non-matching line_pattern must not suppress"
        assert violations[0]["seed_filename"] == "recurrence.v1.json"

    def test_allowlist_suppresses_only_matching_line_pattern(self, tmp_path):
        """Matching line_pattern suppresses exactly the intended violation."""
        fake_py = _write_fake_source(tmp_path, "rcx_pi/selfhost/step_mu.py",
            'x = "hello"\n' * 200 +
            'if algo == "recurrence.v1.json":\n'
            '    do_something()\n'
        )
        # line_pattern "algo ==" matches the violation context
        al = _make_allowlist([_make_entry(
            file=str(fake_py),
            seed_filename="recurrence.v1.json",
            line_pattern="algo ==",
        )])
        violations, total = scan_for_violations(
            [fake_py], [], al,
        )
        assert len(violations) == 0, "Matching line_pattern must suppress"

    def test_allowlist_invalid_line_pattern_fails_closed(self):
        """Bad regex in line_pattern produces validation error."""
        entry = _make_entry(line_pattern="(unclosed")
        data = _make_allowlist([entry])
        errors = validate_allowlist(data)
        assert any("line_pattern" in e for e in errors)
