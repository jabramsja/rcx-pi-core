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
    run_mu_structural,
    step_algorithm_with_bridge,
)
from rcx_pi.selfhost.match_mu import match_mu


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


def test_run_mu_structural_activates_global_budget_when_inactive(monkeypatch):
    class DummyBudget:
        def __init__(self):
            self.active = False
            self.started = 0
            self.stopped = 0

        def is_active(self):
            return self.active

        def start(self, limit=None):
            self.active = True
            self.started += 1

        def stop(self):
            self.active = False
            self.stopped += 1

    budget = DummyBudget()
    monkeypatch.setattr("rcx_pi.selfhost.step_mu.get_step_budget", lambda: budget)

    result = run_mu_structural([], {"ok": True}, max_steps=1)
    assert result["stall"] is True
    assert budget.started == 1
    assert budget.stopped == 1


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
        [], {"_detect_closure": {"trace": None, "result": "x"}}, execution_mode="bootstrap"
    )
    assert result["mode"] == "bootstrap"


def test_run_algorithm_meta_circular_rejects_unknown_mode():
    with pytest.raises(ValueError, match="invalid execution_mode"):
        run_algorithm_meta_circular([], {"ok": True}, execution_mode="unknown")
