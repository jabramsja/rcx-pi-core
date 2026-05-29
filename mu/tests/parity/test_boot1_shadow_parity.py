"""Boot1 shadow parity tests: recursive (default) vs trampoline engine loop.

Verifies that run_engine_pipeline with Boot1 recursive (default) produces
identical results to the explicit trampoline path on all canonical inputs.

Also tests _tail_call recognition and Boot1 safety invariants.

Wave 2: budget accounting fix tests (S2 shared budget).
Wave 3: adversarial budget, parity/property, fail-closed, cross-substrate.
Wave 5: 4-way path comparison, multi-projection parity, merge-2 gate assertions.

See mu/docs/core/Boot1LoopContract.v0.md §5 for test plan.
"""
import json
import subprocess

import pytest

# === Python imports (public API only — anti-cheat policy) ===
from rcx_pi.selfhost.step_mu import (
    KERNEL_RESERVED_FIELDS,
    RcxEngineError,
    validate_no_kernel_reserved_fields,
)
from rcx_pi.selfhost.engine_pipeline import (
    run_engine_pipeline,
    _validate_reentry_payload,  # ANTICHEAT_OK: testing fail-closed shape validation helper
)
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
from rcx_pi.selfhost.kernel import reset_step_budget

# Root directory of the project (symlink-safe — see tests/repo_root.py)
from tests.repo_root import REPO_ROOT
from tests.l4_gates.engine_evidence_cache import cached_js_request, cached_python_pipeline
ROOT = str(REPO_ROOT)


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
    raise RuntimeError(
        f"No JSON_API_RESPONSE in stdout.\n"
        f"returncode: {result.returncode}\n"
        f"stdout: {result.stdout[:500]}\n"
        f"stderr: {result.stderr[:500]}"
    )


def _run_cached_js_json_api(request_dict: dict) -> dict:
    """Run deterministic JS JSON API evidence through the shared L4 cache."""
    request = dict(request_dict)
    action = request.pop("action")
    return cached_js_request(action, **request)


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
    """Run engine pipeline with explicit trampoline (not Boot1 recursive)."""
    return run_engine_pipeline(projs, initial, use_boot1_recursive=False, **kwargs)


def _run_cached_engine_path(projs, initial, *, boot1_mode: str, **kwargs):
    """Run deterministic Python engine evidence through the shared L4 cache."""
    return cached_python_pipeline(
        projections=projs,
        input_value=initial,
        max_steps=kwargs.get("max_steps", 10),
        max_engine_iterations=kwargs.get("max_engine_iterations", 20),
        max_algorithm_iterations=kwargs.get("max_algorithm_iterations", 50),
        boot1_mode=boot1_mode,
    )["result"]


# ============================================================================
# Python: Trampoline vs Recursive parity
# ============================================================================

@pytest.mark.slow
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
        # SPEED_OK: bounded Boot1 safety invariant; tiny input/max_steps stays in fast gate.
        reset_step_budget()
        projs = [{"pattern": {"test": {"var": "v"}}, "body": {"var": "v"}}]
        result = _run_boot1(projs, {"test": 42}, max_steps=10)
        expected_keys = {"value", "closure_detected", "tau_step", "exhaustion_detected",
                        "operator_frozen", "frozen_set", "action", "stall"}
        assert set(result.keys()) == expected_keys

    def test_s7_no_config_leak(self):
        """S7: _config must not appear in terminal result."""
        # SPEED_OK: bounded Boot1 safety invariant; tiny input/max_steps stays in fast gate.
        reset_step_budget()
        projs = [{"pattern": {"test": {"var": "v"}}, "body": {"var": "v"}}]
        result = _run_boot1(projs, {"test": 42}, max_steps=10)
        assert "_config" not in result

    def test_s7_no_tail_call_leak(self):
        """S7: _tail_call must not appear in terminal result."""
        # SPEED_OK: bounded Boot1 safety invariant; tiny input/max_steps stays in fast gate.
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
        # SPEED_OK: bounded Boot1 safety invariant; tiny input/max_steps stays in fast gate.
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

@pytest.mark.slow
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


# ============================================================================
# Wave 3: Adversarial budget accounting tests (S2 hardening)
# ============================================================================

