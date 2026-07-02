"""Tests for the set_roles CLI — the single-switch writer for role_agents.

set_roles edits ONLY executor_config.json (role_agents + derived backends/
bridge_reviewers via executor_common.apply_role_agents) and reports the runtime
EFFECTIVE (env-aware) resolution plus an env-shadow warning.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "mu" / "tools" / "executors"))
import executor_common  # noqa: E402  (path insert must precede import)
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
                "pipeline_agent_pager": {"enabled": True, "route": "claude"},
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


def test_role_switch_preserves_orchestrator_mode_surfaces(tmp_path):
    cfg = _seed_config(tmp_path)
    state_path = tmp_path / ".agent_bus" / "observability" / "orchestrator_mode.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "mode": "codex",
                "repo_root": str(tmp_path),
                "bus_dir": ".agent_bus",
                "tmux_session": "rcx-codex",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    before_state = state_path.read_text(encoding="utf-8")

    rc = set_roles.main(
        ["--implementer", "codex", "--reviewer", "claude", "--repo-root", str(tmp_path)]
    )

    assert rc == 0
    data = json.loads(cfg.read_text())
    assert data["role_agents"] == {"implementer": "codex", "reviewer": "claude"}
    assert data["pipeline_agent_pager"] == {"enabled": True, "route": "claude"}
    assert state_path.read_text(encoding="utf-8") == before_state


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


def test_write_is_atomic_failed_replace_preserves_original(tmp_path, monkeypatch):
    """A crash during the atomic replace must leave the authoritative config intact.

    The live executor_config.json is read by the runtime loader with an unguarded
    json.loads, so set_roles must never leave a torn/truncated file. Simulate a
    failure at the os.replace step and assert the original file is byte-for-byte
    preserved and no temp residue is left behind in the config directory.
    """
    cfg = _seed_config(tmp_path)
    before = cfg.read_text()

    def _boom(*_args, **_kwargs):
        raise OSError("simulated crash during replace")

    monkeypatch.setattr(set_roles.os, "replace", _boom)
    with pytest.raises(OSError):
        set_roles.main(
            ["--implementer", "codex", "--reviewer", "claude", "--repo-root", str(tmp_path)]
        )
    # Complete old file, never a torn write.
    assert cfg.read_text() == before
    # No truncated temp residue left alongside the authoritative config.
    leftovers = sorted(p.name for p in cfg.parent.iterdir() if p.name != cfg.name)
    assert leftovers == [], f"atomic write left temp residue: {leftovers}"


def test_switch_keeps_committed_and_fallback_in_sync_both_directions(tmp_path, monkeypatch):
    """set_roles is the single switch: after a flip the committed config AND the
    bare/missing-config fallback resolve the SAME selection — no hardcoded DEFAULT
    drift — in BOTH directions for any provider pair.

    Regression for the manual DEFAULT_EXECUTOR_CONFIG.role_agents hand-edit this wave
    eliminates: previously a set_roles switch updated only the committed file, so the
    bare/missing-config fallback kept resolving the stale hardcoded literal. The
    fallback now reads the committed file via executor_common._committed_executor_config_path;
    point that seam at the file set_roles writes under --repo-root so no real tracked
    file is touched.
    """
    _clear_role_env(monkeypatch)
    cfg = _seed_config(tmp_path)  # claude/claude committed under tmp_path
    monkeypatch.setattr(
        executor_common, "_committed_executor_config_path", lambda: cfg
    )
    # A root with NO executor_config.json exercises load_executor_config's missing path.
    configless_root = tmp_path / "configless"

    for implementer, reviewer in (
        ("codex", "codex"),
        ("claude", "claude"),
        ("codex", "claude"),
        ("claude", "codex"),
    ):
        rc = set_roles.main(
            [
                "--implementer", implementer,
                "--reviewer", reviewer,
                "--repo-root", str(tmp_path),
            ]
        )
        assert rc == 0
        expected = {"implementer": implementer, "reviewer": reviewer}

        # 1. The committed config reflects the switch.
        committed = json.loads(cfg.read_text())
        assert committed["role_agents"] == expected

        # 2. The bare-defaults fallback resolves the SAME selection (no DEFAULT drift).
        bare = executor_common.merge_executor_config_overrides({})
        assert bare["role_agents"] == expected
        assert bare["bridge_reviewers"]["phase_a"] == reviewer
        assert bare["backends"]["phase_b_executor"] == implementer
        assert bare["backends"]["commit_executor"] is None

        # 3. The missing-config load path (no config at this root) also follows.
        missing = executor_common.load_executor_config(configless_root)
        assert missing["role_agents"] == expected
        assert missing["backends"]["post_merge_supervisor"] == reviewer


def test_role_labels_follow_live_roles_after_switch(tmp_path, monkeypatch):
    """tmux implementer/reviewer pane labels follow a set_roles switch (item 4).

    The pane role labels (_pane_processes.sh / _pane_timeline.sh load_role_agent_labels)
    and the dashboards source their implementer/reviewer display + status names from
    executor_common.configured_role_agents, which reads the LIVE role_agents. A
    set_roles switch must therefore move those labels with no separate label edit.
    Prove the label SOURCE follows the switch in BOTH directions -- it is not a
    one-way latch (the recurring stale-provider risk this wave generalizes).
    """
    _clear_role_env(monkeypatch)
    _seed_config(tmp_path)  # starts claude/claude

    claude_labels = executor_common.configured_role_agents(tmp_path)
    assert claude_labels["implementer"]["agent"] == "claude"
    assert claude_labels["reviewer"]["agent"] == "claude"

    set_roles.main(
        ["--implementer", "codex", "--reviewer", "codex", "--repo-root", str(tmp_path)]
    )
    codex_labels = executor_common.configured_role_agents(tmp_path)
    assert codex_labels["implementer"]["agent"] == "codex"
    assert codex_labels["reviewer"]["agent"] == "codex"
    # The rendered label text (display + short status) moves with the switch.
    for role in ("implementer", "reviewer"):
        assert codex_labels[role]["display_name"] != claude_labels[role]["display_name"]
        assert codex_labels[role]["status_name"] != claude_labels[role]["status_name"]

    # Follows BACK to claude: the label source is live, not a one-way latch.
    set_roles.main(
        ["--implementer", "claude", "--reviewer", "claude", "--repo-root", str(tmp_path)]
    )
    back = executor_common.configured_role_agents(tmp_path)
    assert back["implementer"]["agent"] == "claude"
    assert back["reviewer"]["agent"] == "claude"
    assert (
        back["implementer"]["display_name"]
        == claude_labels["implementer"]["display_name"]
    )
    assert back["reviewer"]["status_name"] == claude_labels["reviewer"]["status_name"]
