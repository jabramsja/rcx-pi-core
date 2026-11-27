"""Actual native caller execution, scheduling equivalence and refusal controls."""

import hashlib
import json
import os
import shlex
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from mu.tools.executors import executor_common as common
from mu.tools.executors import validation_execution as validation
from tests.repo_root import REPO_ROOT
from mu.tests.tools.test_executor_common import complete_process_observation, fixture_orphan_reaper


def _native(repo, caller, selectors, workers, *, extra_env=None, timeout=60, artifact_dir=None):
    """Fresh interpreter -> actual public native helper -> actual pytest child."""
    junit = (artifact_dir or repo) / f"{caller}-{workers}.xml"
    env = dict(os.environ)
    for key in (common.NATIVE_STAGE_BUDGET_ENV, common.VALIDATION_SCHEDULE_ENV):
        env.pop(key, None)
    # pytest and the native runner both shlex-split PYTEST_ADDOPTS; quote the
    # path so a base temporary directory containing spaces stays one option.
    env.update(PYTEST_ADDOPTS=f"-x --junitxml={shlex.quote(str(junit))}", PYTHONDONTWRITEBYTECODE="1")
    env.update(extra_env or {})
    if artifact_dir is not None:
        # Real-repository probes must retain every child artifact in the fixture.
        env["RCX_VALIDATION_LOG_DIR"] = str(artifact_dir / "validation")
    code = f"""
import sys,json
from pathlib import Path
sys.path[:0]=[{str(REPO_ROOT)!r},{str(REPO_ROOT / 'mu')!r},{str(REPO_ROOT / 'mu/tools/executors')!r}]
from mu.tests.tools.test_executor_common import complete_process_observation
import validation_execution as validation
from {caller} import run_pytest_gate
with complete_process_observation(validation.common) as observations:
    result=run_pytest_gate(Path({str(repo)!r}),{selectors!r},workers={workers},timeout={timeout})
if result.get('receipt_path'):
    Path(result['receipt_path']).with_suffix('.os_observations.json').write_text(json.dumps(observations,indent=2))
print(json.dumps(result))
"""
    child = subprocess.run([sys.executable, "-c", code], env=env, cwd=repo,
                           capture_output=True, text=True, timeout=180)
    assert child.returncode == 0, child.stderr
    result = json.loads(child.stdout.splitlines()[-1])
    identities = []
    if junit.exists():
        identities = sorted((case.attrib["classname"], case.attrib["name"],
                             tuple(node.tag for node in case if node.tag in {"failure", "error", "skipped"}))
                            for case in ET.parse(junit).iter("testcase"))
        if result.get("receipt_path"):
            receipt = Path(result["receipt_path"])
            receipt.with_suffix(".junit.xml").write_bytes(junit.read_bytes())
            receipt.with_suffix(".identities.json").write_text(json.dumps({
                "caller": caller, "workers": workers, "identities": identities,
                "command": result["command"], "exit_code": result["exit_code"],
                "junit_sha256": hashlib.sha256(junit.read_bytes()).hexdigest(),
            }, indent=2))
    return result, identities


# A real descendant inheriting the validation streams. With a delay it writes
# both streams late and exits; without one it holds them until released
# (bounded), then records whether its next write could still reach a reader.
_INHERITED_WRITER = (
    "import json,os,sys,time; from pathlib import Path\n"
    "record, release, delay = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]\n"
    "print('descendant started', flush=True)\n"
    "pending = record.with_suffix('.tmp'); pending.write_text(json.dumps({'pid': os.getpid()})); pending.replace(record)\n"
    "if delay:\n"
    "    time.sleep(float(delay))\n"
    "    print('late descendant stdout', flush=True)\n"
    "    print('late descendant stderr', file=sys.stderr, flush=True)\n"
    "    os._exit(0)\n"
    "deadline = time.monotonic() + 60\n"
    "while not release.exists() and time.monotonic() < deadline:\n"
    "    time.sleep(0.02)\n"
    "try:\n"
    "    print('write after hold', flush=True)\n"
    "    outcome = 'written'\n"
    "except BrokenPipeError:\n"
    "    outcome = 'EPIPE'\n"
    "record.with_name(record.name + '.after').write_text(outcome)\n"
    "os._exit(0)\n"
)


def _writer_argv(record: Path, release: Path, delay: float | None) -> str:
    return (f"[sys.executable, '-c', {_INHERITED_WRITER!r}, {str(record)!r}, {str(release)!r}, "
            f"{str(delay or '')!r}]")


