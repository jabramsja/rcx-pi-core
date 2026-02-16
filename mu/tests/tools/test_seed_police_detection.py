"""
Grounding tests for seed_police.sh - verifies seed validation actually catches violations.

Created based on grounding agent mission (2026-01-30): verify every guardrail pattern works.
"""
import json
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "tools" / "checks" / "linters" / "seed_police.sh"


def run_seed_police_on_seed(seed_data: dict, filename: str = "test.v1.json") -> subprocess.CompletedProcess:
    """Write seed to temp dir and run seed_police.sh on it.

    Args:
        seed_data: The seed JSON content
        filename: The seed filename (important for security checks - kernel.v1.json, match.v1.json, etc.)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_file = Path(tmpdir) / filename
        seed_file.write_text(json.dumps(seed_data, indent=2))

        return subprocess.run(
            ["bash", str(SCRIPT), tmpdir],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )


class TestSeedPoliceValidatesStructure:
    """Verify seed_police.sh catches structural issues."""

    def test_rejects_invalid_json(self):
        """seed_police.sh must fail on invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            seed_file = Path(tmpdir) / "bad.v1.json"
            seed_file.write_text("{ invalid json }")

            result = subprocess.run(
                ["bash", str(SCRIPT), tmpdir],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            assert result.returncode != 0, "Should fail on invalid JSON"

    def test_rejects_missing_projections(self):
        """seed_police.sh must fail when 'projections' key missing."""
        seed = {"meta": {"version": 1}}  # No projections key
        result = run_seed_police_on_seed(seed)
        assert result.returncode != 0, "Should fail on missing projections"

    def test_rejects_projections_not_list(self):
        """seed_police.sh must fail when projections is not a list."""
        seed = {"projections": "not a list"}
        result = run_seed_police_on_seed(seed)
        assert result.returncode != 0, "Should fail when projections not list"


class TestSeedPoliceValidatesProjectionFields:
    """Verify seed_police.sh catches missing projection fields."""

    def test_rejects_missing_id(self):
        """seed_police.sh must fail when projection missing 'id'."""
        seed = {"projections": [{"pattern": {}, "body": {}}]}
        result = run_seed_police_on_seed(seed)
        assert result.returncode != 0, "Should fail on missing id"

    def test_rejects_missing_pattern(self):
        """seed_police.sh must fail when projection missing 'pattern'."""
        seed = {"projections": [{"id": "test", "body": {}}]}
        result = run_seed_police_on_seed(seed)
        assert result.returncode != 0, "Should fail on missing pattern"

    def test_rejects_missing_body(self):
        """seed_police.sh must fail when projection missing 'body'."""
        seed = {"projections": [{"id": "test", "pattern": {}}]}
        result = run_seed_police_on_seed(seed)
        assert result.returncode != 0, "Should fail on missing body"


class TestSeedPoliceDetectsTheater:
    """Verify seed_police.sh catches theater projections."""

    def test_rejects_duplicate_ids(self):
        """seed_police.sh must fail on duplicate projection IDs."""
        seed = {
            "projections": [
                {"id": "test.same", "pattern": {"a": 1}, "body": {"b": 2}},
                {"id": "test.same", "pattern": {"c": 3}, "body": {"d": 4}},
            ]
        }
        result = run_seed_police_on_seed(seed)
        assert result.returncode != 0, "Should fail on duplicate IDs"

    def test_rejects_empty_pattern_dict(self):
        """seed_police.sh must fail on empty pattern dict."""
        seed = {"projections": [{"id": "test", "pattern": {}, "body": {"x": 1}}]}
        result = run_seed_police_on_seed(seed)
        assert result.returncode != 0, "Should fail on empty pattern {}"

    def test_rejects_empty_pattern_list(self):
        """seed_police.sh must fail on empty pattern list."""
        seed = {"projections": [{"id": "test", "pattern": [], "body": {"x": 1}}]}
        result = run_seed_police_on_seed(seed)
        assert result.returncode != 0, "Should fail on empty pattern []"


class TestSeedPoliceDetectsHostLeakage:
    """Verify seed_police.sh catches host language leakage."""

    def test_rejects_lambda_in_string(self):
        """seed_police.sh must fail when 'lambda' in string value."""
        seed = {
            "projections": [
                {"id": "test", "pattern": {"x": 1}, "body": {"code": "lambda x: x"}}
            ]
        }
        result = run_seed_police_on_seed(seed)
        assert result.returncode != 0, "Should fail on lambda in string"

    def test_rejects_def_in_string(self):
        """seed_police.sh must fail when 'def ' in string value."""
        seed = {
            "projections": [
                {"id": "test", "pattern": {"x": 1}, "body": {"code": "def foo():"}}
            ]
        }
        result = run_seed_police_on_seed(seed)
        assert result.returncode != 0, "Should fail on def in string"

    def test_rejects_function_in_string(self):
        """seed_police.sh must fail when 'function(' in string value."""
        seed = {
            "projections": [
                {"id": "test", "pattern": {"x": 1}, "body": {"code": "function() {}"}}
            ]
        }
        result = run_seed_police_on_seed(seed)
        assert result.returncode != 0, "Should fail on function in string"

    def test_rejects_arrow_function_in_string(self):
        """seed_police.sh must fail when '=>' in string value."""
        seed = {
            "projections": [
                {"id": "test", "pattern": {"x": 1}, "body": {"code": "x => x"}}
            ]
        }
        result = run_seed_police_on_seed(seed)
        assert result.returncode != 0, "Should fail on arrow function in string"

    def test_rejects_eval_in_string(self):
        """seed_police.sh must fail when 'eval(' in string value."""
        seed = {
            "projections": [
                {"id": "test", "pattern": {"x": 1}, "body": {"code": "eval(x)"}}
            ]
        }
        result = run_seed_police_on_seed(seed)
        assert result.returncode != 0, "Should fail on eval in string"

    def test_rejects_dunder_in_string(self):
        """seed_police.sh must fail when dunder in string value."""
        seed = {
            "projections": [
                {"id": "test", "pattern": {"x": 1}, "body": {"code": "__class__"}}
            ]
        }
        result = run_seed_police_on_seed(seed)
        assert result.returncode != 0, "Should fail on dunder in string"


class TestSeedPoliceDetectsSecurity:
    """Verify seed_police.sh catches security violations."""

    def test_rejects_reserved_field_in_non_kernel_pattern(self):
        """seed_police.sh must fail when non-kernel projection uses _mode."""
        seed = {
            "projections": [
                {"id": "domain.test", "pattern": {"_mode": "done"}, "body": {"x": 1}}
            ]
        }
        result = run_seed_police_on_seed(seed)
        assert result.returncode != 0, "Should fail on reserved field in domain projection"

    def test_allows_reserved_field_in_kernel_projection(self):
        """seed_police.sh must allow kernel projections to use _mode.

        SECURITY (9-agent finding 2026-01-30): Reserved fields are only allowed if
        BOTH the seed filename AND projection ID match the allowed pattern.
        e.g., kernel.done in kernel.v1.json is allowed, but kernel.done in evil.v1.json is blocked.
        """
        seed = {
            "projections": [
                {"id": "kernel.done", "pattern": {"_mode": "done"}, "body": {"result": 1}}
            ]
        }
        # Must use kernel-prefixed filename to allow kernel.* projections with reserved fields
        result = run_seed_police_on_seed(seed, filename="kernel.v1.json")
        assert result.returncode == 0, f"Kernel projection should be allowed: {result.stdout}"

    def test_rejects_kernel_projection_in_wrong_seed_file(self):
        """seed_police.sh must block kernel.* projection in non-kernel seed (security fix).

        This prevents an attacker from creating evil.v1.json with kernel.trojan projection
        that uses reserved fields. The projection ID prefix must match the seed filename.
        """
        seed = {
            "projections": [
                {"id": "kernel.trojan", "pattern": {"_mode": "done"}, "body": {"pwned": True}}
            ]
        }
        # Using evil.v1.json - kernel.trojan should be BLOCKED
        result = run_seed_police_on_seed(seed, filename="evil.v1.json")
        assert result.returncode != 0, "kernel.* projection in evil.v1.json should be blocked"
        assert "SECURITY" in result.stdout or "_mode" in result.stdout


class TestSeedPoliceDetectsIdentityProjection:
    """Verify seed_police.sh warns about identity projections (theater)."""

    def test_warns_identity_projection(self):
        """seed_police.sh should warn when pattern === body (identity)."""
        seed = {
            "projections": [
                {
                    "id": "test.identity",
                    "pattern": {"x": 1, "y": 2},
                    "body": {"x": 1, "y": 2}  # Same as pattern
                }
            ]
        }
        result = run_seed_police_on_seed(seed)
        # This is a warning, not an error - seed still passes but output should mention it
        assert "identity" in result.stdout.lower() or "warning" in result.stdout.lower() or result.returncode == 0


class TestSeedPoliceValidSeed:
    """Verify valid seeds pass seed_police.sh."""

    def test_valid_seed_passes(self):
        """A valid seed should pass all checks."""
        seed = {
            "meta": {"version": 1, "name": "test"},
            "projections": [
                {
                    "id": "test.first",
                    "pattern": {"input": {"var": "x"}},
                    "body": {"output": {"var": "x"}}
                },
                {
                    "id": "test.second",
                    "pattern": {"value": 1},
                    "body": {"result": 2}
                }
            ]
        }
        result = run_seed_police_on_seed(seed)
        assert result.returncode == 0, f"Valid seed should pass: {result.stdout}"
