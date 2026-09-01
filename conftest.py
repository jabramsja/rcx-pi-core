"""Repo-root pytest fixtures shared across mirrored test trees."""

from __future__ import annotations

import gc
import os
import tempfile
from collections.abc import MutableMapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest


_PROVIDER_ENV_BY_BASENAME = {
    "claude": (
        "RCX_PIPELINE_AGENT_PAGER_CLAUDE_BIN",
        "RCX_CLAUDE_AUTOPING_CLAUDE_BIN",
    ),
    "codex": ("RCX_PIPELINE_AGENT_PAGER_CODEX_BIN",),
}
_PROVIDER_ISOLATION_ENV_KEYS = (
    "PATH",
    "NODE_OPTIONS",
    *(
        name
        for names in _PROVIDER_ENV_BY_BASENAME.values()
        for name in names
    ),
)
_PROVIDER_ISOLATION_STATE_ATTR = "_rcx_provider_isolation_state"
_PROVIDER_STUB_EXIT_CODE = 86
_PROVIDER_STUB_MARKER = "RCX_TEST_PROVIDER_ISOLATION_CLI_BLOCKED"
_WEBSOCKET_GUARD_MARKER = "RCX_TEST_PROVIDER_ISOLATION_WEBSOCKET_BLOCKED"

_PROVIDER_STUB_SOURCE = f"""#!/bin/sh
printf '%s:%s\\n' '{_PROVIDER_STUB_MARKER}' "${{0##*/}}" >&2
exit {_PROVIDER_STUB_EXIT_CODE}
"""

_WEBSOCKET_GUARD_SOURCE = f"""'use strict';

const MARKER = '{_WEBSOCKET_GUARD_MARKER}';

class PytestProviderIsolationWebSocket {{
  constructor() {{
    process.stdout.write(JSON.stringify({{ error: MARKER }}));
    const error = new Error(MARKER);
    error.code = MARKER;
    throw error;
  }}
}}

Object.defineProperty(globalThis, 'WebSocket', {{
  value: PytestProviderIsolationWebSocket,
  writable: true,
  configurable: true,
}});
"""


@dataclass
class _ProviderIsolationState:
    environment: MutableMapping[str, str]
    environment_before: dict[str, tuple[bool, str]]
    guard_dir: Path
    stub_dir: Path
    websocket_guard: Path
    restored: bool = False


def _snapshot_provider_environment(
    environment: MutableMapping[str, str],
) -> dict[str, tuple[bool, str]]:
    """Capture unset versus empty versus populated values exactly."""
    return {
        key: (key in environment, environment.get(key, ""))
        for key in _PROVIDER_ISOLATION_ENV_KEYS
    }


def _write_provider_stub(path: Path) -> None:
    path.write_text(_PROVIDER_STUB_SOURCE, encoding="utf-8")
    path.chmod(0o700)


def _install_provider_isolation(
    environment: MutableMapping[str, str] | None = None,
    *,
    temporary_parent: str | Path | None = None,
) -> _ProviderIsolationState:
    """Install process-private provider guards without cleanup ownership.

    Guard files intentionally outlive pytest teardown. A detached descendant can
    inherit their absolute paths and begin provider work only after the owning
    pytest process has restored its own environment.
    """
    target = os.environ if environment is None else environment
    environment_before = _snapshot_provider_environment(target)
    guard_dir = Path(
        tempfile.mkdtemp(
            prefix=f"rcx-pytest-provider-isolation-{os.getpid()}-",
            dir=None if temporary_parent is None else str(temporary_parent),
        )
    )
    guard_dir.chmod(0o700)
    stub_dir = guard_dir / "bin"
    stub_dir.mkdir(mode=0o700)

    for basename in _PROVIDER_ENV_BY_BASENAME:
        _write_provider_stub(stub_dir / basename)

    websocket_guard = guard_dir / "provider_websocket_guard.cjs"
    websocket_guard.write_text(_WEBSOCKET_GUARD_SOURCE, encoding="utf-8")
    websocket_guard.chmod(0o600)

    inherited_path = target.get("PATH", "")
    target["PATH"] = (
        f"{stub_dir}{os.pathsep}{inherited_path}"
        if inherited_path
        else str(stub_dir)
    )
    for basename, variable_names in _PROVIDER_ENV_BY_BASENAME.items():
        # Override inherited absolute binaries without changing provider argv
        # shape; the private first PATH entry resolves each safe basename.
        for variable_name in variable_names:
            target[variable_name] = basename

    require_option = f"--require={websocket_guard}"
    inherited_node_options = target.get("NODE_OPTIONS", "")
    target["NODE_OPTIONS"] = (
        f"{inherited_node_options} {require_option}"
        if inherited_node_options
        else require_option
    )

    return _ProviderIsolationState(
        environment=target,
        environment_before=environment_before,
        guard_dir=guard_dir,
        stub_dir=stub_dir,
        websocket_guard=websocket_guard,
    )


def _restore_provider_isolation(state: _ProviderIsolationState) -> None:
    """Restore only the owning mapping's exact inherited environment."""
    if state.restored:
        return
    for key, (was_present, value) in state.environment_before.items():
        if was_present:
            state.environment[key] = value
        else:
            state.environment.pop(key, None)
    state.restored = True


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """Guard provider processes before collection in controllers and workers."""
    if getattr(config, _PROVIDER_ISOLATION_STATE_ATTR, None) is None:
        setattr(
            config,
            _PROVIDER_ISOLATION_STATE_ATTR,
            _install_provider_isolation(),
        )


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    """Restore the owner exactly while retaining descendant guard files."""
    state = getattr(config, _PROVIDER_ISOLATION_STATE_ATTR, None)
    if state is not None:
        _restore_provider_isolation(state)


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