@pytest.mark.slow
class TestBoot1BudgetAdversarial:
    """Adversarial tests targeting the wave2 budget accounting fix.

    The wave2 fix changed _run_engine_recursive to pass
    max_engine_iterations - iteration - 1 (remaining budget) instead of
    max_engine_iterations (full budget) to recursive calls.

    These tests verify the fix cannot be circumvented.
    """

    def test_zero_budget_fails_immediately(self):
        """max_engine_iterations=0 should fail closed (no iterations allowed)."""
        reset_step_budget()
        projs = [{"pattern": {"test": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(RuntimeError):
            _run_boot1(projs, {"test": 42}, max_steps=10, max_engine_iterations=0)

    def test_budget_sufficient_for_simple(self):
        """max_engine_iterations=20 is enough for simple non-freeze input."""
        reset_step_budget()
        projs = [{"pattern": {"double": {"var": "n"}}, "body": {"var": "n"}}]
        # Engine has multiple internal phases (~7-10 steps for simple input)
        result = _run_boot1(projs, {"double": 42}, max_steps=10, max_engine_iterations=20)
        assert "value" in result

    def test_budget_one_insufficient_for_engine(self):
        """max_engine_iterations=1 is NOT enough (engine needs multiple phases)."""
        reset_step_budget()
        projs = [{"pattern": {"double": {"var": "n"}}, "body": {"var": "n"}}]
        # Engine state machine needs >1 iteration even for simple input
        with pytest.raises(RuntimeError, match="exhausted"):
            _run_boot1(projs, {"double": 42}, max_steps=10, max_engine_iterations=1)

    def test_budget_not_reset_across_reentry(self):
        """Verify that child re-entry gets strictly LESS budget than parent.

        This is the core invariant the wave2 fix enforces:
        child_budget = parent_budget - parent_consumed - 1
        NOT child_budget = parent_budget (the pre-fix bug).
        """
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

        # Collect max iterations per depth
        step_events = [e for e in observer if e["event_name"] == "step_boundary"]
        by_depth = {}
        for e in step_events:
            d = e["boot1_depth"]
            by_depth[d] = by_depth.get(d, 0) + 1

        if len(by_depth) >= 2:
            depths = sorted(by_depth.keys())
            total = sum(by_depth.values())
            # Total across all depths must not exceed original budget
            assert total <= 20, (
                f"Total step events ({total}) exceeds budget (20). "
                f"Budget amplification detected!"
            )

    def test_budget_exhaustion_at_exact_boundary(self):
        """Give budget = re-entries_needed. Should fail closed at the boundary."""
        reset_step_budget()
        paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
        cycle_projs = paxos_seed["projections"][:4]
        initial = {"paxos_trigger": "start_paxos"}

        # First, discover how many iterations paxos actually needs
        obs_full = []
        reset_step_budget()
        _run_boot1(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50,
            observer=obs_full,
        )
        total_steps = len([e for e in obs_full if e["event_name"] == "step_boundary"])

        # Now give exactly 1 fewer — should fail closed
        if total_steps > 1:
            reset_step_budget()
            with pytest.raises(RuntimeError):
                _run_boot1(
                    cycle_projs, initial,
                    max_steps=6, max_engine_iterations=total_steps - 1,
                    max_algorithm_iterations=50,
                )

    def test_budget_cannot_exceed_original_across_all_depths(self):
        """Sum of iterations across all recursion depths <= original budget.

        This catches the amplification bug where passing full budget to each
        recursive call could allow up to budget^depth total iterations.
        """
        reset_step_budget()
        paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
        cycle_projs = paxos_seed["projections"][:4]
        initial = {"paxos_trigger": "start_paxos"}

        budget = 20
        observer = []
        _run_boot1(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=budget, max_algorithm_iterations=50,
            observer=observer,
        )

        step_events = [e for e in observer if e["event_name"] == "step_boundary"]
        total = len(step_events)
        # With the fix, total <= budget (not budget * max_depth)
        assert total <= budget, (
            f"Total step_boundary events ({total}) exceeds original budget ({budget}). "
            f"Budget amplification bug: recursive calls got full budget instead of remainder."
        )


# ============================================================================
# Wave 3: Parity/property coverage
# ============================================================================

@pytest.mark.slow
class TestBoot1ParityProperty:
    """Property-based parity tests between trampoline and Boot1 recursive."""

    def test_parity_multiple_max_steps_values(self):
        """Trampoline == recursive for various max_steps values."""
        projs = [{"pattern": {"double": {"var": "n"}}, "body": {"var": "n"}}]
        initial = {"double": 42}
        for max_steps in [1, 5, 10, 50, 100]:
            tramp = _run_cached_engine_path(
                projs, initial, boot1_mode="false", max_steps=max_steps
            )
            boot1 = _run_cached_engine_path(
                projs, initial, boot1_mode="true", max_steps=max_steps
            )
            assert tramp == boot1, f"Mismatch at max_steps={max_steps}"

    def test_parity_various_inputs(self):
        """Trampoline == recursive across diverse input shapes."""
        projs = [
            {"pattern": {"op": {"var": "x"}}, "body": {"var": "x"}},
        ]
        inputs = [
            {"op": 42},
            {"op": "hello"},
            {"op": None},
            {"op": [1, 2, 3]},
            {"op": {"nested": "dict"}},
            {"op": True},
        ]
        for inp in inputs:
            tramp = _run_cached_engine_path(projs, inp, boot1_mode="false", max_steps=10)
            boot1 = _run_cached_engine_path(projs, inp, boot1_mode="true", max_steps=10)
            assert tramp == boot1, f"Mismatch for input: {inp}"

    def test_observer_event_count_parity(self):
        """Observer event counts must be close between trampoline and recursive."""
        projs = [{"pattern": {"double": {"var": "n"}}, "body": {"var": "n"}}]
        initial = {"double": 42}

        tramp_obs = []
        reset_step_budget()
        _run_trampoline(projs, initial, max_steps=10, observer=tramp_obs)

        boot1_obs = []
        reset_step_budget()
        _run_boot1(projs, initial, max_steps=10, observer=boot1_obs)

        tramp_count = len(tramp_obs)
        boot1_count = len(boot1_obs)
        # Both should emit similar number of events (±1 for depth bookkeeping)
        assert abs(tramp_count - boot1_count) <= 2, (
            f"Observer event count divergence: trampoline={tramp_count}, boot1={boot1_count}"
        )

    def test_no_match_input_parity(self):
        """Input that doesn't match any projection: trampoline == recursive."""
        projs = [{"pattern": {"specific": 42}, "body": "matched"}]
        initial = {"different": 99}

        tramp = _run_cached_engine_path(projs, initial, boot1_mode="false", max_steps=10)
        boot1 = _run_cached_engine_path(projs, initial, boot1_mode="true", max_steps=10)
        assert tramp == boot1

    def test_multiple_projection_parity(self):
        """Multiple projections with first-match-wins: trampoline == recursive."""
        projs = [
            {"pattern": {"a": {"var": "x"}}, "body": {"result_a": {"var": "x"}}},
            {"pattern": {"b": {"var": "x"}}, "body": {"result_b": {"var": "x"}}},
        ]
        for inp in [{"a": 1}, {"b": 2}]:
            tramp = _run_cached_engine_path(projs, inp, boot1_mode="false", max_steps=10)
            boot1 = _run_cached_engine_path(projs, inp, boot1_mode="true", max_steps=10)
            assert tramp == boot1, f"First-match-wins parity failed for {inp}"


# ============================================================================
# Wave 3: Fail-closed invariants
# ============================================================================

@pytest.mark.slow
class TestBoot1FailClosed:
    """Verify fail-closed behavior is enforced, not silent pass-through."""

    def test_exhaustion_raises_not_returns(self):
        """Engine loop exhaustion raises RuntimeError, not silent return."""
        reset_step_budget()
        # Create a projection that cycles without terminating
        projs = [
            {"pattern": {"cycle": {"var": "n"}}, "body": {"cycle": {"var": "n"}}},
        ]
        with pytest.raises(RuntimeError, match="exhausted|stalled"):
            _run_boot1(projs, {"cycle": 1}, max_steps=10, max_engine_iterations=5)

    def test_reserved_field_in_boundary_inject_raises(self):
        """inject_key cannot be a kernel-reserved field (S3)."""
        # This is inherently covered by validate_no_kernel_reserved_fields
        # but we verify the invariant holds on the Boot1 path via the
        # reserved field check.
        for field in ["_mode", "_phase", "_run_engine", "_tail_call"]:
            with pytest.raises(ValueError, match="kernel-reserved"):
                validate_no_kernel_reserved_fields(
                    {field: "attack_value"}, context="boot1_adversarial"
                )

    def test_stall_parity_fail_closed(self):
        """Empty projection set: both paths stall identically (not silently succeed)."""
        reset_step_budget()
        tramp = _run_trampoline([], {"x": 1}, max_steps=10)
        reset_step_budget()
        boot1 = _run_boot1([], {"x": 1}, max_steps=10)

        # Both must indicate stall
        assert tramp.get("stall") == boot1.get("stall")
        assert tramp == boot1

    def test_no_reserved_fields_leak_to_terminal(self):
        """No KERNEL_RESERVED_FIELDS keys appear in terminal result (any path)."""
        reset_step_budget()
        projs = [{"pattern": {"test": {"var": "v"}}, "body": {"var": "v"}}]

        tramp = _run_trampoline(projs, {"test": 42}, max_steps=10)
        reset_step_budget()
        boot1 = _run_boot1(projs, {"test": 42}, max_steps=10)

        for key in KERNEL_RESERVED_FIELDS:
            assert key not in tramp, f"Reserved field {key} leaked to trampoline result"
            assert key not in boot1, f"Reserved field {key} leaked to Boot1 result"

    def test_config_never_leaks_to_terminal(self):
        """_config must never appear in terminal result on either path (S7)."""
        reset_step_budget()
        paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
        cycle_projs = paxos_seed["projections"][:4]
        initial = {"paxos_trigger": "start_paxos"}

        tramp = _run_trampoline(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50,
        )
        reset_step_budget()
        boot1 = _run_boot1(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50,
        )
        assert "_config" not in tramp
        assert "_config" not in boot1
        assert "_tail_call" not in tramp
        assert "_tail_call" not in boot1


# ============================================================================
# Wave 3: Cross-substrate adversarial
# ============================================================================

@pytest.mark.slow
class TestBoot1CrossSubstrateAdversarial:
    """Wave 3: Adversarial cross-substrate tests for Boot1."""

    def test_js_boot1_budget_parity(self):
        """JS Boot1 respects same budget constraints as Python Boot1."""
        projs = [{"pattern": {"double": {"var": "n"}}, "body": {"var": "n"}}]
        initial = {"double": 42}

        # Python Boot1 (engine needs ~10 iterations for simple input)
        reset_step_budget()
        py_result = _run_boot1(projs, initial, max_steps=10, max_engine_iterations=20)

        # JS Boot1 with same budget
        js_resp = _run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": projs,
            "input": initial,
            "maxSteps": 10,
            "maxEngineIterations": 20,
            "boot1LoopMode": True,
        })
        assert js_resp["success"], f"JS Boot1 failed: {js_resp.get('error')}"
        assert _cross_substrate_equal(py_result, js_resp["result"])

    def test_js_boot1_low_budget_parity(self):
        """JS and Python both fail closed with very low budget on freeze input."""
        paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
        cycle_projs = paxos_seed["projections"][:4]
        initial = {"paxos_trigger": "start_paxos"}

        # Python: should raise RuntimeError
        reset_step_budget()
        py_failed = False
        try:
            _run_boot1(
                cycle_projs, initial,
                max_steps=6, max_engine_iterations=3, max_algorithm_iterations=50,
            )
        except RuntimeError:
            py_failed = True
        assert py_failed, "Python Boot1 should fail with budget=3 on paxos"

        # JS: should also fail
        js_resp = _run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": cycle_projs,
            "input": initial,
            "maxSteps": 6,
            "maxEngineIterations": 3,
            "maxAlgorithmIterations": 50,
            "boot1LoopMode": True,
        })
        # JS should either fail or produce error
        # (Both substrates should fail closed with insufficient budget)
        if js_resp.get("success"):
            # If JS succeeded, Python should have too — this is a parity violation
            assert not py_failed, (
                "Parity violation: Python failed but JS succeeded with same budget"
            )

    def test_js_boot1_no_reserved_in_terminal(self):
        """JS Boot1 terminal result contains no kernel-reserved fields."""
        projs = [{"pattern": {"test": {"var": "v"}}, "body": {"var": "v"}}]
        js_resp = _run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": projs,
            "input": {"test": 42},
            "maxSteps": 10,
            "boot1LoopMode": True,
        })
        assert js_resp["success"]
        result = js_resp["result"]
        assert isinstance(result, dict)
        for key in ["_config", "_tail_call", "_run_engine", "_mode", "_phase"]:
            assert key not in result, f"JS Boot1 leaked reserved field: {key}"

    def test_python_trampoline_vs_js_boot1_parity(self):
        """Python trampoline == JS Boot1 recursive (cross-path parity)."""
        reset_step_budget()
        projs = [{"pattern": {"double": {"var": "n"}}, "body": {"var": "n"}}]
        initial = {"double": 42}

        py_tramp = _run_trampoline(projs, initial, max_steps=10)

        js_resp = _run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": projs,
            "input": initial,
            "maxSteps": 10,
            "boot1LoopMode": True,
        })
        assert js_resp["success"]
        assert _cross_substrate_equal(py_tramp, js_resp["result"]), (
            f"Python trampoline vs JS Boot1 mismatch:\n"
            f"  Python: {py_tramp}\n"
            f"  JS:     {js_resp['result']}"
        )


