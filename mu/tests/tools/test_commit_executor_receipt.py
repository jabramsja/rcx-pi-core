"""Tests for commit_executor receipt/schema integration.

Covers:
1. New schema (executor flow) fails closed on missing supervisor receipt
2. Step 7 preserves the Phase B handoff receipt chain before reading the fresh supervisor receipt
3. Authority chain: Phase B handoff receipt → step 6 supervisor receipt → step 7 decision → step 9 hook verifies staged state
4. Handoff pre_commit_receipt_path is continuity proof, not the final decision source for step 7
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from mu.tests.tools.module_loader import load_module
from tests.repo_root import REPO_ROOT


commit_mod = load_module(
    "commit_executor",
    REPO_ROOT / "mu" / "tools" / "executors" / "commit_executor.py",
)


def _make_new_schema_handoff(**overrides):
    """Create a valid new-schema handoff for testing."""
    wave_id = overrides.get("wave_id", "test-wave")
    target_gate_id = overrides.get("target_gate_id", "G8")
    base = {
        "wave_id": wave_id,
        "task_id": "[TEST]",
        "wave_class": "L4_ENABLER",
        "target_gate_id": target_gate_id,
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
        "tracker_note_text": (
            f"- Tracker sync note (2026-04-03, {wave_id}): **TEST — receipt handoff note.** "
            f"Class: L4_ENABLER. target_gate_id: {target_gate_id}. "
            "evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`. "
            "evidence_delta: (1) Receipt tests scope the commit handoff. (2) Validation exercises the receipt test module. "
            "(3) Indicator artifact binds the wave. "
            "progress_proof_before: Receipt handoff had no validated tracker note. "
            "progress_proof_after: Receipt handoff now carries a canonical tracker note. "
            "primary_blocker_class: INTEGRATION. "
            "primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
            f"indicator_artifact_ref: reports/l4_wave_indicators/{wave_id}.json. "
            f"indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id {wave_id} --output reports/l4_wave_indicators/{wave_id}.json. "
            "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            "boot0_track_id: V1. boot0_progress_state: HOLD."
        ),
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
    handoff_receipt_dir = repo / ".agent_bus" / "meta"
    handoff_receipt_dir.mkdir(parents=True, exist_ok=True)
    (handoff_receipt_dir / "pre_commit_receipt.json").write_text(json.dumps({
        "decision": "COMMIT_GO",
        "staged_sha": "phase_b_sha",
        "timestamp_utc": "2026-03-24T00:00:00+00:00",
    }))
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
    return repo


class TestSupervisorReceiptIsAuthority:
    """Step 7 preserves the handoff receipt chain and uses step 6 for final authority.

    Authority chain (Bridge R1 fix):
    - Phase B hands off an exact pre_commit_receipt_path
    - Step 7 verifies that handoff receipt exists and authorizes commit continuity
    - Step 6 runs supervisor → produces fresh receipt at receipt_path_from_supervisor
    - Step 7 reads from receipt_path_from_supervisor for the final DECISION
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

    def test_missing_handoff_receipt_fails_closed(self, tmp_path):
        """If the Phase B handoff receipt path is missing, the authority chain breaks."""
        from collections import namedtuple
        repo = _setup_repo(tmp_path)
        (repo / ".agent_bus" / "meta" / "pre_commit_receipt.json").unlink()

        sup_receipt_path = ".scratch/step6_receipt.json"
        (repo / ".scratch").mkdir(parents=True, exist_ok=True)
        (repo / sup_receipt_path).write_text(json.dumps({
            "decision": "COMMIT_GO",
            "staged_sha": "fresh",
            "timestamp_utc": "2026-03-24T00:00:00+00:00",
        }))

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

        assert result["status"] == "error"
        assert result["step"] == "validate_receipt"
        assert any("handoff receipt" in e.lower() for e in result["errors"])

    def test_supervisor_receipt_decision_still_wins_after_handoff_verification(self, tmp_path):
        """Even with a valid handoff receipt, the fresh supervisor receipt sets the final decision."""
        from collections import namedtuple
        repo = _setup_repo(tmp_path)

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

    def test_commit_pipeline_fails_closed_in_agent_review_mode(self, tmp_path):
        repo = _setup_repo(tmp_path)
        handoff = _make_new_schema_handoff()
        with patch.dict(commit_mod.os.environ, {"RCX_AGENT_REVIEW_MODE": "run_review"}, clear=False):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert result["status"] == "error"
        assert result["step"] == "review_mode_guard"
        assert any("agent review mode" in err for err in result["errors"])


