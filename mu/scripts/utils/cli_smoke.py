#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from typing import List, Optional
from rcx_pi.cli_schema import parse_schema_triplet
from rcx_pi.cli_schema_run import run_schema_triplet


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def _run(
    cmd: List[str], cwd: str = ".", stdin: Optional[str] = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=cwd,
        input=stdin,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONHASHSEED": "0"},
    )


def _py_m(module: str, *args: str) -> List[str]:
    return [sys.executable, "-m", module, *args]


def _best_cmd(preferred: List[str], fallback: List[str]) -> List[str]:
    # preferred[0] is the executable name
    if preferred and _which(preferred[0]):
        return preferred
    return fallback


def _require_json(s: str) -> dict:
    try:
        return json.loads(s)
    except Exception as e:
        raise AssertionError(f"Expected JSON, got:\n{s[:4000]}") from e


def main() -> int:
    repo_root = "."
    failures: List[str] = []

    # 1) world trace: schema + sample trace
    cmd_trace_schema = _best_cmd(
        ["rcx-world-trace", "--schema"],
        _py_m("rcx_pi.worlds.world_trace_cli", "--schema"),
    )
    try:
        run_schema_triplet(
            cmd_trace_schema, cwd=repo_root, expected_tag="rcx-world-trace.v1"
        )
    except AssertionError as e:
        failures.append(f"world-trace --schema failed strict parse/tag check: {e}")
    cmd_trace = _best_cmd(
        ["rcx-world-trace", "pingpong", "ping", "--max-steps", "6"],
        _py_m("rcx_pi.worlds.world_trace_cli", "pingpong", "ping", "--max-steps", "6"),
    )
    r = _run(cmd_trace, cwd=repo_root)
    if r.returncode != 0:
        failures.append(f"world-trace pingpong ping failed:\n{r.stderr.strip()}")
    else:
        data = _require_json(r.stdout)
        for k in [
            "schema",
            "schema_doc",
            "world",
            "seed",
            "max_steps",
            "trace",
            "orbit",
            "meta",
        ]:
            if k not in data:
                failures.append(
                    f"world-trace JSON missing key {k!r}; keys={sorted(data.keys())}"
                )
                break
        if data.get("schema") != "rcx-world-trace.v1":
            failures.append(f"world-trace schema mismatch: {data.get('schema')!r}")
        if data.get("world") != "pingpong":
            failures.append(f"world-trace world mismatch: {data.get('world')!r}")
        if data.get("seed") != "ping":
            failures.append(f"world-trace seed mismatch: {data.get('seed')!r}")

    # 2) umbrella rcx-cli (do NOT use `rcx` because you intentionally alias it)
    cmd_umb_help = _best_cmd(
        ["rcx-cli", "--help"],
        _py_m("rcx_pi.rcx_cli", "--help"),
    )
    r = _run(cmd_umb_help, cwd=repo_root)
    if r.returncode != 0:
        failures.append(f"rcx-cli --help failed:\n{r.stderr.strip()}")
    else:
        if "RCX umbrella CLI" not in r.stdout:
            failures.append("rcx-cli --help did not include expected help text")

    if failures:
        print("❌ CLI SMOKE FAILED", file=sys.stderr)
        for f in failures:
            print("\n---\n" + f, file=sys.stderr)
        return 1

    print("✅ CLI SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