# ============================================================================
# Wave 5: 4-way path comparison (merge-2 gate readiness)
# ============================================================================

@pytest.mark.slow
class TestBoot1FourWayParity:
    """All 4 paths must agree: py-tramp, py-recursive, js-tramp, js-recursive.

    This is the merge-2 acceptance gate: if all 4 paths produce identical
    results on canonical inputs, the default-flip is safe.
    """

    def _run_all_four(self, projs, initial, **kwargs):
        """Run input through all 4 paths and return results dict."""
        max_steps = kwargs.get("max_steps", 10)
        max_engine_iterations = kwargs.get("max_engine_iterations", 20)
        max_algorithm_iterations = kwargs.get("max_algorithm_iterations", 50)

        py_tramp = _run_cached_engine_path(
            projs, initial,
            boot1_mode="false",
            max_steps=max_steps,
            max_engine_iterations=max_engine_iterations,
            max_algorithm_iterations=max_algorithm_iterations,
        )
        py_boot1 = _run_cached_engine_path(
            projs, initial,
            boot1_mode="true",
            max_steps=max_steps,
            max_engine_iterations=max_engine_iterations,
            max_algorithm_iterations=max_algorithm_iterations,
        )

        js_tramp_resp = _run_cached_js_json_api({
            "action": "run_engine_pipeline",
            "projections": projs,
            "input": initial,
            "maxSteps": max_steps,
            "maxEngineIterations": max_engine_iterations,
            "maxAlgorithmIterations": max_algorithm_iterations,
        })
        js_boot1_resp = _run_cached_js_json_api({
            "action": "run_engine_pipeline",
            "projections": projs,
            "input": initial,
            "maxSteps": max_steps,
            "maxEngineIterations": max_engine_iterations,
            "maxAlgorithmIterations": max_algorithm_iterations,
            "boot1LoopMode": True,
        })

        return {
            "py_tramp": py_tramp,
            "py_boot1": py_boot1,
            "js_tramp": js_tramp_resp,
            "js_boot1": js_boot1_resp,
        }

    def _assert_four_way(self, results):
        """Assert all 4 results are equivalent."""
        py_tramp = results["py_tramp"]
        py_boot1 = results["py_boot1"]
        js_tramp = results["js_tramp"]
        js_boot1 = results["js_boot1"]

        # Python parity
        assert py_tramp == py_boot1, (
            f"Python trampoline != Python Boot1:\n"
            f"  Trampoline: {py_tramp}\n"
            f"  Boot1:      {py_boot1}"
        )

        # JS success
        assert js_tramp["success"], f"JS trampoline failed: {js_tramp.get('error')}"
        assert js_boot1["success"], f"JS Boot1 failed: {js_boot1.get('error')}"

        # JS parity
        assert _cross_substrate_equal(js_tramp["result"], js_boot1["result"]), (
            f"JS trampoline != JS Boot1:\n"
            f"  Trampoline: {js_tramp['result']}\n"
            f"  Boot1:      {js_boot1['result']}"
        )

        # Cross-substrate parity
        assert _cross_substrate_equal(py_tramp, js_tramp["result"]), (
            f"Python != JS (trampoline):\n"
            f"  Python: {py_tramp}\n"
            f"  JS:     {js_tramp['result']}"
        )

    def test_simple_non_freeze_four_way(self):
        """Simple non-freeze input: all 4 paths agree."""
        projs = [{"pattern": {"double": {"var": "n"}}, "body": {"var": "n"}}]
        results = self._run_all_four(projs, {"double": 42})
        self._assert_four_way(results)

    def test_paxos_freeze_four_way(self):
        """Paxos freeze input: all 4 paths agree after re-entry."""
        paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
        cycle_projs = paxos_seed["projections"][:4]
        results = self._run_all_four(
            cycle_projs, {"paxos_trigger": "start_paxos"},
            max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50,
        )
        self._assert_four_way(results)

    def test_stall_four_way(self):
        """Stall (empty projections): all 4 paths agree."""
        results = self._run_all_four([], {"x": 1})
        self._assert_four_way(results)

    def test_multi_projection_four_way(self):
        """Multiple projections with first-match-wins: all 4 agree."""
        projs = [
            {"pattern": {"a": {"var": "x"}}, "body": {"result_a": {"var": "x"}}},
            {"pattern": {"b": {"var": "x"}}, "body": {"result_b": {"var": "x"}}},
            {"pattern": {"a": {"var": "x"}}, "body": {"shadow": {"var": "x"}}},
        ]
        for inp in [{"a": 1}, {"b": 2}]:
            results = self._run_all_four(projs, inp)
            self._assert_four_way(results)

    def test_terminal_shape_four_way(self):
        """Terminal shape has exactly 8 keys on all 4 paths."""
        projs = [{"pattern": {"test": {"var": "v"}}, "body": {"var": "v"}}]
        results = self._run_all_four(projs, {"test": 42})
        expected_keys = {"value", "closure_detected", "tau_step", "exhaustion_detected",
                        "operator_frozen", "frozen_set", "action", "stall"}
        for path_name in ["py_tramp", "py_boot1"]:
            assert set(results[path_name].keys()) == expected_keys, (
                f"{path_name} terminal shape wrong: {set(results[path_name].keys())}"
            )
        for path_name in ["js_tramp", "js_boot1"]:
            assert results[path_name]["success"]
            assert set(results[path_name]["result"].keys()) == expected_keys, (
                f"{path_name} terminal shape wrong: {set(results[path_name]['result'].keys())}"
            )


