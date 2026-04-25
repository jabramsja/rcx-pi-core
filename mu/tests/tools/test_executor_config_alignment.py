"""Enforcement test: executor config alignment.

Verifies that DEFAULT_EXECUTOR_CONFIG, executor_config.json, dispatch
fallback callsites, and commit_executor config bindings stay in sync.
Catches regressions of Mechanisms A (dispatch hardcodes), B (stale code
default), and the commit-executor config-binding invariant.

See: reports/control_plane/post_commit_roundtrip_2026-04-04.md
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

EXECUTORS_DIR = REPO_ROOT / "mu" / "tools" / "executors"
CONFIG_JSON_PATH = EXECUTORS_DIR / "executor_config.json"
COMMON_PY_PATH = EXECUTORS_DIR / "executor_common.py"
DISPATCH_PY_PATH = EXECUTORS_DIR / "executor_dispatch.py"
COMMIT_PY_PATH = EXECUTORS_DIR / "commit_executor.py"


def _load_default_executor_config() -> dict:
    """Extract DEFAULT_EXECUTOR_CONFIG by AST parse of executor_common.py."""
    tree = ast.parse(COMMON_PY_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        name = None
        value = None
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "DEFAULT_EXECUTOR_CONFIG":
                    name = target.id
                    value = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "DEFAULT_EXECUTOR_CONFIG":
                name = node.target.id
                value = node.value
        if name and value:
            compiled = compile(ast.Expression(body=value), "<ast>", "eval")
            return eval(compiled)  # noqa: S307 — literal dict only
    raise AssertionError("DEFAULT_EXECUTOR_CONFIG not found in executor_common.py")


def _load_default_executor_config_timeouts() -> dict[str, int]:
    """Extract DEFAULT_EXECUTOR_CONFIG["timeouts"] by AST parse of executor_common.py."""
    return _load_default_executor_config()["timeouts"]


def _load_json_config_timeouts() -> dict[str, int]:
    return json.loads(CONFIG_JSON_PATH.read_text(encoding="utf-8"))["timeouts"]


def _load_default_executor_config_backends() -> dict[str, str | None]:
    return _load_default_executor_config()["backends"]


def _load_json_config_backends() -> dict[str, str | None]:
    return json.loads(CONFIG_JSON_PATH.read_text(encoding="utf-8"))["backends"]


def _load_default_executor_config_role_agents() -> dict[str, str]:
    return _load_default_executor_config()["role_agents"]


def _load_json_config_role_agents() -> dict[str, str]:
    return json.loads(CONFIG_JSON_PATH.read_text(encoding="utf-8"))["role_agents"]


def _load_default_executor_config_bridge_agent_defaults() -> dict[str, dict[str, str]]:
    return _load_default_executor_config()["bridge_agent_defaults"]


def _load_json_config_bridge_agent_defaults() -> dict[str, dict[str, str]]:
    return json.loads(CONFIG_JSON_PATH.read_text(encoding="utf-8"))["bridge_agent_defaults"]


class TestExecutorConfigJsonValid:
    def test_config_json_exists_and_valid(self):
        assert CONFIG_JSON_PATH.exists(), "executor_config.json missing"
        data = json.loads(CONFIG_JSON_PATH.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert "timeouts" in data


class TestDefaultMatchesLiveConfig:
    """DEFAULT_EXECUTOR_CONFIG can never silently shrink below live config."""

    def test_every_default_lte_live(self):
        defaults = _load_default_executor_config_timeouts()
        live = _load_json_config_timeouts()
        for key, default_val in defaults.items():
            if key not in live:
                continue  # orphan-key test handles this separately
            assert default_val <= live[key], (
                f"DEFAULT_EXECUTOR_CONFIG['timeouts']['{key}'] = {default_val} "
                f"exceeds live config value {live[key]} — silent budget shrink"
            )

    def test_no_orphan_keys_in_live(self):
        """Every key in executor_config.json must have a fallback in DEFAULT."""
        defaults = _load_default_executor_config_timeouts()
        live = _load_json_config_timeouts()
        orphans = set(live.keys()) - set(defaults.keys())
        assert not orphans, (
            f"executor_config.json has timeout keys without DEFAULT fallbacks: {orphans}"
        )

    def test_no_orphan_keys_in_default(self):
        """Every key in DEFAULT must exist in executor_config.json."""
        defaults = _load_default_executor_config_timeouts()
        live = _load_json_config_timeouts()
        orphans = set(defaults.keys()) - set(live.keys())
        assert not orphans, (
            f"DEFAULT_EXECUTOR_CONFIG has timeout keys missing from executor_config.json: {orphans}"
        )


class TestDispatchFallbacksReferenceDefault:
    """All dispatch .get("timeouts", ...) fallbacks must reference
    DEFAULT_EXECUTOR_CONFIG, not hardcoded numeric literals."""

    def test_no_hardcoded_timeout_fallbacks(self):
        source = DISPATCH_PY_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        violations = []
        for node in ast.walk(tree):
            # Pattern: .get("timeouts", {}).get(name, LITERAL_INT)
            if not isinstance(node, ast.Call):
                continue
            if not (isinstance(node.func, ast.Attribute) and node.func.attr == "get"):
                continue
            # Check if this is a .get() on a .get("timeouts", ...) result
            if not isinstance(node.func.value, ast.Call):
                continue
            inner = node.func.value
            if not (isinstance(inner.func, ast.Attribute) and inner.func.attr == "get"):
                continue
            # Verify inner call has "timeouts" as first arg
            if not (inner.args and isinstance(inner.args[0], ast.Constant)
                    and inner.args[0].value == "timeouts"):
                continue
            # Now check the outer .get() fallback (2nd arg or default kwarg)
            fallback = None
            if len(node.args) >= 2:
                fallback = node.args[1]
            else:
                for kw in node.keywords:
                    if kw.arg == "default":
                        fallback = kw.value
                        break
            if fallback is None:
                continue
            # A bare int/float literal here means a hardcoded fallback
            if isinstance(fallback, ast.Constant) and isinstance(fallback.value, (int, float)):
                violations.append(
                    f"Line {node.lineno}: hardcoded fallback {fallback.value} "
                    f"in .get('timeouts', ...).get(..., {fallback.value})"
                )
        assert not violations, (
            "executor_dispatch.py has hardcoded timeout fallbacks that should "
            "reference DEFAULT_EXECUTOR_CONFIG:\n" + "\n".join(violations)
        )


class TestCommitExecutorConfigBinding:
    """commit_executor.py must derive PRE_PUSH_FAST_TIMEOUT_S and
    BOT_REMEDIATION_TIMEOUT_S and BOT_REMEDIATION_ADAPTER from config lookups,
    not hardcoded literals."""

    def _find_constant_assignment(self, tree: ast.Module, name: str) -> ast.AST | None:
        """Find the top-level assignment to *name* and return its value node."""
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == name:
                        return node.value
        return None

    def _assert_config_derived(self, const_name: str):
        source = COMMIT_PY_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        value_node = self._find_constant_assignment(tree, const_name)
        assert value_node is not None, (
            f"{const_name} assignment not found at module level in commit_executor.py"
        )
        # The value must NOT be a bare int literal — it must reference a config dict access
        assert not (isinstance(value_node, ast.Constant) and isinstance(value_node.value, int)), (
            f"{const_name} is assigned a bare integer literal ({value_node.value}) "
            f"in commit_executor.py — it must be derived from config"
        )

    def test_pre_push_fast_timeout_from_config(self):
        self._assert_config_derived("PRE_PUSH_FAST_TIMEOUT_S")

    def test_bot_remediation_timeout_from_config(self):
        self._assert_config_derived("BOT_REMEDIATION_TIMEOUT_S")

    def test_bot_remediation_adapter_from_config(self):
        source = COMMIT_PY_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        value_node = self._find_constant_assignment(tree, "BOT_REMEDIATION_ADAPTER")
        assert value_node is not None, (
            "BOT_REMEDIATION_ADAPTER assignment not found at module level "
            "in commit_executor.py"
        )
        assert not (
            isinstance(value_node, ast.Constant) and isinstance(value_node.value, str)
        ), (
            "BOT_REMEDIATION_ADAPTER is hardcoded in commit_executor.py — "
            "it must be derived from executor config"
        )

    def test_imports_load_executor_config(self):
        """commit_executor.py must import load_executor_config."""
        source = COMMIT_PY_PATH.read_text(encoding="utf-8")
        assert "load_executor_config" in source, (
            "commit_executor.py does not import load_executor_config"
        )


class TestBackendConfigAlignment:
    def test_bot_remediation_backend_present_in_default_and_live_config(self):
        defaults = _load_default_executor_config_backends()
        live = _load_json_config_backends()
        assert defaults.get("bot_remediation") == "codex"
        assert live.get("bot_remediation") == "codex"


class TestRoleAgentConfigAlignment:
    def test_role_agents_present_in_default_and_live_config(self):
        defaults = _load_default_executor_config_role_agents()
        live = _load_json_config_role_agents()
        assert defaults == {"implementer": "codex", "reviewer": "codex"}
        assert live == {"implementer": "codex", "reviewer": "codex"}

    def test_role_agent_keys_match_between_default_and_live_config(self):
        defaults = _load_default_executor_config_role_agents()
        live = _load_json_config_role_agents()
        assert set(defaults) == set(live) == {"implementer", "reviewer"}


class TestBridgeAgentDefaultConfigAlignment:
    def test_bridge_agent_defaults_match_between_default_and_live_config(self):
        defaults = _load_default_executor_config_bridge_agent_defaults()
        live = _load_json_config_bridge_agent_defaults()
        assert defaults == live

    def test_bridge_agent_defaults_define_provider_model_and_effort_switches(self):
        defaults = _load_json_config_bridge_agent_defaults()
        assert defaults["claude"] == {
            "display_name": "Claude Opus 4.7 max",
            "model": "claude-opus-4-7",
            "effort": "max",
        }
        assert defaults["codex"] == {
            "display_name": "Codex 5.5 xhigh",
            "model": "gpt-5.5",
            "reasoning_effort": "xhigh",
        }
