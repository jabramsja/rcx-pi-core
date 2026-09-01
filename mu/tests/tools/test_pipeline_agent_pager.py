from __future__ import annotations

import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from mu.tests.tools.module_loader import load_module

_TOOLS_DIR = Path(__file__).resolve().parent.parent.parent / "tools"
pager_mod = load_module(
    "pipeline_agent_pager",
    _TOOLS_DIR / "observability" / "pipeline_agent_pager.py",
)
_REAL_LOAD_CLAUDE_PAGER_RECEIVER_CLS = pager_mod._load_claude_pager_receiver_cls  # ANTICHEAT_OK: exact-loader regression seam
# The wave-1 receiver MUST load after the pager: its module-level
# ``_load_claude_dispatch_env`` resolves ``from pipeline_agent_pager import ...``
# against the pager already registered in sys.modules above. The Wave-2 claude leg
# (``_dispatch_claude``) enqueues into THIS receiver module, so the tests inspect
# the very same on-disk queue / delivered.jsonl the pager writes and reads.
receiver_mod = load_module(
    "claude_pager_receiver",
    _TOOLS_DIR / "session" / "claude_pager_receiver.py",
)
_REAL_RECEIVER_ENSURE_DRAINING = receiver_mod.ClaudePagerReceiver.ensure_draining

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROVIDER_ENV_KEYS = (
    "PATH",
    "NODE_OPTIONS",
    "RCX_PIPELINE_AGENT_PAGER_CLAUDE_BIN",
    "RCX_CLAUDE_AUTOPING_CLAUDE_BIN",
    "RCX_PIPELINE_AGENT_PAGER_CODEX_BIN",
)
_CLI_BLOCK_MARKER = "RCX_TEST_PROVIDER_ISOLATION_CLI_BLOCKED"
_WEBSOCKET_BLOCK_MARKER = "RCX_TEST_PROVIDER_ISOLATION_WEBSOCKET_BLOCKED"
_PROVIDER_COLLECTION_PID = os.getpid()
_PROVIDER_ENV_AT_COLLECTION = {
    key: (key in os.environ, os.environ.get(key, ""))
    for key in _PROVIDER_ENV_KEYS
}


def _provider_environment_snapshot(environment=os.environ):
    return {
        key: (key in environment, environment.get(key, ""))
        for key in _PROVIDER_ENV_KEYS
    }


def _node_require_paths(node_options: str) -> list[Path]:
    return [
        Path(token.removeprefix("--require="))
        for token in shlex.split(node_options)
        if token.startswith("--require=")
    ]


def _active_provider_paths(environment=os.environ) -> tuple[Path, Path]:
    stub_dir = Path(environment["PATH"].split(os.pathsep)[0])
    require_paths = _node_require_paths(environment["NODE_OPTIONS"])
    assert require_paths, environment["NODE_OPTIONS"]
    return stub_dir, require_paths[-1]


def _root_conftest_plugin(pytestconfig):
    expected = (_REPO_ROOT / "conftest.py").resolve()
    direct = pytestconfig.pluginmanager.get_plugin(str(expected))
    if direct is not None:
        return direct
    for plugin in pytestconfig.pluginmanager.get_plugins():
        plugin_file = getattr(plugin, "__file__", None)
        if plugin_file and Path(plugin_file).resolve() == expected:
            return plugin
    raise AssertionError(f"root conftest plugin not loaded from {expected}")


def _write_executable(path: Path, source: str) -> None:
    path.write_text(source, encoding="utf-8")
    path.chmod(0o700)


def _path_without_active_provider_stub() -> str:
    active_stub_dir, _guard = _active_provider_paths()
    return os.pathsep.join(
        entry
        for entry in os.environ.get("PATH", "").split(os.pathsep)
        if entry and Path(entry) != active_stub_dir
    )


def _provider_probe_plugin_source() -> str:
    return textwrap.dedent(
        """
        import json
        import os
        import shlex
        from pathlib import Path

        import pytest

        KEYS = (
            "PATH",
            "NODE_OPTIONS",
            "RCX_PIPELINE_AGENT_PAGER_CLAUDE_BIN",
            "RCX_CLAUDE_AUTOPING_CLAUDE_BIN",
            "RCX_PIPELINE_AGENT_PAGER_CODEX_BIN",
        )
        OUTPUT_DIR = Path(os.environ["RCX_PROVIDER_PROBE_OUTPUT_DIR"])

        def snapshot():
            return {
                key: [key in os.environ, os.environ.get(key, "")]
                for key in KEYS
            }

        BEFORE = snapshot()
        ACTIVE = None

        def role():
            return os.environ.get("PYTEST_XDIST_WORKER", "controller")

        def active_paths(environment):
            stub_dir = Path(environment["PATH"][1].split(os.pathsep)[0])
            requires = [
                token.removeprefix("--require=")
                for token in shlex.split(environment["NODE_OPTIONS"][1])
                if token.startswith("--require=")
            ]
            return str(stub_dir), requires[-1]

        def pytest_sessionstart(session):
            global ACTIVE
            ACTIVE = snapshot()
            stub_dir, websocket_guard = active_paths(ACTIVE)
            payload = {
                "pid": os.getpid(),
                "role": role(),
                "before": BEFORE,
                "active": ACTIVE,
                "stub_dir": stub_dir,
                "websocket_guard": websocket_guard,
            }
            (OUTPUT_DIR / f"active-{os.getpid()}.json").write_text(
                json.dumps(payload, sort_keys=True),
                encoding="utf-8",
            )

        @pytest.hookimpl(hookwrapper=True)
        def pytest_unconfigure(config):
            yield
            stub_dir, websocket_guard = active_paths(ACTIVE)
            payload = {
                "pid": os.getpid(),
                "role": role(),
                "before": BEFORE,
                "active": ACTIVE,
                "after": snapshot(),
                "stub_dir": stub_dir,
                "websocket_guard": websocket_guard,
            }
            (OUTPUT_DIR / f"final-{os.getpid()}.json").write_text(
                json.dumps(payload, sort_keys=True),
                encoding="utf-8",
            )
        """
    )


def _run_provider_probe_pytest(
    tmp_path: Path,
    *targets: str,
    workers: int | None = None,
) -> tuple[subprocess.CompletedProcess[str], list[dict]]:
    probe_root = tmp_path / "provider-probe"
    output_dir = probe_root / "output"
    output_dir.mkdir(parents=True)
    (probe_root / "rcx_provider_probe.py").write_text(
        _provider_probe_plugin_source(),
        encoding="utf-8",
    )
    pythonpath = os.pathsep.join(
        part
        for part in (
            str(probe_root),
            str(_REPO_ROOT),
            os.environ.get("PYTHONPATH", ""),
        )
        if part
    )
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONPATH": pythonpath,
            "RCX_PROVIDER_PROBE_OUTPUT_DIR": str(output_dir),
        }
    )
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-p",
        "rcx_provider_probe",
    ]
    if workers is not None:
        command.extend(["-n", str(workers)])
    command.extend(targets)
    result = subprocess.run(
        command,
        cwd=_REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(output_dir.glob("final-*.json"))
    ]
    return result, records


def _assert_active_provider_probe(record: dict) -> None:
    pid = record["pid"]
    active = record["active"]
    stub_dir = Path(record["stub_dir"])
    websocket_guard = Path(record["websocket_guard"])
    assert stub_dir.name == "bin"
    assert stub_dir.parent.name.startswith(
        f"rcx-pytest-provider-isolation-{pid}-"
    )
    assert active["PATH"][1].split(os.pathsep)[0] == str(stub_dir)
    assert active["RCX_PIPELINE_AGENT_PAGER_CLAUDE_BIN"][1] == "claude"
    assert active["RCX_CLAUDE_AUTOPING_CLAUDE_BIN"][1] == "claude"
    assert active["RCX_PIPELINE_AGENT_PAGER_CODEX_BIN"][1] == "codex"
    assert websocket_guard.parent == stub_dir.parent
    assert stub_dir.is_dir()
    assert (stub_dir / "claude").is_file()
    assert (stub_dir / "codex").is_file()
    assert websocket_guard.is_file()


@pytest.fixture(autouse=True)
def _isolate_live_codex_thread_id(monkeypatch):
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE", raising=False)


@pytest.fixture(autouse=True)
def _stub_receiver_drain_spawn(monkeypatch):
    """Neutralize the receiver's detached drain-spawn in pager tests (Wave 2b).

    Wave 2b's ``_dispatch_claude`` calls ``receiver.ensure_draining()`` right after it
    enqueues, to GUARANTEE the drain (PR #1137 P1). The real ``ensure_draining`` spawns a
    detached ``claude_pager_receiver --once`` drainer, which would run a real ``claude -p``.
    The pager tests assert the ENQUEUE + quick-ack + receipt-bridge contract, not the
    spawn; the real spawn contract (bounded ``--once``, detached, fail-closed) is locked in
    ``test_claude_pager_receiver.py`` with a mocked ``Popen``. Stub the method to a harmless
    no-op so no subprocess (and no model call) is ever launched here. Tests that exercise
    the drain-ensure WIRING inject their own fake receiver via ``_claude_pager_receiver``
    (whose own ``ensure_draining`` is independent of this class-level stub).
    """
    monkeypatch.setattr(
        receiver_mod.ClaudePagerReceiver,
        "ensure_draining",
        lambda self: {"started": True, "pid": 0, "mode": "stubbed"},
    )
    monkeypatch.setattr(
        pager_mod,
        "_load_claude_pager_receiver_cls",
        lambda: receiver_mod.ClaudePagerReceiver,
    )


def test_provider_isolation_root_configures_process_local_stubs_before_collection(
    pytestconfig,
):
    assert _PROVIDER_COLLECTION_PID == os.getpid()
    assert _PROVIDER_ENV_AT_COLLECTION == _provider_environment_snapshot()

    _root_conftest_plugin(pytestconfig)
    stub_dir, websocket_guard = _active_provider_paths()
    guard_dir = stub_dir.parent

    assert websocket_guard.parent == guard_dir
    assert guard_dir.name.startswith(
        f"rcx-pytest-provider-isolation-{os.getpid()}-"
    )
    assert os.environ["PATH"].split(os.pathsep)[0] == str(stub_dir)
    assert os.environ["RCX_PIPELINE_AGENT_PAGER_CLAUDE_BIN"] == "claude"
    assert os.environ["RCX_CLAUDE_AUTOPING_CLAUDE_BIN"] == "claude"
    assert os.environ["RCX_PIPELINE_AGENT_PAGER_CODEX_BIN"] == "codex"
    assert guard_dir.stat().st_mode & 0o777 == 0o700
    assert stub_dir.stat().st_mode & 0o777 == 0o700
    assert (stub_dir / "claude").stat().st_mode & 0o777 == 0o700
    assert (stub_dir / "codex").stat().st_mode & 0o777 == 0o700
    assert websocket_guard.stat().st_mode & 0o777 == 0o600
    assert _CLI_BLOCK_MARKER in (stub_dir / "claude").read_text(
        encoding="utf-8"
    )
    assert _WEBSOCKET_BLOCK_MARKER in websocket_guard.read_text(encoding="utf-8")


def test_provider_isolation_stubs_fail_closed_without_live_model():
    stub_dir, _websocket_guard = _active_provider_paths()
    assert shutil.which("claude") == str(stub_dir / "claude")
    assert shutil.which("codex") == str(stub_dir / "codex")

    commands = {
        "basename-claude": ["claude", "--version"],
        "basename-codex": ["codex", "--version"],
        "pager-claude-bin": [
            os.environ["RCX_PIPELINE_AGENT_PAGER_CLAUDE_BIN"],
            "--version",
        ],
        "autoping-claude-bin": [
            os.environ["RCX_CLAUDE_AUTOPING_CLAUDE_BIN"],
            "--version",
        ],
        "pager-codex-bin": [
            os.environ["RCX_PIPELINE_AGENT_PAGER_CODEX_BIN"],
            "--version",
        ],
    }
    for label, command in commands.items():
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
        assert result.returncode == 86, (label, result)
        assert result.stdout == "", (label, result.stdout)
        assert result.stderr.strip() == (
            f"{_CLI_BLOCK_MARKER}:{Path(command[0]).name}"
        )


def test_provider_isolation_codex_app_server_transport_fails_before_connect():
    if shutil.which("node") is None:
        pytest.skip("node is required to exercise the Codex websocket guard")
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(0.25)
        port = listener.getsockname()[1]
        with pytest.raises(
            pager_mod.PipelineAgentPagerError,
            match=_WEBSOCKET_BLOCK_MARKER,
        ):
            pager_mod._codex_app_server_exchange(  # ANTICHEAT_OK: real transport boundary proof
                f"ws://127.0.0.1:{port}",
                [
                    {
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "clientInfo": {
                                "name": "provider-isolation-test",
                                "version": "1.0",
                            }
                        },
                    }
                ],
                1.0,
            )
        with pytest.raises(socket.timeout):
            listener.accept()
    finally:
        listener.close()


