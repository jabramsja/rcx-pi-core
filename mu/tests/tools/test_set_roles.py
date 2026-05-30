"""Tests for the set_roles CLI — the single-switch writer for role_agents.

set_roles edits ONLY executor_config.json (role_agents + derived backends/
bridge_reviewers via executor_common.apply_role_agents) and reports the runtime
EFFECTIVE (env-aware) resolution plus an env-shadow warning.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from tests.repo_root import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "mu" / "tools" / "executors"))
import set_roles  # noqa: E402  (path insert must precede import)


def _seed_config(root: Path) -> Path:
    cfg_dir = root / "mu" / "tools" / "executors"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg = cfg_dir / "executor_config.json"
    cfg.write_text(
        json.dumps(
            {
                "role_agents": {"implementer": "claude", "reviewer": "claude"},
                "bridge_agent_defaults": {"claude": {}, "codex": {}},
                "backends": {
                    "post_merge_supervisor": "codex",
                    "dialectic_executor": "codex",
                    "phase_a_executor": "codex",
                    "phase_b_executor": "codex",
                    "bot_remediation": "codex",
                    "commit_executor": None,
                },
                "bridge_reviewers": {"phase_a": "codex", "phase_b": "codex"},
            },
            indent=2,
        )
        + "\n"
    )
    return cfg


def _clear_role_env(monkeypatch):
    for names in (
        ("RCX_IMPLEMENTER_AGENT_OVERRIDE",),
        ("RCX_REVIEWER_AGENT_OVERRIDE", "RCX_BRIDGE_REVIEWER_OVERRIDE"),
    ):
        for name in names:
            monkeypatch.delenv(name, raising=False)


def test_write_sets_role_agents_and_derived(tmp_path):
    cfg = _seed_config(tmp_path)
    rc = set_roles.main(
        ["--implementer", "claude", "--reviewer", "codex", "--repo-root", str(tmp_path)]
    )
    assert rc == 0
    data = json.loads(cfg.read_text())
    assert data["role_agents"] == {"implementer": "claude", "reviewer": "codex"}
    # implementer-backend keys -> implementer; review-override keys -> reviewer
    assert data["backends"]["phase_a_executor"] == "claude"
    assert data["backends"]["phase_b_executor"] == "claude"
    assert data["backends"]["bot_remediation"] == "claude"
    assert data["backends"]["post_merge_supervisor"] == "codex"
    assert data["backends"]["dialectic_executor"] == "codex"
    assert data["backends"]["commit_executor"] is None
    assert data["bridge_reviewers"] == {"phase_a": "codex", "phase_b": "codex"}


def test_switch_both_directions(tmp_path):
    cfg = _seed_config(tmp_path)
    set_roles.main(
        ["--implementer", "codex", "--reviewer", "claude", "--repo-root", str(tmp_path)]
    )
    data = json.loads(cfg.read_text())
    assert data["role_agents"] == {"implementer": "codex", "reviewer": "claude"}
    assert data["backends"]["phase_b_executor"] == "codex"
    assert data["backends"]["post_merge_supervisor"] == "claude"
    assert data["bridge_reviewers"] == {"phase_a": "claude", "phase_b": "claude"}


def test_idempotent(tmp_path):
    cfg = _seed_config(tmp_path)
    set_roles.main(
        ["--implementer", "claude", "--reviewer", "codex", "--repo-root", str(tmp_path)]
    )
    first = cfg.read_text()
    set_roles.main(
        ["--implementer", "claude", "--reviewer", "codex", "--repo-root", str(tmp_path)]
    )
    assert cfg.read_text() == first


def test_partial_switch_preserves_other_role(tmp_path):
    cfg = _seed_config(tmp_path)  # starts claude/claude
    set_roles.main(["--reviewer", "codex", "--repo-root", str(tmp_path)])
    data = json.loads(cfg.read_text())
    assert data["role_agents"] == {"implementer": "claude", "reviewer": "codex"}


def test_rejects_unknown_agent(tmp_path):
    cfg = _seed_config(tmp_path)
    before = cfg.read_text()
    rc = set_roles.main(["--reviewer", "gpt4", "--repo-root", str(tmp_path)])
    assert rc == 2
    assert cfg.read_text() == before  # rejected writes nothing


def test_show_does_not_modify(tmp_path):
    cfg = _seed_config(tmp_path)
    before = cfg.read_text()
    rc = set_roles.main(["--show", "--repo-root", str(tmp_path)])
    assert rc == 0
    assert cfg.read_text() == before


def test_env_shadow_warning_surfaces(tmp_path, monkeypatch, capsys):
    _seed_config(tmp_path)
    monkeypatch.setenv("RCX_BRIDGE_REVIEWER_OVERRIDE", "codex")
    set_roles.main(
        ["--implementer", "claude", "--reviewer", "claude", "--repo-root", str(tmp_path)]
    )
    out = capsys.readouterr().out
    assert "SHADOW" in out
    assert "RCX_BRIDGE_REVIEWER_OVERRIDE" in out
    assert "EFFECTIVE" in out  # effective resolution reported


def test_no_shadow_when_env_clear(tmp_path, monkeypatch, capsys):
    _seed_config(tmp_path)
    _clear_role_env(monkeypatch)
    set_roles.main(
        ["--implementer", "claude", "--reviewer", "codex", "--repo-root", str(tmp_path)]
    )
    out = capsys.readouterr().out
    assert "sole source of truth" in out
    assert "SHADOW" not in out
