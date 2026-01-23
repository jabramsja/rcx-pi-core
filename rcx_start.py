#!/usr/bin/env python3
"""
rcx_start.py

Single entrypoint / launcher menu for RCX-π Python stuff.

- Always runs from the repo root (WorkingRCX)
- Ensures `rcx_pi` is importable in child processes via PYTHONPATH
- Lets you pick demos/tests from a simple menu
- Can dynamically run any .py in rcx_python_examples/
"""

import os
import sys
import subprocess
import glob
from typing import Dict, Callable, Tuple, List


# ---------------------------------------------------------------------
# Repo root detection
# ---------------------------------------------------------------------


def get_repo_root() -> str:
    """Return the absolute path to the WorkingRCX repo root."""
    return os.path.dirname(os.path.abspath(__file__))


REPO_ROOT = get_repo_root()

# Make sure repo root is on sys.path so *this* process can import rcx_pi too.
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


# ---------------------------------------------------------------------
# Helpers to run commands
# ---------------------------------------------------------------------


def _env_with_repo_on_path() -> dict:
    """Return a copy of os.environ with REPO_ROOT added to PYTHONPATH."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = REPO_ROOT + os.pathsep + existing if existing else REPO_ROOT
    return env


def run_python_module(module: str, args: List[str] | None = None) -> int:
    """Run `python3 -m <module> [args...]` from the repo root."""
    if args is None:
        args = []
    cmd = ["python3", "-m", module, *args]
    print(f"\n[run] cwd={REPO_ROOT}\n[run] {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=REPO_ROOT, env=_env_with_repo_on_path())
    return result.returncode


def run_python_file(relative_path: str, args: List[str] | None = None) -> int:
    """Run `python3 <relative_path> [args...]` from the repo root."""
    if args is None:
        args = []
    script_path = os.path.join(REPO_ROOT, relative_path)
    cmd = ["python3", script_path, *args]
    print(f"\n[run] cwd={REPO_ROOT}\n[run] {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=REPO_ROOT, env=_env_with_repo_on_path())
    return result.returncode


def run_cmd(cmd: List[str], cwd: str | None = None) -> int:
    """Run an arbitrary command (list[str]) with repo-root env + cwd."""
    if cwd is None:
        cwd = REPO_ROOT
    print(f"\n[run] cwd={cwd}\n[run] {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=cwd, env=_env_with_repo_on_path())
    return result.returncode


# ---------------------------------------------------------------------
# Dynamic example picker for rcx_python_examples/
# ---------------------------------------------------------------------


def pick_and_run_example() -> int:
    """
    List all *.py files in rcx_python_examples/ and let the user pick one
    to run. Returns the exit code of the chosen script (or 0 if nothing run).
    """
    examples_dir = os.path.join(REPO_ROOT, "rcx_python_examples")
    files = sorted(glob.glob(os.path.join(examples_dir, "*.py")))

    if not files:
        print("\n[examples] No .py files found in rcx_python_examples/\n")
        return 0

    print("\nExamples in rcx_python_examples/:")
    for i, path in enumerate(files, start=1):
        print(f"  {i}) {os.path.basename(path)}")
    print("  q) back\n")

    choice = input("Select example: ").strip()
    if choice.lower() in {"q", ""}:
        print("[examples] cancelled.\n")
        return 0

    try:
        idx = int(choice)
    except ValueError:
        print("[examples] not a number.\n")
        return 0

    if not (1 <= idx <= len(files)):
        print("[examples] out of range.\n")
        return 0

    basename = os.path.basename(files[idx - 1])
    rel_path = os.path.join("rcx_python_examples", basename)
    print(f"\n[examples] running {basename}...\n")
    return run_python_file(rel_path)


# ---------------------------------------------------------------------
# Menu entries
# ---------------------------------------------------------------------

MenuEntry = Tuple[str, Callable[[], int]]


def make_menu() -> Dict[str, MenuEntry]:
    menu: Dict[str, MenuEntry] = {}

    menu["1"] = (
        "Worlds: mutation demo (rcx_pi.worlds.worlds_mutate_demo)",
        lambda: run_python_module("rcx_pi.worlds.worlds_mutate_demo"),
    )

    menu["2"] = (
        "Worlds: evolve / score demo (rcx_pi.worlds.worlds_evolve)",
        lambda: run_python_module("rcx_pi.worlds.worlds_evolve"),
    )

    menu["3"] = (
        "Worlds: compare demo (rcx_pi.worlds.worlds_compare_demo)",
        lambda: run_python_module("rcx_pi.worlds.worlds_compare_demo"),
    )

    menu["4"] = (
        "Worlds: score demo (rcx_pi.worlds.worlds_score_demo)",
        lambda: run_python_module("rcx_pi.worlds.worlds_score_demo"),
    )

    menu["5"] = (
        "Orbit ASCII: pingpong / ping / 12 steps",
        lambda: run_python_module(
            "rcx_pi.worlds.orbit_ascii_demo", ["pingpong", "ping", "12"]
        ),
    )

    menu["6"] = (
        "Run example from rcx_python_examples/",
        pick_and_run_example,
    )

    menu["7"] = (
        "Rust: green examples suite (rcx_pi_rust/scripts/green_examples.sh)",
        lambda: run_cmd(["bash", "rcx_pi_rust/scripts/green_examples.sh"]),
    )

    menu["8"] = (
        "Run pytest (all rcx_pi tests)",
        lambda: run_cmd(["python3", "-m", "pytest"]),
    )

    return menu


# ---------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------


def main() -> None:
    print("=== RCX-π launcher ===")
    print(f"Repo root: {REPO_ROOT}")
    print("This menu runs things *from the repo root* so `import rcx_pi` works.\n")

    menu = make_menu()

    while True:
        print("Menu:")
        for key in sorted(menu.keys(), key=lambda k: int(k) if k.isdigit() else k):
            label, _fn = menu[key]
            print(f"  {key}) {label}")
        print("  q) quit")

        choice = input("\nSelect option: ").strip()

        if choice.lower() in {"q", "quit", "exit"}:
            print("Bye.")
            break

        if choice not in menu:
            print(f"Unknown choice: {choice!r}\n")
            continue

        label, fn = menu[choice]
        print(f"\n=== Running: {label} ===")
        try:
            code = fn()
            print(f"\n[done] exit code: {code}\n")
        except KeyboardInterrupt:
            print("\n[interrupted]\n")
        except Exception as e:
            print(f"\n[error] {e}\n")


if __name__ == "__main__":
    main()
