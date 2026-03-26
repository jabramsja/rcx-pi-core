"""Tests for supervision_poll.py — read-only poller for long-running executor runs.

Covers:
1. poll_snapshot produces valid structure with process and artifact data
2. stale_run detection triggers after threshold
3. aggregation_hang detection triggers when root alive but no children + idle
4. process_exited detection when root PID is gone
5. --once mode stops after one snapshot
6. artifact polling picks up .scratch logs
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from mu.tests.tools.module_loader import load_module

_EXECUTORS_DIR = Path(__file__).resolve().parent.parent.parent / "tools" / "executors"
poll_mod = load_module("supervision_poll", _EXECUTORS_DIR / "supervision_poll.py")


class TestArtifactSnapshot:
    """_artifact_snapshot returns size and mtime for existing files."""

    def test_missing_file_returns_not_exists(self, tmp_path):
        snap = poll_mod._artifact_snapshot(tmp_path / "nope.json")  # ANTICHEAT_OK: testing internal supervision functions
        assert snap["exists"] is False
        assert snap["size"] == 0

    def test_existing_file_returns_size_and_mtime(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text('{"key": "val"}')
        snap = poll_mod._artifact_snapshot(f)  # ANTICHEAT_OK: testing internal supervision functions
        assert snap["exists"] is True
        assert snap["size"] > 0
        assert snap["mtime"] is not None


class TestPollArtifacts:
    """_poll_artifacts returns snapshots for key artifact paths."""

    def test_returns_expected_keys(self, tmp_path):
        artifacts = poll_mod._poll_artifacts(tmp_path)  # ANTICHEAT_OK: testing internal supervision functions
        assert "findings" in artifacts
        assert "phase_b_state" in artifacts
        assert "phase_b_handoff" in artifacts
        assert "pre_commit_receipt" in artifacts

    def test_picks_up_scratch_logs(self, tmp_path):
        scratch = tmp_path / ".scratch"
        scratch.mkdir()
        (scratch / "phase_b_agent_review_abc12345.stdout.log").write_text("output")
        (scratch / "phase_b_agent_review_abc12345.stderr.log").write_text("errors")
        (scratch / "phase_b_agent_review_abc12345.status.json").write_text("{}")
        artifacts = poll_mod._poll_artifacts(tmp_path)  # ANTICHEAT_OK: testing internal supervision functions
        assert "latest_stdout_log" in artifacts
        assert "latest_stderr_log" in artifacts
        assert "latest_status" in artifacts

    def test_prefers_newest_artifact_by_mtime_not_name(self, tmp_path):
        scratch = tmp_path / ".scratch"
        scratch.mkdir()
        older = scratch / "phase_b_agent_review_zzz.stdout.log"
        newer = scratch / "phase_b_agent_review_aaa.stdout.log"
        older.write_text("old")
        newer.write_text("newer-log")
        now = time.time()
        older_mtime = now - 60
        newer_mtime = now - 1
        import os
        os.utime(older, (older_mtime, older_mtime))
        os.utime(newer, (newer_mtime, newer_mtime))

        artifacts = poll_mod._poll_artifacts(tmp_path)  # ANTICHEAT_OK: testing internal supervision functions
        assert artifacts["latest_stdout_log"]["size"] == len("newer-log")

    def test_bound_artifacts_override_newer_global_artifacts(self, tmp_path):
        scratch = tmp_path / ".scratch"
        scratch.mkdir()
        bound_stdout = scratch / "phase_b_agent_review_bound.stdout.log"
        newer_stdout = scratch / "phase_b_agent_review_newer.stdout.log"
        bound_stderr = scratch / "phase_b_agent_review_bound.stderr.log"
        newer_stderr = scratch / "phase_b_agent_review_newer.stderr.log"
        bound_status = scratch / "phase_b_agent_review_bound.status.json"
        newer_status = scratch / "phase_b_agent_review_newer.status.json"
        bound_stdout.write_text("bound-out")
        newer_stdout.write_text("newer-out")
        bound_stderr.write_text("bound-err")
        newer_stderr.write_text("newer-err")
        bound_status.write_text(json.dumps({"phase_label": "bound"}))
        newer_status.write_text(json.dumps({"phase_label": "newer"}))
        now = time.time()
        import os
        os.utime(bound_stdout, (now - 60, now - 60))
        os.utime(bound_stderr, (now - 60, now - 60))
        os.utime(bound_status, (now - 60, now - 60))
        os.utime(newer_stdout, (now - 1, now - 1))
        os.utime(newer_stderr, (now - 1, now - 1))
        os.utime(newer_status, (now - 1, now - 1))

        artifacts = poll_mod._poll_artifacts(  # ANTICHEAT_OK: testing internal supervision functions
            tmp_path,
            {
                "stdout_log": bound_stdout,
                "stderr_log": bound_stderr,
                "status_path": bound_status,
            },
        )
        assert artifacts["latest_stdout_log"]["size"] == len("bound-out")
        assert artifacts["latest_stderr_log"]["size"] == len("bound-err")
        assert artifacts["latest_status"]["size"] == bound_status.stat().st_size


class TestPollSnapshot:
    """poll_snapshot produces a valid supervision snapshot."""

    def test_snapshot_without_pid(self, tmp_path):
        snap = poll_mod.poll_snapshot(None, tmp_path)
        assert "timestamp" in snap
        assert "artifacts" in snap
        assert "process" not in snap

    def test_snapshot_with_nonexistent_pid(self, tmp_path):
        # Use a PID that almost certainly doesn't exist
        snap = poll_mod.poll_snapshot(99999999, tmp_path)
        assert "process" in snap
        assert snap["process"]["root_alive"] is False

    def test_snapshot_with_own_pid(self, tmp_path):
        import os
        snap = poll_mod.poll_snapshot(os.getpid(), tmp_path)
        assert snap["process"]["root_alive"] is True
        assert snap["process"]["root_pid"] == os.getpid()


class TestReadStatusFile:
    """_read_status_file reads the latest status JSON from .scratch."""

    def test_no_scratch_dir(self, tmp_path):
        result = poll_mod._read_status_file(tmp_path)  # ANTICHEAT_OK: testing internal supervision functions
        assert result == {}

    def test_reads_latest_status_by_mtime(self, tmp_path):
        scratch = tmp_path / ".scratch"
        scratch.mkdir()
        older = scratch / "phase_b_agent_review_zzz.status.json"
        newer = scratch / "phase_b_agent_review_aaa.status.json"
        older.write_text(json.dumps({"phase_label": "old", "running_agents": ["verifier"]}))
        newer.write_text(json.dumps({"phase_label": "new", "running_agents": ["adversary"]}))
        now = time.time()
        import os
        os.utime(older, (now - 60, now - 60))
        os.utime(newer, (now - 1, now - 1))
        result = poll_mod._read_status_file(tmp_path)  # ANTICHEAT_OK: testing internal supervision functions
        assert result["phase_label"] == "new"

    def test_bound_status_path_beats_newer_unrelated_status(self, tmp_path):
        scratch = tmp_path / ".scratch"
        scratch.mkdir()
        bound = scratch / "phase_b_agent_review_bound.status.json"
        newer = scratch / "phase_b_agent_review_newer.status.json"
        bound.write_text(json.dumps({"phase_label": "bound", "running_agents": ["verifier"]}))
        newer.write_text(json.dumps({"phase_label": "newer", "running_agents": ["adversary"]}))
        now = time.time()
        import os
        os.utime(bound, (now - 60, now - 60))
        os.utime(newer, (now - 1, now - 1))
        result = poll_mod._read_status_file(  # ANTICHEAT_OK: testing internal supervision functions
            tmp_path,
            {"status_path": bound},
        )
        assert result["phase_label"] == "bound"


class TestBoundReviewArtifacts:
    """Explicit or state-bound review artifacts must win over newest-file heuristics."""

    def test_load_bound_review_artifacts_from_state(self, tmp_path):
        state_dir = tmp_path / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        scratch = tmp_path / ".scratch"
        scratch.mkdir()
        status = scratch / "phase_b_agent_review_bound.status.json"
        stdout = scratch / "phase_b_agent_review_bound.stdout.log"
        stderr = scratch / "phase_b_agent_review_bound.stderr.log"
        status.write_text("{}")
        stdout.write_text("out")
        stderr.write_text("err")
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "agent_review_status_path": ".scratch/phase_b_agent_review_bound.status.json",
            "agent_review_stdout_path": ".scratch/phase_b_agent_review_bound.stdout.log",
            "agent_review_stderr_path": ".scratch/phase_b_agent_review_bound.stderr.log",
        }))

        bound = poll_mod._load_bound_review_artifacts(tmp_path)  # ANTICHEAT_OK: testing internal supervision functions
        assert bound["status_path"] == status.resolve()
        assert bound["stdout_log"] == stdout.resolve()
        assert bound["stderr_log"] == stderr.resolve()


class TestArtifactFingerprints:
    """_artifact_fingerprints should treat mtime changes as progress."""

    def test_mtime_change_counts_as_progress(self):
        artifacts_a = {"latest_status": {"size": 100, "mtime": "2026-03-25T09:00:00+00:00"}}
        artifacts_b = {"latest_status": {"size": 100, "mtime": "2026-03-25T09:00:01+00:00"}}
        assert poll_mod._artifact_fingerprints(artifacts_a) != poll_mod._artifact_fingerprints(artifacts_b)  # ANTICHEAT_OK: testing internal supervision functions


class TestPollLoop:
    """poll_loop with --once produces output and stops."""

    def test_once_mode_produces_single_snapshot(self, tmp_path, capsys):
        poll_mod.poll_loop(None, tmp_path, once=True)
        captured = capsys.readouterr()
        snap = json.loads(captured.out)
        assert "timestamp" in snap
        assert "supervision" in snap

    def test_stale_run_detection(self, tmp_path, capsys):
        # With stale_threshold=0, the first poll should immediately be stale
        poll_mod.poll_loop(None, tmp_path, stale_threshold=0.0, once=True)
        captured = capsys.readouterr()
        snap = json.loads(captured.out)
        assert snap["supervision"]["warning"] == "stale_run"

    def test_process_exit_stops_loop(self, tmp_path, capsys):
        # Use a non-existent PID — loop should emit process_exited and stop
        poll_mod.poll_loop(99999999, tmp_path, interval=0.01)
        captured = capsys.readouterr()
        # Output is pretty-printed JSON followed by a plain text line.
        # Extract the first JSON object from the output.
        raw = captured.out.strip()
        # Find the first complete JSON object
        decoder = json.JSONDecoder()
        snap, _ = decoder.raw_decode(raw)
        assert snap["supervision"]["info"] == "process_exited"


def _parse_json_snapshots(raw: str) -> list[dict]:
    """Extract all JSON objects from poll_loop output."""
    decoder = json.JSONDecoder()
    snaps = []
    idx = 0
    while idx < len(raw):
        try:
            obj, end = decoder.raw_decode(raw, idx)
            snaps.append(obj)
            idx = end
            while idx < len(raw) and raw[idx] in (" ", "\n", "\r", "\t"):
                idx += 1
        except json.JSONDecodeError:
            idx += 1
    return snaps


class TestStaleRunSemantics:
    """Stale-run detection must consider status semantics and child-PID changes."""

    def test_heartbeat_rewrite_not_treated_as_progress(self, tmp_path, capsys):
        """Pure heartbeat rewrite of status file (mtime changed, semantic content same)
        must NOT reset the stale timer — it is not real progress."""
        snapshots = [
            {
                "timestamp": "T1",
                "artifacts": {
                    "findings": {"exists": False, "size": 0, "mtime": None},
                    "latest_status": {"exists": True, "size": 100,
                                      "mtime": "2026-03-25T09:00:00+00:00"},
                },
                "review_status": {
                    "phase_label": "running", "running_agents": ["verifier"],
                    "completed_agents": [], "last_progress_timestamp": "",
                },
            },
            {
                "timestamp": "T2",
                "artifacts": {
                    "findings": {"exists": False, "size": 0, "mtime": None},
                    # mtime changed — heartbeat rewrite
                    "latest_status": {"exists": True, "size": 100,
                                      "mtime": "2026-03-25T09:00:30+00:00"},
                },
                # Identical semantic content — no real progress
                "review_status": {
                    "phase_label": "running", "running_agents": ["verifier"],
                    "completed_agents": [], "last_progress_timestamp": "",
                },
            },
        ]
        call_count = [0]

        def mock_snapshot(_pid, _repo):
            idx = min(call_count[0], len(snapshots) - 1)
            call_count[0] += 1
            return snapshots[idx]

        class _BreakLoop(Exception):
            pass

        sleep_count = [0]

        def mock_sleep(_secs):
            sleep_count[0] += 1
            if sleep_count[0] >= 2:
                raise _BreakLoop()

        with patch.object(poll_mod, "poll_snapshot", side_effect=mock_snapshot), \
             patch("time.sleep", side_effect=mock_sleep):
            try:
                poll_mod.poll_loop(None, tmp_path, stale_threshold=0.0, interval=0.001)
            except _BreakLoop:
                pass

        snaps = _parse_json_snapshots(capsys.readouterr().out)
        assert len(snaps) == 2
        # Second snapshot: heartbeat rewrite is not progress, so stale_run persists
        assert snaps[1]["supervision"]["output_changed"] is False
        assert snaps[1]["supervision"]["warning"] == "stale_run"

    def test_child_pid_change_counts_as_progress(self, tmp_path, capsys):
        """Child PID set change must count as progress and prevent stale_run."""
        snapshots = [
            {
                "timestamp": "T1",
                "process": {"root_pid": 100, "root_alive": True,
                            "child_pids": [200], "child_count": 1},
                "artifacts": {"findings": {"exists": False, "size": 0, "mtime": None}},
            },
            {
                "timestamp": "T2",
                "process": {"root_pid": 100, "root_alive": True,
                            "child_pids": [201], "child_count": 1},
                "artifacts": {"findings": {"exists": False, "size": 0, "mtime": None}},
            },
        ]
        call_count = [0]

        def mock_snapshot(_pid, _repo):
            idx = min(call_count[0], len(snapshots) - 1)
            call_count[0] += 1
            return snapshots[idx]

        class _BreakLoop(Exception):
            pass

        sleep_count = [0]

        def mock_sleep(_secs):
            sleep_count[0] += 1
            if sleep_count[0] >= 2:
                raise _BreakLoop()

        with patch.object(poll_mod, "poll_snapshot", side_effect=mock_snapshot), \
             patch("time.sleep", side_effect=mock_sleep):
            try:
                poll_mod.poll_loop(100, tmp_path, stale_threshold=60.0, interval=0.001)
            except _BreakLoop:
                pass

        snaps = _parse_json_snapshots(capsys.readouterr().out)
        assert len(snaps) == 2
        # Second snapshot: child PIDs changed, so output_changed is True
        assert snaps[1]["supervision"]["output_changed"] is True
        # No stale_run warning because progress was detected
        assert "warning" not in snaps[1]["supervision"]

    def test_semantic_status_change_counts_as_progress(self, tmp_path, capsys):
        """Review status semantic change (phase/agents) must count as progress."""
        snapshots = [
            {
                "timestamp": "T1",
                "artifacts": {
                    "findings": {"exists": False, "size": 0, "mtime": None},
                    "latest_status": {"exists": True, "size": 100,
                                      "mtime": "2026-03-25T09:00:00+00:00"},
                },
                "review_status": {
                    "phase_label": "running", "running_agents": ["verifier"],
                    "completed_agents": [], "last_progress_timestamp": "",
                },
            },
            {
                "timestamp": "T2",
                "artifacts": {
                    "findings": {"exists": False, "size": 0, "mtime": None},
                    "latest_status": {"exists": True, "size": 100,
                                      "mtime": "2026-03-25T09:00:30+00:00"},
                },
                # Semantic change: verifier completed, adversary now running
                "review_status": {
                    "phase_label": "running", "running_agents": ["adversary"],
                    "completed_agents": ["verifier"], "last_progress_timestamp": "",
                },
            },
        ]
        call_count = [0]

        def mock_snapshot(_pid, _repo):
            idx = min(call_count[0], len(snapshots) - 1)
            call_count[0] += 1
            return snapshots[idx]

        class _BreakLoop(Exception):
            pass

        sleep_count = [0]

        def mock_sleep(_secs):
            sleep_count[0] += 1
            if sleep_count[0] >= 2:
                raise _BreakLoop()

        with patch.object(poll_mod, "poll_snapshot", side_effect=mock_snapshot), \
             patch("time.sleep", side_effect=mock_sleep):
            try:
                poll_mod.poll_loop(None, tmp_path, stale_threshold=60.0, interval=0.001)
            except _BreakLoop:
                pass

        snaps = _parse_json_snapshots(capsys.readouterr().out)
        assert len(snaps) == 2
        # Second snapshot: semantic status changed, so output_changed is True
        assert snaps[1]["supervision"]["output_changed"] is True
        assert "warning" not in snaps[1]["supervision"]
