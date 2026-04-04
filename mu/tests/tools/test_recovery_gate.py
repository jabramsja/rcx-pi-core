"""Tests for recovery_gate: failure classifier and Tier 1–3 recovery."""
from __future__ import annotations

import json, os, re, sqlite3, subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from mu.tests.tools.module_loader import load_module

_EXECUTORS_DIR = Path(__file__).resolve().parent.parent.parent / "tools" / "executors"
_OBSERVABILITY_DIR = Path(__file__).resolve().parent.parent.parent / "tools" / "observability"
rg_mod = load_module("recovery_gate", _EXECUTORS_DIR / "recovery_gate.py")
dash_mod = load_module("pipeline_dashboard_observability", _OBSERVABILITY_DIR / "pipeline_dashboard.py")
web_mod = load_module("pipeline_dashboard_web_observability", _OBSERVABILITY_DIR / "pipeline_dashboard_web.py")
FailureClass = rg_mod.FailureClass


class FakePopen:
    def __init__(
        self,
        *,
        stdout: str = "",
        stderr: str = "",
        pid: int = 4242,
        communicate_exc: Exception | None = None,
    ):
        self._stdout = stdout
        self._stderr = stderr
        self.pid = pid
        self.returncode = 0
        self._communicate_exc = communicate_exc
        self._communicate_calls = 0
        self.killed = False

    def communicate(self, timeout=None):
        self._communicate_calls += 1
        if self._communicate_exc is not None and self._communicate_calls == 1:
            raise self._communicate_exc
        return self._stdout, self._stderr

    def kill(self):
        self.killed = True


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

    def test_pr_merge_conflict_not_misclassified_as_stale_continuation(self):
        stdout = (
            "package note: stale continuation wording appeared in prior evidence\n"
            + json.dumps(
                {
                    "status": "error",
                    "step": "ensure_review_clear_and_merge",
                    "errors": [
                        "merge_pr.sh failed: X Pull request repo#723 is not mergeable: "
                        "the merge commit cannot be cleanly created."
                    ],
                    "pr_number": "723",
                },
                indent=2,
            )
        )
        assert rg_mod.classify_failure(
            {"status": "failed", "step": "commit", "stdout": stdout}
        ) == FailureClass.PR_MERGE_CONFLICT

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

    def test_embedded_bridge_error_classified_as_agent_review_crash(self):
        stdout = json.dumps({
            "status": "error",
            "error": (
                "Bridge subprocess failed in round 1 (exit=2). "
                "bridge_supervisor.py: error: unrecognized arguments: --packet-review"
            ),
            "executor": "phase_a_executor",
        }, indent=2)
        assert rg_mod.classify_failure(
            {"status": "failed", "step": "phase_a_executor", "stdout": stdout}
        ) == FailureClass.AGENT_REVIEW_CRASH

    def test_unclassified(self):
        assert rg_mod.classify_failure({"status": "weird"}) == FailureClass.UNCLASSIFIED
        assert rg_mod.classify_failure({}) == FailureClass.UNCLASSIFIED


class TestReasonSummaries:
    def test_embedded_json_reason_prefers_error_field(self):
        stdout = json.dumps({
            "status": "error",
            "error": (
                "Bridge subprocess failed in round 1 (exit=2). "
                "bridge_supervisor.py: error: unrecognized arguments: --packet-review"
            ),
            "rendered_path": ".agent_bus/rendered/phase-a-r1-123.md",
        }, indent=2)
        reason = rg_mod._summarize_result_reason({"stdout": stdout})  # ANTICHEAT_OK
        assert "Bridge subprocess failed in round 1" in reason
        assert reason != "}"

    def test_embedded_json_reason_ignores_leading_log_lines(self):
        payload = json.dumps({
            "status": "error",
            "error": "Bridge subprocess failed in round 1 (exit=2).",
        }, indent=2)
        stdout = (
            "[phase-a] Bridge exit code: 2\n"
            "[phase-a] Bridge failed (exit 2) — failing closed\n"
            f"{payload}\n"
        )
        reason = rg_mod._summarize_result_reason({"stdout": stdout})  # ANTICHEAT_OK
        assert reason == "Bridge subprocess failed in round 1 (exit=2)."


class TestTierMapping:
    def test_all_classes_mapped_and_tier1_tier4_correct(self):
        for fc in FailureClass:
            assert rg_mod.tier_for(fc) in (1, 2, 3, 4), f"{fc} bad tier"
        tier1 = {fc for fc in FailureClass if rg_mod.tier_for(fc) == 1}
        assert tier1 == {FailureClass.STALE_BRIDGE_LOCK,
                         FailureClass.STALE_EXECUTOR_STATE, FailureClass.STALE_CONTINUATION,
                         FailureClass.MIXED_STAGING}
        # STALE_GIT_INDEX_LOCK demoted to Tier 2 (no sound ownership check)
        assert rg_mod.tier_for(FailureClass.STALE_GIT_INDEX_LOCK) == 2
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

    def test_lock_not_removed_demoted(self, tmp_path):
        """index.lock auto-fix demoted to Tier 2 — never deletes."""
        git_dir = tmp_path / ".git"; git_dir.mkdir()
        lock = git_dir / "index.lock"; lock.write_text("lock")
        r = rg_mod.fix_stale_git_index_lock(tmp_path)
        assert r["fixed"] is False
        assert r["action"] == "demoted_to_tier2"
        assert lock.exists()


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

    def test_empty_wave_does_not_remove(self, tmp_path):
        f = self._make_state(tmp_path, "any")
        r = rg_mod.fix_stale_executor_state(tmp_path, "")
        assert r["fixed"] is False
        assert f.exists()  # no wave_id means can't determine staleness

    def test_corrupt_json_removed(self, tmp_path):
        d = tmp_path / ".agent_bus" / "executors"; d.mkdir(parents=True)
        f = d / "phase_b_state.json"; f.write_text("{corrupt")
        assert rg_mod.fix_stale_executor_state(tmp_path, "w1")["fixed"] is True
        assert not f.exists()


class TestFixMixedStaging:
    def test_no_mixed_files(self, tmp_path):
        mock_sp = type("MockSP", (), {
            "run": staticmethod(lambda cmd, **kw: type("R", (), {
                "returncode": 0, "stdout": "M  clean.py\n", "stderr": ""})()),
            "TimeoutExpired": TimeoutError,
            "CalledProcessError": subprocess.CalledProcessError,
        })()
        with patch.object(rg_mod, "subprocess", mock_sp):
            r = rg_mod.fix_mixed_staging(tmp_path)
        assert r["fixed"] is False and r["action"] == "noop"

    def test_mixed_files_reset(self, tmp_path):
        status_r = type("R", (), {"returncode": 0, "stdout": "MM dirty.py\n", "stderr": ""})()
        reset_r = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        def fake_run(cmd, **kw):
            return status_r if "status" in cmd else reset_r

        mock_sp = type("MockSP", (), {
            "run": staticmethod(fake_run),
            "TimeoutExpired": TimeoutError,
            "CalledProcessError": subprocess.CalledProcessError,
        })()
        with patch.object(rg_mod, "subprocess", mock_sp):
            r = rg_mod.fix_mixed_staging(tmp_path)
        assert r["fixed"] is True and "dirty.py" in r["detail"]


class TestRecoveryLog:
    def test_empty_and_corrupt(self, tmp_path):
        assert rg_mod._load_recovery_log(tmp_path) == [] # ANTICHEAT_OK
        d = tmp_path / ".agent_bus" / "recovery"; d.mkdir(parents=True)
        (d / "recovery_log.json").write_text("{bad json")
        assert rg_mod._load_recovery_log(tmp_path) == [] # ANTICHEAT_OK

    def test_round_trip_and_cap(self, tmp_path):
        rg_mod._save_recovery_log(tmp_path, [{"wave_id": "w1"}]) # ANTICHEAT_OK
        assert rg_mod._load_recovery_log(tmp_path)[0]["wave_id"] == "w1" # ANTICHEAT_OK
        rg_mod._save_recovery_log(tmp_path, [{"i": i} for i in range(600)]) # ANTICHEAT_OK
        loaded = rg_mod._load_recovery_log(tmp_path) # ANTICHEAT_OK
        assert len(loaded) == rg_mod.MAX_LOG_ENTRIES and loaded[-1]["i"] == 599

    def test_attempt_counting(self):
        attempts = [
            {"wave_id": "w1", "step": "s1", "failure_class": "x"},
            {"wave_id": "w1", "step": "s1", "failure_class": "x"},
            {"wave_id": "w1", "step": "s1", "failure_class": "y"},
        ]
        assert rg_mod._count_prior_attempts(attempts, "w1", "s1", "x") == 2 # ANTICHEAT_OK
        assert rg_mod._count_prior_attempts(attempts, "w2", "s1", "x") == 0 # ANTICHEAT_OK


class TestRecoveryStatus:
    def test_status_round_trip_and_wave_invocation_count(self, tmp_path):
        rg_mod._save_recovery_status(  # ANTICHEAT_OK: status file is the public pane substrate
            tmp_path,
            {"active": True, "wave_id": "w1"},
        )
        loaded = rg_mod._load_recovery_status(tmp_path)  # ANTICHEAT_OK
        assert loaded["wave_id"] == "w1"
        attempts = [
            {"wave_id": "w1", "invocation_id": "inv-a"},
            {"wave_id": "w1", "invocation_id": "inv-a"},
            {"wave_id": "w1", "invocation_id": "inv-b"},
            {"wave_id": "w1"},
            {"wave_id": "w2", "invocation_id": "inv-z"},
        ]
        assert rg_mod._count_wave_invocations(attempts, "w1") == 3  # ANTICHEAT_OK

    def test_summarize_result_reason_ignores_numeric_stdout_trailer(self):
        result = {
            "status": "error",
            "step": "commit",
            "stdout": "tokens used\n40,304\n",
            "stderr": "",
        }
        assert rg_mod._summarize_result_reason(result) == "commit: error"  # ANTICHEAT_OK


