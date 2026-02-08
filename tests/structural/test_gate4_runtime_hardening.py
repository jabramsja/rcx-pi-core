"""
Gate 4 runtime hardening tests.

These tests lock adversary-facing boundary checks for runtime helpers used
outside the main kernel loop.
"""

from __future__ import annotations

import pytest

from rcx_pi.selfhost.step_mu import (
    apply_mu,
    run_algorithm_meta_circular,
    run_mu,
    run_mu_structural,
    step_kernel_mu,
    step_algorithm_with_bridge,
)
from rcx_pi.selfhost.match_mu import match_mu
from rcx_pi.selfhost.kernel import get_step_budget, reset_step_budget


def test_apply_mu_rejects_reserved_input_field():
    projection = {"pattern": {"var": "x"}, "body": {"ok": {"var": "x"}}}
    with pytest.raises(ValueError, match="kernel-reserved field"):
        apply_mu(projection, {"_mode": "forged"})


def test_apply_mu_rejects_reserved_projection_pattern():
    projection = {"pattern": {"_mode": "forged"}, "body": {"ok": True}}
    with pytest.raises(ValueError, match="kernel-reserved field"):
        apply_mu(projection, {"ok": True})


def test_apply_mu_rejects_reserved_output_after_substitution(monkeypatch):
    projection = {"pattern": {"var": "x"}, "body": {"ok": {"var": "x"}}}
    monkeypatch.setattr("rcx_pi.selfhost.step_mu.match_mu", lambda *_args, **_kwargs: {"x": 1})
    monkeypatch.setattr(
        "rcx_pi.selfhost.step_mu.subst_mu", lambda *_args, **_kwargs: {"_mode": "forged"}
    )

    with pytest.raises(ValueError, match="kernel-reserved field"):
        apply_mu(projection, {"ok": True})


def test_step_algorithm_with_bridge_rejects_kernel_projection_ids():
    projections = [
        {"id": "kernel.wrap", "pattern": {"_mode": "x"}, "body": {"_mode": "y"}},
    ]
    state = {"_detect_closure": {"_mode": "checking", "_phase": "init"}}

    with pytest.raises(ValueError, match="expects algorithm/domain projections only"):
        step_algorithm_with_bridge(projections, state)


def test_step_algorithm_with_bridge_rejects_unknown_underscore_input():
    with pytest.raises(ValueError, match="unsupported algorithm underscore field"):
        step_algorithm_with_bridge([], {"_evil": 1})


def test_run_mu_structural_rejects_reserved_initial_input():
    with pytest.raises(ValueError, match="kernel-reserved field"):
        run_mu_structural([], {"_mode": "forged"}, max_steps=1)


def test_run_mu_rejects_reserved_initial_input():
    with pytest.raises(ValueError, match="kernel-reserved field"):
        run_mu([], {"_mode": "forged"}, max_steps=1)


def test_run_mu_structural_activates_global_budget_when_inactive(monkeypatch):
    class DummyBudget:
        def __init__(self):
            self.active = False
            self.started = 0
            self.stopped = 0
            self.consumed = 0
            self.limit = 50000

        def is_active(self):
            return self.active

        def start(self, limit=None):
            self.active = True
            self.started += 1

        def stop(self):
            self.active = False
            self.stopped += 1

        def consume(self, steps):
            self.consumed += steps

        def get_total(self):
            return self.consumed

        def get_remaining(self):
            return max(0, self.limit - self.consumed)

    budget = DummyBudget()
    monkeypatch.setattr("rcx_pi.selfhost.step_mu.get_step_budget", lambda: budget)

    result = run_mu_structural([], {"ok": True}, max_steps=1)
    assert result["stall"] is True
    assert budget.started >= 1
    assert budget.stopped >= 1
    assert budget.consumed >= 1


def test_step_kernel_mu_activates_global_budget_when_inactive(monkeypatch):
    class DummyBudget:
        def __init__(self):
            self.active = False
            self.started = 0
            self.stopped = 0
            self.consumed = 0

        def is_active(self):
            return self.active

        def start(self, limit=None):
            self.active = True
            self.started += 1

        def stop(self):
            self.active = False
            self.stopped += 1

        def consume(self, steps):
            self.consumed += steps

    budget = DummyBudget()
    monkeypatch.setattr("rcx_pi.selfhost.step_mu.get_step_budget", lambda: budget)

    result = step_kernel_mu([], {"ok": True})
    assert result == {"ok": True}
    assert budget.started == 1
    assert budget.stopped == 1
    assert budget.consumed >= 1