def inherited_writer_leader(record: Path, release: Path, *, delay: float | None) -> list[str]:
    """An actual leader that exits 0 once its stream-inheriting descendant runs."""
    leader = (
        "import subprocess,sys,time; from pathlib import Path\n"
        f"subprocess.Popen({_writer_argv(record, release, delay)})\n"
        "deadline = time.monotonic() + 10\n"
        f"while not Path({str(record)!r}).exists() and time.monotonic() < deadline:\n"
        "    time.sleep(0.01)\n"
        "print('leader exits 0', flush=True)\n"
    )
    return [sys.executable, "-c", leader]


def _leaking_test_module(record: Path, release: Path, *, delay: float | None) -> str:
    """A passing test that leaves a writer on the gate's own, uncaptured streams."""
    return (
        "import subprocess, sys, time\nfrom pathlib import Path\n"
        "def test_leaves_inherited_writer(capfd):\n"
        "    with capfd.disabled():\n"
        f"        subprocess.Popen({_writer_argv(record, release, delay)})\n"
        "    deadline = time.monotonic() + 10\n"
        f"    while not Path({str(record)!r}).exists() and time.monotonic() < deadline:\n"
        "        time.sleep(0.01)\n"
        f"    assert Path({str(record)!r}).exists()\n"
    )


def prove_fixture_descendant_exited(record: Path, seconds: float = 15) -> None:
    """Bounded PID-specific absence proof for a released fixture descendant.

    Never signals it. Under the Linux subreaper only this orphan is reaped; on
    macOS launchd reaps it.
    """
    if not record.exists():
        return
    pid = json.loads(record.read_text())["pid"]
    deadline = time.monotonic() + seconds
    while True:
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        assert time.monotonic() < deadline, f"fixture descendant {pid} remained after release"
        time.sleep(0.02)


@pytest.mark.parametrize("caller", ["phase_b_executor", "commit_executor"])
@pytest.mark.parametrize("failing", [False, True])
def test_actual_callers_preserve_every_identity_and_failure(tmp_path, caller, failing):
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts = --exitfirst\n")
    (tmp_path / "test_jobs.py").write_text(
        "import pytest\n@pytest.mark.parametrize('i',range(8))\n"
        f"def test_job(i):\n    assert not ({failing!r} and i in (0,5))\n"
    )
    serial, serial_ids = _native(tmp_path, caller, ["test_jobs.py"], 0)
    parallel, parallel_ids = _native(tmp_path, caller, ["test_jobs.py"], 4)
    assert serial_ids == parallel_ids
    assert len(serial_ids) == 8  # Inherited exitfirst must not truncate the suite.
    for result in (serial, parallel):
        assert result["exit_code"] == (1 if failing else 0), result
        assert result["passed"] is (not failing)
        assert result["rcx_process_released"] is False
        assert Path(result["stdout_path"]).read_text() == result["stdout"]
        assert Path(result["receipt_path"]).is_file()
    assert "--max-worker-restart=0" in parallel["command"]
    assert "--dist" not in serial["command"] and "-n" not in serial["command"]


@pytest.mark.parametrize("caller", ["phase_b_executor", "commit_executor"])
def test_native_fixture_junit_path_survives_space_in_base_temp(tmp_path, caller):
    """A base temporary directory containing spaces keeps every JUnit identity."""
    base = tmp_path / "base temp with spaces"
    base.mkdir()
    (base / "test_jobs.py").write_text(
        "import pytest\n@pytest.mark.parametrize('i',range(3))\ndef test_job(i):\n    assert i >= 0\n"
    )
    serial, serial_ids = _native(base, caller, ["test_jobs.py"], 0)
    parallel, parallel_ids = _native(base, caller, ["test_jobs.py"], 4)
    for workers, result in ((0, serial), (4, parallel)):
        assert result["passed"] and result["exit_code"] == 0, result
        assert (base / f"{caller}-{workers}.xml").is_file()
        assert result["command"][-2:] == ["test_jobs.py", "--maxfail=0"]
    assert serial_ids == parallel_ids and len(serial_ids) == 3


def test_actual_native_fixture_benchmark(tmp_path):
    (tmp_path / "test_jobs.py").write_text(
        "import time,pytest\n@pytest.mark.parametrize('i',range(8))\n"
        "def test_independent_job(i):\n    time.sleep(1.5)\n    assert i >= 0\n"
    )
    serial, before = _native(tmp_path, "phase_b_executor", ["test_jobs.py"], 0)
    parallel, after = _native(tmp_path, "phase_b_executor", ["test_jobs.py"], 4)
    assert serial["passed"] and parallel["passed"], (serial, parallel)
    assert before == after and len(after) == 8
    assert parallel["elapsed_seconds"] < serial["elapsed_seconds"] * 0.8, (serial, parallel)
    measurement = {"serial": serial["elapsed_seconds"], "parallel": parallel["elapsed_seconds"],
                   "speedup": serial["elapsed_seconds"] / parallel["elapsed_seconds"],
                   "identities": before, "serial_receipt": serial["receipt_path"],
                   "parallel_receipt": parallel["receipt_path"]}
    Path(parallel["receipt_path"]).with_suffix(".benchmark.json").write_text(json.dumps(measurement, indent=2))


