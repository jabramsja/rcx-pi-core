"""Repo-root pytest fixtures shared across mirrored test trees."""

from __future__ import annotations

import gc
from types import ModuleType
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_routing_record():
    """Fallback routing-record fixture for mirrored dispatcher suites.

    The commit gate can run both ``mu/tests/.../test_executor_dispatch.py`` and
    ``tests/.../test_executor_dispatch.py`` in one pytest invocation. A repo-root
    fixture keeps the shared ``mock_routing_record`` stub available even when
    pytest's mirrored collection path does not honor the per-module fixture
    definition on one of those duplicate-basename files.
    """
    repo_root = Path(__file__).resolve().parent
    phase_b_path = repo_root / "mu" / "tools" / "executors" / "phase_b_executor.py"
    targets: list[ModuleType] = []

    for obj in gc.get_objects():
        if not isinstance(obj, ModuleType):
            continue
        if getattr(obj, "__file__", None) != str(phase_b_path):
            continue
        if hasattr(obj, "load_routing_record"):
            targets.append(obj)

    if not targets:
        from mu.tests.tools.module_loader import load_module

        targets.append(load_module("phase_b_executor", phase_b_path))

    patchers = [
        patch.object(
            mod,
            "load_routing_record",
            return_value={"decision": "ROUTE_PHASE_B", "summary": "test dispatch"},
        )
        for mod in targets
    ]
    for patcher in patchers:
        patcher.start()
    try:
        yield
    finally:
        for patcher in reversed(patchers):
            patcher.stop()
