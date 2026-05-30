"""Tests for dialectic_executor reviewer-role derivation.

The dialectic narrowing reviewer must follow the configured reviewer role
(role_agents.reviewer, env-aware) rather than a hardcoded provider, so that a
`set_roles --reviewer X` switch propagates to CONTINUE_DIALECTIC rounds.
Regression for the PR #1046 bot review finding (dialectic hardcoded
`--reviewer codex`, which ignored the role switch).
"""
from __future__ import annotations

import sys

from tests.repo_root import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "mu" / "tools" / "executors"))
import dialectic_executor as de  # noqa: E402  (path insert must precede import)


def test_dialectic_reviewer_follows_configured_role(monkeypatch):
    monkeypatch.setattr(
        de, "configured_role_agents", lambda root: {"reviewer": {"agent": "claude"}}
    )
    assert de.resolve_dialectic_reviewer(REPO_ROOT) == "claude"
    monkeypatch.setattr(
        de, "configured_role_agents", lambda root: {"reviewer": {"agent": "codex"}}
    )
    assert de.resolve_dialectic_reviewer(REPO_ROOT) == "codex"


def test_dialectic_reviewer_falls_back_to_codex_on_error(monkeypatch):
    def boom(root):
        raise RuntimeError("no config")

    monkeypatch.setattr(de, "configured_role_agents", boom)
    assert de.resolve_dialectic_reviewer(REPO_ROOT) == "codex"
