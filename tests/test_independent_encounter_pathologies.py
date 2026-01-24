"""
Tests for IndependentEncounter.v0.md pathological scenarios.

These tests validate the closure evidence detection logic against
minimal fixtures that exercise edge cases defined in the design doc.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import pytest

from rcx_pi.replay_cli import validate_v2_execution_sequence


FIXTURES_DIR = Path("tests/fixtures/traces_v2/independent_encounter")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        events.append(json.loads(raw))
    return events


def _execution_only(events: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter to execution.* events so v2 replay validation is exercised without coupling to reduction.* schema."""
    out: List[Dict[str, Any]] = []
    for e in events:
        t = str(e.get("type", ""))
        if t.startswith("execution."):
            out.append(e)
    return out


def _extract_stall_key(e: Dict[str, Any]) -> Optional[Tuple[str, int]]:
    """
    IndependentEncounter.v0 uses the notion:
      same (value_hash, pattern_id) stalled twice with no intervening execution.fixed reset.

    These fixtures encode 'stall evidence' via reduction.stall events, since execution.stall
    is a stateful engine transition and cannot validly repeat back-to-back in minimal traces.
    """
    if e.get("type") != "reduction.stall":
        return None
    mu = e.get("mu") or {}
    pattern_id = mu.get("pattern_id")
    value_hash = mu.get("value_hash")
    if not isinstance(pattern_id, int) or not isinstance(value_hash, str):
        return None
    return (value_hash, pattern_id)


def independent_encounter_closure_evidence(events: Iterable[Dict[str, Any]]) -> Set[Tuple[str, int]]:
    """
    Pure spec mirror of docs/IndependentEncounter.v0.md (detection-only):

    - Maintain stall_memory[pattern_id] = value_hash (last seen stall per pattern).
    - On reduction.stall(value_hash=v, pattern_id=p):
        - if stall_memory[p] == v -> emit closure evidence for (v, p)
        - else set stall_memory[p] = v
    - On execution.fixed(before_hash=b, ...):
        - conservative reset: clear any stall_memory entries whose value_hash == b
    - execution.fix does NOT reset (intent-only).
    """
    stall_memory: Dict[int, str] = {}
    evidence: Set[Tuple[str, int]] = set()

    for e in events:
        t = e.get("type")

        if t == "execution.fixed":
            mu = e.get("mu") or {}
            before = mu.get("before_hash")
            if isinstance(before, str):
                # Clear any patterns currently holding this before-hash (conservative reset)
                to_del = [p for p, v in stall_memory.items() if v == before]
                for p in to_del:
                    del stall_memory[p]
            continue

        stall_key = _extract_stall_key(e)
        if stall_key is None:
            continue

        value_hash, pattern_id = stall_key
        prev = stall_memory.get(pattern_id)
        if prev == value_hash:
            evidence.add((value_hash, pattern_id))
        else:
            stall_memory[pattern_id] = value_hash

    return evidence


@pytest.mark.parametrize(
    "name, expected_evidence",
    [
        # Scenario 1: A-then-B-then-A -> closure for (v, pA)
        ("a_then_b_then_a.v2.jsonl", {("aaaaaaaaaaaaaaaa", 101)}),
        # Scenario 2: Idempotent fixed clears memory -> NO closure on second stall
        ("idempotent_fixed_resets.v2.jsonl", set()),
        # Scenario 5: Overwrite same pattern with different value -> NO closure when v returns
        ("overwrite_same_pattern.v2.jsonl", set()),
        # Scenario 7: execution.fix does not reset -> closure on second stall
        ("fix_does_not_reset.v2.jsonl", {("eeeeeeeeeeeeeeee", 303)}),
    ],
)
def test_independent_encounter_pathological_fixtures(name: str, expected_evidence: Set[Tuple[str, int]]) -> None:
    path = FIXTURES_DIR / name
    events = _read_jsonl(path)

    # 1) Determinism: pure detector must be stable.
    ev1 = independent_encounter_closure_evidence(events)
    ev2 = independent_encounter_closure_evidence(events)
    assert ev1 == ev2

    # 2) Spec assertion: evidence matches doc intent.
    assert ev1 == expected_evidence

    # 3) Replay/validation assertion: execution sequence (if present and complete) validates.
    #    A complete sequence starts with execution.stall; incomplete sequences are skipped.
    exec_events = _execution_only(events)
    has_exec_stall = any(e.get("type") == "execution.stall" for e in exec_events)
    if has_exec_stall:
        validate_v2_execution_sequence(exec_events)

    # 4) Extra sanity: fixtures are minimal (2-4 events each).
    assert 2 <= len(events) <= 4


def test_independent_encounter_fixtures_are_distinct() -> None:
    """
    Guardrail: fixtures should not accidentally be duplicates.
    We compare their canonical JSON string content.
    """
    names = [
        "a_then_b_then_a.v2.jsonl",
        "idempotent_fixed_resets.v2.jsonl",
        "overwrite_same_pattern.v2.jsonl",
        "fix_does_not_reset.v2.jsonl",
    ]
    blobs = []
    for n in names:
        p = FIXTURES_DIR / n
        events = _read_jsonl(p)
        blobs.append(json.dumps(events, sort_keys=True, separators=(",", ":")))
    assert len(set(blobs)) == len(blobs)