def test_real_repository_module_through_native_schedules(tmp_path):
    selector = ["mu/tests/tools/test_executor_config_alignment.py"]
    serial, before = _native(REPO_ROOT, "phase_b_executor", selector, 0, artifact_dir=tmp_path)
    parallel, after = _native(REPO_ROOT, "phase_b_executor", selector, 4, artifact_dir=tmp_path)
    assert serial["passed"] and parallel["passed"], (serial, parallel)
    assert before == after and len(after) > 10
    for result in (serial, parallel):
        receipt = Path(result["receipt_path"])
        for key in ("receipt_path", "stdout_path", "stderr_path"):
            assert Path(result[key]).parent == tmp_path / "validation"
            assert Path(result[key]).is_file()
        for suffix in (".os_observations.json", ".junit.xml", ".identities.json"):
            assert receipt.with_suffix(suffix).is_file()


def test_native_validation_logs_follow_active_bus(tmp_path, monkeypatch):
    monkeypatch.delenv("RCX_VALIDATION_LOG_DIR", raising=False)
    monkeypatch.setenv("RCX_AGENT_BUS_DIR", ".agent_bus-validation-control")
    (tmp_path / "test_leaf.py").write_text("def test_leaf(): assert True\n")
    result, identities = _native(tmp_path, "phase_b_executor", ["test_leaf.py"], 0)
    assert result["passed"] and len(identities) == 1, result
    assert Path(result["receipt_path"]).parent == tmp_path / ".agent_bus-validation-control/executors/validation"
    assert not (tmp_path / ".agent_bus/executors/validation").exists()


@pytest.mark.parametrize("addopts,workers", [
    ("-n 8", 0), ("-p no:xdist", 4), ("--maxprocesses 8", 0),
    ("--testrunuid fixture", 0), ("--rsyncignore ignored", 0),
])
def test_pytest_config_cannot_override_native_worker_policy(tmp_path, addopts, workers):
    marker = tmp_path / "collected"
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts = " + addopts + "\n")
    (tmp_path / "test_jobs.py").write_text(
        f"from pathlib import Path; Path({str(marker)!r}).touch()\ndef test_job(): pass\n")
    result, _ = _native(tmp_path, "phase_b_executor", ["test_jobs.py"], workers)
    assert result["exit_code"] == 125 and not result["passed"]
    assert result["validation_budget_hold"] and not marker.exists()


@pytest.mark.parametrize("caller", ["phase_b_executor", "commit_executor"])
def test_profiles_and_zero_collection_are_truthful(tmp_path, caller):
    (tmp_path / "pytest.ini").write_text("[pytest]\nmarkers =\n slow: slow\n fuzzer: fuzzer\n")
    (tmp_path / "test_profiles.py").write_text(
        "import pytest\ndef test_fast(): pass\n@pytest.mark.slow\ndef test_slow(): pass\n"
    )
    result, identities = _native(tmp_path, caller, ["test_profiles.py"], 0)
    assert result["passed"], result
    assert len(identities) == (2 if caller == "phase_b_executor" else 1)
    (tmp_path / "test_empty.py").write_text("value = 1\n")
    result, _ = _native(tmp_path, caller, ["test_empty.py"], 0)
    assert result["exit_code"] == 5 and not result["passed"]


@pytest.mark.parametrize("caller", ["phase_b_executor", "commit_executor"])
def test_empty_selection_starts_no_process_through_actual_callers(tmp_path, monkeypatch, caller):
    """The existing gate contract survives; the shared runner itself stays strict."""
    module = __import__(f"mu.tools.executors.{caller}", fromlist=["run_pytest_gate"])
    def refuse(*args, **kwargs):
        raise AssertionError("empty selection started a process")
    monkeypatch.setattr(validation.subprocess, "Popen", refuse)
    expected = {"exit_code": 0, "stdout": "", "stderr": "", "passed": True}
    assert module.run_pytest_gate(tmp_path, []) == expected
    assert module._run_pytest_on_files(tmp_path, []) == expected  # ANTICHEAT_OK: existing empty-selection contract of both native gates.
    refused = validation.run_pytest(tmp_path, [], profile="fast" if caller == "commit_executor" else "full")
    assert refused["validation_budget_hold"] and refused["exit_code"] == 125 and not refused["passed"]
    assert "explicit test selectors" in refused["stderr"]


