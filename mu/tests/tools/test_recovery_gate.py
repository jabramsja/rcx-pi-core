"""Tests for recovery_gate: failure classifier and Tier 1 auto-fix."""
from __future__ import annotations

import json, os, subprocess
from pathlib import Path
from unittest.mock import patch
import pytest

from mu.tests.tools.module_loader import load_module

_EXECUTORS_DIR = Path(__file__).resolve().parent.parent.parent / "tools" / "executors"
rg_mod = load_module("recovery_gate", _EXECUTORS_DIR / "recovery_gate.py")
FailureClass = rg_mod.FailureClass


class TestClassifyFailure:
    """classify_failure returns correct FailureClass for each signal."""

    @pytest.mark.parametrize("status", [
        "question_for_founder", "max_rounds_reached",
        "supervisor_rejected", "needs_phase_b",
    ])
    def test_terminal_statuses(self, status):
        assert rg_mod.classify_failure(
            {"status": status, "step": "x"}) == FailureClass.TERMINAL_POLICY

    def test_terminal_in_stdout_json(self):
        inner = json.dumps({"status": "supervisor_rejected"})
        assert rg_mod.classify_failure(
            {"status": "failed", "stdout": inner, "stderr": ""}) == FailureClass.TERMINAL_POLICY

    def test_stale_bridge_lock_in_stderr(self):
        assert rg_mod.classify_failure(
            {"status": "error", "stderr": "cannot acquire bridge.lock",
             "step": "bridge_loop"}) == FailureClass.STALE_BRIDGE_LOCK

    def test_stale_bridge_lock_in_stdout(self):
        assert rg_mod.classify_failure(
            {"status": "error", "stdout": "bridge.lock held", "stderr": "",
             "step": "bridge_loop"}) == FailureClass.STALE_BRIDGE_LOCK

    def test_stale_git_index_lock(self):
        assert rg_mod.classify_failure(
            {"status": "error", "stderr": "Unable to create index.lock",
             "step": "stage_files"}) == FailureClass.STALE_GIT_INDEX_LOCK

    def test_stale_executor_state(self):
        assert rg_mod.classify_failure(
            {"status": "error", "stderr": "phase_b_state.json from prior run",
             "step": "phase_b"}) == FailureClass.STALE_EXECUTOR_STATE

    def test_stale_executor_state_via_status(self):
        assert rg_mod.classify_failure(
            {"status": "stale_state", "stderr": "", "step": "phase_b"}
        ) == FailureClass.STALE_EXECUTOR_STATE

    def test_stale_continuation(self):
        assert rg_mod.classify_failure(
            {"status": "error", "stderr": "Stale continuation record",
             "step": "commit"}) == FailureClass.STALE_CONTINUATION

    def test_mixed_staging_keyword(self):
        assert rg_mod.classify_failure(
            {"status": "error", "stderr": "detected mixed staging state",
             "step": "stage_files", "stdout": ""}) == FailureClass.MIXED_STAGING

    def test_mixed_staging_porcelain(self):
        assert rg_mod.classify_failure(
            {"status": "error", "step": "stage_files",
             "stderr": "MM some_file.py", "stdout": ""}) == FailureClass.MIXED_STAGING

    def test_process_timeout(self):
        assert rg_mod.classify_failure(
            {"status": "timeout", "step": "phase_b"}) == FailureClass.PROCESS_TIMEOUT

    @pytest.mark.parametrize("code", [-9, -15, 137])
    def test_transient_kill(self, code):
        assert rg_mod.classify_failure(
            {"status": "failed", "exit_code": code, "stderr": "",
             "step": "impl"}) == FailureClass.TRANSIENT_KILL

    def test_aggregation_hang(self):
        assert rg_mod.classify_failure(
            {"status": "failed", "stderr": "bridge aggregation timeout",
             "step": "bridge_loop"}) == FailureClass.AGGREGATION_HANG

    def test_implementer_stale(self):
        assert rg_mod.classify_failure(
            {"status": "failed", "implementer_status": "stale",
             "stderr": "", "step": "impl"}) == FailureClass.IMPLEMENTER_STALE

    def test_git_staging_conflict(self):
        assert rg_mod.classify_failure(
            {"status": "error", "step": "stage_files",
             "stderr": "error: git add failed", "stdout": ""}
        ) == FailureClass.GIT_STAGING_CONFLICT

    def test_test_failure(self):
        assert rg_mod.classify_failure(
            {"status": "error", "step": "pre_commit",
             "stderr": "FAILED test_x - AssertionError"}) == FailureClass.TEST_FAILURE

    def test_agent_review_crash(self):
        assert rg_mod.classify_failure(
            {"status": "error", "step": "agent_review",
             "stderr": "agent died"}) == FailureClass.AGENT_REVIEW_CRASH

    def test_unknown_error(self):
        assert rg_mod.classify_failure(
            {"status": "error", "step": "some_step",
             "stderr": "something unexpected"}) == FailureClass.UNKNOWN_ERROR

    def test_unclassified(self):
        assert rg_mod.classify_failure({"status": "weird"}) == FailureClass.UNCLASSIFIED
        assert rg_mod.classify_failure({}) == FailureClass.UNCLASSIFIED


