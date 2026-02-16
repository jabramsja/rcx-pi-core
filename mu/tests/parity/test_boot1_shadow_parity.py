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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
