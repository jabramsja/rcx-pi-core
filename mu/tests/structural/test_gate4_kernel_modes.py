"""
Gate 4 prep: kernel mode + algorithm-runtime validation behavior.

These tests lock the opt-in infrastructure needed for structural algorithm
execution without changing production defaults.
"""

from __future__ import annotations

import pytest

from rcx_pi.selfhost.step_mu import (
    ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS,
    step_kernel_mu,
    validate_algorithm_runtime_fields,
)


def test_step_kernel_mu_bridge_mode_selects_bridge_loader(monkeypatch):
    calls = {"core": 0, "bridge": 0}

    def fake_core():
        calls["core"] += 1
        return []

    def fake_bridge():
        calls["bridge"] += 1
        return []

    monkeypatch.setattr("rcx_pi.selfhost.step_mu._load_combined_kernel_projections_shared", fake_core)  # ANTICHEAT_OK: kernel mode test
    monkeypatch.setattr(
        "rcx_pi.selfhost.step_mu._load_combined_kernel_with_bridge_projections_shared", fake_bridge  # ANTICHEAT_OK: kernel mode test
    )

    result = step_kernel_mu([], {"ok": True}, kernel_mode="bridge")

    assert result == {"ok": True}
    assert calls["bridge"] == 1
    assert calls["core"] == 0


def test_step_kernel_mu_core_mode_selects_core_loader(monkeypatch):
    calls = {"core": 0, "bridge": 0}

    def fake_core():
        calls["core"] += 1
        return []

    def fake_bridge():
        calls["bridge"] += 1
        return []

    monkeypatch.setattr("rcx_pi.selfhost.step_mu._load_combined_kernel_projections_shared", fake_core)  # ANTICHEAT_OK: kernel mode test
    monkeypatch.setattr(
        "rcx_pi.selfhost.step_mu._load_combined_kernel_with_bridge_projections_shared", fake_bridge  # ANTICHEAT_OK: kernel mode test
    )

    result = step_kernel_mu([], {"ok": True}, kernel_mode="core")

    assert result == {"ok": True}
    assert calls["core"] == 1
    assert calls["bridge"] == 0


def test_step_kernel_mu_invalid_kernel_mode_fails():
    with pytest.raises(ValueError, match="invalid kernel_mode"):
        step_kernel_mu([], {"ok": True}, kernel_mode="invalid")


def test_step_kernel_mu_invalid_validation_mode_fails():
    with pytest.raises(ValueError, match="invalid validation_mode"):
        step_kernel_mu([], {"ok": True}, validation_mode="invalid")


def test_algorithm_runtime_allows_top_level_algorithm_fields(monkeypatch):
    monkeypatch.setattr("rcx_pi.selfhost.step_mu._load_combined_kernel_projections_shared", lambda: [])  # ANTICHEAT_OK: kernel mode test
    value = {"_mode": "recurrence", "_phase": "scan", "_state": "A", "_step": 2}

    result = step_kernel_mu([], value, validation_mode="algorithm_runtime")
    assert result == value


def test_domain_mode_rejects_top_level_reserved_algorithm_fields(monkeypatch):
    monkeypatch.setattr("rcx_pi.selfhost.step_mu._load_combined_kernel_projections_shared", lambda: [])  # ANTICHEAT_OK: kernel mode test
    value = {"_mode": "recurrence", "_phase": "scan"}

    with pytest.raises(ValueError, match="kernel-reserved field"):
        step_kernel_mu([], value, validation_mode="domain")


def test_algorithm_runtime_rejects_unknown_underscore_in_normalized_pairs():
    # Normalized dict encoding with key stored as value in kv-pair head.
    malicious = {
        "_type": "dict",
        "head": {"head": "_evil", "tail": {"head": 1, "tail": None}},
        "tail": None,
    }

    with pytest.raises(ValueError, match="unsupported algorithm underscore field"):
        validate_algorithm_runtime_fields(malicious, "test")


def test_algorithm_runtime_allowlist_includes_known_algorithm_fields():
    expected = {
        "_detect_closure",
        "_detect_exhaustion",
        "_mode",
        "_phase",
        "_current",
        "_check_list",
        "_seen",
        "_step",
        "_result",
        "_frozen",
        "_operator_ids",
        "_tau_step",
        "_state",
        "_trace",
        "_type",
    }
    assert expected.issubset(ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS)