def test_provider_isolation_late_detached_descendant_blocks_cli_and_codex_transport_after_teardown(
    tmp_path,
):
    if shutil.which("node") is None:
        pytest.skip("node is required to exercise the Codex websocket guard")
    if os.name != "posix":
        pytest.skip("detached provider lifecycle proof requires POSIX sessions")

    fake_dir = tmp_path / "safe-fake-providers"
    fake_dir.mkdir()
    fake_hit = tmp_path / "safe-provider-hit"
    for basename in ("claude", "codex"):
        _write_executable(
            fake_dir / basename,
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$0\" >> {shlex.quote(str(fake_hit))}\n"
            "exit 0\n",
        )

    clean_path = _path_without_active_provider_stub()
    assert shutil.which("node", path=clean_path) is not None

    project = tmp_path / "nested-provider-project"
    project.mkdir()
    ready_path = tmp_path / "late-descendant-ready.json"
    release_path = tmp_path / "late-descendant-release"
    result_path = tmp_path / "late-descendant-result.json"
    descendant_path = tmp_path / "late_descendant.py"
    nested_test_path = project / "test_spawn_late_descendant.py"
    coordinator_path = tmp_path / "nested_pytest_coordinator.py"

    descendant_path.write_text(
        textwrap.dedent(
            """
            import json
            import os
            import shlex
            import subprocess
            import time
            from pathlib import Path

            from mu.tests.tools.module_loader import load_module

            ready_path = Path(os.environ["RCX_LATE_READY_PATH"])
            release_path = Path(os.environ["RCX_LATE_RELEASE_PATH"])
            result_path = Path(os.environ["RCX_LATE_RESULT_PATH"])
            repo_root = Path(os.environ["RCX_LATE_REPO_ROOT"])
            require_paths = [
                token.removeprefix("--require=")
                for token in shlex.split(os.environ["NODE_OPTIONS"])
                if token.startswith("--require=")
            ]
            ready_path.write_text(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "stub_dir": str(
                            Path(os.environ["PATH"].split(os.pathsep)[0])
                        ),
                        "websocket_guard": require_paths[-1],
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            deadline = time.monotonic() + 15
            while not release_path.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            if not release_path.exists():
                raise SystemExit("release was not observed")

            commands = {
                "basename-claude": ["claude", "--version"],
                "basename-codex": ["codex", "--version"],
                "explicit-claude": [
                    os.environ["RCX_PIPELINE_AGENT_PAGER_CLAUDE_BIN"],
                    "--version",
                ],
                "explicit-codex": [
                    os.environ["RCX_PIPELINE_AGENT_PAGER_CODEX_BIN"],
                    "--version",
                ],
            }
            command_results = {}
            for label, command in commands.items():
                try:
                    completed = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=3,
                    )
                    command_results[label] = {
                        "returncode": completed.returncode,
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                    }
                except OSError as exc:
                    command_results[label] = {"os_error": str(exc)}

            pager = load_module(
                "late_descendant_pipeline_agent_pager",
                repo_root / "mu" / "tools" / "observability" / "pipeline_agent_pager.py",
            )
            try:
                pager._codex_app_server_exchange(
                    os.environ["RCX_LATE_WEBSOCKET_URL"],
                    [{"id": 1, "method": "initialize", "params": {}}],
                    1.0,
                )
            except Exception as exc:
                websocket_error = str(exc)
            else:
                websocket_error = "NO_ERROR"

            result_path.write_text(
                json.dumps(
                    {
                        "commands": command_results,
                        "websocket_error": websocket_error,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            """
        ),
        encoding="utf-8",
    )
    nested_test_path.write_text(
        textwrap.dedent(
            """
            import os
            import subprocess
            import sys
            import time
            from pathlib import Path

            def test_spawn_late_detached_descendant():
                ready_path = Path(os.environ["RCX_LATE_READY_PATH"])
                proc = subprocess.Popen(
                    [sys.executable, os.environ["RCX_LATE_DESCENDANT_PATH"]],
                    env=os.environ.copy(),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                deadline = time.monotonic() + 10
                while not ready_path.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                assert ready_path.exists(), f"descendant {proc.pid} did not become ready"
            """
        ),
        encoding="utf-8",
    )
    coordinator_path.write_text(
        textwrap.dedent(
            """
            import json
            import os
            import time
            from pathlib import Path

            import pytest

            KEYS = (
                "PATH",
                "NODE_OPTIONS",
                "RCX_PIPELINE_AGENT_PAGER_CLAUDE_BIN",
                "RCX_CLAUDE_AUTOPING_CLAUDE_BIN",
                "RCX_PIPELINE_AGENT_PAGER_CODEX_BIN",
            )

            def snapshot():
                return {
                    key: [key in os.environ, os.environ.get(key, "")]
                    for key in KEYS
                }

            before = snapshot()
            project = Path(os.environ["RCX_LATE_PROJECT"])
            exit_code = pytest.main(
                [
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "-p",
                    "conftest",
                    "--rootdir",
                    str(project),
                    "--confcutdir",
                    str(project),
                    str(Path(os.environ["RCX_LATE_NESTED_TEST"])),
                ]
            )
            after = snapshot()
            Path(os.environ["RCX_LATE_RELEASE_PATH"]).touch()
            result_path = Path(os.environ["RCX_LATE_RESULT_PATH"])
            deadline = time.monotonic() + 15
            while not result_path.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            payload = {
                "pid": os.getpid(),
                "pytest_exit": int(exit_code),
                "before": before,
                "after": after,
                "descendant_result_exists": result_path.exists(),
            }
            print("RCX_LATE_COORDINATOR=" + json.dumps(payload, sort_keys=True))
            raise SystemExit(
                0 if int(exit_code) == 0 and result_path.exists() else 3
            )
            """
        ),
        encoding="utf-8",
    )

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(0.25)
        environment = os.environ.copy()
        environment.update(
            {
                "PATH": f"{fake_dir}{os.pathsep}{clean_path}",
                "NODE_OPTIONS": "",
                "RCX_PIPELINE_AGENT_PAGER_CLAUDE_BIN": str(
                    fake_dir / "claude"
                ),
                "RCX_CLAUDE_AUTOPING_CLAUDE_BIN": str(fake_dir / "claude"),
                "RCX_PIPELINE_AGENT_PAGER_CODEX_BIN": str(fake_dir / "codex"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": "0",
                "PYTHONPATH": os.pathsep.join(
                    part
                    for part in (
                        str(_REPO_ROOT),
                        os.environ.get("PYTHONPATH", ""),
                    )
                    if part
                ),
                "RCX_LATE_PROJECT": str(project),
                "RCX_LATE_NESTED_TEST": str(nested_test_path),
                "RCX_LATE_DESCENDANT_PATH": str(descendant_path),
                "RCX_LATE_READY_PATH": str(ready_path),
                "RCX_LATE_RELEASE_PATH": str(release_path),
                "RCX_LATE_RESULT_PATH": str(result_path),
                "RCX_LATE_REPO_ROOT": str(_REPO_ROOT),
                "RCX_LATE_WEBSOCKET_URL": (
                    f"ws://127.0.0.1:{listener.getsockname()[1]}"
                ),
            }
        )
        coordinator = subprocess.run(
            [sys.executable, str(coordinator_path)],
            cwd=_REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=25,
        )
        assert coordinator.returncode == 0, (
            coordinator.stdout,
            coordinator.stderr,
        )
        payload_line = next(
            line
            for line in coordinator.stdout.splitlines()
            if line.startswith("RCX_LATE_COORDINATOR=")
        )
        coordinator_payload = json.loads(payload_line.split("=", 1)[1])
        assert coordinator_payload["pytest_exit"] == 0
        assert coordinator_payload["before"] == coordinator_payload["after"]
        assert coordinator_payload["descendant_result_exists"] is True

        ready = json.loads(ready_path.read_text(encoding="utf-8"))
        descendant = json.loads(result_path.read_text(encoding="utf-8"))
        retained_stub_dir = Path(ready["stub_dir"])
        retained_websocket_guard = Path(ready["websocket_guard"])
        assert retained_stub_dir.parent.name.startswith(
            f"rcx-pytest-provider-isolation-{coordinator_payload['pid']}-"
        )
        assert (retained_stub_dir / "claude").is_file()
        assert (retained_stub_dir / "codex").is_file()
        assert retained_websocket_guard.is_file()
        assert retained_websocket_guard.parent == retained_stub_dir.parent
        for label, result in descendant["commands"].items():
            assert result["returncode"] == 86, (label, result)
            assert _CLI_BLOCK_MARKER in result["stderr"], (label, result)
        assert _WEBSOCKET_BLOCK_MARKER in descendant["websocket_error"]
        assert not fake_hit.exists()
        with pytest.raises(socket.timeout):
            listener.accept()
    finally:
        listener.close()


def test_provider_isolation_detached_receiver_inherits_stub(
    tmp_path,
    monkeypatch,
):
    if os.name != "posix":
        pytest.skip("detached receiver proof requires POSIX sessions")
    stub_dir, _websocket_guard = _active_provider_paths()
    fake_dir = tmp_path / "safe-receiver-provider"
    fake_dir.mkdir()
    fake_hit = tmp_path / "safe-receiver-provider-hit"
    _write_executable(
        fake_dir / "claude",
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$0\" >> {shlex.quote(str(fake_hit))}\n"
        "exit 0\n",
    )
    monkeypatch.setenv(
        "PATH",
        os.pathsep.join((str(stub_dir), str(fake_dir), _path_without_active_provider_stub())),
    )
    monkeypatch.setenv("RCX_PIPELINE_AGENT_PAGER_CLAUDE_BIN", "claude")

    repo = tmp_path / "receiver-repo"
    repo.mkdir()
    bus_dir = ".agent_bus-provider-isolation"
    receiver = receiver_mod.ClaudePagerReceiver(
        repo,
        bus_dir=bus_dir,
        timeout_s=2.0,
    )
    event_id = "provider-isolation-detached-receiver"
    receiver.enqueue(
        {
            "event_id": event_id,
            "event_type": "commit_ready",
            "wave_id": "provider-isolation",
            "summary": "safe fake page",
        }
    )
    spawn = _REAL_RECEIVER_ENSURE_DRAINING(receiver)
    assert spawn["started"] is True

    base = repo / bus_dir / "observability" / "claude_pager_receiver"
    deadline = time.monotonic() + 10
    evidence = ""
    while time.monotonic() < deadline:
        evidence_parts = []
        for path in base.rglob("*"):
            try:
                if path.is_file():
                    evidence_parts.append(
                        path.read_text(encoding="utf-8", errors="replace")
                    )
            except OSError:
                continue
        evidence = "\n".join(evidence_parts)
        if _CLI_BLOCK_MARKER in evidence and not (
            base / "active_drainer.json"
        ).exists():
            break
        time.sleep(0.02)
    assert _CLI_BLOCK_MARKER in evidence
    assert not fake_hit.exists()
    assert receiver.queued_event_ids() == [event_id]


def test_provider_isolation_rcx_pi_only_child_loads_root_boundary(tmp_path):
    result, records = _run_provider_probe_pytest(
        tmp_path,
        "rcx_pi/specs/test_vars_demo_contract.py",
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert len(records) == 1
    record = records[0]
    assert record["role"] == "controller"
    _assert_active_provider_probe(record)
    assert record["before"] == record["after"]


def test_provider_isolation_ordinary_xdist_is_topology_independent(tmp_path):
    result, records = _run_provider_probe_pytest(
        tmp_path,
        "rcx_pi/specs/test_vars_demo_contract.py",
        "rcx_pi/specs/test_triad_plus_contract.py",
        workers=2,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert {record["role"] for record in records} == {
        "controller",
        "gw0",
        "gw1",
    }
    assert len(records) == 3
    for record in records:
        _assert_active_provider_probe(record)
        assert record["before"] != record["active"]
    assert len({record["stub_dir"] for record in records}) == 3
    assert len({record["websocket_guard"] for record in records}) == 3


def test_provider_isolation_two_worker_lifecycle_and_exact_restoration(tmp_path):
    result, records = _run_provider_probe_pytest(
        tmp_path,
        "rcx_pi/specs/test_vars_demo_contract.py",
        "rcx_pi/specs/test_triad_plus_contract.py",
        workers=2,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert len(records) == 3
    controller = next(
        record for record in records if record["role"] == "controller"
    )
    workers = [record for record in records if record["role"] != "controller"]
    assert {record["role"] for record in workers} == {"gw0", "gw1"}
    for record in records:
        _assert_active_provider_probe(record)
        assert record["before"] == record["after"]
    for worker in workers:
        assert worker["before"] == controller["active"]


def test_provider_isolation_helpers_restore_exact_environment(
    tmp_path,
    pytestconfig,
):
    root_conftest = _root_conftest_plugin(pytestconfig)
    environment = {
        "PATH": "",
        "NODE_OPTIONS": "",
        "RCX_PIPELINE_AGENT_PAGER_CLAUDE_BIN": "",
        "RCX_PIPELINE_AGENT_PAGER_CODEX_BIN": "/safe/original/codex",
        "UNRELATED": "preserved",
    }
    before = dict(environment)
    state = root_conftest._install_provider_isolation(  # ANTICHEAT_OK: lifecycle helper contract
        environment,
        temporary_parent=tmp_path,
    )
    assert state.environment_before == {
        "PATH": (True, ""),
        "NODE_OPTIONS": (True, ""),
        "RCX_PIPELINE_AGENT_PAGER_CLAUDE_BIN": (True, ""),
        "RCX_CLAUDE_AUTOPING_CLAUDE_BIN": (False, ""),
        "RCX_PIPELINE_AGENT_PAGER_CODEX_BIN": (
            True,
            "/safe/original/codex",
        ),
    }
    assert environment["UNRELATED"] == "preserved"
    assert environment != before

    root_conftest._restore_provider_isolation(state)  # ANTICHEAT_OK: lifecycle helper contract
    assert environment == before
    assert state.restored is True
    assert state.guard_dir.is_dir()
    assert (state.stub_dir / "claude").is_file()
    assert (state.stub_dir / "codex").is_file()
    assert state.websocket_guard.is_file()

    root_conftest._restore_provider_isolation(state)  # ANTICHEAT_OK: idempotent restore contract
    assert environment == before


def test_provider_isolation_helpers_preserve_projection_coverage(
    tmp_path,
    pytestconfig,
):
    root_conftest = _root_conftest_plugin(pytestconfig)
    environment = {
        "PATH": "/safe/bin",
        "PYTHONHASHSEED": "0",
        "RCX_PROJECTION_COVERAGE": "1",
        "UNRELATED_TEST_STATE": "keep",
    }
    state = root_conftest._install_provider_isolation(  # ANTICHEAT_OK: lifecycle helper contract
        environment,
        temporary_parent=tmp_path,
    )
    assert environment["PYTHONHASHSEED"] == "0"
    assert environment["RCX_PROJECTION_COVERAGE"] == "1"
    assert environment["UNRELATED_TEST_STATE"] == "keep"

    root_conftest._restore_provider_isolation(state)  # ANTICHEAT_OK: lifecycle helper contract
    assert environment == {
        "PATH": "/safe/bin",
        "PYTHONHASHSEED": "0",
        "RCX_PROJECTION_COVERAGE": "1",
        "UNRELATED_TEST_STATE": "keep",
    }


def _write_receiver_authority_fixture(tmp_path: Path, source: str) -> tuple[Path, Path]:
    tools_dir = tmp_path / "mu" / "tools"
    observability_dir = tools_dir / "observability"
    session_dir = tools_dir / "session"
    observability_dir.mkdir(parents=True)
    session_dir.mkdir()
    receiver_path = session_dir / "claude_pager_receiver.py"
    receiver_path.write_text(source, encoding="utf-8")
    return observability_dir, receiver_path


@pytest.mark.parametrize(
    "shadow_root_name",
    ["executors", "observability", "agents", "checks", "retained-site"],
)
def test_receiver_loader_uses_exact_session_file_before_import_shadows(
    tmp_path,
    monkeypatch,
    shadow_root_name,
):
    import sys

    observability_dir, receiver_path = _write_receiver_authority_fixture(
        tmp_path,
        "class ClaudePagerReceiver:\n"
        "    AUTHORITY_SENTINEL = 'CANONICAL_SESSION_BYTES'\n",
    )
    tools_dir = observability_dir.parent
    shadow_dir = (
        tmp_path / "retained-site"
        if shadow_root_name == "retained-site"
        else tools_dir / shadow_root_name
    )
    shadow_dir.mkdir(parents=True, exist_ok=True)
    (shadow_dir / "claude_pager_receiver.py").write_text(
        "class ClaudePagerReceiver:\n"
        f"    AUTHORITY_SENTINEL = 'SHADOW_{shadow_root_name.upper()}'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(pager_mod, "SCRIPT_DIR", observability_dir)
    monkeypatch.setattr(pager_mod.sys, "path", [str(shadow_dir), *sys.path])
    monkeypatch.delitem(sys.modules, "claude_pager_receiver", raising=False)

    receiver_cls = _REAL_LOAD_CLAUDE_PAGER_RECEIVER_CLS()

    assert receiver_cls.AUTHORITY_SENTINEL == "CANONICAL_SESSION_BYTES"
    loaded = sys.modules["claude_pager_receiver"]
    assert Path(loaded.__file__).resolve() == receiver_path.resolve()


def test_receiver_loader_replaces_wrong_cached_module_with_exact_session_file(
    tmp_path,
    monkeypatch,
):
    import sys
    import types

    observability_dir, receiver_path = _write_receiver_authority_fixture(
        tmp_path,
        "class ClaudePagerReceiver:\n"
        "    AUTHORITY_SENTINEL = 'CANONICAL_SESSION_BYTES'\n",
    )
    poison = types.ModuleType("claude_pager_receiver")
    poison.__file__ = str(tmp_path / "wrong-root" / "claude_pager_receiver.py")
    poison.ClaudePagerReceiver = type(
        "ClaudePagerReceiver",
        (),
        {"AUTHORITY_SENTINEL": "WRONG_CACHED_BYTES"},
    )
    monkeypatch.setattr(pager_mod, "SCRIPT_DIR", observability_dir)
    monkeypatch.setitem(sys.modules, "claude_pager_receiver", poison)

    receiver_cls = _REAL_LOAD_CLAUDE_PAGER_RECEIVER_CLS()

    assert receiver_cls.AUTHORITY_SENTINEL == "CANONICAL_SESSION_BYTES"
    loaded = sys.modules["claude_pager_receiver"]
    assert loaded is not poison
    assert Path(loaded.__file__).resolve() == receiver_path.resolve()


def test_receiver_loader_loads_repo_receiver_with_circular_pager_link(
    monkeypatch,
):
    import sys

    if sys.platform == "win32":
        pytest.skip("claude_pager_receiver uses the POSIX fcntl queue lock")
    canonical_receiver = _TOOLS_DIR / "session" / "claude_pager_receiver.py"
    monkeypatch.setattr(pager_mod, "SCRIPT_DIR", _TOOLS_DIR / "observability")
    monkeypatch.delitem(sys.modules, "claude_pager_receiver", raising=False)

    receiver_cls = _REAL_LOAD_CLAUDE_PAGER_RECEIVER_CLS()

    loaded = sys.modules["claude_pager_receiver"]
    assert receiver_cls is loaded.ClaudePagerReceiver
    assert Path(loaded.__file__).resolve() == canonical_receiver.resolve()
    assert sys.modules["pipeline_agent_pager"] is pager_mod


def test_receiver_loader_cleans_partial_module_before_retry(
    tmp_path,
    monkeypatch,
):
    import importlib
    import sys
    import types

    observability_dir, receiver_path = _write_receiver_authority_fixture(
        tmp_path,
        "PARTIAL_SENTINEL = 'PARTIAL_BYTES'\n"
        "raise RuntimeError('RECEIVER_LOAD_BOOM')\n",
    )
    poison = types.ModuleType("claude_pager_receiver")
    poison.__file__ = str(tmp_path / "wrong-root" / "claude_pager_receiver.py")
    monkeypatch.setattr(pager_mod, "SCRIPT_DIR", observability_dir)
    monkeypatch.setitem(sys.modules, "claude_pager_receiver", poison)

    with pytest.raises(RuntimeError, match="RECEIVER_LOAD_BOOM"):
        _REAL_LOAD_CLAUDE_PAGER_RECEIVER_CLS()

    assert "claude_pager_receiver" not in sys.modules
    receiver_path.write_text(
        "class ClaudePagerReceiver:\n"
        "    AUTHORITY_SENTINEL = 'FRESH_CANONICAL_BYTES_AFTER_RETRY'\n",
        encoding="utf-8",
    )
    importlib.invalidate_caches()

    receiver_cls = _REAL_LOAD_CLAUDE_PAGER_RECEIVER_CLS()

    assert receiver_cls.AUTHORITY_SENTINEL == "FRESH_CANONICAL_BYTES_AFTER_RETRY"
    assert not hasattr(sys.modules["claude_pager_receiver"], "PARTIAL_SENTINEL")


def test_receiver_loader_retry_ignores_same_size_same_mtime_stale_bytecode(
    tmp_path,
    monkeypatch,
):
    import importlib
    import os
    import sys

    failing_source = (
        "if True :\n"
        "    raise RuntimeError('OLD_BYTECODE')\n"
        "class ClaudePagerReceiver:\n"
        "    AUTHORITY_SENTINEL = 'OLD_BYTECODE'\n"
    )
    repaired_source = (
        "if False:\n"
        "    raise RuntimeError('NEW_BYTECODE')\n"
        "class ClaudePagerReceiver:\n"
        "    AUTHORITY_SENTINEL = 'NEW_BYTECODE'\n"
    )
    assert len(failing_source.encode("utf-8")) == len(
        repaired_source.encode("utf-8")
    )
    observability_dir, receiver_path = _write_receiver_authority_fixture(
        tmp_path,
        failing_source,
    )
    monkeypatch.setattr(pager_mod, "SCRIPT_DIR", observability_dir)
    monkeypatch.delitem(sys.modules, "claude_pager_receiver", raising=False)
    original_stat = receiver_path.stat()
    stale_seed_spec = importlib.util.spec_from_file_location(
        "stale_receiver_seed",
        str(receiver_path),
    )
    assert stale_seed_spec is not None and stale_seed_spec.loader is not None
    stale_module = importlib.util.module_from_spec(stale_seed_spec)
    sys.modules["stale_receiver_seed"] = stale_module
    try:
        monkeypatch.setattr(sys, "dont_write_bytecode", False)
        with pytest.raises(RuntimeError, match="OLD_BYTECODE"):
            stale_seed_spec.loader.exec_module(stale_module)
    finally:
        sys.modules.pop("stale_receiver_seed", None)
    stale_pyc = Path(importlib.util.cache_from_source(str(receiver_path)))
    assert stale_pyc.is_file()
    pyc_header = stale_pyc.read_bytes()[:16]
    assert int.from_bytes(pyc_header[4:8], "little") == 0
    assert int.from_bytes(pyc_header[8:12], "little") == int(
        original_stat.st_mtime
    )
    assert int.from_bytes(pyc_header[12:16], "little") == original_stat.st_size

    receiver_path.write_text(repaired_source, encoding="utf-8")
    os.utime(
        receiver_path,
        ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
    )
    repaired_stat = receiver_path.stat()
    assert repaired_stat.st_size == original_stat.st_size
    assert repaired_stat.st_mtime_ns == original_stat.st_mtime_ns

    replay_spec = importlib.util.spec_from_file_location(
        "stale_receiver_replay",
        str(receiver_path),
    )
    assert replay_spec is not None and replay_spec.loader is not None
    replay_module = importlib.util.module_from_spec(replay_spec)
    sys.modules["stale_receiver_replay"] = replay_module
    try:
        with pytest.raises(RuntimeError, match="OLD_BYTECODE"):
            replay_spec.loader.exec_module(replay_module)
    finally:
        sys.modules.pop("stale_receiver_replay", None)

    receiver_cls = _REAL_LOAD_CLAUDE_PAGER_RECEIVER_CLS()

    assert receiver_cls.AUTHORITY_SENTINEL == "NEW_BYTECODE"
    assert (
        sys.modules["claude_pager_receiver"].ClaudePagerReceiver
        is receiver_cls
    )


def test_receiver_loader_executes_opened_bytes_when_source_path_is_swapped(
    tmp_path,
    monkeypatch,
):
    import builtins
    import sys

    authorized_source = (
        "class ClaudePagerReceiver:\n"
        "    AUTHORITY_SENTINEL = 'OPENED_AUTHORIZED_BYTES'\n"
    )
    swapped_source = (
        "class ClaudePagerReceiver:\n"
        "    AUTHORITY_SENTINEL = 'LATE_PATH_SWAP_BYTES'\n"
    )
    observability_dir, receiver_path = _write_receiver_authority_fixture(
        tmp_path,
        authorized_source,
    )
    monkeypatch.setattr(pager_mod, "SCRIPT_DIR", observability_dir)
    monkeypatch.delitem(sys.modules, "claude_pager_receiver", raising=False)
    real_compile = builtins.compile
    swapped = False

    def _swap_path_then_compile(
        source,
        filename,
        mode,
        flags=0,
        dont_inherit=False,
        optimize=-1,
        **kwargs,
    ):
        nonlocal swapped
        if not swapped and Path(filename).resolve() == receiver_path.resolve():
            swapped = True
            receiver_path.write_text(swapped_source, encoding="utf-8")
        return real_compile(
            source,
            filename,
            mode,
            flags=flags,
            dont_inherit=dont_inherit,
            optimize=optimize,
            **kwargs,
        )

    monkeypatch.setattr(builtins, "compile", _swap_path_then_compile)

    receiver_cls = _REAL_LOAD_CLAUDE_PAGER_RECEIVER_CLS()

    assert swapped is True
    assert receiver_cls.AUTHORITY_SENTINEL == "OPENED_AUTHORIZED_BYTES"
    assert "LATE_PATH_SWAP_BYTES" in receiver_path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "invalid_shape",
    ["missing", "file-symlink", "directory", "session-symlink", "unreadable"],
)
def test_receiver_loader_rejects_invalid_canonical_path_shape(
    tmp_path,
    monkeypatch,
    request,
    invalid_shape,
):
    tools_dir = tmp_path / "mu" / "tools"
    observability_dir = tools_dir / "observability"
    observability_dir.mkdir(parents=True)
    session_dir = tools_dir / "session"
    receiver_path = session_dir / "claude_pager_receiver.py"
    if invalid_shape == "session-symlink":
        outside_session = tmp_path / "outside-session"
        outside_session.mkdir()
        (outside_session / receiver_path.name).write_text(
            "class ClaudePagerReceiver:\n"
            "    pass\n",
            encoding="utf-8",
        )
        try:
            session_dir.symlink_to(outside_session, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"directory symlinks unavailable: {exc}")
    else:
        session_dir.mkdir()
        if invalid_shape == "file-symlink":
            outside_receiver = tmp_path / "outside-receiver.py"
            outside_receiver.write_text(
                "class ClaudePagerReceiver:\n"
                "    pass\n",
                encoding="utf-8",
            )
            try:
                receiver_path.symlink_to(outside_receiver)
            except OSError as exc:
                pytest.skip(f"file symlinks unavailable: {exc}")
        elif invalid_shape == "directory":
            receiver_path.mkdir()
        elif invalid_shape == "unreadable":
            import os
            import sys

            if sys.platform == "win32":
                pytest.skip("POSIX unreadable-file permissions required")
            receiver_path.write_text(
                "class ClaudePagerReceiver:\n"
                "    pass\n",
                encoding="utf-8",
            )
            receiver_path.chmod(0)

            def _restore_receiver_permissions() -> None:
                if receiver_path.exists() and not receiver_path.is_symlink():
                    receiver_path.chmod(0o600)

            request.addfinalizer(_restore_receiver_permissions)
            if os.access(receiver_path, os.R_OK):
                pytest.skip("unreadable receiver cannot be represented")
    monkeypatch.setattr(pager_mod, "SCRIPT_DIR", observability_dir)

    with pytest.raises(pager_mod.PipelineAgentPagerError):
        _REAL_LOAD_CLAUDE_PAGER_RECEIVER_CLS()


@pytest.mark.parametrize(
    "receiver_source",
    [
        "AUTHORITY_SENTINEL = 'NO_RECEIVER_CLASS'\n",
        "ClaudePagerReceiver = None\n",
    ],
)
def test_receiver_loader_rejects_missing_or_noncallable_receiver_class(
    tmp_path,
    monkeypatch,
    receiver_source,
):
    import sys

    observability_dir, _receiver_path = _write_receiver_authority_fixture(
        tmp_path,
        receiver_source,
    )
    monkeypatch.setattr(pager_mod, "SCRIPT_DIR", observability_dir)
    monkeypatch.delitem(sys.modules, "claude_pager_receiver", raising=False)

    with pytest.raises(pager_mod.PipelineAgentPagerError, match="no callable"):
        _REAL_LOAD_CLAUDE_PAGER_RECEIVER_CLS()

    assert "claude_pager_receiver" not in sys.modules


class _RecordingReceiver:
    """Fake ``ClaudePagerReceiver`` capturing ``enqueue`` / ``ensure_draining`` call order.

    Used by the Wave-2b drain-ensure wiring tests to prove ``_dispatch_claude`` enqueues
    AND THEN ensures the drain (so a queued event is never left undrained), and to drive
    the fail-open-when-drain-unavailable path deterministically without a real subprocess.
    """

    def __init__(self, *, enqueue_status="queued", ensure_raises=None):
        self.calls: list[str] = []
        self._enqueue_status = enqueue_status
        self._ensure_raises = ensure_raises

    def enqueue(self, event):
        self.calls.append("enqueue")
        return {
            "status": self._enqueue_status,
            "event_id": str(event.get("event_id") or ""),
            "queue_path": "queued.json",
        }

    def ensure_draining(self):
        self.calls.append("ensure_draining")
        if self._ensure_raises is not None:
            raise self._ensure_raises
        return {"started": True, "pid": 4321, "mode": "detached_once"}


def _write_config(
    repo_root: Path,
    *,
    enabled: bool = True,
    route: str = "notify-only",
    timeouts: dict[str, int] | None = None,
) -> None:
    config_path = repo_root / "mu" / "tools" / "executors" / "executor_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pipeline_agent_pager": {
            "enabled": enabled,
            "route": route,
        },
    }
    if timeouts:
        payload["timeouts"] = timeouts
    config_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _event_kwargs(**overrides):
    base = {
        "event_type": "commit_ready",
        "wave_id": "wave-pager",
        "task_id": "[PIPELINE-AGENT-PAGER]",
        "plan_path": "reports/control_plane/pager.md",
        "phase": "phase_b",
        "state": "commit_ready",
        "transition_key": "receipt-1",
        "summary": "commit ready",
        "reason": "receipt validated",
        "artifact_paths": {"receipt": ".agent_bus/meta/pre_commit_receipts/r.json"},
    }
    base.update(overrides)
    return base


def _load_state(repo_root: Path) -> dict:
    return json.loads((repo_root / pager_mod.STATE_PATH).read_text(encoding="utf-8"))


def _load_log(repo_root: Path) -> list[dict]:
    path = repo_root / pager_mod.EVENT_LOG_PATH
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_delivery_log(repo_root: Path) -> list[dict]:
    path = repo_root / pager_mod.DELIVERY_LOG_PATH
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_skip_log(repo_root: Path) -> list[dict]:
    path = repo_root / pager_mod.SKIP_LOG_PATH
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _receiver(repo_root: Path):
    """The wave-1 receiver bound to the default bus -- same paths the pager uses."""
    return receiver_mod.ClaudePagerReceiver(repo_root, bus_dir=".agent_bus")


def _plant_receiver_receipt(repo_root: Path, event_id: str, *, transition_key: str = "", exit_code: int = 0, ack=None):
    """Append a receiver exit-0 delivery receipt exactly as the wave-1 receiver does.

    Stands in for an async receiver delivery: schema
    ``{event_id, transition_key, ack, recorded_at}`` written to the receiver's
    ``delivered.jsonl`` (no ``target`` field). The pager's reconcile receipt-bridge
    consumes this AS-IS to promote claude.
    """
    receiver = _receiver(repo_root)
    if ack is None:
        ack = {
            "acknowledged_at": "2026-06-20T00:00:00+00:00",
            "exit_code": exit_code,
            "target": "claude",
            "mode": "direct",
            "pid": 4321,
            "log_path": str(repo_root / "claude_page.log"),
        }
    receiver.receipts_path.parent.mkdir(parents=True, exist_ok=True)
    with receiver.receipts_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "event_id": event_id,
            "transition_key": transition_key,
            "ack": ack,
            "recorded_at": "2026-06-20T00:00:00+00:00",
        }, sort_keys=True, separators=(",", ":")) + "\n")


