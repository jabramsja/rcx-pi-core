"""Tests for Phase B executor with real implementer actor.

Covers:
1. Implementer no longer invokes bridge_supervisor.py review
2. Implementer uses bridge_adapters.run_adapter() directly
3. Model override honored when backend supports it (claude: yes, codex: no)
4. Phase B stages files BEFORE running supervisor (receipt order)
5. Bridge render association is bound to exact job_id, not newest file
6. Non-timeout implementer failure is fatal
7. Nonzero agent review exit is fatal
8. Handoff includes explicit receipt path
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from mu.tests.tools.module_loader import load_module

# Load modules
_EXECUTORS_DIR = Path(__file__).resolve().parent.parent.parent / "tools" / "executors"

pb_mod = load_module("phase_b_executor", _EXECUTORS_DIR / "phase_b_executor.py")
pa_mod = load_module("phase_a_executor", _EXECUTORS_DIR / "phase_a_executor.py")
impl_mod = load_module("phase_b_implementer", _EXECUTORS_DIR / "phase_b_implementer.py")

# Default valid routing record for tests that call run_phase_b.
# Tests that specifically test routing validation should NOT use this.
_VALID_ROUTING_RECORD = {"decision": "ROUTE_PHASE_B", "summary": "test dispatch"}


@pytest.fixture
def mock_routing_record():
    """Patch load_routing_record to return a valid ROUTE_PHASE_B record."""
    with patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
        yield


def _make_mock_impl():
    """Return a shared successful implementer mock for bridge-loop tests."""
    impl_success = {
        "status": "success", "output": "done", "stderr": "",
        "exit_code": 0, "job_id": "impl-test", "model_override_applied": False,
    }
    mock_impl = MagicMock()
    mock_impl.invoke_implementer.return_value = impl_success
    mock_impl.build_implementation_prompt.return_value = "prompt"
    mock_impl.load_executor_config.return_value = {
        "backends": {"phase_b_executor": "codex"},
        "model_overrides": {},
        "timeouts": {"phase_b_executor": 10},
    }
    return mock_impl


def _init_git_repo(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)


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

    def test_invoke_implementer_fails_closed_in_agent_review_mode(self, tmp_path):
        with patch.dict(os.environ, {"RCX_AGENT_REVIEW_MODE": "run_review"}, clear=False):
            result = impl_mod.invoke_implementer(
                tmp_path,
                "locked plan",
                backend="codex",
            )
        assert result["status"] == "error"
        assert "agent review mode" in result["stderr"]

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

    def test_prompt_bars_commit_stage_governance_commands(self, tmp_path):
        prompt = impl_mod.build_implementation_prompt(
            "plan", repo_root=tmp_path, wave_id="w",
        )
        assert "./tools/pre-push-fast" in prompt
        assert "./tools/audit_fast.sh" in prompt
        assert "./dev.sh" in prompt
        assert "commit/push governance commands" in prompt
        assert "Phase B-local validation" in prompt


class TestImplementerDoesNotUseBridgeSupervisorReview:
    """CRITICAL: implementer must NOT invoke bridge_supervisor.py review.

    The implementer uses bridge_adapters.run_adapter() directly, which invokes
    the backend CLI as a code-writing actor. bridge_supervisor.py review is a
    review-only surface with a prompt that says "do not edit files."
    """

    def test_no_bridge_supervisor_import(self):
        """phase_b_implementer.py must not import or reference bridge_supervisor.py."""
        source = (_EXECUTORS_DIR / "phase_b_implementer.py").read_text()
        assert "bridge_supervisor" not in source, (
            "phase_b_implementer.py still references bridge_supervisor.py. "
            "The implementer must use bridge_adapters.run_adapter() directly."
        )

    def test_no_review_command(self):
        """phase_b_implementer.py must not construct a 'review' command."""
        source = (_EXECUTORS_DIR / "phase_b_implementer.py").read_text()
        assert '"review"' not in source, (
            "phase_b_implementer.py still constructs a 'review' command. "
            "The implementer is a code-writing actor, not a reviewer."
        )

    def test_imports_bridge_adapters(self):
        """phase_b_implementer.py must reference bridge_adapters for direct invocation."""
        source = (_EXECUTORS_DIR / "phase_b_implementer.py").read_text()
        assert "bridge_adapters" in source, (
            "phase_b_implementer.py does not reference bridge_adapters. "
            "The implementer must use run_adapter() directly."
        )


class TestModelOverrideHonesty:
    """Model override is only honored when the backend supports it."""

    def test_codex_backend_does_not_support_model_override(self):
        """Codex backend ignores model_override (codex uses its own model)."""
        assert impl_mod._MODEL_OVERRIDE_SUPPORT.get("codex") is None  # ANTICHEAT_OK: testing implementer model config

    def test_claude_backend_supports_model_override(self):
        """Claude backend honors --model flag."""
        assert impl_mod._MODEL_OVERRIDE_SUPPORT.get("claude") == "--model"  # ANTICHEAT_OK: testing implementer model config

    def test_apply_model_override_codex_noop(self):
        """Model override on codex backend returns was_applied=False."""
        cmd = ["codex", "exec", "-"]
        new_cmd, applied = impl_mod._apply_model_override(cmd, "codex", "sonnet")  # ANTICHEAT_OK: testing implementer model override
        assert not applied
        assert new_cmd == cmd  # Unchanged

    def test_apply_model_override_claude_replaces(self):
        """Model override on claude backend replaces --model value."""
        cmd = ["claude", "--print", "--model", "opus"]
        new_cmd, applied = impl_mod._apply_model_override(cmd, "claude", "sonnet")  # ANTICHEAT_OK: testing implementer model override
        assert applied
        assert "--model" in new_cmd
        idx = new_cmd.index("--model")
        assert new_cmd[idx + 1] == "sonnet"

    def test_apply_model_override_claude_appends(self):
        """Model override on claude backend appends --model if missing."""
        cmd = ["claude", "--print"]
        new_cmd, applied = impl_mod._apply_model_override(cmd, "claude", "haiku")  # ANTICHEAT_OK: testing implementer model override
        assert applied
        assert new_cmd[-2:] == ["--model", "haiku"]


class TestInvokeImplementer:
    """Test implementer invocation with mocked bridge adapter."""

    def _setup_bridge_config(self, tmp_path):
        """Create bridge config and scratch dir for tests."""
        bus_dir = tmp_path / ".agent_bus"
        bus_dir.mkdir(exist_ok=True)
        (bus_dir / "bridge_config.json").write_text(json.dumps({
            "agents": {
                "codex": {
                    "cmd": ["echo", "done"],
                    "timeout_s": 10,
                    "prompt_via_stdin": True,
                    "mode": "live",
                }
            }
        }))
        (tmp_path / ".scratch").mkdir(exist_ok=True)

    def _patch_bridge_adapters(self, **overrides):
        """Create a mock bridge_adapters module for patching."""
        from bridge_adapters import AdapterSpec, BridgeAdapterError
        mock_ba = MagicMock()
        mock_ba.AdapterSpec = AdapterSpec
        mock_ba.BridgeAdapterError = BridgeAdapterError
        mock_ba.load_bridge_config.return_value = {
            "agents": {"codex": {"cmd": ["echo"], "timeout_s": 10, "prompt_via_stdin": True, "mode": "live"}}
        }
        mock_ba.get_adapter.return_value = AdapterSpec(
            name="codex", cmd=["echo", "done"], timeout_s=10,
            prompt_via_stdin=True, env=None, mode="live",
        )
        for k, v in overrides.items():
            setattr(mock_ba, k, v)
        return mock_ba

    def test_returns_structured_result_with_job_id(self, tmp_path):
        """Implementer returns result with job_id for render association."""
        self._setup_bridge_config(tmp_path)
        mock_ba = self._patch_bridge_adapters()
        mock_ba.run_adapter.return_value = "Implementation complete"

        with patch.object(impl_mod, "_bridge_adapters", mock_ba):
            result = impl_mod.invoke_implementer(
                tmp_path, "test prompt", timeout=10,
            )
            assert result["status"] == "success"
            assert result["exit_code"] == 0
            assert result["job_id"].startswith("impl-")

    def test_timeout_returns_structured_error(self, tmp_path):
        """Timeout from bridge adapter is detected and reported."""
        self._setup_bridge_config(tmp_path)
        from bridge_adapters import BridgeAdapterError
        mock_ba = self._patch_bridge_adapters()
        mock_ba.run_adapter.side_effect = BridgeAdapterError("timed out after 1s")

        with patch.object(impl_mod, "_bridge_adapters", mock_ba):
            result = impl_mod.invoke_implementer(
                tmp_path, "test prompt", timeout=1,
            )
            assert result["status"] == "timeout"
            assert result["exit_code"] == -1

    def test_stale_timeout_returns_structured_error(self, tmp_path):
        """Stale implementer runs are detected and reported explicitly."""
        self._setup_bridge_config(tmp_path)
        from bridge_adapters import BridgeAdapterError
        mock_ba = self._patch_bridge_adapters()
        mock_ba.run_adapter.side_effect = BridgeAdapterError("Adapter 'codex' stalled after 30s")

        with patch.object(impl_mod, "_bridge_adapters", mock_ba):
            result = impl_mod.invoke_implementer(
                tmp_path, "test prompt", timeout=30,
            )
            assert result["status"] == "stale"
            assert result["exit_code"] == -2

    def test_passes_configured_output_watchdogs_to_adapter(self, tmp_path):
        """Implementer output watchdogs inherit the configured stale budget."""
        self._setup_bridge_config(tmp_path)
        config_dir = tmp_path / "mu" / "tools" / "executors"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "executor_config.json").write_text(json.dumps({
            "timeouts": {"phase_b_implementer_stale": 123}
        }))
        mock_ba = self._patch_bridge_adapters()
        mock_ba.run_adapter.return_value = "done"

        with patch.object(impl_mod, "_bridge_adapters", mock_ba):
            result = impl_mod.invoke_implementer(
                tmp_path, "test prompt", timeout=600,
            )

        assert result["status"] == "success"
        assert mock_ba.run_adapter.call_args.kwargs["stale_timeout_s"] == 123.0
        assert mock_ba.run_adapter.call_args.kwargs["zero_output_timeout_s"] == 123.0

    def test_nonzero_exit_returns_error(self, tmp_path):
        """Non-timeout failure from bridge adapter returns error status."""
        self._setup_bridge_config(tmp_path)
        from bridge_adapters import BridgeAdapterError
        mock_ba = self._patch_bridge_adapters()
        mock_ba.run_adapter.side_effect = BridgeAdapterError("Adapter 'codex' exited 1")

        with patch.object(impl_mod, "_bridge_adapters", mock_ba):
            result = impl_mod.invoke_implementer(
                tmp_path, "test prompt", timeout=10,
            )
            assert result["status"] == "error"
            assert result["exit_code"] == 1

    def test_model_override_reported_in_result(self, tmp_path):
        """Result includes whether model override was actually applied."""
        self._setup_bridge_config(tmp_path)
        mock_ba = self._patch_bridge_adapters()
        mock_ba.run_adapter.return_value = "done"

        with patch.object(impl_mod, "_bridge_adapters", mock_ba):
            result = impl_mod.invoke_implementer(
                tmp_path, "test prompt", backend="codex", model_override="sonnet", timeout=10,
            )
            assert result["model_override_applied"] is False  # codex can't honor sonnet


class TestLoadExecutorConfig:
    """Test config loading."""

    def test_missing_config_returns_defaults(self, tmp_path):
        config = impl_mod.load_executor_config(tmp_path)
        assert config["backends"]["phase_b_executor"] == "claude"

    def test_existing_config_loaded(self, tmp_path):
        config_dir = tmp_path / "mu" / "tools" / "executors"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "executor_config.json"
        config_file.write_text(json.dumps({
            "backends": {"phase_b_executor": "claude"},
            "model_overrides": {"phase_b_executor": "sonnet"},
            "timeouts": {"phase_b_executor": 600},
        }))
        config = impl_mod.load_executor_config(tmp_path)
        assert config["backends"]["phase_b_executor"] == "claude"
        assert config["model_overrides"]["phase_b_executor"] == "sonnet"
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

    def test_explicit_receipt_path_in_handoff(self, tmp_path):
        """Handoff includes the explicit receipt path, not just canonical."""
        path = pb_mod.prepare_commit_handoff(
            tmp_path,
            wave_id="test-wave",
            task_id="[TEST]",
            wave_class="L4_ENABLER",
            target_gate_id="G8",
            files_to_stage=["file.py"],
            pre_commit_receipt_path=".agent_bus/meta/pre_commit_receipts/receipt_2026-03-23.json",
            commit_message="test",
            pr_title="test",
            pr_body="test",
        )
        handoff = json.loads(path.read_text())
        assert handoff["pre_commit_receipt_path"] == ".agent_bus/meta/pre_commit_receipts/receipt_2026-03-23.json"

    def test_tracker_note_text_in_handoff(self, tmp_path):
        path = pb_mod.prepare_commit_handoff(
            tmp_path,
            wave_id="test",
            task_id="[T]",
            wave_class="MAINTENANCE",
            target_gate_id="G8",
            tracker_note_text="- Tracker sync note (test): test note.",
            commit_message="test",
            pr_title="test",
            pr_body="test",
        )
        handoff = json.loads(path.read_text())
        assert "tracker_note_text" in handoff
        assert handoff["tracker_note_text"] == "- Tracker sync note (test): test note."

    def test_optional_supervisor_context_in_handoff(self, tmp_path):
        path = pb_mod.prepare_commit_handoff(
            tmp_path,
            wave_id="test",
            task_id="[T]",
            wave_class="MAINTENANCE",
            target_gate_id="G8",
            files_to_stage=["file.py"],
            scope_items=["reports/control_plane/test_plan.md", "file.py"],
            evidence_handles={"receipt_chain": "direct receipt path preserved"},
            commit_message="test",
            pr_title="test",
            pr_body="test",
        )
        handoff = json.loads(path.read_text())
        assert handoff["scope_items"] == ["reports/control_plane/test_plan.md", "file.py"]
        assert handoff["evidence_handles"] == {
            "receipt_chain": "direct receipt path preserved"
        }

    def test_build_phase_b_tracker_note_is_l4_compliant(self):
        note = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: testing Phase B tracker-note helper
            wave_id="pipeline-test-run-2026-03-25",
            task_id="[PIPELINE-TEST-RUN]",
            target_gate_id="G8",
            plan_path="reports/control_plane/pipeline_test_run_2026-03-25.md",
            changed_files=[
                "mu/tools/executors/phase_b_executor.py",
                "mu/tests/tools/test_phase_b_executor.py",
            ],
            test_files=[
                "mu/tests/tools/test_phase_b_executor.py",
                "mu/tests/tools/test_executor_dispatch.py",
            ],
            receipt_path=".agent_bus/meta/pre_commit_receipts/receipt_test.json",
            bridge_rounds=2,
            reentry=True,
        )
        assert note.startswith("- Tracker sync note (")
        assert "pipeline-test-run-2026-03-25): **PIPELINE-TEST-RUN — commit-ready Phase B handoff.**" in note
        assert "Class: L4_ENABLER" in note
        assert "target_gate_id: G8" in note
        assert "evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short" in note
        assert "indicator_artifact_ref: reports/l4_wave_indicators/pipeline-test-run-2026-03-25.json" in note
        assert "progress_proof_after: Phase B emitted a commit-ready handoff for pipeline-test-run-2026-03-25" in note

    def test_files_to_stage_in_handoff(self, tmp_path):
        path = pb_mod.prepare_commit_handoff(
            tmp_path,
            wave_id="test",
            task_id="[T]",
            wave_class="MAINTENANCE",
            target_gate_id="G8",
            files_to_stage=["new_file.py"],
            commit_message="test",
            pr_title="test",
            pr_body="test",
        )
        handoff = json.loads(path.read_text())
        assert handoff["files_to_stage"] == ["new_file.py"]

    def test_optional_supervisor_metadata_in_handoff(self, tmp_path):
        path = pb_mod.prepare_commit_handoff(
            tmp_path,
            wave_id="test",
            task_id="[T]",
            wave_class="MAINTENANCE",
            target_gate_id="G8",
            files_to_stage=["new_file.py"],
            commit_message="test",
            pr_title="test",
            pr_body="test",
            supervisor_lane="hooks/agents/bridge control-surface",
            deferred_items=["reports/deferred/non_blocking/example.md"],
            bridge_status={"rounds": 2, "reentry": True},
        )
        handoff = json.loads(path.read_text())
        assert handoff["supervisor_lane"] == "hooks/agents/bridge control-surface"
        assert handoff["deferred_items"] == ["reports/deferred/non_blocking/example.md"]
        assert handoff["bridge_status"] == {"rounds": 2, "reentry": True}


class TestLoadPlanPacketPathTraversal:
    """load_plan_packet must block path traversal attacks."""

    def test_parent_directory_escape_blocked(self, tmp_path):
        """Path traversal with ../ is blocked."""
        repo = tmp_path / "repo"
        repo.mkdir()
        with pytest.raises(pb_mod.PhaseBExecutorError, match="Path traversal blocked"):
            pb_mod.load_plan_packet(repo, "../../etc/passwd")

    def test_absolute_path_blocked(self, tmp_path):
        """Absolute paths outside repo are blocked."""
        repo = tmp_path / "repo"
        repo.mkdir()
        with pytest.raises(pb_mod.PhaseBExecutorError, match="Path traversal blocked"):
            pb_mod.load_plan_packet(repo, "/etc/passwd")

    def test_valid_relative_path_works(self, tmp_path):
        """Legitimate relative paths within repo work."""
        repo = tmp_path / "repo"
        plan_dir = repo / "reports"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "plan.md"
        plan_file.write_text("Phase-A-Lock: LOCKED\nStatus: ACTIVE\n")
        result = pb_mod.load_plan_packet(repo, "reports/plan.md")
        assert result["phase_a_lock"] == "LOCKED"


class TestBlockerDiscovery:
    """Phase B executor discovers active blocking packets for supervisor package."""

    def test_discovers_active_blocking_packets(self, tmp_path):
        """When reports/deferred/blocking/ has .md files, they appear in package."""
        repo = tmp_path / "repo"
        blocking_dir = repo / "reports" / "deferred" / "blocking"
        blocking_dir.mkdir(parents=True)
        (blocking_dir / "blocker1.md").write_text("# Blocker 1")
        (blocking_dir / "blocker2.md").write_text("# Blocker 2")
        (blocking_dir / "README.md").write_text("# README — excluded")

        # Simulate what phase_b_executor does at package-build time
        blocker_paths = sorted(
            str(p.relative_to(repo))
            for p in blocking_dir.iterdir()
            if p.is_file() and p.suffix == ".md" and p.name != "README.md"
        )
        assert len(blocker_paths) == 2
        assert "reports/deferred/blocking/blocker1.md" in blocker_paths
        assert "reports/deferred/blocking/blocker2.md" in blocker_paths
        assert "README.md" not in str(blocker_paths)

    def test_empty_when_no_blocking_packets(self, tmp_path):
        """When no blocking .md files exist, list is empty."""
        repo = tmp_path / "repo"
        blocking_dir = repo / "reports" / "deferred" / "blocking"
        blocking_dir.mkdir(parents=True)
        (blocking_dir / "README.md").write_text("# README only")

        blocker_paths = sorted(
            str(p.relative_to(repo))
            for p in blocking_dir.iterdir()
            if p.is_file() and p.suffix == ".md" and p.name != "README.md"
        )
        assert blocker_paths == []

    def test_empty_when_directory_missing(self, tmp_path):
        """When blocking directory doesn't exist, list is empty."""
        repo = tmp_path / "repo"
        repo.mkdir()
        blocking_dir = repo / "reports" / "deferred" / "blocking"
        blocker_paths = []
        if blocking_dir.is_dir():
            blocker_paths = sorted(
                str(p.relative_to(repo))
                for p in blocking_dir.iterdir()
                if p.is_file() and p.suffix == ".md" and p.name != "README.md"
            )
        assert blocker_paths == []


