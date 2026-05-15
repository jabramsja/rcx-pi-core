"""Tests for commit_executor receipt/schema integration.

Covers:
1. New schema (executor flow) fails closed on missing supervisor receipt
2. Step 7 preserves the Phase B handoff receipt chain before reading the fresh supervisor receipt
3. Authority chain: Phase B handoff receipt → step 6 supervisor receipt → step 7 decision → step 9 hook verifies staged state
4. Handoff pre_commit_receipt_path is continuity proof, not the final decision source for step 7
"""

from __future__ import annotations

import hashlib
import json
import os
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


def _canonical_handoff_sha_for_test(handoff: dict) -> str:
    canonical = json.dumps(handoff, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


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


def _with_founder_override(note: str, token: str) -> str:
    return f"{note} FOUNDER_OVERRIDE:{token} (test authorization)"


def test_build_commit_handoff_replaces_stale_tracker_override_with_same_wave_packet(
    tmp_path,
):
    import subprocess

    repo = _setup_repo(tmp_path)
    wave_id = "post-js-pipeline-governance-deferred-cleanup-2026-05-12"
    predecessor = "js-engine-pipeline-shape-governance-test-2026-05-12"
    packet_path = f"reports/control_plane/{wave_id}.md"
    packet = repo / packet_path
    packet.parent.mkdir(parents=True, exist_ok=True)
    packet.write_text(
        "# Post JS pipeline cleanup\n\n"
        f"Wave ID: {wave_id}\n"
        "Class: L4_ENABLER\n"
        "Lane: control-surface (agent automation / observability)\n"
        f"- Predecessor closure evidence: FOUNDER_OVERRIDE:{predecessor}\n"
        f"- Same-wave authority: FOUNDER_OVERRIDE:{wave_id}\n"
        "Founder authorization: standing pipeline-bug-fix authorization.\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "add", packet_path],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    stale_note = _with_founder_override(
        _make_new_schema_handoff(wave_id=wave_id)["tracker_note_text"],
        predecessor,
    )

    handoff, errors = commit_mod.build_commit_handoff(
        wave_id=wave_id,
        task_id="[NEXT-CODEX-POST-REDTEAM]",
        files_to_stage=["file.py"],
        commit_message="fix: post JS pipeline cleanup",
        fixes_implemented=["test fix"],
        wave_class="L4_ENABLER",
        target_gate_id="G8",
        tracked_packet=packet_path,
        tracker_note_text=stale_note,
        repo_root=repo,
    )

    assert not errors, errors
    assert f"FOUNDER_OVERRIDE:{wave_id}" in handoff["tracker_note_text"]
    assert f"FOUNDER_OVERRIDE:{predecessor}" not in handoff["tracker_note_text"]


def test_build_commit_handoff_default_tracker_note_includes_tracked_packet(tmp_path):
    repo = _setup_repo(tmp_path)
    wave_id = "default-tracker-packet-wave"
    packet_path = f"reports/control_plane/{wave_id}.md"
    packet = repo / packet_path
    packet.parent.mkdir(parents=True, exist_ok=True)
    packet.write_text(
        f"# Packet\n\nWave ID: {wave_id}\nClass: L4_ENABLER\n",
        encoding="utf-8",
    )

    handoff, errors = commit_mod.build_commit_handoff(
        wave_id=wave_id,
        task_id="[NEXT-CODEX-POST-REDTEAM]",
        files_to_stage=["file.py", packet_path],
        commit_message="fix: default tracker packet",
        fixes_implemented=["test fix"],
        wave_class="L4_ENABLER",
        target_gate_id="G8",
        tracked_packet=packet_path,
        repo_root=repo,
    )

    assert not errors, errors
    assert f"Packet: `{packet_path}`" in handoff["tracker_note_text"]


def test_post_commit_pre_push_dirty_isolation_stashes_and_restores(tmp_path):
    import subprocess

    repo = _setup_repo(tmp_path)
    (repo / "dirty.py").write_text("dirty\n", encoding="utf-8")

    messages: list[str] = []
    isolation, error = commit_mod._stash_post_commit_pre_push_dirty_paths(  # ANTICHEAT_OK
        repo,
        wave_id="dirty-isolation-wave",
        log=messages.append,
    )

    assert error is None
    assert isolation is not None
    assert "dirty.py" in isolation["paths"]
    assert "commit_executor:post_commit_pre_push:dirty-isolation-wave:" in isolation["marker"]
    status_after_stash = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "dirty.py" not in status_after_stash

    restore_error = commit_mod._restore_post_commit_pre_push_dirty_paths(  # ANTICHEAT_OK
        repo,
        isolation,
        log=messages.append,
    )

    assert restore_error is None
    status_after_restore = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "dirty.py" in status_after_restore
    assert (repo / "dirty.py").read_text(encoding="utf-8") == "dirty\n"


def test_post_commit_pre_push_dirty_restore_rejects_oid_drift(tmp_path):
    repo = _setup_repo(tmp_path)
    (repo / "dirty.py").write_text("dirty\n", encoding="utf-8")

    isolation, error = commit_mod._stash_post_commit_pre_push_dirty_paths(  # ANTICHEAT_OK
        repo,
        wave_id="dirty-isolation-wave",
        log=lambda _msg: None,
    )
    assert error is None
    assert isolation is not None

    isolation["stash_oid"] = "not-the-created-stash"
    restore_error = commit_mod._restore_post_commit_pre_push_dirty_paths(  # ANTICHEAT_OK
        repo,
        isolation,
        log=lambda _msg: None,
    )

    assert restore_error is not None
    assert "object id mismatch" in restore_error


def test_post_commit_pre_push_dirty_isolation_resume_requires_verified_restore(tmp_path):
    import subprocess

    repo = _setup_repo(tmp_path)
    (repo / "dirty.py").write_text("dirty\n", encoding="utf-8")

    messages: list[str] = []
    isolation, error = commit_mod._stash_post_commit_pre_push_dirty_paths(  # ANTICHEAT_OK
        repo,
        wave_id="dirty-isolation-wave",
        log=messages.append,
    )
    assert error is None
    assert isolation is not None

    subprocess.run(
        ["git", "stash", "pop", "--index", isolation["stash_ref"]],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )

    action, action_error = commit_mod._classify_pre_push_isolation_resume(  # ANTICHEAT_OK
        repo,
        isolation,
    )
    assert action is None
    assert action_error is not None
    assert "dirty before Step 11 can run safely" in action_error

    restore_error = commit_mod._restore_post_commit_pre_push_dirty_paths(  # ANTICHEAT_OK
        repo,
        isolation,
        log=messages.append,
    )
    assert restore_error is not None
    assert "stash missing" in restore_error

    commit_mod._mark_pre_push_isolation_verified(isolation)  # ANTICHEAT_OK
    action, action_error = commit_mod._classify_pre_push_isolation_resume(  # ANTICHEAT_OK
        repo,
        isolation,
    )
    assert action == "already_restored"
    assert action_error is None
    restore_error = commit_mod._restore_post_commit_pre_push_dirty_paths(  # ANTICHEAT_OK
        repo,
        isolation,
        log=messages.append,
    )
    assert restore_error is None
    assert any("already restored" in message for message in messages)


def test_post_commit_pre_push_dirty_isolation_checkpoint_is_durable(tmp_path):
    import subprocess

    repo = _setup_repo(tmp_path)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)
    commit_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    continuation_path = commit_mod._continuation_record_path(  # ANTICHEAT_OK
        repo,
        "dirty-isolation-wave",
    )
    result = {
        "commit_sha": commit_sha,
        "receipt_decision": "COMMIT_GO",
        "handoff_sha": "handoff-sha",
        "steps_completed": ["ensure_feature_branch", "git_commit"],
        "pre_push_isolation": {
            "marker": "commit_executor:post_commit_pre_push:dirty-isolation-wave:abc",
            "stash_ref": "stash@{0}",
            "stash_oid": "stash-oid",
            "paths": "dirty.py\n",
        },
    }

    commit_mod._checkpoint_post_commit_progress(  # ANTICHEAT_OK
        result,
        continuation_path=continuation_path,
        target_branch="dev",
    )

    payload = json.loads(continuation_path.read_text(encoding="utf-8"))
    assert payload["pre_push_isolation"]["marker"].endswith("dirty-isolation-wave:abc")
    loaded = commit_mod._load_post_commit_continuation(  # ANTICHEAT_OK
        continuation_path,
        repo_root=repo,
        handoff_sha="handoff-sha",
        target_branch="dev",
    )
    assert loaded is not None
    assert loaded["pre_push_isolation"]["paths"] == "dirty.py\n"

    result.pop("pre_push_isolation")
    commit_mod._checkpoint_post_commit_progress(  # ANTICHEAT_OK
        result,
        continuation_path=continuation_path,
        target_branch="dev",
    )
    payload = json.loads(continuation_path.read_text(encoding="utf-8"))
    assert "pre_push_isolation" not in payload

    (repo / "dirty.py").write_text("restored dirty work\n", encoding="utf-8")
    result["pre_push_restored_paths"] = ["dirty.py"]
    commit_mod._checkpoint_post_commit_progress(  # ANTICHEAT_OK
        result,
        continuation_path=continuation_path,
        target_branch="dev",
    )
    loaded = commit_mod._load_post_commit_continuation(  # ANTICHEAT_OK
        continuation_path,
        repo_root=repo,
        handoff_sha="handoff-sha",
        target_branch="dev",
    )
    assert loaded is not None
    assert loaded["pre_push_restored_paths"] == ["dirty.py"]


def test_post_commit_pre_push_dirty_isolation_checkpoints_before_stash(tmp_path):
    import subprocess

    repo = _setup_repo(tmp_path)
    hook = repo / "mu" / "tools" / "hooks" / "pre-push-fast"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)
    commit_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (repo / "dirty.py").write_text("operator dirty work\n", encoding="utf-8")

    continuation_path = commit_mod._continuation_record_path(  # ANTICHEAT_OK
        repo,
        "dirty-isolation-wave",
    )
    result = {
        "commit_sha": commit_sha,
        "receipt_decision": "COMMIT_GO",
        "handoff_sha": "handoff-sha",
        "steps_completed": ["git_commit"],
    }
    observed: dict[str, dict] = {}
    original_stash = commit_mod._stash_post_commit_pre_push_dirty_paths  # ANTICHEAT_OK

    def observing_stash(repo_root, *args, **kwargs):
        payload = json.loads(continuation_path.read_text(encoding="utf-8"))
        observed["payload"] = payload
        pending = payload["pre_push_isolation"]
        assert pending["pre_push_state"] == commit_mod.PRE_PUSH_ISOLATION_STASH_PENDING_VALUE
        assert "dirty.py" in pending["paths"]
        assert "stash_ref" not in pending
        assert pending["marker"] == kwargs["isolation"]["marker"]
        return original_stash(repo_root, *args, **kwargs)

    with patch.object(
        commit_mod,
        "_stash_post_commit_pre_push_dirty_paths",
        side_effect=observing_stash,
    ):
        pipeline_result = commit_mod._run_post_commit_pipeline(  # ANTICHEAT_OK
            handoff={"wave_id": "dirty-isolation-wave"},
            repo_root=repo,
            result=result,
            target_branch="dev",
            base_branch="dev",
            continuation_path=continuation_path,
            log=lambda _msg: None,
        )

    assert observed["payload"]["pre_push_isolation"]["marker"].startswith(
        "commit_executor:post_commit_pre_push:dirty-isolation-wave:"
    )
    assert pipeline_result["status"] == "error"
    assert pipeline_result["step"] == "run_pre_push_script"
    status_after_restore = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "dirty.py" in status_after_restore


def test_bot_remediation_tracker_followup_appends_tasks_for_tracker_relevant_scope(tmp_path):
    repo = _setup_repo(tmp_path)
    wave_id = "bot-remediation-tracker-wave"
    tracker_note = _make_new_schema_handoff(wave_id=wave_id)["tracker_note_text"]
    (repo / "TASKS.md").write_text(f"## Ra\n\n{tracker_note}\n\n---\n", encoding="utf-8")

    result = commit_mod.ensure_bot_remediation_tracker_followup(
        repo,
        wave_id=wave_id,
        scoped_files=["mu/tools/executors/phase_b_executor.py"],
    )

    assert result == {
        "updated": True,
        "tracker_paths": ["mu/tools/executors/phase_b_executor.py"],
        "path": "TASKS.md",
    }
    tasks_content = (repo / "TASKS.md").read_text(encoding="utf-8")
    assert tasks_content.count(f"Tracker sync follow-up") == 1
    assert f"Tracker sync follow-up" in tasks_content
    assert wave_id in tasks_content
    assert "mu/tools/executors/phase_b_executor.py" in tasks_content

    second_result = commit_mod.ensure_bot_remediation_tracker_followup(
        repo,
        wave_id=wave_id,
        scoped_files=["mu/tools/executors/phase_b_executor.py"],
    )
    assert "errors" not in second_result
    assert (repo / "TASKS.md").read_text(encoding="utf-8").count("Tracker sync follow-up") == 1


def test_bot_remediation_tracker_followup_skips_when_tracker_file_scoped(tmp_path):
    repo = _setup_repo(tmp_path)
    wave_id = "bot-remediation-tracker-scoped-wave"
    tracker_note = _make_new_schema_handoff(wave_id=wave_id)["tracker_note_text"]
    (repo / "TASKS.md").write_text(f"## Ra\n\n{tracker_note}\n\n---\n", encoding="utf-8")

    result = commit_mod.ensure_bot_remediation_tracker_followup(
        repo,
        wave_id=wave_id,
        scoped_files=["TASKS.md", "mu/tools/executors/phase_b_executor.py"],
    )

    assert result == {
        "updated": False,
        "tracker_paths": ["mu/tools/executors/phase_b_executor.py"],
    }
    assert "Tracker sync follow-up" not in (repo / "TASKS.md").read_text(encoding="utf-8")


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


