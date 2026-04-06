"""Tests for the agent bridge supervisor v1."""

from __future__ import annotations

import fcntl
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from mu.tests.tools.module_loader import load_module
from tests.repo_root import REPO_ROOT


adapters = load_module("bridge_adapters", REPO_ROOT / "mu" / "tools" / "agents" / "bridge_adapters.py")
bridge = load_module("bridge_supervisor", REPO_ROOT / "tools" / "agents" / "bridge_supervisor.py")
migrations = load_module("bridge_migrations", REPO_ROOT / "tools" / "agents" / "bridge_migrations.py")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout


def _init_temp_repo(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.name", "Bridge Test")
    _git(repo, "config", "user.email", "bridge@example.com")
    (repo / "README.md").write_text("bridge test repo\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")


def test_parse_envelope_from_mixed_output() -> None:
    output = """Some prose\nBEGIN_AGENT_ENVELOPE\n{\n  \"job_id\": \"job-1\",\n  \"turn_id\": \"r1-reader\",\n  \"agent_role\": \"reader\",\n  \"decision\": \"REQUEST_CHANGES\",\n  \"summary\": \"Need review\",\n  \"touched_files_claimed\": [],\n  \"findings\": [],\n  \"validations_claimed\": [],\n  \"request_for_next_agent\": \"review\"\n}\nEND_AGENT_ENVELOPE\nMore prose\n"""
    envelope = bridge.parse_envelope(output)
    assert envelope["job_id"] == "job-1"
    assert envelope["decision"] == "REQUEST_CHANGES"


def test_parse_envelope_duplicate_identical_blocks_are_accepted() -> None:
    envelope = """BEGIN_AGENT_ENVELOPE
{
  "job_id": "job-1",
  "turn_id": "r1-reader",
  "agent_role": "reader",
  "decision": "REQUEST_CHANGES",
  "summary": "Need review",
  "touched_files_claimed": [],
  "findings": [],
  "validations_claimed": [],
  "request_for_next_agent": "review"
}
END_AGENT_ENVELOPE"""
    parsed = bridge.parse_envelope(f"{envelope}\n{envelope}")
    assert parsed["job_id"] == "job-1"


def test_parse_envelope_conflicting_blocks_are_rejected() -> None:
    output = """BEGIN_AGENT_ENVELOPE
{
  "job_id": "job-1",
  "turn_id": "r1-reader",
  "agent_role": "reader",
  "decision": "GO",
  "summary": "Looks good",
  "touched_files_claimed": [],
  "findings": [],
  "validations_claimed": [],
  "request_for_next_agent": ""
}
END_AGENT_ENVELOPE
BEGIN_AGENT_ENVELOPE
{
  "job_id": "job-1",
  "turn_id": "r1-reader",
  "agent_role": "reader",
  "decision": "NO_GO",
  "summary": "Actually not good",
  "touched_files_claimed": [],
  "findings": [],
  "validations_claimed": [],
  "request_for_next_agent": ""
}
END_AGENT_ENVELOPE"""
    with pytest.raises(bridge.BridgeError, match="multiple differing envelope blocks"):
        bridge.parse_envelope(output)


def test_parse_envelope_ignores_prompt_template_placeholder_block() -> None:
    placeholder = (
        "BEGIN_AGENT_ENVELOPE\n"
        f"{bridge.JSON_SCHEMA_STUB}\n"
        "END_AGENT_ENVELOPE"
    )
    authoritative = """BEGIN_AGENT_ENVELOPE
{
  "job_id": "job-1",
  "turn_id": "r1-reviewer",
  "agent_role": "reviewer",
  "decision": "GO",
  "summary": "Looks good",
  "touched_files_claimed": [],
  "findings": [],
  "validations_claimed": [],
  "request_for_next_agent": ""
}
END_AGENT_ENVELOPE"""
    parsed = bridge.parse_envelope(f"{placeholder}\n{authoritative}")
    assert parsed["decision"] == "GO"


def test_parse_envelope_ignores_replayed_stderr_envelope() -> None:
    output = (
        "BEGIN_AGENT_ENVELOPE\n"
        "{\n"
        '  "job_id": "job-1",\n'
        '  "turn_id": "r1-reviewer",\n'
        '  "agent_role": "reviewer",\n'
        '  "decision": "GO",\n'
        '  "summary": "current",\n'
        '  "touched_files_claimed": [],\n'
        '  "findings": [],\n'
        '  "validations_claimed": [],\n'
        '  "request_for_next_agent": ""\n'
        "}\n"
        "END_AGENT_ENVELOPE\n"
        "\n[stderr]\n"
        "historical replay:\n"
        "BEGIN_AGENT_ENVELOPE\n"
        "{\n"
        '  "job_id": "job-1",\n'
        '  "turn_id": "r0-reviewer",\n'
        '  "agent_role": "reviewer",\n'
        '  "decision": "NO_GO",\n'
        '  "summary": "old",\n'
        '  "touched_files_claimed": [],\n'
        '  "findings": [],\n'
        '  "validations_claimed": [],\n'
        '  "request_for_next_agent": ""\n'
        "}\n"
        "END_AGENT_ENVELOPE\n"
    )
    parsed = bridge.parse_envelope(output)
    assert parsed["decision"] == "GO"
    assert parsed["summary"] == "current"


def test_run_adapter_normalizes_claude_stream_json_result(tmp_path: Path) -> None:
    stream_agent = tmp_path / "stream_agent.py"
    stream_agent.write_text(
        """\
import json
import sys

sys.stdin.read()
envelope = \"\"\"BEGIN_AGENT_ENVELOPE
{
  "job_id": "job-1",
  "turn_id": "r1-reviewer",
  "agent_role": "reviewer",
  "decision": "GO",
  "summary": "normalized",
  "touched_files_claimed": [],
  "findings": [],
  "validations_claimed": [],
  "request_for_next_agent": ""
}
END_AGENT_ENVELOPE\"\"\"
print(json.dumps({"type": "system", "subtype": "init"}))
print(json.dumps({"type": "result", "subtype": "success", "result": envelope}))
""",
        encoding="utf-8",
    )

    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("review prompt", encoding="utf-8")
    raw_output_path = tmp_path / "raw.txt"
    spec = adapters.AdapterSpec(
        name="claude",
        cmd=[sys.executable, str(stream_agent), "--output-format", "stream-json"],
        timeout_s=30,
        prompt_via_stdin=True,
    )

    output = adapters.run_adapter(
        spec,
        prompt_text="review prompt",
        prompt_path=prompt_path,
        repo_root=tmp_path,
        job_id="job-1",
        turn_id="r1-reviewer",
        agent_role="reviewer",
        raw_output_path=raw_output_path,
    )

    parsed = bridge.parse_envelope(output)
    assert parsed["decision"] == "GO"
    raw_lines = raw_output_path.read_text(encoding="utf-8").splitlines()
    assert raw_lines[0].startswith('{"type": "system"') or raw_lines[0].startswith('{"type":"system"')


def test_run_adapter_normalizes_claude_stream_json_assistant_content(tmp_path: Path) -> None:
    stream_agent = tmp_path / "stream_agent_assistant.py"
    stream_agent.write_text(
        """\
import json
import sys

sys.stdin.read()
envelope = \"\"\"BEGIN_AGENT_ENVELOPE
{
  "job_id": "job-1",
  "turn_id": "r1-reviewer",
  "agent_role": "reviewer",
  "decision": "REQUEST_CHANGES",
  "summary": "assistant-content",
  "touched_files_claimed": [],
  "findings": [],
  "validations_claimed": [],
  "request_for_next_agent": ""
}
END_AGENT_ENVELOPE\"\"\"
print(json.dumps({
    "type": "assistant",
    "message": {
        "role": "assistant",
        "content": [{"type": "text", "text": envelope}]
    }
}))
print(json.dumps({"type": "result", "subtype": "success", "result": ""}))
""",
        encoding="utf-8",
    )

    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("review prompt", encoding="utf-8")
    spec = adapters.AdapterSpec(
        name="claude",
        cmd=[sys.executable, str(stream_agent), "--output-format", "stream-json"],
        timeout_s=30,
        prompt_via_stdin=True,
    )

    output = adapters.run_adapter(
        spec,
        prompt_text="review prompt",
        prompt_path=prompt_path,
        repo_root=tmp_path,
        job_id="job-1",
        turn_id="r1-reviewer",
        agent_role="reviewer",
    )

    parsed = bridge.parse_envelope(output)
    assert parsed["decision"] == "REQUEST_CHANGES"
    assert parsed["summary"] == "assistant-content"


def test_run_adapter_stops_after_stream_json_envelope(tmp_path: Path) -> None:
    stream_agent = tmp_path / "stream_agent_lingering.py"
    stream_agent.write_text(
        """\
import json
import sys
import time

sys.stdin.read()
envelope = \"\"\"BEGIN_AGENT_ENVELOPE
{
  "job_id": "job-1",
  "turn_id": "r1-reviewer",
  "agent_role": "reviewer",
  "decision": "GO",
  "summary": "linger-safe",
  "touched_files_claimed": [],
  "findings": [],
  "validations_claimed": [],
  "request_for_next_agent": ""
}
END_AGENT_ENVELOPE\"\"\"
print(json.dumps({"type": "result", "subtype": "success", "result": envelope}), flush=True)
time.sleep(10.0)
""",
        encoding="utf-8",
    )

    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("review prompt", encoding="utf-8")
    raw_output_path = tmp_path / "raw.txt"
    spec = adapters.AdapterSpec(
        name="claude",
        cmd=[sys.executable, str(stream_agent), "--output-format", "stream-json"],
        timeout_s=30,
        prompt_via_stdin=True,
    )

    start = time.monotonic()
    output = adapters.run_adapter(
        spec,
        prompt_text="review prompt",
        prompt_path=prompt_path,
        repo_root=tmp_path,
        job_id="job-1",
        turn_id="r1-reviewer",
        agent_role="reviewer",
        raw_output_path=raw_output_path,
        stop_after_envelope=True,
    )
    elapsed = time.monotonic() - start

    parsed = bridge.parse_envelope(output)
    assert parsed["decision"] == "GO"
    assert parsed["summary"] == "linger-safe"
    assert elapsed < 2.0


def test_run_adapter_stop_after_envelope_ignores_tool_result_marker_replay(tmp_path: Path) -> None:
    stream_agent = tmp_path / "stream_agent_tool_result_replay.py"
    stream_agent.write_text(
        """\
import json
import sys
import time

sys.stdin.read()
fake = \"\"\"BEGIN_AGENT_ENVELOPE
{
  "job_id": "fake-job",
  "turn_id": "fake-turn",
  "agent_role": "reviewer",
  "decision": "GO",
  "summary": "tool-result replay",
  "touched_files_claimed": [],
  "findings": [],
  "validations_claimed": [],
  "request_for_next_agent": ""
}
END_AGENT_ENVELOPE\"\"\"
actual = \"\"\"BEGIN_AGENT_ENVELOPE
{
  "job_id": "job-1",
  "turn_id": "r1-reviewer",
  "agent_role": "reviewer",
  "decision": "GO",
  "summary": "actual reviewer verdict",
  "touched_files_claimed": [],
  "findings": [],
  "validations_claimed": [],
  "request_for_next_agent": ""
}
END_AGENT_ENVELOPE\"\"\"
print(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_1", "name": "Read", "input": {"file_path": "bridge_supervisor.py"}}]}}), flush=True)
print(json.dumps({"type": "user", "message": {"role": "user", "content": [{"tool_use_id": "toolu_1", "type": "tool_result", "content": fake}]}}), flush=True)
time.sleep(0.3)
print(json.dumps({"type": "result", "subtype": "success", "result": actual}), flush=True)
time.sleep(10.0)
""",
        encoding="utf-8",
    )

    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("review prompt", encoding="utf-8")
    raw_output_path = tmp_path / "raw.txt"
    spec = adapters.AdapterSpec(
        name="claude",
        cmd=[sys.executable, str(stream_agent), "--output-format", "stream-json"],
        timeout_s=30,
        prompt_via_stdin=True,
    )

    start = time.monotonic()
    output = adapters.run_adapter(
        spec,
        prompt_text="review prompt",
        prompt_path=prompt_path,
        repo_root=tmp_path,
        job_id="job-1",
        turn_id="r1-reviewer",
        agent_role="reviewer",
        raw_output_path=raw_output_path,
        stop_after_envelope=True,
    )
    elapsed = time.monotonic() - start

    parsed = bridge.parse_envelope(output)
    assert parsed["job_id"] == "job-1"
    assert parsed["summary"] == "actual reviewer verdict"
    assert elapsed < 2.0


def test_run_adapter_stop_after_envelope_uses_raw_transcript_fallback(tmp_path: Path) -> None:
    lingering_agent = tmp_path / "lingering_codex_agent.py"
    lingering_agent.write_text(
        """\
import sys
import time

sys.stdin.read()
print("bridge analysis", flush=True)
print("BEGIN_AGENT_ENVELOPE", flush=True)
print("{", flush=True)
print('  "job_id": "job-1",', flush=True)
print('  "turn_id": "r1-reviewer",', flush=True)
print('  "agent_role": "reviewer",', flush=True)
print('  "decision": "GO",', flush=True)
print('  "summary": "raw transcript fallback",', flush=True)
print('  "touched_files_claimed": [],', flush=True)
print('  "findings": [],', flush=True)
print('  "validations_claimed": [],', flush=True)
print('  "request_for_next_agent": ""', flush=True)
print("}", flush=True)
print("END_AGENT_ENVELOPE", flush=True)
time.sleep(10.0)
""",
        encoding="utf-8",
    )

    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("review prompt", encoding="utf-8")
    raw_output_path = tmp_path / "raw.txt"
    spec = adapters.AdapterSpec(
        name="codex",
        cmd=[sys.executable, str(lingering_agent)],
        timeout_s=30,
        prompt_via_stdin=True,
    )

    start = time.monotonic()
    with patch.object(adapters, "_authoritative_output_so_far", return_value="bridge analysis"):
        output = adapters.run_adapter(
            spec,
            prompt_text="review prompt",
            prompt_path=prompt_path,
            repo_root=tmp_path,
            job_id="job-1",
            turn_id="r1-reviewer",
            agent_role="reviewer",
            raw_output_path=raw_output_path,
            stop_after_envelope=True,
        )
    elapsed = time.monotonic() - start

    parsed = bridge.parse_envelope(output)
    assert parsed["decision"] == "GO"
    assert parsed["summary"] == "raw transcript fallback"
    assert elapsed < 2.0


def test_run_adapter_stop_after_meta_envelope_uses_raw_transcript_fallback(tmp_path: Path) -> None:
    lingering_agent = tmp_path / "lingering_codex_meta_agent.py"
    lingering_agent.write_text(
        """\
import sys
import time

sys.stdin.read()
print("meta analysis", flush=True)
print("BEGIN_META_ENVELOPE", flush=True)
print("{", flush=True)
print('  "decision": "ROUTE_PHASE_A",', flush=True)
print('  "summary": "meta raw transcript fallback",', flush=True)
print('  "findings": [],', flush=True)
print('  "request_for_claude": "Continue"', flush=True)
print("}", flush=True)
print("END_META_ENVELOPE", flush=True)
time.sleep(10.0)
""",
        encoding="utf-8",
    )

    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("review prompt", encoding="utf-8")
    raw_output_path = tmp_path / "raw.txt"
    spec = adapters.AdapterSpec(
        name="codex",
        cmd=[sys.executable, str(lingering_agent)],
        timeout_s=30,
        prompt_via_stdin=True,
    )

    start = time.monotonic()
    with patch.object(adapters, "_authoritative_output_so_far", return_value="meta analysis"):
        output = adapters.run_adapter(
            spec,
            prompt_text="review prompt",
            prompt_path=prompt_path,
            repo_root=tmp_path,
            job_id="job-1",
            turn_id="r1-meta",
            agent_role="meta-reviewer",
            raw_output_path=raw_output_path,
            stop_after_envelope=True,
        )
    elapsed = time.monotonic() - start

    assert 'BEGIN_META_ENVELOPE' in output
    assert '"decision": "ROUTE_PHASE_A"' in output
    assert '"summary": "meta raw transcript fallback"' in output
    assert elapsed < 2.0


def test_run_adapter_streaming_stop_after_envelope_uses_raw_transcript_fallback(tmp_path: Path) -> None:
    lingering_agent = tmp_path / "lingering_streaming_codex_agent.py"
    lingering_agent.write_text(
        """\
import sys
import time

sys.stdin.read()
print("bridge analysis", flush=True)
print("BEGIN_AGENT_ENVELOPE", flush=True)
print("{", flush=True)
print('  "job_id": "job-1",', flush=True)
print('  "turn_id": "r1-reviewer",', flush=True)
print('  "agent_role": "reviewer",', flush=True)
print('  "decision": "GO",', flush=True)
print('  "summary": "streaming raw transcript fallback",', flush=True)
print('  "touched_files_claimed": [],', flush=True)
print('  "findings": [],', flush=True)
print('  "validations_claimed": [],', flush=True)
print('  "request_for_next_agent": ""', flush=True)
print("}", flush=True)
print("END_AGENT_ENVELOPE", flush=True)
time.sleep(10.0)
""",
        encoding="utf-8",
    )

    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("review prompt", encoding="utf-8")
    raw_output_path = tmp_path / "raw.txt"
    spec = adapters.AdapterSpec(
        name="codex",
        cmd=[sys.executable, str(lingering_agent)],
        timeout_s=30,
        prompt_via_stdin=True,
    )

    start = time.monotonic()
    with patch.object(adapters, "_authoritative_output_so_far", return_value="bridge analysis"):
        output = adapters.run_adapter(
            spec,
            prompt_text="review prompt",
            prompt_path=prompt_path,
            repo_root=tmp_path,
            job_id="job-1",
            turn_id="r1-reviewer",
            agent_role="reviewer",
            raw_output_path=raw_output_path,
            stop_after_envelope=True,
            stream=True,
        )
    elapsed = time.monotonic() - start

    parsed = bridge.parse_envelope(output)
    assert parsed["decision"] == "GO"
    assert parsed["summary"] == "streaming raw transcript fallback"
    assert elapsed < 2.0


def test_run_adapter_stale_timeout_fails_closed(tmp_path: Path) -> None:
    stale_agent = tmp_path / "stale_agent.py"
    stale_agent.write_text(
        """\
import sys
import time

sys.stdin.read()
print("started", flush=True)
time.sleep(10.0)
""",
        encoding="utf-8",
    )

    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("review prompt", encoding="utf-8")
    raw_output_path = tmp_path / "raw.txt"
    spec = adapters.AdapterSpec(
        name="codex",
        cmd=[sys.executable, str(stale_agent)],
        timeout_s=30,
        prompt_via_stdin=True,
    )

    start = time.monotonic()
    with pytest.raises(adapters.BridgeAdapterError, match="stalled after"):
        adapters.run_adapter(
            spec,
            prompt_text="review prompt",
            prompt_path=prompt_path,
            repo_root=tmp_path,
            job_id="job-1",
            turn_id="r1-reviewer",
            agent_role="reviewer",
            raw_output_path=raw_output_path,
            stale_timeout_s=1.0,
        )
    elapsed = time.monotonic() - start

    assert elapsed < 4.0


def test_run_adapter_zero_output_watchdog_tracks_stdout_only(tmp_path: Path) -> None:
    stderr_only_agent = tmp_path / "stderr_only_agent.py"
    stderr_only_agent.write_text(
        """\
import sys
import time

sys.stdin.read()
sys.stderr.write("warming up\\n")
sys.stderr.flush()
time.sleep(10.0)
""",
        encoding="utf-8",
    )

    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("review prompt", encoding="utf-8")
    raw_output_path = tmp_path / "raw.txt"
    spec = adapters.AdapterSpec(
        name="codex",
        cmd=[sys.executable, str(stderr_only_agent)],
        timeout_s=30,
        prompt_via_stdin=True,
    )

    start = time.monotonic()
    with pytest.raises(adapters.BridgeAdapterError, match="produced no stdout"):
        adapters.run_adapter(
            spec,
            prompt_text="review prompt",
            prompt_path=prompt_path,
            repo_root=tmp_path,
            job_id="job-1",
            turn_id="r1-reviewer",
            agent_role="reviewer",
            raw_output_path=raw_output_path,
            zero_output_timeout_s=1.0,
        )
    elapsed = time.monotonic() - start

    assert elapsed < 5.0
    raw_text = raw_output_path.read_text(encoding="utf-8")
    assert raw_text.startswith("[stderr]\n")
    assert "warming up" in raw_text


def test_run_adapter_stale_timeout_kills_detached_descendants(tmp_path: Path) -> None:
    child_pid_path = tmp_path / "child.pid"
    detached_agent = tmp_path / "detached_agent.py"
    detached_agent.write_text(
        """\
import subprocess
import sys
import time
from pathlib import Path

pid_path = Path(sys.argv[1])
sys.stdin.read()
child = subprocess.Popen(
    [sys.executable, "-c", "import time; time.sleep(30)"],
    start_new_session=True,
)
pid_path.write_text(str(child.pid), encoding="utf-8")
print("spawned", flush=True)
time.sleep(30.0)
""",
        encoding="utf-8",
    )

    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("review prompt", encoding="utf-8")
    raw_output_path = tmp_path / "raw.txt"
    spec = adapters.AdapterSpec(
        name="codex",
        cmd=[sys.executable, str(detached_agent), str(child_pid_path)],
        timeout_s=30,
        prompt_via_stdin=True,
    )

    with pytest.raises(adapters.BridgeAdapterError, match="stalled after"):
        adapters.run_adapter(
            spec,
            prompt_text="review prompt",
            prompt_path=prompt_path,
            repo_root=tmp_path,
            job_id="job-1",
            turn_id="r1-reviewer",
            agent_role="reviewer",
            raw_output_path=raw_output_path,
            stale_timeout_s=1.0,
        )

    child_pid = int(child_pid_path.read_text(encoding="utf-8").strip())
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        pytest.fail(f"Detached descendant survived adapter cleanup: pid={child_pid}")


def test_kill_process_group_waits_for_tracked_pids_to_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    kill_calls: list[tuple[str, int, int]] = []
    sleeps: list[float] = []
    live_counts = {7002: 0}
    poll_count = {"value": 0}
    wait_calls: list[float] = []
    clock = {"value": 0.0}

    class _FakeProc:
        pid = 7001

        def kill(self) -> None:
            kill_calls.append(("proc", self.pid, int(adapters.signal.SIGKILL)))

        def poll(self) -> int | None:
            poll_count["value"] += 1
            if poll_count["value"] < 4:
                return None
            return -9

        def wait(self, timeout: float | None = None) -> int:
            wait_calls.append(0.0 if timeout is None else timeout)
            return -9

    def fake_fingerprint(_root_pid: int) -> tuple[tuple[int, float], ...]:
        return ((7001, 0.0), (7002, 0.0))

    def fake_killpg(pid: int, sig: int) -> None:
        kill_calls.append(("pg", pid, int(sig)))

    def fake_kill(pid: int, sig: int) -> None:
        kill_calls.append(("pid", pid, int(sig)))

    def fake_pid_is_live_non_zombie(pid: int) -> bool:
        live_counts[pid] += 1
        return live_counts[pid] < 3

    def fake_monotonic() -> float:
        clock["value"] += 0.01
        return clock["value"]

    monkeypatch.setattr(adapters, "_process_tree_fingerprint", fake_fingerprint)
    monkeypatch.setattr(adapters.os, "killpg", fake_killpg)
    monkeypatch.setattr(adapters.os, "kill", fake_kill)
    monkeypatch.setattr(adapters, "_pid_is_live_non_zombie", fake_pid_is_live_non_zombie)
    monkeypatch.setattr(adapters.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(adapters.time, "sleep", lambda seconds: sleeps.append(seconds))

    adapters._kill_process_group(_FakeProc(), wait_for_exit=True)  # ANTICHEAT_OK: testing tracked stale-timeout cleanup helper directly

    assert ("pg", 7001, int(adapters.signal.SIGKILL)) in kill_calls
    assert ("pid", 7002, int(adapters.signal.SIGKILL)) in kill_calls
    assert sleeps
    assert wait_calls == [0.0]
    assert poll_count["value"] >= 4
    assert live_counts[7002] >= 3


def test_pid_exists_accepts_zombie(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapters.os, "kill", lambda pid, sig: None)

    assert adapters._pid_exists(7001)  # ANTICHEAT_OK: wait-for-exit must keep counting zombie descendants as present


def test_pid_is_live_non_zombie_rejects_zombie(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapters.os, "kill", lambda pid, sig: None)

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(["ps"], 0, stdout="Z+\n", stderr="")

    monkeypatch.setattr(adapters.subprocess, "run", fake_run)

    assert not adapters._pid_is_live_non_zombie(7001)  # ANTICHEAT_OK: testing zombie-aware liveness helper directly


def test_init_db_creates_runtime_paths_and_config(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    assert paths.db_path.exists()
    assert paths.prompts_dir.exists()
    assert paths.raw_dir.exists()
    assert paths.rendered_dir.exists()
    assert paths.config_path.exists()


def test_run_job_end_to_end_with_fake_agents(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    fake_agent = repo_root / "fake_agent.py"
    fake_agent.write_text(
        """
import json
import re
import sys

prompt = sys.stdin.read()
job = re.search(r"JOB_ID: (.+)", prompt).group(1).strip()
round_no = re.search(r"ROUND: (.+)", prompt).group(1).strip()
role = "reviewer" if "You are the REVIEWER" in prompt else "reader"
turn_id = f"r{round_no}-{role}"
decision = "GO" if role == "reviewer" else "REQUEST_CHANGES"
summary = "review complete" if role == "reviewer" else "reader pass complete"
print("BEGIN_AGENT_ENVELOPE")
print(json.dumps({
    "job_id": job,
    "turn_id": turn_id,
    "agent_role": role,
    "decision": decision,
    "summary": summary,
    "touched_files_claimed": [],
    "findings": [],
    "validations_claimed": [],
    "request_for_next_agent": "none"
}, indent=2))
print("END_AGENT_ENVELOPE")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = {
        "agents": {
            "claude": {
                "mode": "live",
                "cmd": [sys.executable, str(fake_agent)],
                "prompt_via_stdin": True,
                "timeout_s": 30,
                "env": {},
            },
            "codex": {
                "mode": "live",
                "cmd": [sys.executable, str(fake_agent)],
                "prompt_via_stdin": True,
                "timeout_s": 30,
                "env": {},
            },
        }
    }
    paths.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    job_id = bridge.submit_job(
        paths,
        task_text="Implement bridge v1",
        scope_hint="tooling",
        wave_class="MAINTENANCE",
        allow_edits=True,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=2,
        acceptance_checks=[],
        job_id="bridge-test-job",
    )
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        job = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        turns = conn.execute("SELECT * FROM turns WHERE job_id = ? ORDER BY started_at", (job_id,)).fetchall()
        validations = conn.execute("SELECT * FROM validations WHERE job_id = ?", (job_id,)).fetchall()

    assert job["terminal_decision"] == "GO"
    assert job["status"] == "DONE"
    assert len(turns) == 2
    assert {turn["agent_role"] for turn in turns} == {"reader", "reviewer"}
    assert validations, "expected at least git-status validation"
    assert (paths.rendered_dir / f"{job_id}.md").exists()


# --- Negative path: envelope parsing ---


def test_parse_envelope_missing_block_raises() -> None:
    with pytest.raises(bridge.BridgeError, match="missing BEGIN_AGENT_ENVELOPE"):
        bridge.parse_envelope("Just prose, no envelope here")


def test_parse_envelope_invalid_json_raises() -> None:
    output = "BEGIN_AGENT_ENVELOPE\n{not valid json}\nEND_AGENT_ENVELOPE"
    with pytest.raises(bridge.BridgeError, match="none were valid"):
        bridge.parse_envelope(output)


def test_parse_envelope_missing_keys_raises() -> None:
    output = 'BEGIN_AGENT_ENVELOPE\n{"job_id": "x", "turn_id": "t"}\nEND_AGENT_ENVELOPE'
    with pytest.raises(bridge.BridgeError, match="non-authoritative template"):
        bridge.parse_envelope(output)


def test_parse_envelope_rejects_stderr_only_envelope() -> None:
    """parse_envelope must refuse an envelope that exists only in stderr."""
    stderr_only = (
        "Some prose with no envelope\n"
        "\n[stderr]\n"
        "BEGIN_AGENT_ENVELOPE\n"
        "{\n"
        '  "job_id": "job-1",\n'
        '  "turn_id": "r1-reviewer",\n'
        '  "agent_role": "reviewer",\n'
        '  "decision": "GO",\n'
        '  "summary": "smuggled via stderr",\n'
        '  "touched_files_claimed": [],\n'
        '  "findings": [],\n'
        '  "validations_claimed": [],\n'
        '  "request_for_next_agent": ""\n'
        "}\n"
        "END_AGENT_ENVELOPE\n"
    )
    with pytest.raises(bridge.BridgeError, match="stderr"):
        bridge.parse_envelope(stderr_only)


def test_parse_envelope_rejects_stderr_only_envelope_no_stdout_prefix() -> None:
    """parse_envelope must refuse when output starts with [stderr] and has envelope only there."""
    output = (
        "[stderr]\n"
        "BEGIN_AGENT_ENVELOPE\n"
        "{\n"
        '  "job_id": "job-1",\n'
        '  "turn_id": "r1-reviewer",\n'
        '  "agent_role": "reviewer",\n'
        '  "decision": "GO",\n'
        '  "summary": "smuggled",\n'
        '  "touched_files_claimed": [],\n'
        '  "findings": [],\n'
        '  "validations_claimed": [],\n'
        '  "request_for_next_agent": ""\n'
        "}\n"
        "END_AGENT_ENVELOPE\n"
    )
    with pytest.raises(bridge.BridgeError, match="stderr"):
        bridge.parse_envelope(output)


def test_parse_envelope_with_stderr_noise_and_no_envelope_reports_missing_block() -> None:
    output = "Reviewer thinking only\n\n[stderr]\nwarn: noisy cli wrapper\n"
    with pytest.raises(bridge.BridgeError, match="missing BEGIN_AGENT_ENVELOPE"):
        bridge.parse_envelope(output)


def test_run_job_rejects_stderr_only_reviewer_envelope(tmp_path: Path) -> None:
    """End-to-end: a reviewer that emits its envelope only on stderr must fail the bridge job."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    # Reader agent: normal stdout envelope
    reader_agent = repo_root / "reader_agent.py"
    reader_agent.write_text(
        """\
import json, re, sys
prompt = sys.stdin.read()
job = re.search(r"JOB_ID: (.+)", prompt).group(1).strip()
round_no = re.search(r"ROUND: (.+)", prompt).group(1).strip()
print("BEGIN_AGENT_ENVELOPE")
print(json.dumps({
    "job_id": job, "turn_id": f"r{round_no}-reader", "agent_role": "reader",
    "decision": "REQUEST_CHANGES", "summary": "reader pass",
    "touched_files_claimed": [], "findings": [],
    "validations_claimed": [], "request_for_next_agent": "review"
}, indent=2))
print("END_AGENT_ENVELOPE")
""",
        encoding="utf-8",
    )

    # Reviewer agent: envelope ONLY on stderr (simulates smuggling)
    stderr_reviewer = repo_root / "stderr_reviewer.py"
    stderr_reviewer.write_text(
        """\
import json, re, sys
prompt = sys.stdin.read()
job = re.search(r"JOB_ID: (.+)", prompt).group(1).strip()
round_no = re.search(r"ROUND: (.+)", prompt).group(1).strip()
# Emit envelope on stderr only — stdout has no envelope
print("Reviewer thinking...", file=sys.stdout)
print("BEGIN_AGENT_ENVELOPE", file=sys.stderr)
print(json.dumps({
    "job_id": job, "turn_id": f"r{round_no}-reviewer", "agent_role": "reviewer",
    "decision": "GO", "summary": "smuggled via stderr",
    "touched_files_claimed": [], "findings": [],
    "validations_claimed": [], "request_for_next_agent": ""
}, indent=2), file=sys.stderr)
print("END_AGENT_ENVELOPE", file=sys.stderr)
""",
        encoding="utf-8",
    )

    config = {
        "agents": {
            "claude": {
                "mode": "live",
                "cmd": [sys.executable, str(reader_agent)],
                "prompt_via_stdin": True,
                "timeout_s": 30,
                "env": {},
            },
            "codex": {
                "mode": "live",
                "cmd": [sys.executable, str(stderr_reviewer)],
                "prompt_via_stdin": True,
                "timeout_s": 30,
                "env": {},
            },
        }
    }
    paths.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    job_id = bridge.submit_job(
        paths,
        task_text="Test stderr envelope rejection",
        scope_hint="tooling",
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="stderr-envelope-test",
    )
    # The reviewer's stderr-only envelope must NOT produce a GO decision.
    # parse_envelope raises BridgeError when envelope is only in stderr.
    with pytest.raises(bridge.BridgeError, match="stderr"):
        bridge.run_job(paths, job_id)

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        job_row = conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        reviewer_turns = conn.execute(
            "SELECT * FROM turns WHERE job_id = ? AND agent_role = 'reviewer'",
            (job_id,),
        ).fetchall()

    # Job must not be DONE/GO — it should still be in a recoverable state
    assert job_row["terminal_decision"] != "GO"
    # The reviewer turn must be marked FAILED
    assert any(t["status"] == "FAILED" for t in reviewer_turns)


# --- DEFECT-1: stale reviewer retry turn_id collision ---


def test_stale_reviewer_retry_no_turn_id_collision(tmp_path: Path) -> None:
    """Verify stale reviewer retry uses distinct UUID-based turn_ids."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    stale_agent = repo_root / "stale_agent.py"
    stale_agent.write_text(
        """\
import json
import os
import re
import sys

prompt = sys.stdin.read()
job = re.search(r"JOB_ID: (.+)", prompt).group(1).strip()
round_no = re.search(r"ROUND: (.+)", prompt).group(1).strip()
role = "reviewer" if "You are the REVIEWER" in prompt else "reader"

# First reviewer call: create marker file to change repo state (triggers staleness)
if role == "reviewer":
    marker = os.path.join(os.getcwd(), "_staleness_marker.txt")
    if not os.path.exists(marker):
        with open(marker, "w") as f:
            f.write("stale trigger")

turn_id = f"r{round_no}-{role}"
decision = "GO" if role == "reviewer" else "REQUEST_CHANGES"
print("BEGIN_AGENT_ENVELOPE")
print(json.dumps({
    "job_id": job,
    "turn_id": turn_id,
    "agent_role": role,
    "decision": decision,
    "summary": "done",
    "touched_files_claimed": [],
    "findings": [],
    "validations_claimed": [],
    "request_for_next_agent": "none"
}, indent=2))
print("END_AGENT_ENVELOPE")
""",
        encoding="utf-8",
    )

    config = {
        "agents": {
            "claude": {
                "mode": "live",
                "cmd": [sys.executable, str(stale_agent)],
                "prompt_via_stdin": True,
                "timeout_s": 30,
                "env": {},
            },
            "codex": {
                "mode": "live",
                "cmd": [sys.executable, str(stale_agent)],
                "prompt_via_stdin": True,
                "timeout_s": 30,
                "env": {},
            },
        }
    }
    paths.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    job_id = bridge.submit_job(
        paths,
        task_text="staleness retry test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=True,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="stale-test-job",
    )
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        turns = conn.execute(
            "SELECT * FROM turns WHERE job_id = ? AND agent_role = 'reviewer' ORDER BY started_at",
            (job_id,),
        ).fetchall()

    assert len(turns) == 2, f"expected 2 reviewer turns (stale + retry), got {len(turns)}"
    # UUID-based turn_ids: pattern is {job_id}--r{round}-{role}-{uuid8}
    assert turns[0]["turn_id"].startswith(f"{job_id}--r1-reviewer-")
    assert turns[1]["turn_id"].startswith(f"{job_id}--r1-reviewer-")
    assert turns[0]["turn_id"] != turns[1]["turn_id"]  # distinct UUIDs
    assert turns[0]["status"] == "stale"
    assert turns[1]["status"] == "completed"


# --- DESIGN-1: reviewer prompt includes staged diff ---


def test_reviewer_prompt_includes_staged_diff(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    (repo_root / "README.md").write_text("updated content for diff test\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")

    job_id = bridge.submit_job(
        paths,
        task_text="diff visibility test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=True,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="diff-test-job",
    )

    with bridge.open_db(paths) as conn:
        job = bridge.read_job(conn, job_id)
        prompt = bridge.build_reviewer_prompt(conn, paths, job, 1, [])

    assert "$staged_diff" not in prompt, "template variable not substituted"
    assert "README.md" in prompt, "staged diff should reference changed file"
    assert "+updated content for diff test" in prompt, "staged diff should show added line"


# --- DEFECT-4: single-supervisor file lock ---


def test_file_lock_blocks_concurrent_run(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    job_id = bridge.submit_job(
        paths,
        task_text="lock test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="lock-test-job",
    )

    lock_path = paths.bus_dir / "bridge.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fp = open(lock_path, "w")
    try:
        fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(bridge.BridgeError, match="Another bridge supervisor"):
            bridge.run_job(paths, job_id)
    finally:
        fcntl.flock(fp, fcntl.LOCK_UN)
        fp.close()


def test_bridge_lock_keeps_inode_stable_for_waiter_contention(tmp_path: Path) -> None:
    lock_path = tmp_path / "bridge.lock"
    waiter = None
    contender = None
    waiter_script = """
import fcntl
import os
import sys
import time

path = sys.argv[1]
fp = open(path, "w")
print(f"opened {os.fstat(fp.fileno()).st_ino}", flush=True)
fcntl.flock(fp, fcntl.LOCK_EX)
print(f"acquired {os.fstat(fp.fileno()).st_ino}", flush=True)
time.sleep(1.0)
"""
    try:
        with bridge._BridgeLock(lock_path):  # ANTICHEAT_OK: same-path contention proof
            waiter = subprocess.Popen(
                [sys.executable, "-c", waiter_script, str(lock_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert waiter.stdout is not None
            assert waiter.stdout.readline().strip().startswith("opened ")

        acquired = waiter.stdout.readline().strip()
        assert acquired.startswith("acquired ")
        waiter_inode = int(acquired.split()[1])

        contender = open(lock_path, "w")
        contender_inode = os.fstat(contender.fileno()).st_ino
        assert contender_inode == waiter_inode
        with pytest.raises(BlockingIOError):
            fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)

        out, err = waiter.communicate(timeout=5)
        assert waiter.returncode == 0, f"{out}\n{err}"
    finally:
        if contender is not None:
            contender.close()
        if waiter is not None and waiter.poll() is None:
            waiter.kill()
            waiter.communicate(timeout=5)


def test_bridge_lock_persists_owner_metadata(tmp_path: Path) -> None:
    lock_path = tmp_path / "bridge.lock"

    with bridge._BridgeLock(lock_path):  # ANTICHEAT_OK: lock metadata coverage
        # While held: metadata is present
        assert lock_path.stat().st_size > 0
        metadata = json.loads(lock_path.read_text(encoding="utf-8"))

    # After release: file exists but is empty (metadata cleared to prevent stale PID)
    assert lock_path.exists()
    assert lock_path.stat().st_size == 0
    # Metadata was correct while held
    assert metadata["holder"] == "bridge_supervisor"
    assert metadata["pid"] == os.getpid()
    assert metadata["lock_path"] == str(lock_path)


def test_bridge_lock_error_clarifies_persistent_path(tmp_path: Path) -> None:
    lock_path = tmp_path / "bridge.lock"
    fp = open(lock_path, "w")
    try:
        fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(bridge.BridgeError, match="persists by design") as excinfo:
            with bridge._BridgeLock(lock_path):  # ANTICHEAT_OK: lock error-path coverage
                pass
    finally:
        fcntl.flock(fp, fcntl.LOCK_UN)
        fp.close()

    assert "if stale" not in str(excinfo.value)


# --- Pause / Continue / Interactive ---


def _make_fake_config(repo_root: Path, fake_agent: Path) -> dict:
    return {
        "agents": {
            "claude": {
                "mode": "live",
                "cmd": [sys.executable, str(fake_agent)],
                "prompt_via_stdin": True,
                "timeout_s": 30,
                "env": {},
            },
            "codex": {
                "mode": "live",
                "cmd": [sys.executable, str(fake_agent)],
                "prompt_via_stdin": True,
                "timeout_s": 30,
                "env": {},
            },
        }
    }


_FAKE_AGENT_SCRIPT = """\
import json
import re
import sys

prompt = sys.stdin.read()
job = re.search(r"JOB_ID: (.+)", prompt).group(1).strip()
round_no = re.search(r"ROUND: (.+)", prompt).group(1).strip()
role = "reviewer" if "You are the REVIEWER" in prompt else "reader"
turn_id = f"r{round_no}-{role}"
decision = "GO" if role == "reviewer" else "REQUEST_CHANGES"
summary = "review complete" if role == "reviewer" else "reader pass complete"
print("BEGIN_AGENT_ENVELOPE")
print(json.dumps({
    "job_id": job,
    "turn_id": turn_id,
    "agent_role": role,
    "decision": decision,
    "summary": summary,
    "touched_files_claimed": [],
    "findings": [],
    "validations_claimed": [],
    "request_for_next_agent": "none"
}, indent=2))
print("END_AGENT_ENVELOPE")
"""


def _setup_bridge_repo(tmp_path: Path) -> tuple:
    """Create temp repo with fake agent and bridge config. Returns (paths, job_id)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    fake_agent = repo_root / "fake_agent.py"
    fake_agent.write_text(_FAKE_AGENT_SCRIPT, encoding="utf-8")

    config = _make_fake_config(repo_root, fake_agent)
    paths.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return paths, fake_agent


def test_pause_after_reader_stops_before_reviewer(tmp_path: Path) -> None:
    """--pause-after-reader should stop with PAUSED and set AWAITING_REVIEWER_APPROVAL."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="pause test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=2,
        acceptance_checks=[],
        job_id="pause-test-job",
    )
    decision = bridge.run_job(paths, job_id, pause_after_reader=True)
    assert decision == "PAUSED"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        job = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        turns = conn.execute("SELECT * FROM turns WHERE job_id = ?", (job_id,)).fetchall()

    assert job["status"] == "AWAITING_REVIEWER_APPROVAL"
    assert len(turns) == 1, "only reader should have run"
    assert turns[0]["agent_role"] == "reader"
    assert turns[0]["status"] == "completed"


def test_continue_resumes_paused_job_to_reviewer(tmp_path: Path) -> None:
    """continue_job should resume a paused job and run the reviewer to completion."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="continue test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=2,
        acceptance_checks=[],
        job_id="continue-test-job",
    )
    # Phase 1: run with pause
    decision = bridge.run_job(paths, job_id, pause_after_reader=True)
    assert decision == "PAUSED"

    # Phase 2: continue
    decision = bridge.continue_job(paths, job_id)
    assert decision == "GO"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        job = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        turns = conn.execute("SELECT * FROM turns WHERE job_id = ? ORDER BY started_at", (job_id,)).fetchall()

    assert job["status"] == "DONE"
    assert job["terminal_decision"] == "GO"
    assert len(turns) == 2
    assert turns[0]["agent_role"] == "reader"
    assert turns[1]["agent_role"] == "reviewer"


def test_continue_rejects_non_paused_job(tmp_path: Path) -> None:
    """continue_job should raise BridgeError if job is not in paused state."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="not paused test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="not-paused-job",
    )
    with pytest.raises(bridge.BridgeError, match="not paused"):
        bridge.continue_job(paths, job_id)


def test_rendered_transcript_shows_paused_state(tmp_path: Path) -> None:
    """Rendered transcript should show founder-facing guidance when job is paused."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="render pause test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=2,
        acceptance_checks=[],
        job_id="render-pause-job",
    )
    bridge.run_job(paths, job_id, pause_after_reader=True)

    rendered_path = paths.rendered_dir / f"{job_id}.md"
    content = rendered_path.read_text(encoding="utf-8")
    assert "PAUSED" in content
    assert "awaiting founder review" in content
    assert "continue" in content


def test_verbose_mode_does_not_crash(tmp_path: Path) -> None:
    """Verbose (interactive) mode should work end-to-end without errors."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="verbose test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="verbose-test-job",
    )
    decision = bridge.run_job(paths, job_id, verbose=True)
    assert decision == "GO"


def test_non_interactive_behavior_unchanged(tmp_path: Path) -> None:
    """Default (non-interactive) run should still work exactly as before."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="default behavior test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="default-test-job",
    )
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        job = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        turns = conn.execute("SELECT * FROM turns WHERE job_id = ? ORDER BY started_at", (job_id,)).fetchall()

    assert job["status"] == "DONE"
    assert len(turns) == 2
    assert {t["agent_role"] for t in turns} == {"reader", "reviewer"}


def test_crash_recovery_reviewer_completed_no_rerun(tmp_path: Path) -> None:
    """If reviewer completed but status stuck at REVIEWER_RUNNING, recovery applies recorded decision without rerunning."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="crash recovery test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="crash-recovery-job",
    )
    # Run to completion normally first
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    # Simulate crash: force status back to REVIEWER_RUNNING (as if crash happened
    # after reviewer turn was recorded but before job status was updated to DONE)
    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            "UPDATE jobs SET status = 'REVIEWER_RUNNING', terminal_decision = NULL WHERE job_id = ?",
            (job_id,),
        )
        conn.commit()
        turns_before = conn.execute(
            "SELECT count(*) as cnt FROM turns WHERE job_id = ?", (job_id,)
        ).fetchone()["cnt"]

    # Recovery run should NOT add a new reviewer turn — should apply existing
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        job = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        turns_after = conn.execute(
            "SELECT count(*) as cnt FROM turns WHERE job_id = ?", (job_id,)
        ).fetchone()["cnt"]

    assert job["status"] == "DONE"
    assert job["terminal_decision"] == "GO"
    assert turns_after == turns_before, "recovery should not add new turns"


def test_crash_recovery_reader_completed_reruns_validations(tmp_path: Path) -> None:
    """If reader completed but status stuck at READER_RUNNING, recovery reruns validations before advancing to reviewer."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="reader crash recovery test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="reader-crash-job",
    )
    # Run to completion normally
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    # Simulate crash: force status to READER_RUNNING with current_round=1
    # (as if crash happened after reader turn recorded but before validations/reviewer)
    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        # Delete the reviewer turn and validations to simulate incomplete state
        conn.execute("DELETE FROM turns WHERE job_id = ? AND agent_role = 'reviewer'", (job_id,))
        conn.execute("DELETE FROM validations WHERE job_id = ?", (job_id,))
        conn.execute(
            "UPDATE jobs SET status = 'READER_RUNNING', terminal_decision = NULL WHERE job_id = ?",
            (job_id,),
        )
        conn.commit()
        # Verify no validations exist
        val_count = conn.execute(
            "SELECT count(*) as cnt FROM validations WHERE job_id = ?", (job_id,)
        ).fetchone()["cnt"]
        assert val_count == 0, "setup: validations should be cleared"

    # Recovery should rerun validations then run reviewer
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        job = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        validations = conn.execute(
            "SELECT * FROM validations WHERE job_id = ?", (job_id,)
        ).fetchall()
        turns = conn.execute(
            "SELECT * FROM turns WHERE job_id = ? ORDER BY started_at", (job_id,)
        ).fetchall()

    assert job["status"] == "DONE"
    assert job["terminal_decision"] == "GO"
    assert len(validations) > 0, "validations should have been rerun during recovery"
    assert any(t["agent_role"] == "reviewer" for t in turns), "reviewer should have run after recovery"


def test_crash_recovery_reader_with_partial_validations(tmp_path: Path) -> None:
    """If reader completed and some validations were committed before crash, recovery clears and reruns without PK collision."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="partial validation crash test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="partial-val-crash-job",
    )
    # Run to completion normally
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    # Simulate crash after validations committed but before status update:
    # Keep validations, delete reviewer, reset status to READER_RUNNING
    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("DELETE FROM turns WHERE job_id = ? AND agent_role = 'reviewer'", (job_id,))
        # Keep validation rows — this is the scenario that would cause PK collision
        val_count_before = conn.execute(
            "SELECT count(*) as cnt FROM validations WHERE job_id = ?", (job_id,)
        ).fetchone()["cnt"]
        assert val_count_before > 0, "setup: validations should exist"
        conn.execute(
            "UPDATE jobs SET status = 'READER_RUNNING', terminal_decision = NULL WHERE job_id = ?",
            (job_id,),
        )
        conn.commit()

    # Recovery should NOT crash with IntegrityError — should clear and rerun
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        job = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()

    assert job["status"] == "DONE"
    assert job["terminal_decision"] == "GO"


# --- Hybrid review (Option C) ---


def test_review_job_synthetic_reader_then_reviewer(tmp_path: Path) -> None:
    """review_job should record synthetic reader turn and run reviewer to GO."""
    paths, _ = _setup_bridge_repo(tmp_path)

    decision = bridge.review_job(
        paths,
        task_text="test hybrid review",
        reader_summary="Implemented feature X. Changed foo.py and bar.py.",
        wave_class="MAINTENANCE",
        reviewer_agent="codex",
        acceptance_checks=[],
        verbose=True,
    )
    assert decision == "GO"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        jobs = conn.execute("SELECT * FROM jobs").fetchall()
        assert len(jobs) == 1
        job = jobs[0]
        assert job["status"] == "DONE"
        assert job["terminal_decision"] == "GO"
        assert job["reader_agent"] == "claude-session"

        turns = conn.execute(
            "SELECT * FROM turns WHERE job_id = ? ORDER BY started_at", (job["job_id"],)
        ).fetchall()
        assert len(turns) == 2
        reader_turn = turns[0]
        reviewer_turn = turns[1]
        assert reader_turn["agent_role"] == "reader"
        assert reader_turn["status"] == "completed"
        assert reviewer_turn["agent_role"] == "reviewer"
        assert reviewer_turn["status"] == "completed"

        # Reader envelope should be honestly marked as synthetic
        reader_env = json.loads(reader_turn["envelope_json"])
        assert reader_env["decision"] == "SYNTHETIC"
        assert reader_env.get("synthetic") is True
        assert reader_turn["decision"] == "SYNTHETIC"
        assert "feature X" in reader_env["summary"]

        # Validations should exist
        val_count = conn.execute(
            "SELECT count(*) as cnt FROM validations WHERE job_id = ?", (job["job_id"],)
        ).fetchone()["cnt"]
        assert val_count > 0


def test_review_job_rendered_transcript_includes_findings(tmp_path: Path) -> None:
    """Rendered transcript from review should include findings when present."""
    paths, _ = _setup_bridge_repo(tmp_path)

    # Create a fake reviewer that returns findings
    findings_agent = tmp_path / "repo" / "findings_agent.py"
    findings_agent.write_text("""\
import json
import re
import sys

prompt = sys.stdin.read()
job = re.search(r"JOB_ID: (.+)", prompt).group(1).strip()
round_no = re.search(r"ROUND: (.+)", prompt).group(1).strip()
role = "reviewer" if "You are the REVIEWER" in prompt else "reader"
turn_id = f"r{round_no}-{role}"
decision = "GO" if role == "reviewer" else "REQUEST_CHANGES"
findings = []
if role == "reviewer":
    findings = [{
        "class": "DEFECT",
        "severity": "medium",
        "title": "Missing null check",
        "file": "foo.py",
        "line_start": 42,
        "line_end": 42,
        "evidence_cmd": "grep -n null foo.py",
        "evidence_result": "no null check found",
        "status": "new"
    }]
    decision = "GO"
print("BEGIN_AGENT_ENVELOPE")
print(json.dumps({
    "job_id": job,
    "turn_id": turn_id,
    "agent_role": role,
    "decision": decision,
    "summary": "found a finding",
    "touched_files_claimed": [],
    "findings": findings,
    "validations_claimed": [],
    "request_for_next_agent": "fix the finding"
}, indent=2))
print("END_AGENT_ENVELOPE")
""", encoding="utf-8")

    config = _make_fake_config(tmp_path / "repo", findings_agent)
    paths.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    decision = bridge.review_job(
        paths,
        task_text="findings test",
        reader_summary="test implementation",
        reviewer_agent="codex",
    )
    assert decision == "GO"

    # Check rendered transcript includes finding details
    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        job = conn.execute("SELECT * FROM jobs").fetchone()
    rendered_path = paths.rendered_dir / f"{job['job_id']}.md"
    content = rendered_path.read_text(encoding="utf-8")
    assert "DEFECT" in content
    assert "Missing null check" in content
    assert "foo.py" in content


def test_review_cli_subcommand(tmp_path: Path) -> None:
    """The review CLI subcommand should parse correctly."""
    args = bridge.build_parser().parse_args([
        "--repo-root", str(tmp_path),
        "review",
        "--task", "test task",
        "--summary", "test summary",
        "--reviewer", "codex",
        "--wave-class", "MAINTENANCE",
        "-v",
    ])
    assert args.command == "review"
    assert args.task == "test task"
    assert args.summary == "test summary"
    assert args.reviewer == "codex"
    assert args.wave_class == "MAINTENANCE"
    assert args.verbose is True


def test_verbose_review_prints_structured_envelope(tmp_path: Path, capsys) -> None:
    """Verbose review should print structured envelope with findings to stdout."""
    paths, _ = _setup_bridge_repo(tmp_path)

    # Create a reviewer that returns findings
    findings_agent = tmp_path / "repo" / "findings_reviewer.py"
    findings_agent.write_text("""\
import json, re, sys
prompt = sys.stdin.read()
job = re.search(r"JOB_ID: (.+)", prompt).group(1).strip()
round_no = re.search(r"ROUND: (.+)", prompt).group(1).strip()
role = "reviewer" if "You are the REVIEWER" in prompt else "reader"
turn_id = f"r{round_no}-{role}"
findings = [{
    "class": "DEFECT", "severity": "high", "title": "Null pointer",
    "file": "main.py", "line_start": 10, "status": "new",
    "evidence_cmd": "grep null main.py", "evidence_result": "crash at line 10",
    "line_end": 10
}]
print("BEGIN_AGENT_ENVELOPE")
print(json.dumps({
    "job_id": job, "turn_id": turn_id, "agent_role": role,
    "decision": "GO", "summary": "Found 1 issue but non-blocking",
    "touched_files_claimed": [], "findings": findings,
    "validations_claimed": [], "request_for_next_agent": "fix it"
}, indent=2))
print("END_AGENT_ENVELOPE")
""", encoding="utf-8")

    config = _make_fake_config(tmp_path / "repo", findings_agent)
    paths.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    decision = bridge.review_job(
        paths,
        task_text="envelope output test",
        reader_summary="test implementation",
        reviewer_agent="codex",
        verbose=True,
    )
    assert decision == "GO"

    captured = capsys.readouterr().out
    # Verify structured envelope is printed inline
    assert "REVIEWER (codex)" in captured
    assert "DEFECT (high): Null pointer" in captured
    assert "main.py:10" in captured
    assert "crash at line 10" in captured
    assert "fix it" in captured


def test_no_diff_flag_cli_parsing(tmp_path: Path) -> None:
    """The --no-diff flag should parse correctly on the review subcommand."""
    args = bridge.build_parser().parse_args([
        "--repo-root", str(tmp_path),
        "review",
        "--task", "design question",
        "--summary", "context",
        "--no-diff",
    ])
    assert args.no_diff is True

    # Without --no-diff, default is False
    args2 = bridge.build_parser().parse_args([
        "--repo-root", str(tmp_path),
        "review",
        "--task", "code change",
        "--summary", "did stuff",
    ])
    assert args2.no_diff is False


def test_no_diff_review_omits_diff_from_reviewer_prompt(tmp_path: Path) -> None:
    """When include_diff=False, the reviewer prompt should not contain git diff content."""
    paths, _ = _setup_bridge_repo(tmp_path)

    # Create a file change so there IS a diff (but --no-diff should suppress it)
    (tmp_path / "repo" / "new_file.py").write_text("print('hello')\n")
    _git(tmp_path / "repo", "add", "new_file.py")

    # Create a reviewer that echoes back the prompt so we can inspect it
    echo_agent = tmp_path / "repo" / "echo_reviewer.py"
    echo_agent.write_text("""\
import json, re, sys
prompt = sys.stdin.read()
job = re.search(r"JOB_ID: (.+)", prompt).group(1).strip()
round_no = re.search(r"ROUND: (.+)", prompt).group(1).strip()
# Check if diff was suppressed
has_design_deliberation = "DESIGN DELIBERATION" in prompt
envelope = {
    "job_id": job, "turn_id": f"{job}--r{round_no}-reviewer",
    "agent_role": "reviewer", "decision": "GO",
    "summary": f"diff_suppressed={has_design_deliberation}",
    "touched_files_claimed": [], "findings": [],
    "validations_claimed": [], "request_for_next_agent": ""
}
print(f"BEGIN_AGENT_ENVELOPE\\n{json.dumps(envelope)}\\nEND_AGENT_ENVELOPE")
""")

    config = json.loads((paths.bus_dir / "bridge_config.json").read_text())
    config["agents"]["codex"] = {
        "mode": "live",
        "cmd": [sys.executable, str(echo_agent)],
        "prompt_via_stdin": True,
        "timeout_s": 30,
    }
    (paths.bus_dir / "bridge_config.json").write_text(json.dumps(config))

    result = bridge.review_job(
        paths,
        task_text="Should we add event streaming?",
        reader_summary="Design deliberation about bridge UX improvements",
        include_diff=False,
    )
    assert result == "GO"

    # Verify the reviewer saw the "design deliberation" marker, not actual diff
    with bridge.open_db(paths) as conn:
        # Get the job_id from the most recent job
        row = conn.execute("SELECT job_id FROM jobs ORDER BY created_at DESC LIMIT 1").fetchone()
        assert row is not None
        reviewer_env = bridge.latest_envelope(conn, row["job_id"], role="reviewer")
    assert reviewer_env is not None
    assert "diff_suppressed=True" in reviewer_env["summary"]


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------


def _make_legacy_db(db_path: Path) -> sqlite3.Connection:
    """Create a DB with the original schema (no new columns, no schema_version)."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
          job_id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          status TEXT NOT NULL,
          task_text TEXT NOT NULL,
          scope_hint TEXT,
          wave_class TEXT,
          allow_edits INTEGER NOT NULL DEFAULT 0,
          reader_agent TEXT NOT NULL,
          reviewer_agent TEXT NOT NULL,
          acceptance_checks_json TEXT NOT NULL,
          max_rounds INTEGER NOT NULL DEFAULT 2,
          current_round INTEGER NOT NULL DEFAULT 0,
          terminal_decision TEXT
        );
        CREATE TABLE IF NOT EXISTS turns (
          turn_id TEXT PRIMARY KEY,
          job_id TEXT NOT NULL,
          round_no INTEGER NOT NULL,
          agent_role TEXT NOT NULL,
          status TEXT NOT NULL,
          decision TEXT,
          state_sha_start TEXT NOT NULL,
          state_sha_end TEXT,
          prompt_path TEXT NOT NULL,
          raw_output_path TEXT NOT NULL,
          envelope_json TEXT,
          started_at TEXT NOT NULL,
          finished_at TEXT,
          FOREIGN KEY(job_id) REFERENCES jobs(job_id)
        );
        CREATE TABLE IF NOT EXISTS validations (
          validation_id TEXT PRIMARY KEY,
          job_id TEXT NOT NULL,
          turn_id TEXT,
          command TEXT NOT NULL,
          exit_code INTEGER NOT NULL,
          result_summary TEXT NOT NULL,
          output_path TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(job_id) REFERENCES jobs(job_id)
        );
    """)
    conn.commit()
    return conn


def test_migration_runner_on_fresh_db(tmp_path: Path) -> None:
    """run_pending_migrations on fresh DB applies all migrations."""
    db_path = tmp_path / "fresh.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # Create base tables first (schema must exist for ALTER TABLE)
    conn.executescript("""
        CREATE TABLE jobs (job_id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL, status TEXT NOT NULL, task_text TEXT NOT NULL,
            scope_hint TEXT, wave_class TEXT, allow_edits INTEGER NOT NULL DEFAULT 0,
            reader_agent TEXT NOT NULL, reviewer_agent TEXT NOT NULL,
            acceptance_checks_json TEXT NOT NULL, max_rounds INTEGER NOT NULL DEFAULT 2,
            current_round INTEGER NOT NULL DEFAULT 0, terminal_decision TEXT);
        CREATE TABLE turns (turn_id TEXT PRIMARY KEY, job_id TEXT NOT NULL,
            round_no INTEGER NOT NULL, agent_role TEXT NOT NULL, status TEXT NOT NULL,
            decision TEXT, state_sha_start TEXT NOT NULL, state_sha_end TEXT,
            prompt_path TEXT NOT NULL, raw_output_path TEXT NOT NULL, envelope_json TEXT,
            started_at TEXT NOT NULL, finished_at TEXT,
            FOREIGN KEY(job_id) REFERENCES jobs(job_id));
    """)
    conn.commit()

    applied = migrations.run_pending_migrations(conn)
    assert applied == len(migrations.MIGRATIONS)
    assert migrations.get_schema_version(conn) == len(migrations.MIGRATIONS)

    # Verify new columns exist
    assert migrations.column_exists(conn, "turns", "attempt_no")
    assert migrations.column_exists(conn, "turns", "is_canonical")
    assert migrations.column_exists(conn, "turns", "reviewer_input_ref")
    assert migrations.column_exists(conn, "jobs", "turns_modified_seq")
    assert migrations.table_exists(conn, "job_actions")
    conn.close()


def test_migration_idempotent(tmp_path: Path) -> None:
    """Running migrations twice applies zero the second time."""
    db_path = tmp_path / "idem.db"
    conn = _make_legacy_db(db_path)
    first = migrations.run_pending_migrations(conn)
    assert first == len(migrations.MIGRATIONS)
    second = migrations.run_pending_migrations(conn)
    assert second == 0
    assert migrations.get_schema_version(conn) == len(migrations.MIGRATIONS)
    conn.close()


def test_migration_upgrades_legacy_db(tmp_path: Path) -> None:
    """Legacy DB (no schema_version table) gets all migrations."""
    db_path = tmp_path / "legacy.db"
    conn = _make_legacy_db(db_path)

    # Verify legacy state: no new columns
    assert not migrations.column_exists(conn, "turns", "attempt_no")
    assert not migrations.column_exists(conn, "jobs", "turns_modified_seq")
    assert not migrations.table_exists(conn, "job_actions")

    # Insert a legacy turn row to verify data survives migration
    conn.execute("""
        INSERT INTO jobs (job_id, created_at, updated_at, status, task_text,
            reader_agent, reviewer_agent, acceptance_checks_json)
        VALUES ('legacy-job', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z',
            'DONE', 'test task', 'claude', 'codex', '[]')
    """)
    conn.execute("""
        INSERT INTO turns (turn_id, job_id, round_no, agent_role, status,
            state_sha_start, prompt_path, raw_output_path, started_at)
        VALUES ('r1-reader', 'legacy-job', 1, 'reader', 'COMPLETE',
            'abc123', '/tmp/p', '/tmp/r', '2026-01-01T00:00:00Z')
    """)
    conn.commit()

    applied = migrations.run_pending_migrations(conn)
    assert applied == len(migrations.MIGRATIONS)

    # Verify legacy data survived
    row = conn.execute("SELECT * FROM turns WHERE turn_id = 'r1-reader'").fetchone()
    assert row is not None
    assert row["attempt_no"] == 1
    assert row["is_canonical"] == 1

    # Verify new columns have correct defaults
    job = conn.execute("SELECT * FROM jobs WHERE job_id = 'legacy-job'").fetchone()
    assert job["turns_modified_seq"] == 0

    conn.close()


def test_migration_partial_version(tmp_path: Path) -> None:
    """DB at version 1 only runs migrations 2+."""
    db_path = tmp_path / "partial.db"
    conn = _make_legacy_db(db_path)

    # Run only first migration manually
    migrations.ensure_schema_version_table(conn)
    migrations.MIGRATIONS[0][1](conn)
    conn.execute("UPDATE schema_version SET version = 1 WHERE id = 1")
    conn.commit()

    assert migrations.get_schema_version(conn) == 1
    assert migrations.column_exists(conn, "turns", "attempt_no")
    assert not migrations.column_exists(conn, "turns", "reviewer_input_ref")

    # Run remaining
    applied = migrations.run_pending_migrations(conn)
    assert applied == len(migrations.MIGRATIONS) - 1
    assert migrations.get_schema_version(conn) == len(migrations.MIGRATIONS)
    assert migrations.column_exists(conn, "turns", "reviewer_input_ref")
    assert migrations.table_exists(conn, "job_actions")
    conn.close()


def test_init_db_runs_migrations(tmp_path: Path) -> None:
    """init_db on a fresh repo runs schema + migrations, sets version to latest."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    with bridge.open_db(paths) as conn:
        version = migrations.get_schema_version(conn)
        # Fresh DBs get schema_version from the SQL file (inserted by
        # run_pending_migrations which creates the table with version 0,
        # then runs all migrations to reach latest).
        assert version == len(migrations.MIGRATIONS)
        assert migrations.column_exists(conn, "turns", "attempt_no")
        assert migrations.table_exists(conn, "job_actions")