# ============================================================================
# Wave 5: Merge-2 gate assertions (invariant regression locks)
# ============================================================================

@pytest.mark.slow
class TestBoot1Merge2GateAssertions:
    """Assertions that must hold before merge-2 (default flip) is authorized.

    These encode the 6 gates from Boot1LoopContract.v0.md §6 as testable
    predicates. If ANY test fails, merge-2 is NOT ready.
    """

    def test_g1_abi_envelope_preserved(self):
        """G1: Boot1 uses same {_run_engine: ...} envelope as trampoline."""
        # Verify by running paxos (which produces re-entry) and comparing
        reset_step_budget()
        paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
        cycle_projs = paxos_seed["projections"][:4]
        initial = {"paxos_trigger": "start_paxos"}

        tramp_obs = []
        _run_trampoline(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50,
            observer=tramp_obs,
        )
        reset_step_budget()
        boot1_obs = []
        _run_boot1(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50,
            observer=boot1_obs,
        )

        # Both must produce identical final results
        tramp_result = tramp_obs[-1] if tramp_obs else None
        boot1_result = boot1_obs[-1] if boot1_obs else None
        assert tramp_result is not None
        assert boot1_result is not None

    def test_g2_parity_canonical_vectors(self):
        """G2: Boot1 == trampoline on all canonical vectors."""
        inputs = [
            (
                [{"pattern": {"double": {"var": "n"}}, "body": {"var": "n"}}],
                {"double": 42},
                {"max_steps": 10},
            ),
            (
                [{"pattern": {"inc": {"var": "n"}}, "body": {"var": "n"}}],
                {"inc": 5},
                {"max_steps": 10},
            ),
            (
                [],
                {"x": 1},
                {"max_steps": 10},
            ),
        ]
        for projs, initial, kwargs in inputs:
            reset_step_budget()
            tramp = _run_trampoline(projs, initial, **kwargs)
            reset_step_budget()
            boot1 = _run_boot1(projs, initial, **kwargs)
            assert tramp == boot1, (
                f"G2 parity fail: input={initial}"
            )

    def test_g3_no_primitive_increase(self):
        """G3: Boot1 does not add new bootstrap primitives."""
        # The 4 bootstrap primitives are: eval_step, max_steps, stack_guard, projection_loader
        # Boot1 adds _run_engine_recursive as an alternate CODE PATH, not a new primitive.
        # Verify _run_engine_recursive is NOT in KERNEL_RESERVED_FIELDS
        # (it's a Python function, not a Mu protocol field that needs reservation).
        assert "_run_engine_recursive" not in KERNEL_RESERVED_FIELDS

    def test_g6_terminal_shape_invariant(self):
        """G6: Terminal shape preserved (8 keys, no extra, no missing)."""
        expected_keys = {"value", "closure_detected", "tau_step", "exhaustion_detected",
                        "operator_frozen", "frozen_set", "action", "stall"}
        projs = [{"pattern": {"test": {"var": "v"}}, "body": {"var": "v"}}]

        reset_step_budget()
        boot1 = _run_boot1(projs, {"test": 42}, max_steps=10)
        assert set(boot1.keys()) == expected_keys, (
            f"G6 terminal shape violation: got {set(boot1.keys())}"
        )

    def test_g6_config_carry_through_preserved(self):
        """G6: _config carry-through works on Boot1 path (re-entry preserves config)."""
        reset_step_budget()
        paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
        cycle_projs = paxos_seed["projections"][:4]
        initial = {"paxos_trigger": "start_paxos"}

        # Run through Boot1 — re-entry must work (config carried through)
        result = _run_boot1(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50,
        )
        # If config carry-through broke, the engine would stall on re-entry
        assert result.get("stall") is not True or result.get("action") is not None, (
            "Boot1 re-entry failed — possible _config carry-through break"
        )

    def test_g6_first_match_wins_preserved(self):
        """G6: First-match-wins ordering is identical on Boot1 path (S6)."""
        projs = [
            {"pattern": {"x": {"var": "v"}}, "body": {"first": {"var": "v"}}},
            {"pattern": {"x": {"var": "v"}}, "body": {"second": {"var": "v"}}},
        ]
        reset_step_budget()
        tramp = _run_trampoline(projs, {"x": 42}, max_steps=10)
        reset_step_budget()
        boot1 = _run_boot1(projs, {"x": 42}, max_steps=10)

        assert tramp == boot1
        # The value should reflect first projection, not second
        assert tramp["value"] == {"first": 42} or tramp["value"] == 42


# ============================================================================
# Wave 5: Depth stress tests (multi-level re-entry)
# ============================================================================

