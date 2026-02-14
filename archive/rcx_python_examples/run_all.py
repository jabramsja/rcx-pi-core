#!/usr/bin/env python3
import os
import sys
import subprocess


def repo_root() -> str:
    # rcx_python_examples/run_all.py -> repo root is one level up
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def main() -> int:
    root = repo_root()
    os.chdir(root)

    env = os.environ.copy()
    env["PYTHONPATH"] = root + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    # also ensure this process can import
    if root not in sys.path:
        sys.path.insert(0, root)

    print("=== RCX-π: running full pytest suite (repo root) ===")
    return subprocess.call([sys.executable, "-m", "pytest"], env=env)


if __name__ == "__main__":
    raise SystemExit(main())
