#!/usr/bin/env python3
from __future__ import annotations

import os, subprocess, sys, time

BASE = os.environ.get("RCX_BASE", "dev")


def run(cmd: list[str], check: bool = True) -> int:
    print("+", " ".join(cmd))
    p = subprocess.run(cmd, text=True)
    if check and p.returncode != 0:
        raise SystemExit(p.returncode)
    return p.returncode


def out(cmd: list[str]) -> str:
    print("+", " ".join(cmd))
    return subprocess.check_output(cmd, text=True).strip()


def pr_state(pr: str) -> str:
    return out(["gh", "pr", "view", pr, "--json", "state", "--jq", ".state"])


def wait_checks(pr: str, timeout_s: int = 900) -> None:
    # gh: --fail-fast requires --watch. This call blocks until checks finish.
    deadline = time.time() + timeout_s
    while True:
        rc = run(["gh", "pr", "checks", pr, "--watch", "--fail-fast"], check=False)
        if rc == 0:
            return
        if time.time() > deadline:
            raise SystemExit("Timed out waiting for checks to pass.")
        time.sleep(5)


def wait_merged(pr: str, timeout_s: int = 900) -> None:
    deadline = time.time() + timeout_s
    while True:
        st = pr_state(pr)
        print("state:", st)
        if st == "MERGED":
            return
        if time.time() > deadline:
            raise SystemExit("Timed out waiting for PR to merge.")
        time.sleep(5)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 scripts/rcx_pr_watch_and_gate.py <PR_NUMBER>")

    pr = sys.argv[1]

    root = out(["git", "rev-parse", "--show-toplevel"])
    os.chdir(root)

    # Informational
    run(["gh", "pr", "view", pr], check=False)

    st = pr_state(pr)
    print("state:", st)

    if st != "MERGED":
        wait_checks(pr)

        # ready only applies to drafts; non-fatal if already non-draft/closed
        run(["gh", "pr", "ready", pr], check=False)

        # enable auto-merge; non-fatal if already merged/enabled/etc
        run(
            ["gh", "pr", "merge", pr, "--auto", "--merge", "--delete-branch"],
            check=False,
        )

        wait_merged(pr)

    # Truth: sync + deterministic gates
    run(["git", "checkout", BASE])
    run(["git", "pull", "--ff-only"])
    run(["./scripts/check_orbit_all.sh"])

    print(f"OK: PR{pr} merged; {BASE} synced; deterministic gates green")


if __name__ == "__main__":
    main()