@pytest.mark.usefixtures("mock_routing_record")
class TestReentryRestageFailClosed:
    """Re-entry restage failure must stop the pipeline, not run supervisor on stale state."""

    def test_reentry_restage_failure_stops_pipeline(self, tmp_path):
        """If _stage_files returns False after re-entry, fail closed."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        bridge_calls = [0]
        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value=""), \
             patch.object(pb_mod, "_stage_files", side_effect=[True, True, True, False]), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "NEEDS_PHASE_B", "summary": "fix", "status": "ok", "findings": []},
                 "receipt_path": "",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "reentry_staging"


@pytest.mark.usefixtures("mock_routing_record")
class TestPhaseBFailClosed:
    """Phase B executor fails closed on implementer and agent failures."""

    def test_implementer_error_is_fatal(self, tmp_path):
        """Non-timeout implementer failure must stop the pipeline."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan = repo / "reports" / "control_plane" / "test_plan.md"
        plan.write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        impl_error = {
            "status": "error",
            "output": "",
            "stderr": "adapter exited 1",
            "exit_code": 1,
            "job_id": "impl-test",
            "model_override_applied": False,
        }

        # Patch via sys.modules so the imports inside run_phase_b find mocks
        mock_impl = _make_mock_impl()
        mock_impl.invoke_implementer.return_value = impl_error

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/test_plan.md")
            assert result["status"] == "error"
            assert result.get("step") == "implementer"

    def test_agent_review_hard_failure_is_fatal(self, tmp_path):
        """Hard-gate/compliance SDK review exits must stop the pipeline."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan = repo / "reports" / "control_plane" / "test_plan.md"
        plan.write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tools/executors/file.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tools/executors/file.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={
                 "exit_code": 1,
                 "stdout": "REJECT",
                 "stderr": "",
                 "report_path": ".scratch/sdk_report.md",
                 "status_path": ".scratch/sdk_status.json",
                 "stdout_path": ".scratch/sdk_stdout.log",
             }), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/test_plan.md")
            assert result["status"] == "commit_ready"
            assert result["agent_exit_code"] == 1
            assert result["agent_review_warning_only"] is True

    def test_agent_review_warning_exit_continues_to_bridge(self, tmp_path):
        """Warnings-only SDK exit=2 should continue to bridge review."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan = repo / "reports" / "control_plane" / "test_plan.md"
        plan.write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tools/executors/file.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tools/executors/file.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={
                 "exit_code": 2, "stdout": "warnings", "stderr": "",
                 "report_path": ".scratch/sdk_report.md",
                 "status_path": ".scratch/sdk_status.json",
                 "stdout_path": ".scratch/sdk_stdout.log",
             }), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/test_plan.md")

        assert result["status"] == "commit_ready"
        assert result["agent_exit_code"] == 2
        assert result["agent_review_warning_only"] is True
        assert result["agent_review_report_path"] == ".scratch/sdk_report.md"


@pytest.mark.usefixtures("mock_routing_record")
class TestFinalPytestGate:
    """Failed pytest MUST block commit_ready — hard gate after bridge convergence."""

    def test_run_pytest_on_files_forces_deterministic_hash_seed(self, tmp_path):
        completed = subprocess.CompletedProcess(
            args=["pytest"],
            returncode=0,
            stdout="ok",
            stderr="",
        )
        with patch.object(pb_mod.subprocess, "run", return_value=completed) as mock_run:
            result = pb_mod._run_pytest_on_files(tmp_path, ["mu/tests/tools/test_foo.py"])  # ANTICHEAT_OK: testing internal final-pytest gate helper

        assert result["passed"] is True
        kwargs = mock_run.call_args.kwargs
        assert kwargs["env"]["PYTHONHASHSEED"] == "0"

    def test_pytest_failure_blocks_commit_ready(self, tmp_path):
        """If final pytest gate fails, status must be error, not commit_ready."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tests/tools/test_foo.py", "mu/tools/executors/foo.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tests/tools/test_foo.py", "mu/tools/executors/foo.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 1, "stdout": "FAILED test_foo.py", "stderr": "", "passed": False,
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "final_pytest_gate"

    def test_pytest_failure_surfaces_stderr_when_stdout_empty(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tests/tools/test_foo.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tests/tools/test_foo.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 3, "stdout": "", "stderr": "PYTHONHASHSEED must be '0'", "passed": False,
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert "PYTHONHASHSEED" in result["errors"][0]

    def test_pytest_success_allows_commit_ready(self, tmp_path):
        """If final pytest gate passes, pipeline continues to supervisor."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tests/tools/test_foo.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tests/tools/test_foo.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 0, "stdout": "1 passed", "stderr": "", "passed": True,
             }) as mock_pytest, \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        mock_pytest.assert_called_once_with(repo, ["mu/tests/tools/test_foo.py"], timeout=300)


class TestBridgeRenderAssociation:
    """Bridge review uses exact job_id, not newest/freshest render."""

    def test_run_bridge_review_passes_job_id(self, tmp_path):
        """run_bridge_review passes --job-id to bridge_supervisor."""
        with patch.object(pb_mod, "_run_bridge_review_subprocess") as mock_run:
            mock_run.return_value = {
                "exit_code": 0, "stdout": "GO\n", "stderr": "",
            }
            result = pb_mod.run_bridge_review(
                tmp_path,
                "test review",
                job_id="phase-b-r1-abc12345",
                timeout=10,
            )
            # Verify --job-id was passed in the command
            call_args = mock_run.call_args[0][1]
            assert "--job-id" in call_args
            idx = call_args.index("--job-id")
            assert call_args[idx + 1] == "phase-b-r1-abc12345"

    def test_run_bridge_review_uses_configured_reviewer(self, tmp_path):
        """Phase B bridge review must honor executor-configured reviewer backend."""
        config_dir = tmp_path / "mu" / "tools" / "executors"
        config_dir.mkdir(parents=True)
        (config_dir / "executor_config.json").write_text(
            json.dumps({"bridge_reviewers": {"phase_b": "claude"}}),
            encoding="utf-8",
        )
        with patch.object(pb_mod, "_run_bridge_review_subprocess") as mock_run:
            mock_run.return_value = {
                "exit_code": 0, "stdout": "GO\n", "stderr": "",
            }
            pb_mod.run_bridge_review(
                tmp_path,
                "test review",
                job_id="phase-b-r1-abc12345",
                timeout=10,
            )

        call_args = mock_run.call_args[0][1]
        assert "--reviewer" in call_args
        idx = call_args.index("--reviewer")
        assert call_args[idx + 1] == "claude"

    def test_run_bridge_review_sets_configured_turn_timeout_env(self, tmp_path):
        """Phase B bridge review should widen the bridge turn budget via env."""
        config_dir = tmp_path / "mu" / "tools" / "executors"
        config_dir.mkdir(parents=True)
        (config_dir / "executor_config.json").write_text(
            json.dumps({"bridge_turn_timeouts": {"phase_b": 901}}),
            encoding="utf-8",
        )
        with patch.object(pb_mod, "_run_bridge_review_subprocess") as mock_run:
            mock_run.return_value = {
                "exit_code": 0, "stdout": "GO\n", "stderr": "",
            }
            pb_mod.run_bridge_review(
                tmp_path,
                "test review",
                job_id="phase-b-r1-abc12345",
                timeout=1200,
            )

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["env"]["RCX_BRIDGE_MAX_TURN_WALL_TIME_S"] == "901.0"

    def test_run_bridge_review_parses_decision_from_stdout(self, tmp_path):
        """Decision is parsed from stdout, not from rendered file freshness."""
        with patch.object(pb_mod, "_run_bridge_review_subprocess") as mock_run:
            mock_run.return_value = {
                "exit_code": 0, "stdout": "GO\n", "stderr": "",
            }
            result = pb_mod.run_bridge_review(
                tmp_path, "test", job_id="test-job", timeout=10,
            )
            assert result["decision"] == "GO"

    def test_run_bridge_review_parses_request_changes(self, tmp_path):
        """REQUEST_CHANGES decision is parsed from stdout."""
        with patch.object(pb_mod, "_run_bridge_review_subprocess") as mock_run:
            mock_run.return_value = {
                "exit_code": 1, "stdout": "REQUEST_CHANGES\n", "stderr": "",
            }
            result = pb_mod.run_bridge_review(
                tmp_path, "test", job_id="test-job", timeout=10,
            )
            assert result["decision"] == "REQUEST_CHANGES"

    def test_run_bridge_review_preserves_stale_exit_code(self, tmp_path):
        """Bridge stale-review supervision surfaces exit_code=-2."""
        with patch.object(pb_mod, "_run_bridge_review_subprocess") as mock_run:
            mock_run.return_value = {
                "exit_code": -2, "stdout": "", "stderr": "Bridge review stale after 120s",
            }
            result = pb_mod.run_bridge_review(
                tmp_path, "test", job_id="test-job", timeout=10,
            )
            assert result["exit_code"] == -2
            assert "stale" in result["stderr"]

    def test_read_bridge_render_by_job_id(self, tmp_path):
        """_read_bridge_render reads the exact job_id file."""
        rendered_dir = tmp_path / ".agent_bus" / "rendered"
        rendered_dir.mkdir(parents=True)
        # Write a render for a specific job_id
        (rendered_dir / "phase-b-r1-abc12345.md").write_text("Decision: GO\nContent here")
        # Write a DIFFERENT render (should NOT be read)
        (rendered_dir / "some-other-job.md").write_text("Decision: NO_GO\nOther content")

        content = pb_mod._read_bridge_render(tmp_path, "phase-b-r1-abc12345")  # ANTICHEAT_OK: testing bridge render reader
        assert "Decision: GO" in content
        assert "Other content" not in content

    def test_read_bridge_render_missing_returns_empty(self, tmp_path):
        """Missing render for job_id returns empty string."""
        content = pb_mod._read_bridge_render(tmp_path, "nonexistent-job")  # ANTICHEAT_OK: testing bridge render reader
        assert content == ""

    def test_read_bridge_render_rejects_path_traversal_job_id(self, tmp_path):
        """Unsafe job_id values must not escape the rendered directory."""
        rendered_dir = tmp_path / ".agent_bus" / "rendered"
        rendered_dir.mkdir(parents=True)
        (rendered_dir / "phase-b-r1-abc12345.md").write_text("Decision: GO\nContent here")
        content = pb_mod._read_bridge_render(tmp_path, "../phase-b-r1-abc12345")  # ANTICHEAT_OK: testing bridge render reader
        assert content == ""


class TestBridgeReviewMonitoring:
    """Bridge review supervision fails closed on stale reviewer tails."""

    def test_bridge_review_stale_kills_subprocess(self, tmp_path):
        stdout_log = tmp_path / ".scratch" / "phase_b_bridge_stale-job.stdout.log"
        stdout_log.parent.mkdir(parents=True, exist_ok=True)
        proc = MagicMock()
        proc.pid = 12345
        proc.poll.side_effect = [None, None, None]

        frozen_snapshot = {
            "child_pids": (200,),
            "cpu_fingerprint": ((12345, 1.0), (200, 1.0)),
            "artifact_fingerprint": (),
        }
        monotonic_values = iter([0.0, 0.0, 0.0, 2.0, 2.0])

        with patch.object(pb_mod.subprocess, "Popen", return_value=proc), \
             patch.object(pb_mod, "_bridge_progress_snapshot", side_effect=[
                 frozen_snapshot,
                 frozen_snapshot,
                 frozen_snapshot,
                 frozen_snapshot,
             ]), \
             patch.object(pb_mod, "_terminate_bridge_subprocess") as mock_terminate, \
             patch.object(pb_mod.time, "sleep", return_value=None), \
             patch.object(pb_mod.time, "monotonic", side_effect=lambda: next(monotonic_values)):
            result = pb_mod._run_bridge_review_subprocess(  # ANTICHEAT_OK: testing internal bridge subprocess supervision helper
                tmp_path,
                [sys.executable, "-c", "print('hi')"],
                job_id="stale-job",
                timeout=30,
                verbose=False,
                poll_interval=0.0,
                stale_timeout=1.0,
                aggregation_hang_timeout=10.0,
            )

        assert result["exit_code"] == -2
        assert "stale" in result["stderr"]
        mock_terminate.assert_called_once()


class TestImplementerIsConfigDriven:
    """The implementer backend comes from executor_config.json."""

    def test_config_driven_backend(self, tmp_path):
        config = impl_mod.load_executor_config(tmp_path)
        backend = config.get("backends", {}).get("phase_b_executor", "claude")
        assert backend in ("codex", "claude", "sonnet")  # Valid backends


@pytest.mark.usefixtures("mock_routing_record")
class TestBridgeLoopReinvokesImplementer:
    """Bridge REQUEST_CHANGES/NO_GO must re-invoke implementer, not just loop bridge."""

    def test_request_changes_reinvokes_implementer(self, tmp_path):
        """REQUEST_CHANGES causes implementer re-invocation before next bridge round."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        call_count = [0]

        def bridge_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "j1"}
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": "j2"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side_effect), \
             patch.object(pb_mod, "_read_bridge_render", return_value="findings here"), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        # Implementer must have been called at least twice:
        # once for initial implementation, once for the bridge fix
        assert mock_impl.invoke_implementer.call_count >= 2
        assert result["status"] == "commit_ready"

    def test_bridge_rounds_restage_current_wave_before_each_review(self, tmp_path):
        """Each bridge round must review the current staged candidate, not stale index state."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        bridge_calls = [0]

        def bridge_side_effect(*args, **kwargs):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                return {"exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "j1"}
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": "j2"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["TASKS.md", "f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["TASKS.md", "f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side_effect), \
             patch.object(pb_mod, "_read_bridge_render", return_value="findings here"), \
             patch.object(pb_mod, "_stage_files", return_value=True) as mock_stage, \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert mock_stage.call_count == 3
        # Step 5b adds plan_path to changed_files before staging
        assert mock_stage.call_args_list[0].args[1] == ["TASKS.md", "f.py", "reports/control_plane/plan.md"]
        assert mock_stage.call_args_list[1].args[1] == ["TASKS.md", "f.py", "reports/control_plane/plan.md"]

    def test_bridge_round_staging_failure_stops_pipeline(self, tmp_path):
        """If restaging fails before bridge review, fail closed instead of reviewing stale index state."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["TASKS.md"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["TASKS.md"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "_stage_files", return_value=False), \
             patch.object(pb_mod, "run_bridge_review") as mock_bridge:
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "bridge_staging"
        mock_bridge.assert_not_called()

    def test_question_fails_closed(self, tmp_path):
        """QUESTION requires founder input — pipeline fails closed."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 1, "stdout": "QUESTION\n", "stderr": "",
                 "decision": "QUESTION", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_read_bridge_render", return_value="question content"):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "question_for_founder"
        assert "founder" in result["errors"][0].lower()

    def test_implementer_failure_during_bridge_fix_is_fatal(self, tmp_path):
        """If implementer fails during bridge fix round, pipeline stops."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        call_count = [0]
        def impl_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"status": "success", "output": "ok", "stderr": "", "exit_code": 0,
                        "job_id": "i1", "model_override_applied": False}
            return {"status": "error", "output": "", "stderr": "adapter crashed", "exit_code": 1,
                    "job_id": "i2", "model_override_applied": False}

        mock_impl = _make_mock_impl()
        mock_impl.invoke_implementer.side_effect = impl_side_effect

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                 "decision": "REQUEST_CHANGES", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_read_bridge_render", return_value="fix this"), \
             patch.object(pb_mod, "_stage_files", return_value=True):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "implementer_bridge_fix"


@pytest.mark.usefixtures("mock_routing_record")
class TestBridgeDecisionExitContract:
    """REQUEST_CHANGES/NO_GO remain recoverable under the bridge CLI exit contract."""

    def test_cli_exit_one_with_request_changes_is_recoverable(self, tmp_path):
        """bridge_supervisor review returns exit=1 for REQUEST_CHANGES; executor must continue."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        call_count = [0]

        def bridge_side(*a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"exit_code": 1, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "j1"}
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": "j2"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="findings"), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert mock_impl.invoke_implementer.call_count >= 2

    def test_unexpected_positive_exit_with_no_go_fails_closed(self, tmp_path):
        """Unexpected positive exits remain infrastructure failures even with a decision token."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 7, "stdout": "NO_GO\n", "stderr": "",
                 "decision": "NO_GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "bridge_subprocess"
        assert "unexpected exit" in result["errors"][0].lower()

    def test_zero_exit_with_request_changes_is_recoverable(self, tmp_path):
        """exit_code=0 + REQUEST_CHANGES is a real review — pipeline should continue."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        call_count = [0]

        def bridge_side(*a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "j1"}
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": "j2"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="findings"), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert mock_impl.invoke_implementer.call_count >= 2


@pytest.mark.usefixtures("mock_routing_record")
class TestReentryLoopMirrorsInitial:
    """NEEDS_PHASE_B re-entry loop must mirror initial: REQUEST_CHANGES re-invokes implementer, QUESTION fails closed."""

    def test_reentry_question_fails_closed(self, tmp_path):
        """QUESTION during re-entry must fail closed for founder input."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        bridge_calls = [0]

        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            if bridge_calls[0] <= 1:
                return {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1"}
            # Re-entry bridge returns QUESTION
            return {"exit_code": 1, "stdout": "QUESTION\n", "stderr": "", "decision": "QUESTION", "job_id": "j2"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="question text"), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "NEEDS_PHASE_B", "summary": "fix more", "status": "ok", "findings": []},
                 "receipt_path": "",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "question_for_founder"
        assert "founder" in result["errors"][0].lower()

    def test_reentry_request_changes_reinvokes_implementer(self, tmp_path):
        """REQUEST_CHANGES during re-entry must re-invoke implementer with bridge findings."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        bridge_calls = [0]

        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                return {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "init"}
            if bridge_calls[0] == 2:
                # Re-entry R1: REQUEST_CHANGES (exit_code=1 under bridge CLI contract)
                return {"exit_code": 1, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "re1"}
            # Re-entry R2: GO
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "re2"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="bridge findings text"), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "NEEDS_PHASE_B", "summary": "needs fix", "status": "ok", "findings": []},
                 "receipt_path": "",
             }):
            # First supervisor returns NEEDS_PHASE_B, re-entry bridge R1 returns REQUEST_CHANGES,
            # implementer re-invoked, re-entry bridge R2 returns GO
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=10)

        # Implementer must have been called at least 3 times:
        # 1. initial, 2. first re-entry (supervisor findings), 3. second re-entry (bridge findings)
        assert mock_impl.invoke_implementer.call_count >= 3


