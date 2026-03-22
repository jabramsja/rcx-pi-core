"""Tests for executor dispatcher and commit executor.

Covers Slice 1 (dispatcher) and Slice 2 (commit_executor).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from tests.repo_root import REPO_ROOT


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


dispatch_mod = _load_module(
    "executor_dispatch",
    REPO_ROOT / "mu" / "tools" / "executors" / "executor_dispatch.py",
)
commit_mod = _load_module(
    "commit_executor",
    REPO_ROOT / "mu" / "tools" / "executors" / "commit_executor.py",
)
phase_b_mod = _load_module(
    "phase_b_executor",
    REPO_ROOT / "mu" / "tools" / "executors" / "phase_b_executor.py",
)


# ===========================================================================
# Dispatcher tests (Slice 1)
# ===========================================================================


class TestDispatcherRouting:
    """Dispatcher maps routing decisions to executors."""

    def test_route_phase_a_maps_to_phase_a_executor(self):
        assert dispatch_mod.resolve_executor("ROUTE_PHASE_A") == "phase_a_executor"

    def test_route_phase_b_maps_to_phase_b_executor(self):
        assert dispatch_mod.resolve_executor("ROUTE_PHASE_B") == "phase_b_executor"

    def test_continue_dialectic_maps_to_dialectic_executor(self):
        assert dispatch_mod.resolve_executor("CONTINUE_DIALECTIC") == "dialectic_executor"

    def test_commit_go_maps_to_commit_executor(self):
        assert dispatch_mod.resolve_executor("COMMIT_GO") == "commit_executor"

    def test_update_tracker_maps_to_commit_executor(self):
        assert dispatch_mod.resolve_executor("UPDATE_TRACKER_ONLY") == "commit_executor"

    def test_unknown_token_returns_none(self):
        assert dispatch_mod.resolve_executor("UNKNOWN_TOKEN") is None


class TestDispatcherStopTokens:
    """Stop tokens produce stopped status, not executor dispatch."""

    def test_stop_for_founder(self):
        record = {"decision": "STOP_FOR_FOUNDER", "summary": "policy question"}
        result = dispatch_mod.dispatch(record, skip_freshness=True)
        assert result["status"] == "stopped"
        assert result["decision"] == "STOP_FOR_FOUNDER"

    def test_stop_for_triage(self):
        record = {"decision": "STOP_FOR_TRIAGE_DISCUSSION", "summary": "queue empty"}
        result = dispatch_mod.dispatch(record, skip_freshness=True)
        assert result["status"] == "stopped"


class TestDispatcherNotImplemented:
    """Unimplemented executors return not_implemented status."""

    def test_phase_a_not_implemented(self):
        record = {"decision": "ROUTE_PHASE_A", "summary": "plan needed"}
        result = dispatch_mod.dispatch(record, skip_freshness=True)
        assert result["status"] == "not_implemented"
        assert result["executor"] == "phase_a_executor"

    def test_phase_b_is_now_implemented(self):
        """Phase B executor is available since Slice 3."""
        assert "phase_b_executor" in dispatch_mod.AVAILABLE_EXECUTORS

    def test_dialectic_not_implemented(self):
        record = {"decision": "CONTINUE_DIALECTIC", "summary": "narrow"}
        result = dispatch_mod.dispatch(record, skip_freshness=True)
        assert result["status"] == "not_implemented"


class TestDispatcherConfig:
    """Config loading and defaults."""

    def test_load_default_config(self):
        config = dispatch_mod.load_config()
        assert "backends" in config
        assert "timeouts" in config
        assert "bridge_loop_limits" in config

    def test_load_missing_config_returns_defaults(self, tmp_path):
        config = dispatch_mod.load_config(tmp_path / "nonexistent.json")
        assert config["bridge_loop_limits"]["phase_a"] == 15


class TestDispatcherInputValidation:
    """Routing record validation."""

    def test_missing_routing_record(self, tmp_path):
        with pytest.raises(dispatch_mod.DispatchError, match="not found"):
            dispatch_mod.load_routing_record(tmp_path)

    def test_invalid_json_routing_record(self, tmp_path):
        (tmp_path / ".agent_bus" / "meta").mkdir(parents=True)
        (tmp_path / ".agent_bus" / "meta" / "post_merge_routing.json").write_text("not json")
        with pytest.raises(dispatch_mod.DispatchError, match="not valid JSON"):
            dispatch_mod.load_routing_record(tmp_path)

    def test_missing_decision_field(self, tmp_path):
        (tmp_path / ".agent_bus" / "meta").mkdir(parents=True)
        (tmp_path / ".agent_bus" / "meta" / "post_merge_routing.json").write_text('{"summary": "ok"}')
        with pytest.raises(dispatch_mod.DispatchError, match="missing keys"):
            dispatch_mod.load_routing_record(tmp_path)


# ===========================================================================
# Commit executor tests (Slice 2)
# ===========================================================================


def _make_valid_handoff(**overrides):
    base = {
        "staged_files": ["file1.py"],
        "commit_message": "feat: test\n\nCo-Authored-By: test",
        "pr_title": "feat: test",
        "pr_body": "## Summary\ntest",
        "head_branch": "jabramsja/test",
        "base_branch": "dev",
        "hold_push": False,
        "pre_commit_receipt_path": ".agent_bus/meta/pre_commit_receipt.json",
        "task_id": "[TEST-1]",
        "wave_name": "test-wave",
        "caller": "phase_b",
    }
    base.update(overrides)
    return base


class TestCommitHandoffValidation:
    """Handoff schema validation."""

    def test_valid_handoff_passes(self):
        valid, errors = commit_mod.validate_handoff(_make_valid_handoff())
        assert valid, errors

    def test_missing_fields_fails(self):
        valid, errors = commit_mod.validate_handoff({"staged_files": ["x"]})
        assert not valid
        assert any("Missing" in e for e in errors)

    def test_empty_staged_files_fails(self):
        valid, errors = commit_mod.validate_handoff(_make_valid_handoff(staged_files=[]))
        assert not valid
        assert any("empty" in e for e in errors)

    def test_invalid_caller_fails(self):
        valid, errors = commit_mod.validate_handoff(_make_valid_handoff(caller="invalid"))
        assert not valid
        assert any("caller" in e for e in errors)

    def test_hold_push_must_be_bool(self):
        valid, errors = commit_mod.validate_handoff(_make_valid_handoff(hold_push="yes"))
        assert not valid
        assert any("boolean" in e for e in errors)

    def test_non_dict_fails(self):
        valid, errors = commit_mod.validate_handoff("not a dict")
        assert not valid


class TestCommitPipelineValidation:
    """Commit pipeline pre-checks."""

    def _make_receipt(self, repo: Path) -> None:
        """Create a valid pre-commit receipt for testing."""
        receipt_dir = repo / ".agent_bus" / "meta"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        receipt = {"decision": "COMMIT_GO", "staged_sha": "test", "timestamp_utc": "2026-03-22T00:00:00+00:00"}
        (receipt_dir / "pre_commit_receipt.json").write_text(json.dumps(receipt))

    def test_wrong_branch_fails(self, tmp_path):
        import subprocess
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        env = {**__import__("os").environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=repo, capture_output=True, env=env)
        self._make_receipt(repo)

        handoff = _make_valid_handoff(head_branch="wrong-branch")
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert result["status"] == "error"
        assert result["step"] == "branch_check"

    def test_staged_mismatch_fails(self, tmp_path):
        import subprocess
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        env = {**__import__("os").environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "branch", "-m", "jabramsja/test"], cwd=repo, capture_output=True)
        self._make_receipt(repo)

        handoff = _make_valid_handoff(staged_files=["nonexistent.py"])
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert result["status"] == "error"
        assert result["step"] == "staged_check"

    def test_missing_receipt_fails(self, tmp_path):
        import subprocess
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        env = {**__import__("os").environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=repo, capture_output=True, env=env)
        # No receipt created
        handoff = _make_valid_handoff()
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert result["status"] == "error"
        assert result["step"] == "receipt_check"


# ===========================================================================
# Phase B executor tests (Slice 3)
# ===========================================================================


class TestPhaseBPlanLoading:
    """Phase B executor loads and validates plan packets."""

    def test_load_valid_plan(self, tmp_path):
        plan = tmp_path / "plan.md"
        plan.write_text("# Plan\n\nDate: 2026-03-22\nStatus: Phase B\nPhase-A-Lock: LOCKED\n")
        result = phase_b_mod.load_plan_packet(tmp_path, "plan.md")
        assert result["phase_a_lock"] == "LOCKED"
        assert result["path"] == "plan.md"

    def test_load_missing_plan_raises(self, tmp_path):
        with pytest.raises(phase_b_mod.PhaseBExecutorError, match="not found"):
            phase_b_mod.load_plan_packet(tmp_path, "missing.md")

    def test_validate_wrong_decision(self):
        record = {"decision": "ROUTE_PHASE_A"}
        plan = {"phase_a_lock": "LOCKED"}
        valid, errors = phase_b_mod.validate_inputs(record, plan)
        assert not valid
        assert any("ROUTE_PHASE_B" in e for e in errors)

    def test_validate_unlocked_plan(self):
        record = {"decision": "ROUTE_PHASE_B"}
        plan = {"phase_a_lock": "UNLOCKED"}
        valid, errors = phase_b_mod.validate_inputs(record, plan)
        assert not valid
        assert any("LOCKED" in e for e in errors)

    def test_validate_correct_inputs(self):
        record = {"decision": "ROUTE_PHASE_B"}
        plan = {"phase_a_lock": "LOCKED"}
        valid, errors = phase_b_mod.validate_inputs(record, plan)
        assert valid


class TestPhaseBCommitHandoff:
    """Phase B executor prepares commit handoffs."""

    def test_prepare_handoff(self, tmp_path):
        path = phase_b_mod.prepare_commit_handoff(
            tmp_path,
            staged_files=["a.py"],
            commit_message="feat: test",
            pr_title="feat: test",
            pr_body="## Summary\ntest",
            head_branch="jabramsja/test",
            task_id="[TEST]",
            wave_name="test",
        )
        assert path.exists()
        handoff = json.loads(path.read_text())
        assert handoff["caller"] == "phase_b"
        assert handoff["staged_files"] == ["a.py"]
        assert handoff["pre_commit_receipt_path"] == ".agent_bus/meta/pre_commit_receipt.json"


class TestPhaseBDispatcherIntegration:
    """Dispatcher correctly routes to phase_b_executor."""

    def test_route_phase_b_dispatches(self):
        assert dispatch_mod.resolve_executor("ROUTE_PHASE_B") == "phase_b_executor"

    def test_phase_b_now_available(self):
        assert "phase_b_executor" in dispatch_mod.AVAILABLE_EXECUTORS


class TestPhaseBRunPhaseB:
    """Integration: run_phase_b with a real plan packet."""

    def test_ready_with_locked_plan(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan = repo / "reports" / "control_plane" / "test_plan.md"
        plan.write_text("# Plan\n\nDate: 2026-03-22\nStatus: Phase B\nPhase-A-Lock: LOCKED\n")

        result = phase_b_mod.run_phase_b(
            repo, "reports/control_plane/test_plan.md", verbose=True
        )
        assert result["status"] == "ready"
