"""Enforcement test: executor config alignment.

Verifies that DEFAULT_EXECUTOR_CONFIG, executor_config.json, dispatch
fallback callsites, and commit_executor config bindings stay in sync.
Catches regressions of Mechanisms A (dispatch hardcodes), B (stale code
default), and the commit-executor config-binding invariant.

See: reports/control_plane/post_commit_roundtrip_2026-04-04.md
"""

from __future__ import annotations

import ast
import copy
import json
import re
import sys
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

# executor_common owns the single derivation rule role_agents -> backends/
# bridge_reviewers (apply_role_agents). Import it the same way set_roles.py and
# the observability panes do, so the LIVE-internal consistency check re-derives
# through the canonical rule instead of duplicating the role->key mapping here.
sys.path.insert(0, str(REPO_ROOT / "mu" / "tools" / "executors"))
from executor_common import (  # noqa: E402  (path insert must precede import)
    IMPLEMENTER_BACKEND_KEYS,
    REVIEW_OVERRIDE_BACKEND_KEYS,
    REVIEWER_BRIDGE_KEYS,
    apply_role_agents,
    merge_executor_config_overrides,
)
import executor_dispatch as dispatch  # noqa: E402  (path insert must precede import)

ROLE_AGENT_KEYS = {"implementer", "reviewer"}
REQUIRED_BRIDGE_AGENT_DEFAULT_KEYS = {
    "claude": {"display_name", "model", "effort"},
    "codex": {"display_name", "model", "reasoning_effort"},
}

EXECUTORS_DIR = REPO_ROOT / "mu" / "tools" / "executors"
CONFIG_JSON_PATH = EXECUTORS_DIR / "executor_config.json"
COMMON_PY_PATH = EXECUTORS_DIR / "executor_common.py"
DISPATCH_PY_PATH = EXECUTORS_DIR / "executor_dispatch.py"
COMMIT_PY_PATH = EXECUTORS_DIR / "commit_executor.py"
REQUIRED_CI_WORKFLOW_PATHS = (
    REPO_ROOT / ".github" / "workflows" / "ci.yml",
    REPO_ROOT / ".github" / "workflows" / "green_gate.yml",
)


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