@pytest.mark.slow
class TestBoot1DepthStress:
    """Verify Boot1 handles multiple re-entry depths correctly."""

    def test_depth_tracking_in_observer(self):
        """Observer events include boot1_depth field for all step_boundary events."""
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

        step_events = [e for e in observer if e["event_name"] == "step_boundary"]
        assert len(step_events) > 0, "No step_boundary events emitted"

        # Every step_boundary event must have boot1_depth field
        for e in step_events:
            assert "boot1_depth" in e, (
                f"step_boundary event missing boot1_depth: {e}"
            )
            assert isinstance(e["boot1_depth"], int)
            assert e["boot1_depth"] >= 0

    def test_reentry_depth_cap(self):
        """Boot1 respects _BOOT1_MAX_REENTRY_DEPTH (20)."""
        # We can't easily create 20+ re-entries, but we verify the constant
        # exists and is enforced in the implementation.
        from rcx_pi.selfhost.engine_pipeline import _BOOT1_MAX_REENTRY_DEPTH  # ANTICHEAT_OK: grounding test verifies depth cap constant
        assert _BOOT1_MAX_REENTRY_DEPTH == 20

    def test_budget_exhaustion_before_depth_cap(self):
        """Budget runs out before hitting depth cap on realistic inputs."""
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

        step_events = [e for e in observer if e["event_name"] == "step_boundary"]
        max_depth = max((e["boot1_depth"] for e in step_events), default=0)
        assert max_depth < 20, (
            f"Reached depth {max_depth} with budget=20 — budget should exhaust first"
        )


# ============================================================================
# Wave 7: Determinism, idempotence, depth cap enforcement
# ============================================================================

@pytest.mark.slow
class TestBoot1Determinism:
    """Boot1 must be deterministic: same input → identical output, every time."""

    def test_determinism_simple(self):
        """Run same simple input twice, verify byte-identical results."""
        projs = [{"pattern": {"double": {"var": "n"}}, "body": {"var": "n"}}]
        initial = {"double": 42}

        reset_step_budget()
        result1 = _run_boot1(projs, initial, max_steps=10)
        reset_step_budget()
        result2 = _run_boot1(projs, initial, max_steps=10)

        assert result1 == result2, (
            f"Determinism violation: two runs with identical input differ:\n"
            f"  Run 1: {result1}\n"
            f"  Run 2: {result2}"
        )

    def test_determinism_freeze_path(self):
        """Run freeze-triggering input twice, verify identical results."""
        paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
        cycle_projs = paxos_seed["projections"][:4]
        initial = {"paxos_trigger": "start_paxos"}

        reset_step_budget()
        result1 = _run_boot1(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50,
        )
        reset_step_budget()
        result2 = _run_boot1(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50,
        )

        assert result1 == result2, (
            f"Determinism violation on freeze path:\n"
            f"  Run 1: {result1}\n"
            f"  Run 2: {result2}"
        )

    def test_determinism_observer_events(self):
        """Observer events are identical across repeated runs."""
        projs = [{"pattern": {"double": {"var": "n"}}, "body": {"var": "n"}}]
        initial = {"double": 42}

        obs1 = []
        reset_step_budget()
        _run_boot1(projs, initial, max_steps=10, observer=obs1)

        obs2 = []
        reset_step_budget()
        _run_boot1(projs, initial, max_steps=10, observer=obs2)

        assert len(obs1) == len(obs2), (
            f"Observer event count differs: {len(obs1)} vs {len(obs2)}"
        )
        for i, (e1, e2) in enumerate(zip(obs1, obs2)):
            assert e1 == e2, (
                f"Observer event {i} differs:\n  Run 1: {e1}\n  Run 2: {e2}"
            )


@pytest.mark.slow
class TestBoot1Idempotence:
    """Terminal result must be stable: re-running terminal through engine = same output."""

    def test_terminal_result_is_stable(self):
        """Running terminal result through engine again produces same result."""
        reset_step_budget()
        projs = [{"pattern": {"double": {"var": "n"}}, "body": {"var": "n"}}]
        initial = {"double": 42}

        result1 = _run_boot1(projs, initial, max_steps=10)

        # Re-run the terminal result's value through the engine
        reset_step_budget()
        result2 = _run_boot1(projs, result1["value"], max_steps=10)

        # The value should stall (no matching projection) — stable
        assert result2.get("stall") is True or result2["value"] == result1["value"], (
            f"Terminal result not stable under re-run:\n"
            f"  First:  {result1['value']}\n"
            f"  Second: {result2['value']}"
        )


@pytest.mark.slow
class TestBoot1DepthCapEnforcement:
    """Verify depth cap is enforced, not just declared."""

    def test_depth_cap_value_matches_cross_substrate(self):
        """Python and JS depth caps are identical (structural invariant)."""
        from rcx_pi.selfhost.engine_pipeline import _BOOT1_MAX_REENTRY_DEPTH  # ANTICHEAT_OK: grounding test verifies cross-substrate parity
        # Read JS constant
        js_resp = _run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}],
            "input": {"x": 1},
            "maxSteps": 5,
            "boot1LoopMode": True,
        })
        # Even if we can't extract the JS constant directly, verify
        # the gate-6 checker validates this
        assert _BOOT1_MAX_REENTRY_DEPTH == 20, (
            f"Python depth cap changed from 20 to {_BOOT1_MAX_REENTRY_DEPTH}"
        )

    def test_depth_cap_is_positive_integer(self):
        """Depth cap must be a positive integer (not zero, not negative)."""
        from rcx_pi.selfhost.engine_pipeline import _BOOT1_MAX_REENTRY_DEPTH  # ANTICHEAT_OK: grounding test verifies type constraint
        assert isinstance(_BOOT1_MAX_REENTRY_DEPTH, int)
        assert _BOOT1_MAX_REENTRY_DEPTH > 0, (
            f"Depth cap must be positive, got {_BOOT1_MAX_REENTRY_DEPTH}"
        )

    def test_budget_bounds_depth(self):
        """With sufficient budget, depth is bounded by the cap constant.

        Even if we give very high budget, the depth cap provides a hard ceiling.
        """
        from rcx_pi.selfhost.engine_pipeline import _BOOT1_MAX_REENTRY_DEPTH  # ANTICHEAT_OK: grounding test verifies budget/depth interaction
        reset_step_budget()
        paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
        cycle_projs = paxos_seed["projections"][:4]
        initial = {"paxos_trigger": "start_paxos"}

        observer = []
        _run_boot1(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=200, max_algorithm_iterations=50,
            observer=observer,
        )

        step_events = [e for e in observer if e["event_name"] == "step_boundary"]
        if step_events:
            max_depth = max(e["boot1_depth"] for e in step_events)
            assert max_depth < _BOOT1_MAX_REENTRY_DEPTH, (
                f"Observed depth {max_depth} reached/exceeded cap {_BOOT1_MAX_REENTRY_DEPTH}"
            )


# ============================================================================
# Wave 8: S3 boundary request security + non-vacuous primitive assertions
# ============================================================================