class TestTierMapping:
    def test_all_classes_mapped_and_tier1_tier4_correct(self):
        for fc in FailureClass:
            assert rg_mod.tier_for(fc) in (1, 2, 3, 4), f"{fc} bad tier"
        tier1 = {fc for fc in FailureClass if rg_mod.tier_for(fc) == 1}
        assert tier1 == {FailureClass.STALE_BRIDGE_LOCK, FailureClass.STALE_GIT_INDEX_LOCK,
                         FailureClass.STALE_EXECUTOR_STATE, FailureClass.STALE_CONTINUATION,
                         FailureClass.MIXED_STAGING}
        tier4 = {fc for fc in FailureClass if rg_mod.tier_for(fc) == 4}
        assert tier4 == {FailureClass.TERMINAL_POLICY, FailureClass.UNCLASSIFIED}


class TestFixStaleBridgeLock:
    def test_no_lock_file(self, tmp_path):
        assert rg_mod.fix_stale_bridge_lock(tmp_path)["fixed"] is False

    def test_dead_pid_truncated(self, tmp_path):
        bus = tmp_path / ".agent_bus"; bus.mkdir()
        lock = bus / "bridge.lock"; lock.write_text("999999999\n")
        r = rg_mod.fix_stale_bridge_lock(tmp_path)
        assert r["fixed"] is True and "truncate" in r["action"]
        assert lock.read_text() == ""

    def test_live_pid_not_removed(self, tmp_path):
        bus = tmp_path / ".agent_bus"; bus.mkdir()
        lock = bus / "bridge.lock"; lock.write_text(f"{os.getpid()}\n")
        assert rg_mod.fix_stale_bridge_lock(tmp_path)["fixed"] is False

    def test_corrupt_lock_truncated(self, tmp_path):
        bus = tmp_path / ".agent_bus"; bus.mkdir()
        (bus / "bridge.lock").write_text("not-a-pid\n")
        r = rg_mod.fix_stale_bridge_lock(tmp_path)
        assert r["fixed"] is True and "corrupt" in r["action"]


class TestFixStaleGitIndexLock:
    def test_no_lock(self, tmp_path):
        (tmp_path / ".git").mkdir()
        assert rg_mod.fix_stale_git_index_lock(tmp_path)["fixed"] is False

    def test_lock_removed(self, tmp_path):
        git_dir = tmp_path / ".git"; git_dir.mkdir()
        lock = git_dir / "index.lock"; lock.write_text("lock")
        assert rg_mod.fix_stale_git_index_lock(tmp_path)["fixed"] is True
        assert not lock.exists()


class TestFixStaleExecutorState:
    def _make_state(self, tmp_path, wave_id="old"):
        d = tmp_path / ".agent_bus" / "executors"; d.mkdir(parents=True)
        f = d / "phase_b_state.json"; f.write_text(json.dumps({"wave_id": wave_id}))
        return f

    def test_no_state_file(self, tmp_path):
        assert rg_mod.fix_stale_executor_state(tmp_path, "w1")["fixed"] is False

    def test_mismatched_wave_removed(self, tmp_path):
        f = self._make_state(tmp_path, "old-wave")
        assert rg_mod.fix_stale_executor_state(tmp_path, "new-wave")["fixed"] is True
        assert not f.exists()

    def test_matching_wave_kept(self, tmp_path):
        f = self._make_state(tmp_path, "same")
        assert rg_mod.fix_stale_executor_state(tmp_path, "same")["fixed"] is False
        assert f.exists()

    def test_empty_wave_always_removes(self, tmp_path):
        f = self._make_state(tmp_path, "any")
        assert rg_mod.fix_stale_executor_state(tmp_path, "")["fixed"] is True
        assert not f.exists()

    def test_corrupt_json_removed(self, tmp_path):
        d = tmp_path / ".agent_bus" / "executors"; d.mkdir(parents=True)
        f = d / "phase_b_state.json"; f.write_text("{corrupt")
        assert rg_mod.fix_stale_executor_state(tmp_path, "w1")["fixed"] is True
        assert not f.exists()


class TestFixMixedStaging:
    def test_no_mixed_files(self, tmp_path):
        with patch("recovery_gate.subprocess") as mock_sp:
            mock_sp.run.return_value = type("R", (), {
                "returncode": 0, "stdout": "M  clean.py\n", "stderr": ""})()
            mock_sp.TimeoutExpired = TimeoutError
            mock_sp.CalledProcessError = subprocess.CalledProcessError
            r = rg_mod.fix_mixed_staging(tmp_path)
        assert r["fixed"] is False and r["action"] == "noop"

    def test_mixed_files_reset(self, tmp_path):
        status_r = type("R", (), {"returncode": 0, "stdout": "MM dirty.py\n", "stderr": ""})()
        reset_r = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        def fake_run(cmd, **kw):
            return status_r if "status" in cmd else reset_r

        with patch("recovery_gate.subprocess") as mock_sp:
            mock_sp.run = fake_run
            mock_sp.TimeoutExpired = TimeoutError
            mock_sp.CalledProcessError = subprocess.CalledProcessError
            r = rg_mod.fix_mixed_staging(tmp_path)
        assert r["fixed"] is True and "dirty.py" in r["detail"]


