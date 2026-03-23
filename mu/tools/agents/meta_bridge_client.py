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


def _validate_decision(decision: str) -> None:
    """Reject template enum placeholders and empty decisions."""
    if not decision:
        raise MetaBridgeClientError("Supervisor returned empty decision")
    if _TEMPLATE_ENUM_PATTERN in decision:
        raise MetaBridgeClientError(
            f"Supervisor returned pipe-delimited template enum, not a real decision: {decision[:100]}"
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

    # Get actual receipt path from supervisor response
    # The supervisor writes the receipt and returns the path
    receipt_path = ""
    if response.decision in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
        # Check if the canonical receipt was written
        import subprocess as _sp
        try:
            toplevel = _sp.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True,
                cwd=str(package_path.resolve().parent),
            ).stdout.strip()
            canonical = Path(toplevel) / ".agent_bus" / "meta" / "pre_commit_receipt.json"
            if canonical.exists():
                receipt_path = str(canonical.relative_to(Path(toplevel)))
            else:
                raise MetaBridgeClientError(
                    f"Supervisor returned {response.decision} but no receipt written at {canonical}"
                )
        except _sp.CalledProcessError:
            receipt_path = ".agent_bus/meta/pre_commit_receipt.json"

    return SupervisorResult(
        decision=response.decision,
        summary=response.summary,
        status=response.status,
        validations_passed=response.validations_passed,
        validations_failed=response.validations_failed,
        findings=response.findings,
        request_for_claude=response.request_for_claude,
        error_code=response.error_code,
        error_detail=response.error_detail,
        receipt_path=receipt_path,
    )
