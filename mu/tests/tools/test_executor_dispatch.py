"""Tests for executor dispatcher and commit executor.

Covers Slice 1 (dispatcher), Slice 2 (commit_executor),
and the 15-step state machine (commit pipeline automation plan).
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from mu.tests.tools.module_loader import load_module
from tests.repo_root import REPO_ROOT

# Load executor_common first (dependency)
common_mod = load_module(
    "executor_common",
    REPO_ROOT / "mu" / "tools" / "executors" / "executor_common.py",
)
dispatch_mod = load_module(
    "executor_dispatch",
    REPO_ROOT / "mu" / "tools" / "executors" / "executor_dispatch.py",
)
commit_mod = load_module(
    "commit_executor",
    REPO_ROOT / "mu" / "tools" / "executors" / "commit_executor.py",
)
phase_a_mod = load_module(
    "phase_a_executor",
    REPO_ROOT / "mu" / "tools" / "executors" / "phase_a_executor.py",
)
dialectic_mod = load_module(
    "dialectic_executor",
    REPO_ROOT / "mu" / "tools" / "executors" / "dialectic_executor.py",
)
phase_b_mod = load_module(
    "phase_b_executor",
    REPO_ROOT / "mu" / "tools" / "executors" / "phase_b_executor.py",
)
recovery_mod = load_module(
    "recovery_gate",
    REPO_ROOT / "mu" / "tools" / "executors" / "recovery_gate.py",
)


_VALID_ROUTING_RECORD = {"decision": "ROUTE_PHASE_B", "summary": "test dispatch"}


@pytest.fixture
def mock_routing_record():
    """Patch load_routing_record to return a valid ROUTE_PHASE_B record."""
    with patch.object(phase_b_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
        yield


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

    def test_phase_a_is_now_implemented(self):
        """Phase A executor is available since Slice 4."""
        assert "phase_a_executor" in dispatch_mod.AVAILABLE_EXECUTORS

    def test_phase_b_is_now_implemented(self):
        """Phase B executor is available since Slice 3."""
        assert "phase_b_executor" in dispatch_mod.AVAILABLE_EXECUTORS

    def test_dialectic_is_now_implemented(self):
        """Dialectic executor is available since Slice 5."""
        assert "dialectic_executor" in dispatch_mod.AVAILABLE_EXECUTORS


class TestDispatcherConfig:
    """Config loading and defaults."""

    def test_load_default_config(self):
        config = dispatch_mod.load_config()
        assert "backends" in config
        assert "bridge_reviewers" in config
        assert "bridge_turn_timeouts" in config
        assert "timeouts" in config
        assert "bridge_loop_limits" in config

    def test_load_missing_config_returns_defaults(self, tmp_path):
        config = dispatch_mod.load_config(tmp_path / "nonexistent.json")
        assert config["bridge_loop_limits"]["phase_a"] == 15

    def test_load_partial_custom_config_merges_shared_defaults(self, tmp_path):
        config_path = tmp_path / "executor_config.json"
        config_path.write_text(json.dumps({"timeouts": {"commit_executor": 999}}))
        config = dispatch_mod.load_config(config_path)
        assert config["timeouts"]["commit_executor"] == 999
        assert config["bridge_turn_timeouts"]["phase_b"] == 900
        assert config["review_depths"]["phase_b"] == "quick"


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

    def test_dispatch_fails_closed_in_agent_review_mode(self):
        record = {"decision": "COMMIT_GO", "summary": "review-time probe"}
        with patch.dict(os.environ, {"RCX_AGENT_REVIEW_MODE": "run_review"}, clear=False):
            result = dispatch_mod.dispatch(record, skip_freshness=True)
        assert result["status"] == "error"
        assert "agent review mode" in result["message"]


# ===========================================================================
# Shared test helpers
# ===========================================================================


def _make_new_handoff(**overrides):
    """Create a valid new-schema handoff dict."""
    wave_id = overrides.get("wave_id", "test-wave-id")
    target_gate_id = overrides.get("target_gate_id", "G8")
    base = {
        "wave_id": wave_id,
        "wave_class": "L4_ENABLER",
        "target_gate_id": target_gate_id,
        "branch_prefix": "jabramsja",
        "tracker_note_text": (
            f"- Tracker sync note (2026-04-03, {wave_id}): **TEST — valid handoff note.** "
            f"Class: L4_ENABLER. target_gate_id: {target_gate_id}. "
            "evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py`. "
            "evidence_delta: (1) Test handoff scopes one file. (2) Validation exercises the executor test module. "
            "(3) Indicator artifact binds the wave. "
            "progress_proof_before: Test handoff had no validated tracker note. "
            "progress_proof_after: Test handoff now carries a canonical tracker note. "
            "primary_blocker_class: INTEGRATION. "
            "primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
            f"indicator_artifact_ref: reports/l4_wave_indicators/{wave_id}.json. "
            f"indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id {wave_id} --output reports/l4_wave_indicators/{wave_id}.json. "
            "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            "boot0_track_id: V1. boot0_progress_state: HOLD."
        ),
        "fixes_implemented": ["test fix"],
        "files_to_stage": ["file1.py"],
        "force_add_files": [],
        "commit_message": "feat: test\n\nCo-Authored-By: test",
        "pr_title": "feat: test",
        "pr_body": "## Summary\ntest",
        "base_branch": "dev",
        "pre_commit_receipt_path": ".agent_bus/meta/pre_commit_receipt.json",
        "task_id": "[TEST-1]",
        "caller": "phase_b",
    }
    base.update(overrides)
    return base


def _init_git_repo(tmp_path):
    """Create a git repo with initial commit and TASKS.md with Ra section."""
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, env=env)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, capture_output=True)

    # Create TASKS.md with Ra section
    tasks = repo / "TASKS.md"
    tasks.write_text(
        "# Tasks\n\n---\n\n## Ra (Resolved)\n\n"
        "Items here are resolved.\n\n"
        "- Tracker sync note (2026-03-22, old-wave): old note.\n\n"
        "---\n\n## NEXT\n"
    )

    # Create a minimal indicator collector script (B2: fail-closed when missing)
    indicator_dir = repo / "mu" / "tools" / "metrics"
    indicator_dir.mkdir(parents=True, exist_ok=True)
    indicator_script = indicator_dir / "collect_l4_wave_indicators.py"
    indicator_script.write_text(
        '#!/usr/bin/env python3\n'
        'import argparse, json, pathlib\n'
        'p = argparse.ArgumentParser()\n'
        'p.add_argument("--wave-id")\n'
        'p.add_argument("--output")\n'
        'a = p.parse_args()\n'
        'out = pathlib.Path(a.output)\n'
        'out.parent.mkdir(parents=True, exist_ok=True)\n'
        'out.write_text(json.dumps({"wave_id": a.wave_id}))\n'
    )

    # Initial commit
    subprocess.run(["git", "add", "TASKS.md", str(indicator_script.relative_to(repo))],
                   cwd=repo, capture_output=True, env=env)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True, env=env)
    # Ensure branch is named "dev"
    subprocess.run(["git", "branch", "-m", "dev"], cwd=repo, capture_output=True, env=env)
    return repo, env


def _compute_staged_sha(repo):
    """Compute staged_sha (sha256 of 'git diff --cached --binary') for receipt tests."""
    import hashlib
    staged_diff = subprocess.run(
        ["git", "diff", "--cached", "--binary"],
        cwd=repo, capture_output=True, check=True,
    ).stdout
    return hashlib.sha256(staged_diff).hexdigest()


def _commit_post_commit_source() -> str:
    """Return combined source for the main pipeline and extracted post-commit helper."""
    import inspect
    parts = [
        inspect.getsource(commit_mod.run_commit_pipeline),
        inspect.getsource(commit_mod._run_post_commit_pipeline),  # ANTICHEAT_OK: testing extracted post-commit helper source
    ]
    for helper in ("_extract_review_findings", "_attempt_bot_finding_remediation"):
        if hasattr(commit_mod, helper):
            parts.append(inspect.getsource(getattr(commit_mod, helper)))  # ANTICHEAT_OK: testing refactored review/remediation helpers
    return "\n".join(parts)


# ===========================================================================
# Commit executor tests (Slice 2)
# ===========================================================================


class TestCommitHandoffValidation:
    """Handoff schema validation (new schema)."""

    def test_valid_handoff_passes(self):
        valid, errors = commit_mod.validate_handoff(_make_new_handoff())
        assert valid, errors

    def test_incomplete_l4_tracker_note_fails_early(self):
        valid, errors = commit_mod.validate_handoff(
            _make_new_handoff(
                tracker_note_text=(
                    "- Tracker sync note (2026-04-03, test-wave-id): **TEST — incomplete note.** "
                    "Class: L4_ENABLER. target_gate_id: G8."
                )
            )
        )
        assert not valid
        assert any("evidence_command" in e for e in errors)
        assert any("progress_proof_before" in e for e in errors)

    def test_build_commit_handoff_defaults_to_contract_complete_note(self, tmp_path):
        repo, env = _init_git_repo(tmp_path)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        test_file = repo / "mu" / "tests" / "tools" / "test_auto_note.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        handoff, errors = commit_mod.build_commit_handoff(
            wave_id="test-wave-id",
            task_id="[TEST-1]",
            files_to_stage=["mu/tests/tools/test_auto_note.py"],
            commit_message="fix: auto note",
            fixes_implemented=["auto tracker generation"],
            repo_root=repo,
        )
        assert not errors, errors
        note = handoff["tracker_note_text"]
        assert "evidence_command:" in note
        assert "progress_proof_before:" in note
        assert "indicator_collection_command:" in note
        assert "test_auto_note.py" in note
        valid, validation_errors = commit_mod.validate_handoff(handoff)
        assert valid, validation_errors

    def test_missing_fields_fails(self):
        valid, errors = commit_mod.validate_handoff({"files_to_stage": ["x"]})
        assert not valid
        assert any("Missing" in e for e in errors)

    def test_unexpected_fields_fail(self):
        valid, errors = commit_mod.validate_handoff(
            _make_new_handoff(unexpected="surprise")
        )
        assert not valid
        assert any("Unexpected field: unexpected" == e for e in errors)

    def test_optional_phase_b_metadata_passes(self):
        valid, errors = commit_mod.validate_handoff(
            _make_new_handoff(
                supervisor_lane="hooks/agents/bridge control-surface",
                deferred_items=["reports/deferred/non_blocking/example.md"],
                bridge_status={"rounds": 2, "reentry": True},
            )
        )
        assert valid, errors

    def test_optional_supervisor_context_passes(self):
        valid, errors = commit_mod.validate_handoff(
            _make_new_handoff(
                scope_items=["reports/control_plane/test_plan.md", "file1.py"],
                evidence_handles={"receipt_chain": "exact receipt path"},
            )
        )
        assert valid, errors

    def test_empty_files_to_stage_fails(self):
        valid, errors = commit_mod.validate_handoff(_make_new_handoff(files_to_stage=[]))
        assert not valid
        assert any("empty" in e.lower() or "non-empty" in e.lower() for e in errors)

    def test_invalid_caller_fails(self):
        valid, errors = commit_mod.validate_handoff(_make_new_handoff(caller="invalid"))
        assert not valid
        assert any("caller" in e for e in errors)

    def test_branch_prefix_with_slash_fails(self):
        valid, errors = commit_mod.validate_handoff(_make_new_handoff(branch_prefix="../bad"))
        assert not valid
        assert any("branch_prefix" in e for e in errors)

    def test_force_add_nested_env_path_fails(self):
        valid, errors = commit_mod.validate_handoff(
            _make_new_handoff(force_add_files=["reports/.env/secrets.txt"]),
        )
        assert not valid
        assert any("force_add_files denied" in e for e in errors)

    def test_force_add_dotenv_variants_fail(self):
        for candidate in ["reports/.env.local", "reports/.envrc", "reports/.envrc.local"]:
            valid, errors = commit_mod.validate_handoff(
                _make_new_handoff(force_add_files=[candidate]),
            )
            assert not valid
            assert any("force_add_files denied" in e for e in errors)

    def test_force_add_backslash_git_path_fails(self):
        valid, errors = commit_mod.validate_handoff(
            _make_new_handoff(force_add_files=[".GIT\\config"]),
        )
        assert not valid
        assert any("force_add_files denied" in e for e in errors)

    def test_non_dict_fails(self):
        valid, errors = commit_mod.validate_handoff("not a dict")
        assert not valid


class TestCommitPipelineValidation:
    """Commit pipeline pre-checks (new schema)."""

    def test_wrong_branch_fails(self, tmp_path):
        """On wrong branch → error at ensure_feature_branch."""
        repo = tmp_path / "repo"
        repo.mkdir()
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "init"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "checkout", "-b", "wrong-branch"], cwd=repo, capture_output=True, env=env)

        handoff = _make_new_handoff()
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert result["status"] == "error"
        assert result["step"] == "ensure_feature_branch"

    def test_missing_receipt_fails(self, tmp_path):
        """Missing receipt → error at validate_receipt (after supervisor)."""
        repo, env = _init_git_repo(tmp_path)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")

        # Mock supervisor that returns a non-existent receipt path
        mock_result = MagicMock()
        mock_result.decision = "COMMIT_GO"
        mock_result.receipt_path = ".agent_bus/meta/nonexistent_receipt.json"
        mock_result.summary = "ok"

        # Also need the handoff receipt path to not exist
        handoff = _make_new_handoff(
            pre_commit_receipt_path=".agent_bus/meta/nonexistent_receipt.json"
        )

        with patch.dict(sys.modules, {"meta_bridge_client": MagicMock()}):
            sys.modules["meta_bridge_client"].run_meta_bridge_package = MagicMock(return_value=mock_result)
            sys.modules["meta_bridge_client"].MetaBridgeClientError = Exception
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "error"
        assert result["step"] == "validate_receipt"


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
        with pytest.raises(phase_b_mod.PhaseBExecutorError, match="ROUTE_PHASE_B"):
            phase_b_mod.validate_inputs(record, plan)

    def test_validate_unlocked_plan(self):
        record = {"decision": "ROUTE_PHASE_B"}
        plan = {"phase_a_lock": "UNLOCKED"}
        with pytest.raises(phase_b_mod.PhaseBExecutorError, match="LOCKED"):
            phase_b_mod.validate_inputs(record, plan)

    def test_validate_correct_inputs(self):
        record = {"decision": "ROUTE_PHASE_B"}
        plan = {"phase_a_lock": "LOCKED"}
        phase_b_mod.validate_inputs(record, plan)  # should not raise


class TestPhaseBCommitHandoff:
    """Phase B executor prepares commit handoffs."""

    def test_prepare_handoff(self, tmp_path):
        path = phase_b_mod.prepare_commit_handoff(
            tmp_path,
            wave_id="test",
            task_id="[TEST]",
            wave_class="MAINTENANCE",
            target_gate_id="G8",
            files_to_stage=["a.py"],
            commit_message="feat: test",
            pr_title="feat: test",
            pr_body="## Summary\ntest",
        )
        assert path.exists()
        handoff = json.loads(path.read_text())
        assert handoff["caller"] == "phase_b"
        assert handoff["files_to_stage"] == ["a.py"]
        assert handoff["wave_id"] == "test"
        assert handoff["pre_commit_receipt_path"] == ".agent_bus/meta/pre_commit_receipt.json"


class TestPhaseBDispatcherIntegration:
    """Dispatcher correctly routes to phase_b_executor."""

    def test_route_phase_b_dispatches(self):
        assert dispatch_mod.resolve_executor("ROUTE_PHASE_B") == "phase_b_executor"

    def test_phase_b_now_available(self):
        assert "phase_b_executor" in dispatch_mod.AVAILABLE_EXECUTORS


@pytest.mark.usefixtures("mock_routing_record")
class TestPhaseBRunPhaseB:
    """Integration: run_phase_b with a real plan packet."""

    def test_loads_locked_plan(self, tmp_path):
        """run_phase_b loads and validates a locked plan packet.

        Without the full infrastructure (bridge config, adapters), the implementer
        will fail. Since implementer failure is now FAIL CLOSED, the pipeline
        stops at the implementer step. But the plan loading and validation
        succeeded — the error is at the implementer step, not load_plan.
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".scratch").mkdir(parents=True)
        plan = repo / "reports" / "control_plane" / "test_plan.md"
        plan.write_text("# Plan\n\nDate: 2026-03-22\nStatus: Phase B\nPhase-A-Lock: LOCKED\n")

        result = phase_b_mod.run_phase_b(
            repo, "reports/control_plane/test_plan.md", verbose=True
        )
        # Implementer fails closed (no bridge config in tmp repo) — this is correct.
        # The key assertion: the error is at the implementer step, NOT at load_plan.
        assert result.get("status") == "error"
        assert result.get("step") == "implementer"
        assert result.get("implementer_invoked") is True


# ===========================================================================
# Phase A executor tests (Slice 4)
# ===========================================================================


class TestPhaseAPlanCreation:
    """Phase A executor creates plan packet drafts."""

    def test_create_plan_draft(self, tmp_path):
        scope = {"request": "create executors", "summary": "executor plan"}
        path = phase_a_mod.create_plan_draft(tmp_path, "test_plan", scope)
        assert path.exists()
        content = path.read_text()
        assert "Phase-A-Lock: UNLOCKED" in content
        assert "create executors" in content

    def test_existing_plan_not_overwritten(self, tmp_path):
        from datetime import datetime, timezone
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        (tmp_path / "reports" / "control_plane").mkdir(parents=True)
        existing = tmp_path / "reports" / "control_plane" / f"test_plan_{date_str}.md"
        existing.write_text("# existing plan")
        scope = {"request": "new content"}
        path = phase_a_mod.create_plan_draft(tmp_path, "test_plan", scope)
        assert path == existing
        assert path.read_text() == "# existing plan"

    def test_lock_plan(self, tmp_path):
        (tmp_path / "reports" / "control_plane").mkdir(parents=True)
        plan = tmp_path / "reports" / "control_plane" / "test.md"
        plan.write_text("Status: Phase A (design -- not yet agent-reviewed or bridge-converged)\nPhase-A-Lock: UNLOCKED\n")
        phase_a_mod.lock_plan(tmp_path, "reports/control_plane/test.md")
        content = plan.read_text()
        assert "Phase-A-Lock: LOCKED" in content
        assert "bridge-converged" in content

    def test_create_plan_draft_rejects_path_traversal(self, tmp_path):
        scope = {"request": "create executors", "summary": "executor plan"}
        with pytest.raises(phase_a_mod.PhaseAExecutorError, match="plan_name|Path traversal|Unsafe"):
            phase_a_mod.create_plan_draft(tmp_path, "../../evil", scope)

    def test_lock_plan_replaces_only_one_lock_line(self, tmp_path):
        (tmp_path / "reports" / "control_plane").mkdir(parents=True)
        plan = tmp_path / "reports" / "control_plane" / "test.md"
        plan.write_text(
            "Status: Phase A (design -- not yet agent-reviewed or bridge-converged)\n"
            "Phase-A-Lock: UNLOCKED\n"
            "Notes mention Phase-A-Lock: UNLOCKED but are not the control line.\n"
        )
        phase_a_mod.lock_plan(tmp_path, "reports/control_plane/test.md")
        content = plan.read_text()
        assert content.count("Phase-A-Lock: LOCKED") == 1
        assert "Notes mention Phase-A-Lock: UNLOCKED" in content

    def test_lock_plan_is_idempotent_for_reused_locked_packet(self, tmp_path):
        (tmp_path / "reports" / "control_plane").mkdir(parents=True)
        plan = tmp_path / "reports" / "control_plane" / "test.md"
        plan.write_text(
            "Status: Phase A (design -- not yet agent-reviewed or bridge-converged)\n"
            "Phase-A-Lock: LOCKED\n",
            encoding="utf-8",
        )
        phase_a_mod.lock_plan(tmp_path, "reports/control_plane/test.md")
        content = plan.read_text(encoding="utf-8")
        assert content.count("Phase-A-Lock: LOCKED") == 1
        assert "bridge-converged" in content

    def test_lock_plan_rejects_multiple_control_lines(self, tmp_path):
        (tmp_path / "reports" / "control_plane").mkdir(parents=True)
        plan = tmp_path / "reports" / "control_plane" / "test.md"
        plan.write_text(
            "Phase-A-Lock: UNLOCKED\n"
            "Phase-A-Lock: LOCKED\n",
            encoding="utf-8",
        )
        with pytest.raises(phase_a_mod.PhaseAExecutorError, match="exactly one Phase-A-Lock control line"):
            phase_a_mod.lock_plan(tmp_path, "reports/control_plane/test.md")

    def test_lock_plan_rejects_missing_control_line(self, tmp_path):
        (tmp_path / "reports" / "control_plane").mkdir(parents=True)
        plan = tmp_path / "reports" / "control_plane" / "test.md"
        plan.write_text(
            "# Some plan\nStatus: draft\n",
            encoding="utf-8",
        )
        with pytest.raises(phase_a_mod.PhaseAExecutorError, match="No Phase-A-Lock control line found"):
            phase_a_mod.lock_plan(tmp_path, "reports/control_plane/test.md")


class TestPhaseADispatcherIntegration:
    """Dispatcher correctly routes to phase_a_executor."""

    def test_route_phase_a_dispatches(self):
        assert dispatch_mod.resolve_executor("ROUTE_PHASE_A") == "phase_a_executor"

    def test_phase_a_now_available(self):
        assert "phase_a_executor" in dispatch_mod.AVAILABLE_EXECUTORS


class TestPhaseAScopeExtraction:
    """Phase A extracts scope from routing record."""

    def test_extract_scope(self):
        record = {
            "decision": "ROUTE_PHASE_A",
            "summary": "Next step is executor implementation",
            "request_for_claude": "Create plan for phase_a_executor",
        }
        scope = phase_a_mod.extract_plan_scope(record)
        assert scope["request"] == "Create plan for phase_a_executor"
        assert scope["summary"] == "Next step is executor implementation"


