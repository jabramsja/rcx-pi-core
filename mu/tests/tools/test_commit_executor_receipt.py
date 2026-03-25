"""Tests for commit_executor receipt/schema integration.

Covers:
1. New schema (executor flow) fails closed on missing supervisor receipt
2. Step 7 reads from supervisor receipt (step 6 output), NOT handoff pre_commit_receipt_path
3. Authority chain: Step 6 supervisor → receipt → step 7 decision → step 9 hook verifies staged state
4. Handoff pre_commit_receipt_path is NOT the authority for step 7
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.repo_root import REPO_ROOT


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


commit_mod = _load_module(
    "commit_executor",
    REPO_ROOT / "mu" / "tools" / "executors" / "commit_executor.py",
)


def _make_new_schema_handoff(**overrides):
    """Create a valid new-schema handoff for testing."""
    base = {
        "wave_id": "test-wave",
        "task_id": "[TEST]",
        "wave_class": "L4_ENABLER",
        "target_gate_id": "G8",
        "caller": "phase_b",
        "branch_prefix": "jabramsja",
        "files_to_stage": ["file.py"],
        "force_add_files": [],
        "commit_message": "feat: test\n\nCo-Authored-By: test",
        "pr_title": "feat: test",
        "pr_body": "## Summary\ntest",
        "base_branch": "dev",
        "pre_commit_receipt_path": ".agent_bus/meta/pre_commit_receipt.json",
        "fixes_implemented": ["test fix"],
        "tracker_note_text": "- Tracker sync note (test-wave): test",
    }
    base.update(overrides)
    return base


def _setup_repo(tmp_path):
    """Create a minimal git repo for pipeline tests."""
    import subprocess
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        **__import__("os").environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "checkout", "-b", "dev"], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=repo, capture_output=True, env=env)
    (repo / "TASKS.md").write_text("## Ra\n\n- Tracker sync note (seed): init\n\n---\n")
    (repo / "file.py").write_text("# test")
    return repo


class TestSupervisorReceiptIsAuthority:
    """Step 7 uses the supervisor's receipt from step 6 as authority.

    Authority chain (Bridge R1 fix):
    - Step 6 runs supervisor → produces fresh receipt at receipt_path_from_supervisor
    - Step 7 reads from receipt_path_from_supervisor for DECISION
    - Step 7 does NOT read from handoff pre_commit_receipt_path (stale)
    - Step 9 pre-commit hook verifies staged state independently
    """

    def test_step7_reads_supervisor_receipt(self, tmp_path):
        """Step 7 reads from the supervisor receipt path, not the handoff path.
        When the supervisor receipt exists with COMMIT_GO, step 7 passes.
        """
        from collections import namedtuple
        repo = _setup_repo(tmp_path)

        # Create supervisor receipt at the path the supervisor returns
        sup_receipt_dir = repo / ".agent_bus" / "meta" / "pre_commit_receipts"
        sup_receipt_dir.mkdir(parents=True, exist_ok=True)
        sup_receipt_path = ".agent_bus/meta/pre_commit_receipts/receipt_step6.json"
        (repo / sup_receipt_path).write_text(json.dumps({
            "decision": "COMMIT_GO", "staged_sha": "abc",
            "timestamp_utc": "2026-03-24T00:00:00+00:00",
        }))

        # Handoff receipt does NOT exist — but step 7 should NOT care
        # because it reads from supervisor receipt, not handoff path

        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])
        fake_result = SupervisorResult(
            decision="COMMIT_GO", summary="test", receipt_path=sup_receipt_path,
        )

        handoff = _make_new_schema_handoff()
        import types
        mock_client = types.ModuleType("meta_bridge_client")
        mock_client.run_meta_bridge_package = lambda *a, **kw: fake_result
        mock_client.MetaBridgeClientError = Exception
        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        # Step 7 should pass reading from supervisor receipt
        assert "validate_receipt" in result.get("steps_completed", []), (
            f"Step 7 should succeed reading supervisor receipt. Got: {result}"
        )

    def test_missing_supervisor_receipt_fails_closed(self, tmp_path):
        """If the supervisor's receipt doesn't exist on disk, step 7 fails closed."""
        from collections import namedtuple
        repo = _setup_repo(tmp_path)

        # Supervisor returns a receipt path that does NOT exist on disk
        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])
        fake_result = SupervisorResult(
            decision="COMMIT_GO", summary="test",
            receipt_path=".scratch/nonexistent_receipt.json",
        )

        handoff = _make_new_schema_handoff()
        import types
        mock_client = types.ModuleType("meta_bridge_client")
        mock_client.run_meta_bridge_package = lambda *a, **kw: fake_result
        mock_client.MetaBridgeClientError = Exception
        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "error"
        assert result["step"] == "validate_receipt"
        assert any("not found" in e.lower() or "receipt" in e.lower() for e in result["errors"])

    def test_handoff_receipt_not_used_at_step7(self, tmp_path):
        """Even if handoff receipt exists, step 7 reads supervisor receipt.
        When supervisor receipt has HOLD and handoff has GO, the HOLD wins.
        """
        from collections import namedtuple
        repo = _setup_repo(tmp_path)

        # Handoff receipt says COMMIT_GO
        handoff_receipt_dir = repo / ".agent_bus" / "meta"
        handoff_receipt_dir.mkdir(parents=True, exist_ok=True)
        (handoff_receipt_dir / "pre_commit_receipt.json").write_text(json.dumps({
            "decision": "COMMIT_GO", "staged_sha": "x",
            "timestamp_utc": "2026-03-24T00:00:00+00:00",
        }))

        # Supervisor receipt says COMMIT_GO_HOLD_PUSH
        sup_receipt_dir = repo / ".scratch"
        sup_receipt_dir.mkdir(parents=True, exist_ok=True)
        sup_receipt_path = ".scratch/step6_receipt.json"
        (repo / sup_receipt_path).write_text(json.dumps({
            "decision": "COMMIT_GO_HOLD_PUSH", "staged_sha": "y",
            "timestamp_utc": "2026-03-24T00:00:00+00:00",
        }))

        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])
        fake_result = SupervisorResult(
            decision="COMMIT_GO_HOLD_PUSH", summary="hold", receipt_path=sup_receipt_path,
        )

        handoff = _make_new_schema_handoff()
        import types
        mock_client = types.ModuleType("meta_bridge_client")
        mock_client.run_meta_bridge_package = lambda *a, **kw: fake_result
        mock_client.MetaBridgeClientError = Exception
        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        # The supervisor's HOLD decision should win (not the handoff GO)
        completed = result.get("steps_completed", [])
        assert "validate_receipt" in completed
        # Pipeline should reach hold_check and return held
        if "git_commit" in completed:
            assert result.get("status") == "held"


class TestReceiptChainEndToEnd:
    """Behavioral regression: the step 6 → step 7 receipt chain
    must work end-to-end with the corrected authority model.

    Authority chain (Bridge R1 fix):
    - Step 6 supervisor produces fresh receipt at receipt_path_from_supervisor
    - Step 7 reads from receipt_path_from_supervisor for DECISION ONLY
    - Step 7 does NOT check staged_sha (step 9 hook handles that)
    """

    def test_receipt_chain_survives_tasks_and_indicator_staging(self, tmp_path):
        """Full receipt chain: step 3 modifies TASKS.md, step 4 stages it,
        step 5 stages indicator, step 6 runs supervisor (mints fresh receipt),
        step 7 reads supervisor receipt for decision.
        """
        from collections import namedtuple
        repo = _setup_repo(tmp_path)
        (repo / "file.py").write_text("# changed code")

        # Create supervisor receipt
        sup_receipt_dir = repo / ".scratch"
        sup_receipt_dir.mkdir(parents=True, exist_ok=True)
        sup_receipt_path = ".scratch/step6_receipt.json"
        (repo / sup_receipt_path).write_text(json.dumps({
            "decision": "COMMIT_GO",
            "staged_sha": "fresh_sha_from_step6",
            "timestamp_utc": "2026-03-24T00:00:00+00:00",
        }))

        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])

        def mock_supervisor(*a, **kw):
            return SupervisorResult(
                decision="COMMIT_GO", summary="test",
                receipt_path=sup_receipt_path,
            )

        handoff = _make_new_schema_handoff()
        import types
        mock_client = types.ModuleType("meta_bridge_client")
        mock_client.run_meta_bridge_package = mock_supervisor
        mock_client.MetaBridgeClientError = Exception
        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        completed = result.get("steps_completed", [])
        assert "build_and_run_supervisor" in completed, f"Step 6 failed: {result}"
        assert "validate_receipt" in completed, (
            f"Step 7 should succeed reading supervisor receipt. Got: {result}"
        )

    def test_missing_supervisor_receipt_blocks_pipeline(self, tmp_path):
        """When supervisor receipt path doesn't exist on disk, step 7 fails closed."""
        from collections import namedtuple
        repo = _setup_repo(tmp_path)

        # Supervisor returns a path that does NOT exist
        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])
        fake_result = SupervisorResult(
            decision="COMMIT_GO", summary="test",
            receipt_path=".scratch/missing_receipt.json",
        )

        handoff = _make_new_schema_handoff()
        import types
        mock_client = types.ModuleType("meta_bridge_client")
        mock_client.run_meta_bridge_package = lambda *a, **kw: fake_result
        mock_client.MetaBridgeClientError = Exception
        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "error"
        assert result["step"] == "validate_receipt"
        assert any("not found" in e.lower() or "receipt" in e.lower() for e in result["errors"])


class TestNewSchemaValidation:
    """New schema handoff validation."""

    def test_valid_new_schema_passes(self):
        valid, errors = commit_mod.validate_handoff(_make_new_schema_handoff())
        assert valid, errors

    def test_missing_wave_id_fails(self):
        handoff = _make_new_schema_handoff()
        del handoff["wave_id"]
        valid, errors = commit_mod.validate_handoff(handoff)
        assert not valid

    def test_empty_branch_prefix_fails(self):
        valid, errors = commit_mod.validate_handoff(
            _make_new_schema_handoff(branch_prefix="")
        )
        assert not valid
        assert any("branch_prefix" in e for e in errors)

    def test_base_branch_must_be_dev(self):
        valid, errors = commit_mod.validate_handoff(
            _make_new_schema_handoff(base_branch="main")
        )
        assert not valid
        assert any("dev" in e for e in errors)
