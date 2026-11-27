"""Finite native validation execution shared by the existing executors.

No dispatch, retry, review, or successful process-tree release authority lives
here. Normal child exit proves only that child's exit, exactly as in dispatch.
Output completion is separate: children write kernel pipes that only this
runner copies into the durable files, so end-of-file on both streams proves
every holder of them, including a reparented descendant, has closed them.
"""

from __future__ import annotations

import importlib.util
import argparse
import hashlib
import inspect
import json
import os
import selectors
import shlex
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    import executor_common as common
except ImportError:
    from mu.tools.executors import executor_common as common

MAX_WORKERS = 4
XDIST_OPTIONS = frozenset({
    "-n", "--numprocesses", "--maxprocesses", "--max-worker-restart", "--dist",
    "--loadscope-reorder", "--no-loadscope-reorder", "--tx", "--px", "-d",
    "--rsyncdir", "--rsyncignore", "--testrunuid", "--maxschedchunk",
    "-f", "--looponfail",
})
VALIDATION_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
# The code object that actually executed this namespace; see executor_common.
EXECUTED_MODULE_CODE = sys._getframe(0).f_code if hasattr(sys, "_getframe") else None
PROGRESS_SECONDS = 30
# Bounded drain after termination, matching the termination helper's own wait.
OUTPUT_SETTLE_SECONDS = 5
OUTPUT_CHUNK_BYTES = 65536
FAST_PROFILE_MARKER = "not slow and not fuzzer"
COMMIT_SELECTOR_SECONDS = {
    "mu/tests/tools/test_workingrcx_fleet_apply.py": 900,
    "mu/tests/tools/test_worktree_lifecycle.py": 600,
    "mu/tests/tools/test_phase_b_executor.py": 600,
}


def _pytest_options(repo_root: Path, test_files: list[str], env: dict[str, str]):
    """Read pytest's own configuration discovery without loading any test/plugin.

    Pin the discovered file in argv so its bytes join the execution binding.
    Preserve addopts selections; inspect them only for unsupported scheduling.
    """
    from _pytest.config import UsageError
    from _pytest.config.findpaths import determine_setup

    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False, exit_on_error=False)
    parser.add_argument("-c", "--inifile")
    parser.add_argument("-o", "--override-ini", action="append", default=[])
    parser.add_argument("--rootdir")
    try:
        inherited = shlex.split(env.get("PYTEST_ADDOPTS", ""))
        options, _ = parser.parse_known_args(inherited)
        kwargs = dict(inifile=str(repo_root / options.inifile) if options.inifile else None,
                      args=[str(repo_root / path) for path in test_files],
                      rootdir_cmd_arg=str(repo_root / options.rootdir) if options.rootdir else None,
                      invocation_dir=repo_root)
        # pytest 8 and 9 share discovery; 9 also applies overrides here.
        if "override_ini" in inspect.signature(determine_setup).parameters:
            kwargs["override_ini"] = options.override_ini
        _, config_path, config, *_ = determine_setup(**kwargs)
        addopts = config.get("addopts", "")
        addopts = getattr(addopts, "value", addopts)  # pytest 9 carries value provenance.
        for override in options.override_ini:
            if override.startswith("addopts="):
                addopts = override.split("=", 1)[1]
        configured = shlex.split(addopts) if isinstance(addopts, str) else list(addopts)
        return configured + inherited, config_path
    except (ValueError, TypeError, OSError, argparse.ArgumentError, UsageError) as exc:
        raise common.ValidationBudgetError(f"HOLD: malformed pytest configuration: {exc}") from exc


def pytest_timeout(test_files: list[str], *, profile: str, timeout: int) -> int:
    common._budget_positive_int(timeout, "pytest timeout")
    seconds = (max(timeout, sum(COMMIT_SELECTOR_SECONDS.get(path, 240) for path in test_files))
               if profile == "fast" else timeout)
    if seconds > common.VALIDATION_CEILING_SECONDS:
        raise common.ValidationBudgetError("HOLD: pytest schedule exceeds the 7200s validation ceiling")
    return seconds


