"""Repo-root pytest fixtures shared across mirrored test trees."""

from __future__ import annotations

import gc
import hashlib
import os
import shlex
import subprocess
import tempfile
from types import ModuleType
from pathlib import Path
from unittest.mock import patch

import pytest

try:
    import fcntl as _fcntl
except ImportError:  # non-POSIX (e.g. Windows); the node serializer no-ops.
    _fcntl = None    # CI/dev targets are POSIX (Linux nightly + macOS dev).


@pytest.fixture
def mock_routing_record():
    """Fallback routing-record fixture for mirrored dispatcher suites.

    The commit gate can run both ``mu/tests/.../test_executor_dispatch.py`` and
    ``tests/.../test_executor_dispatch.py`` in one pytest invocation. A repo-root
    fixture keeps the shared ``mock_routing_record`` stub available even when
    pytest's mirrored collection path does not honor the per-module fixture
    definition on one of those duplicate-basename files.
    """
    repo_root = Path(__file__).resolve().parent
    phase_b_path = repo_root / "mu" / "tools" / "executors" / "phase_b_executor.py"
    targets: list[ModuleType] = []

    for obj in gc.get_objects():
        if not isinstance(obj, ModuleType):
            continue
        if getattr(obj, "__file__", None) != str(phase_b_path):
            continue
        if hasattr(obj, "load_routing_record"):
            targets.append(obj)

    if not targets:
        from mu.tests.tools.module_loader import load_module

        targets.append(load_module("phase_b_executor", phase_b_path))

    patchers = [
        patch.object(
            mod,
            "load_routing_record",
            return_value={"decision": "ROUTE_PHASE_B", "summary": "test dispatch"},
        )
        for mod in targets
    ]
    for patcher in patchers:
        patcher.start()
    try:
        yield
    finally:
        for patcher in reversed(patchers):
            patcher.stop()


# =============================================================================
# Cross-worker node-subprocess serializer
# (wave: parity-node-subprocess-load-2026-07-02)
# =============================================================================
# Cross-substrate parity tests spawn a CPU-heavy ``node`` subprocess whose
# ``subprocess.run(..., timeout=N)`` budget is calibrated for a SERIAL run.
# Under the nightly's (slow_tests.yml) and audit_fast's ``-n auto --dist
# worksteal`` parallelism, every xdist worker can spawn its own ``node`` at
# once; the resulting CPU over-subscription starves each node past its timeout
# -> ``subprocess.TimeoutExpired`` -> the test FAILS in parallel while PASSING
# serially. This kept slow_tests.yml RED since 2026-06-26 and flaked every
# commit's Step-11 pre-push.
#
# Structural fix: serialize EVERY ``node`` spawn in the pytest session behind a
# single cross-process ``fcntl.flock``. Because ``-n auto`` runs each worker as
# a SEPARATE OS process that imports this repo-root conftest, every worker's
# node spawn contends on the SAME lock file -> at most ONE node runs at a time
# across ALL workers, session-wide. We patch the ``subprocess.Popen``
# chokepoint (``run``/``call``/``check_output``/``check_call`` — and
# ``from subprocess import run`` callers — all funnel through it), so coverage
# is by CONSTRUCTION: no per-file routing to forget, and a newly-added node
# test is serialized automatically with zero edits. Non-node spawns pass
# through UNCHANGED.
#
# Dist-mode-agnostic: ``fcntl.flock`` is a per-open-file cross-process lock,
# independent of ``--dist worksteal``/``load``/``loadgroup``. (The
# ``@pytest.mark.xdist_group`` alternative is INERT here — xdist honors that
# group mark ONLY under ``--dist loadgroup``, which no targeted env uses.)
#
# Assumes node spawns are synchronous (``subprocess.run``/``call``): each node
# call is reaped before the next is issued within a worker, so there is no
# intra-worker concurrency and no self-blocking on the process-wide flock.

# Executable basenames treated as "a node spawn". ``nodejs`` is included
# defensively; the suite uses ``node``.
_NODE_EXECUTABLE_BASENAMES = frozenset({"node", "nodejs"})

# One stable lock file shared by every worker of THIS repo checkout (the repo
# root is hashed into the name so unrelated checkouts/sessions do not serialize
# against each other). All workers resolve the same repo-root conftest, hence
# the same path, hence the same ``flock``.
_NODE_LOCK_PATH = os.path.join(
    tempfile.gettempdir(),
    "rcx_node_subprocess_%s.lock"
    % hashlib.sha1(str(Path(__file__).resolve().parent).encode("utf-8")).hexdigest()[:16],
)


