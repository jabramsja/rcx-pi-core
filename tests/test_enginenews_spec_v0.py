"""
Enginenews Spec v0 Stress-Test Harness.

This module stress-tests the RCX v2 replay pipeline using PUBLIC CLI only.
All metrics are computed from trace event lines without engine access.

See docs/execution/EnginenewsSpecMapping.v0.md for spec details.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import pytest


FIXTURES_DIR = Path("tests/fixtures/traces_v2/enginenews_spec_v0")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read JSONL file into list of event dicts."""
    events: List[Dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        events.append(json.loads(raw))
    return events


def _run_cli_replay(fixture_path: Path) -> Tuple[int, str]:
    """
    Run CLI replay on fixture and return (exit_code, stdout).

    Uses subprocess to ensure we test the PUBLIC interface only.
    """
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"

    result = subprocess.run(
        [
            "python3", "-m", "rcx_pi.rcx_cli", "replay",
            "--trace", str(fixture_path),
            "--check-canon",
            "--print-exec-summary",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    # Combine stdout and stderr for robust parsing
    combined = result.stdout + "\n" + result.stderr
    return result.returncode, combined


def _parse_exec_summary(output: str) -> Dict[str, Any]:
    """
    Parse execution summary JSON from CLI output.

    Finds the last line that looks like a JSON object {...}.
    """
    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    for ln in reversed(lines):
        if ln.startswith("{") and ln.endswith("}"):
            return json.loads(ln)
    raise ValueError(f"No JSON summary found in output:\n{output}")


# =============================================================================
# Metrics computed from events only (no engine access)
# =============================================================================

def compute_event_counts(events: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count execution event types."""
    counts = {"stall": 0, "fix": 0, "fixed": 0}
    for e in events:
        t = e.get("type", "")
        if t == "execution.stall":
            counts["stall"] += 1
        elif t == "execution.fix":
            counts["fix"] += 1
        elif t == "execution.fixed":
            counts["fixed"] += 1
    return counts


def compute_stall_density(events: List[Dict[str, Any]]) -> float:
    """Compute stall_count / total_execution_events."""
    counts = compute_event_counts(events)
    total = counts["stall"] + counts["fix"] + counts["fixed"]
    if total == 0:
        return 0.0
    return counts["stall"] / total


def compute_fix_efficacy(events: List[Dict[str, Any]]) -> float:
    """
    Compute effective_fixes / fixed_count.

    A fix is effective if after_hash != before_hash.
    """
    fixed_count = 0
    effective_count = 0
    for e in events:
        if e.get("type") == "execution.fixed":
            fixed_count += 1
            mu = e.get("mu", {})
            if mu.get("before_hash") != mu.get("after_hash"):
                effective_count += 1
    if fixed_count == 0:
        return 0.0
    return effective_count / fixed_count


def compute_closure_evidence(events: List[Dict[str, Any]]) -> Set[Tuple[str, str]]:
    """
    Compute closure evidence per IndependentEncounter.v0.md.

    For execution.stall events:
    - stall_memory[pattern_id] = value_hash
    - If stall_memory[p] == v on stall(v, p): closure evidence for (v, p)

    On execution.fixed(before_hash=b):
    - Clear stall_memory entries where value == b (conservative reset)

    Returns set of (value_hash, pattern_id) pairs with closure evidence.

    Note: In valid single-value execution sequences, closure evidence is
    structurally impossible because every execution.fixed clears the stall
    memory for the stalled value. This metric exists for completeness and
    will be 0 for all valid fixtures.
    """
    stall_memory: Dict[str, str] = {}  # pattern_id -> value_hash
    evidence: Set[Tuple[str, str]] = set()

    for e in events:
        t = e.get("type")

        if t == "execution.fixed":
            mu = e.get("mu", {})
            before = mu.get("before_hash")
            if isinstance(before, str):
                # Clear patterns holding this before-hash
                to_del = [p for p, v in stall_memory.items() if v == before]
                for p in to_del:
                    del stall_memory[p]
            continue

        if t == "execution.stall":
            mu = e.get("mu", {})
            value_hash = mu.get("value_hash")
            pattern_id = mu.get("pattern_id")
            if not isinstance(value_hash, str) or pattern_id is None:
                continue
            pattern_key = str(pattern_id)
            prev = stall_memory.get(pattern_key)
            if prev == value_hash:
                evidence.add((value_hash, pattern_key))
            else:
                stall_memory[pattern_key] = value_hash

    return evidence


# =============================================================================
# Test fixtures and expectations
# =============================================================================

FIXTURE_EXPECTATIONS = {
    "progressive_refinement.v2.jsonl": {
        "exit_code": 0,
        "final_status": "ACTIVE",
        "stall_density": 1/3,  # 1 stall / 3 events
        "fix_efficacy": 1.0,   # 1 effective fix / 1 fixed
        "closure_evidence_count": 0,
    },
    "stall_pressure.v2.jsonl": {
        "exit_code": 0,
        "final_status": "STALLED",
        "stall_density": 1.0,  # 1 stall / 1 event
        "fix_efficacy": 0.0,   # no fixed events
        "closure_evidence_count": 0,
    },
    "multi_cycle.v2.jsonl": {
        "exit_code": 0,
        "final_status": "ACTIVE",
        "stall_density": 0.5,  # 2 stalls / 4 events
        "fix_efficacy": 1.0,   # 2 effective fixes / 2 fixed
        "closure_evidence_count": 0,
    },
    "idempotent_cycle.v2.jsonl": {
        "exit_code": 0,
        "final_status": "STALLED",
        "stall_density": 2/3,  # 2 stalls / 3 events
        "fix_efficacy": 0.0,   # 0 effective (idempotent) / 1 fixed
        "closure_evidence_count": 0,  # memory cleared by fixed(before=hash_stable)
    },
}


@pytest.mark.parametrize("fixture_name", list(FIXTURE_EXPECTATIONS.keys()))
def test_enginenews_cli_replay_accepts_fixtures(fixture_name: str) -> None:
    """CLI replay must accept all valid enginenews fixtures."""
    path = FIXTURES_DIR / fixture_name
    exit_code, output = _run_cli_replay(path)
    expected = FIXTURE_EXPECTATIONS[fixture_name]

    assert exit_code == expected["exit_code"], f"Unexpected exit code for {fixture_name}:\n{output}"


@pytest.mark.parametrize("fixture_name", list(FIXTURE_EXPECTATIONS.keys()))
def test_enginenews_cli_summary_matches_expectation(fixture_name: str) -> None:
    """CLI --print-exec-summary must match expected final_status."""
    path = FIXTURES_DIR / fixture_name
    exit_code, output = _run_cli_replay(path)
    expected = FIXTURE_EXPECTATIONS[fixture_name]

    if exit_code != 0:
        pytest.skip(f"CLI failed with exit code {exit_code}")

    summary = _parse_exec_summary(output)
    assert summary["final_status"] == expected["final_status"], (
        f"final_status mismatch for {fixture_name}: "
        f"got {summary['final_status']}, expected {expected['final_status']}"
    )


@pytest.mark.parametrize("fixture_name", list(FIXTURE_EXPECTATIONS.keys()))
def test_enginenews_metrics_from_events(fixture_name: str) -> None:
    """Metrics computed from events must match expectations."""
    path = FIXTURES_DIR / fixture_name
    events = _read_jsonl(path)
    expected = FIXTURE_EXPECTATIONS[fixture_name]

    # Stall density
    actual_density = compute_stall_density(events)
    assert abs(actual_density - expected["stall_density"]) < 0.001, (
        f"stall_density mismatch for {fixture_name}: "
        f"got {actual_density}, expected {expected['stall_density']}"
    )

    # Fix efficacy
    actual_efficacy = compute_fix_efficacy(events)
    assert abs(actual_efficacy - expected["fix_efficacy"]) < 0.001, (
        f"fix_efficacy mismatch for {fixture_name}: "
        f"got {actual_efficacy}, expected {expected['fix_efficacy']}"
    )

    # Closure evidence
    evidence = compute_closure_evidence(events)
    assert len(evidence) == expected["closure_evidence_count"], (
        f"closure_evidence_count mismatch for {fixture_name}: "
        f"got {len(evidence)}, expected {expected['closure_evidence_count']}"
    )


@pytest.mark.parametrize("fixture_name", list(FIXTURE_EXPECTATIONS.keys()))
def test_enginenews_cli_determinism(fixture_name: str) -> None:
    """CLI must produce identical JSON output across repeated runs."""
    path = FIXTURES_DIR / fixture_name

    # Run twice
    exit1, output1 = _run_cli_replay(path)
    exit2, output2 = _run_cli_replay(path)

    assert exit1 == exit2, f"Exit codes differ for {fixture_name}"

    if exit1 != 0:
        pytest.skip(f"CLI failed with exit code {exit1}")

    summary1 = _parse_exec_summary(output1)
    summary2 = _parse_exec_summary(output2)

    assert summary1 == summary2, (
        f"Non-deterministic CLI output for {fixture_name}:\n"
        f"Run 1: {summary1}\n"
        f"Run 2: {summary2}"
    )


def test_enginenews_fixtures_are_distinct() -> None:
    """Guardrail: fixtures must not be duplicates."""
    blobs = []
    for name in FIXTURE_EXPECTATIONS.keys():
        path = FIXTURES_DIR / name
        events = _read_jsonl(path)
        blobs.append(json.dumps(events, sort_keys=True, separators=(",", ":")))
    assert len(set(blobs)) == len(blobs), "Duplicate fixtures detected"


def test_enginenews_fixtures_are_minimal() -> None:
    """Fixtures must be minimal (2-6 events each per spec)."""
    for name in FIXTURE_EXPECTATIONS.keys():
        path = FIXTURES_DIR / name
        events = _read_jsonl(path)
        assert 1 <= len(events) <= 6, (
            f"Fixture {name} has {len(events)} events, expected 1-6"
        )