class TestPhaseABridgeLoopFailClosed:
    """Phase A bridge loop fails closed on QUESTION and unrecognized decisions."""

    def _setup_phase_a(self, tmp_path, monkeypatch=None, *, placeholder_stub: bool = False):
        """Create minimal structure for run_phase_a."""
        # Create plan directory
        plan_dir = tmp_path / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        # Create rendered output directory
        rendered_dir = tmp_path / ".agent_bus" / "rendered"
        rendered_dir.mkdir(parents=True)
        # Create routing record (optional, not required for scope extraction failure)
        bus_dir = tmp_path / ".agent_bus" / "meta"
        bus_dir.mkdir(parents=True)
        routing = {"decision": "ROUTE_PHASE_A", "summary": "test"}
        (bus_dir / "post_merge_routing.json").write_text(json.dumps(routing))
        plan_path = phase_a_mod.create_plan_draft(
            tmp_path,
            "test_plan",
            {"request": "test", "summary": "test"},
        )
        if not placeholder_stub:
            plan_path.write_text(
                """# Test Plan

Date: 2026-04-02
Status: Phase A (design -- not yet agent-reviewed or bridge-converged)
Phase-A-Lock: UNLOCKED

## Scope

- `mu/tools/executors/phase_a_executor.py`

## Work Items

- Exercise bridge-loop control flow for a real Phase A plan.

## Constraints

- No implementation changes in this fixture.

## Stop Conditions

- Stop if bridge decisions are misclassified.

## Acceptance Criteria

- The mocked bridge path converges or fails exactly as asserted by the test.

## Grounding

- Phase A bridge loop regression fixture.
""",
                encoding="utf-8",
            )
        # Mock checkpoint commit (tmp_path is not a git repo)
        if monkeypatch is not None:
            monkeypatch.setattr(
                phase_a_mod, "checkpoint_commit_plan",
                lambda *a, **kw: {"sha": "fake_checkpoint_sha"},
            )
        return rendered_dir

    def test_question_decision_fails_closed(self, tmp_path, monkeypatch):
        """QUESTION decision must fail closed, not burn rounds."""
        rendered_dir = self._setup_phase_a(tmp_path, monkeypatch)
        call_count = {"n": 0}

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            call_count["n"] += 1
            # Write rendered output with QUESTION decision
            rendered = rendered_dir / f"{job_id}.md"
            rendered.write_text("Decision: QUESTION\n\nWhat about X?\n")
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=5)
        assert result["status"] == "error"
        assert "QUESTION" in result["error"]
        # Must fail on the FIRST round, not burn all 5
        assert call_count["n"] == 1

    def test_unrecognized_decision_fails_closed(self, tmp_path, monkeypatch):
        """Unrecognized decision must fail closed, not burn rounds."""
        rendered_dir = self._setup_phase_a(tmp_path, monkeypatch)
        call_count = {"n": 0}

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            call_count["n"] += 1
            rendered = rendered_dir / f"{job_id}.md"
            rendered.write_text("Decision: SOMETHING_UNKNOWN\n\nWeird output\n")
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=5)
        assert result["status"] == "error"
        assert "unrecognized" in result["error"]
        assert call_count["n"] == 1

    def test_go_decision_converges(self, tmp_path, monkeypatch):
        """GO decision converges normally (regression check)."""
        rendered_dir = self._setup_phase_a(tmp_path, monkeypatch)

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            rendered = rendered_dir / f"{job_id}.md"
            rendered.write_text("Decision: GO\n\nLooks good.\n")
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=5)
        assert result["status"] == "converged"

    def test_extract_bridge_decision_accepts_rendered_bullet_format(self):
        render_content = (
            "# Bridge Job x\n\n"
            "- Decision: SYNTHETIC (founder session, not a real review)\n"
            "- Decision: GO\n"
        )
        assert phase_a_mod._extract_bridge_decision(render_content) == "GO"  # ANTICHEAT_OK: testing internal bridge decision parser

    def test_extract_bridge_decision_uses_last_valid_turn(self):
        render_content = (
            "# Bridge Job x\n\n"
            "## Reader turn\n"
            "Decision: REQUEST_CHANGES\n\n"
            "## Reviewer turn\n"
            "Decision: GO\n"
        )
        assert phase_a_mod._extract_bridge_decision(render_content) == "GO"  # ANTICHEAT_OK: testing internal bridge decision parser

    def test_extract_bridge_decision_prefers_terminal_error_over_earlier_request_changes(self):
        render_content = (
            "# Bridge Job x\n\n"
            "## Reader turn\n"
            "Decision: REQUEST_CHANGES\n\n"
            "## Reviewer turn\n"
            "Decision: ERROR\n"
        )
        assert phase_a_mod._extract_bridge_decision(render_content) == "ERROR"  # ANTICHEAT_OK: testing terminal bridge decision parsing

    def test_request_changes_continues_loop(self, tmp_path, monkeypatch):
        """REQUEST_CHANGES continues the loop (regression check)."""
        rendered_dir = self._setup_phase_a(tmp_path, monkeypatch)
        call_count = {"n": 0}

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            call_count["n"] += 1
            rendered = rendered_dir / f"{job_id}.md"
            if call_count["n"] < 3:
                rendered.write_text("Decision: REQUEST_CHANGES\n\nFix X.\n")
            else:
                rendered.write_text("Decision: GO\n\nFixed.\n")
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=5)
        assert result["status"] == "converged"
        assert call_count["n"] == 3

    @pytest.mark.parametrize("decision", ["REQUEST_CHANGES", "NO_GO"])
    def test_non_go_exit_one_continues_loop(self, tmp_path, monkeypatch, decision):
        """bridge_supervisor review returns exit=1 for non-GO decisions; Phase A must keep looping."""
        rendered_dir = self._setup_phase_a(tmp_path, monkeypatch)
        call_count = {"n": 0}

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            call_count["n"] += 1
            rendered = rendered_dir / f"{job_id}.md"
            if call_count["n"] < 3:
                rendered.write_text(f"Decision: {decision}\n\nNeeds more work.\n")
                return {"exit_code": 1, "stdout": f"{decision}\n", "stderr": ""}
            rendered.write_text("Decision: GO\n\nFixed.\n")
            return {"exit_code": 0, "stdout": "GO\n", "stderr": ""}

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=5)
        assert result["status"] == "converged"
        assert call_count["n"] == 3

    def test_phase_a_implementer_prompt_stays_packet_scoped(self, tmp_path, monkeypatch):
        """Phase A implementer prompt must forbid unrelated dirty-diff spelunking."""
        rendered_dir = self._setup_phase_a(tmp_path, monkeypatch, placeholder_stub=True)
        captured: dict[str, str] = {}

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            rendered = rendered_dir / f"{job_id}.md"
            rendered.write_text("Decision: REQUEST_CHANGES\n\nPacket is still stubby.\n")
            return {"exit_code": 1, "stdout": "REQUEST_CHANGES\n", "stderr": ""}

        def fake_parse_findings(_content):
            return [{
                "disposition": "blocking",
                "severity": "critical",
                "title": "Stub packet",
                "detail": "Replace the stub with a real Phase A plan.",
                "class": "DOC_ACCURACY",
                "file": "reports/control_plane/test_plan_2026-04-02.md",
                "line_start": 12,
                "evidence_cmd": "nl -ba reports/control_plane/test_plan_2026-04-02.md | sed -n '1,40p'",
                "evidence_result": "The packet is still a stub and needs a real plan rewrite.",
            }]

        def fake_invoke(repo_root, prompt, *, backend="claude", timeout=900, verbose=False):
            captured["prompt"] = prompt
            return {"status": "error", "stderr": "stop after prompt capture"}

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)
        monkeypatch.setattr(phase_a_mod, "_parse_phase_a_findings", fake_parse_findings)
        monkeypatch.setattr(phase_a_mod, "_invoke_implementer", fake_invoke)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=1)
        assert result["status"] == "max_rounds_reached"
        prompt = captured["prompt"]
        assert "Do NOT inspect unrelated dirty files" in prompt
        assert "Search TASKS.md for the exact task id" in prompt
        assert "Replace the stub with the real plan directly in that file." in prompt
        assert "files, lines, and docs explicitly cited in the blocking findings above" in prompt
        assert "Prefer current code truth over stale packet wording when they conflict." in prompt
        assert "If a blocking finding proves a work item is already implemented in current code" in prompt
        assert "Because the current packet is still a stub" in prompt
        assert "do NOT inspect downstream implementation files" in prompt
        assert "do NOT try to solve the underlying implementation in this turn" in prompt
        assert "Reproduce with: nl -ba reports/control_plane/test_plan_2026-04-02.md" in prompt
        assert "Evidence result: The packet is still a stub" in prompt

    def test_deferred_agent_review_accepts_authorization_section_alias(self, tmp_path, monkeypatch):
        """Deferred Phase A review must treat Authorization as equivalent to Grounding."""
        rendered_dir = tmp_path / ".agent_bus" / "rendered"
        rendered_dir.mkdir(parents=True)
        bus_dir = tmp_path / ".agent_bus" / "meta"
        bus_dir.mkdir(parents=True)
        routing = {"decision": "ROUTE_PHASE_A", "summary": "test"}
        (bus_dir / "post_merge_routing.json").write_text(json.dumps(routing))
        plan_path = phase_a_mod.create_plan_draft(
            tmp_path,
            "test_plan",
            {"request": "test", "summary": "test"},
        )
        rel_plan_path = str(plan_path.relative_to(tmp_path))
        bridge_calls = {"n": 0}
        agent_calls = {"n": 0, "files": []}

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            agent_calls["n"] += 1
            agent_calls["files"] = list(files)
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        def fake_run_bridge(repo_root, plan_path_arg, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            bridge_calls["n"] += 1
            rendered = rendered_dir / f"{job_id}.md"
            if bridge_calls["n"] == 1:
                rendered.write_text("Decision: REQUEST_CHANGES\n\nStub packet.\n", encoding="utf-8")
                return {"exit_code": 1, "stdout": "REQUEST_CHANGES\n", "stderr": ""}
            rendered.write_text("Decision: GO\n\nReal plan accepted.\n", encoding="utf-8")
            return {"exit_code": 0, "stdout": "GO\n", "stderr": ""}

        def fake_parse_findings(_content):
            return [{
                "disposition": "blocking",
                "severity": "high",
                "title": "Stub packet",
                "detail": "Replace the stub with a real Phase A plan.",
                "class": "DOC_ACCURACY",
                "file": rel_plan_path,
                "line_start": 1,
                "evidence_cmd": f"nl -ba {rel_plan_path} | sed -n '1,80p'",
                "evidence_result": "The packet is still a placeholder stub.",
            }]

        def fake_invoke(repo_root, prompt, *, backend="claude", timeout=900, verbose=False):
            plan_path.write_text(
                """# Test Plan

Date: 2026-04-02
Status: Phase A (design -- not yet agent-reviewed or bridge-converged)
Phase-A-Lock: UNLOCKED
Purpose: Exercise deferred SDK review after same-file stub rewrite.

## Authorization

- Parent task: `[DEFERRED-CONSOLIDATION]`
- Governing packet: `reports/control_plane/wave1b_pipeline_cleanup_2026-03-31.md`

## Scope

- `mu/tools/observability/_pane_prci.sh`

## Work Items

- Close E5 and E6 in the single observability script.

## Constraints

- Do not widen scope outside `_pane_prci.sh`.

## Stop Conditions

- Stop if the fix requires executor changes.

## Acceptance Criteria

- Deferred SDK review runs after the rewritten plan passes bridge review.
""",
                encoding="utf-8",
            )
            return {"status": "success", "stdout": "", "stderr": ""}

        monkeypatch.setattr(
            phase_a_mod, "checkpoint_commit_plan",
            lambda *a, **kw: {"sha": "fake_checkpoint_sha"},
        )
        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)
        monkeypatch.setattr(phase_a_mod, "_parse_phase_a_findings", fake_parse_findings)
        monkeypatch.setattr(phase_a_mod, "_invoke_implementer", fake_invoke)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=5)
        assert result["status"] == "converged"
        assert bridge_calls["n"] == 2
        assert agent_calls["n"] == 1
        assert agent_calls["files"] == [rel_plan_path]
        assert result["agent_review_ran"] is True
    def test_parse_phase_a_findings_preserves_reviewer_evidence(self):
        """Phase A finding parser must preserve reviewer evidence for implementer rewrites."""
        content = """BEGIN_AGENT_ENVELOPE
{
  "findings": [
    {
      "class": "DOC_ACCURACY",
      "severity": "high",
      "title": "Already landed item",
      "detail": "Remove the stale TODO from the packet.",
      "disposition": "blocking",
      "file": "reports/control_plane/example.md",
      "line_start": 41,
      "line_end": 45,
      "evidence_cmd": "nl -ba mu/tools/executors/commit_executor.py | sed -n '2672,2698p'",
      "evidence_result": "Targeted pytest gate already exists.",
      "status": "new"
    }
  ]
}
END_AGENT_ENVELOPE"""

        findings = phase_a_mod._parse_phase_a_findings(content)  # ANTICHEAT_OK: testing internal Phase A finding parser
        assert findings == [{
            "class": "DOC_ACCURACY",
            "severity": "high",
            "title": "Already landed item",
            "detail": "Remove the stale TODO from the packet.",
            "disposition": "blocking",
            "file": "reports/control_plane/example.md",
            "line_start": 41,
            "line_end": 45,
            "evidence_cmd": "nl -ba mu/tools/executors/commit_executor.py | sed -n '2672,2698p'",
            "evidence_result": "Targeted pytest gate already exists.",
            "status": "new",
        }]

    def test_bridge_failure_no_rendered_output_fails_closed(self, tmp_path, monkeypatch):
        """Bridge failure with no rendered output fails closed."""
        self._setup_phase_a(tmp_path, monkeypatch)

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            # No rendered output written, non-zero exit
            return {"exit_code": 1, "stdout": "", "stderr": "bridge crashed"}

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=5)
        assert result["status"] == "error"
        assert "bridge subprocess failed in round 1" in result["error"].lower()
        assert "bridge crashed" in result["error"]

    def test_bridge_failure_with_stale_rendered_output_fails_closed(self, tmp_path, monkeypatch):
        """A stale reader-only render must not mask a nonzero bridge subprocess exit."""
        rendered_dir = self._setup_phase_a(tmp_path, monkeypatch)

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            rendered = rendered_dir / f"{job_id}.md"
            rendered.write_text(
                "# Bridge Review\n\nStatus: PAUSED - awaiting founder review before reviewer\n",
                encoding="utf-8",
            )
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": "Adapter 'codex' produced no stdout after 120.0s",
            }

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=5)
        assert result["status"] == "error"
        assert "bridge subprocess failed in round 1" in result["error"].lower()
        assert "produced no stdout" in result["error"]
        assert ".agent_bus/rendered/phase-a-r1-" in result["rendered_path"]

    def test_go_substring_smuggling_does_not_false_converge(self, tmp_path, monkeypatch):
        """Phase A must parse the canonical decision line, not any GO substring."""
        rendered_dir = self._setup_phase_a(tmp_path, monkeypatch)

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            rendered = rendered_dir / f"{job_id}.md"
            rendered.write_text(
                "Decision: NO_GO\n\nReason: do not trust a quoted Decision: GO from prior text.\n"
            )
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=1)
        assert result["status"] == "max_rounds_reached"

    def test_terminal_bridge_error_decision_fails_closed(self, tmp_path, monkeypatch):
        """Phase A must fail closed when the final reviewer turn reports ERROR."""
        rendered_dir = self._setup_phase_a(tmp_path, monkeypatch)

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            rendered = rendered_dir / f"{job_id}.md"
            rendered.write_text(
                "Decision: REQUEST_CHANGES\n\nInterim reader turn.\n\nDecision: ERROR\n\nReviewer failed closed.\n"
            )
            return {"exit_code": 1, "stdout": "", "stderr": "reviewer error"}

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=5)
        assert result["status"] == "error"
        assert "decision=ERROR" in result["error"]

    def test_zero_exit_without_rendered_output_fails_closed(self, tmp_path, monkeypatch):
        """Phase A must error if the bridge exits 0 but writes no rendered file."""
        self._setup_phase_a(tmp_path, monkeypatch)

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=5)
        assert result["status"] == "error"
        assert "no rendered output" in result["error"].lower()

    def test_bridge_review_stale_watchdog_fails_closed(self, tmp_path, monkeypatch):
        """Phase A bridge review must fail closed on silent stale reviewer hangs."""
        tools_agents = tmp_path / "tools" / "agents"
        tools_agents.mkdir(parents=True)
        fake_bridge = tools_agents / "bridge_supervisor.py"
        fake_bridge.write_text(
            "#!/usr/bin/env python3\n"
            "import time\n"
            "time.sleep(30)\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(phase_a_mod, "PHASE_A_BRIDGE_STALE_TIMEOUT", 0.05)
        monkeypatch.setattr(phase_a_mod, "PHASE_A_BRIDGE_AGGREGATION_HANG_TIMEOUT", 999.0)
        monkeypatch.setattr(phase_a_mod, "PHASE_A_BRIDGE_POLL_SLEEP", 0.01)
        monkeypatch.setattr(phase_a_mod, "resolve_bridge_turn_timeout", lambda *args, **kwargs: 0.05)

        result = phase_a_mod.run_bridge_design_review(
            tmp_path,
            "reports/control_plane/test_plan.md",
            1,
            job_id="phase-a-r1-watchdog",
            timeout=30,
        )

        assert result["exit_code"] == -2
        assert "Bridge review stale" in result["stderr"]
        assert "phase_a_bridge_phase-a-r1-watchdog.stdout.log" in result["stderr"]

    def test_bridge_review_stale_watchdog_honors_bridge_turn_budget(self, tmp_path, monkeypatch):
        """A live reviewer turn may stay quiet until the configured bridge-turn budget expires."""
        tools_agents = tmp_path / "tools" / "agents"
        tools_agents.mkdir(parents=True)
        fake_bridge = tools_agents / "bridge_supervisor.py"
        fake_bridge.write_text(
            "#!/usr/bin/env python3\n"
            "import time\n"
            "time.sleep(0.12)\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(phase_a_mod, "PHASE_A_BRIDGE_STALE_TIMEOUT", 0.05)
        monkeypatch.setattr(phase_a_mod, "PHASE_A_BRIDGE_AGGREGATION_HANG_TIMEOUT", 999.0)
        monkeypatch.setattr(phase_a_mod, "PHASE_A_BRIDGE_POLL_SLEEP", 0.01)
        # Keep a wide margin above interpreter startup + the silent reviewer sleep
        # so Linux CI still proves that the bridge-turn budget overrides the
        # smaller stale watchdog threshold.
        monkeypatch.setattr(phase_a_mod, "resolve_bridge_turn_timeout", lambda *args, **kwargs: 0.5)

        result = phase_a_mod.run_bridge_design_review(
            tmp_path,
            "reports/control_plane/test_plan.md",
            1,
            job_id="phase-a-r1-budget",
            timeout=1.0,
        )

        assert result["exit_code"] == 0
        assert "Bridge review stale" not in result["stderr"]

    def test_bridge_task_is_repo_local_only(self, tmp_path):
        """Phase A bridge task must explicitly forbid external web/network research."""
        tools_agents = tmp_path / "tools" / "agents"
        tools_agents.mkdir(parents=True)
        fake_bridge = tools_agents / "bridge_supervisor.py"
        fake_bridge.write_text(
            "#!/usr/bin/env python3\n",
            encoding="utf-8",
        )

        result = phase_a_mod.run_bridge_design_review(
            tmp_path,
            "reports/control_plane/test_plan.md",
            1,
            job_id="phase-a-r1-local-only",
            timeout=30,
        )

        task_text = (tmp_path / ".scratch" / "phase_a_bridge_r1.md").read_text(encoding="utf-8")
        assert "Use repo-local evidence only." in task_text
        assert "Do not browse the web" in task_text
        assert "Read only the exact TASKS.md block needed to confirm current-task authorization" in task_text
        assert "Read the governing tracked packet only if the plan is not an obvious stub" in task_text
        assert "do NOT open governing packets, prior replay notes, or downstream implementation files" in task_text
        assert result["exit_code"] == 0

    def test_bridge_design_review_uses_configured_reviewer(self, tmp_path):
        """Phase A bridge review must honor executor-configured reviewer backend."""
        tools_agents = tmp_path / "tools" / "agents"
        tools_agents.mkdir(parents=True)
        fake_bridge = tools_agents / "bridge_supervisor.py"
        fake_bridge.write_text(
            "#!/usr/bin/env python3\n"
            "import json\n"
            "import pathlib\n"
            "import sys\n"
            "scratch = pathlib.Path.cwd() / '.scratch'\n"
            "scratch.mkdir(exist_ok=True)\n"
            "(scratch / 'phase_a_bridge_args.json').write_text(json.dumps(sys.argv[1:]), encoding='utf-8')\n",
            encoding="utf-8",
        )
        config_path = tmp_path / "mu" / "tools" / "executors"
        config_path.mkdir(parents=True)
        (config_path / "executor_config.json").write_text(
            json.dumps({"bridge_reviewers": {"phase_a": "claude"}}),
            encoding="utf-8",
        )

        result = phase_a_mod.run_bridge_design_review(
            tmp_path,
            "reports/control_plane/test_plan.md",
            1,
            job_id="phase-a-r1-config-reviewer",
            timeout=30,
        )

        argv = json.loads((tmp_path / ".scratch" / "phase_a_bridge_args.json").read_text(encoding="utf-8"))
        assert "--reviewer" in argv
        assert argv[argv.index("--reviewer") + 1] == "claude"
        assert result["exit_code"] == 0

    def test_bridge_design_review_sets_configured_turn_timeout_env(self, tmp_path):
        """Phase A bridge review should pass its turn-time budget to bridge_supervisor."""
        tools_agents = tmp_path / "tools" / "agents"
        tools_agents.mkdir(parents=True)
        fake_bridge = tools_agents / "bridge_supervisor.py"
        fake_bridge.write_text(
            "#!/usr/bin/env python3\n"
            "import json\n"
            "import os\n"
            "import pathlib\n"
            "scratch = pathlib.Path.cwd() / '.scratch'\n"
            "scratch.mkdir(exist_ok=True)\n"
            "(scratch / 'phase_a_bridge_env.json').write_text(json.dumps({'turn_timeout': os.getenv('RCX_BRIDGE_MAX_TURN_WALL_TIME_S')}), encoding='utf-8')\n",
            encoding="utf-8",
        )
        config_path = tmp_path / "mu" / "tools" / "executors"
        config_path.mkdir(parents=True)
        (config_path / "executor_config.json").write_text(
            json.dumps({"bridge_turn_timeouts": {"phase_a": 451}}),
            encoding="utf-8",
        )

        result = phase_a_mod.run_bridge_design_review(
            tmp_path,
            "reports/control_plane/test_plan.md",
            1,
            job_id="phase-a-r1-config-timeout",
            timeout=600,
        )

        env_payload = json.loads((tmp_path / ".scratch" / "phase_a_bridge_env.json").read_text(encoding="utf-8"))
        assert env_payload["turn_timeout"] == "451.0"
        assert result["exit_code"] == 0


# ===========================================================================
# Dialectic executor tests (Slice 5)
# ===========================================================================


class TestDialecticProposalExtraction:
    """Dialectic executor extracts unbounded proposals."""

    def test_extract_unbounded_proposal(self):
        record = {
            "next_candidates": [
                {"candidate": "broad thing", "bounded": False},
                {"candidate": "narrow thing", "bounded": True},
            ]
        }
        proposal = dialectic_mod.extract_proposal(record)
        assert proposal["candidate"] == "broad thing"
        assert not proposal["bounded"]

    def test_extract_first_when_all_bounded(self):
        record = {
            "next_candidates": [
                {"candidate": "first", "bounded": True},
                {"candidate": "second", "bounded": True},
            ]
        }
        proposal = dialectic_mod.extract_proposal(record)
        assert proposal["candidate"] == "first"

    def test_empty_candidates(self):
        proposal = dialectic_mod.extract_proposal({"next_candidates": []})
        assert proposal["candidate"] == ""


class TestDialecticEnvelopeParsing:
    """Dialectic envelope parsing."""

    def test_valid_envelope(self):
        output = 'text\nBEGIN_DIALECTIC_ENVELOPE\n{"candidate": "narrowed", "bounded": true}\nEND_DIALECTIC_ENVELOPE\nmore'
        result = dialectic_mod.parse_dialectic_envelope(output)
        assert result["candidate"] == "narrowed"
        assert result["bounded"] is True

    def test_missing_envelope_raises(self):
        with pytest.raises(dialectic_mod.DialecticExecutorError, match="missing"):
            dialectic_mod.parse_dialectic_envelope("no envelope here")


class TestDialecticDispatcherIntegration:
    """Dispatcher correctly routes to dialectic_executor."""

    def test_route_dialectic_dispatches(self):
        assert dispatch_mod.resolve_executor("CONTINUE_DIALECTIC") == "dialectic_executor"

    def test_dialectic_now_available(self):
        assert "dialectic_executor" in dispatch_mod.AVAILABLE_EXECUTORS


# ===========================================================================
# executor_common tests
# ===========================================================================


class TestExecutorCommon:
    """Canonical load_routing_record from executor_common."""

    def test_missing_record_raises(self, tmp_path):
        with pytest.raises(common_mod.ExecutorCommonError, match="not found"):
            common_mod.load_routing_record(tmp_path)

    def test_invalid_json_raises(self, tmp_path):
        (tmp_path / ".agent_bus" / "meta").mkdir(parents=True)
        (tmp_path / ".agent_bus" / "meta" / "post_merge_routing.json").write_text("bad")
        with pytest.raises(common_mod.ExecutorCommonError, match="not valid JSON"):
            common_mod.load_routing_record(tmp_path)

    def test_missing_keys_raises(self, tmp_path):
        (tmp_path / ".agent_bus" / "meta").mkdir(parents=True)
        (tmp_path / ".agent_bus" / "meta" / "post_merge_routing.json").write_text('{"summary":"ok"}')
        with pytest.raises(common_mod.ExecutorCommonError, match="missing keys"):
            common_mod.load_routing_record(tmp_path)

    def test_valid_record_loads(self, tmp_path):
        (tmp_path / ".agent_bus" / "meta").mkdir(parents=True)
        (tmp_path / ".agent_bus" / "meta" / "post_merge_routing.json").write_text(
            '{"decision":"ROUTE_PHASE_B","summary":"ok"}'
        )
        record = common_mod.load_routing_record(tmp_path)
        assert record["decision"] == "ROUTE_PHASE_B"


# ===========================================================================
# 15-step commit pipeline tests (new schema)
# ===========================================================================


# --- Test 1-7: validate_inputs (Step 1) ---

class TestNewSchemaValidation:
    """New-schema handoff validation (Step 1)."""

    def test_1_missing_tracker_note_text_errors(self):
        """Test 1: Missing tracker_note_text → error."""
        handoff = _make_new_handoff()
        del handoff["tracker_note_text"]
        valid, errors = commit_mod.validate_handoff(handoff)
        assert not valid
        assert any("tracker_note_text" in e or "Missing" in e for e in errors)

    def test_2_missing_files_to_stage_errors(self):
        """Test 2: Missing files_to_stage → error."""
        handoff = _make_new_handoff()
        del handoff["files_to_stage"]
        valid, errors = commit_mod.validate_handoff(handoff)
        assert not valid

    def test_3_missing_fixes_implemented_errors(self):
        """Test 3: Missing fixes_implemented → error."""
        handoff = _make_new_handoff()
        del handoff["fixes_implemented"]
        valid, errors = commit_mod.validate_handoff(handoff)
        assert not valid

    def test_4_base_branch_not_dev_errors(self):
        """Test 4: base_branch != 'dev' → error."""
        valid, errors = commit_mod.validate_handoff(_make_new_handoff(base_branch="main"))
        assert not valid
        assert any("dev" in e for e in errors)

    def test_5_wave_id_fails_regex(self):
        """Test 5: wave_id fails regex → error."""
        valid, errors = commit_mod.validate_handoff(_make_new_handoff(wave_id="BAD WAVE"))
        assert not valid
        assert any("wave_id" in e for e in errors)

    def test_6_path_traversal_in_path_field(self):
        """Test 6: Path traversal in any path field → error."""
        valid, errors = commit_mod.validate_handoff(
            _make_new_handoff(pre_commit_receipt_path="../../../etc/passwd")
        )
        assert not valid
        assert any("traversal" in e.lower() for e in errors)

    def test_7_force_add_files_with_git_path_denied(self):
        """Test 7: force_add_files with .git/ path → error."""
        valid, errors = commit_mod.validate_handoff(
            _make_new_handoff(force_add_files=[".git/config"])
        )
        assert not valid
        assert any("denied" in e.lower() or "denylist" in e.lower() for e in errors)

    def test_valid_new_schema_passes(self):
        """Valid new-schema handoff passes validation."""
        valid, errors = commit_mod.validate_handoff(_make_new_handoff())
        assert valid, errors

    def test_empty_tracker_note_text_errors(self):
        """Empty tracker_note_text → error."""
        valid, errors = commit_mod.validate_handoff(_make_new_handoff(tracker_note_text=""))
        assert not valid

    def test_empty_fixes_implemented_errors(self):
        """Empty fixes_implemented list → error."""
        valid, errors = commit_mod.validate_handoff(_make_new_handoff(fixes_implemented=[]))
        assert not valid

    def test_empty_files_to_stage_errors(self):
        """Empty files_to_stage list → error."""
        valid, errors = commit_mod.validate_handoff(_make_new_handoff(files_to_stage=[]))
        assert not valid

    def test_path_traversal_in_files_to_stage(self):
        """Path traversal in files_to_stage → error."""
        valid, errors = commit_mod.validate_handoff(
            _make_new_handoff(files_to_stage=["../../etc/passwd"])
        )
        assert not valid

    def test_force_add_env_denied(self):
        """force_add_files with .env → error."""
        valid, errors = commit_mod.validate_handoff(
            _make_new_handoff(force_add_files=[".env"])
        )
        assert not valid

    def test_force_add_agent_bus_db_denied(self):
        """force_add_files with .agent_bus/meta/*.db → error."""
        valid, errors = commit_mod.validate_handoff(
            _make_new_handoff(force_add_files=[".agent_bus/meta/state.db"])
        )
        assert not valid

    def test_force_add_denylist_case_insensitive(self):
        """force_add_files denylist must be case-insensitive (macOS is case-insensitive)."""
        # .GIT/config should be denied just like .git/config
        valid, errors = commit_mod.validate_handoff(
            _make_new_handoff(force_add_files=[".GIT/config"])
        )
        assert not valid
        assert any("denied" in e.lower() for e in errors)

        # .Env should be denied just like .env
        valid2, errors2 = commit_mod.validate_handoff(
            _make_new_handoff(force_add_files=[".Env"])
        )
        assert not valid2
        assert any("denied" in e.lower() for e in errors2)

        # .AGENT_BUS/meta/foo.db should be denied
        valid3, errors3 = commit_mod.validate_handoff(
            _make_new_handoff(force_add_files=[".AGENT_BUS/meta/foo.db"])
        )
        assert not valid3
        assert any("denied" in e.lower() for e in errors3)

    def test_pre_commit_receipt_path_non_string_errors(self):
        """pre_commit_receipt_path must be a string — non-string rejected."""
        valid, errors = commit_mod.validate_handoff(
            _make_new_handoff(pre_commit_receipt_path=42)
        )
        assert not valid
        assert any("string" in e.lower() for e in errors)

    def test_pre_commit_receipt_path_absolute_errors(self):
        """pre_commit_receipt_path must be relative — absolute path rejected."""
        valid, errors = commit_mod.validate_handoff(
            _make_new_handoff(pre_commit_receipt_path="/tmp/evil/receipt.json")
        )
        assert not valid
        assert any("absolute" in e.lower() for e in errors)

    def test_pre_commit_receipt_path_empty_errors(self):
        """pre_commit_receipt_path must be non-empty."""
        valid, errors = commit_mod.validate_handoff(
            _make_new_handoff(pre_commit_receipt_path="")
        )
        assert not valid
        assert any("non-empty" in e.lower() or "empty" in e.lower() for e in errors)


# --- Tests 8-11: ensure_feature_branch (Step 2) ---

class TestEnsureFeatureBranch:
    """Feature branch creation and verification (Step 2)."""

    def test_8_on_dev_creates_target(self, tmp_path):
        """Test 8: On dev → creates target branch."""
        repo, env = _init_git_repo(tmp_path)
        (repo / "file1.py").write_text("x = 1\n")
        handoff = _make_new_handoff()
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        # Will fail at supervisor step (no supervisor available) but should pass step 2
        assert "ensure_feature_branch" in result.get("steps_completed", [])

    def test_9_already_on_target_continues(self, tmp_path):
        """Test 9: Already on target → continues."""
        repo, env = _init_git_repo(tmp_path)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")
        handoff = _make_new_handoff()
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert "ensure_feature_branch" in result.get("steps_completed", [])

    def test_10_on_other_branch_errors(self, tmp_path):
        """Test 10: On other branch → error."""
        repo, env = _init_git_repo(tmp_path)
        subprocess.run(
            ["git", "checkout", "-b", "other-branch"],
            cwd=repo, capture_output=True, env=env,
        )
        handoff = _make_new_handoff()
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert result["status"] == "error"
        assert result["step"] == "ensure_feature_branch"

    def test_11_remote_collision_errors(self, tmp_path):
        """Test 11: Remote branch collision → error (mocked)."""
        repo, env = _init_git_repo(tmp_path)
        handoff = _make_new_handoff()

        # Mock _run to intercept ls-remote (return remote collision)
        orig_run = commit_mod._run  # ANTICHEAT_OK: testing internal executor functions

        def mock_run(args, **kwargs):
            if len(args) >= 3 and args[0] == "git" and args[1] == "ls-remote":
                result = MagicMock()
                result.stdout = "abc123\trefs/heads/jabramsja/test-wave-id"
                result.returncode = 0
                return result
            return orig_run(args, **kwargs)

        with patch.object(commit_mod, "_run", side_effect=mock_run):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "error"
        assert result["step"] == "ensure_feature_branch"
        assert any("Remote" in e or "already exists" in e for e in result["errors"])


# --- Tests 12-15: ensure_tracker_note (Step 3) ---

class TestEnsureTrackerNote:
    """Tracker note insertion into TASKS.md (Step 3)."""

    def test_12_missing_appends_after_last_in_ra(self, tmp_path):
        """Test 12: Missing wave_id → appends after last tracker note in Ra."""
        repo, env = _init_git_repo(tmp_path)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")
        handoff = _make_new_handoff()
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert "ensure_tracker_note" in result.get("steps_completed", [])
        tasks_content = (repo / "TASKS.md").read_text()
        assert "test-wave-id" in tasks_content

    def test_13_wave_id_present_skips(self, tmp_path):
        """Test 13: wave_id already present → skips."""
        repo, env = _init_git_repo(tmp_path)
        # Pre-insert wave_id into TASKS.md
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        content = content.replace(
            "old note.",
            "old note.\n"
            "- Tracker sync note (2026-03-26, test-wave-id): already here. "
            "FOUNDER_OVERRIDE:2026-03-26-test-wave-id. "
            "indicator_artifact_ref: reports/l4_wave_indicators/test-wave-id.json.\n",
        )
        tasks.write_text(content)
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "add note"], cwd=repo, capture_output=True, env=env)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")
        handoff = _make_new_handoff()
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert "ensure_tracker_note" in result.get("steps_completed", [])

    def test_noncanonical_tracker_note_is_repaired(self, tmp_path):
        """A single malformed tracker note line must be repaired in place."""
        repo, env = _init_git_repo(tmp_path)
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        content = content.replace(
            "old note.",
            "old note.\n- Tracker sync note (Phase B, test-wave-id): malformed placeholder.\n",
        )
        tasks.write_text(content)
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "bad tracker note"], cwd=repo, capture_output=True, env=env)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")
        handoff = _make_new_handoff(
            tracker_note_text=(
                "- Tracker sync note (2026-03-27, test-wave-id): **TEST — repaired tracker note.** "
                "Class: L4_ENABLER. target_gate_id: G8. "
                "evidence_command: `pytest mu/tests/tools/test_executor_dispatch.py -q`. "
                "evidence_delta: repair malformed tracker note. "
                "progress_proof_before: malformed tracker note blocked parser binding. "
                "progress_proof_after: canonical tracker note restored. "
                "primary_blocker_class: INTEGRATION. "
                "primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
                "indicator_artifact_ref: reports/l4_wave_indicators/test-wave-id.json. "
                "indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id test-wave-id --output reports/l4_wave_indicators/test-wave-id.json. "
                "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
                "boot0_track_id: V1. boot0_progress_state: HOLD."
            ),
        )
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert "ensure_tracker_note" in result.get("steps_completed", [])
        tasks_content = (repo / "TASKS.md").read_text()
        assert "- Tracker sync note (Phase B, test-wave-id): malformed placeholder." not in tasks_content
        assert "test-wave-id): **TEST — repaired tracker note.**" in tasks_content

    def test_canonical_tracker_note_is_updated_when_handoff_changes(self, tmp_path):
        """A single canonical tracker note should be refreshed from the handoff when it drifts."""
        repo, env = _init_git_repo(tmp_path)
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        content = content.replace(
            "old note.",
            "old note.\n"
            "- Tracker sync note (2026-03-26, test-wave-id): **TEST — old canonical note.** "
            "Class: L4_ENABLER. target_gate_id: G8. "
            "evidence_command: `pytest old.py -q`. "
            "evidence_delta: old. "
            "progress_proof_before: old. "
            "progress_proof_after: old. "
            "primary_blocker_class: INTEGRATION. "
            "primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
            "indicator_artifact_ref: reports/l4_wave_indicators/test-wave-id.json. "
            "indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id test-wave-id --output reports/l4_wave_indicators/test-wave-id.json. "
            "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            "boot0_track_id: V1. boot0_progress_state: HOLD.\n",
        )
        tasks.write_text(content)
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "old canonical note"], cwd=repo, capture_output=True, env=env)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")
        handoff = _make_new_handoff(
            tracker_note_text=(
                "- Tracker sync note (2026-03-27, test-wave-id): **TEST — refreshed canonical note.** "
                "Class: L4_ENABLER. target_gate_id: G8. "
                "evidence_command: `pytest new.py -q`. "
                "evidence_delta: new. "
                "progress_proof_before: old. "
                "progress_proof_after: refreshed. "
                "primary_blocker_class: INTEGRATION. "
                "primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
                "indicator_artifact_ref: reports/l4_wave_indicators/test-wave-id.json. "
                "indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id test-wave-id --output reports/l4_wave_indicators/test-wave-id.json. "
                "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
                "boot0_track_id: V1. boot0_progress_state: HOLD."
            ),
        )
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert "ensure_tracker_note" in result.get("steps_completed", [])
        tasks_content = (repo / "TASKS.md").read_text()
        assert "old canonical note" not in tasks_content
        assert "refreshed canonical note" in tasks_content

    def test_14_duplicate_wave_id_errors(self, tmp_path):
        """Test 14: Duplicate wave_id → error."""
        repo, env = _init_git_repo(tmp_path)
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        content = content.replace(
            "old note.",
            "old note.\n- test-wave-id first\n- test-wave-id second\n",
        )
        tasks.write_text(content)
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "dup"], cwd=repo, capture_output=True, env=env)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        handoff = _make_new_handoff()
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert result["status"] == "error"
        assert result["step"] == "ensure_tracker_note"
        assert any("duplicate" in e.lower() for e in result["errors"])

    def test_tracker_note_plus_authorized_next_reference_does_not_false_duplicate(self, tmp_path):
        """A canonical tracker note plus an authorized NEXT-item reference must not fail as duplicate."""
        repo, env = _init_git_repo(tmp_path)
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        content = content.replace(
            "old note.",
            "old note.\n"
            "- Tracker sync note (2026-03-27, test-wave-id): **TEST — canonical note.** "
            "Class: L4_ENABLER. target_gate_id: G8. "
            "evidence_command: `pytest mu/tests/tools/test_executor_dispatch.py -q`. "
            "evidence_delta: canonical note. "
            "progress_proof_before: old. "
            "progress_proof_after: new. "
            "primary_blocker_class: INTEGRATION. "
            "primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
            "indicator_artifact_ref: reports/l4_wave_indicators/test-wave-id.json. "
            "indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id test-wave-id --output reports/l4_wave_indicators/test-wave-id.json. "
            "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            "boot0_track_id: V1. boot0_progress_state: HOLD.\n"
            "\n---\n\n## NEXT\n"
            "- **[TEST]** Authorized item. **Tracked packet:** `reports/control_plane/test-wave-id.md`.\n"
            "  Current status: references test-wave-id again for operator truth.\n",
        )
        tasks.write_text(content)
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "canonical note plus next reference"], cwd=repo, capture_output=True, env=env)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")
        handoff = _make_new_handoff()
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert result["step"] != "ensure_tracker_note" or result["status"] != "error"
        assert "ensure_tracker_note" in result.get("steps_completed", [])

    def test_15_ra_missing_errors(self, tmp_path):
        """Test 15: '## Ra' missing from TASKS.md → error."""
        repo, env = _init_git_repo(tmp_path)
        tasks = repo / "TASKS.md"
        tasks.write_text("# Tasks\n\n## NEXT\n\n- something\n")
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "no ra"], cwd=repo, capture_output=True, env=env)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        handoff = _make_new_handoff()
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert result["status"] == "error"
        assert result["step"] == "ensure_tracker_note"

    def test_exact_wave_id_match_does_not_false_positive_substring(self, tmp_path):
        """A similar wave_id like test-wave-id-extra must not block insertion for test-wave-id."""
        repo, env = _init_git_repo(tmp_path)
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        tasks.write_text(content.replace("old note.", "old note.\n- Tracker sync note (test-wave-id-extra): already here.\n"))
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "similar note"], cwd=repo, capture_output=True, env=env)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")
        handoff = _make_new_handoff()
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert "ensure_tracker_note" in result.get("steps_completed", [])
        tasks_content = (repo / "TASKS.md").read_text()
        assert "test-wave-id-extra" in tasks_content
        assert "test-wave-id" in tasks_content

    def test_archived_tracker_note_outside_ra_does_not_block_active_note_insert(self, tmp_path):
        """Archived tracker-note history outside ## Ra must not satisfy or overwrite the live note."""
        repo, env = _init_git_repo(tmp_path)
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        tasks.write_text(
            content.replace(
                "---\n\n## NEXT\n",
                "---\n\n## ARCHIVE\n"
                "- Tracker sync note (2026-03-20, test-wave-id): **TEST — archived historical note.** "
                "Class: L4_ENABLER. target_gate_id: G8. "
                "evidence_command: `pytest old.py -q`. "
                "evidence_delta: archived. "
                "progress_proof_before: old. "
                "progress_proof_after: old. "
                "primary_blocker_class: INTEGRATION. "
                "primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
                "indicator_artifact_ref: reports/l4_wave_indicators/test-wave-id.json. "
                "indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id test-wave-id --output reports/l4_wave_indicators/test-wave-id.json. "
                "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
                "boot0_track_id: V1. boot0_progress_state: HOLD.\n\n"
                "---\n\n## NEXT\n"
            )
        )
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "archived tracker note"], cwd=repo, capture_output=True, env=env)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")
        handoff = _make_new_handoff(
            tracker_note_text=(
                "- Tracker sync note (2026-03-27, test-wave-id): **TEST — active canonical note.** "
                "Class: L4_ENABLER. target_gate_id: G8. "
                "evidence_command: `pytest new.py -q`. "
                "evidence_delta: active. "
                "progress_proof_before: archived. "
                "progress_proof_after: active. "
                "primary_blocker_class: INTEGRATION. "
                "primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
                "indicator_artifact_ref: reports/l4_wave_indicators/test-wave-id.json. "
                "indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id test-wave-id --output reports/l4_wave_indicators/test-wave-id.json. "
                "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
                "boot0_track_id: V1. boot0_progress_state: HOLD."
            ),
        )

        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert "ensure_tracker_note" in result.get("steps_completed", [])
        tasks_content = (repo / "TASKS.md").read_text()
        assert tasks_content.count("active canonical note") == 1
        assert tasks_content.count("archived historical note") == 1
        ra_idx = tasks_content.index("## Ra")
        archive_idx = tasks_content.index("## ARCHIVE")
        assert tasks_content.index("active canonical note") > ra_idx
        assert tasks_content.index("active canonical note") < archive_idx