class TestRecoveryLog:
    def test_empty_and_corrupt(self, tmp_path):
        assert rg_mod._load_recovery_log(tmp_path) == []
        d = tmp_path / ".agent_bus" / "recovery"; d.mkdir(parents=True)
        (d / "recovery_log.json").write_text("{bad json")
        assert rg_mod._load_recovery_log(tmp_path) == []

    def test_round_trip_and_cap(self, tmp_path):
        rg_mod._save_recovery_log(tmp_path, [{"wave_id": "w1"}])
        assert rg_mod._load_recovery_log(tmp_path)[0]["wave_id"] == "w1"
        rg_mod._save_recovery_log(tmp_path, [{"i": i} for i in range(600)])
        loaded = rg_mod._load_recovery_log(tmp_path)
        assert len(loaded) == rg_mod.MAX_LOG_ENTRIES and loaded[-1]["i"] == 599

    def test_attempt_counting(self):
        attempts = [
            {"wave_id": "w1", "step": "s1", "failure_class": "x"},
            {"wave_id": "w1", "step": "s1", "failure_class": "x"},
            {"wave_id": "w1", "step": "s1", "failure_class": "y"},
        ]
        assert rg_mod._count_prior_attempts(attempts, "w1", "s1", "x") == 2
        assert rg_mod._count_prior_attempts(attempts, "w2", "s1", "x") == 0


class TestAttemptRecovery:
    def test_tier4_escalates(self, tmp_path):
        r = rg_mod.attempt_recovery(tmp_path, {"status": "question_for_founder", "step": "b"}, "w1")
        assert r["recovered"] is False and r["tier"] == 4 and r["action"] == "escalate"

    def test_tier2_not_implemented(self, tmp_path):
        r = rg_mod.attempt_recovery(tmp_path, {"status": "timeout", "step": "p"}, "w1")
        assert r["recovered"] is False and r["tier"] == 2 and r["action"] == "not_implemented"

    def test_tier1_bridge_lock_recovery(self, tmp_path):
        bus = tmp_path / ".agent_bus"; bus.mkdir()
        (bus / "bridge.lock").write_text("999999999\n")
        r = rg_mod.attempt_recovery(
            tmp_path, {"status": "error", "stderr": "bridge.lock held", "step": "bridge_loop"}, "w1")
        assert r["recovered"] is True and r["tier"] == 1

    def test_tier1_index_lock_recovery(self, tmp_path):
        git_dir = tmp_path / ".git"; git_dir.mkdir()
        lock = git_dir / "index.lock"; lock.write_text("lock")
        r = rg_mod.attempt_recovery(
            tmp_path, {"status": "error", "stderr": "index.lock held", "step": "s"}, "w1")
        assert r["recovered"] is True and not lock.exists()

    def test_exhausted_after_max_attempts(self, tmp_path):
        rg_mod._save_recovery_log(tmp_path, [
            {"wave_id": "w1", "step": "s1", "failure_class": "stale_bridge_lock"},
            {"wave_id": "w1", "step": "s1", "failure_class": "stale_bridge_lock"},
        ])
        r = rg_mod.attempt_recovery(
            tmp_path, {"status": "error", "stderr": "bridge.lock", "step": "s1"}, "w1")
        assert r["recovered"] is False and r["exhausted"] is True

    def test_different_class_not_exhausted(self, tmp_path):
        rg_mod._save_recovery_log(tmp_path, [
            {"wave_id": "w1", "step": "s1", "failure_class": "stale_bridge_lock"},
            {"wave_id": "w1", "step": "s1", "failure_class": "stale_bridge_lock"},
        ])
        git_dir = tmp_path / ".git"; git_dir.mkdir()
        (git_dir / "index.lock").write_text("x")
        r = rg_mod.attempt_recovery(
            tmp_path, {"status": "error", "stderr": "index.lock held", "step": "s1"}, "w1")
        assert r["exhausted"] is False and r["recovered"] is True

    def test_recovery_logged(self, tmp_path):
        bus = tmp_path / ".agent_bus"; bus.mkdir()
        (bus / "bridge.lock").write_text("999999999\n")
        rg_mod.attempt_recovery(
            tmp_path, {"status": "error", "stderr": "bridge.lock held", "step": "bridge_loop"}, "w1")
        entries = rg_mod._load_recovery_log(tmp_path)
        assert len(entries) == 1
        assert entries[0]["wave_id"] == "w1" and entries[0]["tier"] == 1

    def test_unclassified_escalates(self, tmp_path):
        r = rg_mod.attempt_recovery(tmp_path, {"status": "banana"}, "w1")
        assert r["recovered"] is False and r["tier"] == 4 and r["failure_class"] == "unclassified"
