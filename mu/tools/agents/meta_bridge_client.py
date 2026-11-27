#!/usr/bin/env python3
"""Structured meta-bridge supervisor client.

Provides a reusable Python API for invoking the pre-commit supervisor
without shell+grep parsing. Uses the real Python API (run_meta_bridge)
directly, with lock-aware retry and structured result handling.

Never greps output text. Never mistakes template enum strings for
real decisions.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import time
import types
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

_EXECUTOR_COMMON_SUPERVISOR_IMPORT_SYMBOLS = frozenset({
    "agent_bus_path",
    "bridge_config_path",
    "ensure_bridge_config_path",
    "resolve_agent_bus_dir",
    "ValidationBudgetError",
    "read_validation_schedule_transport",
    "validation_parent_remaining",
    "admit_stage_budget",
    "decode_stage_budget",
    "ensure_not_agent_review_mode",
    # Every other module-level executor_common import of meta_bridge_supervisor.
    "ExecutorCommonError",
    "bridge_agent_display_name",
    "configured_role_agents",
    "emit_pipeline_agent_event",
    "is_agent_bus_runtime_path",
    "load_executor_config",
    "normalize_wave_id",
    "packet_status_is_completed",
    "read_control_plane_packet_status",
})
_VALIDATION_EXECUTION_SUPERVISOR_SYMBOLS = ("pytest_command", "pytest_timeout", "run_validation", "run_pytest")
_SUPERVISOR_DEPENDENCY_SYMBOLS = {
    "executor_common": _EXECUTOR_COMMON_SUPERVISOR_IMPORT_SYMBOLS,
    "validation_execution": _VALIDATION_EXECUTION_SUPERVISOR_SYMBOLS,
}


def _refresh_executor_common_before_supervisor_import(supervisor_dir: Path) -> None:
    """Keep the existing caller entry point at the complete dependency boundary."""
    prepare_supervisor_execution_api(supervisor_dir)


def _supervisor_dependency_paths(supervisor_dir: Path) -> dict[str, Path]:
    executors = supervisor_dir.parent / "executors"
    return {name: (executors / (name + ".py")).resolve()
            for name in ("executor_common", "validation_execution")}


def _registered_from(module: Any, path: Path) -> bool:
    source_path = getattr(module, "__file__", None)
    return bool(source_path) and Path(source_path).resolve() == path


def _executed_bound_code(module: Any, code: types.CodeType) -> bool:
    """Whether a registered namespace executed exactly what its bound bytes denote.

    Each dependency keeps the module code object its own import frame ran
    (``EXECUTED_MODULE_CODE``), whichever loader supplied it. Equality with the
    code the bound bytes compile to is the provenance test: a timestamp cache of
    other source runs, and so records, other code. A missing witness (a baseline
    module) proves nothing. Symbol compatibility and self-reported disk hashes
    never substitute for this comparison.
    """
    witness = getattr(module, "__dict__", {}).get("EXECUTED_MODULE_CODE")
    return type(witness) is types.CodeType and witness == code


def _retained_supervisor_dependencies(previous: dict[str, Any], code: dict[str, types.CodeType],
                                      absent: object) -> tuple[str, ...]:
    """Registered dependencies a newly imported supervisor may keep, as a pair.

    executor_common is kept only when it executed its bound code and exposes every
    supervisor import. A missing validation module is then executed against that
    owner, so modules that already imported it keep their class and exception
    identity. A present validation module is kept only when it too executed its
    bound code, is complete and consumes that exact owner; any other registered
    pair is executed again as a whole from the bound bytes.
    """
    def proven(name: str) -> bool:
        module = previous[name]
        return (module is not absent and _executed_bound_code(module, code[name])
                and all(callable(getattr(module, symbol, None))
                        for symbol in _SUPERVISOR_DEPENDENCY_SYMBOLS[name]))

    if not proven("executor_common"):
        return ()
    validation = previous["validation_execution"]
    if validation is absent:
        return ("executor_common",)
    if proven("validation_execution") and getattr(validation, "common", None) is previous["executor_common"]:
        return ("executor_common", "validation_execution")
    return ()


def prepare_supervisor_execution_api(supervisor_dir: Path, *, retain_proven: bool = False) -> None:
    """Execute both dependencies from bound bytes as one handoff transaction.

    The client handoff executes the pair every time. A newly imported supervisor
    passes ``retain_proven=True``: when a baseline client callable is cached it is
    the only current code that runs, and it keeps only a registered pair proven to
    have executed its bound code. A stale owner is therefore replaced even when its
    API is symbol-compatible, while a proven pair keeps its class identity.
    Existing executor callables retain their original module. No process-wide
    reload, role override, guard suppression or review restart occurs here. Disk
    hashes reported by imported modules are diagnostics, never execution
    provenance: even -B can consume an existing same-size/same-timestamp
    bytecode cache.
    """
    executors = supervisor_dir.parent / "executors"
    paths = _supervisor_dependency_paths(supervisor_dir)
    absent = object()
    previous = {name: sys.modules.get(name, absent) for name in paths}
    # Refuse either foreign owner before publishing either replacement.
    for name, module in previous.items():
        if module is not absent and not _registered_from(module, paths[name]):
            raise MetaBridgeClientError(f"{name} module has an unexpected source")
    sources = {name: path.read_bytes() for name, path in paths.items()}
    # dont_inherit: compile exactly as the import system does, so this client's
    # own __future__ flags never alter what the bound dependency bytes denote.
    code = {name: compile(sources[name], str(path), "exec", dont_inherit=True)
            for name, path in paths.items()}
    retained = _retained_supervisor_dependencies(previous, code, absent) if retain_proven else ()
    if str(executors) not in sys.path:
        sys.path.insert(0, str(executors))
    current = {name: previous[name] for name in retained}
    try:
        for name, path in paths.items():
            if name in current:
                continue
            spec = importlib.util.spec_from_file_location(name, path)
            if spec is None or spec.loader is None:
                raise MetaBridgeClientError(f"Cannot refresh {name}: no loader for {path}")
            module = importlib.util.module_from_spec(spec)
            current[name] = module
            sys.modules[name] = module
            # Publish common first so validation consumes this exact owner.
            # Never ask a bytecode loader to decide which source executed.
            exec(code[name], module.__dict__)
        for name, symbols in _SUPERVISOR_DEPENDENCY_SYMBOLS.items():
            missing = sorted(symbol for symbol in symbols if not callable(getattr(current[name], symbol, None)))
            if missing:
                raise MetaBridgeClientError(f"Refreshed {name} missing required symbols: {missing}")
        if current["validation_execution"].common is not current["executor_common"]:
            raise MetaBridgeClientError("Validation execution changed its common module owner")
        for name, path in paths.items():
            if sys.modules.get(name) is not current[name] or path.read_bytes() != sources[name]:
                raise MetaBridgeClientError(f"{name} source changed during refresh")
            if not _executed_bound_code(current[name], code[name]):
                raise MetaBridgeClientError(f"{name} has no execution witness for its bound bytes")
    except BaseException:
        # Restore the entire pair, including absence, on failure or interruption.
        # Old callable namespaces were never mutated, including their classes.
        for name, module in previous.items():
            if module is absent:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        raise


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
    bus_dir: str | Path | None = None,
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
        supervisor_dir_path = Path(__file__).resolve().parent
        supervisor_dir = str(supervisor_dir_path)
        if supervisor_dir not in sys.path:
            sys.path.insert(0, supervisor_dir)
        _refresh_executor_common_before_supervisor_import(supervisor_dir_path)
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
                bus_dir=bus_dir,
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

    # Reject incomplete envelopes before decision validation or any receipt-capable
    # branch can mint commit authority.
    _required_attrs = ("decision", "summary", "status")
    for attr in _required_attrs:
        if not hasattr(response, attr) or getattr(response, attr) is None:
            raise MetaBridgeClientError(
                f"Supervisor response missing required field: {attr}"
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
            exact_receipt_path = write_pre_commit_receipt(
                response,
                package_path,
                bus_dir=bus_dir,
            )
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
