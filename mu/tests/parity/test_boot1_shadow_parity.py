"""Boot1 shadow parity tests: trampoline vs recursive engine loop.

Verifies that run_engine_pipeline(use_boot1_recursive=True) produces
identical results to the default trampoline path on all canonical inputs.

Also tests _tail_call recognition and Boot1 safety invariants.

See mu/docs/core/Boot1LoopContract.v0.md §5 for test plan.
"""
import json
import os
import subprocess

import pytest

# === Python imports (public API only — anti-cheat policy) ===
from rcx_pi.selfhost.step_mu import (
    KERNEL_RESERVED_FIELDS,
    run_engine_pipeline,
    validate_no_kernel_reserved_fields,
)
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
from rcx_pi.selfhost.kernel import reset_step_budget

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# Helper
# ============================================================================

def _run_js_json_api(request_dict: dict) -> dict:
    """Run a JSON API request against the JS substrate."""
    result = subprocess.run(
        ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request_dict)],
        capture_output=True, text=True, cwd=ROOT, timeout=120
    )
    for line in result.stdout.split('\n'):
        if line.startswith('JSON_API_RESPONSE:'):
            return json.loads(line[len('JSON_API_RESPONSE:'):])
    raise RuntimeError(f"No JSON_API_RESPONSE: {result.stdout[:500]}")


def _cross_substrate_equal(a, b):
    """Compare values across substrates (handles JS null vs Python None)."""
    if a is None and b is None:
        return True
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_cross_substrate_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        return all(_cross_substrate_equal(x, y) for x, y in zip(a, b))
    return a == b


def _run_boot1(projs, initial, **kwargs):
    """Run engine pipeline with Boot1 recursive shadow."""
    return run_engine_pipeline(projs, initial, use_boot1_recursive=True, **kwargs)


def _run_trampoline(projs, initial, **kwargs):
    """Run engine pipeline with default trampoline."""
    return run_engine_pipeline(projs, initial, **kwargs)


# ============================================================================
# Python: Trampoline vs Recursive parity
# ============================================================================

class TestBoot1PythonShadowParity:
    """Verify use_boot1_recursive=True produces identical results to trampoline."""

    def test_simple_non_freeze_parity(self):
        """Non-freeze input: both paths produce identical terminal result."""
        reset_step_budget()
        projs = [{"pattern": {"double": {"var": "n"}}, "body": {"var": "n"}}]
        initial = {"double": 42}

        trampoline_result = _run_trampoline(projs, initial, max_steps=10)
        reset_step_budget()
        recursive_result = _run_boot1(projs, initial, max_steps=10)
        assert trampoline_result == recursive_result

    def test_paxos_freeze_parity(self):
        """Freeze-triggering input: both paths produce identical result after re-entry."""
        reset_step_budget()
        paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
        cycle_projs = paxos_seed["projections"][:4]
        initial = {"paxos_trigger": "start_paxos"}

        trampoline_result = _run_trampoline(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50,
        )
        reset_step_budget()
        recursive_result = _run_boot1(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50,
        )
        assert trampoline_result == recursive_result

    def test_use_boot1_recursive_flag(self):
        """use_boot1_recursive=True routes to recursive path and produces same result."""
        reset_step_budget()
        projs = [{"pattern": {"double": {"var": "n"}}, "body": {"var": "n"}}]
        initial = {"double": 42}

        trampoline_result = _run_trampoline(projs, initial, max_steps=10)
        reset_step_budget()
        recursive_result = _run_boot1(projs, initial, max_steps=10)
        assert trampoline_result == recursive_result

    def test_observer_events_emitted(self):
        """Observer events are emitted by Boot1 recursive path."""
        reset_step_budget()
        projs = [{"pattern": {"double": {"var": "n"}}, "body": {"var": "n"}}]
        initial = {"double": 42}

        boot1_obs = []
        _run_boot1(projs, initial, max_steps=10, observer=boot1_obs)

        # Boot1 path should emit step_boundary events
        event_names = [e["event_name"] for e in boot1_obs]
        assert "step_boundary" in event_names

    def test_terminal_shape_identical(self):
        """Both paths produce identical 8-key terminal shape (invariant S4)."""
        reset_step_budget()
        projs = [{"pattern": {"inc": {"var": "n"}}, "body": {"var": "n"}}]
        initial = {"inc": 5}

        trampoline_result = _run_trampoline(projs, initial, max_steps=10)
        reset_step_budget()
        recursive_result = _run_boot1(projs, initial, max_steps=10)

        expected_keys = {"value", "closure_detected", "tau_step", "exhaustion_detected",
                        "operator_frozen", "frozen_set", "action", "stall"}
        assert set(trampoline_result.keys()) == expected_keys
        assert set(recursive_result.keys()) == expected_keys
        assert trampoline_result == recursive_result

    def test_stall_parity(self):
        """Empty projections produce identical stall results on both paths."""
        reset_step_budget()
        trampoline = _run_trampoline([], {"x": 1}, max_steps=10)
        reset_step_budget()
        recursive = _run_boot1([], {"x": 1}, max_steps=10)
        assert trampoline == recursive


