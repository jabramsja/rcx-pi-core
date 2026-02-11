"""
Paxos End-to-End: Deadlock Metabolization via Structural Closure Detection

Proves the full pipeline:
  paxos livelock → trace → hash → recurrence.v2 → healer → consensus

All building blocks already exist; this test wires them together.

See: mu/programs/paxos_demo.v1.json (6 projections)
     mu/closures/recurrence.v2.json (9 projections)
     docs/core/recurrence_v2_design.md
     roadmap/ContentAddressedMu.md
"""
from __future__ import annotations

import signal

import pytest

from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
from rcx_pi.selfhost.step_mu import (
    apply_mu,
    hash_trace_for_recurrence,
    run_algorithm_meta_circular,
    run_mu_structural,
)
from rcx_pi.selfhost.mu_type import mu_equal
from rcx_pi.selfhost.kernel import reset_step_budget


# CI runners are ~3x slower than local; use RCX_CI env var to detect.
import os as _os
TEST_TIMEOUT_SECONDS = 360 if _os.environ.get("RCX_CI") else 120


class _Timeout(Exception):
    pass


def _timeout_handler(signum, frame):
    raise _Timeout(f"Paxos e2e exceeded {TEST_TIMEOUT_SECONDS}s")


def run_recurrence_to_completion(recurrence_projs, recurrence_input, max_iterations=50):
    """Run recurrence algorithm repeatedly until terminal result or timeout."""
    current = recurrence_input
    for i in range(max_iterations):
        reset_step_budget()
        result = run_algorithm_meta_circular(recurrence_projs, current)
        if mu_equal(result, current):
            return result  # Stalled
        if isinstance(result, dict) and "closure_detected" in result:
            return result
        current = result
    return current


# ---------------------------------------------------------------------------
# Fixtures: load seeds once
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def paxos_seed():
    return load_verified_seed(get_seed_path("paxos_demo.v1.json"))


@pytest.fixture(scope="module")
def paxos_cycle_projs(paxos_seed):
    """First 4 projections: the livelock cycle (no healer)."""
    return paxos_seed["projections"][:4]


@pytest.fixture(scope="module")
def healer_proj(paxos_seed):
    """5th projection: healer.detect_deadlock (recurrence shape)."""
    return paxos_seed["projections"][4]


@pytest.fixture(scope="module")
def healer_engine_proj(paxos_seed):
    """6th projection: healer.detect_deadlock_engine (engine output shape)."""
    return paxos_seed["projections"][5]


@pytest.fixture(scope="module")
def recurrence_projs():
    seed = load_verified_seed(get_seed_path("recurrence.v2.json"))
    return seed["projections"]


# ---------------------------------------------------------------------------
# Phase A tests
# ---------------------------------------------------------------------------