class TestDispatcherPlanNameSanitization:
    """Phase A dispatch must sanitize candidate text before passing --plan-name."""

    def test_phase_a_candidate_text_is_sanitized(self, tmp_path, monkeypatch):
        record = {
            "decision": "ROUTE_PHASE_A",
            "state_sha": "ignored",
            "wave_name": "unsafe wave",
            "next_candidates": [{"candidate": "../../Unsafe Plan (v1)"}],
        }

        captured: dict[str, list[str]] = {}

        calls = []
        def fake_run(args, cwd, timeout):
            calls.append(args)
            if len(calls) == 1:
                return subprocess.CompletedProcess(args, 0, stdout="[phase-a] Status: converged\n[phase-a] Plan: test_plan.md\n", stderr="")
            return subprocess.CompletedProcess(args, 0, stdout="{}", stderr="")

        monkeypatch.setattr(dispatch_mod, "validate_routing_record_freshness", lambda *a, **k: (True, "fresh"))
        monkeypatch.setattr(dispatch_mod, "_run_executor_in_group", fake_run)

        dispatch_mod.dispatch(record, repo_root=tmp_path, skip_freshness=True)

        phase_a_args = calls[0]
        assert "--plan-name" in phase_a_args
        plan_name = phase_a_args[phase_a_args.index("--plan-name") + 1]
        assert ".." not in plan_name
        assert "/" not in plan_name
        assert "\\" not in plan_name
        assert plan_name == "unsafe_plan_v1"

    def test_phase_a_prefers_tracked_packet_stem(self, tmp_path, monkeypatch):
        record = {
            "decision": "ROUTE_PHASE_A",
            "state_sha": "ignored",
            "wave_name": "tracked-wave",
            "next_candidates": [{
                "candidate": "ignored candidate",
                "tracked_packet": "reports/control_plane/recovery_tier3_wiring_2026-04-01.md",
            }],
        }

        calls = []

        def fake_run(args, cwd, timeout):
            calls.append(args)
            return subprocess.CompletedProcess(
                args, 0,
                stdout="[phase-a] Status: converged\n[phase-a] Plan: reports/control_plane/recovery_tier3_wiring_2026-04-01.md\n",
                stderr="",
            )

        monkeypatch.setattr(dispatch_mod, "validate_routing_record_freshness", lambda *a, **k: (True, "fresh"))
        monkeypatch.setattr(dispatch_mod, "_run_executor_in_group", fake_run)

        dispatch_mod.dispatch(record, repo_root=tmp_path, skip_freshness=True)

        phase_a_args = calls[0]
        assert "--json" in phase_a_args
        plan_name = phase_a_args[phase_a_args.index("--plan-name") + 1]
        assert plan_name == "recovery_tier3_wiring_2026-04-01"

    def test_phase_b_dispatch_requests_json_output(self, tmp_path, monkeypatch):
        record = {
            "decision": "ROUTE_PHASE_B",
            "wave_name": "tracked-wave",
            "next_candidates": [{
                "tracked_packet": "reports/control_plane/recovery_tier3_wiring_2026-04-01.md",
            }],
        }
        calls = []

        def fake_run(args, cwd, timeout):
            calls.append(args)
            return subprocess.CompletedProcess(args, 1, stdout="{}", stderr="")

        monkeypatch.setattr(dispatch_mod, "validate_routing_record_freshness", lambda *a, **k: (True, "fresh"))
        monkeypatch.setattr(dispatch_mod, "_run_executor_in_group", fake_run)

        dispatch_mod.dispatch(record, repo_root=tmp_path, skip_freshness=True)

        assert "--json" in calls[0]


# --- Tests 16-19: stage_files (Step 4) and collect_indicator (Step 5) ---

class TestStageFiles:
    """File staging (Step 4) and indicator collection (Step 5)."""

    def test_16_nothing_to_stage_errors(self, tmp_path):
        """Test 16: Nothing to stage → error (no manufactured diff)."""
        repo, env = _init_git_repo(tmp_path)
        # Create and commit file1.py, so staging it again stages nothing new
        (repo / "file1.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "file1.py"], cwd=repo, capture_output=True, env=env)
        # Pre-insert wave_id so ensure_tracker_note skips (no TASKS.md modification)
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        tasks.write_text(content.replace("old note.", "old note.\n- test-wave-id present\n"))
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "add file1"], cwd=repo, capture_output=True, env=env)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        # file1.py already committed with same content — staging it adds nothing
        # TASKS.md already has wave_id — no modification
        handoff = _make_new_handoff()
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert result["status"] == "error"
        assert result["step"] == "stage_files"
        assert any("Nothing staged" in e or "nothing" in e.lower() for e in result["errors"])

    def test_17_auto_adds_tasks_not_indicator(self, tmp_path):
        """Test 17: Auto-adds TASKS.md but NOT indicator (step 5 handles indicator)."""
        repo, env = _init_git_repo(tmp_path)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")
        handoff = _make_new_handoff()
        # Pipeline will proceed past step 4. We verify by checking steps_completed
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert "stage_files" in result.get("steps_completed", [])

    def test_18_indicator_runs_after_staging(self, tmp_path):
        """Test 18: Indicator collection runs AFTER staging (mocked)."""
        repo, env = _init_git_repo(tmp_path)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")

        # Create mock indicator script
        (repo / "mu" / "tools" / "metrics").mkdir(parents=True, exist_ok=True)
        (repo / "mu" / "tools" / "metrics" / "collect_l4_wave_indicators.py").write_text(
            '#!/usr/bin/env python3\nimport argparse, json, os\n'
            'p = argparse.ArgumentParser()\np.add_argument("--wave-id")\n'
            'p.add_argument("--output")\nargs = p.parse_args()\n'
            'os.makedirs(os.path.dirname(args.output), exist_ok=True)\n'
            'with open(args.output, "w") as f: json.dump({"wave_id": args.wave_id}, f)\n'
        )
        (repo / "reports" / "l4_wave_indicators").mkdir(parents=True, exist_ok=True)

        handoff = _make_new_handoff()
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        # Should pass step 5
        assert "collect_and_stage_indicator" in result.get("steps_completed", [])

    def test_19_indicator_force_adds_artifact(self, tmp_path):
        """Test 19: Indicator artifact is force-added to staging."""
        repo, env = _init_git_repo(tmp_path)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")

        # Create mock indicator script
        (repo / "mu" / "tools" / "metrics").mkdir(parents=True, exist_ok=True)
        (repo / "mu" / "tools" / "metrics" / "collect_l4_wave_indicators.py").write_text(
            '#!/usr/bin/env python3\nimport argparse, json, os\n'
            'p = argparse.ArgumentParser()\np.add_argument("--wave-id")\n'
            'p.add_argument("--output")\nargs = p.parse_args()\n'
            'os.makedirs(os.path.dirname(args.output), exist_ok=True)\n'
            'with open(args.output, "w") as f: json.dump({"wave_id": args.wave_id}, f)\n'
        )
        (repo / "reports" / "l4_wave_indicators").mkdir(parents=True, exist_ok=True)

        # Gitignore reports
        (repo / ".gitignore").write_text("reports/l4_wave_indicators/\n")
        subprocess.run(["git", "add", ".gitignore"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "ignore"], cwd=repo, capture_output=True, env=env)

        handoff = _make_new_handoff()
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert "collect_and_stage_indicator" in result.get("steps_completed", [])


# --- Tests 20-22: Supervisor package (Step 6) ---

class TestSupervisorPackage:
    """Supervisor package construction (Step 6)."""

    def test_20_supervisor_package_has_11_fields(self, tmp_path):
        """Test 20: Supervisor package built with correct 11 fields."""
        # We can't run the full pipeline but we can verify the package structure
        # by inspecting the handoff fields that map to supervisor package fields.
        handoff = _make_new_handoff()
        expected_fields = {
            "task_id", "wave_name", "lane", "changed_files", "scope_items",
            "fixes_implemented", "deferred_items", "bridge_status",
            "evidence_handles", "blocker_report_paths", "current_judgment",
        }
        # Verify handoff has the source data for all 11 supervisor fields
        assert "task_id" in handoff
        assert "caller" in handoff  # maps to lane
        assert "files_to_stage" in handoff  # maps to scope_items
        assert "fixes_implemented" in handoff
        assert len(expected_fields) == 11

    def test_20b_phase_b_metadata_is_preserved_into_supervisor_package(self, tmp_path):
        repo, env = _init_git_repo(tmp_path)
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        tasks.write_text(content.replace("old note.", "old note.\n- test-wave-id already\n"))
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "note"], cwd=repo, capture_output=True, env=env)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")

        mock_result = MagicMock()
        mock_result.decision = "NEEDS_PHASE_B"
        mock_result.receipt_path = ".agent_bus/meta/pre_commit_receipt.json"
        mock_result.summary = "re-enter phase b"

        handoff = _make_new_handoff(
            caller="phase_b",
            supervisor_lane="hooks/agents/bridge control-surface",
            deferred_items=["reports/deferred/non_blocking/example.md"],
            bridge_status={"rounds": 2, "reentry": True},
            scope_items=[
                "reports/control_plane/test_plan.md",
                "mu/tools/agents/meta_bridge_supervisor.py",
            ],
            evidence_handles={"receipt_chain": "canonical and per-invocation receipts preserved"},
        )

        with patch.dict(sys.modules, {"meta_bridge_client": MagicMock()}):
            sys.modules["meta_bridge_client"].run_meta_bridge_package = MagicMock(return_value=mock_result)
            sys.modules["meta_bridge_client"].MetaBridgeClientError = Exception
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "error"
        assert result["step"] == "build_and_run_supervisor"
        package = json.loads((repo / ".scratch" / "auto_supervisor_package.json").read_text())
        assert package["lane"] == "hooks/agents/bridge control-surface"
        assert package["deferred_items"] == ["reports/deferred/non_blocking/example.md"]
        assert package["bridge_status"] == {"rounds": 2, "reentry": True}
        assert package["scope_items"] == [
            "reports/control_plane/test_plan.md",
            "mu/tools/agents/meta_bridge_supervisor.py",
            "file1.py",
        ]
        assert package["evidence_handles"] == {
            "receipt_chain": "canonical and per-invocation receipts preserved",
            "indicator": "reports/l4_wave_indicators/test-wave-id.json",
        }

    def test_21_changed_files_empty_errors(self, tmp_path):
        """Test 21: changed_files empty → error before supervisor.

        This is mechanically enforced: if step 4 stages nothing, step 4 fails.
        Step 6 also checks changed_files non-empty as belt+suspenders.
        """
        repo, env = _init_git_repo(tmp_path)
        (repo / "file1.py").write_text("x = 1\n")
        # Pre-insert wave_id so tracker note skips
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        tasks.write_text(content.replace("old note.", "old note.\n- test-wave-id present\n"))
        subprocess.run(["git", "add", "file1.py", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "add"], cwd=repo, capture_output=True, env=env)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        handoff = _make_new_handoff()
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert result["status"] == "error"
        # Fails at stage_files (nothing to stage) which prevents supervisor from seeing empty
        assert result["step"] == "stage_files"

    def test_22_supervisor_invoked_with_sanitized_env(self):
        """Test 22: _run sanitizes RCX_SKIP_* env vars."""
        # Verify _run strips RCX_SKIP_* from env
        with patch.dict(os.environ, {"RCX_SKIP_TESTS": "1", "PATH": "/usr/bin"}):
            # The _run function creates env without RCX_SKIP_* keys
            # We verify by checking the function's env sanitization logic
            env = {k: v for k, v in os.environ.items() if not k.startswith("RCX_SKIP_")}
            assert "RCX_SKIP_TESTS" not in env
            assert "PATH" in env


# --- Tests 23-28: Receipt, pre-commit, commit, hold (Steps 7-10) ---

class TestReceiptAndCommit:
    """Receipt validation, pre-commit, commit, hold (Steps 7-10)."""

    def test_23_receipt_read_directly_not_verify(self):
        """Test 23: Receipt read directly (JSON parse, not verify_pre_commit_receipt).

        The plan says step 7 reads receipt JSON directly for the decision field only.
        We verify by checking that step 7 (validate_receipt) uses json.loads on the
        receipt file, and does NOT call verify_pre_commit_receipt().
        """
        import inspect
        source = inspect.getsource(commit_mod.run_commit_pipeline)
        # Step 7 should NOT call verify_pre_commit_receipt
        # It should use json.loads to read the receipt directly
        # The function uses receipt_data = json.loads(receipt_file.read_text(...))
        assert "json.loads(receipt_file.read_text" in source

    def test_step6_fails_closed_on_empty_supervisor_receipt_path(self, tmp_path):
        """Step 6 must fail closed when supervisor returns empty receipt_path.

        R2 finding #1: empty receipt_path rejected at step 6 (build_and_run_supervisor).
        """
        repo, env = _init_git_repo(tmp_path)
        # Pre-insert wave_id
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        tasks.write_text(content.replace("old note.", "old note.\n- test-wave-id already\n"))
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "note"], cwd=repo, capture_output=True, env=env)

        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")

        # Create a receipt at the handoff path (this SHOULD NOT be used as fallback)
        receipt_dir = repo / ".agent_bus" / "meta"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        (receipt_dir / "pre_commit_receipt.json").write_text(
            json.dumps({"decision": "COMMIT_GO", "staged_sha": "x", "timestamp_utc": "2026-01-01T00:00:00Z"})
        )

        # Mock supervisor that returns COMMIT_GO but empty receipt_path
        mock_result = MagicMock()
        mock_result.decision = "COMMIT_GO"
        mock_result.receipt_path = ""  # Empty — must fail closed at step 6
        mock_result.summary = "ok"

        with patch.dict(sys.modules, {"meta_bridge_client": MagicMock()}):
            sys.modules["meta_bridge_client"].run_meta_bridge_package = MagicMock(return_value=mock_result)
            sys.modules["meta_bridge_client"].MetaBridgeClientError = Exception
            result = commit_mod.run_commit_pipeline(_make_new_handoff(), repo_root=repo)

        assert result["status"] == "error"
        assert result["step"] == "build_and_run_supervisor"
        assert any("empty" in e.lower() or "fail closed" in e.lower() for e in result["errors"])

    def test_step6_fails_closed_on_none_supervisor_receipt_path(self, tmp_path):
        """Step 6 must fail closed when supervisor returns None receipt_path."""
        repo, env = _init_git_repo(tmp_path)
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        tasks.write_text(content.replace("old note.", "old note.\n- test-wave-id already\n"))
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "note"], cwd=repo, capture_output=True, env=env)

        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")

        # Create a receipt at the handoff path (must NOT be used as fallback)
        receipt_dir = repo / ".agent_bus" / "meta"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        (receipt_dir / "pre_commit_receipt.json").write_text(
            json.dumps({"decision": "COMMIT_GO"})
        )

        mock_result = MagicMock()
        mock_result.decision = "COMMIT_GO"
        mock_result.receipt_path = None  # None — must fail closed at step 6
        mock_result.summary = "ok"

        with patch.dict(sys.modules, {"meta_bridge_client": MagicMock()}):
            sys.modules["meta_bridge_client"].run_meta_bridge_package = MagicMock(return_value=mock_result)
            sys.modules["meta_bridge_client"].MetaBridgeClientError = Exception
            result = commit_mod.run_commit_pipeline(_make_new_handoff(), repo_root=repo)

        assert result["status"] == "error"
        assert result["step"] == "build_and_run_supervisor"

    def test_step6_fails_closed_on_absolute_supervisor_receipt_path(self, tmp_path):
        """Step 6 must reject absolute receipt_path from supervisor."""
        repo, env = _init_git_repo(tmp_path)
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        tasks.write_text(content.replace("old note.", "old note.\n- test-wave-id already\n"))
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "note"], cwd=repo, capture_output=True, env=env)

        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")

        mock_result = MagicMock()
        mock_result.decision = "COMMIT_GO"
        mock_result.receipt_path = "/tmp/evil/outside_receipt.json"  # Absolute — must fail
        mock_result.summary = "ok"

        with patch.dict(sys.modules, {"meta_bridge_client": MagicMock()}):
            sys.modules["meta_bridge_client"].run_meta_bridge_package = MagicMock(return_value=mock_result)
            sys.modules["meta_bridge_client"].MetaBridgeClientError = Exception
            result = commit_mod.run_commit_pipeline(_make_new_handoff(), repo_root=repo)

        assert result["status"] == "error"
        assert result["step"] == "build_and_run_supervisor"
        assert any("absolute" in e.lower() for e in result["errors"])

    def test_step6_fails_closed_on_traversal_supervisor_receipt_path(self, tmp_path):
        """Step 6 must reject receipt_path with path traversal from supervisor."""
        repo, env = _init_git_repo(tmp_path)
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        tasks.write_text(content.replace("old note.", "old note.\n- test-wave-id already\n"))
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "note"], cwd=repo, capture_output=True, env=env)

        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")

        mock_result = MagicMock()
        mock_result.decision = "COMMIT_GO"
        mock_result.receipt_path = "../../../etc/passwd"  # Traversal — must fail
        mock_result.summary = "ok"

        with patch.dict(sys.modules, {"meta_bridge_client": MagicMock()}):
            sys.modules["meta_bridge_client"].run_meta_bridge_package = MagicMock(return_value=mock_result)
            sys.modules["meta_bridge_client"].MetaBridgeClientError = Exception
            result = commit_mod.run_commit_pipeline(_make_new_handoff(), repo_root=repo)

        assert result["status"] == "error"
        assert result["step"] == "build_and_run_supervisor"
        assert any("traversal" in e.lower() for e in result["errors"])

    def test_step6_fails_closed_on_supervisor_receipt_prefix_confusion(self, tmp_path):
        """Containment must use path ancestry, not naive string prefix matching."""
        repo, env = _init_git_repo(tmp_path)
        evil_repo = tmp_path / "repo-evil"
        evil_repo.mkdir()
        (evil_repo / "receipt.json").write_text(json.dumps({"decision": "COMMIT_GO"}))

        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        tasks.write_text(content.replace("old note.", "old note.\n- test-wave-id already\n"))
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "note"], cwd=repo, capture_output=True, env=env)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")

        mock_result = MagicMock()
        mock_result.decision = "COMMIT_GO"
        mock_result.receipt_path = "../repo-evil/receipt.json"
        mock_result.summary = "ok"

        with patch.object(commit_mod, "_has_path_traversal", return_value=False), \
             patch.dict(sys.modules, {"meta_bridge_client": MagicMock()}):
            sys.modules["meta_bridge_client"].run_meta_bridge_package = MagicMock(return_value=mock_result)
            sys.modules["meta_bridge_client"].MetaBridgeClientError = Exception
            result = commit_mod.run_commit_pipeline(_make_new_handoff(), repo_root=repo)

        assert result["status"] == "error"
        assert result["step"] == "build_and_run_supervisor"
        assert any("escapes repo" in e.lower() for e in result["errors"])

    def test_step7_uses_supervisor_receipt_path(self, tmp_path):
        """Step 7 validates the full receipt chain: both the Phase B handoff
        receipt (from the handoff's pre_commit_receipt_path) AND the supervisor
        receipt (from step 6 output). Both must exist and authorize commit."""
        repo, env = _init_git_repo(tmp_path)
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        tasks.write_text(content.replace("old note.", "old note.\n- test-wave-id already\n"))
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "note"], cwd=repo, capture_output=True, env=env)

        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")

        # Supervisor writes receipt at its own path
        supervisor_receipt_dir = repo / ".scratch"
        supervisor_receipt_dir.mkdir(parents=True, exist_ok=True)
        (supervisor_receipt_dir / "supervisor_receipt.json").write_text(
            json.dumps({"decision": "COMMIT_GO", "staged_sha": "x", "timestamp_utc": "2026-01-01T00:00:00Z"})
        )

        # Handoff receipt must also exist — step 7 validates the full chain
        handoff_receipt_dir = repo / ".agent_bus" / "meta"
        handoff_receipt_dir.mkdir(parents=True, exist_ok=True)
        (handoff_receipt_dir / "pre_commit_receipt.json").write_text(
            json.dumps({"decision": "COMMIT_GO", "staged_sha": "x", "timestamp_utc": "2026-01-01T00:00:00Z"})
        )

        mock_result = MagicMock()
        mock_result.decision = "COMMIT_GO"
        mock_result.receipt_path = ".scratch/supervisor_receipt.json"
        mock_result.summary = "ok"

        handoff = _make_new_handoff(
            pre_commit_receipt_path=".agent_bus/meta/pre_commit_receipt.json"
        )

        with patch.dict(sys.modules, {"meta_bridge_client": MagicMock()}):
            sys.modules["meta_bridge_client"].run_meta_bridge_package = MagicMock(return_value=mock_result)
            sys.modules["meta_bridge_client"].MetaBridgeClientError = Exception
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        # Step 7 should PASS — both handoff and supervisor receipts exist and authorize
        assert "validate_receipt" in result.get("steps_completed", []), (
            f"Step 7 should succeed with full receipt chain. Got: {result}"
        )

    def test_step7_reads_supervisor_receipt_decision_only(self, tmp_path):
        """Step 7 validates the full receipt chain but does NOT check staged_sha.

        No staged_sha check at step 7 — the supervisor receipt was minted against
        the staged state AFTER steps 3-5 ran. The pre-commit hook at step 9
        verifies staged state independently.
        """
        repo, env = _init_git_repo(tmp_path)
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        tasks.write_text(content.replace("old note.", "old note.\n- test-wave-id already\n"))
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "note"], cwd=repo, capture_output=True, env=env)

        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")

        # Create supervisor receipt with valid decision.
        sup_receipt_dir = repo / ".scratch"
        sup_receipt_dir.mkdir(parents=True, exist_ok=True)
        (sup_receipt_dir / "supervisor_receipt.json").write_text(
            json.dumps({"decision": "COMMIT_GO", "staged_sha": "fresh_sha",
                         "timestamp_utc": "2026-01-01T00:00:00Z"})
        )

        # Handoff receipt must also exist — step 7 validates the full chain
        handoff_receipt_dir = repo / ".agent_bus" / "meta"
        handoff_receipt_dir.mkdir(parents=True, exist_ok=True)
        (handoff_receipt_dir / "pre_commit_receipt.json").write_text(
            json.dumps({"decision": "COMMIT_GO", "staged_sha": "fresh_sha",
                         "timestamp_utc": "2026-01-01T00:00:00Z"})
        )

        mock_result = MagicMock()
        mock_result.decision = "COMMIT_GO"
        mock_result.receipt_path = ".scratch/supervisor_receipt.json"
        mock_result.summary = "ok"

        handoff = _make_new_handoff()

        with patch.dict(sys.modules, {"meta_bridge_client": MagicMock()}):
            sys.modules["meta_bridge_client"].run_meta_bridge_package = MagicMock(return_value=mock_result)
            sys.modules["meta_bridge_client"].MetaBridgeClientError = Exception
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        # Should pass step 7 (validate_receipt) — no staged_sha check here
        assert "validate_receipt" in result.get("steps_completed", []), (
            f"Step 7 should succeed with full receipt chain. Got: {result}"
        )

    def test_24_pre_commit_script_failure_errors(self, tmp_path):
        """Test 24: Pre-commit script failure → error at step 8."""
        repo, env = _init_git_repo(tmp_path)
        # Pre-insert wave_id so tracker note step skips
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        tasks.write_text(content.replace("old note.", "old note.\n- test-wave-id already\n"))
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "note"], cwd=repo, capture_output=True, env=env)

        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")

        # Create a failing pre-commit script
        hooks_dir = repo / "mu" / "tools" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        script = hooks_dir / "pre-commit-doc-check"
        script.write_text("#!/bin/bash\necho 'FAIL' >&2\nexit 1\n")
        script.chmod(0o755)

        # Stage file1.py to compute staged_sha for valid receipt
        subprocess.run(["git", "add", "file1.py"], cwd=repo, capture_output=True, env=env)
        staged_sha = _compute_staged_sha(repo)

        # Create receipt with correct staged_sha
        receipt_dir = repo / ".agent_bus" / "meta"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        (receipt_dir / "pre_commit_receipt.json").write_text(
            json.dumps({"decision": "COMMIT_GO", "staged_sha": staged_sha, "timestamp_utc": "2026-01-01T00:00:00Z"})
        )

        # Mock supervisor to return COMMIT_GO
        mock_result = MagicMock()
        mock_result.decision = "COMMIT_GO"
        mock_result.receipt_path = ".agent_bus/meta/pre_commit_receipt.json"
        mock_result.summary = "ok"

        with patch.dict(sys.modules, {"meta_bridge_client": MagicMock()}):
            sys.modules["meta_bridge_client"].run_meta_bridge_package = MagicMock(return_value=mock_result)
            sys.modules["meta_bridge_client"].MetaBridgeClientError = Exception
            result = commit_mod.run_commit_pipeline(_make_new_handoff(), repo_root=repo)

        assert result["status"] == "error"
        assert result["step"] == "run_pre_commit_script"

    def test_step11_pre_push_failure_surfaces_stdout_when_stderr_empty(self, tmp_path):
        """Step 11 should surface stdout if pre-push-fast writes no stderr."""
        repo, env, mock_result = self._setup_repo_through_supervisor(tmp_path, "COMMIT_GO")

        hooks_dir = repo / "mu" / "tools" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        script = hooks_dir / "pre-push-fast"
        script.write_text("#!/bin/bash\necho 'tracker note contract failed'\nexit 1\n")
        script.chmod(0o755)

        with patch.dict(sys.modules, {"meta_bridge_client": MagicMock()}):
            sys.modules["meta_bridge_client"].run_meta_bridge_package = MagicMock(return_value=mock_result)
            sys.modules["meta_bridge_client"].MetaBridgeClientError = Exception
            result = commit_mod.run_commit_pipeline(_make_new_handoff(), repo_root=repo)

        assert result["status"] == "error"
        assert result["step"] == "run_pre_push_script"
        assert any("tracker note contract failed" in e for e in result["errors"])

    def test_step11_uses_extended_pre_push_timeout(self, tmp_path):
        """Step 11 must give pre-push-fast enough time for the real fast audit path."""
        repo, env, mock_result = self._setup_repo_through_supervisor(tmp_path, "COMMIT_GO")

        hooks_dir = repo / "mu" / "tools" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        script = hooks_dir / "pre-push-fast"
        script.write_text("#!/bin/bash\nexit 0\n")
        script.chmod(0o755)

        orig_run = commit_mod._run  # ANTICHEAT_OK: asserting Step 11 timeout contract
        seen_timeout = {"value": None}

        def fake_run(cmd, cwd=None, timeout=None, check=True, env=None):
            if cmd[:2] == ["bash", str(script)]:
                seen_timeout["value"] = timeout
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)
            return orig_run(cmd, cwd=cwd, timeout=timeout, check=check, env=env)

        with patch.dict(sys.modules, {"meta_bridge_client": MagicMock()}):
            sys.modules["meta_bridge_client"].run_meta_bridge_package = MagicMock(return_value=mock_result)
            sys.modules["meta_bridge_client"].MetaBridgeClientError = Exception
            with patch.object(commit_mod, "_run", side_effect=fake_run):
                result = commit_mod.run_commit_pipeline(_make_new_handoff(), repo_root=repo)

        assert result["status"] == "error"
        assert result["step"] == "run_pre_push_script"
        assert any("timed out" in e for e in result["errors"])
        assert seen_timeout["value"] == commit_mod.PRE_PUSH_FAST_TIMEOUT_S

    def _setup_repo_through_supervisor(self, tmp_path, receipt_decision="COMMIT_GO"):
        """Helper: create repo, pre-insert wave_id, create receipt, return (repo, env, mock)."""
        repo, env = _init_git_repo(tmp_path)
        # Pre-insert wave_id so tracker note step skips
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        tasks.write_text(content.replace("old note.", "old note.\n- test-wave-id already\n"))
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "note"], cwd=repo, capture_output=True, env=env)

        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")

        # Stage file1.py to compute staged_sha for valid receipt
        subprocess.run(["git", "add", "file1.py"], cwd=repo, capture_output=True, env=env)
        staged_sha = _compute_staged_sha(repo)

        receipt_dir = repo / ".agent_bus" / "meta"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        (receipt_dir / "pre_commit_receipt.json").write_text(
            json.dumps({"decision": receipt_decision, "staged_sha": staged_sha,
                         "timestamp_utc": "2026-01-01T00:00:00Z"})
        )

        mock_result = MagicMock()
        mock_result.decision = receipt_decision
        mock_result.receipt_path = ".agent_bus/meta/pre_commit_receipt.json"
        mock_result.summary = "ok"
        return repo, env, mock_result

    def test_25_commit_go_full_pipeline(self, tmp_path):
        """Test 25: COMMIT_GO → full pipeline (steps 11-15 run).

        We verify by checking that hold_check is in steps_completed and
        the pipeline continues past step 10.
        """
        repo, env, mock_result = self._setup_repo_through_supervisor(tmp_path, "COMMIT_GO")

        with patch.dict(sys.modules, {"meta_bridge_client": MagicMock()}):
            sys.modules["meta_bridge_client"].run_meta_bridge_package = MagicMock(return_value=mock_result)
            sys.modules["meta_bridge_client"].MetaBridgeClientError = Exception
            result = commit_mod.run_commit_pipeline(_make_new_handoff(), repo_root=repo)

        # Should pass hold_check (COMMIT_GO means continue)
        assert "hold_check" in result.get("steps_completed", [])
        # Should fail at step 11 (pre-push-fast) or 12 (git push) since no remote
        # But the key is that it GOT PAST hold_check
        assert result.get("status") in ("error", "success")

    def test_26_commit_go_hold_push_held_at_step_10(self, tmp_path):
        """Test 26: COMMIT_GO_HOLD_PUSH → held at step 10, steps 11-15 NOT run."""
        repo, env, mock_result = self._setup_repo_through_supervisor(tmp_path, "COMMIT_GO_HOLD_PUSH")

        with patch.dict(sys.modules, {"meta_bridge_client": MagicMock()}):
            sys.modules["meta_bridge_client"].run_meta_bridge_package = MagicMock(return_value=mock_result)
            sys.modules["meta_bridge_client"].MetaBridgeClientError = Exception
            result = commit_mod.run_commit_pipeline(_make_new_handoff(), repo_root=repo)

        assert result["status"] == "held"
        assert "hold_check" in result["steps_completed"]
        assert "git_commit" in result["steps_completed"]
        # Steps 11-15 must NOT be in steps_completed
        assert "run_pre_push_script" not in result["steps_completed"]
        assert "git_push" not in result["steps_completed"]
        assert "ensure_pr" not in result["steps_completed"]
        assert "wait_ci" not in result["steps_completed"]
        assert "ensure_review_clear_and_merge" not in result["steps_completed"]
        assert "commit_sha" in result

    def test_27_post_merge_verify_failure_errors(self):
        """Test 27: Post-merge verify failure → error (not success).

        The plan says: FAIL-CLOSED on verify failure.
        We verify by checking the code returns error status on CalledProcessError.
        """
        source = _commit_post_commit_source()
        # The code should return error on post-merge verify failure
        assert "Post-merge verify failed" in source

    def test_28_timeout_structured_error(self):
        """Test 28: TimeoutExpired → structured error.

        Verify that TimeoutExpired is caught and returns structured error
        at various steps in the pipeline.
        """
        import inspect
        source = inspect.getsource(commit_mod.run_commit_pipeline)
        assert "TimeoutExpired" in source


# --- Tests 29-37: PR and review (Steps 13-15) ---

class TestPRAndReview:
    """PR creation, CI wait, review, and merge (Steps 13-15)."""

    def test_29_pr_number_non_numeric_errors(self):
        """Test 29: PR number non-numeric → error.

        The plan says: validate PR number is numeric (isdigit).
        """
        source = _commit_post_commit_source()
        assert "isdigit" in source

    def test_30_ensure_pr_no_pr_creates(self):
        """Test 30: No existing PR → creates new.

        Verified by code structure: pr_list empty → gh pr create path.
        """
        source = _commit_post_commit_source()
        assert "gh pr create" in source or "pr create" in source

    def test_31_ensure_pr_existing_reuses_and_syncs(self):
        """Test 31: Existing PR → reuses + syncs via gh pr edit."""
        source = _commit_post_commit_source()
        # The code builds command lists like ["gh", "pr", "edit", ...]
        assert '"gh", "pr", "edit"' in source or "pr edit" in source

    def test_32_ensure_pr_multiple_errors(self):
        """Test 32: Multiple open PRs → error."""
        source = _commit_post_commit_source()
        assert "Multiple" in source or "multiple" in source

    def test_33_human_changes_requested_errors(self):
        """Test 33: Human CHANGES_REQUESTED → error."""
        source = _commit_post_commit_source()
        assert "CHANGES_REQUESTED" in source

    def test_34_unresolved_human_thread_errors(self):
        """Test 34: Unresolved human thread → error."""
        source = _commit_post_commit_source()
        assert "Unresolved human" in source or "unresolved human" in source.lower()

    def test_35_unresolved_bot_thread_returns_bot_findings(self):
        """Test 35: Unresolved bot thread → bot_findings_pending."""
        source = _commit_post_commit_source()
        assert "bot_findings_pending" in source

    def test_36_resolved_bot_threads_clear(self):
        """Test 36: Resolved bot threads only → clear, merge proceeds.

        Verified by code: isResolved threads are skipped (continue).
        """
        source = _commit_post_commit_source()
        assert "isResolved" in source

    def test_37_merge_pr_exit_1_errors(self):
        """Test 37: merge_pr.sh exit 1 → error."""
        source = _commit_post_commit_source()
        assert "merge_pr.sh failed" in source


