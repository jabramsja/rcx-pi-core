#!/usr/bin/env python3
"""
Diagnose whether this shell can run Claude agent runners.

This is a local environment check (no repository mutation).
It surfaces common failure causes:
- Python architecture mismatch
- SDK dependency import failures (claude_agent_sdk / pydantic_core)
- Bun runtime issues (e.g., AVX capability mismatch)
- Runner bootstrap viability (run_review.py --help)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CmdResult:
    cmd: list[str]
    returncode: int
    stdout: str
    stderr: str


def _run(cmd: list[str], *, timeout: int = 20, env: dict[str, str] | None = None) -> CmdResult:
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=REPO_ROOT,
        )
        return CmdResult(cmd=cmd, returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
    except Exception as exc:  # pragma: no cover - defensive
        return CmdResult(cmd=cmd, returncode=999, stdout="", stderr=f"{type(exc).__name__}: {exc}")


def _module_spec(mod_name: str) -> dict[str, Any]:
    try:
        spec = importlib.util.find_spec(mod_name)
    except Exception as exc:
        return {
            "module": mod_name,
            "found": False,
            "origin": None,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "module": mod_name,
        "found": bool(spec),
        "origin": getattr(spec, "origin", None) if spec else None,
        "error": None,
    }


def _shared_object_arch(path: str | None) -> dict[str, Any]:
    if not path or not Path(path).exists():
        return {"path": path, "exists": False, "file_output": None}
    file_cmd = _run(["file", path], timeout=10)
    return {
        "path": path,
        "exists": True,
        "file_output": (file_cmd.stdout or file_cmd.stderr).strip(),
    }


def _check_runner_with_python(python_exe: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    check = _run([python_exe, "tools/run_review.py", "--help"], timeout=30, env=env)
    return {
        "python": python_exe,
        "ok": check.returncode == 0,
        "returncode": check.returncode,
        "stderr_head": (check.stderr or "").splitlines()[:6],
        "stdout_head": (check.stdout or "").splitlines()[:6],
    }


def collect_diagnostics() -> dict[str, Any]:
    data: dict[str, Any] = {}

    data["python"] = {
        "executable": sys.executable,
        "version": sys.version.split()[0],
        "machine": platform.machine(),
        "platform": platform.platform(),
    }

    data["modules"] = {
        "claude_agent_sdk": _module_spec("claude_agent_sdk"),
        "pydantic_core": _module_spec("pydantic_core"),
        "pydantic_core._pydantic_core": _module_spec("pydantic_core._pydantic_core"),
    }

    pyd_core_bin_origin = data["modules"]["pydantic_core._pydantic_core"]["origin"]
    # Fallback: locate binary next to pydantic_core package when extension spec is unavailable.
    if not pyd_core_bin_origin:
        pkg_origin = data["modules"]["pydantic_core"]["origin"]
        if pkg_origin:
            pkg_dir = Path(pkg_origin).resolve().parent
            matches = sorted(pkg_dir.glob("_pydantic_core*.so"))
            if matches:
                pyd_core_bin_origin = str(matches[0])

    data["pydantic_core_binary"] = _shared_object_arch(pyd_core_bin_origin)

    try:
        import claude_agent_sdk  # type: ignore

        data["sdk_import"] = {
            "ok": True,
            "version": getattr(claude_agent_sdk, "__version__", None),
            "error": None,
        }
    except Exception as exc:
        data["sdk_import"] = {
            "ok": False,
            "version": None,
            "error": f"{type(exc).__name__}: {exc}",
        }

    bun_check = _run(["bun", "--version"], timeout=10)
    bun_info: dict[str, Any] = {
        "found": bun_check.returncode == 0,
        "version": (bun_check.stdout or "").strip() if bun_check.returncode == 0 else None,
        "error": (bun_check.stderr or "").strip() if bun_check.returncode != 0 else None,
    }
    # Capture capability errors that may still appear even when command fails.
    if "AVX" in (bun_check.stderr or "") or "AVX" in (bun_check.stdout or ""):
        bun_info["avx_warning"] = True
    else:
        bun_info["avx_warning"] = False
    data["bun"] = bun_info

    python_candidates = [sys.executable]
    for candidate in (
        "/usr/local/bin/python3-intel64",
        "/usr/local/bin/python3.13-intel64",
        "/opt/homebrew/bin/python3",
    ):
        if Path(candidate).exists() and candidate not in python_candidates:
            python_candidates.append(candidate)

    data["runner_bootstrap"] = [_check_runner_with_python(py) for py in python_candidates]

    # Overall determination: at least one interpreter can run run_review --help.
    data["can_run_runners_here"] = any(item["ok"] for item in data["runner_bootstrap"])
    return data


def print_human(data: dict[str, Any]) -> None:
    print("== Agent Runtime Diagnostics ==")
    print(f"Python: {data['python']['version']} ({data['python']['machine']})")
    print(f"Executable: {data['python']['executable']}")
    print("")

    sdk = data["sdk_import"]
    if sdk["ok"]:
        print("SDK import: PASS")
    else:
        print(f"SDK import: FAIL ({sdk['error']})")

    pyd = data["pydantic_core_binary"]
    if pyd["exists"]:
        print(f"pydantic_core: {pyd['file_output']}")
    else:
        print("pydantic_core: not found")

    bun = data["bun"]
    if bun["found"]:
        avx_note = " (AVX warning detected)" if bun.get("avx_warning") else ""
        print(f"Bun: PASS {bun['version']}{avx_note}")
    else:
        print(f"Bun: FAIL ({bun['error']})")
    print("")

    print("Runner bootstrap checks (run_review.py --help):")
    for item in data["runner_bootstrap"]:
        status = "PASS" if item["ok"] else "FAIL"
        print(f"- {item['python']}: {status}")
        if not item["ok"] and item["stderr_head"]:
            print(f"  stderr: {item['stderr_head'][0]}")

    print("")
    overall = "PASS" if data["can_run_runners_here"] else "FAIL"
    print(f"Overall runnable in this shell: {overall}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose Claude agent runtime compatibility")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    args = parser.parse_args()

    data = collect_diagnostics()
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print_human(data)

    sys.exit(0 if data["can_run_runners_here"] else 1)


if __name__ == "__main__":
    main()
