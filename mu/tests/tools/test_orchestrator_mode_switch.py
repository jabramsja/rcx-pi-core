from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from tests.repo_root import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "mu" / "tools" / "session"))
import set_orchestrator_mode as switch  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "mu" / "tools" / "executors"))
import executor_dispatch as dispatch  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "mu" / "tools" / "agents"))
import meta_bridge_supervisor as meta  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "mu" / "tools" / "observability"))
import pipeline_dashboard as dash  # noqa: E402
import pipeline_dashboard_web as web  # noqa: E402


def _seed_repo(tmp_path: Path, *, route: str = "both") -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    bus = repo_root / ".agent_bus"
    bus.mkdir(parents=True)
    cfg_path = repo_root / "mu" / "tools" / "executors" / "executor_config.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        json.dumps(
            {
                "role_agents": {"implementer": "claude", "reviewer": "claude"},
                "bridge_agent_defaults": {
                    "codex": {
                        "display_name": "Local Codex",
                        "model": "gpt-local",
                        "reasoning_effort": "xhigh",
                    },
                    "claude": {
                        "display_name": "Local Claude",
                        "model": "claude-local",
                        "effort": "max",
                    },
                },
                "pipeline_agent_pager": {"enabled": True, "route": route},
                "backends": {
                    "post_merge_supervisor": "codex",
                    "dialectic_executor": "codex",
                    "phase_a_executor": "claude",
                    "phase_b_executor": "claude",
                    "bot_remediation": "claude",
                    "commit_executor": None,
                },
                "bridge_reviewers": {"phase_a": "claude", "phase_b": "claude"},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return repo_root, cfg_path


def _write_pager_state(
    repo_root: Path,
    *,
    pending_target: str = "claude",
    bus_dir: str = ".agent_bus",
) -> Path:
    state_path = repo_root / bus_dir / "observability" / "pipeline_agent_pager_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "events": {
                    "event-1": {
                        "event_id": "event-1",
                        "requested_targets": ["codex", "claude"],
                        "delivered_targets": {"codex": {"ok": True}},
                        "pending_targets": [pending_target],
                    }
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return state_path


def _write_claude_autoping(repo_root: Path, *, pid: int = 4242) -> Path:
    path = repo_root / ".agent_bus" / "observability" / "claude_autoping_session-1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "session_id": "session-1",
                "repo_root": str(repo_root),
                "bus_dir": ".agent_bus",
                "watcher_pid": pid,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_codex_autoping(
    codex_home: Path,
    repo_root: Path,
    *,
    thread_id: str = "thread-1",
    pid: int | None = None,
) -> Path:
    path = codex_home / "state" / f"rcx_autoping_{thread_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "thread_id": thread_id,
                "repo_root": str(repo_root),
                "bus_dir": ".agent_bus",
                "watcher_pid": os.getpid() if pid is None else pid,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _read_config(repo_root: Path) -> dict:
    return json.loads(
        (repo_root / "mu" / "tools" / "executors" / "executor_config.json").read_text(
            encoding="utf-8"
        )
    )


def _watcher_command(repo_root: Path, kind: str, label: str) -> str:
    if kind == "codex":
        return (
            f"python3 {repo_root}/mu/tools/session/codex_autoping_watch.py "
            f"--repo-root {repo_root} --thread-id {label} --bus-dir .agent_bus"
        )
    return (
        f"python3 {repo_root}/mu/tools/session/claude_autoping_watch.py "
        f"--repo-root {repo_root} --session-id {label} --bus-dir .agent_bus"
    )


def _codex_active_ping_command(thread_id: str) -> str:
    return (
        "codex exec resume "
        f"{thread_id} "
        "'Autonomous WorkingRCX pipeline watchdog tick. Active bus root: .agent_bus'"
    )


def _command_reader(commands: dict[int, str]):
    return lambda pid: commands.get(pid, "")


def _live_autoping(
    repo_root: Path,
    kind: str,
    label: str,
    *,
    pid: int = 5555,
) -> switch.LiveAutopingProcess:
    return switch.LiveAutopingProcess(
        kind=kind,
        pid=pid,
        label=label,
        process_type="watcher",
        command=_watcher_command(repo_root, kind, label),
    )


class RecordingRunner:
    def __init__(self, *, pane_stdout: str = "") -> None:
        self.calls: list[list[str]] = []
        self.pane_stdout = pane_stdout

    def __call__(self, cmd, **_kwargs):
        self.calls.append([str(item) for item in cmd])
        stdout = self.pane_stdout if "_pane_processes.sh" in " ".join(map(str, cmd)) else ""
        return subprocess.CompletedProcess(cmd, 0, stdout, "")


def test_dry_run_reports_exact_actions_without_writing_or_launching(tmp_path):
    repo_root, cfg_path = _seed_repo(tmp_path, route="both")
    pager_state = _write_pager_state(repo_root, pending_target="claude")
    _write_claude_autoping(repo_root, pid=4242)
    before_config = cfg_path.read_text(encoding="utf-8")
    before_pager = pager_state.read_text(encoding="utf-8")
    runner = RecordingRunner()
    killed: list[int] = []

    report = switch.apply_orchestrator_mode(
        mode="codex",
        repo_root=repo_root,
        bus_dir=".agent_bus",
        tmux_session="rcx-test",
        dry_run=True,
        verify=True,
        runner=runner,
        pid_exists=lambda _pid: True,
        killer=killed.append,
        command_reader=_command_reader(
            {4242: _watcher_command(repo_root, "claude", "session-1")}
        ),
        codex_thread_id="thread-1",
    )

    assert report.ok
    assert report.config_changed is False
    assert report.state_changed is True
    assert report.skipped_pager_targets == [
        {
            "event_id": "event-1",
            "target": "claude",
            "skip_reason": "orchestrator_mode_switched_to_codex",
        }
    ]
    assert report.stopped_autoping == ["claude:session-1:pid=4242"]
    assert runner.calls == []
    assert killed == []
    assert cfg_path.read_text(encoding="utf-8") == before_config
    assert pager_state.read_text(encoding="utf-8") == before_pager
    assert not (repo_root / ".agent_bus" / "observability" / "orchestrator_mode.json").exists()
    rendered = switch.render_report(report, dry_run=True)
    assert "DRY-RUN orchestrator_mode=codex" in rendered
    assert "effective_pager_route=codex" in rendered
    assert "--orchestrator-mode codex" in rendered
    assert "ensure_codex_autoping.sh" in rendered
    assert "gpt-local" in rendered


def test_apply_writes_route_skips_stale_targets_restarts_surfaces_and_preserves_roles(tmp_path):
    repo_root, _cfg_path = _seed_repo(tmp_path, route="both")
    pager_state = _write_pager_state(repo_root, pending_target="claude")
    _write_claude_autoping(repo_root, pid=4242)
    runner = RecordingRunner()
    killed: list[int] = []

    report = switch.apply_orchestrator_mode(
        mode="codex",
        repo_root=repo_root,
        bus_dir=".agent_bus",
        tmux_session="rcx-test",
        dry_run=False,
        verify=False,
        runner=runner,
        pid_exists=lambda _pid: True,
        killer=killed.append,
        command_reader=_command_reader(
            {4242: _watcher_command(repo_root, "claude", "session-1")}
        ),
        codex_thread_id="thread-1",
    )

    assert report.ok
    config = _read_config(repo_root)
    assert config["pipeline_agent_pager"]["route"] == "both"
    assert config["role_agents"] == {"implementer": "claude", "reviewer": "claude"}
    assert config["backends"]["phase_b_executor"] == "claude"
    assert config["bridge_reviewers"] == {"phase_a": "claude", "phase_b": "claude"}
    state = json.loads(
        (repo_root / ".agent_bus" / "observability" / "orchestrator_mode.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["mode"] == "codex"
    assert state["provider"]["display_name"] == "Local Codex"
    pager = json.loads(pager_state.read_text(encoding="utf-8"))
    event = pager["events"]["event-1"]
    assert event["pending_targets"] == []
    assert event["skipped_targets"]["claude"]["skip_reason"] == "orchestrator_mode_switched_to_codex"
    receipts = (
        repo_root / ".agent_bus" / "observability" / "pipeline_agent_skip_receipts.jsonl"
    ).read_text(encoding="utf-8").splitlines()
    assert len(receipts) == 1
    assert killed == [4242]
    flattened = [" ".join(call) for call in runner.calls]
    assert any("pipeline_monitor.sh --bus-dir .agent_bus --tmux-session rcx-test --orchestrator-mode codex stop" in call for call in flattened)
    assert any("pipeline_monitor.sh --bus-dir .agent_bus --tmux-session rcx-test --orchestrator-mode codex start --detach" in call for call in flattened)
    assert any("ensure_codex_autoping.sh" in call and "--thread-id thread-1" in call for call in flattened)

    second = switch.apply_orchestrator_mode(
        mode="codex",
        repo_root=repo_root,
        bus_dir=".agent_bus",
        tmux_session="rcx-test",
        dry_run=False,
        verify=False,
        runner=RecordingRunner(),
        pid_exists=lambda _pid: False,
        killer=lambda _pid: None,
    )

    assert second.config_changed is False
    assert second.skipped_pager_targets == []
    assert (
        repo_root / ".agent_bus" / "observability" / "pipeline_agent_skip_receipts.jsonl"
    ).read_text(encoding="utf-8").splitlines() == receipts


def test_terminal_skip_uses_pager_lock_and_receipt_helper(monkeypatch, tmp_path):
    repo_root, _cfg_path = _seed_repo(tmp_path, route="both")
    alt_bus = ".agent_bus-alt"
    (repo_root / alt_bus).mkdir()
    pager_state = _write_pager_state(
        repo_root,
        pending_target="claude",
        bus_dir=alt_bus,
    )
    events: list[str] = []
    real_append = switch.pager_append_skip_receipt

    class RecordingLock:
        def __init__(self, locked_repo: Path) -> None:
            assert locked_repo == repo_root

        def __enter__(self):
            events.append("lock-enter")
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            events.append("lock-exit")

    def recording_append(repo_root_arg: Path, *, event_id: str, target: str, skip_reason: str):
        assert events == ["lock-enter"]
        events.append(f"receipt:{event_id}:{target}:{skip_reason}")
        return real_append(
            repo_root_arg,
            event_id=event_id,
            target=target,
            skip_reason=skip_reason,
        )

    monkeypatch.setattr(switch, "PagerLock", RecordingLock)
    monkeypatch.setattr(switch, "pager_append_skip_receipt", recording_append)

    skipped = switch.terminally_skip_opposite_pager_targets(
        repo_root,
        alt_bus,
        "codex",
        dry_run=False,
    )

    assert skipped == [
        {
            "event_id": "event-1",
            "target": "claude",
            "skip_reason": "orchestrator_mode_switched_to_codex",
        }
    ]
    assert events == [
        "lock-enter",
        "receipt:event-1:claude:orchestrator_mode_switched_to_codex",
        "lock-exit",
    ]
    pager = json.loads(pager_state.read_text(encoding="utf-8"))
    assert pager["events"]["event-1"]["pending_targets"] == []
    receipts = (repo_root / alt_bus / "observability" / "pipeline_agent_skip_receipts.jsonl").read_text(
        encoding="utf-8"
    )
    assert "orchestrator_mode_switched_to_codex" in receipts


def test_apply_stops_wrong_autoping_process_without_state_file(tmp_path):
    repo_root, _cfg_path = _seed_repo(tmp_path, route="both")
    live_wrong = _live_autoping(repo_root, "claude", "session-lost")
    runner = RecordingRunner()
    killed: list[int] = []

    report = switch.apply_orchestrator_mode(
        mode="codex",
        repo_root=repo_root,
        bus_dir=".agent_bus",
        tmux_session="rcx-test",
        dry_run=False,
        verify=False,
        runner=runner,
        pid_exists=lambda pid: pid == live_wrong.pid,
        killer=killed.append,
        autoping_scanner=lambda kind, **_kwargs: [live_wrong] if kind == "claude" else [],
        codex_thread_id="thread-1",
    )

    assert report.ok
    assert not (
        repo_root / ".agent_bus" / "observability" / "claude_autoping_session-lost.json"
    ).exists()
    assert report.stopped_autoping == ["claude:session-lost:pid=5555"]
    assert killed == [5555]


def test_apply_verify_fails_without_selected_autoping_watcher(monkeypatch, tmp_path):
    repo_root, _cfg_path = _seed_repo(tmp_path, route="both")
    codex_home = tmp_path / ".codex"
    monkeypatch.setenv("RCX_CODEX_HOME", str(codex_home))
    runner = RecordingRunner()

    report = switch.apply_orchestrator_mode(
        mode="codex",
        repo_root=repo_root,
        bus_dir=".agent_bus",
        tmux_session="rcx-test",
        dry_run=False,
        verify=True,
        runner=runner,
        pid_exists=lambda _pid: False,
        killer=lambda _pid: None,
        codex_thread_id="thread-1",
    )

    assert not report.ok
    assert "no codex autoping state file found for selected root/bus" in "\n".join(
        report.verify_failures
    )
    assert any("ensure_codex_autoping.sh" in " ".join(call) for call in runner.calls)


def test_verify_fails_for_stale_opposite_pending_target_and_wrong_autoping(tmp_path):
    repo_root, _cfg_path = _seed_repo(tmp_path, route="codex")
    _write_pager_state(repo_root, pending_target="claude")
    _write_claude_autoping(repo_root, pid=4242)
    switch._write_json(  # ANTICHEAT_OK: unit test seeds public tool state
        repo_root / ".agent_bus" / "observability" / "orchestrator_mode.json",
        {
            "version": 1,
            "mode": "codex",
            "repo_root": str(repo_root),
            "bus_dir": ".agent_bus",
            "tmux_session": "rcx-test",
        },
    )

    report = switch.verify_orchestrator_mode(
        mode="codex",
        repo_root=repo_root,
        bus_dir=".agent_bus",
        tmux_session="rcx-test",
        runner=RecordingRunner(),
        pid_exists=lambda _pid: True,
        command_reader=_command_reader(
            {4242: _watcher_command(repo_root, "claude", "session-1")}
        ),
        worker_scanner=lambda _root: [],
    )

    assert not report.ok
    joined = "\n".join(report.verify_failures)
    assert "stale opposite-orchestrator pager targets remain pending: event-1:claude" in joined
    assert "wrong orchestrator autoping still live: claude:session-1 pids=[4242]" in joined


def test_verify_fails_for_wrong_autoping_process_without_state_file(monkeypatch, tmp_path):
    repo_root, _cfg_path = _seed_repo(tmp_path, route="codex")
    codex_home = tmp_path / ".codex"
    monkeypatch.setenv("RCX_CODEX_HOME", str(codex_home))
    selected_pid = os.getpid()
    _write_codex_autoping(codex_home, repo_root, pid=selected_pid)
    live_wrong = _live_autoping(repo_root, "claude", "session-lost")
    switch._write_json(  # ANTICHEAT_OK: unit test seeds public tool state
        repo_root / ".agent_bus" / "observability" / "orchestrator_mode.json",
        {
            "version": 1,
            "mode": "codex",
            "repo_root": str(repo_root),
            "bus_dir": ".agent_bus",
            "tmux_session": "rcx-test",
        },
    )

    report = switch.verify_orchestrator_mode(
        mode="codex",
        repo_root=repo_root,
        bus_dir=".agent_bus",
        tmux_session="rcx-test",
        runner=RecordingRunner(),
        pid_exists=lambda pid: pid in {selected_pid, live_wrong.pid},
        command_reader=_command_reader(
            {selected_pid: _watcher_command(repo_root, "codex", "thread-1")}
        ),
        worker_scanner=lambda _root: [],
        autoping_scanner=lambda kind, **_kwargs: [live_wrong] if kind == "claude" else [],
    )

    assert not report.ok
    joined = "\n".join(report.verify_failures)
    assert "wrong orchestrator autoping still live: claude:session-lost pids=[5555]" in joined
    assert "no codex autoping state file found" not in joined


def test_verify_requires_selected_autoping_watcher_not_active_ping(monkeypatch, tmp_path):
    repo_root, _cfg_path = _seed_repo(tmp_path, route="codex")
    codex_home = tmp_path / ".codex"
    monkeypatch.setenv("RCX_CODEX_HOME", str(codex_home))
    autoping_path = _write_codex_autoping(codex_home, repo_root, pid=1111)
    payload = json.loads(autoping_path.read_text(encoding="utf-8"))
    payload["active_pid"] = 2222
    autoping_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    switch._write_json(  # ANTICHEAT_OK: unit test seeds public tool state
        repo_root / ".agent_bus" / "observability" / "orchestrator_mode.json",
        {
            "version": 1,
            "mode": "codex",
            "repo_root": str(repo_root),
            "bus_dir": ".agent_bus",
            "tmux_session": "rcx-test",
        },
    )

    report = switch.verify_orchestrator_mode(
        mode="codex",
        repo_root=repo_root,
        bus_dir=".agent_bus",
        tmux_session="rcx-test",
        runner=RecordingRunner(),
        pid_exists=lambda pid: pid == 2222,
        command_reader=_command_reader({2222: _codex_active_ping_command("thread-1")}),
        worker_scanner=lambda _root: [],
    )

    assert not report.ok
    assert "codex autoping state exists but no watcher pid is live" in "\n".join(
        report.verify_failures
    )


def test_verify_uses_live_worker_provider_not_role_defaults(monkeypatch, tmp_path):
    repo_root, _cfg_path = _seed_repo(tmp_path, route="codex")
    codex_home = tmp_path / ".codex"
    monkeypatch.setenv("RCX_CODEX_HOME", str(codex_home))
    selected_pid = os.getpid()
    _write_codex_autoping(codex_home, repo_root, pid=selected_pid)
    switch._write_json(  # ANTICHEAT_OK: unit test seeds public tool state
        repo_root / ".agent_bus" / "observability" / "orchestrator_mode.json",
        {
            "version": 1,
            "mode": "codex",
            "repo_root": str(repo_root),
            "bus_dir": ".agent_bus",
            "tmux_session": "rcx-test",
        },
    )
    worker = switch.LiveBridgeWorker(
        pid=100,
        provider="codex",
        role="review",
        command=f"codex exec -m gpt-local --cwd {repo_root}",
    )

    passing = switch.verify_orchestrator_mode(
        mode="codex",
        repo_root=repo_root,
        bus_dir=".agent_bus",
        tmux_session="rcx-test",
        runner=RecordingRunner(pane_stdout="WHO'S WORKING\nREVIEWING  Local Codex\n"),
        pid_exists=lambda pid: pid == selected_pid,
        command_reader=_command_reader(
            {selected_pid: _watcher_command(repo_root, "codex", "thread-1")}
        ),
        worker_scanner=lambda _root: [worker],
    )
    assert passing.ok, passing.verify_failures

    blank = switch.verify_orchestrator_mode(
        mode="codex",
        repo_root=repo_root,
        bus_dir=".agent_bus",
        tmux_session="rcx-test",
        runner=RecordingRunner(pane_stdout="Nobody is working right now.\n"),
        pid_exists=lambda pid: pid == selected_pid,
        command_reader=_command_reader(
            {selected_pid: _watcher_command(repo_root, "codex", "thread-1")}
        ),
        worker_scanner=lambda _root: [worker],
    )
    assert not blank.ok
    assert any("Who's Working is blank" in item for item in blank.verify_failures)

    mislabeled = switch.verify_orchestrator_mode(
        mode="codex",
        repo_root=repo_root,
        bus_dir=".agent_bus",
        tmux_session="rcx-test",
        runner=RecordingRunner(pane_stdout="WHO'S WORKING\nREVIEWING  Claude\n"),
        pid_exists=lambda pid: pid == selected_pid,
        command_reader=_command_reader(
            {selected_pid: _watcher_command(repo_root, "codex", "thread-1")}
        ),
        worker_scanner=lambda _root: [worker],
    )
    assert not mislabeled.ok
    assert any("Local Codex" in item for item in mislabeled.verify_failures)
    assert any("displayed as Claude" in item for item in mislabeled.verify_failures)


def test_scan_live_bridge_workers_matches_process_cwd_when_argv_lacks_root(monkeypatch, tmp_path):
    repo_root, _cfg_path = _seed_repo(tmp_path, route="codex")

    class FakeCompleted:
        returncode = 0
        stdout = (
            "101 201 codex exec - --json -m gpt-5.5\n"
            "201 1 python3 mu/tools/executors/phase_b_executor.py "
            "--routing-record .agent_bus/meta/post_merge_routing.json\n"
        )
        stderr = ""

    def fake_run(cmd, **_kwargs):
        assert cmd == ["ps", "-Ao", "pid=,ppid=,command="]
        return FakeCompleted()

    monkeypatch.setattr(switch.subprocess, "run", fake_run)
    monkeypatch.setattr(
        switch,
        "_pid_cwd",
        lambda pid: str(repo_root) if pid == 101 else None,
    )

    workers = switch.scan_live_bridge_workers(repo_root)

    assert [(worker.pid, worker.provider, worker.role) for worker in workers] == [
        (101, "codex", "implement")
    ]


def test_scan_live_bridge_workers_filters_by_selected_bus(monkeypatch, tmp_path):
    repo_root, _cfg_path = _seed_repo(tmp_path, route="codex")

    class FakeCompleted:
        returncode = 0
        stdout = (
            "101 201 codex exec - --json -m gpt-5.5\n"
            "201 1 python3 mu/tools/executors/phase_b_executor.py "
            "--bus-dir .agent_bus-other "
            "--routing-record .agent_bus-other/meta/post_merge_routing.json\n"
        )
        stderr = ""

    def fake_run(cmd, **_kwargs):
        assert cmd == ["ps", "-Ao", "pid=,ppid=,command="]
        return FakeCompleted()

    monkeypatch.setattr(switch.subprocess, "run", fake_run)
    monkeypatch.setattr(
        switch,
        "_pid_cwd",
        lambda pid: str(repo_root) if pid == 101 else None,
    )

    assert switch.scan_live_bridge_workers(repo_root, bus_dir=".agent_bus") == []
    workers = switch.scan_live_bridge_workers(repo_root, bus_dir=".agent_bus-other")
    assert [(worker.pid, worker.provider, worker.role) for worker in workers] == [
        (101, "codex", "implement")
    ]


def test_process_chain_requires_bus_marker_for_named_bus(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    class FakeCompleted:
        returncode = 0
        stdout = (
            f"101 201 codex exec -m gpt-local --cwd {repo_root}\n"
            "201 1 python3 mu/tools/executors/phase_b_executor.py\n"
        )
        stderr = ""

    def fake_run(cmd, **_kwargs):
        assert cmd == ["ps", "-Ao", "pid=,ppid=,command="]
        return FakeCompleted()

    monkeypatch.setattr(switch.subprocess, "run", fake_run)

    workers = switch.scan_live_bridge_workers(repo_root, bus_dir=".agent_bus")
    assert [(worker.pid, worker.provider, worker.role) for worker in workers] == [
        (101, "codex", "implement")
    ]
    assert switch.scan_live_bridge_workers(repo_root, bus_dir=".agent_bus-other") == []


def test_verify_passes_selected_bus_to_live_worker_scanner(monkeypatch, tmp_path):
    repo_root, _cfg_path = _seed_repo(tmp_path, route="codex")
    codex_home = tmp_path / ".codex"
    monkeypatch.setenv("RCX_CODEX_HOME", str(codex_home))
    selected_pid = os.getpid()
    _write_codex_autoping(codex_home, repo_root, pid=selected_pid)
    switch._write_json(  # ANTICHEAT_OK: unit test seeds public tool state
        repo_root / ".agent_bus" / "observability" / "orchestrator_mode.json",
        {
            "version": 1,
            "mode": "codex",
            "repo_root": str(repo_root),
            "bus_dir": ".agent_bus",
            "tmux_session": "rcx-test",
        },
    )
    seen: list[tuple[Path, str]] = []

    def scanner(root: Path, *, bus_dir: str) -> list[switch.LiveBridgeWorker]:
        seen.append((root, bus_dir))
        return []

    report = switch.verify_orchestrator_mode(
        mode="codex",
        repo_root=repo_root,
        bus_dir=".agent_bus",
        tmux_session="rcx-test",
        runner=RecordingRunner(),
        pid_exists=lambda pid: pid == selected_pid,
        command_reader=_command_reader(
            {selected_pid: _watcher_command(repo_root, "codex", "thread-1")}
        ),
        worker_scanner=scanner,
    )

    assert report.ok, report.verify_failures
    assert seen == [(repo_root, ".agent_bus")]


def test_terminal_dashboard_filters_bridge_subprocesses_by_repo_and_bus(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(dash, "REPO_ROOT", repo_root)
    monkeypatch.setattr(dash, "ACTIVE_BUS_DIR", Path(".agent_bus"))
    monkeypatch.setattr(dash, "pid_cwd", lambda _pid: None)
    monkeypatch.setattr(dash, "pid_ppid", lambda _pid: None)
    monkeypatch.setattr(dash, "pid_start", lambda _pid: 0.0)
    monkeypatch.setattr(dash, "bridge_role_for_pid", lambda _pid: "review")

    assert dash.detect_subs([
        "user 999 0.0 0.0 0 0 ?? S 12:00PM 0:00.00 codex exec --worker-from-other-repo"
    ]) == []
    assert dash.detect_subs([
        f"user 999 0.0 0.0 0 0 ?? S 12:00PM 0:00.00 codex exec --repo-root {repo_root} --bus-dir .agent_bus-other"
    ]) == []
    monkeypatch.setattr(dash, "ACTIVE_BUS_DIR", Path(".agent_bus-other"))
    assert dash.detect_subs([
        f"user 999 0.0 0.0 0 0 ?? S 12:00PM 0:00.00 codex exec --repo-root {repo_root}"
    ]) == []
    monkeypatch.setattr(dash, "ACTIVE_BUS_DIR", Path(".agent_bus"))
    assert dash.detect_subs([
        f"user 999 0.0 0.0 0 0 ?? S 12:00PM 0:00.00 codex exec --repo-root {repo_root} --bus-dir .agent_bus"
    ]) == [("codex-review", 999, 0.0)]


def test_web_dashboard_filters_bridge_subprocesses_by_repo_and_bus(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(web, "REPO_ROOT", repo_root)
    monkeypatch.setattr(web, "ACTIVE_BUS_DIR", ".agent_bus")
    monkeypatch.setattr(web, "pid_cwd", lambda _pid: None)
    monkeypatch.setattr(web, "pid_ppid", lambda _pid: None)
    monkeypatch.setattr(web, "pid_start", lambda _pid: 0.0)
    monkeypatch.setattr(web, "bridge_role_for_pid", lambda _pid: "reviewer")
    monkeypatch.setattr(web, "_display_name", lambda agent: agent)

    assert web.detect_subs([
        "user 999 0.0 0.0 0 0 ?? S 12:00PM 0:00.00 codex exec --worker-from-other-repo"
    ]) == []
    assert web.detect_subs([
        f"user 999 0.0 0.0 0 0 ?? S 12:00PM 0:00.00 codex exec --repo-root {repo_root} --bus-dir .agent_bus-other"
    ]) == []
    monkeypatch.setattr(web, "ACTIVE_BUS_DIR", ".agent_bus-other")
    assert web.detect_subs([
        f"user 999 0.0 0.0 0 0 ?? S 12:00PM 0:00.00 codex exec --repo-root {repo_root}"
    ]) == []
    monkeypatch.setattr(web, "ACTIVE_BUS_DIR", ".agent_bus")
    assert web.detect_subs([
        f"user 999 0.0 0.0 0 0 ?? S 12:00PM 0:00.00 codex exec --repo-root {repo_root} --bus-dir .agent_bus"
    ]) == [
        {
            "agent": "codex",
            "name": "codex",
            "role": "reviewer",
            "pid": 999,
            "started": 0.0,
        }
    ]


def test_terminal_dashboard_ignores_claude_autoping_keepalive(monkeypatch):
    line = (
        "jeff 101 0.0 0.0 ?? Ss 0:00.00 claude --resume session-1 "
        "--print 'WorkingRCX dedicated Claude monitor keepalive tick.'"
    )
    monkeypatch.setattr(dash, "pid_cwd", lambda _pid: dash.REPO_ROOT)
    monkeypatch.setattr(dash, "pid_start", lambda _pid: 1.0)
    monkeypatch.setattr(dash, "pid_has_ancestor_matching", lambda *_args, **_kwargs: False)

    assert dash.detect_subs([line]) == []


def test_web_dashboard_ignores_claude_autoping_keepalive(monkeypatch):
    line = (
        "jeff 101 0.0 0.0 ?? Ss 0:00.00 claude --resume session-1 "
        "--print 'WorkingRCX dedicated Claude monitor keepalive tick.'"
    )
    monkeypatch.setattr(web, "pid_cwd", lambda _pid: web.REPO_ROOT)
    monkeypatch.setattr(web, "pid_start", lambda _pid: 1.0)
    monkeypatch.setattr(web, "pid_has_ancestor_matching", lambda *_args, **_kwargs: False)

    assert web.detect_subs([line]) == []


def test_scan_live_bridge_workers_ignores_claude_autoping_keepalive(monkeypatch, tmp_path):
    repo_root, _cfg_path = _seed_repo(tmp_path, route="claude")

    class FakeCompleted:
        returncode = 0
        stdout = (
            "101 1 claude --resume session-1 --print "
            "'WorkingRCX dedicated Claude monitor keepalive tick.\\n"
            "Active bus root: .agent_bus'\n"
        )
        stderr = ""

    def fake_run(cmd, **_kwargs):
        assert cmd == ["ps", "-Ao", "pid=,ppid=,command="]
        return FakeCompleted()

    monkeypatch.setattr(switch.subprocess, "run", fake_run)

    assert switch.scan_live_bridge_workers(repo_root) == []


def test_stop_autoping_preserves_live_pid_that_is_not_matching_watcher(tmp_path):
    repo_root, _cfg_path = _seed_repo(tmp_path, route="codex")
    record = switch.AutopingRecord(
        kind="claude",
        path=repo_root / ".agent_bus" / "observability" / "claude_autoping_session-1.json",
        watcher_pid=4242,
        active_pid=None,
        repo_root=str(repo_root),
        bus_dir=".agent_bus",
        label="session-1",
    )
    killed: list[int] = []

    stopped = switch.stop_autoping_records(
        [record],
        dry_run=False,
        pid_exists=lambda _pid: True,
        killer=killed.append,
        command_reader=_command_reader({4242: "sleep 999"}),
    )

    assert stopped == []
    assert killed == []


def test_scan_live_autoping_processes_finds_repo_bus_watcher_without_state(
    monkeypatch, tmp_path
):
    repo_root, _cfg_path = _seed_repo(tmp_path, route="codex")

    class FakeCompleted:
        returncode = 0
        stdout = f"5555 1 {_watcher_command(repo_root, 'claude', 'session-lost')}\n"
        stderr = ""

    def fake_run(cmd, **_kwargs):
        assert cmd == ["ps", "-ww", "-Ao", "pid=,ppid=,command="]
        return FakeCompleted()

    monkeypatch.setattr(switch.subprocess, "run", fake_run)

    processes = switch.scan_live_autoping_processes(
        "claude",
        repo_root=repo_root,
        bus_dir=".agent_bus",
    )

    assert processes == [
        switch.LiveAutopingProcess(
            kind="claude",
            pid=5555,
            label="session-lost",
            process_type="watcher",
            command=_watcher_command(repo_root, "claude", "session-lost"),
        )
    ]


def _write_dummy_watchers(repo_root: Path, *names: str) -> None:
    session_dir = repo_root / "mu" / "tools" / "session"
    session_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        target = session_dir / name
        target.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        target.chmod(0o755)


def test_autoping_wrappers_resolve_mu_session_targets_for_selected_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_dummy_watchers(
        repo_root,
        "codex_autoping_watch.py",
        "codex_autoping_window.sh",
        "claude_autoping_watch.py",
    )
    obs = repo_root / ".agent_bus" / "observability"
    obs.mkdir(parents=True)
    (obs / "claude_monitor_session_id").write_text("session-1\n", encoding="utf-8")
    env = os.environ.copy()
    env.pop("RCX_PIPELINE_SESSION", None)

    codex = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "mu" / "tools" / "session" / "ensure_codex_autoping.sh"),
            "--repo",
            str(repo_root),
            "--thread-id",
            "thread-1",
            "--bus-dir",
            ".agent_bus",
            "--tmux-session",
            "rcx-test-wrapper",
        ],
        capture_output=True,
        text=True,
        env=env | {"RCX_CODEX_HOME": str(tmp_path / ".codex")},
        timeout=10,
    )
    assert codex.returncode == 0, codex.stderr
    assert (
        f"Autoping watcher: {repo_root}/mu/tools/session/codex_autoping_watch.py"
        in codex.stdout
    )

    claude = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "mu" / "tools" / "session" / "ensure_claude_autoping.sh"),
            "--repo",
            str(repo_root),
            "--session-id",
            "session-1",
            "--bus-dir",
            ".agent_bus",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert claude.returncode == 0, claude.stderr
    assert (
        f"Autoping watcher: {repo_root}/mu/tools/session/claude_autoping_watch.py"
        in claude.stdout
    )


def test_codex_autoping_wrapper_replaces_duplicate_tmux_windows_by_id(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_dummy_watchers(
        repo_root,
        "codex_autoping_watch.py",
        "codex_autoping_window.sh",
    )
    tmux_log = tmp_path / "tmux.log"
    tmux_bin = tmp_path / "tmux-bin"
    tmux_bin.mkdir()
    _write_exec(
        tmux_bin / "tmux",
        f"""#!/usr/bin/env bash
printf '%s\\n' "$*" >> {str(tmux_log)!r}
case "${{1:-}}" in
  has-session) exit 0 ;;
  list-windows)
    printf '@2 AUTO-PING\\n@3 AUTO-PING\\n'
    exit 0
    ;;
  kill-window|new-window) exit 0 ;;
  *) exit 1 ;;
esac
""",
    )
    env = os.environ.copy()
    env.pop("RCX_PIPELINE_SESSION", None)
    env["PATH"] = f"{tmux_bin}:{env['PATH']}"
    env["RCX_CODEX_HOME"] = str(tmp_path / ".codex")

    codex = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "mu" / "tools" / "session" / "ensure_codex_autoping.sh"),
            "--repo",
            str(repo_root),
            "--thread-id",
            "thread-1",
            "--bus-dir",
            ".agent_bus",
            "--tmux-session",
            "rcx-test-wrapper",
            "--force-restart",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )

    assert codex.returncode == 0, codex.stderr
    log_text = tmux_log.read_text(encoding="utf-8")
    assert "kill-window -t @2" in log_text
    assert "kill-window -t @3" in log_text
    assert "new-window -d -t rcx-test-wrapper -n AUTO-PING" in log_text


def test_codex_autoping_status_renders_repo_root_and_bus_dir(tmp_path):
    codex_home = tmp_path / ".codex"
    state_dir = codex_home / "state"
    state_dir.mkdir(parents=True)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (state_dir / "rcx_autoping_thread-1.json").write_text(
        json.dumps(
            {
                "thread_id": "thread-1",
                "watcher_pid": 1234,
                "status": "initial_delay",
                "repo_root": str(repo_root),
                "bus_dir": ".agent_bus-codexmode",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rendered = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "mu" / "tools" / "session" / "render_codex_autoping_status.py"),
            "--thread-id",
            "thread-1",
        ],
        capture_output=True,
        text=True,
        env=os.environ | {"RCX_CODEX_HOME": str(codex_home)},
        timeout=10,
    )

    assert rendered.returncode == 0, rendered.stderr
    assert f"repo_root: {repo_root}" in rendered.stdout
    assert "bus_dir: .agent_bus-codexmode" in rendered.stdout


def _write_exec(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _write_pane_test_repo(repo_root: Path) -> Path:
    obs = repo_root / "mu" / "tools" / "observability"
    obs.mkdir(parents=True, exist_ok=True)
    pane = obs / "_pane_processes.sh"
    pane.write_text(
        (REPO_ROOT / "mu" / "tools" / "observability" / "_pane_processes.sh").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    pane.chmod(0o755)
    timeline = obs / "_pane_timeline.sh"
    timeline.write_text(
        (REPO_ROOT / "mu" / "tools" / "observability" / "_pane_timeline.sh").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    timeline.chmod(0o755)
    _write_exec(obs / "_resolve_live_root.sh", f"#!/usr/bin/env bash\nprintf '%s\\n' {shlex.quote(str(repo_root))}\n")
    executors = repo_root / "mu" / "tools" / "executors"
    executors.mkdir(parents=True, exist_ok=True)
    (executors / "executor_common.py").write_text(
        """
from pathlib import Path

def configured_role_agents(repo_root: Path, bus_dir=None):
    return {
        "reviewer": {"display_name": "Claude Role Default", "status_name": "Claude"},
        "implementer": {"display_name": "Claude Role Default", "status_name": "Claude"},
    }

def bridge_agent_display_name(repo_root: Path, agent_name: str, bus_dir=None):
    return {"codex": "Local Codex", "claude": "Local Claude"}.get(agent_name, agent_name.title())
""".lstrip(),
        encoding="utf-8",
    )
    (repo_root / ".agent_bus" / "meta" / "pre_commit_receipts").mkdir(parents=True, exist_ok=True)
    return pane


def _write_fake_process_tools(bin_dir: Path, repo_root: Path) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    repo_q = shlex.quote(str(repo_root))
    _write_exec(
        bin_dir / "pgrep",
        """#!/usr/bin/env bash
printf '%s\n' 101 102 103 104 105 106 107
""",
    )
    _write_exec(
        bin_dir / "ps",
        f"""#!/usr/bin/env bash
if [ "${{1:-}}" != "-p" ]; then
  exit 1
fi
pid="${{2:-}}"
field="${{4:-}}"
case "$field" in
  command=)
    case "$pid" in
      101|102|103|104|105|106) printf '%s\\n' "codex exec -m gpt-local --global-worker-$pid" ;;
      107) printf '%s\\n' "codex exec -m gpt-local --repo {repo_q} --worker relevant" ;;
      207) printf '%s\\n' "python3 mu/tools/agents/bridge_supervisor.py --bus-dir .agent_bus --repo-root {repo_q} review --reviewer codex" ;;
      *) exit 1 ;;
    esac
    ;;
  ppid=)
    case "$pid" in
      107) printf '%s\\n' 207 ;;
      207) printf '%s\\n' 1 ;;
      *) printf '%s\\n' 1 ;;
    esac
    ;;
  lstart=)
    printf '%s\\n' "Fri Jun 19 12:00:00 2026"
    ;;
  *)
    exit 1
    ;;
esac
""",
    )
    _write_exec(
        bin_dir / "lsof",
        f"""#!/usr/bin/env bash
pid=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-p" ]; then
    pid="${{2:-}}"
    shift 2
  else
    shift
  fi
done
case "$pid" in
  107) printf 'n%s\\n' {repo_q} ;;
  *) printf 'n/tmp\\n' ;;
esac
""",
    )
    _write_exec(
        bin_dir / "git",
        f"""#!/usr/bin/env bash
if [ "${{1:-}}" = "-C" ]; then
  shift 2
fi
case "$*" in
  "rev-parse --show-toplevel") printf '%s\\n' {repo_q} ;;
  "rev-parse --abbrev-ref HEAD") printf '%s\\n' pane-test ;;
  *) exit 1 ;;
esac
""",
    )


def test_pane_bus_filters_require_marker_for_named_bus(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    repo_q = shlex.quote(str(repo_root))
    for script_name in ("_pane_processes.sh", "_pane_timeline.sh"):
        script_path = REPO_ROOT / "mu" / "tools" / "observability" / script_name
        source_q = shlex.quote(str(script_path))
        shell = f"""
repo_path={repo_q}
BUS_DIR=.agent_bus-other
RCX_AGENT_BUS_DIR=.agent_bus-other
source {source_q}
pid_command() {{
  case "$1" in
    101) printf '%s\\n' "codex exec -m gpt-local --cwd $repo_path" ;;
    102) printf '%s\\n' "codex exec -m gpt-local --cwd $repo_path --bus-dir .agent_bus-other" ;;
    201) printf '%s\\n' "python3 mu/tools/executors/phase_b_executor.py" ;;
    *) printf '%s\\n' "" ;;
  esac
}}
pid_ppid() {{
  case "$1" in
    101|102) printf '%s\\n' 201 ;;
    201) printf '%s\\n' 1 ;;
    *) printf '%s\\n' "" ;;
  esac
}}
if pid_matches_selected_bus_dir 101; then
  echo "markerless chain matched named bus"
  exit 11
fi
if ! pid_matches_selected_bus_dir 102; then
  echo "explicit named bus marker was rejected"
  exit 12
fi
BUS_DIR=.agent_bus
RCX_AGENT_BUS_DIR=.agent_bus
if ! pid_matches_selected_bus_dir 101; then
  echo "markerless default-bus chain was rejected"
  exit 13
fi
"""
        result = subprocess.run(
            ["bash", "-lc", shell],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"{script_name}: {result.stdout}{result.stderr}"


def test_pane_processes_filters_by_repo_before_rendering_live_codex_reviewer(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pane = _write_pane_test_repo(repo_root)
    fake_bin = tmp_path / "fake-bin"
    _write_fake_process_tools(fake_bin, repo_root)

    result = subprocess.run(
        ["bash", str(pane)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=os.environ
        | {
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "BUS_DIR": ".agent_bus",
            "RCX_AGENT_BUS_DIR": ".agent_bus",
            "RCX_PANE_ONESHOT": "1",
            "RCX_PANE_ENABLE_PROCESS_SCAN": "1",
            "RCX_PANE_MAX_LINES": "120",
            "TERM": "xterm",
        },
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert "WHO'S WORKING" in result.stdout
    assert "REVIEWING" in result.stdout
    assert "Local Codex" in result.stdout
    assert "PIDs: 107" in result.stdout
    assert "Claude Role Default" not in result.stdout


def test_pane_processes_filters_bridge_workers_by_selected_bus(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pane = _write_pane_test_repo(repo_root)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    repo_q = shlex.quote(str(repo_root))
    _write_exec(fake_bin / "pgrep", "#!/usr/bin/env bash\nprintf '%s\\n' 107\n")
    _write_exec(
        fake_bin / "ps",
        f"""#!/usr/bin/env bash
if [ "${{1:-}}" != "-p" ]; then
  exit 1
fi
pid="${{2:-}}"
field="${{4:-}}"
case "$field" in
  command=)
    case "$pid" in
      107) printf '%s\\n' "codex exec -m gpt-local --repo {repo_q} --worker other-bus" ;;
      207) printf '%s\\n' "python3 mu/tools/agents/bridge_supervisor.py --bus-dir .agent_bus-other --repo-root {repo_q} review --reviewer codex" ;;
      *) exit 1 ;;
    esac
    ;;
  ppid=)
    case "$pid" in
      107) printf '%s\\n' 207 ;;
      207) printf '%s\\n' 1 ;;
      *) printf '%s\\n' 1 ;;
    esac
    ;;
  lstart=)
    printf '%s\\n' "Fri Jun 19 12:00:00 2026"
    ;;
  *)
    exit 1
    ;;
esac
""",
    )
    _write_exec(fake_bin / "lsof", f"#!/usr/bin/env bash\nprintf 'n%s\\n' {repo_q}\n")
    _write_exec(
        fake_bin / "git",
        f"""#!/usr/bin/env bash
if [ "${{1:-}}" = "-C" ]; then
  shift 2
fi
case "$*" in
  "rev-parse --show-toplevel") printf '%s\\n' {repo_q} ;;
  "rev-parse --abbrev-ref HEAD") printf '%s\\n' pane-test ;;
  *) exit 1 ;;
esac
""",
    )

    result = subprocess.run(
        ["bash", str(pane)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=os.environ
        | {
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "BUS_DIR": ".agent_bus",
            "RCX_AGENT_BUS_DIR": ".agent_bus",
            "RCX_PANE_ONESHOT": "1",
            "RCX_PANE_ENABLE_PROCESS_SCAN": "1",
            "RCX_PANE_MAX_LINES": "120",
            "TERM": "xterm",
        },
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert "Nobody is working right now." in result.stdout
    assert "Local Codex" not in result.stdout


def test_pane_timeline_filters_bridge_worker_by_selected_bus(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_pane_test_repo(repo_root)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    repo_q = shlex.quote(str(repo_root))
    _write_exec(fake_bin / "pgrep", "#!/usr/bin/env bash\nprintf '%s\\n' 107\n")
    _write_exec(
        fake_bin / "ps",
        f"""#!/usr/bin/env bash
if [ "${{1:-}}" != "-p" ]; then
  exit 1
fi
pid="${{2:-}}"
field="${{4:-}}"
case "$field" in
  command=)
    case "$pid" in
      107) printf '%s\\n' "codex exec -m gpt-local --repo {repo_q} --worker wrong-bus" ;;
      207) printf '%s\\n' "python3 mu/tools/agents/bridge_supervisor.py --bus-dir .agent_bus-other --repo-root {repo_q} review --reviewer codex" ;;
      *) exit 1 ;;
    esac
    ;;
  ppid=)
    case "$pid" in
      107) printf '%s\\n' 207 ;;
      207) printf '%s\\n' 1 ;;
      *) printf '%s\\n' 1 ;;
    esac
    ;;
  lstart=)
    printf '%s\\n' "Fri Jun 19 12:00:00 2026"
    ;;
  *)
    exit 1
    ;;
esac
""",
    )
    _write_exec(fake_bin / "lsof", f"#!/usr/bin/env bash\nprintf 'n%s\\n' {repo_q}\n")
    _write_exec(
        fake_bin / "git",
        f"""#!/usr/bin/env bash
if [ "${{1:-}}" = "-C" ]; then
  shift 2
fi
case "$*" in
  "rev-parse --show-toplevel") printf '%s\\n' {repo_q} ;;
  "rev-parse --abbrev-ref HEAD") printf '%s\\n' pane-test ;;
  log*) exit 0 ;;
  *) exit 1 ;;
esac
""",
    )

    result = subprocess.run(
        ["bash", str(repo_root / "mu" / "tools" / "observability" / "_pane_timeline.sh")],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=os.environ
        | {
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "BUS_DIR": ".agent_bus",
            "RCX_AGENT_BUS_DIR": ".agent_bus",
            "RCX_PANE_ONESHOT": "1",
            "TERM": "xterm",
        },
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert "← idle" in result.stdout
    assert "reviewing now" not in result.stdout


def test_pane_processes_does_not_render_claude_autoping_keepalive_as_worker(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pane = _write_pane_test_repo(repo_root)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    repo_q = shlex.quote(str(repo_root))
    _write_exec(fake_bin / "pgrep", "#!/usr/bin/env bash\nprintf '%s\\n' 101\n")
    _write_exec(
        fake_bin / "ps",
        f"""#!/usr/bin/env bash
if [ "${{1:-}}" != "-p" ]; then
  exit 1
fi
pid="${{2:-}}"
field="${{4:-}}"
case "$field" in
  command=)
    case "$pid" in
      101) printf '%s\\n' "claude --resume session-1 --print 'WorkingRCX dedicated Claude monitor keepalive tick.'" ;;
      *) exit 1 ;;
    esac
    ;;
  ppid=)
    printf '%s\\n' 1
    ;;
  lstart=)
    printf '%s\\n' "Fri Jun 19 12:00:00 2026"
    ;;
  *)
    exit 1
    ;;
esac
""",
    )
    _write_exec(fake_bin / "lsof", f"#!/usr/bin/env bash\nprintf 'n%s\\n' {repo_q}\n")
    _write_exec(
        fake_bin / "git",
        f"""#!/usr/bin/env bash
if [ "${{1:-}}" = "-C" ]; then
  shift 2
fi
case "$*" in
  "rev-parse --show-toplevel") printf '%s\\n' {repo_q} ;;
  "rev-parse --abbrev-ref HEAD") printf '%s\\n' pane-test ;;
  *) exit 1 ;;
esac
""",
    )

    result = subprocess.run(
        ["bash", str(pane)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=os.environ
        | {
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "BUS_DIR": ".agent_bus",
            "RCX_AGENT_BUS_DIR": ".agent_bus",
            "RCX_PANE_ONESHOT": "1",
            "RCX_PANE_ENABLE_PROCESS_SCAN": "1",
            "RCX_PANE_MAX_LINES": "120",
            "TERM": "xterm",
        },
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert "Nobody is working right now." in result.stdout
    assert "Local Claude" not in result.stdout


def test_phase_a_surface_help_uses_neutral_agent_request_name(tmp_path, capsys):
    parser = dispatch.build_surface_parser()
    try:
        parser.parse_args(["phase-a", "--help"])
    except SystemExit as exc:
        assert exc.code == 0
    else:
        raise AssertionError("phase-a --help should exit after rendering help")
    help_text = capsys.readouterr().out
    assert "--request-for-agent" in help_text
    assert "--request-for-claude" not in help_text
    assert "Detailed Phase A request." in help_text

    args = parser.parse_args(
        [
            "phase-a",
            "--plan-name",
            "neutral-request-surface-2026-06-19",
            "--request-for-agent",
            "Create a neutral Phase A packet.",
        ]
    )
    assert getattr(args, "request_for_agent") == "Create a neutral Phase A packet."
    assert not hasattr(args, "request_for_claude")

    legacy_args = parser.parse_args(
        [
            "phase-a",
            "--plan-name",
            "neutral-request-surface-2026-06-19",
            "--request-for-claude",
            "Legacy compatibility input.",
        ]
    )
    assert getattr(legacy_args, "request_for_agent") == "Legacy compatibility input."
    assert not hasattr(legacy_args, "request_for_claude")

    record = dispatch._surface_record_for_chain(args, tmp_path)  # ANTICHEAT_OK: parser surface regression
    assert record["request_for_agent"] == "Create a neutral Phase A packet."
    assert record["request_for_claude"] == "Create a neutral Phase A packet."


def test_post_merge_routing_writer_emits_neutral_request_field(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    class FakeState:
        head_sha = "head-sha"
        state_sha = "state-sha"

    monkeypatch.setattr(meta, "compute_repo_state", lambda _repo_root: FakeState())
    monkeypatch.setattr(meta, "utc_now", lambda: "2026-06-19T00:00:00+00:00")

    response = meta.MetaBridgeResponse(
        status="success",
        decision=meta.Decision.ROUTE_PHASE_A.value,
        summary="Route the next bounded wave.",
        request_for_claude="Create a neutral Phase A packet.",
    )

    path = meta.write_post_merge_routing_record(
        response,
        {"wave_name": "neutral-routing-2026-06-19", "task_id": "[NEXT]"},
        repo_root,
        bus_dir=".agent_bus",
    )

    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["request_for_agent"] == "Create a neutral Phase A packet."
    assert record["request_for_claude"] == "Create a neutral Phase A packet."
