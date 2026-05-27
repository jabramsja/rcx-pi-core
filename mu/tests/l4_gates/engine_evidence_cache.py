"""Shared cached evidence helpers for expensive L4 engine tests."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline
from rcx_pi.selfhost.kernel import reset_step_budget
from tests.repo_root import REPO_ROOT

_DEFAULT_CACHED_JS_TIMEOUT_S = 180
_DEFAULT_UNCACHED_JS_TIMEOUT_S = 60
_SHARED_LOCK_WAIT_TIMEOUT_S = 600
_SHARED_LOCK_STALE_AFTER_S = 300
_JS_PROCESS_CACHE: dict[str, dict[str, Any]] = {}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _shared_cache_dir() -> Path | None:
    run_uid = os.environ.get("PYTEST_XDIST_TESTRUNUID")
    if not run_uid:
        return None
    cache_dir = Path(tempfile.gettempdir()) / "rcx_l4_engine_evidence" / run_uid
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _lock_owner_pid(lock_text: str) -> int | None:
    try:
        pid = int(lock_text.strip().splitlines()[0])
    except (IndexError, ValueError):
        return None
    return pid if pid > 0 else None


def _reclaim_stale_shared_cache_lock(lock_path: Path) -> bool:
    try:
        lock_stat = lock_path.stat()
        lock_text = lock_path.read_text()
    except FileNotFoundError:
        return True

    owner_pid = _lock_owner_pid(lock_text)
    stale_by_dead_owner = owner_pid is not None and not _pid_is_alive(owner_pid)
    stale_by_age = time.time() - lock_stat.st_mtime > _SHARED_LOCK_STALE_AFTER_S
    if not stale_by_dead_owner and not stale_by_age:
        return False

    try:
        current_stat = lock_path.stat()
    except FileNotFoundError:
        return True
    if (
        current_stat.st_ino != lock_stat.st_ino
        or current_stat.st_mtime_ns != lock_stat.st_mtime_ns
        or current_stat.st_size != lock_stat.st_size
    ):
        return False

    try:
        lock_path.unlink()
    except FileNotFoundError:
        return True
    return True


def _shared_cache_get_or_compute(kind: str, key: dict[str, Any], compute):
    cache_dir = _shared_cache_dir()
    if cache_dir is None:
        return compute()

    digest = hashlib.sha256(_stable_json({"kind": kind, "key": key}).encode("utf-8")).hexdigest()
    path = cache_dir / f"{kind}_{digest}.json"
    lock_path = cache_dir / f"{kind}_{digest}.lock"
    if path.exists():
        return json.loads(path.read_text())

    start = time.monotonic()
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if path.exists():
                return json.loads(path.read_text())
            if _reclaim_stale_shared_cache_lock(lock_path):
                continue
            if time.monotonic() - start > _SHARED_LOCK_WAIT_TIMEOUT_S:
                raise TimeoutError(f"timed out waiting for shared L4 evidence cache lock: {lock_path}")
            time.sleep(0.05)
            continue

        try:
            with os.fdopen(fd, "w") as lock_file:
                lock_file.write(str(os.getpid()))
            if path.exists():
                return json.loads(path.read_text())
            value = compute()
            tmp_path = cache_dir / f"{kind}_{digest}.{os.getpid()}.tmp"
            tmp_path.write_text(_stable_json(value))
            os.replace(tmp_path, path)
            return value
        finally:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass


@lru_cache(maxsize=None)
def _cached_python_pipeline(
    projections_json: str,
    input_json: str,
    max_steps: int,
    max_engine_iterations: int,
    max_algorithm_iterations: int,
    boot1_mode: str,
) -> dict[str, Any]:
    key = {
        "projections_json": projections_json,
        "input_json": input_json,
        "max_steps": max_steps,
        "max_engine_iterations": max_engine_iterations,
        "max_algorithm_iterations": max_algorithm_iterations,
        "boot1_mode": boot1_mode,
    }

    def compute():
        projections = json.loads(projections_json)
        input_value = json.loads(input_json)
        observer: list[dict[str, Any]] = []
        kwargs: dict[str, Any] = {
            "max_steps": max_steps,
            "max_engine_iterations": max_engine_iterations,
            "max_algorithm_iterations": max_algorithm_iterations,
            "observer": observer,
            "return_meta": True,
        }
        if boot1_mode == "true":
            kwargs["use_boot1_recursive"] = True
        elif boot1_mode == "false":
            kwargs["use_boot1_recursive"] = False
        elif boot1_mode != "omitted":
            raise ValueError(f"unknown boot1_mode: {boot1_mode!r}")

        reset_step_budget()
        result = run_engine_pipeline(projections, input_value, **kwargs)
        return {"meta": result, "observer": observer}

    return _shared_cache_get_or_compute("python_pipeline_superset", key, compute)


def clear_python_pipeline_cache() -> None:
    """Clear in-process Python engine evidence cached for focused tests."""
    _cached_python_pipeline.cache_clear()


def cached_python_pipeline(
    *,
    projections: list[Any] | None = None,
    input_value: Any,
    max_steps: int = 10,
    max_engine_iterations: int = 20,
    max_algorithm_iterations: int = 50,
    boot1_mode: str = "false",
    return_meta: bool = False,
    observer_enabled: bool = False,
) -> dict[str, Any]:
    """Run deterministic engine evidence once and return an isolated copy."""
    evidence = _cached_python_pipeline(
        _stable_json(projections or []),
        _stable_json(input_value),
        max_steps,
        max_engine_iterations,
        max_algorithm_iterations,
        boot1_mode,
    )
    meta = evidence["meta"]
    view = {
        "result": meta if return_meta else meta["engine_result"],
        "observer": evidence["observer"] if observer_enabled else [],
    }
    return copy.deepcopy(view)


def _cached_js_json_api(payload_json: str, timeout_s: int) -> dict[str, Any]:
    if payload_json in _JS_PROCESS_CACHE:
        return _JS_PROCESS_CACHE[payload_json]

    key = {"payload_json": payload_json}

    def compute():
        return _run_js_json_api_payload(payload_json, timeout_s)

    value = _shared_cache_get_or_compute("js_json_api", key, compute)
    _JS_PROCESS_CACHE[payload_json] = value
    return value


def _run_js_json_api_payload(payload_json: str, timeout_s: int) -> dict[str, Any]:
    js_path = REPO_ROOT / "mu" / "host" / "js" / "eval_step.js"
    result = subprocess.run(
        ["node", str(js_path), "--json-api", payload_json],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=timeout_s,
    )
    for line in result.stdout.split("\n"):
        if line.startswith("JSON_API_RESPONSE:"):
            return json.loads(line[len("JSON_API_RESPONSE:"):])
    pytest.fail(
        f"No JSON_API_RESPONSE in JS output.\n"
        f"returncode: {result.returncode}\n"
        f"stdout: {result.stdout[:500]}\n"
        f"stderr: {result.stderr[:500]}"
    )


def cached_js_request(
    action: str,
    *,
    observer: bool = False,
    timeout_s: int = _DEFAULT_CACHED_JS_TIMEOUT_S,
    **kwargs: Any,
) -> dict[str, Any]:
    """Send a deterministic JS JSON API request once and return an isolated copy."""
    request: dict[str, Any] = {"action": action, **kwargs}
    if observer:
        request["observer"] = True
    payload_json = _stable_json(request)
    return copy.deepcopy(_cached_js_json_api(payload_json, timeout_s))


def uncached_js_request(
    action: str,
    *,
    observer: bool = False,
    timeout_s: int = _DEFAULT_UNCACHED_JS_TIMEOUT_S,
    **kwargs: Any,
) -> dict[str, Any]:
    """Send a JS JSON API request without caching for negative/error-path proofs."""
    request: dict[str, Any] = {"action": action, **kwargs}
    if observer:
        request["observer"] = True
    return _run_js_json_api_payload(_stable_json(request), timeout_s)
