#!/usr/bin/env python3
"""Verify pre-commit receipt for the git pre-commit hook.

This script ONLY verifies — it never runs the supervisor.
The hook calls this to check that Claude explicitly ran the
meta-bridge supervisor for the current staged state.

Exit codes:
    0 -> receipt valid, commit may proceed
    1 -> receipt missing/stale/invalid, commit should be blocked
    2 -> skip (no staged files, or RCX_SKIP_RECEIPT_CHECK=1)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    # Allow explicit skip (e.g., for non-Claude commits, CI, founder override)
    if os.environ.get("RCX_SKIP_RECEIPT_CHECK") == "1":
        return 2

    # Find repo root
    try:
        toplevel = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        repo_root = Path(toplevel)
    except subprocess.CalledProcessError:
        print("[receipt-check] Not in a git repo, skipping", file=sys.stderr)
        return 2

    # Check if anything is staged
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=str(repo_root),
    ).stdout.strip()
    if not staged:
        return 2  # Nothing staged, skip

    # Import verifier from meta_bridge_supervisor
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

    # Also need bridge_adapters on path (dependency of meta_bridge_supervisor)
    try:
        from meta_bridge_supervisor import verify_pre_commit_receipt
    except ImportError as exc:
        print(f"\n❌ PRE-COMMIT RECEIPT CHECK FAILED", file=sys.stderr)
        print(f"   Cannot import verifier: {exc}", file=sys.stderr)
        print(f"   Blocking commit (fail-closed). Fix the import or set RCX_SKIP_RECEIPT_CHECK=1.", file=sys.stderr)
        return 1

    passed, message = verify_pre_commit_receipt(repo_root)
    if passed:
        print(f"✅ {message}")
        return 0
    else:
        print(f"\n❌ PRE-COMMIT RECEIPT CHECK FAILED")
        print(f"   {message}")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