def test_profile_deselection_probe_holds_on_uncertain_observation(tmp_path):
    """Main-run evidence survives; an unobservable probe cannot mint success."""
    (tmp_path / "test_slow.py").write_text("import pytest\n@pytest.mark.slow\ndef test_slow(): assert False\n")
    original_observer = validation.common.observe_executor_processes
    calls = []
    # Restore the injected fault before the enclosing real-observation fixture.
    with complete_process_observation(validation.common), pytest.MonkeyPatch.context() as monkeypatch:
        real = validation.common.observe_executor_processes
        def observed(owner, **kwargs):
            calls.append(owner)
            if len(calls) == 1:
                return real(owner, **kwargs)
            return validation.common.ExecutorProcessObservation(False, {}, {}, "fixture probe uncertainty")
        monkeypatch.setattr(validation.common, "observe_executor_processes", observed)
        result = validation.run_pytest(tmp_path, ["test_slow.py"], profile="fast", workers=0)
    assert validation.common.observe_executor_processes is original_observer
    assert len(calls) == 2  # One main admission, one refused probe admission.
    assert result["exit_code"] == 5 and not result["passed"]
    assert result["status"] == "budget_hold" and result["validation_budget_hold"] is True
    assert "fixture probe uncertainty" in result["collection_probe_error"]
    assert "fixture probe uncertainty" in result["stderr"] and "collection_probe" not in result
    assert Path(result["stdout_path"]).read_text() == result["stdout"]
    assert json.loads(Path(result["receipt_path"]).read_text()) == result
    assert common.validation_hold_result(result, step="fixture") is not None


def test_full_profile_zero_collection_is_never_probed(tmp_path):
    (tmp_path / "test_empty.py").write_text("value = 1\n")
    result, _ = _native(tmp_path, "phase_b_executor", ["test_empty.py"], 4)
    assert result["exit_code"] == 5 and not result["passed"] and result["status"] == "failed"
    assert "collection_probe" not in result and "profile_deselected" not in result