class TestAttemptRecovery:
    def test_tier4_escalates(self, tmp_path):
        r = rg_mod.attempt_recovery(tmp_path, {"status": "question_for_founder", "step": "b"}, "w1")
        assert r["recovered"] is False and r["tier"] == 4 and r["action"] == "escalate"

    def test_tier2_timeout_recovers_via_fix(self, tmp_path, monkeypatch):
        """PROCESS_TIMEOUT now has a Tier 2 fix — returns recovered=True."""
        cfg_dir = tmp_path / "mu" / "tools" / "executors"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "executor_config.json").write_text(json.dumps({
            "timeouts": {"phase_b_executor": 100}
        }))
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)
        r = rg_mod.attempt_recovery(tmp_path, {"status": "timeout", "step": "p"}, "w1")
        assert r["recovered"] is True and r["tier"] == 2
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)

    def test_tier2_pr_merge_conflict_recovers_via_branch_sync(self, tmp_path, monkeypatch):
        calls: list[list[str]] = []

        def fake_run(args, cwd=None, capture_output=False, text=False, timeout=None, **kwargs):
            calls.append(list(args))
            if args[:2] == ["git", "status"]:
                return subprocess.CompletedProcess(args, 0, "", "")
            if args[:4] == ["gh", "pr", "view", "723"]:
                return subprocess.CompletedProcess(
                    args,
                    0,
                    json.dumps({"baseRefName": "dev", "mergeStateStatus": "DIRTY"}),
                    "",
                )
            if args[:3] == ["git", "fetch", "origin"]:
                return subprocess.CompletedProcess(args, 0, "", "")
            if args[:2] == ["git", "merge"]:
                return subprocess.CompletedProcess(args, 0, "Merge made by the 'ort' strategy.\n", "")
            if args[:3] == ["git", "push", "origin"]:
                return subprocess.CompletedProcess(args, 0, "", "")
            raise AssertionError(f"unexpected subprocess.run call: {args}")

        monkeypatch.setattr(rg_mod.subprocess, "run", fake_run)
        stdout = json.dumps(
            {
                "status": "error",
                "step": "ensure_review_clear_and_merge",
                "errors": [
                    "merge_pr.sh failed: X Pull request repo#723 is not mergeable: "
                    "the merge commit cannot be cleanly created."
                ],
                "pr_number": "723",
            }
        )

        r = rg_mod.attempt_recovery(
            tmp_path,
            {"status": "failed", "step": "commit", "stdout": stdout},
            "w1",
        )

        assert r["recovered"] is True
        assert r["tier"] == 2
        assert r["failure_class"] == "pr_merge_conflict"
        assert r["action"] == "merge_base_branch_and_push"
        assert ["git", "fetch", "origin", "dev"] in calls
        assert ["git", "merge", "--no-edit", "origin/dev"] in calls
        assert ["git", "push", "origin", "HEAD"] in calls

    def test_tier1_bridge_lock_recovery(self, tmp_path):
        bus = tmp_path / ".agent_bus"; bus.mkdir()
        (bus / "bridge.lock").write_text("999999999\n")
        r = rg_mod.attempt_recovery(
            tmp_path, {"status": "error", "stderr": "bridge.lock held", "step": "bridge_loop"}, "w1")
        assert r["recovered"] is True and r["tier"] == 1

    def test_tier2_index_lock_no_fix_registered(self, tmp_path):
        """index.lock is Tier 2 but has no registered fix — returns no_fix_registered."""
        git_dir = tmp_path / ".git"; git_dir.mkdir()
        (git_dir / "index.lock").write_text("lock")
        r = rg_mod.attempt_recovery(
            tmp_path, {"status": "error", "stderr": "index.lock held", "step": "s"}, "w1")
        assert r["recovered"] is False and r["tier"] == 2 and r["action"] == "no_fix_registered"

    def test_exhausted_after_max_attempts(self, tmp_path):
        rg_mod._save_recovery_log(tmp_path, [ # ANTICHEAT_OK
            {"wave_id": "w1", "step": "s1", "failure_class": "stale_bridge_lock"},
            {"wave_id": "w1", "step": "s1", "failure_class": "stale_bridge_lock"},
        ])
        r = rg_mod.attempt_recovery(
            tmp_path, {"status": "error", "stderr": "bridge.lock", "step": "s1"}, "w1")
        assert r["recovered"] is False and r["exhausted"] is True

    def test_different_class_not_exhausted(self, tmp_path):
        """Exhaustion is per (wave, step, class) — different class resets count."""
        rg_mod._save_recovery_log(tmp_path, [ # ANTICHEAT_OK
            {"wave_id": "w1", "step": "s1", "failure_class": "stale_bridge_lock"},
            {"wave_id": "w1", "step": "s1", "failure_class": "stale_bridge_lock"},
        ])
        # Use mixed_staging (Tier 1) instead of index_lock (now Tier 2)
        r = rg_mod.attempt_recovery(
            tmp_path, {"status": "error", "stderr": "mixed staging",
                       "step": "stage_files", "stdout": "MM dirty.py"},
            "w1")
        assert r["exhausted"] is False  # different class, not exhausted

    def test_recovery_logged(self, tmp_path):
        bus = tmp_path / ".agent_bus"; bus.mkdir()
        (bus / "bridge.lock").write_text("999999999\n")
        rg_mod.attempt_recovery(
            tmp_path, {"status": "error", "stderr": "bridge.lock held", "step": "bridge_loop"}, "w1")
        entries = rg_mod._load_recovery_log(tmp_path) # ANTICHEAT_OK
        assert len(entries) == 1
        assert entries[0]["wave_id"] == "w1" and entries[0]["tier"] == 1
        status = rg_mod._load_recovery_status(tmp_path)  # ANTICHEAT_OK
        assert status["active"] is False
        assert status["outcome"] == "success"
        assert status["failure_class"] == "stale_bridge_lock"
        assert status["wave_invocation_count"] == 1

    def test_unclassified_escalates(self, tmp_path):
        r = rg_mod.attempt_recovery(tmp_path, {"status": "banana"}, "w1")
        assert r["recovered"] is False and r["tier"] == 4 and r["failure_class"] == "unclassified"

    def test_tier3_attempt_recovery_invokes_live_loop(self, tmp_path):
        loop_result = {
            "recovered": True,
            "exhausted": False,
            "iterations": 1,
            "log": [{"action": "shell", "detail": "retrying phase_b_executor"}],
        }
        with patch.object(rg_mod, "run_recovery_loop", return_value=loop_result) as mock_loop:
            r = rg_mod.attempt_recovery(
                tmp_path,
                {"status": "failed", "step": "phase_b", "stderr": "FAILED test_x"},
                "w1",
            )
        mock_loop.assert_called_once()
        assert r["recovered"] is True
        assert r["tier"] == 3
        assert r["action"] == "recovery_loop"
        assert "retrying phase_b_executor" in r["detail"]

    def test_distinct_executor_timeouts_separate_buckets(self, tmp_path, monkeypatch):
        """Timeout results with different executors don't share exhaustion bucket.

        Bridge R6 Finding 1: dispatch timeout results omit 'step', so
        unrelated timeout sites collapsed into (wave, unknown, process_timeout).
        Fix: step falls back to executor name.
        """
        cfg_dir = tmp_path / "mu" / "tools" / "executors"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "executor_config.json").write_text(json.dumps({
            "timeouts": {"phase_b_executor": 100, "commit_executor": 100}
        }))
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_KEY", raising=False)
        # Two phase_b timeouts (no step — falls back to executor name)
        r1 = rg_mod.attempt_recovery(
            tmp_path,
            {"status": "timeout", "executor": "phase_b_executor"},
            "w-timeout")
        assert r1["recovered"] is True
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_KEY", raising=False)
        r2 = rg_mod.attempt_recovery(
            tmp_path,
            {"status": "timeout", "executor": "phase_b_executor"},
            "w-timeout")
        assert r2["recovered"] is True
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_KEY", raising=False)
        # Third phase_b timeout should be exhausted (max 2 per tuple)
        r3 = rg_mod.attempt_recovery(
            tmp_path,
            {"status": "timeout", "executor": "phase_b_executor"},
            "w-timeout")
        assert r3["exhausted"] is True
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_KEY", raising=False)
        # But a COMMIT executor timeout should NOT be exhausted — separate bucket
        r4 = rg_mod.attempt_recovery(
            tmp_path,
            {"status": "timeout", "executor": "commit_executor"},
            "w-timeout")
        assert r4["recovered"] is True, (
            "commit_executor timeout should not be exhausted by "
            "phase_b_executor exhaustion — they must use separate buckets")
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_KEY", raising=False)


# ===========================================================================
# Tier 2 auto-retry tests
# ===========================================================================


class TestFixProcessTimeout:
    def test_increases_timeout(self, tmp_path, monkeypatch):
        """Verify 50% increase, capped at 2x original."""
        # Write a config with known timeout
        cfg_dir = tmp_path / "mu" / "tools" / "executors"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "executor_config.json").write_text(json.dumps({
            "timeouts": {"phase_b_executor": 100}
        }))
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_KEY", raising=False)
        r = rg_mod.fix_process_timeout(tmp_path)
        assert r["fixed"] is True
        assert r["action"] == "increase_timeout"
        assert os.environ["RCX_RECOVERY_TIMEOUT_OVERRIDE"] == "150"
        # Default timeout key when no result provided
        assert os.environ["RCX_RECOVERY_TIMEOUT_KEY"] == "phase_b_executor"
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_KEY", raising=False)

    def test_cap_at_2x(self, tmp_path, monkeypatch):
        """50% of 100 = 150, cap = 200. 150 < 200 so no cap. Test with explicit cap scenario."""
        cfg_dir = tmp_path / "mu" / "tools" / "executors"
        cfg_dir.mkdir(parents=True)
        # 1.5 * 100 = 150, min(150, 200) = 150 — no cap yet
        # To hit the cap: need int(val * 1.5) > val * 2, impossible for positive vals
        # The cap prevents bugs where the increase factor is changed; verify it's applied
        (cfg_dir / "executor_config.json").write_text(json.dumps({
            "timeouts": {"phase_b_executor": 3600}
        }))
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_KEY", raising=False)
        monkeypatch.delenv("RCX_RECOVERY_ORIGINAL_TIMEOUT_phase_b_executor", raising=False)
        r = rg_mod.fix_process_timeout(tmp_path)
        new_val = int(os.environ["RCX_RECOVERY_TIMEOUT_OVERRIDE"])
        assert new_val == 5400  # 1.5 * 3600
        assert new_val <= 3600 * 2  # never exceeds 2x
        assert os.environ["RCX_RECOVERY_TIMEOUT_KEY"] == "phase_b_executor"
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_KEY", raising=False)

    def test_increases_timeout_commit_executor(self, tmp_path, monkeypatch):
        """Step-aware: commit_executor timeout targets the correct config key."""
        cfg_dir = tmp_path / "mu" / "tools" / "executors"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "executor_config.json").write_text(json.dumps({
            "timeouts": {"phase_b_executor": 3600, "commit_executor": 3600}
        }))
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_KEY", raising=False)
        monkeypatch.delenv("RCX_RECOVERY_ORIGINAL_TIMEOUT_commit_executor", raising=False)
        r = rg_mod.fix_process_timeout(
            tmp_path, result={"executor": "commit_executor", "status": "timeout"})
        assert r["fixed"] is True
        assert os.environ["RCX_RECOVERY_TIMEOUT_OVERRIDE"] == "5400"
        assert os.environ["RCX_RECOVERY_TIMEOUT_KEY"] == "commit_executor"
        assert "commit_executor" in r["detail"]
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_KEY", raising=False)