def pytest_command(test_files: list[str], *, profile: str, workers: int = MAX_WORKERS,
                   env: dict[str, str] | None = None, repo_root: Path | None = None) -> list[str]:
    """Preserve selectors/profiles; change scheduling and complete-suite policy only."""
    if profile not in ("full", "fast"):
        raise common.ValidationBudgetError("HOLD: unknown pytest profile")
    if type(workers) is not int or not 0 <= workers <= MAX_WORKERS:
        raise common.ValidationBudgetError("HOLD: pytest workers must be between zero and four")
    if not test_files or any(type(path) is not str or not path or path.startswith("-") for path in test_files):
        raise common.ValidationBudgetError("HOLD: pytest requires explicit test selectors")
    child_env = os.environ if env is None else env
    inherited, config_path = _pytest_options(Path(repo_root or Path.cwd()).resolve(), test_files, child_env)
    plugins = [inherited[i + 1] for i, arg in enumerate(inherited[:-1]) if arg == "-p"]
    plugins += [arg[2:] for arg in inherited if arg.startswith("-p") and arg != "-p"]
    if workers:
        if (child_env.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD")
                or any(plugin in ("no:xdist", "no:xdist.plugin") for plugin in plugins)
                or importlib.util.find_spec("xdist") is None):
            raise common.ValidationBudgetError("HOLD: requested xdist workers are unavailable/disabled; select serial explicitly")
    elif any(arg.split("=", 1)[0] in XDIST_OPTIONS
             or arg.startswith("-n") for arg in inherited):
        raise common.ValidationBudgetError("HOLD: serial validation inherited xdist-only options")
    command = [sys.executable, "-m", "pytest", "--tb=short", "-p", "no:cacheprovider"]
    if config_path is not None:
        command += ["-c", str(config_path)]
    if profile == "fast":
        command += ["--import-mode=importlib", "-m", FAST_PROFILE_MARKER]
    if workers:
        command += ["-n", str(workers), "--dist", "worksteal", "--max-worker-restart=0"]
    # Last command-line value defeats inherited -x/--exitfirst/--maxfail, including
    # pytest.ini addopts, without discarding inherited selection expressions.
    return command + list(test_files) + ["--maxfail=0"]


class _Interrupted(BaseException):
    def __init__(self, signum: int):
        self.signum = signum


class _OutputCopier:
    """Copy one child's stdout/stderr pipes into the durable files.

    One bounded thread per invocation, started before the child exists, so
    draining never waits on the main thread. It ends at end-of-file on both
    streams, on a read failure, or when the runner stops it. A durable-file
    write failure is recorded while draining continues, so writer closure stays
    observable. The kernel reports end-of-file only after every holder of a
    stream's write end, whatever its ancestry, session or environment, has
    closed it. Only this runner writes the durable files, so no inherited
    writer can change them once hashed.
    """

    def __init__(self, sinks: dict[str, Any]):
        self.writers: list[int] = []
        self.error: OSError | None = None
        self._open: set[str] = set()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._selector = selectors.DefaultSelector()
        try:
            for name, sink in sinks.items():
                reader, writer = os.pipe()
                self.writers.append(writer)
                try:
                    os.set_blocking(reader, False)
                    self._selector.register(reader, selectors.EVENT_READ, (name, sink))
                except BaseException:
                    os.close(reader)
                    raise
                self._open.add(name)
            self._thread = threading.Thread(target=self._copy, name="rcx-validation-output", daemon=True)
            self._thread.start()
        except BaseException as exc:
            self.release_writers()
            self._close_readers()
            if isinstance(exc, (OSError, RuntimeError)):
                # A required execution primitive is unavailable: HOLD before admission.
                raise common.ValidationBudgetError(f"HOLD: validation output capture unavailable: {exc}") from exc
            raise

    def _copy(self) -> None:
        try:
            while not self._stop.is_set() and self._selector.get_map():
                for ready, _ in self._selector.select(0.1):
                    try:
                        chunk = os.read(ready.fd, OUTPUT_CHUNK_BYTES)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        self._selector.unregister(ready.fd)
                        os.close(ready.fd)
                        with self._lock:
                            self._open.discard(ready.data[0])
                    elif self.error is None:
                        try:
                            ready.data[1].write(chunk)
                            ready.data[1].flush()
                        except (OSError, ValueError) as exc:
                            # Output is incomplete, but keep draining so every
                            # writer's closure stays observable.
                            self.error = exc if isinstance(exc, OSError) else OSError(str(exc))
        except OSError as exc:  # Reading failed: closure is no longer observable.
            self.error = self.error or exc

    def _close_readers(self) -> None:
        for registered in list(self._selector.get_map().values()):
            self._selector.unregister(registered.fd)
            os.close(registered.fd)
        self._selector.close()

    def release_writers(self) -> None:
        """Close this runner's write ends; only the child tree may hold them."""
        while self.writers:
            os.close(self.writers.pop())

    def open_streams(self) -> list[str]:
        with self._lock:
            return sorted(self._open)

    def finished(self, seconds: float = 0) -> bool:
        """Wait boundedly; True once copying ended (end-of-file, read failure or stop)."""
        self._thread.join(seconds)
        return not self._thread.is_alive()

    def close(self) -> list[str]:
        """Stop copying and return the streams a writer still held open."""
        self._stop.set()
        if not self.finished(OUTPUT_SETTLE_SECONDS):
            return self.open_streams() or ["stdout", "stderr"]  # The copier itself is stuck.
        unresolved = self.open_streams()
        self._close_readers()
        return unresolved