@pytest.mark.parametrize("extra", [{"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}, {"PYTEST_ADDOPTS": "-p no:xdist"}])
def test_worker_unavailable_refuses_before_fixture_runs(tmp_path, extra):
    marker = tmp_path / "executed"
    (tmp_path / "test_jobs.py").write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\ndef test_x(): pass\n")
    result, _ = _native(tmp_path, "phase_b_executor", ["test_jobs.py"], 4, extra_env=extra)
    assert not result["passed"] and result["exit_code"] == 125
    assert not marker.exists()
    if "PYTEST_DISABLE_PLUGIN_AUTOLOAD" in extra:
        serial, _ = _native(tmp_path, "phase_b_executor", ["test_jobs.py"], 0, extra_env=extra)
        assert serial["passed"], serial


def test_crashed_worker_never_restarts_into_green(tmp_path):
    (tmp_path / "test_crash.py").write_text("import os\ndef test_crash(): os._exit(9)\ndef test_other(): pass\n")
    result, _ = _native(tmp_path, "phase_b_executor", ["test_crash.py"], 4)
    assert not result["passed"] and result["exit_code"] != 0
    assert "--max-worker-restart=0" in result["command"]


def test_actual_timeout_preserves_both_streams(tmp_path):
    with complete_process_observation(validation.common):
        result = validation.run_validation(tmp_path, [sys.executable, "-u", "-c",
            "import time,sys; print('before timeout'); print('diagnostic',file=sys.stderr); time.sleep(30)"],
            timeout=1, profile="fixture", key="meta_validation")
    assert result["timed_out"] and result["exit_code"] == 124 and not result["passed"]
    assert "before timeout" in result["stdout"] and "diagnostic" in result["stderr"]
    assert "timed out" in result["stderr"]
    assert Path(result["stdout_path"]).read_text() == result["stdout"]
    # Available snapshot evidence is not unsampled lifetime attribution.
    assert result["rcx_process_released"] is (result["rcx_process_release_evidence"] is not None)


def test_actual_interruption_preserves_output_and_parent_signal(tmp_path):
    ready = tmp_path / "ready"
    code = f"""
import sys,json
from pathlib import Path
sys.path[:0]=[{str(REPO_ROOT)!r},{str(REPO_ROOT / 'mu')!r},{str(REPO_ROOT / 'mu/tools/executors')!r}]
from mu.tests.tools.test_executor_common import complete_process_observation
import validation_execution as validation
from validation_execution import run_validation
with complete_process_observation(validation.common):
 r=run_validation(Path({str(tmp_path)!r}), [sys.executable,'-u','-c',
    "import time; from pathlib import Path; print('before interruption'); Path({str(ready)!r}).touch(); time.sleep(30)"],
    timeout=30,profile='fixture',key='meta_validation')
print(json.dumps(r))
"""
    child = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 15
        while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready.exists()
        child.send_signal(signal.SIGTERM)
        stdout, stderr = child.communicate(timeout=15)
        assert child.returncode == 0, stderr
        result = json.loads(stdout)
        assert result["interrupted"] and result["exit_code"] == 143 and not result["passed"]
        assert "before interruption" in result["stdout"]
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def test_normal_leader_exit_waits_for_delayed_inherited_output_descendant(tmp_path):
    """Leader exit is not completion: a descendant still writing the inherited
    streams finishes within the same allowance before success or hashing."""
    record, release = tmp_path / "descendant.json", tmp_path / "release"
    with fixture_orphan_reaper(), complete_process_observation(validation.common):
        try:
            result = validation.run_validation(
                tmp_path, inherited_writer_leader(record, release, delay=2), timeout=60,
                profile="fixture", key="meta_validation")
        finally:
            release.touch()
            prove_fixture_descendant_exited(record)
    assert result["passed"] and result["status"] == "passed" and result["exit_code"] == 0, result
    assert result["output_complete"] is True and not result.get("ownership_hold")
    assert result["elapsed_seconds"] >= 2, result  # Waited past the leader's own exit.
    assert result["stdout"].splitlines() == ["descendant started", "leader exits 0", "late descendant stdout"]
    assert result["stderr"] == "late descendant stderr\n"
    for stream in ("stdout", "stderr"):
        raw = Path(result[f"{stream}_path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == result[f"{stream}_sha256"]
    assert result["rcx_process_released"] is False  # Normal exit is still not release evidence.
    assert json.loads(Path(result["receipt_path"]).read_text()) == result


def test_unresolved_inherited_writer_is_an_ownership_hold(tmp_path):
    """A writer still holding inherited streams at the boundary is a structured
    HOLD: never success, nothing is signaled, and the recorded hashes stay final."""
    record, release = tmp_path / "descendant.json", tmp_path / "release"
    with fixture_orphan_reaper(), complete_process_observation(validation.common):
        try:
            result = validation.run_validation(
                tmp_path, inherited_writer_leader(record, release, delay=None), timeout=5,
                profile="fixture", key="meta_validation")
            assert not record.with_name(record.name + ".after").exists()  # Alive and unreleased at the HOLD.
        finally:
            release.touch()
            prove_fixture_descendant_exited(record)
    # The writer outlived the run; its next write found no reader and changed nothing.
    assert record.with_name(record.name + ".after").read_text() == "EPIPE"
    assert not result["passed"] and result["status"] == "timeout" and result["exit_code"] == 124, result
    assert result["process_exit_code"] == 0 and result["timed_out"] and not result["interrupted"]
    assert result["ownership_hold"] is True and result["output_complete"] is False
    assert result["unresolved_output_streams"] == ["stderr", "stdout"]
    assert result["rcx_process_released"] is False and result["rcx_process_release_evidence"] is None
    assert "leader exited 0" in result["diagnostic"] and "output incomplete: HOLD" in result["stderr"]
    assert result["stdout"].splitlines() == ["descendant started", "leader exits 0"]
    for stream in ("stdout", "stderr"):
        raw = Path(result[f"{stream}_path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == result[f"{stream}_sha256"]
    assert json.loads(Path(result["receipt_path"]).read_text()) == result


def test_timeout_termination_drains_owned_descendant_output(tmp_path):
    """Terminating a live owned tree drains its inherited streams to end-of-file:
    an ordinary timeout, never an output HOLD manufactured by the drain."""
    descendant = "import time; print('owned descendant', flush=True); time.sleep(30)"
    leader = (f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{descendant!r}]); "
              "print('leader running', flush=True); time.sleep(30)")
    with complete_process_observation(validation.common):
        result = validation.run_validation(tmp_path, [sys.executable, "-c", leader], timeout=5,
                                           profile="fixture", key="meta_validation")
    assert result["timed_out"] and result["exit_code"] == 124 and not result["passed"], result
    assert result["output_complete"] is True and "unresolved_output_streams" not in result
    assert {"owned descendant", "leader running"} <= set(result["stdout"].splitlines())
    assert "timed out after 5s" in result["diagnostic"]
    # Release itself keeps its landed evidence semantics.
    assert result["ownership_hold"] is (result["rcx_process_release_evidence"] is None)
    assert result["rcx_process_released"] is (result["rcx_process_release_evidence"] is not None)


def _durable_stdout_fault(monkeypatch, fail_on: str) -> None:
    """Inject an OS failure into the runner's durable stdout file only.

    The child stays real; only the parent's write or close of that one file fails.
    """
    real_open = Path.open

    class FailingSink:
        def __init__(self, real):
            self.real = real

        def write(self, data):
            if fail_on == "write":
                raise OSError(28, "fixture: no space left on device")
            return self.real.write(data)

        def flush(self):
            return self.real.flush()

        def close(self):
            self.real.close()
            if fail_on == "close":
                raise OSError(5, "fixture: close failed")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.close()
            return False

    def faulty_open(path, mode="r", *args, **kwargs):
        handle = real_open(path, mode, *args, **kwargs)
        return FailingSink(handle) if mode == "xb" and path.name.endswith(".stdout") else handle

    monkeypatch.setattr(Path, "open", faulty_open)


def test_output_copy_failure_is_an_ordinary_failure_not_success(tmp_path, monkeypatch):
    """A durable-file write failure loses output and fails the run, but writer
    closure stays observable, so a released tree is not turned into a HOLD."""
    _durable_stdout_fault(monkeypatch, "write")
    with complete_process_observation(validation.common):
        result = validation.run_validation(tmp_path, [sys.executable, "-u", "-c",
            "import time; print('lost output'); time.sleep(30)"], timeout=30,
            profile="fixture", key="meta_validation")
    assert not result["passed"] and result["status"] == "execution_error" and result["exit_code"] == 126, result
    assert "no space left on device" in result["diagnostic"]
    assert result["output_complete"] is False and "unresolved_output_streams" not in result
    assert result["ownership_hold"] is (result["rcx_process_release_evidence"] is None)
    assert result["elapsed_seconds"] < 25  # Failed promptly; never waited out the allowance.


def test_durable_file_close_failure_after_completion_never_passes(tmp_path, monkeypatch):
    """Even after a successful child, an unconfirmed durable record is never success."""
    _durable_stdout_fault(monkeypatch, "close")
    with complete_process_observation(validation.common):
        result = validation.run_validation(tmp_path, [sys.executable, "-c", "print('complete')"],
                                           timeout=30, profile="fixture", key="meta_validation")
    assert result["process_exit_code"] == 0, result
    assert not result["passed"] and result["status"] == "execution_error" and result["exit_code"] == 126, result
    assert result["output_complete"] is False and "close failed" in result["diagnostic"]


@pytest.mark.parametrize("caller,workers,stream", [("phase_b_executor", 0, "stdout"),
                                                   ("commit_executor", 4, "stderr")])
def test_actual_callers_wait_for_writer_leaked_by_a_test(tmp_path, caller, workers, stream):
    """Both native gates finish only once a writer a test left on the gate's
    streams closes them; xdist workers retain only the controller's stderr."""
    record, release = tmp_path / "descendant.json", tmp_path / "release"
    (tmp_path / "test_writer.py").write_text(_leaking_test_module(record, release, delay=2))
    with fixture_orphan_reaper():
        try:
            result, identities = _native(tmp_path, caller, ["test_writer.py"], workers)
        finally:
            release.touch()
            prove_fixture_descendant_exited(record)
    assert result["passed"] and result["exit_code"] == 0 and result["output_complete"] is True, result
    assert len(identities) == 1
    assert f"late descendant {stream}" in result[stream]


def test_actual_phase_b_caller_holds_on_writer_leaked_by_a_test(tmp_path):
    """The final-gate caller turns an unresolved leaked writer into a transported
    HOLD even though every selected test passed and pytest exited normally."""
    record, release = tmp_path / "descendant.json", tmp_path / "release"
    (tmp_path / "test_writer.py").write_text(_leaking_test_module(record, release, delay=None))
    with fixture_orphan_reaper():
        try:
            result, identities = _native(tmp_path, "phase_b_executor", ["test_writer.py"], 0, timeout=10)
        finally:
            release.touch()
            prove_fixture_descendant_exited(record)
    assert [outcome for *_, outcome in identities] == [()]  # The leaking test itself passed.
    assert not result["passed"] and result["process_exit_code"] == 0, result
    assert result["ownership_hold"] is True and result["output_complete"] is False
    assert result["status"] == "ownership_hold" and result["validation_budget_hold"] is True
    hold = common.validation_hold_result(result, step="final_pytest_gate")
    assert hold is not None and hold["error_code"] == "VALIDATION_BUDGET_HOLD"


def test_source_bound_budget_roundtrip_and_drift(tmp_path):
    command = [sys.executable, "-c", "print('budget')"]
    budget = common.admit_stage_budget(tmp_path, key="meta_validation", command=command,
                                      baseline=5, seconds=5, ceiling=5)
    script = (f"import sys;sys.path.insert(0,{str(REPO_ROOT / 'mu/tools/executors')!r});"
              "from executor_common import decode_stage_budget;from pathlib import Path;"
              f"b=decode_stage_budget({budget.encode()!r},Path({str(tmp_path)!r}),key='meta_validation',command={command!r});"
              "print(b.remaining())")
    child = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=10)
    assert child.returncode == 0, child.stderr
    assert 0 < float(child.stdout) < 5
    config = tmp_path / "mu/tools/executors/executor_config.json"
    config.parent.mkdir(parents=True)
    config.write_text("{}")
    with pytest.raises(common.ValidationBudgetError, match="source drift"):
        common.decode_stage_budget(budget.encode(), tmp_path)


@pytest.mark.parametrize("mutation", ["unknown", "boolean", "over-cap", "command", "expired", "duplicate"])
def test_budget_refuses_invalid_transport(tmp_path, mutation):
    budget = common.admit_stage_budget(tmp_path, key="pytest_full", command=["python3", "-m", "pytest"],
                                      baseline=10, seconds=10, ceiling=10)
    value = json.loads(budget.encode())
    if mutation == "unknown": value["extra"] = 1
    if mutation == "boolean": value["seconds"] = True
    if mutation == "over-cap": value["seconds"] = 11
    if mutation == "command": value["command"] = ["another"]
    if mutation == "expired": value["started_ns"] -= 20_000_000_000
    raw = json.dumps(value)
    if mutation == "duplicate": raw = raw[:-1] + ', "seconds":10}'
    with pytest.raises(common.ValidationBudgetError):
        common.decode_stage_budget(raw, tmp_path, key="pytest_full", command=list(budget.command))


def test_sequential_budget_conflict_refuses_before_child(tmp_path, monkeypatch):
    marker = tmp_path / "executed"
    with pytest.raises(common.ValidationBudgetError, match="requires 7s"):
        common.admit_stage_budget(tmp_path, key="phase_b_executor", command=["python3"],
                                  baseline=5, seconds=5, ceiling=10,
                                  allocations=(("pytest_full", 4), ("review", 3)))
    budget = common.admit_stage_budget(tmp_path, key="phase_b_executor", command=["python3"],
                                      baseline=3, seconds=3, ceiling=3,
                                      allocations=(("meta_validation", 2), ("review", 1)))
    monkeypatch.setenv(common.NATIVE_STAGE_BUDGET_ENV, budget.encode())
    with pytest.raises(validation.common.ValidationBudgetError, match="sequential reserve"):
        validation.run_validation(tmp_path, [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"],
                                  timeout=2, profile="fixture", key="meta_validation")
    assert not marker.exists()


def test_contended_stage_admission_holds_without_minting_clock(tmp_path):
    rows = common.validation_schedule_requirements(tmp_path, 1200)
    request = {"validation_seconds": 1200,
               **{key: sum(seconds for _, seconds in items) for key, items in rows.items()}}
    raw = common.retain_validation_schedule(tmp_path, request,
        wave_id="lock-control", evidence_command="true")
    schedule = common.read_validation_schedule_transport(tmp_path, raw)
    ledger = tmp_path / ".agent_bus/executors/validation/lock-control.schedule.admissions.json"
    before = ledger.read_bytes()
    ready = tmp_path / "locked"
    locker = subprocess.Popen([sys.executable, "-c",
        "import fcntl,sys,time;from pathlib import Path;"
        "handle=open(sys.argv[1],'r+');fcntl.flock(handle,fcntl.LOCK_EX);"
        "Path(sys.argv[2]).touch();time.sleep(30)", str(ledger), str(ready)])
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and locker.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready.exists(), "fixture did not acquire the admission lock"
        code = f'''
import sys
from pathlib import Path
sys.path.insert(0,{str(REPO_ROOT / 'mu/tools/executors')!r})
import executor_common as common
try:
    common.retain_native_stage_budget(Path({str(tmp_path)!r}),{schedule!r},
        command=[sys.executable,'-c','pass'],key='phase_b_executor',
        baseline={common.DEFAULT_EXECUTOR_CONFIG['timeouts']['phase_b_executor']},
        seconds={request['phase_b_executor']},ceiling={request['phase_b_executor']},
        allocations={rows['phase_b_executor']!r})
except common.ValidationBudgetError as exc:
    print(str(exc))
    raise SystemExit(125)
'''
        refused = subprocess.run([sys.executable, "-c", code],
            capture_output=True, text=True, timeout=5)
        assert refused.returncode == 125, refused.stderr
        assert "already locked" in refused.stdout
        assert ledger.read_bytes() == before
        budget = ledger.parent / f"{schedule['invocation']}.phase_b_executor.budget.json"
        assert not budget.exists() and not budget.with_suffix(".admitted.json").exists()
    finally:
        locker.terminate()
        locker.wait(timeout=5)


@pytest.mark.parametrize("caller,key,leaf", [("phase_b_executor", "pytest_full", 7200),
                                            ("commit_executor", "pytest_fast", 240)])
def test_small_evidence_allowance_preserves_native_pytest_leaf(tmp_path, caller, key, leaf):
    """A one-second evidence request must not silently shrink another leaf key."""
    (tmp_path / "test_leaf.py").write_text("def test_actual_leaf(): assert True\n")
    code = f"""
import sys,os,json
from pathlib import Path
sys.path[:0]=[{str(REPO_ROOT)!r},{str(REPO_ROOT / 'mu')!r},{str(REPO_ROOT / 'mu/tools/executors')!r}]
from mu.tests.tools.test_executor_common import complete_process_observation
import validation_execution as validation
import executor_common as common
from {caller} import run_pytest_gate
repo=Path({str(tmp_path)!r})
rows=common.validation_schedule_requirements(repo,1)[{caller!r}]
budget=common.admit_stage_budget(repo,key={caller!r},command=[sys.executable,'fixture'],
    baseline={18000 if caller == 'phase_b_executor' else 3600},seconds=sum(v for _,v in rows),
    ceiling=sum(v for _,v in rows),allocations=rows)
os.environ[common.NATIVE_STAGE_BUDGET_ENV]=budget.encode()
with complete_process_observation(validation.common):
 result=run_pytest_gate(repo,['test_leaf.py'],timeout={leaf},workers=0)
print(json.dumps({{'result':result,'allocations':dict(rows)}}))
"""
    env = os.environ.copy()
    env.pop(common.NATIVE_STAGE_BUDGET_ENV, None)
    env.pop(common.VALIDATION_SCHEDULE_ENV, None)
    child = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=30)
    assert child.returncode == 0, child.stderr
    outcome = json.loads(child.stdout)
    assert outcome["result"]["passed"], outcome
    assert outcome["result"]["timeout_seconds"] == leaf
    assert outcome["allocations"][key] == 7200
    assert outcome["allocations"]["meta_validation"] == 1


@pytest.mark.parametrize("diagnostic", [
    "changed identity", "process ancestry changed between observations",
])
def test_uncertain_observation_refuses_before_actor(tmp_path, monkeypatch, diagnostic):
    marker = tmp_path / "executed"
    monkeypatch.setattr(validation.common, "observe_executor_processes", lambda *a, **kw:
                        validation.common.ExecutorProcessObservation(False, {}, {}, diagnostic))
    with pytest.raises(validation.common.ValidationBudgetError, match=diagnostic):
        validation.run_validation(tmp_path, [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"],
                                  timeout=2, profile="fixture", key="meta_validation")
    assert not marker.exists()


def test_pytest_ancestry_hold_preserves_diagnostic_without_child(tmp_path, monkeypatch):
    marker = tmp_path / "collected"
    (tmp_path / "test_leaf.py").write_text(
        f"from pathlib import Path; Path({str(marker)!r}).touch()\ndef test_leaf(): pass\n"
    )
    diagnostic = "process ancestry changed between observations"
    monkeypatch.setattr(validation.common, "observe_executor_processes", lambda *a, **kw:
                        validation.common.ExecutorProcessObservation(False, {}, {}, diagnostic))
    result = validation.run_pytest(tmp_path, ["test_leaf.py"], profile="fast", workers=0)
    assert result["exit_code"] == 125 and not result["passed"]
    assert result["validation_budget_hold"] and not result["rcx_process_released"]
    assert diagnostic in result["stderr"]
    assert json.loads(Path(result["receipt_path"]).read_text()) == result
    assert not marker.exists()


@pytest.mark.parametrize("fault", ["uncertain", "changed_identity"])
def test_actual_child_timeout_refuses_uncertain_release(tmp_path, fault):
    original_observer = validation.common.observe_executor_processes
    # Restore the injected fault before the enclosing real-observation fixture.
    # Reversing teardown resurrects its cached wrapper in subsequent tests.
    with complete_process_observation(validation.common), pytest.MonkeyPatch.context() as monkeypatch:
        observe = validation.common.observe_executor_processes
        count = 0
        def observed(owner, **kwargs):
            nonlocal count
            count += 1
            result = observe(owner, **kwargs)
            if count == 2:
                if fault == "uncertain":
                    return validation.common.ExecutorProcessObservation(False, {}, {}, "fixture query failed")
                identities = dict(result.identities)
                for pid, identity in identities.items():
                    if identity.owned:
                        identities[pid] = validation.common.ExecutorProcessIdentity(
                            pid=identity.pid,
                            ppid=identity.ppid,
                            started="Wed Jan 01 00:00:00 2020",
                            owned=identity.owned,
                        )
                return validation.common.ExecutorProcessObservation(
                    complete=result.complete,
                    parents=result.parents,
                    identities=identities,
                    error=result.error,
                )
            return result
        monkeypatch.setattr(validation.common, "observe_executor_processes", observed)
        result = validation.run_validation(tmp_path, [sys.executable, "-u", "-c",
            "import time; print('actual child reached'); time.sleep(30)"], timeout=1,
            profile="fixture", key="meta_validation")
        assert result["timed_out"] and not result["passed"]
        assert "actual child reached" in result["stdout"]
        assert result["ownership_hold"] and not result["rcx_process_released"]
        assert result["rcx_process_release_evidence"] is None
    assert validation.common.observe_executor_processes is original_observer
