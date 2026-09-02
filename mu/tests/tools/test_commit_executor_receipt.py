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
meta_bridge_mod = load_module(
    "meta_bridge_supervisor_for_commit_receipt_tests",
    REPO_ROOT / "mu" / "tools" / "agents" / "meta_bridge_supervisor.py",
)
pager_mod = load_module(
    "pipeline_agent_pager",
    REPO_ROOT / "mu" / "tools" / "observability" / "pipeline_agent_pager.py",
)
recovery_gate_mod = load_module(
    "recovery_gate_for_commit_executor_receipt_tests",
    REPO_ROOT / "mu" / "tools" / "executors" / "recovery_gate.py",
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


def _write_pager_config(repo_root: Path, *, route: str = "both") -> None:
    config_path = repo_root / "mu" / "tools" / "executors" / "executor_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps({"pipeline_agent_pager": {"enabled": True, "route": route}}) + "\n",
        encoding="utf-8",
    )


def _write_bot_remediation_executor_config(
    repo_root: Path,
    *,
    backend: str = "claude",
    raw_config: object | None = None,
) -> Path:
    config_path = repo_root / "mu" / "tools" / "executors" / "executor_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if raw_config is None:
        raw_config = {"backends": {"bot_remediation": backend}}
    config_path.write_text(json.dumps(raw_config) + "\n", encoding="utf-8")
    return config_path


def _valid_supervisor_package() -> dict:
    return {
        "task_id": "[TEST]",
        "wave_name": "test-wave",
        "lane": "phase_b",
        "changed_files": ["file.py"],
        "fenced_files": [],
        "scope_items": ["file.py"],
        "fixes_implemented": ["test fix"],
        "deferred_items": [],
        "bridge_status": {},
        "evidence_handles": {},
        "blocker_report_paths": [],
        "current_judgment": "COMMIT_GO",
        "founder_override_token": "",
        "wave_class": "L4_ENABLER",
        "tracker_note_text": "",
        "evidence_command": "",
    }


