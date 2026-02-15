"""
N6a: Observer Event Contract — schema and canonicalization grounding tests.

Validates the event contract defined in mu/docs/core/ObserverEventContract.v0.md
using test-local fixtures only. No runtime hooks are modified.

N6b (cross-substrate isomorphic stream comparison) is DEFERRED.
JS parity tests will be added when N6b is promoted to NEXT.
"""

from __future__ import annotations

import hashlib
import json

import pytest


# ---------------------------------------------------------------------------
# Contract constants (must match ObserverEventContract.v0.md)
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = frozenset({
    "event_name",
    "step",
    "state_hash",
    "error_code",
    "substrate",
    "timestamp",
})

VALID_EVENT_NAMES = frozenset({
    "step_boundary",
    "stall_detected",
    "closure_detected",
    "fail_closed",
})

VALID_SUBSTRATES = frozenset({"python", "js"})


def _make_event(
    event_name: str = "step_boundary",
    step: int = 0,
    state_hash: str | None = "abc123",
    error_code: str | None = None,
    substrate: str = "python",
    timestamp: int = 0,
) -> dict:
    """Build a conforming observer event (test fixture helper)."""
    return {
        "event_name": event_name,
        "step": step,
        "state_hash": state_hash,
        "error_code": error_code,
        "substrate": substrate,
        "timestamp": timestamp,
    }


def _canonical_json(event: dict) -> str:
    """Canonical JSON serialization per ObserverEventContract.v0.md."""
    return json.dumps(event, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestObserverEventSchema:
    """Validate event schema required fields and invariants."""

    def test_schema_required_fields_present(self):
        """Every event must contain exactly the required field set."""
        event = _make_event()
        assert set(event.keys()) == REQUIRED_FIELDS

    def test_schema_no_extra_fields(self):
        """Events with extra fields violate the contract."""
        event = _make_event()
        event["extra"] = "bad"
        assert set(event.keys()) != REQUIRED_FIELDS

    def test_event_name_must_be_registered(self):
        """event_name must be one of the mandatory event points."""
        for name in VALID_EVENT_NAMES:
            event = _make_event(event_name=name)
            assert event["event_name"] in VALID_EVENT_NAMES

    def test_substrate_must_be_valid(self):
        """substrate must be 'python' or 'js'."""
        for sub in VALID_SUBSTRATES:
            event = _make_event(substrate=sub)
            assert event["substrate"] in VALID_SUBSTRATES

    def test_fail_closed_requires_error_code(self):
        """fail_closed events must have a non-null error_code."""
        event = _make_event(
            event_name="fail_closed",
            error_code="input.shape_mismatch",
        )
        assert event["error_code"] is not None

    def test_success_events_have_null_error_code(self):
        """Non-failure events must have null error_code."""
        for name in ("step_boundary", "stall_detected", "closure_detected"):
            event = _make_event(event_name=name, error_code=None)
            assert event["error_code"] is None

    def test_step_is_non_negative(self):
        """step must be >= 0."""
        event = _make_event(step=0)
        assert event["step"] >= 0

    def test_timestamp_is_non_negative(self):
        """timestamp must be >= 0."""
        event = _make_event(timestamp=0)
        assert event["timestamp"] >= 0


# ---------------------------------------------------------------------------
# Ordering tests
# ---------------------------------------------------------------------------


class TestObserverEventOrdering:
    """Validate deterministic ordering rules."""

    def test_ordering_rule_deterministic_sort(self):
        """Events sort by (step ASC, timestamp ASC) — deterministic total order."""
        events = [
            _make_event(step=2, timestamp=0, event_name="closure_detected"),
            _make_event(step=0, timestamp=0, event_name="step_boundary"),
            _make_event(step=1, timestamp=1, event_name="stall_detected"),
            _make_event(step=1, timestamp=0, event_name="step_boundary"),
        ]
        sorted_events = sorted(events, key=lambda e: (e["step"], e["timestamp"]))
        expected_order = [
            (0, 0, "step_boundary"),
            (1, 0, "step_boundary"),
            (1, 1, "stall_detected"),
            (2, 0, "closure_detected"),
        ]
        actual_order = [
            (e["step"], e["timestamp"], e["event_name"])
            for e in sorted_events
        ]
        assert actual_order == expected_order

    def test_ordering_is_stable_across_reruns(self):
        """Same input produces same sort order every time (no randomness)."""
        events = [
            _make_event(step=3, timestamp=0),
            _make_event(step=1, timestamp=2),
            _make_event(step=1, timestamp=0),
            _make_event(step=2, timestamp=1),
        ]
        sort_key = lambda e: (e["step"], e["timestamp"])
        run1 = [(e["step"], e["timestamp"]) for e in sorted(events, key=sort_key)]
        run2 = [(e["step"], e["timestamp"]) for e in sorted(events, key=sort_key)]
        assert run1 == run2


# ---------------------------------------------------------------------------
# Canonicalization tests
# ---------------------------------------------------------------------------


class TestObserverEventCanonicalization:
    """Validate canonical JSON serialization for hashability."""

    def test_canonicalization_stable_for_same_payload(self):
        """Identical events produce identical canonical JSON."""
        e1 = _make_event(step=5, state_hash="deadbeef")
        e2 = _make_event(step=5, state_hash="deadbeef")
        assert _canonical_json(e1) == _canonical_json(e2)

    def test_canonicalization_keys_sorted(self):
        """Canonical JSON has alphabetically sorted keys."""
        event = _make_event()
        serialized = _canonical_json(event)
        parsed_keys = list(json.loads(serialized).keys())
        assert parsed_keys == sorted(parsed_keys)

    def test_canonicalization_no_whitespace(self):
        """Canonical JSON has no spaces or newlines."""
        event = _make_event()
        serialized = _canonical_json(event)
        assert " " not in serialized
        assert "\n" not in serialized

    def test_canonicalization_hash_deterministic(self):
        """sha256 of canonical JSON is deterministic for identical payloads."""
        e1 = _make_event(step=7, event_name="closure_detected", state_hash="cafe")
        e2 = _make_event(step=7, event_name="closure_detected", state_hash="cafe")
        h1 = hashlib.sha256(_canonical_json(e1).encode("utf-8")).hexdigest()
        h2 = hashlib.sha256(_canonical_json(e2).encode("utf-8")).hexdigest()
        assert h1 == h2

    def test_different_payloads_produce_different_hashes(self):
        """Different events must produce different canonical hashes."""
        e1 = _make_event(step=1)
        e2 = _make_event(step=2)
        h1 = hashlib.sha256(_canonical_json(e1).encode("utf-8")).hexdigest()
        h2 = hashlib.sha256(_canonical_json(e2).encode("utf-8")).hexdigest()
        assert h1 != h2


# ---------------------------------------------------------------------------
# N6b placeholder — JS isomorphism tests deferred
# ---------------------------------------------------------------------------

# N6b: Cross-substrate isomorphic stream comparison is OUT OF SCOPE for N6a.
# When N6b is promoted to NEXT, add tests here that:
#   1. Run identical inputs through Python and JS
#   2. Collect event streams from both substrates
#   3. Assert pairwise canonical equality after sorting by (step, timestamp)
# See mu/docs/core/ObserverEventContract.v0.md § "Parity Intent" for contract.
