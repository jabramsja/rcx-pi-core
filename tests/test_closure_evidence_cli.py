"""
Closure Evidence CLI Tests.

Tests the --print-closure-evidence CLI flag using subprocess calls only.
All assertions are based on PUBLIC interface output, no engine internals.

See docs/execution/ClosureEvidence.v0.md and docs/execution/IndependentEncounter.v0.md for spec.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest


FIXTURES_DIR = Path("tests/fixtures/traces_v2/independent_encounter")
CANONICAL_FIXTURES_DIR = Path("tests/fixtures/traces_v2/closure_evidence")


def _run_cli_closure_evidence(fixture_path: Path) -> Tuple[int, str]:
    """
    Run CLI replay with --print-closure-evidence and return (exit_code, stdout).

    Uses subprocess to ensure we test the PUBLIC interface only.
    """
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"

    result = subprocess.run(
        [
            "python3", "-m", "rcx_pi.rcx_cli", "replay",
            "--trace", str(fixture_path),
            "--print-closure-evidence",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stdout


def _run_cli_closure_evidence_with_canon(fixture_path: Path) -> Tuple[int, str]:
    """Run CLI with both --check-canon and --print-closure-evidence."""
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"

    result = subprocess.run(
        [
            "python3", "-m", "rcx_pi.rcx_cli", "replay",
            "--trace", str(fixture_path),
            "--check-canon",
            "--print-closure-evidence",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stdout


def _parse_closure_evidence(output: str) -> Dict[str, Any]:
    """Parse closure evidence JSON from CLI output."""
    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    for ln in reversed(lines):
        if ln.startswith("{") and ln.endswith("}"):
            return json.loads(ln)
    raise ValueError(f"No JSON found in output:\n{output}")


# Expected evidence per fixture (based on IndependentEncounter.v0.md pathological scenarios)
# These fixtures use reduction.stall (observational) and test without --check-canon
FIXTURE_EXPECTATIONS = {
    # Scenario 1: A-then-B-then-A -> closure for pattern 101
    "a_then_b_then_a.v2.jsonl": {
        "evidence_count": 1,
        "evidence_patterns": [("101", "aaaaaaaaaaaaaaaa")],
        "counts": {"stall": 3, "fix": 0, "fixed": 0},
    },
    # Scenario 2: Idempotent fixed clears memory -> NO closure
    "idempotent_fixed_resets.v2.jsonl": {
        "evidence_count": 0,
        "evidence_patterns": [],
        "counts": {"stall": 2, "fix": 0, "fixed": 1},
    },
    # Scenario 5: Overwrite same pattern with different value -> NO closure
    "overwrite_same_pattern.v2.jsonl": {
        "evidence_count": 0,
        "evidence_patterns": [],
        "counts": {"stall": 3, "fix": 0, "fixed": 0},
    },
    # Scenario 7: execution.fix does not reset -> closure on second stall
    "fix_does_not_reset.v2.jsonl": {
        "evidence_count": 1,
        "evidence_patterns": [("303", "eeeeeeeeeeeeeeee")],
        "counts": {"stall": 2, "fix": 1, "fixed": 0},
    },
}


@pytest.mark.parametrize("fixture_name", list(FIXTURE_EXPECTATIONS.keys()))
def test_closure_evidence_cli_runs(fixture_name: str) -> None:
    """CLI with --print-closure-evidence must succeed for all fixtures."""
    path = FIXTURES_DIR / fixture_name
    exit_code, output = _run_cli_closure_evidence(path)
    assert exit_code == 0, f"CLI failed for {fixture_name}:\n{output}"


@pytest.mark.parametrize("fixture_name", list(FIXTURE_EXPECTATIONS.keys()))
def test_closure_evidence_cli_schema(fixture_name: str) -> None:
    """CLI output must have correct schema keys."""
    path = FIXTURES_DIR / fixture_name
    exit_code, output = _run_cli_closure_evidence(path)
    assert exit_code == 0

    evidence = _parse_closure_evidence(output)

    # Schema validation
    assert "v" in evidence
    assert evidence["v"] == 1
    assert "counts" in evidence
    assert set(evidence["counts"].keys()) == {"stall", "fix", "fixed"}
    assert "evidence" in evidence
    assert isinstance(evidence["evidence"], list)
    assert "evidence_count" in evidence
    assert evidence["evidence_count"] == len(evidence["evidence"])


@pytest.mark.parametrize("fixture_name", list(FIXTURE_EXPECTATIONS.keys()))
def test_closure_evidence_cli_matches_expectation(fixture_name: str) -> None:
    """CLI output must match expected evidence per IndependentEncounter.v0.md."""
    path = FIXTURES_DIR / fixture_name
    exit_code, output = _run_cli_closure_evidence(path)
    expected = FIXTURE_EXPECTATIONS[fixture_name]
    assert exit_code == 0

    evidence = _parse_closure_evidence(output)

    # Evidence count
    assert evidence["evidence_count"] == expected["evidence_count"], (
        f"evidence_count mismatch for {fixture_name}: "
        f"got {evidence['evidence_count']}, expected {expected['evidence_count']}"
    )

    # Evidence patterns (sorted by pattern_id, value_hash)
    actual_patterns = [
        (e["pattern_id"], e["value_hash"])
        for e in evidence["evidence"]
    ]
    assert actual_patterns == expected["evidence_patterns"], (
        f"evidence patterns mismatch for {fixture_name}: "
        f"got {actual_patterns}, expected {expected['evidence_patterns']}"
    )

    # Counts
    assert evidence["counts"] == expected["counts"], (
        f"counts mismatch for {fixture_name}: "
        f"got {evidence['counts']}, expected {expected['counts']}"
    )


@pytest.mark.parametrize("fixture_name", list(FIXTURE_EXPECTATIONS.keys()))
def test_closure_evidence_cli_determinism(fixture_name: str) -> None:
    """CLI must produce identical JSON output across repeated runs."""
    path = FIXTURES_DIR / fixture_name

    # Run twice
    exit1, output1 = _run_cli_closure_evidence(path)
    exit2, output2 = _run_cli_closure_evidence(path)

    assert exit1 == exit2 == 0

    evidence1 = _parse_closure_evidence(output1)
    evidence2 = _parse_closure_evidence(output2)

    assert evidence1 == evidence2, (
        f"Non-deterministic CLI output for {fixture_name}:\n"
        f"Run 1: {evidence1}\n"
        f"Run 2: {evidence2}"
    )


def test_closure_evidence_evidence_has_indices() -> None:
    """Evidence items must include first_seen_at and trigger_at indices."""
    # Use a fixture that produces evidence
    path = FIXTURES_DIR / "a_then_b_then_a.v2.jsonl"
    exit_code, output = _run_cli_closure_evidence(path)
    assert exit_code == 0

    evidence = _parse_closure_evidence(output)
    assert evidence["evidence_count"] == 1

    item = evidence["evidence"][0]
    assert "first_seen_at" in item
    assert "trigger_at" in item
    assert isinstance(item["first_seen_at"], int)
    assert isinstance(item["trigger_at"], int)
    # For a_then_b_then_a: first stall at index 0, trigger at index 2
    assert item["first_seen_at"] == 0
    assert item["trigger_at"] == 2


# =============================================================================
# Canonical fixture tests (execution.* events only, --check-canon compatible)
# =============================================================================

def test_closure_evidence_canonical_fixture_with_check_canon() -> None:
    """Canonical execution.* fixture works with --check-canon + --print-closure-evidence."""
    path = CANONICAL_FIXTURES_DIR / "stall_then_fixed_canonical.v2.jsonl"
    exit_code, output = _run_cli_closure_evidence_with_canon(path)

    assert exit_code == 0, f"CLI failed:\n{output}"

    evidence = _parse_closure_evidence(output)

    # Schema validation
    assert evidence["v"] == 1
    assert set(evidence["counts"].keys()) == {"stall", "fix", "fixed"}
    assert isinstance(evidence["evidence"], list)
    assert evidence["evidence_count"] == len(evidence["evidence"])

    # This fixture produces no closure evidence (fixed clears stall memory)
    assert evidence["evidence_count"] == 0
    assert evidence["counts"] == {"stall": 1, "fix": 0, "fixed": 1}


def test_closure_evidence_canonical_fixture_determinism() -> None:
    """Canonical fixture produces deterministic output across runs."""
    path = CANONICAL_FIXTURES_DIR / "stall_then_fixed_canonical.v2.jsonl"

    exit1, output1 = _run_cli_closure_evidence_with_canon(path)
    exit2, output2 = _run_cli_closure_evidence_with_canon(path)

    assert exit1 == exit2 == 0

    evidence1 = _parse_closure_evidence(output1)
    evidence2 = _parse_closure_evidence(output2)

    assert evidence1 == evidence2, (
        f"Non-deterministic output:\nRun 1: {evidence1}\nRun 2: {evidence2}"
    )
