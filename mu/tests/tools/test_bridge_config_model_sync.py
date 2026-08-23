"""Regression tests for bridge_config <- bridge_agent_defaults provider sync.

executor_common.sync_bridge_config_agents_from_defaults keeps the live
.agent_bus/bridge_config.json per-agent provider settings (model / effort /
display_name) aligned with executor_config.json's bridge_agent_defaults, so the
running provider config cannot drift from the committed default (2026-06-02:
bridge_config ran the claude implementer on claude-opus-4-7 while
bridge_agent_defaults.claude said claude-opus-4-8). set_roles.py invokes the sync
after apply_role_agents so every role switch re-syncs too.

See: reports/control_plane/bridge_config_model_sync_2026-06-02.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "mu" / "tools" / "executors"))
import set_roles  # noqa: E402  (path insert must precede import)
import executor_common  # noqa: E402  (path insert must precede import)
from executor_common import (  # noqa: E402  (path insert must precede import)
    sync_bridge_config_agents_from_defaults,
)


def _claude_cmd(model: str = "claude-opus-4-7", effort: str = "low") -> list[str]:
    """A claude bridge cmd in the live shape: --model <m> ... --effort <e>."""
    return [
        "claude",
        "--print",
        "--dangerously-skip-permissions",
        "--model",
        model,
        "--effort",
        effort,
        "--verbose",
        "--output-format",
        "stream-json",
        "--max-turns",
        "100",
    ]


def _codex_cmd(model: str = "gpt-5.0", effort: str = "medium") -> list[str]:
    """A codex bridge cmd in the live shape: -m <m> ... -c model_reasoning_effort="<e>"."""
    return [
        "codex",
        "exec",
        "-",
        "--json",
        "-m",
        model,
        "-c",
        f'model_reasoning_effort="{effort}"',
        "--sandbox",
        "danger-full-access",
    ]


_DEFAULT_BRIDGE_AGENT_DEFAULTS = {
    "claude": {
        "display_name": "Claude Opus 4.8 max",
        "model": "claude-opus-4-8",
        "effort": "max",
    },
    "codex": {
        "display_name": "Codex 5.6 Sol ultra",
        "model": "gpt-5.6-sol",
        "reasoning_effort": "ultra",
    },
}


def _seed_executor_config(root: Path, defaults: dict | None = None) -> Path:
    cfg_dir = root / "mu" / "tools" / "executors"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg = cfg_dir / "executor_config.json"
    cfg.write_text(
        json.dumps(
            {
                "role_agents": {"implementer": "claude", "reviewer": "codex"},
                "bridge_agent_defaults": defaults
                if defaults is not None
                else _DEFAULT_BRIDGE_AGENT_DEFAULTS,
            },
            indent=2,
        )
        + "\n"
    )
    return cfg


def _seed_bridge_config(root: Path, agents: dict) -> Path:
    bus = root / ".agent_bus"
    bus.mkdir(parents=True, exist_ok=True)
    path = bus / "bridge_config.json"
    path.write_text(json.dumps({"agents": agents}, indent=2) + "\n")
    return path


def _agent_cmd(path: Path, agent: str) -> list[str]:
    return json.loads(path.read_text())["agents"][agent]["cmd"]


def test_committed_codex_menu_and_fallback_metadata_are_gpt_56_sol_ultra():
    committed = json.loads(
        (REPO_ROOT / "mu" / "tools" / "executors" / "executor_config.json").read_text()
    )
    expected_codex = {
        "display_name": "Codex 5.6 Sol ultra",
        "model": "gpt-5.6-sol",
        "reasoning_effort": "ultra",
    }

    assert committed["bridge_agent_defaults"]["codex"] == expected_codex
    assert (
        executor_common.DEFAULT_EXECUTOR_CONFIG["bridge_agent_defaults"]["codex"]
        == expected_codex
    )
    assert (
        executor_common.merge_executor_config_overrides({})["bridge_agent_defaults"]["codex"]
        == expected_codex
    )

    assert committed["role_agents"] == {"implementer": "claude", "reviewer": "claude"}
    assert committed["backends"] == {
        "post_merge_supervisor": "claude",
        "dialectic_executor": "claude",
        "phase_a_executor": "claude",
        "phase_b_executor": "claude",
        "bot_remediation": "claude",
        "commit_executor": None,
    }
    assert committed["bridge_reviewers"] == {"phase_a": "claude", "phase_b": "claude"}
    assert committed["pipeline_agent_pager"] == {"enabled": True, "route": "claude"}


def test_sync_corrects_model_drift(tmp_path):
    """The exact wave scenario: claude cmd model claude-opus-4-7 -> claude-opus-4-8."""
    _seed_executor_config(tmp_path)
    bridge = _seed_bridge_config(
        tmp_path,
        {"claude": {"mode": "live", "display_name": "stale", "cmd": _claude_cmd(model="claude-opus-4-7")}},
    )
    assert "claude-opus-4-7" in _agent_cmd(bridge, "claude")

    result = sync_bridge_config_agents_from_defaults(tmp_path)

    assert result == bridge
    cmd = _agent_cmd(bridge, "claude")
    assert "claude-opus-4-7" not in cmd
    assert cmd[cmd.index("--model") + 1] == "claude-opus-4-8"


def test_sync_reads_seeded_defaults_not_hardcoded(tmp_path):
    """The synced model comes from bridge_agent_defaults, not a hardcoded constant."""
    _seed_executor_config(
        tmp_path,
        defaults={"claude": {"model": "claude-sentinel-9-9", "effort": "max", "display_name": "Sentinel"}},
    )
    bridge = _seed_bridge_config(
        tmp_path, {"claude": {"mode": "live", "cmd": _claude_cmd(model="claude-opus-4-7")}}
    )

    sync_bridge_config_agents_from_defaults(tmp_path)

    cmd = _agent_cmd(bridge, "claude")
    assert cmd[cmd.index("--model") + 1] == "claude-sentinel-9-9"


def test_sync_corrects_effort_and_display_name_both_shapes(tmp_path):
    """Effort syncs for both --effort (claude) and model_reasoning_effort (codex);
    display_name syncs for both."""
    _seed_executor_config(tmp_path)
    bridge = _seed_bridge_config(
        tmp_path,
        {
            "claude": {"mode": "live", "display_name": "stale-claude", "cmd": _claude_cmd(effort="low")},
            "codex": {"mode": "live", "display_name": "stale-codex", "cmd": _codex_cmd(effort="medium")},
        },
    )

    sync_bridge_config_agents_from_defaults(tmp_path)

    data = json.loads(bridge.read_text())
    claude, codex = data["agents"]["claude"], data["agents"]["codex"]
    assert claude["cmd"][claude["cmd"].index("--effort") + 1] == "max"
    assert claude["display_name"] == "Claude Opus 4.8 max"
    assert codex["cmd"][codex["cmd"].index("-m") + 1] == "gpt-5.6-sol"
    assert 'model_reasoning_effort="ultra"' in codex["cmd"]
    assert 'model_reasoning_effort="medium"' not in codex["cmd"]
    assert codex["display_name"] == "Codex 5.6 Sol ultra"


def test_sync_leaves_other_cmd_args_and_fields_untouched(tmp_path):
    """Only model/effort/display_name change; every other cmd arg + field is preserved."""
    _seed_executor_config(tmp_path)
    original_cmd = _claude_cmd(model="claude-opus-4-7", effort="low")
    model_value_idx = original_cmd.index("--model") + 1
    effort_value_idx = original_cmd.index("--effort") + 1
    bridge = _seed_bridge_config(
        tmp_path,
        {
            "claude": {
                "mode": "live",
                "display_name": "stale",
                "cmd": list(original_cmd),
                "prompt_via_stdin": True,
                "timeout_s": 900,
                "env": {"FOO": "bar"},
            }
        },
    )

    sync_bridge_config_agents_from_defaults(tmp_path)

    agent = json.loads(bridge.read_text())["agents"]["claude"]
    # Untouched non-provider fields.
    assert agent["mode"] == "live"
    assert agent["prompt_via_stdin"] is True
    assert agent["timeout_s"] == 900
    assert agent["env"] == {"FOO": "bar"}
    # Only the two provider value tokens changed; no args added/removed/reordered.
    cmd = agent["cmd"]
    assert len(cmd) == len(original_cmd)
    for i, token in enumerate(original_cmd):
        if i in (model_value_idx, effort_value_idx):
            continue
        assert cmd[i] == token


def test_sync_skips_agent_missing_from_defaults(tmp_path):
    """An agent in bridge_config but absent from bridge_agent_defaults is left untouched."""
    _seed_executor_config(
        tmp_path,
        defaults={"claude": {"model": "claude-opus-4-8", "effort": "max", "display_name": "Claude"}},
    )
    bridge = _seed_bridge_config(
        tmp_path,
        {
            "claude": {"mode": "live", "cmd": _claude_cmd(model="claude-opus-4-7")},
            "ghost": {"mode": "live", "display_name": "ghost", "cmd": _codex_cmd(model="ghost-1")},
        },
    )

    sync_bridge_config_agents_from_defaults(tmp_path)

    data = json.loads(bridge.read_text())
    assert "claude-opus-4-8" in data["agents"]["claude"]["cmd"]  # synced
    assert "ghost-1" in data["agents"]["ghost"]["cmd"]  # untouched
    assert data["agents"]["ghost"]["display_name"] == "ghost"


def test_sync_noop_when_bridge_config_absent(tmp_path):
    """No bridge_config.json -> graceful no-op returning None, no file created."""
    _seed_executor_config(tmp_path)
    result = sync_bridge_config_agents_from_defaults(tmp_path)
    assert result is None
    assert not (tmp_path / ".agent_bus" / "bridge_config.json").exists()


def test_sync_does_not_rewrite_when_already_in_sync(tmp_path):
    """Already-aligned config is not rewritten (byte-for-byte preserved)."""
    _seed_executor_config(tmp_path)
    bridge = _seed_bridge_config(
        tmp_path,
        {
            "claude": {
                "mode": "live",
                "display_name": "Claude Opus 4.8 max",
                "cmd": _claude_cmd(model="claude-opus-4-8", effort="max"),
            }
        },
    )
    before = bridge.read_text()

    sync_bridge_config_agents_from_defaults(tmp_path)

    assert bridge.read_text() == before


def test_set_roles_resyncs_bridge_config(tmp_path):
    """set_roles.main re-syncs bridge_config after apply_role_agents (call-site wiring)."""
    _seed_executor_config(tmp_path)
    bridge = _seed_bridge_config(
        tmp_path,
        {"claude": {"mode": "live", "display_name": "stale", "cmd": _claude_cmd(model="claude-opus-4-7")}},
    )

    rc = set_roles.main(
        ["--implementer", "claude", "--reviewer", "codex", "--repo-root", str(tmp_path)]
    )

    assert rc == 0
    cmd = _agent_cmd(bridge, "claude")
    assert cmd[cmd.index("--model") + 1] == "claude-opus-4-8"


def test_sync_atomic_write_failed_replace_preserves_original(tmp_path, monkeypatch):
    """A crash during the atomic replace must leave bridge_config.json intact.

    Bridge adapters load .agent_bus/bridge_config.json with an unguarded
    json.loads, so the sync must never leave a torn/truncated file. Simulate a
    failure at the os.replace step and assert the original file is byte-for-byte
    preserved and no temp residue is left behind in the bus directory.
    """
    _seed_executor_config(tmp_path)
    bridge = _seed_bridge_config(
        tmp_path,
        {"claude": {"mode": "live", "display_name": "stale", "cmd": _claude_cmd(model="claude-opus-4-7")}},
    )
    before = bridge.read_text()

    def _boom(*_args, **_kwargs):
        raise OSError("simulated crash during replace")

    monkeypatch.setattr(executor_common.os, "replace", _boom)
    with pytest.raises(OSError):
        sync_bridge_config_agents_from_defaults(tmp_path)

    # Complete old file, never a torn write.
    assert bridge.read_text() == before
    # No truncated temp residue left alongside bridge_config.json.
    leftovers = sorted(p.name for p in bridge.parent.iterdir() if p.name != bridge.name)
    assert leftovers == [], f"atomic write left temp residue: {leftovers}"


def _seed_bridge_example(root: Path, agents: dict) -> Path:
    ex_dir = root / "mu" / "tools" / "agents"
    ex_dir.mkdir(parents=True, exist_ok=True)
    path = ex_dir / "bridge_config.example.json"
    path.write_text(json.dumps({"agents": agents}, indent=2) + "\n")
    return path


def test_sync_seeds_missing_adapter_from_example(tmp_path):
    """A menu agent in bridge_agent_defaults + the example seed but ABSENT from a
    pre-existing bus is seeded into bridge_config so it is invokable (PR #1097 bot P1:
    activating 'fable' must not fail closed at get_adapter on an older bus).
    """
    _seed_executor_config(
        tmp_path,
        defaults={
            "claude": {"display_name": "Claude Opus 4.8 max", "model": "claude-opus-4-8", "effort": "max"},
            "fable": {"display_name": "Claude Fable 5 max", "model": "claude-fable-5", "effort": "max"},
        },
    )
    _seed_bridge_example(
        tmp_path,
        {
            "claude": {"mode": "live", "display_name": "Claude", "cmd": _claude_cmd(),
                       "prompt_via_stdin": True, "timeout_s": 900, "env": {}},
            "fable": {"mode": "live", "display_name": "Claude Fable 5 max",
                      "cmd": _claude_cmd(model="claude-fable-5", effort="max"),
                      "prompt_via_stdin": True, "timeout_s": 900, "env": {}},
        },
    )
    bridge = _seed_bridge_config(
        tmp_path, {"claude": {"mode": "live", "cmd": _claude_cmd(model="claude-opus-4-8")}}
    )
    assert "fable" not in json.loads(bridge.read_text())["agents"]

    sync_bridge_config_agents_from_defaults(tmp_path)

    data = json.loads(bridge.read_text())["agents"]
    assert "fable" in data, "fable adapter not seeded into pre-existing bus from example"
    cmd = data["fable"]["cmd"]
    assert cmd[cmd.index("--model") + 1] == "claude-fable-5"
    assert data["fable"]["display_name"] == "Claude Fable 5 max"


def test_sync_does_not_fabricate_adapter_absent_from_example(tmp_path):
    """An agent in bridge_agent_defaults but NOT in the example seed is left out (the
    existing get_adapter fail-closed still guards it -- no fabricated adapter).
    """
    _seed_executor_config(
        tmp_path,
        defaults={
            "claude": {"display_name": "Claude", "model": "claude-opus-4-8", "effort": "max"},
            "ghost": {"display_name": "Ghost", "model": "ghost-1", "effort": "max"},
        },
    )
    _seed_bridge_example(tmp_path, {"claude": {"mode": "live", "cmd": _claude_cmd()}})  # no ghost
    bridge = _seed_bridge_config(
        tmp_path, {"claude": {"mode": "live", "cmd": _claude_cmd(model="claude-opus-4-8")}}
    )

    sync_bridge_config_agents_from_defaults(tmp_path)

    data = json.loads(bridge.read_text())["agents"]
    assert "ghost" not in data, "agent absent from the example seed must not be fabricated"


def _cmd_max_turns(model: str, max_turns) -> list:
    return ["claude", "--print", "--dangerously-skip-permissions", "--model", model,
            "--effort", "max", "--verbose", "--output-format", "stream-json",
            "--max-turns", str(max_turns)]


def test_sync_updates_existing_adapter_max_turns_from_example(tmp_path):
    """An EXISTING adapter with a stale --max-turns is synced to the example value, not
    only newly-seeded ones (PR #1098 bot P1: a bus already at --max-turns 50 kept 50, so
    the fable implementer kept exhausting its budget even after the example said 100).
    """
    _seed_executor_config(
        tmp_path,
        defaults={"fable": {"display_name": "Claude Fable 5 max", "model": "claude-fable-5", "effort": "max"}},
    )
    _seed_bridge_example(
        tmp_path,
        {"fable": {"mode": "live", "display_name": "Claude Fable 5 max",
                   "cmd": _cmd_max_turns("claude-fable-5", 100)}},
    )
    # a pre-existing bus adapter still on the stale --max-turns 50
    bridge = _seed_bridge_config(
        tmp_path, {"fable": {"mode": "live", "cmd": _cmd_max_turns("claude-fable-5", 50)}}
    )
    pre = json.loads(bridge.read_text())["agents"]["fable"]["cmd"]
    assert pre[pre.index("--max-turns") + 1] == "50"

    sync_bridge_config_agents_from_defaults(tmp_path)

    cmd = json.loads(bridge.read_text())["agents"]["fable"]["cmd"]
    assert cmd[cmd.index("--max-turns") + 1] == "100", (
        "existing adapter --max-turns not synced from the example seed"
    )
