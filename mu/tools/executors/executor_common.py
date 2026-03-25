#!/usr/bin/env python3
"""Shared utilities for executor scripts.

Canonical implementations of functions previously duplicated across
executor_dispatch.py, phase_a_executor.py, phase_b_executor.py, and
dialectic_executor.py.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
from pathlib import Path
from typing import Any

ROUTING_RECORD_PATH = Path(".agent_bus/meta/post_merge_routing.json")

# ---------------------------------------------------------------------------
# Finding disposition classification contract
# ---------------------------------------------------------------------------
# Shared between bridge_reviewer_prompt.txt and phase_b_executor.py.
# If you change these criteria, update BOTH the prompt template and the
# executor's _disposition_for_finding fallback logic.

BLOCKING_CRITERIA = (
    "Causes runtime failure, crash, or data loss in the live pipeline",
    "Violates a hard invariant (receipt authority, fail-closed behavior, process cleanup)",
    "Security bypass or privilege escalation",
    "Breaks an existing test or causes test regression",
    "Makes a pipeline step silently skip or produce wrong output",
)

NON_BLOCKING_CRITERIA = (
    "Hardening improvement that does not affect current correctness",
    "Theoretical edge case that requires synthetic/adversarial setup to trigger",
    "Code quality, style, or naming suggestion",
    "Defense-in-depth addition",
    "Documentation accuracy without behavioral impact",
    "Performance optimization",
)

# Keyword patterns used by the executor to infer disposition when the reviewer
# omits the disposition field.  Checked against the finding's title + summary.
BLOCKING_KEYWORDS = (
    "runtime failure", "crash", "data loss",
    "test failure", "test regression", "breaks test",
    "invariant violation", "invariant violated",
    "security bypass", "privilege escalation",
    "silently skip", "wrong output", "silent failure",
    "receipt authority", "fail-closed", "fail closed",
    "process cleanup", "orphan",
)

NON_BLOCKING_KEYWORDS = (
    "hardening", "defense-in-depth", "defence-in-depth",
    "theoretical", "adversarial setup", "synthetic scenario",
    "style", "naming", "readability",
    "documentation", "doc accuracy", "docstring",
    "performance", "optimization",
    "edge case",
)

# Detail-text indicators for high-severity findings that lack keyword matches.
# Used to distinguish hardening items from real defects when the reviewer
# omits disposition and no primary keywords match.
HARDENING_INDICATORS = (
    "theoretical", "synthetic", "adversarial setup",
    "spoofable", "could be bypassed", "could be spoofed",
    "hypothetical", "unlikely in practice",
)
DEFECT_INDICATORS = (
    "returns success", "still proceeds", "accepted",
    "reaches commit_ready", "silently passes",
    "no error raised", "skips validation",
    "orphaned", "not cleaned up", "leaked process",
    "receipt not checked", "receipt ignored",
    "proceeds without receipt", "skips receipt",
)

# Repeat-finding hard-failure cap: if the same blocking finding appears in
# this many consecutive bridge rounds without resolution, the bridge loop
# terminates as a hard failure.  Blocking findings are NEVER auto-downgraded.
REPEAT_FINDING_CAP = 3


class ExecutorCommonError(RuntimeError):
    """Raised when a shared executor utility fails."""


def load_routing_record(repo_root: Path) -> dict[str, Any]:
    """Load and validate the post-merge routing record.

    This is the canonical implementation. All executors should import
    this instead of maintaining their own copy.

    Returns the parsed JSON record.
    Raises ExecutorCommonError if the file is missing, invalid JSON,
    or missing required keys.
    """
    record_path = repo_root / ROUTING_RECORD_PATH
    if not record_path.exists():
        raise ExecutorCommonError(f"Routing record not found: {record_path}")

    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExecutorCommonError(f"Routing record is not valid JSON: {exc}") from exc

    required = {"decision", "summary"}
    missing = required - set(record.keys())
    if missing:
        raise ExecutorCommonError(f"Routing record missing keys: {sorted(missing)}")

    return record


def run_bridge_subprocess(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    """Run a bridge subprocess with proper process-group cleanup on timeout.

    Uses Popen with start_new_session=True so that the bridge process and
    its direct children form a new process group.  On timeout, os.killpg()
    kills the entire group (including adapter grandchildren that haven't
    created their own sessions).  Adapter processes that DID create their
    own sessions (via start_new_session=True in bridge_adapters.py) are
    handled by their own watchdog timers — but SIGTERM is sent to the
    bridge first to give it a chance to clean up before SIGKILL.

    Returns a CompletedProcess with stdout, stderr, and returncode.
    Raises ExecutorCommonError on timeout (after cleanup).
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=proc.returncode,
            stdout=stdout,
            stderr=stderr,
        )
    except subprocess.TimeoutExpired:
        # Graceful: SIGTERM the process group so bridge_supervisor can
        # clean up its adapter children before we force-kill.
        pgid = os.getpgid(proc.pid)
        try:
            os.killpg(pgid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass
        # Brief grace period for cleanup, then SIGKILL
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                try:
                    proc.kill()
                except OSError:
                    pass
            proc.wait()
        raise ExecutorCommonError(
            f"Bridge subprocess timed out after {timeout}s"
        )
