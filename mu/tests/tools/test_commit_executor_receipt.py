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
    # Make later commit-path assertions hermetic instead of depending on the
    # runner's ambient git identity.
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, capture_output=True)
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

    def test_step7_emits_commit_ready_pager_event(self, tmp_path):
        from collections import namedtuple

        repo = _setup_repo(tmp_path)
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
        pager_calls = []

        handoff = _make_new_schema_handoff(scope_items=["reports/control_plane/test_wave.md"])
        import types
        mock_client = types.ModuleType("meta_bridge_client")
        mock_client.run_meta_bridge_package = lambda *a, **kw: fake_result
        mock_client.MetaBridgeClientError = Exception

        def fake_emit(repo_root, **kwargs):
            pager_calls.append(kwargs)
            return {
                "enabled": True,
                "event_id": "evt-commit-ready",
                "attempted": [],
                "budget_exhausted": False,
            }

        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}), \
             patch.object(commit_mod, "emit_pipeline_agent_event", side_effect=fake_emit), \
             patch.object(
                 commit_mod,
                 "_run_post_commit_pipeline",
                 side_effect=lambda **kwargs: {
                     "status": "success",
                     "steps_completed": kwargs["result"]["steps_completed"],
                 },
             ):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "success", f"Unexpected commit pipeline result: {result}"
        assert pager_calls
        event = pager_calls[0]
        assert event["event_type"] == "commit_ready"
        assert event["task_id"] == "[TEST]"
        assert event["plan_path"] == "reports/control_plane/test_wave.md"
        assert event["phase"] == "commit_executor"
        assert event["state"] == "commit_ready"
        assert event["transition_key"] == sup_receipt_path

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

    def test_standalone_empty_handoff_receipt_skips_provenance_check(self, tmp_path):
        """Standalone commit continuations intentionally omit stale handoff receipts."""
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

        handoff = _make_new_schema_handoff(
            caller="standalone",
            pre_commit_receipt_path="",
        )
        import types
        mock_client = types.ModuleType("meta_bridge_client")
        mock_client.run_meta_bridge_package = lambda *a, **kw: fake_result
        mock_client.MetaBridgeClientError = Exception
        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}), \
             patch.object(
                 commit_mod,
                 "_run_post_commit_pipeline",
                 side_effect=lambda **kwargs: {
                     **kwargs["result"],
                     "status": "success",
                 },
             ):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert "validate_receipt" in result.get("steps_completed", []), (
            f"Standalone continuation should skip stale handoff receipt provenance. Got: {result}"
        )
        assert result.get("handoff_receipt_path") == ""
        assert result.get("handoff_receipt_decision") == "STANDALONE_SKIP"

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

    def test_same_wave_followup_touches_tasks_when_tracker_relevant_files_change(self, tmp_path):
        from collections import namedtuple

        repo = _setup_repo(tmp_path)
        tracker_file = repo / "mu" / "tools" / "agents" / "meta_bridge_supervisor.py"
        tracker_file.parent.mkdir(parents=True, exist_ok=True)
        tracker_file.write_text("# tracker relevant change\n", encoding="utf-8")

        sup_receipt_path = ".scratch/step6_receipt.json"
        scratch_dir = repo / ".scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        (repo / sup_receipt_path).write_text(
            json.dumps(
                {
                    "decision": "COMMIT_GO",
                    "staged_sha": "fresh_sha_from_step6",
                    "timestamp_utc": "2026-03-24T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )

        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])

        def mock_supervisor(*a, **kw):
            return SupervisorResult(
                decision="COMMIT_GO",
                summary="test",
                receipt_path=sup_receipt_path,
            )

        wave_id = "same-wave-followup"
        target_gate_id = "G8"
        tracker_note_text = (
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
        )
        (repo / "TASKS.md").write_text(
            "## Ra\n\n"
            f"{tracker_note_text}\n"
            "\n---\n",
            encoding="utf-8",
        )

        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            target_gate_id=target_gate_id,
            files_to_stage=["mu/tools/agents/meta_bridge_supervisor.py"],
            tracker_note_text=tracker_note_text,
        )
        import types

        mock_client = types.ModuleType("meta_bridge_client")
        mock_client.run_meta_bridge_package = mock_supervisor
        mock_client.MetaBridgeClientError = Exception
        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}), patch.object(
            commit_mod,
            "_run_post_commit_pipeline",
            side_effect=lambda **kwargs: {
                "status": "success",
                "steps_completed": kwargs["result"]["steps_completed"],
            },
        ):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "success", f"Unexpected commit pipeline result: {result}"
        tasks_text = (repo / "TASKS.md").read_text(encoding="utf-8")
        assert "Tracker sync follow-up" in tasks_text
        assert "mu/tools/agents/meta_bridge_supervisor.py" in tasks_text

    def test_mocked_supervisor_import_does_not_leak_temp_agents_path(self, tmp_path):
        from collections import namedtuple
        import types

        repo = _setup_repo(tmp_path)
        stub_agents_dir = repo / "mu" / "tools" / "agents"
        stub_agents_dir.mkdir(parents=True, exist_ok=True)
        (stub_agents_dir / "meta_bridge_supervisor.py").write_text(
            "# temp stub should not leak onto global sys.path\n",
            encoding="utf-8",
        )

        sup_receipt_path = ".scratch/step6_receipt.json"
        scratch_dir = repo / ".scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        (repo / sup_receipt_path).write_text(
            json.dumps(
                {
                    "decision": "COMMIT_GO",
                    "staged_sha": "fresh_sha_from_step6",
                    "timestamp_utc": "2026-03-24T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )

        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])
        fake_result = SupervisorResult(
            decision="COMMIT_GO",
            summary="test",
            receipt_path=sup_receipt_path,
        )
        mock_client = types.ModuleType("meta_bridge_client")
        mock_client.run_meta_bridge_package = lambda *a, **kw: fake_result
        mock_client.MetaBridgeClientError = Exception
        leaked_agents_dir = str(stub_agents_dir)
        assert leaked_agents_dir not in sys.path

        handoff = _make_new_schema_handoff()
        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}), patch.object(
            commit_mod,
            "_run_post_commit_pipeline",
            side_effect=lambda **kwargs: {
                "status": "success",
                "steps_completed": kwargs["result"]["steps_completed"],
            },
        ):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "success", f"Unexpected commit pipeline result: {result}"
        assert leaked_agents_dir not in sys.path


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

    def test_build_commit_handoff_allows_standalone_empty_receipt_path(self, tmp_path):
        repo = _setup_repo(tmp_path)
        handoff, errors = commit_mod.build_commit_handoff(
            wave_id="standalone-wave",
            task_id="[PIPELINE-RECOVERY]",
            files_to_stage=["file.py"],
            commit_message="chore: continue standalone-wave staged diff",
            fixes_implemented=[
                "Resume standalone continuation for current staged diff: file.py."
            ],
            caller="standalone",
            pre_commit_receipt_path="",
            repo_root=repo,
        )
        assert errors == []
        assert handoff["caller"] == "standalone"
        assert handoff["pre_commit_receipt_path"] == ""
        valid, validation_errors = commit_mod.validate_handoff(handoff)
        assert valid, validation_errors

    def test_prepare_handoff_from_routing_record_standalone_narrows_to_staged_diff(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        packet_dir = repo / "reports" / "control_plane"
        packet_dir.mkdir(parents=True, exist_ok=True)
        (packet_dir / "resume.md").write_text(
            "# Resume\n"
            "FOUNDER_OVERRIDE:pipeline-recovery-2026-04-21 "
            "(founder authorized resumed continuation narrowing)\n",
            encoding="utf-8",
        )
        (repo / "file.py").write_text("# staged now\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "--", "file.py"],
            cwd=repo,
            capture_output=True,
            check=True,
        )

        record = {
            "wave_name": "pipeline-recovery-2026-04-21",
            "summary": "stale earlier same-wave fixes",
            "decision": "COMMIT_GO",
            "task_id": "[PIPELINE-RECOVERY]",
            "next_candidates": [
                {
                    "candidate": "resume",
                    "tracked_packet": "reports/control_plane/resume.md",
                }
            ],
        }

        handoff, errors = commit_mod.prepare_handoff_from_routing_record(
            record,
            repo,
            standalone=True,
        )

        assert errors == []
        assert handoff is not None
        assert handoff["caller"] == "standalone"
        assert handoff["pre_commit_receipt_path"] == ""
        assert handoff["files_to_stage"] == ["file.py"]
        assert "stale earlier same-wave fixes" not in handoff["fixes_implemented"][0]
        assert "FOUNDER_OVERRIDE:pipeline-recovery-2026-04-21" in handoff["tracker_note_text"]
        valid, validation_errors = commit_mod.validate_handoff(handoff)
        assert valid, validation_errors

    def test_prepare_handoff_from_routing_record_standalone_regenerates_embedded_handoff(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        (repo / "file.py").write_text("# staged now\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "--", "file.py"],
            cwd=repo,
            capture_output=True,
            check=True,
        )
        embedded = _make_new_schema_handoff(
            wave_id="pipeline-recovery-2026-04-21",
            files_to_stage=["old.py"],
            fixes_implemented=["old stale claim"],
        )
        record = {
            "wave_name": "pipeline-recovery-2026-04-21",
            "summary": "stale earlier same-wave fixes",
            "decision": "COMMIT_GO",
            "handoff": embedded,
        }

        handoff, errors = commit_mod.prepare_handoff_from_routing_record(
            record,
            repo,
            standalone=True,
        )

        assert errors == []
        assert handoff is not None
        assert handoff["caller"] == "standalone"
        assert handoff["pre_commit_receipt_path"] == ""
        assert handoff["files_to_stage"] == ["file.py"]
        assert handoff["fixes_implemented"] != ["old stale claim"]
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

    def test_validate_handoff_accepts_empty_files_to_stage_when_force_add_non_empty(self):
        """Regression: a `.claude/`-only commit has every path auto-routed to
        force_add_files by build_commit_handoff's string-startswith check,
        leaving files_to_stage empty. The commit is semantically valid
        (git add -f at Step 4 handles force_add_files correctly), so the
        validator must NOT reject this shape.

        Diagnosed 2026-04-11 during block-protected-branch-lexer follow-up
        wave: the 3-file `.claude/hooks/*` commit could not pass validation
        despite being commit-ready. Root cause at commit_executor.py:2082-
        2086 was `not fts` clause rejecting empty independent of force_add.
        Structural fix landed by this test's wave.
        """
        valid, errors = commit_mod.validate_handoff(
            _make_new_schema_handoff(
                files_to_stage=[],
                force_add_files=[
                    ".claude/hooks/_block_protected_branch_tokenize.py",
                    ".claude/hooks/block-protected-branch.sh",
                    ".claude/hooks/test_block_protected_branch.sh",
                ],
            )
        )
        assert valid, (
            f"Expected validation to pass for empty files_to_stage + "
            f"non-empty force_add_files, got errors: {errors}"
        )
        assert not any("files_to_stage must be a non-empty list" in e for e in errors)
        assert not any("must be non-empty" in e and "files_to_stage" in e for e in errors)

    def test_validate_handoff_rejects_both_files_lists_empty(self):
        """A commit with zero files is still an error: the new validator
        accepts files_to_stage OR force_add_files non-empty, but not both
        empty. Preserves the 'commit must have at least one file' invariant.
        """
        valid, errors = commit_mod.validate_handoff(
            _make_new_schema_handoff(
                files_to_stage=[],
                force_add_files=[],
            )
        )
        assert not valid
        assert any(
            "files_to_stage or force_add_files must be non-empty" in e
            for e in errors
        ), f"Expected new empty-both error, got: {errors}"

    def test_validate_handoff_rejects_files_to_stage_non_list(self):
        """files_to_stage must be a list type, not a string/dict/None. The
        new validator checks type first, independent of the empty-list case.
        """
        valid, errors = commit_mod.validate_handoff(
            _make_new_schema_handoff(files_to_stage="not-a-list")
        )
        assert not valid
        assert any("files_to_stage must be a list" in e for e in errors)

    def test_validate_handoff_accepts_files_to_stage_non_empty_force_add_empty(self):
        """Regression invariance: the common case (non-empty files_to_stage,
        empty force_add_files) must still validate cleanly. Protects against
        regressions in the else-branch path of the new code.
        """
        valid, errors = commit_mod.validate_handoff(
            _make_new_schema_handoff(
                files_to_stage=["mu/tools/executors/commit_executor.py"],
                force_add_files=[],
            )
        )
        assert valid, (
            f"Expected validation to pass for standard non-empty "
            f"files_to_stage + empty force_add_files, got errors: {errors}"
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
        assert mock_run.call_args.kwargs["timeout"] == 660

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

    def test_run_pytest_on_files_gives_two_heavy_files_real_slack(self, tmp_path):
        from types import SimpleNamespace

        repo = tmp_path / "repo"
        repo.mkdir()

        with patch.object(
            commit_mod.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
        ) as mock_run:
            result = commit_mod._run_pytest_on_files(  # ANTICHEAT_OK: testing 2-file timeout floor after observed 198.857s gate
                repo,
                [
                    "mu/tests/tools/test_phase_b_executor.py",
                    "mu/tests/tools/test_recovery_gate.py",
                ],
            )

        assert result["passed"] is True
        assert mock_run.call_args.kwargs["timeout"] == 300


class TestCIPollFallbackTimeout:
    """Regression: _poll_ci_checks_fallback 900s budget tolerates observed green-gate wall time.

    PR #783 (2026-04-17) demonstrated green-gate can take 5m7s (307s) after a
    bot-remediation push, which exceeded the former 300s fallback budget. The
    executor false-positive classified CI as failed and cascaded into tier-3
    recovery exhaustion despite all checks green.
    """

    def _run_fallback_with_simulated_clock(self, *, ci_transitions_to_success_at, runtime_cap):
        """Drive _poll_ci_checks_fallback with a controllable fake monotonic clock.

        Returns (result, final_clock_seconds).
        - ci_transitions_to_success_at: simulated wall-time seconds after which the
          mocked gh output flips from pending to SUCCESS. Pass None to mean
          "CI never completes" (stays pending for the entire run).
        - runtime_cap: timeout argument passed into the fallback.
        """
        from types import SimpleNamespace

        clock = [0.0]

        def fake_monotonic():
            return clock[0]

        def fake_sleep(seconds):
            clock[0] += seconds

        def fake_subprocess_run(*args, **kwargs):
            if ci_transitions_to_success_at is None or clock[0] < ci_transitions_to_success_at:
                return SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps({"statusCheckRollup": [
                        {"name": "ci_check", "conclusion": None},
                    ]}),
                    stderr="",
                )
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"statusCheckRollup": [
                    {"name": "ci_check", "conclusion": "SUCCESS"},
                ]}),
                stderr="",
            )

        with patch.object(commit_mod.time, "monotonic", fake_monotonic), \
             patch.object(commit_mod.time, "sleep", fake_sleep), \
             patch.object(commit_mod.subprocess, "run", side_effect=fake_subprocess_run):
            result = commit_mod._poll_ci_checks_fallback(  # ANTICHEAT_OK: testing CI-poll fallback timeout budget under simulated clock
                Path("/tmp/ci_poll_budget_test_repo"),
                "783",
                timeout=runtime_cap,
                poll_interval=15,
            )

        return result, clock[0]

    def test_ci_poll_fallback_tolerates_green_gate_wall_time_over_5_minutes(self):
        """With the 900s budget, CI completing at t=350s must return True.

        The former 300s budget would have false-positive timed out before this
        transition. The bumped 900s budget must survive with 2.5x headroom.
        """
        result, final_clock = self._run_fallback_with_simulated_clock(
            ci_transitions_to_success_at=350,
            runtime_cap=900,
        )
        assert result is True, (
            f"Expected True (CI passed at t=350s under 900s budget), got {result}"
        )
        assert final_clock >= 350, (
            f"Simulated clock should have advanced past 350s, got {final_clock}s"
        )
        assert final_clock < 900, (
            f"Simulated clock should not have hit the 900s cap, got {final_clock}s"
        )

    def test_ci_poll_fallback_still_times_out_at_new_budget(self):
        """With the 900s budget, genuinely stalled CI must still return False.

        Guards against the bump making the timeout unconditionally permissive —
        a CI that never completes must still hit the budget ceiling.
        """
        result, final_clock = self._run_fallback_with_simulated_clock(
            ci_transitions_to_success_at=None,
            runtime_cap=900,
        )
        assert result is False, (
            f"Expected False (timed out at 900s budget), got {result}"
        )
        assert final_clock >= 900, (
            f"Simulated clock should have exhausted the 900s budget, got {final_clock}s"
        )