def test_no_env_commit_retry_handoff_route_drives_commit_and_supervisor_events(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_pager_config(repo, route="both")
    monkeypatch.delenv("RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE", raising=False)

    deliveries: list[str] = []

    def ack_target(repo_root, target, event, state, config, *, timeout_s):
        deliveries.append(target)
        return {
            "acknowledged": True,
            "ack": {
                "acknowledged_at": "2026-06-30T00:00:00+00:00",
                "target": target,
            },
        }

    monkeypatch.setattr(pager_mod, "_dispatch_target", ack_target)
    handoff = _make_new_schema_handoff(pager_route="codex")

    def emit_via_test_pager(repo_root, **kwargs):
        return pager_mod.emit_transition_event(repo_root, **kwargs)

    with patch.object(commit_mod, "emit_pipeline_agent_event", side_effect=emit_via_test_pager), \
         patch.object(commit_mod, "_run_commit_pipeline_impl", return_value={
             "status": "success",
             "steps_completed": ["validate_inputs"],
             "commit_sha": "abc123",
         }):
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        package_path = repo / ".scratch" / "auto_supervisor_package.json"
        package_path.parent.mkdir(parents=True, exist_ok=True)
        supervisor_package = _valid_supervisor_package()
        assert "pager_route" not in supervisor_package
        schema_valid, schema_errors = meta_bridge_mod.validate_package_schema(supervisor_package)
        assert schema_valid, schema_errors
        package_path.write_text(json.dumps(supervisor_package) + "\n", encoding="utf-8")
        commit_mod._emit_pre_commit_supervisor_lifecycle_event(  # ANTICHEAT_OK: locks explicit route propagation into pre-commit supervisor pager events
            repo,
            package_path,
            event_type="pre_commit_supervisor_started",
            state="started",
            route="codex",
        )

    assert result["status"] == "success"
    assert deliveries == ["codex", "codex", "codex"]
    state = json.loads(
        (repo / ".agent_bus" / "observability" / "pipeline_agent_pager_state.json").read_text(
            encoding="utf-8"
        )
    )
    entries = list(state["events"].values())
    assert {entry["route"] for entry in entries} == {"codex"}
    assert all(entry["requested_targets"] == ["codex"] for entry in entries)


def test_default_structural_tracker_note_l4_files_command_includes_indicator_artifact():
    wave_id = "standalone-structural-indicator-proof"
    note = commit_mod._build_default_tracker_note_text(  # ANTICHEAT_OK: locks standalone structural tracker evidence
        wave_id=wave_id,
        wave_class="L4_STRUCTURAL",
        target_gate_id="G8",
        commit_message="feat: structural proof",
        files_to_stage=[
            "mu/host/python/rcx_pi/selfhost/step_mu.py",
            "mu/tests/l4_gates/test_kernel_run_result_contract.py",
        ],
        tracked_packet=f"reports/control_plane/{wave_id}.md",
    )

    indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
    assert f"indicator_artifact_ref: {indicator_path}" in note
    assert "tools/checks/enforce_l4_execution_contract.py --files" in note
    assert f"mu/tests/l4_gates/test_kernel_run_result_contract.py {indicator_path}" in note
    assert f"--wave-id {wave_id} --wave-class L4_STRUCTURAL" in note


def test_classless_comment_runtime_override_is_canonical_tracker_note_line():
    wave_id = "classless-comment-runtime-2026-05-20"
    line = (
        f"- Tracker sync note (2026-05-20, {wave_id}): **TEST.** "
        "contract_path: classless FOUNDER_OVERRIDE comment-only runtime override. "
        "target_gate_id: G8. no_op_proof: comment-only runtime text. "
        f"FOUNDER_OVERRIDE:{wave_id}. "
        "primary_blocker_class: INTEGRATION. "
        "primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION."
    )

    assert commit_mod._is_canonical_tracker_note_line(line, wave_id)  # ANTICHEAT_OK: locks classless tracker-note acceptance


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


def test_validate_tracker_note_rejects_setroles_show_evidence_command():
    """Guard: a tracker-note evidence_command that reads env-aware EFFECTIVE role
    state (`set_roles.py --show`) is rejected at build time; a committed-state
    read is accepted unchanged.

    Regression for the 2026-05-30 standalone NEEDS_PHASE_B footgun where an
    env-aware evidence_command contradicted the committed-config claim and the
    pre-commit supervisor rejected the package only after gates 1-10 had passed.
    """
    wave_id = "commit-evidence-guard-setroles-show-2026-06-01"

    def _note_with_evidence_command(evidence_command: str) -> str:
        return (
            f"- Tracker sync note (2026-06-01, {wave_id}): **TEST evidence-command guard.** "
            "Class: L4_ENABLER. target_gate_id: G8. "
            f"evidence_command: `{evidence_command}`. "
            "evidence_delta: (1) guard rejects env-aware reads. (2) test covers it. "
            "(3) indicator binds the wave. "
            "progress_proof_before: no guard. progress_proof_after: guard asserted. "
            "primary_blocker_class: INTEGRATION. "
            "primary_invariant_id: INV_TYPED_FAIL_CLOSED_OUTCOMES. "
            f"indicator_artifact_ref: reports/l4_wave_indicators/{wave_id}.json. "
            "indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py "
            f"--wave-id {wave_id} --output reports/l4_wave_indicators/{wave_id}.json. "
            "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            "boot0_track_id: V1. boot0_progress_state: HOLD."
        )

    # REJECT: env-aware effective-state read (the exact observed footgun).
    reject_errors = commit_mod._validate_tracker_note_text(  # ANTICHEAT_OK: locks the set_roles.py --show evidence-command guard
        tracker_note_text=_note_with_evidence_command(
            "python3 mu/tools/executors/set_roles.py --show"
        ),
        wave_id=wave_id,
        wave_class="L4_ENABLER",
        target_gate_id="G8",
    )
    assert any("set_roles.py --show" in e for e in reject_errors), reject_errors
    # The rejection message must name a committed-state-read alternative.
    assert any(
        "executor_config.json" in e and "git diff" in e for e in reject_errors
    ), reject_errors

    # ACCEPT: a committed-state read is unaffected (no guard error; note valid).
    accept_errors = commit_mod._validate_tracker_note_text(  # ANTICHEAT_OK: locks the committed-state evidence-command accept path
        tracker_note_text=_note_with_evidence_command(
            "grep -A2 role_agents mu/tools/executors/executor_config.json"
        ),
        wave_id=wave_id,
        wave_class="L4_ENABLER",
        target_gate_id="G8",
    )
    assert accept_errors == [], accept_errors


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


def test_post_commit_continuation_rekeys_phase_b_handoff_refresh(tmp_path):
    import subprocess

    repo = _setup_repo(tmp_path)
    wave_id = "continuation-rekey-wave"
    target_branch = f"jabramsja/{wave_id}"
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "checkout", "-b", target_branch],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (repo / "file.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "wave commit"], cwd=repo, check=True, capture_output=True)
    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    continuation_path = commit_mod._continuation_record_path(repo, wave_id)  # ANTICHEAT_OK
    continuation_path.parent.mkdir(parents=True, exist_ok=True)
    continuation_path.write_text(
        json.dumps(
            {
                "version": commit_mod.COMMIT_CONTINUATION_VERSION,
                "status": commit_mod.CONTINUATION_ACTIVE_STATUS,
                "handoff_sha": "old-phase-b-handoff-sha",
                "target_branch": target_branch,
                "commit_sha": head_sha,
                "receipt_decision": "COMMIT_GO",
                "steps_completed": ["validate_inputs", "ensure_feature_branch", "git_commit"],
                "updated_at_unix": 0,
            }
        ),
        encoding="utf-8",
    )
    packet = f"reports/control_plane/{wave_id}_2026-05-21.md"
    refreshed_handoff = _make_new_schema_handoff(
        wave_id=wave_id,
        target_branch=target_branch,
        tracked_packet=packet,
        files_to_stage=["file.py", packet],
        force_add_files=[packet],
    )
    refreshed_handoff_sha = _canonical_handoff_sha_for_test(refreshed_handoff)

    loaded = commit_mod._load_post_commit_continuation(  # ANTICHEAT_OK: direct continuation loader regression
        continuation_path,
        repo_root=repo,
        handoff_sha=refreshed_handoff_sha,
        target_branch=target_branch,
        wave_id=wave_id,
        handoff=refreshed_handoff,
    )

    assert loaded is not None
    assert loaded["handoff_sha"] == refreshed_handoff_sha
    blocked = commit_mod._load_post_commit_continuation(  # ANTICHEAT_OK: mismatched non-packet handoff must not rekey
        continuation_path,
        repo_root=repo,
        handoff_sha="different-handoff-sha",
        target_branch=target_branch,
        wave_id=wave_id,
        handoff={**refreshed_handoff, "tracked_packet": f"reports/deferred/{wave_id}.md"},
    )
    assert blocked is None


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


def test_tracker_followup_preserves_multiple_historical_lines_when_clean():
    wave_id = "multi-followup-clean-wave"
    tracker_note = _make_new_schema_handoff(wave_id=wave_id)["tracker_note_text"]
    first_followup = (
        f"- Tracker sync follow-up (2026-05-21T00:00:00Z, {wave_id}): "
        "same-wave follow-up commit touched tracker-relevant file(s) without "
        "phase/task-state change: mu/host/js/engine/kernel.js.\n"
    )
    second_followup = (
        f"- Tracker sync follow-up (2026-05-21T00:10:00Z, {wave_id}): "
        "same-wave pipeline recovery follow-up touched tracker-relevant executor files "
        "without runtime semantic change: mu/tools/executors/recovery_gate.py.\n"
    )
    lines = [
        "## Ra\n",
        "\n",
        tracker_note + "\n",
        first_followup,
        second_followup,
        "---\n",
    ]
    original = list(lines)

    modified, error, action = commit_mod._sync_tracker_followup_line(  # ANTICHEAT_OK: direct tracker-ledger regression
        lines,
        wave_id=wave_id,
        canonical_idx=2,
        tracker_followup_indices=[3, 4],
        tracker_paths=[],
        tracker_file_staged=False,
    )

    assert (modified, error, action) == (False, None, None)
    assert lines == original

    new_path = "mu/tools/executors/commit_executor.py"
    modified, error, action = commit_mod._sync_tracker_followup_line(  # ANTICHEAT_OK: direct tracker-ledger regression
        lines,
        wave_id=wave_id,
        canonical_idx=2,
        tracker_followup_indices=[3, 4],
        tracker_paths=[new_path],
        tracker_file_staged=False,
    )

    assert (modified, error, action) == (True, None, "inserted")
    followup_lines = [
        line for line in lines
        if line.startswith("- Tracker sync follow-up") and wave_id in line
    ]
    assert len(followup_lines) == 3
    assert new_path in followup_lines[-1]


def test_tracker_followup_reemits_existing_scope_when_tracker_not_staged():
    wave_id = "multi-followup-restaged-wave"
    tracker_note = _make_new_schema_handoff(wave_id=wave_id)["tracker_note_text"]
    kernel_path = "mu/host/js/engine/kernel.js"
    pipeline_path = "mu/host/js/engine/pipeline.js"
    first_followup = (
        f"- Tracker sync follow-up (2026-05-21T00:00:00Z, {wave_id}): "
        "same-wave follow-up commit touched tracker-relevant file(s) without "
        f"phase/task-state change: {kernel_path}, {pipeline_path}.\n"
    )
    second_followup = (
        f"- Tracker sync follow-up (2026-05-21T00:10:00Z, {wave_id}): "
        "same-wave pipeline recovery follow-up touched tracker-relevant executor files "
        "without runtime semantic change: mu/tools/executors/recovery_gate.py.\n"
    )
    lines = [
        "## Ra\n",
        "\n",
        tracker_note + "\n",
        first_followup,
        second_followup,
        "---\n",
    ]

    modified, error, action = commit_mod._sync_tracker_followup_line(  # ANTICHEAT_OK: direct tracker-ledger regression
        lines,
        wave_id=wave_id,
        canonical_idx=2,
        tracker_followup_indices=[3, 4],
        tracker_paths=[kernel_path, pipeline_path],
        tracker_file_staged=False,
    )

    assert (modified, error, action) == (True, None, "inserted")
    followup_lines = [
        line for line in lines
        if line.startswith("- Tracker sync follow-up") and wave_id in line
    ]
    assert len(followup_lines) == 3
    assert kernel_path in followup_lines[-1]
    assert pipeline_path in followup_lines[-1]

    staged_lines = [
        "## Ra\n",
        "\n",
        tracker_note + "\n",
        first_followup,
        second_followup,
        "---\n",
    ]
    modified, error, action = commit_mod._sync_tracker_followup_line(  # ANTICHEAT_OK: direct tracker-ledger regression
        staged_lines,
        wave_id=wave_id,
        canonical_idx=2,
        tracker_followup_indices=[3, 4],
        tracker_paths=[kernel_path, pipeline_path],
        tracker_file_staged=True,
    )

    assert (modified, error, action) == (False, None, None)


def test_structural_staged_followup_retargets_supervisor_class_when_branch_range_has_runtime():
    staged_files = [
        "TASKS.md",
        "mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py",
        "reports/control_plane/wave.md",
    ]
    branch_range_files = [
        "mu/host/js/core/seed_loader.js",
        "mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py",
    ]

    wave_class = commit_mod._supervisor_wave_class_for_staged_scope(  # ANTICHEAT_OK
        "L4_STRUCTURAL",
        staged_changed_files=staged_files,
        branch_range_files=branch_range_files,
    )

    assert wave_class == "L4_ENABLER"


def test_structural_initial_scope_keeps_supervisor_class_when_staged_runtime_present():
    staged_files = [
        "mu/host/js/core/seed_loader.js",
        "mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py",
    ]

    wave_class = commit_mod._supervisor_wave_class_for_staged_scope(  # ANTICHEAT_OK
        "L4_STRUCTURAL",
        staged_changed_files=staged_files,
        branch_range_files=staged_files,
    )

    assert wave_class == "L4_STRUCTURAL"


def test_dirty_tracker_followup_paths_ignore_clean_handoff_runtime_paths(tmp_path):
    import subprocess

    repo = _setup_repo(tmp_path)
    runtime_path = repo / "mu" / "host" / "js" / "core" / "seed_loader.js"
    control_path = repo / "mu" / "tools" / "executors" / "commit_executor.py"
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    control_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text("// already committed runtime\n", encoding="utf-8")
    control_path.write_text("# committed control\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "--", "mu/host/js/core/seed_loader.js", "mu/tools/executors/commit_executor.py"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "baseline files"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    control_path.write_text("# dirty control\n", encoding="utf-8")

    tracker_paths = commit_mod._dirty_tracker_relevant_paths_for_handoff(  # ANTICHEAT_OK
        repo,
        [
            "mu/host/js/core/seed_loader.js",
            "mu/tools/executors/commit_executor.py",
        ],
        [],
    )

    assert tracker_paths == ["mu/tools/executors/commit_executor.py"]


def test_tracker_followup_refreshes_when_canonical_note_updates(tmp_path):
    import subprocess

    repo = _setup_repo(tmp_path)
    wave_id = "tracker-followup-canonical-update-wave"
    runtime_rel = "mu/host/js/core/seed_loader.js"
    control_rel = "mu/tools/executors/commit_executor.py"
    runtime_path = repo / runtime_rel
    control_path = repo / control_rel
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    control_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text("// already committed runtime\n", encoding="utf-8")
    control_path.write_text("# committed control\n", encoding="utf-8")
    old_tracker_note = _make_new_schema_handoff(
        wave_id=wave_id,
        target_gate_id="G7",
    )["tracker_note_text"]
    stale_followup = (
        f"- Tracker sync follow-up (2026-05-17T00:00:00Z, {wave_id}): "
        "same-wave follow-up commit touched tracker-relevant file(s) without "
        f"phase/task-state change: {runtime_rel}.\n"
    )
    (repo / "TASKS.md").write_text(
        f"## Ra\n\n{old_tracker_note}\n{stale_followup}\n---\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "baseline tracker state"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    control_path.write_text("# dirty control follow-up\n", encoding="utf-8")

    handoff = _make_new_schema_handoff(
        wave_id=wave_id,
        target_gate_id="G8",
        files_to_stage=[runtime_rel, control_rel],
        scope_items=[runtime_rel, control_rel],
        fixes_implemented=["refresh stale tracker follow-up from dirty staged paths"],
    )
    with patch.object(
        commit_mod,
        "_load_repo_meta_bridge_client",
        side_effect=ImportError("stop after tracker sync"),
    ):
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

    assert result["step"] == "build_and_run_supervisor"
    tasks_content = (repo / "TASKS.md").read_text(encoding="utf-8")
    assert "target_gate_id: G8" in tasks_content
    followup_lines = [
        line for line in tasks_content.splitlines()
        if line.startswith("- Tracker sync follow-up") and wave_id in line
    ]
    assert len(followup_lines) == 1
    assert control_rel in followup_lines[0]
    assert runtime_rel not in followup_lines[0]


def test_tracker_note_update_preserves_structural_canonical_note_for_control_repair(tmp_path):
    import subprocess

    repo = _setup_repo(tmp_path)
    wave_id = "same-wave-structural-control-repair"
    runtime_rel = "mu/host/js/engine/routing.js"
    control_rel = "mu/tools/executors/phase_b_executor.py"
    runtime_path = repo / runtime_rel
    control_path = repo / control_rel
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    control_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text("// committed runtime\n", encoding="utf-8")
    control_path.write_text("# committed control\n", encoding="utf-8")
    structural_note = (
        f"- Tracker sync note (2026-05-21, {wave_id}): **Structural runtime proof.** "
        "Class: L4_STRUCTURAL. target_gate_id: G8. workload_target: host_debt_reduction. "
        "host_semantics_delta_before: runtime/substrate scope must remain structurally governed. "
        "host_semantics_delta_after: runtime/substrate scope remains governed by structural proof. "
        f"structural_artifact_ref: {runtime_rel}. "
        "evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`. "
        "post_gate_contract_sweep: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/structural/ mu/tests/parity/`.\n"
    )
    (repo / "TASKS.md").write_text(f"## Ra\n\n{structural_note}\n---\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "baseline structural tracker note"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    control_path.write_text("# dirty control repair\n", encoding="utf-8")

    handoff = _make_new_schema_handoff(
        wave_id=wave_id,
        wave_class="L4_ENABLER",
        files_to_stage=[control_rel],
        scope_items=[control_rel],
        fixes_implemented=["preserve structural tracker note during control repair"],
    )
    with patch.object(
        commit_mod,
        "_load_repo_meta_bridge_client",
        side_effect=ImportError("stop after tracker sync"),
    ):
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

    assert result["step"] == "build_and_run_supervisor"
    tasks_content = (repo / "TASKS.md").read_text(encoding="utf-8")
    canonical_lines = [
        line for line in tasks_content.splitlines()
        if line.startswith("- Tracker sync note") and wave_id in line
    ]
    assert canonical_lines == [structural_note.rstrip("\n")]
    followup_lines = [
        line for line in tasks_content.splitlines()
        if line.startswith("- Tracker sync follow-up") and wave_id in line
    ]
    assert len(followup_lines) == 1
    assert control_rel in followup_lines[0]


def test_tracker_followup_ignores_clean_declared_tracker_file(tmp_path):
    import subprocess

    repo = _setup_repo(tmp_path)
    wave_id = "tracker-followup-clean-declared-tasks-wave"
    runtime_rel = "mu/host/python/rcx_pi/selfhost/step_mu.py"
    pipeline_rel = "mu/tools/executors/commit_executor.py"
    runtime_path = repo / runtime_rel
    pipeline_path = repo / pipeline_rel
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    pipeline_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text("# committed runtime\n", encoding="utf-8")
    pipeline_path.write_text("# committed pipeline\n", encoding="utf-8")
    tracker_note = _make_new_schema_handoff(wave_id=wave_id)["tracker_note_text"]
    (repo / "TASKS.md").write_text(f"## Ra\n\n{tracker_note}\n---\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "baseline tracker state"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    runtime_path.write_text("# dirty runtime follow-up\n", encoding="utf-8")
    pipeline_path.write_text("# dirty pipeline follow-up\n", encoding="utf-8")
    subprocess.run(["git", "add", "--", runtime_rel, pipeline_rel], cwd=repo, check=True, capture_output=True)

    handoff = _make_new_schema_handoff(
        wave_id=wave_id,
        files_to_stage=["TASKS.md", runtime_rel],
        scope_items=[runtime_rel],
        fixes_implemented=["emit tracker follow-up when declared TASKS.md is clean"],
    )
    with patch.object(
        commit_mod,
        "_load_repo_meta_bridge_client",
        side_effect=ImportError("stop after tracker sync"),
    ):
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

    assert result["step"] == "build_and_run_supervisor"
    tasks_content = (repo / "TASKS.md").read_text(encoding="utf-8")
    followup_lines = [
        line for line in tasks_content.splitlines()
        if line.startswith("- Tracker sync follow-up") and wave_id in line
    ]
    assert len(followup_lines) == 1
    assert runtime_rel in followup_lines[0]
    assert pipeline_rel in followup_lines[0]


def test_tracker_followup_preserves_existing_staged_followup(tmp_path):
    import subprocess

    repo = _setup_repo(tmp_path)
    wave_id = "tracker-followup-existing-staged-wave"
    runtime_rel = "mu/host/python/rcx_pi/selfhost/step_mu.py"
    pipeline_rel = "mu/tools/executors/commit_executor.py"
    runtime_path = repo / runtime_rel
    pipeline_path = repo / pipeline_rel
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    pipeline_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text("# committed runtime\n", encoding="utf-8")
    pipeline_path.write_text("# committed pipeline\n", encoding="utf-8")
    tracker_note = _make_new_schema_handoff(wave_id=wave_id)["tracker_note_text"]
    (repo / "TASKS.md").write_text(f"## Ra\n\n{tracker_note}\n---\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "baseline tracker state"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    runtime_path.write_text("# dirty runtime follow-up\n", encoding="utf-8")
    pipeline_path.write_text("# dirty pipeline follow-up\n", encoding="utf-8")
    stale_followup = (
        f"- Tracker sync follow-up (2026-05-17T00:00:00Z, {wave_id}): "
        "same-wave follow-up commit touched tracker-relevant file(s) without "
        f"phase/task-state change: {runtime_rel}.\n"
    )
    (repo / "TASKS.md").write_text(
        f"## Ra\n\n{tracker_note}\n{stale_followup}---\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "add", "--", runtime_rel, pipeline_rel, "TASKS.md"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    handoff = _make_new_schema_handoff(
        wave_id=wave_id,
        files_to_stage=[runtime_rel, pipeline_rel],
        scope_items=[runtime_rel, pipeline_rel],
        fixes_implemented=["preserve staged tracker follow-up across retry"],
    )
    with patch.object(
        commit_mod,
        "_load_repo_meta_bridge_client",
        side_effect=ImportError("stop after tracker sync"),
    ):
        result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

    assert result["step"] == "build_and_run_supervisor"
    tasks_content = (repo / "TASKS.md").read_text(encoding="utf-8")
    followup_lines = [
        line for line in tasks_content.splitlines()
        if line.startswith("- Tracker sync follow-up") and wave_id in line
    ]
    assert len(followup_lines) == 1
    assert runtime_rel in followup_lines[0]
    assert pipeline_rel in followup_lines[0]
    staged_tasks = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--", "TASKS.md"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert staged_tasks == ["TASKS.md"]


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


def _commit_all_for_test(repo: Path, message: str) -> None:
    import subprocess

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo, check=True, capture_output=True)


def _seed_growth_cap_repo_for_test(repo: Path) -> None:
    cap_path = repo / "mu" / "tests" / "docs" / "test_growth_caps.py"
    cap_path.parent.mkdir(parents=True, exist_ok=True)
    cap_path.write_text(
        "BASELINE_TEST_FILES = 1\n"
        "CAP_TEST_FILES = 0\n"
        "BASELINE_TOOL_SCRIPTS = 0\n"
        "CAP_TOOL_SCRIPTS = 0\n",
        encoding="utf-8",
    )
    _commit_all_for_test(repo, "baseline growth cap")


def _write_governance_packet_for_test(repo: Path, wave_id: str, packet_path: str) -> str:
    pre_review_block = (
        "<!-- PRE_REVIEW_AUTH:start -->\n"
        "## Phase B Pre-Review Candidate Authorization\n\n"
        "- Authorized pre-review file(s):\n"
        "  - `file.py`\n"
        "- Boundary: commit-time generated governance is not part of this allowlist.\n"
        "<!-- PRE_REVIEW_AUTH:end -->"
    )
    packet_file = repo / packet_path
    packet_file.parent.mkdir(parents=True, exist_ok=True)
    packet_file.write_text(
        "# Commit Generated Governance Wave\n\n"
        "Status: Phase B ready\n"
        f"Wave ID: {wave_id}\n"
        "Wave class: L4_ENABLER\n"
        "Target gate: G8\n"
        "Lane: control-surface\n\n"
        f"{pre_review_block}\n\n"
        f"FOUNDER_OVERRIDE:{wave_id}\n",
        encoding="utf-8",
    )
    return pre_review_block


def _write_same_wave_growth_cap_for_test(
    repo: Path,
    wave_id: str,
    *,
    baseline_test_files: int = 1,
    cap_test_files: int = 1,
    baseline_tool_scripts: int = 0,
    cap_tool_scripts: int = 0,
) -> None:
    cap_path = repo / commit_mod.GROWTH_CAP_TEST_RELPATH
    cap_path.parent.mkdir(parents=True, exist_ok=True)
    cap_path.write_text(
        f"BASELINE_TEST_FILES = {baseline_test_files}\n"
        f"CAP_TEST_FILES = {cap_test_files}  # +1 for prior.py ({wave_id} wave, FOUNDER_OVERRIDE:{wave_id})\n"
        f"BASELINE_TOOL_SCRIPTS = {baseline_tool_scripts}\n"
        f"CAP_TOOL_SCRIPTS = {cap_tool_scripts}\n",
        encoding="utf-8",
    )


def _commit_same_wave_growth_cap_for_test(
    repo: Path,
    wave_id: str,
    *,
    baseline_test_files: int = 1,
    cap_test_files: int = 1,
    baseline_tool_scripts: int = 0,
    cap_tool_scripts: int = 0,
) -> None:
    _write_same_wave_growth_cap_for_test(
        repo,
        wave_id,
        baseline_test_files=baseline_test_files,
        cap_test_files=cap_test_files,
        baseline_tool_scripts=baseline_tool_scripts,
        cap_tool_scripts=cap_tool_scripts,
    )
    _commit_all_for_test(repo, "same-wave growth cap already recorded")


def _stage_commit_refresh_inputs_for_test(
    repo: Path,
    wave_id: str,
    *,
    file_text: str = "# changed code\n",
) -> str:
    import subprocess

    indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
    indicator_file = repo / indicator_path
    indicator_file.parent.mkdir(parents=True, exist_ok=True)
    indicator_file.write_text(json.dumps({"wave_id": wave_id}), encoding="utf-8")
    (repo / "file.py").write_text(file_text, encoding="utf-8")
    subprocess.run(["git", "add", "--", "file.py"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-f", "--", indicator_path], cwd=repo, check=True)
    return indicator_path


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


class TestResumeContinuationRecovery:
    """``--resume-continuation`` finishes a stranded PR's remaining post-commit steps.

    A stranded PR (already committed, ``COMMIT_GO`` continuation record written,
    its dispatcher process gone) is recovered by re-invoking the executor with
    ``--resume-continuation``:

    - with a valid continuation record, the existing commit driver
      (``run_commit_pipeline``) is invoked to finish the post-commit steps
      through the normal gates;
    - with no/invalid record, the flag fails closed (exit non-zero) and takes no
      completion action (the driver is never invoked).
    """

    def _run_resume_main(self, tmp_path, continuation):
        import subprocess

        repo = tmp_path / "repo"
        repo.mkdir()
        handoff_path = tmp_path / "handoff.json"
        handoff_path.write_text(
            json.dumps(_make_new_schema_handoff(wave_id="resume-continuation-wave")),
            encoding="utf-8",
        )
        pipeline_calls = []

        def fake_run(args, **kwargs):
            if list(args) == ["git", "rev-parse", "--show-toplevel"]:
                return subprocess.CompletedProcess(args, 0, f"{repo}\n", "")
            raise AssertionError(f"unexpected subprocess.run call: {args}")

        def fake_pipeline(handoff, **kwargs):
            pipeline_calls.append({"handoff": handoff, "kwargs": kwargs})
            return {
                "status": "success",
                "steps_completed": ["validate_inputs", "git_commit", "post_commit"],
                "pr_number": "4242",
            }

        with patch.object(commit_mod.subprocess, "run", side_effect=fake_run), \
             patch.object(
                 commit_mod,
                 "_resolve_control_surface_founder_override_token",
                 return_value="",
             ), \
             patch.object(
                 commit_mod,
                 "_load_post_commit_continuation",
                 return_value=continuation,
             ) as load_record, \
             patch.object(
                 commit_mod, "run_commit_pipeline", side_effect=fake_pipeline,
             ), \
             patch.object(
                 sys,
                 "argv",
                 [
                     "commit_executor.py",
                     "--handoff",
                     str(handoff_path),
                     "--resume-continuation",
                 ],
             ):
            exit_code = commit_mod.main()

        return exit_code, pipeline_calls, load_record

    def test_resume_continuation_invokes_driver_when_record_valid(self, tmp_path):
        continuation = {
            "version": commit_mod.COMMIT_CONTINUATION_VERSION,
            "status": commit_mod.CONTINUATION_ACTIVE_STATUS,
            "commit_sha": "a" * 40,
            "receipt_decision": "COMMIT_GO",
            "steps_completed": ["validate_inputs", "git_commit"],
            "target_branch": "jabramsja/resume-continuation-wave",
        }

        exit_code, pipeline_calls, load_record = self._run_resume_main(
            tmp_path,
            continuation,
        )

        # Valid record: the guard consults the continuation loader and falls
        # through to the existing driver to finish the remaining steps.
        assert load_record.called
        assert len(pipeline_calls) == 1
        assert exit_code == 0

    def test_resume_continuation_fails_closed_without_record(self, tmp_path):
        exit_code, pipeline_calls, load_record = self._run_resume_main(
            tmp_path,
            None,
        )

        # No/invalid record: fail closed (exit non-zero) and take no completion
        # action — the existing driver must never be invoked.
        assert load_record.called
        assert pipeline_calls == []
        assert exit_code == 1


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
            side_effect=lambda **kwargs: {**kwargs["result"], "status": "success"},
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

    def test_commit_generated_growth_cap_first_bump_settles_scope_before_supervisor(self, tmp_path):
        from collections import namedtuple
        import types

        repo = _setup_repo(tmp_path)
        _seed_growth_cap_repo_for_test(repo)
        wave_id = "commit-generated-growth-cap-wave"
        packet_path = "reports/control_plane/commit_generated_growth_cap_wave.md"
        pre_review_block = _write_governance_packet_for_test(repo, wave_id, packet_path)
        new_test_path = "mu/tests/generated/test_growth_cap_new_case.py"
        (repo / "file.py").write_text("# changed code\n", encoding="utf-8")
        (repo / new_test_path).parent.mkdir(parents=True, exist_ok=True)
        (repo / new_test_path).write_text("def test_generated_case():\n    assert True\n", encoding="utf-8")

        sup_receipt_path = ".scratch/step6_receipt.json"
        (repo / ".scratch").mkdir(parents=True, exist_ok=True)
        (repo / sup_receipt_path).write_text(
            json.dumps(
                {
                    "decision": "COMMIT_GO",
                    "staged_sha": "fresh_sha_from_step6",
                    "timestamp_utc": "2026-08-21T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )
        captured_package = {}
        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])

        def mock_supervisor(package_path, *a, **kw):
            captured_package.update(json.loads(Path(package_path).read_text(encoding="utf-8")))
            return SupervisorResult("COMMIT_GO", "test", sup_receipt_path)

        tracker_note = _with_founder_override(
            _make_new_schema_handoff(wave_id=wave_id)["tracker_note_text"],
            wave_id,
        )
        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", new_test_path, packet_path],
            tracked_packet=packet_path,
            scope_items=[packet_path],
            evidence_handles={"phase_b_receipt": ".agent_bus/meta/pre_commit_receipt.json"},
            tracker_note_text=tracker_note,
        )

        mock_client = types.ModuleType("meta_bridge_client")
        mock_client.run_meta_bridge_package = mock_supervisor
        mock_client.MetaBridgeClientError = Exception
        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}), patch.object(
            commit_mod,
            "_run_post_commit_pipeline",
            side_effect=lambda **kwargs: {**kwargs["result"], "status": "success"},
        ):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        growth_path = commit_mod.GROWTH_CAP_TEST_RELPATH
        assert result["status"] == "success", result
        assert result["growth_cap_autobump_outcome"]["reason"] == "bumped"
        assert result["commit_generated_governance_paths"] == [growth_path]
        assert "settle_commit_generated_governance" in result["steps_completed"]
        assert growth_path in captured_package["changed_files"]
        assert growth_path in captured_package["scope_items"]
        assert (
            captured_package["evidence_handles"][commit_mod.COMMIT_GENERATED_GOVERNANCE_EVIDENCE_KEY]
            == growth_path
        )

        durable_handoff = json.loads(
            (repo / ".agent_bus" / "executors" / "phase_b_handoff.json").read_text(
                encoding="utf-8"
            )
        )
        assert growth_path in durable_handoff["files_to_stage"]
        assert durable_handoff["scope_items"].count(growth_path) == 1
        assert (
            durable_handoff["evidence_handles"][commit_mod.COMMIT_GENERATED_GOVERNANCE_EVIDENCE_KEY]
            == growth_path
        )

        tasks_text = (repo / "TASKS.md").read_text(encoding="utf-8")
        packet_text = (repo / packet_path).read_text(encoding="utf-8")
        refreshed_pre_review = packet_text[
            packet_text.index("<!-- PRE_REVIEW_AUTH:start -->"):
            packet_text.index("<!-- PRE_REVIEW_AUTH:end -->") + len("<!-- PRE_REVIEW_AUTH:end -->")
        ]
        assert refreshed_pre_review == pre_review_block
        assert "## Commit-Time Generated Governance Authorization" in packet_text
        assert f"  - `{growth_path}`" in packet_text
        assert f"`{growth_path}`" in tasks_text
        assert "scope_refs:" in tasks_text
        assert f"`{growth_path}`" in captured_package["tracker_note_text"]

    def test_commit_generated_growth_cap_same_wave_retry_reconstructs_scope(self, tmp_path):
        from collections import namedtuple
        import types

        repo = _setup_repo(tmp_path)
        _seed_growth_cap_repo_for_test(repo)
        wave_id = "commit-generated-growth-cap-retry-wave"
        packet_path = "reports/control_plane/commit_generated_growth_cap_retry_wave.md"
        _write_governance_packet_for_test(repo, wave_id, packet_path)
        growth_path = commit_mod.GROWTH_CAP_TEST_RELPATH
        cap_file = repo / growth_path
        _commit_same_wave_growth_cap_for_test(repo, wave_id)
        new_test_path = "mu/tests/generated/test_growth_cap_retry_case.py"
        (repo / "file.py").write_text("# changed code\n", encoding="utf-8")
        (repo / new_test_path).parent.mkdir(parents=True, exist_ok=True)
        (repo / new_test_path).write_text("def test_retry_case():\n    assert True\n", encoding="utf-8")

        sup_receipt_path = ".scratch/step6_receipt.json"
        (repo / ".scratch").mkdir(parents=True, exist_ok=True)
        (repo / sup_receipt_path).write_text(
            json.dumps(
                {
                    "decision": "COMMIT_GO",
                    "staged_sha": "fresh_sha_from_step6",
                    "timestamp_utc": "2026-08-21T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )
        captured_package = {}
        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])

        def mock_supervisor(package_path, *a, **kw):
            captured_package.update(json.loads(Path(package_path).read_text(encoding="utf-8")))
            return SupervisorResult("COMMIT_GO", "test", sup_receipt_path)

        tracker_note = _with_founder_override(
            _make_new_schema_handoff(wave_id=wave_id)["tracker_note_text"],
            wave_id,
        )
        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", new_test_path, packet_path],
            tracked_packet=packet_path,
            scope_items=[packet_path],
            tracker_note_text=tracker_note,
        )

        mock_client = types.ModuleType("meta_bridge_client")
        mock_client.run_meta_bridge_package = mock_supervisor
        mock_client.MetaBridgeClientError = Exception
        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}), patch.object(
            commit_mod,
            "_run_post_commit_pipeline",
            side_effect=lambda **kwargs: {**kwargs["result"], "status": "success"},
        ):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "success", result
        assert "growth_cap_autobump_outcome" in result, result
        assert result["growth_cap_autobump_outcome"]["reason"] == "already_recorded"
        assert result["commit_generated_governance_paths"] == [growth_path]
        assert captured_package["scope_items"].count(growth_path) == 1
        assert growth_path not in captured_package["changed_files"]
        assert (
            captured_package["evidence_handles"][commit_mod.COMMIT_GENERATED_GOVERNANCE_EVIDENCE_KEY]
            == growth_path
        )
        durable_handoff = json.loads(
            (repo / ".agent_bus" / "executors" / "phase_b_handoff.json").read_text(
                encoding="utf-8"
            )
        )
        assert growth_path not in durable_handoff["files_to_stage"]
        assert durable_handoff["scope_items"].count(growth_path) == 1
        assert (
            durable_handoff["evidence_handles"][commit_mod.COMMIT_GENERATED_GOVERNANCE_EVIDENCE_KEY]
            == growth_path
        )
        packet_text = (repo / packet_path).read_text(encoding="utf-8")
        assert packet_text.count("## Commit-Time Generated Governance Authorization") == 1
        assert packet_text.count(f"`{growth_path}`") >= 1
        assert cap_file.read_text(encoding="utf-8").count(f"FOUNDER_OVERRIDE:{wave_id}") == 1

    def test_commit_generated_growth_cap_mixed_retry_preserves_scope(self, tmp_path):
        from collections import namedtuple
        import types

        repo = _setup_repo(tmp_path)
        _seed_growth_cap_repo_for_test(repo)
        wave_id = "commit-generated-growth-cap-mixed-retry-wave"
        packet_path = "reports/control_plane/commit_generated_growth_cap_mixed_retry_wave.md"
        _write_governance_packet_for_test(repo, wave_id, packet_path)
        growth_path = commit_mod.GROWTH_CAP_TEST_RELPATH
        cap_file = repo / growth_path
        _commit_same_wave_growth_cap_for_test(
            repo,
            wave_id,
            baseline_tool_scripts=1,
            cap_tool_scripts=1,
        )
        new_test_path = "mu/tests/generated/test_growth_cap_mixed_retry_case.py"
        new_tool_path = "mu/tools/generated_mixed_retry_probe.sh"
        (repo / "file.py").write_text("# changed code\n", encoding="utf-8")
        (repo / new_test_path).parent.mkdir(parents=True, exist_ok=True)
        (repo / new_test_path).write_text(
            "def test_mixed_retry_case():\n    assert True\n",
            encoding="utf-8",
        )
        (repo / new_tool_path).parent.mkdir(parents=True, exist_ok=True)
        (repo / new_tool_path).write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

        sup_receipt_path = ".scratch/step6_receipt.json"
        (repo / ".scratch").mkdir(parents=True, exist_ok=True)
        (repo / sup_receipt_path).write_text(
            json.dumps(
                {
                    "decision": "COMMIT_GO",
                    "staged_sha": "fresh_sha_from_step6",
                    "timestamp_utc": "2026-08-21T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )
        captured_package = {}
        SupervisorResult = namedtuple("SupervisorResult", ["decision", "summary", "receipt_path"])

        def mock_supervisor(package_path, *a, **kw):
            captured_package.update(json.loads(Path(package_path).read_text(encoding="utf-8")))
            return SupervisorResult("COMMIT_GO", "test", sup_receipt_path)

        tracker_note = _with_founder_override(
            _make_new_schema_handoff(wave_id=wave_id)["tracker_note_text"],
            wave_id,
        )
        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", new_test_path, new_tool_path, packet_path],
            tracked_packet=packet_path,
            scope_items=[packet_path],
            tracker_note_text=tracker_note,
        )

        mock_client = types.ModuleType("meta_bridge_client")
        mock_client.run_meta_bridge_package = mock_supervisor
        mock_client.MetaBridgeClientError = Exception
        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}), patch.object(
            commit_mod,
            "_run_post_commit_pipeline",
            side_effect=lambda **kwargs: {**kwargs["result"], "status": "success"},
        ):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        outcome = result.get("growth_cap_autobump_outcome", {})
        assert result["status"] == "success", result
        assert outcome["reason"] == "zero_shortfall", outcome
        assert outcome["cap_bumps"]["CAP_TEST_FILES"]["reason"] == "already_recorded", outcome
        assert outcome["cap_bumps"]["CAP_TOOL_SCRIPTS"]["reason"] == "zero_shortfall", outcome
        assert outcome["commit_generated_governance_paths"] == [growth_path]
        assert result["commit_generated_governance_paths"] == [growth_path]
        assert captured_package["scope_items"].count(growth_path) == 1
        assert growth_path not in captured_package["changed_files"]
        assert (
            captured_package["evidence_handles"][commit_mod.COMMIT_GENERATED_GOVERNANCE_EVIDENCE_KEY]
            == growth_path
        )
        durable_handoff = json.loads(
            (repo / ".agent_bus" / "executors" / "phase_b_handoff.json").read_text(
                encoding="utf-8"
            )
        )
        assert growth_path not in durable_handoff["files_to_stage"]
        assert durable_handoff["scope_items"].count(growth_path) == 1
        assert cap_file.read_text(encoding="utf-8").count(f"FOUNDER_OVERRIDE:{wave_id}") == 1

    def test_commit_generated_governance_refresh_rejects_unsupported_path(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "commit-generated-unsupported-wave"
        packet_path = "reports/control_plane/commit_generated_unsupported_wave.md"
        _write_governance_packet_for_test(repo, wave_id, packet_path)
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
        _refreshed, _staged, error = commit_mod.refresh_commit_path_packet_truth(
            repo_root=repo,
            handoff=handoff,
            indicator_path=indicator_path,
            commit_status="pre_commit_supervisor_pending",
            commit_generated_governance_paths=["mu/tests/docs/not_growth_caps.py"],
            commit_generated_governance_provenance="bumped",
        )

        assert error == (
            "unsupported commit-generated governance path before supervisor: "
            "mu/tests/docs/not_growth_caps.py"
        )

    def test_commit_generated_governance_refresh_rejects_provenance_free_path(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        _seed_growth_cap_repo_for_test(repo)
        wave_id = "commit-generated-refresh-provenance-free-wave"
        packet_path = "reports/control_plane/commit_generated_refresh_provenance_free_wave.md"
        _write_governance_packet_for_test(repo, wave_id, packet_path)
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        indicator_file = repo / indicator_path
        indicator_file.parent.mkdir(parents=True, exist_ok=True)
        indicator_file.write_text(json.dumps({"wave_id": wave_id}), encoding="utf-8")
        growth_path = commit_mod.GROWTH_CAP_TEST_RELPATH
        (repo / growth_path).write_text(
            "BASELINE_TEST_FILES = 1\n"
            f"CAP_TEST_FILES = 1  # +1 for prior.py ({wave_id} wave, FOUNDER_OVERRIDE:{wave_id})\n"
            "BASELINE_TOOL_SCRIPTS = 0\n"
            "CAP_TOOL_SCRIPTS = 0\n",
            encoding="utf-8",
        )
        (repo / "file.py").write_text("# changed code\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", "file.py", growth_path], cwd=repo, check=True)
        subprocess.run(["git", "add", "-f", "--", indicator_path], cwd=repo, check=True)

        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", packet_path],
            tracked_packet=packet_path,
            scope_items=[packet_path],
        )
        packet_text_before = (repo / packet_path).read_text(encoding="utf-8")
        _refreshed, staged, error = commit_mod.refresh_commit_path_packet_truth(
            repo_root=repo,
            handoff=handoff,
            indicator_path=indicator_path,
            commit_status="pre_commit_supervisor_pending",
            commit_generated_governance_paths=[growth_path],
            commit_generated_governance_provenance="",
        )

        assert error == "commit-generated governance provenance is required before supervisor"
        assert staged == []
        packet_text_after = (repo / packet_path).read_text(encoding="utf-8")
        assert packet_text_after == packet_text_before
        assert "Step-5e provenance: `unspecified`" not in packet_text_after

    def test_commit_generated_governance_refresh_accepts_clean_already_recorded_reuse(self, tmp_path):
        repo = _setup_repo(tmp_path)
        _seed_growth_cap_repo_for_test(repo)
        wave_id = "commit-generated-clean-reuse-wave"
        packet_path = "reports/control_plane/commit_generated_clean_reuse_wave.md"
        _write_governance_packet_for_test(repo, wave_id, packet_path)
        growth_path = commit_mod.GROWTH_CAP_TEST_RELPATH
        _commit_same_wave_growth_cap_for_test(repo, wave_id)
        indicator_path = _stage_commit_refresh_inputs_for_test(repo, wave_id)

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
            commit_generated_governance_paths=[growth_path],
            commit_generated_governance_provenance="already_recorded",
        )

        assert error is None
        assert growth_path not in staged
        assert growth_path not in refreshed["files_to_stage"]
        assert refreshed["scope_items"].count(growth_path) == 1
        assert (
            refreshed["evidence_handles"][commit_mod.COMMIT_GENERATED_GOVERNANCE_EVIDENCE_KEY]
            == growth_path
        )
        packet_text = (repo / packet_path).read_text(encoding="utf-8")
        assert "Step-5e provenance: `already_recorded`" in packet_text
        assert packet_text.count("## Commit-Time Generated Governance Authorization") == 1

    def test_commit_generated_governance_refresh_rejects_already_recorded_worktree_only_provenance(
        self,
        tmp_path,
    ):
        repo = _setup_repo(tmp_path)
        _seed_growth_cap_repo_for_test(repo)
        wave_id = "commit-generated-worktree-only-reuse-wave"
        packet_path = "reports/control_plane/commit_generated_worktree_only_reuse_wave.md"
        _write_governance_packet_for_test(repo, wave_id, packet_path)
        growth_path = commit_mod.GROWTH_CAP_TEST_RELPATH
        _write_same_wave_growth_cap_for_test(repo, wave_id)
        indicator_path = _stage_commit_refresh_inputs_for_test(repo, wave_id)

        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", packet_path],
            tracked_packet=packet_path,
            scope_items=[packet_path],
        )
        _refreshed, staged, error = commit_mod.refresh_commit_path_packet_truth(
            repo_root=repo,
            handoff=handoff,
            indicator_path=indicator_path,
            commit_status="pre_commit_supervisor_pending",
            commit_generated_governance_paths=[growth_path],
            commit_generated_governance_provenance="already_recorded",
        )

        assert staged == []
        assert error == (
            "commit-generated governance already_recorded path lacks same-wave "
            f"HEAD/index provenance before supervisor: {growth_path}"
        )

    def test_commit_generated_governance_refresh_rejects_already_recorded_index_head_mismatch(
        self,
        tmp_path,
    ):
        import subprocess

        repo = _setup_repo(tmp_path)
        _seed_growth_cap_repo_for_test(repo)
        wave_id = "commit-generated-index-head-mismatch-wave"
        packet_path = "reports/control_plane/commit_generated_index_head_mismatch_wave.md"
        _write_governance_packet_for_test(repo, wave_id, packet_path)
        growth_path = commit_mod.GROWTH_CAP_TEST_RELPATH
        _write_same_wave_growth_cap_for_test(repo, wave_id)
        subprocess.run(["git", "add", "--", growth_path], cwd=repo, check=True)
        indicator_path = _stage_commit_refresh_inputs_for_test(repo, wave_id)

        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", packet_path],
            tracked_packet=packet_path,
            scope_items=[packet_path],
        )
        _refreshed, staged, error = commit_mod.refresh_commit_path_packet_truth(
            repo_root=repo,
            handoff=handoff,
            indicator_path=indicator_path,
            commit_status="pre_commit_supervisor_pending",
            commit_generated_governance_paths=[growth_path],
            commit_generated_governance_provenance="already_recorded",
        )

        assert staged == []
        assert error == (
            "commit-generated governance already_recorded path has index/HEAD "
            f"mismatch before supervisor: {growth_path}"
        )

    def test_commit_generated_governance_refresh_rejects_already_recorded_unstaged_drift(
        self,
        tmp_path,
    ):
        repo = _setup_repo(tmp_path)
        _seed_growth_cap_repo_for_test(repo)
        wave_id = "commit-generated-unstaged-drift-wave"
        packet_path = "reports/control_plane/commit_generated_unstaged_drift_wave.md"
        _write_governance_packet_for_test(repo, wave_id, packet_path)
        growth_path = commit_mod.GROWTH_CAP_TEST_RELPATH
        cap_file = repo / growth_path
        _commit_same_wave_growth_cap_for_test(repo, wave_id)
        cap_file.write_text(cap_file.read_text(encoding="utf-8") + "# unstaged drift\n", encoding="utf-8")
        indicator_path = _stage_commit_refresh_inputs_for_test(repo, wave_id)

        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", packet_path],
            tracked_packet=packet_path,
            scope_items=[packet_path],
        )
        _refreshed, staged, error = commit_mod.refresh_commit_path_packet_truth(
            repo_root=repo,
            handoff=handoff,
            indicator_path=indicator_path,
            commit_status="pre_commit_supervisor_pending",
            commit_generated_governance_paths=[growth_path],
            commit_generated_governance_provenance="already_recorded",
        )

        assert staged == []
        assert error == (
            "commit-generated governance already_recorded path has unstaged "
            f"delta before supervisor: {growth_path}"
        )

    def test_commit_generated_governance_refresh_rejects_already_recorded_wrong_wave_provenance(
        self,
        tmp_path,
    ):
        repo = _setup_repo(tmp_path)
        _seed_growth_cap_repo_for_test(repo)
        wave_id = "commit-generated-wrong-wave-reuse-wave"
        packet_path = "reports/control_plane/commit_generated_wrong_wave_reuse_wave.md"
        _write_governance_packet_for_test(repo, wave_id, packet_path)
        growth_path = commit_mod.GROWTH_CAP_TEST_RELPATH
        _commit_same_wave_growth_cap_for_test(repo, "different-commit-generated-wave")
        indicator_path = _stage_commit_refresh_inputs_for_test(repo, wave_id)

        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=["file.py", packet_path],
            tracked_packet=packet_path,
            scope_items=[packet_path],
        )
        _refreshed, staged, error = commit_mod.refresh_commit_path_packet_truth(
            repo_root=repo,
            handoff=handoff,
            indicator_path=indicator_path,
            commit_status="pre_commit_supervisor_pending",
            commit_generated_governance_paths=[growth_path],
            commit_generated_governance_provenance="already_recorded",
        )

        assert staged == []
        assert error == (
            "commit-generated governance already_recorded path lacks same-wave "
            f"HEAD/index provenance before supervisor: {growth_path}"
        )

    def test_commit_generated_governance_fails_before_supervisor_when_not_staged(self, tmp_path):
        import types

        repo = _setup_repo(tmp_path)
        wave_id = "commit-generated-not-staged-wave"
        packet_path = "reports/control_plane/commit_generated_not_staged_wave.md"
        _write_governance_packet_for_test(repo, wave_id, packet_path)
        (repo / "file.py").write_text("# changed code\n", encoding="utf-8")
        supervisor_called = False

        def mock_supervisor(*a, **kw):
            nonlocal supervisor_called
            supervisor_called = True
            raise AssertionError("supervisor must not run")

        def fake_autobump(*a, **kw):
            return {
                "bumped": True,
                "reason": "bumped",
                "commit_generated_governance_paths": [commit_mod.GROWTH_CAP_TEST_RELPATH],
            }

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
            "_maybe_autobump_growth_cap_for_founder_override",
            side_effect=fake_autobump,
        ):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "error"
        assert result["step"] == "settle_commit_generated_governance"
        assert "not staged before supervisor" in result["errors"][0]
        assert "build_and_run_supervisor" not in result.get("steps_completed", [])
        assert supervisor_called is False

    def test_commit_generated_governance_fails_before_supervisor_without_provenance(self, tmp_path):
        import subprocess
        import types

        repo = _setup_repo(tmp_path)
        wave_id = "commit-generated-provenance-free-wave"
        packet_path = "reports/control_plane/commit_generated_provenance_free_wave.md"
        _write_governance_packet_for_test(repo, wave_id, packet_path)
        growth_path = commit_mod.GROWTH_CAP_TEST_RELPATH
        growth_file = repo / growth_path
        growth_file.parent.mkdir(parents=True, exist_ok=True)
        growth_file.write_text("BASELINE_TEST_FILES = 1\nCAP_TEST_FILES = 0\n", encoding="utf-8")
        (repo / "file.py").write_text("# changed code\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", growth_path], cwd=repo, check=True)
        supervisor_called = False

        def mock_supervisor(*a, **kw):
            nonlocal supervisor_called
            supervisor_called = True
            raise AssertionError("supervisor must not run")

        def fake_autobump(*a, **kw):
            return {
                "bumped": False,
                "reason": "zero_shortfall",
                "commit_generated_governance_paths": [growth_path],
            }

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
            "_maybe_autobump_growth_cap_for_founder_override",
            side_effect=fake_autobump,
        ):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "error"
        assert result["step"] == "settle_commit_generated_governance"
        assert "without bumped or same-wave already_recorded provenance" in result["errors"][0]
        assert "build_and_run_supervisor" not in result.get("steps_completed", [])
        assert supervisor_called is False

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

    def test_pre_push_failure_after_commit_demotes_completed_packet_and_task_for_dispatch_retry(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "runtime-pre-push-failure-reentry-wave"
        packet_path = "reports/control_plane/runtime_pre_push_failure_reentry_wave.md"
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
            "  6. **[FOUNDER-ORDERED-REDTEAM-RUNTIME-PRE-PUSH-FAILURE-REENTRY] "
            "IMPLEMENTED / LOCAL EVIDENCE (2026-05-21).** "
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
        result = {
            "status": "error",
            "step": "run_pre_push_script",
            "errors": ["pre-push-fast failed"],
            "steps_completed": [
                "validate_inputs",
                "ensure_feature_branch",
                "build_and_run_supervisor",
                "validate_receipt",
                "run_pre_commit_script",
                "git_commit",
            ],
        }

        getattr(commit_mod, "_maybe_demote_completed_handoff_state_for_commit_retry")(
            repo_root=repo,
            handoff=handoff,
            result=result,
        )

        assert result["status"] == "error"
        assert set(result["commit_retry_state_demotion"]["changed"]) == {
            packet_path,
            "TASKS.md",
        }
        assert (
            f"Status: {commit_mod.COMMIT_RETRY_PENDING_STATUS}"
            in packet_file.read_text(encoding="utf-8")
        )
        tasks_text = (repo / "TASKS.md").read_text(encoding="utf-8")
        assert (
            "IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT / LOCAL EVIDENCE "
            "(2026-05-21)"
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

    def test_tracker_note_refresh_preserves_structural_note_for_control_repair(self, tmp_path):
        import subprocess

        repo = tmp_path / "repo"
        repo.mkdir()
        wave_id = "packet-structural-preserve-wave"
        structural_note = (
            f"- Tracker sync note (2026-05-21, {wave_id}): **Structural runtime proof.** "
            "Class: L4_STRUCTURAL. target_gate_id: G8. workload_target: host_debt_reduction.\n"
        )
        enabler_note = (
            f"- Tracker sync note (2026-05-21, {wave_id}): **Control repair.** "
            "Class: L4_ENABLER. target_gate_id: G8.\n"
        )
        (repo / "TASKS.md").write_text(f"## Ra\n\n{structural_note}\n---\n", encoding="utf-8")
        add_calls = []

        def fake_run(args, **kwargs):
            if args == ["git", "add", "--", "TASKS.md"]:
                add_calls.append(args)
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch.object(commit_mod, "_run", side_effect=fake_run):
            error = commit_mod.refresh_tasks_tracker_note_after_packet_truth(
                repo,
                wave_id=wave_id,
                tracker_note_text=enabler_note,
            )

        tasks_text = (repo / "TASKS.md").read_text(encoding="utf-8")
        assert error is None
        assert structural_note in tasks_text
        assert enabler_note not in tasks_text
        assert add_calls == []

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

    def test_validate_handoff_accepts_same_wave_committed_deletion_with_closed_archive(self, tmp_path):
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
        subprocess.run(["git", "commit", "-m", "close deferred packet"], cwd=repo, check=True, capture_output=True)
        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            files_to_stage=[deferred_path, archive_path],
            deferred_items=[],
        )

        ok_without_repo, errors_without_repo = commit_mod.validate_handoff(handoff)
        ok, errors = commit_mod.validate_handoff(handoff, repo_root=repo)

        assert ok_without_repo is False
        assert any("both active deferred and archived closed" in error for error in errors_without_repo)
        assert ok is True
        assert errors == []

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

    def test_structural_truth_refresh_does_not_replace_evidence_with_tooling_only_scope(self):
        wave_id = "structural-evidence-preserve-wave"
        tracker_note = (
            f"- Tracker sync note (2026-05-19, {wave_id}): **TEST.**. "
            "Class: L4_STRUCTURAL. target_gate_id: G8. workload_target: execution_layer_truth. "
            "host_semantics_delta_before: runtime proof before. "
            "host_semantics_delta_after: runtime proof after. "
            "structural_artifact_ref: mu/host/js/core/bootstrap_core.js; "
            "mu/tests/l4_gates/test_stage0_production_pilot_gate.py; "
            "mu/tests/structural/test_execution_layer_truth_contract.py. "
            "evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short "
            "mu/tests/l4_gates/test_stage0_production_pilot_gate.py "
            "mu/tests/structural/test_execution_layer_truth_contract.py`. "
            "evidence_delta: (1) Final pytest gate covered 2 test file(s). "
            "progress_proof_before: before. progress_proof_after: after. "
            "post_gate_contract_sweep: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short "
            "mu/tests/structural/test_execution_layer_truth_contract.py`. "
            "primary_blocker_class: INTEGRATION. primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
            f"indicator_artifact_ref: reports/l4_wave_indicators/{wave_id}.json. "
            f"indicator_collection_command: python3 tools/metrics/collect_l4_wave_indicators.py --wave-id {wave_id} "
            f"--output reports/l4_wave_indicators/{wave_id}.json. "
            "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            "boot0_track_id: V1. boot0_progress_state: HOLD."
        )

        refreshed = commit_mod._refresh_tracker_note_test_evidence(  # ANTICHEAT_OK: locks structural evidence preservation
            tracker_note,
            ["mu/tests/structural/test_subtree_root_guard.py"],
        )

        assert refreshed == tracker_note
        assert "mu/tests/l4_gates/test_stage0_production_pilot_gate.py" in refreshed
        assert "mu/tests/structural/test_execution_layer_truth_contract.py" in refreshed
        assert "test_subtree_root_guard.py" not in refreshed

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

    def test_prepare_handoff_update_tracker_only_code_scope_uses_phase_b_lane(self, tmp_path):
        record = {
            "wave_name": "control-surface-repair-wave",
            "summary": "repair control surface code",
            "decision": "UPDATE_TRACKER_ONLY",
            "files_to_stage": [
                "TASKS.md",
                "mu/tools/executors/phase_b_implementer.py",
                "mu/tests/tools/test_phase_b_executor.py",
            ],
        }

        handoff, errors = commit_mod.prepare_handoff_from_routing_record(record, tmp_path)

        assert errors == []
        assert handoff is not None
        assert handoff["caller"] == "phase_b"
        valid, validation_errors = commit_mod.validate_handoff(handoff)
        assert valid, validation_errors

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

    def test_prepare_handoff_from_routing_record_standalone_derives_structural_class_from_packet(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "n3-runtime-retry"
        packet_path = "reports/control_plane/n3-runtime-retry.md"
        packet_file = repo / packet_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Packet\n"
            f"Wave ID: {wave_id}\n"
            "Class: L4_STRUCTURAL\n"
            "Target gate: G8\n",
            encoding="utf-8",
        )
        runtime_path = repo / "mu" / "host" / "js" / "core" / "seed_loader.js"
        runtime_path.parent.mkdir(parents=True, exist_ok=True)
        runtime_path.write_text("// staged runtime split\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "--", packet_path, "mu/host/js/core/seed_loader.js"],
            cwd=repo,
            capture_output=True,
            check=True,
        )

        record = {
            "wave_name": wave_id,
            "summary": "structural staged retry",
            "decision": "ROUTE_PHASE_A",
            "task_id": "[NEXT-CODEX-POST-REDTEAM]",
            "next_candidates": [
                {
                    "candidate": wave_id,
                    "tracked_packet": packet_path,
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
        assert handoff["wave_class"] == "L4_STRUCTURAL"
        assert "Class: L4_STRUCTURAL" in handoff["tracker_note_text"]
        assert "workload_target: host_debt_reduction" in handoff["tracker_note_text"]
        assert "host_semantics_delta_before:" in handoff["tracker_note_text"]
        assert "host_semantics_delta_after:" in handoff["tracker_note_text"]
        assert "structural_artifact_ref:" in handoff["tracker_note_text"]
        assert "post_gate_contract_sweep:" in handoff["tracker_note_text"]
        assert "mu/tests/l4_gates/" in handoff["tracker_note_text"]
        assert "no_op_proof:" not in handoff["tracker_note_text"]

    def test_prepare_handoff_from_routing_record_standalone_discovers_staged_same_wave_packet(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "n3-runtime-retry"
        packet_path = "reports/control_plane/n3-runtime-retry_2026-05-20.md"
        packet_file = repo / packet_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Packet\n"
            f"Wave ID: {wave_id}\n"
            "Class: L4_STRUCTURAL\n"
            "Target gate: G8\n",
            encoding="utf-8",
        )
        runtime_path = repo / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
        runtime_path.parent.mkdir(parents=True, exist_ok=True)
        runtime_path.write_text("# staged runtime retry\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "--", packet_path, "mu/host/python/rcx_pi/selfhost/step_mu.py"],
            cwd=repo,
            capture_output=True,
            check=True,
        )

        record = {
            "wave_name": wave_id,
            "summary": "structural staged retry",
            "decision": "ROUTE_PHASE_A",
            "task_id": "[NEXT-CODEX-POST-REDTEAM]",
            "next_candidates": [{"candidate": wave_id}],
        }

        handoff, errors = commit_mod.prepare_handoff_from_routing_record(
            record,
            repo,
            standalone=True,
        )

        assert errors == []
        assert handoff is not None
        assert handoff["wave_class"] == "L4_STRUCTURAL"
        assert handoff["tracked_packet"] == packet_path
        assert "Class: L4_STRUCTURAL" in handoff["tracker_note_text"]
        assert f"Packet: `{packet_path}`" in handoff["tracker_note_text"]
        assert "no_op_proof:" not in handoff["tracker_note_text"]

    def test_prepare_handoff_from_routing_record_standalone_preserves_existing_structural_tracker_note(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "n3-runtime-retry"
        packet_path = "reports/control_plane/n3-runtime-retry.md"
        packet_file = repo / packet_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Packet\n"
            f"Wave ID: {wave_id}\n"
            "Class: L4_STRUCTURAL\n"
            "Target gate: G8\n",
            encoding="utf-8",
        )
        existing_note = (
            f"- Tracker sync note (2026-05-16, {wave_id}): "
            "**custom structural closeout.** Class: L4_STRUCTURAL. target_gate_id: G8. "
            f"Packet: `{packet_path}`. evidence_command: `custom`. "
            "workload_target: host_debt_reduction. "
            "host_semantics_delta_before: standalone handoff was not bound to structural class. "
            "host_semantics_delta_after: standalone handoff preserves structural class. "
            "structural_artifact_ref: mu/host/python/rcx_pi/selfhost/seed_integrity.py. "
            "evidence_delta: structural runtime retry evidence. "
            "progress_proof_before: standalone recovery defaulted class incorrectly. "
            "progress_proof_after: standalone recovery preserves structural class. "
            "post_gate_contract_sweep: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/parity/`. "
            "primary_blocker_class: INTEGRATION. "
            "primary_invariant_id: INV_CROSS_SUBSTRATE_PARITY. "
            f"indicator_artifact_ref: reports/l4_wave_indicators/{wave_id}.json. "
            f"indicator_collection_command: python3 tools/metrics/collect_l4_wave_indicators.py --wave-id {wave_id} --output reports/l4_wave_indicators/{wave_id}.json. "
            "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            "boot0_track_id: V1. boot0_progress_state: HOLD."
        )
        (repo / "TASKS.md").write_text(
            "# RCX Task List (Canonical)\n\n"
            "## Ra (Resolved / Merged)\n"
            "Items here are implemented.\n"
            f"{existing_note}\n",
            encoding="utf-8",
        )
        runtime_path = repo / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "seed_integrity.py"
        runtime_path.parent.mkdir(parents=True, exist_ok=True)
        runtime_path.write_text("# staged runtime split\n", encoding="utf-8")
        subprocess.run(
            [
                "git",
                "add",
                "--",
                "TASKS.md",
                packet_path,
                "mu/host/python/rcx_pi/selfhost/seed_integrity.py",
            ],
            cwd=repo,
            capture_output=True,
            check=True,
        )

        record = {
            "wave_name": wave_id,
            "summary": "structural staged retry",
            "decision": "ROUTE_PHASE_A",
            "task_id": "[NEXT-CODEX-POST-REDTEAM]",
            "next_candidates": [
                {
                    "candidate": wave_id,
                    "tracked_packet": packet_path,
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
        assert handoff["wave_class"] == "L4_STRUCTURAL"
        assert handoff["tracker_note_text"] == existing_note

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

    def test_phase_b_handoff_allows_authorized_existing_pr_target_branch(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "existing-pr-control-surface-repair"
        packet_rel = f"reports/control_plane/{wave_id}.md"
        packet = repo / packet_rel
        packet.parent.mkdir(parents=True, exist_ok=True)
        packet.write_text(
            "# Existing PR control-surface repair\n\n"
            f"Wave ID: {wave_id}\n"
            "Class: L4_ENABLER\n"
            "Lane: control-surface (agent automation / observability)\n"
            "Purpose: bounded repair on the existing PR branch.\n"
            "Founder authorization: standing pipeline-bug-fix authorization.\n"
            f"FOUNDER_OVERRIDE:{wave_id}\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "--", packet_rel], cwd=repo, check=True)
        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            target_branch="jabramsja/existing-pr-branch",
            tracked_packet=packet_rel,
            tracker_note_text=_with_founder_override(
                _make_new_schema_handoff(wave_id=wave_id)["tracker_note_text"],
                wave_id,
            ),
        )

        valid, validation_errors = commit_mod.validate_handoff(handoff, repo_root=repo)

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

    def test_validate_handoff_accepts_authorized_standalone_same_pr_repair_target_branch(
        self, tmp_path
    ):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "seed-parity-argv-ci-repair-2026-05-17"
        packet_path = f"reports/control_plane/{wave_id}.md"
        packet = repo / packet_path
        packet.parent.mkdir(parents=True, exist_ok=True)
        packet.write_text(
            "# Seed Parity Argv CI Repair\n"
            f"Wave ID: {wave_id}\n"
            "Class: L4_ENABLER\n"
            "Lane: control-surface\n"
            "Authorization: authorized control-surface L4_ENABLER; "
            "standing pipeline-bug-fix authorization.\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "--", packet_path],
            cwd=repo,
            capture_output=True,
            check=True,
        )
        note = _with_founder_override(
            _make_new_schema_handoff(wave_id=wave_id)["tracker_note_text"],
            wave_id,
        )
        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            caller="standalone",
            pre_commit_receipt_path="",
            tracked_packet=packet_path,
            files_to_stage=["file.py", packet_path],
            target_branch="jabramsja/original-structural-wave-2026-05-17",
            tracker_note_text=note,
        )

        valid, validation_errors = commit_mod.validate_handoff(handoff, repo_root=repo)

        assert valid, validation_errors

    def test_validate_handoff_rejects_unauthorized_standalone_same_pr_repair_target_branch(
        self, tmp_path
    ):
        import subprocess

        repo = _setup_repo(tmp_path)
        wave_id = "seed-parity-argv-ci-repair-2026-05-17"
        packet_path = f"reports/control_plane/{wave_id}.md"
        packet = repo / packet_path
        packet.parent.mkdir(parents=True, exist_ok=True)
        packet.write_text(
            "# Seed Parity Argv CI Repair\n"
            f"Wave ID: {wave_id}\n"
            "Class: L4_ENABLER\n"
            "Lane: control-surface\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "--", packet_path],
            cwd=repo,
            capture_output=True,
            check=True,
        )
        note = _with_founder_override(
            _make_new_schema_handoff(wave_id=wave_id)["tracker_note_text"],
            wave_id,
        )
        handoff = _make_new_schema_handoff(
            wave_id=wave_id,
            caller="standalone",
            pre_commit_receipt_path="",
            tracked_packet=packet_path,
            files_to_stage=["file.py", packet_path],
            target_branch="jabramsja/original-structural-wave-2026-05-17",
            tracker_note_text=note,
        )

        valid, validation_errors = commit_mod.validate_handoff(handoff, repo_root=repo)

        assert not valid
        assert any("authorized standalone control-surface" in err for err in validation_errors)

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

    def test_stage_handoff_paths_skips_older_branch_history_deletion_after_push(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        target_rel = "reports/deferred/non_blocking/wave_bridge_nonblockers.md"
        target = repo / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# Deferred\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", target_rel], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "add deferred packet"], cwd=repo, check=True, capture_output=True)
        base_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(["git", "update-ref", "refs/remotes/origin/dev", base_sha], cwd=repo, check=True)
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "rm", "--", target_rel], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "delete deferred packet"], cwd=repo, check=True, capture_output=True)
        (repo / "file.py").write_text("# follow-up\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", "file.py"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "follow-up"], cwd=repo, check=True, capture_output=True)
        feature_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(["git", "update-ref", "refs/remotes/origin/feature", feature_sha], cwd=repo, check=True)
        subprocess.run(["git", "config", "branch.feature.remote", "origin"], cwd=repo, check=True)
        subprocess.run(
            ["git", "config", "branch.feature.merge", "refs/heads/feature"],
            cwd=repo,
            check=True,
        )

        commit_mod._stage_handoff_paths(  # ANTICHEAT_OK: direct stage helper regression for pushed stale handoff paths
            repo,
            files_to_stage=[target_rel],
            force_files=[],
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-status", "--", target_rel],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )

        assert staged.stdout.strip() == ""

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

    def test_collect_commit_test_files_includes_bootstrap_core_carveout_gate(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "mu" / "host" / "js" / "core").mkdir(parents=True)
        (repo / "tests" / "l4_gates").mkdir(parents=True)
        (repo / "mu" / "host" / "js" / "core" / "bootstrap_core.js").write_text("module.exports = {}\n")
        (repo / "tests" / "l4_gates" / "test_bootstrap_core_carveout_gate.py").write_text("def test_gate(): pass\n")

        result = commit_mod._collect_commit_test_files(  # ANTICHEAT_OK: locks targeted runtime gate mapping
            repo,
            ["mu/host/js/core/bootstrap_core.js"],
        )

        assert result == ["tests/l4_gates/test_bootstrap_core_carveout_gate.py"]

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

    def test_private_attr_gate_scans_only_selected_staged_tests(self, tmp_path):
        repo = _setup_repo(tmp_path)
        linters = repo / "mu" / "tools" / "checks" / "linters"
        linters.mkdir(parents=True, exist_ok=True)
        for checker_name in [
            "check_private_attr_access.py",
            "check_underscore_imports.py",
        ]:
            (linters / checker_name).write_text(
                (REPO_ROOT / "mu" / "tools" / "checks" / "linters" / checker_name).read_text(
                    encoding="utf-8",
                ),
                encoding="utf-8",
            )
        tests_dir = repo / "mu" / "tests" / "tools"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_selected_clean.py").write_text(
            "from rcx_pi.selfhost.step_mu import run_mu\n"
            "def test_selected_clean():\n"
            "    assert True\n",
            encoding="utf-8",
        )
        (tests_dir / "test_unselected_dirty.py").write_text(
            "from rcx_pi.selfhost.step_mu import _unselected_private\n"
            "def test_unselected_dirty(foo):\n"
            "    foo._unselected_violation()\n",
            encoding="utf-8",
        )

        result = commit_mod.run_private_attr_test_gate(
            repo,
            ["mu/tests/tools/test_selected_clean.py"],
        )

        assert result["passed"] is True, result
        assert result["skipped"] is False
        assert result["test_files"] == ["mu/tests/tools/test_selected_clean.py"]

    def test_collect_commit_test_files_uses_max_steps_guard_selector_for_narrow_diff(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        test_path = "mu/tests/parity/test_js_parity_automated.py"
        target = repo / test_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "_MAX_STEPS_GUARDED_ACTIONS = (\n"
            "    ('run_engine_with_routing', {'maxEngineIterations': 5}),\n"
            ")\n"
            "_GUARDED_ACTION_BASE_ARGS = {\n"
            "    'run_engine_with_routing': 'deeper engine convergence',\n"
            "}\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)
        target.write_text(
            "_MAX_STEPS_GUARDED_ACTIONS = (\n"
            "    ('run_engine_with_routing', {'maxEngineIterations': 1}),\n"
            ")\n"
            "_GUARDED_ACTION_BASE_ARGS = {\n"
            "    'run_engine_with_routing': 'deeper engine convergence',\n"
            "}\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "--", test_path], cwd=repo, check=True, capture_output=True)

        result = commit_mod._collect_commit_test_files(  # ANTICHEAT_OK: locks commit Step 8b selector narrowing
            repo,
            [test_path],
        )

        assert result == [
            "mu/tests/parity/test_js_parity_automated.py::TestAPIMaxStepsGuard",
        ]

    def test_collect_commit_test_files_falls_back_to_full_file_for_mixed_parity_diff(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        test_path = "mu/tests/parity/test_js_parity_automated.py"
        target = repo / test_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "_MAX_STEPS_GUARDED_ACTIONS = (\n"
            "    ('run_engine_with_routing', {'maxEngineIterations': 5}),\n"
            ")\n"
            "UNRELATED_ASSERTION = 1\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)
        target.write_text(
            "_MAX_STEPS_GUARDED_ACTIONS = (\n"
            "    ('run_engine_with_routing', {'maxEngineIterations': 1}),\n"
            ")\n"
            "UNRELATED_ASSERTION = 2\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "--", test_path], cwd=repo, check=True, capture_output=True)

        result = commit_mod._collect_commit_test_files(  # ANTICHEAT_OK: locks mixed-diff fallback behavior
            repo,
            [test_path],
        )

        assert result == ["mu/tests/parity/test_js_parity_automated.py"]

    def test_collect_commit_test_files_targets_commit_executor_gate_class(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "mu" / "tests" / "tools").mkdir(parents=True)
        (repo / "mu" / "tests" / "tools" / "test_commit_executor_receipt.py").write_text(
            "class TestCommitExecutorPytestGate: pass\n",
            encoding="utf-8",
        )

        result = commit_mod._collect_commit_test_files(  # ANTICHEAT_OK: locks commit-executor self-test targeting
            repo,
            ["mu/tools/executors/commit_executor.py"],
        )

        assert result == [
            "mu/tests/tools/test_commit_executor_receipt.py::TestCommitExecutorPytestGate",
        ]

    def test_collect_commit_test_files_uses_full_file_for_direct_mapped_test_file(self, tmp_path):
        repo = tmp_path / "repo"
        test_path = "mu/tests/tools/test_phase_b_executor.py"
        target = repo / test_path
        target.parent.mkdir(parents=True)
        target.write_text(
            "class TestSdkReviewDepthContract: pass\n"
            "def test_unrelated_new_failure(): assert False\n",
            encoding="utf-8",
        )

        result = commit_mod._collect_commit_test_files(  # ANTICHEAT_OK: direct test-file edits must not be hidden by selector maps
            repo,
            [test_path],
        )

        assert result == [test_path]

    def test_collect_commit_test_files_targets_phase_b_executor_selectors(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "mu" / "tests" / "tools").mkdir(parents=True)
        (repo / "mu" / "tests" / "tools" / "test_phase_b_executor.py").write_text(
            "class TestSdkReviewDepthContract: pass\n",
            encoding="utf-8",
        )

        result = commit_mod._collect_commit_test_files(  # ANTICHEAT_OK: locks Phase B executor recovery selectors
            repo,
            ["mu/tools/executors/phase_b_executor.py"],
        )

        assert result == [
            "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_phase_b_pytest_gate_timeout_allows_pre_push_budget",
            "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_phase_b_pytest_gate_timeout_keeps_floor_for_invalid_values",
            "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_gate_diff_text_includes_staged_and_unstaged_diff",
            "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_executor_test_context_only_marker_falls_back_to_file",
            "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_max_steps_guard_matrix_diff",
            "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_max_steps_mixed_diff_falls_back_to_file_gate",
            "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_select_pytest_gate_files_skips_missing_targeted_executor_tests",
            "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_select_pytest_gate_files_uses_targeted_executor_timeout_selectors",
        ]

    def test_pre_commit_doc_check_timeout_covers_docs_changed_hook_runtime(self, tmp_path):
        from collections import namedtuple
        import subprocess
        import types

        repo = _setup_repo(tmp_path)
        hook = repo / "mu" / "tools" / "hooks" / "pre-commit-doc-check"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")

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

        real_run = commit_mod._run  # ANTICHEAT_OK: test captures Step 8 hook subprocess budget
        captured: dict[str, int | float | None] = {}

        def intercept_run(args, cwd, check=True, timeout=120, env=None):
            if list(args[:2]) == ["bash", str(hook)]:
                captured["timeout"] = timeout
                raise subprocess.CalledProcessError(
                    1,
                    args,
                    output="",
                    stderr="forced hook stop",
                )
            if list(args[:2]) == ["git", "commit"]:
                raise AssertionError("git commit should not run after hook failure")
            return real_run(args, cwd=cwd, check=check, timeout=timeout, env=env)

        handoff = _make_new_schema_handoff()
        with patch.dict(sys.modules, {"meta_bridge_client": mock_client}), \
             patch.object(commit_mod, "_run", side_effect=intercept_run):
            result = commit_mod.run_commit_pipeline(handoff, repo_root=repo)

        assert result["status"] == "error"
        assert result["step"] == "run_pre_commit_script"
        assert captured["timeout"] == commit_mod.PRE_COMMIT_DOC_CHECK_TIMEOUT_SECONDS
        assert captured["timeout"] > 30

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
        underscore_checker = repo / "mu" / "tools" / "checks" / "linters" / "check_underscore_imports.py"
        underscore_checker.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

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

    def test_run_commit_pipeline_blocks_underscore_import_gate_before_git_commit(self, tmp_path):
        from collections import namedtuple
        import subprocess
        import types

        repo = _setup_repo(tmp_path)
        (repo / "mu" / "tests").mkdir(parents=True, exist_ok=True)
        (repo / "mu" / "tests" / "test_file.py").write_text(
            "def test_smoke():\n    assert True\n",
            encoding="utf-8",
        )
        linters = repo / "mu" / "tools" / "checks" / "linters"
        linters.mkdir(parents=True, exist_ok=True)
        (linters / "check_private_attr_access.py").write_text(
            "import sys\nsys.exit(0)\n",
            encoding="utf-8",
        )
        (linters / "check_underscore_imports.py").write_text(
            "import sys\n"
            "print('ERROR: Found underscored imports from rcx_pi:')\n"
            "print('  mu/tests/test_file.py:3: from rcx_pi.selfhost.step_mu import _private_helper')\n"
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
                raise AssertionError("git commit should not run after underscored-import gate failure")
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
        assert "ERROR: Found underscored imports from rcx_pi" in error_text
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

    def test_run_pytest_on_files_uses_fast_shard_marker_filter(self, tmp_path):
        from types import SimpleNamespace

        repo = tmp_path / "repo"
        repo.mkdir()

        with patch.object(
            commit_mod.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
        ) as mock_run:
            result = commit_mod._run_pytest_on_files(  # ANTICHEAT_OK: locks commit Step 8b fast-shard marker filter
                repo,
                [
                    "mu/tests/l4_gates/test_boot1_default_pipeline_gate.py",
                    "mu/tests/parity/test_boot1_shadow_parity.py",
                ],
            )

        assert result["passed"] is True
        args = mock_run.call_args.args[0]
        assert ["-m", "not slow and not fuzzer"] in [
            args[index:index + 2]
            for index in range(len(args) - 1)
        ]
        env = mock_run.call_args.kwargs["env"]
        assert env["PYTHONHASHSEED"] == "0"
        assert env["RCX_CI"] == "1"
        assert env["HYPOTHESIS_PROFILE"] == "ci_fast"

    def test_run_pytest_on_files_accepts_all_deselected_fast_marker_lane(self, tmp_path):
        from types import SimpleNamespace

        repo = tmp_path / "repo"
        repo.mkdir()

        stdout = (
            "collected 17 items / 17 deselected / 0 selected\n\n"
            "============================ 17 deselected in 0.02s ============================"
        )
        with patch.object(
            commit_mod.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=5, stdout=stdout, stderr=""),
        ) as mock_run:
            result = commit_mod._run_pytest_on_files(  # ANTICHEAT_OK: locks slow-only commit gate handling
                repo,
                ["mu/tests/l4_gates/test_observer_type_guard_gate.py"],
            )

        assert result["passed"] is True
        assert result["exit_code"] == 5
        args = mock_run.call_args.args[0]
        assert ["-m", "not slow and not fuzzer"] in [
            args[index:index + 2]
            for index in range(len(args) - 1)
        ]


class TestBotRemediationValidation:
    def _fake_bridge_adapters(self, write_changes):
        from types import SimpleNamespace

        class BridgeAdapterError(Exception):
            pass

        def run_adapter(_adapter=None, *, repo_root, **_kwargs):
            write_changes(repo_root)

        return SimpleNamespace(
            AdapterSpec=lambda **kwargs: SimpleNamespace(**kwargs),
            BridgeAdapterError=BridgeAdapterError,
            load_bridge_config=lambda _path: {},
            get_adapter=lambda _config, _name: SimpleNamespace(
                name="fake",
                cmd=["true"],
                prompt_via_stdin=True,
                env={},
                mode="test",
            ),
            run_adapter=run_adapter,
        )

    def _base_result(self):
        return {
            "handoff_sha": "handoff-sha",
            "receipt_decision": "COMMIT_GO",
            "pr_number": "1036",
            "steps_completed": [
                "validate_inputs",
                "ensure_feature_branch",
                "stage_files",
                "pre_commit_supervisor",
                "validate_receipt",
                "run_pre_commit_script",
                "git_commit",
                "run_pre_push_script",
                "git_push",
                "ensure_pr",
                "wait_ci",
            ],
        }

    def _adapter_lookup_failure_bridge(self, seen):
        from types import SimpleNamespace

        class BridgeAdapterError(Exception):
            pass

        def load_bridge_config(_path):
            seen.setdefault("load_bridge_config_calls", 0)
            seen["load_bridge_config_calls"] += 1
            return {}

        def get_adapter(_config, name):
            seen.setdefault("adapter_names", []).append(name)
            raise BridgeAdapterError("adapter lookup failed")

        def run_adapter(*_args, **_kwargs):
            raise AssertionError("adapter must not run after lookup failure")

        return SimpleNamespace(
            AdapterSpec=lambda **kwargs: SimpleNamespace(**kwargs),
            BridgeAdapterError=BridgeAdapterError,
            load_bridge_config=load_bridge_config,
            get_adapter=get_adapter,
            run_adapter=run_adapter,
        )

    def _run_step15_adapter_probe(self, repo):
        logs: list[str] = []
        result = commit_mod._attempt_bot_finding_remediation(  # ANTICHEAT_OK: direct Step 15 adapter authority regression
            [{
                "path": "file.py",
                "body": "P1 adapter authority regression",
                "author": commit_mod.BOT_REVIEW_LOGIN,
                "line": 1,
            }],
            repo_root=repo,
            repo_owner="owner",
            repo_name="repo",
            pr_number="1036",
            target_branch="bot-remediation-test",
            head_sha="old-head",
            wave_id="bot-remediation-adapter-authority-test",
            continuation_path=repo / ".agent_bus" / "meta" / "commit_continuation.json",
            result=self._base_result(),
            log=logs.append,
        )
        return result, logs

    def test_bot_remediation_target_scoped_role_override_selects_target_codex(
        self,
        tmp_path,
        monkeypatch,
    ):
        repo = _setup_repo(tmp_path)
        _write_bot_remediation_executor_config(repo, backend="fable")
        monkeypatch.setenv("RCX_IMPLEMENTER_AGENT_OVERRIDE", "codex")
        monkeypatch.setenv(
            commit_mod.ROLE_AGENT_OVERRIDE_REPO_ROOT_ENV,
            str(repo.resolve()),
        )
        assert commit_mod.BOT_REMEDIATION_ADAPTER != "fable"

        seen: dict[str, object] = {}
        with patch.object(
            commit_mod,
            "BOT_REMEDIATION_ADAPTER",
            "legacy-global-must-not-be-used",
        ), patch.object(
            commit_mod,
            "_bridge_adapters",
            self._adapter_lookup_failure_bridge(seen),
        ):
            result, _logs = self._run_step15_adapter_probe(repo)

        assert result["status"] == "bot_findings_pending"
        assert seen["adapter_names"] == ["codex"]

    def test_bot_remediation_mismatched_override_root_uses_target_committed_role(
        self,
        tmp_path,
        monkeypatch,
    ):
        repo = _setup_repo(tmp_path)
        _write_bot_remediation_executor_config(repo, backend="fable")
        monkeypatch.setenv("RCX_IMPLEMENTER_AGENT_OVERRIDE", "codex")
        monkeypatch.setenv(
            commit_mod.ROLE_AGENT_OVERRIDE_REPO_ROOT_ENV,
            str(tmp_path / "other-target"),
        )

        seen: dict[str, object] = {}
        with patch.object(
            commit_mod,
            "BOT_REMEDIATION_ADAPTER",
            "legacy-global-must-not-be-used",
        ), patch.object(
            commit_mod,
            "_bridge_adapters",
            self._adapter_lookup_failure_bridge(seen),
        ):
            result, _logs = self._run_step15_adapter_probe(repo)

        assert result["status"] == "bot_findings_pending"
        assert seen["adapter_names"] == ["fable"]

    def test_bot_remediation_missing_target_config_blocks_fallback_adapter_lookup(
        self,
        tmp_path,
        monkeypatch,
    ):
        repo = _setup_repo(tmp_path)
        for env_name in commit_mod.ROLE_AGENT_ENV_VARS.get("implementer", ()):
            monkeypatch.delenv(env_name, raising=False)
        monkeypatch.delenv(commit_mod.ROLE_AGENT_OVERRIDE_REPO_ROOT_ENV, raising=False)
        fallback_config = commit_mod.load_executor_config(repo)
        assert fallback_config["backends"]["bot_remediation"]

        seen: dict[str, object] = {}
        with patch.object(
            commit_mod,
            "BOT_REMEDIATION_ADAPTER",
            "legacy-global-must-not-be-used",
        ), patch.object(
            commit_mod,
            "_bridge_adapters",
            self._adapter_lookup_failure_bridge(seen),
        ):
            result, logs = self._run_step15_adapter_probe(repo)

        assert result["status"] == "bot_findings_pending"
        assert seen.get("adapter_names", []) == []
        assert seen.get("load_bridge_config_calls", 0) == 0
        assert "target executor config missing" in "\n".join(logs)

    @pytest.mark.parametrize(
        "config_content",
        [
            pytest.param("{not json\n", id="malformed-json"),
            pytest.param("[]\n", id="non-object-config"),
            pytest.param("{}\n", id="missing-backends"),
            pytest.param(json.dumps({"backends": []}) + "\n", id="non-object-backends"),
            pytest.param(json.dumps({"backends": {}}) + "\n", id="missing-backend"),
            pytest.param(
                json.dumps({"backends": {"bot_remediation": ""}}) + "\n",
                id="blank-backend",
            ),
            pytest.param(
                json.dumps({"backends": {"bot_remediation": 42}}) + "\n",
                id="non-string-backend",
            ),
        ],
    )
    def test_bot_remediation_invalid_target_config_blocks_adapter_lookup(
        self,
        tmp_path,
        config_content,
    ):
        repo = _setup_repo(tmp_path)
        config_path = repo / "mu" / "tools" / "executors" / "executor_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(config_content, encoding="utf-8")

        seen: dict[str, object] = {}
        with patch.object(
            commit_mod,
            "BOT_REMEDIATION_ADAPTER",
            "legacy-global-must-not-be-used",
        ), patch.object(
            commit_mod,
            "_bridge_adapters",
            self._adapter_lookup_failure_bridge(seen),
        ):
            result, _logs = self._run_step15_adapter_probe(repo)

        assert result["status"] == "bot_findings_pending"
        assert seen.get("adapter_names", []) == []
        assert seen.get("load_bridge_config_calls", 0) == 0

    def test_bot_remediation_valid_target_config_adapter_lookup_failure_pending(
        self,
        tmp_path,
        monkeypatch,
    ):
        repo = _setup_repo(tmp_path)
        _write_bot_remediation_executor_config(repo, backend="fable")
        for env_name in commit_mod.ROLE_AGENT_ENV_VARS.get("implementer", ()):
            monkeypatch.delenv(env_name, raising=False)
        monkeypatch.delenv(commit_mod.ROLE_AGENT_OVERRIDE_REPO_ROOT_ENV, raising=False)

        seen: dict[str, object] = {}
        with patch.object(
            commit_mod,
            "BOT_REMEDIATION_ADAPTER",
            "legacy-global-must-not-be-used",
        ), patch.object(
            commit_mod,
            "_bridge_adapters",
            self._adapter_lookup_failure_bridge(seen),
        ):
            result, _logs = self._run_step15_adapter_probe(repo)

        assert result["status"] == "bot_findings_pending"
        assert seen["adapter_names"] == ["fable"]

    def test_bot_remediation_private_attr_gate_blocks_before_commit_or_push(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        _write_bot_remediation_executor_config(repo)
        linters = repo / "mu" / "tools" / "checks" / "linters"
        linters.mkdir(parents=True, exist_ok=True)
        (linters / "check_private_attr_access.py").write_text(
            "import sys\n"
            "print('ERROR: Found private attr access in tests/ or mu/tests/:')\n"
            "print('  mu/tests/test_bot_fix.py:3: ._stage0_match')\n"
            "sys.exit(1)\n",
            encoding="utf-8",
        )
        (linters / "check_underscore_imports.py").write_text(
            "import sys\nsys.exit(0)\n",
            encoding="utf-8",
        )
        (repo / "mu" / "tests").mkdir(parents=True, exist_ok=True)
        (repo / "mu" / "tests" / ".keep").write_text("", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "baseline linters"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        def write_changes(repo_root):
            test_path = repo_root / "mu" / "tests" / "test_bot_fix.py"
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.write_text("def test_bot_fix():\n    assert True\n", encoding="utf-8")

        real_run = commit_mod._run  # ANTICHEAT_OK: verifies bot remediation git command ordering
        seen_commands: list[list[str]] = []

        def intercept_run(args, cwd, check=True, timeout=120, env=None):
            command = list(args)
            seen_commands.append(command)
            if command[:2] == ["git", "commit"] or command[:2] == ["git", "push"]:
                raise AssertionError("bot-remediation gate failure must block commit/push")
            return real_run(args, cwd=cwd, check=check, timeout=timeout, env=env)

        logs: list[str] = []
        with patch.object(
            commit_mod,
            "_bridge_adapters",
            self._fake_bridge_adapters(write_changes),
        ), patch.object(
            commit_mod,
            "_run_pytest_on_files",
            return_value={"exit_code": 0, "stdout": "", "stderr": "", "passed": True},
        ), patch.object(commit_mod, "_run", side_effect=intercept_run):
            result = commit_mod._attempt_bot_finding_remediation(  # ANTICHEAT_OK: direct Step 15 remediation regression
                [{
                    "path": "mu/tests/test_bot_fix.py",
                    "body": "P1 private attr fallout",
                    "author": commit_mod.BOT_REVIEW_LOGIN,
                    "line": 3,
                }],
                repo_root=repo,
                repo_owner="owner",
                repo_name="repo",
                pr_number="1036",
                target_branch="bot-remediation-test",
                head_sha="old-head",
                wave_id="bot-remediation-private-attr-test",
                continuation_path=repo / ".agent_bus" / "meta" / "commit_continuation.json",
                result=self._base_result(),
                log=logs.append,
            )

        assert result["status"] == "bot_findings_pending"
        assert "errors" in result, (result, logs, seen_commands)
        assert "private-attr test-integrity gate failed" in "\n".join(result["errors"])
        assert "ERROR: Found private attr access in tests/" in "\n".join(result["errors"])
        assert not any(cmd[:2] == ["git", "commit"] for cmd in seen_commands)
        assert not any(cmd[:2] == ["git", "push"] for cmd in seen_commands)
        receipt_ok, receipt_message = meta_bridge_mod.verify_pre_commit_receipt(repo)
        assert receipt_ok is False, receipt_message
        assert (
            "No pre-commit receipt found" in receipt_message
            or "Pre-commit receipt is stale" in receipt_message
            or "does not authorize commit" in receipt_message
        )

    def test_bot_remediation_pre_push_guard_runs_before_push(self, tmp_path):
        import subprocess

        repo = _setup_repo(tmp_path)
        _write_bot_remediation_executor_config(repo)
        linters = repo / "mu" / "tools" / "checks" / "linters"
        linters.mkdir(parents=True, exist_ok=True)
        (linters / "check_private_attr_access.py").write_text(
            "import sys\nsys.exit(0)\n",
            encoding="utf-8",
        )
        (linters / "check_underscore_imports.py").write_text(
            "import sys\nsys.exit(0)\n",
            encoding="utf-8",
        )
        pre_push = repo / "mu" / "tools" / "hooks" / "pre-push-fast"
        pre_push.parent.mkdir(parents=True, exist_ok=True)
        pre_push.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "baseline gates"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        def write_changes(repo_root):
            (repo_root / "file.py").write_text("VALUE = 1\n", encoding="utf-8")

        real_run = commit_mod._run  # ANTICHEAT_OK: verifies bot remediation pre-push before push
        seen_commands: list[list[str]] = []

        def intercept_run(args, cwd, check=True, timeout=120, env=None):
            command = list(args)
            seen_commands.append(command)
            if command[:3] == ["git", "push", "--no-verify"]:
                raise subprocess.CalledProcessError(
                    1,
                    command,
                    output="",
                    stderr="blocked test push",
                )
            return real_run(args, cwd=cwd, check=check, timeout=timeout, env=env)

        with patch.object(
            commit_mod,
            "_bridge_adapters",
            self._fake_bridge_adapters(write_changes),
        ), patch.object(commit_mod, "_run", side_effect=intercept_run):
            result = commit_mod._attempt_bot_finding_remediation(  # ANTICHEAT_OK: direct Step 15 remediation regression
                [{
                    "path": "file.py",
                    "body": "P1 update file",
                    "author": commit_mod.BOT_REVIEW_LOGIN,
                    "line": 1,
                }],
                repo_root=repo,
                repo_owner="owner",
                repo_name="repo",
                pr_number="1036",
                target_branch="bot-remediation-test",
                head_sha="old-head",
                wave_id="bot-remediation-pre-push-test",
                continuation_path=repo / ".agent_bus" / "meta" / "commit_continuation.json",
                result=self._base_result(),
                log=lambda _msg: None,
            )

        assert result["status"] == "bot_findings_pending"
        pre_push_command = ["bash", str(pre_push)]
        push_indexes = [
            index for index, command in enumerate(seen_commands)
            if command[:3] == ["git", "push", "--no-verify"]
        ]
        pre_push_indexes = [
            index for index, command in enumerate(seen_commands)
            if command == pre_push_command
        ]
        assert pre_push_indexes, seen_commands
        assert push_indexes, seen_commands
        assert pre_push_indexes[0] < push_indexes[0]

    def _capture_step15_commit_env(self, repo):
        """Drive Step-15 remediation to the `git commit -m` call and return its env.

        Stops at the bot-remediation commit and returns the ``env`` argument the
        commit ``_run`` was invoked with -- i.e. the ``_commit_subprocess_env()``
        value resolved by production at that call site (the regression target).
        """
        import subprocess

        _write_bot_remediation_executor_config(repo)
        # Baseline commit so only the adapter's change is in-scope (sibling tests
        # do the same; otherwise the seed files show as untracked out-of-scope).
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "baseline"],
            cwd=repo, check=True, capture_output=True,
        )

        def write_changes(repo_root):
            (repo_root / "file.py").write_text("VALUE = 2\n", encoding="utf-8")

        real_run = commit_mod._run  # ANTICHEAT_OK: regression captures the git-commit env arg
        captured = {}

        def intercept_run(args, cwd, check=True, timeout=120, env=None):
            command = list(args)
            if command[:3] == ["git", "commit", "-m"]:
                captured["commit_env"] = env
                # Short-circuit after capture so the flow does not push / poll CI.
                raise subprocess.CalledProcessError(1, command, output="", stderr="captured")
            return real_run(args, cwd=cwd, check=check, timeout=timeout, env=env)

        with patch.object(
            commit_mod,
            "_bridge_adapters",
            self._fake_bridge_adapters(write_changes),
        ), patch.object(commit_mod, "_run", side_effect=intercept_run):
            commit_mod._attempt_bot_finding_remediation(  # ANTICHEAT_OK: direct Step 15 remediation regression
                [{
                    "path": "file.py",
                    "body": "P1 update file",
                    "author": commit_mod.BOT_REVIEW_LOGIN,
                    "line": 1,
                }],
                repo_root=repo,
                repo_owner="owner",
                repo_name="repo",
                pr_number="1036",
                target_branch="bot-remediation-test",
                head_sha="old-head",
                wave_id="bot-remediation-env-test",
                continuation_path=repo / ".agent_bus" / "meta" / "commit_continuation.json",
                result=self._base_result(),
                log=lambda _msg: None,
            )
        assert "commit_env" in captured, "Step 15 remediation never reached `git commit -m`"
        return captured["commit_env"]

    def test_bot_remediation_commit_carries_active_lane_bus_env(self, tmp_path):
        # Regression (PR #1069 / lane #24): on a NON-DEFAULT (lane) bus the Step-15
        # remediation commit must run with env=_commit_subprocess_env() so its
        # pre-commit hook resolves the SAME lane bus the receipt was minted to (else
        # the hook resolves the default .agent_bus and fails the commit with
        # 'No pre-commit receipt found'). Mirrors how Step 9 passes step9_env.
        repo = _setup_repo(tmp_path)
        lane_bus = commit_mod.agent_bus_relpath(".agent_bus-lane1")
        token = commit_mod._ACTIVE_BUS_DIR.set(lane_bus)  # ANTICHEAT_OK: activates lane bus authority
        try:
            commit_env = self._capture_step15_commit_env(repo)
            expected_env = commit_mod._commit_subprocess_env()  # ANTICHEAT_OK: regression compares commit env
            assert commit_env == expected_env
            assert commit_env is not None
            assert commit_env.get("RCX_AGENT_BUS_DIR") == str(lane_bus)
        finally:
            commit_mod._ACTIVE_BUS_DIR.reset(token)  # ANTICHEAT_OK: restores bus ContextVar

    def test_bot_remediation_commit_env_none_without_active_bus(self, tmp_path):
        # No active bus ContextVar: _commit_subprocess_env() returns None, so the
        # remediation commit env stays None -- unchanged default-bus behavior.
        repo = _setup_repo(tmp_path)
        assert commit_mod._active_bus_dir() is None  # ANTICHEAT_OK: regression precondition (default bus)
        commit_env = self._capture_step15_commit_env(repo)
        assert commit_env is None

    def _prepare_step15_auto_defer_repo(self, repo):
        """Create the clean-tree premise used by the Step-15 auto-defer path."""
        import subprocess

        _write_bot_remediation_executor_config(repo)
        # Production ignores the bus and scratch runtime surfaces.  Keep those
        # transient files out of the no-change adapter's porcelain status, while
        # tracking an explicit pre-push-fast stub so the guard is never skipped.
        (repo / ".gitignore").write_text(
            ".agent_bus/\n.agent_bus-*/\n.scratch/\n", encoding="utf-8"
        )
        pre_push = repo / "mu" / "tools" / "hooks" / "pre-push-fast"
        pre_push.parent.mkdir(parents=True, exist_ok=True)
        pre_push.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "baseline auto-defer"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def _drive_step15_auto_defer_child(
        self,
        repo,
        *,
        fail_at=None,
        failure_kind=None,
        resolver_timeout=False,
    ):
        """Drive the no-change adapter through the report child-commit strand.

        Git staging and commit are real local operations.  Only the remote push
        and GraphQL calls are intercepted.  ``fail_at`` selects one controlled
        subprocess boundary (stage, commit, guard, or push).
        """
        import subprocess

        wave_id = "bot-remediation-auto-defer-child-test"
        pr_number = "1036"
        target_branch = "bot-remediation-test"
        baseline_head = self._prepare_step15_auto_defer_repo(repo)
        continuation_path = (
            repo / ".agent_bus" / "meta" / "commit_continuation.json"
        )
        report_path = (
            repo
            / "reports"
            / "deferred"
            / "non_blocking"
            / f"pr{pr_number}_bot_auto_deferred_{wave_id}.md"
        )
        findings = [{
            "path": "docs/nit.md",
            "body": "P2 minor doc nit",
            "author": commit_mod.BOT_REVIEW_LOGIN,
            "line": 1,
        }]
        result = self._base_result()
        result.update({
            "commit_sha": baseline_head,
            "bot_review_request_sha": baseline_head,
            "pre_push_isolation": {"marker": "stale-head-isolation"},
            "pre_push_restored_paths": ["stale-head.py"],
            "stable_auto_defer_marker": "preserve-me",
        })
        # Seed an old-head continuation, including every currently supported
        # per-head field.  The child-head checkpoint must replace this payload.
        commit_mod._checkpoint_post_commit_progress(  # ANTICHEAT_OK: seeds stale-head continuation state
            result,
            continuation_path=continuation_path,
            target_branch=target_branch,
        )

        events: list[str] = []
        commands: list[dict[str, object]] = []
        checkpoints: list[dict[str, object]] = []
        checkpoint_inputs: list[dict[str, object]] = []
        reset_step_inputs: list[list[str]] = []
        guard_heads: list[str] = []
        resolver_calls: list[dict[str, object]] = []
        graphql_inputs: list[str] = []
        report_paths: list[Path] = []
        receipt_verifications: list[tuple[bool, str]] = []
        logs: list[str] = []

        real_run = commit_mod._run  # ANTICHEAT_OK: command/order observation wrapper
        real_checkpoint = commit_mod._checkpoint_post_commit_progress  # ANTICHEAT_OK: ordinary checkpoint wrapper
        real_reset_steps = commit_mod._continuation_steps_for_new_commit  # ANTICHEAT_OK: child-head step reset wrapper
        real_write_report = commit_mod._write_auto_deferred_bot_findings_report  # ANTICHEAT_OK: local-report boundary wrapper
        real_mint_receipt = commit_mod._mint_bot_remediation_receipt  # ANTICHEAT_OK: receipt-order wrapper
        real_guard = commit_mod._run_bot_remediation_pre_push_guard  # ANTICHEAT_OK: exact-HEAD guard wrapper
        real_resolver = commit_mod._resolve_auto_deferred_bot_threads  # ANTICHEAT_OK: post-push resolver wrapper
        real_subprocess_run = subprocess.run

        def selected_failure(command, timeout):
            if failure_kind == "called_process_error":
                raise subprocess.CalledProcessError(
                    23,
                    command,
                    output="controlled stdout",
                    stderr="controlled stderr",
                )
            if failure_kind == "timeout_expired":
                raise subprocess.TimeoutExpired(command, timeout=timeout)
            raise AssertionError(f"unknown failure kind: {failure_kind!r}")

        def intercept_run(
            args,
            *,
            cwd,
            check=True,
            timeout=120,
            env=None,
            input_text=None,
        ):
            command = list(args)
            commands.append({"command": command, "timeout": timeout, "env": env})
            is_stage = command[:4] == ["git", "add", "-f", "--"]
            is_commit = command[:3] == ["git", "commit", "-m"]
            is_guard = command == [
                "bash",
                str(repo / "mu" / "tools" / "hooks" / "pre-push-fast"),
            ]
            is_push = command[:2] == ["git", "push"]
            is_head_read = command == ["git", "rev-parse", "HEAD"]
            if is_stage:
                assert report_path.exists(), "report must exist before it is staged"
                events.append("stage_report")
            elif is_commit:
                events.append("commit_child")
                receipt_verifications.append(
                    meta_bridge_mod.verify_pre_commit_receipt(
                        Path(cwd),
                        bus_dir=(env or {}).get("RCX_AGENT_BUS_DIR"),
                    )
                )
            elif is_guard:
                events.append("guard_subprocess")
            elif is_push:
                events.append("push")
            elif is_head_read:
                events.append("read_child_head")

            if (
                (fail_at == "stage" and is_stage)
                or (fail_at == "commit" and is_commit)
                or (fail_at == "guard" and is_guard)
                or (fail_at == "push" and is_push)
            ):
                selected_failure(command, timeout)
            if is_push:
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            return real_run(
                command,
                cwd=Path(cwd),
                check=check,
                timeout=timeout,
                env=env,
                input_text=input_text,
            )

        def capture_report(*args, **kwargs):
            events.append("write_report")
            path = real_write_report(*args, **kwargs)
            report_paths.append(path)
            return path

        def capture_receipt(*args, **kwargs):
            staged = real_subprocess_run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.splitlines()
            assert str(report_path.relative_to(repo)) in staged
            events.append("mint_receipt")
            return real_mint_receipt(*args, **kwargs)

        def capture_checkpoint(
            checkpoint_result,
            *,
            continuation_path,
            target_branch,
        ):
            checkpoint_inputs.append(json.loads(json.dumps(checkpoint_result)))
            real_checkpoint(
                checkpoint_result,
                continuation_path=continuation_path,
                target_branch=target_branch,
            )
            payload = json.loads(continuation_path.read_text(encoding="utf-8"))
            checkpoints.append(payload)
            events.append(f"checkpoint:{payload['steps_completed'][-1]}")

        def capture_reset_steps(steps_completed):
            reset_step_inputs.append(list(steps_completed))
            return real_reset_steps(steps_completed)

        def capture_guard(repo_root, *, log=None):
            head = real_subprocess_run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            guard_heads.append(head)
            events.append("guard_enter")
            guard_result = real_guard(repo_root, log=log)
            events.append(
                "guard_passed" if guard_result["passed"] else "guard_failed"
            )
            return guard_result

        def capture_resolver(**kwargs):
            resolver_calls.append(dict(kwargs))
            events.append("resolver")
            return real_resolver(**kwargs)

        def intercept_subprocess_run(args, *positional, **kwargs):
            command = list(args)
            if command == ["gh", "api", "graphql", "--input", "-"]:
                graphql_input = str(kwargs.get("input") or "")
                graphql_inputs.append(graphql_input)
                if "mutation" in graphql_input:
                    events.append("graphql_mutation")
                    if resolver_timeout:
                        raise subprocess.TimeoutExpired(command, timeout=30)
                    stdout = json.dumps({
                        "data": {"resolveReviewThread": {"thread": {"isResolved": True}}}
                    })
                else:
                    events.append("graphql_query")
                    stdout = json.dumps({
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "reviewThreads": {
                                        "nodes": [
                                            {
                                                "id": "human-thread",
                                                "isResolved": False,
                                                "comments": {"nodes": [{
                                                    "author": {"login": "human-reviewer"}
                                                }]},
                                            },
                                            {
                                                "id": "resolved-bot-thread",
                                                "isResolved": True,
                                                "comments": {"nodes": [{
                                                    "author": {"login": commit_mod.BOT_REVIEW_LOGIN}
                                                }]},
                                            },
                                            {
                                                "id": "eligible-bot-thread",
                                                "isResolved": False,
                                                "comments": {"nodes": [{
                                                    "author": {"login": commit_mod.BOT_REVIEW_LOGIN}
                                                }]},
                                            },
                                        ]
                                    }
                                }
                            }
                        }
                    })
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=stdout,
                    stderr="",
                )
            return real_subprocess_run(args, *positional, **kwargs)

        lane_bus = commit_mod.agent_bus_relpath(".agent_bus-auto-defer")
        token = commit_mod._ACTIVE_BUS_DIR.set(lane_bus)  # ANTICHEAT_OK: active receipt/commit bus authority
        try:
            expected_commit_env = commit_mod._commit_subprocess_env()  # ANTICHEAT_OK: exact existing commit env
            with patch.object(
                commit_mod,
                "_bridge_adapters",
                self._fake_bridge_adapters(lambda _repo_root: None),
            ), patch.object(
                commit_mod,
                "_write_auto_deferred_bot_findings_report",
                side_effect=capture_report,
            ), patch.object(
                commit_mod,
                "_mint_bot_remediation_receipt",
                side_effect=capture_receipt,
            ), patch.object(
                commit_mod,
                "_checkpoint_post_commit_progress",
                side_effect=capture_checkpoint,
            ), patch.object(
                commit_mod,
                "_continuation_steps_for_new_commit",
                side_effect=capture_reset_steps,
            ), patch.object(
                commit_mod,
                "_run_bot_remediation_pre_push_guard",
                side_effect=capture_guard,
            ), patch.object(
                commit_mod,
                "_resolve_auto_deferred_bot_threads",
                side_effect=capture_resolver,
            ), patch.object(
                commit_mod,
                "_wait_for_pr_ci",
            ) as wait_for_ci, patch.object(
                commit_mod,
                "_query_pr_review_state",
            ) as query_pr_state, patch.object(
                commit_mod,
                "_maybe_request_current_head_bot_review",
            ) as request_bot_review, patch.object(
                commit_mod,
                "_wait_for_bot_review_freshness",
            ) as wait_review, patch.object(
                commit_mod,
                "_run",
                side_effect=intercept_run,
            ), patch.object(
                commit_mod.subprocess,
                "run",
                side_effect=intercept_subprocess_run,
            ):
                response = commit_mod._attempt_bot_finding_remediation(  # ANTICHEAT_OK: full no-change auto-defer path
                    findings,
                    repo_root=repo,
                    repo_owner="owner",
                    repo_name="repo",
                    pr_number=pr_number,
                    target_branch=target_branch,
                    head_sha=baseline_head,
                    wave_id=wave_id,
                    continuation_path=continuation_path,
                    result=result,
                    log=logs.append,
                )
        finally:
            commit_mod._ACTIVE_BUS_DIR.reset(token)  # ANTICHEAT_OK: restore bus ContextVar

        child_head = real_subprocess_run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return {
            "response": response,
            "baseline_head": baseline_head,
            "child_head": child_head,
            "expected_commit_env": expected_commit_env,
            "events": events,
            "commands": commands,
            "checkpoints": checkpoints,
            "checkpoint_inputs": checkpoint_inputs,
            "reset_step_inputs": reset_step_inputs,
            "guard_heads": guard_heads,
            "resolver_calls": resolver_calls,
            "graphql_inputs": graphql_inputs,
            "report_paths": report_paths,
            "report_path": report_path,
            "receipt_verifications": receipt_verifications,
            "logs": logs,
            "downstream_calls": {
                "wait_for_ci": wait_for_ci.call_count,
                "query_pr_state": query_pr_state.call_count,
                "request_bot_review": request_bot_review.call_count,
                "wait_review": wait_review.call_count,
            },
        }

    def test_auto_defer_report_writer_is_filesystem_only(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        with patch.object(
            commit_mod.subprocess,
            "run",
            side_effect=AssertionError("report creation must not spawn a subprocess"),
        ):
            report_path = commit_mod._write_auto_deferred_bot_findings_report(  # ANTICHEAT_OK: local-only report boundary
                repo,
                [{"path": "docs/nit.md", "body": "P2 local report"}],
                "local-report-wave",
                "1036",
                lambda _msg: None,
            )

        assert report_path.exists()
        report = report_path.read_text(encoding="utf-8")
        assert "PR #1036 Bot Findings (Auto-Deferred)" in report
        assert "`docs/nit.md`" in report
        assert "P2 local report" in report

    def test_auto_defer_uses_child_commit_checkpoint_guard_push_then_resolver(
        self,
        tmp_path,
    ):
        import subprocess

        repo = _setup_repo(tmp_path)
        captured = self._drive_step15_auto_defer_child(
            repo,
            resolver_timeout=True,
        )

        assert captured["response"] is None
        assert captured["child_head"] != captured["baseline_head"]
        parent_head = subprocess.run(
            ["git", "rev-parse", f"{captured['child_head']}^"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert parent_head == captured["baseline_head"]
        assert captured["report_paths"] == [captured["report_path"]]
        committed_paths = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", captured["child_head"]],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        assert str(captured["report_path"].relative_to(repo)) in committed_paths

        commands = captured["commands"]
        command_lists = [entry["command"] for entry in commands]
        assert command_lists.index([
            "git", "add", "-f", "--", str(captured["report_path"].relative_to(repo)),
        ]) < next(
            index
            for index, command in enumerate(command_lists)
            if command[:3] == ["git", "commit", "-m"]
        )
        commit_commands = [
            entry for entry in commands
            if entry["command"][:3] == ["git", "commit", "-m"]
        ]
        assert len(commit_commands) == 1
        assert commit_commands[0]["env"] == captured["expected_commit_env"]
        assert captured["receipt_verifications"]
        receipt_passed, receipt_message = captured["receipt_verifications"][0]
        assert receipt_passed, receipt_message
        assert not any("--amend" in command for command in command_lists)
        assert not any(
            any(arg.startswith("--force") for arg in command)
            for command in command_lists
        )

        push_entries = [
            entry for entry in commands if entry["command"][:2] == ["git", "push"]
        ]
        assert push_entries == [{
            "command": [
                "git", "push", "--no-verify", "origin", "bot-remediation-test",
            ],
            "timeout": 300,
            "env": None,
        }]

        expected_reset_steps = self._base_result()["steps_completed"][:7]
        assert captured["reset_step_inputs"] == [
            self._base_result()["steps_completed"]
        ]
        first_checkpoint = captured["checkpoints"][0]
        first_checkpoint_input = captured["checkpoint_inputs"][0]
        assert first_checkpoint["commit_sha"] == captured["child_head"]
        assert first_checkpoint["steps_completed"] == expected_reset_steps
        assert first_checkpoint_input["stable_auto_defer_marker"] == "preserve-me"
        for stale_key in (
            "bot_review_request_sha",
            "pre_push_isolation",
            "pre_push_restored_paths",
        ):
            assert stale_key not in first_checkpoint
            assert stale_key not in first_checkpoint_input

        assert captured["guard_heads"]
        assert all(
            head == captured["child_head"] for head in captured["guard_heads"]
        )
        guard_checkpoints = [
            payload for payload in captured["checkpoints"]
            if payload["steps_completed"][-1] == "run_pre_push_script"
        ]
        push_checkpoints = [
            payload for payload in captured["checkpoints"]
            if payload["steps_completed"][-1] == "git_push"
        ]
        assert guard_checkpoints
        assert push_checkpoints
        assert all(
            payload["commit_sha"] == captured["child_head"]
            for payload in guard_checkpoints + push_checkpoints
        )

        events = captured["events"]
        assert events.index("write_report") < events.index("stage_report")
        assert events.index("stage_report") < events.index("mint_receipt")
        assert events.index("mint_receipt") < events.index("commit_child")
        assert events.index("commit_child") < events.index("read_child_head")
        assert events.index("read_child_head") < events.index("checkpoint:git_commit")
        assert events.index("checkpoint:git_commit") < events.index("guard_enter")
        assert events.index("guard_passed") < events.index("checkpoint:run_pre_push_script")
        assert events.index("checkpoint:run_pre_push_script") < events.index("push")
        assert events.index("push") < events.index("checkpoint:git_push")
        assert events.index("checkpoint:git_push") < events.index("resolver")
        assert events.index("resolver") < events.index("graphql_query")
        assert events.index("graphql_query") < events.index("graphql_mutation")

        mutations = [value for value in captured["graphql_inputs"] if "mutation" in value]
        assert len(mutations) == 1
        assert "eligible-bot-thread" in mutations[0]
        assert "human-thread" not in mutations[0]
        assert "resolved-bot-thread" not in mutations[0]
        assert any("failed to resolve comment threads (non-fatal)" in log for log in captured["logs"])
        assert captured["downstream_calls"] == {
            "wait_for_ci": 0,
            "query_pr_state": 0,
            "request_bot_review": 0,
            "wait_review": 0,
        }

    @pytest.mark.parametrize("fail_at", ["stage", "commit", "guard", "push"])
    @pytest.mark.parametrize(
        "failure_kind",
        ["called_process_error", "timeout_expired"],
    )
    def test_auto_defer_subprocess_failure_is_controlled_before_remote_followup(
        self,
        tmp_path,
        fail_at,
        failure_kind,
    ):
        repo = _setup_repo(tmp_path)
        captured = self._drive_step15_auto_defer_child(
            repo,
            fail_at=fail_at,
            failure_kind=failure_kind,
        )

        response = captured["response"]
        assert response is not None
        assert response["status"] == "bot_findings_pending"
        assert captured["resolver_calls"] == []
        assert captured["graphql_inputs"] == []
        assert captured["downstream_calls"] == {
            "wait_for_ci": 0,
            "query_pr_state": 0,
            "request_bot_review": 0,
            "wait_review": 0,
        }

        command_lists = [entry["command"] for entry in captured["commands"]]
        assert not any(
            any(str(arg).endswith("merge_pr.sh") for arg in command)
            for command in command_lists
        )
        assert not any(
            payload["steps_completed"][-1] == "git_push"
            for payload in captured["checkpoints"]
        )
        head_reads = [
            command for command in command_lists
            if command == ["git", "rev-parse", "HEAD"]
        ]
        assert len(head_reads) <= 1, "must not advance to the post-CI PR-head refresh"
        push_commands = [
            command for command in command_lists if command[:2] == ["git", "push"]
        ]
        if fail_at == "push":
            assert push_commands == [[
                "git", "push", "--no-verify", "origin", "bot-remediation-test",
            ]]
        else:
            assert push_commands == []

    def _fake_bridge_adapters_timeout(self, message="Adapter 'claude' timed out after 600s"):
        """Fake bridge adapters whose ``run_adapter`` RAISES BridgeAdapterError.

        Drives the production ``except _bridge_adapters.BridgeAdapterError``
        branch of ``_attempt_bot_finding_remediation`` -- the bot-remediation
        adapter TIMEOUT/error path (the slow ``bot_remediation=claude`` adapter
        hitting the 600s adapter timeout). Mirrors ``_fake_bridge_adapters``
        otherwise so the pre-loop adapter load/get path behaves identically.
        """
        from types import SimpleNamespace

        class BridgeAdapterError(Exception):
            pass

        def run_adapter(_adapter=None, *, repo_root, **_kwargs):
            raise BridgeAdapterError(message)

        return SimpleNamespace(
            AdapterSpec=lambda **kwargs: SimpleNamespace(**kwargs),
            BridgeAdapterError=BridgeAdapterError,
            load_bridge_config=lambda _path: {},
            get_adapter=lambda _config, _name: SimpleNamespace(
                name="fake",
                cmd=["true"],
                prompt_via_stdin=True,
                env={},
                mode="test",
            ),
            run_adapter=run_adapter,
        )

    def _run_timeout_remediation(self, repo, findings, *, wave_id):
        """Drive ``_attempt_bot_finding_remediation`` so the remediation adapter
        raises BridgeAdapterError (timeout). Returns ``(response, auto_defer)``.

        ``_auto_defer_bot_findings`` is mocked to return the successful
        auto-defer sentinel without writing, committing, pushing, or resolving.
        The unit under test is the timeout-path classification (auto-defer vs
        route-to-recovery), while the child-commit mechanics are covered by
        ``test_auto_defer_uses_child_commit_checkpoint_guard_push_then_resolver``.
        """
        _write_bot_remediation_executor_config(repo)
        with patch.object(
            commit_mod, "_bridge_adapters", self._fake_bridge_adapters_timeout(),
        ), patch.object(
            commit_mod, "_auto_defer_bot_findings", return_value=None,
        ) as auto_defer:
            response = commit_mod._attempt_bot_finding_remediation(  # ANTICHEAT_OK: direct Step 15 timeout classification regression
                findings,
                repo_root=repo,
                repo_owner="owner",
                repo_name="repo",
                pr_number="1036",
                target_branch="bot-remediation-test",
                head_sha="old-head",
                wave_id=wave_id,
                continuation_path=repo / ".agent_bus" / "meta" / "commit_continuation.json",
                result=self._base_result(),
                log=lambda _msg: None,
            )
        return response, auto_defer

    def test_bot_remediation_timeout_autodefers_deferrable(self, tmp_path):
        # Regression (wave bot-remediation-timeout-autodefers-2026-06-29): a bot
        # remediation adapter TIMEOUT (BridgeAdapterError) on an all-deferrable
        # (P2+/non-critical) finding set must AUTO-DEFER so the commit proceeds,
        # exactly as the no-change path already does for the SAME findings.
        # Before the shared-classifier refactor the `except BridgeAdapterError`
        # branch returned bot_findings_pending UNCONDITIONALLY, stranding the
        # wave (the slow bot_remediation=claude adapter routinely hits the 600s
        # adapter timeout). The timeout/error path and the no-change path now
        # share ONE classifier, so their disposition is identical.
        repo = _setup_repo(tmp_path)
        response, auto_defer = self._run_timeout_remediation(
            repo,
            [{
                "path": "docs/nit.md",
                "body": "P2 minor doc nit",
                "author": commit_mod.BOT_REVIEW_LOGIN,
                "line": 1,
            }],
            wave_id="bot-remediation-timeout-autodefer-test",
        )
        # None == auto-deferred (caller proceeds to merge), NOT bot_findings_pending.
        assert response is None, response
        assert auto_defer.called, "all-deferrable timeout must auto-defer"

    def test_bot_remediation_timeout_p1_finding_routes_to_recovery(self, tmp_path):
        # A bot remediation adapter TIMEOUT with a P0/P1 finding must STILL route
        # to recovery (bot_findings_pending), never auto-defer -- the shared
        # classifier reuses the EXISTING P0/P1 guard (the bot's P-level badge),
        # so the blocking disposition is unchanged on the timeout path.
        repo = _setup_repo(tmp_path)
        response, auto_defer = self._run_timeout_remediation(
            repo,
            [{
                "path": "docs/nit.md",
                "body": "P1 blocking regression",
                "author": commit_mod.BOT_REVIEW_LOGIN,
                "line": 1,
            }],
            wave_id="bot-remediation-timeout-p1-test",
        )
        assert response is not None
        assert response["status"] == "bot_findings_pending"
        auto_defer.assert_not_called()

    def test_bot_remediation_timeout_critical_path_finding_routes_to_recovery(self, tmp_path):
        # A bot remediation adapter TIMEOUT with a finding on a critical-path
        # file (here mu/tools/executors/) must route to recovery REGARDLESS of
        # P-level -- the shared classifier reuses the EXISTING
        # _CRITICAL_PATH_PREFIXES guard. The finding below is only P2, proving
        # the critical-path guard (not the P0/P1 guard) is what fires on the
        # timeout path.
        repo = _setup_repo(tmp_path)
        response, auto_defer = self._run_timeout_remediation(
            repo,
            [{
                "path": "mu/tools/executors/commit_executor.py",
                "body": "P2 nit on a critical-path file",
                "author": commit_mod.BOT_REVIEW_LOGIN,
                "line": 1,
            }],
            wave_id="bot-remediation-timeout-critical-test",
        )
        assert response is not None
        assert response["status"] == "bot_findings_pending"
        auto_defer.assert_not_called()


class TestCommitValidationChildBusIsolation:
    """Commit-owned validation children must be hermetic against the live lane.

    Reproduction (pipeline-fix-37b -> 37c): on a namespaced live lane the parent
    env carries ``RCX_AGENT_BUS_DIR=.agent_bus-fix37`` PLUS the live dispatcher's
    ``RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE`` and role overrides. Before this
    fix the validation call sites passed ``env=None`` or ``{**os.environ, ...}``,
    so the pre-push-fast / targeted-pytest child inherited the live lane bus AND
    the live pager route. The repository's own bus-resolving tests then resolved
    ``.agent_bus-fix37``, and
    ``test_pager_persists_event_delivery_state_and_lock_in_namespaced_bus`` failed
    because the leaked ``codex`` route suppressed delivery-receipt/state/lock
    persistence -- the pipeline-fix-37b Step 11 failure that its bus-only strip did
    NOT close. ``_commit_subprocess_env`` (commit/amend hooks) MUST keep the lane
    bus; only validation children drop the bus AND the role/pager overrides.

    WI-1 finding (counterproof-repoint-r2, 2026-07-26) -- why the counter-proof
    below went vacuous, established by direct experiment, not conjecture: the
    leaked route override DOES still reach the delivery path
    (``_resolve_route`` honours it ahead of the repository's configured route),
    and delivery-receipt/state/lock persistence IS still route-sensitive. What
    moved is AMBIENT MACHINE STATE. Under ``route=codex`` the receipt is written
    only when ``_dispatch_codex`` acknowledges, and that requires a live codex
    app-server websocket listener on ``ws://127.0.0.1:8765``. With the founder's
    codex app-server up (observed listening, PID-owned by ``codex``) the leaked
    route ACKNOWLEDGED, the receipt was written, the reproduced target passed --
    and the test minted a REAL codex thread as a side effect. With that listener
    unreachable the same run failed on the missing
    ``pipeline_agent_delivery_receipts.jsonl``, exactly as in pipeline-fix-37b.
    So the counter-proof's pass/fail was a function of whether a process outside
    this repository happened to be running. The reproduction is therefore PINNED
    (see ``_pin_codex_transport_unconfigured``) into a deterministic negative
    control instead of being re-pointed at another ambient-state-dependent target.
    """

    _MALICIOUS_LANE = ".agent_bus-fix37"
    _PAGER_ENV = "RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE"
    _BRIDGE_TURN_TIMEOUT_OVERRIDE_ENV = "RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_OVERRIDE"
    _BRIDGE_TURN_TIMEOUT_KEY_ENV = "RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY"
    _BRIDGE_TURN_TIMEOUT_ENVS = frozenset(
        {_BRIDGE_TURN_TIMEOUT_OVERRIDE_ENV, _BRIDGE_TURN_TIMEOUT_KEY_ENV}
    )
    _PAGER_TEST = (
        "mu/tests/tools/test_agent_bus_namespacing.py::"
        "test_pager_persists_event_delivery_state_and_lock_in_namespaced_bus"
    )
    # Deterministic codex-transport pin (WI-2). A non-``ws://`` URL is rejected
    # IN-PROCESS by ``pipeline_agent_pager._codex_app_server_url`` before any
    # socket or subprocess, and ``_is_codex_transport_unavailable`` is False for
    # that rejection, so the ``codex exec resume`` fallback -- the one path that
    # would spawn the real ``codex`` binary -- can never fire. An empty
    # ``CODEX_THREAD_ID`` removes the fallback's other trigger. Neither key is a
    # protected key, so BOTH legs of the counter-proof inherit the pin and the
    # ONLY variable that differs between them is the route override itself.
    _CODEX_URL_ENV = "RCX_CODEX_APP_SERVER_URL"
    _CODEX_THREAD_ENV = "CODEX_THREAD_ID"
    _CODEX_TRANSPORT_UNCONFIGURED = "http://127.0.0.1:8765"

    def _seed_live_overrides(self, monkeypatch):
        """Export a full live pipeline lane parent env: bus + pager + roles + guard."""
        monkeypatch.setenv("RCX_AGENT_BUS_DIR", self._MALICIOUS_LANE)
        monkeypatch.setenv(self._PAGER_ENV, "codex")
        for env_names in commit_mod.ROLE_AGENT_ENV_VARS.values():
            for name in env_names:
                monkeypatch.setenv(name, "codex")
        monkeypatch.setenv(commit_mod.ROLE_AGENT_OVERRIDE_REPO_ROOT_ENV, "/live/repo")

    def _pin_codex_transport_unconfigured(self, monkeypatch):
        """Remove ambient codex reachability from the leaked-route reproduction.

        Pins the codex delivery leg to a transport it can never acknowledge on any
        machine, so the reproduction no longer depends on whether a live codex
        app-server happens to be listening -- and never pages a real codex thread
        from inside the test suite. Applied to the PARENT env so it is inherited by
        the leaky child AND by the hermetic validation child alike.
        """
        monkeypatch.setenv(self._CODEX_URL_ENV, self._CODEX_TRANSPORT_UNCONFIGURED)
        monkeypatch.setenv(self._CODEX_THREAD_ENV, "")

    def _write_pager_repo(self, base, name):
        """Mirror the reproduced target's fixture: pager ENABLED on the DEFAULT
        ``notify-only`` route, so the resolved route can only change via an env
        override."""
        repo = base / name
        (repo / "mu" / "tools" / "executors").mkdir(parents=True, exist_ok=True)
        (repo / "mu" / "tools" / "executors" / "executor_config.json").write_text(
            json.dumps({"pipeline_agent_pager": {"enabled": True, "route": "notify-only"}})
            + "\n",
            encoding="utf-8",
        )
        return repo

    def _emit_pager_event(self, repo):
        """Emit the reproduced target's exact transition event into ``repo``."""
        return pager_mod.emit_transition_event(
            repo,
            bus_dir=".agent_bus-test",
            event_type="commit_ready",
            wave_id="wave-bus",
            task_id="[BUS]",
            plan_path="reports/control_plane/bus.md",
            phase="phase_b",
            state="commit_ready",
            transition_key="bus-ready",
            summary="ready",
            reason="receipt available",
            artifact_paths={"receipt": ".agent_bus-test/meta/pre_commit_receipts/r.json"},
        )

    def test_commit_validation_env_strips_bus_pager_and_role_overrides(self, monkeypatch):
        # A malicious/live parent env carries every protected override plus
        # unrelated variables that MUST survive byte-for-byte.
        self._seed_live_overrides(monkeypatch)
        monkeypatch.setenv("RCX_RECOVERY_UPSTREAM_CONNECTIVITY_RETRY", "1")
        monkeypatch.setenv("RCX_SKIP_RECEIPT_CHECK", "1")
        monkeypatch.setenv("UNRELATED_VALIDATION_VAR", "keep-me")

        hermetic = commit_mod._commit_validation_env()  # ANTICHEAT_OK: validation-child override isolation regression

        # Every protected key is gone: live lane bus + pager route + ALL role
        # overrides + the repo-root role-override guard.
        protected = commit_mod._commit_validation_protected_env_keys()  # ANTICHEAT_OK: canonical protected-key set under test
        assert "RCX_AGENT_BUS_DIR" in protected and self._PAGER_ENV in protected
        for key in protected:
            assert key not in hermetic, f"protected key leaked into validation child: {key}"
        # Unrelated env preserved byte-for-byte; RCX_SKIP_* stripped for _run parity.
        assert hermetic.get("RCX_RECOVERY_UPSTREAM_CONNECTIVITY_RETRY") == "1"
        assert hermetic.get("UNRELATED_VALIDATION_VAR") == "keep-me"
        assert hermetic.get("PATH") == os.environ.get("PATH")
        assert not any(k.startswith("RCX_SKIP_") for k in hermetic)
        # It equals EXACTLY the parent env minus RCX_SKIP_* and every protected key.
        expected = {k: v for k, v in os.environ.items() if not k.startswith("RCX_SKIP_")}
        for key in protected:
            expected.pop(key, None)
        assert hermetic == expected
        # Building the validation-child env never mutates the parent os.environ.
        assert os.environ.get("RCX_AGENT_BUS_DIR") == self._MALICIOUS_LANE
        assert os.environ.get(self._PAGER_ENV) == "codex"
        assert os.environ.get("RCX_SKIP_RECEIPT_CHECK") == "1"

    def test_commit_validation_env_strips_inherited_bridge_turn_timeout_state(
        self, monkeypatch
    ):
        inherited = {
            self._BRIDGE_TURN_TIMEOUT_OVERRIDE_ENV: "901",
            self._BRIDGE_TURN_TIMEOUT_KEY_ENV: "phase_b",
        }
        for key, value in inherited.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", "777")
        monkeypatch.setenv("UNRELATED_VALIDATION_VAR", "keep-me")
        parent_before = dict(os.environ)

        hermetic = commit_mod._commit_validation_env()  # ANTICHEAT_OK: bridge-turn timeout containment regression

        protected = commit_mod._commit_validation_protected_env_keys()  # ANTICHEAT_OK: exact protected-key set under test
        assert self._BRIDGE_TURN_TIMEOUT_ENVS <= protected
        for key in inherited:
            assert key not in hermetic
        assert hermetic.get("RCX_RECOVERY_TIMEOUT_OVERRIDE") == "777"
        assert hermetic.get("UNRELATED_VALIDATION_VAR") == "keep-me"
        assert dict(os.environ) == parent_before

    def test_commit_validation_env_strips_bridge_turn_timeout_caller_overrides(
        self, monkeypatch
    ):
        parent_values = {
            self._BRIDGE_TURN_TIMEOUT_OVERRIDE_ENV: "901",
            self._BRIDGE_TURN_TIMEOUT_KEY_ENV: "phase_b",
        }
        for key, value in parent_values.items():
            monkeypatch.setenv(key, value)
        parent_before = dict(os.environ)

        hermetic = commit_mod._commit_validation_env(  # ANTICHEAT_OK: caller override containment regression
            {
                self._BRIDGE_TURN_TIMEOUT_OVERRIDE_ENV: "1200",
                self._BRIDGE_TURN_TIMEOUT_KEY_ENV: "phase_a",
                "BENIGN_OVERRIDE": "applied",
            }
        )

        for key in self._BRIDGE_TURN_TIMEOUT_ENVS:
            assert key not in hermetic
        assert hermetic.get("BENIGN_OVERRIDE") == "applied"
        assert dict(os.environ) == parent_before

    def test_commit_validation_env_pins_survive_but_overrides_cannot_reinject(self, monkeypatch):
        self._seed_live_overrides(monkeypatch)
        # The pytest determinism pins are applied BEFORE the protected-key removal,
        # so they survive; they are not protected keys.
        pinned = commit_mod._commit_validation_env(  # ANTICHEAT_OK: pins-survive regression
            {"PYTHONHASHSEED": "0", "RCX_CI": "1", "HYPOTHESIS_PROFILE": "ci_fast"}
        )
        assert pinned.get("PYTHONHASHSEED") == "0"
        assert pinned.get("RCX_CI") == "1"
        assert pinned.get("HYPOTHESIS_PROFILE") == "ci_fast"
        assert "RCX_AGENT_BUS_DIR" not in pinned and self._PAGER_ENV not in pinned
        # A MALICIOUS caller override cannot restore any protected key or a skip key,
        # because the protected-key removal runs after overrides are applied.
        evil = commit_mod._commit_validation_env(  # ANTICHEAT_OK: malicious-override regression
            {
                "RCX_AGENT_BUS_DIR": ".agent_bus-evil",
                self._PAGER_ENV: "claude",
                "RCX_IMPLEMENTER_AGENT_OVERRIDE": "codex",
                "RCX_ROLE_AGENT_OVERRIDE_REPO_ROOT": "/evil",
                "RCX_SKIP_RECEIPT_CHECK": "1",
                "BENIGN_OVERRIDE": "applied",
            }
        )
        assert "RCX_AGENT_BUS_DIR" not in evil
        assert self._PAGER_ENV not in evil
        assert "RCX_IMPLEMENTER_AGENT_OVERRIDE" not in evil
        assert "RCX_ROLE_AGENT_OVERRIDE_REPO_ROOT" not in evil
        assert not any(k.startswith("RCX_SKIP_") for k in evil)
        assert evil.get("BENIGN_OVERRIDE") == "applied"

    def test_commit_validation_env_follows_canonical_role_truth(self, monkeypatch):
        # Acceptance: sanitization follows canonical role override truth, so the
        # later independent supervisor role can be added to ROLE_AGENT_ENV_VARS
        # without reopening the leak -- no edit to this helper is required.
        patched = dict(commit_mod.ROLE_AGENT_ENV_VARS)
        patched["supervisor"] = ("RCX_SUPERVISOR_AGENT_OVERRIDE",)
        monkeypatch.setattr(commit_mod, "ROLE_AGENT_ENV_VARS", patched)
        monkeypatch.setenv("RCX_SUPERVISOR_AGENT_OVERRIDE", "codex")
        assert (
            "RCX_SUPERVISOR_AGENT_OVERRIDE"
            in commit_mod._commit_validation_protected_env_keys()  # ANTICHEAT_OK: canonical-truth forward-compat
        )
        assert "RCX_SUPERVISOR_AGENT_OVERRIDE" not in commit_mod._commit_validation_env()  # ANTICHEAT_OK

    def test_bot_remediation_pre_push_guard_env_omits_overrides(self, tmp_path, monkeypatch):
        # Production call site #1: Step-15 bot-remediation pre-push guard.
        repo = _setup_repo(tmp_path)
        pre_push = repo / "mu" / "tools" / "hooks" / "pre-push-fast"
        pre_push.parent.mkdir(parents=True, exist_ok=True)
        pre_push.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")

        self._seed_live_overrides(monkeypatch)

        captured: dict[str, object] = {}
        real_run = commit_mod._run  # ANTICHEAT_OK: validation-child override isolation regression

        def intercept_run(args, cwd, check=True, timeout=120, env=None, input_text=None):
            if list(args) == ["bash", str(pre_push)]:
                captured["env"] = env
            return real_run(
                args, cwd=cwd, check=check, timeout=timeout, env=env, input_text=input_text
            )

        with patch.object(commit_mod, "_run", side_effect=intercept_run):
            guard = commit_mod._run_bot_remediation_pre_push_guard(  # ANTICHEAT_OK: direct guard regression
                repo, log=lambda _msg: None
            )

        assert guard["passed"] is True
        assert "env" in captured, "pre-push guard never invoked the pre-push-fast script"
        env = captured["env"]
        assert env is not None
        assert "RCX_AGENT_BUS_DIR" not in env
        assert self._PAGER_ENV not in env
        assert env.get("PATH") == os.environ.get("PATH")
        # Exactly the hermetic construction, and the parent env is not mutated.
        assert env == commit_mod._commit_validation_env()  # ANTICHEAT_OK: validation-child override isolation regression
        assert os.environ.get("RCX_AGENT_BUS_DIR") == self._MALICIOUS_LANE
        assert os.environ.get(self._PAGER_ENV) == "codex"

    def test_step11_post_commit_pre_push_env_omits_overrides(self, tmp_path, monkeypatch):
        # Production call site #2: ordinary Step 11 (_run_post_commit_pipeline).
        import subprocess

        repo = _setup_repo(tmp_path)
        pre_push = repo / "mu" / "tools" / "hooks" / "pre-push-fast"
        pre_push.parent.mkdir(parents=True, exist_ok=True)
        pre_push.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        # Clean the worktree so Step 11 takes the direct pre-push path (no dirty
        # isolation stash), then the intercept captures the pre-push env.
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True
        )
        head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
        ).stdout.strip()

        self._seed_live_overrides(monkeypatch)

        captured: dict[str, object] = {}
        real_run = commit_mod._run  # ANTICHEAT_OK: validation-child override isolation regression

        def intercept_run(args, cwd, check=True, timeout=120, env=None, input_text=None):
            if list(args) == ["bash", str(pre_push)]:
                captured["env"] = env
                # Short-circuit before push/CI now that the env is captured.
                raise subprocess.CalledProcessError(1, list(args), output="", stderr="captured")
            return real_run(
                args, cwd=cwd, check=check, timeout=timeout, env=env, input_text=input_text
            )

        result = {
            "commit_sha": head_sha,
            "receipt_decision": "COMMIT_GO",
            "handoff_sha": "handoff-sha",
            "steps_completed": ["git_commit"],
        }
        with patch.object(commit_mod, "_run", side_effect=intercept_run):
            pipeline_result = commit_mod._run_post_commit_pipeline(  # ANTICHEAT_OK: Step 11 regression
                handoff={"wave_id": "validation-child-override-isolation-step11"},
                repo_root=repo,
                result=result,
                target_branch="dev",
                base_branch="dev",
                continuation_path=repo / ".agent_bus" / "meta" / "commit_continuation.json",
                log=lambda _msg: None,
            )

        assert "env" in captured, "Step 11 never invoked the pre-push-fast script"
        env = captured["env"]
        assert env is not None
        assert "RCX_AGENT_BUS_DIR" not in env
        assert self._PAGER_ENV not in env
        assert env.get("PATH") == os.environ.get("PATH")
        assert env == commit_mod._commit_validation_env()  # ANTICHEAT_OK: Step 11 regression
        # The short-circuit surfaces as the pre-push step error (env was captured
        # on the real production path), and the parent env is not mutated.
        assert pipeline_result["step"] == "run_pre_push_script"
        assert os.environ.get("RCX_AGENT_BUS_DIR") == self._MALICIOUS_LANE
        assert os.environ.get(self._PAGER_ENV) == "codex"

    def test_run_pytest_on_files_builds_hermetic_validation_env(self, tmp_path, monkeypatch):
        # Production call sites #3/#4: the Step 8b pre-commit targeted pytest gate
        # and the Step 15 bot-remediation targeted pytest gate both route through
        # _run_pytest_on_files, which built its child env from a raw ``**os.environ``
        # and therefore leaked a namespaced live lane AND the live pager/role
        # overrides into the repository's own tests. Lock the hermetic child env.
        import subprocess

        self._seed_live_overrides(monkeypatch)
        monkeypatch.setenv("RCX_RECOVERY_UPSTREAM_CONNECTIVITY_RETRY", "1")
        monkeypatch.setenv("RCX_SKIP_RECEIPT_CHECK", "1")
        monkeypatch.setenv("UNRELATED_VALIDATION_VAR", "keep-me")

        captured: dict[str, object] = {}
        real_run = subprocess.run

        def intercept(args, **kwargs):
            if any("pytest" in str(a) for a in args):
                captured["env"] = kwargs.get("env")
                # Do not actually spawn pytest; a clean pass is enough to reach
                # the env-construction assertions.
                return subprocess.CompletedProcess(list(args), 0, stdout="1 passed", stderr="")
            return real_run(args, **kwargs)

        with patch.object(commit_mod.subprocess, "run", side_effect=intercept):
            res = commit_mod._run_pytest_on_files(  # ANTICHEAT_OK: validation-child override isolation regression
                tmp_path, ["mu/tests/tools/test_agent_bus_namespacing.py"]
            )

        assert res["passed"] is True
        assert "env" in captured, "_run_pytest_on_files never invoked pytest"
        env = captured["env"]
        assert env is not None
        # The reproduced leak is closed: no live lane bus and no live pager/role
        # override reaches the child.
        assert "RCX_AGENT_BUS_DIR" not in env
        assert self._PAGER_ENV not in env
        for key in commit_mod._commit_validation_protected_env_keys():  # ANTICHEAT_OK
            assert key not in env
        # The pytest determinism pins survive (applied BEFORE the protected-key removal).
        assert env.get("PYTHONHASHSEED") == "0"
        assert env.get("RCX_CI") == "1"
        assert env.get("HYPOTHESIS_PROFILE") == "ci_fast"
        # Unrelated parent env preserved byte-for-byte; RCX_SKIP_* sanitized.
        assert env.get("RCX_RECOVERY_UPSTREAM_CONNECTIVITY_RETRY") == "1"
        assert env.get("UNRELATED_VALIDATION_VAR") == "keep-me"
        assert env.get("PATH") == os.environ.get("PATH")
        assert not any(k.startswith("RCX_SKIP_") for k in env)
        # It IS exactly the commit-owned validation construction carrying the pins.
        assert env == commit_mod._commit_validation_env(  # ANTICHEAT_OK: validation-child override isolation regression
            {"PYTHONHASHSEED": "0", "RCX_CI": "1", "HYPOTHESIS_PROFILE": "ci_fast"}
        )
        # Building the child env never mutates the parent os.environ.
        assert os.environ.get("RCX_AGENT_BUS_DIR") == self._MALICIOUS_LANE
        assert os.environ.get(self._PAGER_ENV) == "codex"
        assert os.environ.get("RCX_SKIP_RECEIPT_CHECK") == "1"

    def test_private_attr_gate_builds_hermetic_validation_env(self, tmp_path, monkeypatch):
        # Production call sites #5/#6: the ordinary Step 8c and bot-remediation
        # Step 15 anti-cheat gates both launch these two checker children through
        # run_private_attr_test_gate. Lock both launches to the shared boundary.
        repo = _setup_repo(tmp_path)
        linters = repo / "mu" / "tools" / "checks" / "linters"
        linters.mkdir(parents=True, exist_ok=True)
        for checker_name in (
            "check_private_attr_access.py",
            "check_underscore_imports.py",
        ):
            (linters / checker_name).write_text("# checker\n", encoding="utf-8")
        selected_test = repo / "mu" / "tests" / "tools" / "test_selected_clean.py"
        selected_test.parent.mkdir(parents=True, exist_ok=True)
        selected_test.write_text("def test_selected_clean(): pass\n", encoding="utf-8")

        inherited = {
            self._BRIDGE_TURN_TIMEOUT_OVERRIDE_ENV: "901",
            self._BRIDGE_TURN_TIMEOUT_KEY_ENV: "phase_b",
        }
        for key, value in inherited.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("RCX_RECOVERY_UPSTREAM_CONNECTIVITY_RETRY", "1")
        monkeypatch.setenv("UNRELATED_VALIDATION_VAR", "keep-me")
        parent_before = dict(os.environ)
        expected = commit_mod._commit_validation_env()  # ANTICHEAT_OK: Step 8c/15 validation-child containment regression

        captured_envs: list[dict[str, str] | None] = []

        def intercept(args, **kwargs):
            captured_envs.append(kwargs.get("env"))
            return commit_mod.subprocess.CompletedProcess(
                list(args), 0, stdout="", stderr=""
            )

        with patch.object(commit_mod.subprocess, "run", side_effect=intercept):
            result = commit_mod.run_private_attr_test_gate(
                repo,
                ["mu/tests/tools/test_selected_clean.py"],
            )

        assert result["passed"] is True
        assert result["skipped"] is False
        assert len(captured_envs) == 2, "both anti-cheat checker children must run"
        for env in captured_envs:
            assert env == expected
            for key in self._BRIDGE_TURN_TIMEOUT_ENVS:
                assert key not in env
            assert env.get("RCX_RECOVERY_UPSTREAM_CONNECTIVITY_RETRY") == "1"
            assert env.get("UNRELATED_VALIDATION_VAR") == "keep-me"
        assert dict(os.environ) == parent_before

    def test_pager_receipt_test_passes_through_validation_child_under_live_pager_override(
        self, monkeypatch
    ):
        # THE acceptance regression: run the exact pager receipt test through the
        # real commit-owned validation path (_run_pytest_on_files) while the parent
        # exports a live namespaced lane AND RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE.
        # Loud failure (never a silent skip) if the reproduced target ever moves.
        assert (
            REPO_ROOT / "mu" / "tests" / "tools" / "test_agent_bus_namespacing.py"
        ).exists(), "reproduced bus-namespacing test file is missing"

        self._seed_live_overrides(monkeypatch)
        # Make the leaked-route reproduction a DETERMINISTIC negative control: pin
        # the codex transport unconfigured so the reproduction's outcome no longer
        # depends on whether a live codex app-server happens to be listening on this
        # machine (the WI-1 finding recorded in the class docstring).
        self._pin_codex_transport_unconfigured(monkeypatch)
        # The pin MUST be unprotected, so the leaky child below and the hermetic
        # validation child both inherit it and the ONLY variable that differs is the
        # leaked route override. If either pin key ever becomes a protected key this
        # pairing stops being a controlled experiment -- fail loudly, do not drift.
        protected = commit_mod._commit_validation_protected_env_keys()  # ANTICHEAT_OK: counter-proof control-variable symmetry
        assert self._CODEX_URL_ENV not in protected, (
            f"{self._CODEX_URL_ENV} became a protected validation-child key: the "
            "counter-proof's two legs no longer share the codex-transport pin, so "
            "the leaked route is no longer the only differing variable"
        )
        assert self._CODEX_THREAD_ENV not in protected, (
            f"{self._CODEX_THREAD_ENV} became a protected validation-child key: the "
            "counter-proof's two legs no longer share the codex-transport pin"
        )
        assert commit_mod._commit_validation_env().get(self._CODEX_URL_ENV) == (  # ANTICHEAT_OK: counter-proof control-variable symmetry
            self._CODEX_TRANSPORT_UNCONFIGURED
        ), "the validation child did not inherit the codex-transport pin"

        # Counter-proof that the leak is real RIGHT NOW: the SAME test run with the
        # UNsanitized parent env (the pre-fix construction) fails because the leaked
        # ``codex`` route sends the page down the codex delivery leg, which cannot
        # acknowledge under the pin, so delivery-receipt persistence never happens.
        import subprocess

        leaky = subprocess.run(
            [
                sys.executable, "-m", "pytest", "-x", "--tb=short",
                "--import-mode=importlib", "-p", "no:cacheprovider", self._PAGER_TEST,
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONHASHSEED": "0", "RCX_CI": "1", "HYPOTHESIS_PROFILE": "ci_fast"},
        )
        leaky_output = (leaky.stdout or "") + (leaky.stderr or "")
        assert leaky.returncode != 0, (
            "pre-fix reproduction is vacuous: the pager test did not fail under a "
            "leaked RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE=codex\n"
            + leaky_output[-2000:]
        )
        # ...and it failed for THE reproduced reason. Without this, an unrelated
        # collection/import error would satisfy the counter-proof vacuously in the
        # opposite direction. The premises behind these two strings are pinned by
        # ``test_pager_route_override_counter_proof_premises_stay_pinned``.
        assert f"FAILED {self._PAGER_TEST}" in leaky_output, (
            "the leaked-route reproduction did not fail on the reproduced target "
            "itself (an unrelated error would satisfy the counter-proof vacuously)\n"
            + leaky_output[-2000:]
        )
        assert "pipeline_agent_delivery_receipts.jsonl" in leaky_output, (
            "the leaked-route reproduction failed for the WRONG reason: the expected "
            "failure is the missing delivery receipt under the codex route\n"
            + leaky_output[-2000:]
        )

        # The fix: the commit-owned validation child strips the override and the
        # exact pager receipt test resolves its temporary .agent_bus / config route.
        res = commit_mod._run_pytest_on_files(REPO_ROOT, [self._PAGER_TEST])  # ANTICHEAT_OK: real e2e validation-child isolation
        combined = (res.get("stdout") or "") + (res.get("stderr") or "")
        assert res["passed"] is True, combined[-2000:]
        assert res["exit_code"] == 0, combined[-2000:]
        assert self._MALICIOUS_LANE not in combined
        # The hermetic child never mutates the parent overrides.
        assert os.environ.get("RCX_AGENT_BUS_DIR") == self._MALICIOUS_LANE
        assert os.environ.get(self._PAGER_ENV) == "codex"

    def test_pager_route_override_counter_proof_premises_stay_pinned(
        self, tmp_path, monkeypatch
    ):
        """Pin every premise the counter-proof above stands on.

        The counter-proof in
        ``test_pager_receipt_test_passes_through_validation_child_under_live_pager_override``
        is only a real gate while four premises hold. Each one previously drifted
        (or could drift) SILENTLY, turning ``assert leaky.returncode != 0`` into a
        vacuous assertion that no longer proved the leak. This test asserts each
        premise directly and hermetically -- no pytest subprocess, no network, no
        live codex -- so a future drift fails loudly and names its own cause instead
        of quietly hollowing out the counter-proof.
        """
        # PREMISE 1 -- the leak vector still exists: the pager resolves the env route
        # override AHEAD of the repository's own configured route, and commit_executor
        # names the SAME canonical key it sanitizes.
        assert commit_mod._PAGER_ROUTE_OVERRIDE_ENV == pager_mod.PAGER_ROUTE_OVERRIDE_ENV, (  # ANTICHEAT_OK: canonical route-override key parity
            "commit_executor's pager route-override literal drifted from the pager's "
            "canonical key: the counter-proof would seed a key nothing reads"
        )
        repo = self._write_pager_repo(tmp_path, "resolve")
        config = {"pipeline_agent_pager": {"enabled": True, "route": "notify-only"}}
        monkeypatch.delenv(self._PAGER_ENV, raising=False)
        assert pager_mod._resolve_route(repo, config, None) == "notify-only"  # ANTICHEAT_OK: route resolution is the leak vector under test
        monkeypatch.setenv(self._PAGER_ENV, "codex")
        assert pager_mod._resolve_route(repo, config, None) == "codex", (  # ANTICHEAT_OK: route resolution is the leak vector under test
            "the pager no longer honours the env route override ahead of the "
            "configured route: the leak the counter-proof reproduces is gone, so the "
            "counter-proof must be removed rather than left unsatisfiable"
        )

        # PREMISE 2 -- the negative control is HERMETIC: the codex-transport pin is
        # rejected in-process, and that rejection is not classified as a transport
        # outage, so the ``codex exec resume`` fallback (which would spawn the real
        # ``codex`` binary and reintroduce ambient machine state) can never fire.
        self._pin_codex_transport_unconfigured(monkeypatch)
        with pytest.raises(pager_mod.PipelineAgentPagerError) as excinfo:
            pager_mod._codex_app_server_url()  # ANTICHEAT_OK: transport-pin rejection is the hermeticity premise
        assert not pager_mod._is_codex_transport_unavailable(str(excinfo.value)), (  # ANTICHEAT_OK: fallback-unreachability premise
            "the codex-transport pin is now classified as a transport outage, so the "
            "exec-resume fallback can spawn a real codex binary: the counter-proof's "
            "negative control is no longer hermetic"
        )

        # PREMISE 3 -- delivery-receipt persistence is still ROUTE-SENSITIVE, which is
        # the whole discriminator. Under the leaked route the codex leg cannot ack, so
        # events/state/lock persist but the delivery receipt does NOT; with the override
        # stripped the configured notify-only route acks and the receipt IS written.
        leaked_repo = self._write_pager_repo(tmp_path, "leaked")
        leaked = self._emit_pager_event(leaked_repo)
        leaked_obs = leaked_repo / ".agent_bus-test" / "observability"
        assert leaked["route"] == "codex"
        assert [a["target"] for a in leaked["attempted"]] == ["codex"]
        assert leaked["attempted"][0]["acknowledged"] is False
        assert (leaked_obs / "pipeline_agent_events.jsonl").exists()
        assert (leaked_obs / "pipeline_agent_pager_state.json").exists()
        assert (leaked_obs / "pipeline_agent_pager.lock").exists()
        assert not (leaked_obs / "pipeline_agent_delivery_receipts.jsonl").exists(), (
            "the leaked codex route now persists a delivery receipt anyway: the "
            "reproduced target can no longer fail under the leak, so the "
            "counter-proof is vacuous and must be re-pointed or removed"
        )

        monkeypatch.delenv(self._PAGER_ENV, raising=False)
        clean_repo = self._write_pager_repo(tmp_path, "clean")
        clean = self._emit_pager_event(clean_repo)
        clean_obs = clean_repo / ".agent_bus-test" / "observability"
        assert clean["route"] == "notify-only"
        assert [a["target"] for a in clean["attempted"]] == ["notify-only"]
        assert clean["attempted"][0]["acknowledged"] is True
        assert (clean_obs / "pipeline_agent_delivery_receipts.jsonl").exists(), (
            "the configured notify-only route no longer persists a delivery receipt: "
            "the counter-proof's PASSING leg would fail for a reason unrelated to "
            "override stripping"
        )

        # PREMISE 4 -- the pin keys stay unprotected, so both counter-proof legs
        # inherit the SAME codex transport and the leaked route override remains the
        # only differing variable between them.
        protected = commit_mod._commit_validation_protected_env_keys()  # ANTICHEAT_OK: counter-proof control-variable symmetry
        assert self._CODEX_URL_ENV not in protected
        assert self._CODEX_THREAD_ENV not in protected
        assert self._PAGER_ENV in protected, (
            "the route override is no longer sanitized from validation children: the "
            "counter-proof's passing leg proves nothing"
        )


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


class TestDraftPRReadyBeforeMerge:
    def _run_step15_path(
        self,
        tmp_path,
        *,
        initial_is_draft: bool,
        post_ci_is_draft: bool | None = None,
        ready_fails: bool = False,
        remains_draft_after_ready: bool = False,
        omit_draft_state: bool = False,
        omit_head_ref_name: bool = False,
    ):
        import subprocess

        repo = tmp_path / "repo"
        repo.mkdir()
        merge_script = repo / "mu" / "tools" / "hooks" / "merge_pr.sh"
        merge_script.parent.mkdir(parents=True, exist_ok=True)
        merge_script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        target_branch = "jabramsja/draft-ready-test"
        head_sha = "a" * 40
        events: list[str] = []
        commands: list[list[str]] = []
        query_count = 0

        def pr_payload(*, is_draft: bool) -> dict:
            payload = {
                "headRefOid": head_sha,
                "headRefName": target_branch,
                "isDraft": is_draft,
                "reviewDecision": "APPROVED",
                "latestReviews": {"nodes": [{
                    "author": {"login": commit_mod.BOT_REVIEW_LOGIN},
                    "body": "",
                    "state": "APPROVED",
                    "submittedAt": "2026-07-01T00:00:00Z",
                    "commit": {"oid": head_sha},
                }]},
                "reviewThreads": {"nodes": []},
                "comments": {"nodes": []},
            }
            if omit_draft_state:
                payload.pop("isDraft")
            if omit_head_ref_name:
                payload.pop("headRefName")
            return payload

        def fake_query(*args, **kwargs):
            nonlocal query_count
            query_count += 1
            if query_count == 1:
                return pr_payload(is_draft=initial_is_draft)
            if "ready" not in events:
                return pr_payload(
                    is_draft=(
                        initial_is_draft
                        if post_ci_is_draft is None
                        else post_ci_is_draft
                    )
                )
            return pr_payload(is_draft=remains_draft_after_ready)

        def fake_wait_for_ci(*args, **kwargs):
            events.append("pre_merge_ci")
            return None

        def completed(cmd, *, stdout="", stderr="", returncode=0):
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

        def fake_run(cmd, **kwargs):
            command = list(cmd)
            commands.append(command)
            if command == ["git", "rev-parse", "HEAD"]:
                return completed(command, stdout=head_sha + "\n")
            if command == ["gh", "pr", "ready", "1189"]:
                events.append("ready")
                if ready_fails:
                    raise subprocess.CalledProcessError(
                        1,
                        command,
                        output="",
                        stderr="ready transition rejected",
                    )
                return completed(command)
            if command == ["bash", str(merge_script), "1189", "--sweep"]:
                events.append("merge")
                return completed(command)
            if command[:2] == ["git", "fetch"]:
                return completed(command)
            if command[:2] == ["git", "status"]:
                return completed(command)
            if command[:2] == ["git", "merge"]:
                return completed(command)
            raise AssertionError(f"unexpected command: {command}")

        result = {
            "status": "success",
            "steps_completed": [
                "run_pre_push_script",
                "git_push",
                "ensure_pr",
                "wait_ci",
            ],
            "pr_number": "1189",
        }
        with patch.object(commit_mod, "_parse_origin_owner_repo", return_value=("owner", "repo")), \
             patch.object(commit_mod, "_query_pr_review_state", side_effect=fake_query), \
             patch.object(commit_mod, "_wait_for_pr_ci", side_effect=fake_wait_for_ci), \
             patch.object(
                 commit_mod,
                 "_try_auto_resolve_pr_conflict",
                 return_value={"resolved": True, "action": "no_action"},
             ), \
             patch.object(commit_mod, "_resolve_post_merge_verify_root", return_value=repo), \
             patch.object(commit_mod, "_sync_primary_worktree_to_base", return_value={"status": "skipped"}), \
             patch.object(commit_mod, "_refresh_post_merge_package_for_next_open_queue"), \
             patch.object(commit_mod, "_post_merge_cleanup", return_value={"status": "skipped"}), \
             patch.object(commit_mod, "_clear_continuation_record"), \
             patch.object(commit_mod, "_run", side_effect=fake_run):
            outcome = commit_mod._run_post_commit_pipeline(  # ANTICHEAT_OK: Step 15 draft PR readiness regression
                handoff={"wave_id": "draft-ready-test"},
                repo_root=repo,
                result=result,
                target_branch=target_branch,
                base_branch="dev",
                continuation_path=repo / ".agent_bus" / "executors" / "commit_executor_draft-ready-test.json",
                log=lambda _msg: None,
            )

        return outcome, events, commands, query_count

    def test_draft_pr_is_marked_ready_after_ci_and_before_merge(self, tmp_path):
        outcome, events, commands, query_count = self._run_step15_path(
            tmp_path,
            initial_is_draft=True,
        )

        assert outcome["status"] == "success", outcome
        assert "ensure_review_clear_and_merge" in outcome["steps_completed"]
        assert ["gh", "pr", "ready", "1189"] in commands
        assert events.index("pre_merge_ci") < events.index("ready") < events.index("merge")
        assert query_count == 3

    def test_pr_that_becomes_draft_during_pre_merge_ci_is_readied_before_merge(self, tmp_path):
        outcome, events, commands, query_count = self._run_step15_path(
            tmp_path,
            initial_is_draft=False,
            post_ci_is_draft=True,
        )

        assert outcome["status"] == "success", outcome
        assert ["gh", "pr", "ready", "1189"] in commands
        assert events.index("pre_merge_ci") < events.index("ready") < events.index("merge")
        assert query_count == 3

    def test_non_draft_pr_merges_without_ready_transition(self, tmp_path):
        outcome, events, commands, query_count = self._run_step15_path(
            tmp_path,
            initial_is_draft=False,
        )

        assert outcome["status"] == "success", outcome
        assert ["gh", "pr", "ready", "1189"] not in commands
        assert events == ["pre_merge_ci", "merge"]
        assert query_count == 2

    def test_legacy_review_payload_without_draft_metadata_skips_ready_transition(self, tmp_path):
        outcome, events, commands, query_count = self._run_step15_path(
            tmp_path,
            initial_is_draft=False,
            omit_draft_state=True,
            omit_head_ref_name=True,
        )

        assert outcome["status"] == "success", outcome
        assert ["gh", "pr", "ready", "1189"] not in commands
        assert events == ["pre_merge_ci", "merge"]
        assert query_count == 2

    def test_ready_transition_failure_fails_before_merge_pr_script(self, tmp_path):
        outcome, events, commands, query_count = self._run_step15_path(
            tmp_path,
            initial_is_draft=True,
            ready_fails=True,
            remains_draft_after_ready=True,
        )

        assert outcome["status"] == "error"
        assert outcome["step"] == "ensure_review_clear_and_merge"
        assert outcome["failure_class"] == "draft_pr_ready_failed"
        assert "ready transition rejected" in outcome["errors"][0]
        assert "merge" not in events
        assert events == ["pre_merge_ci", "ready"]
        assert query_count == 2

    def test_ready_transition_failure_classifies_for_recovery(self):
        failure_class = recovery_gate_mod.classify_failure({
            "status": "error",
            "step": "ensure_review_clear_and_merge",
            "failure_class": "draft_pr_ready_failed",
            "errors": [
                "Failed to mark draft PR #1189 ready before merge_pr.sh: "
                "ready transition rejected"
            ],
        })

        assert failure_class.value == "draft_pr_ready_failed"
        assert recovery_gate_mod.tier_for(failure_class) == 3


class TestCIPollFallbackTimeout:
    """Regression: fallback CI polling uses the configured commit CI budget.

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
        """With the configured budget, CI completing at t=350s must return True.

        The former 300s budget would have false-positive timed out before this
        transition. The configured budget must survive with headroom.
        """
        result, final_clock = self._run_fallback_with_simulated_clock(
            ci_transitions_to_success_at=350,
            runtime_cap=commit_mod.COMMIT_CI_POLL_TIMEOUT_S,
        )
        assert result is True, (
            f"Expected True (CI passed at t=350s), got {result}"
        )
        assert final_clock >= 350, (
            f"Simulated clock should have advanced past 350s, got {final_clock}s"
        )
        assert final_clock < commit_mod.COMMIT_CI_POLL_TIMEOUT_S, (
            "Simulated clock should not have hit the configured cap, "
            f"got {final_clock}s"
        )

    def test_ci_poll_fallback_still_times_out_at_new_budget(self):
        """With the configured budget, genuinely stalled CI must still return False.

        Guards against the bump making the timeout unconditionally permissive —
        a CI that never completes must still hit the budget ceiling.
        """
        result, final_clock = self._run_fallback_with_simulated_clock(
            ci_transitions_to_success_at=None,
            runtime_cap=commit_mod.COMMIT_CI_POLL_TIMEOUT_S,
        )
        assert result is False, (
            "Expected False (timed out at configured budget), "
            f"got {result}"
        )
        assert final_clock >= commit_mod.COMMIT_CI_POLL_TIMEOUT_S, (
            "Simulated clock should have exhausted the configured budget, "
            f"got {final_clock}s"
        )


class TestRequiredCIGreenGuard:
    @staticmethod
    def _successful_rollup(names):
        return [
            {
                "name": name,
                "workflowName": "CI" if name == "test" else "rcx-green-gate",
                "conclusion": "SUCCESS",
            }
            for name in names
        ]

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

    def test_wait_for_pr_ci_rejects_branch_protection_subset_check_surface(self, tmp_path):
        import subprocess

        subset_rollup = self._successful_rollup(["test", "green-gate"])

        def completed(cmd, *, stdout="", stderr="", returncode=0):
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

        def fake_run(cmd, **kwargs):
            if cmd == ["gh", "pr", "checks", "1030", "--watch", "--required"]:
                return completed(cmd)
            if cmd == ["gh", "pr", "view", "1030", "--json", "statusCheckRollup"]:
                return completed(
                    cmd,
                    stdout=json.dumps({"statusCheckRollup": subset_rollup}),
                )
            raise AssertionError(f"unexpected command: {cmd}")

        result = {
            "commit_sha": "a" * 40,
            "handoff_sha": "handoff-sha",
            "receipt_decision": "COMMIT_GO",
            "steps_completed": ["git_commit"],
        }

        with patch.object(commit_mod, "_wait_for_required_checks_to_register", return_value=None), \
             patch.object(commit_mod, "_wait_for_required_checks_to_pass", return_value=True), \
             patch.object(commit_mod, "_run", side_effect=fake_run), \
             patch.object(commit_mod, "COMMIT_CI_VERIFY_TIMEOUT_S", 0):
            response = commit_mod._wait_for_pr_ci(  # ANTICHEAT_OK: locks full PR status surface before wait_ci completion
                tmp_path,
                pr_number="1030",
                result=result,
                continuation_path=tmp_path / "continuation.json",
                target_branch="jabramsja/test",
                log=lambda _msg: None,
            )

        assert response is not None
        assert response["status"] == "error"
        assert response["step"] == "wait_ci"
        assert response["failure_class"] == "unknown_error"
        assert "wait_ci" not in result["steps_completed"]
        surface = response["ci_check_surface"]
        assert surface["missing_expected_checks"] == [
            "engine-run-schema",
            "orbit-dot",
            "orbit-index",
            "orbit-provenance",
            "orbit-svg",
        ]
        assert "missing expected check(s): engine-run-schema" in response["errors"][0]

    def test_wait_for_pr_ci_accepts_completed_seven_check_green_surface(self, tmp_path):
        import subprocess

        full_rollup = self._successful_rollup(commit_mod.EXPECTED_PR_CHECK_SURFACE)

        def completed(cmd, *, stdout="", stderr="", returncode=0):
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

        def fake_run(cmd, **kwargs):
            if cmd == ["gh", "pr", "checks", "1030", "--watch", "--required"]:
                return completed(cmd)
            if cmd == ["gh", "pr", "view", "1030", "--json", "statusCheckRollup"]:
                return completed(
                    cmd,
                    stdout=json.dumps({"statusCheckRollup": full_rollup}),
                )
            raise AssertionError(f"unexpected command: {cmd}")

        result = {
            "commit_sha": "a" * 40,
            "handoff_sha": "handoff-sha",
            "receipt_decision": "COMMIT_GO",
            "steps_completed": ["git_commit"],
        }

        with patch.object(commit_mod, "_wait_for_required_checks_to_register", return_value=None), \
             patch.object(commit_mod, "_wait_for_required_checks_to_pass", return_value=True), \
             patch.object(commit_mod, "_run", side_effect=fake_run), \
             patch.object(commit_mod, "COMMIT_CI_VERIFY_TIMEOUT_S", 0):
            response = commit_mod._wait_for_pr_ci(  # ANTICHEAT_OK: locks seven-check PR status surface acceptance
                tmp_path,
                pr_number="1030",
                result=result,
                continuation_path=tmp_path / "continuation.json",
                target_branch="jabramsja/test",
                log=lambda _msg: None,
            )

        assert response is None
        assert "wait_ci" in result["steps_completed"]

    def test_wait_for_pr_ci_rejects_watch_success_until_required_checks_green(self, tmp_path):
        import subprocess

        watch_timeouts = []

        def completed(cmd, *, stdout="", stderr="", returncode=0):
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

        def fake_run(cmd, **kwargs):
            if cmd == ["gh", "pr", "checks", "844", "--required"]:
                return completed(cmd, stdout="test\tpending\n", returncode=8)
            if cmd == ["gh", "pr", "checks", "844", "--watch", "--required"]:
                watch_timeouts.append(kwargs.get("timeout"))
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
        assert watch_timeouts == [commit_mod.COMMIT_CI_WATCH_TIMEOUT_S]

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