class TestPaxosEndToEnd:
    """Full pipeline: paxos livelock → recurrence.v2 closure → healer consensus."""

    @pytest.fixture(autouse=True)
    def setup(self):
        reset_step_budget()

    def _with_timeout(self, fn):
        old = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(TEST_TIMEOUT_SECONDS)
        try:
            return fn()
        except _Timeout:
            return {"_timeout": True}
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)

    # ------------------------------------------------------------------
    # Step 1: Paxos livelock produces oscillating trace
    # ------------------------------------------------------------------

    def test_paxos_cycle_produces_livelock(self, paxos_cycle_projs):
        """4 paxos projections create a 3-state oscillating cycle, not a stall."""
        initial = {"paxos_trigger": "start_paxos"}
        # 6 steps gives 2 full 3-state cycles; keeps kernel state small enough
        # for meta-circular processing (production tests validate 5-step traces)
        result = run_mu_structural(paxos_cycle_projs, initial, max_steps=6)

        assert result["steps"] >= 4, "Should run at least one full cycle"
        assert result["stall"] is False, (
            "Paxos should livelock (not stall) — states keep changing"
        )
        # Trace is a Mu linked list
        assert isinstance(result["trace"], dict)
        assert "head" in result["trace"]

    # ------------------------------------------------------------------
    # Step 2: hash_trace_for_recurrence adds state_hash
    # ------------------------------------------------------------------

    def test_hashed_trace_has_state_hashes(self, paxos_cycle_projs):
        """hash_trace_for_recurrence adds state_hash to every trace entry."""
        initial = {"paxos_trigger": "start_paxos"}
        result = run_mu_structural(paxos_cycle_projs, initial, max_steps=6)

        hashed_trace = hash_trace_for_recurrence(result["trace"])

        # Walk the hashed trace and verify state_hash on each entry
        current = hashed_trace
        count = 0
        while isinstance(current, dict) and "head" in current:
            entry = current["head"]
            if isinstance(entry, dict) and "state" in entry:
                assert "state_hash" in entry, (
                    f"Entry at step {entry.get('step')} missing state_hash"
                )
                assert isinstance(entry["state_hash"], str), "state_hash should be hex string"
                assert len(entry["state_hash"]) == 64, "SHA-256 hex digest is 64 chars"
            count += 1
            current = current.get("tail")

        assert count >= 4, f"Expected at least 4 trace entries, got {count}"

    # ------------------------------------------------------------------
    # Step 3: recurrence.v2 detects closure on real paxos trace
    # ------------------------------------------------------------------

    def test_recurrence_v2_detects_paxos_closure(self, paxos_cycle_projs, recurrence_projs):
        """recurrence.v2 detects the Paxos 3-state livelock closure."""
        initial = {"paxos_trigger": "start_paxos"}
        trace_result = run_mu_structural(paxos_cycle_projs, initial, max_steps=6)
        hashed_trace = hash_trace_for_recurrence(trace_result["trace"])

        recurrence_input = {
            "_detect_closure": {
                "trace": hashed_trace,
                "result": trace_result["result"],
            }
        }

        result = self._with_timeout(
            lambda: run_recurrence_to_completion(recurrence_projs, recurrence_input)
        )

        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert result.get("_timeout") is not True, "Recurrence timed out"
        assert result.get("closure_detected") is True, (
            f"Expected closure_detected=True, got: {result}"
        )

    # ------------------------------------------------------------------
    # Step 4: healer resolves the detected closure
    # ------------------------------------------------------------------

    def test_healer_resolves_detected_closure(self, paxos_cycle_projs, recurrence_projs, healer_proj):
        """healer.detect_deadlock converts closure result to consensus."""
        initial = {"paxos_trigger": "start_paxos"}
        trace_result = run_mu_structural(paxos_cycle_projs, initial, max_steps=6)
        hashed_trace = hash_trace_for_recurrence(trace_result["trace"])

        recurrence_input = {
            "_detect_closure": {
                "trace": hashed_trace,
                "result": trace_result["result"],
            }
        }

        closure_result = self._with_timeout(
            lambda: run_recurrence_to_completion(recurrence_projs, recurrence_input)
        )
        assert closure_result.get("closure_detected") is True, "Precondition: closure detected"

        # Feed closure result to healer projection
        healer_result = apply_mu(healer_proj, closure_result)

        assert healer_result is not None, "Healer should match closure result"
        assert isinstance(healer_result, dict), f"Expected dict, got {type(healer_result)}"
        assert healer_result.get("status") == "consensus_reached", (
            f"Expected consensus_reached, got: {healer_result}"
        )
        assert healer_result.get("leader") == "Node_A"
        assert healer_result.get("reason") == "deadlock_resolution_protocol"

    # ------------------------------------------------------------------
    # Full pipeline in one test
    # ------------------------------------------------------------------

    def test_full_pipeline(self, paxos_cycle_projs, recurrence_projs, healer_proj):
        """Complete deadlock metabolization: livelock → closure → consensus."""
        # 1. Run paxos livelock
        initial = {"paxos_trigger": "start_paxos"}
        trace_result = run_mu_structural(paxos_cycle_projs, initial, max_steps=6)
        assert trace_result["stall"] is False, "Paxos should livelock"

        # 2. Hash the trace for v2 compatibility
        hashed_trace = hash_trace_for_recurrence(trace_result["trace"])

        # 3. Detect closure via recurrence.v2
        recurrence_input = {
            "_detect_closure": {
                "trace": hashed_trace,
                "result": trace_result["result"],
            }
        }
        closure_result = self._with_timeout(
            lambda: run_recurrence_to_completion(recurrence_projs, recurrence_input)
        )
        assert closure_result.get("closure_detected") is True, "Closure should be detected"

        # 4. Heal the deadlock
        healer_result = apply_mu(healer_proj, closure_result)
        assert healer_result.get("status") == "consensus_reached", (
            "Healer should resolve deadlock to consensus"
        )

    # ------------------------------------------------------------------
    # Sanity: trace actually contains repeated states
    # ------------------------------------------------------------------

    def test_trace_contains_repeated_states(self, paxos_cycle_projs):
        """Verify the trace has repeated states (the cycle that recurrence detects)."""
        initial = {"paxos_trigger": "start_paxos"}
        trace_result = run_mu_structural(paxos_cycle_projs, initial, max_steps=6)
        hashed_trace = hash_trace_for_recurrence(trace_result["trace"])

        # Collect state hashes
        hashes = []
        current = hashed_trace
        while isinstance(current, dict) and "head" in current:
            entry = current["head"]
            if isinstance(entry, dict) and "state_hash" in entry:
                hashes.append(entry["state_hash"])
            current = current.get("tail")

        # With a 3-state cycle over 6 steps, we must see duplicates
        unique = set(hashes)
        assert len(unique) < len(hashes), (
            f"Expected repeated state hashes in livelock trace. "
            f"Got {len(hashes)} entries with {len(unique)} unique hashes."
        )

    # ------------------------------------------------------------------
    # Engine output → healer composability
    # ------------------------------------------------------------------

    def test_healer_matches_engine_output(self, healer_engine_proj):
        """healer.detect_deadlock_engine matches the engine pipeline output shape."""
        # Simulate engine output shape (what run_engine_pipeline returns)
        engine_output = {
            "value": {"paxos_mode": "paxos_run", "status": "voting", "node_a": "idle", "node_b": "idle"},
            "closure_detected": True,
            "tau_step": 3,
            "exhaustion_detected": False,
            "operator_frozen": None,
            "frozen_set": None,
            "action": "continue",
            "stall": True,
        }

        healer_result = apply_mu(healer_engine_proj, engine_output)

        assert healer_result is not None, "Engine healer should match engine output"
        assert isinstance(healer_result, dict)
        assert healer_result.get("status") == "consensus_reached"
        assert healer_result.get("leader") == "Node_A"
        assert healer_result.get("reason") == "deadlock_resolution_protocol"
        assert healer_result.get("origin_anomaly") == engine_output["value"]

    def test_healer_rejects_no_closure_engine_output(self, healer_engine_proj):
        """healer should NOT match when closure_detected is false."""
        engine_output = {
            "value": {"x": 1},
            "closure_detected": False,
            "tau_step": None,
            "exhaustion_detected": False,
            "operator_frozen": None,
            "frozen_set": None,
            "action": "continue",
            "stall": True,
        }

        healer_result = apply_mu(healer_engine_proj, engine_output)

        # When closure_detected=False, pattern has literal `true` so it shouldn't match
        # apply_mu returns the input unchanged when no match
        assert healer_result is not None
        if isinstance(healer_result, dict):
            assert healer_result.get("status") != "consensus_reached", (
                "Healer should NOT match when closure_detected=False"
            )