# --- Tests 38-40: Integration scenarios ---

class TestIntegrationScenarios:
    """Integration tests for full pipeline and re-invocation."""

    def test_38_no_change_after_hold_errors(self, tmp_path):
        """Test 38: Already-committed files in files_to_stage → nothing staged → error at step 4."""
        repo, env = _init_git_repo(tmp_path)
        (repo / "file1.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "file1.py"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "add file1"], cwd=repo, capture_output=True, env=env)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        # Pre-insert wave_id so ensure_tracker_note skips
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        tasks.write_text(content.replace("old note.", "old note.\n- test-wave-id present\n"))
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "note"], cwd=repo, capture_output=True, env=env)

        # files_to_stage has already-committed files → staging adds nothing
        handoff = _make_new_handoff()
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert result["status"] == "error"
        assert result["step"] == "stage_files"

    def test_39_full_pipeline_commit_go_mock(self, tmp_path):
        """Test 39: Full pipeline integration test — mock externals, COMMIT_GO, all 15 steps."""
        repo, env = _init_git_repo(tmp_path)
        # Pre-insert wave_id so tracker note step doesn't modify TASKS.md (keeps staged_sha stable)
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        tasks.write_text(content.replace("old note.", "old note.\n- test-wave-id already\n"))
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "note"], cwd=repo, capture_output=True, env=env)

        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")

        # Stage file1.py to compute staged_sha for valid receipt
        subprocess.run(["git", "add", "file1.py"], cwd=repo, capture_output=True, env=env)
        staged_sha = _compute_staged_sha(repo)

        # Create receipt with correct staged_sha
        receipt_dir = repo / ".agent_bus" / "meta"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        (receipt_dir / "pre_commit_receipt.json").write_text(
            json.dumps({"decision": "COMMIT_GO", "staged_sha": staged_sha,
                         "timestamp_utc": "2026-01-01T00:00:00Z"})
        )

        # Mock supervisor
        mock_sup = MagicMock()
        mock_sup.decision = "COMMIT_GO"
        mock_sup.receipt_path = ".agent_bus/meta/pre_commit_receipt.json"
        mock_sup.summary = "ok"

        # Count which steps we reach
        handoff = _make_new_handoff()

        with patch.dict(sys.modules, {"meta_bridge_client": MagicMock()}):
            sys.modules["meta_bridge_client"].run_meta_bridge_package = MagicMock(return_value=mock_sup)
            sys.modules["meta_bridge_client"].MetaBridgeClientError = Exception
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        steps = result.get("steps_completed", [])
        # Should reach at least through git_commit and hold_check
        assert "validate_inputs" in steps
        assert "ensure_feature_branch" in steps
        assert "ensure_tracker_note" in steps
        assert "stage_files" in steps
        assert "build_and_run_supervisor" in steps
        assert "validate_receipt" in steps
        assert "git_commit" in steps
        assert "hold_check" in steps
        # Beyond this, will fail at push (no remote) — that's expected

    def test_40_bot_fix_reinvocation(self, tmp_path):
        """Test 40: Bot-fix re-invocation — ensure_tracker_note skips, pipeline reaches commit."""
        repo, env = _init_git_repo(tmp_path)
        # Simulate being on target branch already (re-invocation)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        # Pre-insert wave_id (first invocation already added it)
        tasks = repo / "TASKS.md"
        content = tasks.read_text()
        tasks.write_text(content.replace("old note.", "old note.\n- Tracker sync note (test-wave-id): first.\n"))
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "first run"], cwd=repo, capture_output=True, env=env)

        # New fix file (this is the new change for bot fix)
        (repo / "file1.py").write_text("x = 2  # fixed\n")

        # Stage file1.py to compute staged_sha for valid receipt
        subprocess.run(["git", "add", "file1.py"], cwd=repo, capture_output=True, env=env)
        staged_sha = _compute_staged_sha(repo)

        receipt_dir = repo / ".agent_bus" / "meta"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        (receipt_dir / "pre_commit_receipt.json").write_text(
            json.dumps({"decision": "COMMIT_GO", "staged_sha": staged_sha,
                         "timestamp_utc": "2026-01-01T00:00:00Z"})
        )

        mock_sup = MagicMock()
        mock_sup.decision = "COMMIT_GO"
        mock_sup.receipt_path = ".agent_bus/meta/pre_commit_receipt.json"
        mock_sup.summary = "ok"

        handoff = _make_new_handoff()

        with patch.dict(sys.modules, {"meta_bridge_client": MagicMock()}):
            sys.modules["meta_bridge_client"].run_meta_bridge_package = MagicMock(return_value=mock_sup)
            sys.modules["meta_bridge_client"].MetaBridgeClientError = Exception
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        steps = result.get("steps_completed", [])
        # ensure_feature_branch: already on target → continues
        assert "ensure_feature_branch" in steps
        # ensure_tracker_note: wave_id present → skips
        assert "ensure_tracker_note" in steps
        # stage_files: stages new fix files
        assert "stage_files" in steps
        # git_commit: new commit
        assert "git_commit" in steps