class TestFixTransientKill:
    def test_returns_retryable(self, tmp_path):
        r = rg_mod.fix_transient_kill(tmp_path)
        assert r["fixed"] is True
        assert r["action"] == "retryable"


class TestFixAggregationHang:
    @staticmethod
    def _create_bridge_db(db_path, jobs=None):
        """Create a bridge.db with the jobs schema and optional job rows."""
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS jobs ("
            "  job_id TEXT PRIMARY KEY,"
            "  created_at TEXT NOT NULL,"
            "  updated_at TEXT NOT NULL,"
            "  status TEXT NOT NULL,"
            "  task_text TEXT NOT NULL,"
            "  scope_hint TEXT,"
            "  wave_class TEXT,"
            "  terminal_decision TEXT"
            ")")
        for job in (jobs or []):
            conn.execute(
                "INSERT INTO jobs (job_id, created_at, updated_at, status, "
                "task_text, scope_hint) VALUES (?, ?, ?, ?, ?, ?)",
                (job["job_id"], "2026-01-01", "2026-01-01",
                 job["status"], "test task", job.get("scope_hint", "")))
        conn.commit()
        conn.close()

    def test_clears_lock_and_marks_stale_jobs(self, tmp_path):
        """Lock is removed. Stale bridge.db jobs are marked failed, DB preserved."""
        bus = tmp_path / ".agent_bus"
        bus.mkdir()
        (bus / "bridge.lock").write_text("123\n")
        db_path = bus / "bridge.db"
        self._create_bridge_db(db_path, jobs=[
            {"job_id": "j1", "status": "in_progress", "scope_hint": "wave-a"},
            {"job_id": "j2", "status": "pending", "scope_hint": "wave-a"},
            {"job_id": "j3", "status": "completed", "scope_hint": "wave-a"},
        ])
        r = rg_mod.fix_aggregation_hang(tmp_path, wave_id="wave-a")
        assert r["fixed"] is True
        assert r["action"] == "clear_bridge_state"
        assert not (bus / "bridge.lock").exists()
        # bridge.db must still exist (not deleted)
        assert db_path.exists()
        # Stale jobs marked failed, completed job untouched
        conn = sqlite3.connect(str(db_path))
        rows = {r[0]: r[1] for r in conn.execute(
            "SELECT job_id, status FROM jobs").fetchall()}
        conn.close()
        assert rows["j1"] == "failed"
        assert rows["j2"] == "failed"
        assert rows["j3"] == "completed"
        assert "bridge.lock" in r["detail"]
        assert "bridge.db" in r["detail"]

    def test_wave_scoped_does_not_affect_other_waves(self, tmp_path):
        """Jobs for other waves are NOT marked failed (Finding 3 fix)."""
        bus = tmp_path / ".agent_bus"
        bus.mkdir()
        db_path = bus / "bridge.db"
        self._create_bridge_db(db_path, jobs=[
            {"job_id": "j-wave-a", "status": "in_progress",
             "scope_hint": "wave-a"},
            {"job_id": "j-wave-b", "status": "in_progress",
             "scope_hint": "wave-b"},
            {"job_id": "j-legacy", "status": "pending",
             "scope_hint": ""},
        ])
        r = rg_mod.fix_aggregation_hang(tmp_path, wave_id="wave-a")
        assert r["fixed"] is True
        conn = sqlite3.connect(str(db_path))
        rows = {r[0]: (r[1], r[2]) for r in conn.execute(
            "SELECT job_id, status, terminal_decision FROM jobs").fetchall()}
        conn.close()
        # wave-a job: marked failed
        assert rows["j-wave-a"][0] == "failed"
        assert rows["j-wave-a"][1] == "recovery_aggregation_hang"
        # wave-b job: UNTOUCHED (different scope_hint)
        assert rows["j-wave-b"][0] == "in_progress"
        assert rows["j-wave-b"][1] is None
        # legacy job (empty scope_hint): UNTOUCHED (Bridge R7 fix —
        # NULL/empty scope_hint rows must not be treated as current-wave)
        assert rows["j-legacy"][0] == "pending"
        assert rows["j-legacy"][1] is None

    def test_null_scoped_rows_untouched_when_wave_id_provided(self, tmp_path):
        """NULL scope_hint rows must NOT be failed — they may belong to other
        waves that didn't set scope_hint (Bridge R7 blocking fix)."""
        bus = tmp_path / ".agent_bus"
        bus.mkdir()
        db_path = bus / "bridge.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE jobs (job_id TEXT, created_at TEXT, updated_at TEXT, "
            "status TEXT, task_text TEXT, scope_hint TEXT, "
            "terminal_decision TEXT)")
        # Insert a row with explicit NULL scope_hint (real-world path:
        # bridge_supervisor.submit_job() without --scope-hint)
        conn.execute(
            "INSERT INTO jobs (job_id, created_at, updated_at, status, "
            "task_text, scope_hint) VALUES (?, ?, ?, ?, ?, NULL)",
            ("j-null", "2026-01-01", "2026-01-01", "in_progress", "test"))
        conn.execute(
            "INSERT INTO jobs (job_id, created_at, updated_at, status, "
            "task_text, scope_hint) VALUES (?, ?, ?, ?, ?, ?)",
            ("j-wave-x", "2026-01-01", "2026-01-01", "in_progress",
             "test", "wave-x"))
        conn.commit()
        conn.close()
        r = rg_mod.fix_aggregation_hang(tmp_path, wave_id="wave-x")
        assert r["fixed"] is True
        conn = sqlite3.connect(str(db_path))
        rows = {r[0]: (r[1],) for r in conn.execute(
            "SELECT job_id, status FROM jobs").fetchall()}
        conn.close()
        # wave-x job: marked failed
        assert rows["j-wave-x"][0] == "failed"
        # NULL-scoped job: UNTOUCHED
        assert rows["j-null"][0] == "in_progress"

    def test_no_stale_jobs_db_untouched(self, tmp_path):
        """If all jobs are completed, bridge.db has nothing to mark."""
        bus = tmp_path / ".agent_bus"
        bus.mkdir()
        db_path = bus / "bridge.db"
        self._create_bridge_db(db_path, jobs=[
            {"job_id": "j1", "status": "completed"},
        ])
        r = rg_mod.fix_aggregation_hang(tmp_path)
        assert r["fixed"] is True
        assert r["action"] == "no_stale_state"
        assert db_path.exists()

    def test_no_files_still_retryable(self, tmp_path):
        r = rg_mod.fix_aggregation_hang(tmp_path)
        assert r["fixed"] is True
        assert r["action"] == "no_stale_state"


class TestFixImplementerStale:
    def test_increases_stale_timeout(self, tmp_path, monkeypatch):
        cfg_dir = tmp_path / "mu" / "tools" / "executors"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "executor_config.json").write_text(json.dumps({
            "timeouts": {"phase_b_implementer_stale": 200}
        }))
        monkeypatch.delenv("RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE", raising=False)
        r = rg_mod.fix_implementer_stale(tmp_path)
        assert r["fixed"] is True
        assert r["action"] == "increase_stale_timeout"
        assert os.environ["RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE"] == "300"
        monkeypatch.delenv("RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE", raising=False)


class TestTier2FixesMap:
    def test_all_five_registered(self):
        """All 5 Tier 2 failure classes have registered fix functions."""
        expected = {
            rg_mod.FailureClass.PROCESS_TIMEOUT,
            rg_mod.FailureClass.TRANSIENT_KILL,
            rg_mod.FailureClass.AGGREGATION_HANG,
            rg_mod.FailureClass.IMPLEMENTER_STALE,
            rg_mod.FailureClass.PR_MERGE_CONFLICT,
        }
        assert set(rg_mod._TIER2_FIXES.keys()) == expected  # ANTICHEAT_OK


class TestTier2AttemptRecovery:
    def test_tier2_timeout_recovers(self, tmp_path, monkeypatch):
        """attempt_recovery for PROCESS_TIMEOUT returns recovered=True."""
        cfg_dir = tmp_path / "mu" / "tools" / "executors"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "executor_config.json").write_text(json.dumps({
            "timeouts": {"phase_b_executor": 100}
        }))
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)
        r = rg_mod.attempt_recovery(
            tmp_path, {"status": "timeout", "step": "phase_b"}, "w1")
        assert r["recovered"] is True
        assert r["tier"] == 2
        assert r["failure_class"] == "process_timeout"
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)

    def test_tier2_transient_kill_recovers(self, tmp_path):
        r = rg_mod.attempt_recovery(
            tmp_path, {"status": "failed", "exit_code": -9, "stderr": "", "step": "impl"}, "w1")
        assert r["recovered"] is True and r["tier"] == 2

    def test_tier2_logged(self, tmp_path):
        r = rg_mod.attempt_recovery(
            tmp_path, {"status": "failed", "exit_code": -9, "stderr": "", "step": "impl"}, "w1")
        entries = rg_mod._load_recovery_log(tmp_path)  # ANTICHEAT_OK
        assert len(entries) == 1
        assert entries[0]["tier"] == 2


# ===========================================================================
# Tier 3 LLM recovery loop tests
# ===========================================================================