def _ack_codex(repo_root, event, state, *, timeout_s):
    """Fake codex dispatch that acknowledges immediately.

    Used by route=both tests to isolate the REAL claude leg
    (``_dispatch_claude``) while keeping codex delivered through the normal
    delivered/receipt flow. Mirrors ``_dispatch_codex``'s success return so the
    codex delivered/pending/retry semantics and receipts stay exercised.
    """
    return {
        "acknowledged": True,
        "ack": {
            "acknowledged_at": "2026-06-01T00:00:00+00:00",
            "thread_id": "thread-codex-1",
            "turn_id": "turn-codex-1",
            "target": "codex",
        },
        "codex_thread_id": "thread-codex-1",
    }


def _write_autoping_state(
    codex_home: Path,
    repo_root: Path,
    thread_id: str,
    *,
    updated_at: str,
    status: str = "waiting_for_prior_ping",
) -> None:
    state_dir = codex_home / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    safe_thread = "".join(ch if ch.isalnum() or ch in "_.-" else "_" for ch in thread_id)
    (state_dir / f"rcx_autoping_{safe_thread}.json").write_text(
        json.dumps(
            {
                "thread_id": thread_id,
                "status": status,
                "updated_at": updated_at,
                "bridge_state": {"wave_root": str(repo_root.resolve())},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _codex_initialize_response(request_id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": {"serverInfo": {"name": "codex"}}}


def _codex_thread_response(request_id: int, thread_id: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": {"thread": {"id": thread_id}}}


def _codex_turn_response(request_id: int, *, thread_id: str, turn_id: str | None = None) -> dict:
    payload = {"thread": {"id": thread_id}}
    if turn_id is not None:
        payload["turn"] = {"id": turn_id}
    return {"jsonrpc": "2.0", "id": request_id, "result": payload}


def _codex_error_response(request_id: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"message": message}}


def test_codex_node_bridge_preserves_explicit_empty_params():
    if shutil.which("node") is None:
        pytest.skip("node is required to exercise the Codex websocket bridge")
    requests = [
        {
            "id": 1,
            "method": "initialize",
            "params": {"clientInfo": {"name": "test", "version": "1.0"}},
        },
        {"id": 2, "method": "thread/start", "params": {}},
        {
            "id": 3,
            "method": "turn/start",
            "params": {
                "threadId": {"$from": "2.result.thread.id"},
                "input": [{"type": "text", "text": "pager wake"}],
            },
        },
    ]
    websocket_stub = r"""
class StubWebSocket {
  constructor() {
    this.listeners = {};
    setImmediate(() => this.listeners.open && this.listeners.open());
  }
  addEventListener(name, callback) {
    this.listeners[name] = callback;
  }
  send(raw) {
    const sent = JSON.parse(raw);
    const result = { echo: sent };
    if (sent.method === "thread/start") {
      result.thread = { id: "thread-1" };
    }
    if (sent.method === "turn/start") {
      result.thread = { id: sent.params.threadId };
      result.turn = { id: "turn-1" };
    }
    setImmediate(() => {
      this.listeners.message({
        data: JSON.stringify({ jsonrpc: "2.0", id: sent.id, result }),
      });
    });
  }
  close() {}
}
global.WebSocket = StubWebSocket;
"""

    proc = subprocess.run(
        [
            "node",
            "-e",
            websocket_stub + pager_mod.CODEX_APP_SERVER_NODE_SCRIPT,
            "ws://127.0.0.1:1",
            json.dumps(requests),
            "1000",
        ],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    thread_start = payload["responses"][1]["result"]["echo"]
    assert thread_start["method"] == "thread/start"
    assert thread_start["params"] == {}


def test_event_id_uses_canonical_identity_tuple_and_log_appends_once(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="notify-only")

    first = pager_mod.emit_transition_event(repo, **_event_kwargs(summary="first"))
    second = pager_mod.emit_transition_event(repo, **_event_kwargs(summary="second", reason="different summary"))

    assert first["event_id"] == second["event_id"]
    log_entries = _load_log(repo)
    assert len(log_entries) == 1
    assert log_entries[0]["event_id"] == first["event_id"]
    state = _load_state(repo)
    entry = state["events"][first["event_id"]]
    assert entry["delivered_targets"][pager_mod.NOTIFY_ONLY_TARGET]["mode"] == pager_mod.NOTIFY_ONLY_TARGET
    assert entry["pending_targets"] == []


def test_lifecycle_event_types_are_accepted_persisted_deduped_and_routed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="notify-only")

    lifecycle_event_types = [
        "phase_a_entered",
        "phase_a_reviewer_started",
        "phase_a_reviewer_completed",
        "phase_a_implementer_started",
        "phase_a_implementer_completed",
        "phase_a_go",
        "phase_a_no_go",
        "phase_a_question",
        "phase_b_implementer_started",
        "phase_b_implementer_completed",
        "phase_b_reviewer_started",
        "phase_b_bridge_completed",
        "phase_b_final_pytest_started",
        "phase_b_final_pytest_passed",
        "phase_b_final_verdict",
        "pre_commit_supervisor_started",
        "pre_commit_supervisor_completed",
        "commit_started",
        "commit_ready",
        "commit_succeeded",
        "commit_failed",
        "commit_held",
        "recovery_started",
        "recovery_state_changed",
        "recovery_escalated",
        "recovery_returned",
        "recovery_succeeded",
        "recovery_failed",
        "pipeline_hard_fail",
        "executor_hard_fail",
    ]

    first_ids = []
    for event_type in lifecycle_event_types:
        first = pager_mod.emit_transition_event(
            repo,
            **_event_kwargs(
                event_type=event_type,
                phase=event_type.split("_", 1)[0],
                state=event_type,
                transition_key=f"{event_type}:transition",
                summary=f"{event_type} summary",
            ),
        )
        second = pager_mod.emit_transition_event(
            repo,
            **_event_kwargs(
                event_type=event_type,
                phase=event_type.split("_", 1)[0],
                state=event_type,
                transition_key=f"{event_type}:transition",
                summary=f"{event_type} duplicate",
            ),
        )
        assert second["event_id"] == first["event_id"]
        first_ids.append(first["event_id"])

    assert len(set(first_ids)) == len(lifecycle_event_types)
    log_entries = _load_log(repo)
    assert len(log_entries) == len(lifecycle_event_types)
    state = _load_state(repo)
    assert set(state["events"]) == set(first_ids)
    for event_id in first_ids:
        entry = state["events"][event_id]
        assert entry["requested_targets"] == [pager_mod.NOTIFY_ONLY_TARGET]
        assert entry["pending_targets"] == []
        assert pager_mod.NOTIFY_ONLY_TARGET in entry["delivered_targets"]


def test_unsupported_lifecycle_event_type_fails_closed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="notify-only")

    with pytest.raises(pager_mod.PipelineAgentPagerError, match="unsupported pager event_type"):
        pager_mod.emit_transition_event(
            repo,
            **_event_kwargs(event_type="phase_a_secret_unreviewed_transition"),
        )

    assert _load_log(repo) == []
    assert not (repo / pager_mod.STATE_PATH).exists()


def test_disabled_pager_skips_route_validation(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, enabled=False, route="notify-only")

    result = pager_mod.emit_transition_event(repo, route="definitely-invalid", **_event_kwargs())

    assert result == {
        "enabled": False,
        "route": "definitely-invalid",
        "event_id": None,
        "attempted": [],
        "budget_exhausted": False,
    }
    assert not (repo / pager_mod.EVENT_LOG_PATH).exists()
    assert not (repo / pager_mod.STATE_PATH).exists()


def test_pager_route_env_override_precedes_executor_config(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="notify-only")
    monkeypatch.setenv("RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE", "codex")
    calls: list[str] = []

    def ack_target(repo_root, target, event, state, config, *, timeout_s):
        calls.append(target)
        return {
            "acknowledged": True,
            "ack": {
                "acknowledged_at": "2026-06-01T00:00:00+00:00",
                "target": target,
            },
        }

    monkeypatch.setattr(pager_mod, "_dispatch_target", ack_target)

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())

    assert result["route"] == "codex"
    assert calls == ["codex"]
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert entry["requested_targets"] == ["codex"]
    assert set(entry["delivered_targets"]) == {"codex"}


def test_bus_local_orchestrator_mode_precedes_executor_config_route(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="both")
    state_path = repo / pager_mod.ORCHESTRATOR_MODE_PATH
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"mode": "codex"}) + "\n", encoding="utf-8")
    calls: list[str] = []

    def ack_target(repo_root, target, event, state, config, *, timeout_s):
        calls.append(target)
        return {
            "acknowledged": True,
            "ack": {
                "acknowledged_at": "2026-06-01T00:00:00+00:00",
                "target": target,
            },
        }

    monkeypatch.setattr(pager_mod, "_dispatch_target", ack_target)

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())

    assert result["route"] == "codex"
    assert calls == ["codex"]
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert entry["requested_targets"] == ["codex"]
    assert set(entry["delivered_targets"]) == {"codex"}