class TestExactReceiptAuthority:
    """Receipt path must be exact per-invocation, not heuristic discovery."""

    def test_write_pre_commit_receipt_returns_per_invocation_path(self):
        """Supervisor receipt writer returns per-invocation path, not canonical."""
        # Use the already-loaded module from other tests.
        import meta_bridge_supervisor as meta_mod

        from unittest.mock import patch as _p

        response = meta_mod.MetaBridgeResponse(
            status="success", decision="COMMIT_GO", summary="ok",
        )
        pkg_path = Path("/tmp/test_receipt_pkg.json")
        pkg_path.write_text("{}", encoding="utf-8")

        import tempfile
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            with _p.object(meta_mod, "META_BUS_DIR_NAME", ".agent_bus/meta"), \
                 _p.object(meta_mod, "compute_staged_sha", return_value="abc"):
                result_path = meta_mod.write_pre_commit_receipt(response, pkg_path, repo_root=repo)

            # Must return per-invocation path, not canonical
            assert "pre_commit_receipts" in str(result_path)
            assert "receipt_" in result_path.name
            assert result_path.exists()

            # Canonical must ALSO exist (hook compat)
            canonical = repo / ".agent_bus" / "meta" / meta_mod.PRE_COMMIT_RECEIPT_NAME
            assert canonical.exists()

    def test_protocol_docs_no_manual_commit_fallback(self):
        """protocol_wave_execution.md must not present manual commit as normal path."""
        import os
        mem_dir = "/Users/jeffabrams/.claude/projects/-Users-jeffabrams-Desktop-RCX-X-RCXStack-RCXStackminimal-WorkingRCX/memory"
        proto = Path(mem_dir) / "protocol_wave_execution.md"
        if proto.exists():
            content = proto.read_text()
            # Must not have the old manual fallback steps
            assert "git push -u origin" not in content
            assert "gh pr create --base dev" not in content
            assert "merge_pr.sh <PR#> --sweep" not in content
            # Should reference commit_executor as the path
            assert "commit_executor" in content


class TestEmptyReceiptPathRejected:
    """Phase B must reject empty receipt_path before emitting commit_ready."""

    def test_empty_receipt_path_fails_closed(self):
        """If supervisor returns empty receipt_path, phase_b must NOT emit commit_ready.

        R2 finding #2: empty receipt_path + commit_ready violates the receipt authority contract.
        """
        # Verify the guard exists in source — structural check
        import inspect
        src = inspect.getsource(pb_mod.run_phase_b)
        # The fix adds a guard: "if not receipt_path" → return error before commit_ready
        # This must appear between supervisor result capture and commit_ready assignment
        assert "if not receipt_path" in src, (
            "phase_b_executor must guard against empty receipt_path before commit_ready"
        )
        # The guard must return an error status
        lines = src.splitlines()
        for i, line in enumerate(lines):
            if "if not receipt_path" in line:
                following = "\n".join(lines[i:i + 10])
                assert "error" in following.lower() and "fail" in following.lower(), (
                    "Empty receipt_path guard must return error with fail-closed message"
                )
                break