class TestRecoveryLoop:
    def test_diagnose_and_fix(self, tmp_path):
        """Mock claude --print returning a shell fix, verify it runs."""
        result = {"status": "failed", "step": "pre_commit",
                  "stderr": "test_x failed", "stdout": ""}
        claude_response = json.dumps({
            "action": "shell",
            "commands": ["echo fixed"],
            "explanation": "applying fix"
        })
        verify_ok = MagicMock(returncode=0, stdout="", stderr="")

        def mock_run(cmd, **kw):
            if isinstance(cmd, list):  # verify command
                return verify_ok
            # shell=True command
            return MagicMock(stdout="ok", stderr="", returncode=0)

        popen_factory = lambda *args, **kwargs: FakePopen(stdout=claude_response, pid=4242)
        orig_update = rg_mod._update_recovery_status  # ANTICHEAT_OK: capture live recovery status transitions
        with patch.object(rg_mod, "subprocess") as mock_sp:
            mock_sp.run = mock_run
            mock_sp.Popen = popen_factory
            mock_sp.PIPE = subprocess.PIPE
            mock_sp.TimeoutExpired = subprocess.TimeoutExpired
            with patch.object(rg_mod, "_update_recovery_status", wraps=orig_update) as update_spy:
                r = rg_mod.run_recovery_loop(
                    tmp_path, result, "w1", verify_command=["echo", "verify"])
        assert r["recovered"] is True
        assert r["iterations"] == 1
        assert any(call.kwargs.get("child_pid") == 4242 for call in update_spy.mock_calls if call.kwargs)
        status = rg_mod._load_recovery_status(tmp_path)  # ANTICHEAT_OK
        assert status["active"] is False
        assert status["outcome"] == "success"
        assert status["child_pid"] == 0
        assert status["last_action"] == "shell"

    def test_successful_shell_fix_requests_retry_without_verify(self, tmp_path):
        result = {
            "status": "failed",
            "step": "phase_b_executor",
            "executor": "phase_b_executor",
            "stderr": "FAILED test_x",
            "stdout": "",
        }
        claude_response = json.dumps({
            "action": "shell",
            "commands": ["echo fixed"],
            "explanation": "apply fix and retry",
        })

        def mock_run(cmd, **kw):
            return MagicMock(stdout="ok", stderr="", returncode=0)

        with patch.object(rg_mod, "subprocess") as mock_sp:
            mock_sp.run = mock_run
            mock_sp.Popen = lambda *args, **kwargs: FakePopen(stdout=claude_response, pid=5151)
            mock_sp.PIPE = subprocess.PIPE
            mock_sp.TimeoutExpired = subprocess.TimeoutExpired
            r = rg_mod.run_recovery_loop(tmp_path, result, "w-retry")
        assert r["recovered"] is True
        assert r["exhausted"] is False
        assert r["iterations"] == 1
        status = rg_mod._load_recovery_status(tmp_path)  # ANTICHEAT_OK
        assert status["active"] is False
        assert status["outcome"] == "retry_requested"
        assert status["state"] == "tier3_retry_requested"
        assert status["retry_target"] == "phase_b_executor"
        entries = rg_mod._load_recovery_log(tmp_path)  # ANTICHEAT_OK
        assert entries[-1]["outcome"] == "retry_requested"

    def test_max_iterations(self, tmp_path):
        """Verify loop stops after max_iterations."""
        result = {"status": "failed", "step": "test", "stderr": "fail", "stdout": ""}
        claude_response = json.dumps({
            "action": "shell", "commands": ["echo try"], "explanation": "trying"
        })
        verify_fail = MagicMock(returncode=1, stdout="", stderr="still fails")

        def mock_run(cmd, **kw):
            if isinstance(cmd, list):  # verify
                return verify_fail
            return MagicMock(stdout="", stderr="", returncode=0)

        with patch.object(rg_mod, "subprocess") as mock_sp:
            mock_sp.run = mock_run
            mock_sp.Popen = lambda *args, **kwargs: FakePopen(stdout=claude_response, pid=31337)
            mock_sp.PIPE = subprocess.PIPE
            mock_sp.TimeoutExpired = subprocess.TimeoutExpired
            r = rg_mod.run_recovery_loop(
                tmp_path, result, "w1", max_iterations=3,
                verify_command=["echo", "verify"])
        assert r["recovered"] is False
        assert r["exhausted"] is True
        assert r["iterations"] == 3
        status = rg_mod._load_recovery_status(tmp_path)  # ANTICHEAT_OK
        assert status["outcome"] == "exhausted"
        assert status["state"] == "tier3_exhausted"
        assert status["current_iteration"] == 3

    def test_escalate_action(self, tmp_path):
        """Verify escalate action returns exhausted=True."""
        result = {"status": "failed", "step": "test", "stderr": "x", "stdout": ""}
        claude_response = json.dumps({
            "action": "escalate", "commands": [], "explanation": "need human"
        })

        with patch.object(rg_mod, "subprocess") as mock_sp:
            mock_sp.run = lambda *args, **kwargs: MagicMock(returncode=0, stdout="", stderr="")
            mock_sp.Popen = lambda *args, **kwargs: FakePopen(stdout=claude_response)
            mock_sp.PIPE = subprocess.PIPE
            mock_sp.TimeoutExpired = subprocess.TimeoutExpired
            r = rg_mod.run_recovery_loop(tmp_path, result, "w1")
        assert r["recovered"] is False
        assert r["exhausted"] is True
        assert r["iterations"] == 1
        status = rg_mod._load_recovery_status(tmp_path)  # ANTICHEAT_OK
        assert status["outcome"] == "escalated"
        assert status["state"] == "tier3_escalated"

    def test_dangerous_command_blocked(self, tmp_path):
        """Verify denylist blocks rm -rf etc."""
        result = {"status": "failed", "step": "test", "stderr": "x", "stdout": ""}
        claude_response = json.dumps({
            "action": "shell",
            "commands": ["rm -rf /tmp/stuff", "echo safe"],
            "explanation": "cleanup"
        })
        verify_fail = MagicMock(returncode=1, stdout="", stderr="nope")

        def mock_run(cmd, **kw):
            if isinstance(cmd, list):  # verify
                return verify_fail
            return MagicMock(stdout="ok", stderr="", returncode=0)

        with patch.object(rg_mod, "subprocess") as mock_sp:
            mock_sp.run = mock_run
            mock_sp.Popen = lambda *args, **kwargs: FakePopen(stdout=claude_response)
            mock_sp.PIPE = subprocess.PIPE
            mock_sp.TimeoutExpired = subprocess.TimeoutExpired
            r = rg_mod.run_recovery_loop(
                tmp_path, result, "w1", max_iterations=1,
                verify_command=["echo", "check"])
        # Verify the dangerous command was blocked in the log
        assert any(
            entry.get("blocked") is True
            for entry in r["log"]
            if entry.get("action") == "shell"
        )

    def test_timeout_handled(self, tmp_path):
        """Verify claude call timeout is handled gracefully."""
        result = {"status": "failed", "step": "test", "stderr": "x", "stdout": ""}

        with patch.object(rg_mod, "subprocess") as mock_sp:
            mock_sp.run = lambda *args, **kwargs: MagicMock(returncode=0, stdout="", stderr="")
            mock_sp.Popen = lambda *args, **kwargs: FakePopen(
                communicate_exc=subprocess.TimeoutExpired(cmd="claude", timeout=60),
                pid=9999,
            )
            mock_sp.PIPE = subprocess.PIPE
            mock_sp.TimeoutExpired = subprocess.TimeoutExpired
            r = rg_mod.run_recovery_loop(
                tmp_path, result, "w1", max_iterations=1)
        assert r["recovered"] is False
        assert len(r["log"]) == 1
        assert r["log"][0]["action"] == "timeout"
        status = rg_mod._load_recovery_status(tmp_path)  # ANTICHEAT_OK
        assert status["outcome"] == "exhausted"
        assert status["last_action"] == "exhausted"


class TestDangerousCommandDetection:
    @pytest.mark.parametrize("cmd", [
        "rm -rf /tmp/x", "git push origin main", "git reset --hard HEAD",
        "sudo rm -rf /", "git push --force",
        "rm -r /tmp/stuff", "git checkout .", "git restore .",
        "git clean -fd", "dd if=/dev/zero of=/dev/sda",
        "chmod 777 /etc/passwd",
    ])
    def test_dangerous_blocked(self, cmd):
        assert rg_mod._is_dangerous_command(cmd) is True  # ANTICHEAT_OK

    @pytest.mark.parametrize("cmd", [
        "echo hello", "git status", "pytest tests/", "cat file.py",
        "git diff", "git log --oneline",
    ])
    def test_safe_allowed(self, cmd):
        assert rg_mod._is_dangerous_command(cmd) is False  # ANTICHEAT_OK


class TestApplyEditRepoEscape:
    def test_edit_within_repo(self, tmp_path):
        """Edit within repo root succeeds."""
        target = tmp_path / "file.py"
        target.write_text("old content")
        ok, msg = rg_mod._apply_edit(  # ANTICHEAT_OK
            {"file_path": "file.py", "old_text": "old", "new_text": "new"},
            tmp_path)
        assert ok is True
        assert "new content" in target.read_text()

    def test_edit_outside_repo_blocked(self, tmp_path):
        """Edit targeting path outside repo_root is blocked."""
        ok, msg = rg_mod._apply_edit(  # ANTICHEAT_OK
            {"file_path": "../../etc/passwd", "old_text": "x", "new_text": "y"},
            tmp_path)
        assert ok is False
        assert "repo-escape blocked" in msg

    def test_edit_symlink_escape_blocked(self, tmp_path):
        """Symlink that resolves outside repo_root is blocked."""
        outside = tmp_path.parent / "outside_file"
        outside.write_text("secret")
        link = tmp_path / "link.txt"
        link.symlink_to(outside)
        ok, msg = rg_mod._apply_edit(  # ANTICHEAT_OK
            {"file_path": "link.txt", "old_text": "secret", "new_text": "hacked"},
            tmp_path)
        assert ok is False
        assert "repo-escape blocked" in msg
        assert outside.read_text() == "secret"  # unchanged


class TestRecoveryLoopDurableLogging:
    def test_iterations_persisted_to_recovery_log(self, tmp_path):
        """Each Tier 3 iteration is durably logged to recovery_log.json."""
        result = {"status": "failed", "step": "pre_commit",
                  "stderr": "test failed", "stdout": ""}
        claude_response = json.dumps({
            "action": "shell", "commands": ["echo fix"], "explanation": "trying"
        })
        verify_fail = MagicMock(returncode=1, stdout="", stderr="still fails")

        def mock_run(cmd, **kw):
            if isinstance(cmd, list):
                return verify_fail
            return MagicMock(stdout="ok", stderr="", returncode=0)

        with patch.object(rg_mod, "subprocess") as mock_sp:
            mock_sp.run = mock_run
            mock_sp.Popen = lambda *args, **kwargs: FakePopen(stdout=claude_response)
            mock_sp.PIPE = subprocess.PIPE
            mock_sp.TimeoutExpired = subprocess.TimeoutExpired
            rg_mod.run_recovery_loop(
                tmp_path, result, "w-log-test", max_iterations=2,
                verify_command=["echo", "check"])

        entries = rg_mod._load_recovery_log(tmp_path)  # ANTICHEAT_OK
        assert len(entries) == 2
        assert all(e["tier"] == 3 for e in entries)
        assert all(e["wave_id"] == "w-log-test" for e in entries)
        assert entries[0]["invocation_id"] == entries[1]["invocation_id"]

    def test_escalate_persisted(self, tmp_path):
        """Escalate action is durably logged."""
        result = {"status": "failed", "step": "test", "stderr": "x", "stdout": ""}
        claude_response = json.dumps({
            "action": "escalate", "commands": [], "explanation": "need human"
        })

        with patch.object(rg_mod, "subprocess") as mock_sp:
            mock_sp.run = lambda *args, **kwargs: MagicMock(returncode=0, stdout="", stderr="")
            mock_sp.Popen = lambda *args, **kwargs: FakePopen(stdout=claude_response)
            mock_sp.PIPE = subprocess.PIPE
            mock_sp.TimeoutExpired = subprocess.TimeoutExpired
            rg_mod.run_recovery_loop(tmp_path, result, "w-esc")

        entries = rg_mod._load_recovery_log(tmp_path)  # ANTICHEAT_OK
        assert len(entries) == 1
        assert "escalate" in entries[0]["action"]
        assert entries[0]["outcome"] == "escalated"


