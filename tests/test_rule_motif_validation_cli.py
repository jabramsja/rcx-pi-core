"""
Rule Motif Validation CLI Tests.

Tests the `rules --check-rule-motifs` CLI flag using subprocess calls only.
All assertions are based on PUBLIC interface output, no engine internals.

See docs/RuleAsMotif.v0.md for spec.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import Any, Dict, Tuple

import pytest


def _run_cli_check_rule_motifs() -> Tuple[int, str, str]:
    """
    Run CLI with --check-rule-motifs and return (exit_code, stdout, stderr).

    Uses subprocess to ensure we test the PUBLIC interface only.
    """
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"

    result = subprocess.run(
        [
            "python3", "-m", "rcx_pi.rcx_cli", "rules",
            "--check-rule-motifs",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def _run_cli_check_rule_motifs_from(path: str) -> Tuple[int, str, str]:
    """
    Run CLI with --check-rule-motifs-from and return (exit_code, stdout, stderr).
    """
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"

    result = subprocess.run(
        [
            "python3", "-m", "rcx_pi.rcx_cli", "rules",
            "--check-rule-motifs-from", path,
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


class TestCheckRuleMotifsCliRuns:
    """CLI must succeed and produce valid output for built-in motifs."""

    def test_exit_code_zero(self) -> None:
        """CLI with --check-rule-motifs must succeed for built-in motifs."""
        exit_code, stdout, stderr = _run_cli_check_rule_motifs()
        assert exit_code == 0, f"CLI failed: {stderr}"

    def test_produces_valid_json(self) -> None:
        """CLI must produce valid JSON output."""
        exit_code, stdout, stderr = _run_cli_check_rule_motifs()
        assert exit_code == 0
        report = json.loads(stdout.strip())
        assert isinstance(report, dict)

    def test_report_ok_is_true(self) -> None:
        """Built-in rule motifs must pass validation (ok=true)."""
        exit_code, stdout, _ = _run_cli_check_rule_motifs()
        assert exit_code == 0
        report = json.loads(stdout.strip())
        assert report["ok"] is True

    def test_report_has_required_fields(self) -> None:
        """Report must have v, rule_count, ok, errors fields."""
        exit_code, stdout, _ = _run_cli_check_rule_motifs()
        assert exit_code == 0
        report = json.loads(stdout.strip())
        assert "v" in report
        assert report["v"] == 1
        assert "rule_count" in report
        assert report["rule_count"] == 8  # 8 rules from rules_pure.py
        assert "ok" in report
        assert "errors" in report
        assert isinstance(report["errors"], list)

    def test_no_errors_for_builtin_motifs(self) -> None:
        """Built-in motifs must have zero validation errors."""
        exit_code, stdout, _ = _run_cli_check_rule_motifs()
        assert exit_code == 0
        report = json.loads(stdout.strip())
        assert report["errors"] == []


class TestCheckRuleMotifsDeterminism:
    """Output must be deterministic across runs."""

    def test_identical_output_twice(self) -> None:
        """Two runs must produce identical output."""
        exit1, stdout1, _ = _run_cli_check_rule_motifs()
        exit2, stdout2, _ = _run_cli_check_rule_motifs()

        assert exit1 == exit2 == 0
        assert stdout1 == stdout2, "Non-deterministic output detected"

    def test_output_is_compact_json(self) -> None:
        """Output must use compact JSON (no extra whitespace)."""
        exit_code, stdout, _ = _run_cli_check_rule_motifs()
        assert exit_code == 0

        line = stdout.strip()
        parsed = json.loads(line)
        compact = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
        assert line == compact, f"Non-compact JSON detected:\n{line}\nvs\n{compact}"


class TestCheckRuleMotifsFromFile:
    """Test --check-rule-motifs-from with custom files."""

    def test_valid_motifs_from_file(self) -> None:
        """Valid motifs in a file should pass validation."""
        valid_motifs = [
            {
                "rule": {
                    "id": "test.rule",
                    "pattern": {"op": "test", "x": {"var": "a"}},
                    "body": {"var": "a"},
                }
            }
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(valid_motifs, f)
            f.flush()
            path = f.name

        try:
            exit_code, stdout, stderr = _run_cli_check_rule_motifs_from(path)
            assert exit_code == 0, f"CLI failed: {stderr}"
            report = json.loads(stdout.strip())
            assert report["ok"] is True
            assert report["rule_count"] == 1
            assert report["errors"] == []
        finally:
            os.unlink(path)

    def test_unbound_var_error(self) -> None:
        """Motif with unbound variable in body must fail validation."""
        broken_motifs = [
            {
                "rule": {
                    "id": "broken.unbound",
                    "pattern": {"op": "noop"},
                    "body": {"var": "x"},  # x is not bound in pattern
                }
            }
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(broken_motifs, f)
            f.flush()
            path = f.name

        try:
            exit_code, stdout, stderr = _run_cli_check_rule_motifs_from(path)
            assert exit_code == 1, "Expected exit code 1 for invalid motifs"
            report = json.loads(stdout.strip())
            assert report["ok"] is False
            assert len(report["errors"]) >= 1
            # Find the UNBOUND_VAR error
            unbound_errors = [
                e for e in report["errors"] if e["code"] == "UNBOUND_VAR"
            ]
            assert len(unbound_errors) == 1
            assert "x" in unbound_errors[0]["detail"]
        finally:
            os.unlink(path)

    def test_missing_id_error(self) -> None:
        """Motif missing rule.id must fail validation."""
        broken_motifs = [
            {
                "rule": {
                    "pattern": {"op": "noop"},
                    "body": {"value": 0},
                }
            }
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(broken_motifs, f)
            f.flush()
            path = f.name

        try:
            exit_code, stdout, _ = _run_cli_check_rule_motifs_from(path)
            assert exit_code == 1
            report = json.loads(stdout.strip())
            assert report["ok"] is False
            missing_id_errors = [
                e for e in report["errors"] if e["code"] == "MISSING_ID"
            ]
            assert len(missing_id_errors) == 1
        finally:
            os.unlink(path)

    def test_duplicate_id_error(self) -> None:
        """Motifs with duplicate rule.id must fail validation."""
        broken_motifs = [
            {
                "rule": {
                    "id": "dup.rule",
                    "pattern": {"op": "a"},
                    "body": {"value": 1},
                }
            },
            {
                "rule": {
                    "id": "dup.rule",  # duplicate
                    "pattern": {"op": "b"},
                    "body": {"value": 2},
                }
            },
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(broken_motifs, f)
            f.flush()
            path = f.name

        try:
            exit_code, stdout, _ = _run_cli_check_rule_motifs_from(path)
            assert exit_code == 1
            report = json.loads(stdout.strip())
            assert report["ok"] is False
            dup_errors = [
                e for e in report["errors"] if e["code"] == "DUPLICATE_ID"
            ]
            assert len(dup_errors) == 1
        finally:
            os.unlink(path)

    def test_missing_pattern_error(self) -> None:
        """Motif missing pattern must fail validation."""
        broken_motifs = [
            {
                "rule": {
                    "id": "no.pattern",
                    "body": {"value": 0},
                }
            }
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(broken_motifs, f)
            f.flush()
            path = f.name

        try:
            exit_code, stdout, _ = _run_cli_check_rule_motifs_from(path)
            assert exit_code == 1
            report = json.loads(stdout.strip())
            assert report["ok"] is False
            missing_pattern_errors = [
                e for e in report["errors"] if e["code"] == "MISSING_PATTERN"
            ]
            assert len(missing_pattern_errors) == 1
        finally:
            os.unlink(path)

    def test_missing_body_error(self) -> None:
        """Motif missing body must fail validation."""
        broken_motifs = [
            {
                "rule": {
                    "id": "no.body",
                    "pattern": {"op": "test"},
                }
            }
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(broken_motifs, f)
            f.flush()
            path = f.name

        try:
            exit_code, stdout, _ = _run_cli_check_rule_motifs_from(path)
            assert exit_code == 1
            report = json.loads(stdout.strip())
            assert report["ok"] is False
            missing_body_errors = [
                e for e in report["errors"] if e["code"] == "MISSING_BODY"
            ]
            assert len(missing_body_errors) == 1
        finally:
            os.unlink(path)

    def test_file_not_found_error(self) -> None:
        """Non-existent file must fail with LOAD_ERROR."""
        exit_code, stdout, _ = _run_cli_check_rule_motifs_from(
            "/nonexistent/path/to/motifs.json"
        )
        assert exit_code == 1
        report = json.loads(stdout.strip())
        assert report["ok"] is False
        load_errors = [e for e in report["errors"] if e["code"] == "LOAD_ERROR"]
        assert len(load_errors) == 1

    def test_invalid_json_error(self) -> None:
        """Invalid JSON file must fail with LOAD_ERROR."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("not valid json {{{")
            f.flush()
            path = f.name

        try:
            exit_code, stdout, _ = _run_cli_check_rule_motifs_from(path)
            assert exit_code == 1
            report = json.loads(stdout.strip())
            assert report["ok"] is False
            load_errors = [
                e for e in report["errors"] if e["code"] == "LOAD_ERROR"
            ]
            assert len(load_errors) == 1
        finally:
            os.unlink(path)

    def test_not_array_error(self) -> None:
        """JSON that is not an array must fail with INVALID_FORMAT."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"not": "an array"}, f)
            f.flush()
            path = f.name

        try:
            exit_code, stdout, _ = _run_cli_check_rule_motifs_from(path)
            assert exit_code == 1
            report = json.loads(stdout.strip())
            assert report["ok"] is False
            fmt_errors = [
                e for e in report["errors"] if e["code"] == "INVALID_FORMAT"
            ]
            assert len(fmt_errors) == 1
        finally:
            os.unlink(path)