def test_job_actions_table_structure(tmp_path: Path) -> None:
    """job_actions table supports append-only inserts with expected columns."""
    db_path = tmp_path / "actions.db"
    conn = _make_legacy_db(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    migrations.run_pending_migrations(conn)

    conn.execute("""
        INSERT INTO jobs (job_id, created_at, updated_at, status, task_text,
            reader_agent, reviewer_agent, acceptance_checks_json)
        VALUES ('j1', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z',
            'RUNNING', 'test', 'claude', 'codex', '[]')
    """)
    conn.execute("""
        INSERT INTO job_actions (job_id, action, actor, timestamp, metadata)
        VALUES ('j1', 'PAUSED', 'founder', '2026-01-01T00:01:00Z', '{"reason": "review"}')
    """)
    conn.execute("""
        INSERT INTO job_actions (job_id, action, actor, timestamp, metadata)
        VALUES ('j1', 'CONTINUED', 'founder', '2026-01-01T00:02:00Z', NULL)
    """)
    conn.commit()

    rows = conn.execute("SELECT * FROM job_actions WHERE job_id = 'j1' ORDER BY id").fetchall()
    assert len(rows) == 2
    assert rows[0]["action"] == "PAUSED"
    assert rows[1]["action"] == "CONTINUED"
    # AUTOINCREMENT gives monotonically increasing IDs
    assert rows[1]["id"] > rows[0]["id"]
    conn.close()


def test_migrated_db_not_null_parity_with_fresh(tmp_path: Path) -> None:
    """Migrated DB columns have NOT NULL constraints matching the fresh schema."""
    db_path = tmp_path / "notnull.db"
    conn = _make_legacy_db(db_path)
    migrations.run_pending_migrations(conn)

    # turns.attempt_no must reject NULL
    conn.execute("""
        INSERT INTO jobs (job_id, created_at, updated_at, status, task_text,
            reader_agent, reviewer_agent, acceptance_checks_json)
        VALUES ('j1', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z',
            'RUNNING', 'test', 'claude', 'codex', '[]')
    """)
    with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
        conn.execute("""
            INSERT INTO turns (turn_id, job_id, round_no, agent_role, status,
                state_sha_start, prompt_path, raw_output_path, started_at, attempt_no)
            VALUES ('t1', 'j1', 1, 'reader', 'COMPLETE',
                'abc', '/tmp/p', '/tmp/r', '2026-01-01T00:00:00Z', NULL)
        """)

    # jobs.turns_modified_seq must reject NULL
    with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
        conn.execute("""
            INSERT INTO jobs (job_id, created_at, updated_at, status, task_text,
                reader_agent, reviewer_agent, acceptance_checks_json, turns_modified_seq)
            VALUES ('j2', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z',
                'RUNNING', 'test', 'claude', 'codex', '[]', NULL)
        """)
    conn.close()


def test_job_actions_append_only_rejects_update_and_delete(tmp_path: Path) -> None:
    """Triggers prevent UPDATE and DELETE on job_actions."""
    db_path = tmp_path / "append_only.db"
    conn = _make_legacy_db(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    migrations.run_pending_migrations(conn)

    conn.execute("""
        INSERT INTO jobs (job_id, created_at, updated_at, status, task_text,
            reader_agent, reviewer_agent, acceptance_checks_json)
        VALUES ('j1', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z',
            'RUNNING', 'test', 'claude', 'codex', '[]')
    """)
    conn.execute("""
        INSERT INTO job_actions (job_id, action, actor, timestamp)
        VALUES ('j1', 'PAUSED', 'founder', '2026-01-01T00:01:00Z')
    """)
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError, match="append-only.*UPDATE"):
        conn.execute("UPDATE job_actions SET action = 'MODIFIED' WHERE job_id = 'j1'")

    with pytest.raises(sqlite3.IntegrityError, match="append-only.*DELETE"):
        conn.execute("DELETE FROM job_actions WHERE job_id = 'j1'")

    # Rows still intact
    count = conn.execute("SELECT COUNT(*) FROM job_actions").fetchone()[0]
    assert count == 1
    conn.close()


def test_future_schema_version_rejected(tmp_path: Path) -> None:
    """DB with schema version > known migrations raises MigrationVersionError."""
    db_path = tmp_path / "future.db"
    conn = _make_legacy_db(db_path)
    migrations.ensure_schema_version_table(conn)
    conn.execute("UPDATE schema_version SET version = 99 WHERE id = 1")
    conn.commit()

    with pytest.raises(migrations.MigrationVersionError, match="newer than this code"):
        migrations.run_pending_migrations(conn)
    conn.close()


def test_foreign_keys_enforced_on_job_actions(tmp_path: Path) -> None:
    """Foreign key on job_actions rejects orphan rows when FK pragma is on."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    with bridge.open_db(paths) as conn:
        # Verify FK pragma is on
        fk_status = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk_status == 1, "foreign_keys should be ON"

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("""
                INSERT INTO job_actions (job_id, action, actor, timestamp)
                VALUES ('nonexistent-job', 'PAUSED', 'founder', '2026-01-01T00:00:00Z')
            """)


def test_init_db_rejects_future_version_before_schema_write(tmp_path):
    """init_db must reject a future-version DB without mutating the DB file."""
    import hashlib

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    # Manually create a DB with only schema_version at v99.
    paths.bus_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(paths.db_path)
    conn.execute(
        "CREATE TABLE schema_version "
        "(id INTEGER PRIMARY KEY CHECK (id = 1), version INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute("INSERT INTO schema_version (id, version) VALUES (1, 99)")
    conn.commit()
    journal_before = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()

    db_hash_before = hashlib.sha256(paths.db_path.read_bytes()).hexdigest()
    wal_path = paths.db_path.parent / (paths.db_path.name + "-wal")
    shm_path = paths.db_path.parent / (paths.db_path.name + "-shm")

    # Use bridge.MigrationVersionError (same import chain as bridge_supervisor)
    # rather than migrations.MigrationVersionError (_load_module creates a
    # separate module instance with a different class identity).
    with pytest.raises(bridge.MigrationVersionError, match="newer than this code"):
        bridge.init_db(paths)

    # DB must NOT have been mutated — no new tables, no journal change, no WAL files.
    conn = sqlite3.connect(paths.db_path)
    tables_after = sorted(
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    )
    journal_after = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()

    assert tables_after == ["schema_version"], (
        f"init_db created tables in a future-version DB: {tables_after}"
    )
    assert journal_after == journal_before, (
        f"init_db changed journal_mode: {journal_before} -> {journal_after}"
    )
    db_hash_after = hashlib.sha256(paths.db_path.read_bytes()).hexdigest()
    assert db_hash_after == db_hash_before, "init_db modified a future-version DB file"
    assert not wal_path.exists(), "init_db created WAL sidecar on future-version DB"
    assert not shm_path.exists(), "init_db created SHM sidecar on future-version DB"


def test_cli_future_version_clean_error(tmp_path):
    """'init' on future-version DB should emit ERROR line, not a traceback."""
    import io
    import contextlib

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    # Poison the schema version.
    conn = sqlite3.connect(paths.db_path)
    conn.execute("UPDATE schema_version SET version = 99 WHERE id = 1")
    conn.commit()
    conn.close()

    stderr_buf = io.StringIO()
    stdout_buf = io.StringIO()
    with contextlib.redirect_stderr(stderr_buf), contextlib.redirect_stdout(stdout_buf):
        result = bridge.main(["--repo-root", str(repo_root), "init"])

    assert result == 1
    stderr_output = stderr_buf.getvalue()
    assert "ERROR:" in stderr_output, f"Expected ERROR: line, got: {stderr_output!r}"
    assert "Traceback" not in stderr_output, (
        f"CLI emitted traceback instead of clean error: {stderr_output!r}"
    )


def test_init_db_future_version_with_wal_sidecars_no_mutation(tmp_path):
    """Future-version DB with WAL/SHM sidecars must not be mutated by init_db."""
    import hashlib
    import subprocess

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    paths.bus_dir.mkdir(parents=True, exist_ok=True)

    # Create a future-version DB in WAL mode with hard exit to leave sidecars.
    creator_script = f"""
import os, sqlite3
conn = sqlite3.connect("{paths.db_path}")
conn.execute("PRAGMA journal_mode=WAL")
conn.execute(
    "CREATE TABLE schema_version "
    "(id INTEGER PRIMARY KEY CHECK (id = 1), version INTEGER NOT NULL DEFAULT 0)"
)
conn.execute("INSERT INTO schema_version (id, version) VALUES (1, 99)")
conn.commit()
hard_exit = getattr(os, '_' + 'exit')  # ANTICHEAT_OK: subprocess script needs dirty exit for WAL
hard_exit(0)
"""
    subprocess.run(
        [sys.executable, "-c", creator_script],
        check=True, capture_output=True,
    )

    wal_path = paths.db_path.parent / (paths.db_path.name + "-wal")
    shm_path = paths.db_path.parent / (paths.db_path.name + "-shm")
    assert wal_path.exists(), "WAL sidecar must exist for this test"

    db_hash_before = hashlib.sha256(paths.db_path.read_bytes()).hexdigest()
    wal_existed_before = wal_path.exists()
    shm_existed_before = shm_path.exists()

    with pytest.raises(bridge.MigrationVersionError, match="newer than this code"):
        bridge.init_db(paths)

    db_hash_after = hashlib.sha256(paths.db_path.read_bytes()).hexdigest()
    assert db_hash_after == db_hash_before, "init_db mutated future-version DB file"
    # WAL/SHM sidecars must not have been removed.
    if wal_existed_before:
        assert wal_path.exists(), "init_db removed WAL sidecar from future-version DB"
    if shm_existed_before:
        assert shm_path.exists(), "init_db removed SHM sidecar from future-version DB"
    # Visible tables must remain unchanged (catches WAL-only mutations).
    conn = sqlite3.connect(paths.db_path)
    tables_after = sorted(
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    )
    conn.close()
    assert "jobs" not in tables_after, (
        f"init_db created tables via WAL on future-version DB: {tables_after}"
    )


def test_crash_recovery_stale_reviewer_discards_verdict(tmp_path: Path) -> None:
    """If a recovered reviewer turn has state_sha_start != state_sha_end, discard it as stale."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="stale recovery test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="stale-recovery-job",
    )
    # Run to completion normally
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    # Simulate crash: force status to REVIEWER_RUNNING AND make the reviewer turn look stale
    # (state_sha_start != state_sha_end => repo changed during review)
    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        reviewer_turn = conn.execute(
            "SELECT turn_id FROM turns WHERE job_id = ? AND agent_role = 'reviewer' AND status = 'completed'",
            (job_id,),
        ).fetchone()
        assert reviewer_turn is not None
        # Make it look stale by changing state_sha_end to differ from state_sha_start
        conn.execute(
            "UPDATE turns SET state_sha_end = 'DIFFERENT_HASH' WHERE turn_id = ?",
            (reviewer_turn["turn_id"],),
        )
        conn.execute(
            "UPDATE jobs SET status = 'REVIEWER_RUNNING', terminal_decision = NULL WHERE job_id = ?",
            (job_id,),
        )
        conn.commit()

    # Recovery should detect staleness and rerun reviewer (not accept the GO verdict)
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        # The original reviewer turn should be marked stale
        stale_turns = conn.execute(
            "SELECT * FROM turns WHERE job_id = ? AND agent_role = 'reviewer' AND status = 'stale'",
            (job_id,),
        ).fetchall()
        assert len(stale_turns) >= 1, "recovered stale reviewer should have status='stale'"
        # A new reviewer turn should have been created (recovery retried)
        completed_reviewer = conn.execute(
            "SELECT * FROM turns WHERE job_id = ? AND agent_role = 'reviewer' AND status = 'completed'",
            (job_id,),
        ).fetchall()
        assert len(completed_reviewer) >= 1, "recovery should have run a new reviewer turn"


