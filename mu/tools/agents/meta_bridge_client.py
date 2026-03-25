#!/usr/bin/env python3
"""Structured meta-bridge supervisor client.

Provides a reusable Python API for invoking the pre-commit supervisor
without shell+grep parsing. Uses the real Python API (run_meta_bridge)
directly, with lock-aware retry and structured result handling.

Never greps output text. Never mistakes template enum strings for
real decisions.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Pipe-delimited enum placeholders from meta_bridge_task.txt template.
# These are NEVER valid real decisions — reject if seen.
_TEMPLATE_ENUM_PATTERN = "|"


class MetaBridgeClientError(RuntimeError):
    """Raised when the client cannot invoke the supervisor."""


@dataclass(frozen=True)
class SupervisorResult:
    """Structured result from supervisor invocation."""

    decision: str
    summary: str
    status: str  # "success", "error", "partial"
    validations_passed: list[str]
    validations_failed: list[dict[str, str]]
    findings: list[dict[str, Any]]
    request_for_claude: str
    error_code: str
    error_detail: str
    receipt_path: str  # path to receipt if COMMIT_GO/COMMIT_GO_HOLD_PUSH

    @property
    def is_commit_capable(self) -> bool:
        return self.decision in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH")

    @property
    def is_error(self) -> bool:
        return self.decision.startswith("ERROR_")

    @property
    def is_hold(self) -> bool:
        return self.decision == "COMMIT_GO_HOLD_PUSH"


# Valid concrete decisions from the Decision enum in meta_bridge_supervisor.py
VALID_DECISIONS = frozenset({
    "COMMIT_GO", "COMMIT_GO_HOLD_PUSH", "NO_ACTION",
    "NEEDS_PHASE_A", "NEEDS_PHASE_B",
    "STOP_FOR_FOUNDER", "STOP_FOR_TRIAGE_DISCUSSION",
    "CONTINUE_DIALECTIC", "ROUTE_PHASE_A", "ROUTE_PHASE_B", "UPDATE_TRACKER_ONLY",
    "ERROR_PACKAGE_INVALID", "ERROR_CODEX_TIMEOUT", "ERROR_CODEX_ABORT",
    "ERROR_VALIDATION_FAILED", "ERROR_REPO_CHANGED", "ERROR_MERGE_NOT_FOUND",
    "ERROR_INTERNAL", "RETRY_SUGGESTED",
})


def _validate_decision(decision: str) -> None:
    """Reject invalid decisions using positive allowlist."""
    if not decision:
        raise MetaBridgeClientError("Supervisor returned empty decision")
    if _TEMPLATE_ENUM_PATTERN in decision:
        raise MetaBridgeClientError(
            f"Supervisor returned pipe-delimited template enum, not a real decision: {decision[:100]}"
        )
    if decision not in VALID_DECISIONS:
        raise MetaBridgeClientError(
            f"Supervisor returned unknown decision '{decision}'. "
            f"Valid: {sorted(VALID_DECISIONS)}"
        )


def run_meta_bridge_package(
    package_path: Path,
    *,
    wait_for_lock_seconds: int = 30,
    poll_interval_seconds: float = 1.0,
    verbose: bool = False,
    dry_run: bool = False,
) -> SupervisorResult:
    """Invoke the meta-bridge supervisor with structured result handling.

    Uses the real Python API (run_meta_bridge) directly — no subprocess,
    no shell, no grep.

    Args:
        package_path: Path to the supervisor package JSON file.
        wait_for_lock_seconds: Max seconds to wait if lock is held.
        poll_interval_seconds: Seconds between lock-retry attempts.
        verbose: Pass through to supervisor.
        dry_run: Pass through to supervisor (skip Codex call).

    Returns:
        SupervisorResult with structured decision and details.

    Raises:
        MetaBridgeClientError: On lock timeout, import failure, or invalid decision.
    """
    # Import supervisor lazily to avoid circular deps
    try:
        import sys
        supervisor_dir = str(Path(__file__).resolve().parent)
        if supervisor_dir not in sys.path:
            sys.path.insert(0, supervisor_dir)
        from meta_bridge_supervisor import (
            MetaBridgeError,
            run_meta_bridge,
        )
    except ImportError as exc:
        raise MetaBridgeClientError(f"Cannot import meta_bridge_supervisor: {exc}") from exc

    # Lock-aware retry loop
    deadline = time.monotonic() + wait_for_lock_seconds
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            response = run_meta_bridge(
                package_path,
                verbose=verbose,
                dry_run=dry_run,
            )
            break
        except MetaBridgeError as exc:
            if "Another meta-bridge supervisor is running" in str(exc):
                last_error = exc
                if verbose:
                    print(f"[meta-bridge-client] Lock held, retrying in {poll_interval_seconds}s...")
                time.sleep(poll_interval_seconds)
                continue
            raise MetaBridgeClientError(f"Supervisor error: {exc}") from exc
    else:
        raise MetaBridgeClientError(
            f"Supervisor lock held for {wait_for_lock_seconds}s. "
            f"Last error: {last_error}"
        )

    # Validate the decision is real, not a template placeholder
    _validate_decision(response.decision)

    # Write receipt for commit-capable decisions and capture the exact path.
    # write_pre_commit_receipt returns the per-invocation receipt path directly —
    # no heuristic discovery needed.
    receipt_path = ""
    if response.decision in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
        import subprocess as _sp
        try:
            from meta_bridge_supervisor import write_pre_commit_receipt
            exact_receipt_path = write_pre_commit_receipt(response, package_path)
        except Exception as exc:
            raise MetaBridgeClientError(
                f"Supervisor returned {response.decision} but receipt write failed: {exc}"
            ) from exc

        # Convert absolute path to repo-relative for handoff portability.
        # FAIL CLOSED if conversion fails — absolute paths are never safe
        # for downstream executors.
        try:
            toplevel = _sp.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True,
                cwd=str(package_path.resolve().parent),
            ).stdout.strip()
            repo = Path(toplevel)
            receipt_path = str(exact_receipt_path.relative_to(repo))
        except (_sp.CalledProcessError, ValueError) as exc:
            raise MetaBridgeClientError(
                f"Cannot convert receipt path to repo-relative — fail closed. "
                f"absolute={exact_receipt_path}, error={exc}"
            ) from exc

    # Validate envelope has required fields before constructing result
    _required_attrs = ("decision", "summary", "status")
    for attr in _required_attrs:
        if not hasattr(response, attr) or getattr(response, attr) is None:
            raise MetaBridgeClientError(
                f"Supervisor response missing required field: {attr}"
            )

    return SupervisorResult(
        decision=response.decision,
        summary=response.summary,
        status=response.status,
        validations_passed=getattr(response, "validations_passed", []) or [],
        validations_failed=getattr(response, "validations_failed", []) or [],
        findings=getattr(response, "findings", []) or [],
        request_for_claude=getattr(response, "request_for_claude", "") or "",
        error_code=getattr(response, "error_code", "") or "",
        error_detail=getattr(response, "error_detail", "") or "",
        receipt_path=receipt_path,
    )