def run_validation(
    repo_root: Path, command: list[str], *, timeout: int,
    profile: str, key: str, env: dict[str, str] | None = None,
    progress: Callable[[str], None] | None = None,
    log_dir: Path | None = None,
    enclosing_budget: common.NativeStageBudget | None = None,
    reserve_seconds: int = 0,
) -> dict[str, Any]:
    """Run an actual child with durable streams and bounded stage progress.

    Completion requires the leader's exit and end-of-file on both output pipes
    within the same finite allowance: the bounded completion the previous
    callers' captured pipes gave them. A writer still holding an inherited stream
    at that boundary is an ownership HOLD, never success, so no caller restores
    evidence or admits further work while it can still write. On interruption or
    timeout use the landed identity-checked termination helper, then drain
    boundedly. Uncertain cleanup is a HOLD. No group signal, unknown PID signal,
    automatic worker restart, or release receipt manufactured from normal exit
    is allowed.
    """
    repo_root = Path(repo_root).resolve()
    common._budget_positive_int(timeout, "validation timeout")
    if timeout > common.VALIDATION_CEILING_SECONDS:
        raise common.ValidationBudgetError("HOLD: validation exceeds 7200s ceiling")
    common.validation_parent_remaining(repo_root, seconds=timeout, key=key)
    if enclosing_budget is not None:
        enclosing_budget = common.decode_stage_budget(enclosing_budget.encode(), repo_root, env=env)
        if (type(reserve_seconds) is not int or reserve_seconds < 0
                or timeout + reserve_seconds > enclosing_budget.seconds):
            raise common.ValidationBudgetError("HOLD: incoherent sequential validation allocation")
        if enclosing_budget.remaining() <= reserve_seconds:
            raise common.ValidationBudgetError("HOLD: enclosing validation budget exhausted its sequential reserve")
    budget = common.admit_stage_budget(repo_root, key=key, command=command,
                                      baseline=timeout, seconds=timeout,
                                      ceiling=common.VALIDATION_CEILING_SECONDS, env=env)
    owner = uuid.uuid4().hex
    observation = common.observe_executor_processes(owner, cwd=repo_root)
    if not observation.complete:
        raise common.ValidationBudgetError(f"HOLD: process observation unavailable before validation: {observation.error}")
    child_env = dict(os.environ if env is None else env)
    inherited = child_env.get(common.EXECUTOR_PROCESS_OWNER_ENV, "")
    child_env[common.EXECUTOR_PROCESS_OWNER_ENV] = ":".join(filter(None, (inherited, owner)))
    # Test fixtures must not inherit the live invocation's authority. The
    # execution parent has already checked it, and remains its sole owner.
    child_env.pop(common.NATIVE_STAGE_BUDGET_ENV, None)
    child_env.pop(common.VALIDATION_SCHEDULE_ENV, None)
    root = log_dir or Path(os.environ.get("RCX_VALIDATION_LOG_DIR") or
                           common.agent_bus_path(repo_root, os.environ.get("RCX_AGENT_BUS_DIR"), "executors", "validation"))
    root.mkdir(parents=True, exist_ok=True)
    prefix = root / budget.invocation
    stdout_path, stderr_path = Path(str(prefix) + ".stdout"), Path(str(prefix) + ".stderr")
    receipt_path = Path(str(prefix) + ".json")
    report = progress or (lambda message: print(message, file=sys.stderr, flush=True))
    started = datetime.now(timezone.utc).isoformat()
    result: dict[str, Any] = {
        "command": list(command), "profile": profile, "timeout_seconds": timeout,
        "started_at": started, "budget": json.loads(budget.encode()),
        "stdout_path": str(stdout_path), "stderr_path": str(stderr_path),
        "receipt_path": str(receipt_path), "rcx_process_released": False,
        "passed": False, "timed_out": False, "interrupted": False, "output_complete": False,
        **({"enclosing_budget": json.loads(enclosing_budget.encode()),
            "sequential_reserve_seconds": reserve_seconds} if enclosing_budget is not None else {}),
    }
    proc = None
    previous = {}
    pending_signal = None
    copier: _OutputCopier | None = None
    copied = True
    unresolved: list[str] = []
    settle_seconds = OUTPUT_SETTLE_SECONDS

    def interrupted(signum, _frame):
        # Do not raise between Popen creating a child and assigning its handle.
        # The bounded poll below handles the signal with known child identity.
        nonlocal pending_signal
        pending_signal = signum

    def terminate_after_os_error(exc: OSError) -> None:
        if proc is not None and proc.poll() is None:
            evidence = common.terminate_owned_executor(proc, owner, cwd=repo_root)
            result.update(ownership_hold=evidence is None, rcx_process_released=evidence is not None,
                          rcx_process_release_evidence=evidence)
        result.update(exit_code=127 if isinstance(exc, FileNotFoundError) else 126, passed=False,
                      status="execution_error", diagnostic=str(exc))

    try:
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            try:
                if threading.current_thread() is threading.main_thread():
                    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
                    for sig in previous:
                        signal.signal(sig, interrupted)
                report(f"[validation] start profile={profile} budget={timeout}s argv={shlex.join(command)} logs={prefix}")
                receipt_path.write_text(json.dumps({**result, "status": "running"}, indent=2) + "\n")
                # Recheck immutable command/source immediately before actor admission.
                common.decode_stage_budget(budget.encode(), repo_root, key=key, command=command, env=child_env)
                if enclosing_budget is not None:
                    common.decode_stage_budget(enclosing_budget.encode(), repo_root, env=child_env)
                if pending_signal is not None:
                    raise _Interrupted(pending_signal)
                copier = _OutputCopier({"stdout": stdout, "stderr": stderr})
                proc = subprocess.Popen(command, cwd=repo_root, env=child_env, stdout=copier.writers[0],
                                        stderr=copier.writers[1], start_new_session=True)
                copier.release_writers()
                next_progress = time.monotonic() + PROGRESS_SECONDS
                while True:
                    if pending_signal is not None:
                        raise _Interrupted(pending_signal)
                    remaining = budget.remaining()
                    if enclosing_budget is not None:
                        parent_remaining = enclosing_budget.remaining() - reserve_seconds
                        if parent_remaining <= 0:
                            raise common.ValidationBudgetError("HOLD: enclosing validation exhausted its sequential reserve")
                        remaining = min(remaining, parent_remaining)
                    if copier.error is not None:
                        raise copier.error
                    if proc.poll() is None:
                        try:
                            proc.wait(timeout=min(1.0, remaining))
                        except subprocess.TimeoutExpired:
                            pass
                    elif copier.finished(min(1.0, remaining)):
                        if copier.error is not None:
                            raise copier.error
                        if pending_signal is not None:
                            raise _Interrupted(pending_signal)
                        result["exit_code"] = proc.returncode
                        result["status"] = "passed" if proc.returncode == 0 else "failed"
                        result["passed"] = proc.returncode == 0
                        break
                    if time.monotonic() >= next_progress:
                        waiting = ("" if proc.returncode is None else f" leader_exit={proc.returncode}"
                                   " awaiting inherited output=" + ",".join(copier.open_streams()))
                        report(f"[validation] running profile={profile} elapsed={timeout - remaining:.1f}s "
                               f"budget={timeout}s{waiting}")
                        next_progress = time.monotonic() + PROGRESS_SECONDS
            except (common.ValidationBudgetError, _Interrupted, KeyboardInterrupt) as exc:
                interrupted_run = isinstance(exc, (_Interrupted, KeyboardInterrupt))
                if proc is None and not interrupted_run:
                    raise
                leader_exit = proc.poll() if proc is not None else None
                if leader_exit is not None:
                    settle_seconds = 0  # Termination stops nothing; the allowance already waited.
                evidence = common.terminate_owned_executor(proc, owner, cwd=repo_root) if proc is not None else None
                result.update(exit_code=(128 + getattr(exc, "signum", signal.SIGINT)) if interrupted_run else 124,
                              status="interrupted" if interrupted_run else "timeout",
                              interrupted=interrupted_run, timed_out=not interrupted_run,
                              ownership_hold=proc is not None and evidence is None,
                              rcx_process_release_evidence=evidence, rcx_process_released=evidence is not None,
                              diagnostic=(f"{key} interrupted" if interrupted_run else
                                          f"{key} timed out after {timeout}s" if leader_exit is None else
                                          f"{key} leader exited {leader_exit}; inherited output was still open "
                                          "at the validation budget boundary")
                              + f"; boundary: {exc}"
                              + ("; process ownership uncertain: HOLD" if proc is not None and evidence is None else ""))
            except OSError as exc:
                copied = proc is None  # A failure after launch may have lost output.
                terminate_after_os_error(exc)
            except BaseException:
                if proc is not None:
                    common.terminate_owned_executor(proc, owner, cwd=repo_root)
                raise
            finally:
                if copier is not None:
                    copier.release_writers()  # The child never started, or already holds them.
                    copier.finished(settle_seconds)  # Bounded drain after termination.
                    unresolved = copier.close()
                    copied = copied and copier.error is None
    except OSError as exc:  # The exclusive durable files could not be created or closed.
        copied = copied and proc is None
        terminate_after_os_error(exc)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    result["output_complete"] = copied and not unresolved
    if unresolved:
        # No release or attribution is possible for a writer outside the
        # observed tree; it must not race restoration or further admission.
        result.update(passed=False, ownership_hold=True, rcx_process_released=False,
                      rcx_process_release_evidence=None, unresolved_output_streams=unresolved,
                      diagnostic="; ".join(filter(None, (result.get("diagnostic"), "inherited output not proven closed ("
                                                         + ",".join(unresolved) + "): output incomplete: HOLD"))))
    result.update(finished_at=datetime.now(timezone.utc).isoformat(),
                  elapsed_seconds=(time.monotonic_ns() - budget.started_ns) / 1_000_000_000,
                  process_exit_code=proc.returncode if proc is not None else None,
                  stdout=stdout_path.read_text(errors="backslashreplace"),
                  stderr=stderr_path.read_text(errors="backslashreplace"))
    result["stdout_sha256"] = hashlib.sha256(stdout_path.read_bytes()).hexdigest()
    result["stderr_sha256"] = hashlib.sha256(stderr_path.read_bytes()).hexdigest()
    if result.get("diagnostic"):
        result["stderr"] += "\n" + result["diagnostic"]
    receipt_path.write_text(json.dumps(result, indent=2) + "\n")
    report(f"[validation] finish profile={profile} elapsed={result['elapsed_seconds']:.3f}s "
           f"budget={timeout}s exit={result['exit_code']} status={result['status']} "
           f"output_complete={result['output_complete']} receipt={receipt_path}")
    return result