class TestRecoveryStatusRendering:
    def test_no_status_file(self, tmp_path):
        lines = dash_mod.render_recovery_lines(tmp_path)
        assert lines[0] == "RECOVERY"
        assert "No recovery activity recorded yet." in lines[-1]

    def test_active_looping_recovery(self, tmp_path):
        status_path = tmp_path / ".agent_bus" / "recovery"
        status_path.mkdir(parents=True)
        now = datetime(2026, 4, 3, 21, 0, tzinfo=timezone.utc)
        (status_path / "recovery_status.json").write_text(
            json.dumps(
                {
                    "active": True,
                    "wave_id": "wave-alpha",
                    "failure_class": "process_timeout",
                    "tier": 2,
                    "wave_invocation_count": 2,
                    "tuple_attempt_index": 1,
                    "retry_target": "phase_a_executor",
                    "state": "tier2_fixing",
                    "owner_pid": 1,
                    "reason": "phase_a timed out",
                    "updated_at": (now - timedelta(seconds=12)).isoformat(),
                    "current_iteration": 0,
                    "max_iterations": 0,
                    "current_command": "",
                    "explanation": "",
                    "detail": "",
                }
            ),
            encoding="utf-8",
        )
        rendered = "\n".join(dash_mod.render_recovery_lines(tmp_path, now=now))
        assert "ACTIVE — Tier 2 recovery (process_timeout)" in rendered
        assert "Problem: a step timed out" in rendered
        assert "If recovery works, go back to: Phase A" in rendered
        assert "Invocation: 2 in wave" in rendered
        assert "Reason: phase_a timed out" in rendered

    def test_hung_child_pid_and_completed_outcome(self, tmp_path):
        status_path = tmp_path / ".agent_bus" / "recovery"
        status_path.mkdir(parents=True)
        now = datetime(2026, 4, 3, 21, 0, tzinfo=timezone.utc)
        (status_path / "recovery_status.json").write_text(
            json.dumps(
                {
                    "active": True,
                    "wave_id": "wave-beta",
                    "failure_class": "agent_review_crash",
                    "tier": 3,
                    "wave_invocation_count": 1,
                    "tuple_attempt_index": 1,
                    "retry_target": "commit_executor",
                    "state": "tier3_waiting_on_claude",
                    "owner_pid": 999999,
                    "child_pid": 888888,
                    "child_role": "claude",
                    "reason": "connector stalled",
                    "updated_at": (now - timedelta(seconds=120)).isoformat(),
                    "current_iteration": 2,
                    "max_iterations": 3,
                    "current_command": "claude --print",
                    "explanation": "trying a narrower fix",
                    "detail": "",
                }
            ),
            encoding="utf-8",
        )
        rendered = "\n".join(dash_mod.render_recovery_lines(tmp_path, now=now))
        assert "POSSIBLY HUNG — Tier 3 recovery (agent_review_crash)" in rendered
        assert "asking the recovery agent what to try" in rendered
        assert "loop 2/3" in rendered
        assert "claude PID: 888888 (dead)" in rendered

        (status_path / "recovery_status.json").write_text(
            json.dumps(
                {
                    "active": False,
                    "wave_id": "wave-beta",
                    "failure_class": "agent_review_crash",
                    "tier": 3,
                    "wave_invocation_count": 1,
                    "tuple_attempt_index": 1,
                    "retry_target": "commit_executor",
                    "state": "tier3_verify_pass",
                    "owner_pid": 1234,
                    "child_pid": 0,
                    "reason": "connector stalled",
                    "updated_at": (now - timedelta(seconds=20)).isoformat(),
                    "finished_at": (now - timedelta(seconds=20)).isoformat(),
                    "current_iteration": 1,
                    "max_iterations": 3,
                    "current_command": "",
                    "explanation": "narrowed the fix",
                    "detail": "verification passed",
                    "outcome": "success",
                    "last_action": "shell",
                    "recovered": True,
                }
            ),
            encoding="utf-8",
        )
        rendered = "\n".join(dash_mod.render_recovery_lines(tmp_path, now=now))
        assert "LAST RECOVERY — Tier 3 recovery (agent_review_crash)" in rendered
        assert "Outcome: success via shell" in rendered
        assert "Recovery note: narrowed the fix" in rendered

    def test_recent_attempts_rendered_for_matching_invocation(self, tmp_path):
        status_path = tmp_path / ".agent_bus" / "recovery"
        status_path.mkdir(parents=True)
        now = datetime(2026, 4, 3, 21, 0, tzinfo=timezone.utc)
        (status_path / "recovery_status.json").write_text(
            json.dumps(
                {
                    "active": True,
                    "invocation_id": "wave-gamma-phase_b_executor-process_timeout-01",
                    "wave_id": "wave-gamma",
                    "step": "phase_b_executor",
                    "failure_class": "process_timeout",
                    "tier": 3,
                    "wave_invocation_count": 3,
                    "tuple_attempt_index": 2,
                    "retry_target": "phase_b_executor",
                    "state": "tier3_verifying",
                    "owner_pid": 1234,
                    "child_pid": 5678,
                    "child_role": "claude",
                    "reason": "phase_b timed out",
                    "updated_at": (now - timedelta(seconds=8)).isoformat(),
                    "current_iteration": 2,
                    "max_iterations": 3,
                    "current_command": "pytest mu/tests/tools/test_executor_dispatch.py -q",
                    "explanation": "retry with narrower timeout override",
                    "detail": "",
                }
            ),
            encoding="utf-8",
        )
        (status_path / "recovery_log.json").write_text(
            json.dumps(
                {
                    "attempts": [
                        {
                            "timestamp": (now - timedelta(seconds=40)).isoformat(),
                            "wave_id": "wave-old",
                            "step": "phase_b_executor",
                            "failure_class": "process_timeout",
                            "tier": 3,
                            "action": "tier3_iter1_skip",
                            "outcome": "skipped",
                            "duration_s": 0.5,
                            "detail": "old unrelated invocation",
                            "invocation_id": "wave-old-phase_b_executor-process_timeout-01",
                        },
                        {
                            "timestamp": (now - timedelta(seconds=20)).isoformat(),
                            "wave_id": "wave-gamma",
                            "step": "phase_b_executor",
                            "failure_class": "process_timeout",
                            "tier": 3,
                            "action": "tier3_iter1_parse_error",
                            "outcome": "failed",
                            "duration_s": 1.25,
                            "detail": "claude returned prose instead of json",
                            "invocation_id": "wave-gamma-phase_b_executor-process_timeout-01",
                        },
                        {
                            "timestamp": (now - timedelta(seconds=5)).isoformat(),
                            "wave_id": "wave-gamma",
                            "step": "phase_b_executor",
                            "failure_class": "process_timeout",
                            "tier": 3,
                            "action": "tier3_iter2_shell",
                            "outcome": "retry_requested",
                            "duration_s": 2.75,
                            "detail": "timeout override applied; retrying Phase B",
                            "invocation_id": "wave-gamma-phase_b_executor-process_timeout-01",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )

        rendered = "\n".join(dash_mod.render_recovery_lines(tmp_path, now=now))
        assert "Recent attempts:" in rendered
        assert "tier3_iter1_parse_error -> failed" in rendered
        assert "tier3_iter2_shell -> retry_requested" in rendered
        assert "old unrelated invocation" not in rendered

    def test_inactive_trivial_invocation_uses_detail_and_wave_history(self, tmp_path):
        status_path = tmp_path / ".agent_bus" / "recovery"
        status_path.mkdir(parents=True)
        now = datetime(2026, 4, 4, 5, 0, tzinfo=timezone.utc)
        (status_path / "recovery_status.json").write_text(
            json.dumps(
                {
                    "active": False,
                    "invocation_id": "wave-delta-commit-stale-continuation-01",
                    "wave_id": "wave-delta",
                    "step": "commit",
                    "failure_class": "stale_continuation",
                    "tier": 1,
                    "wave_invocation_count": 2,
                    "tuple_attempt_index": 1,
                    "retry_target": "commit_executor",
                    "state": "tier1_failed",
                    "owner_pid": 999999,
                    "child_pid": 0,
                    "reason": "40,304",
                    "updated_at": (now - timedelta(seconds=30)).isoformat(),
                    "finished_at": (now - timedelta(seconds=30)).isoformat(),
                    "current_iteration": 0,
                    "max_iterations": 0,
                    "current_command": "",
                    "explanation": "",
                    "detail": "phase_b_state.json not found",
                    "outcome": "failed",
                    "last_action": "noop",
                    "recovered": False,
                }
            ),
            encoding="utf-8",
        )
        (status_path / "recovery_log.json").write_text(
            json.dumps(
                {
                    "attempts": [
                        {
                            "timestamp": (now - timedelta(seconds=80)).isoformat(),
                            "wave_id": "wave-delta",
                            "step": "commit",
                            "failure_class": "test_failure",
                            "tier": 3,
                            "action": "tier3_iter1_parse_error",
                            "outcome": "failed",
                            "duration_s": 1.25,
                            "detail": "claude returned prose instead of json",
                            "invocation_id": "wave-delta-commit-test-failure-01",
                        },
                        {
                            "timestamp": (now - timedelta(seconds=45)).isoformat(),
                            "wave_id": "wave-delta",
                            "step": "commit",
                            "failure_class": "test_failure",
                            "tier": 3,
                            "action": "tier3_iter2_edit",
                            "outcome": "retry_requested",
                            "duration_s": 2.5,
                            "detail": "lane metadata corrected",
                            "invocation_id": "wave-delta-commit-test-failure-01",
                        },
                        {
                            "timestamp": (now - timedelta(seconds=30)).isoformat(),
                            "wave_id": "wave-delta",
                            "step": "commit",
                            "failure_class": "stale_continuation",
                            "tier": 1,
                            "action": "noop",
                            "outcome": "failed",
                            "duration_s": 0.003,
                            "detail": "phase_b_state.json not found",
                            "invocation_id": "wave-delta-commit-stale-continuation-01",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )

        rendered = "\n".join(dash_mod.render_recovery_lines(tmp_path, now=now))
        assert "Reason: phase_b_state.json not found" in rendered
        assert "40,304" not in rendered
        assert "Owner PID: 999999 (dead, historical)" in rendered
        assert "Recent attempts in wave:" in rendered
        assert "tier3_iter2_edit -> retry_requested" in rendered


class TestRecoveryWebSnapshot:
    def test_missing_snapshot_returns_none(self, tmp_path):
        with patch.object(web_mod, "REPO_ROOT", tmp_path):
            assert web_mod.recovery_snapshot() is None  # ANTICHEAT_OK

    def test_active_snapshot_exposes_plain_recovery_fields(self, tmp_path):
        status_path = tmp_path / ".agent_bus" / "recovery"
        status_path.mkdir(parents=True)
        now = datetime.now(timezone.utc)
        (status_path / "recovery_status.json").write_text(
            json.dumps(
                {
                    "active": True,
                    "tier": 3,
                    "failure_class": "agent_review_crash",
                    "wave_id": "wave-recovery",
                    "wave_invocation_count": 4,
                    "tuple_attempt_index": 2,
                    "retry_target": "phase_a_executor",
                    "state": "tier3_waiting_on_claude",
                    "reason": "Bridge subprocess failed in round 1",
                    "explanation": "trying a narrower fix",
                    "current_iteration": 2,
                    "max_iterations": 3,
                    "owner_pid": 123,
                    "child_pid": 456,
                    "child_role": "claude",
                    "current_command": "claude --print",
                    "updated_at": now.isoformat(),
                }
            ),
            encoding="utf-8",
        )
        with patch.object(web_mod, "REPO_ROOT", tmp_path):
            snapshot = web_mod.recovery_snapshot()  # ANTICHEAT_OK
        assert snapshot["label"] == "ACTIVE"
        assert snapshot["retry_target"] == "Phase A"
        assert snapshot["reason"] == "Bridge subprocess failed in round 1"
        assert snapshot["current_iteration"] == 2
        assert snapshot["max_iterations"] == 3
        assert snapshot["child_role"] == "claude"

    def test_snapshot_reason_prefers_detail_over_numeric_reason(self, tmp_path):
        status_path = tmp_path / ".agent_bus" / "recovery"
        status_path.mkdir(parents=True)
        now = datetime.now(timezone.utc)
        (status_path / "recovery_status.json").write_text(
            json.dumps(
                {
                    "active": False,
                    "tier": 1,
                    "failure_class": "stale_continuation",
                    "wave_id": "wave-recovery",
                    "wave_invocation_count": 2,
                    "tuple_attempt_index": 1,
                    "retry_target": "commit_executor",
                    "state": "tier1_failed",
                    "reason": "40,304",
                    "detail": "phase_b_state.json not found",
                    "explanation": "",
                    "current_iteration": 0,
                    "max_iterations": 0,
                    "owner_pid": 999999,
                    "child_pid": 0,
                    "current_command": "",
                    "updated_at": now.isoformat(),
                }
            ),
            encoding="utf-8",
        )
        with patch.object(web_mod, "REPO_ROOT", tmp_path):
            snapshot = web_mod.recovery_snapshot()  # ANTICHEAT_OK
        assert snapshot["reason"] == "phase_b_state.json not found"
        assert snapshot["detail"] == ""
        assert snapshot["owner_state"] == "dead"


class TestObservabilityNoiseFilters:
    def test_terminal_dashboard_ignores_tail_watchers(self):
        lines = [
            "jeff 15571 0.0 0.0 ?? Ss 0:00.00 tail -f /repo/.scratch/phase_a_executor_live.log",
            "jeff 20001 0.0 0.0 ?? Ss 0:00.00 python mu/tools/executors/commit_executor.py",
        ]
        with patch.object(dash_mod, "pid_start", return_value=123.0):
            phase, pid, started = dash_mod.detect_phase(lines)
        assert phase == "commit"
        assert pid == 20001
        assert started == 123.0

    def test_web_dashboard_ignores_tail_watchers(self):
        lines = [
            "jeff 15571 0.0 0.0 ?? Ss 0:00.00 tail -f /repo/.scratch/phase_a_executor_live.log",
            "jeff 20002 0.0 0.0 ?? Ss 0:00.00 python mu/tools/executors/phase_b_executor.py",
        ]
        with patch.object(web_mod, "pid_start", return_value=456.0):
            phase = web_mod.detect_phase(lines)
        assert phase["phase"] == "phase-b"
        assert phase["pid"] == 20002
        assert phase["started"] == 456.0

    def test_only_watcher_noise_reports_idle(self):
        lines = [
            "jeff 15571 0.0 0.0 ?? Ss 0:00.00 tail -f /repo/.scratch/phase_a_executor_live.log",
            "jeff 15572 0.0 0.0 ?? Ss 0:00.00 bash /tmp/rcx_log_watcher.sh",
        ]
        with patch.object(dash_mod, "pid_start", return_value=789.0):
            phase, pid, started = dash_mod.detect_phase(lines)
        assert phase == "idle"
        assert pid is None
        assert started is None


class TestObservabilityWorktreeResolution:
    def _write_executable(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | 0o111)

    def _fake_git_dir(
        self,
        tmp_path: Path,
        *,
        show_toplevel: str | None,
        branch: str | None,
        worktree_output: str = "",
    ) -> Path:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        script = f"""#!/usr/bin/env bash
set -eu
args=("$@")
if [ "${{args[0]:-}}" = "-C" ]; then
  args=("${{args[@]:2}}")
fi
case "${{args[*]}}" in
  "rev-parse --show-toplevel")
    {"printf '%s\\n' " + repr(show_toplevel) if show_toplevel is not None else "exit 128"}
    ;;
  "rev-parse --abbrev-ref HEAD")
    {"printf '%s\\n' " + repr(branch) if branch is not None else "exit 1"}
    ;;
  "symbolic-ref --quiet --short HEAD")
    {"printf '%s\\n' " + repr(branch) if branch is not None else "exit 1"}
    ;;
  "worktree list --porcelain")
    printf '%b' {worktree_output!r}
    ;;
  *)
    exit 1
    ;;
esac
"""
        self._write_executable(bin_dir / "git", script)
        return bin_dir

    def _minimal_bus(self, repo_root: Path) -> None:
        (repo_root / ".agent_bus" / "executors").mkdir(parents=True, exist_ok=True)
        (repo_root / ".agent_bus" / "meta" / "pre_commit_receipts").mkdir(parents=True, exist_ok=True)

    def _install_observability_script(self, repo_root: Path, name: str) -> None:
        target = repo_root / "mu" / "tools" / "observability"
        target.mkdir(parents=True, exist_ok=True)
        script = target / name
        script.write_text((_OBSERVABILITY_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
        script.chmod(script.stat().st_mode | 0o111)

    def _write_commit_state(self, repo_root: Path, *, status: str) -> None:
        state = repo_root / ".agent_bus" / "executors" / "commit_executor_test.json"
        state.write_text(f'{{"status": "{status}"}}\\n', encoding="utf-8")

    def _set_age_seconds(self, path: Path, *, age_seconds: int) -> None:
        now = datetime.now(timezone.utc).timestamp()
        aged = now - age_seconds
        os.utime(path, (aged, aged))

    def test_pipeline_status_fails_closed_when_branch_is_unresolved(self, tmp_path):
        common = tmp_path / "common"
        common.mkdir()
        bin_dir = self._fake_git_dir(tmp_path, show_toplevel=None, branch=None)
        env = os.environ | {"PATH": f"{bin_dir}:{os.environ['PATH']}"}

        result = subprocess.run(
            ["bash", str(_OBSERVABILITY_DIR / "pipeline_status.sh")],
            cwd=common,
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode != 0
        assert "cannot resolve repo root" in result.stderr.lower()

    def test_pipeline_status_uses_exact_linked_worktree_from_common_dir(self, tmp_path):
        common = tmp_path / "common"
        common.mkdir()
        linked = tmp_path / "linked"
        linked.mkdir()
        self._minimal_bus(linked)
        branch = "jabramsja/pipeline-monitor-worktree-rebind-2026-04-03"
        worktree_output = (
            f"worktree {common}\n"
            "bare\n\n"
            f"worktree {linked}\n"
            "HEAD 0123456789abcdef\n"
            f"branch refs/heads/{branch}\n"
        )
        bin_dir = self._fake_git_dir(
            tmp_path,
            show_toplevel=None,
            branch=branch,
            worktree_output=worktree_output,
        )
        env = os.environ | {"PATH": f"{bin_dir}:{os.environ['PATH']}"}

        result = subprocess.run(
            ["bash", str(_OBSERVABILITY_DIR / "pipeline_status.sh")],
            cwd=common,
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0
        assert "PIPELINE STATUS" in result.stdout

    def test_pipeline_status_uses_unique_active_worktree_when_branch_is_stale(self, tmp_path):
        common = tmp_path / "common"
        common.mkdir()
        stale = tmp_path / "stale"
        active = tmp_path / "active"
        stale.mkdir()
        active.mkdir()
        self._minimal_bus(active)
        self._write_commit_state(active, status="post_commit_pending")
        worktree_output = (
            f"worktree {common}\n"
            "bare\n\n"
            f"worktree {stale}\n"
            "HEAD 1111111111111111\n"
            "branch refs/heads/jabramsja/stale-wave\n\n"
            f"worktree {active}\n"
            "HEAD 2222222222222222\n"
            "branch refs/heads/jabramsja/active-wave\n"
        )
        bin_dir = self._fake_git_dir(
            tmp_path,
            show_toplevel=None,
            branch="jabramsja/missing-wave",
            worktree_output=worktree_output,
        )
        env = os.environ | {"PATH": f"{bin_dir}:{os.environ['PATH']}"}

        result = subprocess.run(
            ["bash", str(_OBSERVABILITY_DIR / "pipeline_status.sh")],
            cwd=common,
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0
        assert "PIPELINE STATUS" in result.stdout
        assert "post_commit_pending" in result.stdout

    def test_pipeline_status_prefers_unique_active_worktree_over_quiet_current_root(self, tmp_path):
        stale = tmp_path / "stale"
        active = tmp_path / "active"
        stale.mkdir()
        active.mkdir()
        self._minimal_bus(stale)
        self._minimal_bus(active)
        self._write_commit_state(stale, status="post_commit_pending")
        self._set_age_seconds(
            stale / ".agent_bus" / "executors" / "commit_executor_test.json",
            age_seconds=7 * 60 * 60,
        )
        self._write_commit_state(active, status="post_commit_pending")
        worktree_output = (
            f"worktree {stale}\n"
            "HEAD 1111111111111111\n"
            "branch refs/heads/jabramsja/stale-wave\n\n"
            f"worktree {active}\n"
            "HEAD 2222222222222222\n"
            "branch refs/heads/jabramsja/active-wave\n"
        )
        bin_dir = self._fake_git_dir(
            tmp_path,
            show_toplevel=str(stale),
            branch="jabramsja/stale-wave",
            worktree_output=worktree_output,
        )
        env = os.environ | {"PATH": f"{bin_dir}:{os.environ['PATH']}"}

        result = subprocess.run(
            ["bash", str(_OBSERVABILITY_DIR / "pipeline_status.sh")],
            cwd=stale,
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0
        assert "post_commit_pending" in result.stdout

    def test_pipeline_status_renders_recovery_block_when_dashboard_is_present(self, tmp_path):
        repo_root = tmp_path / "active"
        repo_root.mkdir()
        self._minimal_bus(repo_root)
        self._install_observability_script(repo_root, "pipeline_status.sh")
        self._install_observability_script(repo_root, "pipeline_dashboard.py")
        recovery_dir = repo_root / ".agent_bus" / "recovery"
        recovery_dir.mkdir(parents=True)
        now = datetime.now(timezone.utc)
        (recovery_dir / "recovery_status.json").write_text(
            json.dumps(
                {
                    "active": True,
                    "tier": 3,
                    "failure_class": "agent_review_crash",
                    "wave_id": "wave-recovery",
                    "retry_target": "phase_a_executor",
                    "state": "tier3_waiting_on_claude",
                    "reason": "Bridge subprocess failed in round 1",
                    "current_iteration": 2,
                    "max_iterations": 3,
                    "updated_at": now.isoformat(),
                }
            ),
            encoding="utf-8",
        )
        worktree_output = (
            f"worktree {repo_root}\n"
            "HEAD 1111111111111111\n"
            "branch refs/heads/jabramsja/recovery-wave\n"
        )
        bin_dir = self._fake_git_dir(
            tmp_path,
            show_toplevel=str(repo_root),
            branch="jabramsja/recovery-wave",
            worktree_output=worktree_output,
        )
        env = os.environ | {"PATH": f"{bin_dir}:{os.environ['PATH']}"}

        result = subprocess.run(
            ["bash", str(repo_root / "mu" / "tools" / "observability" / "pipeline_status.sh")],
            cwd=repo_root,
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0
        assert "RECOVERY" in result.stdout
        assert "Tier 3 recovery (agent_review_crash)" in result.stdout

    def test_pipeline_status_uses_sole_linked_worktree_when_only_one_exists(self, tmp_path):
        common = tmp_path / "common"
        common.mkdir()
        linked = tmp_path / "linked"
        linked.mkdir()
        self._minimal_bus(linked)
        worktree_output = (
            f"worktree {common}\n"
            "bare\n\n"
            f"worktree {linked}\n"
            "HEAD 3333333333333333\n"
            "branch refs/heads/dev\n"
        )
        bin_dir = self._fake_git_dir(
            tmp_path,
            show_toplevel=None,
            branch="main",
            worktree_output=worktree_output,
        )
        env = os.environ | {"PATH": f"{bin_dir}:{os.environ['PATH']}"}

        result = subprocess.run(
            ["bash", str(_OBSERVABILITY_DIR / "pipeline_status.sh")],
            cwd=common,
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0
        assert "PIPELINE STATUS" in result.stdout

    def test_pipeline_status_uses_unique_dev_worktree_when_common_head_is_unattached(self, tmp_path):
        common = tmp_path / "common"
        common.mkdir()
        feature = tmp_path / "feature"
        dev = tmp_path / "dev"
        feature.mkdir()
        dev.mkdir()
        self._minimal_bus(dev)
        worktree_output = (
            f"worktree {common}\n"
            "bare\n\n"
            f"worktree {feature}\n"
            "HEAD 1111111111111111\n"
            "branch refs/heads/jabramsja/feature-wave\n\n"
            f"worktree {dev}\n"
            "HEAD 2222222222222222\n"
            "branch refs/heads/dev\n"
        )
        bin_dir = self._fake_git_dir(
            tmp_path,
            show_toplevel=None,
            branch="main",
            worktree_output=worktree_output,
        )
        env = os.environ | {"PATH": f"{bin_dir}:{os.environ['PATH']}"}

        result = subprocess.run(
            ["bash", str(_OBSERVABILITY_DIR / "pipeline_status.sh")],
            cwd=common,
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0
        assert "PIPELINE STATUS" in result.stdout

    def test_pipeline_status_prefers_freshest_active_worktree_when_multiple_active_worktrees_exist(self, tmp_path):
        common = tmp_path / "common"
        common.mkdir()
        active_one = tmp_path / "active-one"
        active_two = tmp_path / "active-two"
        active_one.mkdir()
        active_two.mkdir()
        self._minimal_bus(active_one)
        self._minimal_bus(active_two)
        self._write_commit_state(active_one, status="post_commit_pending")
        self._write_commit_state(active_two, status="bot_findings_pending")
        self._set_age_seconds(
            active_one / ".agent_bus" / "executors" / "commit_executor_test.json",
            age_seconds=10 * 60,
        )
        worktree_output = (
            f"worktree {common}\n"
            "bare\n\n"
            f"worktree {active_one}\n"
            "HEAD 1111111111111111\n"
            "branch refs/heads/jabramsja/active-one\n\n"
            f"worktree {active_two}\n"
            "HEAD 2222222222222222\n"
            "branch refs/heads/jabramsja/active-two\n"
        )
        bin_dir = self._fake_git_dir(
            tmp_path,
            show_toplevel=None,
            branch="jabramsja/missing-wave",
            worktree_output=worktree_output,
        )
        env = os.environ | {"PATH": f"{bin_dir}:{os.environ['PATH']}"}

        result = subprocess.run(
            ["bash", str(_OBSERVABILITY_DIR / "pipeline_status.sh"), "--print-root"],
            cwd=common,
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0
        assert result.stdout.strip() == str(active_two)

    def test_pipeline_status_prefers_current_root_when_it_has_the_freshest_recent_signal(self, tmp_path):
        current = tmp_path / "current"
        active_one = tmp_path / "active-one"
        active_two = tmp_path / "active-two"
        current.mkdir()
        active_one.mkdir()
        active_two.mkdir()
        self._minimal_bus(current)
        self._minimal_bus(active_one)
        self._minimal_bus(active_two)
        self._write_commit_state(active_one, status="post_commit_pending")
        self._write_commit_state(active_two, status="bot_findings_pending")
        self._set_age_seconds(
            active_one / ".agent_bus" / "executors" / "commit_executor_test.json",
            age_seconds=20 * 60,
        )
        self._set_age_seconds(
            active_two / ".agent_bus" / "executors" / "commit_executor_test.json",
            age_seconds=10 * 60,
        )
        (current / ".scratch").mkdir(parents=True, exist_ok=True)
        (current / ".scratch" / "commit_executor_live.log").write_text(
            "[commit-executor] Step 15: merged\n",
            encoding="utf-8",
        )
        worktree_output = (
            f"worktree {current}\n"
            "HEAD 1111111111111111\n"
            "branch refs/heads/jabramsja/current-wave\n\n"
            f"worktree {active_one}\n"
            "HEAD 2222222222222222\n"
            "branch refs/heads/jabramsja/active-one\n\n"
            f"worktree {active_two}\n"
            "HEAD 3333333333333333\n"
            "branch refs/heads/jabramsja/active-two\n"
        )
        bin_dir = self._fake_git_dir(
            tmp_path,
            show_toplevel=str(current),
            branch="jabramsja/current-wave",
            worktree_output=worktree_output,
        )
        env = os.environ | {"PATH": f"{bin_dir}:{os.environ['PATH']}"}

        result = subprocess.run(
            ["bash", str(_OBSERVABILITY_DIR / "pipeline_status.sh"), "--print-root"],
            cwd=current,
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0
        assert result.stdout.strip() == str(current)

    def test_pipeline_monitor_fails_closed_when_branch_is_unresolved(self, tmp_path):
        common = tmp_path / "common"
        common.mkdir()
        bin_dir = self._fake_git_dir(tmp_path, show_toplevel=None, branch=None)
        env = os.environ | {"PATH": f"{bin_dir}:{os.environ['PATH']}"}

        result = subprocess.run(
            ["bash", str(_OBSERVABILITY_DIR / "pipeline_monitor.sh"), "status"],
            cwd=common,
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode != 0
        assert "cannot resolve repo root" in result.stderr.lower()

    def test_pipeline_monitor_status_uses_unique_dev_worktree_when_common_head_is_unattached(self, tmp_path):
        common = tmp_path / "common"
        common.mkdir()
        feature = tmp_path / "feature"
        dev = tmp_path / "dev"
        feature.mkdir()
        dev.mkdir()
        self._minimal_bus(dev)
        self._install_observability_script(dev, "pipeline_status.sh")
        worktree_output = (
            f"worktree {common}\n"
            "bare\n\n"
            f"worktree {feature}\n"
            "HEAD 1111111111111111\n"
            "branch refs/heads/jabramsja/feature-wave\n\n"
            f"worktree {dev}\n"
            "HEAD 2222222222222222\n"
            "branch refs/heads/dev\n"
        )
        bin_dir = self._fake_git_dir(
            tmp_path,
            show_toplevel=None,
            branch="main",
            worktree_output=worktree_output,
        )
        env = os.environ | {"PATH": f"{bin_dir}:{os.environ['PATH']}"}

        result = subprocess.run(
            ["bash", str(_OBSERVABILITY_DIR / "pipeline_monitor.sh"), "status"],
            cwd=common,
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0
        assert "PIPELINE STATUS" in result.stdout

    def test_pipeline_monitor_status_prefers_unique_active_worktree_over_quiet_current_root(self, tmp_path):
        stale = tmp_path / "stale"
        active = tmp_path / "active"
        stale.mkdir()
        active.mkdir()
        self._minimal_bus(stale)
        self._minimal_bus(active)
        self._install_observability_script(active, "pipeline_status.sh")
        self._write_commit_state(stale, status="post_commit_pending")
        self._set_age_seconds(
            stale / ".agent_bus" / "executors" / "commit_executor_test.json",
            age_seconds=7 * 60 * 60,
        )
        self._write_commit_state(active, status="post_commit_pending")
        worktree_output = (
            f"worktree {stale}\n"
            "HEAD 1111111111111111\n"
            "branch refs/heads/jabramsja/stale-wave\n\n"
            f"worktree {active}\n"
            "HEAD 2222222222222222\n"
            "branch refs/heads/jabramsja/active-wave\n"
        )
        bin_dir = self._fake_git_dir(
            tmp_path,
            show_toplevel=str(stale),
            branch="jabramsja/stale-wave",
            worktree_output=worktree_output,
        )
        env = os.environ | {"PATH": f"{bin_dir}:{os.environ['PATH']}"}

        result = subprocess.run(
            ["bash", str(_OBSERVABILITY_DIR / "pipeline_monitor.sh"), "status"],
            cwd=stale,
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0
        assert "post_commit_pending" in result.stdout

    def test_pipeline_monitor_status_prefers_freshest_active_worktree_when_multiple_active_worktrees_exist(self, tmp_path):
        common = tmp_path / "common"
        common.mkdir()
        active_one = tmp_path / "active-one"
        active_two = tmp_path / "active-two"
        active_one.mkdir()
        active_two.mkdir()
        self._minimal_bus(active_one)
        self._minimal_bus(active_two)
        self._install_observability_script(active_two, "pipeline_status.sh")
        self._write_commit_state(active_one, status="post_commit_pending")
        self._write_commit_state(active_two, status="bot_findings_pending")
        self._set_age_seconds(
            active_one / ".agent_bus" / "executors" / "commit_executor_test.json",
            age_seconds=15 * 60,
        )
        worktree_output = (
            f"worktree {common}\n"
            "bare\n\n"
            f"worktree {active_one}\n"
            "HEAD 1111111111111111\n"
            "branch refs/heads/jabramsja/active-one\n\n"
            f"worktree {active_two}\n"
            "HEAD 2222222222222222\n"
            "branch refs/heads/jabramsja/active-two\n"
        )
        bin_dir = self._fake_git_dir(
            tmp_path,
            show_toplevel=None,
            branch="jabramsja/missing-wave",
            worktree_output=worktree_output,
        )
        env = os.environ | {"PATH": f"{bin_dir}:{os.environ['PATH']}"}

        result = subprocess.run(
            ["bash", str(_OBSERVABILITY_DIR / "pipeline_monitor.sh"), "status"],
            cwd=common,
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0
        assert "bot_findings_pending" in result.stdout

    def test_pane_findings_renders_fallback_when_no_bridge_rounds_exist(self, tmp_path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        self._install_observability_script(repo_root, "_pane_findings.sh")
        (repo_root / ".agent_bus" / "meta" / "raw").mkdir(parents=True, exist_ok=True)
        (repo_root / ".scratch").mkdir(parents=True, exist_ok=True)
        (repo_root / ".scratch" / "commit_executor_live.log").write_text(
            "[commit-executor] Step 14: waiting for CI on PR #719...\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            ["bash", str(repo_root / "mu" / "tools" / "observability" / "_pane_findings.sh")],
            cwd=repo_root,
            capture_output=True,
            text=True,
            env=os.environ | {"RCX_PANE_ONESHOT": "1", "TERM": "xterm"},
            timeout=10,
        )

        assert result.returncode == 0
        assert "No active Phase A/Phase B bridge rounds" in result.stdout
        assert "Commit path" in result.stdout
        assert "Step 14: waiting for CI on PR #719..." in result.stdout

    def test_pane_findings_renders_latest_meta_review_when_bridge_rounds_are_idle(self, tmp_path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        self._install_observability_script(repo_root, "_pane_findings.sh")
        meta_dir = repo_root / ".agent_bus" / "meta" / "raw"
        meta_dir.mkdir(parents=True, exist_ok=True)
        (repo_root / ".scratch").mkdir(parents=True, exist_ok=True)
        (meta_dir / "meta-wave.txt").write_text(
            "BEGIN_META_ENVELOPE\n"
            '{\n'
            '  "decision": "COMMIT_GO",\n'
            '  "summary": "Bounded review closed cleanly."\n'
            '}\n'
            "END_META_ENVELOPE\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            ["bash", str(repo_root / "mu" / "tools" / "observability" / "_pane_findings.sh")],
            cwd=repo_root,
            capture_output=True,
            text=True,
            env=os.environ | {"RCX_PANE_ONESHOT": "1", "TERM": "xterm"},
            timeout=10,
        )

        assert result.returncode == 0
        assert "Latest meta review" in result.stdout
        assert "COMMIT_GO" in result.stdout
        assert "Bounded review closed cleanly." in result.stdout

    def test_pane_findings_uses_active_worktree_when_current_root_is_quiet(self, tmp_path):
        quiet = tmp_path / "quiet"
        active = tmp_path / "active"
        quiet.mkdir()
        active.mkdir()
        self._minimal_bus(quiet)
        self._minimal_bus(active)
        self._write_commit_state(active, status="post_commit_pending")
        self._install_observability_script(quiet, "_pane_findings.sh")
        self._install_observability_script(quiet, "pipeline_status.sh")
        raw_dir = active / ".agent_bus" / "raw" / "phase-a-r1-1234abcd"
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "phase-a-r1-1234abcd--r1-reviewer.txt").write_text(
            "BEGIN_AGENT_ENVELOPE\n"
            '{\n'
            '  "decision": "REQUEST_CHANGES",\n'
            '  "summary": "Stub packet rejected until the real plan is written.",\n'
            '  "findings": [\n'
            '    {"disposition": "blocking", "severity": "high", "title": "Replace stub with real plan"}\n'
            '  ]\n'
            '}\n'
            "END_AGENT_ENVELOPE\n",
            encoding="utf-8",
        )
        worktree_output = (
            f"worktree {quiet}\n"
            "HEAD 1111111111111111\n"
            "branch refs/heads/jabramsja/quiet-wave\n\n"
            f"worktree {active}\n"
            "HEAD 2222222222222222\n"
            "branch refs/heads/jabramsja/active-wave\n"
        )
        bin_dir = self._fake_git_dir(
            tmp_path,
            show_toplevel=str(quiet),
            branch="jabramsja/quiet-wave",
            worktree_output=worktree_output,
        )
        env = os.environ | {
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "RCX_PANE_ONESHOT": "1",
            "TERM": "xterm",
        }

        result = subprocess.run(
            ["bash", str(quiet / "mu" / "tools" / "observability" / "_pane_findings.sh")],
            cwd=quiet,
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )

        assert result.returncode == 0
        clean_stdout = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", result.stdout)
        assert "Watching: jabramsja/active-wave" in clean_stdout
        assert "REQUEST_CHANGES" in clean_stdout
        assert "Meaning: Needs fixes before continuing." in clean_stdout

    def test_pane_processes_ignores_unrelated_global_codex_session_logs(self, tmp_path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        self._minimal_bus(repo_root)
        self._install_observability_script(repo_root, "_pane_processes.sh")
        self._install_observability_script(repo_root, "pipeline_status.sh")
        self._install_observability_script(repo_root, "pipeline_dashboard.py")

        fake_home = tmp_path / "home"
        codex_dir = fake_home / ".codex" / "sessions" / datetime.now().strftime("%Y/%m/%d")
        codex_dir.mkdir(parents=True, exist_ok=True)
        (codex_dir / "unrelated.jsonl").write_text(
            json.dumps(
                {
                    "timestamp": "2026-04-04T06:00:00Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "content": [{"text": "unrelated global codex session"}],
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

        bin_dir = self._fake_git_dir(
            tmp_path,
            show_toplevel=str(repo_root),
            branch="jabramsja/repo-wave",
            worktree_output=f"worktree {repo_root}\nHEAD 1111111111111111\nbranch refs/heads/jabramsja/repo-wave\n",
        )
        env = os.environ | {
            "HOME": str(fake_home),
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "RCX_PANE_ONESHOT": "1",
            "TERM": "xterm",
        }

        result = subprocess.run(
            ["bash", str(repo_root / "mu" / "tools" / "observability" / "_pane_processes.sh")],
            cwd=repo_root,
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )

        assert result.returncode == 0
        clean_stdout = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", result.stdout)
        assert "Pipeline is idle. No active work." in clean_stdout
        assert "unrelated global codex session" not in clean_stdout

    def test_pane_processes_uses_local_dashboard_code_for_active_worktree_data(self, tmp_path):
        quiet = tmp_path / "quiet"
        active = tmp_path / "active"
        quiet.mkdir()
        active.mkdir()
        self._minimal_bus(quiet)
        self._minimal_bus(active)
        self._write_commit_state(active, status="post_commit_pending")
        self._install_observability_script(quiet, "_pane_processes.sh")
        self._install_observability_script(quiet, "pipeline_status.sh")
        self._install_observability_script(quiet, "pipeline_dashboard.py")

        recovery_dir = active / ".agent_bus" / "recovery"
        recovery_dir.mkdir(parents=True, exist_ok=True)
        (recovery_dir / "recovery_status.json").write_text(
            json.dumps(
                {
                    "active": True,
                    "tier": 3,
                    "failure_class": "agent_review_crash",
                    "wave_id": "wave-active",
                    "wave_invocation_count": 2,
                    "tuple_attempt_index": 1,
                    "retry_target": "phase_b_executor",
                    "state": "tier3_waiting_on_claude",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "invocation_id": "wave-active-phase_b_executor-agent_review_crash-01",
                }
            ),
            encoding="utf-8",
        )

        worktree_output = (
            f"worktree {quiet}\n"
            "HEAD 1111111111111111\n"
            "branch refs/heads/jabramsja/quiet-wave\n\n"
            f"worktree {active}\n"
            "HEAD 2222222222222222\n"
            "branch refs/heads/jabramsja/active-wave\n"
        )
        bin_dir = self._fake_git_dir(
            tmp_path,
            show_toplevel=str(quiet),
            branch="jabramsja/quiet-wave",
            worktree_output=worktree_output,
        )
        env = os.environ | {
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "RCX_PANE_ONESHOT": "1",
            "TERM": "xterm",
        }

        result = subprocess.run(
            ["bash", str(quiet / "mu" / "tools" / "observability" / "_pane_processes.sh")],
            cwd=quiet,
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )

        assert result.returncode == 0
        clean_stdout = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", result.stdout)
        assert "Watching: jabramsja/active-wave" in clean_stdout
        assert "ACTIVE — Tier 3 recovery (agent_review_crash)" in clean_stdout
        assert "Problem: a review subprocess crashed" in clean_stdout