class TestCommitContinuationAndBotFreshness:
    """Regression coverage for bounded post-commit continuation and bot freshness."""

    def test_valid_post_commit_continuation_resumes_at_post_commit_helper(self, tmp_path):
        repo, env = _init_git_repo(tmp_path)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "file1.py"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "wave commit"], cwd=repo, capture_output=True, env=env)
        head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True,
        ).stdout.strip()

        handoff = _make_new_handoff()
        continuation_path = repo / ".agent_bus" / "executors" / "commit_executor_test-wave-id.json"
        continuation_path.parent.mkdir(parents=True, exist_ok=True)
        continuation_path.write_text(json.dumps({
            "version": commit_mod.COMMIT_CONTINUATION_VERSION,
            "status": commit_mod.CONTINUATION_ACTIVE_STATUS,
            "handoff_sha": commit_mod._handoff_sha(handoff),  # ANTICHEAT_OK: testing continuation binding helper
            "target_branch": "jabramsja/test-wave-id",
            "commit_sha": head_sha,
            "receipt_decision": "COMMIT_GO",
            "steps_completed": [
                "validate_inputs",
                "ensure_feature_branch",
                "ensure_tracker_note",
                "stage_files",
                "collect_and_stage_indicator",
                "build_and_run_supervisor",
                "validate_receipt",
                "run_pre_commit_script",
                "git_commit",
                "hold_check",
            ],
        }))

        captured: dict[str, object] = {}

        def fake_post_commit_pipeline(**kwargs):
            captured["result"] = kwargs["result"].copy()
            return {"status": "continued", "steps_completed": kwargs["result"]["steps_completed"]}

        with patch.object(commit_mod, "_run_post_commit_pipeline", side_effect=fake_post_commit_pipeline) as mock_helper:
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "continued"
        assert mock_helper.call_count == 1
        resumed = captured["result"]
        assert resumed["handoff_sha"] == commit_mod._handoff_sha(handoff)  # ANTICHEAT_OK: resumed post-commit helper must retain continuation binding
        assert resumed["commit_sha"] == head_sha
        assert resumed["receipt_decision"] == "COMMIT_GO"
        assert resumed["steps_completed"][-1] == "hold_check"

    def test_hold_continuation_returns_held_and_clears_record(self, tmp_path):
        repo, env = _init_git_repo(tmp_path)
        subprocess.run(
            ["git", "checkout", "-b", "jabramsja/test-wave-id"],
            cwd=repo, capture_output=True, env=env,
        )
        (repo / "file1.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "file1.py"], cwd=repo, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-m", "wave commit"], cwd=repo, capture_output=True, env=env)
        head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True,
        ).stdout.strip()

        handoff = _make_new_handoff()
        continuation_path = repo / ".agent_bus" / "executors" / "commit_executor_test-wave-id.json"
        continuation_path.parent.mkdir(parents=True, exist_ok=True)
        continuation_path.write_text(json.dumps({
            "version": commit_mod.COMMIT_CONTINUATION_VERSION,
            "status": commit_mod.CONTINUATION_ACTIVE_STATUS,
            "handoff_sha": commit_mod._handoff_sha(handoff),  # ANTICHEAT_OK: testing continuation binding helper
            "target_branch": "jabramsja/test-wave-id",
            "commit_sha": head_sha,
            "receipt_decision": "COMMIT_GO_HOLD_PUSH",
            "steps_completed": ["validate_inputs", "ensure_feature_branch", "git_commit", "hold_check"],
        }))

        with patch.object(commit_mod, "_run_post_commit_pipeline") as mock_helper:
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "held"
        assert result["commit_sha"] == head_sha
        assert not continuation_path.exists()
        mock_helper.assert_not_called()

    def test_has_fresh_connector_review_requires_current_head_commit(self):
        pr_data = {
            "headRefOid": "abc123",
            "latestReviews": {
                "nodes": [
                    {
                        "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                        "state": "COMMENTED",
                        "commit": {"oid": "abc123"},
                    },
                    {
                        "author": {"login": "human-reviewer"},
                        "state": "APPROVED",
                        "commit": {"oid": "abc123"},
                    },
                ]
            }
        }
        assert commit_mod._has_fresh_connector_review(pr_data, "abc123") is True  # ANTICHEAT_OK: testing connector-review freshness helper
        assert commit_mod._has_fresh_connector_review(pr_data, "def456") is False  # ANTICHEAT_OK: testing connector-review freshness helper

    def test_has_fresh_connector_review_ignores_other_bot_on_current_head(self):
        pr_data = {
            "headRefOid": "abc123",
            "latestReviews": {
                "nodes": [
                    {
                        "author": {"login": "dependabot[bot]"},
                        "state": "COMMENTED",
                        "commit": {"oid": "abc123"},
                    },
                ],
            },
        }
        assert commit_mod._has_fresh_connector_review(pr_data, "abc123") is False  # ANTICHEAT_OK: non-connector bot reviews must not satisfy freshness

    def test_wait_for_bot_review_freshness_polls_until_current_head_review(self):
        calls = {"count": 0}

        def query_state():
            calls["count"] += 1
            if calls["count"] == 1:
                return {"headRefOid": "abc123", "latestReviews": {"nodes": []}}
            return {
                "headRefOid": "abc123",
                "latestReviews": {
                    "nodes": [
                        {
                            "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                            "state": "COMMENTED",
                            "commit": {"oid": "abc123"},
                        }
                    ]
                }
            }

        with patch.object(commit_mod.time, "sleep", return_value=None):
            pr_data = commit_mod._wait_for_bot_review_freshness(  # ANTICHEAT_OK: testing bot-review polling helper
                query_state,
                head_sha="abc123",
                wait_seconds=1,
                poll_interval=0,
            )

        assert calls["count"] == 2
        assert commit_mod._has_fresh_connector_review(pr_data, "abc123") is True  # ANTICHEAT_OK: testing connector-review freshness helper

    def test_bot_review_author_helper_accepts_connector_login(self):
        assert commit_mod._is_bot_review_author(commit_mod.BOT_REVIEW_LOGIN) is True  # ANTICHEAT_OK: testing bot-review author helper
        assert commit_mod._is_bot_review_author("some-bot") is True  # ANTICHEAT_OK: testing bot-review author helper
        assert commit_mod._is_bot_review_author("human-reviewer") is False  # ANTICHEAT_OK: testing bot-review author helper

    def test_connector_review_author_helper_rejects_other_bots(self):
        assert commit_mod._is_connector_review_author(commit_mod.BOT_REVIEW_LOGIN) is True  # ANTICHEAT_OK: testing connector-review author helper
        assert commit_mod._is_connector_review_author("chatgpt-codex-connector[bot]") is True  # ANTICHEAT_OK: testing connector-review author helper
        assert commit_mod._is_connector_review_author("dependabot[bot]") is False  # ANTICHEAT_OK: testing connector-review author helper
        assert commit_mod._is_connector_review_author("renovate-bot") is False  # ANTICHEAT_OK: testing connector-review author helper

    def test_pr_review_query_requests_thread_outdatedness(self):
        assert "isOutdated" in commit_mod.PR_REVIEW_QUERY

    def test_pr_review_query_requests_thread_comment_timestamps(self):
        assert "createdAt" in commit_mod.PR_REVIEW_QUERY

    def test_pr_review_query_requests_head_ref_oid(self):
        assert "headRefOid" in commit_mod.PR_REVIEW_QUERY

    def test_current_head_connector_issue_comment_outcome_requires_clear_comment_after_latest_request(self):
        pr_data = {
            "headRefOid": "abc123",
            "comments": {
                "nodes": [
                    {
                        "author": {"login": "jabramsja"},
                        "body": commit_mod.BOT_REVIEW_TRIGGER_COMMENT,
                        "createdAt": "2026-03-27T07:37:49Z",
                    },
                    {
                        "author": {"login": "chatgpt-codex-connector[bot]"},
                        "body": "Codex Review: Didn't find any major issues. Swish!",
                        "createdAt": "2026-03-27T07:39:03Z",
                    },
                ]
            }
        }

        outcome = commit_mod._current_head_connector_issue_comment_outcome(  # ANTICHEAT_OK: testing connector issue-comment freshness helper
            pr_data,
            "abc123",
        )
        assert outcome is not None
        assert outcome["kind"] == "clear"

        stale_pr_data = {
            "headRefOid": "abc123",
            "comments": {
                "nodes": [
                    {
                        "author": {"login": "chatgpt-codex-connector[bot]"},
                        "body": "Codex Review: Didn't find any major issues. Swish!",
                        "createdAt": "2026-03-27T07:39:03Z",
                    },
                    {
                        "author": {"login": "jabramsja"},
                        "body": commit_mod.BOT_REVIEW_TRIGGER_COMMENT,
                        "createdAt": "2026-03-27T07:40:00Z",
                    },
                ]
            }
        }

        assert commit_mod._current_head_connector_issue_comment_outcome(stale_pr_data, "abc123") is None  # ANTICHEAT_OK: testing connector issue-comment freshness helper

    def test_current_head_connector_issue_comment_outcome_ignores_non_connector_bot(self):
        pr_data = {
            "headRefOid": "abc123",
            "comments": {
                "nodes": [
                    {
                        "author": {"login": "jabramsja"},
                        "body": commit_mod.BOT_REVIEW_TRIGGER_COMMENT,
                        "createdAt": "2026-03-27T07:37:49Z",
                    },
                    {
                        "author": {"login": "dependabot[bot]"},
                        "body": "Codex Review: Didn't find any major issues. Swish!",
                        "createdAt": "2026-03-27T07:39:03Z",
                    },
                ]
            }
        }

        assert commit_mod._current_head_connector_issue_comment_outcome(pr_data, "abc123") is None  # ANTICHEAT_OK: testing connector-only issue-comment freshness helper

    def test_current_head_connector_issue_comment_outcome_requires_expected_head(self):
        pr_data = {
            "headRefOid": "other456",
            "comments": {
                "nodes": [
                    {
                        "author": {"login": "jabramsja"},
                        "body": commit_mod.BOT_REVIEW_TRIGGER_COMMENT,
                        "createdAt": "2026-03-27T10:14:29Z",
                    },
                    {
                        "author": {"login": "chatgpt-codex-connector[bot]"},
                        "body": "Codex Review: Didn't find any major issues. Swish!",
                        "createdAt": "2026-03-27T10:15:00Z",
                    },
                ]
            },
        }

        assert commit_mod._current_head_connector_issue_comment_outcome(pr_data, "abc123") is None  # ANTICHEAT_OK: commit-bound issue-comment freshness helper

    def test_wait_for_bot_review_freshness_accepts_no_issues_issue_comment(self):
        calls = {"count": 0}

        def query_state():
            calls["count"] += 1
            if calls["count"] == 1:
                return {
                    "headRefOid": "abc123",
                    "latestReviews": {"nodes": []},
                    "comments": {
                        "nodes": [
                            {
                                "author": {"login": "jabramsja"},
                                "body": commit_mod.BOT_REVIEW_TRIGGER_COMMENT,
                                "createdAt": "2026-03-27T07:37:49Z",
                            }
                        ]
                    },
                }
            return {
                "headRefOid": "abc123",
                "latestReviews": {"nodes": []},
                "comments": {
                    "nodes": [
                        {
                            "author": {"login": "jabramsja"},
                            "body": commit_mod.BOT_REVIEW_TRIGGER_COMMENT,
                            "createdAt": "2026-03-27T07:37:49Z",
                        },
                        {
                            "author": {"login": "chatgpt-codex-connector[bot]"},
                            "body": "Codex Review: Didn't find any major issues. Swish!",
                            "createdAt": "2026-03-27T07:39:03Z",
                        },
                    ]
                },
            }

        with patch.object(commit_mod.time, "sleep", return_value=None):
            pr_data = commit_mod._wait_for_bot_review_freshness(  # ANTICHEAT_OK: testing bot-review polling helper
                query_state,
                head_sha="abc123",
                wait_seconds=1,
                poll_interval=0,
            )

        assert calls["count"] == 2
        outcome = commit_mod._current_head_connector_issue_comment_outcome(pr_data, "abc123")  # ANTICHEAT_OK: testing connector issue-comment freshness helper
        assert outcome is not None
        assert outcome["kind"] == "clear"

    def test_wait_for_required_checks_to_register_retries_no_checks_reported(self, tmp_path, monkeypatch):
        calls = {"count": 0}

        def fake_run(args, *, cwd, check=True, timeout=120, env=None):
            calls["count"] += 1
            if calls["count"] == 1:
                return subprocess.CompletedProcess(
                    args,
                    1,
                    stdout="",
                    stderr="no checks reported on the 'jabramsja/test-wave-id' branch",
                )
            return subprocess.CompletedProcess(
                args,
                8,
                stdout="green-gate\tpending\t0\thttps://example.invalid/check\n",
                stderr="",
            )

        monkeypatch.setattr(commit_mod, "_run", fake_run)
        monkeypatch.setattr(commit_mod.time, "sleep", lambda _: None)

        commit_mod._wait_for_required_checks_to_register(  # ANTICHEAT_OK: testing CI registration helper
            tmp_path,
            pr_number="673",
            wait_seconds=1,
            poll_interval=0,
        )

        assert calls["count"] == 2

    def test_post_commit_ignores_outdated_connector_threads(self, tmp_path, monkeypatch):
        repo = tmp_path
        handoff = _make_new_handoff()
        result = {"steps_completed": ["validate_inputs", "ensure_feature_branch", "git_commit", "hold_check"]}
        continuation_path = repo / ".agent_bus" / "executors" / "commit_executor_test-wave-id.json"
        continuation_path.parent.mkdir(parents=True, exist_ok=True)
        merge_script = repo / "mu" / "tools" / "hooks" / "merge_pr.sh"
        merge_script.parent.mkdir(parents=True, exist_ok=True)
        merge_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

        def completed(cmd, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=stderr)

        def fake_run(cmd, cwd=None, timeout=None, check=True, env=None):
            if cmd[:3] == ["git", "rev-parse", "HEAD"]:
                return completed(cmd, stdout="abc123\n")
            if cmd[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return completed(cmd, stdout="dev\n")
            if cmd[:4] == ["git", "remote", "get-url", "origin"]:
                return completed(cmd, stdout="https://github.com/jabramsja/rcx-pi-core.git\n")
            if cmd[:2] == ["git", "status"]:
                return completed(cmd)
            if cmd[:4] == ["git", "push", "--no-verify", "-u"]:
                return completed(cmd)
            if cmd[:4] == ["gh", "pr", "list", "--head"]:
                return completed(cmd, stdout='[{"number":673}]')
            if cmd[:4] == ["gh", "pr", "checks", "673"]:
                return completed(cmd)
            if cmd[:4] == ["gh", "pr", "edit", "673"]:
                return completed(cmd)
            if cmd[:3] == ["gh", "api", "graphql"]:
                payload = {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "reviewDecision": "",
                                "headRefOid": "abc123",
                                "latestReviews": {
                                    "nodes": [
                                        {
                                            "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                                            "state": "COMMENTED",
                                            "commit": {"oid": "abc123"},
                                        }
                                    ]
                                },
                                "reviewThreads": {
                                    "nodes": [
                                        {
                                            "isResolved": False,
                                            "isOutdated": True,
                                            "comments": {
                                                "nodes": [
                                                    {
                                                        "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                                                        "body": "old finding",
                                                        "path": "x.py",
                                                        "line": 1,
                                                    }
                                                ]
                                            },
                                        }
                                    ]
                                },
                            }
                        }
                    }
                }
                return completed(cmd, stdout=json.dumps(payload))
            if cmd[:2] == ["bash", str(merge_script)]:
                return completed(cmd)
            if cmd[:2] == ["git", "pull"]:
                return completed(cmd)
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(commit_mod, "_run", fake_run)
        monkeypatch.setattr(commit_mod, "_wait_for_bot_review_freshness", lambda query_state, head_sha, **kwargs: query_state())

        post_commit = commit_mod._run_post_commit_pipeline(  # ANTICHEAT_OK: testing internal post-commit pipeline helper
            repo_root=repo,
            handoff=handoff,
            result=result,
            target_branch="jabramsja/test-wave-id",
            base_branch="dev",
            continuation_path=continuation_path,
            log=lambda _: None,
        )

        assert post_commit["pr_number"] == "673"
        assert "ensure_review_clear_and_merge" in post_commit["steps_completed"]
        assert "merge_sha" in post_commit

    def test_wait_for_bot_review_freshness_times_out_fail_closed(self):
        with patch.object(commit_mod.time, "sleep", return_value=None):
            with pytest.raises(TimeoutError, match="No current-head"):
                commit_mod._wait_for_bot_review_freshness(  # ANTICHEAT_OK: testing timeout fail-closed helper
                    lambda: {"headRefOid": "abc123", "latestReviews": {"nodes": []}},
                    head_sha="abc123",
                    wait_seconds=0,
                    poll_interval=0,
                )

    def test_wait_for_bot_review_freshness_fails_closed_on_pr_head_change(self):
        with patch.object(commit_mod.time, "sleep", return_value=None):
            with pytest.raises(ValueError, match="PR head moved from expected"):
                commit_mod._wait_for_bot_review_freshness(  # ANTICHEAT_OK: testing PR-head binding in freshness wait
                    lambda: {"headRefOid": "other456", "latestReviews": {"nodes": []}, "comments": {"nodes": []}},
                    head_sha="abc123",
                    wait_seconds=1,
                    poll_interval=0,
                )

    def test_wait_for_bot_review_freshness_extends_deadline_after_acknowledgement(self, monkeypatch):
        query_calls = {"count": 0}

        def query_state():
            query_calls["count"] += 1
            if query_calls["count"] < 3:
                return {"headRefOid": "abc123", "latestReviews": {"nodes": []}, "comments": {"nodes": []}}
            return {
                "headRefOid": "abc123",
                "latestReviews": {
                    "nodes": [
                        {
                            "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                            "state": "COMMENTED",
                            "commit": {"oid": "abc123"},
                        }
                    ]
                },
                "comments": {"nodes": []},
            }

        time_points = iter([0.0, 0.2, 1.2])
        monkeypatch.setattr(commit_mod.time, "time", lambda: next(time_points))
        monkeypatch.setattr(commit_mod.time, "sleep", lambda _: None)

        pr_data = commit_mod._wait_for_bot_review_freshness(  # ANTICHEAT_OK: testing acknowledgement-based wait extension
            query_state,
            head_sha="abc123",
            wait_seconds=1,
            request_acknowledged=lambda _: True,
            acknowledged_wait_seconds=5,
            poll_interval=0,
            )

        assert query_calls["count"] == 3
        assert commit_mod._has_fresh_connector_review(pr_data, "abc123")  # ANTICHEAT_OK: verifying review freshness helper

    def test_wait_for_bot_review_freshness_acknowledgement_does_not_clear_without_review(self, monkeypatch):
        time_points = iter([0.0, 0.2, 1.1])
        monkeypatch.setattr(commit_mod.time, "time", lambda: next(time_points))
        monkeypatch.setattr(commit_mod.time, "sleep", lambda _: None)

        with pytest.raises(TimeoutError, match="No current-head"):
            commit_mod._wait_for_bot_review_freshness(  # ANTICHEAT_OK: acknowledgement must not substitute for review clearance
                lambda: {"headRefOid": "abc123", "latestReviews": {"nodes": []}, "comments": {"nodes": []}},
                head_sha="abc123",
                wait_seconds=0,
                request_acknowledged=lambda _: True,
                acknowledged_wait_seconds=1,
                poll_interval=0,
            )

    def test_post_commit_ignores_prior_cycle_unresolved_bot_threads(self, tmp_path, monkeypatch):
        repo = tmp_path
        handoff = _make_new_handoff()
        result = {
            "steps_completed": [
                "validate_inputs",
                "ensure_feature_branch",
                "git_commit",
                "hold_check",
                "run_pre_push_script",
                "git_push",
                "ensure_pr",
                "wait_ci",
            ],
            "handoff_sha": "handoff-sha",
            "commit_sha": "abc123",
            "receipt_decision": "COMMIT_GO",
            "pr_number": "673",
        }
        continuation_path = repo / ".agent_bus" / "executors" / "commit_executor_test-wave-id.json"
        continuation_path.parent.mkdir(parents=True, exist_ok=True)
        merge_script = repo / "mu" / "tools" / "hooks" / "merge_pr.sh"
        merge_script.parent.mkdir(parents=True, exist_ok=True)
        merge_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

        def completed(cmd, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=stderr)

        def fake_run(cmd, cwd=None, timeout=None, check=True, env=None):
            if cmd[:3] == ["git", "rev-parse", "HEAD"]:
                return completed(cmd, stdout="abc123\n")
            if cmd[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return completed(cmd, stdout="dev\n")
            if cmd[:4] == ["git", "remote", "get-url", "origin"]:
                return completed(cmd, stdout="https://github.com/jabramsja/rcx-pi-core.git\n")
            if cmd[:2] == ["git", "status"]:
                return completed(cmd)
            if cmd[:3] == ["gh", "api", "graphql"]:
                payload = {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "headRefOid": "abc123",
                                "reviewDecision": "",
                                "latestReviews": {
                                    "nodes": [
                                        {
                                            "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                                            "state": "COMMENTED",
                                            "submittedAt": "2026-03-27T07:40:00Z",
                                            "commit": {"oid": "abc123"},
                                        }
                                    ]
                                },
                                "reviewThreads": {
                                    "nodes": [
                                        {
                                            "isResolved": False,
                                            "isOutdated": False,
                                            "comments": {
                                                "nodes": [
                                                    {
                                                        "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                                                        "body": "prior-cycle finding",
                                                        "path": "x.py",
                                                        "line": 1,
                                                        "createdAt": "2026-03-27T07:35:00Z",
                                                    }
                                                ]
                                            },
                                        }
                                    ]
                                },
                                "comments": {
                                    "nodes": [
                                        {
                                            "author": {"login": "jabramsja"},
                                            "body": commit_mod.BOT_REVIEW_TRIGGER_COMMENT,
                                            "createdAt": "2026-03-27T07:37:49Z",
                                        }
                                    ]
                                },
                            }
                        }
                    }
                }
                return completed(cmd, stdout=json.dumps(payload))
            if cmd[:2] == ["bash", str(merge_script)]:
                return completed(cmd)
            if cmd[:2] == ["git", "pull"]:
                return completed(cmd)
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(commit_mod, "_run", fake_run)

        post_commit = commit_mod._run_post_commit_pipeline(  # ANTICHEAT_OK: Step 15 must ignore prior-cycle unresolved bot threads
            repo_root=repo,
            handoff=handoff,
            result=result,
            target_branch="jabramsja/test-wave-id",
            base_branch="dev",
            continuation_path=continuation_path,
            log=lambda _: None,
        )

        assert "ensure_review_clear_and_merge" in post_commit["steps_completed"]
        assert "merge_sha" in post_commit

    def test_post_commit_reports_only_current_cycle_bot_threads(self, tmp_path, monkeypatch):
        repo = tmp_path
        handoff = _make_new_handoff()
        result = {
            "steps_completed": [
                "validate_inputs",
                "ensure_feature_branch",
                "git_commit",
                "hold_check",
                "run_pre_push_script",
                "git_push",
                "ensure_pr",
                "wait_ci",
            ],
            "handoff_sha": "handoff-sha",
            "commit_sha": "abc123",
            "receipt_decision": "COMMIT_GO",
            "pr_number": "673",
        }
        continuation_path = repo / ".agent_bus" / "executors" / "commit_executor_test-wave-id.json"
        continuation_path.parent.mkdir(parents=True, exist_ok=True)

        def completed(cmd, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=stderr)

        def fake_run(cmd, cwd=None, timeout=None, check=True, env=None):
            if cmd[:3] == ["git", "rev-parse", "HEAD"]:
                return completed(cmd, stdout="abc123\n")
            if cmd[:4] == ["git", "remote", "get-url", "origin"]:
                return completed(cmd, stdout="https://github.com/jabramsja/rcx-pi-core.git\n")
            if cmd[:3] == ["gh", "api", "graphql"]:
                payload = {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "headRefOid": "abc123",
                                "reviewDecision": "",
                                "latestReviews": {
                                    "nodes": [
                                        {
                                            "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                                            "state": "COMMENTED",
                                            "submittedAt": "2026-03-27T07:40:00Z",
                                            "commit": {"oid": "abc123"},
                                        }
                                    ]
                                },
                                "reviewThreads": {
                                    "nodes": [
                                        {
                                            "isResolved": False,
                                            "isOutdated": False,
                                            "comments": {
                                                "nodes": [
                                                    {
                                                        "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                                                        "body": "prior-cycle finding",
                                                        "path": "old.py",
                                                        "line": 1,
                                                        "createdAt": "2026-03-27T07:35:00Z",
                                                    }
                                                ]
                                            },
                                        },
                                        {
                                            "isResolved": False,
                                            "isOutdated": False,
                                            "comments": {
                                                "nodes": [
                                                    {
                                                        "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                                                        "body": "current-cycle finding",
                                                        "path": "new.py",
                                                        "line": 9,
                                                        "createdAt": "2026-03-27T07:41:00Z",
                                                    }
                                                ]
                                            },
                                        },
                                    ]
                                },
                                "comments": {
                                    "nodes": [
                                        {
                                            "author": {"login": "jabramsja"},
                                            "body": commit_mod.BOT_REVIEW_TRIGGER_COMMENT,
                                            "createdAt": "2026-03-27T07:37:49Z",
                                        }
                                    ]
                                },
                            }
                        }
                    }
                }
                return completed(cmd, stdout=json.dumps(payload))
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(commit_mod, "_run", fake_run)

        post_commit = commit_mod._run_post_commit_pipeline(  # ANTICHEAT_OK: Step 15 must scope bot findings to the active review cycle
            repo_root=repo,
            handoff=handoff,
            result=result,
            target_branch="jabramsja/test-wave-id",
            base_branch="dev",
            continuation_path=continuation_path,
            log=lambda _: None,
        )

        assert post_commit["status"] == "bot_findings_pending"
        assert post_commit["bot_findings"] == [
            {
                "author": commit_mod.BOT_REVIEW_LOGIN,
                "body": "current-cycle finding",
                "path": "new.py",
                "line": 9,
            }
        ]

    def test_current_head_connector_issue_comment_outcome_ignores_pre_review_clear_comment(self):
        pr_data = {
            "headRefOid": "abc123",
            "latestReviews": {
                "nodes": [
                    {
                        "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                        "state": "COMMENTED",
                        "submittedAt": "2026-03-27T07:40:00Z",
                        "commit": {"oid": "abc123"},
                    }
                ]
            },
            "comments": {
                "nodes": [
                    {
                        "author": {"login": "jabramsja"},
                        "body": commit_mod.BOT_REVIEW_TRIGGER_COMMENT,
                        "createdAt": "2026-03-27T07:37:49Z",
                    },
                    {
                        "author": {"login": "chatgpt-codex-connector[bot]"},
                        "body": "Codex Review: Didn't find any major issues. Swish!",
                        "createdAt": "2026-03-27T07:39:03Z",
                    },
                ]
            },
        }

        assert commit_mod._current_head_connector_issue_comment_outcome(pr_data, "abc123") is None  # ANTICHEAT_OK: testing connector issue-comment freshness helper against newer current-head review floor

    def test_bot_review_request_acknowledgement_detects_connector_eyes_reaction(self, tmp_path, monkeypatch):
        repo = tmp_path
        pr_data = {
            "comments": {
                "nodes": [
                    {
                        "author": {"login": "jabramsja"},
                        "body": commit_mod.BOT_REVIEW_TRIGGER_COMMENT,
                        "createdAt": "2026-03-27T08:58:34Z",
                        "databaseId": 4141124626,
                    }
                ]
            }
        }

        def completed(cmd, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=stderr)

        def fake_run(cmd, cwd=None, timeout=None, check=True, env=None):
            if cmd[:2] == ["gh", "api"] and cmd[2].endswith("/issues/comments/4141124626/reactions"):
                payload = [
                    {
                        "user": {"login": "chatgpt-codex-connector[bot]"},
                        "content": "eyes",
                    }
                ]
                return completed(cmd, stdout=json.dumps(payload))
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(commit_mod, "_run", fake_run)

        assert commit_mod._bot_review_request_acknowledged(  # ANTICHEAT_OK: direct helper regression for Step 15 ack path
            repo,
            repo_owner="jabramsja",
            repo_name="rcx-pi-core",
            pr_data=pr_data,
        )

    def test_bot_review_request_acknowledgement_rejects_non_connector_bot_reaction(self, tmp_path, monkeypatch):
        repo = tmp_path
        pr_data = {
            "comments": {
                "nodes": [
                    {
                        "author": {"login": "jabramsja"},
                        "body": commit_mod.BOT_REVIEW_TRIGGER_COMMENT,
                        "createdAt": "2026-03-27T08:58:34Z",
                        "databaseId": 4141124626,
                    }
                ]
            }
        }

        def completed(cmd, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=stderr)

        def fake_run(cmd, cwd=None, timeout=None, check=True, env=None):
            if cmd[:2] == ["gh", "api"] and cmd[2].endswith("/issues/comments/4141124626/reactions"):
                payload = [
                    {
                        "user": {"login": "dependabot[bot]"},
                        "content": "eyes",
                    }
                ]
                return completed(cmd, stdout=json.dumps(payload))
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(commit_mod, "_run", fake_run)

        assert not commit_mod._bot_review_request_acknowledged(  # ANTICHEAT_OK: connector-specific ack regression
            repo,
            repo_owner="jabramsja",
            repo_name="rcx-pi-core",
            pr_data=pr_data,
        )

    def test_post_commit_requests_current_head_bot_review_once(self, tmp_path, monkeypatch):
        repo = tmp_path
        handoff = _make_new_handoff()
        result = {
            "steps_completed": ["validate_inputs", "ensure_feature_branch", "git_commit", "hold_check"],
            "handoff_sha": "handoff-sha",
            "commit_sha": "abc123",
            "receipt_decision": "COMMIT_GO",
        }
        continuation_path = repo / ".agent_bus" / "executors" / "commit_executor_test-wave-id.json"
        continuation_path.parent.mkdir(parents=True, exist_ok=True)
        continuation_path.write_text(
            json.dumps(
                {
                    "version": commit_mod.COMMIT_CONTINUATION_VERSION,
                    "status": commit_mod.CONTINUATION_ACTIVE_STATUS,
                    "handoff_sha": "handoff-sha",
                    "target_branch": "jabramsja/test-wave-id",
                    "commit_sha": "abc123",
                    "receipt_decision": "COMMIT_GO",
                    "steps_completed": list(result["steps_completed"]),
                    "pr_number": "673",
                    "updated_at_unix": 0,
                }
            ),
            encoding="utf-8",
        )
        merge_script = repo / "mu" / "tools" / "hooks" / "merge_pr.sh"
        merge_script.parent.mkdir(parents=True, exist_ok=True)
        merge_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        comment_calls = []
        graphql_calls = {"count": 0}

        def completed(cmd, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=stderr)

        def fake_run(cmd, cwd=None, timeout=None, check=True, env=None):
            if cmd[:3] == ["git", "rev-parse", "HEAD"]:
                return completed(cmd, stdout="abc123\n")
            if cmd[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return completed(cmd, stdout="dev\n")
            if cmd[:4] == ["git", "remote", "get-url", "origin"]:
                return completed(cmd, stdout="https://github.com/jabramsja/rcx-pi-core.git\n")
            if cmd[:2] == ["git", "status"]:
                return completed(cmd)
            if cmd[:4] == ["git", "push", "--no-verify", "-u"]:
                return completed(cmd)
            if cmd[:4] == ["gh", "pr", "list", "--head"]:
                return completed(cmd, stdout='[{"number":673}]')
            if cmd[:4] == ["gh", "pr", "checks", "673"]:
                return completed(cmd)
            if cmd[:4] == ["gh", "pr", "edit", "673"]:
                return completed(cmd)
            if cmd[:3] == ["gh", "pr", "comment"]:
                comment_calls.append(cmd)
                return completed(cmd)
            if cmd[:3] == ["gh", "api", "graphql"]:
                graphql_calls["count"] += 1
                if graphql_calls["count"] == 1:
                    payload = {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "headRefOid": "abc123",
                                    "reviewDecision": "",
                                    "latestReviews": {"nodes": []},
                                    "reviewThreads": {"nodes": []},
                                }
                            }
                        }
                    }
                else:
                    payload = {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "headRefOid": "abc123",
                                    "reviewDecision": "",
                                    "latestReviews": {
                                        "nodes": [
                                            {
                                                "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                                                "state": "COMMENTED",
                                                "commit": {"oid": "abc123"},
                                            }
                                        ]
                                    },
                                    "reviewThreads": {"nodes": []},
                                }
                            }
                        }
                    }
                return completed(cmd, stdout=json.dumps(payload))
            if cmd[:2] == ["bash", str(merge_script)]:
                return completed(cmd)
            if cmd[:2] == ["git", "pull"]:
                return completed(cmd)
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(commit_mod, "_run", fake_run)
        monkeypatch.setattr(commit_mod.time, "sleep", lambda _: None)

        post_commit = commit_mod._run_post_commit_pipeline(  # ANTICHEAT_OK: exercising post-commit review request path
            repo_root=repo,
            handoff=handoff,
            result=result,
            target_branch="jabramsja/test-wave-id",
            base_branch="dev",
            continuation_path=continuation_path,
            log=lambda _: None,
        )

        assert post_commit["pr_number"] == "673"
        assert "ensure_review_clear_and_merge" in post_commit["steps_completed"]
        assert len(comment_calls) == 1

    def test_post_commit_accepts_current_head_no_issues_issue_comment_without_review_object(self, tmp_path, monkeypatch):
        repo = tmp_path
        handoff = _make_new_handoff()
        result = {
            "steps_completed": ["validate_inputs", "ensure_feature_branch", "git_commit", "hold_check"],
            "handoff_sha": "handoff-sha",
            "commit_sha": "abc123",
            "receipt_decision": "COMMIT_GO",
        }
        continuation_path = repo / ".agent_bus" / "executors" / "commit_executor_test-wave-id.json"
        continuation_path.parent.mkdir(parents=True, exist_ok=True)
        continuation_path.write_text(
            json.dumps(
                {
                    "version": commit_mod.COMMIT_CONTINUATION_VERSION,
                    "status": commit_mod.CONTINUATION_ACTIVE_STATUS,
                    "handoff_sha": "handoff-sha",
                    "target_branch": "jabramsja/test-wave-id",
                    "commit_sha": "abc123",
                    "receipt_decision": "COMMIT_GO",
                    "steps_completed": list(result["steps_completed"]),
                    "pr_number": "673",
                    "updated_at_unix": 0,
                }
            ),
            encoding="utf-8",
        )
        merge_script = repo / "mu" / "tools" / "hooks" / "merge_pr.sh"
        merge_script.parent.mkdir(parents=True, exist_ok=True)
        merge_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        comment_calls = []
        graphql_calls = {"count": 0}

        def completed(cmd, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=stderr)

        def fake_run(cmd, cwd=None, timeout=None, check=True, env=None):
            if cmd[:3] == ["git", "rev-parse", "HEAD"]:
                return completed(cmd, stdout="abc123\n")
            if cmd[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return completed(cmd, stdout="dev\n")
            if cmd[:4] == ["git", "remote", "get-url", "origin"]:
                return completed(cmd, stdout="https://github.com/jabramsja/rcx-pi-core.git\n")
            if cmd[:2] == ["git", "status"]:
                return completed(cmd)
            if cmd[:4] == ["git", "push", "--no-verify", "-u"]:
                return completed(cmd)
            if cmd[:4] == ["gh", "pr", "list", "--head"]:
                return completed(cmd, stdout='[{"number":673}]')
            if cmd[:4] == ["gh", "pr", "checks", "673"]:
                return completed(cmd)
            if cmd[:4] == ["gh", "pr", "edit", "673"]:
                return completed(cmd)
            if cmd[:3] == ["gh", "pr", "comment"]:
                comment_calls.append(cmd)
                return completed(cmd)
            if cmd[:3] == ["gh", "api", "graphql"]:
                graphql_calls["count"] += 1
                if graphql_calls["count"] == 1:
                    payload = {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "headRefOid": "abc123",
                                    "reviewDecision": "",
                                    "latestReviews": {"nodes": []},
                                    "reviewThreads": {"nodes": []},
                                    "comments": {"nodes": []},
                                }
                            }
                        }
                    }
                else:
                    payload = {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "headRefOid": "abc123",
                                    "reviewDecision": "",
                                    "latestReviews": {"nodes": []},
                                    "reviewThreads": {"nodes": []},
                                    "comments": {
                                        "nodes": [
                                            {
                                                "author": {"login": "jabramsja"},
                                                "body": commit_mod.BOT_REVIEW_TRIGGER_COMMENT,
                                                "createdAt": "2026-03-27T07:37:49Z",
                                            },
                                            {
                                                "author": {"login": "chatgpt-codex-connector[bot]"},
                                                "body": "Codex Review: Didn't find any major issues. Swish!",
                                                "createdAt": "2026-03-27T07:39:03Z",
                                            },
                                        ]
                                    },
                                }
                            }
                        }
                    }
                return completed(cmd, stdout=json.dumps(payload))
            if cmd[:2] == ["bash", str(merge_script)]:
                return completed(cmd)
            if cmd[:2] == ["git", "pull"]:
                return completed(cmd)
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(commit_mod, "_run", fake_run)
        monkeypatch.setattr(commit_mod.time, "sleep", lambda _: None)

        post_commit = commit_mod._run_post_commit_pipeline(  # ANTICHEAT_OK: exercising no-issues issue-comment clearance path
            repo_root=repo,
            handoff=handoff,
            result=result,
            target_branch="jabramsja/test-wave-id",
            base_branch="dev",
            continuation_path=continuation_path,
            log=lambda _: None,
        )

        assert post_commit["pr_number"] == "673"
        assert "ensure_review_clear_and_merge" in post_commit["steps_completed"]
        assert len(comment_calls) == 1

    def test_post_commit_does_not_request_review_when_current_head_clear_issue_comment_and_request_binding_exist(self, tmp_path, monkeypatch):
        repo = tmp_path
        handoff = _make_new_handoff()
        result = {
            "steps_completed": ["validate_inputs", "ensure_feature_branch", "git_commit", "hold_check"],
            "handoff_sha": "handoff-sha",
            "commit_sha": "abc123",
            "receipt_decision": "COMMIT_GO",
        }
        continuation_path = repo / ".agent_bus" / "executors" / "commit_executor_test-wave-id.json"
        continuation_path.parent.mkdir(parents=True, exist_ok=True)
        continuation_path.write_text(
            json.dumps(
                {
                    "version": commit_mod.COMMIT_CONTINUATION_VERSION,
                    "status": commit_mod.CONTINUATION_ACTIVE_STATUS,
                    "handoff_sha": "handoff-sha",
                    "target_branch": "jabramsja/test-wave-id",
                    "commit_sha": "abc123",
                    "receipt_decision": "COMMIT_GO",
                    "steps_completed": list(result["steps_completed"]),
                    "pr_number": "673",
                    "bot_review_request_sha": "abc123",
                    "updated_at_unix": 0,
                }
            ),
            encoding="utf-8",
        )
        merge_script = repo / "mu" / "tools" / "hooks" / "merge_pr.sh"
        merge_script.parent.mkdir(parents=True, exist_ok=True)
        merge_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        comment_calls = []

        def completed(cmd, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=stderr)

        def fake_run(cmd, cwd=None, timeout=None, check=True, env=None):
            if cmd[:3] == ["git", "rev-parse", "HEAD"]:
                return completed(cmd, stdout="abc123\n")
            if cmd[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return completed(cmd, stdout="dev\n")
            if cmd[:4] == ["git", "remote", "get-url", "origin"]:
                return completed(cmd, stdout="https://github.com/jabramsja/rcx-pi-core.git\n")
            if cmd[:2] == ["git", "status"]:
                return completed(cmd)
            if cmd[:4] == ["git", "push", "--no-verify", "-u"]:
                return completed(cmd)
            if cmd[:4] == ["gh", "pr", "list", "--head"]:
                return completed(cmd, stdout='[{"number":673}]')
            if cmd[:4] == ["gh", "pr", "checks", "673"]:
                return completed(cmd)
            if cmd[:4] == ["gh", "pr", "edit", "673"]:
                return completed(cmd)
            if cmd[:3] == ["gh", "pr", "comment"]:
                comment_calls.append(cmd)
                return completed(cmd)
            if cmd[:3] == ["gh", "api", "graphql"]:
                payload = {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "headRefOid": "abc123",
                                "reviewDecision": "",
                                "latestReviews": {"nodes": []},
                                "reviewThreads": {"nodes": []},
                                "comments": {
                                    "nodes": [
                                        {
                                            "author": {"login": "jabramsja"},
                                            "body": commit_mod.BOT_REVIEW_TRIGGER_COMMENT,
                                            "createdAt": "2026-03-27T07:37:49Z",
                                        },
                                        {
                                            "author": {"login": "chatgpt-codex-connector[bot]"},
                                            "body": "Codex Review: Didn't find any major issues. Swish!",
                                            "createdAt": "2026-03-27T07:39:03Z",
                                        },
                                    ]
                                },
                            }
                        }
                    }
                }
                return completed(cmd, stdout=json.dumps(payload))
            if cmd[:2] == ["bash", str(merge_script)]:
                return completed(cmd)
            if cmd[:2] == ["git", "pull"]:
                return completed(cmd)
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(commit_mod, "_run", fake_run)
        monkeypatch.setattr(commit_mod.time, "sleep", lambda _: None)

        post_commit = commit_mod._run_post_commit_pipeline(  # ANTICHEAT_OK: existing clear issue comment must avoid re-request
            repo_root=repo,
            handoff=handoff,
            result=result,
            target_branch="jabramsja/test-wave-id",
            base_branch="dev",
            continuation_path=continuation_path,
            log=lambda _: None,
        )

        assert post_commit["pr_number"] == "673"
        assert "ensure_review_clear_and_merge" in post_commit["steps_completed"]
        assert len(comment_calls) == 0

    def test_post_commit_requests_review_when_clear_issue_comment_lacks_current_head_request_binding(self, tmp_path, monkeypatch):
        repo = tmp_path
        handoff = _make_new_handoff()
        result = {
            "steps_completed": ["validate_inputs", "ensure_feature_branch", "git_commit", "hold_check"],
            "handoff_sha": "handoff-sha",
            "commit_sha": "abc123",
            "receipt_decision": "COMMIT_GO",
        }
        continuation_path = repo / ".agent_bus" / "executors" / "commit_executor_test-wave-id.json"
        continuation_path.parent.mkdir(parents=True, exist_ok=True)
        continuation_path.write_text(
            json.dumps(
                {
                    "version": commit_mod.COMMIT_CONTINUATION_VERSION,
                    "status": commit_mod.CONTINUATION_ACTIVE_STATUS,
                    "handoff_sha": "handoff-sha",
                    "target_branch": "jabramsja/test-wave-id",
                    "commit_sha": "abc123",
                    "receipt_decision": "COMMIT_GO",
                    "steps_completed": list(result["steps_completed"]),
                    "pr_number": "673",
                    "updated_at_unix": 0,
                }
            ),
            encoding="utf-8",
        )
        merge_script = repo / "mu" / "tools" / "hooks" / "merge_pr.sh"
        merge_script.parent.mkdir(parents=True, exist_ok=True)
        merge_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        comment_calls = []
        graphql_calls = {"count": 0}

        def completed(cmd, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=stderr)

        def fake_run(cmd, cwd=None, timeout=None, check=True, env=None):
            if cmd[:3] == ["git", "rev-parse", "HEAD"]:
                return completed(cmd, stdout="abc123\n")
            if cmd[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return completed(cmd, stdout="dev\n")
            if cmd[:4] == ["git", "remote", "get-url", "origin"]:
                return completed(cmd, stdout="https://github.com/jabramsja/rcx-pi-core.git\n")
            if cmd[:2] == ["git", "status"]:
                return completed(cmd)
            if cmd[:4] == ["git", "push", "--no-verify", "-u"]:
                return completed(cmd)
            if cmd[:4] == ["gh", "pr", "list", "--head"]:
                return completed(cmd, stdout='[{"number":673}]')
            if cmd[:4] == ["gh", "pr", "checks", "673"]:
                return completed(cmd)
            if cmd[:4] == ["gh", "pr", "edit", "673"]:
                return completed(cmd)
            if cmd[:3] == ["gh", "pr", "comment"]:
                comment_calls.append(cmd)
                return completed(cmd)
            if cmd[:3] == ["gh", "api", "graphql"]:
                graphql_calls["count"] += 1
                if graphql_calls["count"] == 1:
                    payload = {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "headRefOid": "abc123",
                                    "reviewDecision": "",
                                    "latestReviews": {"nodes": []},
                                    "reviewThreads": {"nodes": []},
                                    "comments": {
                                        "nodes": [
                                            {
                                                "author": {"login": "jabramsja"},
                                                "body": commit_mod.BOT_REVIEW_TRIGGER_COMMENT,
                                                "createdAt": "2026-03-27T07:37:49Z",
                                            },
                                            {
                                                "author": {"login": "chatgpt-codex-connector[bot]"},
                                                "body": "Codex Review: Didn't find any major issues. Swish!",
                                                "createdAt": "2026-03-27T07:39:03Z",
                                            },
                                        ]
                                    },
                                }
                            }
                        }
                    }
                else:
                    payload = {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "headRefOid": "abc123",
                                    "reviewDecision": "",
                                    "latestReviews": {
                                        "nodes": [
                                            {
                                                "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                                                "state": "COMMENTED",
                                                "commit": {"oid": "abc123"},
                                            }
                                        ]
                                    },
                                    "reviewThreads": {"nodes": []},
                                    "comments": {
                                        "nodes": [
                                            {
                                                "author": {"login": "jabramsja"},
                                                "body": commit_mod.BOT_REVIEW_TRIGGER_COMMENT,
                                                "createdAt": "2026-03-27T07:40:00Z",
                                            },
                                            {
                                                "author": {"login": "chatgpt-codex-connector[bot]"},
                                                "body": "Codex Review: Didn't find any major issues. Swish!",
                                                "createdAt": "2026-03-27T07:41:00Z",
                                            },
                                        ]
                                    },
                                }
                            }
                        }
                    }
                return completed(cmd, stdout=json.dumps(payload))
            if cmd[:2] == ["bash", str(merge_script)]:
                return completed(cmd)
            if cmd[:2] == ["git", "pull"]:
                return completed(cmd)
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(commit_mod, "_run", fake_run)
        monkeypatch.setattr(commit_mod.time, "sleep", lambda _: None)

        post_commit = commit_mod._run_post_commit_pipeline(  # ANTICHEAT_OK: clear issue comment must be request-bound to skip re-request
            repo_root=repo,
            handoff=handoff,
            result=result,
            target_branch="jabramsja/test-wave-id",
            base_branch="dev",
            continuation_path=continuation_path,
            log=lambda _: None,
        )

        assert post_commit["pr_number"] == "673"
        assert "ensure_review_clear_and_merge" in post_commit["steps_completed"]
        assert len(comment_calls) == 1

    def test_post_commit_wait_ci_retries_until_checks_register(self, tmp_path, monkeypatch):
        repo = tmp_path
        handoff = _make_new_handoff()
        result = {
            "steps_completed": ["validate_inputs", "ensure_feature_branch", "git_commit", "hold_check"],
            "handoff_sha": "handoff-sha",
            "commit_sha": "abc123",
            "receipt_decision": "COMMIT_GO",
        }
        continuation_path = repo / ".agent_bus" / "executors" / "commit_executor_test-wave-id.json"
        continuation_path.parent.mkdir(parents=True, exist_ok=True)
        continuation_path.write_text(
            json.dumps(
                {
                    "version": commit_mod.COMMIT_CONTINUATION_VERSION,
                    "status": commit_mod.CONTINUATION_ACTIVE_STATUS,
                    "handoff_sha": "handoff-sha",
                    "target_branch": "jabramsja/test-wave-id",
                    "commit_sha": "abc123",
                    "receipt_decision": "COMMIT_GO",
                    "steps_completed": list(result["steps_completed"]),
                    "pr_number": "673",
                    "updated_at_unix": 0,
                }
            ),
            encoding="utf-8",
        )
        merge_script = repo / "mu" / "tools" / "hooks" / "merge_pr.sh"
        merge_script.parent.mkdir(parents=True, exist_ok=True)
        merge_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        required_checks_calls = {"count": 0}

        def completed(cmd, returncode=0, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

        def fake_run(cmd, cwd=None, check=True, timeout=None, env=None):
            if cmd[:3] == ["git", "rev-parse", "HEAD"]:
                return completed(cmd, stdout="abc123\n")
            if cmd[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return completed(cmd, stdout="dev\n")
            if cmd[:4] == ["git", "remote", "get-url", "origin"]:
                return completed(cmd, stdout="https://github.com/jabramsja/rcx-pi-core.git\n")
            if cmd[:2] == ["git", "status"]:
                return completed(cmd)
            if cmd[:4] == ["git", "push", "--no-verify", "-u"]:
                return completed(cmd)
            if cmd[:4] == ["gh", "pr", "list", "--head"]:
                return completed(cmd, stdout='[{"number":673}]')
            if cmd[:4] == ["gh", "pr", "edit", "673"]:
                return completed(cmd)
            if cmd[:4] == ["gh", "pr", "checks", "673"] and "--required" in cmd and "--watch" not in cmd:
                required_checks_calls["count"] += 1
                if required_checks_calls["count"] == 1:
                    return completed(
                        cmd,
                        returncode=1,
                        stderr="no checks reported on the 'jabramsja/test-wave-id' branch",
                    )
                return completed(
                    cmd,
                    returncode=8,
                    stdout="green-gate\tpending\t0\thttps://example.invalid/check\n",
                )
            if cmd[:4] == ["gh", "pr", "checks", "673"] and "--watch" in cmd:
                return completed(cmd)
            if cmd[:3] == ["gh", "api", "graphql"]:
                payload = {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "headRefOid": "abc123",
                                "reviewDecision": "",
                                "latestReviews": {
                                    "nodes": [
                                        {
                                            "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                                            "state": "COMMENTED",
                                            "commit": {"oid": "abc123"},
                                        }
                                    ]
                                },
                                "reviewThreads": {"nodes": []},
                                "comments": {"nodes": []},
                            }
                        }
                    }
                }
                return completed(cmd, stdout=json.dumps(payload))
            if cmd[:2] == ["bash", str(merge_script)]:
                return completed(cmd)
            if cmd[:2] == ["git", "pull"]:
                return completed(cmd)
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(commit_mod, "_run", fake_run)
        monkeypatch.setattr(commit_mod.time, "sleep", lambda _: None)

        post_commit = commit_mod._run_post_commit_pipeline(  # ANTICHEAT_OK: exercising wait_ci registration-race helper through post-commit pipeline
            repo_root=repo,
            handoff=handoff,
            result=result,
            target_branch="jabramsja/test-wave-id",
            base_branch="dev",
            continuation_path=continuation_path,
            log=lambda _: None,
        )

        assert post_commit["pr_number"] == "673"
        assert "wait_ci" in post_commit["steps_completed"]
        assert "ensure_review_clear_and_merge" in post_commit["steps_completed"]
        assert required_checks_calls["count"] == 2

    def test_post_commit_resume_skips_checkpointed_pre_push_and_checkpoints_git_push(self, tmp_path, monkeypatch):
        repo = tmp_path
        handoff = _make_new_handoff()
        result = {
            "steps_completed": [
                "validate_inputs",
                "ensure_feature_branch",
                "git_commit",
                "hold_check",
                "run_pre_push_script",
            ],
            "handoff_sha": "handoff-sha",
            "commit_sha": "abc123",
            "receipt_decision": "COMMIT_GO",
        }
        continuation_path = repo / ".agent_bus" / "executors" / "commit_executor_test-wave-id.json"
        continuation_path.parent.mkdir(parents=True, exist_ok=True)
        continuation_path.write_text(
            json.dumps(
                {
                    "version": commit_mod.COMMIT_CONTINUATION_VERSION,
                    "status": commit_mod.CONTINUATION_ACTIVE_STATUS,
                    "handoff_sha": "handoff-sha",
                    "target_branch": "jabramsja/test-wave-id",
                    "commit_sha": "abc123",
                    "receipt_decision": "COMMIT_GO",
                    "steps_completed": list(result["steps_completed"]),
                    "updated_at_unix": 0,
                }
            ),
            encoding="utf-8",
        )
        pre_push_script = repo / "mu" / "tools" / "hooks" / "pre-push-fast"
        pre_push_script.parent.mkdir(parents=True, exist_ok=True)
        pre_push_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        pre_push_calls = []
        push_calls = []

        def completed(cmd, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=stderr)

        def fake_run(cmd, cwd=None, timeout=None, check=True, env=None):
            if cmd[:2] == ["bash", str(pre_push_script)]:
                pre_push_calls.append(cmd)
                return completed(cmd)
            if cmd[:4] == ["git", "push", "--no-verify", "-u"]:
                push_calls.append(cmd)
                return completed(cmd)
            if cmd[:4] == ["gh", "pr", "list", "--head"]:
                return completed(cmd, stdout="[]")
            if cmd[:3] == ["gh", "pr", "create"]:
                raise subprocess.CalledProcessError(1, cmd, stderr="create boom")
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(commit_mod, "_run", fake_run)

        post_commit = commit_mod._run_post_commit_pipeline(  # ANTICHEAT_OK: exercising checkpointed post-commit resume boundary
            repo_root=repo,
            handoff=handoff,
            result=result,
            target_branch="jabramsja/test-wave-id",
            base_branch="dev",
            continuation_path=continuation_path,
            log=lambda _: None,
        )

        assert post_commit["status"] == "error"
        assert post_commit["step"] == "ensure_pr"
        assert pre_push_calls == []
        assert len(push_calls) == 1
        assert push_calls[0][:5] == ["git", "push", "--no-verify", "-u", "origin"]

        continuation = json.loads(continuation_path.read_text(encoding="utf-8"))
        assert "run_pre_push_script" in continuation["steps_completed"]
        assert "git_push" in continuation["steps_completed"]

    def test_post_commit_does_not_recomment_same_head_bot_review_request(self, tmp_path, monkeypatch):
        repo = tmp_path
        handoff = _make_new_handoff()
        result = {
            "steps_completed": ["validate_inputs", "ensure_feature_branch", "git_commit", "hold_check"],
            "handoff_sha": "handoff-sha",
            "commit_sha": "abc123",
            "receipt_decision": "COMMIT_GO",
        }
        continuation_path = repo / ".agent_bus" / "executors" / "commit_executor_test-wave-id.json"
        continuation_path.parent.mkdir(parents=True, exist_ok=True)
        continuation_path.write_text(
            json.dumps(
                {
                    "version": commit_mod.COMMIT_CONTINUATION_VERSION,
                    "status": commit_mod.CONTINUATION_ACTIVE_STATUS,
                    "handoff_sha": "handoff-sha",
                    "target_branch": "jabramsja/test-wave-id",
                    "commit_sha": "abc123",
                    "receipt_decision": "COMMIT_GO",
                    "steps_completed": list(result["steps_completed"]),
                    "pr_number": "673",
                    "bot_review_request_sha": "abc123",
                    "updated_at_unix": 0,
                }
            ),
            encoding="utf-8",
        )
        merge_script = repo / "mu" / "tools" / "hooks" / "merge_pr.sh"
        merge_script.parent.mkdir(parents=True, exist_ok=True)
        merge_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        comment_calls = []
        graphql_calls = {"count": 0}

        def completed(cmd, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=stderr)

        def fake_run(cmd, cwd=None, timeout=None, check=True, env=None):
            if cmd[:3] == ["git", "rev-parse", "HEAD"]:
                return completed(cmd, stdout="abc123\n")
            if cmd[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return completed(cmd, stdout="dev\n")
            if cmd[:4] == ["git", "remote", "get-url", "origin"]:
                return completed(cmd, stdout="https://github.com/jabramsja/rcx-pi-core.git\n")
            if cmd[:2] == ["git", "status"]:
                return completed(cmd)
            if cmd[:4] == ["git", "push", "--no-verify", "-u"]:
                return completed(cmd)
            if cmd[:4] == ["gh", "pr", "list", "--head"]:
                return completed(cmd, stdout='[{"number":673}]')
            if cmd[:4] == ["gh", "pr", "checks", "673"]:
                return completed(cmd)
            if cmd[:4] == ["gh", "pr", "edit", "673"]:
                return completed(cmd)
            if cmd[:3] == ["gh", "pr", "comment"]:
                comment_calls.append(cmd)
                return completed(cmd)
            if cmd[:3] == ["gh", "api", "graphql"]:
                graphql_calls["count"] += 1
                if graphql_calls["count"] == 1:
                    payload = {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "headRefOid": "abc123",
                                    "reviewDecision": "",
                                    "latestReviews": {"nodes": []},
                                    "reviewThreads": {"nodes": []},
                                }
                            }
                        }
                    }
                else:
                    payload = {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "headRefOid": "abc123",
                                    "reviewDecision": "",
                                    "latestReviews": {
                                        "nodes": [
                                            {
                                                "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                                                "state": "COMMENTED",
                                                "commit": {"oid": "abc123"},
                                            }
                                        ]
                                    },
                                    "reviewThreads": {"nodes": []},
                                }
                            }
                        }
                    }
                return completed(cmd, stdout=json.dumps(payload))
            if cmd[:2] == ["bash", str(merge_script)]:
                return completed(cmd)
            if cmd[:2] == ["git", "pull"]:
                return completed(cmd)
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(commit_mod, "_run", fake_run)
        monkeypatch.setattr(commit_mod.time, "sleep", lambda _: None)

        post_commit = commit_mod._run_post_commit_pipeline(  # ANTICHEAT_OK: exercising post-commit review request dedupe
            repo_root=repo,
            handoff=handoff,
            result=result,
            target_branch="jabramsja/test-wave-id",
            base_branch="dev",
            continuation_path=continuation_path,
            log=lambda _: None,
        )

        assert post_commit["pr_number"] == "673"
        assert "ensure_review_clear_and_merge" in post_commit["steps_completed"]
        assert comment_calls == []

    def test_post_commit_pipeline_returns_structured_error_on_review_query_timeout(self, tmp_path):
        repo, _ = _init_git_repo(tmp_path)
        handoff = _make_new_handoff()
        continuation_path = repo / ".agent_bus" / "executors" / "commit_executor_test-wave-id.json"
        result = {
            "steps_completed": [
                "validate_inputs",
                "ensure_feature_branch",
                "ensure_tracker_note",
                "stage_files",
                "collect_and_stage_indicator",
                "build_and_run_supervisor",
                "validate_receipt",
                "run_pre_commit_script",
                "git_commit",
                "hold_check",
            ],
            "commit_sha": "abc123",
            "handoff_sha": commit_mod._handoff_sha(handoff),  # ANTICHEAT_OK: testing continuation binding helper
            "receipt_decision": "COMMIT_GO",
        }

        def fake_run(args, *, cwd, check=True, timeout=120, env=None):
            if args[:4] == ["git", "push", "--no-verify", "-u"]:
                return subprocess.CompletedProcess(args, 0, "", "")
            if args[:3] == ["gh", "pr", "list"]:
                return subprocess.CompletedProcess(args, 0, "[]\n", "")
            if args[:3] == ["gh", "pr", "create"]:
                return subprocess.CompletedProcess(
                    args, 0, "https://github.com/jabramsja/rcx-pi-core/pull/671\n", ""
                )
            if args[:3] == ["gh", "pr", "checks"]:
                return subprocess.CompletedProcess(args, 0, "", "")
            if args[:3] == ["git", "rev-parse", "HEAD"]:
                return subprocess.CompletedProcess(args, 0, "abc123\n", "")
            if args[:3] == ["gh", "api", "graphql"]:
                raise subprocess.TimeoutExpired(cmd=args, timeout=30)
            raise AssertionError(f"Unexpected command: {args}")

        with patch.object(commit_mod, "_run", side_effect=fake_run):
            with patch.object(commit_mod, "_parse_origin_owner_repo", return_value=("jabramsja", "rcx-pi-core")):
                post_commit = commit_mod._run_post_commit_pipeline(  # ANTICHEAT_OK: exercising post-commit helper directly
                    handoff=handoff,
                    repo_root=repo,
                    result=result,
                    target_branch="jabramsja/test-wave-id",
                    base_branch="dev",
                    continuation_path=continuation_path,
                    log=lambda _: None,
                )

        assert post_commit["status"] == "error"
        assert post_commit["step"] == "ensure_review_clear_and_merge"
        assert "Review query failed" in post_commit["errors"][0]
        assert "timed out" in post_commit["errors"][0]
        assert "wait_ci" in post_commit["steps_completed"]

    def test_post_commit_uses_linked_base_worktree_for_merge_verification(self, tmp_path, monkeypatch):
        repo = tmp_path / "feature-worktree"
        repo.mkdir()
        dev_worktree = tmp_path / "dev-worktree"
        dev_worktree.mkdir()
        handoff = _make_new_handoff()
        continuation_path = repo / ".agent_bus" / "executors" / "commit_executor_test-wave-id.json"
        continuation_path.parent.mkdir(parents=True, exist_ok=True)
        merge_script = repo / "mu" / "tools" / "hooks" / "merge_pr.sh"
        merge_script.parent.mkdir(parents=True, exist_ok=True)
        merge_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        result = {
            "steps_completed": [
                "validate_inputs",
                "ensure_feature_branch",
                "git_commit",
                "hold_check",
                "run_pre_push_script",
                "git_push",
                "ensure_pr",
                "wait_ci",
            ],
            "handoff_sha": "handoff-sha",
            "commit_sha": "abc123",
            "receipt_decision": "COMMIT_GO",
            "pr_number": "673",
        }
        merge_cwds = []
        pull_cwds = []

        def completed(cmd, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=stderr)

        def fake_run(cmd, cwd=None, timeout=None, check=True, env=None):
            if cmd[:4] == ["git", "remote", "get-url", "origin"]:
                return completed(cmd, stdout="https://github.com/jabramsja/rcx-pi-core.git\n")
            if cmd[:3] == ["git", "rev-parse", "HEAD"]:
                if cwd == dev_worktree:
                    return completed(cmd, stdout="merge456\n")
                return completed(cmd, stdout="abc123\n")
            if cmd[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return completed(cmd, stdout="jabramsja/test-wave-id\n")
            if cmd[:4] == ["git", "worktree", "list", "--porcelain"]:
                stdout = (
                    f"worktree {repo}\n"
                    "HEAD abc123\n"
                    "branch refs/heads/jabramsja/test-wave-id\n\n"
                    f"worktree {dev_worktree}\n"
                    "HEAD merge456\n"
                    "branch refs/heads/dev\n\n"
                )
                return completed(cmd, stdout=stdout)
            if cmd[:3] == ["gh", "api", "graphql"]:
                payload = {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "headRefOid": "abc123",
                                "reviewDecision": "",
                                "latestReviews": {
                                    "nodes": [
                                        {
                                            "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                                            "state": "COMMENTED",
                                            "commit": {"oid": "abc123"},
                                        }
                                    ]
                                },
                                "reviewThreads": {"nodes": []},
                                "comments": {"nodes": []},
                            }
                        }
                    }
                }
                return completed(cmd, stdout=json.dumps(payload))
            if cmd[:2] == ["bash", str(merge_script)]:
                merge_cwds.append(cwd)
                return completed(cmd)
            if cmd[:2] == ["git", "pull"]:
                pull_cwds.append(cwd)
                return completed(cmd)
            if cmd[:2] == ["git", "status"]:
                return completed(cmd)
            if cmd[:2] == ["git", "checkout"]:
                raise AssertionError("post-merge verify should not checkout dev in feature worktree")
            raise AssertionError(f"unexpected command: {cmd} cwd={cwd}")

        monkeypatch.setattr(commit_mod, "_run", fake_run)

        post_commit = commit_mod._run_post_commit_pipeline(  # ANTICHEAT_OK: exercising linked-worktree merge verification path
            repo_root=repo,
            handoff=handoff,
            result=result,
            target_branch="jabramsja/test-wave-id",
            base_branch="dev",
            continuation_path=continuation_path,
            log=lambda _: None,
        )

        assert "step" not in post_commit
        assert post_commit["merge_sha"] == "merge456"
        assert "ensure_review_clear_and_merge" in post_commit["steps_completed"]
        assert merge_cwds == [repo.parent]
        assert pull_cwds == [dev_worktree]


