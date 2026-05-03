from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from mu.tests.tools.module_loader import load_module
from tests.repo_root import REPO_ROOT


TOOLS_DIR = REPO_ROOT / "mu" / "tools"
EXECUTORS_DIR = TOOLS_DIR / "executors"
AGENTS_DIR = TOOLS_DIR / "agents"
OBSERVABILITY_DIR = TOOLS_DIR / "observability"

for candidate in (EXECUTORS_DIR, AGENTS_DIR, OBSERVABILITY_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

executor_common = load_module("executor_common", EXECUTORS_DIR / "executor_common.py")
commit_executor = load_module("commit_executor", EXECUTORS_DIR / "commit_executor.py")
phase_b = load_module("phase_b_bus_namespacing", EXECUTORS_DIR / "phase_b_executor.py")
dialectic = load_module("dialectic_executor_bus_namespacing", EXECUTORS_DIR / "dialectic_executor.py")
bridge = load_module("bridge_supervisor_bus_namespacing", AGENTS_DIR / "bridge_supervisor.py")
meta = load_module("meta_bridge_supervisor_bus_namespacing", AGENTS_DIR / "meta_bridge_supervisor.py")
pager = load_module("pipeline_agent_pager_bus_namespacing", OBSERVABILITY_DIR / "pipeline_agent_pager.py")
recovery = load_module("recovery_gate_bus_namespacing", EXECUTORS_DIR / "recovery_gate.py")
monitor_identity = load_module(
    "pipeline_monitor_identity_bus_namespacing",
    OBSERVABILITY_DIR / "pipeline_monitor_identity.py",
)
dashboard_web = load_module(
    "pipeline_dashboard_web_bus_namespacing",
    OBSERVABILITY_DIR / "pipeline_dashboard_web.py",
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _init_git_repo(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.name", "Bus Test")
    _git(repo, "config", "user.email", "bus@example.com")
    (repo / "README.md").write_text("bus test\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")
    (repo / "tracked.txt").write_text("staged change\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")


def _write_pager_config(repo: Path) -> None:
    config_path = repo / "mu" / "tools" / "executors" / "executor_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps({"pipeline_agent_pager": {"enabled": True, "route": "notify-only"}}) + "\n",
        encoding="utf-8",
    )


def _write_monitor_identity_config(repo: Path, lanes: dict[str, dict[str, object]]) -> None:
    config_path = repo / "mu" / "tools" / "executors" / "executor_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps({"pipeline_monitor": {"lanes": lanes}}) + "\n",
        encoding="utf-8",
    )


def _event_kwargs(**overrides):
    payload = {
        "event_type": "commit_ready",
        "wave_id": "wave-bus",
        "task_id": "[BUS]",
        "plan_path": "reports/control_plane/bus.md",
        "phase": "phase_b",
        "state": "commit_ready",
        "transition_key": "bus-ready",
        "summary": "ready",
        "reason": "receipt available",
        "artifact_paths": {"receipt": ".agent_bus-test/meta/pre_commit_receipts/r.json"},
    }
    payload.update(overrides)
    return payload


def _tracker_note(wave_id: str, target_gate_id: str) -> str:
    return (
        f"- Tracker sync note (2026-04-29, {wave_id}): **TEST - bus namespace handoff.** "
        "Class: L4_ENABLER. "
        f"target_gate_id: {target_gate_id}. "
        "evidence_command: `python3 -m pytest mu/tests/tools/test_agent_bus_namespacing.py`. "
        "evidence_delta: (1) Namespaced bus paths are covered. "
        "(2) Commit handoff writes to the active bus. "
        "(3) Default bus state is not consumed for invocation-owned paths. "
        "progress_proof_before: Handoff paths used only the default bus. "
        "progress_proof_after: Handoff paths follow the active invocation bus. "
        "primary_blocker_class: INTEGRATION. "
        "primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
        f"indicator_artifact_ref: reports/l4_wave_indicators/{wave_id}.json. "
        f"indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id {wave_id} --output reports/l4_wave_indicators/{wave_id}.json. "
        "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
        "boot0_track_id: V1. boot0_progress_state: HOLD."
    )


def test_agent_bus_resolver_defaults_namespaces_and_rejects_invalid_paths(tmp_path):
    assert executor_common.agent_bus_relpath() == Path(".agent_bus")
    assert executor_common.routing_record_path(tmp_path) == (
        tmp_path / ".agent_bus" / "meta" / "post_merge_routing.json"
    )
    assert executor_common.resolve_agent_bus_dir(tmp_path, ".agent_bus-test") == (
        tmp_path / ".agent_bus-test"
    )

    default_routing = tmp_path / ".agent_bus" / "meta" / "post_merge_routing.json"
    default_routing.parent.mkdir(parents=True)
    default_routing.write_text(
        json.dumps({"decision": "ROUTE_PHASE_B", "summary": "default", "wave_id": "default"}) + "\n",
        encoding="utf-8",
    )
    namespaced_routing = tmp_path / ".agent_bus-test" / "meta" / "post_merge_routing.json"
    namespaced_routing.parent.mkdir(parents=True)
    namespaced_routing.write_text(
        json.dumps({"decision": "ROUTE_PHASE_B", "summary": "namespaced", "wave_id": "namespaced"}) + "\n",
        encoding="utf-8",
    )

    loaded = executor_common.load_routing_record(tmp_path, bus_dir=".agent_bus-test")
    assert loaded["wave_id"] == "namespaced"

    for invalid in ("/tmp/.agent_bus-x", ".agent_bus/nested", "../.agent_bus-x", ".scratch", ".agent_bus-"):
        with pytest.raises(executor_common.ExecutorCommonError):
            executor_common.resolve_agent_bus_dir(tmp_path, invalid)
    assert not (tmp_path / ".scratch").exists()


def test_monitor_identity_defaults_and_two_named_lanes_are_distinct(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    default_identity = monitor_identity.resolve_monitor_identity(repo)
    assert default_identity.bus_dir == ".agent_bus"
    assert default_identity.active_bus_root == repo / ".agent_bus"
    assert default_identity.dashboard_port == 8099
    assert default_identity.tmux_session == "rcx-pipeline"

    _write_monitor_identity_config(
        repo,
        {
            "alpha": {
                "bus_dir": ".agent_bus-alpha",
                "dashboard_port": 8101,
                "tmux_session": "rcx-pipeline-alpha",
            },
            "beta": {
                "bus_dir": ".agent_bus-beta",
                "dashboard_port": 8102,
                "tmux_session": "rcx-pipeline-beta",
            },
        },
    )

    alpha = monitor_identity.resolve_monitor_identity(repo, bus_dir=".agent_bus-alpha")
    beta = monitor_identity.resolve_monitor_identity(repo, lane="beta")

    assert alpha.active_bus_root == repo / ".agent_bus-alpha"
    assert beta.active_bus_root == repo / ".agent_bus-beta"
    assert {alpha.dashboard_port, beta.dashboard_port} == {8101, 8102}
    assert {alpha.tmux_session, beta.tmux_session} == {
        "rcx-pipeline-alpha",
        "rcx-pipeline-beta",
    }


@pytest.mark.parametrize(
    ("lanes", "message"),
    [
        (
            {
                "port-only": {
                    "dashboard_port": 8103,
                    "tmux_session": "rcx-pipeline-port-only",
                }
            },
            "missing active bus root",
        ),
        (
            {
                "missing-port": {
                    "bus_dir": ".agent_bus-missing-port",
                    "tmux_session": "rcx-pipeline-missing-port",
                }
            },
            "missing dashboard_port",
        ),
        (
            {
                "bad-session": {
                    "bus_dir": ".agent_bus-bad-session",
                    "dashboard_port": 8104,
                    "tmux_session": "bad:session",
                }
            },
            "invalid tmux session",
        ),
        (
            {
                "bad-port": {
                    "bus_dir": ".agent_bus-bad-port",
                    "dashboard_port": 70000,
                    "tmux_session": "rcx-pipeline-bad-port",
                }
            },
            "invalid dashboard_port",
        ),
        (
            {
                "bad-fractional-port": {
                    "bus_dir": ".agent_bus-bad-fractional-port",
                    "dashboard_port": 8101.9,
                    "tmux_session": "rcx-pipeline-bad-fractional-port",
                }
            },
            "invalid dashboard_port",
        ),
        (
            {
                "alpha": {
                    "bus_dir": ".agent_bus-alpha",
                    "dashboard_port": 8105,
                    "tmux_session": "rcx-pipeline-alpha",
                },
                "beta": {
                    "bus_dir": ".agent_bus-beta",
                    "dashboard_port": 8105,
                    "tmux_session": "rcx-pipeline-beta",
                },
            },
            "duplicate dashboard port",
        ),
        (
            {
                "alpha": {
                    "bus_dir": ".agent_bus-alpha",
                    "dashboard_port": 8106,
                    "tmux_session": "rcx-pipeline-shared",
                },
                "beta": {
                    "bus_dir": ".agent_bus-beta",
                    "dashboard_port": 8107,
                    "tmux_session": "rcx-pipeline-shared",
                },
            },
            "duplicate tmux session",
        ),
        (
            {
                "alpha": {
                    "bus_dir": ".agent_bus-shared",
                    "dashboard_port": 8108,
                    "tmux_session": "rcx-pipeline-alpha",
                },
                "beta": {
                    "bus_dir": ".agent_bus-shared",
                    "dashboard_port": 8109,
                    "tmux_session": "rcx-pipeline-beta",
                },
            },
            "shared lock contention",
        ),
    ],
)
def test_monitor_identity_config_fails_closed_for_invalid_named_lanes(tmp_path, lanes, message):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_monitor_identity_config(repo, lanes)

    with pytest.raises(monitor_identity.MonitorIdentityError, match=message):
        monitor_identity.resolve_monitor_identity(repo, bus_dir=".agent_bus-alpha")


def test_bridge_receipt_and_phase_b_handoff_use_namespaced_bus(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)

    paths = bridge.bridge_paths(repo, bus_dir=".agent_bus-test")
    assert paths.bus_dir == repo / ".agent_bus-test"
    assert paths.db_path == repo / ".agent_bus-test" / "bridge.db"
    assert paths.prompts_dir == repo / ".agent_bus-test" / "prompts"
    assert paths.raw_dir == repo / ".agent_bus-test" / "raw"
    assert paths.rendered_dir == repo / ".agent_bus-test" / "rendered"

    package_path = repo / ".agent_bus-test" / "meta" / "pre_commit_package.json"
    package_path.parent.mkdir(parents=True)
    package_path.write_text(json.dumps({"task_id": "[BUS]"}) + "\n", encoding="utf-8")
    response = meta.MetaBridgeResponse(status="success", decision="COMMIT_GO", summary="ok")
    receipt_path = meta.write_pre_commit_receipt(
        response,
        package_path,
        repo_root=repo,
        bus_dir=".agent_bus-test",
    )
    assert receipt_path.is_relative_to(repo / ".agent_bus-test" / "meta" / "pre_commit_receipts")
    assert (repo / ".agent_bus-test" / "meta" / "pre_commit_receipt.json").exists()
    assert not (repo / ".agent_bus" / "meta" / "pre_commit_receipt.json").exists()

    ok, message = meta.verify_pre_commit_receipt(
        repo,
        receipt_path=receipt_path,
        bus_dir=".agent_bus-test",
    )
    assert ok, message

    wave_id = "bus-namespace-wave"
    handoff_path = phase_b.prepare_commit_handoff(
        repo,
        wave_id=wave_id,
        task_id="[BUS]",
        wave_class="L4_ENABLER",
        target_gate_id="G8",
        files_to_stage=["tracked.txt"],
        commit_message="feat: bus namespace\n\nCo-Authored-By: test",
        fixes_implemented=["bus namespace"],
        tracker_note_text=_tracker_note(wave_id, "G8"),
        bus_dir=".agent_bus-test",
    )
    assert handoff_path == repo / ".agent_bus-test" / "executors" / "phase_b_handoff.json"
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    assert handoff["pre_commit_receipt_path"] == ".agent_bus-test/meta/pre_commit_receipt.json"
    assert not (repo / ".agent_bus" / "executors" / "phase_b_handoff.json").exists()


def test_dialectic_executor_uses_namespaced_bus_for_routing_bridge_artifacts_and_result(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    default_routing = repo / ".agent_bus" / "meta" / "post_merge_routing.json"
    default_routing.parent.mkdir(parents=True)
    default_routing.write_text(
        json.dumps(
            {
                "decision": "CONTINUE_DIALECTIC",
                "summary": "stale default routing",
                "next_candidates": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    namespaced_routing = repo / ".agent_bus-test" / "meta" / "post_merge_routing.json"
    namespaced_routing.parent.mkdir(parents=True)
    namespaced_routing.write_text(
        json.dumps(
            {
                "decision": "CONTINUE_DIALECTIC",
                "summary": "active routing",
                "next_candidates": [{"candidate": "narrow me", "bounded": False}],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    bridge_calls = []

    def fake_bridge(cmd, cwd, timeout):
        bridge_calls.append(cmd)
        job_id = cmd[cmd.index("--job-id") + 1]
        rendered = repo / ".agent_bus-test" / "rendered" / f"{job_id}.md"
        rendered.parent.mkdir(parents=True)
        rendered.write_text(
            "BEGIN_DIALECTIC_ENVELOPE\n"
            '{"candidate": "bounded namespaced result", "bounded": true}\n'
            "END_DIALECTIC_ENVELOPE\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(dialectic, "run_bridge_subprocess", fake_bridge)

    result = dialectic.run_dialectic(repo, bus_dir=".agent_bus-test")

    assert result["status"] == "narrowed"
    assert result["narrowed_proposal"]["candidate"] == "bounded namespaced result"
    assert bridge_calls
    bus_idx = bridge_calls[0].index("--bus-dir")
    assert bridge_calls[0][bus_idx:bus_idx + 3] == ["--bus-dir", ".agent_bus-test", "review"]
    result_path = repo / ".agent_bus-test" / "executors" / "dialectic_result.json"
    assert json.loads(result_path.read_text(encoding="utf-8"))["status"] == "narrowed"
    assert not (repo / ".agent_bus" / "executors" / "dialectic_result.json").exists()


def test_bridge_init_db_seeds_namespaced_config_from_default_bus_before_example(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    default_config = {
        "adapters": {
            "sentinel-default-config": {
                "cmd": ["sentinel-default-config"],
                "timeout_s": 1,
            }
        }
    }
    default_config_path = repo / ".agent_bus" / "bridge_config.json"
    default_config_path.parent.mkdir(parents=True)
    default_config_path.write_text(json.dumps(default_config) + "\n", encoding="utf-8")

    paths = bridge.bridge_paths(repo, bus_dir=".agent_bus-test")
    bridge.init_db(paths)

    active_config_path = repo / ".agent_bus-test" / "bridge_config.json"
    active_config = json.loads(active_config_path.read_text(encoding="utf-8"))
    example_config = json.loads((AGENTS_DIR / "bridge_config.example.json").read_text(encoding="utf-8"))
    assert active_config == default_config
    assert active_config != example_config


def test_commit_executor_hook_env_carries_namespaced_bus_without_skip_bypass(monkeypatch):
    monkeypatch.setenv("RCX_SKIP_RECEIPT_CHECK", "1")
    token = commit_executor._ACTIVE_BUS_DIR.set(Path(".agent_bus-test"))  # ANTICHEAT_OK: context-var bus override is the regression target
    try:
        env = commit_executor._commit_subprocess_env(skip_receipt_check=False)  # ANTICHEAT_OK: hook env helper is the behavior under test
        skip_env = commit_executor._commit_subprocess_env(skip_receipt_check=True)  # ANTICHEAT_OK: hook env helper is the behavior under test
    finally:
        commit_executor._ACTIVE_BUS_DIR.reset(token)  # ANTICHEAT_OK: reset paired context-var bus override

    assert env is not None
    assert env["RCX_AGENT_BUS_DIR"] == ".agent_bus-test"
    assert "RCX_SKIP_RECEIPT_CHECK" not in env
    assert skip_env is not None
    assert skip_env["RCX_AGENT_BUS_DIR"] == ".agent_bus-test"
    assert skip_env["RCX_SKIP_RECEIPT_CHECK"] == "1"


def test_pager_persists_event_delivery_state_and_lock_in_namespaced_bus(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_pager_config(repo)

    result = pager.emit_transition_event(repo, bus_dir=".agent_bus-test", **_event_kwargs())

    assert result["enabled"] is True
    obs = repo / ".agent_bus-test" / "observability"
    assert (obs / "pipeline_agent_events.jsonl").exists()
    assert (obs / "pipeline_agent_delivery_receipts.jsonl").exists()
    assert (obs / "pipeline_agent_pager_state.json").exists()
    assert (obs / "pipeline_agent_pager.lock").exists()
    assert not (repo / ".agent_bus" / "observability").exists()


def test_recovery_agent_invocation_threads_namespaced_bus_to_adapter(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    seen: dict[str, object] = {}
    spec = SimpleNamespace(prompt_via_stdin=False)

    def load_bridge_config(path: Path) -> dict[str, object]:
        seen["bridge_config_path"] = path
        return {"adapters": {}}

    def get_adapter(_config: dict[str, object], backend: str) -> SimpleNamespace:
        seen["backend"] = backend
        return spec

    def prepare_adapter_env(_spec: SimpleNamespace, context: dict[str, str]):
        seen["context"] = dict(context)
        return ["adapter", "{bus_dir}".format(**context)], {"RCX_AGENT_BUS_DIR": context["bus_dir"]}

    fake_adapters = SimpleNamespace(
        load_bridge_config=load_bridge_config,
        get_adapter=get_adapter,
        _prepare_adapter_env=prepare_adapter_env,
    )
    monkeypatch.setattr(
        recovery,
        "load_executor_config",
        lambda _repo_root: {"backends": {"recovery_gate": "codex"}},
    )
    monkeypatch.setattr(
        recovery,
        "_load_bridge_adapters_module",
        lambda _repo_root: fake_adapters,
    )

    token = recovery._ACTIVE_BUS_DIR.set(Path(".agent_bus-test"))  # ANTICHEAT_OK: context-var bus override is the regression target
    try:
        invocation = recovery._resolve_recovery_agent_invocation(  # ANTICHEAT_OK: invocation builder is the behavior under test
            repo,
            wave_id="wave-bus",
            step="phase-b",
            iteration=0,
            prompt="recover",
        )
    finally:
        recovery._ACTIVE_BUS_DIR.reset(token)  # ANTICHEAT_OK: reset paired context-var bus override

    assert seen["bridge_config_path"] == repo / ".agent_bus-test" / "bridge_config.json"
    assert seen["backend"] == "codex"
    assert seen["context"]["bus_dir"] == ".agent_bus-test"
    assert invocation["cmd"] == ["adapter", ".agent_bus-test"]
    assert invocation["env"]["RCX_AGENT_BUS_DIR"] == ".agent_bus-test"
    assert invocation["prompt_input"] is None
    assert not (repo / ".agent_bus" / "bridge_config.json").exists()


def test_pipeline_monitor_status_uses_namespaced_bus(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    default_handoff = repo / ".agent_bus" / "executors" / "phase_b_handoff.json"
    default_handoff.parent.mkdir(parents=True)
    default_handoff.write_text(
        json.dumps({"wave_id": "default-wave", "task_id": "[DEFAULT]"}) + "\n",
        encoding="utf-8",
    )
    namespaced_handoff = repo / ".agent_bus-test" / "executors" / "phase_b_handoff.json"
    namespaced_handoff.parent.mkdir(parents=True)
    namespaced_handoff.write_text(
        json.dumps({"wave_id": "namespaced-wave", "task_id": "[NAMESPACE]"}) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(OBSERVABILITY_DIR / "pipeline_monitor.sh"), "--bus-dir", ".agent_bus-test", "status"],
        cwd=repo,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "namespaced-wave" in result.stdout
    assert "default-wave" not in result.stdout


def test_pipeline_monitor_exec_exports_namespaced_bus_to_child_command(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    live_log = tmp_path / "live.log"

    result = subprocess.run(
        [
            "bash",
            str(OBSERVABILITY_DIR / "pipeline_monitor.sh"),
            "--bus-dir",
            ".agent_bus-test",
            "exec",
            "bash",
            "-c",
            'printf "%s\\n" "$RCX_AGENT_BUS_DIR"',
        ],
        cwd=repo,
        env={**os.environ, "RCX_PIPELINE_LIVE_LOG": str(live_log)},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[-1] == ".agent_bus-test"
    assert live_log.read_text(encoding="utf-8") == ".agent_bus-test\n"


def test_pipeline_monitor_start_passes_namespaced_bus_to_tmux_panes():
    source = (OBSERVABILITY_DIR / "pipeline_monitor.sh").read_text(encoding="utf-8")

    assert "BUS_DIR=$bus_q RCX_AGENT_BUS_DIR=$bus_q RCX_PIPELINE_MONITOR_LANE=$lane_q" in source
    assert "bash $watcher_q" in source
    assert "bash $obs_q/_pane_findings.sh" in source
    assert "bash $obs_q/_pane_processes.sh" in source
    assert "bash $obs_q/_pane_timeline.sh" in source


def test_pipeline_dashboard_web_reports_dashboard_port_collision(monkeypatch, capsys, tmp_path):
    identity = SimpleNamespace(
        lane="alpha",
        bus_dir=".agent_bus-alpha",
        active_bus_root=tmp_path / ".agent_bus-alpha",
        dashboard_port=18123,
        tmux_session="rcx-pipeline-alpha",
        configured=True,
        named=True,
        as_dict=lambda: {
            "lane": "alpha",
            "bus_dir": ".agent_bus-alpha",
            "active_bus_root": str(tmp_path / ".agent_bus-alpha"),
            "dashboard_port": 18123,
            "tmux_session": "rcx-pipeline-alpha",
            "configured": True,
            "named": True,
        },
    )

    monkeypatch.setattr(dashboard_web, "_resolve_dashboard_identity", lambda _args: identity)

    def fail_bind(*_args, **_kwargs):
        raise OSError("address already in use")

    monkeypatch.setattr(dashboard_web.http.server, "HTTPServer", fail_bind)

    assert dashboard_web.main(["--lane", "alpha"]) == 2
    assert "dashboard port collision" in capsys.readouterr().err


def test_commit_bot_remediation_adapter_receives_active_bus_dir(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    config_path = repo / ".agent_bus-test" / "bridge_config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps({"adapters": {}}) + "\n", encoding="utf-8")

    seen: dict[str, object] = {}
    adapter = SimpleNamespace(
        name="codex",
        cmd=["true"],
        timeout_s=1,
        prompt_via_stdin=True,
        env={},
        mode="buffered",
    )

    def load_bridge_config(path: Path) -> dict[str, object]:
        seen["config_path"] = path
        return {"adapters": {}}

    def get_adapter(_config: dict[str, object], backend: str):
        seen["backend"] = backend
        return adapter

    def run_adapter(_spec, **kwargs):
        seen["run_kwargs"] = dict(kwargs)
        return "no changes"

    fake_adapters = SimpleNamespace(
        AdapterSpec=lambda **kwargs: SimpleNamespace(**kwargs),
        BridgeAdapterError=RuntimeError,
        load_bridge_config=load_bridge_config,
        get_adapter=get_adapter,
        run_adapter=run_adapter,
    )
    monkeypatch.setattr(commit_executor, "_bridge_adapters", fake_adapters)
    monkeypatch.setattr(commit_executor, "_run", lambda *_args, **_kwargs: SimpleNamespace(stdout=""))

    token = commit_executor._ACTIVE_BUS_DIR.set(Path(".agent_bus-test"))  # ANTICHEAT_OK: context-var bus override is the regression target
    try:
        result = commit_executor._attempt_bot_finding_remediation(  # ANTICHEAT_OK: remediation path must receive active bus
            [{"severity": "P1", "body": "P1 finding", "path": "mu/tools/executors/commit_executor.py"}],
            repo_root=repo,
            repo_owner="owner",
            repo_name="repo",
            pr_number="1",
            target_branch="branch",
            head_sha="abc123",
            wave_id="wave-bus",
            continuation_path=repo / ".agent_bus-test" / "executors" / "commit_executor_wave-bus.json",
            result={"steps_completed": []},
            log=lambda _message: None,
        )
    finally:
        commit_executor._ACTIVE_BUS_DIR.reset(token)  # ANTICHEAT_OK: reset paired context-var bus override

    assert result is not None
    assert seen["config_path"] == config_path
    assert seen["run_kwargs"]["repo_root"] == repo
    assert seen["run_kwargs"]["bus_dir"] == Path(".agent_bus-test")


def _missing_bus_dir_keywords(path: Path, call_name: str) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    missing: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        else:
            name = None
        if name != call_name:
            continue
        if not any(keyword.arg == "bus_dir" for keyword in node.keywords):
            missing.append(node.lineno)
    return missing


def test_phase_b_implementer_invocations_pass_active_bus_dir():
    missing = _missing_bus_dir_keywords(
        EXECUTORS_DIR / "phase_b_executor.py",
        "invoke_implementer",
    )

    assert missing == []


def test_direct_bridge_adapter_invocations_pass_active_bus_dir():
    missing_by_file = {
        path.name: _missing_bus_dir_keywords(path, "run_adapter")
        for path in (
            AGENTS_DIR / "bridge_supervisor.py",
            AGENTS_DIR / "meta_bridge_supervisor.py",
            EXECUTORS_DIR / "commit_executor.py",
        )
    }

    assert missing_by_file == {
        "bridge_supervisor.py": [],
        "meta_bridge_supervisor.py": [],
        "commit_executor.py": [],
    }


def test_invalid_bus_path_fails_before_runtime_files_are_created(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_pager_config(repo)

    with pytest.raises(executor_common.ExecutorCommonError):
        pager.emit_transition_event(repo, bus_dir="runtime", **_event_kwargs())

    assert not (repo / "runtime").exists()
    assert not (repo / ".agent_bus").exists()


def test_recovery_status_and_log_are_namespaced_but_learned_patterns_stay_default(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    token = recovery._ACTIVE_BUS_DIR.set(Path(".agent_bus-test"))  # ANTICHEAT_OK: context-var bus override is the regression target
    try:
        recovery._save_recovery_status(repo, {"active": True, "wave_id": "wave-bus"})  # ANTICHEAT_OK: persistence substrate is the behavior under test
        recovery._save_recovery_log(repo, [{"wave_id": "wave-bus", "step": "phase_b"}])  # ANTICHEAT_OK: persistence substrate is the behavior under test
        recovery._save_learning_store(repo, recovery._empty_store())  # ANTICHEAT_OK: learned-pattern default-bus exception is under test

        assert recovery._load_recovery_status(repo)["wave_id"] == "wave-bus"  # ANTICHEAT_OK: persisted status observation is the behavior under test
        assert recovery._load_recovery_log(repo)[0]["step"] == "phase_b"  # ANTICHEAT_OK: persisted log observation is the behavior under test
    finally:
        recovery._ACTIVE_BUS_DIR.reset(token)  # ANTICHEAT_OK: reset paired context-var bus override

    assert (repo / ".agent_bus-test" / "recovery" / "recovery_status.json").exists()
    assert (repo / ".agent_bus-test" / "recovery" / "recovery_log.json").exists()
    assert not (repo / ".agent_bus-test" / "recovery" / "learned_patterns.json").exists()
    assert not (repo / ".agent_bus-test" / "recovery" / "learned_patterns.inbox").exists()
    assert (repo / ".agent_bus" / "recovery" / "learned_patterns.json").exists()