def test_run_mu_structural_projection_id_probe_is_budget_neutral():
    projections = [
        {
            "id": "p.double",
            "pattern": {"op": "double", "v": {"var": "x"}},
            "body": {"op": "done", "v": {"var": "x"}},
        }
    ]
    value = {"op": "double", "v": 7}

    # Baseline: one bridge kernel step cost
    reset_step_budget()
    budget = get_step_budget()
    budget.start(limit=5000)
    try:
        baseline_before = budget.get_total()
        step_kernel_mu(
            projections,
            value,
            kernel_mode="bridge",
            validation_mode="domain",
        )
        baseline_delta = budget.get_total() - baseline_before
    finally:
        budget.stop()

    # Trace path should consume the same budget for one iteration.
    reset_step_budget()
    budget = get_step_budget()
    budget.start(limit=5000)
    try:
        trace_before = budget.get_total()
        run_mu_structural(projections, value, max_steps=1)
        trace_delta = budget.get_total() - trace_before
    finally:
        budget.stop()

    assert trace_delta == baseline_delta


def test_step_kernel_mu_return_meta_stall_true_on_no_match():
    meta = step_kernel_mu([], {"ok": True}, return_meta=True)
    assert isinstance(meta, dict)
    assert meta["stall"] is True
    assert meta["output"] == {"ok": True}


def test_step_kernel_mu_return_meta_stall_false_on_match():
    projections = [
        {
            "id": "p.match",
            "pattern": {"x": {"var": "v"}},
            "body": {"ok": {"var": "v"}},
        }
    ]
    meta = step_kernel_mu(projections, {"x": 1}, return_meta=True)
    assert isinstance(meta, dict)
    assert meta["stall"] is False
    assert meta["output"] == {"ok": 1}


def test_match_mu_allows_shared_substructures_without_false_cycle():
    # Shared (aliased) sub-structures are not cycles and should not be rejected.
    shared_var = {"var": "v"}
    pattern = {"0": shared_var, "00": shared_var}
    value = {"0": 1, "00": 1}
    result = match_mu(pattern, value)
    assert isinstance(result, dict)
    assert result.get("v") == 1


def test_run_algorithm_meta_circular_defaults_to_structural_kernel(monkeypatch):
    seen = {}

    def fake_step_kernel_mu(projections, input_value, **kwargs):
        seen["kwargs"] = kwargs
        return {"mode": "structural", "input": input_value}

    def fail_bootstrap(*_args, **_kwargs):
        raise AssertionError("bootstrap fallback should not run in default mode")

    monkeypatch.setattr("rcx_pi.selfhost.step_mu.step_kernel_mu", fake_step_kernel_mu)
    monkeypatch.setattr("rcx_pi.selfhost.step_mu.step_algorithm_with_bridge", fail_bootstrap)

    result = run_algorithm_meta_circular([], {"_detect_closure": {"trace": None, "result": "x"}})
    assert result["mode"] == "structural"
    assert seen["kwargs"]["kernel_mode"] == "bridge"
    assert seen["kwargs"]["validation_mode"] == "algorithm_runtime"


def test_run_algorithm_meta_circular_bootstrap_fallback_is_explicit(monkeypatch):
    monkeypatch.setattr(
        "rcx_pi.selfhost.step_mu.step_algorithm_with_bridge",
        lambda *_args, **_kwargs: {"mode": "bootstrap"}
    )
    monkeypatch.setattr(
        "rcx_pi.selfhost.step_mu.step_kernel_mu",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("kernel path should not run"))
    )

    result = run_algorithm_meta_circular(
        [],
        {"_detect_closure": {"trace": None, "result": "x"}},
        execution_mode="bootstrap",
        allow_bootstrap_fallback=True,
    )
    assert result["mode"] == "bootstrap"


def test_run_algorithm_meta_circular_bootstrap_requires_explicit_opt_in():
    with pytest.raises(ValueError, match="bootstrap fallback is disabled by default"):
        run_algorithm_meta_circular(
            [],
            {"_detect_closure": {"trace": None, "result": "x"}},
            execution_mode="bootstrap",
        )


def test_run_algorithm_meta_circular_rejects_unknown_mode():
    with pytest.raises(ValueError, match="invalid execution_mode"):
        run_algorithm_meta_circular([], {"ok": True}, execution_mode="unknown")