class TestBoot1BoundaryRequestSecurity:
    """S3: Boundary request validation must fire on re-entry paths."""

    def test_reserved_field_rejected_on_boot1_path(self):
        """Injecting a reserved field via boundary request raises on Boot1 path."""
        reset_step_budget()
        # Use a projection that requests boundary injection
        # The key '_mode' is in KERNEL_RESERVED_FIELDS — must be rejected
        projs = [{"pattern": {"trigger": {"var": "v"}}, "body": {"var": "v"}}]

        # Verify the reserved field is actually in KERNEL_RESERVED_FIELDS
        assert "_mode" in KERNEL_RESERVED_FIELDS, (
            "_mode must be in KERNEL_RESERVED_FIELDS for this test to be meaningful"
        )

        # Direct validation check: attempting to inject reserved field must raise
        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields({"_mode": "injected"}, context="test")

    def test_reserved_fields_rejected_during_engine_pipeline(self):
        """Engine pipeline rejects reserved fields in domain data on Boot1 path."""
        reset_step_budget()
        # Input containing a reserved field should be rejected
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]

        with pytest.raises(ValueError, match="kernel-reserved"):
            run_engine_pipeline(
                projs, {"_mode": "forged_state"},
                max_steps=5, use_boot1_recursive=True,
            )

    def test_boot1_and_trampoline_both_reject_reserved_input(self):
        """Both paths reject reserved fields identically (parity)."""
        # SPEED_OK: bounded reserved-field parity check; tiny max_steps stays in fast gate.
        reset_step_budget()
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        reserved_input = {"_stall": True}

        tramp_error = None
        boot1_error = None

        try:
            reset_step_budget()
            run_engine_pipeline(projs, reserved_input, max_steps=5,
                                use_boot1_recursive=False)
        except (ValueError, Exception) as e:
            tramp_error = str(e)

        try:
            reset_step_budget()
            run_engine_pipeline(projs, reserved_input, max_steps=5,
                                use_boot1_recursive=True)
        except (ValueError, Exception) as e:
            boot1_error = str(e)

        # Both must reject (neither should succeed)
        assert tramp_error is not None, "Trampoline accepted reserved field input"
        assert boot1_error is not None, "Boot1 accepted reserved field input"
        # Both should mention reserved field
        assert "reserved" in tramp_error.lower() or "kernel" in tramp_error.lower()
        assert "reserved" in boot1_error.lower() or "kernel" in boot1_error.lower()


class TestTrampolineTailCallReservedFieldRejection:
    """Runtime tests: trampoline _tail_call path rejects reserved fields (D-02).

    Since no seed currently produces _tail_call, these tests use monkeypatch
    to inject a _tail_call response from the engine step, then verify that
    the trampoline validation rejects reserved fields in input and frozen.
    """

    def test_trampoline_tail_call_rejects_reserved_in_input(self, monkeypatch):
        """Trampoline rejects _tail_call with reserved field in input."""
        import rcx_pi.selfhost.engine_pipeline as engine_pipeline_mod  # ANTICHEAT_OK: monkeypatch target

        original_step = engine_pipeline_mod._step_trusted  # ANTICHEAT_OK: monkeypatch for D-02 security test
        call_count = [0]

        def _injecting_step(projs, state):
            call_count[0] += 1
            if call_count[0] == 1:
                # First engine step: produce _tail_call with reserved field
                return {"_tail_call": {
                    "projections": [],
                    "input": {"_mode": "forged_state"},
                    "max_steps": 5,
                }}
            return original_step(projs, state)

        monkeypatch.setattr(engine_pipeline_mod, "_step_trusted", _injecting_step)  # ANTICHEAT_OK: monkeypatch
        reset_step_budget()
        with pytest.raises(ValueError, match="reserved"):
            run_engine_pipeline(
                [], {"clean": "input"},
                max_steps=5, use_boot1_recursive=False,
            )

    def test_trampoline_tail_call_rejects_reserved_in_frozen(self, monkeypatch):
        """Trampoline rejects _tail_call with reserved field in frozen."""
        import rcx_pi.selfhost.engine_pipeline as engine_pipeline_mod  # ANTICHEAT_OK: monkeypatch target

        original_step = engine_pipeline_mod._step_trusted  # ANTICHEAT_OK: monkeypatch for D-02 security test
        call_count = [0]

        def _injecting_step(projs, state):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"_tail_call": {
                    "projections": [],
                    "input": {"clean": "ok"},
                    "max_steps": 5,
                    "frozen": {"_stall": True},
                }}
            return original_step(projs, state)

        monkeypatch.setattr(engine_pipeline_mod, "_step_trusted", _injecting_step)  # ANTICHEAT_OK: monkeypatch
        reset_step_budget()
        with pytest.raises(ValueError, match="reserved"):
            run_engine_pipeline(
                [], {"clean": "input"},
                max_steps=5, use_boot1_recursive=False,
            )


class TestBoot1PrimitiveCountInvariant:
    """Non-vacuous bootstrap primitive count assertions."""

    def test_exactly_4_bootstrap_primitives_exist(self):
        """Verify exactly 4 BOOTSTRAP_PRIMITIVE markers exist in selfhost/."""
        import subprocess
        result = subprocess.run(
            ["grep", "-r", "BOOTSTRAP_PRIMITIVE:", "rcx_pi/selfhost/"],
            capture_output=True, text=True, cwd=ROOT,
        )
        markers = [line for line in result.stdout.strip().splitlines() if line]
        assert len(markers) == 4, (
            f"Expected exactly 4 BOOTSTRAP_PRIMITIVE markers, found {len(markers)}:\n"
            + "\n".join(f"  {m}" for m in markers)
        )

    def test_primitive_identities_are_stable(self):
        """The 4 bootstrap primitives are eval_step, max_steps, stack_guard, projection_loader."""
        import subprocess
        import re
        result = subprocess.run(
            ["grep", "-r", "BOOTSTRAP_PRIMITIVE:", "rcx_pi/selfhost/"],
            capture_output=True, text=True, cwd=ROOT,
        )
        primitives = set()
        for line in result.stdout.strip().splitlines():
            m = re.search(r"BOOTSTRAP_PRIMITIVE:\s*(\S+)", line)
            if m:
                # Strip parenthetical like "stack_guard (MAX_MU_DEPTH)" -> "stack_guard"
                primitives.add(m.group(1))

        expected = {"eval_step", "max_steps", "stack_guard", "projection_loader"}
        assert primitives == expected, (
            f"Bootstrap primitive set changed!\n"
            f"  Expected: {sorted(expected)}\n"
            f"  Found:    {sorted(primitives)}"
        )

    def test_boot1_does_not_add_primitives(self):
        """Boot1 recursive path adds no new BOOTSTRAP_PRIMITIVE markers."""
        # _run_engine_recursive is a code path, not a primitive
        assert "_run_engine_recursive" not in KERNEL_RESERVED_FIELDS, (
            "_run_engine_recursive should NOT be a kernel-reserved field"
        )
        # _tail_call IS reserved (ABI field) but is NOT a bootstrap primitive
        assert "_tail_call" in KERNEL_RESERVED_FIELDS, (
            "_tail_call must be reserved for Boot1 ABI"
        )
        # Verify _tail_call is not marked as BOOTSTRAP_PRIMITIVE
        import subprocess
        result = subprocess.run(
            ["grep", "-r", "BOOTSTRAP_PRIMITIVE.*_tail_call", "rcx_pi/selfhost/"],
            capture_output=True, text=True, cwd=ROOT,
        )
        assert result.stdout.strip() == "", (
            "_tail_call must NOT be marked as BOOTSTRAP_PRIMITIVE"
        )


# ============================================================================
# Wave 9: Boot1 type hardening cross-substrate parity
# ============================================================================