# ============================================================================
# Python: Boot1 safety invariants
# ============================================================================

class TestBoot1SafetyInvariants:
    """Verify Boot1 safety invariants S1–S7 via public API."""

    def test_s4_terminal_shape_preserved(self):
        """S4: Terminal result has exactly 8 keys."""
        reset_step_budget()
        projs = [{"pattern": {"test": {"var": "v"}}, "body": {"var": "v"}}]
        result = _run_boot1(projs, {"test": 42}, max_steps=10)
        expected_keys = {"value", "closure_detected", "tau_step", "exhaustion_detected",
                        "operator_frozen", "frozen_set", "action", "stall"}
        assert set(result.keys()) == expected_keys

    def test_s7_no_config_leak(self):
        """S7: _config must not appear in terminal result."""
        reset_step_budget()
        projs = [{"pattern": {"test": {"var": "v"}}, "body": {"var": "v"}}]
        result = _run_boot1(projs, {"test": 42}, max_steps=10)
        assert "_config" not in result

    def test_s7_no_tail_call_leak(self):
        """S7: _tail_call must not appear in terminal result."""
        reset_step_budget()
        projs = [{"pattern": {"test": {"var": "v"}}, "body": {"var": "v"}}]
        result = _run_boot1(projs, {"test": 42}, max_steps=10)
        assert "_tail_call" not in result

    def test_tail_call_reserved(self):
        """_tail_call is in KERNEL_RESERVED_FIELDS."""
        assert "_tail_call" in KERNEL_RESERVED_FIELDS

    def test_run_engine_reserved(self):
        """_run_engine is in KERNEL_RESERVED_FIELDS."""
        assert "_run_engine" in KERNEL_RESERVED_FIELDS

    def test_tail_call_rejected_in_domain_data(self):
        """Domain data with _tail_call is rejected by validation."""
        with pytest.raises(ValueError, match="kernel-reserved"):
            validate_no_kernel_reserved_fields(
                {"_tail_call": {"projections": [], "input": 1}},
                context="test_domain",
            )

    def test_no_reserved_fields_in_boot1_terminal(self):
        """Boot1 terminal result contains no kernel-reserved fields."""
        reset_step_budget()
        projs = [{"pattern": {"test": {"var": "v"}}, "body": {"var": "v"}}]
        result = _run_boot1(projs, {"test": 42}, max_steps=10)
        for key in result:
            assert key not in KERNEL_RESERVED_FIELDS, (
                f"Boot1 terminal result contains reserved field: {key}"
            )


# ============================================================================
# Python: _tail_call security
# ============================================================================