def _profile_deselection_probe(repo_root: Path, test_files: list[str], result: dict[str, Any], *,
                               seconds: int, env: dict[str, str]) -> dict[str, Any]:
    """Attribute a fast-profile exit 5 to the profile marker only with collection proof.

    The existing commit gate accepts a selection whose collected tests the fast
    profile deselects entirely. Under xdist the controller reports ``[0 items]``
    without deselection counts, so output text cannot separate that from zero
    collection. One serial collection-only child with the same selectors, config,
    import mode and environment, minus only the profile marker pair, decides it
    within the remaining finite leaf allowance. Exit 0 proves collected items the
    profile deselected; zero collection, errors and timeouts still fail. Refused
    admission or uncertain ownership is a HOLD. Nothing reruns the selected tests.
    """
    try:
        remaining = int(seconds - result["elapsed_seconds"])
        if remaining < 1:
            raise common.ValidationBudgetError("HOLD: no finite allowance remains for the profile deselection probe")
        serial = pytest_command(test_files, profile="fast", workers=0, env=env, repo_root=repo_root)
        mode = serial.index("--import-mode=importlib")
        if serial[mode + 1:mode + 3] != ["-m", FAST_PROFILE_MARKER]:
            raise common.ValidationBudgetError("HOLD: fast profile marker is not where the native command places it")
        probe_command = [*serial[:3], "--collect-only", "-q", *serial[3:mode + 1], *serial[mode + 3:]]
        probe = run_validation(repo_root, probe_command, timeout=remaining,
                               profile="fast_collection_probe", key="pytest_fast", env=env)
        result["collection_probe"] = probe
        if probe.get("ownership_hold") or probe.get("interrupted"):
            result.update(status="ownership_hold" if probe.get("ownership_hold") else "interrupted",
                          validation_budget_hold=True)
        elif probe["status"] == "passed" and probe["exit_code"] == 0:
            # Keep pytest's truthful exit 5; the selection collected real items.
            result.update(passed=True, status="profile_deselected", profile_deselected=True)
    except common.ValidationBudgetError as exc:
        result.update(status="budget_hold", validation_budget_hold=True, collection_probe_error=str(exc))
        result["stderr"] += ("\n" if result["stderr"] else "") + str(exc)
    Path(result["receipt_path"]).write_text(json.dumps(result, indent=2) + "\n")
    return result