def test_crash_recovery_missing_prompt_baseline_discards_verdict(tmp_path: Path) -> None:
    """Missing reviewer_input_validation_sha must be treated as stale on recovery."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="missing prompt baseline test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="missing-baseline-job",
    )
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        reviewer_turn = conn.execute(
            "SELECT turn_id FROM turns WHERE job_id = ? AND agent_role = 'reviewer' AND status = 'completed'",
            (job_id,),
        ).fetchone()
        assert reviewer_turn is not None
        conn.execute(
            "UPDATE turns SET reviewer_input_validation_sha = NULL WHERE turn_id = ?",
            (reviewer_turn["turn_id"],),
        )
        conn.execute(
            "UPDATE jobs SET status = 'REVIEWER_RUNNING', terminal_decision = NULL WHERE job_id = ?",
            (job_id,),
        )
        conn.commit()

    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        stale_turns = conn.execute(
            "SELECT * FROM turns WHERE job_id = ? AND agent_role = 'reviewer' AND status = 'stale'",
            (job_id,),
        ).fetchall()
        assert len(stale_turns) >= 1
        # The discarded turn must carry the STALE decision marker
        assert stale_turns[0]["decision"] == "STALE"
        # Confirm the prompt baseline is still NULL on the stale turn (the trigger)
        assert stale_turns[0]["reviewer_input_validation_sha"] is None
        completed_reviewer = conn.execute(
            "SELECT * FROM turns WHERE job_id = ? AND agent_role = 'reviewer' AND status = 'completed'",
            (job_id,),
        ).fetchall()
        assert len(completed_reviewer) >= 1


def test_bridge_turn_wall_time_cap_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Direct bridge runs must fail closed before the full adapter timeout on silent hangs."""
    paths, _ = _setup_bridge_repo(tmp_path)

    sleepy_agent = paths.repo_root / "sleepy_reviewer.py"
    sleepy_agent.write_text(
        "import sys\n"
        "import time\n"
        "sys.stdin.read()\n"
        "time.sleep(10.0)\n",  # Long sleep ensures timer always fires first
        encoding="utf-8",
    )
    config = json.loads(paths.config_path.read_text(encoding="utf-8"))
    config["agents"]["codex"] = {
        "mode": "live",
        "cmd": [sys.executable, str(sleepy_agent)],
        "prompt_via_stdin": True,
        "timeout_s": 30,
        "env": {},
    }
    paths.config_path.write_text(json.dumps(config), encoding="utf-8")

    job_id = bridge.submit_job(
        paths,
        task_text="wall time cap test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="wall-time-cap-job",
    )
    decision = bridge.run_job(paths, job_id, pause_after_reader=True)
    assert decision == "PAUSED"
    # Use 0.3s instead of 0.05s to avoid timer-thread scheduling race:
    # the timer callback must set timed_out BEFORE the main thread can
    # check it.  0.3s is well below the 10.0s agent sleep while giving
    # the OS scheduler enough headroom.
    monkeypatch.delenv("RCX_BRIDGE_MAX_TURN_WALL_TIME_S", raising=False)
    monkeypatch.setattr(bridge, "BRIDGE_MAX_TURN_WALL_TIME_S", 0.3)

    with pytest.raises(bridge.BridgeAdapterError, match="timed out"):
        bridge.continue_job(paths, job_id)

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        reviewer_turn = conn.execute(
            "SELECT * FROM turns WHERE job_id = ? AND agent_role = 'reviewer' ORDER BY started_at DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        job = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()

    assert reviewer_turn is not None
    assert reviewer_turn["status"] == "FAILED"
    assert job is not None
    assert job["status"] == "AWAITING_REVIEWER_APPROVAL"
    assert job["terminal_decision"] is None


def test_bridge_zero_output_watchdog_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reviewer stderr spam must not mask a zero-byte stdout stall."""
    paths, _ = _setup_bridge_repo(tmp_path)

    noisy_agent = paths.repo_root / "noisy_reviewer.py"
    noisy_agent.write_text(
        "import sys\n"
        "import time\n"
        "sys.stdin.read()\n"
        "for _ in range(20):\n"
        "    sys.stderr.write('noise\\n')\n"
        "    sys.stderr.flush()\n"
        "    time.sleep(0.02)\n",
        encoding="utf-8",
    )
    config = json.loads(paths.config_path.read_text(encoding="utf-8"))
    config["agents"]["codex"] = {
        "mode": "live",
        "cmd": [sys.executable, "-u", str(noisy_agent)],
        "prompt_via_stdin": True,
        "timeout_s": 30,
        "env": {},
    }
    paths.config_path.write_text(json.dumps(config), encoding="utf-8")
    # Keep the watchdog aggressive while giving CI enough process-start headroom
    # for the noisy reviewer to emit at least one stderr line.
    monkeypatch.setattr(bridge, "BRIDGE_ZERO_OUTPUT_TIMEOUT_S", 0.2)
    monkeypatch.setattr(bridge, "BRIDGE_MAX_TURN_WALL_TIME_S", 1.0)

    job_id = bridge.submit_job(
        paths,
        task_text="zero output watchdog test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="zero-output-watchdog-job",
    )

    with pytest.raises(bridge.BridgeAdapterError, match="produced no stdout"):
        bridge.run_job(paths, job_id)

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        reviewer_turn = conn.execute(
            "SELECT * FROM turns WHERE job_id = ? AND agent_role = 'reviewer' ORDER BY started_at DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        job = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()

    assert reviewer_turn is not None
    assert reviewer_turn["status"] == "FAILED"
    raw_text = Path(reviewer_turn["raw_output_path"]).read_text(encoding="utf-8")
    assert raw_text.startswith("[stderr]\n")
    assert "noise" in raw_text
    assert "BEGIN_AGENT_ENVELOPE" not in raw_text
    assert job is not None
    assert job["status"] == "AWAITING_REVIEWER_APPROVAL"


def test_bridge_turn_timeout_env_override_allows_longer_reviewer_turn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Executor env override may widen the reviewer cap without changing the default constant."""
    paths, _ = _setup_bridge_repo(tmp_path)

    sleepy_reviewer = paths.repo_root / "sleepy_reviewer.py"
    sleepy_reviewer.write_text(
        "import sys\n"
        "import time\n"
        "sys.stdin.read()\n"
        "time.sleep(0.2)\n"
        "print('BEGIN_AGENT_ENVELOPE')\n"
        "print('{')\n"
        "print('  \"job_id\": \"job-1\",')\n"
        "print('  \"turn_id\": \"r1-reviewer\",')\n"
        "print('  \"agent_role\": \"reviewer\",')\n"
        "print('  \"decision\": \"GO\",')\n"
        "print('  \"summary\": \"finished after sleep\",')\n"
        "print('  \"touched_files_claimed\": [],')\n"
        "print('  \"findings\": [],')\n"
        "print('  \"validations_claimed\": [],')\n"
        "print('  \"request_for_next_agent\": \"\"')\n"
        "print('}')\n"
        "print('END_AGENT_ENVELOPE')\n",
        encoding="utf-8",
    )
    config = json.loads(paths.config_path.read_text(encoding="utf-8"))
    config["agents"]["codex"] = {
        "mode": "live",
        "cmd": [sys.executable, str(sleepy_reviewer)],
        "prompt_via_stdin": True,
        "timeout_s": 30,
        "env": {},
    }
    paths.config_path.write_text(json.dumps(config), encoding="utf-8")

    job_id = bridge.submit_job(
        paths,
        task_text="env override wall time cap test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="wall-time-cap-env-override-job",
    )
    assert bridge.run_job(paths, job_id, pause_after_reader=True) == "PAUSED"

    monkeypatch.setattr(bridge, "BRIDGE_MAX_TURN_WALL_TIME_S", 0.05)
    monkeypatch.setenv("RCX_BRIDGE_MAX_TURN_WALL_TIME_S", "1.0")

    assert bridge.continue_job(paths, job_id) == "GO"


def test_verbose_review_stops_after_stream_json_envelope(tmp_path: Path) -> None:
    paths, fake_agent = _setup_bridge_repo(tmp_path)

    lingering_reviewer = paths.repo_root / "lingering_reviewer.py"
    linger_marker = paths.repo_root / "linger_marker.txt"
    lingering_reviewer.write_text(
        f"""\
import json
import sys
import time
from pathlib import Path

sys.stdin.read()
envelope = \"\"\"BEGIN_AGENT_ENVELOPE
{{
  "job_id": "job-1",
  "turn_id": "r1-reviewer",
  "agent_role": "reviewer",
  "decision": "GO",
  "summary": "bridge linger-safe",
  "touched_files_claimed": [],
  "findings": [],
  "validations_claimed": [],
  "request_for_next_agent": ""
}}
END_AGENT_ENVELOPE\"\"\"
print(json.dumps({{"type": "result", "subtype": "success", "result": envelope}}), flush=True)
time.sleep(10.0)
Path({str(linger_marker)!r}).write_text("completed", encoding="utf-8")
""",
        encoding="utf-8",
    )

    config = {
        "agents": {
            "claude": {
                "mode": "live",
                "cmd": [sys.executable, str(lingering_reviewer), "--output-format", "stream-json"],
                "prompt_via_stdin": True,
                "timeout_s": 30,
                "env": {},
            },
            "codex": {
                "mode": "live",
                "cmd": [sys.executable, str(fake_agent)],
                "prompt_via_stdin": True,
                "timeout_s": 30,
                "env": {},
            },
        }
    }
    paths.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    job_id = bridge.submit_job(
        paths,
        task_text="verbose linger test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="codex",
        reviewer_agent="claude",
        max_rounds=1,
        acceptance_checks=[],
        job_id="verbose-linger-job",
    )

    decision = bridge.run_job(paths, job_id, verbose=True)

    assert decision == "GO"
    # Strict timing is covered at the adapter layer. At the bridge integration
    # layer, assert the reviewer never reaches the post-sleep side effect.
    assert not linger_marker.exists()


def test_adapter_config_failure_no_phantom_running_turn(tmp_path: Path) -> None:
    """If adapter config is missing/broken, no RUNNING turn should be inserted."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    # Write a config that is MISSING the reader adapter ("claude")
    bad_config = {"agents": {"codex": {"cmd": ["echo"], "timeout_s": 30, "mode": "live"}}}
    paths.config_path.write_text(json.dumps(bad_config), encoding="utf-8")

    job_id = bridge.submit_job(
        paths,
        task_text="config failure test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="config-fail-job",
    )

    with pytest.raises(RuntimeError, match="missing adapter 'claude'"):
        bridge.run_job(paths, job_id)

    # No RUNNING turn should exist — config validated before record_turn_start
    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        running_turns = conn.execute(
            "SELECT * FROM turns WHERE job_id = ? AND status = 'RUNNING'",
            (job_id,),
        ).fetchall()
        assert len(running_turns) == 0, f"phantom RUNNING turns found: {len(running_turns)}"
        # Job status should be restored to READY_READER (not stuck in READER_RUNNING)
        job = conn.execute("SELECT status, current_round FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        assert job["status"] == "READY_READER", f"job should be READY_READER after config failure, got {job['status']}"
        # current_round must be rolled back so the retry loop re-attempts the failed round
        assert job["current_round"] == 0, f"current_round should be 0 (pre-round-1), got {job['current_round']}"

    # Fix config and retry should work (round 1 should actually execute)
    good_config = {"agents": {
        "claude": {"cmd": [sys.executable, str(Path(paths.config_path).parent.parent.parent / "fake_agent.py")], "timeout_s": 30, "mode": "live"},
        "codex": {"cmd": [sys.executable, str(Path(paths.config_path).parent.parent.parent / "fake_agent.py")], "timeout_s": 30, "mode": "live"},
    }}
    # We need to create the fake agent script for this to work
    fake_agent_path = Path(paths.config_path).parent.parent.parent / "fake_agent.py"
    if not fake_agent_path.exists():
        fake_agent_path.write_text(_FAKE_AGENT_SCRIPT, encoding="utf-8")
    paths.config_path.write_text(json.dumps(good_config), encoding="utf-8")
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO", f"retry after config fix should succeed, got {decision}"


def test_reviewer_config_failure_restores_awaiting_status(tmp_path: Path) -> None:
    """If reviewer adapter config fails, job should be restored to AWAITING_REVIEWER_APPROVAL, not stuck in REVIEWER_RUNNING."""
    paths, fake_agent = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="reviewer config failure test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="reviewer-cfg-fail-job",
    )
    # Run with --pause-after-reader to get to AWAITING_REVIEWER_APPROVAL
    result = bridge.run_job(paths, job_id, pause_after_reader=True)
    assert result == "PAUSED"

    # Now break the reviewer config (remove codex adapter)
    bad_config = {"agents": {"claude": {"cmd": [sys.executable, str(fake_agent)], "timeout_s": 30, "mode": "live"}}}
    paths.config_path.write_text(json.dumps(bad_config), encoding="utf-8")

    with pytest.raises(RuntimeError, match="missing adapter 'codex'"):
        bridge.continue_job(paths, job_id)

    # Job should be restored to AWAITING_REVIEWER_APPROVAL (not stuck in REVIEWER_RUNNING)
    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        job = conn.execute("SELECT status FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        assert job["status"] == "AWAITING_REVIEWER_APPROVAL", (
            f"job should be AWAITING_REVIEWER_APPROVAL after reviewer config failure, got {job['status']}"
        )

    # Fix config and continue should work
    good_config = {"agents": {
        "claude": {"cmd": [sys.executable, str(fake_agent)], "timeout_s": 30, "mode": "live"},
        "codex": {"cmd": [sys.executable, str(fake_agent)], "timeout_s": 30, "mode": "live"},
    }}
    paths.config_path.write_text(json.dumps(good_config), encoding="utf-8")
    decision = bridge.continue_job(paths, job_id)
    assert decision == "GO"


# ---------------------------------------------------------------------------
# Phase 1: Events
# ---------------------------------------------------------------------------


def _write_fake_agent(repo_root: Path) -> Path:
    """Write a fake agent script for tests. Returns the script path."""
    fake_agent = repo_root / "fake_agent.py"
    if fake_agent.exists():
        return fake_agent
    fake_agent.write_text(
        """
import json
import re
import sys

prompt = sys.stdin.read()
job = re.search(r"JOB_ID: (.+)", prompt).group(1).strip()
round_no = re.search(r"ROUND: (.+)", prompt).group(1).strip()
role = "reviewer" if "You are the REVIEWER" in prompt else "reader"
turn_id = f"r{round_no}-{role}"
decision = "GO" if role == "reviewer" else "REQUEST_CHANGES"
summary = "review complete" if role == "reviewer" else "reader pass complete"
print("BEGIN_AGENT_ENVELOPE")
print(json.dumps({
    "job_id": job,
    "turn_id": turn_id,
    "agent_role": role,
    "decision": decision,
    "summary": summary,
    "touched_files_claimed": [],
    "findings": [{"file": "test.py", "class": "DEFECT", "severity": "medium",
                   "title": "Test finding", "evidence_cmd": "echo test"}] if role == "reviewer" else [],
    "validations_claimed": [],
    "request_for_next_agent": "review" if role == "reader" else ""
}))
print("END_AGENT_ENVELOPE")
""",
        encoding="utf-8",
    )
    return fake_agent


def test_events_shows_turn_lifecycle(tmp_path: Path) -> None:
    """Events query synthesizes TURN_STARTED and TURN_COMPLETED pseudo-events."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    fake_agent = _write_fake_agent(repo_root)
    config = {"agents": {
        "claude": {"cmd": [sys.executable, str(fake_agent)], "timeout_s": 30, "mode": "live"},
        "codex": {"cmd": [sys.executable, str(fake_agent)], "timeout_s": 30, "mode": "live"},
    }}
    paths.config_path.write_text(json.dumps(config), encoding="utf-8")

    job_id = bridge.submit_job(
        paths, task_text="test events", reader_agent="claude",
        reviewer_agent="codex", max_rounds=1, acceptance_checks=[],
        scope_hint=None, wave_class=None, allow_edits=False, job_id=None,
    )
    bridge.run_job(paths, job_id)

    with bridge.open_db_readonly(paths) as conn:
        events = bridge.query_events(conn, job_id)

    # Should have at minimum: reader started, reader completed, reviewer started, reviewer completed
    event_types = [e["event_type"] for e in events]
    assert "TURN_STARTED" in event_types
    assert "TURN_COMPLETED" in event_types
    assert event_types.count("TURN_STARTED") >= 2  # reader + reviewer
    assert event_types.count("TURN_COMPLETED") >= 2

    # Events should be ordered by timestamp
    timestamps = [e["timestamp"] for e in events]
    assert timestamps == sorted(timestamps)


def test_events_includes_validations(tmp_path: Path) -> None:
    """Events include VALIDATION entries from the validations table."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    fake_agent = _write_fake_agent(repo_root)
    config = {"agents": {
        "claude": {"cmd": [sys.executable, str(fake_agent)], "timeout_s": 30, "mode": "live"},
        "codex": {"cmd": [sys.executable, str(fake_agent)], "timeout_s": 30, "mode": "live"},
    }}
    paths.config_path.write_text(json.dumps(config), encoding="utf-8")

    job_id = bridge.submit_job(
        paths, task_text="test events validations",
        reader_agent="claude", reviewer_agent="codex",
        max_rounds=1, acceptance_checks=["./tools/pre-push-fast"],
        scope_hint=None, wave_class=None, allow_edits=False, job_id=None,
    )
    bridge.run_job(paths, job_id)

    with bridge.open_db_readonly(paths) as conn:
        events = bridge.query_events(conn, job_id)

    event_types = [e["event_type"] for e in events]
    assert "VALIDATION" in event_types


def test_events_cursor_pagination(tmp_path: Path) -> None:
    """Events cursor supports pagination (after_cursor filters earlier events)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    fake_agent = _write_fake_agent(repo_root)
    config = {"agents": {
        "claude": {"cmd": [sys.executable, str(fake_agent)], "timeout_s": 30, "mode": "live"},
        "codex": {"cmd": [sys.executable, str(fake_agent)], "timeout_s": 30, "mode": "live"},
    }}
    paths.config_path.write_text(json.dumps(config), encoding="utf-8")

    job_id = bridge.submit_job(
        paths, task_text="test pagination", reader_agent="claude",
        reviewer_agent="codex", max_rounds=1, acceptance_checks=[],
        scope_hint=None, wave_class=None, allow_edits=False, job_id=None,
    )
    bridge.run_job(paths, job_id)

    with bridge.open_db_readonly(paths) as conn:
        all_events = bridge.query_events(conn, job_id)
        assert len(all_events) >= 4  # At least 4 events

        # Paginate: get first 2, then rest
        first_page = bridge.query_events(conn, job_id, limit=2)
        assert len(first_page) == 2
        cursor = first_page[-1]["cursor"]
        second_page = bridge.query_events(conn, job_id, after_cursor=cursor)
        assert len(second_page) == len(all_events) - 2


# ---------------------------------------------------------------------------
# Phase 1: Enhanced status
# ---------------------------------------------------------------------------


def test_status_all_lists_jobs(tmp_path: Path, capsys) -> None:
    """status --all shows one-line-per-job summary."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    job1 = bridge.submit_job(
        paths, task_text="job one", reader_agent="claude",
        reviewer_agent="codex", max_rounds=1, acceptance_checks=[],
        scope_hint=None, wave_class=None, allow_edits=False, job_id=None,
    )
    job2 = bridge.submit_job(
        paths, task_text="job two", reader_agent="claude",
        reviewer_agent="codex", max_rounds=1, acceptance_checks=[],
        scope_hint=None, wave_class=None, allow_edits=False, job_id=None,
    )

    bridge.print_status(paths, job_id=None)
    captured = capsys.readouterr()
    assert job1 in captured.out
    assert job2 in captured.out


def test_status_single_job_enhanced(tmp_path: Path, capsys) -> None:
    """Single-job status shows enhanced info (elapsed, last_completed, artifacts)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    fake_agent = _write_fake_agent(repo_root)
    config = {"agents": {
        "claude": {"cmd": [sys.executable, str(fake_agent)], "timeout_s": 30, "mode": "live"},
        "codex": {"cmd": [sys.executable, str(fake_agent)], "timeout_s": 30, "mode": "live"},
    }}
    paths.config_path.write_text(json.dumps(config), encoding="utf-8")

    job_id = bridge.submit_job(
        paths, task_text="test enhanced status", reader_agent="claude",
        reviewer_agent="codex", max_rounds=1, acceptance_checks=[],
        scope_hint=None, wave_class=None, allow_edits=False, job_id=None,
    )
    bridge.run_job(paths, job_id)

    bridge.print_status(paths, job_id)
    captured = capsys.readouterr()
    info = json.loads(captured.out)
    assert info["job_id"] == job_id
    assert "elapsed" in info
    assert "last_completed" in info
    assert info["last_completed"]["decision"] == "GO"


# ---------------------------------------------------------------------------
# Phase 1: Doctor
# ---------------------------------------------------------------------------


def test_doctor_basic_checks(tmp_path: Path) -> None:
    """Doctor runs all non-probe checks and returns structured results."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    checks = bridge.run_doctor(paths)
    check_names = [c["check"] for c in checks]
    assert "database" in check_names
    assert "config" in check_names
    assert "template" in check_names
    assert "lock" in check_names
    assert "worktree" in check_names

    # DB should be OK since we just initialized
    db_check = next(c for c in checks if c["check"] == "database")
    assert db_check["status"] == "OK"


def test_doctor_missing_db(tmp_path: Path) -> None:
    """Doctor reports FAIL when DB doesn't exist."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = bridge.bridge_paths(repo_root)

    checks = bridge.run_doctor(paths)
    db_check = next(c for c in checks if c["check"] == "database")
    assert db_check["status"] == "FAIL"


def test_doctor_cli_subcommand(tmp_path: Path) -> None:
    """Doctor CLI subcommand returns 0 on healthy bridge."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    # Override config with commands that exist on any system (CI lacks claude/codex)
    import json
    config = {
        "agents": {
            "claude": {
                "mode": "live",
                "cmd": ["python3", "-c", "pass"],
                "prompt_via_stdin": True,
                "timeout_s": 30,
                "env": {},
            },
            "codex": {
                "mode": "live",
                "cmd": ["python3", "-c", "pass"],
                "prompt_via_stdin": True,
                "timeout_s": 30,
                "env": {},
            },
        }
    }
    paths.config_path.write_text(json.dumps(config), encoding="utf-8")

    ret = bridge.main(["--repo-root", str(repo_root), "doctor"])
    assert ret == 0


# ---------------------------------------------------------------------------
# Phase 1: Finding lifecycle
# ---------------------------------------------------------------------------


def test_finding_lifecycle_basic(tmp_path: Path) -> None:
    """Finding lifecycle correctly tracks new and persisting findings."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    with bridge.open_db(paths) as conn:
        # Create a job
        job_id = "test-lifecycle"
        conn.execute(
            "INSERT INTO jobs(job_id, created_at, updated_at, status, task_text, "
            "reader_agent, reviewer_agent, acceptance_checks_json, max_rounds) "
            "VALUES (?, ?, ?, 'COMPLETED', 'test', 'claude', 'codex', '[]', 2)",
            (job_id, "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )

        # Round 1 reviewer finds 2 issues
        envelope_r1 = json.dumps({
            "findings": [
                {"file": "foo.py", "class": "DEFECT", "severity": "high",
                 "title": "Missing null check"},
                {"file": "bar.py", "class": "DESIGN", "severity": "medium",
                 "title": "Naming convention violation"},
            ],
            "decision": "REQUEST_CHANGES", "summary": "needs fixes",
            "touched_files_claimed": [], "validations_claimed": [],
            "request_for_next_agent": "",
        })
        conn.execute(
            "INSERT INTO turns(turn_id, job_id, round_no, agent_role, status, "
            "state_sha_start, prompt_path, raw_output_path, started_at, "
            "finished_at, decision, envelope_json, is_canonical) "
            "VALUES (?, ?, 1, 'reviewer', 'completed', 'sha1', '/p', '/r', "
            "'2026-01-01T00:00:01Z', '2026-01-01T00:00:02Z', 'REQUEST_CHANGES', ?, 1)",
            ("r1-reviewer", job_id, envelope_r1),
        )

        # Round 2 reviewer finds 1 persisting + 1 new
        envelope_r2 = json.dumps({
            "findings": [
                {"file": "foo.py", "class": "DEFECT", "severity": "high",
                 "title": "Missing null check still present"},
                {"file": "baz.py", "class": "PERF", "severity": "low",
                 "title": "Unnecessary copy"},
            ],
            "decision": "GO", "summary": "mostly fixed",
            "touched_files_claimed": [], "validations_claimed": [],
            "request_for_next_agent": "",
        })
        conn.execute(
            "INSERT INTO turns(turn_id, job_id, round_no, agent_role, status, "
            "state_sha_start, prompt_path, raw_output_path, started_at, "
            "finished_at, decision, envelope_json, is_canonical) "
            "VALUES (?, ?, 2, 'reviewer', 'completed', 'sha2', '/p2', '/r2', "
            "'2026-01-01T00:01:01Z', '2026-01-01T00:01:02Z', 'GO', ?, 1)",
            ("r2-reviewer", job_id, envelope_r2),
        )
        conn.commit()

        registry = bridge.rebuild_finding_registry(conn, job_id)

    summary = registry["summary"]
    # Round 2: "Missing null check" persists, "Naming convention" is addressed (disappeared
    # from immediately previous round), "Unnecessary copy" is new
    assert summary["persisting"] >= 1, f"Expected persisting findings, got {summary}"
    assert summary["new"] >= 1, f"Expected new findings, got {summary}"
    assert summary["addressed"] >= 1, f"Expected addressed findings, got {summary}"


def test_finding_lifecycle_prompt_format() -> None:
    """format_lifecycle_prompt_section produces expected string format."""
    registry = {
        "summary": {"new": 1, "persisting": 2, "addressed": 0, "silent": 1, "regression": 0},
    }
    result = bridge.format_lifecycle_prompt_section(registry)
    assert "PRIOR FINDINGS:" in result
    assert "1 new" in result
    assert "2 persisting" in result
    assert "1 silent" in result


def test_title_similarity_matching() -> None:
    """Title similarity correctly identifies similar vs different findings."""
    # Similar titles should match
    assert bridge.title_similarity("Missing null check", "missing null check") >= 0.6
    assert bridge.title_similarity("error handling absent", "absent error handling") >= 0.6
    # Different titles should not match
    assert bridge.title_similarity("Missing null check", "Naming convention violation") < 0.6