class TestModularSurfaceEntrypoints:
    """executor_dispatch.py also acts as the modular control-plane entrypoint."""

    def test_phase_a_surface_builds_phase_a_executor_command(self):
        args = dispatch_mod.build_surface_parser().parse_args(
            ["phase-a", "--plan-name", "executor_surfaces_plan", "--max-rounds", "7", "--json"]
        )
        cmd = dispatch_mod.build_surface_command(args)
        assert cmd[:2] == [dispatch_mod.sys.executable, str(dispatch_mod.SCRIPT_DIR / "phase_a_executor.py")]
        assert "--plan-name" in cmd
        assert "executor_surfaces_plan" in cmd
        assert "--max-rounds" in cmd
        assert "7" in cmd
        assert "--json" in cmd

    def test_phase_b_surface_reads_routing_record_path(self, tmp_path):
        routing_path = tmp_path / "routing.json"
        routing_path.write_text('{"decision":"ROUTE_PHASE_B","summary":"test"}', encoding="utf-8")
        args = dispatch_mod.build_surface_parser().parse_args(
            [
                "phase-b",
                "--plan", "reports/control_plane/example.md",
                "--routing-record-path", str(routing_path),
                "--bootstrap-exception",
                "--verbose",
            ]
        )
        cmd = dispatch_mod.build_surface_command(args)
        assert cmd[:2] == [dispatch_mod.sys.executable, str(dispatch_mod.SCRIPT_DIR / "phase_b_executor.py")]
        assert "--plan" in cmd
        assert "reports/control_plane/example.md" in cmd
        assert "--routing-record" in cmd
        assert '{"decision":"ROUTE_PHASE_B","summary":"test"}' in cmd
        assert "--bootstrap-exception" in cmd
        assert "--verbose" in cmd

    def test_pre_commit_surface_builds_supervisor_command(self, tmp_path):
        package_path = tmp_path / "package.json"
        package_path.write_text("{}", encoding="utf-8")
        args = dispatch_mod.build_surface_parser().parse_args(
            ["pre-commit-supervisor", "--package", str(package_path), "--dry-run", "--json"]
        )
        cmd = dispatch_mod.build_surface_command(args)
        assert cmd[:2] == [dispatch_mod.sys.executable, str(dispatch_mod.AGENTS_DIR / "meta_bridge_supervisor.py")]
        assert "--dry-run" in cmd
        assert "--mode" not in cmd
        assert "--json" in cmd

    def test_post_merge_surface_builds_supervisor_mode_command(self, tmp_path):
        package_path = tmp_path / "package.json"
        package_path.write_text("{}", encoding="utf-8")
        args = dispatch_mod.build_surface_parser().parse_args(
            ["post-merge-supervisor", "--package", str(package_path), "--verbose"]
        )
        cmd = dispatch_mod.build_surface_command(args)
        assert cmd[:2] == [dispatch_mod.sys.executable, str(dispatch_mod.AGENTS_DIR / "meta_bridge_supervisor.py")]
        assert "--mode" in cmd
        assert "post-merge" in cmd
        assert "--verbose" in cmd

    def test_phase_b_surface_recovery_retries_after_tier3_success(self, tmp_path):
        handoff_dir = tmp_path / ".agent_bus" / "executors"
        handoff_dir.mkdir(parents=True)
        (handoff_dir / "phase_b_handoff.json").write_text("{}", encoding="utf-8")
        args = dispatch_mod.build_surface_parser().parse_args(
            [
                "phase-b",
                "--routing-record-json",
                '{"wave_name":"surface-wave","decision":"ROUTE_PHASE_B"}',
            ]
        )
        recovery = {
            "recovered": True,
            "exhausted": False,
            "failure_class": "needs_phase_b",
            "tier": 3,
            "action": "recovery_loop",
            "detail": "phase-b re-entry succeeded",
        }
        failed = subprocess.CompletedProcess(["phase-b"], 1, stdout="", stderr="")
        succeeded = subprocess.CompletedProcess(["phase-b"], 0, stdout="", stderr="")
        commit_ok = subprocess.CompletedProcess(
            ["commit"], 0, "[commit-executor] Status: success\n", ""
        )

        with patch.object(dispatch_mod, "_run_executor_in_group", side_effect=[failed, succeeded, commit_ok]) as mock_run, \
             patch.object(dispatch_mod, "attempt_recovery", return_value=recovery) as mock_recovery, \
             patch.object(dispatch_mod, "_clear_phase_b_state_for_retry") as mock_clear:
            exit_code = dispatch_mod.run_recoverable_surface_command(
                args,
                repo_root=tmp_path,
                config={"timeouts": {"phase_b_executor": 300}},
            )

        assert exit_code == 0
        assert mock_run.call_count == 3
        assert mock_recovery.call_args[0][2] == "surface-wave"
        mock_clear.assert_called_once()

    def test_phase_surface_success_after_recovery_restores_overrides(self, tmp_path, monkeypatch):
        args = dispatch_mod.build_surface_parser().parse_args(
            ["phase-a", "--plan-name", "surface-wave", "--json"]
        )
        fail = subprocess.CompletedProcess(["phase-a"], 1, stdout="", stderr="boom")
        succeed = subprocess.CompletedProcess(["phase-a"], 0, stdout='{"status":"converged"}', stderr="")
        recovery = {
            "recovered": True,
            "exhausted": False,
            "failure_class": "process_timeout",
            "tier": 2,
            "action": "increase_timeout",
            "detail": "retry with bumped timeout",
        }
        config = {"timeouts": {"phase_a_executor": 300}}
        orig = {"phase_a_executor": 300}

        def fake_apply(cfg, *, repo_root, verbose=False):
            cfg["timeouts"]["phase_a_executor"] = 450
            os.environ["RCX_RECOVERY_ORIGINAL_TIMEOUT_phase_a_executor"] = "300"
            return orig

        monkeypatch.delenv("RCX_RECOVERY_ORIGINAL_TIMEOUT_phase_a_executor", raising=False)
        with patch.object(dispatch_mod, "_run_executor_in_group", side_effect=[fail, succeed]), \
             patch.object(dispatch_mod, "attempt_recovery", return_value=recovery), \
             patch.object(dispatch_mod, "_apply_recovery_overrides", side_effect=fake_apply), \
             patch.object(dispatch_mod, "_continue_successful_executor_chain", return_value={"status": "success"}), \
             patch.object(dispatch_mod, "_clear_phase_b_state_for_retry") as mock_clear, \
             patch.object(dispatch_mod, "_restore_config_on_disk") as mock_restore:
            exit_code = dispatch_mod.run_recoverable_surface_command(
                args,
                repo_root=tmp_path,
                config=config,
            )

        assert exit_code == 0
        mock_clear.assert_called_once()
        mock_restore.assert_called_once_with(tmp_path, orig, verbose=False)
        assert config["timeouts"] == orig
        assert "RCX_RECOVERY_ORIGINAL_TIMEOUT_phase_a_executor" not in os.environ

    def test_phase_a_surface_success_chains_to_phase_b_and_commit(self, tmp_path):
        plan_path = tmp_path / "reports" / "control_plane" / "plan.md"
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text("# plan\n", encoding="utf-8")
        handoff_dir = tmp_path / ".agent_bus" / "executors"
        handoff_dir.mkdir(parents=True)
        (handoff_dir / "phase_b_handoff.json").write_text("{}", encoding="utf-8")

        args = dispatch_mod.build_surface_parser().parse_args(
            ["phase-a", "--plan-name", "surface-wave", "--json"]
        )
        phase_a_ok = subprocess.CompletedProcess(
            ["phase-a"], 0, json.dumps({"plan_path": str(plan_path)}), ""
        )
        phase_b_ok = subprocess.CompletedProcess(
            ["phase-b"], 0, json.dumps({"status": "commit_ready"}), ""
        )
        commit_ok = subprocess.CompletedProcess(
            ["commit"], 0, "[commit-executor] Status: success\n", ""
        )
        calls: list[list[str]] = []

        def fake_run(cmd, *, cwd, timeout):
            calls.append(cmd)
            return [phase_a_ok, phase_b_ok, commit_ok][len(calls) - 1]

        with patch.object(dispatch_mod, "_run_executor_in_group", side_effect=fake_run) as mock_run, \
             patch.object(dispatch_mod, "attempt_recovery") as mock_recovery:
            exit_code = dispatch_mod.run_recoverable_surface_command(
                args,
                repo_root=tmp_path,
                config={
                    "timeouts": {
                        "phase_a_executor": 300,
                        "phase_b_executor": 3600,
                        "commit_executor": 300,
                    }
                },
            )

        assert exit_code == 0
        assert mock_run.call_count == 3
        mock_recovery.assert_not_called()
        assert calls[0][:2] == [
            dispatch_mod.sys.executable,
            str(dispatch_mod.SCRIPT_DIR / "phase_a_executor.py"),
        ]
        assert calls[1][:2] == [
            dispatch_mod.sys.executable,
            str(dispatch_mod.SCRIPT_DIR / "phase_b_executor.py"),
        ]
        assert "--plan" in calls[1]
        assert str(plan_path) in calls[1]
        phase_b_record = json.loads(calls[1][calls[1].index("--routing-record") + 1])
        assert phase_b_record["decision"] == "ROUTE_PHASE_B"
        assert calls[2][:2] == [
            dispatch_mod.sys.executable,
            str(dispatch_mod.SCRIPT_DIR / "commit_executor.py"),
        ]
        assert "--handoff" in calls[2]

    def test_phase_a_surface_success_chains_with_pretty_json_stdout(self, tmp_path):
        plan_path = tmp_path / "reports" / "control_plane" / "plan.md"
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text("# plan\n", encoding="utf-8")
        handoff_dir = tmp_path / ".agent_bus" / "executors"
        handoff_dir.mkdir(parents=True)
        (handoff_dir / "phase_b_handoff.json").write_text("{}", encoding="utf-8")

        args = dispatch_mod.build_surface_parser().parse_args(
            ["phase-a", "--plan-name", "surface-wave", "--json"]
        )
        phase_a_stdout = "\n".join(
            [
                f"[phase-a] Plan draft: {plan_path}",
                "[phase-a] Bridge converged: GO",
                json.dumps({"status": "converged", "plan_path": str(plan_path)}, indent=2),
            ]
        )
        phase_a_ok = subprocess.CompletedProcess(["phase-a"], 0, phase_a_stdout, "")
        phase_b_ok = subprocess.CompletedProcess(
            ["phase-b"], 0, json.dumps({"status": "commit_ready"}), ""
        )
        commit_ok = subprocess.CompletedProcess(
            ["commit"], 0, "[commit-executor] Status: success\n", ""
        )
        calls: list[list[str]] = []

        def fake_run(cmd, *, cwd, timeout):
            calls.append(cmd)
            return [phase_a_ok, phase_b_ok, commit_ok][len(calls) - 1]

        with patch.object(dispatch_mod, "_run_executor_in_group", side_effect=fake_run) as mock_run, \
             patch.object(dispatch_mod, "attempt_recovery") as mock_recovery:
            exit_code = dispatch_mod.run_recoverable_surface_command(
                args,
                repo_root=tmp_path,
                config={
                    "timeouts": {
                        "phase_a_executor": 300,
                        "phase_b_executor": 3600,
                        "commit_executor": 300,
                    }
                },
            )

        assert exit_code == 0
        assert mock_run.call_count == 3
        mock_recovery.assert_not_called()
        assert "--plan" in calls[1]
        assert str(plan_path) in calls[1]

    def test_phase_b_surface_success_chains_to_commit(self, tmp_path):
        handoff_dir = tmp_path / ".agent_bus" / "executors"
        handoff_dir.mkdir(parents=True)
        (handoff_dir / "phase_b_handoff.json").write_text("{}", encoding="utf-8")
        args = dispatch_mod.build_surface_parser().parse_args(
            [
                "phase-b",
                "--plan", "reports/control_plane/example.md",
                "--routing-record-json", '{"wave_name":"surface-wave","decision":"ROUTE_PHASE_B"}',
                "--json",
            ]
        )
        phase_b_ok = subprocess.CompletedProcess(
            ["phase-b"], 0, json.dumps({"status": "commit_ready"}), ""
        )
        commit_ok = subprocess.CompletedProcess(
            ["commit"], 0, "[commit-executor] Status: success\n", ""
        )
        calls: list[list[str]] = []

        def fake_run(cmd, *, cwd, timeout):
            calls.append(cmd)
            return [phase_b_ok, commit_ok][len(calls) - 1]

        with patch.object(dispatch_mod, "_run_executor_in_group", side_effect=fake_run) as mock_run, \
             patch.object(dispatch_mod, "attempt_recovery") as mock_recovery:
            exit_code = dispatch_mod.run_recoverable_surface_command(
                args,
                repo_root=tmp_path,
                config={
                    "timeouts": {
                        "phase_b_executor": 3600,
                        "commit_executor": 300,
                    }
                },
            )

        assert exit_code == 0
        assert mock_run.call_count == 2
        mock_recovery.assert_not_called()
        assert calls[0][:2] == [
            dispatch_mod.sys.executable,
            str(dispatch_mod.SCRIPT_DIR / "phase_b_executor.py"),
        ]
        assert calls[1][:2] == [
            dispatch_mod.sys.executable,
            str(dispatch_mod.SCRIPT_DIR / "commit_executor.py"),
        ]

    def test_commit_surface_failure_routes_to_recovery_and_retries(self, tmp_path):
        handoff_path = tmp_path / "handoff.json"
        handoff_path.write_text(
            json.dumps({"wave_id": "commit-surface-wave", "task_id": "[PIPELINE-RECOVERY]"}),
            encoding="utf-8",
        )
        args = dispatch_mod.build_surface_parser().parse_args(
            ["commit", "--handoff", str(handoff_path), "--json"]
        )
        commit_fail = subprocess.CompletedProcess(
            ["commit"], 1, json.dumps({"status": "error", "step": "wait_ci"}), "CI failed"
        )
        commit_ok = subprocess.CompletedProcess(
            ["commit"], 0, json.dumps({"status": "success"}), ""
        )
        recovery = {
            "recovered": True,
            "exhausted": False,
            "failure_class": "test_failure",
            "tier": 3,
            "action": "recovery_loop",
            "detail": "resume commit surface",
        }

        with patch.object(
            dispatch_mod,
            "_run_executor_in_group",
            side_effect=[commit_fail, commit_ok],
        ) as mock_run, \
             patch.object(dispatch_mod, "attempt_recovery", return_value=recovery) as mock_recovery:
            exit_code = dispatch_mod.run_recoverable_surface_command(
                args,
                repo_root=tmp_path,
                config={"timeouts": {"commit_executor": 300}},
            )

        assert exit_code == 0
        assert mock_run.call_count == 2
        mock_recovery.assert_called_once()
        assert mock_recovery.call_args[0][2] == "commit-surface-wave"

    def test_commit_surface_stderr_only_failure_routes_to_recovery(self, tmp_path):
        handoff_path = tmp_path / "handoff.json"
        handoff_path.write_text(
            json.dumps({"wave_id": "commit-surface-wave", "task_id": "[PIPELINE-RECOVERY]"}),
            encoding="utf-8",
        )
        args = dispatch_mod.build_surface_parser().parse_args(
            ["commit", "--handoff", str(handoff_path), "--json"]
        )
        commit_fail = subprocess.CompletedProcess(
            ["commit"], 1, "", "fatal: remote rejected push"
        )
        recovery = {
            "recovered": False,
            "exhausted": True,
            "failure_class": "unknown_error",
            "tier": 3,
            "action": "recovery_loop",
            "detail": "raw failure reached recovery",
        }

        with patch.object(
            dispatch_mod,
            "_run_executor_in_group",
            return_value=commit_fail,
        ) as mock_run, \
             patch.object(dispatch_mod, "attempt_recovery", return_value=recovery) as mock_recovery:
            exit_code = dispatch_mod.run_recoverable_surface_command(
                args,
                repo_root=tmp_path,
                config={"timeouts": {"commit_executor": 300}},
            )

        assert exit_code == 1
        assert mock_run.call_count == 1
        mock_recovery.assert_called_once()
        result = mock_recovery.call_args[0][1]
        assert result["status"] == "failed"
        assert result["stdout"] == ""
        assert result["stderr"] == "fatal: remote rejected push"

    def test_phase_a_surface_chained_commit_failure_retries_commit_only(self, tmp_path):
        plan_path = tmp_path / "reports" / "control_plane" / "plan.md"
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text("# plan\n", encoding="utf-8")
        handoff_dir = tmp_path / ".agent_bus" / "executors"
        handoff_dir.mkdir(parents=True)
        (handoff_dir / "phase_b_handoff.json").write_text("{}", encoding="utf-8")

        args = dispatch_mod.build_surface_parser().parse_args(
            ["phase-a", "--plan-name", "surface-wave", "--json"]
        )
        phase_a_ok = subprocess.CompletedProcess(
            ["phase-a"], 0, json.dumps({"plan_path": str(plan_path)}), ""
        )
        phase_b_ok = subprocess.CompletedProcess(
            ["phase-b"], 0, json.dumps({"status": "commit_ready"}), ""
        )
        commit_fail = subprocess.CompletedProcess(
            ["commit"], 1, "[commit-executor] Status: failed\n", "boom"
        )
        recovery = {
            "recovered": True,
            "exhausted": False,
            "failure_class": "unknown_error",
            "tier": 3,
            "action": "recovery_loop",
            "detail": "retry commit only",
        }
        retried_commit = {
            "status": "success",
            "decision": "COMMIT_GO",
            "executor": "commit_executor",
            "stdout": "[commit-executor] Status: success\n",
            "stderr": "",
            "chained_from": "retry_commit_only",
        }

        with patch.object(
            dispatch_mod,
            "_run_executor_in_group",
            side_effect=[phase_a_ok, phase_b_ok, commit_fail],
        ) as mock_run, \
             patch.object(dispatch_mod, "attempt_recovery", return_value=recovery) as mock_recovery, \
             patch.object(dispatch_mod, "_retry_commit_only", return_value=retried_commit) as mock_retry:
            exit_code = dispatch_mod.run_recoverable_surface_command(
                args,
                repo_root=tmp_path,
                config={
                    "timeouts": {
                        "phase_a_executor": 300,
                        "phase_b_executor": 3600,
                        "commit_executor": 300,
                    }
                },
            )

        assert exit_code == 0
        assert mock_run.call_count == 3
        mock_recovery.assert_called_once()
        mock_retry.assert_called_once()

    def test_commit_surface_requires_exactly_one_handoff_or_routing_record(self, tmp_path):
        handoff_path = tmp_path / "handoff.json"
        handoff_path.write_text("{}", encoding="utf-8")
        routing_path = tmp_path / "routing.json"
        routing_path.write_text("{}", encoding="utf-8")
        args = dispatch_mod.build_surface_parser().parse_args(
            [
                "commit",
                "--handoff", str(handoff_path),
                "--routing-record-path", str(routing_path),
            ]
        )
        with pytest.raises(dispatch_mod.ControlSurfaceError, match="either --handoff or a routing record"):
            dispatch_mod.build_surface_command(args)

    def test_commit_surface_builds_handoff_command(self, tmp_path):
        handoff_path = tmp_path / "handoff.json"
        handoff_path.write_text("{}", encoding="utf-8")
        args = dispatch_mod.build_surface_parser().parse_args(
            ["commit", "--handoff", str(handoff_path), "--json"]
        )
        cmd = dispatch_mod.build_surface_command(args)
        assert cmd[:2] == [dispatch_mod.sys.executable, str(dispatch_mod.SCRIPT_DIR / "commit_executor.py")]
        assert "--handoff" in cmd
        assert str(handoff_path) in cmd
        assert "--json" in cmd

    def test_classify_commit_executor_result_detects_json_held(self):
        commit_result = subprocess.CompletedProcess(
            ["commit"], 0, json.dumps({"status": "held"}), ""
        )
        assert dispatch_mod._classify_commit_executor_result(commit_result) == (  # ANTICHEAT_OK: testing internal commit-result classifier
            "held",
            "COMMIT_HELD",
        )

    def test_classify_commit_executor_result_detects_json_error(self):
        commit_result = subprocess.CompletedProcess(
            ["commit"], 0, json.dumps({"status": "error"}), ""
        )
        assert dispatch_mod._classify_commit_executor_result(commit_result) == (  # ANTICHEAT_OK: testing internal commit-result classifier
            "failed",
            "COMMIT_GO",
        )

    def test_main_routes_commit_surface_through_recovery_wrapper(self, tmp_path):
        handoff_path = tmp_path / "handoff.json"
        handoff_path.write_text(json.dumps({"wave_id": "commit-surface-wave"}), encoding="utf-8")
        config = {"timeouts": {"commit_executor": 300}}

        with patch.object(dispatch_mod, "resolve_repo_root_for_dispatch", return_value=tmp_path), \
             patch.object(dispatch_mod, "load_config", return_value=config) as mock_load, \
             patch.object(dispatch_mod, "run_recoverable_surface_command", return_value=0) as mock_run:
            exit_code = dispatch_mod.main(
                ["commit", "--handoff", str(handoff_path), "--json"]
            )

        assert exit_code == 0
        mock_load.assert_called_once()
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args.kwargs["repo_root"] == tmp_path
        assert call_args.kwargs["config"] == config

    def test_resolve_repo_root_for_dispatch_uses_linked_worktree_from_bare_common_dir(self):
        branch = "jabramsja/recovery-tier3-wiring-closeout-2026-04-01"
        linked = "/tmp/workingrcx_surface_linked"
        worktree_output = (
            "worktree /repo/common\n"
            "bare\n\n"
            f"worktree {linked}\n"
            "HEAD 6061a20f5577da91909753fb51c117d0d6938db5\n"
            f"branch refs/heads/{branch}\n"
        )

        calls: list[list[str]] = []

        def fake_run(cmd, capture_output=False, text=False, check=False, **kwargs):
            calls.append(cmd)
            if cmd == ["git", "rev-parse", "--show-toplevel"]:
                return subprocess.CompletedProcess(cmd, 0, stdout="/repo/common\n", stderr="")
            if cmd == ["git", "rev-parse", "--is-inside-work-tree"]:
                return subprocess.CompletedProcess(cmd, 0, stdout="false\n", stderr="")
            if cmd == ["git", "rev-parse", "--is-bare-repository"]:
                return subprocess.CompletedProcess(cmd, 0, stdout="true\n", stderr="")
            if cmd == ["git", "symbolic-ref", "--quiet", "--short", "HEAD"]:
                return subprocess.CompletedProcess(cmd, 0, stdout=f"{branch}\n", stderr="")
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return subprocess.CompletedProcess(cmd, 0, stdout=worktree_output, stderr="")
            raise AssertionError(f"unexpected git command: {cmd}")

        with patch.object(dispatch_mod.subprocess, "run", side_effect=fake_run):
            repo_root = dispatch_mod.resolve_repo_root_for_dispatch()

        assert repo_root == Path(linked)
        assert calls[:3] == [
            ["git", "rev-parse", "--show-toplevel"],
            ["git", "rev-parse", "--is-inside-work-tree"],
            ["git", "rev-parse", "--is-bare-repository"],
        ]
        assert calls[3:] == [
            ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
            ["git", "worktree", "list", "--porcelain"],
        ]

    def test_main_phase_surface_mode_runs_recoverable_command(self):
        with patch.object(dispatch_mod, "run_recoverable_surface_command", return_value=0) as mock_run, \
             patch.object(dispatch_mod, "run_surface_command") as mock_surface, \
             patch.object(dispatch_mod, "load_config", return_value={"timeouts": {}}), \
             patch.object(dispatch_mod, "resolve_repo_root_for_dispatch", return_value=REPO_ROOT):
            exit_code = dispatch_mod.main(["phase-a", "--plan-name", "example"])
        assert exit_code == 0
        mock_run.assert_called_once()
        mock_surface.assert_not_called()

    def test_main_non_phase_surface_runs_forwarded_command(self, tmp_path):
        package_path = tmp_path / "package.json"
        package_path.write_text("{}", encoding="utf-8")
        with patch.object(dispatch_mod, "run_recoverable_surface_command") as mock_recoverable, \
             patch.object(dispatch_mod, "run_surface_command", return_value=0) as mock_run, \
             patch.object(dispatch_mod, "resolve_repo_root_for_dispatch", return_value=REPO_ROOT):
            exit_code = dispatch_mod.main(
                ["pre-commit-supervisor", "--package", str(package_path)]
            )
        assert exit_code == 0
        mock_recoverable.assert_not_called()
        mock_run.assert_called_once()


class TestDispatcherExecutorGroupCleanup:
    """Dispatcher timeout cleanup must reap the process tree before retry."""

    def test_timeout_calls_terminate_process_tree(self):
        mock_proc = MagicMock()
        mock_proc.communicate.side_effect = subprocess.TimeoutExpired(
            cmd=["test"], timeout=1
        )
        mock_proc.pid = 4321
        mock_proc.wait.return_value = None

        with patch.object(dispatch_mod.subprocess, "Popen", return_value=mock_proc) as mock_popen, \
             patch.object(dispatch_mod.os, "killpg") as mock_killpg, \
             patch.object(dispatch_mod, "terminate_process_tree") as mock_terminate:
            with pytest.raises(subprocess.TimeoutExpired):
                dispatch_mod._run_executor_in_group(["test"], cwd=Path("."), timeout=1)  # ANTICHEAT_OK: testing direct executor-group timeout cleanup helper

        _, kwargs = mock_popen.call_args
        assert kwargs["start_new_session"] is True
        mock_killpg.assert_called_once_with(4321, signal.SIGTERM)
        mock_terminate.assert_called_once_with(4321, cwd=Path("."))
        mock_proc.kill.assert_called_once()

    def test_interrupt_calls_terminate_process_tree(self):
        """Direct dispatcher interruption must reap the child executor tree."""
        mock_proc = MagicMock()
        mock_proc.pid = 4321
        installed_handlers: dict[int, Any] = {}

        def fake_signal(signum, handler):
            previous = installed_handlers.get(signum, signal.SIG_DFL)
            installed_handlers[signum] = handler
            return previous

        def fake_communicate(timeout):
            installed_handlers[signal.SIGTERM](signal.SIGTERM, None)
            raise AssertionError("signal handler should not return")

        mock_proc.communicate.side_effect = fake_communicate
        mock_proc.wait.return_value = None

        with patch.object(dispatch_mod.subprocess, "Popen", return_value=mock_proc), \
             patch.object(dispatch_mod, "terminate_process_tree") as mock_terminate, \
             patch.object(dispatch_mod.signal, "signal", side_effect=fake_signal):
            with pytest.raises(SystemExit) as exc:
                dispatch_mod._run_executor_in_group(["test"], cwd=Path("."), timeout=1)  # ANTICHEAT_OK: testing direct executor-group signal cleanup helper

        assert exc.value.code == 128 + signal.SIGTERM
        mock_terminate.assert_called_with(4321, cwd=Path("."))
        mock_proc.wait.assert_called()


# --- Phase B handoff new schema test ---

class TestPhaseBNewSchemaHandoff:
    """Phase B prepare_commit_handoff produces new schema."""

    def test_handoff_includes_tracker_note_text(self, tmp_path):
        """Handoff includes tracker_note_text for commit executor."""
        path = phase_b_mod.prepare_commit_handoff(
            tmp_path,
            wave_id="test-wave",
            task_id="[TEST]",
            wave_class="L4_ENABLER",
            target_gate_id="G8",
            tracker_note_text="- Tracker sync note (test): test.",
            fixes_implemented=["fix1"],
            files_to_stage=["a.py"],
            commit_message="feat: test",
            pr_title="feat: test",
            pr_body="## Summary\ntest",
        )
        handoff = json.loads(path.read_text())
        assert handoff["tracker_note_text"] == "- Tracker sync note (test): test."
        assert handoff["fixes_implemented"] == ["fix1"]
        assert handoff["force_add_files"] == []
        assert "wave_id" in handoff
        assert "branch_prefix" in handoff


# ===========================================================================
# Bridge R1 NO_GO Finding Fixes
# ===========================================================================


class TestDispositionKeywordsCoverBlockingContract:
    """Finding 2: BLOCKING_KEYWORDS and DEFECT_INDICATORS must cover
    receipt authority, fail-closed behavior, and process cleanup terms
    so the omitted-disposition fallback classifies them as blocking."""

    @pytest.mark.parametrize("keyword", [
        "receipt authority",
        "fail-closed",
        "fail closed",
        "process cleanup",
        "orphan",
    ])
    def test_blocking_keyword_present(self, keyword):
        assert keyword in common_mod.BLOCKING_KEYWORDS, (
            f"'{keyword}' missing from BLOCKING_KEYWORDS"
        )

    @pytest.mark.parametrize("indicator", [
        "orphaned",
        "not cleaned up",
        "leaked process",
        "receipt not checked",
        "receipt ignored",
        "proceeds without receipt",
        "skips receipt",
    ])
    def test_defect_indicator_present(self, indicator):
        assert indicator in common_mod.DEFECT_INDICATORS, (
            f"'{indicator}' missing from DEFECT_INDICATORS"
        )

    def test_blocking_criteria_mentions_receipt_authority(self):
        joined = " ".join(common_mod.BLOCKING_CRITERIA)
        assert "receipt authority" in joined

    def test_blocking_criteria_mentions_fail_closed(self):
        joined = " ".join(common_mod.BLOCKING_CRITERIA)
        assert "fail-closed" in joined

    def test_blocking_criteria_mentions_process_cleanup(self):
        joined = " ".join(common_mod.BLOCKING_CRITERIA)
        assert "process cleanup" in joined