def run_pytest(repo_root: Path, test_files: list[str], *, profile: str,
               timeout: int = 120, workers: int = MAX_WORKERS,
               env: dict[str, str] | None = None) -> dict[str, Any]:
    """Shared native full/fast callers; zero collection and every pytest error fail.

    A fast-profile selection that collects only tests the profile deselects keeps
    the existing commit-gate success, proven by an actual collection child.
    """
    child_env = {**(os.environ if env is None else env), "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"}
    started_at = datetime.now(timezone.utc).isoformat()
    started_ns = time.monotonic_ns()
    command = None
    if profile == "fast":
        child_env.update(RCX_CI="1", HYPOTHESIS_PROFILE="ci_fast")
    try:
        command = pytest_command(test_files, profile=profile, workers=workers, env=child_env, repo_root=repo_root)
        seconds = pytest_timeout(test_files, profile=profile, timeout=timeout)
        result = run_validation(repo_root, command, timeout=seconds, profile=profile,
                                key="pytest_" + profile, env=child_env)
        if result["timed_out"]:
            result["exit_code"] = -1  # Preserve the native pytest caller's timeout status.
        if result.get("ownership_hold") or result.get("interrupted"):
            result["status"] = "ownership_hold" if result.get("ownership_hold") else "interrupted"
            result["validation_budget_hold"] = True
            return result
        if (profile == "fast" and result["exit_code"] == 5 and result["status"] == "failed"
                and not result["stderr"].strip()):
            return _profile_deselection_probe(repo_root, test_files, result, seconds=seconds, env=child_env)
        return result
    except common.ValidationBudgetError as exc:
        root = Path(os.environ.get("RCX_VALIDATION_LOG_DIR") or
                    common.agent_bus_path(repo_root, os.environ.get("RCX_AGENT_BUS_DIR"), "executors", "validation"))
        root.mkdir(parents=True, exist_ok=True)
        receipt = root / (uuid.uuid4().hex + ".json")
        result = dict(passed=False, exit_code=125, stdout="", stderr=str(exc),
                      status="budget_hold", profile=profile, timed_out=False, validation_budget_hold=True,
                      command=command, selected_tests=list(test_files), requested_timeout_seconds=timeout,
                      started_at=started_at, finished_at=datetime.now(timezone.utc).isoformat(),
                      elapsed_seconds=(time.monotonic_ns() - started_ns) / 1_000_000_000,
                      receipt_path=str(receipt), rcx_process_released=False)
        receipt.write_text(json.dumps(result, indent=2) + "\n")
        print(f"[validation] HOLD profile={profile}: {exc}; receipt={receipt}", file=sys.stderr, flush=True)
        return result