def test_explicit_pager_route_precedes_env_override(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="notify-only")
    monkeypatch.setenv("RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE", "codex")

    result = pager_mod.emit_transition_event(
        repo,
        route="notify-only",
        **_event_kwargs(),
    )

    assert result["route"] == "notify-only"
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert entry["requested_targets"] == [pager_mod.NOTIFY_ONLY_TARGET]
    assert pager_mod.NOTIFY_ONLY_TARGET in entry["delivered_targets"]


def test_explicit_codex_route_narrows_committed_both_route(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="both")
    monkeypatch.delenv("RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE", raising=False)
    calls: list[str] = []

    def ack_target(repo_root, target, event, state, config, *, timeout_s):
        calls.append(target)
        return {
            "acknowledged": True,
            "ack": {
                "acknowledged_at": "2026-06-30T00:00:00+00:00",
                "target": target,
            },
        }

    monkeypatch.setattr(pager_mod, "_dispatch_target", ack_target)

    result = pager_mod.emit_transition_event(
        repo,
        route="codex",
        **_event_kwargs(),
    )

    assert result["route"] == "codex"
    assert calls == ["codex"]
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert entry["requested_targets"] == ["codex"]


def test_explicit_codex_route_replaces_prior_same_identity_both_route(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="both")
    monkeypatch.delenv("RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE", raising=False)
    deliveries: list[tuple[str, str]] = []

    def ack_target(repo_root, target, event, state, config, *, timeout_s):
        deliveries.append((event["route"], target))
        return {
            "acknowledged": True,
            "ack": {
                "acknowledged_at": "2026-07-01T00:00:00+00:00",
                "target": target,
            },
        }

    monkeypatch.setattr(pager_mod, "_dispatch_target", ack_target)

    first = pager_mod.emit_transition_event(repo, **_event_kwargs())
    second = pager_mod.emit_transition_event(repo, route="codex", **_event_kwargs())

    assert first["route"] == "both"
    assert second["route"] == "codex"
    assert second["event_id"] == first["event_id"]
    assert deliveries == [("both", "codex"), ("both", "claude")]
    log_entries = _load_log(repo)
    assert len(log_entries) == 2
    assert [entry["route"] for entry in log_entries] == ["both", "codex"]
    state = _load_state(repo)
    entry = state["events"][first["event_id"]]
    assert entry["route"] == "codex"
    assert entry["requested_targets"] == ["codex"]
    assert set(entry["delivered_targets"]) == {"codex"}
    assert entry["pending_targets"] == []


def test_invalid_pager_route_env_override_fails_closed(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="notify-only")
    monkeypatch.setenv("RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE", "not-a-route")

    with pytest.raises(pager_mod.PipelineAgentPagerError, match="unsupported pager route"):
        pager_mod.emit_transition_event(repo, **_event_kwargs())

    assert _load_log(repo) == []
    assert not (repo / pager_mod.STATE_PATH).exists()


def test_truncated_event_log_tail_is_quarantined_and_does_not_brick_dispatch(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="notify-only")

    log_path = repo / pager_mod.EVENT_LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text('{"event_id":"truncated"', encoding="utf-8")

    replay = pager_mod.dispatch_pending_events(repo)

    assert replay["enabled"] is True
    assert replay["attempted"] == []
    assert _load_log(repo) == []
    quarantined = sorted(
        (repo / pager_mod.OBSERVABILITY_DIR).glob("pipeline_agent_events.jsonl.corrupt.*")
    )
    assert len(quarantined) == 1
    assert '{"event_id":"truncated"' in quarantined[0].read_text(encoding="utf-8")


def test_both_route_persists_partial_success_and_retries_only_pending_target(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="both")
    calls: list[str] = []
    attempts = {"claude": 0}

    def fake_dispatch(repo_root, target, event, state, config, *, timeout_s):
        calls.append(target)
        if target == "codex":
            return {
                "acknowledged": True,
                "ack": {"acknowledged_at": "2026-04-17T00:00:00+00:00", "thread_id": "thread-1", "turn_id": "turn-1"},
                "codex_thread_id": "thread-1",
            }
        attempts["claude"] += 1
        if attempts["claude"] == 1:
            return {"acknowledged": False, "error": "claude exited 1"}
        return {
            "acknowledged": True,
            "ack": {"acknowledged_at": "2026-04-17T00:00:01+00:00", "exit_code": 0},
        }

    monkeypatch.setattr(pager_mod, "_dispatch_target", fake_dispatch)

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())
    assert result["enabled"] is True
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert set(entry["delivered_targets"]) == {"codex"}
    assert entry["pending_targets"] == ["claude"]

    replay = pager_mod.dispatch_pending_events(repo)
    assert replay["enabled"] is True
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert set(entry["delivered_targets"]) == {"codex", "claude"}
    assert entry["pending_targets"] == []
    assert calls == ["codex", "claude", "claude"]


def test_re_emitting_same_event_under_new_route_replaces_requested_targets(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="notify-only")

    first = pager_mod.emit_transition_event(repo, **_event_kwargs())
    state = _load_state(repo)
    entry = state["events"][first["event_id"]]
    assert entry["requested_targets"] == [pager_mod.NOTIFY_ONLY_TARGET]
    assert entry["pending_targets"] == []

    _write_config(repo, route="codex")
    dispatch_calls: list[str] = []

    def pending_codex(repo_root, target, event, state, config, *, timeout_s):
        dispatch_calls.append(target)
        return {"acknowledged": False, "error": "codex unavailable"}

    monkeypatch.setattr(pager_mod, "_dispatch_target", pending_codex)

    second = pager_mod.emit_transition_event(repo, **_event_kwargs(summary="reroute to codex"))
    assert second["event_id"] == first["event_id"]
    assert dispatch_calls == ["codex"]
    log_entries = _load_log(repo)
    assert len(log_entries) == 2
    assert [entry["route"] for entry in log_entries] == [pager_mod.NOTIFY_ONLY_TARGET, "codex"]
    state = _load_state(repo)
    entry = state["events"][first["event_id"]]
    assert entry["route"] == "codex"
    assert entry["requested_targets"] == ["codex"]
    assert entry["pending_targets"] == ["codex"]


def test_route_replay_rebuilds_replaced_targets_from_append_only_log(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="notify-only")

    first = pager_mod.emit_transition_event(repo, **_event_kwargs())
    _write_config(repo, route="codex")

    monkeypatch.setattr(
        pager_mod,
        "_dispatch_target",
        lambda *args, **kwargs: {"acknowledged": False, "error": "codex unavailable"},
    )
    second = pager_mod.emit_transition_event(repo, **_event_kwargs(summary="reroute to codex"))
    assert second["event_id"] == first["event_id"]
    assert len(_load_log(repo)) == 2

    (repo / pager_mod.STATE_PATH).unlink()

    dispatch_calls: list[str] = []

    def ack_codex(repo_root, target, event, state, config, *, timeout_s):
        dispatch_calls.append(target)
        return {
            "acknowledged": True,
            "ack": {
                "acknowledged_at": "2026-04-17T00:00:00+00:00",
                "thread_id": "thread-1",
                "turn_id": "turn-1",
                "target": "codex",
            },
            "codex_thread_id": "thread-1",
        }

    monkeypatch.setattr(pager_mod, "_dispatch_target", ack_codex)

    replay = pager_mod.dispatch_pending_events(repo)

    assert replay["enabled"] is True
    assert dispatch_calls == ["codex"]
    state = _load_state(repo)
    entry = state["events"][first["event_id"]]
    assert entry["route"] == "codex"
    assert entry["requested_targets"] == ["codex"]
    assert set(entry["delivered_targets"]) == {"codex"}
    assert entry["pending_targets"] == []
    assert len(_load_delivery_log(repo)) == 2


def test_trigger_budget_exhaustion_leaves_pending_target_durable_for_replay(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(
        repo,
        route="both",
        timeouts={
            "pipeline_agent_pager_trigger": 1,
            "pipeline_agent_pager_codex_ack": 5,
            "pipeline_agent_pager_claude_ack": 5,
        },
    )
    calls: list[str] = []

    def slow_first_target(repo_root, target, event, state, config, *, timeout_s):
        calls.append(target)
        if target == "codex":
            time.sleep(1.1)
            return {
                "acknowledged": True,
                "ack": {"acknowledged_at": "2026-04-17T00:00:00+00:00", "thread_id": "thread-1", "turn_id": "turn-1"},
                "codex_thread_id": "thread-1",
            }
        return {
            "acknowledged": True,
            "ack": {"acknowledged_at": "2026-04-17T00:00:01+00:00", "exit_code": 0},
        }

    monkeypatch.setattr(pager_mod, "_dispatch_target", slow_first_target)

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())
    assert result["budget_exhausted"] is True
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert set(entry["delivered_targets"]) == {"codex"}
    assert entry["pending_targets"] == ["claude"]

    monkeypatch.setattr(
        pager_mod,
        "_dispatch_target",
        lambda repo_root, target, event, state, config, *, timeout_s: {
            "acknowledged": True,
            "ack": {"acknowledged_at": "2026-04-17T00:00:02+00:00", "exit_code": 0},
        },
    )
    pager_mod.dispatch_pending_events(repo)
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert set(entry["delivered_targets"]) == {"codex", "claude"}
    assert entry["pending_targets"] == []
    assert calls == ["codex"]


def test_dispatcher_state_persists_last_dispatch_provenance(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="notify-only")

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())

    state = _load_state(repo)
    last_dispatch = state["dispatcher"]["last_dispatch"]
    assert last_dispatch["event_id"] == result["event_id"]
    assert last_dispatch["event_type"] == "commit_ready"
    assert last_dispatch["phase"] == "phase_b"
    assert last_dispatch["state"] == "commit_ready"
    assert last_dispatch["target"] == pager_mod.NOTIFY_ONLY_TARGET
    assert last_dispatch["acknowledged"] is True
    assert last_dispatch["attempted_at"]
    assert last_dispatch["completed_at"]
    assert last_dispatch["summary"] == "commit ready"


def test_overlapping_emit_calls_do_not_duplicate_delivery(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="codex")
    dispatch_calls = 0
    first_started = threading.Event()

    def fake_dispatch(repo_root, target, event, state, config, *, timeout_s):
        nonlocal dispatch_calls
        dispatch_calls += 1
        first_started.set()
        time.sleep(0.2)
        return {
            "acknowledged": True,
            "ack": {"acknowledged_at": "2026-04-17T00:00:00+00:00", "thread_id": "thread-1", "turn_id": "turn-1"},
            "codex_thread_id": "thread-1",
        }

    monkeypatch.setattr(pager_mod, "_dispatch_target", fake_dispatch)
    results = []

    def worker():
        results.append(pager_mod.emit_transition_event(repo, **_event_kwargs()))

    thread_a = threading.Thread(target=worker)
    thread_b = threading.Thread(target=worker)
    thread_a.start()
    assert first_started.wait(timeout=2)
    thread_b.start()
    thread_a.join()
    thread_b.join()

    assert len(results) == 2
    assert dispatch_calls == 1
    assert len(_load_log(repo)) == 1


def test_invalid_codex_listener_port_stays_pending_and_reportable(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="codex")
    monkeypatch.setenv("RCX_CODEX_APP_SERVER_URL", "ws://127.0.0.1:not-a-port")

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())

    assert result["enabled"] is True
    assert result["attempted"] == [
        {
            "event_id": result["event_id"],
            "target": "codex",
            "acknowledged": False,
            "error": "RCX_CODEX_APP_SERVER_URL must include a valid websocket port",
            "receipt_log_warning": "",
        }
    ]
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert entry["delivered_targets"] == {}
    assert entry["pending_targets"] == ["codex"]
    assert entry["attempts"]["codex"]["count"] == 1
    assert entry["attempts"]["codex"]["last_error"] == (
        "RCX_CODEX_APP_SERVER_URL must include a valid websocket port"
    )
    assert state["codex_thread_id"] is None
    assert _load_delivery_log(repo) == []


def test_missing_codex_listener_port_stays_pending_without_exchange(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="codex")
    monkeypatch.setenv("RCX_CODEX_APP_SERVER_URL", "ws://127.0.0.1")

    def unexpected_exchange(url, requests, timeout_s):
        raise AssertionError(f"unexpected exchange attempt for {url}")

    monkeypatch.setattr(
        pager_mod,
        "_codex_app_server_exchange",
        unexpected_exchange,
    )

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())

    assert result["enabled"] is True
    assert result["attempted"] == [
        {
            "event_id": result["event_id"],
            "target": "codex",
            "acknowledged": False,
            "error": "RCX_CODEX_APP_SERVER_URL must include a valid websocket port",
            "receipt_log_warning": "",
        }
    ]
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert entry["delivered_targets"] == {}
    assert entry["pending_targets"] == ["codex"]
    assert entry["attempts"]["codex"]["count"] == 1
    assert entry["attempts"]["codex"]["last_error"] == (
        "RCX_CODEX_APP_SERVER_URL must include a valid websocket port"
    )
    assert state["codex_thread_id"] is None
    assert _load_delivery_log(repo) == []


def test_non_loopback_codex_listener_stays_pending_and_reportable(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="codex")
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager state setup
    state["codex_thread_id"] = "thread-existing"
    pager_mod._save_state(repo, state)  # ANTICHEAT_OK: direct pager state setup
    monkeypatch.setenv("RCX_CODEX_APP_SERVER_URL", "ws://192.168.1.50:8765")

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())

    assert result["attempted"] == [
        {
            "event_id": result["event_id"],
            "target": "codex",
            "acknowledged": False,
            "error": "RCX_CODEX_APP_SERVER_URL must target a loopback websocket listener",
            "receipt_log_warning": "",
        }
    ]
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert entry["delivered_targets"] == {}
    assert entry["pending_targets"] == ["codex"]
    assert entry["attempts"]["codex"]["last_error"] == (
        "RCX_CODEX_APP_SERVER_URL must target a loopback websocket listener"
    )
    assert state["codex_thread_id"] == "thread-existing"
    assert _load_delivery_log(repo) == []


def test_unavailable_codex_listener_fallback_failure_stays_pending_and_reportable(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="codex")
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager state setup
    state["codex_thread_id"] = "thread-existing"
    pager_mod._save_state(repo, state)  # ANTICHEAT_OK: direct pager state setup

    def unavailable_exchange(url, requests, timeout_s):
        raise pager_mod.PipelineAgentPagerError(
            f"{url} unavailable: websocket connection failed"
        )

    monkeypatch.setattr(
        pager_mod,
        "_codex_app_server_exchange",
        unavailable_exchange,
    )
    monkeypatch.setattr(
        pager_mod,
        "_dispatch_codex_exec_resume",
        lambda repo_root, event_record, *, thread_id, timeout_s: {
            "acknowledged": False,
            "error": "codex exec resume exited 1: fallback unavailable",
            "codex_thread_id": thread_id,
        },
    )

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())
    expected_error = (
        "ws://127.0.0.1:8765 unavailable: websocket connection failed; "
        "codex exec resume exited 1: fallback unavailable"
    )

    assert result["attempted"] == [
        {
            "event_id": result["event_id"],
            "target": "codex",
            "acknowledged": False,
            "error": expected_error,
            "receipt_log_warning": "",
        }
    ]
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert entry["delivered_targets"] == {}
    assert entry["pending_targets"] == ["codex"]
    assert entry["attempts"]["codex"]["count"] == 1
    assert entry["attempts"]["codex"]["last_error"] == expected_error
    assert state["codex_thread_id"] == "thread-existing"
    assert _load_delivery_log(repo) == []


def test_codex_ack_requires_accepted_turn_response_fields(tmp_path):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    request_batches: list[list[dict]] = []

    def missing_turn_exchange(url, requests, timeout_s):
        request_batches.append(requests)
        return [
            _codex_initialize_response(1),
            _codex_thread_response(2, "thread-1"),
            _codex_turn_response(3, thread_id="thread-1"),
        ]

    with patch.object(pager_mod, "_codex_app_server_exchange", side_effect=missing_turn_exchange):
        failed = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK
    assert failed["acknowledged"] is False
    assert "missing" in failed["error"]
    assert [request["method"] for request in request_batches[0]] == [
        "initialize",
        "thread/start",
        "turn/start",
    ]
    assert request_batches[0][0]["params"]["clientInfo"] == {
        "name": "pipeline_agent_pager",
        "version": "1.0",
    }
    expected_prompt = getattr(pager_mod, "_event_prompt")(event)
    assert request_batches[0][2]["params"] == {
        "threadId": {"$from": "2.result.thread.id"},
        "input": [{"type": "text", "text": expected_prompt}],
    }

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        return_value=[
            _codex_initialize_response(1),
            _codex_thread_response(2, "thread-1"),
            _codex_turn_response(3, thread_id="thread-1", turn_id="turn-1"),
        ],
    ):
        succeeded = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK
    assert succeeded["acknowledged"] is True
    assert succeeded["codex_thread_id"] == "thread-1"
    assert succeeded["ack"]["turn_id"] == "turn-1"

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        return_value=[
            _codex_initialize_response(1),
            _codex_thread_response(2, "thread-1"),
            {"jsonrpc": "2.0", "id": 3, "result": {"turn": {"id": "turn-1"}}},
        ],
    ):
        turn_only = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK
    assert turn_only["acknowledged"] is True
    assert turn_only["codex_thread_id"] == "thread-1"
    assert turn_only["ack"]["thread_id"] == "thread-1"
    assert turn_only["ack"]["turn_id"] == "turn-1"


def test_codex_ack_rejects_mismatched_thread_id(tmp_path):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        return_value=[
            _codex_initialize_response(1),
            _codex_thread_response(2, "thread-expected"),
            _codex_turn_response(3, thread_id="thread-other", turn_id="turn-1"),
        ],
    ):
        failed = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert failed["acknowledged"] is False
    assert "did not match requested thread" in failed["error"]
    assert failed["codex_thread_id"] == "thread-expected"


