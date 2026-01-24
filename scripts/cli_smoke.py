#!/usr/bin/env python3
from __future__ import annotations

import json
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

    # 1) program descriptor: schema
    cmd_desc_schema = _best_cmd(
        ["rcx-program-descriptor", "--schema"],
        _py_m("rcx_pi.program_descriptor_cli", "--schema"),
    )
    r = _run(cmd_desc_schema, cwd=repo_root)
    if r.returncode != 0:
        failures.append(f"program-descriptor --schema failed:\n{r.stderr.strip()}")
    else:
        raw = r.stdout
        lines = [ln for ln in raw.splitlines() if ln.strip() != ""]
        line = lines[0] if lines else ""
        if line:
            try:
                run_schema_triplet(
                    cmd_desc_schema,
                    cwd=repo_root,
                    expected_tag="rcx-program-descriptor.v1",
                )
            except Exception as e:
                failures.append(f"--schema output failed strict parse: {line!r} ({e})")
                line = ""
                # NOTE: replaced invalid 'continue' (not inside a loop)
        if "rcx-program-descriptor.v1" not in line:
            failures.append(f"program-descriptor --schema unexpected output: {line!r}")

    # 2) program run: schema + sample run
    cmd_run_schema = _best_cmd(
        ["rcx-program-run", "--schema"],
        _py_m("rcx_pi.program_run_cli", "--schema"),
    )
    r = _run(cmd_run_schema, cwd=repo_root)
    if r.returncode != 0:
        failures.append(f"program-run --schema failed:\n{r.stderr.strip()}")
    else:
        raw = r.stdout
        lines = [ln for ln in raw.splitlines() if ln.strip() != ""]
        line = lines[0] if lines else ""
        if line:
            try:
                run_schema_triplet(
                    cmd_run_schema, cwd=repo_root, expected_tag="rcx-program-run.v1"
                )
            except Exception as e:
                failures.append(f"--schema output failed strict parse: {line!r} ({e})")
                line = ""
                # NOTE: replaced invalid 'continue' (not inside a loop)
        if "rcx-program-run.v1" not in line:
            failures.append(f"program-run --schema unexpected output: {line!r}")

    cmd_run = _best_cmd(
        ["rcx-program-run", "succ-list", "[1,2,3]"],
        _py_m("rcx_pi.program_run_cli", "succ-list", "[1,2,3]"),
    )
    r = _run(cmd_run, cwd=repo_root)
    if r.returncode != 0:
        failures.append(f"program-run succ-list failed:\n{r.stderr.strip()}")
    else:
        data = _require_json(r.stdout)
        for k in ["schema", "schema_doc", "program", "input", "output", "ok"]:
            if k not in data:
                failures.append(
                    f"program-run JSON missing key {k!r}; keys={sorted(data.keys())}"
                )
                break
        if data.get("schema") != "rcx-program-run.v1":
            failures.append(f"program-run schema mismatch: {data.get('schema')!r}")
        if data.get("program") != "succ-list":
            failures.append(f"program-run program mismatch: {data.get('program')!r}")
        if data.get("output") != [2, 3, 4]:
            failures.append(f"program-run output mismatch: {data.get('output')!r}")
        if data.get("ok") is not True:
            failures.append(f"program-run ok not true: {data.get('ok')!r}")

    # 3) world trace: schema + sample trace
    cmd_trace_schema = _best_cmd(
        ["rcx-world-trace", "--schema"],
        _py_m("rcx_pi.worlds.world_trace_cli", "--schema"),
    )
    r = _run(cmd_trace_schema, cwd=repo_root)
    if r.returncode != 0:
        failures.append(f"world-trace --schema failed:\n{r.stderr.strip()}")
    else:
        raw = r.stdout
        lines = [ln for ln in raw.splitlines() if ln.strip() != ""]
        line = lines[0] if lines else ""
        if line:
            try:
                run_schema_triplet(
                    cmd_trace_schema, cwd=repo_root, expected_tag="rcx-world-trace.v1"
                )
            except Exception as e:
                failures.append(f"--schema output failed strict parse: {line!r} ({e})")
                line = ""
                # NOTE: was 'continue' in generator output; replaced to keep module-valid syntax
        if line and "rcx-world-trace.v1" not in line:
            failures.append(f"world-trace --schema unexpected output: {line!r}")

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

    # 4) umbrella rcx-cli (do NOT use `rcx` because you intentionally alias it)
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