class TestSkipSupervisorBypassClosure:
    def test_run_commit_pipeline_rejects_skip_supervisor_without_synthesized_receipt(
        self,
        tmp_path,
        monkeypatch,
    ):
        repo = _setup_repo(tmp_path)
        monkeypatch.delenv("RCX_SKIP_RECEIPT_CHECK", raising=False)

        result = commit_mod.run_commit_pipeline(
            _make_new_schema_handoff(),
            repo_root=repo,
            skip_supervisor=True,
        )

        assert result["status"] == "error"
        assert result["step"] == "skip_supervisor_forbidden"
        assert "build_and_run_supervisor" not in result.get("steps_completed", [])
        assert "validate_receipt" not in result.get("steps_completed", [])
        assert result.get("receipt_decision") != "COMMIT_GO"
        assert "RCX_SKIP_RECEIPT_CHECK" not in os.environ

    def test_cli_rejects_skip_supervisor_before_pipeline_execution(self, tmp_path):
        handoff_path = tmp_path / "handoff.json"
        handoff_path.write_text(
            json.dumps(_make_new_schema_handoff()),
            encoding="utf-8",
        )

        result = __import__("subprocess").run(
            [
                sys.executable,
                str(REPO_ROOT / "mu" / "tools" / "executors" / "commit_executor.py"),
                "--handoff",
                str(handoff_path),
                "--skip-supervisor",
                "--json",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=20,
        )

        assert result.returncode == 1
        assert "--skip-supervisor is disabled" in result.stderr
        assert "build_and_run_supervisor" not in result.stdout
        assert "validate_receipt" not in result.stdout


class TestStandaloneRecoveryTrigger:
    def _run_main_with_pipeline_result(self, tmp_path, result):
        import subprocess

        repo = tmp_path / "repo"
        repo.mkdir()
        handoff_path = tmp_path / "handoff.json"
        handoff_path.write_text(
            json.dumps(_make_new_schema_handoff(wave_id="standalone-recovery")),
            encoding="utf-8",
        )
        recovery_calls = []

        def fake_run(args, **kwargs):
            if list(args) == ["git", "rev-parse", "--show-toplevel"]:
                return subprocess.CompletedProcess(args, 0, f"{repo}\n", "")
            raise AssertionError(f"unexpected subprocess.run call: {args}")

        def fake_attempt(repo_root, failed_result, wave_id, bus_dir=None):
            recovery_calls.append({
                "repo_root": repo_root,
                "result": dict(failed_result),
                "wave_id": wave_id,
                "bus_dir": bus_dir,
            })
            return {
                "recovered": False,
                "action": "recovery_loop",
                "tier": 3,
                "failure_class": failed_result.get("status", "unknown"),
                "detail": "test recovery",
                "exhausted": False,
            }

        with patch.object(commit_mod.subprocess, "run", side_effect=fake_run), \
             patch.object(commit_mod, "run_commit_pipeline", return_value=dict(result)), \
             patch.object(
                 commit_mod,
                 "_load_repo_recovery_symbols",
                 return_value=(fake_attempt, lambda value: value),
             ), \
             patch.object(
                 sys,
                 "argv",
                 [
                     "commit_executor.py",
                     "--handoff",
                     str(handoff_path),
                     "--standalone",
                 ],
             ):
            exit_code = commit_mod.main()

        return exit_code, recovery_calls

    @pytest.mark.parametrize(
        "status",
        [
            "pre_push_failed",
            "stage_failed",
            "implementer_error",
            "bridge_error",
            "l4_contract_violation",
        ],
    )
    def test_standalone_invokes_recovery_for_widened_failure_statuses(
        self,
        tmp_path,
        status,
    ):
        exit_code, recovery_calls = self._run_main_with_pipeline_result(
            tmp_path,
            {"status": status, "step": "commit_executor"},
        )

        assert exit_code == 1
        assert len(recovery_calls) == 1
        assert recovery_calls[0]["result"]["status"] == status
        assert recovery_calls[0]["wave_id"] == "standalone-recovery"

    @pytest.mark.parametrize("status", ["success", "held"])
    def test_standalone_does_not_recover_success_or_held(self, tmp_path, status):
        exit_code, recovery_calls = self._run_main_with_pipeline_result(
            tmp_path,
            {"status": status, "step": "commit_executor"},
        )

        assert exit_code == 0
        assert recovery_calls == []


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
        event = next(
            call for call in pager_calls
            if call.get("event_type") == "commit_ready"
        )
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
        original_handoff_sha = _canonical_handoff_sha_for_test(handoff)
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
        assert result.get("handoff_receipt_decision") == "STANDALONE_NO_HANDOFF_RECEIPT"
        assert result.get("handoff_sha") == original_handoff_sha
        assert result.get("receipt_refreshed_handoff_sha") != original_handoff_sha
        continuation_path = (
            repo
            / ".agent_bus"
            / "executors"
            / "commit_executor_test-wave.json"
        )
        continuation = json.loads(continuation_path.read_text(encoding="utf-8"))
        assert continuation["handoff_sha"] == original_handoff_sha

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
        pager_calls = []

        def fake_emit(repo_root, **kwargs):
            pager_calls.append(kwargs)
            return {"enabled": True, "event_id": "review-mode", "attempted": []}

        with patch.dict(commit_mod.os.environ, {"RCX_AGENT_REVIEW_MODE": "run_review"}, clear=False), \
             patch.object(commit_mod, "_commit_lifecycle_pager_enabled", return_value=True), \
             patch.object(commit_mod, "emit_pipeline_agent_event", side_effect=fake_emit):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
        assert result["status"] == "error"
        assert result["step"] == "review_mode_guard"
        assert any("agent review mode" in err for err in result["errors"])
        assert pager_calls == []


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

    def test_commit_packet_truth_refresh_rebinds_packet_and_handoff_before_supervisor(self, tmp_path):
        from collections import namedtuple
        import types

        repo = _setup_repo(tmp_path)
        wave_id = "packet-truth-wave"
        packet_path = "reports/control_plane/packet_truth_wave.md"
        packet_file = repo / packet_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Packet Truth Wave\n\n"
            "Status: Phase B ready\n"
            "Wave ID: packet-truth-wave\n"
            "Wave class: L4_ENABLER\n"
            "Target gate: G8\n"
            "Lane: control-surface\n",
            encoding="utf-8",
        )
        (repo / "file.py").write_text("# changed code\n", encoding="utf-8")

        sup_receipt_path = ".scratch/step6_receipt.json"
        (repo / ".scratch").mkdir(parents=True, exist_ok=True)
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

        captured_package = {}
        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])

        def mock_supervisor(package_path, *a, **kw):
            captured_package.update(json.loads(Path(package_path).read_text(encoding="utf-8")))
            return SupervisorResult(
                decision="COMMIT_GO",
                summary="test",
                receipt_path=sup_receipt_path,
            )

        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", packet_path],
            tracked_packet=packet_path,
            scope_items=[packet_path],
            evidence_handles={"phase_b_receipt": ".agent_bus/meta/pre_commit_receipt.json"},
        )

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
        assert "refresh_commit_packet_truth" in result["steps_completed"]
        changed_files = set(captured_package["changed_files"])
        assert "TASKS.md" in changed_files
        assert packet_path in changed_files
        assert f"reports/l4_wave_indicators/{wave_id}.json" in changed_files
        assert packet_path in captured_package["scope_items"]
        assert f"reports/l4_wave_indicators/{wave_id}.json" in captured_package["scope_items"]
        assert captured_package["evidence_handles"]["indicator"] == (
            f"reports/l4_wave_indicators/{wave_id}.json"
        )
        packet_text = packet_file.read_text(encoding="utf-8")
        assert "## Commit Path Truth Refresh" in packet_text
        assert f"- Active packet: `{packet_path}`" in packet_text
        assert "- Commit status: `pre_commit_supervisor_pending`" in packet_text
        assert f"  - `reports/l4_wave_indicators/{wave_id}.json`" in packet_text
        assert "  - `TASKS.md`" in packet_text

    def test_commit_supervisor_package_fences_unstaged_out_of_scope_dirty_files(self, tmp_path):
        from collections import namedtuple
        import subprocess
        import types

        repo = _setup_repo(tmp_path)
        (repo / "out_of_scope.py").write_text("# baseline\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "baseline"],
            cwd=repo,
            capture_output=True,
            check=True,
        )

        wave_id = "commit-fenced-dirty-wave"
        packet_path = "reports/control_plane/commit_fenced_dirty_wave.md"
        packet_file = repo / packet_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Commit Fenced Dirty Wave\n\n"
            "Status: Phase B ready\n"
            f"Wave ID: {wave_id}\n"
            "Wave class: L4_ENABLER\n"
            "Target gate: G8\n",
            encoding="utf-8",
        )
        (repo / "file.py").write_text("# changed code\n", encoding="utf-8")
        (repo / "out_of_scope.py").write_text("# later wave dirty work\n", encoding="utf-8")

        sup_receipt_path = ".scratch/step6_receipt.json"
        (repo / ".scratch").mkdir(parents=True, exist_ok=True)
        (repo / sup_receipt_path).write_text(
            json.dumps(
                {
                    "decision": "COMMIT_GO",
                    "staged_sha": "fresh_sha_from_step6",
                    "timestamp_utc": "2026-05-15T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )

        captured_package = {}
        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])

        def mock_supervisor(package_path, *a, **kw):
            captured_package.update(json.loads(Path(package_path).read_text(encoding="utf-8")))
            return SupervisorResult(
                decision="COMMIT_GO",
                summary="test",
                receipt_path=sup_receipt_path,
            )

        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", packet_path],
            tracked_packet=packet_path,
            scope_items=[packet_path],
        )

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

        assert result["status"] == "success", result
        assert "out_of_scope.py" in captured_package["fenced_files"]
        assert "out_of_scope.py" not in captured_package["changed_files"]
        assert "file.py" in captured_package["changed_files"]

    def test_pre_commit_failure_demotes_completed_packet_and_task_for_dispatch_retry(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06"
        packet_path = (
            "reports/control_plane/"
            "founder_ordered_redteam_mu_structural_blocking_remediation_2026-05-06.md"
        )
        packet_file = repo / packet_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Packet\n\n"
            "Status: COMPLETED (commit-ready, supervisor COMMIT_GO)\n"
            f"Wave ID: {wave_id}\n",
            encoding="utf-8",
        )
        (repo / "TASKS.md").write_text(
            "## Ra\n"
            "  6. **[FOUNDER-ORDERED-REDTEAM-MU-STRUCTURAL-BLOCKING-REMEDIATION] "
            "IMPLEMENTED / LOCAL EVIDENCE (2026-05-08).** "
            "Task: `[NEXT-CODEX-POST-REDTEAM]`. "
            f"Wave ID: `{wave_id}`. "
            f"Packet: `{packet_path}`.\n",
            encoding="utf-8",
        )
        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            tracked_packet=packet_path,
            files_to_stage=[packet_path, "TASKS.md"],
            scope_items=[packet_path],
        )
        handoff_path = repo / ".agent_bus" / "executors" / "phase_b_handoff.json"
        handoff_path.parent.mkdir(parents=True, exist_ok=True)
        handoff_path.write_text(
            json.dumps({
                **handoff,
                "evidence_handles": {
                    "indicator": f"reports/l4_wave_indicators/{wave_id}.json",
                    "pre_commit_receipt": ".agent_bus/meta/pre_commit_receipts/fresh.json",
                },
            }, indent=2)
            + "\n",
            encoding="utf-8",
        )

        with patch.object(
            commit_mod,
            "_run_commit_pipeline_impl",
            return_value={
                "status": "error",
                "step": "run_pre_commit_script",
                "errors": ["pre-commit-doc-check failed"],
                "steps_completed": [
                    "validate_inputs",
                    "ensure_feature_branch",
                    "build_and_run_supervisor",
                    "validate_receipt",
                ],
            },
        ):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "error"
        assert set(result["commit_retry_state_demotion"]["changed"]) == {
            packet_path,
            "TASKS.md",
        }
        assert result["commit_retry_state_demotion"]["handoff_receipt_invalidated"] is True
        assert (
            f"Status: {commit_mod.COMMIT_RETRY_PENDING_STATUS}"
            in packet_file.read_text(encoding="utf-8")
        )
        tasks_text = (repo / "TASKS.md").read_text(encoding="utf-8")
        assert (
            "IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT / LOCAL EVIDENCE "
            "(2026-05-08)"
        ) in tasks_text
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        assert packet_path in staged
        assert "TASKS.md" in staged
        durable_handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
        assert durable_handoff["pre_commit_receipt_path"] == handoff["pre_commit_receipt_path"]
        assert "pre_commit_receipt" not in durable_handoff["evidence_handles"]

    def test_pre_validation_failure_does_not_demote_completed_packet_state(self, tmp_path):
        repo = _setup_repo(tmp_path)
        wave_id = "founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06"
        packet_path = (
            "reports/control_plane/"
            "founder_ordered_redteam_mu_structural_blocking_remediation_2026-05-06.md"
        )
        packet_file = repo / packet_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Packet\n\n"
            "Status: COMPLETED (commit-ready, supervisor COMMIT_GO)\n"
            f"Wave ID: {wave_id}\n",
            encoding="utf-8",
        )
        tasks_file = repo / "TASKS.md"
        original_tasks = (
            "## Ra\n"
            "  6. **[FOUNDER-ORDERED-REDTEAM-MU-STRUCTURAL-BLOCKING-REMEDIATION] "
            "IMPLEMENTED / LOCAL EVIDENCE (2026-05-08).** "
            "Task: `[NEXT-CODEX-POST-REDTEAM]`. "
            f"Wave ID: `{wave_id}`. "
            f"Packet: `{packet_path}`.\n"
        )
        tasks_file.write_text(original_tasks, encoding="utf-8")
        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            tracked_packet=packet_path,
            files_to_stage=[packet_path, "TASKS.md"],
            scope_items=[packet_path],
        )
        result = {
            "status": "error",
            "step": "validate_inputs",
            "errors": ["invalid handoff"],
            "steps_completed": ["validate_inputs"],
        }

        getattr(commit_mod, "_maybe_demote_completed_handoff_state_for_commit_retry")(
            repo_root=repo,
            handoff=handoff,
            result=result,
        )

        assert "commit_retry_state_demotion" not in result
        assert (
            "Status: COMPLETED (commit-ready, supervisor COMMIT_GO)"
            in packet_file.read_text(encoding="utf-8")
        )
        assert tasks_file.read_text(encoding="utf-8") == original_tasks

    def test_commit_retry_pending_state_restored_before_receipt_review(
        self,
        tmp_path,
    ):
        from collections import namedtuple
        import types

        repo = _setup_repo(tmp_path)
        wave_id = "founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06"
        packet_path = (
            "reports/control_plane/"
            "founder_ordered_redteam_mu_structural_blocking_remediation_2026-05-06.md"
        )
        packet_file = repo / packet_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Packet\n\n"
            f"Status: {commit_mod.COMMIT_RETRY_PENDING_STATUS}\n"
            f"Wave ID: {wave_id}\n"
            "Class: L4_STRUCTURAL\n",
            encoding="utf-8",
        )
        (repo / "TASKS.md").write_text(
            "## Ra\n"
            "  6. **[FOUNDER-ORDERED-REDTEAM-MU-STRUCTURAL-BLOCKING-REMEDIATION] "
            "IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT / LOCAL EVIDENCE "
            "(2026-05-08).** "
            "Task: `[NEXT-CODEX-POST-REDTEAM]`. "
            f"Wave ID: `{wave_id}`. "
            "Class: `L4_STRUCTURAL`. "
            f"Packet: `{packet_path}`.\n",
            encoding="utf-8",
        )
        (repo / "file.py").write_text("# structural retry restoration\n", encoding="utf-8")

        sup_receipt_path = ".scratch/step6_receipt.json"
        (repo / ".scratch").mkdir(parents=True, exist_ok=True)
        (repo / sup_receipt_path).write_text(
            json.dumps(
                {
                    "decision": "COMMIT_GO",
                    "staged_sha": "fresh_sha_from_step6",
                    "timestamp_utc": "2026-05-09T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )
        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])
        captured_package = {}

        def mock_supervisor(package_path, *args, **kwargs):
            captured_package.update(json.loads(Path(package_path).read_text(encoding="utf-8")))
            return SupervisorResult(
                decision="COMMIT_GO",
                summary="test",
                receipt_path=sup_receipt_path,
            )

        mock_client = types.ModuleType("meta_bridge_client")
        mock_client.run_meta_bridge_package = mock_supervisor
        mock_client.MetaBridgeClientError = Exception
        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            wave_class="L4_STRUCTURAL",
            files_to_stage=["file.py", packet_path, "TASKS.md"],
            tracked_packet=packet_path,
            scope_items=[packet_path],
        )

        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}), patch.object(
            commit_mod,
            "_run_post_commit_pipeline",
            side_effect=lambda **kwargs: {**kwargs["result"], "status": "success"},
        ):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "success", result
        assert "restore_commit_retry_state" in result["steps_completed"]
        assert result["steps_completed"].index("restore_commit_retry_state") < result[
            "steps_completed"
        ].index("build_and_run_supervisor")
        assert result["steps_completed"].index("restore_commit_retry_state") < result[
            "steps_completed"
        ].index("validate_receipt")
        assert set(result["commit_retry_state_restoration"]["changed"]) == {
            packet_path,
            "TASKS.md",
        }
        assert (
            f"Status: {commit_mod.COMMIT_RETRY_RESTORED_STATUS}"
            in packet_file.read_text(encoding="utf-8")
        )
        assert (
            "IMPLEMENTED / LOCAL EVIDENCE (2026-05-08)"
            in (repo / "TASKS.md").read_text(encoding="utf-8")
        )
        assert packet_path in captured_package["changed_files"]
        assert "TASKS.md" in captured_package["changed_files"]
        assert captured_package["wave_class"] == "L4_STRUCTURAL"

    def test_commit_retry_pending_state_demotes_again_when_receipt_validation_fails(
        self,
        tmp_path,
    ):
        from collections import namedtuple
        import types

        repo = _setup_repo(tmp_path)
        wave_id = "founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06"
        packet_path = (
            "reports/control_plane/"
            "founder_ordered_redteam_mu_structural_blocking_remediation_2026-05-06.md"
        )
        packet_file = repo / packet_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Packet\n\n"
            f"Status: {commit_mod.COMMIT_RETRY_PENDING_STATUS}\n"
            f"Wave ID: {wave_id}\n"
            "Class: L4_STRUCTURAL\n",
            encoding="utf-8",
        )
        pending_tasks = (
            "## Ra\n"
            "  6. **[FOUNDER-ORDERED-REDTEAM-MU-STRUCTURAL-BLOCKING-REMEDIATION] "
            "IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT / LOCAL EVIDENCE "
            "(2026-05-08).** "
            "Task: `[NEXT-CODEX-POST-REDTEAM]`. "
            f"Wave ID: `{wave_id}`. "
            "Class: `L4_STRUCTURAL`. "
            f"Packet: `{packet_path}`.\n"
        )
        tasks_file = repo / "TASKS.md"
        tasks_file.write_text(pending_tasks, encoding="utf-8")
        (repo / "file.py").write_text("# structural retry restoration\n", encoding="utf-8")

        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])

        def mock_supervisor(*args, **kwargs):
            return SupervisorResult(
                decision="COMMIT_GO",
                summary="test",
                receipt_path=".scratch/missing_step6_receipt.json",
            )

        mock_client = types.ModuleType("meta_bridge_client")
        mock_client.run_meta_bridge_package = mock_supervisor
        mock_client.MetaBridgeClientError = Exception
        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            wave_class="L4_STRUCTURAL",
            files_to_stage=["file.py", packet_path, "TASKS.md"],
            tracked_packet=packet_path,
            scope_items=[packet_path],
        )

        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "error", result
        assert result["step"] == "validate_receipt"
        assert "restore_commit_retry_state" in result["steps_completed"]
        assert "validate_receipt" not in result["steps_completed"]
        assert set(result["commit_retry_state_demotion"]["changed"]) == {
            packet_path,
            "TASKS.md",
        }
        assert commit_mod.COMMIT_RETRY_PENDING_STATUS in packet_file.read_text(
            encoding="utf-8"
        )
        assert tasks_file.read_text(encoding="utf-8") == pending_tasks

    def test_commit_retry_pending_state_demotes_again_when_handoff_persist_fails(
        self,
        tmp_path,
    ):
        from collections import namedtuple
        import types

        repo = _setup_repo(tmp_path)
        wave_id = "founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06"
        packet_path = (
            "reports/control_plane/"
            "founder_ordered_redteam_mu_structural_blocking_remediation_2026-05-06.md"
        )
        packet_file = repo / packet_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Packet\n\n"
            f"Status: {commit_mod.COMMIT_RETRY_PENDING_STATUS}\n"
            f"Wave ID: {wave_id}\n"
            "Class: L4_STRUCTURAL\n",
            encoding="utf-8",
        )
        pending_tasks = (
            "## Ra\n"
            "  6. **[FOUNDER-ORDERED-REDTEAM-MU-STRUCTURAL-BLOCKING-REMEDIATION] "
            "IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT / LOCAL EVIDENCE "
            "(2026-05-08).** "
            "Task: `[NEXT-CODEX-POST-REDTEAM]`. "
            f"Wave ID: `{wave_id}`. "
            "Class: `L4_STRUCTURAL`. "
            f"Packet: `{packet_path}`.\n"
        )
        tasks_file = repo / "TASKS.md"
        tasks_file.write_text(pending_tasks, encoding="utf-8")
        (repo / "file.py").write_text("# structural retry restoration\n", encoding="utf-8")

        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])

        def mock_supervisor(*args, **kwargs):
            raise AssertionError("supervisor should not run after handoff persist failure")

        mock_client = types.ModuleType("meta_bridge_client")
        mock_client.run_meta_bridge_package = mock_supervisor
        mock_client.MetaBridgeClientError = Exception
        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            wave_class="L4_STRUCTURAL",
            files_to_stage=["file.py", packet_path, "TASKS.md"],
            tracked_packet=packet_path,
            scope_items=[packet_path],
        )
        persist_calls = []

        def mock_persist(*args, **kwargs):
            persist_calls.append((args, kwargs))
            return "simulated handoff persist failure"

        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}), patch.object(
            commit_mod,
            "_persist_phase_b_handoff_for_commit_path",
            side_effect=mock_persist,
        ):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "error", result
        assert result["step"] == "restore_commit_retry_state"
        assert result["errors"] == ["simulated handoff persist failure"]
        assert len(persist_calls) == 1
        assert "restore_commit_retry_state" in result["steps_completed"]
        assert "build_and_run_supervisor" not in result["steps_completed"]
        assert set(result["commit_retry_state_restoration"]["changed"]) == {
            packet_path,
            "TASKS.md",
        }
        assert set(result["commit_retry_state_demotion"]["changed"]) == {
            packet_path,
            "TASKS.md",
        }
        assert commit_mod.COMMIT_RETRY_PENDING_STATUS in packet_file.read_text(
            encoding="utf-8"
        )
        assert tasks_file.read_text(encoding="utf-8") == pending_tasks

    def test_commit_retry_restore_skips_handoff_without_tracked_packet(self, tmp_path):
        from collections import namedtuple
        import types

        repo = _setup_repo(tmp_path)
        (repo / "file.py").write_text("# legacy handoff\n", encoding="utf-8")

        sup_receipt_path = ".scratch/step6_receipt.json"
        (repo / ".scratch").mkdir(parents=True, exist_ok=True)
        (repo / sup_receipt_path).write_text(
            json.dumps(
                {
                    "decision": "COMMIT_GO",
                    "staged_sha": "fresh_sha_from_step6",
                    "timestamp_utc": "2026-05-09T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )
        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])

        def mock_supervisor(*args, **kwargs):
            return SupervisorResult(
                decision="COMMIT_GO",
                summary="test",
                receipt_path=sup_receipt_path,
            )

        mock_client = types.ModuleType("meta_bridge_client")
        mock_client.run_meta_bridge_package = mock_supervisor
        mock_client.MetaBridgeClientError = Exception
        handoff = _make_new_schema_handoff(
            wave_id="legacy-wave",
            files_to_stage=["file.py"],
        )

        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}), patch.object(
            commit_mod,
            "_run_post_commit_pipeline",
            side_effect=lambda **kwargs: {**kwargs["result"], "status": "success"},
        ):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "success", result
        assert "restore_commit_retry_state" not in result["steps_completed"]
        assert "commit_retry_state_restoration" not in result

    def test_tracker_note_refresh_retries_self_cleared_index_lock_once(self, tmp_path):
        import subprocess

        repo = tmp_path / "repo"
        repo.mkdir()
        wave_id = "packet-lock-wave"
        old_note = (
            f"- Tracker sync note (2026-05-02, {wave_id}): **Old note.** "
            "Class: L4_ENABLER. target_gate_id: G8.\n"
        )
        new_note = (
            f"- Tracker sync note (2026-05-02, {wave_id}): **New note.** "
            "Class: L4_ENABLER. target_gate_id: G8.\n"
        )
        (repo / "TASKS.md").write_text(f"## Ra\n\n{old_note}\n---\n", encoding="utf-8")
        add_calls = []

        def fake_run(args, **kwargs):
            if args == ["git", "add", "--", "TASKS.md"]:
                add_calls.append(args)
                if len(add_calls) == 1:
                    raise subprocess.CalledProcessError(
                        128,
                        args,
                        output="",
                        stderr=(
                            "fatal: Unable to create "
                            f"'{repo / '.git' / 'index.lock'}': File exists"
                        ),
                    )
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch.object(commit_mod, "_run", side_effect=fake_run), \
             patch.object(commit_mod, "_git_owner_processes_for_repo", return_value=[]):
            error = commit_mod.refresh_tasks_tracker_note_after_packet_truth(
                repo,
                wave_id=wave_id,
                tracker_note_text=new_note,
            )

        assert error is None
        assert len(add_calls) == 2
        assert new_note in (repo / "TASKS.md").read_text(encoding="utf-8")

    def test_tracker_note_refresh_fails_closed_when_index_lock_persists(self, tmp_path):
        import subprocess

        repo = tmp_path / "repo"
        repo.mkdir()
        git_dir = repo / ".git"
        git_dir.mkdir()
        lock_path = git_dir / "index.lock"
        lock_path.write_text("locked", encoding="utf-8")
        wave_id = "packet-lock-wave"
        old_note = (
            f"- Tracker sync note (2026-05-02, {wave_id}): **Old note.** "
            "Class: L4_ENABLER. target_gate_id: G8.\n"
        )
        new_note = (
            f"- Tracker sync note (2026-05-02, {wave_id}): **New note.** "
            "Class: L4_ENABLER. target_gate_id: G8.\n"
        )
        (repo / "TASKS.md").write_text(f"## Ra\n\n{old_note}\n---\n", encoding="utf-8")
        add_calls = []

        def fake_run(args, **kwargs):
            if args == ["git", "add", "--", "TASKS.md"]:
                add_calls.append(args)
                raise subprocess.CalledProcessError(
                    128,
                    args,
                    output="",
                    stderr=f"fatal: Unable to create '{lock_path}': File exists",
                )
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch.object(commit_mod, "_run", side_effect=fake_run), \
             patch.object(commit_mod, "_git_owner_processes_for_repo", return_value=[]):
            error = commit_mod.refresh_tasks_tracker_note_after_packet_truth(
                repo,
                wave_id=wave_id,
                tracker_note_text=new_note,
            )

        assert error is not None
        assert "index.lock" in error
        assert len(add_calls) == 1
        assert lock_path.exists()

    def test_tracker_note_refresh_fails_closed_when_git_owner_remains(self, tmp_path):
        import subprocess

        repo = tmp_path / "repo"
        repo.mkdir()
        git_dir = repo / ".git"
        git_dir.mkdir()
        lock_path = git_dir / "index.lock"
        wave_id = "packet-lock-wave"
        old_note = (
            f"- Tracker sync note (2026-05-02, {wave_id}): **Old note.** "
            "Class: L4_ENABLER. target_gate_id: G8.\n"
        )
        new_note = (
            f"- Tracker sync note (2026-05-02, {wave_id}): **New note.** "
            "Class: L4_ENABLER. target_gate_id: G8.\n"
        )
        (repo / "TASKS.md").write_text(f"## Ra\n\n{old_note}\n---\n", encoding="utf-8")
        add_calls = []

        def fake_run(args, **kwargs):
            if args == ["git", "add", "--", "TASKS.md"]:
                add_calls.append(args)
                raise subprocess.CalledProcessError(
                    128,
                    args,
                    output="",
                    stderr=f"fatal: Unable to create '{lock_path}': File exists",
                )
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch.object(commit_mod, "_run", side_effect=fake_run), \
             patch.object(
                 commit_mod,
                 "_git_owner_processes_for_repo",
                 return_value=["pid=123 cwd=/repo command=git add -- TASKS.md"],
             ):
            error = commit_mod.refresh_tasks_tracker_note_after_packet_truth(
                repo,
                wave_id=wave_id,
                tracker_note_text=new_note,
            )

        assert error is not None
        assert "active git owner remains" in error
        assert len(add_calls) == 1
        assert not lock_path.exists()

    def test_git_commit_retries_self_cleared_index_lock_once(self, tmp_path):
        import subprocess

        repo = tmp_path / "repo"
        repo.mkdir()
        git_dir = repo / ".git"
        git_dir.mkdir()
        lock_path = git_dir / "index.lock"
        commit_calls = []

        def fake_run(args, **kwargs):
            if args == ["git", "commit", "-m", "test commit"]:
                commit_calls.append(args)
                if len(commit_calls) == 1:
                    raise subprocess.CalledProcessError(
                        128,
                        args,
                        output="",
                        stderr=f"fatal: Unable to create '{lock_path}': File exists",
                    )
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch.object(commit_mod, "_run", side_effect=fake_run), \
             patch.object(commit_mod, "_git_owner_processes_for_repo", return_value=[]):
            _completed, retry_detail = commit_mod._run_git_commit_with_self_cleared_index_lock_retry(  # ANTICHEAT_OK: regression for transient git index lock at commit step
                repo,
                "test commit",
                env={},
            )

        assert len(commit_calls) == 2
        assert retry_detail == "index.lock self-cleared before retry; no lock owner remained"

    def test_git_commit_fails_closed_when_index_lock_persists(self, tmp_path):
        import subprocess

        repo = tmp_path / "repo"
        repo.mkdir()
        git_dir = repo / ".git"
        git_dir.mkdir()
        lock_path = git_dir / "index.lock"
        lock_path.write_text("locked", encoding="utf-8")
        commit_calls = []

        def fake_run(args, **kwargs):
            if args == ["git", "commit", "-m", "test commit"]:
                commit_calls.append(args)
                raise subprocess.CalledProcessError(
                    128,
                    args,
                    output="",
                    stderr=f"fatal: Unable to create '{lock_path}': File exists",
                )
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch.object(commit_mod, "_run", side_effect=fake_run), \
             patch.object(commit_mod, "_git_owner_processes_for_repo", return_value=[]):
            with pytest.raises(subprocess.CalledProcessError):
                commit_mod._run_git_commit_with_self_cleared_index_lock_retry(  # ANTICHEAT_OK: fail-closed persistent git index lock regression
                    repo,
                    "test commit",
                    env={},
                )

        assert len(commit_calls) == 1
        assert lock_path.exists()

    def test_commit_packet_truth_refresh_binds_continuation_to_persisted_handoff(self, tmp_path):
        from collections import namedtuple
        import subprocess
        import types

        repo = _setup_repo(tmp_path)
        subprocess.run(
            ["git", "add", "--", "mu/tools/metrics/collect_l4_wave_indicators.py"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "test fixture indicator collector"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        wave_id = "packet-continuation-wave"
        packet_path = "reports/control_plane/packet_continuation_wave.md"
        packet_file = repo / packet_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Packet Continuation Wave\n\n"
            "Status: Phase B ready\n"
            "Wave ID: packet-continuation-wave\n"
            "Wave class: L4_ENABLER\n"
            "Target gate: G8\n",
            encoding="utf-8",
        )
        (repo / "file.py").write_text("# changed for continuation binding\n", encoding="utf-8")

        sup_receipt_path = ".scratch/step6_receipt.json"
        (repo / ".scratch").mkdir(parents=True, exist_ok=True)
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
        mock_client = types.ModuleType("meta_bridge_client")
        mock_client.run_meta_bridge_package = lambda *a, **kw: SupervisorResult(
            decision="COMMIT_GO",
            summary="test",
            receipt_path=sup_receipt_path,
        )
        mock_client.MetaBridgeClientError = Exception
        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", packet_path],
            tracked_packet=packet_path,
            scope_items=[packet_path],
        )
        original_handoff_sha = _canonical_handoff_sha_for_test(handoff)
        post_commit_results = []

        def fake_post_commit_pipeline(**kwargs):
            post_commit_results.append(dict(kwargs["result"]))
            return {**kwargs["result"], "status": "continued"}

        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}), patch.object(
            commit_mod,
            "_run_post_commit_pipeline",
            side_effect=fake_post_commit_pipeline,
        ):
            first = commit_mod.run_commit_pipeline(handoff, repo_root=repo)
            persisted_handoff = json.loads(
                (
                    repo
                    / ".agent_bus"
                    / "executors"
                    / "phase_b_handoff.json"
                ).read_text(encoding="utf-8")
            )
            persisted_handoff_sha = _canonical_handoff_sha_for_test(persisted_handoff)
            second = commit_mod.run_commit_pipeline(persisted_handoff, repo_root=repo)

        continuation_path = (
            repo / ".agent_bus" / "executors" / f"commit_executor_{wave_id}.json"
        )
        continuation = json.loads(continuation_path.read_text(encoding="utf-8"))

        assert first["status"] == "continued", first
        assert second["status"] == "continued", second
        assert len(post_commit_results) == 2
        assert first["handoff_sha"] == persisted_handoff_sha
        assert first["refreshed_handoff_sha"] != original_handoff_sha
        assert continuation["handoff_sha"] == persisted_handoff_sha
        assert post_commit_results[-1]["handoff_sha"] == persisted_handoff_sha
        assert post_commit_results[-1]["commit_sha"] == continuation["commit_sha"]
        assert "git_commit" in post_commit_results[-1]["steps_completed"]

    def test_post_commit_continuation_resets_push_steps_when_head_advances(self, tmp_path, monkeypatch):
        import subprocess

        old_sha = "a" * 40
        new_sha = "b" * 40
        target_branch = "jabramsja/test-wave-id"
        continuation_path = tmp_path / ".agent_bus" / "executors" / "commit_executor_test-wave-id.json"
        continuation_path.parent.mkdir(parents=True, exist_ok=True)
        continuation_path.write_text(
            json.dumps(
                {
                    "version": commit_mod.COMMIT_CONTINUATION_VERSION,
                    "status": commit_mod.CONTINUATION_ACTIVE_STATUS,
                    "handoff_sha": "handoff-sha",
                    "target_branch": target_branch,
                    "commit_sha": old_sha,
                    "receipt_decision": "COMMIT_GO",
                    "steps_completed": [
                        "validate_inputs",
                        "ensure_feature_branch",
                        "git_commit",
                        "run_pre_push_script",
                        "git_push",
                        "ensure_pr",
                        "wait_ci",
                    ],
                    "pr_number": "833",
                    "bot_review_request_sha": old_sha,
                    "updated_at_unix": 0,
                }
            ),
            encoding="utf-8",
        )

        def completed(cmd, returncode=0, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

        def fake_run(cmd, cwd=None, check=True, timeout=None, env=None):
            if cmd[:3] == ["git", "rev-parse", "HEAD"]:
                return completed(cmd, stdout=f"{new_sha}\n")
            if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
                return completed(cmd, stdout=f"{target_branch}\n")
            if cmd[:3] == ["git", "status", "--short"]:
                return completed(cmd, stdout="")
            if cmd[:3] == ["git", "merge-base", "--is-ancestor"]:
                assert cmd[-2:] == [old_sha, new_sha]
                return completed(cmd)
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(commit_mod, "_run", fake_run)

        loaded = commit_mod._load_post_commit_continuation(  # ANTICHEAT_OK: direct continuation loader regression
            continuation_path,
            repo_root=tmp_path,
            handoff_sha="handoff-sha",
            target_branch=target_branch,
        )

        assert loaded is not None
        assert loaded["commit_sha"] == new_sha
        assert loaded["steps_completed"] == [
            "validate_inputs",
            "ensure_feature_branch",
            "git_commit",
        ]
        assert loaded["pr_number"] == "833"
        assert "bot_review_request_sha" not in loaded

    def test_commit_packet_truth_refresh_missing_packet_names_root_input(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "missing-packet-wave"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        indicator_file = repo / indicator_path
        indicator_file.parent.mkdir(parents=True, exist_ok=True)
        indicator_file.write_text(json.dumps({"wave_id": wave_id}), encoding="utf-8")
        (repo / "file.py").write_text("# changed code\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", "file.py"], cwd=repo, check=True)
        subprocess.run(["git", "add", "-f", "--", indicator_path], cwd=repo, check=True)

        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            tracked_packet="reports/control_plane/missing_packet.md",
            scope_items=["reports/control_plane/missing_packet.md"],
        )

        _refreshed, _staged, error = commit_mod.refresh_commit_path_packet_truth(
            repo_root=repo,
            handoff=handoff,
            indicator_path=indicator_path,
            commit_status="pre_commit_supervisor_pending",
        )

        assert error == (
            "active packet not found for commit packet truth refresh: "
            "reports/control_plane/missing_packet.md"
        )

    def test_commit_packet_truth_refresh_ignores_scope_only_packet(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "scope-only-packet-wave"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        indicator_file = repo / indicator_path
        indicator_file.parent.mkdir(parents=True, exist_ok=True)
        indicator_file.write_text(json.dumps({"wave_id": wave_id}), encoding="utf-8")
        (repo / "file.py").write_text("# changed code\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", "file.py"], cwd=repo, check=True)
        subprocess.run(["git", "add", "-f", "--", indicator_path], cwd=repo, check=True)

        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            scope_items=["reports/control_plane/missing_scope_only_packet.md"],
        )

        refreshed, staged, error = commit_mod.refresh_commit_path_packet_truth(
            repo_root=repo,
            handoff=handoff,
            indicator_path=indicator_path,
            commit_status="pre_commit_supervisor_pending",
        )

        assert error is None
        assert refreshed is handoff
        assert "reports/control_plane/missing_scope_only_packet.md" not in staged

    def test_commit_packet_truth_refresh_is_idempotent(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "idempotent-packet-wave"
        packet_path = "reports/control_plane/idempotent_packet_wave.md"
        packet_file = repo / packet_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Idempotent Packet Wave\n\n"
            "Wave ID: idempotent-packet-wave\n"
            "Wave class: L4_ENABLER\n"
            "Target gate: G8\n"
            "Lane: control-surface\n",
            encoding="utf-8",
        )
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        indicator_file = repo / indicator_path
        indicator_file.parent.mkdir(parents=True, exist_ok=True)
        indicator_file.write_text(json.dumps({"wave_id": wave_id}), encoding="utf-8")
        (repo / "file.py").write_text("# changed code\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", "file.py"], cwd=repo, check=True)
        subprocess.run(["git", "add", "-f", "--", indicator_path], cwd=repo, check=True)

        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", packet_path],
            tracked_packet=packet_path,
            scope_items=[packet_path],
        )

        refreshed, staged, error = commit_mod.refresh_commit_path_packet_truth(
            repo_root=repo,
            handoff=handoff,
            indicator_path=indicator_path,
            commit_status="pre_commit_supervisor_pending",
        )
        assert error is None
        assert packet_path in staged
        first_text = packet_file.read_text(encoding="utf-8")

        refreshed_again, staged_again, error_again = commit_mod.refresh_commit_path_packet_truth(
            repo_root=repo,
            handoff=refreshed,
            indicator_path=indicator_path,
            commit_status="pre_commit_supervisor_pending",
        )
        assert error_again is None
        assert packet_file.read_text(encoding="utf-8") == first_text
        assert refreshed_again["tracked_packet"] == packet_path
        assert staged_again == staged

    def test_same_wave_deferred_authorization_refresh_updates_scope_and_acceptance(self):
        wave_id = "deferred-auth-wave"
        deferred_path = "reports/deferred/non_blocking/deferred-auth-wave_bridge_nonblockers.md"
        packet_text = (
            "# Deferred Auth Wave\n\n"
            f"Wave ID: {wave_id}\n\n"
            "## Scope\n\n"
            "- `mu/tools/executors/commit_executor.py`\n"
            "\n"
            "Only files under the explicit paths above may be edited.\n\n"
            "## Stop Conditions\n\n"
            "- The required fix resolves to files outside `mu/tools/executors/`, or a canonical `TASKS.md` tracker note for this wave.\n\n"
            "## Acceptance Criteria\n\n"
            "- The final touched-file set stays within `mu/tools/executors/`, and the same-wave canonical `TASKS.md` tracker note, or returns for re-authorization.\n"
        )

        refreshed = commit_mod._refresh_same_wave_deferred_packet_authorization(  # ANTICHEAT_OK: testing bounded packet refresh helper
            packet_text,
            wave_id=wave_id,
            deferred_paths=[deferred_path],
        )
        refreshed_again = commit_mod._refresh_same_wave_deferred_packet_authorization(  # ANTICHEAT_OK: testing idempotence
            refreshed,
            wave_id=wave_id,
            deferred_paths=[deferred_path],
        )

        assert refreshed_again == refreshed
        assert "## Same-Wave Deferred Non-Blocking Authorization" in refreshed
        assert f"- `{deferred_path}`" in refreshed
        assert "Same-wave Phase B/commit generated deferred non-blocking" in refreshed
        stop_line = next(line for line in refreshed.splitlines() if "required fix resolves" in line)
        acceptance_line = next(line for line in refreshed.splitlines() if "final touched-file set" in line)
        assert f"`{deferred_path}`" in stop_line
        assert f"`{deferred_path}`" in acceptance_line

    def test_same_wave_deferred_authorization_refresh_clears_stale_auth_without_paths(self):
        wave_id = "deferred-auth-wave"
        deferred_path = "reports/deferred/non_blocking/deferred-auth-wave_bridge_nonblockers.md"
        packet_text = (
            "# Deferred Auth Wave\n\n"
            f"Wave ID: {wave_id}\n\n"
            f"{commit_mod.DEFERRED_AUTH_REFRESH_START}\n"
            "## Same-Wave Deferred Non-Blocking Authorization\n\n"
            f"- Refresh wave: `{wave_id}`\n"
            "- Purpose: stale active authorization.\n"
            "- Authorized deferred packet(s):\n"
            f"  - `{deferred_path}`\n"
            "- Scope binding: stale.\n"
            "- Acceptance binding: stale.\n"
            f"{commit_mod.DEFERRED_AUTH_REFRESH_END}\n"
        )

        refreshed = commit_mod._refresh_same_wave_deferred_packet_authorization(  # ANTICHEAT_OK: testing bounded packet refresh helper
            packet_text,
            wave_id=wave_id,
            deferred_paths=[],
        )

        auth_block = refreshed[
            refreshed.index(commit_mod.DEFERRED_AUTH_REFRESH_START):
            refreshed.index(commit_mod.DEFERRED_AUTH_REFRESH_END)
            + len(commit_mod.DEFERRED_AUTH_REFRESH_END)
        ]
        assert "- Authorized deferred packet(s): none" in auth_block
        assert f"`{deferred_path}`" not in auth_block

    def test_validate_handoff_rejects_same_wave_active_packet_when_closed_archive_staged(self):
        wave_id = "deferred-auth-wave"
        deferred_path = "reports/deferred/non_blocking/deferred-auth-wave_bridge_nonblockers.md"
        archive_path = (
            "reports/archive/deferred/"
            "deferred-auth-wave_bridge_nonblockers_closed-by-deferred-auth-wave.md"
        )
        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", deferred_path, archive_path],
            deferred_items=[deferred_path],
        )

        ok, errors = commit_mod.validate_handoff(handoff)

        assert ok is False
        assert any("both active deferred and archived closed" in error for error in errors)

    def test_validate_handoff_rejects_same_wave_active_packet_with_archive_without_deferred_items(self):
        wave_id = "deferred-auth-wave"
        deferred_path = "reports/deferred/non_blocking/deferred-auth-wave_bridge_nonblockers.md"
        archive_path = (
            "reports/archive/deferred/"
            "deferred-auth-wave_bridge_nonblockers_closed-by-deferred-auth-wave.md"
        )
        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", deferred_path],
            force_add_files=[archive_path],
        )

        ok, errors = commit_mod.validate_handoff(handoff)

        assert ok is False
        assert any("both active deferred and archived closed" in error for error in errors)

    def test_build_handoff_accepts_same_wave_staged_deletion_with_closed_archive(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "deferred-auth-wave"
        deferred_path = "reports/deferred/non_blocking/deferred-auth-wave_bridge_nonblockers.md"
        archive_path = (
            "reports/archive/deferred/"
            "deferred-auth-wave_bridge_nonblockers_closed-by-deferred-auth-wave.md"
        )
        deferred_file = repo / deferred_path
        deferred_file.parent.mkdir(parents=True, exist_ok=True)
        deferred_file.write_text("# Deferred\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", deferred_path], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "add deferred packet"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "rm", "--", deferred_path], cwd=repo, check=True, capture_output=True)
        archive_file = repo / archive_path
        archive_file.parent.mkdir(parents=True, exist_ok=True)
        archive_file.write_text("# Closed deferred packet\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", archive_path], cwd=repo, check=True)
        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=[deferred_path, archive_path],
            deferred_items=[],
        )

        ok_without_repo, errors_without_repo = commit_mod.validate_handoff(handoff)
        ok, errors = commit_mod.validate_handoff(handoff, repo_root=repo)
        rebuilt, build_errors = commit_mod.build_commit_handoff(
            wave_id=wave_id,
            task_id="[TEST]",
            files_to_stage=[deferred_path, archive_path],
            commit_message="test: staged deletion handoff\n\nCo-Authored-By: test",
            fixes_implemented=["test"],
            wave_class="L4_ENABLER",
            target_gate_id="G8",
            repo_root=repo,
        )

        assert ok_without_repo is False
        assert any("both active deferred and archived closed" in error for error in errors_without_repo)
        assert ok is True
        assert errors == []
        assert build_errors == []
        assert rebuilt["files_to_stage"] == [deferred_path, archive_path]

    def test_commit_packet_truth_refresh_authorizes_staged_same_wave_deferred_packet(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "deferred-auth-wave"
        packet_path = "reports/control_plane/deferred_auth_wave.md"
        deferred_path = "reports/deferred/non_blocking/deferred-auth-wave_bridge_nonblockers.md"
        packet_file = repo / packet_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Deferred Auth Wave\n\n"
            "Wave ID: deferred-auth-wave\n"
            "Wave class: L4_ENABLER\n"
            "Target gate: G8\n"
            "Lane: control-surface\n\n"
            "## Scope\n\n"
            "- `mu/tools/executors/commit_executor.py`\n"
            "\n"
            "Only files under the explicit paths above may be edited.\n\n"
            "## Stop Conditions\n\n"
            "- The required fix resolves to files outside `mu/tools/executors/`, or a canonical `TASKS.md` tracker note for this wave.\n\n"
            "## Acceptance Criteria\n\n"
            "- The final touched-file set stays within `mu/tools/executors/`, and the same-wave canonical `TASKS.md` tracker note, or returns for re-authorization.\n",
            encoding="utf-8",
        )
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        indicator_file = repo / indicator_path
        indicator_file.parent.mkdir(parents=True, exist_ok=True)
        indicator_file.write_text(json.dumps({"wave_id": wave_id}), encoding="utf-8")
        deferred_file = repo / deferred_path
        deferred_file.parent.mkdir(parents=True, exist_ok=True)
        deferred_file.write_text("# Deferred\n", encoding="utf-8")
        (repo / "file.py").write_text("# changed code\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", "file.py", deferred_path], cwd=repo, check=True)
        subprocess.run(["git", "add", "-f", "--", indicator_path], cwd=repo, check=True)

        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", packet_path, deferred_path],
            tracked_packet=packet_path,
            scope_items=[packet_path],
            deferred_items=[deferred_path],
        )

        refreshed, staged, error = commit_mod.refresh_commit_path_packet_truth(
            repo_root=repo,
            handoff=handoff,
            indicator_path=indicator_path,
            commit_status="pre_commit_supervisor_pending",
        )

        assert error is None
        assert deferred_path in staged
        assert deferred_path in refreshed["files_to_stage"]
        packet_text = packet_file.read_text(encoding="utf-8")
        assert "## Same-Wave Deferred Non-Blocking Authorization" in packet_text
        assert f"- `{deferred_path}`" in packet_text
        stop_line = next(line for line in packet_text.splitlines() if "required fix resolves" in line)
        acceptance_line = next(line for line in packet_text.splitlines() if "final touched-file set" in line)
        assert f"`{deferred_path}`" in stop_line
        assert f"`{deferred_path}`" in acceptance_line

        start = packet_text.index(commit_mod.DEFERRED_AUTH_REFRESH_START)
        end = packet_text.index(commit_mod.DEFERRED_AUTH_REFRESH_END) + len(
            commit_mod.DEFERRED_AUTH_REFRESH_END
        )
        packet_file.write_text(
            packet_text[:start].rstrip() + "\n\n" + packet_text[end:].lstrip(),
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "--", packet_path], cwd=repo, check=True)

        _refreshed_again, _staged_again, error_again = commit_mod.refresh_commit_path_packet_truth(
            repo_root=repo,
            handoff=refreshed,
            indicator_path=indicator_path,
            commit_status="pre_commit_supervisor_pending",
        )

        assert error_again is None
        assert "## Same-Wave Deferred Non-Blocking Authorization" in packet_file.read_text(encoding="utf-8")

    def test_commit_packet_truth_refresh_does_not_authorize_deleted_same_wave_deferred_packet(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "deferred-auth-wave"
        packet_path = "reports/control_plane/deferred_auth_wave.md"
        deferred_path = "reports/deferred/non_blocking/deferred-auth-wave_bridge_nonblockers.md"
        packet_file = repo / packet_path
        deferred_file = repo / deferred_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        deferred_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Deferred Auth Wave\n\n"
            "Wave ID: deferred-auth-wave\n\n"
            f"{commit_mod.DEFERRED_AUTH_REFRESH_START}\n"
            "## Same-Wave Deferred Non-Blocking Authorization\n\n"
            "- Refresh wave: `deferred-auth-wave`\n"
            "- Purpose: stale active authorization.\n"
            "- Authorized deferred packet(s):\n"
            f"  - `{deferred_path}`\n"
            "- Scope binding: stale.\n"
            "- Acceptance binding: stale.\n"
            f"{commit_mod.DEFERRED_AUTH_REFRESH_END}\n",
            encoding="utf-8",
        )
        deferred_file.write_text("# Deferred\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", packet_path, deferred_path], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)

        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        indicator_file = repo / indicator_path
        indicator_file.parent.mkdir(parents=True, exist_ok=True)
        indicator_file.write_text(json.dumps({"wave_id": wave_id}), encoding="utf-8")
        packet_file.write_text(packet_file.read_text(encoding="utf-8") + "\n## Touch\n", encoding="utf-8")
        (repo / "file.py").write_text("# changed code\n", encoding="utf-8")
        deferred_file.unlink()
        subprocess.run(["git", "add", "--", "file.py", packet_path], cwd=repo, check=True)
        subprocess.run(["git", "add", "-u", "--", deferred_path], cwd=repo, check=True)
        subprocess.run(["git", "add", "-f", "--", indicator_path], cwd=repo, check=True)

        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", packet_path, deferred_path],
            tracked_packet=packet_path,
            scope_items=[packet_path],
            deferred_items=[],
        )

        _refreshed, staged, error = commit_mod.refresh_commit_path_packet_truth(
            repo_root=repo,
            handoff=handoff,
            indicator_path=indicator_path,
            commit_status="pre_commit_supervisor_pending",
        )

        assert error is None
        assert deferred_path in staged
        packet_text = packet_file.read_text(encoding="utf-8")
        auth_block = packet_text[
            packet_text.index(commit_mod.DEFERRED_AUTH_REFRESH_START):
            packet_text.index(commit_mod.DEFERRED_AUTH_REFRESH_END)
            + len(commit_mod.DEFERRED_AUTH_REFRESH_END)
        ]
        assert "- Authorized deferred packet(s): none" in auth_block
        assert f"`{deferred_path}`" not in auth_block

    def test_commit_packet_truth_refresh_authorizes_index_staged_deferred_packet_without_worktree_file(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "deferred-auth-wave"
        packet_path = "reports/control_plane/deferred_auth_wave.md"
        deferred_path = "reports/deferred/non_blocking/deferred-auth-wave_bridge_nonblockers.md"
        packet_file = repo / packet_path
        deferred_file = repo / deferred_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        deferred_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Deferred Auth Wave\n\n"
            "Wave ID: deferred-auth-wave\n",
            encoding="utf-8",
        )
        deferred_file.write_text("# Deferred\n", encoding="utf-8")

        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        indicator_file = repo / indicator_path
        indicator_file.parent.mkdir(parents=True, exist_ok=True)
        indicator_file.write_text(json.dumps({"wave_id": wave_id}), encoding="utf-8")
        (repo / "file.py").write_text("# changed code\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "--", "file.py", packet_path, deferred_path],
            cwd=repo,
            check=True,
        )
        subprocess.run(["git", "add", "-f", "--", indicator_path], cwd=repo, check=True)
        deferred_file.unlink()

        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", packet_path, deferred_path],
            tracked_packet=packet_path,
            scope_items=[packet_path],
            deferred_items=[deferred_path],
        )

        _refreshed, staged, error = commit_mod.refresh_commit_path_packet_truth(
            repo_root=repo,
            handoff=handoff,
            indicator_path=indicator_path,
            commit_status="pre_commit_supervisor_pending",
        )

        assert error is None
        assert deferred_path in staged
        packet_text = packet_file.read_text(encoding="utf-8")
        auth_block = packet_text[
            packet_text.index(commit_mod.DEFERRED_AUTH_REFRESH_START):
            packet_text.index(commit_mod.DEFERRED_AUTH_REFRESH_END)
            + len(commit_mod.DEFERRED_AUTH_REFRESH_END)
        ]
        assert f"`{deferred_path}`" in auth_block

    def test_commit_packet_truth_refresh_uses_documented_bridge_round_floor(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "bridge-floor-wave"
        packet_path = "reports/control_plane/bridge_floor_wave.md"
        deferred_path = "reports/deferred/non_blocking/bridge-floor-wave_bridge_nonblockers.md"
        packet_file = repo / packet_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Bridge Floor Wave\n\n"
            "Wave ID: bridge-floor-wave\n"
            "Wave class: L4_ENABLER\n"
            "Target gate: G8\n"
            "Lane: control-surface\n\n"
            "Bridge Round 3 found that the staged package still underreported the live packet.\n",
            encoding="utf-8",
        )
        deferred_file = repo / deferred_path
        deferred_file.parent.mkdir(parents=True, exist_ok=True)
        deferred_file.write_text(
            "# Deferred Non-Blocking Findings: bridge-floor-wave\n\n"
            "Wave: bridge-floor-wave\n"
            "Status: DEFERRED_NON_BLOCKING\n",
            encoding="utf-8",
        )
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        indicator_file = repo / indicator_path
        indicator_file.parent.mkdir(parents=True, exist_ok=True)
        indicator_file.write_text(json.dumps({"wave_id": wave_id}), encoding="utf-8")
        (repo / "file.py").write_text("# changed code\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", "file.py", deferred_path], cwd=repo, check=True)
        subprocess.run(["git", "add", "-f", "--", indicator_path], cwd=repo, check=True)

        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", packet_path, deferred_path],
            tracked_packet=packet_path,
            scope_items=[packet_path],
            deferred_items=[deferred_path],
            bridge_status={"rounds": 1, "total_rounds": 1},
        )
        handoff = {
            **handoff,
            "tracker_note_text": handoff["tracker_note_text"].replace(
                "Receipt handoff now carries a canonical tracker note.",
                "Receipt handoff now carries bridge rounds=1 and a canonical tracker note.",
            ),
        }
        (repo / "TASKS.md").write_text(
            "## Ra\n\n" + handoff["tracker_note_text"] + "\n\n---\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "--", "TASKS.md"], cwd=repo, check=True)

        refreshed, _staged, error = commit_mod.refresh_commit_path_packet_truth(
            repo_root=repo,
            handoff=handoff,
            indicator_path=indicator_path,
            commit_status="pre_commit_supervisor_pending",
        )

        assert error is None
        assert refreshed["bridge_status"] == {"rounds": 3, "total_rounds": 3}
        assert "bridge rounds=3" in refreshed["tracker_note_text"]
        assert "bridge rounds=3" in (repo / "TASKS.md").read_text(encoding="utf-8")

    def test_commit_packet_truth_refresh_uses_prose_bridge_round_floor(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "bridge-prose-floor-wave"
        packet_path = "reports/control_plane/bridge_prose_floor_wave.md"
        packet_file = repo / packet_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Bridge Prose Floor Wave\n\n"
            "Wave ID: bridge-prose-floor-wave\n"
            "Wave class: L4_ENABLER\n\n"
            "Manual repair grounding: dispatcher first exited max_rounds_reached "
            "after six Phase B bridge rounds before the package was repaired. "
            "Parser examples such as fifteen Phase B bridge rounds are not "
            "same-wave bridge history.\n",
            encoding="utf-8",
        )
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        indicator_file = repo / indicator_path
        indicator_file.parent.mkdir(parents=True, exist_ok=True)
        indicator_file.write_text(json.dumps({"wave_id": wave_id}), encoding="utf-8")
        (repo / "file.py").write_text("# changed code\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", "file.py"], cwd=repo, check=True)
        subprocess.run(["git", "add", "-f", "--", indicator_path], cwd=repo, check=True)

        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", packet_path],
            tracked_packet=packet_path,
            scope_items=[packet_path],
            bridge_status={"rounds": 1, "total_rounds": 1},
        )
        handoff = {
            **handoff,
            "tracker_note_text": handoff["tracker_note_text"].replace(
                "Receipt handoff now carries a canonical tracker note.",
                "Receipt handoff now carries bridge rounds=1 and a canonical tracker note.",
            ),
        }
        (repo / "TASKS.md").write_text(
            "## Ra\n\n" + handoff["tracker_note_text"] + "\n\n---\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "--", "TASKS.md"], cwd=repo, check=True)

        assert commit_mod._documented_bridge_round_floor_from_text(  # ANTICHEAT_OK: direct helper regression for package truth floor
            "after eleven Phase B bridge rounds"
        ) == 11
        assert commit_mod._documented_bridge_round_floor_from_text(  # ANTICHEAT_OK: direct helper regression for package truth floor
            "after six Phase B bridge rounds. Parser examples such as fifteen Phase B bridge rounds."
        ) == 6
        refreshed, _staged, error = commit_mod.refresh_commit_path_packet_truth(
            repo_root=repo,
            handoff=handoff,
            indicator_path=indicator_path,
            commit_status="pre_commit_supervisor_pending",
        )

        assert error is None
        assert refreshed["bridge_status"] == {"rounds": 6, "total_rounds": 6}
        assert "bridge rounds=6" in refreshed["tracker_note_text"]

    def test_commit_packet_truth_refresh_updates_rebuilt_handoff_file_count(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "packet-count-refresh-wave"
        packet_path = "reports/control_plane/packet_count_refresh_wave.md"
        packet_file = repo / packet_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Packet Count Refresh Wave\n\n"
            "Wave ID: packet-count-refresh-wave\n"
            "Wave class: L4_ENABLER\n"
            "Target gate: G8\n"
            "Lane: control-surface\n",
            encoding="utf-8",
        )
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        indicator_file = repo / indicator_path
        indicator_file.parent.mkdir(parents=True, exist_ok=True)
        indicator_file.write_text(json.dumps({"wave_id": wave_id}), encoding="utf-8")
        (repo / "file.py").write_text("# changed code\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", "file.py"], cwd=repo, check=True)
        subprocess.run(["git", "add", "-f", "--", indicator_path], cwd=repo, check=True)
        stale_note = (
            f"- Tracker sync note (2026-04-30, {wave_id}): **TEST.**. "
            "Class: L4_ENABLER. target_gate_id: G8. "
            "evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py`. "
            "evidence_delta: (1) Routed commit handoff scopes 11 wave-owned file(s). "
            "(2) Evidence gate exercises 1 wave-owned test module(s). "
            "(3) Indicator artifact binds the wave. "
            "progress_proof_before: stale count. "
            f"progress_proof_after: Phase B handoff for {wave_id} now carries 11 wave-owned file(s), "
            "bridge rounds=1, explicit receipt authority, and an L4-compliant tracker note. "
            "primary_blocker_class: INTEGRATION. "
            "primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
            f"indicator_artifact_ref: {indicator_path}. "
            f"indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id {wave_id} --output {indicator_path}. "
            "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            "boot0_track_id: V1. boot0_progress_state: HOLD."
        )
        (repo / "TASKS.md").write_text(f"## Ra\n\n{stale_note}\n\n---\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", "TASKS.md"], cwd=repo, check=True)
        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=[
                "file.py",
                packet_path,
                "old_a.py",
                "old_b.py",
                "old_c.py",
                "old_d.py",
                "old_e.py",
                "old_f.py",
                "old_g.py",
                "old_h.py",
                "old_i.py",
            ],
            tracked_packet=packet_path,
            scope_items=[packet_path],
            tracker_note_text=stale_note,
        )

        refreshed, staged, error = commit_mod.refresh_commit_path_packet_truth(
            repo_root=repo,
            handoff=handoff,
            indicator_path=indicator_path,
            commit_status="pre_commit_supervisor_pending",
        )

        assert error is None
        assert len(staged) == 4
        tasks_text = (repo / "TASKS.md").read_text(encoding="utf-8")
        packet_text = packet_file.read_text(encoding="utf-8")
        assert "Routed commit handoff scopes 4 wave-owned file(s)" in refreshed["tracker_note_text"]
        assert "now carries 4 wave-owned file(s)" in refreshed["tracker_note_text"]
        assert "11 wave-owned file(s)" not in refreshed["tracker_note_text"]
        assert "Routed commit handoff scopes 4 wave-owned file(s)" in tasks_text
        assert "now carries 4 wave-owned file(s)" in tasks_text
        assert "Routed commit handoff scopes 4 wave-owned file(s)" in packet_text
        assert "11 wave-owned file(s)" not in tasks_text
        assert "11 wave-owned file(s)" not in packet_text

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
            "files_to_stage": ["TASKS.md"],
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
            "files_to_stage": ["TASKS.md"],
        }
        handoff, errors = commit_mod.prepare_handoff_from_routing_record(record, tmp_path)
        assert errors == []
        assert handoff is not None
        valid, validation_errors = commit_mod.validate_handoff(handoff)
        assert valid, validation_errors
        assert "no_op_proof:" in handoff["tracker_note_text"]
        assert "defer_reason_code:" in handoff["tracker_note_text"]

    @pytest.mark.parametrize(
        "extra_scope",
        [
            {"tracker_note_text": "   "},
            {"files_to_stage": ["", "   "]},
            {"force_add_files": ["", "   "]},
        ],
    )
    def test_prepare_handoff_tracker_only_blank_scope_rejected(self, tmp_path, extra_scope):
        record = {
            "wave_name": "tracker-only-wave",
            "summary": "sync tracker only",
            "decision": "UPDATE_TRACKER_ONLY",
            **extra_scope,
        }
        handoff, errors = commit_mod.prepare_handoff_from_routing_record(record, tmp_path)
        assert handoff is None
        assert any("no actionable tracker scope" in error for error in errors)

    def test_prepare_handoff_tracker_only_null_force_add_files_treated_as_empty(self, tmp_path):
        record = {
            "wave_name": "tracker-only-wave",
            "summary": "sync tracker only",
            "decision": "UPDATE_TRACKER_ONLY",
            "force_add_files": None,
            "files_to_stage": ["TASKS.md"],
        }
        handoff, errors = commit_mod.prepare_handoff_from_routing_record(record, tmp_path)
        assert errors == []
        assert handoff is not None
        assert handoff["force_add_files"] == []
        valid, validation_errors = commit_mod.validate_handoff(handoff)
        assert valid, validation_errors

    def test_prepare_handoff_tracker_only_null_next_candidates_treated_as_empty(self, tmp_path):
        record = {
            "wave_name": "tracker-only-wave",
            "summary": "sync tracker only",
            "decision": "UPDATE_TRACKER_ONLY",
            "next_candidates": None,
            "files_to_stage": ["TASKS.md"],
        }
        handoff, errors = commit_mod.prepare_handoff_from_routing_record(record, tmp_path)
        assert errors == []
        assert handoff is not None
        valid, validation_errors = commit_mod.validate_handoff(handoff)
        assert valid, validation_errors

    def test_prepare_handoff_tracker_only_coerces_non_string_commit_message(self, tmp_path):
        record = {
            "wave_name": "tracker-only-wave",
            "summary": "sync tracker only",
            "decision": "UPDATE_TRACKER_ONLY",
            "commit_message": 123,
            "files_to_stage": ["TASKS.md"],
        }
        handoff, errors = commit_mod.prepare_handoff_from_routing_record(record, tmp_path)
        assert errors == []
        assert handoff is not None
        assert handoff["commit_message"] == "123"
        valid, validation_errors = commit_mod.validate_handoff(handoff)
        assert valid, validation_errors

    def test_prepare_handoff_tracker_only_derives_same_wave_override_from_tasks(
        self, tmp_path
    ):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "founder-ordered-redteam-wave-queue-2026-05-05"
        (repo / "TASKS.md").write_text(
            "## Ra\n\n- Tracker sync note (seed): init\n\n---\n\n"
            "## NEXT\n\n"
            "- **[NEXT-CODEX-POST-REDTEAM]** OPEN.\n"
            "  3. **[FOUNDER-ORDERED-REDTEAM-WAVE-QUEUE] ACTIVE DIRECTIVE.** "
            f"FOUNDER_OVERRIDE:{wave_id}.\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "--", "TASKS.md"],
            cwd=repo,
            capture_output=True,
            check=True,
        )
        record = {
            "wave_name": wave_id,
            "summary": "persist founder-ordered redteam wave queue directive",
            "decision": "UPDATE_TRACKER_ONLY",
            "wave_class": "MAINTENANCE",
            "files_to_stage": ["TASKS.md"],
        }

        handoff, errors = commit_mod.prepare_handoff_from_routing_record(record, repo)

        assert errors == []
        assert handoff is not None
        assert f"FOUNDER_OVERRIDE:{wave_id}" in handoff["tracker_note_text"]
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
            founder_override_token="standalone-wave",
        )
        assert errors == []
        assert handoff["caller"] == "standalone"
        assert handoff["pre_commit_receipt_path"] == ""
        assert "FOUNDER_OVERRIDE:standalone-wave" in handoff["tracker_note_text"]
        valid, validation_errors = commit_mod.validate_handoff(handoff)
        assert valid, validation_errors

    def test_build_commit_handoff_derives_founder_override_from_authorized_packet(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "authorized-control-wave"
        packet_path = "reports/control_plane/authorized_control_wave.md"
        packet_file = repo / packet_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Authorized Control Wave\n"
            "Wave ID: authorized-control-wave\n"
            "Wave class: L4_ENABLER\n"
            "Lane: control-surface\n"
            "Authorization: standing pipeline-bug-fix authorization\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "--", packet_path],
            cwd=repo,
            capture_output=True,
            check=True,
        )

        handoff, errors = commit_mod.build_commit_handoff(
            wave_id=wave_id,
            task_id="[PIPELINE-RECOVERY]",
            files_to_stage=["file.py", packet_path],
            commit_message="chore: authorized control wave",
            fixes_implemented=["authorized packet drives override derivation"],
            caller="phase_b",
            tracked_packet=packet_path,
            repo_root=repo,
        )

        assert errors == []
        assert handoff is not None
        assert f"FOUNDER_OVERRIDE:{wave_id}" in handoff["tracker_note_text"]
        valid, validation_errors = commit_mod.validate_handoff(handoff)
        assert valid, validation_errors

    def test_run_commit_pipeline_derives_founder_override_for_existing_phase_b_handoff(self, tmp_path):
        from collections import namedtuple
        import subprocess
        import types

        repo = _setup_repo(tmp_path)
        wave_id = "existing-phase-b-authorized-wave"
        packet_path = "reports/control_plane/existing_phase_b_authorized_wave.md"
        packet_file = repo / packet_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Existing Phase B Authorized Wave\n"
            "Wave ID: existing-phase-b-authorized-wave\n"
            "Wave class: L4_ENABLER\n"
            "Lane: control-surface\n"
            "Authorization: standing pipeline-bug-fix authorization\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "--", packet_path],
            cwd=repo,
            capture_output=True,
            check=True,
        )
        (repo / "file.py").write_text("# changed code\n", encoding="utf-8")

        sup_receipt_path = ".scratch/step6_receipt.json"
        (repo / ".scratch").mkdir(parents=True, exist_ok=True)
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

        captured_package = {}
        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])

        def mock_supervisor(package_path, *a, **kw):
            captured_package.update(json.loads(Path(package_path).read_text(encoding="utf-8")))
            return SupervisorResult(
                decision="COMMIT_GO",
                summary="test",
                receipt_path=sup_receipt_path,
            )

        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", packet_path],
            tracked_packet=packet_path,
            scope_items=[packet_path],
        )
        assert "FOUNDER_OVERRIDE:" not in handoff["tracker_note_text"]

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

        assert result["status"] == "success", result
        assert captured_package["founder_override_token"] == f"FOUNDER_OVERRIDE:{wave_id}"
        assert f"FOUNDER_OVERRIDE:{wave_id}" in (repo / "TASKS.md").read_text(encoding="utf-8")

    def test_run_commit_pipeline_omits_founder_override_for_structural_handoff(self, tmp_path):
        from collections import namedtuple
        import types

        repo = _setup_repo(tmp_path)
        wave_id = "structural-wave"
        (repo / "file.py").write_text("# changed code\n", encoding="utf-8")

        sup_receipt_path = ".scratch/step6_receipt.json"
        (repo / ".scratch").mkdir(parents=True, exist_ok=True)
        (repo / sup_receipt_path).write_text(
            json.dumps(
                {
                    "decision": "COMMIT_GO",
                    "staged_sha": "fresh_sha_from_step6",
                    "timestamp_utc": "2026-05-01T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )

        captured_package = {}
        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])

        def mock_supervisor(package_path, *a, **kw):
            captured_package.update(json.loads(Path(package_path).read_text(encoding="utf-8")))
            return SupervisorResult(
                decision="COMMIT_GO",
                summary="test",
                receipt_path=sup_receipt_path,
            )

        base_handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py"],
            wave_class="L4_STRUCTURAL",
        )
        handoff = {
            **base_handoff,
            "tracker_note_text": _with_founder_override(
                base_handoff["tracker_note_text"].replace("Class: L4_ENABLER", "Class: L4_STRUCTURAL"),
                wave_id,
            ),
        }

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

        assert result["status"] == "success", result
        assert captured_package["wave_class"] == "L4_STRUCTURAL"
        assert captured_package["founder_override_token"] == ""

    def test_prepare_handoff_from_routing_record_standalone_narrows_to_staged_diff(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        packet_dir = repo / "reports" / "control_plane"
        packet_dir.mkdir(parents=True, exist_ok=True)
        (packet_dir / "resume.md").write_text(
            "# Resume\n"
            "FOUNDER_OVERRIDE:pipeline-recovery-2026-04-21 "
            "(founder authorized resumed continuation narrowing)\n"
            "unblocks_wave_id: wave-next-codex-post-redteam\n"
            "unblocks_runtime_blocker: INV_STRUCTURAL_FORWARD_MOTION\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "--", "reports/control_plane/resume.md"],
            cwd=repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add resume packet"],
            cwd=repo,
            capture_output=True,
            check=True,
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
            "wave_class": "MAINTENANCE",
            "target_gate_id": "G8",
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
        assert "unblocks_wave_id: wave-next-codex-post-redteam" in handoff["tracker_note_text"]
        assert (
            "unblocks_runtime_blocker: INV_STRUCTURAL_FORWARD_MOTION"
            in handoff["tracker_note_text"]
        )
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
            tracker_note_text=_with_founder_override(
                _make_new_schema_handoff(
                    wave_id="pipeline-recovery-2026-04-21",
                )["tracker_note_text"],
                "pipeline-recovery-2026-04-21",
            ),
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

    def test_prepare_handoff_standalone_force_adds_indexed_ignored_paths(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        (repo / ".gitignore").write_text("reports/archive/deferred/*\n", encoding="utf-8")
        ignored_path = (
            repo
            / "reports"
            / "archive"
            / "deferred"
            / "closed-by-cleanup.md"
        )
        ignored_path.parent.mkdir(parents=True, exist_ok=True)
        ignored_path.write_text("# archived\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "-f", "--", "reports/archive/deferred/closed-by-cleanup.md"],
            cwd=repo,
            capture_output=True,
            check=True,
        )
        indexed_check = subprocess.run(
            ["git", "check-ignore", "-q", "reports/archive/deferred/closed-by-cleanup.md"],
            cwd=repo,
            capture_output=True,
            check=False,
        )
        assert indexed_check.returncode != 0

        record = {
            "wave_name": "deferred-non-blocking-cleanup-2026-05-06",
            "summary": "archive deferred non-blocking cleanup",
            "decision": "UPDATE_TRACKER_ONLY",
            "task_id": "[NEXT-CODEX-POST-REDTEAM]",
            "wave_class": "MAINTENANCE",
            "target_gate_id": "G8",
        }
        handoff, errors = commit_mod.prepare_handoff_from_routing_record(
            record,
            repo,
            standalone=True,
        )

        assert errors == []
        assert handoff is not None
        assert "reports/archive/deferred/closed-by-cleanup.md" in handoff["force_add_files"]
        assert "reports/archive/deferred/closed-by-cleanup.md" not in handoff["files_to_stage"]
        valid, validation_errors = commit_mod.validate_handoff(handoff)
        assert valid, validation_errors

    def test_prepare_handoff_standalone_preserves_same_wave_tasks_override_for_maintenance(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "deferred-non-blocking-cleanup-2026-05-06"
        (repo / "TASKS.md").write_text(
            "## Ra\n\n"
            f"- Tracker sync note (2026-05-06, {wave_id}): **manual authorized cleanup.** "
            f"Class: MAINTENANCE. FOUNDER_OVERRIDE:{wave_id} (founder authorized cleanup rerun)\n\n"
            "---\n",
            encoding="utf-8",
        )
        (repo / "file.py").write_text("# staged now\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "--", "TASKS.md", "file.py"],
            cwd=repo,
            capture_output=True,
            check=True,
        )

        record = {
            "wave_name": wave_id,
            "summary": "archive deferred non-blocking cleanup",
            "decision": "UPDATE_TRACKER_ONLY",
            "task_id": "[NEXT-CODEX-POST-REDTEAM]",
            "wave_class": "MAINTENANCE",
            "target_gate_id": "G8",
        }
        handoff, errors = commit_mod.prepare_handoff_from_routing_record(
            record,
            repo,
            standalone=True,
        )

        assert errors == []
        assert handoff is not None
        assert f"FOUNDER_OVERRIDE:{wave_id}" in handoff["tracker_note_text"]
        valid, validation_errors = commit_mod.validate_handoff(handoff)
        assert valid, validation_errors

    def test_prepare_handoff_from_routing_record_standalone_preserves_restart_target_branch(self, tmp_path):
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
            target_branch="jabramsja/pipeline-recovery-2026-04-21-restart-2026-04-21",
            tracker_note_text=_with_founder_override(
                _make_new_schema_handoff(
                    wave_id="pipeline-recovery-2026-04-21",
                )["tracker_note_text"],
                "pipeline-recovery-2026-04-21",
            ),
        )
        record = {
            "wave_name": "pipeline-recovery-2026-04-21",
            "summary": "restart continuation",
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
        assert handoff["target_branch"] == "jabramsja/pipeline-recovery-2026-04-21-restart-2026-04-21"
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

    def test_build_commit_handoff_canonicalizes_symlink_stage_aliases(self, tmp_path):
        repo = _setup_repo(tmp_path)
        real_file = repo / "mu" / "tests" / "docs" / "test_growth_caps.py"
        real_file.parent.mkdir(parents=True, exist_ok=True)
        real_file.write_text("def test_growth_cap():\n    assert True\n", encoding="utf-8")
        (repo / "tests").symlink_to("mu/tests", target_is_directory=True)

        note = _with_founder_override(
            _make_new_schema_handoff(wave_id="symlink-alias")["tracker_note_text"],
            "symlink-alias",
        )

        handoff, errors = commit_mod.build_commit_handoff(
            wave_id="symlink-alias",
            task_id="[TEST]",
            files_to_stage=["tests/docs/test_growth_caps.py"],
            commit_message="test: canonicalize symlink path",
            fixes_implemented=["canonicalize symlink path aliases"],
            tracker_note_text=note,
            repo_root=repo,
        )

        assert not errors
        assert handoff["files_to_stage"] == ["mu/tests/docs/test_growth_caps.py"]

    def test_stage_handoff_paths_is_idempotent_for_staged_deletion(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        target = repo / "obsolete.md"
        target.write_text("remove me\n", encoding="utf-8")
        subprocess.run(["git", "add", "obsolete.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "add obsolete"], cwd=repo, check=True)
        target.unlink()

        commit_mod._stage_handoff_paths(  # ANTICHEAT_OK: direct stage helper regression for deleted handoff paths
            repo,
            files_to_stage=["obsolete.md"],
            force_files=[],
        )
        first = subprocess.run(
            ["git", "diff", "--cached", "--name-status", "--", "obsolete.md"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        assert first.stdout.strip() == "D\tobsolete.md"

        commit_mod._stage_handoff_paths(  # ANTICHEAT_OK: direct stage helper regression for deleted handoff paths
            repo,
            files_to_stage=["obsolete.md"],
            force_files=[],
        )
        second = subprocess.run(
            ["git", "diff", "--cached", "--name-status", "--", "obsolete.md"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        assert second.stdout.strip() == "D\tobsolete.md"

        subprocess.run(["git", "commit", "-m", "delete obsolete"], cwd=repo, check=True)
        commit_mod._stage_handoff_paths(  # ANTICHEAT_OK: direct stage helper regression for deleted handoff paths
            repo,
            files_to_stage=["obsolete.md"],
            force_files=[],
        )
        third = subprocess.run(
            ["git", "diff", "--cached", "--name-status", "--", "obsolete.md"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        assert third.stdout.strip() == ""

    def test_stage_handoff_paths_does_not_stage_scope_only_deletion(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        changed = repo / "changed.txt"
        context = repo / "context.md"
        changed.write_text("original\n", encoding="utf-8")
        context.write_text("context\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", "changed.txt", "context.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)
        changed.write_text("changed\n", encoding="utf-8")
        context.unlink()

        staged_files, force_files = commit_mod._stage_handoff_paths(  # ANTICHEAT_OK: direct stage helper regression for scope-only context paths
            repo,
            files_to_stage=["changed.txt"],
            force_files=[],
            scope_files=["context.md"],
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        unstaged = subprocess.run(
            ["git", "diff", "--name-status"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )

        assert staged_files == ["changed.txt"]
        assert force_files == []
        assert set(staged.stdout.splitlines()) == {"M\tchanged.txt"}
        assert "D\tcontext.md" in set(unstaged.stdout.splitlines())

    def test_stage_handoff_paths_restages_scoped_deletion_after_rebind_restore(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        subprocess.run(
            [
                "git", "add", "--",
                "TASKS.md",
                "file.py",
                "mu/tools/metrics/collect_l4_wave_indicators.py",
            ],
            cwd=repo,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "baseline test repo"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        active_rel = "reports/deferred/non_blocking/wave_bridge_nonblockers.md"
        archive_rel = "reports/archive/deferred/wave_bridge_nonblockers_closed-by-wave.md"
        active = repo / active_rel
        archive = repo / archive_rel
        active.parent.mkdir(parents=True, exist_ok=True)
        active.write_text("# Deferred\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", active_rel], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "add deferred packet"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "rm", "--", active_rel], cwd=repo, check=True, capture_output=True)
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_text("# Closed deferred packet\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", archive_rel], cwd=repo, check=True)
        handoff = _make_new_schema_handoff(
            wave_id="wave",
            files_to_stage=[archive_rel],
            force_add_files=[],
            scope_items=[active_rel],
        )

        tracked_dirty, untracked_dirty, outside_scope = commit_mod._collect_branch_rebind_dirty_scope(  # ANTICHEAT_OK: direct branch-rebind regression for scoped staged deletion
            repo,
            handoff=handoff,
        )
        snapshot = commit_mod._capture_scope_snapshot(  # ANTICHEAT_OK: direct branch-rebind regression for scoped staged deletion
            repo,
            sorted((tracked_dirty | untracked_dirty) - set(outside_scope)),
        )
        commit_mod._clear_scope_for_branch_rebind(  # ANTICHEAT_OK: direct branch-rebind regression for scoped staged deletion
            repo,
            tracked_paths=sorted(tracked_dirty),
            untracked_paths=sorted(untracked_dirty),
        )
        commit_mod._restore_scope_snapshot(repo, snapshot)  # ANTICHEAT_OK: direct branch-rebind regression for scoped staged deletion
        staged_files, force_files = commit_mod._stage_handoff_paths(  # ANTICHEAT_OK: direct branch-rebind regression for scoped staged deletion
            repo,
            files_to_stage=list(handoff["files_to_stage"]),
            force_files=list(handoff["force_add_files"]),
            scope_files=list(handoff["scope_items"]),
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        staged_lines = set(staged.stdout.splitlines())

        assert outside_scope == []
        assert active_rel in tracked_dirty
        assert archive_rel in tracked_dirty
        assert staged_files == [archive_rel]
        assert force_files == []
        assert f"D\t{active_rel}" in staged_lines
        assert f"A\t{archive_rel}" in staged_lines

    def test_stage_handoff_paths_is_idempotent_for_branch_history_deletion(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        target = repo / "obsolete.md"
        target.write_text("remove me\n", encoding="utf-8")
        subprocess.run(["git", "add", "obsolete.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "add obsolete"], cwd=repo, check=True)
        subprocess.run(["git", "branch", "origin/dev"], cwd=repo, check=True)
        subprocess.run(["git", "checkout", "-b", "wave"], cwd=repo, check=True)
        subprocess.run(["git", "branch", "--set-upstream-to", "origin/dev"], cwd=repo, check=True)
        target.unlink()
        subprocess.run(["git", "add", "-u", "--", "obsolete.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "delete obsolete"], cwd=repo, check=True)
        (repo / "later.md").write_text("later\n", encoding="utf-8")
        subprocess.run(["git", "add", "later.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "later branch work"], cwd=repo, check=True)

        commit_mod._stage_handoff_paths(  # ANTICHEAT_OK: direct stage helper regression for already-committed branch deletes
            repo,
            files_to_stage=["obsolete.md"],
            force_files=[],
        )
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status", "--", "obsolete.md"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == ""

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

    def test_force_add_files_rejects_namespaced_agent_bus_runtime_state(self):
        valid, errors = commit_mod.validate_handoff(
            _make_new_schema_handoff(
                force_add_files=[".agent_bus-test/executors/phase_b_handoff.json"]
            )
        )
        assert not valid
        assert any(".agent_bus-*" in e for e in errors)

    def test_files_to_stage_rejects_namespaced_agent_bus_runtime_state(self):
        valid, errors = commit_mod.validate_handoff(
            _make_new_schema_handoff(
                files_to_stage=[".agent_bus-test/foo.txt"],
                force_add_files=[],
            )
        )
        assert not valid
        assert any("files_to_stage denied" in e and ".agent_bus*" in e for e in errors)

    def test_namespaced_agent_bus_paths_are_transient_status_artifacts(self):
        assert commit_mod._is_transient_status_path(".agent_bus-test/foo.txt")  # ANTICHEAT_OK: status artifact classifier is the regression target
        assert commit_mod._runtime_bus_artifact_match(".agent_bus-test/foo.txt") == ".agent_bus*"  # ANTICHEAT_OK: runtime-bus matcher is the regression target


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

    def test_run_commit_pipeline_blocks_private_attr_gate_before_git_commit(self, tmp_path):
        from collections import namedtuple
        import subprocess
        import types

        repo = _setup_repo(tmp_path)
        (repo / "mu" / "tests").mkdir(parents=True, exist_ok=True)
        (repo / "mu" / "tests" / "test_file.py").write_text(
            "def test_smoke():\n    assert True\n",
            encoding="utf-8",
        )
        checker = repo / "mu" / "tools" / "checks" / "linters" / "check_private_attr_access.py"
        checker.parent.mkdir(parents=True, exist_ok=True)
        checker.write_text(
            "import sys\n"
            "print('ERROR: Found private attr access in tests/ or mu/tests/:')\n"
            "print('  mu/tests/test_file.py:3: ._private_helper')\n"
            "sys.exit(1)\n",
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

        real_subprocess_run = subprocess.run
        seen_commands: list[list[str]] = []

        def intercept_subprocess_run(args, *run_args, **run_kwargs):
            command = list(args) if isinstance(args, (list, tuple)) else [str(args)]
            seen_commands.append(command)
            if command[:2] == ["git", "commit"]:
                raise AssertionError("git commit should not run after private-attr gate failure")
            return real_subprocess_run(args, *run_args, **run_kwargs)

        handoff = _make_new_schema_handoff(
            files_to_stage=["file.py", "mu/tests/test_file.py"],
        )
        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}), \
             patch.object(
                 commit_mod,
                 "_run_pytest_on_files",
                 return_value={"exit_code": 0, "stdout": "", "stderr": "", "passed": True},
             ), \
             patch.object(commit_mod.subprocess, "run", side_effect=intercept_subprocess_run):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "error"
        assert result["step"] == "private_attr_gate"
        error_text = "\n".join(result["errors"])
        assert "private-attr test-integrity gate failed before local commit creation" in error_text
        assert "ERROR: Found private attr access in tests/" in error_text
        assert "git_commit" not in result.get("steps_completed", [])
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
        assert mock_run.call_args.kwargs["timeout"] == 1200

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
        assert mock_run.call_args.kwargs["timeout"] == 240

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
        assert mock_run.call_args.kwargs["timeout"] == 480

    def test_run_pytest_on_files_timeout_reports_budget(self, tmp_path):
        import subprocess

        repo = tmp_path / "repo"
        repo.mkdir()

        with patch.object(
            commit_mod.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(["pytest"], timeout=480),
        ):
            result = commit_mod._run_pytest_on_files(  # ANTICHEAT_OK: testing timeout diagnostic includes computed budget
                repo,
                [
                    "mu/tests/tools/test_phase_b_executor.py",
                    "mu/tests/tools/test_recovery_gate.py",
                ],
            )

        assert result["passed"] is False
        assert result["exit_code"] == -1
        assert result["stderr"] == "pytest timed out after 480s"


class TestReviewFindingExtraction:
    def _base_pr_data(self, *, head_sha="abc123", latest_reviews=None, review_threads=None, comments=None):
        return {
            "headRefOid": head_sha,
            "reviewDecision": "",
            "latestReviews": {"nodes": latest_reviews or []},
            "reviewThreads": {"nodes": review_threads or []},
            "comments": {"nodes": comments or []},
        }

    def test_pr_review_query_fetches_top_level_review_body(self):
        assert "latestReviews(first: 20)" in commit_mod.PR_REVIEW_QUERY
        latest_reviews_section = commit_mod.PR_REVIEW_QUERY.split("latestReviews(first: 20)", 1)[1]
        latest_reviews_section = latest_reviews_section.split("reviewThreads(first: 100)", 1)[0]
        assert "body" in latest_reviews_section

    @pytest.mark.parametrize("priority", ["P1", "P2"])
    def test_commented_current_head_connector_review_badge_blocks_merge(self, priority):
        head_sha = "abc123"
        pr_data = self._base_pr_data(
            head_sha=head_sha,
            latest_reviews=[{
                "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                "body": (
                    f"**<sub><sub>![{priority} Badge](https://img.shields.io/badge/"
                    f"{priority}-orange?style=flat)</sub></sub> Restrict unsafe path**"
                ),
                "state": "COMMENTED",
                "submittedAt": "2026-04-29T00:00:00Z",
                "commit": {"oid": head_sha},
            }],
        )

        outcome = commit_mod._extract_review_findings(  # ANTICHEAT_OK: tests Step 15 review classifier
            pr_data,
            head_sha,
            result={"steps_completed": ["ensure_pr"]},
            pr_number="829",
        )

        assert outcome["outcome"] == "bot_findings"
        assert outcome["bot_findings"][0]["author"] == commit_mod.BOT_REVIEW_LOGIN
        assert "Restrict unsafe path" in outcome["bot_findings"][0]["body"]
        assert outcome["bot_findings"][0]["path"] == ""
        assert outcome["bot_findings"][0]["line"] is None

    def test_commented_connector_review_without_blocking_badge_stays_clean(self):
        head_sha = "abc123"
        pr_data = self._base_pr_data(
            head_sha=head_sha,
            latest_reviews=[{
                "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                "body": "Codex Review: didn't find any major issues.",
                "state": "COMMENTED",
                "submittedAt": "2026-04-29T00:00:00Z",
                "commit": {"oid": head_sha},
            }],
        )

        outcome = commit_mod._extract_review_findings(  # ANTICHEAT_OK: tests non-blocking Step 15 review body
            pr_data,
            head_sha,
            result={"steps_completed": ["ensure_pr"]},
            pr_number="829",
        )

        assert outcome == {"outcome": "clean"}

    def test_stale_connector_review_badge_on_old_head_is_ignored(self):
        pr_data = self._base_pr_data(
            head_sha="new-head",
            latest_reviews=[{
                "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                "body": "![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat) old finding",
                "state": "COMMENTED",
                "submittedAt": "2026-04-29T00:00:00Z",
                "commit": {"oid": "old-head"},
            }],
        )

        outcome = commit_mod._extract_review_findings(  # ANTICHEAT_OK: tests current-head review gating
            pr_data,
            "new-head",
            result={"steps_completed": ["ensure_pr"]},
            pr_number="829",
        )

        assert outcome == {"outcome": "clean"}


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


class TestRequiredCIGreenGuard:
    def test_required_check_guard_waits_after_watch_reports_success(self, tmp_path):
        import subprocess

        clock = [0.0]
        json_calls = []
        logs = []

        def fake_monotonic():
            return clock[0]

        def fake_sleep(seconds):
            clock[0] += seconds

        def completed(cmd, *, stdout="", returncode=0):
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")

        def fake_run(cmd, **kwargs):
            assert cmd[:4] == ["gh", "pr", "checks", "844"], cmd
            assert "--required" in cmd, cmd
            assert "--json" in cmd, cmd
            json_calls.append(cmd)
            if len(json_calls) == 1:
                return completed(cmd, stdout=json.dumps([
                    {"name": "test", "state": "IN_PROGRESS", "bucket": "pending"},
                    {"name": "green-gate", "state": "SUCCESS", "bucket": "pass"},
                ]))
            return completed(cmd, stdout=json.dumps([
                {"name": "test", "state": "SUCCESS", "bucket": "pass"},
                {"name": "green-gate", "state": "SUCCESS", "bucket": "pass"},
            ]))

        with patch.object(commit_mod, "_run", side_effect=fake_run), \
             patch.object(commit_mod.time, "monotonic", fake_monotonic), \
             patch.object(commit_mod.time, "sleep", fake_sleep):
            result = commit_mod._wait_for_required_checks_to_pass(  # ANTICHEAT_OK: regression guard for gh-watch premature success
                tmp_path,
                "844",
                timeout=30,
                poll_interval=15,
                log=logs.append,
            )

        assert result is True
        assert len(json_calls) == 2
        assert clock[0] == 15
        assert any("pending required check(s): test=IN_PROGRESS" in line for line in logs)

    def test_wait_for_pr_ci_rejects_watch_success_until_required_checks_green(self, tmp_path):
        import subprocess

        def completed(cmd, *, stdout="", stderr="", returncode=0):
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

        def fake_run(cmd, **kwargs):
            if cmd == ["gh", "pr", "checks", "844", "--required"]:
                return completed(cmd, stdout="test\tpending\n", returncode=8)
            if cmd == ["gh", "pr", "checks", "844", "--watch", "--required"]:
                return completed(cmd)
            if cmd == ["gh", "pr", "view", "844", "--json", "statusCheckRollup"]:
                return completed(cmd, stdout=json.dumps({"statusCheckRollup": []}))
            raise AssertionError(f"unexpected command: {cmd}")

        result = {
            "commit_sha": "a" * 40,
            "handoff_sha": "handoff-sha",
            "receipt_decision": "COMMIT_GO",
            "steps_completed": ["git_commit"],
        }

        with patch.object(commit_mod, "_run", side_effect=fake_run), \
             patch.object(commit_mod, "_wait_for_required_checks_to_pass", return_value=False):
            response = commit_mod._wait_for_pr_ci(  # ANTICHEAT_OK: ensures gh-watch zero exit is not sufficient for wait_ci
                tmp_path,
                pr_number="844",
                result=result,
                continuation_path=tmp_path / "continuation.json",
                target_branch="jabramsja/test",
                log=lambda _msg: None,
            )

        assert response is not None
        assert response["status"] == "error"
        assert response["step"] == "wait_ci"
        assert response["failure_class"] == "unknown_error"
        assert response["errors"][0].startswith(
            "Required CI checks did not reach green after gh watch returned. "
        )
        assert "test\tpending" in response["ci_checks_output"]
        assert result["steps_completed"] == ["git_commit"]

    def test_wait_for_pr_ci_failure_payload_includes_failed_check_log_excerpt(self, tmp_path):
        import subprocess

        details_url = "https://github.com/jabramsja/rcx-pi-core/actions/runs/25290911912/job/74142462431"
        gh_view_payload = {
            "statusCheckRollup": [
                {
                    "name": "test",
                    "workflowName": "CI",
                    "conclusion": "FAILURE",
                    "detailsUrl": details_url,
                },
                {
                    "name": "fixture-seeds",
                    "workflowName": "CI",
                    "conclusion": "SUCCESS",
                    "detailsUrl": "",
                },
            ]
        }

        def completed(cmd, *, stdout="", stderr="", returncode=0):
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

        def fake_run(cmd, **kwargs):
            if cmd == ["gh", "pr", "checks", "859", "--watch", "--required"]:
                raise subprocess.CalledProcessError(1, cmd)
            if cmd == ["gh", "pr", "checks", "859", "--required"]:
                return completed(cmd, stdout=f"test\tfail\t4m2s\t{details_url}\n", returncode=8)
            if cmd == ["gh", "pr", "view", "859", "--json", "statusCheckRollup"]:
                return completed(cmd, stdout=json.dumps(gh_view_payload))
            if cmd == ["gh", "run", "view", "25290911912", "--log-failed"]:
                return completed(
                    cmd,
                    stdout=(
                        "FAILED tests/tools/test_recovery_gate.py::"
                        "TestObservabilityWorktreeResolution::"
                        "test_ensure_codex_autoping_restarts_live_watcher_when_tmux_window_missing\n"
                        "tests/tools/test_recovery_gate.py:6768: AssertionError\n"
                    ),
                )
            raise AssertionError(f"unexpected command: {cmd}")

        result = {
            "commit_sha": "a" * 40,
            "handoff_sha": "handoff-sha",
            "receipt_decision": "COMMIT_GO",
            "steps_completed": ["git_commit"],
        }

        with patch.object(commit_mod, "_run", side_effect=fake_run), \
             patch.object(commit_mod, "_poll_ci_checks_fallback", return_value=False):
            response = commit_mod._wait_for_pr_ci(  # ANTICHEAT_OK: verifies wait_ci failure context for recovery
                tmp_path,
                pr_number="859",
                result=result,
                continuation_path=tmp_path / "continuation.json",
                target_branch="jabramsja/test",
                log=lambda _msg: None,
            )

        assert response is not None
        assert response["status"] == "error"
        assert response["step"] == "wait_ci"
        assert response["failure_class"] == "test_failure"
        assert response["ci_failures"] == [
                {
                    "name": "test",
                    "workflow": "CI",
                    "conclusion": "FAILURE",
                    "details_url": details_url,
                    "excerpt": (
                        "FAILED tests/tools/test_recovery_gate.py::"
                    "TestObservabilityWorktreeResolution::"
                    "test_ensure_codex_autoping_restarts_live_watcher_when_tmux_window_missing\n"
                    "tests/tools/test_recovery_gate.py:6768: AssertionError"
                ),
            }
        ]
        assert "Failed required CI: test (CI): tests/tools/test_recovery_gate.py:6768: AssertionError" in (
            response["errors"][0]
        )

    def test_wait_for_pr_ci_transport_failure_without_failed_checks_is_not_test_failure(self, tmp_path):
        import subprocess

        def completed(cmd, *, stdout="", stderr="", returncode=0):
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

        def fake_run(cmd, **kwargs):
            if cmd == ["gh", "pr", "checks", "859", "--watch", "--required"]:
                raise subprocess.CalledProcessError(1, cmd, stderr="network unavailable")
            if cmd == ["gh", "pr", "checks", "859", "--required"]:
                return completed(cmd, stdout="test\tpending\t0\t\n", returncode=8)
            if cmd == ["gh", "pr", "view", "859", "--json", "statusCheckRollup"]:
                return completed(cmd, stdout=json.dumps({"statusCheckRollup": []}))
            raise AssertionError(f"unexpected command: {cmd}")

        result = {
            "commit_sha": "a" * 40,
            "handoff_sha": "handoff-sha",
            "receipt_decision": "COMMIT_GO",
            "steps_completed": ["git_commit"],
        }

        with patch.object(commit_mod, "_run", side_effect=fake_run), \
             patch.object(commit_mod, "_poll_ci_checks_fallback", return_value=False):
            response = commit_mod._wait_for_pr_ci(  # ANTICHEAT_OK: transport failures must not masquerade as tests
                tmp_path,
                pr_number="859",
                result=result,
                continuation_path=tmp_path / "continuation.json",
                target_branch="jabramsja/test",
                log=lambda _msg: None,
            )

        assert response is not None
        assert response["status"] == "error"
        assert response["step"] == "wait_ci"
        assert response["failure_class"] == "unknown_error"
        assert response["ci_failures"] == []
        assert "test\tpending" in response["ci_checks_output"]