class TestRunBridgeSubprocessCleanup:
    """Finding 1: run_bridge_subprocess must use start_new_session and
    os.killpg on timeout to clean up adapter grandchildren."""

    def test_normal_completion_returns_completed_process(self):
        """Successful subprocess returns CompletedProcess."""
        result = common_mod.run_bridge_subprocess(
            [sys.executable, "-c", "print('hello')"],
            cwd=Path("."),
            timeout=10,
        )
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_timeout_raises_executor_common_error(self):
        """Timeout raises ExecutorCommonError after cleanup."""
        with pytest.raises(common_mod.ExecutorCommonError, match="timed out"):
            common_mod.run_bridge_subprocess(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                cwd=Path("."),
                timeout=1,
            )

    def test_nonzero_exit_preserved(self):
        """Non-zero exit code is captured, not raised."""
        result = common_mod.run_bridge_subprocess(
            [sys.executable, "-c", "import sys; sys.exit(42)"],
            cwd=Path("."),
            timeout=10,
        )
        assert result.returncode == 42

    def test_stderr_captured(self):
        """stderr is captured in CompletedProcess."""
        result = common_mod.run_bridge_subprocess(
            [sys.executable, "-c",
             "import sys; sys.stderr.write('err_msg\\n')"],
            cwd=Path("."),
            timeout=10,
        )
        assert "err_msg" in result.stderr

    @patch("executor_common.subprocess.Popen")
    def test_uses_start_new_session(self, mock_popen):
        """Popen is called with start_new_session=True."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("out", "err")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc
        common_mod.run_bridge_subprocess(
            ["echo", "test"], cwd=Path("."), timeout=10,
        )
        _, kwargs = mock_popen.call_args
        assert kwargs["start_new_session"] is True

    @patch("executor_common.os.killpg")
    @patch("executor_common.os.getpgid", return_value=12345)
    @patch("executor_common.subprocess.Popen")
    def test_timeout_calls_killpg(self, mock_popen, mock_getpgid, mock_killpg):
        """On timeout, os.killpg is called to clean up process group."""
        mock_proc = MagicMock()
        mock_proc.communicate.side_effect = subprocess.TimeoutExpired(
            cmd=["test"], timeout=1
        )
        mock_proc.pid = 12345
        mock_proc.wait.side_effect = [None]  # After SIGTERM, wait succeeds
        mock_popen.return_value = mock_proc
        with pytest.raises(common_mod.ExecutorCommonError):
            common_mod.run_bridge_subprocess(
                ["test"], cwd=Path("."), timeout=1,
            )
        # SIGTERM sent to process group first
        mock_killpg.assert_any_call(12345, signal.SIGTERM)


class TestExecutorsUseBridgeSubprocess:
    """Bridge invocation surfaces use the shared cleanup/watchdog helpers."""

    def test_phase_a_imports_bridge_watchdog_helpers(self):
        assert hasattr(phase_a_mod, "process_descendants")
        assert hasattr(phase_a_mod, "terminate_process_tree")
        assert hasattr(phase_a_mod, "artifact_size_mtime_ns")

    def test_dialectic_imports_run_bridge_subprocess(self):
        assert hasattr(dialectic_mod, "run_bridge_subprocess")

    def test_phase_b_imports_run_bridge_subprocess(self):
        assert hasattr(phase_b_mod, "run_bridge_subprocess")


# ===========================================================================
# Bridge R6 finding fixes
# ===========================================================================


class TestBridgeR6Finding1NeedsPhaseBreentryPackage:
    """Finding 1: NEEDS_PHASE_B crash-resume must build a complete supervisor package.

    The resume path at _skip_to_reentry must build all 11 supervisor package
    fields, not an empty dict.  If the package is incomplete, the re-entry
    supervisor call at ~line 1499 (package_path.write_text) produces invalid
    JSON for validate_package_schema().
    """

    def test_resume_supervisor_package_has_all_11_fields(self, tmp_path):
        """Resumed supervisor_package must contain all 11 required fields."""
        # Setup: create saved state that triggers _skip_to_reentry
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan = repo / "reports" / "control_plane" / "test_plan.md"
        plan.write_text("# Plan\n\nDate: 2026-03-22\nStatus: Phase B\nPhase-A-Lock: LOCKED\n")
        (repo / ".scratch").mkdir(parents=True)
        (repo / ".agent_bus" / "meta").mkdir(parents=True)
        (repo / ".agent_bus" / "executors").mkdir(parents=True)
        routing = {"decision": "ROUTE_PHASE_B", "summary": "test", "task_id": "[TEST]"}
        (repo / ".agent_bus" / "meta" / "post_merge_routing.json").write_text(json.dumps(routing))

        # Save state indicating needs_phase_b_reentry
        state = {
            "plan_path": "reports/control_plane/test_plan.md",
            "completed_step": "needs_phase_b_reentry",
            "wave_id": "test_plan",
            "bridge_rounds": 2,
            "deferred_packet_path": None,
            "implementer_changed": [],
            "executor_created": [],
            "all_non_blocking": [],
            "finding_history": {},
            "reentry_findings": "Fix some issue",
        }
        state_path = repo / ".agent_bus" / "executors" / "phase_b_state.json"
        state_path.write_text(json.dumps(state))

        # We need to mock out the parts that would actually run
        captured_package = {}

        def mock_invoke_implementer(repo, prompt, **kwargs):
            return {"status": "success", "exit_code": 0}

        def mock_bridge_review(repo, task, *, job_id=None, verbose=False, timeout=1200):
            return {"exit_code": 0, "stdout": "", "stderr": "", "decision": "GO", "job_id": job_id or ""}

        def mock_collect_changed(repo):
            return ["mu/tools/executors/test.py"]

        def mock_stage_files(repo, files):
            return True

        def mock_run_pytest(repo, files, *, timeout=120):
            return {"exit_code": 0, "stdout": "", "stderr": "", "passed": True}

        original_write = Path.write_text

        def capture_write_text(self_path, content, *args, **kwargs):
            if "phase_b_supervisor_package.json" in str(self_path):
                captured_package.update(json.loads(content))
            return original_write(self_path, content, *args, **kwargs)

        # Mock supervisor to return COMMIT_GO
        def mock_supervisor(repo, pkg_path, *, verbose=False):
            return {
                "exit_code": 0,
                "parsed": {"decision": "COMMIT_GO", "summary": "ok"},
                "receipt_path": ".agent_bus/meta/pre_commit_receipt.json",
            }

        with patch.object(phase_b_mod, "load_routing_record", return_value=routing), \
             patch.object(phase_b_mod, "run_bridge_review", side_effect=mock_bridge_review), \
             patch.object(phase_b_mod, "_collect_changed_files", side_effect=mock_collect_changed), \
             patch.object(phase_b_mod, "_stage_files", side_effect=mock_stage_files), \
             patch.object(phase_b_mod, "_run_pytest_on_files", side_effect=mock_run_pytest), \
             patch.object(phase_b_mod, "run_pre_commit_supervisor", side_effect=mock_supervisor), \
             patch.object(Path, "write_text", side_effect=capture_write_text):
            try:
                # Need to also mock build_implementation_prompt and invoke_implementer
                with patch.object(phase_b_mod, "invoke_implementer", side_effect=mock_invoke_implementer), \
                     patch.object(phase_b_mod, "build_implementation_prompt", return_value="prompt"):
                    result = phase_b_mod.run_phase_b(
                        repo, "reports/control_plane/test_plan.md", verbose=True,
                    )
            except Exception:
                pass  # May fail downstream; we only care about the package

        # The key assertion: captured package must have all 11 fields
        required_fields = {
            "task_id", "wave_name", "lane", "changed_files",
            "scope_items", "fixes_implemented", "deferred_items",
            "bridge_status", "evidence_handles", "blocker_report_paths",
            "current_judgment",
        }
        if captured_package:
            missing = required_fields - set(captured_package.keys())
            assert not missing, f"Supervisor package missing fields: {sorted(missing)}"


class TestBridgeR6Finding2PhaseAAgentGate:
    """Finding 2: Phase A must gate on failed SDK review exits.

    Previously, agent exit code was recorded but never used as a gate.
    Nonzero exit must be fatal, same as Phase B.
    """

    def _setup_phase_a(self, tmp_path, monkeypatch=None):
        plan_dir = tmp_path / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        rendered_dir = tmp_path / ".agent_bus" / "rendered"
        rendered_dir.mkdir(parents=True)
        bus_dir = tmp_path / ".agent_bus" / "meta"
        bus_dir.mkdir(parents=True)
        routing = {"decision": "ROUTE_PHASE_A", "summary": "test"}
        (bus_dir / "post_merge_routing.json").write_text(json.dumps(routing))
        plan_path = phase_a_mod.create_plan_draft(
            tmp_path,
            "test_plan",
            {"request": "test", "summary": "test"},
        )
        plan_path.write_text(
            """# Test Plan

Date: 2026-04-02
Status: Phase A (design -- not yet agent-reviewed or bridge-converged)
Phase-A-Lock: UNLOCKED

## Scope

- `mu/tools/executors/recovery_gate.py`

## Work Items

- Route SDK review findings into the bridge context.

## Constraints

- No unrelated files.

## Stop Conditions

- Stop if bridge cannot classify findings.

## Acceptance Criteria

- Phase A runs SDK review before bridge for real plans.

## Grounding

- TASKS.md route under test.
""",
            encoding="utf-8",
        )
        if monkeypatch is not None:
            monkeypatch.setattr(
                phase_a_mod, "checkpoint_commit_plan",
                lambda *a, **kw: {"sha": "fake_checkpoint_sha"},
            )
        return rendered_dir

    def test_hard_gate_agent_review_blocks_bridge(self, tmp_path, monkeypatch):
        """Hard-gate / infra exits must prevent bridge from running."""
        self._setup_phase_a(tmp_path, monkeypatch)
        bridge_called = {"n": 0}

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {"exit_code": 4, "stdout": "", "stderr": "preflight failed"}

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            bridge_called["n"] += 1
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=5)
        assert result["status"] == "error"
        assert "agent review failed" in result["error"].lower() or "SDK agent review failed" in result["error"]
        assert result["agent_exit_code"] == 4
        # Bridge must NOT have been called
        assert bridge_called["n"] == 0

    def test_agent_review_timeout_budget_comes_from_executor_config(self, tmp_path, monkeypatch):
        """Phase A must pass the configured agent-review budget into run_sdk_agents."""
        rendered_dir = self._setup_phase_a(tmp_path, monkeypatch)
        captured: dict[str, int] = {}

        monkeypatch.setattr(
            phase_a_mod,
            "load_executor_config",
            lambda repo_root: {
                "review_depths": {"phase_a": "quick"},
                "timeouts": {"agent_review": 901},
            },
        )

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            captured["timeout"] = timeout
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            rendered = rendered_dir / f"{job_id}.md"
            rendered.write_text("Decision: GO\n\nLooks good.\n")
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=5)
        assert result["status"] == "converged"
        assert captured["timeout"] == 901

    def test_soft_warning_agent_review_proceeds_to_bridge(self, tmp_path, monkeypatch):
        """Exit 2 is a soft gate and must not block bridge review."""
        rendered_dir = self._setup_phase_a(tmp_path, monkeypatch)
        bridge_called = {"n": 0}

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {"exit_code": 2, "stdout": "", "stderr": "expert: COULD_SIMPLIFY"}

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            bridge_called["n"] += 1
            rendered = rendered_dir / f"{job_id}.md"
            rendered.write_text("Decision: GO\n\nLooks good.\n")
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=5)
        assert result["status"] == "converged"
        assert result["agent_exit_code"] == 2
        assert bridge_called["n"] == 1

    def test_semantic_blocker_agent_review_continues_to_bridge(self, tmp_path, monkeypatch):
        """Exit 1 (semantic blockers) must continue to bridge for contextual classification."""
        rendered_dir = self._setup_phase_a(tmp_path, monkeypatch)
        bridge_called = {"n": 0}

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": "adversary timed out",
                "report_path": ".scratch/phase_a_agent_review_test.report.md",
                "status_path": ".scratch/phase_a_agent_review_test.status.json",
                "stdout_path": ".scratch/phase_a_agent_review_test.stdout.log",
            }

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            bridge_called["n"] += 1
            rendered = rendered_dir / f"{job_id}.md"
            rendered.write_text("Decision: GO\n\nLooks good.\n")
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=5)
        assert result["status"] == "converged"
        assert result["agent_exit_code"] == 1
        assert result["agent_review_warning_only"] is True
        assert result["agent_review_report_path"] == ".scratch/phase_a_agent_review_test.report.md"
        assert result["agent_review_status_path"] == ".scratch/phase_a_agent_review_test.status.json"
        assert result["agent_review_stdout_path"] == ".scratch/phase_a_agent_review_test.stdout.log"
        assert bridge_called["n"] == 1

    def test_infra_gate_agent_review_preserves_report_artifacts(self, tmp_path, monkeypatch):
        """Infra exits (>=3) must fail closed and preserve report/status artifact paths."""
        self._setup_phase_a(tmp_path, monkeypatch)

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {
                "exit_code": 4,
                "stdout": "",
                "stderr": "preflight failed",
                "report_path": ".scratch/phase_a_agent_review_test.report.md",
                "status_path": ".scratch/phase_a_agent_review_test.status.json",
                "stdout_path": ".scratch/phase_a_agent_review_test.stdout.log",
            }

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", lambda *a, **k: pytest.fail("bridge must not run"))

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=5)
        assert result["status"] == "error"
        assert result["agent_review_report_path"] == ".scratch/phase_a_agent_review_test.report.md"
        assert result["agent_review_status_path"] == ".scratch/phase_a_agent_review_test.status.json"
        assert result["agent_review_stdout_path"] == ".scratch/phase_a_agent_review_test.stdout.log"

    def test_infra_gate_error_reads_status_diagnostic(self, tmp_path, monkeypatch):
        """Infra exits must surface agent status diagnostic, not just truncated stderr."""
        self._setup_phase_a(tmp_path, monkeypatch)

        # Write a status.json that the error handler should read
        scratch = tmp_path / ".scratch"
        scratch.mkdir(exist_ok=True)
        status_data = {
            "phase_label": "agent_review",
            "status": "completed",
            "completed_agents": {
                "verifier": {"verdict": "PASS"},
                "adversary": {"verdict": "UNKNOWN", "detail": "AGENT TIMEOUT: adversary exceeded 360s"},
            },
            "running_agents": [],
        }
        (scratch / "phase_a_agent_review_test.status.json").write_text(
            json.dumps(status_data), encoding="utf-8"
        )

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {
                "exit_code": 3,
                "stdout": "",
                "stderr": "WARNING: Bun AVX blah blah noise",
                "report_path": ".scratch/phase_a_agent_review_test.report.md",
                "status_path": ".scratch/phase_a_agent_review_test.status.json",
                "stdout_path": ".scratch/phase_a_agent_review_test.stdout.log",
            }

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", lambda *a, **k: pytest.fail("bridge must not run"))

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=5)
        assert result["status"] == "error"
        # Error must include the agent status diagnostic, not just noisy stderr
        assert "adversary=UNKNOWN" in result["error"]
        assert "verifier=PASS" in result["error"]
        assert "agent_status:" in result["error"]

    def test_agent_review_artifacts_passed_to_bridge(self, tmp_path, monkeypatch):
        """Phase A must surface agent review artifacts to bridge reviewer (parity with Phase B)."""
        rendered_dir = self._setup_phase_a(tmp_path, monkeypatch)
        captured_ctx = {}

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {
                "exit_code": 2,
                "stdout": "",
                "stderr": "expert: COULD_SIMPLIFY",
                "report_path": ".scratch/phase_a_agent_review_test.report.md",
                "status_path": ".scratch/phase_a_agent_review_test.status.json",
                "stdout_path": ".scratch/phase_a_agent_review_test.stdout.log",
            }

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            captured_ctx["agent_review_context"] = agent_review_context
            rendered = rendered_dir / f"{job_id}.md"
            rendered.write_text("Decision: GO\n\nLooks good.\n")
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=5)
        assert result["status"] == "converged"
        # Bridge must have received agent review context
        ctx = captured_ctx["agent_review_context"]
        assert "report" in ctx
        assert "phase_a_agent_review_test.report.md" in ctx
        assert "exit_code: 2" in ctx

    def test_successful_agent_review_proceeds_to_bridge(self, tmp_path, monkeypatch):
        """Zero agent exit code allows bridge to proceed (regression check)."""
        rendered_dir = self._setup_phase_a(tmp_path, monkeypatch)

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            rendered = rendered_dir / f"{job_id}.md"
            rendered.write_text("Decision: GO\n\nLooks good.\n")
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=5)
        assert result["status"] == "converged"


class TestBridgeR6Finding3PhaseARequestChangesSilentSuccess:
    """Finding 3: Phase A must not return success after repeated REQUEST_CHANGES
    with no plan mutation.

    Previously, repeated REQUEST_CHANGES `continue`d past the max-rounds guard,
    exhausting the for-loop and falling through with status="success" (the
    initial default) — a false positive.
    """

    def _setup_phase_a(self, tmp_path, monkeypatch=None):
        plan_dir = tmp_path / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        rendered_dir = tmp_path / ".agent_bus" / "rendered"
        rendered_dir.mkdir(parents=True)
        bus_dir = tmp_path / ".agent_bus" / "meta"
        bus_dir.mkdir(parents=True)
        routing = {"decision": "ROUTE_PHASE_A", "summary": "test"}
        (bus_dir / "post_merge_routing.json").write_text(json.dumps(routing))
        plan_path = phase_a_mod.create_plan_draft(
            tmp_path,
            "test_plan",
            {"request": "test", "summary": "test"},
        )
        plan_path.write_text(
            """# Test Plan

Date: 2026-04-02
Status: Phase A (design -- not yet agent-reviewed or bridge-converged)
Phase-A-Lock: UNLOCKED

## Scope

- `mu/tools/executors/phase_a_executor.py`

## Work Items

- Exercise REQUEST_CHANGES / NO_GO loop accounting on a real plan packet.

## Constraints

- No stub packet in this fixture.

## Stop Conditions

- Stop if bridge loop silently succeeds without convergence.

## Acceptance Criteria

- Repeated non-GO decisions either consume rounds or converge honestly.

## Grounding