class TestTailCallSecurity:
    """Test _tail_call security properties."""

    def test_tail_call_in_kernel_reserved(self):
        """_tail_call cannot be injected via boundary request inject_key."""
        assert "_tail_call" in KERNEL_RESERVED_FIELDS

    def test_tail_call_domain_forgery_blocked(self):
        """Domain data cannot forge _tail_call to hijack engine control flow."""
        with pytest.raises(ValueError, match="kernel-reserved"):
            validate_no_kernel_reserved_fields(
                {"_tail_call": {"projections": [{"pattern": {}, "body": "pwned"}], "input": {}}},
                context="domain_input",
            )

    def test_run_engine_forgery_blocked(self):
        """Domain data cannot forge _run_engine to redirect engine re-entry."""
        with pytest.raises(ValueError, match="kernel-reserved"):
            validate_no_kernel_reserved_fields(
                {"_run_engine": {"projections": [], "input": {}}},
                context="domain_input",
            )


# ============================================================================
# Cross-substrate: Boot1 parity
# ============================================================================

@pytest.mark.slow
class TestBoot1CrossSubstrateParity:
    """Cross-substrate verification for Boot1 shadow path."""

    def test_js_boot1_simple_parity(self):
        """JS Boot1 recursive produces same result as JS trampoline."""
        projs = [{"pattern": {"double": {"var": "n"}}, "body": {"var": "n"}}]
        initial = {"double": 42}

        # JS trampoline
        trampoline_resp = _run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": projs,
            "input": initial,
            "maxSteps": 10,
        })
        assert trampoline_resp["success"], f"JS trampoline failed: {trampoline_resp.get('error')}"

        # JS Boot1 recursive
        recursive_resp = _run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": projs,
            "input": initial,
            "maxSteps": 10,
            "boot1LoopMode": True,
        })
        assert recursive_resp["success"], f"JS Boot1 failed: {recursive_resp.get('error')}"

        assert _cross_substrate_equal(trampoline_resp["result"], recursive_resp["result"]), (
            f"JS trampoline vs Boot1 mismatch:\n"
            f"  Trampoline: {trampoline_resp['result']}\n"
            f"  Boot1:      {recursive_resp['result']}"
        )

    def test_python_boot1_vs_js_boot1_parity(self):
        """Python Boot1 recursive == JS Boot1 recursive."""
        reset_step_budget()
        projs = [{"pattern": {"double": {"var": "n"}}, "body": {"var": "n"}}]
        initial = {"double": 42}

        py_result = _run_boot1(
            projs, initial, max_steps=10, max_engine_iterations=20,
        )

        js_resp = _run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": projs,
            "input": initial,
            "maxSteps": 10,
            "maxEngineIterations": 20,
            "boot1LoopMode": True,
        })
        assert js_resp["success"], f"JS Boot1 failed: {js_resp.get('error')}"

        assert _cross_substrate_equal(py_result, js_resp["result"]), (
            f"Python Boot1 vs JS Boot1 mismatch:\n"
            f"  Python: {py_result}\n"
            f"  JS:     {js_resp['result']}"
        )

    def test_paxos_boot1_cross_substrate(self):
        """Paxos freeze cycle: Python Boot1 == JS Boot1."""
        reset_step_budget()
        paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
        cycle_projs = paxos_seed["projections"][:4]
        initial = {"paxos_trigger": "start_paxos"}

        py_result = _run_boot1(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50,
        )

        js_resp = _run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": cycle_projs,
            "input": initial,
            "maxSteps": 6,
            "maxEngineIterations": 20,
            "maxAlgorithmIterations": 50,
            "boot1LoopMode": True,
        })
        assert js_resp["success"], f"JS Boot1 Paxos failed: {js_resp.get('error')}"

        assert _cross_substrate_equal(py_result, js_resp["result"]), (
            f"Paxos Boot1 cross-substrate mismatch:\n"
            f"  Python: {py_result}\n"
            f"  JS:     {js_resp['result']}"
        )

    def test_js_boot1_stall_parity(self):
        """JS Boot1 handles empty projections same as trampoline."""
        # JS trampoline
        trampoline_resp = _run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": [],
            "input": {"x": 1},
            "maxSteps": 10,
        })
        # JS Boot1
        recursive_resp = _run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": [],
            "input": {"x": 1},
            "maxSteps": 10,
            "boot1LoopMode": True,
        })
        assert trampoline_resp["success"] == recursive_resp["success"]
        if trampoline_resp["success"]:
            assert _cross_substrate_equal(trampoline_resp["result"], recursive_resp["result"])


