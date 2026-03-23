"""Tests for Phase B executor with real implementer actor."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Load modules
_EXECUTORS_DIR = Path(__file__).resolve().parent.parent.parent / "tools" / "executors"

_pb_spec = importlib.util.spec_from_file_location(
    "phase_b_executor", _EXECUTORS_DIR / "phase_b_executor.py"
)
assert _pb_spec and _pb_spec.loader
pb_mod = importlib.util.module_from_spec(_pb_spec)
sys.modules["phase_b_executor"] = pb_mod
_pb_spec.loader.exec_module(pb_mod)

_impl_spec = importlib.util.spec_from_file_location(
    "phase_b_implementer", _EXECUTORS_DIR / "phase_b_implementer.py"
)
assert _impl_spec and _impl_spec.loader
impl_mod = importlib.util.module_from_spec(_impl_spec)
sys.modules["phase_b_implementer"] = impl_mod
_impl_spec.loader.exec_module(impl_mod)


class TestBuildImplementationPrompt:
    """Test that the implementer prompt is structured correctly."""

    def test_prompt_contains_plan_content(self, tmp_path):
        prompt = impl_mod.build_implementation_prompt(
            "# My Plan\n\nDo the thing.",
            repo_root=tmp_path,
            wave_id="test-wave",
        )
        assert "# My Plan" in prompt
        assert "Do the thing." in prompt

    def test_prompt_contains_wave_id(self, tmp_path):
        prompt = impl_mod.build_implementation_prompt(
            "plan content",
            repo_root=tmp_path,
            wave_id="my-wave-id",
        )
        assert "my-wave-id" in prompt

    def test_prompt_includes_scope_hint(self, tmp_path):
        prompt = impl_mod.build_implementation_prompt(
            "plan",
            repo_root=tmp_path,
            wave_id="w",
            scope_hint="only mu/tools/",
        )
        assert "only mu/tools/" in prompt

    def test_prompt_is_implementation_not_review(self, tmp_path):
        prompt = impl_mod.build_implementation_prompt(
            "plan", repo_root=tmp_path, wave_id="w",
        )
        assert "write code" in prompt.lower()
        assert "NOT a reviewer" in prompt


class TestInvokeImplementer:
    """Test implementer invocation with mocked subprocess."""

    def test_returns_structured_result(self, tmp_path):
        # Mock subprocess.run
        with patch("phase_b_implementer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="Implementation complete", stderr=""
            )
            result = impl_mod.invoke_implementer(
                tmp_path, "test prompt", timeout=10,
            )
            assert result["status"] == "success"
            assert result["exit_code"] == 0

    def test_timeout_returns_structured_error(self, tmp_path):
        import subprocess
        with patch("phase_b_implementer.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 10)):
            result = impl_mod.invoke_implementer(
                tmp_path, "test prompt", timeout=10,
            )
            assert result["status"] == "timeout"
            assert result["exit_code"] == -1

    def test_failure_returns_error_status(self, tmp_path):
        with patch("phase_b_implementer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="bridge error"
            )
            result = impl_mod.invoke_implementer(
                tmp_path, "test prompt", timeout=10,
            )
            assert result["status"] == "error"
            assert result["exit_code"] == 1


class TestLoadExecutorConfig:
    """Test config loading."""

    def test_missing_config_returns_defaults(self, tmp_path):
        config = impl_mod.load_executor_config(tmp_path)
        assert config["backends"]["phase_b_executor"] == "codex"

    def test_existing_config_loaded(self, tmp_path):
        config_dir = tmp_path / "mu" / "tools" / "executors"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "executor_config.json"
        config_file.write_text(json.dumps({
            "backends": {"phase_b_executor": "sonnet"},
            "model_overrides": {},
            "timeouts": {"phase_b_executor": 600},
        }))
        config = impl_mod.load_executor_config(tmp_path)
        assert config["backends"]["phase_b_executor"] == "sonnet"
        assert config["timeouts"]["phase_b_executor"] == 600


class TestPrepareCommitHandoff:
    """Test updated handoff schema."""

    def test_new_schema_fields_present(self, tmp_path):
        path = pb_mod.prepare_commit_handoff(
            tmp_path,
            wave_id="test-wave",
            task_id="[TEST]",
            wave_class="L4_ENABLER",
            target_gate_id="G8",
            files_to_stage=["file.py"],
            commit_message="test",
            pr_title="test",
            pr_body="test",
        )
        handoff = json.loads(path.read_text())
        assert handoff["wave_id"] == "test-wave"
        assert handoff["wave_class"] == "L4_ENABLER"
        assert handoff["target_gate_id"] == "G8"
        assert handoff["branch_prefix"] == "jabramsja"
        assert "hold_push" not in handoff  # Removed from new schema

    def test_structured_tracker_sync(self, tmp_path):
        path = pb_mod.prepare_commit_handoff(
            tmp_path,
            wave_id="test",
            task_id="[T]",
            wave_class="MAINTENANCE",
            target_gate_id="G8",
            tracker_sync={"wave_id": "test", "wave_class": "MAINTENANCE"},
            commit_message="test",
            pr_title="test",
            pr_body="test",
        )
        handoff = json.loads(path.read_text())
        assert "tracker_sync" in handoff
        assert handoff["tracker_sync"]["wave_class"] == "MAINTENANCE"

    def test_legacy_staged_files_fallback(self, tmp_path):
        path = pb_mod.prepare_commit_handoff(
            tmp_path,
            wave_id="test",
            task_id="[T]",
            wave_class="MAINTENANCE",
            target_gate_id="G8",
            staged_files=["legacy.py"],
            commit_message="test",
            pr_title="test",
            pr_body="test",
        )
        handoff = json.loads(path.read_text())
        assert handoff["files_to_stage"] == ["legacy.py"]

    def test_implementer_is_config_driven(self, tmp_path):
        """The implementer backend comes from executor_config.json, not hardcoded."""
        config = impl_mod.load_executor_config(tmp_path)
        backend = config.get("backends", {}).get("phase_b_executor", "codex")
        # Default is codex, but it's config-driven
        assert backend in ("codex", "sonnet", "claude")