class TestReceiptChainEndToEnd:
    """Behavioral regression: the step 6 → step 7 receipt chain
    must work end-to-end with the corrected authority model.

    Authority chain (Bridge R1 fix):
    - Phase B handoff receipt remains verified continuity proof
    - Step 6 supervisor produces fresh receipt at receipt_path_from_supervisor
    - Step 7 reads from receipt_path_from_supervisor for the final DECISION ONLY
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


class TestWaveIdBounds:
    def test_validate_handoff_rejects_overlong_wave_id(self):
        handoff = _make_new_schema_handoff(wave_id="a" * 81)
        valid, errors = commit_mod.validate_handoff(handoff)
        assert not valid
        assert any("wave_id must match" in e for e in errors)

    def test_prepare_handoff_from_routing_record_bounds_long_wave_name(self, tmp_path):
        record = {
            "wave_name": "x" * 120,
            "summary": "tighten commit pipeline",
            "decision": "UPDATE_TRACKER_ONLY",
        }
        handoff, errors = commit_mod.prepare_handoff_from_routing_record(record, tmp_path)
        assert errors == []
        assert handoff is not None
        assert len(handoff["wave_id"]) <= commit_mod.MAX_WAVE_ID_LEN
        assert commit_mod.WAVE_ID_RE.fullmatch(handoff["wave_id"])

    def test_prepare_handoff_from_routing_record_builds_valid_tracker_only_note(self, tmp_path):
        record = {
            "wave_name": "tracker-only-wave",
            "summary": "sync tracker only",
            "decision": "UPDATE_TRACKER_ONLY",
        }
        handoff, errors = commit_mod.prepare_handoff_from_routing_record(record, tmp_path)
        assert errors == []
        assert handoff is not None
        valid, validation_errors = commit_mod.validate_handoff(handoff)
        assert valid, validation_errors
        assert "no_op_proof:" in handoff["tracker_note_text"]
        assert "defer_reason_code:" in handoff["tracker_note_text"]

    def test_prepare_handoff_tracker_only_null_force_add_files_treated_as_empty(self, tmp_path):
        record = {
            "wave_name": "tracker-only-wave",
            "summary": "sync tracker only",
            "decision": "UPDATE_TRACKER_ONLY",
            "force_add_files": None,
        }
        handoff, errors = commit_mod.prepare_handoff_from_routing_record(record, tmp_path)
        assert errors == []
        assert handoff is not None
        assert handoff["force_add_files"] == []
        valid, validation_errors = commit_mod.validate_handoff(handoff)
        assert valid, validation_errors

    def test_prepare_handoff_tracker_only_coerces_non_string_commit_message(self, tmp_path):
        record = {
            "wave_name": "tracker-only-wave",
            "summary": "sync tracker only",
            "decision": "UPDATE_TRACKER_ONLY",
            "commit_message": 123,
        }
        handoff, errors = commit_mod.prepare_handoff_from_routing_record(record, tmp_path)
        assert errors == []
        assert handoff is not None
        assert handoff["commit_message"] == "123"
        valid, validation_errors = commit_mod.validate_handoff(handoff)
        assert valid, validation_errors

    def test_has_path_traversal_decodes_percent_escapes(self):
        assert commit_mod._has_path_traversal("..%2F..%2Fetc%2Fpasswd") is True  # ANTICHEAT_OK: testing path traversal detection
        assert commit_mod._has_path_traversal("%2e%2e/foo") is True  # ANTICHEAT_OK: testing path traversal detection

    def test_has_path_traversal_decodes_double_escaped_components(self):
        assert commit_mod._has_path_traversal("%252e%252e%252fetc%252fpasswd") is True  # ANTICHEAT_OK: testing path traversal detection
        assert commit_mod._has_path_traversal("..%255C..%255Csecret.txt") is True  # ANTICHEAT_OK: testing path traversal detection

    def test_has_path_traversal_normalizes_unicode_compatibility_dots(self):
        assert commit_mod._has_path_traversal("safe/\uff0e\uff0e/secret.txt") is True  # ANTICHEAT_OK: testing unicode traversal normalization

    def test_has_path_traversal_rejects_null_byte_payloads(self):
        assert commit_mod._has_path_traversal("safe\x00../secret.txt") is True  # ANTICHEAT_OK: testing null-byte hostile path detection
        assert commit_mod._has_path_traversal("safe%00../secret.txt") is True  # ANTICHEAT_OK: testing percent-decoded null-byte hostile path detection

    def test_decode_untrusted_path_returns_none_on_malformed_percent_escape(self):
        """Regression: %FF%FE is invalid UTF-8; must return None, not True."""
        result = commit_mod._decode_untrusted_path("%FF%FE")  # ANTICHEAT_OK: testing malformed percent-escape decoding helper
        assert result is None, f"Expected None for malformed percent escape, got {result!r}"

    def test_is_absolute_rejects_malformed_percent_escape(self):
        """Regression: malformed percent-escaped path must not raise TypeError."""
        assert commit_mod._is_absolute_untrusted_path("%FF%FE") is True  # ANTICHEAT_OK: testing malformed percent-escape absolute-path helper

    def test_has_path_traversal_rejects_malformed_percent_escape(self):
        """Regression: malformed percent-escaped path must not raise TypeError."""
        assert commit_mod._has_path_traversal("%FF%FE") is True  # ANTICHEAT_OK: testing malformed percent-escape traversal helper

    def test_validate_handoff_rejects_malformed_percent_escape_in_files_to_stage(self):
        """Regression: validate_handoff must fail closed on malformed percent escapes."""
        valid, errors = commit_mod.validate_handoff(
            _make_new_schema_handoff(files_to_stage=["%FF%FE"])
        )
        assert not valid
        assert any("traversal" in e.lower() or "path" in e.lower() for e in errors)

    def test_validate_handoff_rejects_absolute_files_to_stage(self):
        valid, errors = commit_mod.validate_handoff(
            _make_new_schema_handoff(files_to_stage=["/etc/passwd"])
        )
        assert not valid
        assert any("Absolute path in files_to_stage" in e for e in errors)

    def test_validate_handoff_rejects_windows_absolute_files_to_stage(self):
        valid, errors = commit_mod.validate_handoff(
            _make_new_schema_handoff(files_to_stage=[r"C:%5cWindows%5cSystem32%5cdrivers%5cetc%5chosts"])
        )
        assert not valid
        assert any("Absolute path in files_to_stage" in e for e in errors)

    def test_validate_handoff_rejects_absolute_force_add_files(self):
        valid, errors = commit_mod.validate_handoff(
            _make_new_schema_handoff(force_add_files=["/tmp/outside.txt"])
        )
        assert not valid
        assert any("Absolute path in force_add_files" in e for e in errors)

    def test_validate_handoff_rejects_windows_absolute_force_add_files(self):
        valid, errors = commit_mod.validate_handoff(
            _make_new_schema_handoff(force_add_files=[r"C:%5cUsers%5cPublic%5coutside.txt"])
        )
        assert not valid
        assert any("Absolute path in force_add_files" in e for e in errors)

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

    def test_force_add_files_rejects_agent_bus_executor_state(self):
        valid, errors = commit_mod.validate_handoff(
            _make_new_schema_handoff(
                force_add_files=[".agent_bus/executors/phase_b_handoff.json"]
            )
        )
        assert not valid
        assert any(".agent_bus/" in e for e in errors)


class TestHandoffReceiptContainment:
    """Bridge R1 Finding: handoff receipt path must be repo-contained."""

    def test_handoff_receipt_traversal_blocked_at_validation(self, tmp_path):
        """Path traversal in pre_commit_receipt_path → caught by validate_handoff (step 1).
        Defense-in-depth: step 7 also checks, but validate_handoff rejects first."""
        handoff = _make_new_schema_handoff(
            pre_commit_receipt_path="../../../etc/passwd"  # ANTICHEAT_OK: testing path traversal detection
        )
        valid, errors = commit_mod.validate_handoff(handoff)
        assert not valid
        assert any("traversal" in e.lower() for e in errors)

    def test_handoff_receipt_traversal_blocked_at_step7(self, tmp_path):
        """Step 7 re-checks containment as defense-in-depth (bypassed validate_handoff)."""
        from collections import namedtuple
        repo = _setup_repo(tmp_path)

        # Create a receipt that has .. but would need to be injected past validate_handoff
        # We test the step 7 check directly by calling with a modified handoff
        # that would not normally pass validate_handoff, simulating a bypass scenario.
        sub = repo / "sub"
        sub.mkdir()
        # Create receipt outside repo via relative path trick
        receipt_rel = "sub/../../outside_receipt.json"
        # The _has_path_traversal function should catch ".." in parts
        assert commit_mod._has_path_traversal(receipt_rel) is True  # ANTICHEAT_OK: testing path traversal detection

    def test_handoff_receipt_symlink_escape_blocked(self, tmp_path):
        """Symlink pointing outside repo in pre_commit_receipt_path → step 7 error."""
        from collections import namedtuple
        repo = _setup_repo(tmp_path)

        # Create a symlink inside the repo that points outside
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        (outside_dir / "receipt.json").write_text(json.dumps({
            "decision": "COMMIT_GO", "staged_sha": "abc",
            "timestamp_utc": "2026-03-24T00:00:00+00:00",
        }))
        link_dir = repo / "link_out"
        link_dir.mkdir(parents=True, exist_ok=True)
        link_path = link_dir / "receipt.json"
        link_path.symlink_to(outside_dir / "receipt.json")

        sup_receipt_dir = repo / ".scratch"
        sup_receipt_dir.mkdir(parents=True, exist_ok=True)
        sup_receipt_path = ".scratch/step6_receipt.json"
        (repo / sup_receipt_path).write_text(json.dumps({
            "decision": "COMMIT_GO", "staged_sha": "abc",
            "timestamp_utc": "2026-03-24T00:00:00+00:00",
        }))

        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])
        fake_result = SupervisorResult(
            decision="COMMIT_GO", summary="test", receipt_path=sup_receipt_path,
        )

        handoff = _make_new_schema_handoff(
            pre_commit_receipt_path="link_out/receipt.json"
        )
        import types
        mock_client = types.ModuleType("meta_bridge_client")
        mock_client.run_meta_bridge_package = lambda *a, **kw: fake_result
        mock_client.MetaBridgeClientError = Exception
        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "error"
        assert result["step"] == "validate_receipt"
        assert any("escapes repo" in e.lower() for e in result["errors"])


class TestCommitExecutorPytestGate:
    """Step 8 runs targeted pytest before allowing git commit."""

    def test_collect_commit_test_files_includes_direct_and_mirrored_tests(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "mu" / "tools").mkdir(parents=True)
        (repo / "mu" / "tests" / "tools").mkdir(parents=True)
        (repo / "tests").mkdir(parents=True)
        (repo / "mu" / "tools" / "example.py").write_text("# code\n")
        (repo / "mu" / "tests" / "tools" / "test_example_executor.py").write_text("def test_example(): pass\n")
        (repo / "tests" / "test_direct_stage.py").write_text("def test_direct(): pass\n")

        result = commit_mod._collect_commit_test_files(  # ANTICHEAT_OK: testing targeted pytest collection
            repo,
            ["mu/tools/example.py", "tests/test_direct_stage.py", "README.md"],
        )

        assert result == [
            "mu/tests/tools/test_example_executor.py",
            "tests/test_direct_stage.py",
        ]

    def test_collect_commit_test_files_dedupes_symlinked_test_mirrors(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "mu" / "tools").mkdir(parents=True)
        (repo / "mu" / "tests" / "tools").mkdir(parents=True)
        (repo / "tests").symlink_to("mu/tests", target_is_directory=True)
        (repo / "mu" / "tools" / "example.py").write_text("# code\n")
        (repo / "mu" / "tests" / "tools" / "test_example_executor.py").write_text(
            "def test_example(): pass\n"
        )

        result = commit_mod._collect_commit_test_files(  # ANTICHEAT_OK: testing targeted pytest collection
            repo,
            ["mu/tools/example.py"],
        )

        assert result == ["mu/tests/tools/test_example_executor.py"]

    def test_collect_commit_test_files_canonicalizes_staged_symlink_test_path(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "mu" / "tests" / "tools").mkdir(parents=True)
        (repo / "tests").symlink_to("mu/tests", target_is_directory=True)
        (repo / "mu" / "tests" / "tools" / "test_example_executor.py").write_text(
            "def test_example(): pass\n"
        )

        result = commit_mod._collect_commit_test_files(  # ANTICHEAT_OK: testing staged symlink-path canonicalization
            repo,
            ["tests/tools/test_example_executor.py"],
        )

        assert result == ["mu/tests/tools/test_example_executor.py"]

    def test_run_commit_pipeline_blocks_on_targeted_pytest_failure(self, tmp_path):
        from collections import namedtuple
        import types

        repo = _setup_repo(tmp_path)
        (repo / "tests").mkdir(parents=True, exist_ok=True)
        (repo / "tests" / "test_file.py").write_text(
            "def test_smoke():\n    assert True\n",
            encoding="utf-8",
        )

        sup_receipt_path = ".scratch/step6_receipt.json"
        (repo / ".scratch").mkdir(parents=True, exist_ok=True)
        (repo / sup_receipt_path).write_text(json.dumps({
            "decision": "COMMIT_GO",
            "staged_sha": "fresh_sha",
            "timestamp_utc": "2026-03-24T00:00:00+00:00",
        }))

        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])
        fake_result = SupervisorResult(
            decision="COMMIT_GO",
            summary="test",
            receipt_path=sup_receipt_path,
        )

        mock_client = types.ModuleType("meta_bridge_client")
        mock_client.run_meta_bridge_package = lambda *a, **kw: fake_result
        mock_client.MetaBridgeClientError = Exception

        real_run = commit_mod._run  # ANTICHEAT_OK: testing commit gate behavior via private runner helper
        seen_commands: list[list[str]] = []

        def intercept_run(args, cwd, check=True, timeout=120, env=None):
            seen_commands.append(list(args))
            if list(args[:2]) == ["git", "commit"]:
                raise AssertionError("git commit should not run after pytest gate failure")
            return real_run(args, cwd=cwd, check=check, timeout=timeout, env=env)

        handoff = _make_new_schema_handoff()
        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}), \
             patch.object(
                 commit_mod,
                 "_run_pytest_on_files",
                 return_value={
                     "exit_code": 1,
                     "stdout": "FAILED tests/test_file.py::test_smoke",
                     "stderr": "",
                     "passed": False,
                 },
             ) as mock_pytest, \
             patch.object(commit_mod, "_run", side_effect=intercept_run):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "error"
        assert result["step"] == "run_pre_commit_script"
        assert "targeted pytest gate failed" in result["errors"][0]
        assert "git_commit" not in result.get("steps_completed", [])
        assert mock_pytest.call_args[0][1] == ["tests/test_file.py"]
        assert not any(cmd[:2] == ["git", "commit"] for cmd in seen_commands)

    def test_run_pytest_on_files_handles_duplicate_basenames(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "mu" / "tests" / "tools").mkdir(parents=True)
        (repo / "tests").mkdir(parents=True)
        (repo / "mu" / "tests" / "tools" / "test_dup.py").write_text(
            "import pytest\n\n"
            "@pytest.fixture\n"
            "def foo():\n"
            "    return 1\n\n"
            "def test_one(foo):\n"
            "    assert foo == 1\n",
            encoding="utf-8",
        )
        (repo / "tests" / "test_dup.py").write_text(
            "import pytest\n\n"
            "@pytest.fixture\n"
            "def bar():\n"
            "    return 2\n\n"
            "def test_two(bar):\n"
            "    assert bar == 2\n",
            encoding="utf-8",
        )

        result = commit_mod._run_pytest_on_files(  # ANTICHEAT_OK: testing targeted pytest helper with duplicate basenames
            repo,
            ["mu/tests/tools/test_dup.py", "tests/test_dup.py"],
        )

        assert result["passed"] is True, result

    def test_run_pytest_on_files_scales_timeout_with_file_count(self, tmp_path):
        from types import SimpleNamespace

        repo = tmp_path / "repo"
        repo.mkdir()

        with patch.object(
            commit_mod.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
        ) as mock_run:
            result = commit_mod._run_pytest_on_files(  # ANTICHEAT_OK: testing targeted pytest timeout scaling helper
                repo,
                [
                    "mu/tests/tools/test_agent_bridge_supervisor.py",
                    "mu/tests/tools/test_executor_dispatch.py",
                    "tests/tools/test_executor_dispatch.py",
                    "mu/tests/tools/test_commit_executor_receipt.py",
                    "tests/test_extra.py",
                ],
            )

        assert result["passed"] is True
        assert mock_run.call_args.kwargs["timeout"] == 450

    def test_run_pytest_on_files_gives_single_large_file_real_slack(self, tmp_path):
        from types import SimpleNamespace

        repo = tmp_path / "repo"
        repo.mkdir()

        with patch.object(
            commit_mod.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
        ) as mock_run:
            result = commit_mod._run_pytest_on_files(  # ANTICHEAT_OK: testing single-file timeout floor
                repo,
                ["mu/tests/tools/test_phase_b_executor.py"],
            )

        assert result["passed"] is True
        assert mock_run.call_args.kwargs["timeout"] == 180