def _workflow_timeout_seconds(path: Path) -> int:
    values = [
        int(match.group(1)) * 60
        for match in re.finditer(r"^\s*timeout-minutes:\s*(\d+)\s*$", path.read_text(), re.MULTILINE)
    ]
    assert values, f"{path} has no timeout-minutes entries"
    return max(values)


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

    def test_commit_ci_wait_budget_covers_required_workflow_timeout(self):
        """Commit CI wait cannot be shorter than required workflow job caps."""
        live = _load_json_config_timeouts()
        required_workflow_timeout = max(
            _workflow_timeout_seconds(path) for path in REQUIRED_CI_WORKFLOW_PATHS
        )
        assert live["commit_ci_watch"] >= required_workflow_timeout, (
            "commit_ci_watch must cover the longest required workflow timeout"
        )
        assert live["commit_ci_poll"] >= required_workflow_timeout, (
            "commit_ci_poll must cover the longest required workflow timeout"
        )

    def test_pipeline_agent_pager_enabled_matches_live(self):
        """DEFAULT pager-enabled must equal live (True) so the bare/missing-config
        fallback emits commit_started/commit_failed exactly like prod -- no silent
        fallback drift back to pager-OFF."""
        default_enabled = _load_default_executor_config()["pipeline_agent_pager"]["enabled"]
        live_enabled = json.loads(CONFIG_JSON_PATH.read_text(encoding="utf-8"))[
            "pipeline_agent_pager"
        ]["enabled"]
        assert default_enabled is True, (
            "DEFAULT_EXECUTOR_CONFIG['pipeline_agent_pager']['enabled'] must be True "
            "so the bare-config fallback emits the commit-outcome pager like prod"
        )
        assert default_enabled == live_enabled, (
            "DEFAULT pipeline_agent_pager.enabled drifted from live executor_config.json"
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

    def test_commit_ci_watch_timeout_from_config(self):
        self._assert_config_derived("COMMIT_CI_WATCH_TIMEOUT_S")

    def test_commit_ci_poll_timeout_from_config(self):
        self._assert_config_derived("COMMIT_CI_POLL_TIMEOUT_S")

    def test_commit_ci_verify_timeout_from_config(self):
        self._assert_config_derived("COMMIT_CI_VERIFY_TIMEOUT_S")

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
        # bot_remediation is an implementer-backend key, so in EACH config it must
        # be present and equal THAT config's own implementer role agent
        # (executor_common.apply_role_agents materializes IMPLEMENTER_BACKEND_KEYS
        # from role_agents.implementer). Per A2
        # (FOUNDER_OVERRIDE:role-switch-convergence-2026-05-31) the live config is
        # authoritative and need NOT equal DEFAULT, so each config is checked
        # against its OWN role_agents rather than asserting DEFAULT==live -- the old
        # DEFAULT==live coupling broke on an implementer-role flip because
        # set_roles.py edits live only. Asserting against the implementer agent
        # also stays correct across role switches instead of hard-coding a provider.
        defaults = _load_default_executor_config_backends()
        live = _load_json_config_backends()
        assert "bot_remediation" in defaults
        assert "bot_remediation" in live
        default_implementer = _load_default_executor_config_role_agents().get("implementer")
        live_implementer = _load_json_config_role_agents().get("implementer")
        assert defaults.get("bot_remediation") == default_implementer
        assert live.get("bot_remediation") == live_implementer


class TestRoleAgentConfigAlignment:
    def test_role_agents_match_between_default_and_live_config(self):
        """LIVE config is internally consistent with its OWN role_agents.

        A2 (founder-approved, FOUNDER_OVERRIDE:role-switch-convergence-2026-05-31):
        the live executor_config.json role_agents is authoritative;
        DEFAULT_EXECUTOR_CONFIG is a fallback that need NOT equal live. set_roles.py
        edits the live file only (role_agents + the derived backends/bridge_reviewers
        via executor_common.apply_role_agents), so the previous DEFAULT==live
        assertion broke on every role flip (the 2026-05-30 role-flip saga).

        Instead, re-derive from the LIVE role_agents using the same canonical
        apply_role_agents rule the runtime loader uses and assert the live file
        already equals that fixed-point. Because the expectations are derived FROM
        the live role_agents, a set_roles.py live-only flip can never break this
        test (the derived fields always move with role_agents). The method name is
        retained for continuity; it now checks live-internal consistency.
        """
        live = json.loads(CONFIG_JSON_PATH.read_text(encoding="utf-8"))
        role_agents = live["role_agents"]
        assert set(role_agents) == ROLE_AGENT_KEYS, (
            f"live role_agents keys {sorted(role_agents)} != {sorted(ROLE_AGENT_KEYS)}"
        )
        implementer = role_agents["implementer"]
        reviewer = role_agents["reviewer"]

        # Canonical fixed-point: applying the live role_agents to a copy of the
        # live config must be a no-op for every materialized field. This ties the
        # test to the single derivation source (apply_role_agents) so it follows
        # any future change to the role->field mapping automatically.
        materialized = apply_role_agents(copy.deepcopy(live), implementer, reviewer)
        assert materialized["backends"] == live["backends"], (
            "live backends are not the materialization fixed-point of live role_agents"
        )
        assert materialized["bridge_reviewers"] == live["bridge_reviewers"], (
            "live bridge_reviewers are not the fixed-point of live role_agents"
        )

        # Explicit per-key consistency for readable diagnostics (same source of
        # truth: the key sets are imported from executor_common).
        for key in IMPLEMENTER_BACKEND_KEYS:
            assert live["backends"][key] == implementer, (
                f"live backends[{key!r}]={live['backends'].get(key)!r} != "
                f"implementer {implementer!r}"
            )
        for key in REVIEW_OVERRIDE_BACKEND_KEYS:
            assert live["backends"][key] == reviewer, (
                f"live backends[{key!r}]={live['backends'].get(key)!r} != "
                f"reviewer {reviewer!r}"
            )
        for key in REVIEWER_BRIDGE_KEYS:
            assert live["bridge_reviewers"][key] == reviewer, (
                f"live bridge_reviewers[{key!r}]={live['bridge_reviewers'].get(key)!r} != "
                f"reviewer {reviewer!r}"
            )

    def test_role_agents_define_supported_implementer_and_reviewer(self):
        live = _load_json_config_role_agents()
        assert set(live) == ROLE_AGENT_KEYS
        # A2 (FOUNDER_OVERRIDE:role-switch-convergence-2026-05-31): valid role agents
        # are those DEFINED in the live bridge_agent_defaults menu, not a hardcoded
        # {claude, codex}. Deriving from live makes adding a menu agent (e.g. 'fable')
        # a config-only change with no test edit.
        defined_agents = set(_load_json_config_bridge_agent_defaults())
        assert set(live.values()) <= defined_agents, (
            f"role_agents values {sorted(live.values())} must be agents defined in "
            f"the live bridge_agent_defaults menu {sorted(defined_agents)}"
        )


class TestBridgeAgentDefaultConfigAlignment:
    def test_bridge_agent_defaults_match_between_default_and_live_config(self):
        """A2 (FOUNDER_OVERRIDE:role-switch-convergence-2026-05-31): the live
        bridge_agent_defaults menu is authoritative and may define MORE agents than
        DEFAULT_EXECUTOR_CONFIG (e.g. an added 'fable' menu entry). DEFAULT is a
        fallback SUBSET, so assert live is a SUPERSET of DEFAULT -- every DEFAULT agent
        present in live with matching provider config -- rather than DEFAULT==live,
        which broke on every menu addition. The method name is retained for continuity.
        """
        defaults = _load_default_executor_config_bridge_agent_defaults()
        live = _load_json_config_bridge_agent_defaults()
        for agent, cfg in defaults.items():
            assert agent in live, (
                f"DEFAULT bridge_agent_defaults agent {agent!r} missing from live menu"
            )
            assert live[agent] == cfg, (
                f"live bridge_agent_defaults[{agent!r}]={live[agent]!r} != DEFAULT {cfg!r}"
            )

    def test_bridge_agent_defaults_define_provider_model_and_effort_switches(self):
        defaults = _load_json_config_bridge_agent_defaults()
        assert set(REQUIRED_BRIDGE_AGENT_DEFAULT_KEYS) <= set(defaults)
        for provider, required_keys in REQUIRED_BRIDGE_AGENT_DEFAULT_KEYS.items():
            provider_defaults = defaults[provider]
            assert required_keys <= set(provider_defaults)
            for key in required_keys:
                assert isinstance(provider_defaults[key], str)
                assert provider_defaults[key]


class TestFallbackMaterializesRolesNoDrift:
    """BOTH the bare-defaults merge path AND the dispatch load_config --config
    fallback must materialize backends/bridge_reviewers from role_agents via the
    single apply_role_agents rule.

    Regression guard for the role-switch drift the minimal PR #1166 stranded on:
    a missing or role-only config must not leak the static DEFAULT_EXECUTOR_CONFIG
    reviewer provider (codex) into the dispatched reviewer backends, and
    commit_executor must stay None on every path. See work items 2/3/5 of
    reports/control_plane/claude-roles-full-2026-06-27_2026-06-27.md.
    """

    @staticmethod
    def _assert_role_fixed_point(config: dict) -> None:
        """config's backends/bridge_reviewers are the apply_role_agents fixed-point
        of its own role_agents (the canonical rule the runtime loader uses), and
        commit_executor is not derived to a provider."""
        role_agents = config["role_agents"]
        implementer = role_agents["implementer"]
        reviewer = role_agents["reviewer"]
        materialized = apply_role_agents(copy.deepcopy(config), implementer, reviewer)
        assert config["backends"] == materialized["backends"], (
            "backends are not the materialization fixed-point of role_agents"
        )
        assert config["bridge_reviewers"] == materialized["bridge_reviewers"], (
            "bridge_reviewers are not the fixed-point of role_agents"
        )
        for key in IMPLEMENTER_BACKEND_KEYS:
            assert config["backends"][key] == implementer
        for key in REVIEW_OVERRIDE_BACKEND_KEYS:
            assert config["backends"][key] == reviewer
        for key in REVIEWER_BRIDGE_KEYS:
            assert config["bridge_reviewers"][key] == reviewer
        assert config["backends"]["commit_executor"] is None

    def test_bare_defaults_merge_materializes_roles(self):
        # The bare-defaults path itself derives every materialized field from
        # role_agents — no static codex literal leaks through unmaterialized.
        self._assert_role_fixed_point(merge_executor_config_overrides({}))

    def test_role_only_override_merge_has_no_codex_drift(self):
        # A role-only override flipping the reviewer to claude must derive EVERY
        # reviewer-side backend + bridge_reviewer to claude; the DEFAULT codex
        # literals must not survive the merge.
        config = merge_executor_config_overrides(
            {"role_agents": {"implementer": "claude", "reviewer": "claude"}}
        )
        assert config["role_agents"] == {"implementer": "claude", "reviewer": "claude"}
        self._assert_role_fixed_point(config)
        for key in REVIEW_OVERRIDE_BACKEND_KEYS:
            assert config["backends"][key] == "claude"
        for key in REVIEWER_BRIDGE_KEYS:
            assert config["bridge_reviewers"][key] == "claude"

    def test_codex_override_merge_materializes_roles_both_directions(self):
        # The codex direction of the same fallback (the claude direction is covered
        # above). A role-only override flipping BOTH roles to codex must derive EVERY
        # implementer/reviewer backend + bridge_reviewer to codex -- no claude DEFAULT
        # literal survives the merge -- with commit_executor still None. This is the
        # "both directions" half item 2 adds so a future claude->codex switch can
        # never leave a stale provider in the bare/missing-config fallback.
        config = merge_executor_config_overrides(
            {"role_agents": {"implementer": "codex", "reviewer": "codex"}}
        )
        assert config["role_agents"] == {"implementer": "codex", "reviewer": "codex"}
        self._assert_role_fixed_point(config)
        for key in IMPLEMENTER_BACKEND_KEYS:
            assert config["backends"][key] == "codex"
        for key in REVIEW_OVERRIDE_BACKEND_KEYS:
            assert config["backends"][key] == "codex"
        for key in REVIEWER_BRIDGE_KEYS:
            assert config["bridge_reviewers"][key] == "codex"

    def test_mixed_override_merge_materializes_split_roles(self):
        # Implementer and reviewer derive INDEPENDENTLY in the fallback: an
        # implementer=codex / reviewer=claude split lands codex on the
        # implementer-backend keys and claude on every reviewer-side key (backends +
        # bridge_reviewers), with commit_executor still None. Guards against a future
        # single-provider shortcut that would collapse the split.
        config = merge_executor_config_overrides(
            {"role_agents": {"implementer": "codex", "reviewer": "claude"}}
        )
        assert config["role_agents"] == {"implementer": "codex", "reviewer": "claude"}
        self._assert_role_fixed_point(config)
        for key in IMPLEMENTER_BACKEND_KEYS:
            assert config["backends"][key] == "codex"
        for key in REVIEW_OVERRIDE_BACKEND_KEYS:
            assert config["backends"][key] == "claude"
        for key in REVIEWER_BRIDGE_KEYS:
            assert config["bridge_reviewers"][key] == "claude"

    def test_dispatch_load_config_missing_fallback_materializes_roles(self, tmp_path):
        self._assert_role_fixed_point(dispatch.load_config(tmp_path / "nonexistent.json"))

    def test_dispatch_load_config_role_only_fallback_has_no_codex_drift(
        self, tmp_path, monkeypatch
    ):
        # The --config fallback materializes purely from the file's role_agents
        # (config-only path, no env). Clear role env so the assertion is exact.
        for name in (
            "RCX_IMPLEMENTER_AGENT_OVERRIDE",
            "RCX_REVIEWER_AGENT_OVERRIDE",
            "RCX_BRIDGE_REVIEWER_OVERRIDE",
        ):
            monkeypatch.delenv(name, raising=False)
        config_path = tmp_path / "executor_config.json"
        config_path.write_text(
            json.dumps({"role_agents": {"implementer": "claude", "reviewer": "claude"}}),
            encoding="utf-8",
        )
        config = dispatch.load_config(config_path)
        assert config["role_agents"] == {"implementer": "claude", "reviewer": "claude"}
        self._assert_role_fixed_point(config)
        for key in REVIEW_OVERRIDE_BACKEND_KEYS:
            assert config["backends"][key] == "claude"
        for key in REVIEWER_BRIDGE_KEYS:
            assert config["bridge_reviewers"][key] == "claude"