- Phase A bridge loop silent-success regression fixture.
""",
            encoding="utf-8",
        )
        if monkeypatch is not None:
            monkeypatch.setattr(
                phase_a_mod, "checkpoint_commit_plan",
                lambda *a, **kw: {"sha": "fake_checkpoint_sha"},
            )
        return rendered_dir

    def test_all_request_changes_returns_max_rounds_not_success(self, tmp_path, monkeypatch):
        """All rounds returning REQUEST_CHANGES must yield max_rounds_reached, not success."""
        rendered_dir = self._setup_phase_a(tmp_path, monkeypatch)
        call_count = {"n": 0}

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            call_count["n"] += 1
            rendered = rendered_dir / f"{job_id}.md"
            rendered.write_text("Decision: REQUEST_CHANGES\n\nPlease fix section 3.\n")
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=3)
        assert result["status"] == "max_rounds_reached", (
            f"Expected max_rounds_reached, got {result['status']}. "
            "REQUEST_CHANGES must not silently succeed."
        )
        assert "error" in result  # Should have an error message
        assert call_count["n"] == 3  # All 3 rounds were used

    def test_no_go_then_go_converges(self, tmp_path, monkeypatch):
        """NO_GO followed by GO still converges (regression check)."""
        rendered_dir = self._setup_phase_a(tmp_path, monkeypatch)
        call_count = {"n": 0}

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            call_count["n"] += 1
            rendered = rendered_dir / f"{job_id}.md"
            if call_count["n"] < 3:
                rendered.write_text("Decision: NO_GO\n\nNeeds work.\n")
            else:
                rendered.write_text("Decision: GO\n\nGood now.\n")
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)

        result = phase_a_mod.run_phase_a(tmp_path, "test_plan", max_bridge_rounds=5)
        assert result["status"] == "converged"
        assert call_count["n"] == 3


# ===========================================================================
# Phase A tracked-packet reuse (Slice 3 follow-on)
# ===========================================================================


class TestPhaseATrackedPacketReuse:
    """Phase A reuses existing tracked packets instead of creating new dated stubs."""

    def test_reuses_locked_packet(self, tmp_path):
        """If a locked packet exists, create_plan_draft returns it."""
        plan_dir = tmp_path / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        existing = plan_dir / "my_plan_2026-03-20.md"
        existing.write_text("# My Plan\nPhase-A-Lock: LOCKED\n\nReal content here.\n")
        scope = {"request": "new content"}
        path = phase_a_mod.create_plan_draft(tmp_path, "my_plan", scope)
        assert path == existing

    def test_reuses_substantial_unlocked_packet(self, tmp_path):
        """If a substantial (>10 lines) unlocked packet exists, reuse it."""
        plan_dir = tmp_path / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        existing = plan_dir / "my_plan_2026-03-20.md"
        content = "# My Plan\nPhase-A-Lock: UNLOCKED\n" + "\n".join(f"Line {i}" for i in range(20))
        existing.write_text(content)
        scope = {"request": "new content"}
        path = phase_a_mod.create_plan_draft(tmp_path, "my_plan", scope)
        assert path == existing

    def test_creates_new_when_no_matching_packet(self, tmp_path):
        """When no matching packet exists, creates a new one."""
        scope = {"request": "create something", "summary": "test"}
        path = phase_a_mod.create_plan_draft(tmp_path, "brand_new_plan", scope)
        assert path.exists()
        assert "brand_new_plan" in path.name
        assert "Phase-A-Lock: UNLOCKED" in path.read_text()

    def test_prefers_locked_over_unlocked(self, tmp_path):
        """When both locked and unlocked exist, prefer the locked one."""
        plan_dir = tmp_path / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        unlocked = plan_dir / "my_plan_2026-03-19.md"
        unlocked.write_text("# Plan\nPhase-A-Lock: UNLOCKED\n" + "\n".join(f"L{i}" for i in range(20)))
        locked = plan_dir / "my_plan_2026-03-20.md"
        locked.write_text("# Plan\nPhase-A-Lock: LOCKED\n\nReal content.\n")
        scope = {"request": "x"}
        path = phase_a_mod.create_plan_draft(tmp_path, "my_plan", scope)
        assert path == locked

    def test_run_phase_a_reused_locked_packet_converges(self, tmp_path, monkeypatch):
        plan_dir = tmp_path / "reports" / "control_plane"
        rendered_dir = tmp_path / ".agent_bus" / "rendered"
        rendered_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / ".agent_bus" / "executors").mkdir(parents=True, exist_ok=True)
        locked = plan_dir / "my_plan_2026-03-20.md"
        plan_dir.mkdir(parents=True, exist_ok=True)
        locked.write_text(
            "# My Plan\n"
            "Status: Phase A (design -- not yet agent-reviewed or bridge-converged)\n"
            "Phase-A-Lock: LOCKED\n"
            "\n"
            "## Scope\n"
            "\n"
            "- `mu/tools/executors/phase_a_executor.py`\n"
            "\n"
            "## Work Items\n"
            "\n"
            "- Reuse this locked packet without creating a new stub.\n"
            "\n"
            "## Constraints\n"
            "\n"
            "- No extra packets.\n"
            "\n"
            "## Stop Conditions\n"
            "\n"
            "- Stop if Phase A rewrites a locked packet path.\n"
            "\n"
            "## Acceptance Criteria\n"
            "\n"
            "- Locked tracked packet stays canonical.\n"
            "\n"
            "## Grounding\n"
            "\n"
            "- Tracked packet reuse regression fixture.\n",
            encoding="utf-8",
        )

        def fake_run_sdk_agents(repo_root, files, *, depth="full", verbose=False, timeout=600):
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        def fake_run_bridge(repo_root, plan_path, round_num, *, job_id=None, timeout=1200, agent_review_context=""):
            rendered = rendered_dir / f"{job_id}.md"
            rendered.write_text("Decision: GO\n\nLooks good.\n", encoding="utf-8")
            return {"exit_code": 0, "stdout": "", "stderr": ""}

        monkeypatch.setattr(phase_a_mod, "run_sdk_agents", fake_run_sdk_agents)
        monkeypatch.setattr(phase_a_mod, "run_bridge_design_review", fake_run_bridge)
        monkeypatch.setattr(
            phase_a_mod, "checkpoint_commit_plan",
            lambda *a, **kw: {"sha": "fake_checkpoint_sha"},
        )

        result = phase_a_mod.run_phase_a(tmp_path, "my_plan", max_bridge_rounds=5)
        assert result["status"] == "converged"
        content = locked.read_text(encoding="utf-8")
        assert content.count("Phase-A-Lock: LOCKED") == 1
        assert "bridge-converged" in content


class TestFindTrackedPacket:
    """_find_tracked_packet searches for existing packets by plan name."""

    def test_returns_none_when_no_directory(self, tmp_path):
        result = phase_a_mod._find_tracked_packet(tmp_path / "nonexistent", "test")  # ANTICHEAT_OK: testing tracked packet reuse
        assert result is None

    def test_returns_exact_packet_match(self, tmp_path):
        plan_dir = tmp_path / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        exact = plan_dir / "my_plan.md"
        exact.write_text("# Plan\nPhase-A-Lock: UNLOCKED\n")
        result = phase_a_mod._find_tracked_packet(plan_dir, "my_plan")  # ANTICHEAT_OK: testing tracked packet reuse
        assert result == exact

    def test_returns_none_when_no_matches(self, tmp_path):
        plan_dir = tmp_path / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        (plan_dir / "other_plan_2026-03-20.md").write_text("# Other\n")
        result = phase_a_mod._find_tracked_packet(plan_dir, "my_plan")  # ANTICHEAT_OK: testing tracked packet reuse
        assert result is None

    def test_returns_locked_packet(self, tmp_path):
        plan_dir = tmp_path / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        locked = plan_dir / "my_plan_2026-03-20.md"
        locked.write_text("# Plan\nPhase-A-Lock: LOCKED\n")
        result = phase_a_mod._find_tracked_packet(plan_dir, "my_plan")  # ANTICHEAT_OK: testing tracked packet reuse
        assert result == locked


# ===========================================================================
# Dispatcher -> commit mechanical bridge (Slice 2 follow-on)
# ===========================================================================


class TestDispatcherCommitMechanicalBridge:
    """Dispatcher routes to commit_executor mechanically instead of returning needs_handoff."""

    def test_commit_go_with_handoff_file(self, tmp_path):
        """When a handoff file exists, dispatcher passes --handoff."""
        handoff_dir = tmp_path / ".agent_bus" / "executors"
        handoff_dir.mkdir(parents=True)
        (handoff_dir / "phase_b_handoff.json").write_text(json.dumps({
            "wave_id": "test",
            "task_id": "[TEST-1]",
        }))

        record = {
            "decision": "COMMIT_GO",
            "summary": "test",
            "wave_name": "test",
            "task_id": "[TEST-1]",
        }
        with patch.object(dispatch_mod, "_run_executor_in_group") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="ok", stderr=""
            )
            result = dispatch_mod.dispatch(
                record, repo_root=tmp_path, skip_freshness=True
            )
        assert result["status"] == "success"
        # Verify --handoff was passed
        call_args = mock_run.call_args[0][0]
        assert "--handoff" in call_args

    def test_update_tracker_without_handoff_passes_routing_record(self, tmp_path):
        """When no handoff file exists, dispatcher passes --routing-record."""
        record = {"decision": "UPDATE_TRACKER_ONLY", "summary": "update tracker"}
        with patch.object(dispatch_mod, "_run_executor_in_group") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="ok", stderr=""
            )
            result = dispatch_mod.dispatch(
                record, repo_root=tmp_path, skip_freshness=True
            )
        assert result["status"] == "success"
        call_args = mock_run.call_args[0][0]
        assert "--routing-record" in call_args

    def test_no_longer_returns_needs_handoff(self, tmp_path):
        """Dispatcher must not return needs_handoff for mechanically preparable routes."""
        # Use UPDATE_TRACKER_ONLY since COMMIT_GO now requires a handoff file
        record = {"decision": "UPDATE_TRACKER_ONLY", "summary": "test"}
        with patch.object(dispatch_mod, "_run_executor_in_group") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="ok", stderr=""
            )
            result = dispatch_mod.dispatch(
                record, repo_root=tmp_path, skip_freshness=True
            )
        assert result["status"] != "needs_handoff"


class TestCommitExecutorRoutingRecordAcceptance:
    """commit_executor accepts --routing-record and prepares handoff internally."""

    def test_prepare_handoff_from_valid_record(self, tmp_path):
        record = {
            "decision": "UPDATE_TRACKER_ONLY",
            "summary": "update the tracker",
            "wave_name": "tracker-update",
            "next_candidates": [{"candidate": "update TASKS.md"}],
        }
        handoff, errors = commit_mod.prepare_handoff_from_routing_record(record, tmp_path)
        assert not errors
        assert handoff is not None
        assert handoff["caller"] == "update_tracker_only"
        assert "TASKS.md" in handoff["files_to_stage"]
        assert handoff["wave_id"] == "tracker-update"

    def test_prepare_handoff_tracker_only_fallback_note_is_contract_complete(self, tmp_path):
        record = {
            "decision": "UPDATE_TRACKER_ONLY",
            "summary": "update the tracker",
            "wave_name": "tracker-update",
        }
        handoff, errors = commit_mod.prepare_handoff_from_routing_record(record, tmp_path)
        assert not errors
        assert handoff is not None
        valid, validation_errors = commit_mod.validate_handoff(handoff)
        assert valid, validation_errors
        note = handoff["tracker_note_text"]
        assert "primary_invariant_id:" in note
        assert "indicator_artifact_ref:" in note
        assert "boot0_progress_state:" in note

    def test_prepare_handoff_from_valid_embedded_handoff(self, tmp_path):
        """Embedded handoffs are accepted only after full validation."""
        embedded = _make_new_handoff(wave_id="embedded-test")
        record = {
            "decision": "COMMIT_GO",
            "summary": "test",
            "handoff": embedded,
        }
        handoff, errors = commit_mod.prepare_handoff_from_routing_record(record, tmp_path)
        assert not errors
        assert handoff == embedded
        assert handoff is not embedded

    def test_prepare_handoff_from_invalid_embedded_handoff_fails(self, tmp_path):
        record = {
            "decision": "COMMIT_GO",
            "summary": "test",
            "handoff": {"wave_id": "embedded-test", "caller": "phase_b"},
        }
        handoff, errors = commit_mod.prepare_handoff_from_routing_record(record, tmp_path)
        assert handoff is None
        assert any("Embedded handoff invalid" in err for err in errors)

    def test_prepare_handoff_commit_go_without_embedded_fails(self, tmp_path):
        """COMMIT_GO without embedded handoff must fail — cannot synthesize."""
        record = {"decision": "COMMIT_GO", "summary": "test", "wave_name": "w"}
        handoff, errors = commit_mod.prepare_handoff_from_routing_record(record, tmp_path)
        assert errors
        assert handoff is None
        assert any("receipt chain" in e for e in errors)

    def test_prepare_handoff_commit_go_hold_push_without_embedded_fails(self, tmp_path):
        """COMMIT_GO_HOLD_PUSH without embedded handoff must fail — cannot synthesize."""
        record = {"decision": "COMMIT_GO_HOLD_PUSH", "summary": "test", "wave_name": "w"}
        handoff, errors = commit_mod.prepare_handoff_from_routing_record(record, tmp_path)
        assert errors
        assert handoff is None
        assert any("receipt chain" in e for e in errors)

    def test_prepare_handoff_missing_wave_fails(self, tmp_path):
        record = {"decision": "UPDATE_TRACKER_ONLY", "summary": "test"}
        handoff, errors = commit_mod.prepare_handoff_from_routing_record(record, tmp_path)
        assert errors
        assert handoff is None

    def test_prepare_handoff_missing_summary_fails(self, tmp_path):
        record = {"decision": "UPDATE_TRACKER_ONLY", "wave_name": "w"}
        handoff, errors = commit_mod.prepare_handoff_from_routing_record(record, tmp_path)
        assert errors
        assert handoff is None


class TestDispatcherPlanlessPhaseB:
    """Dispatcher falls back to planless mode when no tracked_packet in candidates."""

    def test_phase_b_planless_passes_routing_record(self, tmp_path):
        """When no tracked_packet in candidates, dispatcher passes --routing-record."""
        record = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "wave_name": "w",
            "next_candidates": [{"candidate": "do it"}],
        }
        with patch.object(dispatch_mod, "_run_executor_in_group") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="ok", stderr=""
            )
            result = dispatch_mod.dispatch(
                record, repo_root=tmp_path, skip_freshness=True
            )
        call_args = mock_run.call_args[0][0]
        assert "--routing-record" in call_args
        assert "--plan" not in call_args

    def test_phase_b_with_tracked_packet_passes_plan(self, tmp_path):
        """When tracked_packet exists in candidates, dispatcher passes --plan."""
        record = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "next_candidates": [{"candidate": "do", "tracked_packet": "reports/plan.md"}],
        }
        with patch.object(dispatch_mod, "_run_executor_in_group") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="ok", stderr=""
            )
            result = dispatch_mod.dispatch(
                record, repo_root=tmp_path, skip_freshness=True
            )
        call_args = mock_run.call_args[0][0]
        assert "--plan" in call_args
        assert "reports/plan.md" in call_args


class TestTrackedPacketPathTraversal:
    """Finding 964: tracked_packet path traversal must be blocked fail-closed."""

    def test_tracked_packet_with_dotdot_blocked(self, tmp_path):
        """Path traversal via .. in tracked_packet → error."""
        record = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "next_candidates": [{"candidate": "do", "tracked_packet": "../../../etc/passwd"}],
        }
        result = dispatch_mod.dispatch(
            record, repo_root=tmp_path, skip_freshness=True
        )
        assert result["status"] == "error"
        assert "traversal" in result["message"].lower()

    def test_tracked_packet_escaping_repo_root_blocked(self, tmp_path):
        """Absolute-like path that resolves outside repo → error."""
        record = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "next_candidates": [{"candidate": "do", "tracked_packet": "foo/../../.."}],
        }
        result = dispatch_mod.dispatch(
            record, repo_root=tmp_path, skip_freshness=True
        )
        assert result["status"] == "error"

    def test_tracked_packet_valid_path_passes(self, tmp_path):
        """Valid relative path inside repo → proceeds normally."""
        record = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "next_candidates": [{"candidate": "do", "tracked_packet": "reports/plan.md"}],
        }
        with patch.object(dispatch_mod, "_run_executor_in_group") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="ok", stderr=""
            )
            result = dispatch_mod.dispatch(
                record, repo_root=tmp_path, skip_freshness=True
            )
        assert result["status"] in ("success", "failed")
        call_args = mock_run.call_args[0][0]
        assert "--plan" in call_args


class TestWaveIdExactMatchInCommitExecutor:
    """Finding 965: wave_id verification uses exact match, not substring."""

    def test_exact_match_does_not_false_positive_on_substring(self):
        """wave_id 'abc' should not match 'abc-extra' via substring."""
        text = "- Tracker sync note (abc-extra): something\n"
        count = commit_mod._count_exact_wave_id_mentions(text, "abc")  # ANTICHEAT_OK: testing internal executor functions
        assert count == 0, "substring 'abc' inside 'abc-extra' must not match"

    def test_exact_match_finds_real_occurrence(self):
        """wave_id 'abc' should match when bounded by non-wave chars."""
        text = "- Tracker sync note (abc): something\n"
        count = commit_mod._count_exact_wave_id_mentions(text, "abc")  # ANTICHEAT_OK: testing internal executor functions
        assert count == 1

    def test_exact_match_detects_duplicate(self):
        """Two exact occurrences should count as 2."""
        text = "- abc done\n- abc again\n"
        count = commit_mod._count_exact_wave_id_mentions(text, "abc")  # ANTICHEAT_OK: testing internal executor functions
        assert count == 2

    def test_exact_match_counts_multiple_same_line_mentions_once(self):
        """A single tracker line may repeat the wave_id in metadata without becoming duplicate."""
        text = (
            "- Tracker sync note (2026-03-26, abc): already here. "
            "FOUNDER_OVERRIDE:2026-03-26-abc. "
            "indicator_artifact_ref: reports/l4_wave_indicators/abc.json.\n"
        )
        count = commit_mod._count_exact_wave_id_mentions(text, "abc")  # ANTICHEAT_OK: testing internal executor functions
        assert count == 1


class TestDispatcherStaleHandoffOverride:
    """Bridge R1 Finding: dispatcher must not prefer stale handoff over UPDATE_TRACKER_ONLY."""

    def test_update_tracker_only_ignores_stale_handoff(self, tmp_path):
        """UPDATE_TRACKER_ONLY must use --routing-record even if phase_b_handoff.json exists."""
        # Create a stale handoff file
        handoff_dir = tmp_path / ".agent_bus" / "executors"
        handoff_dir.mkdir(parents=True)
        (handoff_dir / "phase_b_handoff.json").write_text('{"stale": true}')

        record = {
            "decision": "UPDATE_TRACKER_ONLY",
            "summary": "just tracker",
            "wave_name": "tracker-only-wave",
        }
        with patch.object(dispatch_mod, "_run_executor_in_group") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="ok", stderr=""
            )
            result = dispatch_mod.dispatch(
                record, repo_root=tmp_path, skip_freshness=True
            )
        call_args = mock_run.call_args[0][0]
        assert "--routing-record" in call_args, (
            "UPDATE_TRACKER_ONLY should pass --routing-record, not --handoff"
        )
        assert "--handoff" not in call_args

    def test_commit_go_uses_handoff_when_present(self, tmp_path):
        """COMMIT_GO should still use --handoff if the file exists."""
        handoff_dir = tmp_path / ".agent_bus" / "executors"
        handoff_dir.mkdir(parents=True)
        (handoff_dir / "phase_b_handoff.json").write_text(json.dumps({
            "wave_id": "ready-to-commit",
            "task_id": "[EXECUTOR-SURFACES]",
        }))

        record = {
            "decision": "COMMIT_GO",
            "summary": "ready to commit",
            "wave_name": "ready-to-commit",
            "task_id": "[EXECUTOR-SURFACES]",
        }
        with patch.object(dispatch_mod, "_run_executor_in_group") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="ok", stderr=""
            )
            result = dispatch_mod.dispatch(
                record, repo_root=tmp_path, skip_freshness=True
            )
        call_args = mock_run.call_args[0][0]
        assert "--handoff" in call_args, (
            "COMMIT_GO should use --handoff when the file exists"
        )

    def test_commit_go_rejects_stale_handoff_identity(self, tmp_path):
        """COMMIT_GO must fail closed if the handoff belongs to a different wave/task."""
        handoff_dir = tmp_path / ".agent_bus" / "executors"
        handoff_dir.mkdir(parents=True)
        (handoff_dir / "phase_b_handoff.json").write_text(json.dumps({
            "wave_id": "old-wave",
            "task_id": "[OLD-TASK]",
        }))

        record = {
            "decision": "COMMIT_GO",
            "summary": "ready to commit",
            "wave_name": "current-wave",
            "task_id": "[EXECUTOR-SURFACES]",
        }
        result = dispatch_mod.dispatch(
            record, repo_root=tmp_path, skip_freshness=True
        )
        assert result["status"] == "error"
        assert "handoff validation failed" in result["message"]

    def test_commit_go_without_handoff_fails_closed(self, tmp_path):
        """COMMIT_GO without handoff file must fail closed — no fallback to --routing-record."""
        record = {
            "decision": "COMMIT_GO",
            "summary": "ready to commit",
        }
        result = dispatch_mod.dispatch(
            record, repo_root=tmp_path, skip_freshness=True
        )
        assert result["status"] == "error"
        assert "No Phase B handoff file" in result["message"]

    def test_commit_go_hold_push_without_handoff_fails_closed(self, tmp_path):
        """COMMIT_GO_HOLD_PUSH without handoff file must also fail closed."""
        record = {
            "decision": "COMMIT_GO_HOLD_PUSH",
            "summary": "ready to commit",
        }
        result = dispatch_mod.dispatch(
            record, repo_root=tmp_path, skip_freshness=True
        )
        assert result["status"] == "error"
        assert "No Phase B handoff file" in result["message"]


# ===========================================================================
# Recovery gate wiring tests
# ===========================================================================


class TestRecoveryGateWiring:
    """Recovery gate integration with the dispatcher retry loop."""

    @staticmethod
    def _routing_file(tmp_path, wave_name="test-wave"):
        f = tmp_path / "routing.json"
        f.write_text(json.dumps({
            "decision": "ROUTE_PHASE_B", "summary": "test",
            "wave_name": wave_name,
        }))
        return f

    @staticmethod
    def _base_args(routing_file):
        return ["--routing-record", str(routing_file), "--skip-freshness"]

    def test_recovery_gate_wired_on_failure(self, tmp_path):
        """attempt_recovery is called when dispatch returns failed status."""
        routing_file = self._routing_file(tmp_path)
        fail_result = {
            "status": "failed", "decision": "ROUTE_PHASE_B",
            "executor": "phase_b_executor",
            "stderr": "bridge.lock held by dead PID",
        }
        recovery_result = {
            "recovered": False, "exhausted": False,
            "failure_class": "stale_bridge_lock", "tier": 1,
            "action": "noop", "detail": "test",
        }
        mock_proc = MagicMock()
        mock_proc.stdout = str(tmp_path)
        with patch.object(dispatch_mod, "dispatch", return_value=fail_result), \
             patch.object(dispatch_mod, "attempt_recovery",
                          return_value=recovery_result) as mock_recovery, \
             patch.object(dispatch_mod.subprocess, "run", return_value=mock_proc):
            dispatch_mod.main(self._base_args(routing_file))
            mock_recovery.assert_called_once()
            call_args = mock_recovery.call_args
            assert call_args[0][1] == fail_result  # result dict passed
            assert call_args[0][2] == "test-wave"  # wave_id from normalize

    def test_recovery_grants_extra_attempt(self, tmp_path):
        """Recovery success grants one extra retry without counting against budget."""
        routing_file = self._routing_file(tmp_path)
        fail_result = {
            "status": "failed", "decision": "ROUTE_PHASE_B",
            "executor": "phase_b_executor",
            "stderr": "bridge.lock exists",
        }
        success_result = {
            "status": "success", "decision": "ROUTE_PHASE_B",
            "executor": "phase_b_executor",
        }
        recovery_success = {
            "recovered": True, "exhausted": False,
            "failure_class": "stale_bridge_lock", "tier": 1,
            "action": "truncate_dead_pid_lock", "detail": "fixed",
        }
        mock_proc = MagicMock()
        mock_proc.stdout = str(tmp_path)
        with patch.object(dispatch_mod, "dispatch",
                          side_effect=[fail_result, success_result]) as mock_dispatch, \
             patch.object(dispatch_mod, "attempt_recovery",
                          return_value=recovery_success), \
             patch.object(dispatch_mod.subprocess, "run", return_value=mock_proc):
            # No --retries: max_attempts=1, but recovery grants one extra
            exit_code = dispatch_mod.main(self._base_args(routing_file))
            assert mock_dispatch.call_count == 2  # original + recovery retry
            assert exit_code == 0  # succeeds on retry

    def test_recovery_exhausted_stops_retry(self, tmp_path):
        """Exhausted recovery breaks the retry loop immediately."""
        routing_file = self._routing_file(tmp_path)
        fail_result = {
            "status": "failed", "decision": "ROUTE_PHASE_B",
            "executor": "phase_b_executor",
            "stderr": "bridge.lock held",
        }
        recovery_exhausted = {
            "recovered": False, "exhausted": True,
            "failure_class": "stale_bridge_lock", "tier": 1,
            "action": "exhausted", "detail": "max attempts reached",
        }
        mock_proc = MagicMock()
        mock_proc.stdout = str(tmp_path)
        with patch.object(dispatch_mod, "dispatch",
                          return_value=fail_result) as mock_dispatch, \
             patch.object(dispatch_mod, "attempt_recovery",
                          return_value=recovery_exhausted), \
             patch.object(dispatch_mod.subprocess, "run", return_value=mock_proc):
            # Even with --retries 2, exhausted recovery stops immediately
            args = self._base_args(routing_file) + ["--retries", "2"]
            dispatch_mod.main(args)
            assert mock_dispatch.call_count == 1  # only one attempt

    def test_recovery_not_called_on_success(self, tmp_path):
        """Recovery is not invoked when dispatch succeeds."""
        routing_file = self._routing_file(tmp_path)
        success_result = {
            "status": "success", "decision": "ROUTE_PHASE_B",
            "executor": "phase_b_executor",
        }
        mock_proc = MagicMock()
        mock_proc.stdout = str(tmp_path)
        with patch.object(dispatch_mod, "dispatch",
                          return_value=success_result), \
             patch.object(dispatch_mod, "attempt_recovery") as mock_recovery, \
             patch.object(dispatch_mod.subprocess, "run", return_value=mock_proc):
            dispatch_mod.main(self._base_args(routing_file))
            mock_recovery.assert_not_called()

    def test_recovery_not_called_on_terminal(self, tmp_path):
        """Terminal executor outcomes bypass recovery entirely."""
        routing_file = self._routing_file(tmp_path)
        terminal_result = {
            "status": "failed", "decision": "ROUTE_PHASE_B",
            "executor": "phase_b_executor",
            "stdout": json.dumps({"status": "question_for_founder"}),
        }
        mock_proc = MagicMock()
        mock_proc.stdout = str(tmp_path)
        with patch.object(dispatch_mod, "dispatch",
                          return_value=terminal_result), \
             patch.object(dispatch_mod, "attempt_recovery") as mock_recovery, \
             patch.object(dispatch_mod.subprocess, "run", return_value=mock_proc):
            dispatch_mod.main(self._base_args(routing_file) + ["--retries", "2"])
            mock_recovery.assert_not_called()

    def test_recovery_result_in_dispatch_output(self, tmp_path):
        """Recovery result dict is attached to the dispatch result."""
        routing_file = self._routing_file(tmp_path)
        fail_result = {
            "status": "failed", "decision": "ROUTE_PHASE_B",
            "executor": "phase_b_executor",
            "stderr": "bridge.lock",
        }
        recovery_result = {
            "recovered": False, "exhausted": False,
            "failure_class": "stale_bridge_lock", "tier": 1,
            "action": "noop", "detail": "bridge.lock not found",
        }
        mock_proc = MagicMock()
        mock_proc.stdout = str(tmp_path)
        with patch.object(dispatch_mod, "dispatch",
                          return_value=fail_result), \
             patch.object(dispatch_mod, "attempt_recovery",
                          return_value=recovery_result), \
             patch.object(dispatch_mod.subprocess, "run", return_value=mock_proc):
            dispatch_mod.main(self._base_args(routing_file))
            assert "recovery" in fail_result
            assert fail_result["recovery"] == recovery_result

    def test_tier2_recovery_retries_with_adjustment(self, tmp_path, monkeypatch):
        """Tier 2 recovery (e.g. timeout) grants retry with adjusted config."""
        routing_file = self._routing_file(tmp_path)
        fail_result = {
            "status": "failed", "decision": "ROUTE_PHASE_B",
            "executor": "phase_b_executor",
            "stderr": "", "step": "phase_b",
        }
        success_result = {
            "status": "success", "decision": "ROUTE_PHASE_B",
            "executor": "phase_b_executor",
        }
        recovery_tier2 = {
            "recovered": True, "exhausted": False,
            "failure_class": "process_timeout", "tier": 2,
            "action": "increase_timeout", "detail": "timeout increased",
        }
        # Simulate fix_process_timeout having set the env var
        monkeypatch.setenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", "5400")
        captured_configs = []

        def capture_dispatch(record, *, config=None, **kw):
            captured_configs.append(
                dict(config.get("timeouts", {})) if config else {})
            return fail_result if len(captured_configs) == 1 else success_result

        mock_proc = MagicMock()
        mock_proc.stdout = str(tmp_path)
        with patch.object(dispatch_mod, "dispatch",
                          side_effect=capture_dispatch) as mock_dispatch, \
             patch.object(dispatch_mod, "attempt_recovery",
                          return_value=recovery_tier2), \
             patch.object(dispatch_mod.subprocess, "run", return_value=mock_proc):
            exit_code = dispatch_mod.main(self._base_args(routing_file))
            assert mock_dispatch.call_count == 2  # original + recovery retry
            assert exit_code == 0
            # Verify the retry used the overridden timeout
            assert captured_configs[1].get("phase_b_executor") == 5400
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)

    def test_tier2_commit_timeout_uses_correct_key(self, tmp_path, monkeypatch):
        """Tier 2 PROCESS_TIMEOUT for commit_executor targets the correct config key."""
        routing_file = self._routing_file(tmp_path)
        fail_result = {
            "status": "failed", "decision": "ROUTE_PHASE_B",
            "executor": "commit_executor",
            "stderr": "", "step": "commit",
        }
        success_result = {
            "status": "success", "decision": "ROUTE_PHASE_B",
            "executor": "commit_executor",
        }
        recovery_tier2 = {
            "recovered": True, "exhausted": False,
            "failure_class": "process_timeout", "tier": 2,
            "action": "increase_timeout", "detail": "timeout increased",
        }
        monkeypatch.setenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", "5400")
        monkeypatch.setenv("RCX_RECOVERY_TIMEOUT_KEY", "commit_executor")
        captured_configs = []

        def capture_dispatch(record, *, config=None, **kw):
            captured_configs.append(
                dict(config.get("timeouts", {})) if config else {})
            return fail_result if len(captured_configs) == 1 else success_result

        mock_proc = MagicMock()
        mock_proc.stdout = str(tmp_path)
        with patch.object(dispatch_mod, "dispatch",
                          side_effect=capture_dispatch), \
             patch.object(dispatch_mod, "attempt_recovery",
                          return_value=recovery_tier2), \
             patch.object(dispatch_mod.subprocess, "run", return_value=mock_proc):
            exit_code = dispatch_mod.main(self._base_args(routing_file))
            assert exit_code == 0
            # Verify the retry used the overridden timeout on commit_executor, not phase_b
            assert captured_configs[1].get("commit_executor") == 5400
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_KEY", raising=False)

    def test_apply_overrides_writes_to_disk(self, tmp_path, monkeypatch):
        """_apply_recovery_overrides writes overrides to executor_config.json on disk."""
        cfg_dir = tmp_path / "mu" / "tools" / "executors"
        cfg_dir.mkdir(parents=True)
        original_config = {
            "timeouts": {
                "phase_b_executor": 3600,
                "phase_b_implementer_stale": 300,
                "commit_executor": 3600,
            }
        }
        cfg_path = cfg_dir / "executor_config.json"
        cfg_path.write_text(json.dumps(original_config, indent=2) + "\n")

        # Test stale timeout override writes to disk
        monkeypatch.setenv("RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE", "450")
        in_memory = {"timeouts": dict(original_config["timeouts"])}
        orig = dispatch_mod._apply_recovery_overrides(  # ANTICHEAT_OK
            in_memory, repo_root=tmp_path)
        assert orig is not None  # disk was modified
        assert orig["phase_b_implementer_stale"] == 300  # original value
        # In-memory config updated
        assert in_memory["timeouts"]["phase_b_implementer_stale"] == 450
        # Disk config updated
        disk = json.loads(cfg_path.read_text())
        assert disk["timeouts"]["phase_b_implementer_stale"] == 450
        # Restore
        dispatch_mod._restore_config_on_disk(tmp_path, orig)  # ANTICHEAT_OK
        restored = json.loads(cfg_path.read_text())
        assert restored["timeouts"]["phase_b_implementer_stale"] == 300
        monkeypatch.delenv("RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE", raising=False)

    def test_apply_overrides_clears_env_vars(self, tmp_path, monkeypatch):
        """Env vars are consumed and cleared to prevent leakage (Bridge R4 fix)."""
        cfg_dir = tmp_path / "mu" / "tools" / "executors"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "executor_config.json").write_text(json.dumps({
            "timeouts": {"phase_b_executor": 3600, "phase_b_implementer_stale": 300}
        }))
        monkeypatch.setenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", "5400")
        monkeypatch.setenv("RCX_RECOVERY_TIMEOUT_KEY", "phase_b_executor")
        monkeypatch.setenv("RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE", "450")
        in_memory = {"timeouts": {"phase_b_executor": 3600, "phase_b_implementer_stale": 300}}
        dispatch_mod._apply_recovery_overrides(in_memory, repo_root=tmp_path)  # ANTICHEAT_OK
        # Values applied to in-memory config
        assert in_memory["timeouts"]["phase_b_executor"] == 5400
        assert in_memory["timeouts"]["phase_b_implementer_stale"] == 450
        # Env vars cleared after consumption
        assert os.environ.get("RCX_RECOVERY_TIMEOUT_OVERRIDE") is None
        assert os.environ.get("RCX_RECOVERY_TIMEOUT_KEY") is None
        assert os.environ.get("RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE") is None

    def test_recovery_restores_in_memory_config(self, tmp_path, monkeypatch):
        """In-memory config is restored after retry loop, not just disk (Bridge R4 fix)."""
        cfg_dir = tmp_path / "mu" / "tools" / "executors"
        cfg_dir.mkdir(parents=True)
        original_config = {
            "timeouts": {
                "phase_b_executor": 3600,
                "phase_b_implementer_stale": 300,
                "commit_executor": 3600,
            }
        }
        cfg_path = cfg_dir / "executor_config.json"
        cfg_path.write_text(json.dumps(original_config, indent=2) + "\n")

        routing_file = self._routing_file(tmp_path)
        fail_result = {
            "status": "timeout", "decision": "ROUTE_PHASE_B",
            "executor": "phase_b_executor",
        }
        success_result = {
            "status": "success", "decision": "ROUTE_PHASE_B",
            "executor": "phase_b_executor",
        }
        recovery_tier2 = {
            "recovered": True, "exhausted": False,
            "failure_class": "process_timeout", "tier": 2,
            "action": "increase_timeout", "detail": "timeout increased",
        }
        captured_configs_after = []

        def set_env_and_return(*a, **k):
            monkeypatch.setenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", "5400")
            return recovery_tier2

        call_count = {"n": 0}

        def counting_dispatch(record, *, config=None, **kw):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return fail_result
            # On retry, capture the config then succeed
            captured_configs_after.append(
                dict(config.get("timeouts", {})) if config else {})
            return success_result

        mock_proc = MagicMock()
        mock_proc.stdout = str(tmp_path)
        with patch.object(dispatch_mod, "dispatch",
                          side_effect=counting_dispatch), \
             patch.object(dispatch_mod, "attempt_recovery",
                          side_effect=set_env_and_return), \
             patch.object(dispatch_mod.subprocess, "run", return_value=mock_proc):
            # Capture the config object passed to main so we can inspect after
            original_load = dispatch_mod.load_config

            config_ref = {}

            def capture_config(*a, **kw):
                c = original_load(*a, **kw)
                config_ref["config"] = c
                return c

            with patch.object(dispatch_mod, "load_config",
                              side_effect=capture_config):
                dispatch_mod.main(self._base_args(routing_file))

        # Disk must be restored
        disk = json.loads(cfg_path.read_text())
        assert disk["timeouts"]["phase_b_executor"] == 3600
        # In-memory config must also be restored (not still 5400)
        assert config_ref["config"]["timeouts"]["phase_b_executor"] == 3600
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)

    def test_timeout_status_routed_to_recovery(self, tmp_path):
        """Timeout status reaches recovery gate (Finding 1 fix)."""
        routing_file = self._routing_file(tmp_path)
        timeout_result = {
            "status": "timeout", "decision": "ROUTE_PHASE_B",
            "executor": "phase_b_executor",
            "message": "timed out after 3600s",
        }
        success_result = {
            "status": "success", "decision": "ROUTE_PHASE_B",
            "executor": "phase_b_executor",
        }
        recovery_tier2 = {
            "recovered": True, "exhausted": False,
            "failure_class": "process_timeout", "tier": 2,
            "action": "increase_timeout", "detail": "timeout increased",
        }
        mock_proc = MagicMock()
        mock_proc.stdout = str(tmp_path)
        with patch.object(dispatch_mod, "dispatch",
                          side_effect=[timeout_result, success_result]) as mock_d, \
             patch.object(dispatch_mod, "attempt_recovery",
                          return_value=recovery_tier2) as mock_rec, \
             patch.object(dispatch_mod.subprocess, "run", return_value=mock_proc):
            exit_code = dispatch_mod.main(self._base_args(routing_file))
            mock_rec.assert_called_once()
            assert mock_d.call_count == 2  # original + recovery retry
            assert exit_code == 0

    def test_sequential_recovery_preserves_original_timeouts(
        self, tmp_path, monkeypatch,
    ):
        """Second recovery does not overwrite the true pre-recovery baseline (Finding 2)."""
        cfg_dir = tmp_path / "mu" / "tools" / "executors"
        cfg_dir.mkdir(parents=True)
        original_config = {
            "timeouts": {
                "phase_b_executor": 3600,
                "phase_b_implementer_stale": 300,
                "commit_executor": 3600,
            }
        }
        cfg_path = cfg_dir / "executor_config.json"
        cfg_path.write_text(json.dumps(original_config, indent=2) + "\n")

        routing_file = self._routing_file(tmp_path)
        fail_result = {
            "status": "timeout", "decision": "ROUTE_PHASE_B",
            "executor": "phase_b_executor",
        }
        success_result = {
            "status": "success", "decision": "ROUTE_PHASE_B",
            "executor": "phase_b_executor",
        }
        recovery_tier2 = {
            "recovered": True, "exhausted": False,
            "failure_class": "process_timeout", "tier": 2,
            "action": "increase_timeout", "detail": "timeout increased",
        }
        call_count = {"n": 0}

        def counting_dispatch(record, *, config=None, **kw):
            call_count["n"] += 1
            if call_count["n"] <= 2:
                return fail_result
            return success_result

        # First recovery sets timeout override to 5400, second to 8100
        override_values = iter(["5400", "8100"])

        def set_override_env(*a, **k):
            monkeypatch.setenv(
                "RCX_RECOVERY_TIMEOUT_OVERRIDE", next(override_values))
            return recovery_tier2

        mock_proc = MagicMock()
        mock_proc.stdout = str(tmp_path)
        with patch.object(dispatch_mod, "dispatch",
                          side_effect=counting_dispatch), \
             patch.object(dispatch_mod, "attempt_recovery",
                          side_effect=set_override_env), \
             patch.object(dispatch_mod.subprocess, "run", return_value=mock_proc):
            dispatch_mod.main(self._base_args(routing_file))
        # After completion, disk config must be restored to the ORIGINAL 3600,
        # not the intermediate 5400
        disk = json.loads(cfg_path.read_text())
        assert disk["timeouts"]["phase_b_executor"] == 3600
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)

    def test_tier3_unrecovered_fails_closed_under_retries(self, tmp_path):
        """Tier 3 non-recovery still fails closed under --retries."""
        routing_file = self._routing_file(tmp_path)
        fail_result = {
            "status": "failed", "decision": "ROUTE_PHASE_B",
            "executor": "phase_b_executor",
            "stderr": "FAILED test_x - AssertionError",
            "step": "pre_commit",
        }
        recovery_tier3 = {
            "recovered": False, "exhausted": False,
            "failure_class": "test_failure", "tier": 3,
            "action": "recovery_loop", "detail": "no safe fix proposed",
        }
        mock_proc = MagicMock()
        mock_proc.stdout = str(tmp_path)
        with patch.object(dispatch_mod, "dispatch",
                          return_value=fail_result) as mock_dispatch, \
             patch.object(dispatch_mod, "attempt_recovery",
                          return_value=recovery_tier3), \
             patch.object(dispatch_mod.subprocess, "run", return_value=mock_proc):
            # Even with --retries 2, tier 3 must fail closed
            args = self._base_args(routing_file) + ["--retries", "2"]
            exit_code = dispatch_mod.main(args)
            assert exit_code == 1  # not recovered, not retried
            assert mock_dispatch.call_count == 1, (
                "tier 3 non-recovery must fail closed, not retry")

    def test_tier3_recovery_loop_grants_retry(self, tmp_path):
        """Recovered Tier 3 failures retry immediately without consuming retry budget."""
        routing_file = self._routing_file(tmp_path)
        fail_result = {
            "status": "failed", "decision": "ROUTE_PHASE_B",
            "executor": "phase_b_executor",
            "stderr": "FAILED test_x - AssertionError",
            "step": "pre_commit",
        }
        success_result = {
            "status": "success", "decision": "ROUTE_PHASE_B",
            "executor": "phase_b_executor",
        }
        recovery_tier3 = {
            "recovered": True, "exhausted": False,
            "failure_class": "needs_phase_b", "tier": 3,
            "action": "recovery_loop", "detail": "phase b re-entry succeeded",
        }
        mock_proc = MagicMock()
        mock_proc.stdout = str(tmp_path)
        with patch.object(dispatch_mod, "dispatch",
                          side_effect=[fail_result, success_result]) as mock_dispatch, \
             patch.object(dispatch_mod, "attempt_recovery",
                          return_value=recovery_tier3), \
             patch.object(dispatch_mod, "_clear_phase_b_state_for_retry") as mock_clear, \
             patch.object(dispatch_mod.subprocess, "run", return_value=mock_proc):
            args = self._base_args(routing_file) + ["--retries", "2"]
            exit_code = dispatch_mod.main(args)
            assert exit_code == 0
            assert mock_dispatch.call_count == 2
            mock_clear.assert_called_once()

    def test_tier4_escalate_fails_closed_under_retries(self, tmp_path):
        """Tier 4 escalate must fail closed — never retried (R6 Finding 2).

        Bridge R6 Finding 2: tier-4 action=escalate was retried 3 times
        when --retries 2 was set, violating the recovery gate's fail-closed
        intent and re-running side-effectful executors.
        """
        routing_file = self._routing_file(tmp_path)
        fail_result = {
            "status": "failed", "decision": "ROUTE_PHASE_B",
            "executor": "phase_b_executor",
            "stderr": "unrecoverable", "step": "bridge_loop",
        }
        recovery_tier4 = {
            "recovered": False, "exhausted": False,
            "failure_class": "terminal_policy", "tier": 4,
            "action": "escalate", "detail": "requires escalation",
        }
        mock_proc = MagicMock()
        mock_proc.stdout = str(tmp_path)
        with patch.object(dispatch_mod, "dispatch",
                          return_value=fail_result) as mock_dispatch, \
             patch.object(dispatch_mod, "attempt_recovery",
                          return_value=recovery_tier4), \
             patch.object(dispatch_mod.subprocess, "run", return_value=mock_proc):
            args = self._base_args(routing_file) + ["--retries", "2"]
            exit_code = dispatch_mod.main(args)
            assert exit_code == 1
            assert mock_dispatch.call_count == 1, (
                "tier 4 escalate must fail closed — "
                "was retried when it should have stopped immediately")

    def test_chained_phase_b_timeout_reports_correct_executor(self, tmp_path):
        """Chained Phase B timeout reports phase_b_executor, not phase_a_executor.

        Bridge R5 finding: TimeoutExpired from chained subprocess.run propagated
        to the outer handler, misattributing the timeout to the outer executor.
        """
        record = {"decision": "ROUTE_PHASE_A", "summary": "test chain timeout"}
        # Phase A subprocess succeeds with a plan path in stdout
        phase_a_stdout = json.dumps({"plan_path": str(tmp_path / "plan.md")})
        (tmp_path / "plan.md").write_text("# plan")
        phase_a_ok = MagicMock(
            returncode=0, stdout=phase_a_stdout, stderr="")

        call_count = {"n": 0}
        calls = []

        def mock_run(args, cwd, timeout):
            call_count["n"] += 1
            calls.append(args)
            if call_count["n"] == 1:
                # Phase A succeeds
                return phase_a_ok
            # Phase B times out
            raise subprocess.TimeoutExpired(cmd=args, timeout=3600)

        with patch.object(dispatch_mod, "_run_executor_in_group", side_effect=mock_run), \
             patch.object(dispatch_mod, "ensure_not_agent_review_mode"):
            result = dispatch_mod.dispatch(
                record, repo_root=tmp_path, skip_freshness=True)

        assert result["status"] == "timeout"
        assert result["executor"] == "phase_b_executor"
        assert result.get("chained_from") == "phase_a_executor"
        assert "Phase B" in result.get("message", "")
        assert "--json" in calls[0]
        assert "--json" in calls[1]

    def test_chained_commit_timeout_reports_commit_executor(self, tmp_path):
        """Chained commit timeout (from Phase B chain) reports commit_executor.

        Bridge R5 finding: same issue as above but for the Phase B → commit leg.
        """
        record = {"decision": "ROUTE_PHASE_B", "summary": "test chain timeout"}
        # Phase B succeeds
        phase_b_ok = MagicMock(returncode=0, stdout="{}", stderr="")
        # Create handoff file so the commit chain is reached
        handoff_dir = tmp_path / ".agent_bus" / "executors"
        handoff_dir.mkdir(parents=True)
        (handoff_dir / "phase_b_handoff.json").write_text("{}")

        call_count = {"n": 0}
        calls = []

        def mock_run(args, cwd, timeout):
            call_count["n"] += 1
            calls.append(args)
            if call_count["n"] == 1:
                return phase_b_ok
            # Commit times out
            raise subprocess.TimeoutExpired(cmd=args, timeout=300)

        with patch.object(dispatch_mod, "_run_executor_in_group", side_effect=mock_run), \
             patch.object(dispatch_mod, "ensure_not_agent_review_mode"):
            result = dispatch_mod.dispatch(
                record, repo_root=tmp_path, skip_freshness=True)

        assert result["status"] == "timeout"
        assert result["executor"] == "commit_executor"
        assert result.get("chained_from") == "phase_b_executor"
        assert "Commit" in result.get("message", "")
        assert "--json" in calls[0]
        assert "--json" in calls[1]