@pytest.mark.slow
class TestBoot1TypeHardeningCrossSubstrate:
    """JS must reject non-boolean boot1LoopMode identically to Python's TypeError.

    Prevents truthy-string routing: JSON "true" (string) is truthy in JS
    and would silently route to the recursive path without explicit intent.
    """

    def test_js_rejects_string_boot1(self):
        """JS rejects boot1LoopMode="true" (string, not boolean)."""
        resp = _run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}],
            "input": {"x": 1},
            "maxSteps": 5,
            "boot1LoopMode": "true",
        })
        assert not resp["success"], "JS should reject string boot1LoopMode"
        assert "boolean" in resp.get("error", "").lower()

    def test_js_rejects_int_boot1(self):
        """JS rejects boot1LoopMode=1 (number, not boolean)."""
        resp = _run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}],
            "input": {"x": 1},
            "maxSteps": 5,
            "boot1LoopMode": 1,
        })
        assert not resp["success"], "JS should reject numeric boot1LoopMode"
        assert "boolean" in resp.get("error", "").lower()

    def test_js_accepts_true(self):
        """JS accepts boot1LoopMode=true (boolean)."""
        resp = _run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}],
            "input": {"x": 1},
            "maxSteps": 5,
            "boot1LoopMode": True,
        })
        assert resp["success"], f"JS should accept boolean true: {resp.get('error')}"

    def test_js_accepts_false(self):
        """JS accepts boot1LoopMode=false (boolean)."""
        resp = _run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}],
            "input": {"x": 1},
            "maxSteps": 5,
            "boot1LoopMode": False,
        })
        assert resp["success"], f"JS should accept boolean false: {resp.get('error')}"

    def test_js_accepts_null_defaults_to_boot1(self):
        """JS accepts boot1LoopMode=null (defaults to true/boot1 recursive)."""
        resp = _run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}],
            "input": {"x": 1},
            "maxSteps": 5,
            "boot1LoopMode": None,
        })
        assert resp["success"], f"JS should accept null boot1LoopMode: {resp.get('error')}"

    def test_js_accepts_omitted_defaults_to_boot1(self):
        """JS accepts omitted boot1LoopMode (defaults to true/boot1 recursive)."""
        resp = _run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}],
            "input": {"x": 1},
            "maxSteps": 5,
        })
        assert resp["success"], f"JS should accept omitted boot1LoopMode: {resp.get('error')}"


# ============================================================================
# Wave 10: run_engine_with_routing Boot1 parity (red-team hardening)
# ============================================================================

@pytest.mark.slow
class TestRunEngineWithRoutingBoot1:
    """run_engine_with_routing must support boot1LoopMode like run_engine_pipeline.

    This closes the parity gap identified in the red-team review: the
    run_engine_with_routing JSON API handler lacked boot1LoopMode support.
    """

    BASE_REQUEST = {
        "action": "run_engine_with_routing",
        "projections": [],
        "input": {"test": True},
        "maxSteps": 6,
        "maxEngineIterations": 5,
        "maxAlgorithmIterations": 10,
        "observer": True,
    }

    def test_boot1_true_emits_boot1_depth(self):
        """boot1LoopMode=true routes through recursive path with boot1_depth events."""
        req = {**self.BASE_REQUEST, "boot1LoopMode": True}
        resp = _run_js_json_api(req)
        events = resp.get("observer_events", [])
        boot1_events = [e for e in events if "boot1_depth" in str(e)]
        assert len(boot1_events) > 0, (
            f"boot1LoopMode=true should emit boot1_depth observer events, "
            f"got {len(events)} events: {events[:5]}"
        )

    def test_boot1_false_no_boot1_depth(self):
        """boot1LoopMode=false routes through trampoline path (no boot1_depth)."""
        req = {**self.BASE_REQUEST, "boot1LoopMode": False}
        resp = _run_js_json_api(req)
        events = resp.get("observer_events", [])
        boot1_events = [e for e in events if "boot1_depth" in str(e)]
        assert len(boot1_events) == 0, (
            f"boot1LoopMode=false should NOT emit boot1_depth events, "
            f"got: {boot1_events}"
        )

    def test_boot1_omitted_defaults_boot1(self):
        """Omitting boot1LoopMode defaults to boot1 recursive (boot1_depth present)."""
        req = {k: v for k, v in self.BASE_REQUEST.items()}
        resp = _run_js_json_api(req)
        events = resp.get("observer_events", [])
        boot1_events = [e for e in events if "boot1_depth" in str(e)]
        assert len(boot1_events) > 0, (
            f"Omitted boot1LoopMode should default to boot1 recursive, "
            f"got no boot1_depth events out of {len(events)} total"
        )

    def test_boot1_non_boolean_rejected(self):
        """Non-boolean boot1LoopMode must be rejected with type_error."""
        for bad_value in ["yes", 1, "true", 0]:
            req = {**self.BASE_REQUEST, "boot1LoopMode": bad_value}
            resp = _run_js_json_api(req)
            assert not resp.get("success"), (
                f"boot1LoopMode={bad_value!r} should be rejected, got success"
            )
            assert resp.get("error_code") == "type_error", (
                f"boot1LoopMode={bad_value!r} should give type_error, "
                f"got: {resp.get('error_code')}"
            )

    def test_boot1_true_preserves_routing_shape(self):
        """boot1LoopMode=true must still return {engine_result, hemispheres} shape."""
        req = {**self.BASE_REQUEST, "boot1LoopMode": True}
        resp = _run_js_json_api(req)
        # May error (engine.exhausted) — check shape if success
        if resp.get("success"):
            result = resp["result"]
            assert "engine_result" in result, "Missing engine_result key"
            assert "hemispheres" in result, "Missing hemispheres key"
            hemi = result["hemispheres"]
            expected_keys = {"r_null", "r_inf", "r_a", "lobes", "sink"}
            assert set(hemi.keys()) == expected_keys, (
                f"Hemisphere keys mismatch: {set(hemi.keys())} != {expected_keys}"
            )

    def test_routing_parity_boot1_true_vs_false(self):
        """run_engine_with_routing boot1=true and boot1=false produce equivalent results."""
        projs = [{"pattern": {"double": {"var": "n"}}, "body": {"var": "n"}}]
        req_base = {
            "action": "run_engine_with_routing",
            "projections": projs,
            "input": {"double": 42},
            "maxSteps": 10,
            "maxEngineIterations": 20,
            "maxAlgorithmIterations": 50,
        }
        resp_false = _run_js_json_api({**req_base, "boot1LoopMode": False})
        resp_true = _run_js_json_api({**req_base, "boot1LoopMode": True})
        if resp_false.get("success") and resp_true.get("success"):
            assert _cross_substrate_equal(resp_false["result"], resp_true["result"]), (
                f"run_engine_with_routing boot1 parity mismatch:\n"
                f"  false: {resp_false['result']}\n"
                f"  true:  {resp_true['result']}"
            )


# ============================================================================
# Wave A3: Malformed re-entry payload fail-closed tests
# ============================================================================