def _spawn_is_node(args, popen_kwargs) -> bool:
    """Return True when a ``Popen(args, **kwargs)`` spawn resolves to ``node``.

    Detects the list form (``["node", "-e", ...]`` -> argv[0]), the shell/string
    form (``"node -e ..."`` with ``shell=True`` -> first token), and an explicit
    ``executable=`` override. Everything else is a non-node spawn and passes
    through untouched.
    """
    program = popen_kwargs.get("executable")
    if program is None:
        if isinstance(args, (list, tuple)):
            program = args[0] if args else None
        elif isinstance(args, (str, bytes)):
            text = args.decode("utf-8", "replace") if isinstance(args, bytes) else args
            if popen_kwargs.get("shell"):
                try:
                    tokens = shlex.split(text)
                except ValueError:
                    tokens = text.split()
                program = tokens[0] if tokens else None
            else:
                # Non-shell string arg is the literal program name (POSIX
                # semantics: no tokenization).
                program = text
    if program is None:
        return False
    try:
        program = os.fspath(program)
    except TypeError:
        program = str(program)
    if isinstance(program, bytes):
        program = program.decode("utf-8", "replace")
    basename = os.path.basename(program).lower()
    if basename.endswith(".exe"):
        basename = basename[:-4]
    return basename in _NODE_EXECUTABLE_BASENAMES


class _NodeSpawnGuard:
    """Holds one exclusive cross-process ``fcntl.flock`` for a single node spawn."""

    __slots__ = ("_handle",)

    def __init__(self):
        self._handle = None

    def acquire(self) -> None:
        # 'a+' creates-if-missing and never truncates a peer worker's lock file.
        handle = open(_NODE_LOCK_PATH, "a+")  # noqa: SIM115 (held for spawn lifetime)
        try:
            # Blocking exclusive lock: queue behind any peer worker's node.
            _fcntl.flock(handle.fileno(), _fcntl.LOCK_EX)
        except BaseException:
            handle.close()
            raise
        self._handle = handle

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        self._handle = None
        try:
            _fcntl.flock(handle.fileno(), _fcntl.LOCK_UN)
        finally:
            handle.close()


_ORIGINAL_POPEN = subprocess.Popen


class _NodeSerializingPopen(_ORIGINAL_POPEN):
    """``subprocess.Popen`` that serializes ``node`` spawns cross-process.

    A node spawn acquires the shared flock BEFORE the child is forked and holds
    it until the child is reaped — released in ``wait``/``__exit__``/``__del__``,
    including on ``TimeoutExpired`` (``run``/``call`` reap via a post-kill
    ``wait`` on timeout, which flows through the overridden ``wait``). Non-node
    spawns behave exactly like the stock class (guard stays ``None``; every
    release is a no-op).
    """

    _rcx_node_serializer = True

    def __init__(self, args, *popen_args, **popen_kwargs):
        self._rcx_node_guard = None
        if _fcntl is not None and _spawn_is_node(args, popen_kwargs):
            guard = _NodeSpawnGuard()
            guard.acquire()  # block until this worker owns the single node slot
            self._rcx_node_guard = guard
        try:
            super().__init__(args, *popen_args, **popen_kwargs)
        except BaseException:
            # Spawn failed after acquiring -> release immediately.
            self._rcx_release_node_guard()
            raise

    def _rcx_release_node_guard(self) -> None:
        guard = self.__dict__.get("_rcx_node_guard")
        if guard is None:
            return
        self._rcx_node_guard = None
        try:
            guard.release()
        except Exception:
            pass  # never let lock teardown (e.g. interpreter shutdown) escape

    def wait(self, *wait_args, **wait_kwargs):
        # A timeout raises TimeoutExpired WITHOUT releasing (child still alive);
        # a normal return means the child was reaped -> release.
        result = super().wait(*wait_args, **wait_kwargs)
        self._rcx_release_node_guard()
        return result

    def __exit__(self, *exc_info):
        try:
            return super().__exit__(*exc_info)
        finally:
            self._rcx_release_node_guard()

    def __del__(self, *del_args, **del_kwargs):
        # Last-resort safety net (e.g. a manual Popen never waited/closed).
        try:
            self._rcx_release_node_guard()
        except Exception:
            pass
        try:
            super().__del__(*del_args, **del_kwargs)
        except Exception:
            pass


@pytest.fixture(scope="session", autouse=True)
def _serialize_node_subprocess_spawns():
    """Session-wide: serialize every ``node`` subprocess spawn cross-worker.

    Installed once per xdist worker process (each worker imports this conftest
    and runs this autouse session fixture). Patches the ``subprocess.Popen``
    chokepoint so every node spawn — helper-based, inline, ``node -e``, in ANY
    test directory under this rootdir — contends on the shared flock. Restored
    on session teardown.
    """
    if _fcntl is None:
        # Non-POSIX: no fcntl -> run unmodified (POSIX targets always have it).
        yield
        return
    if getattr(subprocess.Popen, "_rcx_node_serializer", False):
        # Already installed (defensive against nested/duplicate sessions).
        yield
        return
    previous = subprocess.Popen
    subprocess.Popen = _NodeSerializingPopen
    try:
        yield
    finally:
        subprocess.Popen = previous