def test_codex_app_server_dispatch_prefers_live_thread_over_stored_thread(tmp_path, monkeypatch):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    state["codex_thread_id"] = "thread-stale"
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-live")
    monkeypatch.setenv("RCX_CODEX_HOME", str(tmp_path / "codex-home"))
    request_batches: list[list[dict]] = []

    def fake_exchange(url, requests, timeout_s):
        request_batches.append(requests)
        return [
            _codex_initialize_response(1),
            _codex_turn_response(2, thread_id="thread-live", turn_id="turn-1"),
        ]

    with patch.object(pager_mod, "_codex_app_server_exchange", side_effect=fake_exchange):
        result = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert result["acknowledged"] is True
    assert result["codex_thread_id"] == "thread-live"
    assert [request["method"] for request in request_batches[0]] == [
        "initialize",
        "turn/start",
    ]
    assert request_batches[0][1]["params"]["threadId"] == "thread-live"


def test_codex_app_server_failure_falls_back_to_exec_resume_for_live_thread(tmp_path, monkeypatch):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    seen: dict[str, object] = {}
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-live")

    def fake_exec_resume(repo_root, event_record, *, thread_id, timeout_s):
        seen["repo_root"] = repo_root
        seen["event_id"] = event_record["event_id"]
        seen["thread_id"] = thread_id
        seen["timeout_s"] = timeout_s
        return {
            "acknowledged": True,
            "ack": {
                "acknowledged_at": "2026-04-17T00:00:00+00:00",
                "thread_id": thread_id,
                "target": "codex",
                "mode": "exec_resume",
                "pid": 12345,
            },
            "codex_thread_id": thread_id,
        }

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        side_effect=pager_mod.PipelineAgentPagerError("ws://127.0.0.1:8765 unavailable: HTTPError"),
    ), patch.object(
        pager_mod,
        "_dispatch_codex_exec_resume",
        side_effect=fake_exec_resume,
    ):
        fallback = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert fallback["acknowledged"] is True
    assert fallback["ack"]["mode"] == "exec_resume"
    assert fallback["codex_thread_id"] == "thread-live"
    assert seen["thread_id"] == "thread-live"
    assert seen["event_id"] == event["event_id"]


def test_codex_node_websocket_unavailable_falls_back_to_exec_resume_for_live_thread(
    tmp_path, monkeypatch
):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    seen: dict[str, object] = {}
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-live")

    def fake_node_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=1,
            stdout='{"error":"node WebSocket unavailable"}',
            stderr="",
        )

    def fake_exec_resume(repo_root, event_record, *, thread_id, timeout_s):
        seen["thread_id"] = thread_id
        seen["timeout_s"] = timeout_s
        return {
            "acknowledged": True,
            "ack": {
                "acknowledged_at": "2026-04-17T00:00:00+00:00",
                "thread_id": thread_id,
                "target": "codex",
                "mode": "exec_resume",
                "pid": 12345,
            },
            "codex_thread_id": thread_id,
        }

    monkeypatch.setattr(pager_mod.subprocess, "run", fake_node_run)
    monkeypatch.setattr(pager_mod, "_dispatch_codex_exec_resume", fake_exec_resume)

    fallback = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert fallback["acknowledged"] is True
    assert fallback["ack"]["mode"] == "exec_resume"
    assert fallback["codex_thread_id"] == "thread-live"
    assert seen["thread_id"] == "thread-live"
    assert seen["timeout_s"] > 0


def test_codex_app_server_fallback_returns_failure_when_timeout_is_exhausted(
    tmp_path,
    monkeypatch,
):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-live")

    def fake_exchange(url, requests, timeout_s):
        time.sleep(0.01)
        raise pager_mod.PipelineAgentPagerError(
            "ws://127.0.0.1:8765 unavailable: HTTPError"
        )

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        side_effect=fake_exchange,
    ), patch.object(
        pager_mod,
        "_dispatch_codex_exec_resume",
        side_effect=AssertionError("exhausted timeout must not launch fallback"),
    ):
        result = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=0.001)  # ANTICHEAT_OK

    assert result["acknowledged"] is False
    assert result["codex_thread_id"] == "thread-live"
    assert "unavailable" in result["error"]
    assert "timed out before acknowledgement" in result["error"]


def test_event_prompt_forbids_headless_pipeline_relaunch():
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager prompt contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )

    prompt = pager_mod._event_prompt(event)  # ANTICHEAT_OK: direct pager prompt contract test

    assert "Do not run shell commands" in prompt
    assert "Do not edit files" in prompt
    assert "Do not launch or relaunch executor_dispatch.py" in prompt
    assert "foreground restart to the operator-visible pipeline surface" in prompt

def test_codex_thread_start_requires_explicit_thread_id_field(tmp_path):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        return_value=[
            _codex_initialize_response(1),
            {"jsonrpc": "2.0", "id": 2, "result": {"id": "not-a-thread-id"}},
            _codex_turn_response(3, thread_id="thread-ignored", turn_id="turn-1"),
        ],
    ):
        failed = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert failed["acknowledged"] is False
    assert failed["error"] == "codex thread create missing thread_id"
    assert failed["codex_thread_id"] is None


def test_codex_stale_thread_reseeds_on_explicit_error(tmp_path):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    state["codex_thread_id"] = "thread-stale"
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    request_batches: list[list[dict]] = []

    def fake_exchange(url, requests, timeout_s):
        request_batches.append(requests)
        if len(request_batches) == 1:
            return [
                _codex_initialize_response(1),
                _codex_error_response(2, "thread not found: thread-stale"),
            ]
        return [
            _codex_initialize_response(1),
            _codex_thread_response(2, "thread-fresh"),
            _codex_turn_response(3, thread_id="thread-fresh", turn_id="turn-1"),
        ]

    with patch.object(pager_mod, "_codex_app_server_exchange", side_effect=fake_exchange):
        succeeded = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert succeeded["acknowledged"] is True
    assert succeeded["codex_thread_id"] == "thread-fresh"
    assert succeeded["ack"]["thread_id"] == "thread-fresh"
    assert succeeded["ack"]["turn_id"] == "turn-1"
    assert [request["method"] for request in request_batches[0]] == [
        "initialize",
        "turn/start",
    ]
    expected_prompt = getattr(pager_mod, "_event_prompt")(event)
    assert request_batches[0][1]["params"] == {
        "threadId": "thread-stale",
        "input": [{"type": "text", "text": expected_prompt}],
    }
    assert [request["method"] for request in request_batches[1]] == [
        "initialize",
        "thread/start",
        "turn/start",
    ]


def test_codex_exec_resume_fallback_prefers_live_thread_over_stored_thread(tmp_path, monkeypatch):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    state["codex_thread_id"] = "thread-stale"
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    seen: dict[str, object] = {}
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-live")

    def fake_exec_resume(repo_root, event_record, *, thread_id, timeout_s):
        seen["repo_root"] = repo_root
        seen["event_id"] = event_record["event_id"]
        seen["thread_id"] = thread_id
        seen["timeout_s"] = timeout_s
        return {
            "acknowledged": True,
            "ack": {
                "acknowledged_at": "2026-04-17T00:00:00+00:00",
                "thread_id": thread_id,
                "target": "codex",
                "mode": "exec_resume",
                "pid": 12345,
            },
            "codex_thread_id": thread_id,
        }

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        side_effect=pager_mod.PipelineAgentPagerError("ws://127.0.0.1:8765 unavailable: HTTPError"),
    ), patch.object(
        pager_mod,
        "_dispatch_codex_exec_resume",
        side_effect=fake_exec_resume,
    ):
        result = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert result["acknowledged"] is True
    assert result["codex_thread_id"] == "thread-live"
    assert result["ack"]["mode"] == "exec_resume"
    assert seen["thread_id"] == "thread-live"


def test_codex_exec_resume_fallback_uses_autoping_thread_when_env_missing(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    codex_home = tmp_path / "codex-home"
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("RCX_CODEX_HOME", str(codex_home))
    _write_autoping_state(
        codex_home,
        repo,
        "thread-live",
        updated_at="2026-04-24T18:48:05+00:00",
    )
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    state["codex_thread_id"] = "thread-stale"
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    seen: dict[str, object] = {}

    def fake_exec_resume(repo_root, event_record, *, thread_id, timeout_s):
        seen["thread_id"] = thread_id
        return {
            "acknowledged": True,
            "ack": {
                "acknowledged_at": "2026-04-17T00:00:00+00:00",
                "thread_id": thread_id,
                "target": "codex",
                "mode": "exec_resume",
                "pid": 12345,
            },
            "codex_thread_id": thread_id,
        }

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        side_effect=pager_mod.PipelineAgentPagerError("ws://127.0.0.1:8765 unavailable: HTTPError"),
    ), patch.object(
        pager_mod,
        "_dispatch_codex_exec_resume",
        side_effect=fake_exec_resume,
    ):
        result = pager_mod._dispatch_codex(repo, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert result["acknowledged"] is True
    assert result["codex_thread_id"] == "thread-live"
    assert seen["thread_id"] == "thread-live"


def test_codex_exec_resume_fallback_skips_paused_context_exhausted_autoping_thread(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    codex_home = tmp_path / "codex-home"
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("RCX_CODEX_HOME", str(codex_home))
    _write_autoping_state(
        codex_home,
        repo,
        "thread-exhausted",
        updated_at="2026-04-24T18:48:05+00:00",
        status="context_exhausted_paused",
    )
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        side_effect=pager_mod.PipelineAgentPagerError(
            "ws://127.0.0.1:8765 unavailable: HTTPError"
        ),
    ), patch.object(
        pager_mod,
        "_dispatch_codex_exec_resume",
        side_effect=AssertionError("exhausted autoping thread must not be resumed"),
    ):
        result = pager_mod._dispatch_codex(repo, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert result["acknowledged"] is False
    assert "unavailable" in result["error"]


def test_codex_exec_resume_fallback_skips_paused_context_exhausted_env_thread(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    codex_home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-exhausted")
    monkeypatch.setenv("RCX_CODEX_HOME", str(codex_home))
    _write_autoping_state(
        codex_home,
        repo,
        "thread-exhausted",
        updated_at="2026-04-24T18:48:05+00:00",
        status="context_exhausted_paused",
    )
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    state["codex_thread_id"] = "thread-exhausted"
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        side_effect=pager_mod.PipelineAgentPagerError(
            "ws://127.0.0.1:8765 unavailable: HTTPError"
        ),
    ), patch.object(
        pager_mod,
        "_dispatch_codex_exec_resume",
        side_effect=AssertionError("exhausted ambient thread must not be resumed"),
    ):
        result = pager_mod._dispatch_codex(repo, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert result["acknowledged"] is False
    assert "unavailable" in result["error"]


def test_replay_prefers_autoping_thread_over_stale_delivery_receipt(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="codex")
    codex_home = tmp_path / "codex-home"
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("RCX_CODEX_HOME", str(codex_home))
    _write_autoping_state(
        codex_home,
        repo,
        "thread-live",
        updated_at="2026-04-24T18:48:05+00:00",
    )
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager state reconciliation test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    event_log_path = repo / pager_mod.EVENT_LOG_PATH
    event_log_path.parent.mkdir(parents=True, exist_ok=True)
    event_log_path.write_text(json.dumps(event) + "\n", encoding="utf-8")
    delivery_path = repo / pager_mod.DELIVERY_LOG_PATH
    delivery_path.write_text(
        json.dumps(
            {
                "event_id": event["event_id"],
                "target": "codex",
                "ack": {
                    "acknowledged_at": "2026-04-24T18:47:07+00:00",
                    "target": "codex",
                    "thread_id": "thread-stale",
                },
                "codex_thread_id": "thread-stale",
                "recorded_at": "2026-04-24T18:47:07+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    replay = pager_mod.dispatch_pending_events(repo)

    assert replay["attempted"] == []
    state = _load_state(repo)
    assert state["codex_thread_id"] == "thread-live"
    entry = state["events"][event["event_id"]]
    assert entry["pending_targets"] == []


def test_codex_exec_resume_env_preserves_live_codex_environment(monkeypatch):
    monkeypatch.setenv("HOME", "/tmp/rcx-codex-runtime-home")
    monkeypatch.setenv("CODEX_HOME", "/tmp/rcx-codex-runtime-home")
    monkeypatch.setenv("RCX_CODEX_HOME", "/tmp/rcx-codex-runtime-home")
    monkeypatch.setenv("KEEP_ME", "yes")

    env = pager_mod._codex_exec_resume_env()  # ANTICHEAT_OK: direct pager adapter contract test

    assert env["HOME"] == "/tmp/rcx-codex-runtime-home"
    assert env["CODEX_HOME"] == "/tmp/rcx-codex-runtime-home"
    assert env["RCX_CODEX_HOME"] == "/tmp/rcx-codex-runtime-home"
    assert env["KEEP_ME"] == "yes"


def test_codex_exec_resume_command_uses_read_only_sandbox_without_bypass():
    command = pager_mod._codex_exec_resume_command(  # ANTICHEAT_OK: pager argv contract test
        "codex-bin",
        "thread-live",
        "wake prompt",
    )

    assert command[:3] == [
        "codex-bin",
        "exec",
        "resume",
    ]
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    disabled_features = {
        command[index + 1]
        for index, value in enumerate(command[:-1])
        if value == "--disable"
    }
    assert disabled_features == set(pager_mod.CODEX_NO_TOOLS_DISABLED_FEATURES)
    assert 'sandbox_mode="read-only"' in command
    assert 'approval_policy="never"' in command
    assert command[-2:] == ["thread-live", "wake prompt"]
    assert "--dangerously-bypass-approvals-and-sandbox" not in command


def test_codex_exec_resume_requires_success_before_acknowledgement(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    terminated: list[int] = []

    class RunningPopen:
        pid = 4242

        def __init__(self, *args, **kwargs):
            pass

        def wait(self, timeout=None):
            raise subprocess.TimeoutExpired(["codex"], timeout)

    monkeypatch.setattr(pager_mod.subprocess, "Popen", RunningPopen)
    monkeypatch.setattr(
        pager_mod,
        "_terminate_process_group",
        lambda proc: terminated.append(proc.pid),
    )

    result = pager_mod._dispatch_codex_exec_resume(  # ANTICHEAT_OK: direct pager adapter contract test
        repo,
        event,
        thread_id="thread-live",
        timeout_s=0.01,
    )

    assert result["acknowledged"] is False
    assert result["codex_thread_id"] == "thread-live"
    assert "timed out" in result["error"]
    assert terminated == [4242]


def test_codex_exec_resume_acknowledges_only_zero_exit(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )

    class SuccessfulPopen:
        pid = 4243

        def __init__(self, *args, **kwargs):
            pass

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(pager_mod.subprocess, "Popen", SuccessfulPopen)

    result = pager_mod._dispatch_codex_exec_resume(  # ANTICHEAT_OK: direct pager adapter contract test
        repo,
        event,
        thread_id="thread-live",
        timeout_s=0.01,
    )

    assert result["acknowledged"] is True
    assert result["ack"]["mode"] == "exec_resume"
    assert result["ack"]["thread_id"] == "thread-live"
    assert result["ack"]["pid"] == 4243


def test_replay_uses_delivery_receipt_log_after_state_persist_crash(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="codex")

    dispatch_calls: list[str] = []

    def fake_dispatch(repo_root, target, event, state, config, *, timeout_s):
        dispatch_calls.append(target)
        return {
            "acknowledged": True,
            "ack": {
                "acknowledged_at": "2026-04-17T00:00:00+00:00",
                "thread_id": "thread-1",
                "turn_id": "turn-1",
                "target": "codex",
            },
            "codex_thread_id": "thread-1",
        }

    original_save_state = pager_mod._save_state  # ANTICHEAT_OK: crash-window regression harness
    save_calls = {"count": 0}

    def crashing_save_state(repo_root, state):
        save_calls["count"] += 1
        if save_calls["count"] >= 3:
            raise RuntimeError("simulated crash during pager state persist")
        return original_save_state(repo_root, state)

    monkeypatch.setattr(pager_mod, "_dispatch_target", fake_dispatch)
    monkeypatch.setattr(pager_mod, "_save_state", crashing_save_state)

    try:
        pager_mod.emit_transition_event(repo, **_event_kwargs())
    except RuntimeError as exc:
        assert "simulated crash" in str(exc)
    else:
        raise AssertionError("emit_transition_event should fail during simulated crash")

    state = _load_state(repo)
    event_id = next(iter(state["events"]))
    assert set(state["events"][event_id]["delivered_targets"]) == {"codex"}
    assert state["events"][event_id]["pending_targets"] == []
    receipts = _load_delivery_log(repo)
    assert len(receipts) == 1
    assert receipts[0]["event_id"] == event_id
    assert receipts[0]["target"] == "codex"

    monkeypatch.setattr(
        pager_mod,
        "_dispatch_target",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("codex should not be redelivered")),
    )
    monkeypatch.setattr(pager_mod, "_save_state", original_save_state)

    replay = pager_mod.dispatch_pending_events(repo)
    assert replay["attempted"] == []
    state = _load_state(repo)
    entry = state["events"][event_id]
    assert set(entry["delivered_targets"]) == {"codex"}
    assert entry["pending_targets"] == []
    assert state["codex_thread_id"] == "thread-1"
    assert dispatch_calls == ["codex"]


def test_receipt_log_failure_after_ack_does_not_redeliver_same_event(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="codex")

    dispatch_calls: list[str] = []

    def fake_dispatch(repo_root, target, event, state, config, *, timeout_s):
        dispatch_calls.append(target)
        return {
            "acknowledged": True,
            "ack": {
                "acknowledged_at": "2026-04-17T00:00:00+00:00",
                "thread_id": "thread-1",
                "turn_id": "turn-1",
                "target": "codex",
            },
            "codex_thread_id": "thread-1",
        }

    monkeypatch.setattr(pager_mod, "_dispatch_target", fake_dispatch)
    monkeypatch.setattr(
        pager_mod,
        "_append_delivery_receipt",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("simulated crash after target ACK but before durable receipt append")
        ),
    )

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())
    assert result["attempted"][0]["acknowledged"] is True
    assert "simulated crash" in result["attempted"][0]["receipt_log_warning"]

    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert set(entry["delivered_targets"]) == {"codex"}
    assert entry["pending_targets"] == []
    assert _load_delivery_log(repo) == []

    monkeypatch.setattr(
        pager_mod,
        "_dispatch_target",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("codex should not be redelivered")
        ),
    )

    replay = pager_mod.dispatch_pending_events(repo)
    assert replay["attempted"] == []
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert set(entry["delivered_targets"]) == {"codex"}
    assert entry["pending_targets"] == []
    assert dispatch_calls == ["codex"]


def test_codex_ack_budget_is_shared_across_stale_thread_reseed(tmp_path):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    state["codex_thread_id"] = "thread-stale"
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    calls: list[float] = []
    request_batches: list[list[dict]] = []

    def fake_exchange(url, requests, timeout_s):
        request_batches.append(requests)
        calls.append(timeout_s)
        if len(calls) == 1:
            time.sleep(0.12)
            return [
                _codex_initialize_response(1),
                _codex_error_response(2, "no rollout found for thread id thread-stale"),
            ]
        raise pager_mod.PipelineAgentPagerError(
            f"second codex exchange exceeded remaining budget ({timeout_s:.3f}s)"
        )

    with patch.object(pager_mod, "_codex_app_server_exchange", side_effect=fake_exchange):
        failed = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=0.2)  # ANTICHEAT_OK

    assert failed["acknowledged"] is False
    assert "remaining budget" in failed["error"]
    assert len(calls) == 2
    assert calls[0] <= 0.2
    assert calls[1] < calls[0]
    assert [request["method"] for request in request_batches[0]] == [
        "initialize",
        "turn/start",
    ]
    assert [request["method"] for request in request_batches[1]] == [
        "initialize",
        "thread/start",
        "turn/start",
    ]


def test_emit_transition_event_clears_stale_codex_thread_id_when_dispatch_requests_it(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="codex")
    state = pager_mod._default_state()  # ANTICHEAT_OK: state persistence regression
    state["codex_thread_id"] = "thread-dead"
    pager_mod._save_state(repo, state)  # ANTICHEAT_OK: direct pager state setup

    def stale_thread_failure(repo_root, target, event, state, config, *, timeout_s):
        assert state["codex_thread_id"] == "thread-dead"
        return {
            "acknowledged": False,
            "error": "thread not found: thread-dead",
            "codex_thread_id": None,
            "clear_codex_thread_id": True,
        }

    monkeypatch.setattr(pager_mod, "_dispatch_target", stale_thread_failure)

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())

    assert result["attempted"] == [
        {
            "event_id": result["event_id"],
            "target": "codex",
            "acknowledged": False,
            "error": "thread not found: thread-dead",
            "receipt_log_warning": "",
        }
    ]
    state = _load_state(repo)
    assert state["codex_thread_id"] is None
    entry = state["events"][result["event_id"]]
    assert entry["pending_targets"] == ["codex"]


# --------------------------------------------------------------------------- #
# Wave-2 claude leg: quick-ack ENQUEUE to the wave-1 receiver (no blocking turn)
# --------------------------------------------------------------------------- #


def test_dispatch_claude_enqueues_to_receiver_and_returns_accepted_async(tmp_path):
    """The claude leg ENQUEUES the page to the wave-1 receiver and quick-acks.

    Wave 2: _dispatch_claude no longer runs a (resume or fresh) ``claude`` turn
    under the ack budget; it enqueues the event into the claude_pager_receiver
    file-queue and returns ``accepted_async``. The enqueue IS the quick-ack -- the
    event lands durably in the receiver's queue and the call returns WITHOUT
    spawning any subprocess. It does NOT return ``acknowledged``: the dispatch loop
    must never take the synchronous delivered-on-ack write for this leg.
    """
    repo = tmp_path / "repo"
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="claude",
        metadata=None,
        **_event_kwargs(),
    )

    # No subprocess may run on the claude leg: a blocking turn is exactly what the
    # ~10-20s ack budget killed every dispatch.
    with patch.object(
        pager_mod.subprocess,
        "run",
        side_effect=AssertionError("claude leg must not spawn a blocking turn"),
    ):
        result = pager_mod._dispatch_claude(repo, event, {}, timeout_s=5)  # ANTICHEAT_OK

    assert result["accepted_async"] is True
    assert result.get("acknowledged") is not True
    assert result["enqueue_status"] == "queued"
    assert not result.get("skipped")

    # The event is durably queued in the receiver's per-bus file-queue, and nothing
    # was marked delivered (the receiver wrote no delivery receipt).
    receiver = _receiver(repo)
    assert receiver.queued_event_ids() == [event["event_id"]]
    assert receiver.delivered_event_ids() == set()


