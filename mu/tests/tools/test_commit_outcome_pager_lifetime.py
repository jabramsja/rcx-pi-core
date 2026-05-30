"""Regression coverage for commit-outcome pager emission across worktree lifetime.

Closes the deferred finding agent-defaults-opus-4-8-2026-05-29
(commit-outcome pager false-error after worktree removal). Two guarantees:

  Part 1 (executor_common.emit_pipeline_agent_event): the pager module is
  registered in sys.modules before exec, so a later emit resolves from the
  cache without re-touching the filesystem -- it survives removal of the
  worktree that __file__ pointed at.

  Part 2 (commit_executor.run_commit_pipeline): a side-channel pager failure on
  the outcome edge must not flip a terminal-success verdict (success/held) to
  error; a non-terminal-success status still flips so real failures stay loud.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from mu.tests.tools.module_loader import load_module
from tests.repo_root import REPO_ROOT

# Load executor_common first: commit_executor binds it via `from executor_common
# import (... emit_pipeline_agent_event ...)`, so it must be in sys.modules so the
# patch seam below targets the same function object the executor calls.
executor_common = load_module(
    "executor_common",
    REPO_ROOT / "mu" / "tools" / "executors" / "executor_common.py",
)
commit_mod = load_module(
    "commit_executor",
    REPO_ROOT / "mu" / "tools" / "executors" / "commit_executor.py",
)


def _write_disabled_pager_config(repo_root: Path) -> None:
    """Disable the pager so the real emit returns its no-filesystem early result.

    With the pager disabled, emit_transition_event short-circuits before any
    backend write, letting Part 1 exercise only the sys.modules cache path.
    """
    config_path = repo_root / "mu" / "tools" / "executors" / "executor_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps({"pipeline_agent_pager": {"enabled": False}}),
        encoding="utf-8",
    )


def test_pager_module_survives_in_sys_modules_after_source_path_gone(tmp_path, monkeypatch):
    """Part 1: a later emit resolves from sys.modules without re-loading from disk.

    Simulates worktree removal by making spec_from_file_location raise for the
    pager module after the first emit populated the cache. The second emit must
    still succeed, proving it never re-touched the (now-dead) __file__ path.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_disabled_pager_config(repo_root)

    # A None sentinel in sys.modules makes `from pipeline_agent_pager import ...`
    # raise ImportError, forcing the fallback on the first emit. monkeypatch
    # records and restores the prior entry on teardown.
    monkeypatch.setitem(sys.modules, "pipeline_agent_pager", None)

    real_spec_from_file_location = importlib.util.spec_from_file_location
    state = {"count": 0, "fail": False}

    def spy_spec_from_file_location(name, location, *args, **kwargs):
        if name == "pipeline_agent_pager":
            state["count"] += 1
            if state["fail"]:
                raise FileNotFoundError(
                    f"simulated worktree removal: {location} no longer exists"
                )
        return real_spec_from_file_location(name, location, *args, **kwargs)

    monkeypatch.setattr(
        importlib.util, "spec_from_file_location", spy_spec_from_file_location
    )

    emit_kwargs = dict(
        event_type="commit_succeeded",
        wave_id="commit-outcome-pager-fix-test",
        task_id="[COMMIT-OUTCOME-PAGER-FIX]",
        phase="commit_executor",
        state="success",
        transition_key="k1",
    )

    first = executor_common.emit_pipeline_agent_event(repo_root, **emit_kwargs)

    # First emit took the disk fallback exactly once and cached the real module.
    assert state["count"] == 1
    cached = sys.modules.get("pipeline_agent_pager")
    assert cached is not None
    assert hasattr(cached, "emit_transition_event")
    assert first.get("enabled") is False

    # Worktree (and __file__) is gone now: any further disk load must fail.
    state["fail"] = True

    second = executor_common.emit_pipeline_agent_event(repo_root, **emit_kwargs)

    # Resolved from sys.modules -- spec_from_file_location was NOT called again,
    # so the dead source path was never touched. This is the worktree-lifetime fix.
    assert state["count"] == 1
    assert second.get("enabled") is False


def _minimal_handoff() -> dict:
    return {"wave_id": "commit-outcome-pager-fix-test"}


@pytest.mark.parametrize("terminal_status", ["success", "held"])
def test_outcome_pager_failure_preserves_terminal_success(tmp_path, terminal_status):
    """Part 2: a side-channel outcome-pager failure must not flip success/held.

    The commit_started edge succeeds (worktree still present); the outcome edge
    raises (worktree removed). A terminal-success verdict must be preserved and
    the pager failure recorded only as a non-fatal warning.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    handoff = _minimal_handoff()

    impl_result = {
        "status": terminal_status,
        "step": "post_merge_cleanup",
        "commit_sha": "abc1234",
        "steps_completed": ["validate_inputs", "git_commit"],
    }

    def fake_emit(_repo_root, **kwargs):
        if kwargs["event_type"] == "commit_started":
            return {"enabled": True, "event_id": "commit_started", "attempted": []}
        # Outcome edge after worktree removal: the pager source path is gone.
        raise FileNotFoundError(
            "pipeline_agent_pager source path removed with worktree"
        )

    with patch.object(commit_mod, "_commit_lifecycle_pager_enabled", return_value=True), \
         patch.object(commit_mod, "_run_commit_pipeline_impl", return_value=impl_result), \
         patch.object(commit_mod, "emit_pipeline_agent_event", side_effect=fake_emit):
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo_root)

    # Verdict preserved -- observability is a side channel, not a gate.
    assert result["status"] == terminal_status
    assert result["step"] == "post_merge_cleanup"
    # Pager failure recorded as a non-fatal warning, not an error flip.
    assert "commit_outcome_pager_warning" in result
    assert any(
        "Commit-outcome pager emission failed" in str(warning)
        for warning in result.get("warnings", [])
    )
    assert not result.get("errors")


def test_outcome_pager_failure_still_flips_non_terminal_success(tmp_path):
    """Part 2 companion: a non-terminal-success status still flips to error.

    A pager failure must not MASK a real pipeline failure. When the pipeline
    result is not success/held, the outcome-pager except path still surfaces
    status=error / step=commit_outcome_pager while preserving the original
    failure context.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    handoff = _minimal_handoff()

    impl_result = {
        "status": "stale",
        "step": "build_and_run_supervisor",
        "errors": ["routing record stale"],
        "steps_completed": [],
    }

    def fake_emit(_repo_root, **kwargs):
        if kwargs["event_type"] == "commit_started":
            return {"enabled": True, "event_id": "commit_started", "attempted": []}
        raise FileNotFoundError(
            "pipeline_agent_pager source path removed with worktree"
        )

    with patch.object(commit_mod, "_commit_lifecycle_pager_enabled", return_value=True), \
         patch.object(commit_mod, "_run_commit_pipeline_impl", return_value=impl_result), \
         patch.object(commit_mod, "emit_pipeline_agent_event", side_effect=fake_emit):
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo_root)

    assert result["status"] == "error"
    assert result["step"] == "commit_outcome_pager"
    assert any(
        "Commit-outcome pager emission failed" in str(error)
        for error in result.get("errors", [])
    )
    # Original pipeline failure context is preserved alongside the pager error.
    assert "routing record stale" in result.get("errors", [])