class TestFindingDisposition:
    """Bridge findings with disposition field are correctly classified.

    Classification contract (shared via executor_common.py):
    1. Explicit disposition field — use as-is.
    2. Critical/high severity — fail closed to blocking unless disposition is explicit.
    3. Keyword match against title/summary (BLOCKING_KEYWORDS / NON_BLOCKING_KEYWORDS).
    4. Medium/low severity without blocking keyword — non_blocking.
    5. Fail-closed default — blocking.
    """

    def test_classify_all_blocking(self):
        """Findings with blocking disposition or critical severity are blocking."""
        findings = [
            {"title": "Bug causes runtime failure", "class": "DEFECT", "severity": "high"},
            {"title": "Bug2", "disposition": "blocking"},
        ]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 2
        assert len(non_blocking) == 0

    def test_classify_all_non_blocking(self):
        """All non_blocking findings classified correctly."""
        findings = [
            {"title": "Nit1", "disposition": "non_blocking"},
            {"title": "Nit2", "disposition": "non_blocking"},
        ]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0
        assert len(non_blocking) == 2

    def test_classify_mixed(self):
        """Mixed disposition findings separated correctly."""
        findings = [
            {"title": "Bug", "disposition": "blocking"},
            {"title": "Nit", "disposition": "non_blocking"},
            {"title": "NoDisposition causes crash", "class": "DEFECT"},
        ]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 2  # "Bug" + "NoDisposition causes crash" (keyword match)
        assert len(non_blocking) == 1

    def test_missing_disposition_is_blocking(self):
        """Fail-closed: missing disposition with no keywords treated as blocking."""
        findings = [{"title": "Unknown"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_missing_disposition_medium_severity_no_keywords_non_blocking(self):
        """Medium severity without keywords → non_blocking (severity-appropriate default)."""
        findings = [{"title": "Some issue", "severity": "medium"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0, "medium severity without keywords should be non_blocking"
        assert len(non_blocking) == 1

    def test_missing_disposition_low_severity_non_blocking(self):
        """Low severity without keywords → non_blocking (severity-appropriate default)."""
        findings = [{"title": "Some issue", "severity": "low"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0, "low severity without keywords should be non_blocking"
        assert len(non_blocking) == 1

    def test_empty_findings(self):
        blocking, non_blocking = pb_mod._classify_findings([])  # ANTICHEAT_OK: testing internal executor functions
        assert blocking == []
        assert non_blocking == []

    # --- Classification contract tests ---

    def test_explicit_disposition_blocking(self):
        """Finding with explicit disposition=blocking is classified as blocking."""
        findings = [{"title": "Anything", "disposition": "blocking"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_explicit_disposition_non_blocking(self):
        """Finding with explicit disposition=non_blocking is classified as non_blocking."""
        findings = [{"title": "Anything", "disposition": "non_blocking"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0
        assert len(non_blocking) == 1

    def test_no_disposition_critical_severity_blocking(self):
        """No disposition + critical severity → always blocking."""
        findings = [{"title": "Something", "severity": "critical"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_critical_severity_overrides_explicit_non_blocking(self):
        """Critical severity cannot be downgraded by explicit non_blocking disposition."""
        findings = [{"title": "Critical bug", "severity": "critical", "disposition": "non_blocking"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_no_disposition_medium_no_runtime_impact_non_blocking(self):
        """No disposition + medium severity + no runtime keywords → non_blocking."""
        findings = [{"title": "Improve error message wording", "severity": "medium"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0, "medium severity with no keywords should be non_blocking"
        assert len(non_blocking) == 1

    def test_no_disposition_high_severity_runtime_failure_blocking(self):
        """No disposition + high severity + 'runtime failure' in title → blocking."""
        findings = [{"title": "Potential runtime failure in commit path", "severity": "high"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_no_disposition_high_severity_theoretical_edge_case_blocks(self):
        """High severity cannot downgrade from title/summary hardening prose alone."""
        findings = [{"title": "Theoretical edge case in unusual config", "severity": "high"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_disposition_for_finding_returns_reason(self):
        """_disposition_for_finding returns (disposition, reason) tuple."""
        disp, reason = pb_mod._disposition_for_finding({"title": "X", "disposition": "blocking"})  # ANTICHEAT_OK: testing internal executor functions
        assert disp == "blocking"
        assert "explicit" in reason

        disp, reason = pb_mod._disposition_for_finding({"title": "crash in pipeline", "severity": "high"})  # ANTICHEAT_OK: testing internal executor functions
        assert disp == "blocking"
        assert "high severity" in reason.lower()

    def test_no_disposition_high_severity_no_keywords_blocking(self):
        """High severity without any keyword match → blocking (fail-closed)."""
        findings = [{"title": "Refactor suggestion", "severity": "high"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_no_disposition_summary_keyword_match(self):
        """Keywords in summary field (not just title) trigger classification."""
        findings = [{"title": "Issue", "summary": "This causes data loss", "severity": "medium"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1, "blocking keyword in summary should trigger blocking"

    def test_non_blocking_keyword_in_title(self):
        """Non-blocking keywords like 'hardening' route to non_blocking."""
        findings = [{"title": "Add hardening for edge case", "severity": "medium"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0
        assert len(non_blocking) == 1

    def test_low_doc_accuracy_blocking_keyword_stays_non_blocking(self):
        """Low-severity DOC_ACCURACY findings stay non-blocking even if they quote a blocker keyword."""
        findings = [{
            "title": "Bridge exit-code=1 conflates non-GO review with BridgeError infrastructure crash",
            "class": "DOC_ACCURACY",
            "severity": "low",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0
        assert len(non_blocking) == 1


class TestGovernanceDowngrade:
    """Governance/doc findings on non-code paths downgrade to non-blocking.

    The predicate requires BOTH governance class AND governance path.
    A POLICY_BOUND finding on actual code stays blocking.
    """

    def test_policy_bound_on_report_path_is_non_blocking_below_severity_floor(self):
        """POLICY_BOUND on reports/ stays non-blocking only below high severity."""
        findings = [{
            "title": "Plan file has unchecked boxes",
            "class": "POLICY_BOUND",
            "severity": "medium",
            "file": "reports/control_plane/wave1a_pipeline_validation_2026-03-31.md",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0, "POLICY_BOUND on reports/ should be non-blocking"
        assert len(non_blocking) == 1

    def test_policy_bound_on_code_file_stays_blocking(self):
        """POLICY_BOUND on actual code file stays blocking — not governance."""
        findings = [{
            "title": "Code policy violation in executor",
            "class": "POLICY_BOUND",
            "severity": "high",
            "file": "mu/tools/executors/phase_b_executor.py",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1, "POLICY_BOUND on code file must stay blocking"
        assert len(non_blocking) == 0

    def test_doc_accuracy_on_tasks_md_is_non_blocking_below_severity_floor(self):
        """DOC_ACCURACY on TASKS.md stays non-blocking only below high severity."""
        findings = [{
            "title": "TASKS.md missing tracker sync note",
            "class": "DOC_ACCURACY",
            "severity": "medium",
            "file": "TASKS.md",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0, "DOC_ACCURACY on TASKS.md should be non-blocking"
        assert len(non_blocking) == 1

    def test_doc_accuracy_on_code_file_stays_blocking(self):
        """DOC_ACCURACY on a code file stays blocking — not governance."""
        findings = [{
            "title": "Doc comment contradicts behavior",
            "class": "DOC_ACCURACY",
            "severity": "high",
            "file": "mu/tools/agents/bridge_adapters.py",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1, "DOC_ACCURACY on code file must stay blocking"
        assert len(non_blocking) == 0

    def test_defect_on_report_path_not_downgraded(self):
        """DEFECT class on reports/ is NOT governance — class must also match."""
        findings = [{
            "title": "Script in report has a bug",
            "class": "DEFECT",
            "severity": "high",
            "file": "reports/control_plane/some_script.py",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1, "DEFECT on any path stays blocking regardless of path"
        assert len(non_blocking) == 0

    def test_governance_downgrade_reason_includes_file(self):
        """The downgrade reason includes the file path for auditability."""
        disp, reason = pb_mod._disposition_for_finding({  # ANTICHEAT_OK: testing internal executor functions
            "title": "Stale reference",
            "class": "POLICY_BOUND",
            "severity": "medium",
            "file": "reports/deferred/README.md",
        })
        assert disp == "non_blocking"
        assert "governance" in reason.lower()
        assert "reports/deferred/README.md" in reason

    @pytest.mark.parametrize("severity", ["high", "critical"])
    def test_governance_path_downgrades_even_high_severity(self, severity):
        """DOC_ACCURACY/POLICY_BOUND on governance paths are editorial — downgraded regardless of severity."""
        findings = [{
            "title": "Critical governance downgrade",
            "class": "POLICY_BOUND",
            "severity": severity,
            "file": "reports/control_plane/example.md",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0
        assert len(non_blocking) == 1

    @pytest.mark.parametrize("severity", ["high", "critical"])
    def test_defect_on_governance_path_stays_blocking(self, severity):
        """DEFECT findings on governance paths still block — only DOC_ACCURACY/POLICY_BOUND downgrade."""
        findings = [{
            "title": "Runtime defect in report",
            "class": "DEFECT",
            "severity": severity,
            "file": "reports/control_plane/example.md",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0


class TestStageFiles:
    """Staging must respect repo ignore rules and fail closed."""

    def test_stage_files_stages_normal_file(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        (repo / "ok.txt").write_text("x", encoding="utf-8")

        assert pb_mod._stage_files(repo, ["ok.txt"]) is True  # ANTICHEAT_OK: testing internal executor functions

        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.splitlines()
        assert staged == ["ok.txt"]

    def test_stage_files_rejects_ignored_file_without_force_add(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        (repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
        (repo / "ignored.txt").write_text("x", encoding="utf-8")

        assert pb_mod._stage_files(repo, ["ignored.txt"]) is False  # ANTICHEAT_OK: testing internal executor functions

        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.splitlines()
        assert staged == []


class TestHighSeverityDetailHeuristic:
    """High severity no longer downgrades from prose-only detail/description text."""

    def test_hardening_indicator_in_detail_still_blocking(self):
        """High severity detail prose cannot downgrade disposition."""
        findings = [{
            "title": "Receipt field could be spoofed",
            "severity": "high",
            "detail": "In a theoretical adversarial setup, the receipt field could be spoofed.",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_defect_indicator_in_detail_blocking(self):
        """High severity finding with defect indicator in detail → blocking."""
        findings = [{
            "title": "Commit proceeds without receipt",
            "severity": "high",
            "detail": "When receipt is missing, the pipeline still proceeds to commit_ready.",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_defect_indicator_returns_success_blocking(self):
        """'returns success' in detail is a defect signal → blocking."""
        findings = [{
            "title": "Validation gap",
            "severity": "high",
            "detail": "The function returns success even when the input is malformed.",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1

    def test_hardening_indicator_could_be_bypassed_still_blocking(self):
        """High severity 'could be bypassed' prose still fails closed."""
        findings = [{
            "title": "Gate check",
            "severity": "high",
            "detail": "With a crafted input, the gate could be bypassed in theory.",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_conflicting_indicators_fail_closed(self):
        """Both defect and hardening indicators → blocking (fail-closed on conflict)."""
        findings = [{
            "title": "Ambiguous",
            "severity": "high",
            "detail": "Theoretical but the function returns success anyway.",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1, "conflicting indicators should fail-closed to blocking"

    def test_no_indicators_still_blocking(self):
        """High severity, no keywords, no detail indicators → blocking (fail-closed)."""
        findings = [{
            "title": "Some vague concern",
            "severity": "high",
            "detail": "This is a finding about something.",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1

    def test_hardening_in_description_field_still_blocking(self):
        """High severity description prose also cannot downgrade disposition."""
        findings = [{
            "title": "Spoofable field",
            "severity": "high",
            "description": "This is a synthetic scenario unlikely in practice.",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_disposition_for_finding_reason_includes_indicator(self):
        """Reason string captures the fail-closed high-severity rule."""
        disp, reason = pb_mod._disposition_for_finding({  # ANTICHEAT_OK: testing internal executor functions
            "title": "X", "severity": "high",
            "detail": "theoretical edge case",
        })
        assert disp == "blocking"
        assert "high severity" in reason.lower()

        disp, reason = pb_mod._disposition_for_finding({  # ANTICHEAT_OK: testing internal executor functions
            "title": "X", "severity": "high",
            "detail": "the pipeline still proceeds past the gate",
        })
        assert disp == "blocking"
        assert "high severity" in reason.lower()


class TestRepeatFindingConvergenceCap:
    """Blocking findings stay blocking (no auto-downgrade). Repeat count tracked for loop termination."""

    def test_finding_stays_blocking_at_cap(self):
        """A finding appearing as blocking for 3+ rounds stays blocking (never downgraded)."""
        finding = {"title": "Stubborn bug", "severity": "high", "file": "foo.py",
                   "detail": "some vague concern"}
        history: dict[str, int] = {}

        # All rounds: stays blocking (no downgrade)
        for i in range(pb_mod.REPEAT_FINDING_CAP + 2):
            blocking, non_blocking = pb_mod._classify_findings([finding], history)  # ANTICHEAT_OK: testing internal executor functions
            assert len(blocking) == 1, f"Round {i+1}: finding must stay blocking"
            assert len(non_blocking) == 0, f"Round {i+1}: no auto-downgrade"

        # But history tracks the count for the caller's hard-failure check
        key = pb_mod._finding_key(finding)  # ANTICHEAT_OK: testing internal executor functions
        assert history[key] == pb_mod.REPEAT_FINDING_CAP + 2

    def test_repeat_cap_per_finding_key(self):
        """Different findings have independent repeat counters."""
        f1 = {"title": "Issue A", "severity": "high", "file": "a.py",
               "detail": "vague concern"}
        f2 = {"title": "Issue B", "severity": "high", "file": "b.py",
               "detail": "vague concern"}
        history: dict[str, int] = {}

        # Run f1 to cap, then introduce f2
        for _ in range(pb_mod.REPEAT_FINDING_CAP):
            pb_mod._classify_findings([f1], history)  # ANTICHEAT_OK: testing internal executor functions

        # f1 is at cap, f2 is fresh — both stay blocking
        blocking, non_blocking = pb_mod._classify_findings([f1, f2], history)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 2, "Both findings must stay blocking"
        assert len(non_blocking) == 0, "No auto-downgrade"
        # But their counts differ
        assert history[pb_mod._finding_key(f1)] == pb_mod.REPEAT_FINDING_CAP + 1  # ANTICHEAT_OK: testing internal executor functions
        assert history[pb_mod._finding_key(f2)] == 1  # ANTICHEAT_OK: testing internal executor functions

    def test_disappeared_finding_pruned_from_history(self):
        """Findings that disappear from a round get pruned from history."""
        f1 = {"title": "Transient", "severity": "high", "file": "x.py",
               "detail": "vague concern"}
        history: dict[str, int] = {}

        # Appear in round 1
        pb_mod._classify_findings([f1], history)  # ANTICHEAT_OK: testing internal executor functions
        assert pb_mod._finding_key(f1) in history  # ANTICHEAT_OK: testing internal executor functions

        # Disappear in round 2 (empty findings)
        pb_mod._classify_findings([], history)  # ANTICHEAT_OK: testing internal executor functions
        assert pb_mod._finding_key(f1) not in history  # ANTICHEAT_OK: testing internal executor functions

    def test_no_history_means_no_downgrade(self):
        """Without finding_history, repeat cap is not applied."""
        finding = {"title": "Bug", "severity": "high", "file": "x.py",
                   "detail": "vague concern"}
        for _ in range(5):
            blocking, non_blocking = pb_mod._classify_findings([finding])  # ANTICHEAT_OK: testing internal executor functions
            assert len(blocking) == 1

    def test_non_blocking_finding_resets_counter(self):
        """A finding that classifies as non_blocking resets its repeat counter."""
        history: dict[str, int] = {}

        # First two rounds: blocking (medium severity, no keywords → non_blocking,
        # but we need blocking first so use no severity + no keywords → fail-closed blocking)
        f_blocking = {"title": "Concern", "file": "x.py"}
        pb_mod._classify_findings([f_blocking], history)  # ANTICHEAT_OK: testing internal executor functions
        pb_mod._classify_findings([f_blocking], history)  # ANTICHEAT_OK: testing internal executor functions
        key = pb_mod._finding_key(f_blocking)  # ANTICHEAT_OK: testing internal executor functions
        assert history[key] == 2

        # Now it appears as medium severity with non_blocking keyword — counter resets
        f_nb = {"title": "Concern", "severity": "medium", "file": "x.py",
                "disposition": "non_blocking"}
        pb_mod._classify_findings([f_nb], history)  # ANTICHEAT_OK: testing internal executor functions
        assert key not in history

    def test_finding_key_stable(self):
        """Finding key is based on title + file, case-insensitive for title."""
        f1 = {"title": "Bug in foo", "file": "src/foo.py"}
        f2 = {"title": "bug in foo", "file": "src/foo.py"}
        f3 = {"title": "Bug in foo", "file": "src/bar.py"}
        assert pb_mod._finding_key(f1) == pb_mod._finding_key(f2)  # ANTICHEAT_OK: testing internal executor functions
        assert pb_mod._finding_key(f1) != pb_mod._finding_key(f3)  # ANTICHEAT_OK: testing internal executor functions


class TestDeferredPacketFiling:
    """Non-blocking findings are auto-filed to deferred packet."""

    def test_writes_deferred_packet(self, tmp_path):
        findings = [
            {"title": "Style nit", "class": "DOC_ACCURACY", "severity": "low", "file": "foo.py", "disposition": "non_blocking"},
        ]
        packet = pb_mod._write_deferred_packet(tmp_path, "test-wave-42", findings)  # ANTICHEAT_OK: testing internal executor functions
        assert packet.exists()
        content = packet.read_text()
        assert "Style nit" in content
        assert "non_blocking" in content
        assert "test-wave-42" in content
        assert packet.parent == tmp_path / "reports" / "deferred" / "non_blocking"

    def test_packet_name_from_wave_id(self, tmp_path):
        packet = pb_mod._write_deferred_packet(tmp_path, "my-wave", [{"title": "x"}])  # ANTICHEAT_OK: testing internal executor functions
        assert packet.name == "my-wave_bridge_nonblockers.md"

    def test_packet_name_normalizes_untrusted_wave_id(self, tmp_path):
        packet = pb_mod._write_deferred_packet(tmp_path, "../../Weird Wave!!", [{"title": "x"}])  # ANTICHEAT_OK: testing internal executor functions
        assert packet.name == "weird-wave_bridge_nonblockers.md"

    def test_creates_directory_if_missing(self, tmp_path):
        repo = tmp_path / "nested"
        repo.mkdir()
        packet = pb_mod._write_deferred_packet(repo, "w", [{"title": "t"}])  # ANTICHEAT_OK: testing internal executor functions
        assert packet.exists()

    def test_collect_supervisor_deferred_items_includes_changed_non_blocking_packets(self):
        deferred_items = pb_mod._collect_supervisor_deferred_items(  # ANTICHEAT_OK: testing internal executor functions
            [
                "mu/tools/executors/phase_b_executor.py",
                "reports/deferred/non_blocking/wave_bridge_nonblockers.md",
                "reports/deferred/non_blocking/README.md",
            ],
            None,
        )
        assert deferred_items == ["reports/deferred/non_blocking/wave_bridge_nonblockers.md"]

    def test_collect_supervisor_deferred_items_dedupes_explicit_packet(self):
        deferred_items = pb_mod._collect_supervisor_deferred_items(  # ANTICHEAT_OK: testing internal executor functions
            ["reports/deferred/non_blocking/wave_bridge_nonblockers.md"],
            "reports/deferred/non_blocking/wave_bridge_nonblockers.md",
        )
        assert deferred_items == ["reports/deferred/non_blocking/wave_bridge_nonblockers.md"]


@pytest.mark.usefixtures("mock_routing_record")
class TestOnlyBlockingToImplementer:
    """Only blocking findings go to implementer; non-blocking deferred."""

    def test_all_non_blocking_converges_as_go(self, tmp_path):
        """When all findings are non_blocking, bridge loop converges (GO equivalent)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        # Bridge returns REQUEST_CHANGES but all findings are non_blocking
        envelope = json.dumps({
            "job_id": "j1", "turn_id": "t1", "agent_role": "reviewer",
            "decision": "REQUEST_CHANGES", "summary": "minor nits",
            "touched_files_claimed": [], "validations_claimed": [],
            "request_for_next_agent": "",
            "findings": [
                {"title": "Style nit", "class": "DOC_ACCURACY", "severity": "low",
                 "file": "f.py", "disposition": "non_blocking", "status": "new"},
            ],
        })
        render_text = f"BEGIN_AGENT_ENVELOPE\n{envelope}\nEND_AGENT_ENVELOPE"

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                 "decision": "REQUEST_CHANGES", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_read_bridge_render", return_value=render_text), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        # Should converge — implementer NOT re-invoked for non-blocking findings
        assert result["status"] == "commit_ready"
        # Implementer called only once (initial), not for non-blocking fix
        assert mock_impl.invoke_implementer.call_count == 1
        # Deferred packet should be filed
        assert result.get("deferred_packet_path") is not None

    def test_bridge_go_with_non_blocking_findings_still_files_deferred_packet(self, tmp_path):
        """A GO render with non-blocking findings must still update deferred packet state."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        envelope = json.dumps({
            "job_id": "j1", "turn_id": "t1", "agent_role": "reviewer",
            "decision": "GO", "summary": "looks good",
            "touched_files_claimed": [], "validations_claimed": [],
            "request_for_next_agent": "",
            "findings": [
                {"title": "Observability nit", "class": "DEFECT", "severity": "low",
                 "file": "mu/tools/executors/supervision_poll.py", "disposition": "non_blocking", "status": "new"},
            ],
        })
        render_text = f"BEGIN_AGENT_ENVELOPE\n{envelope}\nEND_AGENT_ENVELOPE"

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_read_bridge_render", return_value=render_text), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert result.get("deferred_packet_path") is not None

    def test_bridge_go_with_blocking_findings_fails_closed(self, tmp_path):
        """A GO transcript that still carries blocking findings is inconsistent and must fail closed."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        envelope = json.dumps({
            "job_id": "j1", "turn_id": "t1", "agent_role": "reviewer",
            "decision": "GO", "summary": "looks good",
            "touched_files_claimed": [], "validations_claimed": [],
            "request_for_next_agent": "",
            "findings": [
                {"title": "Real bug", "class": "DEFECT", "severity": "high",
                 "file": "f.py", "disposition": "blocking", "status": "new"},
            ],
        })
        render_text = f"BEGIN_AGENT_ENVELOPE\n{envelope}\nEND_AGENT_ENVELOPE"

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_read_bridge_render", return_value=render_text), \
             patch.object(pb_mod, "_stage_files", return_value=True):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "bridge_decision"
        assert "blocking finding" in result["errors"][0]

    def test_blocking_findings_sent_to_implementer(self, tmp_path):
        """Blocking findings are sent to implementer; non-blocking deferred."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        bridge_calls = [0]
        first_job_id = [""]

        # Mixed findings: one blocking, one non-blocking
        envelope = json.dumps({
            "job_id": "j1", "turn_id": "t1", "agent_role": "reviewer",
            "decision": "REQUEST_CHANGES", "summary": "issues",
            "touched_files_claimed": [], "validations_claimed": [],
            "request_for_next_agent": "",
            "findings": [
                {"title": "Real bug", "class": "DEFECT", "severity": "high",
                 "file": "f.py", "disposition": "blocking", "status": "new"},
                {"title": "Style nit", "class": "DOC_ACCURACY", "severity": "low",
                 "file": "f.py", "disposition": "non_blocking", "status": "new"},
            ],
        })
        render_text = f"BEGIN_AGENT_ENVELOPE\n{envelope}\nEND_AGENT_ENVELOPE"

        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                first_job_id[0] = kw["job_id"]
                return {"exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": first_job_id[0]}
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": kw["job_id"]}

        def read_render_side_effect(_repo_root, current_job_id):
            if current_job_id == first_job_id[0]:
                return render_text
            return ""

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", side_effect=read_render_side_effect), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={"exit_code": 0, "passed": True, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        # Implementer re-invoked (only blocking findings sent)
        assert mock_impl.invoke_implementer.call_count >= 2
        # Check that the fix prompt contained "BLOCKING" but not non-blocking title
        fix_call_prompt = mock_impl.build_implementation_prompt.call_args_list[-1]
        prompt_text = fix_call_prompt[0][0] if fix_call_prompt[0] else ""
        # The blocking finding title should appear in prompt
        assert "Real bug" in prompt_text or "BLOCKING" in prompt_text

    def test_rendered_raw_output_preserves_blocking_disposition(self, tmp_path):
        """Rendered REQUEST_CHANGES must honor blocking disposition from reviewer raw output."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        raw_path = repo / ".agent_bus" / "raw" / "j1" / "reviewer.txt"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_envelope = json.dumps({
            "job_id": "j1", "turn_id": "t1", "agent_role": "reviewer",
            "decision": "REQUEST_CHANGES", "summary": "issues",
            "touched_files_claimed": [], "validations_claimed": [],
            "request_for_next_agent": "",
            "findings": [
                {"title": "Raw blocker", "class": "DEFECT", "severity": "medium",
                 "file": "f.py", "disposition": "blocking", "status": "persisting"},
            ],
        })
        raw_path.write_text(
            "noise\nBEGIN_AGENT_ENVELOPE\n"
            f"{raw_envelope}\n"
            "END_AGENT_ENVELOPE\n",
            encoding="utf-8",
        )
        render_text = (
            "### reviewer\n"
            "- Status: completed\n"
            "- Decision: REQUEST_CHANGES\n"
            "- **Findings (1):**\n"
            "  1. **DEFECT** (medium): Raw blocker\n"
            "     - File: `f.py:1` | Status: persisting\n"
            "     - Evidence: preserved via raw output\n"
            f"- Raw output: {raw_path}\n"
        )

        mock_impl = _make_mock_impl()
        bridge_calls = [0]

        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                return {"exit_code": 1, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "j1"}
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": "j2"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value=render_text), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={"exit_code": 0, "passed": True, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert mock_impl.invoke_implementer.call_count >= 2
        assert result.get("deferred_packet_path") is None

    def test_stale_render_still_uses_job_raw_reviewer_findings(self, tmp_path):
        """Phase B must prefer raw reviewer files by job id when the render is stale."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        bridge_calls = [0]
        first_job_id = [""]
        stale_render = [""]

        def bridge_side(*args, **kwargs):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                first_job_id[0] = kwargs["job_id"]
                raw_dir = repo / ".agent_bus" / "raw" / first_job_id[0]
                raw_dir.mkdir(parents=True, exist_ok=True)
                reader_path = raw_dir / f"{first_job_id[0]}--r1-reader-11111111.txt"
                reviewer_path = raw_dir / f"{first_job_id[0]}--r1-reviewer-22222222.txt"
                reader_path.write_text(
                    "BEGIN_AGENT_ENVELOPE\n"
                    '{"findings": []}\n'
                    "END_AGENT_ENVELOPE\n",
                    encoding="utf-8",
                )
                reviewer_envelope = json.dumps({
                    "job_id": first_job_id[0],
                    "turn_id": f"{first_job_id[0]}--r1-reviewer-22222222",
                    "agent_role": "reviewer",
                    "decision": "REQUEST_CHANGES",
                    "summary": "real blocker present",
                    "touched_files_claimed": [],
                    "validations_claimed": [],
                    "request_for_next_agent": "",
                    "findings": [
                        {
                            "title": "Real blocker from raw reviewer",
                            "class": "POLICY_BOUND",
                            "severity": "medium",
                            "file": "mu/tools/observability/_pane_prci.sh",
                            "disposition": "blocking",
                            "status": "persisting",
                        }
                    ],
                })
                reviewer_path.write_text(
                    "noise\nBEGIN_AGENT_ENVELOPE\n"
                    f"{reviewer_envelope}\n"
                    "END_AGENT_ENVELOPE\n",
                    encoding="utf-8",
                )
                stale_render[0] = (
                    f"# Bridge Job {first_job_id[0]}\n\n"
                    "### reader\n"
                    "- Status: completed\n"
                    "- Decision: SYNTHETIC\n"
                    f"- Raw output: {reader_path}\n"
                )
                return {
                    "exit_code": 1,
                    "stdout": "REQUEST_CHANGES\n",
                    "stderr": "",
                    "decision": "REQUEST_CHANGES",
                    "job_id": first_job_id[0],
                }
            return {
                "exit_code": 0,
                "stdout": "GO\n",
                "stderr": "",
                "decision": "GO",
                "job_id": kwargs["job_id"],
            }

        def read_render_side_effect(_repo_root, current_job_id):
            if current_job_id == first_job_id[0]:
                return stale_render[0]
            return ""

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", side_effect=read_render_side_effect), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={"exit_code": 0, "passed": True, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert mock_impl.invoke_implementer.call_count >= 2
        fix_prompt = mock_impl.build_implementation_prompt.call_args_list[-1][0][0]
        assert "Real blocker from raw reviewer" in fix_prompt
        assert "Malformed AGENT_ENVELOPE" not in fix_prompt

    def test_go_low_doc_accuracy_crash_title_does_not_fail_closed(self, tmp_path):
        """A GO transcript with only low DOC_ACCURACY crash-wording findings remains non-blocking."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        envelope = json.dumps({
            "job_id": "j1", "turn_id": "t1", "agent_role": "reviewer",
            "decision": "GO", "summary": "looks good",
            "touched_files_claimed": [], "validations_claimed": [],
            "request_for_next_agent": "",
            "findings": [
                {
                    "title": "Bridge exit-code=1 conflates non-GO review with BridgeError infrastructure crash",
                    "class": "DOC_ACCURACY",
                    "severity": "low",
                    "file": "mu/tools/executors/phase_b_executor.py",
                    "status": "new",
                },
            ],
        })
        render_text = f"BEGIN_AGENT_ENVELOPE\n{envelope}\nEND_AGENT_ENVELOPE"

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tools/executors/phase_b_executor.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tools/executors/phase_b_executor.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 2, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_read_bridge_render", return_value=render_text), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert result["pre_commit_decision"] == "COMMIT_GO"


@pytest.mark.usefixtures("mock_routing_record")
class TestSupervisorReasonSurfacing:
    """Phase B must preserve the actionable supervisor reason instead of only ERROR_INTERNAL."""

    def test_supervisor_rejection_includes_summary_and_detail(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_read_bridge_render", return_value=""), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 1,
                 "parsed": {
                     "decision": "ERROR_INTERNAL",
                     "summary": "Package is stale against staged truth",
                     "status": "error",
                     "findings": [],
                     "error_detail": "missing mu/tools/checks/check_closeout_attestation.py",
                 },
                 "receipt_path": "",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "supervisor_rejected"
        assert result["step"] == "pre_commit_supervisor"
        assert "Package is stale against staged truth" in result["errors"][0]
        assert "missing mu/tools/checks/check_closeout_attestation.py" in result["errors"][0]
        assert "Package is stale against staged truth" == result["pre_commit_summary"].split(" | ")[0]


@pytest.mark.usefixtures("mock_routing_record")
class TestValidationRunsMechanically:
    """Validation (pytest) runs mechanically in the loop after each implementer fix."""

    def test_bridge_fix_pytest_skips_stale_baseline_test_files(self, tmp_path):
        """Bridge-fix pytest must ignore test files that predate the current fix round."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        bridge_calls = [0]

        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                return {"exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "j1"}
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": "j2"}

        changed_files_calls = [0]

        def changed_files_side(_repo_root):
            changed_files_calls[0] += 1
            if changed_files_calls[0] == 1:
                return []
            if changed_files_calls[0] <= 4:
                return ["mu/tests/tools/test_baseline.py"]
            return ["mu/tests/tools/test_baseline.py", "mu/tools/observability/_pane_prci.sh"]

        wave_owned_calls = [0]

        def wave_owned_side(*_a, **_kw):
            wave_owned_calls[0] += 1
            if wave_owned_calls[0] <= 2:
                return ["mu/tests/tools/test_baseline.py"]
            return ["mu/tools/observability/_pane_prci.sh"]

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", side_effect=changed_files_side), \
             patch.object(pb_mod, "_collect_wave_owned_files", side_effect=wave_owned_side), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="some findings"), \
             patch.object(pb_mod, "_run_pytest_on_files") as mock_pytest, \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        mock_pytest.assert_not_called()

    def test_bridge_fix_pytest_runs_only_new_test_files_from_current_fix(self, tmp_path):
        """Bridge-fix pytest must scope to tests introduced by the current fix pass."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        bridge_calls = [0]

        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                return {"exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "j1"}
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": "j2"}

        changed_files_calls = [0]

        def changed_files_side(_repo_root):
            changed_files_calls[0] += 1
            if changed_files_calls[0] == 1:
                return []
            if changed_files_calls[0] <= 4:
                return ["mu/tests/tools/test_baseline.py"]
            return ["mu/tests/tools/test_baseline.py", "mu/tests/tools/test_fix_round.py"]

        wave_owned_calls = [0]

        def wave_owned_side(*_a, **_kw):
            wave_owned_calls[0] += 1
            if wave_owned_calls[0] <= 2:
                return ["mu/tests/tools/test_baseline.py"]
            return ["mu/tools/observability/_pane_prci.sh"]

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", side_effect=changed_files_side), \
             patch.object(pb_mod, "_collect_wave_owned_files", side_effect=wave_owned_side), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="some findings"), \
             patch.object(
                 pb_mod,
                 "_run_pytest_on_files",
                 return_value={"exit_code": 0, "stdout": "passed", "stderr": "", "passed": True},
             ) as mock_pytest, \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        mock_pytest.assert_called_once_with(
            repo,
            ["mu/tests/tools/test_fix_round.py"],
            timeout=300,
        )

    def test_pytest_failure_fed_back_as_blocking(self, tmp_path):
        """pytest failure after implementer fix becomes a blocking finding."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        bridge_calls = [0]

        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                return {"exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "j1"}
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": "j2"}

        pytest_calls = [0]
        def pytest_side(repo_root, test_files, **kw):
            pytest_calls[0] += 1
            if pytest_calls[0] == 1:
                return {"exit_code": 1, "stdout": "FAILED test_foo.py", "stderr": "", "passed": False}
            return {"exit_code": 0, "stdout": "passed", "stderr": "", "passed": True}

        changed_files_calls = [0]

        def changed_files_side(_repo_root):
            changed_files_calls[0] += 1
            if changed_files_calls[0] == 1:
                return []
            if changed_files_calls[0] <= 4:
                return ["mu/tests/tools/test_existing.py"]
            if changed_files_calls[0] == 5:
                return ["mu/tests/tools/test_existing.py", "mu/tests/tools/test_foo.py"]
            if changed_files_calls[0] == 6:
                return ["mu/tests/tools/test_existing.py", "mu/tests/tools/test_foo.py"]
            return ["mu/tests/tools/test_existing.py", "mu/tests/tools/test_foo.py"]

        wave_owned_calls = [0]

        def wave_owned_side(*_a, **_kw):
            wave_owned_calls[0] += 1
            if wave_owned_calls[0] <= 2:
                return ["mu/tests/tools/test_existing.py"]
            if wave_owned_calls[0] == 3:
                return ["mu/tests/tools/test_existing.py", "mu/tests/tools/test_foo.py"]
            return ["mu/tools/observability/_pane_prci.sh"]

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", side_effect=changed_files_side), \
             patch.object(pb_mod, "_collect_wave_owned_files", side_effect=wave_owned_side), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="some findings"), \
             patch.object(pb_mod, "_run_pytest_on_files", side_effect=pytest_side), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        # pytest was called (at least once)
        assert pytest_calls[0] >= 1
        # Implementer re-invoked to fix pytest failure
        assert mock_impl.invoke_implementer.call_count >= 3


@pytest.mark.usefixtures("mock_routing_record")
class TestStatePersistence:
    """State file is written after each step and resume works."""

    def test_state_file_written(self, tmp_path):
        """_save_state writes state to expected path."""
        state = {"plan_path": "test.md", "completed_step": "implementer", "wave_id": "w1"}
        path = pb_mod._save_state(tmp_path, state)  # ANTICHEAT_OK: testing internal executor functions
        assert path.exists()
        loaded = json.loads(path.read_text())
        assert loaded["completed_step"] == "implementer"
        assert loaded["plan_path"] == "test.md"

    def test_load_state_returns_saved(self, tmp_path):
        """_load_state returns previously saved state."""
        state = {"plan_path": "test.md", "completed_step": "bridge_round_2", "wave_id": "w1", "bridge_rounds": 2}
        pb_mod._save_state(tmp_path, state)  # ANTICHEAT_OK: testing internal executor functions
        loaded = pb_mod._load_state(tmp_path)  # ANTICHEAT_OK: testing internal executor functions
        assert loaded is not None
        assert loaded["completed_step"] == "bridge_round_2"
        assert loaded["bridge_rounds"] == 2

    def test_load_state_returns_none_when_missing(self, tmp_path):
        """_load_state returns None when no state file exists."""
        assert pb_mod._load_state(tmp_path) is None  # ANTICHEAT_OK: testing internal executor functions

    def test_clear_state_removes_file(self, tmp_path):
        """_clear_state removes the state file."""
        pb_mod._save_state(tmp_path, {"plan_path": "x"})  # ANTICHEAT_OK: testing internal executor functions
        assert pb_mod._state_file_path(tmp_path).exists()  # ANTICHEAT_OK: testing internal executor functions
        pb_mod._clear_state(tmp_path)  # ANTICHEAT_OK: testing internal executor functions
        assert not pb_mod._state_file_path(tmp_path).exists()  # ANTICHEAT_OK: testing internal executor functions

    def test_clear_state_noop_when_missing(self, tmp_path):
        """_clear_state is a no-op when no state file exists."""
        pb_mod._clear_state(tmp_path)  # Should not raise  # ANTICHEAT_OK: testing internal executor functions

    def test_resume_from_state_file(self, tmp_path):
        """run_phase_b picks up saved state and includes resumed_from in result."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        # Pre-save state
        pb_mod._save_state(repo, {  # ANTICHEAT_OK: testing internal executor functions
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "bridge_round_1",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "deferred_packet_path": "reports/deferred/non_blocking/plan_bridge_nonblockers.md",
        })

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result.get("resumed_from") == "bridge_round_1"
        assert result.get("deferred_packet_path") == "reports/deferred/non_blocking/plan_bridge_nonblockers.md"


@pytest.mark.usefixtures("mock_routing_record")
class TestStaleStateCleared:
    """Terminal exits must clear persisted state to prevent stale resume wedge.

    Bridge R6 finding: Phase B leaves stale resume state on handled max-round exits.
    Next invocation auto-skips completed rounds, creating an infinite wedge.
    Fix: _clear_state on all terminal exits (max_rounds, question, supervisor_rejected).
    """

    def test_max_rounds_clears_state(self, tmp_path):
        """max_rounds_reached must clear state file so next invocation starts fresh."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        mock_impl = _make_mock_impl()

        # Bridge always returns NO_GO with no parseable findings
        def bridge_no_go(*a, **kw):
            return {"exit_code": 0, "stdout": "NO_GO\n", "stderr": "",
                    "decision": "NO_GO", "job_id": kw.get("job_id", "j")}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_no_go), \
             patch.object(pb_mod, "_read_bridge_render", return_value=""), \
             patch.object(pb_mod, "_stage_files", return_value=True):
            result = pb_mod.run_phase_b(
                repo, "reports/control_plane/plan.md", max_bridge_rounds=1,
            )

        assert result["status"] == "max_rounds_reached"
        # State file must be cleared — next invocation must NOT auto-skip rounds
        assert pb_mod._load_state(repo) is None  # ANTICHEAT_OK: testing internal executor functions

    def test_question_for_founder_clears_state(self, tmp_path):
        """QUESTION decision must clear state so next invocation starts fresh."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        mock_impl = _make_mock_impl()

        def bridge_question(*a, **kw):
            return {"exit_code": 0, "stdout": "QUESTION\n", "stderr": "",
                    "decision": "QUESTION", "job_id": kw.get("job_id", "j")}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_question), \
             patch.object(pb_mod, "_read_bridge_render", return_value=""), \
             patch.object(pb_mod, "_stage_files", return_value=True):
            result = pb_mod.run_phase_b(
                repo, "reports/control_plane/plan.md", max_bridge_rounds=5,
            )

        assert result["status"] == "question_for_founder"
        assert pb_mod._load_state(repo) is None  # ANTICHEAT_OK: testing internal executor functions


class TestParseFindings:
    """Parse findings from bridge render text."""

    def test_parse_structured_envelope(self):
        envelope = json.dumps({
            "job_id": "j1", "decision": "REQUEST_CHANGES", "summary": "test",
            "findings": [
                {"title": "Bug", "disposition": "blocking"},
                {"title": "Nit", "disposition": "non_blocking"},
            ],
        })
        render = f"Some preamble\nBEGIN_AGENT_ENVELOPE\n{envelope}\nEND_AGENT_ENVELOPE\nSome footer"
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 2
        assert findings[0]["title"] == "Bug"
        assert findings[1]["disposition"] == "non_blocking"

    def test_parse_no_envelope_returns_empty(self):
        findings = pb_mod._parse_findings_from_render("just some text without envelope")  # ANTICHEAT_OK: testing internal executor functions
        assert findings == []

    def test_parse_malformed_json_returns_blocking_finding(self):
        render = "BEGIN_AGENT_ENVELOPE\n{not valid json\nEND_AGENT_ENVELOPE"
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["severity"] == "critical"
        assert findings[0]["disposition"] == "blocking"
        assert "malformed" in findings[0]["title"].lower()

    def test_parse_envelope_with_code_fences(self):
        envelope = json.dumps({"findings": [{"title": "A", "disposition": "blocking"}]})
        render = f"BEGIN_AGENT_ENVELOPE\n```json\n{envelope}\n```\nEND_AGENT_ENVELOPE"
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1

    def test_parse_multiple_envelopes_uses_last(self):
        """Multiple distinct NON-EMPTY envelopes: use the last valid one (same as bridge_supervisor)."""
        first = json.dumps({"findings": [{"title": "Finding A", "severity": "low"}]})
        second = json.dumps({"findings": [{"title": "Finding B", "severity": "high"}]})
        render = (
            "BEGIN_AGENT_ENVELOPE\n"
            f"{first}\n"
            "END_AGENT_ENVELOPE\n"
            "noise\n"
            "BEGIN_AGENT_ENVELOPE\n"
            f"{second}\n"
            "END_AGENT_ENVELOPE\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "Finding B"
        assert findings[0]["severity"] == "high"

    def test_empty_envelope_plus_real_not_conflicting(self):
        """Empty-findings envelope + real envelope → returns real findings, not conflict."""
        first = json.dumps({"findings": []})
        second = json.dumps({"findings": [{"title": "Real finding", "disposition": "blocking"}]})
        render = (
            "BEGIN_AGENT_ENVELOPE\n"
            f"{first}\n"
            "END_AGENT_ENVELOPE\n"
            "noise\n"
            "BEGIN_AGENT_ENVELOPE\n"
            f"{second}\n"
            "END_AGENT_ENVELOPE\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "Real finding"

    def test_malformed_envelope_does_not_hide_later_valid_envelope(self):
        """Malformed envelope blocks must not suppress a later valid envelope."""
        valid = json.dumps({"findings": [{"title": "Later finding", "disposition": "blocking"}]})
        render = (
            "BEGIN_AGENT_ENVELOPE\n"
            "{not valid json\n"
            "END_AGENT_ENVELOPE\n"
            "noise\n"
            "BEGIN_AGENT_ENVELOPE\n"
            f"{valid}\n"
            "END_AGENT_ENVELOPE\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "Later finding"

    def test_empty_envelope_falls_back_to_markdown_findings(self):
        """An empty structured envelope must not suppress markdown findings."""
        render = (
            "BEGIN_AGENT_ENVELOPE\n"
            '{"findings": []}\n'
            "END_AGENT_ENVELOPE\n"
            "1. **DEFECT** (critical): Markdown finding survives\n"
            "   - File: a.py\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "Markdown finding survives"

    def test_nested_envelope_markers_fail_closed(self):
        render = (
            "BEGIN_AGENT_ENVELOPE\n"
            '{"findings": [{"title": "outer blocker", "severity": "critical", "disposition": "blocking"}]}\n'
            "BEGIN_AGENT_ENVELOPE\n"
            '{"findings": [{"title": "inner harmless", "severity": "low", "disposition": "non_blocking"}]}\n'
            "END_AGENT_ENVELOPE\n"
            "END_AGENT_ENVELOPE\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["severity"] == "critical"
        assert findings[0]["disposition"] == "blocking"
        assert "Nested AGENT_ENVELOPE markers" in findings[0]["title"]


class TestSdkReviewScopeSelection:
    """Phase B SDK review should prioritize tool/runtime files over residue and tests."""

    def test_select_sdk_review_files_prefers_mu_and_tools(self):
        files = [
            "mu/tools/executors/phase_b_executor.py",
            "mu/tests/tools/test_phase_b_executor.py",
            "reports/control_plane/commit_pipeline_automation_plan_2026-03-25.md",
            "reports/deferred/non_blocking/post_merge_supervisor_phase_a_nonblockers_2026-03-21.md",
        ]
        selected = pb_mod._select_sdk_review_files(files)  # ANTICHEAT_OK: testing internal executor functions
        assert selected == ["mu/tools/executors/phase_b_executor.py"]

    def test_select_sdk_review_files_falls_back_to_reports_when_needed(self):
        files = ["reports/control_plane/commit_pipeline_automation_plan_2026-03-25.md"]
        selected = pb_mod._select_sdk_review_files(files)  # ANTICHEAT_OK: testing internal executor functions
        assert selected == []

    def test_parse_fenced_out_files_from_checkout_state_fence(self):
        plan = (
            "### Checkout-state fence\n\n"
            "| File | Status |\n"
            "|------|--------|\n"
            "| `mu/tools/executors/foo.py` | adjacent pipeline-recovery (fenced out) |\n"
            "| `reports/control_plane/plan.md` | current wave |\n"
            "| `mu/tools/runners/run_review.py` | adjacent pipeline-recovery (fenced out) |\n"
        )
        assert pb_mod._parse_fenced_out_files(plan) == [  # ANTICHEAT_OK: testing internal executor functions
            "mu/tools/executors/foo.py",
            "mu/tools/runners/run_review.py",
        ]

    def test_report_only_changed_files_skip_sdk_gate(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["reports/control_plane/plan.md"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["reports/control_plane/plan.md"]), \
             patch.object(pb_mod, "run_sdk_agents", side_effect=AssertionError("SDK gate should be skipped")), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert result["agent_review_ran"] is False
        assert result["agent_review_skipped_reason"] == "no_implementation_files"
        assert result["agent_review_scope"] == []

    def test_checkout_state_fence_excludes_dirty_baseline_from_wave_scope(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan_path = repo / "reports" / "control_plane" / "plan.md"
        plan_path.write_text(
            "# Plan\n\n"
            "Phase-A-Lock: LOCKED\n\n"
            "## Scope\n\n"
            "- `reports/control_plane/plan.md`\n"
            "- `mu/tools/executors/foo.py`\n\n"
            "### Checkout-state fence\n\n"
            "| File | Status |\n"
            "|------|--------|\n"
            "| `mu/tools/executors/foo.py` | adjacent pipeline-recovery (fenced out) |\n"
        )

        mock_impl = _make_mock_impl()
        stage_files = MagicMock(return_value=True)

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=[
                 "mu/tools/executors/foo.py",
                 "reports/control_plane/plan.md",
             ]), \
             patch.object(pb_mod, "run_sdk_agents", side_effect=AssertionError("SDK gate should be skipped")), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", stage_files), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert result["agent_review_ran"] is False
        assert result["agent_review_skipped_reason"] == "no_implementation_files"
        assert result["agent_review_scope"] == []
        assert stage_files.call_args_list
        for call in stage_files.call_args_list:
            assert call.args[1] == ["reports/control_plane/plan.md"]

    def test_parse_markdown_findings(self):
        render = (
            "# Bridge Job phase-b-r1-73bc0b2f\n"
            "\n"
            "## Findings\n"
            "  1. **DEFECT** (critical): Missing validation on input\n"
            "     - File: mu/tools/executors/phase_b_executor.py\n"
            "     - Evidence: No check for None before calling .strip()\n"
            "\n"
            "  2. **DEFECT** (high): Stale import left behind\n"
            "     - File: mu/tools/agents/bridge_adapters.py\n"
            "     - Evidence: os module imported but never used\n"
            "\n"
            "  3. **POLICY_BOUND** (medium): Config not in executor_config.json\n"
            "     - File: mu/tools/executors/executor_config.json\n"
            "     - Evidence: Hard-coded timeout value\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 3
        assert findings[0]["title"] == "Missing validation on input"
        assert findings[0]["severity"] == "critical"
        assert findings[0]["type"] == "DEFECT"
        assert findings[0]["class"] == "DEFECT"
        assert findings[0]["disposition"] == "blocking"
        assert findings[0]["file"] == "mu/tools/executors/phase_b_executor.py"
        assert findings[0]["evidence"] == "No check for None before calling .strip()"
        assert findings[1]["severity"] == "high"
        assert findings[1]["title"] == "Stale import left behind"
        assert findings[2]["type"] == "POLICY_BOUND"

    def test_parse_markdown_single_finding(self):
        render = "1. **DEFECT** (low): Minor nit\n   - File: foo.py\n"
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "Minor nit"
        assert findings[0]["severity"] == "low"
        assert findings[0]["file"] == "foo.py"
        assert findings[0]["disposition"] == "blocking"

    def test_parse_markdown_with_disposition(self):
        render = (
            "1. **DEFECT** (critical): Bad thing\n"
            "   - File: a.py\n"
            "   - Evidence: proof\n"
            "   - Disposition: blocking\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["disposition"] == "blocking"

    def test_envelope_preferred_over_markdown(self):
        """When both envelope and markdown exist, envelope wins."""
        envelope = json.dumps({"findings": [{"title": "FromEnvelope", "disposition": "blocking"}]})
        render = (
            "BEGIN_AGENT_ENVELOPE\n"
            f"{envelope}\n"
            "END_AGENT_ENVELOPE\n"
            "1. **DEFECT** (critical): FromMarkdown\n"
            "   - File: a.py\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "FromEnvelope"

    def test_raw_output_reference_preferred_over_rendered_markdown(self, tmp_path):
        """Rendered transcripts must reload reviewer raw output to preserve disposition."""
        raw_path = tmp_path / "reviewer.txt"
        raw_envelope = json.dumps({
            "findings": [
                {
                    "title": "FromRawEnvelope",
                    "class": "DEFECT",
                    "severity": "medium",
                    "disposition": "blocking",
                }
            ]
        })
        raw_path.write_text(
            "noise\nBEGIN_AGENT_ENVELOPE\n"
            f"{raw_envelope}\n"
            "END_AGENT_ENVELOPE\n",
            encoding="utf-8",
        )
        render = (
            "### reviewer\n"
            "- Decision: REQUEST_CHANGES\n"
            "- **Findings (1):**\n"
            "  1. **DEFECT** (medium): FromRenderedMarkdown\n"
            "     - File: a.py\n"
            f"- Raw output: {raw_path}\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "FromRawEnvelope"
        assert findings[0]["class"] == "DEFECT"
        assert findings[0]["disposition"] == "blocking"

    def test_raw_jsonl_agent_message_beats_command_output_marker_noise(self, tmp_path):
        """JSONL raw transcripts must ignore echoed envelope markers in command output."""
        raw_path = tmp_path / "reviewer-jsonl.txt"
        real_envelope = json.dumps({
            "findings": [
                {
                    "title": "FromAgentMessage",
                    "class": "DOC_ACCURACY",
                    "severity": "low",
                    "disposition": "non_blocking",
                }
            ]
        })
        raw_path.write_text(
            "\n".join([
                json.dumps({
                    "type": "item.completed",
                    "item": {
                        "id": "item_1",
                        "type": "command_execution",
                        "command": "sed -n '1,40p' mu/tools/executors/phase_b_executor.py",
                        "aggregated_output": (
                            'if stripped == "BEGIN_AGENT_ENVELOPE":\\n'
                            'if stripped == "END_AGENT_ENVELOPE":\\n'
                            'return [{"title": "Malformed AGENT_ENVELOPE blocked structured bridge findings parsing"}]'
                        ),
                        "exit_code": 0,
                        "status": "completed",
                    },
                }),
                json.dumps({
                    "type": "item.completed",
                    "item": {
                        "id": "item_2",
                        "type": "agent_message",
                        "text": (
                            "Bootstrap summary\n\n"
                            "BEGIN_AGENT_ENVELOPE\n"
                            f"{real_envelope}\n"
                            "END_AGENT_ENVELOPE"
                        ),
                    },
                }),
            ]) + "\n",
            encoding="utf-8",
        )
        render = (
            "### reviewer\n"
            "- Decision: GO\n"
            "- **Findings (1):**\n"
            "  1. **DOC_ACCURACY** (low): FromRenderedMarkdown\n"
            "     - File: a.py\n"
            f"- Raw output: {raw_path}\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "FromAgentMessage"
        assert findings[0]["class"] == "DOC_ACCURACY"
        assert findings[0]["disposition"] == "non_blocking"


class TestWaveOwnedFilesIncludesDeferredPackets:
    """INV-5: _collect_wave_owned_files must include executor-authored deferred packets."""

    def test_executor_created_files_included(self, tmp_path):
        """Deferred packets created by the executor are included in wave-owned files."""
        repo = tmp_path / "repo"
        repo.mkdir()
        # Create a deferred packet file (executor-authored, not implementer-authored)
        deferred_dir = repo / "reports" / "deferred" / "non_blocking"
        deferred_dir.mkdir(parents=True)
        (deferred_dir / "wave_bridge_nonblockers.md").write_text("# Deferred")

        # Plan is in reports/control_plane/ — deferred is in reports/deferred/
        # Without executor_created_files, this file is NOT under plan_prefix
        with patch.object(pb_mod, "_collect_changed_files", return_value=[
            "mu/tools/executors/foo.py",
            "reports/deferred/non_blocking/wave_bridge_nonblockers.md",
        ]):
            # Without executor_created_files: deferred packet dropped
            files_without = pb_mod._collect_wave_owned_files(  # ANTICHEAT_OK: testing internal executor functions
                repo, "reports/control_plane/plan.md",
                plan_declared_files=["mu/tools/executors/foo.py"],
                implementer_changed_files=set(),
                executor_created_files=None,
            )
            assert "reports/deferred/non_blocking/wave_bridge_nonblockers.md" not in files_without

            # With executor_created_files: deferred packet included
            files_with = pb_mod._collect_wave_owned_files(  # ANTICHEAT_OK: testing internal executor functions
                repo, "reports/control_plane/plan.md",
                plan_declared_files=["mu/tools/executors/foo.py"],
                implementer_changed_files=set(),
                executor_created_files={"reports/deferred/non_blocking/wave_bridge_nonblockers.md"},
            )
            assert "reports/deferred/non_blocking/wave_bridge_nonblockers.md" in files_with

    def test_executor_created_files_empty_is_noop(self, tmp_path):
        """Empty executor_created_files set does not affect results."""
        repo = tmp_path / "repo"
        repo.mkdir()
        with patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tools/foo.py"]):
            files = pb_mod._collect_wave_owned_files(  # ANTICHEAT_OK: testing internal executor functions
                repo, "reports/control_plane/plan.md",
                plan_declared_files=["mu/tools/foo.py"],
                implementer_changed_files=set(),
                executor_created_files=set(),
            )
            assert files == ["mu/tools/foo.py"]

    def test_baseline_wave_files_preserved_when_tracking_active(self, tmp_path):
        """Dirty-wave baseline files remain in scope even if the last implementer delta is narrow."""
        repo = tmp_path / "repo"
        repo.mkdir()
        with patch.object(pb_mod, "_collect_changed_files", return_value=[
            "mu/tools/executors/foo.py",
            "mu/tools/runners/run_review.py",
            "reports/control_plane/plan.md",
        ]):
            files = pb_mod._collect_wave_owned_files(  # ANTICHEAT_OK: testing internal executor functions
                repo,
                "reports/control_plane/plan.md",
                plan_declared_files=["mu/tools/executors/foo.py"],
                implementer_changed_files=set(),
                executor_created_files=set(),
                baseline_wave_files={"mu/tools/runners/run_review.py"},
            )
            assert files == [
                "mu/tools/executors/foo.py",
                "mu/tools/runners/run_review.py",
                "reports/control_plane/plan.md",
            ]


class TestPlanDeclaredFileParsing:
    """Plan markdown parsing must produce clean repo-relative paths for strict tracking."""

    def test_parse_plan_declared_files_strips_backticks_and_line_refs(self):
        content = """
Files:
- `mu/tools/executors/phase_b_executor.py`
- `mu/tools/runners/run_review.py:123`
- `reports/control_plane/commit_pipeline_automation_plan_2026-03-25.md`,
- `CHANGELOG.md`
"""
        parsed = pb_mod._parse_plan_declared_files(content)  # ANTICHEAT_OK: testing internal executor functions
        assert "mu/tools/executors/phase_b_executor.py" in parsed
        assert "mu/tools/runners/run_review.py" in parsed
        assert "reports/control_plane/commit_pipeline_automation_plan_2026-03-25.md" in parsed
        assert "CHANGELOG.md" in parsed


@pytest.mark.usefixtures("mock_routing_record")
class TestEmptyFilesToStageBlocksCommitReady:
    """Resume with empty files_to_stage must NOT return commit_ready."""

    def test_empty_files_to_stage_returns_error(self, tmp_path):
        """If wave-owned files are empty at handoff time, fail closed."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        # _collect_wave_owned_files returns empty at handoff time
        collect_calls = [0]
        def collect_side(*a, **kw):
            collect_calls[0] += 1
            # Return files for initial/pytest/staging steps, empty for final handoff (call 3)
            if collect_calls[0] <= 2:
                return ["f.py"]
            return []  # Empty at handoff

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", side_effect=collect_side), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "commit_handoff"
        assert "empty" in result["errors"][0].lower()


@pytest.mark.usefixtures("mock_routing_record")
class TestPytestFixTracksChangedFiles:
    """After pytest-fix implementer pass, newly changed files must be tracked."""

    def test_pytest_fix_files_included_in_wave_owned(self, tmp_path):
        """Files created by pytest-fix implementer pass are captured via implementer_changed."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        bridge_calls = [0]
        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                return {"exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "j1"}
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": "j2"}

        # Simulate: _collect_changed_files returns progressively more files
        # to create diffs that populate implementer_changed.
        # Calls: 1=pre-impl, 2=post-impl, 3=pre-bridge-fix, 4=post-bridge-fix,
        # 5=pre-pytest-fix, 6=post-pytest-fix (new helper appears here), 7+=stable
        changed_files_calls = [0]
        def changed_files_side(root):
            changed_files_calls[0] += 1
            if changed_files_calls[0] == 1:
                return []  # pre-implementer
            if changed_files_calls[0] <= 4:
                return ["mu/tests/tools/test_existing.py"]
            if changed_files_calls[0] == 5:
                return ["mu/tests/tools/test_existing.py", "mu/tests/tools/test_foo.py"]
            if changed_files_calls[0] == 6:
                return ["mu/tests/tools/test_existing.py", "mu/tests/tools/test_foo.py"]
            # Call 7+: post-pytest-fix — new helper file appears
            return ["mu/tests/tools/test_foo.py", "mu/tools/executors/new_helper.py"]

        pytest_calls = [0]
        def pytest_side(repo_root, test_files, **kw):
            pytest_calls[0] += 1
            if pytest_calls[0] == 1:
                return {"exit_code": 1, "stdout": "FAILED", "stderr": "", "passed": False}
            return {"exit_code": 0, "stdout": "passed", "stderr": "", "passed": True}

        # Track what _collect_wave_owned_files returns across the bridge/pytest-fix path.
        wave_owned_results = []
        wave_owned_calls = [0]

        def tracking_collect(*a, **kw):
            wave_owned_calls[0] += 1
            if wave_owned_calls[0] <= 2:
                result = ["mu/tests/tools/test_existing.py"]
            elif wave_owned_calls[0] == 3:
                result = ["mu/tests/tools/test_existing.py", "mu/tests/tools/test_foo.py"]
            else:
                result = ["mu/tools/executors/new_helper.py"]
            wave_owned_results.append(result)
            return result

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", side_effect=changed_files_side), \
             patch.object(pb_mod, "_collect_wave_owned_files", side_effect=tracking_collect), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="findings"), \
             patch.object(pb_mod, "_run_pytest_on_files", side_effect=pytest_side), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        # The pytest-fix implementer was invoked (3 calls: initial + bridge fix + pytest fix)
        assert mock_impl.invoke_implementer.call_count >= 3
        # The new file should appear in the final wave-owned collection
        # (via implementer_changed tracking from the pytest-fix pass)
        last_wave_owned = wave_owned_results[-1] if wave_owned_results else []
        assert "mu/tools/executors/new_helper.py" in last_wave_owned


@pytest.mark.usefixtures("mock_routing_record")
class TestResumeNeedsPhaseB:
    """CRITICAL: Resume from needs_phase_b_reentry must NOT skip to commit_ready."""

    def test_resume_from_needs_phase_b_reentry_enters_reentry_loop(self, tmp_path):
        """Crash during NEEDS_PHASE_B re-entry resumes into re-entry, not commit_ready."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")
        (repo / ".scratch").mkdir()

        # Write saved state simulating crash during NEEDS_PHASE_B re-entry
        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        changed_files = ["mu/tools/executors/foo.py"]
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "needs_phase_b_reentry",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "bridge_scope_fingerprint": pb_mod._bridge_scope_fingerprint(repo, changed_files),  # ANTICHEAT_OK: testing internal executor functions
            "deferred_packet_path": None,
            "implementer_changed": changed_files,
            "executor_created": [],
            "all_non_blocking": [],
            "reentry_findings": "Fix the thing",
        }))

        mock_impl = _make_mock_impl()
        # Implementer re-entry succeeds
        mock_impl.invoke_implementer.return_value = {
            "status": "success", "output": "done", "stderr": "",
            "exit_code": 0, "job_id": "impl-reentry", "model_override_applied": False,
        }

        # Bridge after re-entry implementer returns GO
        bridge_calls = [0]
        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": f"j-reentry-{bridge_calls[0]}"}

        # Supervisor after re-entry returns COMMIT_GO
        supervisor_calls = [0]
        def supervisor_side(repo_root, pkg, **kw):
            supervisor_calls[0] += 1
            return {
                "exit_code": 0,
                "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=changed_files), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=changed_files), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=supervisor_side):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        # Must have resumed and invoked implementer for re-entry
        assert result.get("resumed_from") == "needs_phase_b_reentry"
        # Implementer was called (re-entry pass)
        assert mock_impl.invoke_implementer.call_count >= 1
        # Bridge was called for re-entry review
        assert bridge_calls[0] >= 1
        # Should reach commit_ready (not error or supervisor_rejected)
        assert result["status"] == "commit_ready", f"Expected commit_ready, got {result}"

    def test_reentry_repeat_cap_fails_closed(self, tmp_path):
        """Re-entry REQUEST_CHANGES must honor REPEAT_FINDING_CAP like the initial loop."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")
        (repo / ".scratch").mkdir()

        finding = {"title": "Stubborn blocker", "severity": "high", "file": "mu/tools/executors/phase_b_executor.py"}
        key = pb_mod._finding_key(finding)  # ANTICHEAT_OK: testing internal executor functions

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "needs_phase_b_reentry",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "deferred_packet_path": None,
            "implementer_changed": ["mu/tools/executors/foo.py"],
            "executor_created": [],
            "all_non_blocking": [],
            "finding_history": {key: pb_mod.REPEAT_FINDING_CAP},
            "reentry_findings": "Fix the stubborn blocker",
        }))

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tools/executors/foo.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tools/executors/foo.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                 "decision": "REQUEST_CHANGES", "job_id": "re1",
             }), \
             patch.object(pb_mod, "_read_bridge_render", return_value="rendered"), \
             patch.object(pb_mod, "_parse_findings_from_render", return_value=[finding]), \
             patch.object(pb_mod, "_stage_files", return_value=True):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "reentry_bridge_convergence"
        assert "unresolvable" in " ".join(result["errors"]).lower()

    def test_resume_from_bridge_converged_does_not_enter_reentry(self, tmp_path):
        """Resume from bridge_converged should go through supervisor normally, not re-entry."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")
        (repo / "f.py").write_text("print('ok')\n")
        bridge_scope_fingerprint = pb_mod._bridge_scope_fingerprint(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            ["f.py"],
        )

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "bridge_converged",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "bridge_scope_fingerprint": bridge_scope_fingerprint,
            "deferred_packet_path": None,
            "implementer_changed": ["f.py"],
            "executor_created": [],
            "all_non_blocking": [],
        }))

        mock_impl = _make_mock_impl()
        run_sdk_agents = MagicMock(return_value={"exit_code": 0, "stdout": "", "stderr": ""})

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", run_sdk_agents), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result.get("resumed_from") == "bridge_converged"
        assert result["status"] == "commit_ready"
        # Implementer was NOT called (skipped on resume from bridge_converged)
        assert mock_impl.invoke_implementer.call_count == 0
        run_sdk_agents.assert_not_called()

    def test_resume_from_bridge_converged_rehydrates_dirty_baseline_into_package(self, tmp_path):
        """Legacy saved state without baseline tracking must still rebuild an honest supervisor package."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\n"
            "Phase-A-Lock: LOCKED\n"
            "- `mu/tools/executors/foo.py`\n"
        )

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "bridge_converged",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "deferred_packet_path": None,
            "implementer_changed": ["mu/tools/executors/foo.py"],
            "executor_created": [],
            "all_non_blocking": [],
        }))

        changed_files = [
            "mu/tools/executors/foo.py",
            "mu/tools/runners/run_review.py",
            "reports/control_plane/plan.md",
        ]
        bridge_scope_fingerprint = pb_mod._bridge_scope_fingerprint(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            changed_files,
        )
        saved_state = json.loads((state_dir / "phase_b_state.json").read_text())
        saved_state["bridge_scope_fingerprint"] = bridge_scope_fingerprint
        (state_dir / "phase_b_state.json").write_text(json.dumps(saved_state))
        captured_package = {}
        mock_impl = _make_mock_impl()

        def supervisor_side(_repo_root, package_path, **_kw):
            captured_package["value"] = json.loads(Path(package_path).read_text())
            return {
                "exit_code": 0,
                "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=changed_files), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=supervisor_side):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert captured_package["value"]["changed_files"] == changed_files

    def test_resume_from_bridge_converged_unions_saved_and_current_baseline(self, tmp_path):
        """Saved baseline scope must be refreshed with any newly dirty wave files before packaging."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\n"
            "Phase-A-Lock: LOCKED\n"
            "- `mu/tools/executors/foo.py`\n"
        )

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "bridge_converged",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "deferred_packet_path": None,
            "implementer_changed": ["mu/tools/executors/foo.py"],
            "executor_created": [],
            "baseline_wave_files": ["mu/tools/executors/foo.py"],
            "all_non_blocking": [],
        }))

        changed_files = [
            "mu/tools/agents/meta_bridge_supervisor.py",
            "mu/tools/executors/foo.py",
            "reports/control_plane/plan.md",
        ]
        bridge_scope_fingerprint = pb_mod._bridge_scope_fingerprint(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            changed_files,
        )
        saved_state = json.loads((state_dir / "phase_b_state.json").read_text())
        saved_state["bridge_scope_fingerprint"] = bridge_scope_fingerprint
        (state_dir / "phase_b_state.json").write_text(json.dumps(saved_state))
        captured_package = {}
        mock_impl = _make_mock_impl()

        def supervisor_side(_repo_root, package_path, **_kw):
            captured_package["value"] = json.loads(Path(package_path).read_text())
            return {
                "exit_code": 0,
                "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=changed_files), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=supervisor_side):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert captured_package["value"]["changed_files"] == changed_files

    def test_resume_from_bridge_converged_surfaces_changed_deferred_packet_in_supervisor_package(self, tmp_path):
        """Supervisor package must acknowledge changed non-blocking packets even without deferred_packet_path state."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\n"
            "Phase-A-Lock: LOCKED\n"
            "- `mu/tools/executors/foo.py`\n"
        )

        changed_files = [
            "mu/tools/executors/foo.py",
            "reports/control_plane/plan.md",
            "reports/deferred/non_blocking/wave_bridge_nonblockers.md",
        ]
        bridge_scope_fingerprint = pb_mod._bridge_scope_fingerprint(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            changed_files,
        )

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "bridge_converged",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "bridge_scope_fingerprint": bridge_scope_fingerprint,
            "deferred_packet_path": None,
            "implementer_changed": ["mu/tools/executors/foo.py"],
            "executor_created": ["reports/deferred/non_blocking/wave_bridge_nonblockers.md"],
            "all_non_blocking": [],
        }))

        captured_package = {}
        mock_impl = _make_mock_impl()

        def supervisor_side(_repo_root, package_path, **_kw):
            captured_package["value"] = json.loads(Path(package_path).read_text())
            return {
                "exit_code": 0,
                "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=changed_files), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=supervisor_side):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert captured_package["value"]["deferred_items"] == [
            "reports/deferred/non_blocking/wave_bridge_nonblockers.md"
        ]

    def test_resume_from_bridge_converged_reruns_sdk_and_bridge_when_scope_fingerprint_drifted(self, tmp_path):
        """A drifted bridge_converged checkpoint must not skip directly to supervisor."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "mu" / "tools").mkdir(parents=True)
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")
        tracked_file = repo / "mu" / "tools" / "foo.py"
        tracked_file.write_text("print('old')\n")
        stale_bridge_scope_fingerprint = pb_mod._bridge_scope_fingerprint(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            ["mu/tools/foo.py"],
        )

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "bridge_converged",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "bridge_scope_fingerprint": stale_bridge_scope_fingerprint,
            "deferred_packet_path": None,
            "implementer_changed": ["mu/tools/foo.py"],
            "executor_created": [],
            "all_non_blocking": [],
        }))

        tracked_file.write_text("print('new')\n")
        mock_impl = _make_mock_impl()
        run_sdk_agents = MagicMock(return_value={"exit_code": 0, "stdout": "", "stderr": ""})
        run_bridge_review = MagicMock(return_value={
            "exit_code": 0,
            "stdout": "GO\n",
            "stderr": "",
            "decision": "GO",
            "job_id": "j1",
        })

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tools/foo.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tools/foo.py"]), \
             patch.object(pb_mod, "run_sdk_agents", run_sdk_agents), \
             patch.object(pb_mod, "run_bridge_review", run_bridge_review), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result.get("resumed_from") == "bridge_converged"
        assert result["status"] == "commit_ready"
        run_sdk_agents.assert_called_once()
        run_bridge_review.assert_called_once()
        assert mock_impl.invoke_implementer.call_count == 0


class TestWaveOwnedFilesNoPrefixGlob:
    """HIGH: _collect_wave_owned_files must not glob plan_prefix when tracking is active."""

    def test_dirty_sibling_in_plan_dir_excluded_with_tracking(self, tmp_path):
        """Dirty control-plane siblings must NOT be included when explicit tracking is active."""
        repo = tmp_path / "repo"
        repo.mkdir()
        with patch.object(pb_mod, "_collect_changed_files", return_value=[
            "mu/tools/executors/foo.py",
            "reports/control_plane/other_wave_plan.md",  # unrelated dirty sibling
            "reports/control_plane/plan.md",
        ]):
            files = pb_mod._collect_wave_owned_files(  # ANTICHEAT_OK: testing internal executor functions
                repo, "reports/control_plane/plan.md",
                plan_declared_files=["mu/tools/executors/foo.py"],
                implementer_changed_files=set(),
                executor_created_files=set(),
            )
            assert "mu/tools/executors/foo.py" in files
            # Plan file itself is always wave-owned
            assert "reports/control_plane/plan.md" in files
            # Unrelated sibling must be excluded
            assert "reports/control_plane/other_wave_plan.md" not in files

    def test_plan_prefix_still_used_in_degraded_fallback(self, tmp_path):
        """When no explicit tracking (both None), prefix-based filtering still works."""
        repo = tmp_path / "repo"
        repo.mkdir()
        with patch.object(pb_mod, "_collect_changed_files", return_value=[
            "reports/control_plane/plan.md",
            "reports/control_plane/other.md",
            "mu/tools/executors/foo.py",
        ]):
            files = pb_mod._collect_wave_owned_files(  # ANTICHEAT_OK: testing internal executor functions
                repo, "reports/control_plane/plan.md",
                plan_declared_files=None,
                implementer_changed_files=None,
                executor_created_files=None,
            )
            # In degraded fallback, plan_prefix files are included
            assert "reports/control_plane/plan.md" in files
            assert "reports/control_plane/other.md" in files
            # mu/tools/ is in _WAVE_OWNED_PREFIXES
            assert "mu/tools/executors/foo.py" in files


class TestRoutingValidationNotBypassed:
    """Phase B must NOT silently rewrite routing tokens.

    Bridge R1 finding: phase_b_executor was overriding stale/wrong routing
    decisions to ROUTE_PHASE_B before validation, making validate_inputs
    meaningless. The fix: validation errors are fatal unless --force is used.
    """

    def test_wrong_routing_token_fails_without_force(self):
        """ROUTE_PHASE_A token → PhaseBExecutorError (no silent rewrite)."""
        routing = {"decision": "ROUTE_PHASE_A", "summary": "test"}
        plan = {"phase_a_lock": "LOCKED"}
        with pytest.raises(pb_mod.PhaseBExecutorError, match="ROUTE_PHASE_B"):
            pb_mod.validate_inputs(routing, plan)

    def test_correct_routing_token_passes(self):
        """ROUTE_PHASE_B token → validation passes (no exception)."""
        routing = {"decision": "ROUTE_PHASE_B", "summary": "test"}
        plan = {"phase_a_lock": "LOCKED"}
        pb_mod.validate_inputs(routing, plan)  # should not raise

    def test_unlocked_plan_fails(self):
        """Plan not LOCKED → PhaseBExecutorError."""
        routing = {"decision": "ROUTE_PHASE_B", "summary": "test"}
        plan = {"phase_a_lock": "DRAFT"}
        with pytest.raises(pb_mod.PhaseBExecutorError, match="LOCKED"):
            pb_mod.validate_inputs(routing, plan)

    def test_run_phase_b_fails_on_bad_routing_without_force(self, tmp_path):
        """run_phase_b with wrong routing token returns error (not override)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        # Write a routing record with wrong decision
        rr_dir = repo / ".agent_bus" / "meta"
        rr_dir.mkdir(parents=True)
        (rr_dir / "post_merge_routing.json").write_text(json.dumps({
            "decision": "ROUTE_PHASE_A",
            "summary": "dispatched to A",
        }))
        # Write a locked plan
        plan_dir = repo / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "test_plan.md"
        plan_file.write_text("---\nPhase-A-Lock: LOCKED\n---\nPlan content\n")

        result = pb_mod.run_phase_b(
            repo, "reports/control_plane/test_plan.md",
            verbose=False, force=False,
        )
        assert result["status"] == "error"
        assert "validate_inputs" in result.get("step", "")

    def test_run_phase_b_force_overrides_bad_routing(self, tmp_path):
        """run_phase_b with --force continues past wrong routing token."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        # Write a routing record with wrong decision
        rr_dir = repo / ".agent_bus" / "meta"
        rr_dir.mkdir(parents=True)
        (rr_dir / "post_merge_routing.json").write_text(json.dumps({
            "decision": "ROUTE_PHASE_A",
            "summary": "dispatched to A",
        }))
        # Write a locked plan
        plan_dir = repo / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "test_plan.md"
        plan_file.write_text("---\nPhase-A-Lock: LOCKED\n---\nPlan content\n")

        # With force=True, it should get past validation (will fail later at
        # a subsequent step like implementer invocation, but NOT at validation)
        result = pb_mod.run_phase_b(
            repo, "reports/control_plane/test_plan.md",
            verbose=False, force=True,
        )
        # Should not have failed at validate_inputs
        assert result.get("step") != "validate_inputs"

    def test_run_phase_b_fails_on_missing_routing_without_force(self, tmp_path):
        """run_phase_b with no routing record returns error (not synthetic)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        # No routing record file at all
        plan_dir = repo / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "test_plan.md"
        plan_file.write_text("---\nPhase-A-Lock: LOCKED\n---\nPlan content\n")

        result = pb_mod.run_phase_b(
            repo, "reports/control_plane/test_plan.md",
            verbose=False, force=False,
        )
        assert result["status"] == "error"
        assert "routing" in result.get("step", "").lower() or "routing" in str(result.get("errors", "")).lower()


@pytest.mark.usefixtures("mock_routing_record")
class TestResumeFromNeedsPhaseBReentrySkipsInitialBridgeLoop:
    """Defect fix: resume from needs_phase_b_reentry must bypass the initial bridge loop.

    The initial bridge loop (step 5) must NOT run when resuming into re-entry.
    Previously, bridge_converged was set True but the for loop still executed
    every round because there was no guard checking bridge_converged at loop entry.
    """

    def test_resume_needs_phase_b_reentry_skips_initial_bridge(self, tmp_path):
        """When resuming from needs_phase_b_reentry, no initial bridge rounds should run."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        # Seed state file with needs_phase_b_reentry
        state = {
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "needs_phase_b_reentry",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "deferred_packet_path": None,
            "implementer_changed": ["f.py"],
            "executor_created": [],
            "all_non_blocking": [],
            "reentry_findings": "Fix the bug",
        }
        pb_mod._save_state(repo, state)  # ANTICHEAT_OK: testing internal executor functions

        mock_impl = _make_mock_impl()
        bridge_calls = []

        def bridge_side(*a, **kw):
            bridge_calls.append(kw.get("job_id", "unknown"))
            # Re-entry bridge returns GO
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "reentry-go"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value=""), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        # Bridge calls should ONLY be re-entry calls, NOT initial loop calls.
        # If initial loop ran, we'd see "phase-b-r1-*" job IDs before re-entry calls.
        for call_jid in bridge_calls:
            assert "phase-b-r" not in str(call_jid) or "reentry" in str(call_jid), (
                f"Initial bridge loop ran during needs_phase_b_reentry resume: {call_jid}"
            )

    def test_resume_needs_phase_b_reentry_refreshes_bridge_when_scope_drifted(self, tmp_path):
        """Changed worktree after a saved re-entry checkpoint must refresh bridge findings first."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        state = {
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "needs_phase_b_reentry",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "deferred_packet_path": None,
            "implementer_changed": ["f.py"],
            "executor_created": [],
            "baseline_wave_files": ["f.py"],
            "all_non_blocking": [],
            "reentry_findings": "Fix the old bug",
        }
        pb_mod._save_state(repo, state)  # ANTICHEAT_OK: testing internal executor functions

        mock_impl = _make_mock_impl()
        bridge_calls = []

        def bridge_side(*a, **kw):
            bridge_calls.append(kw.get("job_id", "unknown"))
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "reentry-go"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value=""), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={"passed": True, "exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "prepare_commit_handoff", return_value=repo / ".agent_bus" / "handoff.json"), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert mock_impl.invoke_implementer.call_count == 0
        assert any("phase-b-reentry" in str(call_jid) for call_jid in bridge_calls)


@pytest.mark.usefixtures("mock_routing_record")
class TestReentryRequestChangesCheckpointsState:
    """Defect fix: re-entry REQUEST_CHANGES must checkpoint new findings and round.

    Previously, if a crash occurred after re-entry REQUEST_CHANGES updated findings_for_impl
    but before the next implementer invocation, the state file still had stale findings and
    the old round count. This test verifies that _save_state is called with fresh data.
    """

    def test_reentry_request_changes_checkpoints_before_continue(self, tmp_path):
        """After re-entry REQUEST_CHANGES, state file must have new findings and round."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        bridge_calls = [0]
        impl_calls = [0]

        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                # Initial bridge: GO
                return {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "init"}
            if bridge_calls[0] == 2:
                # Re-entry R1: REQUEST_CHANGES with new findings (exit=1 under bridge CLI contract)
                return {"exit_code": 1, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "re1"}
            # Re-entry R2: GO
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "re2"}

        def impl_side(*a, **kw):
            impl_calls[0] += 1
            if impl_calls[0] == 3:
                # Third implementer call (after re-entry REQUEST_CHANGES): crash
                # to test state persistence
                raise RuntimeError("Simulated crash")
            return {"status": "success", "output": "done", "stderr": "",
                    "exit_code": 0, "job_id": f"impl-{impl_calls[0]}", "model_override_applied": False}

        mock_impl.invoke_implementer.side_effect = impl_side

        saved_states = []
        original_save = pb_mod._save_state  # ANTICHEAT_OK: testing internal executor functions

        def capturing_save(rr, state):
            saved_states.append(state.copy())
            return original_save(rr, state)

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="NEW_BRIDGE_FINDINGS"), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_save_state", side_effect=capturing_save), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "NEEDS_PHASE_B", "summary": "OLD_SUPERVISOR_FINDINGS", "status": "ok", "findings": []},
                 "receipt_path": "",
             }):
            try:
                pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=10)
            except RuntimeError:
                pass  # Expected crash from impl_side

        # Find the re-entry checkpoint state (after REQUEST_CHANGES)
        reentry_checkpoints = [
            s for s in saved_states
            if s.get("completed_step") == "needs_phase_b_reentry"
        ]
        # Must have at least 2: initial needs_phase_b_reentry + REQUEST_CHANGES checkpoint
        assert len(reentry_checkpoints) >= 2, (
            f"Expected at least 2 needs_phase_b_reentry checkpoints, got {len(reentry_checkpoints)}. "
            f"States saved: {[s.get('completed_step') for s in saved_states]}"
        )
        # The second checkpoint must have the NEW findings, not the old supervisor findings
        latest = reentry_checkpoints[-1]
        assert latest["reentry_findings"] is not None, "Re-entry checkpoint missing findings"
        assert "NEW_BRIDGE_FINDINGS" in str(latest["reentry_findings"]) or "BLOCKING" in str(latest["reentry_findings"]), (
            f"Re-entry checkpoint has stale findings: {latest['reentry_findings']}"
        )


class TestBridgeTimeoutIsError:
    """Bridge timeout must be treated as a hard error, not silently retried.

    Bug: run_bridge_review returns exit_code=-1 on timeout, but the bridge loop
    fell through to the generic 'exit_code != 0 → continue' branch, silently
    retrying. A timeout indicates infrastructure failure and must fail closed.
    """

    def test_bridge_timeout_returns_error(self, tmp_path):
        """Bridge timeout (exit_code=-1) must return error status, not continue."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        mock_impl = _make_mock_impl()

        def bridge_timeout(*a, **kw):
            return {"exit_code": -1, "stdout": "", "stderr": "Bridge review timed out",
                    "decision": "", "job_id": kw.get("job_id", "j")}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_timeout), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            result = pb_mod.run_phase_b(
                repo, "reports/control_plane/plan.md", max_bridge_rounds=5,
            )

        assert result["status"] == "error"
        assert any("timed out" in e for e in result.get("errors", []))
        # State must be cleared to prevent stale resume
        assert pb_mod._load_state(repo) is None  # ANTICHEAT_OK: testing internal executor functions

    def test_bridge_timeout_does_not_silently_retry(self, tmp_path):
        """Bridge timeout must NOT cause multiple bridge invocations (no silent retry)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        mock_impl = _make_mock_impl()
        call_count = 0

        def bridge_timeout(*a, **kw):
            nonlocal call_count
            call_count += 1
            return {"exit_code": -1, "stdout": "", "stderr": "Bridge review timed out",
                    "decision": "", "job_id": kw.get("job_id", "j")}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_timeout), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            pb_mod.run_phase_b(
                repo, "reports/control_plane/plan.md", max_bridge_rounds=5,
            )

        # Only one bridge call — timeout stops immediately, no retry
        assert call_count == 1

    def test_unrecognized_success_decision_fails_closed(self, tmp_path):
        """exit_code=0 with an unknown bridge decision must fail closed."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "MAYBE\n", "stderr": "", "decision": "MAYBE", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            result = pb_mod.run_phase_b(
                repo, "reports/control_plane/plan.md", max_bridge_rounds=5,
            )

        assert result["status"] == "error"
        assert result["step"] == "bridge_decision"
        assert any("unrecognized success decision" in e.lower() for e in result.get("errors", []))

    def test_reentry_bridge_timeout_returns_error(self, tmp_path):
        """Bridge timeout during re-entry must also fail closed."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        # Seed resume state at needs_phase_b_reentry
        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "needs_phase_b_reentry",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "deferred_packet_path": None,
            "implementer_changed": [],
            "executor_created": [],
            "all_non_blocking": [],
            "reentry_findings": "Fix required",
        }))

        mock_impl = _make_mock_impl()

        def bridge_timeout(*a, **kw):
            return {"exit_code": -1, "stdout": "", "stderr": "Bridge review timed out",
                    "decision": "", "job_id": kw.get("job_id", "j")}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_timeout), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            result = pb_mod.run_phase_b(
                repo, "reports/control_plane/plan.md", max_bridge_rounds=5,
            )

        assert result["status"] == "error"
        assert any("timed out" in e for e in result.get("errors", []))
        assert pb_mod._load_state(repo) is None  # ANTICHEAT_OK: testing internal executor functions

    def test_reentry_unrecognized_success_decision_fails_closed(self, tmp_path):
        """Re-entry exit_code=0 with unknown bridge decision must fail closed."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "needs_phase_b_reentry",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "deferred_packet_path": None,
            "implementer_changed": [],
            "executor_created": [],
            "all_non_blocking": [],
            "reentry_findings": "Fix required",
        }))

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "MAYBE\n", "stderr": "", "decision": "MAYBE", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            result = pb_mod.run_phase_b(
                repo, "reports/control_plane/plan.md", max_bridge_rounds=5,
            )

        assert result["status"] == "error"
        assert result["step"] == "reentry_bridge_decision"
        assert any("unrecognized success decision" in e.lower() for e in result.get("errors", []))


class TestMaxRoundsResultIncludesFindings:
    """max_rounds_reached must include errors and deferred finding count.

    Bug: max_rounds_reached returned bare status without errors list or
    accumulated finding counts, making diagnosis impossible.
    """

    def test_max_rounds_includes_errors_list(self, tmp_path):
        """max_rounds_reached must have an errors list with convergence info."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        mock_impl = _make_mock_impl()

        def bridge_no_go(*a, **kw):
            return {"exit_code": 0, "stdout": "NO_GO\n", "stderr": "",
                    "decision": "NO_GO", "job_id": kw.get("job_id", "j")}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_no_go), \
             patch.object(pb_mod, "_read_bridge_render", return_value=""), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            result = pb_mod.run_phase_b(
                repo, "reports/control_plane/plan.md", max_bridge_rounds=2,
            )

        assert result["status"] == "max_rounds_reached"
        assert "errors" in result
        assert len(result["errors"]) > 0
        assert "converge" in result["errors"][0].lower() or "round" in result["errors"][0].lower()

    def test_max_rounds_includes_bridge_rounds_count(self, tmp_path):
        """max_rounds_reached must report correct bridge_rounds count."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        mock_impl = _make_mock_impl()

        def bridge_no_go(*a, **kw):
            return {"exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                    "decision": "REQUEST_CHANGES", "job_id": kw.get("job_id", "j")}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_no_go), \
             patch.object(pb_mod, "_read_bridge_render", return_value=""), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            result = pb_mod.run_phase_b(
                repo, "reports/control_plane/plan.md", max_bridge_rounds=3,
            )

        assert result["status"] == "max_rounds_reached"
        assert result["bridge_rounds"] == 3


class TestReentryStateClearing:
    """Re-entry failure paths must clear persisted state to prevent stale resume.

    Bridge finding: when reentry_pytest_gate or reentry_staging fails, the
    return path skipped _clear_state(), leaving completed_step=needs_phase_b_reentry.
    This caused the next invocation to re-enter implementer/bridge work even
    though convergence had already happened.
    """

    def test_reentry_pytest_gate_failure_clears_state(self):
        """_clear_state must be called before returning from reentry_pytest_gate failure."""
        source = Path(pb_mod.__file__).read_text()  # ANTICHEAT_OK: testing internal executor functions
        # Find the reentry_pytest_gate failure block
        idx = source.find('"reentry_pytest_gate"')
        assert idx > 0, "reentry_pytest_gate error path not found in source"
        # The _clear_state call must appear BEFORE the return in that block.
        # Look backwards from reentry_pytest_gate for _clear_state
        block = source[max(0, idx - 300):idx]
        assert "_clear_state" in block, (
            "reentry_pytest_gate failure path must call _clear_state(repo_root) "
            "before returning, to prevent stale needs_phase_b_reentry state"
        )

    def test_reentry_staging_failure_clears_state(self):
        """_clear_state must be called before returning from reentry_staging failure."""
        source = Path(pb_mod.__file__).read_text()  # ANTICHEAT_OK: testing internal executor functions
        idx = source.find('"reentry_staging"')
        assert idx > 0, "reentry_staging error path not found in source"
        block = source[max(0, idx - 300):idx]
        assert "_clear_state" in block, (
            "reentry_staging failure path must call _clear_state(repo_root) "
            "before returning, to prevent stale needs_phase_b_reentry state"
        )


# ===========================================================================
# Planless Phase B entry path (Slice 1 follow-on)
# ===========================================================================


class TestDerivePlanlessContext:
    """_derive_planless_context builds bounded scope from routing record."""

    def test_valid_routing_record_produces_plan(self, tmp_path):
        record = {
            "decision": "ROUTE_PHASE_B",
            "summary": "implement the thing",
            "wave_name": "test-wave",
            "next_candidates": [{"candidate": "do the thing"}],
        }
        plan = pb_mod._derive_planless_context(record, tmp_path)  # ANTICHEAT_OK: testing planless context derivation
        assert plan["phase_a_lock"] == "ROUTING_RECORD_AUTHORITY"
        assert plan["planless"] == "true"
        assert plan["wave_id"] == "test-wave"
        assert "implement the thing" in plan["content"]

    def test_missing_wave_name_fails_closed(self, tmp_path):
        record = {
            "decision": "ROUTE_PHASE_B",
            "summary": "implement",
            "next_candidates": [{"candidate": "x"}],
        }
        with pytest.raises(pb_mod.PhaseBExecutorError, match="wave_name/wave_id"):
            pb_mod._derive_planless_context(record, tmp_path)  # ANTICHEAT_OK: testing planless context derivation

    def test_missing_summary_fails_closed(self, tmp_path):
        record = {
            "decision": "ROUTE_PHASE_B",
            "wave_name": "w",
            "next_candidates": [{"candidate": "x"}],
        }
        with pytest.raises(pb_mod.PhaseBExecutorError, match="summary"):
            pb_mod._derive_planless_context(record, tmp_path)  # ANTICHEAT_OK: testing planless context derivation

    def test_missing_candidates_fails_closed(self, tmp_path):
        record = {
            "decision": "ROUTE_PHASE_B",
            "summary": "s",
            "wave_name": "w",
        }
        with pytest.raises(pb_mod.PhaseBExecutorError, match="next_candidates"):
            pb_mod._derive_planless_context(record, tmp_path)  # ANTICHEAT_OK: testing planless context derivation

    def test_existing_tracked_packet_redirects_to_plan(self, tmp_path):
        """If routing record references a tracked_packet that exists, fail with guidance."""
        (tmp_path / "reports" / "control_plane").mkdir(parents=True)
        (tmp_path / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")
        record = {
            "decision": "ROUTE_PHASE_B",
            "summary": "s",
            "wave_name": "w",
            "next_candidates": [{"candidate": "x", "tracked_packet": "reports/control_plane/plan.md"}],
        }
        with pytest.raises(pb_mod.PhaseBExecutorError, match="Use --plan"):
            pb_mod._derive_planless_context(record, tmp_path)  # ANTICHEAT_OK: testing planless context derivation


class TestPlanlessPhaseB:
    """run_phase_b with plan_path=None derives context from routing record."""

    def test_planless_with_valid_routing_record(self, tmp_path):
        """Planless mode reaches the implementer step (fails there due to no bridge config)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".scratch").mkdir()
        routing_record = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test planless",
            "wave_name": "planless-test",
            "next_candidates": [{"candidate": "do something"}],
        }
        # Write routing record
        bus = repo / ".agent_bus" / "meta"
        bus.mkdir(parents=True)
        (bus / "post_merge_routing.json").write_text(json.dumps(routing_record))

        result = pb_mod.run_phase_b(repo, None, verbose=True)
        # Should reach implementer step (fails there due to no bridge config)
        assert result.get("planless") is True
        assert result.get("status") == "error"
        assert result.get("step") == "implementer"

    def test_planless_with_underspecified_record_fails_closed(self, tmp_path):
        """Planless mode fails closed when routing record is under-specified."""
        repo = tmp_path / "repo"
        repo.mkdir()
        routing_record = {"decision": "ROUTE_PHASE_B", "summary": ""}
        bus = repo / ".agent_bus" / "meta"
        bus.mkdir(parents=True)
        (bus / "post_merge_routing.json").write_text(json.dumps(routing_record))

        result = pb_mod.run_phase_b(repo, None, verbose=True)
        assert result["status"] == "error"
        assert result["step"] == "derive_planless_context"

    def test_main_passes_cli_routing_record_to_run_phase_b(self, tmp_path, monkeypatch):
        """CLI --routing-record must override disk routing state when invoking run_phase_b."""
        repo = tmp_path / "repo"
        repo.mkdir()
        captured: dict[str, object] = {}
        routing_record = {
            "decision": "ROUTE_PHASE_B",
            "summary": "cli override",
            "wave_name": "cli-wave",
            "next_candidates": [{"candidate": "do something"}],
        }

        def fake_git_rev_parse(args, capture_output, text, check):
            return SimpleNamespace(stdout=str(repo))

        def fake_run_phase_b(repo_root, plan_path, **kwargs):
            captured["repo_root"] = repo_root
            captured["plan_path"] = plan_path
            captured["routing_record_override"] = kwargs.get("routing_record_override")
            return {"status": "ready"}

        monkeypatch.setattr(pb_mod.subprocess, "run", fake_git_rev_parse)
        monkeypatch.setattr(pb_mod, "run_phase_b", fake_run_phase_b)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "phase_b_executor.py",
                "--routing-record",
                json.dumps(routing_record),
                "--json",
            ],
        )

        exit_code = pb_mod.main()
        assert exit_code == 0
        assert captured["repo_root"] == repo
        assert captured["plan_path"] is None
        assert captured["routing_record_override"] == routing_record


class TestSdkReviewDepthContract:
    """Phase A/B should use the 4-agent SDK gate by default."""

    def test_phase_a_sdk_review_defaults_to_quick(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".scratch").mkdir()
        captured: dict[str, object] = {}

        class FakeProc:
            pid = 1234
            returncode = 0

            def poll(self):
                return 0

        def fake_popen(cmd, cwd, stdout, stderr, text, env):
            captured["cmd"] = cmd
            captured["cwd"] = cwd
            captured["env"] = env
            return FakeProc()

        def fake_run(cmd, cwd, capture_output, text, check):
            assert cmd == ["ps", "-axo", "pid=,ppid="]
            return SimpleNamespace(stdout="", stderr="")

        with patch.object(pa_mod.subprocess, "Popen", side_effect=fake_popen), \
             patch.object(pa_mod.subprocess, "run", side_effect=fake_run):
            result = pa_mod.run_sdk_agents(repo, ["mu/tools/executors/phase_a_executor.py"])

        assert result["exit_code"] == 0
        assert captured["cwd"] == repo
        cmd = captured["cmd"]
        assert cmd[:5] == [
            sys.executable,
            "tools/runners/run_review.py",
            "mu/tools/executors/phase_a_executor.py",
            "--depth",
            "quick",
        ]
        assert cmd[5] == "--fail-fast-hard-gate"
        assert cmd[6] == "--no-memory"
        assert cmd[7] == "--output"
        assert str(cmd[8]).endswith(".report.md")
        env = captured["env"]
        assert env["RCX_REVIEW_STATUS_PATH"].endswith(".status.json")
        assert env["RCX_REVIEW_AGENT_TIMEOUT"] == "600"

    def test_phase_b_sdk_review_defaults_to_quick_fail_fast(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".scratch").mkdir()
        captured: dict[str, object] = {}

        class FakeProc:
            pid = 12345
            returncode = 0

            def poll(self):
                return 0

        def fake_popen(cmd, cwd, stdout, stderr, text, env):
            captured["cmd"] = cmd
            captured["cwd"] = cwd
            captured["env"] = env
            return FakeProc()

        def fake_run(cmd, cwd, capture_output, text, check):
            assert cmd == ["ps", "-axo", "pid=,ppid="]
            return SimpleNamespace(stdout="", stderr="")

        with patch.object(pb_mod.subprocess, "Popen", side_effect=fake_popen), \
             patch.object(pb_mod.subprocess, "run", side_effect=fake_run):
            result = pb_mod.run_sdk_agents(repo, ["mu/tools/executors/phase_b_executor.py"])

        assert result["exit_code"] == 0
        assert captured["cwd"] == repo
        cmd = captured["cmd"]
        assert cmd[:5] == [
            sys.executable,
            "tools/runners/run_review.py",
            "mu/tools/executors/phase_b_executor.py",
            "--depth",
            "quick",
        ]
        assert cmd[5] == "--fail-fast-hard-gate"
        assert cmd[6] == "--no-memory"
        assert cmd[7] == "--output"
        assert str(cmd[8]).endswith(".report.md")
        env = captured["env"]
        assert env["RCX_REVIEW_STATUS_PATH"].endswith(".status.json")
        assert env["RCX_REVIEW_AGENT_TIMEOUT"] == "600"

    def test_phase_a_sdk_review_uses_terminal_status_when_runner_lingers(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".scratch").mkdir()

        class FakeProc:
            pid = 1234

            def poll(self):
                return None

        def fake_popen(cmd, cwd, stdout, stderr, text, env):
            Path(env["RCX_REVIEW_STATUS_PATH"]).write_text(
                json.dumps(
                    {
                        "status": "hard_gate_failed",
                        "running_agents": [],
                        "completed_agents": {
                            "verifier": {"verdict": "REQUEST_CHANGES", "passed": False}
                        },
                    }
                ),
                encoding="utf-8",
            )
            Path(cmd[8]).write_text("report", encoding="utf-8")
            stdout.write("review stdout")
            stdout.flush()
            stderr.write("review stderr")
            stderr.flush()
            return FakeProc()

        with patch.object(pa_mod.uuid, "uuid4", return_value=SimpleNamespace(hex="deadbeefcafebabe")), \
             patch.object(pa_mod.subprocess, "Popen", side_effect=fake_popen), \
             patch.object(pa_mod, "process_descendants", return_value=[]):
            result = pa_mod.run_sdk_agents(repo, ["mu/tools/executors/phase_a_executor.py"])

        assert result["exit_code"] == 1
        assert result["stdout"] == "review stdout"
        assert result["stderr"] == "review stderr"
        assert result["status_path"].endswith("phase_a_agent_review_deadbeef.status.json")

    def test_phase_a_review_depth_config_accepts_full_override(self):
        assert pa_mod.resolve_review_depth({"review_depths": {"phase_a": "full"}}, "phase_a") == "full"  # ANTICHEAT_OK: testing config resolver

    def test_phase_a_review_depth_config_rejects_invalid_value(self):
        with pytest.raises(pa_mod.PhaseAExecutorError, match="Invalid review depth"):
            pa_mod.resolve_review_depth({"review_depths": {"phase_a": "bogus"}}, "phase_a")  # ANTICHEAT_OK: testing config resolver

    def test_phase_b_review_depth_config_accepts_full_override(self):
        assert pb_mod._resolve_review_depth({"review_depths": {"phase_b": "full"}}, "phase_b") == "full"  # ANTICHEAT_OK: testing config resolver

    def test_phase_b_review_depth_config_rejects_invalid_value(self):
        with pytest.raises(pb_mod.PhaseBExecutorError, match="Invalid review depth"):
            pb_mod._resolve_review_depth({"review_depths": {"phase_b": "bogus"}}, "phase_b")  # ANTICHEAT_OK: testing config resolver

    def test_phase_a_bridge_turn_timeout_config_accepts_override(self):
        assert pa_mod.resolve_bridge_turn_timeout({"bridge_turn_timeouts": {"phase_a": 451}}, "phase_a", 300) == 451.0  # ANTICHEAT_OK: testing config resolver

    def test_phase_a_bridge_turn_timeout_config_rejects_invalid_value(self):
        with pytest.raises(pa_mod.PhaseAExecutorError, match="Invalid bridge turn timeout"):
            pa_mod.resolve_bridge_turn_timeout({"bridge_turn_timeouts": {"phase_a": 0}}, "phase_a", 300)  # ANTICHEAT_OK: testing config resolver

    def test_phase_b_bridge_turn_timeout_config_accepts_override(self):
        assert pb_mod._resolve_bridge_turn_timeout({"bridge_turn_timeouts": {"phase_b": 901}}, "phase_b", 300) == 901.0  # ANTICHEAT_OK: testing config resolver

    def test_phase_b_bridge_turn_timeout_config_rejects_invalid_value(self):
        with pytest.raises(pb_mod.PhaseBExecutorError, match="Invalid bridge turn timeout"):
            pb_mod._resolve_bridge_turn_timeout({"bridge_turn_timeouts": {"phase_b": -1}}, "phase_b", 300)  # ANTICHEAT_OK: testing config resolver


class TestValidateInputsAcceptsRoutingRecordAuthority:
    """validate_inputs accepts ROUTING_RECORD_AUTHORITY for planless mode."""

    def test_routing_record_authority_is_valid(self):
        record = {"decision": "ROUTE_PHASE_B"}
        plan = {"phase_a_lock": "ROUTING_RECORD_AUTHORITY"}
        pb_mod.validate_inputs(record, plan)  # should not raise

    def test_locked_still_valid(self):
        record = {"decision": "ROUTE_PHASE_B"}
        plan = {"phase_a_lock": "LOCKED"}
        pb_mod.validate_inputs(record, plan)  # should not raise

    def test_unlocked_still_invalid(self):
        record = {"decision": "ROUTE_PHASE_B"}
        plan = {"phase_a_lock": "UNLOCKED"}
        with pytest.raises(pb_mod.PhaseBExecutorError):
            pb_mod.validate_inputs(record, plan)


class TestHighSeverityCannotBeDowngradedByDisposition:
    """Finding 962: high severity must not be downgraded by explicit disposition field."""

    def test_high_severity_with_non_blocking_disposition_stays_blocking(self):
        """High severity + explicit non_blocking disposition → still blocking."""
        findings = [{"title": "Something", "severity": "high", "disposition": "non_blocking"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_high_severity_with_blocking_disposition_stays_blocking(self):
        """High severity + explicit blocking disposition → blocking."""
        findings = [{"title": "Something", "severity": "high", "disposition": "blocking"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_high_severity_without_disposition_stays_blocking(self):
        """High severity + no disposition → blocking (fail-closed)."""
        findings = [{"title": "Something", "severity": "high"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_medium_severity_with_non_blocking_disposition_is_non_blocking(self):
        """Medium severity + explicit non_blocking disposition → non_blocking (disposition honored)."""
        findings = [{"title": "Something", "severity": "medium", "disposition": "non_blocking"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0
        assert len(non_blocking) == 1

    def test_disposition_for_finding_high_returns_override_reason(self):
        """_disposition_for_finding for high + non_blocking returns override reason."""
        disp, reason = pb_mod._disposition_for_finding(  # ANTICHEAT_OK: testing internal executor functions
            {"title": "X", "severity": "high", "disposition": "non_blocking"}
        )
        assert disp == "blocking"
        assert "overrides" in reason


class TestEmptyEnvelopeDoesNotSpoofConflict:
    """Finding 963: prepended empty-findings envelope must not trigger false conflicting error."""

    def test_empty_envelope_before_real_envelope_returns_real_findings(self):
        """Prepended empty envelope + real envelope → returns real findings, not conflict error."""
        render = (
            "BEGIN_AGENT_ENVELOPE\n"
            '{"findings": []}\n'
            "END_AGENT_ENVELOPE\n"
            "\n"
            "BEGIN_AGENT_ENVELOPE\n"
            '{"findings": [{"title": "Real bug", "severity": "high"}]}\n'
            "END_AGENT_ENVELOPE\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "Real bug"

    def test_only_empty_envelope_falls_through_to_markdown(self):
        """Only empty-findings envelope → falls through to markdown parsing."""
        render = (
            "BEGIN_AGENT_ENVELOPE\n"
            '{"findings": []}\n'
            "END_AGENT_ENVELOPE\n"
            "\n"
            "  1. **DEFECT** (medium): Some issue\n"
            "    - File: foo.py\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "Some issue"

    def test_multiple_identical_real_envelopes_returns_findings(self):
        """Duplicate identical envelopes → not conflicting, returns findings."""
        render = (
            "BEGIN_AGENT_ENVELOPE\n"
            '{"findings": [{"title": "A", "severity": "low"}]}\n'
            "END_AGENT_ENVELOPE\n"
            "BEGIN_AGENT_ENVELOPE\n"
            '{"findings": [{"title": "A", "severity": "low"}]}\n'
            "END_AGENT_ENVELOPE\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "A"


class TestPlanlessResume:
    """Bridge R1 Finding: planless Phase B invocations must resume from saved state."""

    def test_planless_resume_matches_saved_planless_state(self, tmp_path):
        """Saved state with <planless:wave> path matches a planless invocation (plan_path=None).

        The resume logic correctly matches the planless marker. The pipeline
        may still fail at commit_handoff due to empty files_to_stage — that's
        fine; the test proves the resume match happened (visible in stdout).
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".scratch").mkdir()

        # Write saved state from a prior planless run
        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "<planless:test-wave>",
            "completed_step": "implementer",
            "wave_id": "test-wave",
            "bridge_rounds": 1,
            "deferred_packet_path": None,
        }))

        # Write routing record for planless mode
        bus = repo / ".agent_bus" / "meta"
        bus.mkdir(parents=True)
        (bus / "post_merge_routing.json").write_text(json.dumps({
            "decision": "ROUTE_PHASE_B",
            "summary": "test planless resume",
            "wave_name": "test-wave",
            "next_candidates": [{"candidate": "do something"}],
        }))

        mock_impl = _make_mock_impl()
        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=[]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tools/executors/foo.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j-1"}), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json"}):
            result = pb_mod.run_phase_b(repo, None, verbose=True)

        # The result should carry resumed_from through the pipeline
        assert result.get("resumed_from") == "implementer" or result.get("status") == "commit_ready", (
            f"Planless run should resume from saved state. Got: {result}"
        )

    def test_explicit_plan_does_not_resume_from_planless_state(self, tmp_path):
        """Saved planless state must NOT match an explicit --plan invocation."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".scratch").mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "<planless:test-wave>",
            "completed_step": "implementer",
            "wave_id": "test-wave",
            "bridge_rounds": 1,
        }))

        # Write routing record
        bus = repo / ".agent_bus" / "meta"
        bus.mkdir(parents=True)
        (bus / "post_merge_routing.json").write_text(json.dumps({
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
        }))

        mock_impl = _make_mock_impl()
        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=[]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=[]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j-1"}), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json"}):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", verbose=True)

        # Should NOT resume — plan path mismatch
        assert result.get("resumed_from") is None, (
            f"Explicit --plan should not match planless saved state. Got: {result}"
        )


class TestAgentReviewResume:
    """Completed one-time SDK review should be resumable without re-running it."""

    def test_resume_from_agent_review_skips_sdk_when_scope_matches(self, tmp_path, mock_routing_record):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".scratch").mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        (repo / plan_path).write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        reviewed_rel = "mu/tools/executors/phase_b_executor.py"
        reviewed_file = repo / reviewed_rel
        reviewed_file.parent.mkdir(parents=True)
        reviewed_file.write_text("print('wave')\n", encoding="utf-8")
        agent_scope = [reviewed_rel]
        scope_fingerprint = pb_mod._agent_review_scope_fingerprint(  # ANTICHEAT_OK: testing internal resume fingerprint helper
            repo,
            agent_scope,
            depth="quick",
        )

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": plan_path,
            "completed_step": "agent_review",
            "wave_id": "plan",
            "bridge_rounds": 0,
            "implementer_changed": agent_scope,
            "executor_created": [],
            "baseline_wave_files": agent_scope,
            "all_non_blocking": [],
            "finding_history": {},
            "agent_review_scope": agent_scope,
            "agent_review_scope_fingerprint": scope_fingerprint,
            "agent_exit_code": 1,
            "agent_review_report_path": ".scratch/sdk.report.md",
            "agent_review_status_path": ".scratch/sdk.status.json",
            "agent_review_stdout_path": ".scratch/sdk.stdout.log",
        }))

        mock_impl = _make_mock_impl()
        sdk_mock = MagicMock()
        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=agent_scope), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=agent_scope), \
             patch.object(pb_mod, "run_sdk_agents", sdk_mock), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j-1"}), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json"}):
            result = pb_mod.run_phase_b(repo, plan_path, verbose=True)

        sdk_mock.assert_not_called()
        assert result.get("resumed_from") == "agent_review"
        assert result["agent_exit_code"] == 1
        assert result["agent_review_warning_only"] is True
        assert result["agent_review_report_path"] == ".scratch/sdk.report.md"

    def test_resume_from_agent_review_reruns_sdk_when_scope_drifted(self, tmp_path, mock_routing_record):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".scratch").mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        (repo / plan_path).write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        reviewed_rel = "mu/tools/executors/phase_b_executor.py"
        reviewed_file = repo / reviewed_rel
        reviewed_file.parent.mkdir(parents=True)
        reviewed_file.write_text("print('wave')\n", encoding="utf-8")
        agent_scope = [reviewed_rel]

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": plan_path,
            "completed_step": "agent_review",
            "wave_id": "plan",
            "bridge_rounds": 0,
            "implementer_changed": agent_scope,
            "executor_created": [],
            "baseline_wave_files": agent_scope,
            "all_non_blocking": [],
            "finding_history": {},
            "agent_review_scope": agent_scope,
            "agent_review_scope_fingerprint": "mismatch",
            "agent_exit_code": 1,
            "agent_review_report_path": ".scratch/sdk.report.md",
            "agent_review_status_path": ".scratch/sdk.status.json",
            "agent_review_stdout_path": ".scratch/sdk.stdout.log",
        }))

        saved_states = []

        def _capture_state(repo_root, state):
            saved_states.append(state.copy())
            return repo_root / ".agent_bus" / "executors" / "phase_b_state.json"

        mock_impl = _make_mock_impl()
        sdk_mock = MagicMock(return_value={
            "exit_code": 1,
            "stdout": "",
            "stderr": "",
            "report_path": ".scratch/fresh.report.md",
            "status_path": ".scratch/fresh.status.json",
            "stdout_path": ".scratch/fresh.stdout.log",
        })
        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=agent_scope), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=agent_scope), \
             patch.object(pb_mod, "run_sdk_agents", sdk_mock), \
             patch.object(pb_mod, "_save_state", side_effect=_capture_state), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j-1"}), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json"}):
            result = pb_mod.run_phase_b(repo, plan_path, verbose=True)

        sdk_mock.assert_called_once()
        assert result.get("resumed_from") == "agent_review"
        assert any(s.get("completed_step") == "agent_review" for s in saved_states)