def test_dispatch_claude_enqueue_leg_reads_no_session_id_resolution_is_delivery_time(
    tmp_path, monkeypatch
):
    """Ack-budget discipline: the ENQUEUE leg does NO session-id file I/O.

    Codex-parity moved the resume-vs-fresh decision (and the never-resume-the-live-
    orchestrator guard) to DELIVERY time, inside the receiver
    (``resolve_claude_page_delivery``); it is NOT done in the ack-budget-critical
    ``_dispatch_claude`` enqueue leg. So even with a well-formed dedicated monitor id
    AND a distinct live id present, ``_dispatch_claude`` neither reads the
    monitor/orchestrator session-id files nor spawns a turn -- it simply enqueues and
    quick-acks. The actual resume-the-monitor delivery (``claude --resume <monitor>``)
    and the fresh fallbacks are locked in test_claude_pager_receiver.py.
    """
    repo = tmp_path / "repo"
    monitor_path = repo / pager_mod.CLAUDE_MONITOR_SESSION_ID_PATH
    monitor_path.parent.mkdir(parents=True, exist_ok=True)
    monitor_path.write_text("sess-monitor-distinct", encoding="utf-8")
    live_path = repo / pager_mod.ORCHESTRATOR_SESSION_ID_PATH
    live_path.write_text("sess-live-distinct", encoding="utf-8")

    def _boom_monitor(*_a, **_k):
        raise AssertionError("ENQUEUE leg must not read the monitor session id")

    def _boom_live(*_a, **_k):
        raise AssertionError("ENQUEUE leg must not read the orchestrator session id")

    monkeypatch.setattr(pager_mod, "_read_claude_monitor_session_id", _boom_monitor)
    monkeypatch.setattr(pager_mod, "_read_orchestrator_session_id", _boom_live)
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="claude",
        metadata=None,
        **_event_kwargs(),
    )

    with patch.object(
        pager_mod.subprocess,
        "run",
        side_effect=AssertionError("claude ENQUEUE leg must not spawn a blocking turn / resume"),
    ):
        result = pager_mod._dispatch_claude(repo, event, {}, timeout_s=5)  # ANTICHEAT_OK

    assert result["accepted_async"] is True
    # The receiver resolves the target and delivers later (resume-the-monitor or fresh) --
    # its argv contract is locked in test_claude_pager_receiver.py.
    assert _receiver(repo).queued_event_ids() == [event["event_id"]]


# --------------------------------------------------------------------------- #
# resolve_claude_page_delivery -- codex-parity delivery-target resolver
# (the pager owns this; the receiver borrows + calls it at delivery time)
# --------------------------------------------------------------------------- #


def _write_pager_session_ids(repo, *, monitor=None, live=None):
    obs = repo / pager_mod.OBSERVABILITY_DIR
    obs.mkdir(parents=True, exist_ok=True)
    if monitor is not None:
        (repo / pager_mod.CLAUDE_MONITOR_SESSION_ID_PATH).write_text(monitor + "\n", encoding="utf-8")
    if live is not None:
        (repo / pager_mod.ORCHESTRATOR_SESSION_ID_PATH).write_text(live + "\n", encoding="utf-8")


def test_resolve_claude_page_delivery_resumes_when_monitor_set_and_distinct(tmp_path):
    """Monitor set + distinct from live -> resume INTO the monitor (RCX_CLAUDE_MONITOR=1)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_pager_session_ids(repo, monitor="sess-monitor", live="sess-live-distinct")

    plan = pager_mod.resolve_claude_page_delivery(repo, bus_dir=".agent_bus")  # ANTICHEAT_OK: resolver contract

    assert plan["mode"] == "resume"
    assert plan["monitor_session_id"] == "sess-monitor"
    assert plan["skip_reason"] == ""
    # Resume env never clobbers orchestrator_session_id (RCX_CLAUDE_MONITOR=1 + pipeline flag).
    assert plan["env"]["RCX_CLAUDE_MONITOR"] == "1"
    assert plan["env"]["RCX_PIPELINE_SESSION"] == "1"


def test_resolve_claude_page_delivery_fresh_when_monitor_unset(tmp_path):
    """No monitor file -> MONITOR_UNSET -> fresh page (RCX_CLAUDE_MONITOR cleared)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / pager_mod.OBSERVABILITY_DIR).mkdir(parents=True, exist_ok=True)

    plan = pager_mod.resolve_claude_page_delivery(repo, bus_dir=".agent_bus")  # ANTICHEAT_OK: resolver contract

    assert plan["mode"] == "fresh"
    assert plan["monitor_session_id"] is None
    assert plan["skip_reason"] == pager_mod.CLAUDE_SKIP_REASON_MONITOR_UNSET
    assert "RCX_CLAUDE_MONITOR" not in plan["env"]
    assert plan["env"]["RCX_PIPELINE_SESSION"] == "1"


def test_resolve_claude_page_delivery_fresh_when_monitor_equals_live(tmp_path):
    """Monitor == live orchestrator -> MONITOR_EQUALS_LIVE -> fresh (never resume live)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_pager_session_ids(repo, monitor="sess-same", live="sess-same")

    plan = pager_mod.resolve_claude_page_delivery(repo, bus_dir=".agent_bus")  # ANTICHEAT_OK: resolver contract

    assert plan["mode"] == "fresh"
    assert plan["monitor_session_id"] is None
    assert plan["skip_reason"] == pager_mod.CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE
    assert "RCX_CLAUDE_MONITOR" not in plan["env"]


def test_resolve_claude_page_delivery_fresh_when_monitor_malformed(tmp_path):
    """A malformed monitor id (internal whitespace) collapses to MONITOR_UNSET -> fresh."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_pager_session_ids(repo, monitor="sess monitor", live="sess-live")

    plan = pager_mod.resolve_claude_page_delivery(repo, bus_dir=".agent_bus")  # ANTICHEAT_OK: resolver contract

    assert plan["mode"] == "fresh"
    assert plan["skip_reason"] == pager_mod.CLAUDE_SKIP_REASON_MONITOR_UNSET


def test_resolve_claude_page_delivery_fail_open_fresh_on_read_error(tmp_path, monkeypatch):
    """Any resolution error fails OPEN to a fresh page -- never a resume, no page lost."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_pager_session_ids(repo, monitor="sess-monitor", live="sess-live")

    def _boom(*_a, **_k):
        raise RuntimeError("bus path validation blew up")

    monkeypatch.setattr(pager_mod, "_read_claude_monitor_session_id", _boom)

    plan = pager_mod.resolve_claude_page_delivery(repo, bus_dir=".agent_bus")  # ANTICHEAT_OK: resolver contract

    assert plan["mode"] == "fresh"
    assert plan["monitor_session_id"] is None
    assert "RCX_CLAUDE_MONITOR" not in plan["env"]


def test_claude_monitor_resume_env_sets_monitor_and_pipeline_flags(monkeypatch):
    """The resume env sets BOTH flags so the resumed monitor re-writes only its OWN id.

    With RCX_PIPELINE_SESSION=1 AND RCX_CLAUDE_MONITOR=1 the SessionStart hook skips the
    orchestrator-suppression guard and writes claude_monitor_session_id (idempotent),
    NEVER orchestrator_session_id -- even if the ambient env had the monitor flag unset.
    """
    monkeypatch.delenv("RCX_CLAUDE_MONITOR", raising=False)
    monkeypatch.setenv("RCX_PIPELINE_SESSION", "")

    env = pager_mod._claude_monitor_resume_env()  # ANTICHEAT_OK: env contract

    assert env["RCX_CLAUDE_MONITOR"] == "1"
    assert env["RCX_PIPELINE_SESSION"] == "1"


def test_session_id_readers_accept_explicit_bus_dir(tmp_path):
    """The session-id readers accept an explicit bus_dir (delivery-time resolution seam).

    The receiver's detached drain subprocess has no ContextVar bus set, so it passes its
    own bus_dir; the explicit kwarg must resolve the SAME file the default (ContextVar)
    path does for the default bus.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_pager_session_ids(repo, monitor="sess-monitor", live="sess-live")

    assert (
        pager_mod._read_claude_monitor_session_id(repo, bus_dir=".agent_bus")  # ANTICHEAT_OK: reader contract
        == "sess-monitor"
        == pager_mod._read_claude_monitor_session_id(repo)  # ANTICHEAT_OK: reader contract (default bus)
    )
    assert (
        pager_mod._read_orchestrator_session_id(repo, bus_dir=".agent_bus")  # ANTICHEAT_OK: reader contract
        == "sess-live"
        == pager_mod._read_orchestrator_session_id(repo)  # ANTICHEAT_OK: reader contract (default bus)
    )


def test_dispatch_claude_enqueue_is_idempotent_across_redispatch(tmp_path):
    """Re-dispatching the same event re-enqueues idempotently (re-queue-on-failure).

    The leg leaves the target pending until the async receipt promotes it, so a
    later dispatch calls enqueue again. The receiver dedups by event_id, so the
    second enqueue is a no-op acceptance (``duplicate_queued``) -- still
    accepted_async, never a second queue entry.
    """
    repo = tmp_path / "repo"
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="claude",
        metadata=None,
        **_event_kwargs(),
    )

    first = pager_mod._dispatch_claude(repo, event, {}, timeout_s=5)  # ANTICHEAT_OK
    second = pager_mod._dispatch_claude(repo, event, {}, timeout_s=5)  # ANTICHEAT_OK

    assert first["accepted_async"] is True and second["accepted_async"] is True
    assert first["enqueue_status"] == "queued"
    assert second["enqueue_status"] == "duplicate_queued"
    assert _receiver(repo).queued_event_ids() == [event["event_id"]]


def test_dispatch_claude_fail_open_when_receiver_unavailable(tmp_path, monkeypatch):
    """Fail-open: an unavailable receiver leaves the target pending (retryable).

    If constructing/using the receiver raises (queue unwritable, module
    unavailable, ...), _dispatch_claude returns a normal retryable error
    (``acknowledged`` False, ``error`` set) -- NOT accepted_async and NOT a skip --
    so the dispatch loop leaves claude in pending_targets exactly as a transient
    failure did before. No page is lost and nothing is marked delivered.
    """
    repo = tmp_path / "repo"
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="claude",
        metadata=None,
        **_event_kwargs(),
    )

    def _unavailable(*_a, **_k):
        raise RuntimeError("receiver queue unavailable")

    monkeypatch.setattr(pager_mod, "_claude_pager_receiver", _unavailable)
    result = pager_mod._dispatch_claude(repo, event, {}, timeout_s=5)  # ANTICHEAT_OK

    assert result["acknowledged"] is False
    assert result.get("accepted_async") is not True
    assert not result.get("skipped")
    assert "enqueue failed" in result["error"]


def test_dispatch_claude_ensures_drain_after_enqueue_no_never_drained_window(tmp_path, monkeypatch):
    """PR #1137 P1: every enqueue is followed by a drain-ensure -> no never-drained window.

    The first wave-2 attempt enqueued and returned, but nothing started the receiver, so
    under route=both the claude queue was never drained. Wave 2b makes the leg
    self-sufficient: _dispatch_claude must ENQUEUE the page AND THEN ensure the receiver
    drain is running, in that ORDER (the event must be durably queued before the bounded
    drain pass is started, so the pass is guaranteed to observe it). The leg quick-acks
    accepted_async only after BOTH steps succeed.
    """
    repo = tmp_path / "repo"
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="claude",
        metadata=None,
        **_event_kwargs(),
    )
    fake = _RecordingReceiver()
    monkeypatch.setattr(pager_mod, "_claude_pager_receiver", lambda _root: fake)

    result = pager_mod._dispatch_claude(repo, event, {}, timeout_s=5)  # ANTICHEAT_OK

    assert result["accepted_async"] is True
    assert result.get("acknowledged") is not True
    assert result["enqueue_status"] == "queued"
    # Drain GUARANTEED after enqueue: both called, enqueue STRICTLY before ensure_draining.
    assert fake.calls == ["enqueue", "ensure_draining"]


def test_dispatch_claude_fail_open_when_drain_cannot_be_ensured(tmp_path, monkeypatch):
    """Fail-open on drain failure: a queue that may not drain is NEVER marked accepted.

    Even though the page was enqueued, if ensure_draining raises (the drainer cannot be
    started), _dispatch_claude must NOT return accepted_async -- it returns a normal
    retryable error (``acknowledged`` False, not a skip) so the dispatch loop leaves claude
    pending. A later dispatch re-enqueues idempotently and re-ensures the drain. This is the
    "leave pending if drain cannot be ensured" half of the two-phase fail-open contract.
    """
    repo = tmp_path / "repo"
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="claude",
        metadata=None,
        **_event_kwargs(),
    )
    fake = _RecordingReceiver(ensure_raises=RuntimeError("cannot start drainer"))
    monkeypatch.setattr(pager_mod, "_claude_pager_receiver", lambda _root: fake)

    result = pager_mod._dispatch_claude(repo, event, {}, timeout_s=5)  # ANTICHEAT_OK

    assert result["acknowledged"] is False
    assert result.get("accepted_async") is not True
    assert not result.get("skipped")
    assert "drain-ensure failed" in result["error"]
    # The enqueue still happened (page durably queued) before the drain-ensure failed.
    assert fake.calls == ["enqueue", "ensure_draining"]