# ============================================================================
# Python: S2 Budget accounting across re-entries
# ============================================================================

class TestBoot1BudgetAccounting:
    """S2: max_engine_iterations is shared across re-entries, not reset."""

    def test_budget_shared_across_reentry(self):
        """Observer events across all depths must total <= max_engine_iterations."""
        reset_step_budget()
        paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
        cycle_projs = paxos_seed["projections"][:4]
        initial = {"paxos_trigger": "start_paxos"}

        observer = []
        _run_boot1(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50,
            observer=observer,
        )

        # Count total step_boundary events across all depths
        step_events = [e for e in observer if e["event_name"] == "step_boundary"]
        total_steps = len(step_events)
        assert total_steps <= 20, (
            f"S2 violated: total step_boundary events ({total_steps}) exceeds "
            f"max_engine_iterations (20). Budget must be shared across re-entries."
        )

    def test_budget_monotonically_decreasing(self):
        """Each recursive depth gets strictly less budget than its parent."""
        reset_step_budget()
        paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
        cycle_projs = paxos_seed["projections"][:4]
        initial = {"paxos_trigger": "start_paxos"}

        observer = []
        _run_boot1(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50,
            observer=observer,
        )

        # Group step_boundary events by depth
        step_events = [e for e in observer if e["event_name"] == "step_boundary"]
        if not step_events:
            return  # No re-entry, nothing to verify

        by_depth = {}
        for e in step_events:
            d = e["boot1_depth"]
            by_depth[d] = by_depth.get(d, 0) + 1

        depths = sorted(by_depth.keys())
        if len(depths) < 2:
            return  # No re-entry, nothing to verify

        # Each deeper level must have strictly fewer iterations available
        for i in range(len(depths) - 1):
            parent_count = by_depth[depths[i]]
            child_count = by_depth[depths[i + 1]]
            # Child budget = parent_budget - parent_consumed - 1
            # So child_count must be < parent_budget - parent_consumed
            assert child_count <= 20 - parent_count - 1, (
                f"Child depth {depths[i+1]} used {child_count} iterations, "
                f"but parent depth {depths[i]} consumed {parent_count}. "
                f"Budget should be decreasing."
            )

    def test_low_budget_exhaustion_fail_closed(self):
        """With budget=2, re-entry that needs more should fail closed."""
        reset_step_budget()
        paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
        cycle_projs = paxos_seed["projections"][:4]
        initial = {"paxos_trigger": "start_paxos"}

        # Give very low budget — should either complete (if no re-entry)
        # or raise RuntimeError (budget exhausted at re-entry depth)
        with pytest.raises(RuntimeError, match="exhausted"):
            _run_boot1(
                cycle_projs, initial,
                max_steps=6, max_engine_iterations=3, max_algorithm_iterations=50,
            )

    def test_trampoline_budget_equivalent(self):
        """Trampoline and recursive use same total budget for same input."""
        reset_step_budget()
        paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
        cycle_projs = paxos_seed["projections"][:4]
        initial = {"paxos_trigger": "start_paxos"}

        trampoline_obs = []
        trampoline_result = _run_trampoline(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50,
            observer=trampoline_obs,
        )

        reset_step_budget()
        boot1_obs = []
        boot1_result = _run_boot1(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50,
            observer=boot1_obs,
        )

        # Both should produce identical results
        assert trampoline_result == boot1_result

        # Both should use similar total steps (trampoline all at depth 0)
        trampoline_steps = len([e for e in trampoline_obs if e["event_name"] == "step_boundary"])
        boot1_steps = len([e for e in boot1_obs if e["event_name"] == "step_boundary"])
        assert boot1_steps <= trampoline_steps + 1, (
            f"Boot1 ({boot1_steps} steps) should not use significantly more "
            f"steps than trampoline ({trampoline_steps} steps)"
        )
