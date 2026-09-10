"""Focused evidence and routing tests for Apply-R2 no-replay finalization."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from mu.tests.tools.module_loader import load_module


REPO_ROOT = Path(__file__).resolve().parents[3]
EXECUTOR_DIR = REPO_ROOT / "mu" / "tools" / "executors"
disposition = load_module(
    "pr_disposition_executor",
    EXECUTOR_DIR / "pr_disposition_executor.py",
)
commit = load_module(
    "commit_executor_no_replay_finalization_test",
    EXECUTOR_DIR / "commit_executor.py",
)
FINALIZATION_INDICATOR_RELATIVE_PATH = Path(
    "reports/l4_wave_indicators/"
    f"{disposition.TERMINAL_SWEEP_WAVE_ID}.json"
)


def _finalization_candidate_paths() -> set[Path]:
    return {
        disposition.TERMINAL_SWEEP_AUTHORITY_RELATIVE_PATH,
        disposition.TERMINAL_SWEEP_FINALIZATION_PACKET_RELATIVE_PATH,
        FINALIZATION_INDICATOR_RELATIVE_PATH,
        *(
            relative_path
            for _kind, relative_path, _digest in (
                disposition.TERMINAL_SWEEP_COPIED_ARTIFACTS
            )
        ),
    }


def _candidate_fixture(tmp_path: Path) -> Path:
    candidate = tmp_path / "candidate"
    paths = {
        disposition.MANIFEST_RELATIVE_PATH,
        *_finalization_candidate_paths(),
    }
    for relative_path in paths:
        source = REPO_ROOT / relative_path
        target = candidate / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return candidate


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _commit_pipeline_fixture(tmp_path: Path) -> tuple[Path, dict]:
    candidate = _candidate_fixture(tmp_path)
    collector = (
        candidate / "mu" / "tools" / "metrics" / "collect_l4_wave_indicators.py"
    )
    collector.parent.mkdir(parents=True, exist_ok=True)
    collector.write_text(
        "import json, pathlib, sys\n"
        "output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
        "output.parent.mkdir(parents=True, exist_ok=True)\n"
        "output.write_text(json.dumps({'wave_id': sys.argv[sys.argv.index('--wave-id') + 1]}) + '\\n')\n",
        encoding="utf-8",
    )

    target_branch = f"jabramsja/{disposition.TERMINAL_SWEEP_WAVE_ID}"
    _run_git(candidate, "init")
    _run_git(candidate, "checkout", "-b", target_branch)
    _run_git(candidate, "config", "user.name", "test")
    _run_git(candidate, "config", "user.email", "test@example.com")
    _run_git(
        candidate,
        "add",
        "--",
        str(disposition.MANIFEST_RELATIVE_PATH),
        str(collector.relative_to(candidate)),
    )
    _run_git(candidate, "commit", "-m", "test baseline")

    tracker_note = (
        "- Tracker sync note (2026-09-10, "
        f"{disposition.TERMINAL_SWEEP_WAVE_ID}): focused no-replay test."
    )
    (candidate / "TASKS.md").write_text(
        f"## Ra\n\n{tracker_note}\n\n---\n",
        encoding="utf-8",
    )
    phase_b_receipt = candidate / ".agent_bus" / "meta" / "pre_commit_receipt.json"
    phase_b_receipt.parent.mkdir(parents=True, exist_ok=True)
    phase_b_receipt.write_text(
        json.dumps({"decision": "COMMIT_GO"}) + "\n",
        encoding="utf-8",
    )
    supervisor_receipt = candidate / ".scratch" / "supervisor_receipt.json"
    supervisor_receipt.parent.mkdir(parents=True, exist_ok=True)
    supervisor_receipt.write_text(
        json.dumps({"decision": "COMMIT_GO"}) + "\n",
        encoding="utf-8",
    )

    files_to_stage = sorted(
        ["TASKS.md", *(str(path) for path in _finalization_candidate_paths())]
    )
    handoff = {
        "base_branch": "dev",
        "branch_prefix": "jabramsja",
        "caller": "phase_b",
        "commit_message": "test: no-replay finalization",
        "files_to_stage": files_to_stage,
        "fixes_implemented": ["prove mismatch stops before commit"],
        "force_add_files": [],
        "pre_commit_receipt_path": str(phase_b_receipt.relative_to(candidate)),
        "pr_body": "test",
        "pr_title": "test",
        "scope_items": files_to_stage,
        "target_branch": target_branch,
        "target_gate_id": "G8",
        "task_id": "[PR-DISPOSITION-R2-NO-REPLAY-FINALIZATION]",
        "tracker_note_text": tracker_note,
        "wave_class": "L4_ENABLER",
        "wave_id": disposition.TERMINAL_SWEEP_WAVE_ID,
    }
    handoff["_supervisor_receipt_path"] = str(
        supervisor_receipt.relative_to(candidate)
    )
    return candidate, handoff


def _patch_commit_pipeline_to_finalization_gate(
    monkeypatch,
    *,
    supervisor_receipt_path: str,
) -> None:
    monkeypatch.setattr(commit, "ensure_not_agent_review_mode", lambda *_args: None)
    monkeypatch.setattr(commit, "validate_handoff", lambda *_args, **_kwargs: (True, []))
    monkeypatch.setattr(
        commit,
        "_commit_lifecycle_pager_enabled",
        lambda *_args: False,
    )
    monkeypatch.setattr(
        commit,
        "_resolve_control_surface_founder_override_token",
        lambda *_args, **_kwargs: "",
    )
    monkeypatch.setattr(
        commit,
        "_repair_handoff_same_wave_founder_override",
        lambda handoff, _repo_root: handoff,
    )
    monkeypatch.setattr(
        commit,
        "refresh_commit_path_packet_truth",
        lambda **kwargs: (kwargs["handoff"], [], None),
    )
    monkeypatch.setattr(
        commit,
        "_restore_pending_handoff_state_for_commit_ready",
        lambda *_args, **_kwargs: {"changed": [], "errors": []},
    )
    monkeypatch.setattr(
        commit,
        "_maybe_autobump_growth_cap_for_founder_override",
        lambda *_args, **_kwargs: {"bumped": False},
    )
    monkeypatch.setattr(
        commit,
        "_range_diff_paths_for_base",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        commit,
        "_collect_commit_fenced_dirty_files",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        commit,
        "_persist_phase_b_handoff_for_commit_path",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        commit,
        "_safe_emit_pre_commit_supervisor_lifecycle_event",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        commit,
        "_emit_commit_ready_event",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        commit,
        "run_private_attr_test_gate",
        lambda *_args, **_kwargs: {"passed": True, "skipped": True},
    )
    monkeypatch.setattr(
        commit,
        "_maybe_demote_completed_handoff_state_for_commit_retry",
        lambda **_kwargs: None,
    )

    def load_supervisor(_repo_root: Path):
        def run_supervisor(*_args, **_kwargs):
            return SimpleNamespace(
                decision="COMMIT_GO",
                receipt_path=supervisor_receipt_path,
                status="success",
                summary="focused test supervisor",
            )

        return run_supervisor, RuntimeError

    monkeypatch.setattr(commit, "_load_repo_meta_bridge_client", load_supervisor)


def _run_commit_pipeline_expect_evidence_hold(
    monkeypatch,
    candidate: Path,
    handoff: dict,
) -> tuple[dict, dict[str, int]]:
    supervisor_receipt_path = handoff.pop("_supervisor_receipt_path")
    _patch_commit_pipeline_to_finalization_gate(
        monkeypatch,
        supervisor_receipt_path=supervisor_receipt_path,
    )
    calls = {
        "apply": 0,
        "commit": 0,
        "post_commit": 0,
        "publish": 0,
        "validate": 0,
    }
    real_validate = disposition.validate_no_replay_finalization_candidate

    def validate(*args, **kwargs):
        calls["validate"] += 1
        return real_validate(*args, **kwargs)

    def forbidden_apply(*_args, **_kwargs):
        calls["apply"] += 1
        raise AssertionError("Apply must never run during no-replay finalization")

    def forbidden_commit(*_args, **_kwargs):
        calls["commit"] += 1
        raise AssertionError("commit must not run after finalization evidence HOLD")

    def forbidden_publish(*_args, **_kwargs):
        calls["publish"] += 1
        raise AssertionError("successor must not publish after evidence HOLD")

    def forbidden_post_commit(*_args, **_kwargs):
        calls["post_commit"] += 1
        raise AssertionError("post-commit flow must not run after evidence HOLD")

    monkeypatch.setattr(
        disposition,
        "validate_no_replay_finalization_candidate",
        validate,
    )
    monkeypatch.setattr(disposition, "apply_dispositions", forbidden_apply)
    monkeypatch.setattr(
        commit,
        "_load_pr_disposition_executor_module",
        lambda: disposition,
    )
    monkeypatch.setattr(
        commit,
        "_run_git_commit_with_self_cleared_index_lock_retry",
        forbidden_commit,
    )
    monkeypatch.setattr(commit, "_run_post_commit_pipeline", forbidden_post_commit)
    monkeypatch.setattr(
        commit,
        "_refresh_post_merge_package_for_next_open_queue",
        forbidden_publish,
    )

    return commit.run_commit_pipeline(handoff, repo_root=candidate), calls


def _seal_authority(payload: dict) -> dict:
    sealed = copy.deepcopy(payload)
    sealed.pop("manifest_sha256", None)
    canonical = json.dumps(
        sealed,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    sealed["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    return sealed


def _write_authority(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_only_exact_finalization_wave_uses_terminal_sweep() -> None:
    assert disposition.requires_terminal_sweep(disposition.TERMINAL_SWEEP_WAVE_ID)
    assert not disposition.requires_terminal_sweep(
        disposition.TERMINAL_SWEEP_SOURCE_WAVE_ID
    )
    assert not disposition.requires_terminal_sweep(
        disposition.TERMINAL_SWEEP_WAVE_ID + "-replay"
    )


def test_finalization_evidence_passes_with_distinct_fresh_digest(
    tmp_path: Path,
) -> None:
    candidate = _candidate_fixture(tmp_path)
    fresh_candidate_sha = "f" * 64
    result = disposition.validate_no_replay_finalization_candidate(
        candidate,
        wave_id=disposition.TERMINAL_SWEEP_WAVE_ID,
        candidate_sha256=fresh_candidate_sha,
    )

    assert result["decision"] == "PASS", result["errors"]
    assert result["errors"] == []
    assert result["candidate_sha256"] == fresh_candidate_sha
    assert (
        result["source_candidate_sha256"]
        == disposition.TERMINAL_SWEEP_SOURCE_CANDIDATE_SHA256
    )
    assert result["candidate_sha256"] != result["source_candidate_sha256"]


def test_historical_source_candidate_digest_reuse_is_hold(tmp_path: Path) -> None:
    candidate = _candidate_fixture(tmp_path)
    historical_candidate_sha = (
        disposition.TERMINAL_SWEEP_SOURCE_CANDIDATE_SHA256
    )

    result = disposition.validate_no_replay_finalization_candidate(
        candidate,
        wave_id=disposition.TERMINAL_SWEEP_WAVE_ID,
        candidate_sha256=historical_candidate_sha,
    )

    assert result["decision"] == "HOLD"
    assert result["candidate_sha256"] == historical_candidate_sha
    assert result["source_candidate_sha256"] == historical_candidate_sha
    assert result["errors"] == [
        "reviewed finalization candidate SHA-256 reuses historical "
        "Apply-R2 staged-candidate SHA-256"
    ]


def test_resealed_historical_source_digest_mismatch_is_hold(tmp_path: Path) -> None:
    candidate = _candidate_fixture(tmp_path)
    authority_path = candidate / disposition.TERMINAL_SWEEP_AUTHORITY_RELATIVE_PATH
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    authority["source"]["staged_candidate_sha256"] = "0" * 64
    _write_authority(authority_path, _seal_authority(authority))

    result = disposition.validate_no_replay_finalization_candidate(
        candidate,
        wave_id=disposition.TERMINAL_SWEEP_WAVE_ID,
        candidate_sha256="f" * 64,
    )

    assert result["decision"] == "HOLD"
    assert "finalization authority manifest contract mismatch" in result["errors"]


def test_copied_byte_mismatch_holds_pipeline_before_commit_or_successor(
    tmp_path: Path,
    monkeypatch,
) -> None:
    candidate, handoff = _commit_pipeline_fixture(tmp_path)
    receipt_path = (
        candidate
        / disposition.TERMINAL_SWEEP_RECEIPTS_RELATIVE_PATH
        / "pr-1196.json"
    )
    receipt_path.write_bytes(receipt_path.read_bytes() + b" ")

    result, calls = _run_commit_pipeline_expect_evidence_hold(
        monkeypatch,
        candidate,
        handoff,
    )

    assert result["status"] == "held"
    assert result["decision"] == "HOLD"
    assert result["step"] == "validate_no_replay_finalization_evidence"
    assert any("copied artifact" in error for error in result["errors"])
    assert calls == {
        "apply": 0,
        "commit": 0,
        "post_commit": 0,
        "publish": 0,
        "validate": 1,
    }


def test_historical_digest_reuse_holds_pipeline_before_commit_or_successor(
    tmp_path: Path,
    monkeypatch,
) -> None:
    candidate, handoff = _commit_pipeline_fixture(tmp_path)
    historical_candidate_sha = (
        disposition.TERMINAL_SWEEP_SOURCE_CANDIDATE_SHA256
    )
    real_sha256 = hashlib.sha256

    def sha256_with_historical_staged_digest(raw=b""):
        if isinstance(raw, bytes) and raw.startswith(b"diff --git "):
            return SimpleNamespace(hexdigest=lambda: historical_candidate_sha)
        return real_sha256(raw)

    monkeypatch.setattr(
        commit,
        "hashlib",
        SimpleNamespace(sha256=sha256_with_historical_staged_digest),
    )

    result, calls = _run_commit_pipeline_expect_evidence_hold(
        monkeypatch,
        candidate,
        handoff,
    )

    assert result["status"] == "held"
    assert result["decision"] == "HOLD"
    assert result["step"] == "validate_no_replay_finalization_evidence"
    assert result["staged_candidate_sha256"] == historical_candidate_sha
    evidence = result["no_replay_finalization_evidence"]
    assert evidence["candidate_sha256"] == historical_candidate_sha
    assert evidence["source_candidate_sha256"] == historical_candidate_sha
    assert result["errors"] == [
        "reviewed finalization candidate SHA-256 reuses historical "
        "Apply-R2 staged-candidate SHA-256"
    ]
    assert calls == {
        "apply": 0,
        "commit": 0,
        "post_commit": 0,
        "publish": 0,
        "validate": 1,
    }


@pytest.mark.parametrize(
    ("decision", "expected_candidate"),
    [
        ("PASS", disposition.TERMINAL_FLEET_CANDIDATE),
        ("HOLD", disposition.TERMINAL_RECONCILIATION_CANDIDATE),
    ],
)
def test_post_merge_pipeline_cleans_then_routes_exactly_one_non_apply_successor(
    tmp_path: Path,
    monkeypatch,
    decision: str,
    expected_candidate: str,
) -> None:
    carrier = tmp_path / "carrier"
    carrier.mkdir()
    survivor = tmp_path / "survivor"
    survivor.mkdir()
    operator_scratch = survivor / "operator-scratch"
    operator_scratch.write_text("preserve operator dirt\n", encoding="utf-8")
    landed_evidence = survivor / "landed-finalization-evidence"
    merge_script = carrier / "mu" / "tools" / "hooks" / "merge_pr.sh"
    merge_script.parent.mkdir(parents=True)
    merge_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    target_branch = f"jabramsja/{disposition.TERMINAL_SWEEP_WAVE_ID}"
    carrier_commit_sha = "a" * 40
    merge_sha = "b" * 40
    reviewed_candidate_sha = "c" * 64
    landed_candidate_sha = reviewed_candidate_sha
    continuation = {
        "commit_sha": carrier_commit_sha,
        "pr_number": "1282",
        "receipt_decision": "COMMIT_GO",
        "staged_candidate_sha256": reviewed_candidate_sha,
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
            "run_pre_push_script",
            "git_push",
            "ensure_pr",
            "wait_ci",
        ],
    }
    handoff = {
        "base_branch": "dev",
        "branch_prefix": "jabramsja",
        "target_branch": target_branch,
        "wave_id": disposition.TERMINAL_SWEEP_WAVE_ID,
    }
    events: list[str] = []
    apply_calls = 0
    survivor_head = "d" * 40

    def forbidden_apply(*_args, **_kwargs):
        nonlocal apply_calls
        apply_calls += 1
        raise AssertionError("Apply must never run during no-replay finalization")

    def prepare(repo_root: Path, **kwargs):
        assert events == ["ff-only"]
        events.append("prepare")
        assert Path(repo_root) == survivor
        assert landed_evidence.read_text(encoding="utf-8") == "landed revision\n"
        assert kwargs["carrier_root"] == carrier
        assert kwargs["candidate_sha256"] == landed_candidate_sha
        assert kwargs["expected_candidate_sha256"] == reviewed_candidate_sha
        return {
            "receipt": {"decision": "PREPARED"},
            "receipt_path": str(tmp_path / "terminal-receipt.json"),
        }

    def cleanup(**kwargs):
        assert kwargs["cleanup_root"] == survivor
        assert kwargs["repo_root"] == carrier
        events.append("cleanup")
        return {
            "branch_deleted": True,
            "status": "success",
            "stashes_dropped": 0,
            "warnings": [],
            "worktree_removed": True,
        }

    def finalize(repo_root: Path, prepared: dict, *, cleanup_result: dict):
        assert events == ["ff-only", "prepare", "cleanup"]
        assert Path(repo_root) == survivor
        assert prepared["receipt"]["decision"] == "PREPARED"
        assert cleanup_result["status"] == "success"
        events.append("finalize")
        return {
            "binding": {
                "decision": decision,
                "merge_sha": merge_sha,
                "path": str(tmp_path / "terminal-receipt.json"),
                "sha256": "e" * 64,
                "wave_id": disposition.TERMINAL_SWEEP_WAVE_ID,
            }
        }

    def validate_authority(
        repo_root: Path,
        binding: dict,
        *,
        expected_merge_sha: str,
    ) -> dict:
        assert Path(repo_root) == survivor
        assert binding["decision"] == decision
        assert binding["merge_sha"] == expected_merge_sha == merge_sha
        return {"decision": decision, "error": "", "valid": True}

    def run_command(
        command,
        cwd=None,
        check=True,
        timeout=120,
        env=None,
        input_text=None,
    ):
        nonlocal survivor_head
        del check, timeout, env, input_text
        command = list(command)
        if command == ["git", "rev-parse", "HEAD"]:
            sha = carrier_commit_sha if Path(cwd) == carrier else survivor_head
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=f"{sha}\n",
                stderr="",
            )
        if command[:1] == ["bash"]:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command == ["git", "fetch", "origin", "dev"]:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command == ["git", "merge", "--ff-only", "origin/dev"]:
            assert events == []
            events.append("ff-only")
            survivor_head = merge_sha
            landed_evidence.write_text("landed revision\n", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command == ["git", "rev-parse", "origin/dev"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=f"{merge_sha}\n",
                stderr="",
            )
        if command == ["git", "status", "--short"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="?? operator-scratch\n",
                stderr="",
            )
        raise AssertionError(f"unexpected post-merge command: {command!r}")

    real_publish = getattr(commit, "_refresh_post_merge_package_for_next_open_queue")

    def publish(**kwargs):
        assert events == ["ff-only", "prepare", "cleanup", "finalize"]
        events.append("publish")
        return real_publish(**kwargs)

    def committed_candidate_sha(repo_root: Path, commit_sha: str) -> str:
        assert repo_root == survivor
        assert commit_sha == carrier_commit_sha
        assert survivor_head == merge_sha
        assert landed_evidence.is_file()
        return landed_candidate_sha

    monkeypatch.setattr(disposition, "apply_dispositions", forbidden_apply)
    monkeypatch.setattr(disposition, "prepare_terminal_sweep_receipt", prepare)
    monkeypatch.setattr(disposition, "finalize_terminal_sweep_receipt", finalize)
    monkeypatch.setattr(
        disposition,
        "validate_terminal_receipt_authority",
        validate_authority,
    )
    monkeypatch.setattr(
        commit,
        "_load_pr_disposition_executor_module",
        lambda: disposition,
    )
    monkeypatch.setattr(commit, "ensure_not_agent_review_mode", lambda *_args: None)
    monkeypatch.setattr(commit, "validate_handoff", lambda *_args, **_kwargs: (True, []))
    monkeypatch.setattr(
        commit,
        "_load_post_commit_continuation",
        lambda *_args, **_kwargs: dict(continuation),
    )
    monkeypatch.setattr(
        commit,
        "_commit_lifecycle_pager_enabled",
        lambda *_args: False,
    )
    monkeypatch.setattr(
        commit,
        "_maybe_demote_completed_handoff_state_for_commit_retry",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(commit, "_parse_origin_owner_repo", lambda *_args: ("o", "r"))
    monkeypatch.setattr(
        commit,
        "_query_pr_review_state",
        lambda *_args, **_kwargs: {"headRefOid": carrier_commit_sha},
    )
    monkeypatch.setattr(
        commit,
        "_has_fresh_connector_review",
        lambda *_args: True,
    )
    monkeypatch.setattr(
        commit,
        "_extract_review_findings",
        lambda *_args, **_kwargs: {"bot_findings": [], "outcome": "clear"},
    )
    monkeypatch.setattr(commit, "_wait_for_pr_ci", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        commit,
        "_ensure_current_draft_pr_ready_for_review",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        commit,
        "_resolve_post_merge_verify_root",
        lambda *_args, **_kwargs: survivor,
    )
    monkeypatch.setattr(
        commit,
        "_sync_primary_worktree_to_base",
        lambda *_args, **_kwargs: {"status": "skipped"},
    )
    monkeypatch.setattr(
        commit,
        "_committed_candidate_sha256",
        committed_candidate_sha,
    )
    monkeypatch.setattr(
        commit,
        "_dirty_worktree_paths",
        lambda repo_root: {"operator-scratch"} if repo_root == survivor else set(),
    )
    monkeypatch.setattr(commit, "_post_merge_cleanup", cleanup)
    monkeypatch.setattr(commit, "_clear_continuation_record", lambda *_args: None)
    monkeypatch.setattr(commit, "_validate_queue_commit_sha", lambda *_args: "")
    monkeypatch.setattr(
        commit,
        "_next_open_founder_ordered_queue_entry",
        lambda *_args, **_kwargs: {"wave_id": "fleet-cleanup-builder-r1-2026-09-10"},
    )
    monkeypatch.setattr(
        commit,
        "_post_merge_blocker_report_paths",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        commit,
        "_refresh_post_merge_package_for_next_open_queue",
        publish,
    )
    monkeypatch.setattr(commit, "_run", run_command)

    result = commit.run_commit_pipeline(handoff, repo_root=carrier)

    assert result["status"] == "success", result
    assert result["post_merge_terminal_decision"] == decision
    assert result["post_merge_next_wave"] == expected_candidate
    assert events == ["ff-only", "prepare", "cleanup", "finalize", "publish"]
    assert apply_calls == 0
    assert survivor_head == merge_sha
    assert operator_scratch.read_text(encoding="utf-8") == "preserve operator dirt\n"
    cleanup_index = result["steps_completed"].index("post_merge_cleanup")
    sweep_index = result["steps_completed"].index("post_merge_terminal_sweep")
    assert cleanup_index < sweep_index
    package = json.loads(
        (survivor / result["post_merge_package_path"]).read_text(encoding="utf-8")
    )
    assert package["terminal_receipt"]["decision"] == decision
    assert [item["candidate"] for item in package["next_candidates"]] == [
        expected_candidate
    ]
    assert all(
        item["candidate"] != disposition.TERMINAL_SWEEP_SOURCE_WAVE_ID
        for item in package["next_candidates"]
    )