def test_distinct_events_sharing_transition_key_both_enqueue_and_promote(tmp_path):
    """PR #1137 P2 end-to-end: two DISTINCT pager events that reuse a transition_key
    (different event_type -> different event_id) are BOTH enqueued and BOTH promotable.

    Before the event_id-only dedup fix the receiver collapsed them: the second enqueue
    returned a duplicate, the leg still quick-acked it, but the receipt-bridge (which
    promotes by event_id) left the second event pending forever. With event_id-only dedup,
    each distinct event is queued and each async receipt promotes its OWN event by event_id.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    repo = repo.resolve()

    # Same transition_key, different event_type/state -> two distinct event_ids.
    event_a = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="claude",
        metadata=None,
        **_event_kwargs(
            event_type="phase_b_implementer_started",
            state="phase_b_implementer_started",
        ),
    )
    event_b = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="claude",
        metadata=None,
        **_event_kwargs(
            event_type="phase_b_implementer_completed",
            state="phase_b_implementer_completed",
        ),
    )
    assert event_a["event_id"] != event_b["event_id"]
    assert event_a["transition_key"] == event_b["transition_key"]

    for event in (event_a, event_b):
        pager_mod._append_event_record(repo, event)  # ANTICHEAT_OK: seed the append-only event log
        result = pager_mod._dispatch_claude(repo, event, {}, timeout_s=5)  # ANTICHEAT_OK
        assert result["accepted_async"] is True
        # NEITHER distinct event is dropped as a transition_key duplicate.
        assert result["enqueue_status"] == "queued"

    # Both distinct events are durably queued (P2: not collapsed by the shared transition_key).
    assert set(_receiver(repo).queued_event_ids()) == {event_a["event_id"], event_b["event_id"]}

    # Each async exit-0 receipt promotes its OWN event by event_id.
    _plant_receiver_receipt(repo, event_a["event_id"], transition_key=event_a["transition_key"])
    _plant_receiver_receipt(repo, event_b["event_id"], transition_key=event_b["transition_key"])
    events = pager_mod._load_events_from_log(repo)  # ANTICHEAT_OK: reconciliation test
    state = pager_mod._default_state()  # ANTICHEAT_OK: reconciliation test
    pager_mod._reconcile_delivery_state(repo, state, events)  # ANTICHEAT_OK: reconciliation test
    assert set(state["events"][event_a["event_id"]]["delivered_targets"]) == {"claude"}
    assert set(state["events"][event_b["event_id"]]["delivered_targets"]) == {"claude"}
    assert state["events"][event_a["event_id"]]["pending_targets"] == []
    assert state["events"][event_b["event_id"]]["pending_targets"] == []


def test_receipt_bridge_is_idempotent_and_tolerant_of_unknown_entries(tmp_path):
    """The reconcile receipt-bridge promotes claude by event_id, is idempotent across
    reconciles, and TOLERATES unknown/foreign receiver entries (skip, never raise).

    Unlike the pager-native delivery-receipt path (which RAISES on an unknown
    event_id), the receiver's delivered.jsonl is not authored per-pager-event, so an
    id this state has not seen -- or a malformed line -- is skipped. Re-reading the
    file across reconciles re-sets the same delivered[claude] (idempotent), and the
    receiver's file is never mutated/quarantined by the read.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    repo = repo.resolve()

    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager state reconciliation test
        route="claude",
        metadata=None,
        **_event_kwargs(),
    )
    pager_mod._append_event_record(repo, event)  # ANTICHEAT_OK: seed the append-only event log
    event_id = event["event_id"]

    # A KNOWN exit-0 receipt, a FOREIGN/unknown-event receipt, and a malformed line.
    _plant_receiver_receipt(repo, event_id, transition_key="receipt-1")
    _plant_receiver_receipt(repo, "unknown-foreign-event-id", transition_key="zzz")
    receipts_path = _receiver(repo).receipts_path
    with receipts_path.open("a", encoding="utf-8") as handle:
        handle.write("{ this is not valid json\n")
    raw_before = receipts_path.read_text(encoding="utf-8")

    events = pager_mod._load_events_from_log(repo)  # ANTICHEAT_OK: reconciliation test
    state = pager_mod._default_state()  # ANTICHEAT_OK: reconciliation test
    # Must NOT raise on the unknown entry or the malformed line.
    pager_mod._reconcile_delivery_state(repo, state, events)  # ANTICHEAT_OK: reconciliation test
    entry = state["events"][event_id]
    assert set(entry["delivered_targets"]) == {"claude"}
    assert entry["delivered_targets"]["claude"]["target"] == "claude"
    assert entry["pending_targets"] == []
    # The foreign event id created no state entry.
    assert "unknown-foreign-event-id" not in state["events"]
    # The receiver's own file was consumed AS-IS -- never quarantined/rewritten.
    assert receipts_path.read_text(encoding="utf-8") == raw_before
    assert not list(receipts_path.parent.glob("delivered.jsonl.corrupt.*"))

    # Idempotent: a second reconcile over the same file re-sets the same delivered.
    first_ack = dict(entry["delivered_targets"]["claude"])
    pager_mod._reconcile_delivery_state(repo, state, events)  # ANTICHEAT_OK: reconciliation test
    assert state["events"][event_id]["delivered_targets"]["claude"] == first_ack
    assert state["events"][event_id]["pending_targets"] == []


def test_emit_claude_leg_quick_acks_then_receipt_bridge_promotes(tmp_path):
    """End-to-end: route=claude quick-acks (accepted_async), writes NO delivered on
    enqueue, then the reconcile receipt-bridge promotes claude on the receiver's
    exit-0 receipt (matched by event_id).

    delivered_targets[claude] is written ONLY by that bridge, never on enqueue.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="claude")

    # Phase 1: emit. The leg only enqueues -- no subprocess may run.
    with patch.object(
        pager_mod.subprocess,
        "run",
        side_effect=AssertionError("claude leg must not spawn a blocking turn"),
    ):
        result = pager_mod.emit_transition_event(repo, **_event_kwargs())

    event_id = result["event_id"]
    assert result["route"] == "claude"
    assert len(result["attempted"]) == 1
    assert result["attempted"][0]["target"] == "claude"
    assert result["attempted"][0]["acknowledged"] is False

    entry = _load_state(repo)["events"][event_id]
    # The quick-ack (accepted_async) is recorded durably in the attempt record.
    assert entry["attempts"]["claude"]["last_enqueue_status"] == "queued"
    assert "last_accepted_async_at" in entry["attempts"]["claude"]
    # No delivered-on-enqueue: claude stays pending; nothing in delivered_targets.
    assert "claude" not in entry["delivered_targets"]
    assert entry["pending_targets"] == ["claude"]
    assert entry.get("skipped_targets", {}) == {}
    # No pager-native claude delivery receipt and no skip receipt were written.
    assert [r for r in _load_delivery_log(repo) if r.get("target") == "claude"] == []
    assert _load_skip_log(repo) == []
    # The receiver holds the queued page.
    assert _receiver(repo).queued_event_ids() == [event_id]

    # Phase 2: the receiver delivered asynchronously (exit 0) and wrote its receipt.
    _plant_receiver_receipt(repo, event_id, transition_key="receipt-1")
    with patch.object(
        pager_mod.subprocess,
        "run",
        side_effect=AssertionError("claude leg must not spawn a blocking turn"),
    ):
        pager_mod.dispatch_pending_events(repo)

    entry2 = _load_state(repo)["events"][event_id]
    assert set(entry2["delivered_targets"]) == {"claude"}
    assert entry2["delivered_targets"]["claude"]["target"] == "claude"
    assert entry2["pending_targets"] == []


def test_both_route_codex_delivers_while_claude_quick_acks_pending(tmp_path, monkeypatch):
    """route=both: codex delivers synchronously; the claude leg quick-acks and stays
    pending until the receiver's async receipt promotes it.

    The two legs are independent: codex goes through its normal delivered/receipt
    flow (faked here), while claude enqueues to the receiver (accepted_async) and is
    NOT delivered on enqueue. After the receiver records its exit-0 receipt, a second
    dispatch promotes claude via the receipt-bridge -- both legs delivered. The codex
    leg is entirely unchanged.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="both")
    monkeypatch.setenv("RCX_CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.setattr(pager_mod, "_dispatch_codex", _ack_codex)

    with patch.object(
        pager_mod.subprocess,
        "run",
        side_effect=AssertionError("claude leg must not spawn a blocking turn"),
    ):
        result = pager_mod.emit_transition_event(repo, **_event_kwargs())
    event_id = result["event_id"]

    entry = _load_state(repo)["events"][event_id]
    # codex delivered; claude only quick-acked (pending, not delivered).
    assert set(entry["delivered_targets"]) == {"codex"}
    assert entry["pending_targets"] == ["claude"]
    assert entry.get("skipped_targets", {}) == {}
    assert len([r for r in _load_delivery_log(repo) if r["target"] == "codex"]) == 1
    assert [r for r in _load_delivery_log(repo) if r.get("target") == "claude"] == []
    assert _load_skip_log(repo) == []
    assert _receiver(repo).queued_event_ids() == [event_id]

    # Receiver delivers asynchronously (exit 0) -> receipt -> bridge promotes claude.
    _plant_receiver_receipt(repo, event_id, transition_key="receipt-1")
    monkeypatch.setattr(pager_mod, "_dispatch_codex", _ack_codex)
    with patch.object(
        pager_mod.subprocess,
        "run",
        side_effect=AssertionError("claude leg must not spawn a blocking turn"),
    ):
        pager_mod.dispatch_pending_events(repo)

    entry2 = _load_state(repo)["events"][event_id]
    assert set(entry2["delivered_targets"]) == {"codex", "claude"}
    assert entry2["delivered_targets"]["claude"]["target"] == "claude"
    assert entry2["pending_targets"] == []


def test_both_route_claude_quick_ack_never_touches_live_session(tmp_path, monkeypatch):
    """route=both with a live orchestrator id present (and a colliding monitor id):
    the claude leg never reads or resumes it -- it just enqueues. (pager != autoping;
    never resume the live orchestrator.)
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="both")
    monkeypatch.setenv("RCX_CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.setattr(pager_mod, "_dispatch_codex", _ack_codex)

    live_path = repo / pager_mod.ORCHESTRATOR_SESSION_ID_PATH
    live_path.parent.mkdir(parents=True, exist_ok=True)
    live_path.write_text("sess-live-never-touched", encoding="utf-8")
    monitor_path = repo / pager_mod.CLAUDE_MONITOR_SESSION_ID_PATH
    monitor_path.write_text("sess-live-never-touched", encoding="utf-8")

    with patch.object(
        pager_mod.subprocess,
        "run",
        side_effect=AssertionError("claude leg must not spawn a blocking turn / resume"),
    ):
        result = pager_mod.emit_transition_event(repo, **_event_kwargs())
    event_id = result["event_id"]

    entry = _load_state(repo)["events"][event_id]
    assert set(entry["delivered_targets"]) == {"codex"}
    assert entry["pending_targets"] == ["claude"]
    assert _receiver(repo).queued_event_ids() == [event_id]


@pytest.mark.parametrize(
    "skip_reason",
    [
        pager_mod.CLAUDE_SKIP_REASON_MONITOR_UNSET,
        pager_mod.CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE,
    ],
)
def test_legacy_persisted_monitor_skip_in_state_is_scrubbed_on_reconcile(
    tmp_path, monkeypatch, skip_reason
):
    """Migration safety: a monitor-state skip PERSISTED in the state file by an
    older build (or the pre-direct-fallback terminal branch) is SCRUBBED by
    _reconcile_delivery_state so the claude leg returns to pending (retryable via a
    direct page), never left permanently parked. _dispatch_claude no longer emits
    these skips, but a migrated repo may still carry one on disk. The scrub is what
    keeps such a stale page from being a silent, permanent drop.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    repo = repo.resolve()
    monkeypatch.setenv("RCX_CODEX_HOME", str(tmp_path / "codex-home"))

    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager state reconciliation test
        route="both",
        metadata=None,
        **_event_kwargs(),
    )
    pager_mod._append_event_record(repo, event)  # ANTICHEAT_OK: seed the append-only event log
    event_id = event["event_id"]

    persisted = pager_mod._default_state()  # ANTICHEAT_OK: direct pager state reconciliation test
    persisted["events"][event_id] = {
        "event_id": event_id,
        "route": "both",
        "requested_targets": ["codex", "claude"],
        "delivered_targets": {"codex": {"target": "codex"}},
        "skipped_targets": {
            "claude": {"skip_reason": skip_reason, "skipped_at": "2026-06-01T00:00:01+00:00"}
        },
        "attempts": {},
        "pending_targets": [],
        "created_at": "2026-06-01T00:00:00+00:00",
        "updated_at": "2026-06-01T00:00:00+00:00",
    }
    events = pager_mod._load_events_from_log(repo)  # ANTICHEAT_OK: direct pager state reconciliation test
    pager_mod._reconcile_delivery_state(repo, persisted, events)  # ANTICHEAT_OK: direct pager state reconciliation test
    entry = persisted["events"][event_id]
    assert "claude" not in entry.get("skipped_targets", {})
    assert entry["pending_targets"] == ["claude"]
    assert set(entry["delivered_targets"]) == {"codex"}


@pytest.mark.parametrize(
    "skip_reason",
    [
        pager_mod.CLAUDE_SKIP_REASON_MONITOR_UNSET,
        pager_mod.CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE,
    ],
)
def test_legacy_monitor_skip_receipt_is_ignored_on_reconcile(
    tmp_path, monkeypatch, skip_reason
):
    """Migration safety: a durable monitor-state skip RECEIPT written by an older
    build is IGNORED on rebuild -- _reconcile_delivery_state must NOT rebuild a
    skipped_targets entry from it, so the claude leg stays pending (retryable via a
    direct page).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    repo = repo.resolve()
    monkeypatch.setenv("RCX_CODEX_HOME", str(tmp_path / "codex-home"))

    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager state reconciliation test
        route="both",
        metadata=None,
        **_event_kwargs(),
    )
    pager_mod._append_event_record(repo, event)  # ANTICHEAT_OK: seed the append-only event log
    event_id = event["event_id"]

    skip_path = repo / pager_mod.SKIP_LOG_PATH
    skip_path.parent.mkdir(parents=True, exist_ok=True)
    skip_path.write_text(
        json.dumps({
            "event_id": event_id,
            "target": "claude",
            "skip_reason": skip_reason,
            "recorded_at": "2026-06-01T00:00:01+00:00",
        }) + "\n",
        encoding="utf-8",
    )
    assert len(_load_skip_log(repo)) == 1  # the planted receipt is on disk

    rebuilt = pager_mod._default_state()  # ANTICHEAT_OK: direct pager state reconciliation test
    events = pager_mod._load_events_from_log(repo)  # ANTICHEAT_OK: direct pager state reconciliation test
    pager_mod._reconcile_delivery_state(repo, rebuilt, events)  # ANTICHEAT_OK: direct pager state reconciliation test
    entry = rebuilt["events"][event_id]
    assert "claude" not in entry.get("skipped_targets", {})
    # No delivery receipts on disk -> both requested legs are pending after rebuild.
    assert entry["pending_targets"] == ["codex", "claude"]


def test_legacy_persisted_monitor_skip_recovers_via_receiver_enqueue(tmp_path, monkeypatch):
    """Migration recovery: a claude leg left terminally parked in the state file by an
    older build is scrubbed on reconcile and then recovered via the Wave-2 enqueue
    path -- quick-acked (accepted_async), then delivered by the receiver's async
    receipt. Proves a migrated repo never permanently drops the claude page. Codex
    stays entirely unaffected.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    repo = repo.resolve()
    _write_config(repo, route="both")
    monkeypatch.setenv("RCX_CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.setattr(pager_mod, "_dispatch_codex", _ack_codex)

    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager state reconciliation test
        route="both",
        metadata=None,
        **_event_kwargs(),
    )
    pager_mod._append_event_record(repo, event)  # ANTICHEAT_OK: seed the append-only event log
    event_id = event["event_id"]

    # Park claude terminally in the persisted state exactly as an older build would.
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager state setup
    state["events"][event_id] = {
        "event_id": event_id,
        "route": "both",
        "requested_targets": ["codex", "claude"],
        "delivered_targets": {"codex": {"target": "codex"}},
        "skipped_targets": {
            "claude": {
                "skip_reason": pager_mod.CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE,
                "skipped_at": "2026-06-01T00:00:01+00:00",
            }
        },
        "attempts": {},
        "pending_targets": [],
        "created_at": "2026-06-01T00:00:00+00:00",
        "updated_at": "2026-06-01T00:00:00+00:00",
    }
    state_path = repo / pager_mod.STATE_PATH
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")
    reloaded = _load_state(repo)["events"][event_id]
    assert "claude" in reloaded["skipped_targets"]
    assert "claude" not in reloaded["pending_targets"]

    # Dispatch: the stale skip is scrubbed and the claude leg is re-attempted via the
    # receiver enqueue (accepted_async) -- no blocking turn, no skip produced.
    with patch.object(
        pager_mod.subprocess,
        "run",
        side_effect=AssertionError("claude leg must not spawn a blocking turn"),
    ):
        report = pager_mod.dispatch_pending_events(repo)

    assert [a["target"] for a in report["attempted"]] == ["claude"]
    entry = _load_state(repo)["events"][event_id]
    # The re-attempt quick-acked (accepted_async), recorded in the attempt record.
    assert entry["attempts"]["claude"]["last_enqueue_status"] == "queued"
    assert "claude" not in entry.get("skipped_targets", {})
    assert entry["pending_targets"] == ["claude"]
    assert _load_skip_log(repo) == []
    assert _receiver(repo).queued_event_ids() == [event_id]

    # The receiver delivers (exit 0) -> receipt -> bridge promotes claude.
    _plant_receiver_receipt(repo, event_id, transition_key="receipt-1")
    with patch.object(
        pager_mod.subprocess,
        "run",
        side_effect=AssertionError("claude leg must not spawn a blocking turn"),
    ):
        pager_mod.dispatch_pending_events(repo)
    entry2 = _load_state(repo)["events"][event_id]
    assert set(entry2["delivered_targets"]) == {"codex", "claude"}
    assert entry2["pending_targets"] == []