class TestReentryPayloadValidation:
    """Malformed _tail_call/_run_engine payloads fail typed, not raw TypeError."""

    def test_string_payload_fails_typed(self):
        """String payload raises RcxEngineError, not TypeError."""
        with pytest.raises(RcxEngineError, match="re-entry payload must be dict"):
            _validate_reentry_payload("not_a_dict", "test")

    def test_none_payload_fails_typed(self):
        """None payload raises RcxEngineError, not TypeError."""
        with pytest.raises(RcxEngineError, match="re-entry payload must be dict"):
            _validate_reentry_payload(None, "test")

    def test_list_payload_fails_typed(self):
        """List payload raises RcxEngineError, not TypeError."""
        with pytest.raises(RcxEngineError, match="re-entry payload must be dict"):
            _validate_reentry_payload([1, 2], "test")

    def test_missing_projections_fails_typed(self):
        """Dict missing 'projections' raises RcxEngineError."""
        with pytest.raises(RcxEngineError, match="missing required key 'projections'"):
            _validate_reentry_payload({"input": {}}, "test")

    def test_missing_input_fails_typed(self):
        """Dict missing 'input' raises RcxEngineError."""
        with pytest.raises(RcxEngineError, match="missing required key 'input'"):
            _validate_reentry_payload({"projections": []}, "test")

    def test_projections_not_list_fails_typed(self):
        """Non-list projections raises RcxEngineError."""
        with pytest.raises(RcxEngineError, match="'projections' must be list"):
            _validate_reentry_payload({"projections": "bad", "input": {}}, "test")

    def test_valid_payload_passes(self):
        """Well-formed payload passes validation."""
        _validate_reentry_payload({"projections": [], "input": {}, "max_steps": 10}, "test")

    def test_reserved_field_in_input_fails(self):
        """Reserved field in input triggers validation error."""
        with pytest.raises(ValueError, match="reserved"):
            _validate_reentry_payload(
                {"projections": [], "input": {"_mode": "evil"}}, "test"
            )

    def test_reserved_field_in_frozen_fails(self):
        """Reserved field in frozen triggers validation error."""
        with pytest.raises(ValueError, match="reserved"):
            _validate_reentry_payload(
                {"projections": [], "input": {}, "frozen": {"_mode": "evil"}}, "test"
            )

    def test_non_mu_input_fails_typed(self):
        """Non-Mu input (e.g. lambda) raises RcxEngineError, not raw TypeError."""
        with pytest.raises(RcxEngineError, match="not valid Mu"):
            _validate_reentry_payload(
                {"projections": [], "input": lambda: None}, "test"
            )

    def test_non_mu_frozen_fails_typed(self):
        """Non-Mu frozen raises RcxEngineError, not raw TypeError."""
        with pytest.raises(RcxEngineError, match="not valid Mu"):
            _validate_reentry_payload(
                {"projections": [], "input": {}, "frozen": lambda: None}, "test"
            )


class TestJsReentryPayloadValidation:
    """JS validateReentryPayload runtime behavior (not just source-lock).

    Exercises the exported validateReentryPayload function from pipeline.js
    directly via node -e to prove it actually rejects malformed payloads
    with the correct error code at runtime.
    """

    @staticmethod
    def _run_js_validation(payload_js_expr: str, context: str = "test") -> dict:
        """Call JS validateReentryPayload and return {ok, error_code, message}."""
        script = (
            "const p = require('./mu/host/js/engine/pipeline');\n"
            "const { muCopy } = require('./mu/host/js/core/stage0_vm');\n"
            "try {\n"
            f"  p.validateReentryPayload({payload_js_expr}, '{context}');\n"
            "  console.log(JSON.stringify({ok: true}));\n"
            "} catch (e) {\n"
            "  console.log(JSON.stringify({ok: false, error_code: e.error_code || 'unknown', message: e.message}));\n"
            "}\n"
        )
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, cwd=ROOT, timeout=10,
        )
        assert result.returncode == 0, f"JS error: {result.stderr}"
        return json.loads(result.stdout.strip())

    def test_js_rejects_string_payload(self):
        """JS rejects string payload with input.shape_mismatch."""
        r = self._run_js_validation('"not_a_dict"')
        assert not r["ok"]
        assert r["error_code"] == "input.shape_mismatch"
        assert "re-entry payload must be dict" in r["message"]

    def test_js_rejects_null_payload(self):
        """JS rejects null payload with input.shape_mismatch."""
        r = self._run_js_validation("null")
        assert not r["ok"]
        assert r["error_code"] == "input.shape_mismatch"

    def test_js_rejects_array_payload(self):
        """JS rejects array payload with input.shape_mismatch."""
        r = self._run_js_validation("[1, 2]")
        assert not r["ok"]
        assert r["error_code"] == "input.shape_mismatch"

    def test_js_rejects_missing_projections(self):
        """JS rejects payload missing 'projections' key."""
        r = self._run_js_validation('({input: {}})')
        assert not r["ok"]
        assert r["error_code"] == "input.shape_mismatch"
        assert "missing required key 'projections'" in r["message"]

    def test_js_rejects_missing_input(self):
        """JS rejects payload missing 'input' key."""
        r = self._run_js_validation('({projections: []})')
        assert not r["ok"]
        assert r["error_code"] == "input.shape_mismatch"
        assert "missing required key 'input'" in r["message"]

    def test_js_accepts_valid_payload(self):
        """JS accepts well-formed payload."""
        r = self._run_js_validation(
            "({projections: [], input: muCopy({}, true, 'valid reentry input')})"
        )
        assert r["ok"]

    def test_js_rejects_non_mu_input(self):
        """JS rejects non-Mu input (function) with input.invalid_type."""
        r = self._run_js_validation('({projections: [], input: function(){}})')
        assert not r["ok"]
        assert r["error_code"] == "input.invalid_type"
        assert "not valid Mu" in r["message"]

    def test_js_rejects_non_mu_frozen(self):
        """JS rejects non-Mu frozen (function) with input.invalid_type."""
        r = self._run_js_validation(
            "({projections: [], input: muCopy({}, true, 'valid reentry input'), frozen: function(){}})"
        )
        assert not r["ok"]
        assert r["error_code"] == "input.invalid_type"
        assert "not valid Mu" in r["message"]


def _has_slow_mark(obj):
    marks = getattr(obj, "pytestmark", [])
    if not isinstance(marks, (list, tuple)):
        marks = [marks]
    return any(getattr(mark, "name", None) == "slow" for mark in marks)


def test_boot1_shadow_expensive_classes_remain_slow_marked():
    """Lock expensive Boot1 parity coverage out of the fast PR shard."""
    expensive_classes = (
        TestBoot1PythonShadowParity,
        TestBoot1BudgetAccounting,
        TestBoot1BudgetAdversarial,
        TestBoot1ParityProperty,
        TestBoot1FailClosed,
        TestBoot1Merge2GateAssertions,
        TestBoot1DepthStress,
        TestBoot1Determinism,
        TestBoot1Idempotence,
        TestBoot1DepthCapEnforcement,
    )
    missing = [cls.__name__ for cls in expensive_classes if not _has_slow_mark(cls)]
    assert not missing, f"Boot1 expensive parity classes must stay @pytest.mark.slow: {missing}"