def test_other_skip_reason_remains_terminal_with_durable_receipt(tmp_path, monkeypatch):
    """The terminal skip branch is retained for any FUTURE/other skip reason.

    Only the two transient monitor-state reasons (UNSET / EQUALS_LIVE) are
    retryable. Any OTHER skip_reason a future claude leg might emit MUST stay
    terminal: parked in skipped_targets, a durable skip receipt written, and never
    retried. This locks the contract that exactly the two monitor-state reasons --
    and no others -- are exempt from terminal fail-closed handling. No production
    path emits such a reason today, so the leg is driven via a stubbed
    _dispatch_claude that returns a synthetic terminal skip.
    """
    other_reason = "claude_some_future_terminal_reason"
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="both")
    monkeypatch.setenv("RCX_CODEX_HOME", str(tmp_path / "codex-home"))

    monkeypatch.setattr(pager_mod, "_dispatch_codex", _ack_codex)

    def _claude_skip_other(repo_root, event, config, *, timeout_s):
        return {
            "acknowledged": False,
            "skipped": True,
            "skip_reason": other_reason,
        }

    monkeypatch.setattr(pager_mod, "_dispatch_claude", _claude_skip_other)

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())
    event_id = result["event_id"]

    state = _load_state(repo)
    entry = state["events"][event_id]
    # codex delivered; the OTHER claude skip is TERMINAL -> parked, off pending.
    assert set(entry["delivered_targets"]) == {"codex"}
    assert entry["skipped_targets"]["claude"]["skip_reason"] == other_reason
    assert entry["pending_targets"] == []
    assert entry["attempts"]["claude"]["last_skip_reason"] == other_reason
    # A durable skip receipt is written so the terminal skip survives a rebuild.
    skip_receipts = _load_skip_log(repo)
    assert len(skip_receipts) == 1
    assert skip_receipts[0]["target"] == "claude"
    assert skip_receipts[0]["skip_reason"] == other_reason

    # A SECOND dispatch must NOT re-attempt the terminal claude leg.
    replay = pager_mod.dispatch_pending_events(repo)
    assert replay["attempted"] == []
    assert len(_load_skip_log(repo)) == 1  # receipt not duplicated on replay


def test_session_start_hook_writes_orchestrator_session_id_for_pager_read(tmp_path):
    """K-2 pager-session-id-autowrite regression: the new
    .claude/hooks/session-start.sh SessionStart hook writes the active
    session id to <repo_root>/.agent_bus/observability/orchestrator_session_id
    so the pager's reader at pipeline_agent_pager.py:656 resolves it for
    `claude --resume <id>` dispatch. This integration test exercises the
    hook AND the pager's reader end-to-end (no mocks).
    """
    repo_root = Path(__file__).resolve().parents[3]
    hook_path = repo_root / ".claude" / "hooks" / "session-start.sh"
    assert hook_path.exists(), f"hook script missing at {hook_path}"

    session_id = "1e9c6188-11d3-4cbb-87eb-399699e72bcc"
    payload = json.dumps({
        "session_id": session_id,
        "hook_event_name": "SessionStart",
        "source": "startup",
    })

    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(tmp_path),
        "CLAUDE_PROJECT_DIR": str(tmp_path),
    }
    result = subprocess.run(
        ["bash", str(hook_path)],
        input=payload,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, (
        f"hook exit={result.returncode} stderr={result.stderr!r}"
    )

    target = tmp_path / ".agent_bus" / "observability" / "orchestrator_session_id"
    assert target.exists(), f"hook did not write {target}"
    assert target.read_text().strip() == session_id

    resolved = pager_mod._read_orchestrator_session_id(tmp_path)  # ANTICHEAT_OK: integration read
    assert resolved == session_id

    malformed_cases = [
        '{"not_session_id":"x"}',
        '{"session_id":""}',
        '{"session_id":"has space"}',
        'not valid json',
    ]
    for payload_bad in malformed_cases:
        clean_root = tmp_path / f"clean_{abs(hash(payload_bad))}"
        clean_root.mkdir(parents=True, exist_ok=True)
        env_clean = {**env, "CLAUDE_PROJECT_DIR": str(clean_root)}
        r = subprocess.run(
            ["bash", str(hook_path)],
            input=payload_bad,
            env=env_clean,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        assert r.returncode == 0, f"hook should fail-open on {payload_bad!r}, got exit={r.returncode}"
        bad_target = clean_root / ".agent_bus" / "observability" / "orchestrator_session_id"
        assert not bad_target.exists(), (
            f"hook wrote file for malformed payload {payload_bad!r}: "
            f"{bad_target.read_text() if bad_target.exists() else '<missing>'}"
        )


def test_codex_exec_resume_env_preserves_rcx_overlay_when_present(monkeypatch):
    monkeypatch.setenv("HOME", "/tmp/real-home")
    monkeypatch.setenv("CODEX_HOME", "/tmp/real-codex-home")
    monkeypatch.setenv("RCX_CODEX_HOME", "/tmp/rcx-overlay")

    env = pager_mod._codex_exec_resume_env()  # ANTICHEAT_OK: tool unit test

    assert env["HOME"] == "/tmp/real-home"
    assert env["CODEX_HOME"] == "/tmp/real-codex-home"
    assert env["RCX_CODEX_HOME"] == "/tmp/rcx-overlay"


def test_requested_targets_both_expands_to_codex_and_claude():
    """Acceptance (e): route=both fans out to BOTH the codex and claude legs."""
    assert pager_mod._requested_targets("both") == ["codex", "claude"]  # ANTICHEAT_OK: route fan-out contract test
    assert pager_mod._requested_targets("codex") == ["codex"]  # ANTICHEAT_OK: route fan-out contract test
    assert pager_mod._requested_targets("claude") == ["claude"]  # ANTICHEAT_OK: route fan-out contract test


def test_executor_config_committed_codex_role_and_pager_defaults():
    """The committed role, backend, reviewer, and pager selections are all Codex."""
    repo_root = Path(__file__).resolve().parents[3]
    config_path = repo_root / "mu" / "tools" / "executors" / "executor_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["role_agents"] == {"implementer": "codex", "reviewer": "codex"}
    assert config["backends"] == {
        "post_merge_supervisor": "codex",
        "dialectic_executor": "codex",
        "phase_a_executor": "codex",
        "phase_b_executor": "codex",
        "bot_remediation": "codex",
        "commit_executor": None,
    }
    assert config["bridge_reviewers"] == {"phase_a": "codex", "phase_b": "codex"}
    assert config["pipeline_agent_pager"] == {"enabled": True, "route": "codex"}


def test_session_start_hook_writes_claude_monitor_session_id_when_flag_set(tmp_path):
    """Acceptance (a): the Work-item-1 writer leg of .claude/hooks/session-start.sh.

    With RCX_CLAUDE_MONITOR=1 the SessionStart hook writes the active session id
    to the DEDICATED claude_monitor_session_id file (the pager's
    _read_claude_monitor_session_id resume target), NOT the live
    orchestrator_session_id. Without the flag the orchestrator behavior is
    unchanged and no monitor file is produced. Atomic write + fail-open preserved.
    Exercised end-to-end against the real hook and the real pager readers.
    """
    repo_root = Path(__file__).resolve().parents[3]
    hook_path = repo_root / ".claude" / "hooks" / "session-start.sh"
    assert hook_path.exists(), f"hook script missing at {hook_path}"

    session_id = "2f7d3c4a-55e1-4a2b-9c6d-aabbccddeeff"
    payload = json.dumps({
        "session_id": session_id,
        "hook_event_name": "SessionStart",
        "source": "startup",
    })

    # (a1) RCX_CLAUDE_MONITOR=1 -> writes claude_monitor_session_id, NOT orchestrator.
    monitor_root = tmp_path / "monitor"
    monitor_root.mkdir(parents=True, exist_ok=True)
    env_monitor = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(tmp_path),
        "CLAUDE_PROJECT_DIR": str(monitor_root),
        "RCX_CLAUDE_MONITOR": "1",
    }
    result = subprocess.run(
        ["bash", str(hook_path)],
        input=payload, env=env_monitor,
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert result.returncode == 0, f"hook exit={result.returncode} stderr={result.stderr!r}"
    obs = monitor_root / ".agent_bus" / "observability"
    monitor_file = obs / "claude_monitor_session_id"
    orchestrator_file = obs / "orchestrator_session_id"
    assert monitor_file.exists(), f"monitor writer did not write {monitor_file}"
    assert monitor_file.read_text().strip() == session_id
    # The dedicated-monitor writer must NEVER touch the live orchestrator file.
    assert not orchestrator_file.exists()
    # The pager resolves the dedicated monitor id end-to-end.
    resolved_monitor = pager_mod._read_claude_monitor_session_id(monitor_root)  # ANTICHEAT_OK: integration read
    assert resolved_monitor == session_id

    # (a2) Without the flag -> orchestrator behavior unchanged; no monitor file.
    orch_root = tmp_path / "orch"
    orch_root.mkdir(parents=True, exist_ok=True)
    env_orch = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(tmp_path),
        "CLAUDE_PROJECT_DIR": str(orch_root),
    }
    result2 = subprocess.run(
        ["bash", str(hook_path)],
        input=payload, env=env_orch,
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert result2.returncode == 0, f"hook exit={result2.returncode} stderr={result2.stderr!r}"
    obs2 = orch_root / ".agent_bus" / "observability"
    orch_file2 = obs2 / "orchestrator_session_id"
    assert orch_file2.exists()
    assert orch_file2.read_text().strip() == session_id
    assert not (obs2 / "claude_monitor_session_id").exists()
    resolved_orch = pager_mod._read_orchestrator_session_id(orch_root)  # ANTICHEAT_OK: integration read
    assert resolved_orch == session_id


def test_session_start_hook_writes_monitor_id_even_in_pipeline_owned_session(tmp_path):
    """Bridge round-1 DEFECT regression: the dedicated-monitor writer leg must
    NOT be bypassed in pipeline-owned sessions.

    bridge_adapters.py sets RCX_PIPELINE_SESSION=1 for EVERY adapter invocation.
    The orchestrator writer leg is (correctly) suppressed in such SUB-sessions so
    a transient sub-session id never clobbers the live orchestrator_session_id.
    But a DEDICATED monitor (RCX_CLAUDE_MONITOR=1) targets a DISTINCT file and
    MUST still write it even when RCX_PIPELINE_SESSION=1 -- otherwise the pager's
    claude leg has no --resume target and route=both would silently drop every
    Claude leg. This guards the exact interaction the bridge flagged: the early
    RCX_PIPELINE_SESSION guard must defer to the monitor leg. Exercised
    end-to-end against the real hook and the real pager reader.
    """
    repo_root = Path(__file__).resolve().parents[3]
    hook_path = repo_root / ".claude" / "hooks" / "session-start.sh"
    assert hook_path.exists(), f"hook script missing at {hook_path}"

    session_id = "9a1b2c3d-44e5-4f60-8a7b-0c1d2e3f4a5b"
    payload = json.dumps({
        "session_id": session_id,
        "hook_event_name": "SessionStart",
        "source": "startup",
    })

    # (1) RCX_PIPELINE_SESSION=1 AND RCX_CLAUDE_MONITOR=1 -> monitor id STILL
    # written (the fix). Before the fix the early guard exited first and wrote
    # nothing, silently starving the pager's claude --resume target.
    monitor_root = tmp_path / "pipeline_monitor"
    monitor_root.mkdir(parents=True, exist_ok=True)
    env_monitor = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(tmp_path),
        "CLAUDE_PROJECT_DIR": str(monitor_root),
        "RCX_PIPELINE_SESSION": "1",
        "RCX_CLAUDE_MONITOR": "1",
    }
    result = subprocess.run(
        ["bash", str(hook_path)],
        input=payload, env=env_monitor,
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert result.returncode == 0, f"hook exit={result.returncode} stderr={result.stderr!r}"
    obs = monitor_root / ".agent_bus" / "observability"
    monitor_file = obs / "claude_monitor_session_id"
    assert monitor_file.exists(), (
        "dedicated-monitor writer was bypassed in a pipeline-owned session "
        f"(RCX_PIPELINE_SESSION=1); expected {monitor_file} to be written"
    )
    assert monitor_file.read_text().strip() == session_id
    # The dedicated-monitor writer must NEVER touch the live orchestrator file.
    assert not (obs / "orchestrator_session_id").exists()
    resolved = pager_mod._read_claude_monitor_session_id(monitor_root)  # ANTICHEAT_OK: integration read
    assert resolved == session_id

    # (2) RCX_PIPELINE_SESSION=1 WITHOUT the monitor flag -> the orchestrator leg
    # stays suppressed (unchanged): a pipeline SUB-session writes NEITHER file, so
    # it can never clobber the live orchestrator id. Proves the fix is narrow and
    # does not regress the original sub-session suppression.
    sub_root = tmp_path / "pipeline_sub"
    sub_root.mkdir(parents=True, exist_ok=True)
    env_sub = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(tmp_path),
        "CLAUDE_PROJECT_DIR": str(sub_root),
        "RCX_PIPELINE_SESSION": "1",
    }
    result2 = subprocess.run(
        ["bash", str(hook_path)],
        input=payload, env=env_sub,
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert result2.returncode == 0, f"hook exit={result2.returncode} stderr={result2.stderr!r}"
    obs2 = sub_root / ".agent_bus" / "observability"
    assert not (obs2 / "orchestrator_session_id").exists()
    assert not (obs2 / "claude_monitor_session_id").exists()


def test_both_route_claude_leg_enqueues_regardless_of_monitor_state(tmp_path, monkeypatch):
    """The ENQUEUE leg is monitor-independent: it always quick-acks by enqueueing.

    The dedicated monitor session id drives the DELIVERY decision (resume-the-monitor
    vs fresh) inside the receiver, NOT the enqueue leg. With a well-formed, distinct
    dedicated monitor id present, route=both still quick-acks claude by ENQUEUEING to
    the receiver -- no ``--resume`` and no blocking turn at enqueue time -- and leaves
    it pending until the async receipt. The resume-the-monitor delivery itself is
    exercised in test_claude_pager_receiver.py. Codex is unaffected.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="both")
    monkeypatch.setenv("RCX_CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.setattr(pager_mod, "_dispatch_codex", _ack_codex)

    monitor_path = repo / pager_mod.CLAUDE_MONITOR_SESSION_ID_PATH
    monitor_path.parent.mkdir(parents=True, exist_ok=True)
    monitor_path.write_text("sess-monitor-present", encoding="utf-8")
    live_path = repo / pager_mod.ORCHESTRATOR_SESSION_ID_PATH
    live_path.write_text("sess-live-present", encoding="utf-8")

    with patch.object(
        pager_mod.subprocess,
        "run",
        side_effect=AssertionError("claude leg must not spawn a blocking turn / resume"),
    ):
        result = pager_mod.emit_transition_event(repo, **_event_kwargs())
    event_id = result["event_id"]

    entry = _load_state(repo)["events"][event_id]
    assert set(entry["delivered_targets"]) == {"codex"}
    assert entry["pending_targets"] == ["claude"]
    assert entry.get("skipped_targets", {}) == {}
    assert _load_skip_log(repo) == []
    assert _receiver(repo).queued_event_ids() == [event_id]


def test_claude_quick_ack_is_replay_safe_and_legacy_skip_receipt_ignored(tmp_path, monkeypatch):
    """Replay-safety for the Wave-2 claude leg.

    A quick-acked-but-not-yet-delivered claude leg stays pending and writes NO durable
    skip receipt, so a state rebuild via _reconcile_delivery_state leaves it pending --
    never re-parked in skipped_targets. This holds even when a legacy
    CLAUDE_SKIP_REASON_MONITOR_UNSET skip receipt (written by an older fail-closed
    build) already exists on disk: the reconcile guard IGNORES it. And once the
    receiver records its exit-0 receipt, the rebuild promotes claude to delivered.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    repo = repo.resolve()
    _write_config(repo, route="both")
    monkeypatch.setenv("RCX_CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.setattr(pager_mod, "_dispatch_codex", _ack_codex)

    # Emit: codex delivers, claude quick-acks (pending). No blocking turn.
    with patch.object(
        pager_mod.subprocess,
        "run",
        side_effect=AssertionError("claude leg must not spawn a blocking turn"),
    ):
        result = pager_mod.emit_transition_event(repo, **_event_kwargs())
    event_id = result["event_id"]
    assert _load_skip_log(repo) == []
    entry0 = _load_state(repo)["events"][event_id]
    assert "claude" not in entry0.get("skipped_targets", {})
    assert entry0["pending_targets"] == ["claude"]
    assert set(entry0["delivered_targets"]) == {"codex"}

    # Plant a durable legacy UNSET skip receipt exactly as an older build would, then
    # rebuild fresh state. The guard must IGNORE it -> claude stays pending, never
    # re-terminalized. (No receiver receipt yet.)
    skip_path = repo / pager_mod.SKIP_LOG_PATH
    skip_path.parent.mkdir(parents=True, exist_ok=True)
    skip_path.write_text(
        json.dumps({
            "event_id": event_id,
            "target": "claude",
            "skip_reason": pager_mod.CLAUDE_SKIP_REASON_MONITOR_UNSET,
            "recorded_at": "2026-06-01T00:00:01+00:00",
        }) + "\n",
        encoding="utf-8",
    )
    rebuilt = pager_mod._default_state()  # ANTICHEAT_OK: direct pager state reconciliation test
    events = pager_mod._load_events_from_log(repo)  # ANTICHEAT_OK: direct pager state reconciliation test
    pager_mod._reconcile_delivery_state(repo, rebuilt, events)  # ANTICHEAT_OK: direct pager state reconciliation test
    entry1 = rebuilt["events"][event_id]
    assert "claude" not in entry1.get("skipped_targets", {})
    assert set(entry1["delivered_targets"]) == {"codex"}
    assert entry1["pending_targets"] == ["claude"]

    # Now the receiver records its exit-0 receipt: a fresh rebuild promotes claude.
    _plant_receiver_receipt(repo, event_id, transition_key="receipt-1")
    rebuilt2 = pager_mod._default_state()  # ANTICHEAT_OK: direct pager state reconciliation test
    pager_mod._reconcile_delivery_state(repo, rebuilt2, events)  # ANTICHEAT_OK: direct pager state reconciliation test
    entry2 = rebuilt2["events"][event_id]
    assert set(entry2["delivered_targets"]) == {"codex", "claude"}
    assert entry2["pending_targets"] == []
    assert "claude" not in entry2.get("skipped_targets", {})
