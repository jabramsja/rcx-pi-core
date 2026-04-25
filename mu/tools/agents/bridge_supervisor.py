#!/usr/bin/env python3
"""Minimal turn-based bridge between a writer agent and a reviewer agent."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from bridge_adapters import BridgeAdapterError, _prepare_adapter_env, get_adapter, load_bridge_config, run_adapter
from bridge_migrations import MIGRATIONS, MigrationVersionError, run_pending_migrations

BUS_DIR_NAME = ".agent_bus"
DB_NAME = "bridge.db"
CONFIG_NAME = "bridge_config.json"
PROMPTS_DIR = "prompts"
RAW_DIR = "raw"
RENDERED_DIR = "rendered"
VALIDATIONS_DIR = "validations"
STATE_IGNORE_PREFIXES = (
    ".agent_bus/",
    ".git/",
    ".scratch/",
    "__pycache__/",
    ".venv/",
    "venv/",
    "node_modules/",
)
JSON_SCHEMA_STUB = json.dumps(
    {
        "job_id": "string",
        "turn_id": "string",
        "agent_role": "reader|reviewer",
        "decision": "GO|NO_GO|REQUEST_CHANGES|QUESTION|STALE|ERROR|SYNTHETIC",
        "summary": "string",
        "touched_files_claimed": ["string"],
        "findings": [
            {
                "class": "DEFECT|POLICY_BOUND|DOC_ACCURACY",
                "severity": "low|medium|high|critical",
                "title": "string",
                "file": "string",
                "line_start": 1,
                "line_end": 1,
                "evidence_cmd": "string",
                "evidence_result": "string",
                "status": "new|addressed|persisting|blocked",
            }
        ],
        "validations_claimed": [
            {
                "command": "string",
                "result": "pass|fail|not_run",
            }
        ],
        "request_for_next_agent": "string",
    },
    indent=2,
)
ENVELOPE_RE = re.compile(
    r"BEGIN_AGENT_ENVELOPE\s*(?:```(?:json)?\s*)?(\{.*?\})\s*(?:```\s*)?END_AGENT_ENVELOPE",
    re.DOTALL,
)
_STDERR_SENTINEL = "\n[stderr]\n"
AUTHORIZED_DECISIONS = frozenset(
    {"GO", "NO_GO", "REQUEST_CHANGES", "QUESTION", "STALE", "ERROR", "SYNTHETIC"}
)
# Fail closed on direct bridge calls before the full adapter timeout elapses.
# This keeps reviewer/reader turns from sitting silently for 20 minutes when no
# outer executor watchdog is present.
BRIDGE_MAX_TURN_WALL_TIME_S = 300.0
BRIDGE_ZERO_OUTPUT_TIMEOUT_S = 1200.0


def _resolve_timeout_override(name: str, default: float) -> float:
    """Read a positive float timeout override from the environment."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _bridge_max_turn_wall_time_override_s() -> float | None:
    """Read the executor-provided bridge turn budget, when explicitly set."""
    raw = os.getenv("RCX_BRIDGE_MAX_TURN_WALL_TIME_S", "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _bridge_turn_timeout_s(adapter_timeout_s: int) -> float:
    """Resolve the bridge turn timeout budget for a reader/reviewer adapter."""
    override = _bridge_max_turn_wall_time_override_s()
    if override is not None:
        return override
    return min(float(adapter_timeout_s), BRIDGE_MAX_TURN_WALL_TIME_S)


def _lock_metadata_payload(holder: str, lock_path: Path) -> dict[str, Any]:
    return {
        "holder": holder,
        "pid": os.getpid(),
        "lock_path": str(lock_path),
        "acquired_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def _write_lock_metadata(fp: Any, *, holder: str, lock_path: Path) -> None:
    fp.seek(0)
    json.dump(_lock_metadata_payload(holder, lock_path), fp, sort_keys=True)
    fp.write("\n")
    fp.truncate()
    fp.flush()


def _read_lock_metadata(lock_path: Path) -> dict[str, Any] | None:
    try:
        raw = lock_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _describe_lock_metadata(lock_path: Path) -> str | None:
    payload = _read_lock_metadata(lock_path)
    if not payload:
        return None
    parts: list[str] = []
    holder = payload.get("holder")
    if isinstance(holder, str) and holder:
        parts.append(f"holder={holder}")
    pid = payload.get("pid")
    if isinstance(pid, int):
        parts.append(f"pid={pid}")
    acquired_at = payload.get("acquired_at_utc")
    if isinstance(acquired_at, str) and acquired_at:
        parts.append(f"acquired_at_utc={acquired_at}")
    return ", ".join(parts) if parts else None


# Import canonical control-surface file set from single source of truth.
try:
    _cs_checks_dir = str(Path(__file__).resolve().parent.parent / "checks")
    if _cs_checks_dir not in sys.path:
        sys.path.insert(0, _cs_checks_dir)
    from check_control_surface_invariants import CONTROL_SURFACE_FILES as _CONTROL_SURFACE_FILES
except ImportError:
    _CONTROL_SURFACE_FILES = frozenset({
        "mu/tools/executors/phase_b_executor.py",
        "mu/tools/executors/commit_executor.py",
        "mu/tools/agents/meta_bridge_supervisor.py",
    })

_CONTROL_SURFACE_PROOF_OBLIGATIONS = """\

## CONTROL-SURFACE REVIEW MODE (activated — touched files are in the Phase B / commit authority chain)

You MUST inspect the following cross-file invariants. Do NOT greenlight on summary/diff evidence alone.

Proof obligations:
1. **Implementer surface**: Read `mu/tools/executors/phase_b_implementer.py`. Verify it uses `bridge_adapters.run_adapter()` directly. It must NOT invoke `bridge_supervisor.py review` (that is review-only).
2. **Bridge loop mechanics**: Read the bridge convergence loop in `mu/tools/executors/phase_b_executor.py`. Verify that `REQUEST_CHANGES` / `NO_GO` re-invoke the implementer with findings BEFORE the next bridge round. `QUESTION` must fail closed (not loop).
3. **Receipt authority chain**: Trace the canonical live path only: `mu/tools/agents/meta_bridge_supervisor.py::write_pre_commit_receipt()` → return value → `mu/tools/agents/meta_bridge_client.py::run_meta_bridge_package()` → `receipt_path` field → `mu/tools/executors/phase_b_executor.py::prepare_commit_handoff()` → `mu/tools/executors/commit_executor.py` verification. The per-invocation receipt path must be exact, not discovered by sorting a directory.
4. **Canonical hook receipt preserved**: `mu/tools/agents/meta_bridge_supervisor.py::write_pre_commit_receipt()` must still write the canonical receipt for hook compatibility. But the EXECUTOR flow must use the per-invocation receipt, not canonical. Do not use legacy/nonexistent aliases when verifying this chain.
5. **No manual fallback in docs**: Protocol docs must not present manual git push/PR/merge as a normal commit path. Only narrow BOOTSTRAP_PHASE_B_EXCEPTION is allowed.

Adjacent files you MUST read (not just the diff):
- `mu/tools/executors/phase_b_executor.py` (bridge loop + handoff)
- `mu/tools/executors/phase_b_implementer.py` (invocation surface)
- `mu/tools/agents/meta_bridge_client.py` (receipt capture)
- `mu/tools/agents/meta_bridge_supervisor.py` (receipt writer + validation gates)
- `mu/tools/executors/commit_executor.py` (receipt verifier)

If you cannot verify any obligation from the available evidence, emit it as a CRITICAL finding — do not skip it."""


def _touches_control_surface(changed_files_str: str) -> bool:
    """Check if any changed file is a control-surface file."""
    files = [f.strip() for f in changed_files_str.split(",") if f.strip()]
    return bool(set(files) & _CONTROL_SURFACE_FILES)


def _build_code_review_instructions(
    changed_actual: str,
    staged: str,
    unstaged: str,
    validation_results_text: str,
    reader_summary: str,
    diff_text: str,
) -> str:
    # Activate control-surface review mode when relevant files are touched
    cs_section = ""
    if _touches_control_surface(changed_actual):
        cs_section = _CONTROL_SURFACE_PROOF_OBLIGATIONS

    return f"""\
Review actual live candidate state, not the reader summary.

Evidence available:
- CHANGED_FILES_ACTUAL: {changed_actual}
- STAGED_FILES: {staged}
- UNSTAGED_FILES: {unstaged}
- VALIDATION_RESULTS: {validation_results_text}
- READER_OUTPUT: {reader_summary}

Staged diff (up to 10000 chars):
{diff_text}

Required review scope:
- red-team ONLY the files listed in CHANGED_FILES_ACTUAL above
- if UNSTAGED_FILES says "out of scope", do NOT read, review, or issue findings about unstaged files — they belong to other waves
- red-team adjacent high-risk files implicated by the in-scope touches
- classify findings as DEFECT, POLICY_BOUND, or DOC_ACCURACY

Exhaustive enumeration requirement:
- Do NOT stop at the first finding. Enumerate ALL issues before issuing your verdict.
- For state machines / control flow: trace every state transition and check what happens if a crash occurs before, during, and after each transition.
- For recovery paths: verify idempotency, primary key conflicts, format compatibility, and missing data.
- For new APIs: verify error handling, edge cases, and backward compatibility.
- Issue NO_GO only after you have listed every finding you can identify, not after finding just one.{cs_section}"""


def _build_design_deliberation_instructions(
    validation_results_text: str,
    reader_summary: str,
) -> str:
    return f"""\
THIS IS A DESIGN DELIBERATION, NOT A CODE REVIEW.

You are reviewing a DESIGN PROPOSAL — evaluate it on its design merits, trade-offs, feasibility, and completeness.

DO NOT:
- Read the local codebase to find implementation bugs
- Run SQLite probes or Python repro scripts against local files
- Red-team source files for crash recovery, state machines, or edge cases
- Treat this as a code review or implementation pre-review

DO:
- Evaluate the design choices, architecture, and trade-offs in the proposal
- Search the web to validate claims about external tools and their capabilities
- Challenge whether the right features are being stolen from the right tools
- Identify missing design considerations, architectural risks, or scope gaps
- Give your independent opinion on priorities, phasing, and what to build vs skip
- If the proposal references external tools/repos, look them up and verify the claims

Evidence available:
- READER_OUTPUT: {reader_summary}
- VALIDATION_RESULTS: {validation_results_text}

Classify findings as DEFECT (design flaw), POLICY_BOUND (needs founder decision), or DOC_ACCURACY (factual error in proposal)."""


class BridgeError(RuntimeError):
    """Raised when supervisor execution cannot continue."""


class _BridgeLock:
    """Exclusive file lock for single-supervisor enforcement."""

    def __init__(self, lock_path: Path):
        self._lock_path = lock_path
        self._fp: Any = None

    def __enter__(self) -> "_BridgeLock":
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self._lock_path, os.O_RDWR | os.O_CREAT, 0o644)
        self._fp = os.fdopen(fd, "r+", encoding="utf-8")
        try:
            fcntl.flock(self._fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            self._fp.close()
            detail = _describe_lock_metadata(self._lock_path)
            detail_suffix = f" Lock metadata: {detail}." if detail else ""
            raise BridgeError(
                "Another bridge supervisor is already running. "
                f"Wait for it to finish.{detail_suffix} "
                "The lockfile path persists by design; only remove "
                ".agent_bus/bridge.lock if a lock probe shows no process "
                "holds the flock."
            )
        _write_lock_metadata(
            self._fp,
            holder="bridge_supervisor",
            lock_path=self._lock_path,
        )
        return self

    def __exit__(self, *exc: object) -> bool:
        if self._fp:
            try:
                # Clear metadata while still holding flock — prevents stale PID
                # appearance after release. File stays (inode-stable for flock).
                self._fp.seek(0)
                self._fp.truncate()
                self._fp.flush()
            except OSError:
                pass  # best-effort cleanup
            try:
                fcntl.flock(self._fp, fcntl.LOCK_UN)
            finally:
                self._fp.close()
                self._fp = None
        return False


@dataclass(frozen=True)
class BridgePaths:
    repo_root: Path
    bus_dir: Path
    db_path: Path
    config_path: Path
    prompts_dir: Path
    raw_dir: Path
    rendered_dir: Path
    validations_dir: Path


@dataclass(frozen=True)
class RepoState:
    head_sha: str
    staged_sha: str
    unstaged_sha: str
    untracked_sha: str
    state_sha: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return text or "job"


def bridge_paths(repo_root: Path) -> BridgePaths:
    bus_dir = repo_root / BUS_DIR_NAME
    return BridgePaths(
        repo_root=repo_root,
        bus_dir=bus_dir,
        db_path=bus_dir / DB_NAME,
        config_path=bus_dir / CONFIG_NAME,
        prompts_dir=bus_dir / PROMPTS_DIR,
        raw_dir=bus_dir / RAW_DIR,
        rendered_dir=bus_dir / RENDERED_DIR,
        validations_dir=bus_dir / VALIDATIONS_DIR,
    )


def ensure_runtime_dirs(paths: BridgePaths) -> None:
    for path in (paths.bus_dir, paths.prompts_dir, paths.raw_dir, paths.rendered_dir, paths.validations_dir):
        path.mkdir(parents=True, exist_ok=True)


def open_db(paths: BridgePaths) -> sqlite3.Connection:
    ensure_runtime_dirs(paths)
    conn = sqlite3.connect(paths.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def open_db_readonly(paths: BridgePaths) -> sqlite3.Connection:
    """Open the bridge DB read-only: no runtime dirs, no WAL, no writes."""
    conn = sqlite3.connect(f"file:{paths.db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _check_future_version(db_path: Path) -> None:
    """Raise MigrationVersionError if the DB is from a newer version.

    Opens the DB in read-only mode (SQLite URI ?mode=ro) so we never
    trigger WAL recovery, journal changes, or any file mutation.
    Path is URI-encoded to handle reserved chars (?, #, %) in directory names.
    """
    if not db_path.exists():
        return  # fresh DB — safe to proceed
    from urllib.parse import quote
    encoded_path = quote(str(db_path), safe="/:")
    try:
        conn = sqlite3.connect(f"file:{encoded_path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return  # can't open read-only (permissions, etc.) — let init_db handle it
    try:
        row = conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='schema_version'",
        ).fetchone()
        if row[0] == 0:
            return  # pre-migration DB — safe to proceed
        ver_row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
        if ver_row is not None and ver_row[0] > len(MIGRATIONS):
            raise MigrationVersionError(
                f"Database schema version ({ver_row[0]}) is newer than this code "
                f"supports ({len(MIGRATIONS)}). Upgrade the bridge code."
            )
    finally:
        conn.close()


def init_db(paths: BridgePaths, *, verbose: bool = False) -> None:
    _check_future_version(paths.db_path)
    ensure_runtime_dirs(paths)
    schema = (SCRIPT_DIR / "bridge_schema.sql").read_text(encoding="utf-8")
    with open_db(paths) as conn:
        conn.executescript(schema)
        conn.commit()
        applied = run_pending_migrations(conn, verbose=verbose)
        if applied and verbose:
            print(f"  applied {applied} migration(s)")
    example = SCRIPT_DIR / "bridge_config.example.json"
    if example.exists() and not paths.config_path.exists():
        shutil.copyfile(example, paths.config_path)


def git_output(repo_root: Path, args: list[str], *, text: bool = True) -> str | bytes:
    result = subprocess.run(["git", *args], cwd=repo_root, capture_output=True, check=False)
    if result.returncode != 0:
        stderr = (result.stderr.decode("utf-8", errors="replace") if not text else result.stderr.decode("utf-8", errors="replace"))
        raise BridgeError(f"git {' '.join(args)} failed: {stderr.strip()}")
    if text:
        return result.stdout.decode("utf-8", errors="replace")
    return result.stdout


def _hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _iter_untracked_files(repo_root: Path) -> list[Path]:
    output = git_output(repo_root, ["ls-files", "--others", "--exclude-standard"])
    paths: list[Path] = []
    for raw in output.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        normalized = raw.replace("\\", "/")
        if any(normalized == prefix.rstrip("/") or normalized.startswith(prefix) for prefix in STATE_IGNORE_PREFIXES):
            continue
        path = repo_root / raw
        if path.is_file():
            paths.append(path)
    return sorted(paths)


def compute_repo_state(repo_root: Path) -> RepoState:
    head_sha = git_output(repo_root, ["rev-parse", "HEAD"]).strip()
    staged_sha = _hash_bytes(git_output(repo_root, ["diff", "--cached", "--binary"], text=False))
    unstaged_sha = _hash_bytes(git_output(repo_root, ["diff", "--binary"], text=False))

    hasher = hashlib.sha256()
    for path in _iter_untracked_files(repo_root):
        rel = path.relative_to(repo_root).as_posix().encode("utf-8")
        hasher.update(rel)
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    untracked_sha = hasher.hexdigest()

    state_sha = hashlib.sha256(
        f"{head_sha}|{staged_sha}|{unstaged_sha}|{untracked_sha}".encode("utf-8")
    ).hexdigest()
    return RepoState(
        head_sha=head_sha,
        staged_sha=staged_sha,
        unstaged_sha=unstaged_sha,
        untracked_sha=untracked_sha,
        state_sha=state_sha,
    )


def changed_files(repo_root: Path, *, staged: bool) -> list[str]:
    args = ["diff", "--cached", "--name-only"] if staged else ["diff", "--name-only"]
    output = git_output(repo_root, args)
    files = [line for line in output.splitlines() if line.strip()]
    if not staged:
        for path in _iter_untracked_files(repo_root):
            files.append(path.relative_to(repo_root).as_posix())
    return files


def _scoped_review_targets_from_task_text(repo_root: Path, task_text: str) -> list[str]:
    """Prefer explicit repo-local paths from the review task over all dirty files."""
    repo_root_resolved = repo_root.resolve()
    targets: list[str] = []
    seen: set[str] = set()
    for token in re.findall(r"`([^`\n]+)`", task_text):
        candidate = Path(token)
        try:
            resolved = candidate.resolve() if candidate.is_absolute() else (repo_root / candidate).resolve()
            if not resolved.is_file() or not resolved.is_relative_to(repo_root_resolved):
                continue
            rel_path = resolved.relative_to(repo_root_resolved).as_posix()
        except (OSError, ValueError):
            continue
        if rel_path in seen:
            continue
        seen.add(rel_path)
        targets.append(rel_path)
    return targets


REVIEWER_DIFF_MAX_CHARS = 10000


def staged_diff_content(repo_root: Path, max_chars: int = REVIEWER_DIFF_MAX_CHARS) -> str:
    """Return staged diff content, truncated if needed."""
    try:
        diff = git_output(repo_root, ["diff", "--cached"])
    except BridgeError:
        return "(error reading staged diff)"
    if not diff.strip():
        return "(no staged changes)"
    if len(diff) > max_chars:
        return diff[:max_chars] + f"\n\n... [truncated at {max_chars} chars] ..."
    return diff


# -- Validation command whitelist (shell injection prevention) --
# Each entry maps a known command string to its tokenized argv form.
# Only whitelisted commands may be executed via --check or built-in defaults.
# To add a new validation command: add it here AND in the test suite.
VALIDATION_WHITELIST: dict[str, list[str]] = {
    # Built-in defaults
    "git status --short": ["git", "status", "--short"],
    "python3 tools/checks/enforce_l4_execution_contract.py --staged": [
        "python3", "tools/checks/enforce_l4_execution_contract.py", "--staged",
    ],
    # Common acceptance checks (tools/checks/)
    "bash tools/checks/check_docs_consistency.sh": [
        "bash", "tools/checks/check_docs_consistency.sh",
    ],
    "bash tools/checks/check_test_speed.sh": [
        "bash", "tools/checks/check_test_speed.sh",
    ],
    "bash tools/checks/check_test_theater.sh": [
        "bash", "tools/checks/check_test_theater.sh",
    ],
    "bash tools/checks/check_test_theater_js.sh": [
        "bash", "tools/checks/check_test_theater_js.sh",
    ],
    "bash tools/checks/check_js_debt.sh": [
        "bash", "tools/checks/check_js_debt.sh",
    ],
    "bash tools/checks/check_untracked_artifacts.sh": [
        "bash", "tools/checks/check_untracked_artifacts.sh",
    ],
    "bash tools/checks/check_agent_review_needed.sh": [
        "bash", "tools/checks/check_agent_review_needed.sh",
    ],
    "bash tools/checks/enforce_tracker_sync.sh": [
        "bash", "tools/checks/enforce_tracker_sync.sh",
    ],
    "python3 tools/checks/check_host_semantics_ratchet.py": [
        "python3", "tools/checks/check_host_semantics_ratchet.py",
    ],
    "python3 tools/checks/check_gate_behavioral_pairs.py": [
        "python3", "tools/checks/check_gate_behavioral_pairs.py",
    ],
    "python3 tools/checks/check_theater_risk_ratchet.py": [
        "python3", "tools/checks/check_theater_risk_ratchet.py",
    ],
    "python3 tools/checks/check_seed_auto_execution_contract.py": [
        "python3", "tools/checks/check_seed_auto_execution_contract.py",
    ],
    "python3 tools/checks/check_simulated_production_logic.py": [
        "python3", "tools/checks/check_simulated_production_logic.py",
    ],
    "python3 tools/checks/check_agent_runtime.py": [
        "python3", "tools/checks/check_agent_runtime.py",
    ],
    # Top-level audit/tool scripts
    "./tools/pre-push-fast": ["./tools/pre-push-fast"],
    "./tools/audit_fast.sh": ["./tools/audit_fast.sh"],
    "./tools/audit_all.sh": ["./tools/audit_all.sh"],
    "./tools/pre-commit-doc-check": ["./tools/pre-commit-doc-check"],
    "./tools/debt_dashboard.sh": ["./tools/debt_dashboard.sh"],
    # Doc tools
    "python3 -m tools.docs.add_doc_headers --check": [
        "python3", "-m", "tools.docs.add_doc_headers", "--check",
    ],
    "python3 tools/docs/docs_sync_report.py --check": [
        "python3", "tools/docs/docs_sync_report.py", "--check",
    ],
    # Pytest invocations (common patterns)
    "pytest tests/parity/test_seed_loading_parity.py -v": [
        "pytest", "tests/parity/test_seed_loading_parity.py", "-v",
    ],
    "pytest tests/parity/test_cross_substrate_constants.py -v": [
        "pytest", "tests/parity/test_cross_substrate_constants.py", "-v",
    ],
    # JS parity
    "node mu/host/js/eval_step.js": ["node", "mu/host/js/eval_step.js"],
}


def resolve_validation_command(command: str) -> list[str]:
    """Resolve a validation command string to a safe argv list via whitelist.

    Raises BridgeError if the command is not in the whitelist.
    """
    argv = VALIDATION_WHITELIST.get(command)
    if argv is not None:
        return argv
    raise BridgeError(
        f"Validation command not in whitelist: {command!r}\n"
        f"Add it to VALIDATION_WHITELIST in bridge_supervisor.py to allow execution.\n"
        f"Known commands: {sorted(VALIDATION_WHITELIST.keys())}"
    )


def default_validation_commands(repo_root: Path, acceptance_checks: list[str]) -> list[str]:
    commands = ["git status --short"]
    enforcer = repo_root / "tools" / "checks" / "enforce_l4_execution_contract.py"
    if enforcer.exists():
        commands.append("python3 tools/checks/enforce_l4_execution_contract.py --staged")
    for check in acceptance_checks:
        if check not in commands:
            commands.append(check)
    return commands


def summarize_validation_output(output: str, exit_code: int) -> str:
    if not output.strip():
        return "pass" if exit_code == 0 else f"fail ({exit_code})"
    first = next((line.strip() for line in output.splitlines() if line.strip()), "")
    prefix = "pass" if exit_code == 0 else f"fail ({exit_code})"
    return f"{prefix}: {first[:160]}".strip()


def run_validations(
    paths: BridgePaths,
    conn: sqlite3.Connection,
    *,
    job_id: str,
    turn_id: str,
    acceptance_checks: list[str],
) -> list[dict[str, Any]]:
    commands = default_validation_commands(paths.repo_root, acceptance_checks)
    out_dir = paths.validations_dir / job_id / turn_id
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for index, command in enumerate(commands, start=1):
        try:
            argv = resolve_validation_command(command)
        except BridgeError as exc:
            # Unknown command: record as validation failure instead of
            # propagating, which would strand the job in READER_RUNNING.
            exit_code = 1
            output = f"[error] {exc}"
            output_path = out_dir / f"validation-{index}.txt"
            output_path.write_text(output, encoding="utf-8")
            validation_id = f"{turn_id}-validation-{index}"
            summary = summarize_validation_output(output, exit_code)
            conn.execute(
                """
                INSERT INTO validations(validation_id, job_id, turn_id, command, exit_code, result_summary, output_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (validation_id, job_id, turn_id, command, exit_code, summary, str(output_path), utc_now()),
            )
            results.append(
                {
                    "command": command,
                    "exit_code": exit_code,
                    "result_summary": summary,
                    "output_path": str(output_path),
                }
            )
            continue
        try:
            validation_env = {**os.environ, "PYTHONHASHSEED": "0"}
            proc = subprocess.run(
                argv,
                cwd=paths.repo_root,
                env=validation_env,
                text=True,
                capture_output=True,
                check=False,
                timeout=300,
            )
            exit_code = proc.returncode
            output = (proc.stdout or "") + ("\n[stderr]\n" + proc.stderr if proc.stderr else "")
        except subprocess.TimeoutExpired:
            exit_code = -1
            output = f"[error] validation command timed out after 300s: {command}"
        except FileNotFoundError:
            exit_code = 127
            output = f"[error] command not found: {argv[0]}"
        except OSError as exc:
            exit_code = 126
            output = f"[error] failed to execute: {exc}"
        output_path = out_dir / f"validation-{index}.txt"
        output_path.write_text(output, encoding="utf-8")
        validation_id = f"{turn_id}-validation-{index}"
        summary = summarize_validation_output(output, exit_code)
        conn.execute(
            """
            INSERT INTO validations(validation_id, job_id, turn_id, command, exit_code, result_summary, output_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (validation_id, job_id, turn_id, command, exit_code, summary, str(output_path), utc_now()),
        )
        results.append(
            {
                "command": command,
                "exit_code": exit_code,
                "result_summary": summary,
                "output_path": str(output_path),
            }
        )
    conn.commit()
    return results


def load_template(name: str) -> Template:
    return Template((SCRIPT_DIR / "templates" / name).read_text(encoding="utf-8"))


def read_job(conn: sqlite3.Connection, job_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    if row is None:
        raise BridgeError(f"Unknown bridge job '{job_id}'")
    return row


def latest_turn(conn: sqlite3.Connection, job_id: str, *, role: str | None = None) -> sqlite3.Row | None:
    query = "SELECT * FROM turns WHERE job_id = ?"
    params: list[Any] = [job_id]
    if role is not None:
        query += " AND agent_role = ?"
        params.append(role)
    query += " ORDER BY started_at DESC, rowid DESC LIMIT 1"
    return conn.execute(query, params).fetchone()


def latest_envelope(conn: sqlite3.Connection, job_id: str, *, role: str | None = None) -> dict[str, Any] | None:
    turn = latest_turn(conn, job_id, role=role)
    if turn is None or not turn["envelope_json"]:
        return None
    return json.loads(turn["envelope_json"])


def write_prompt(paths: BridgePaths, job_id: str, turn_id: str, content: str) -> Path:
    prompt_dir = paths.prompts_dir / job_id
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = prompt_dir / f"{turn_id}.txt"
    prompt_path.write_text(content, encoding="utf-8")
    return prompt_path


def write_raw_output(paths: BridgePaths, job_id: str, turn_id: str, content: str) -> Path:
    raw_dir = paths.raw_dir / job_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_path = raw_dir / f"{turn_id}.txt"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def parse_envelope(output: str) -> dict[str, Any]:
    stdout_only = output
    stderr_only = ""
    has_stderr = False
    if _STDERR_SENTINEL in output:
        stdout_only, _, stderr_only = output.partition(_STDERR_SENTINEL)
        has_stderr = True
    elif output.startswith("[stderr]\n"):
        stdout_only = ""
        stderr_only = output[len("[stderr]\n"):]
        has_stderr = True
    if ENVELOPE_RE.search(stdout_only):
        output = stdout_only
    elif has_stderr and ENVELOPE_RE.search(stderr_only):
        raise BridgeError(
            "Agent envelope found only in stderr, not in authoritative stdout. "
            "Refusing stderr-sourced envelope."
        )
    matches = list(ENVELOPE_RE.finditer(output))
    if not matches:
        raise BridgeError("Agent output missing BEGIN_AGENT_ENVELOPE / END_AGENT_ENVELOPE block")
    envelopes: list[dict[str, Any]] = []
    canonical_payloads: set[str] = set()
    required = {
        "job_id", "turn_id", "agent_role", "decision", "summary",
        "touched_files_claimed", "findings", "validations_claimed",
        "request_for_next_agent",
    }
    parse_errors: list[str] = []
    for index, match in enumerate(matches, start=1):
        try:
            envelope = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            # Codex emits the prompt template (with truncated strings) and
            # draft envelopes during reasoning.  Skip malformed entries and
            # only fail if NO valid envelope is found after the loop.
            parse_errors.append(f"Agent envelope #{index} is not valid JSON: {exc}")
            continue
        missing = required.difference(envelope)
        if missing:
            # Draft envelopes may omit required keys — skip, don't abort.
            continue
        decision = envelope["decision"]
        if decision not in AUTHORIZED_DECISIONS:
            # The live adapter transcript can contain the prompt template before
            # the model reply. Ignore only the pipe-delimited enum placeholder.
            if isinstance(decision, str) and "|" in decision:
                continue
            raise BridgeError(
                f"Agent envelope has invalid decision {decision!r}; "
                f"authorized decisions: {sorted(AUTHORIZED_DECISIONS)}"
            )
        envelopes.append(envelope)
        canonical_payloads.add(json.dumps(envelope, sort_keys=True, separators=(",", ":")))

    if not envelopes:
        if parse_errors:
            raise BridgeError(
                f"Agent output contained {len(matches)} envelope block(s) but none were valid. "
                f"Parse errors: {'; '.join(parse_errors[:3])}"
            )
        raise BridgeError("Agent output contained only non-authoritative template envelope blocks")

    if len(canonical_payloads) > 1:
        raise BridgeError("Agent output contains multiple differing envelope blocks; refusing ambiguous output")

    return envelopes[-1]


def _format_list(items: list[str]) -> str:
    return ", ".join(items) if items else "(none)"


def _validation_results_text(results: list[dict[str, Any]]) -> str:
    if not results:
        return "(none)"
    return "\n".join(f"- {item['command']} => {item['result_summary']}" for item in results)


def build_reader_prompt(conn: sqlite3.Connection, paths: BridgePaths, job: sqlite3.Row, round_no: int, state: RepoState) -> str:
    template = load_template("bridge_reader_prompt.txt")
    previous_reviewer = latest_envelope(conn, job["job_id"], role="reviewer") or {}
    acceptance_checks = json.loads(job["acceptance_checks_json"])
    payload = {
        "job_id": job["job_id"],
        "round_no": round_no,
        "task_text": job["task_text"],
        "wave_class": job["wave_class"] or "(unspecified)",
        "allow_edits": "true" if job["allow_edits"] else "false",
        "repo_root": str(paths.repo_root),
        "head_sha": state.head_sha,
        "state_sha": state.state_sha,
        "changed_files_actual": _format_list(changed_files(paths.repo_root, staged=False) + changed_files(paths.repo_root, staged=True)),
        "previous_reviewer_feedback": previous_reviewer.get("summary", "(none)"),
        "acceptance_checks": _format_list(acceptance_checks),
        "json_schema_stub": JSON_SCHEMA_STUB,
    }
    return template.safe_substitute(payload)


def build_reviewer_prompt(
    conn: sqlite3.Connection,
    paths: BridgePaths,
    job: sqlite3.Row,
    round_no: int,
    validation_results: list[dict[str, Any]],
    *,
    include_diff: bool = True,
) -> str:
    template = load_template("bridge_reviewer_prompt.txt")
    reader_envelope = latest_envelope(conn, job["job_id"], role="reader") or {}
    validation_text = _validation_results_text(validation_results)
    reader_summary = reader_envelope.get("summary", "(none)")
    if include_diff:
        diff_text = staged_diff_content(paths.repo_root)
        staged_list = changed_files(paths.repo_root, staged=True)
        unstaged_list = changed_files(paths.repo_root, staged=False)
        # When files are staged, scope the review to staged files only.
        # Unstaged files in a dirty worktree may be fenced-out (belonging
        # to other waves) and must not pollute the reviewer's scope.
        if staged_list:
            changed_actual = _format_list(staged_list)
            unstaged = "(out of scope — only staged files are under review)"
        else:
            changed_actual = _format_list(unstaged_list)
            unstaged = _format_list(unstaged_list)
        staged = _format_list(staged_list)
        review_mode_instructions = _build_code_review_instructions(
            changed_actual, staged, unstaged, validation_text, reader_summary, diff_text,
        )
    else:
        review_mode_instructions = _build_design_deliberation_instructions(
            validation_text, reader_summary,
        )
    # Inject prior-finding lifecycle context when available (round > 1)
    lifecycle_section = ""
    if round_no > 1:
        registry = rebuild_finding_registry(conn, job["job_id"])
        lifecycle_section = format_lifecycle_prompt_section(registry)
    payload = {
        "job_id": job["job_id"],
        "round_no": round_no,
        "task_text": job["task_text"],
        "wave_class": job["wave_class"] or "(unspecified)",
        "repo_root": str(paths.repo_root),
        "review_mode_instructions": review_mode_instructions,
        "json_schema_stub": JSON_SCHEMA_STUB,
        "prior_findings": lifecycle_section,
    }
    return template.safe_substitute(payload)


def record_turn(
    conn: sqlite3.Connection,
    *,
    turn_id: str,
    job_id: str,
    round_no: int,
    agent_role: str,
    status: str,
    decision: str,
    state_sha_start: str,
    state_sha_end: str,
    prompt_path: Path,
    raw_output_path: Path,
    envelope: dict[str, Any],
    started_at: str,
    finished_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO turns(
            turn_id, job_id, round_no, agent_role, status, decision,
            state_sha_start, state_sha_end, prompt_path, raw_output_path,
            envelope_json, started_at, finished_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            turn_id,
            job_id,
            round_no,
            agent_role,
            status,
            decision,
            state_sha_start,
            state_sha_end,
            str(prompt_path),
            str(raw_output_path),
            json.dumps(envelope, indent=2, sort_keys=True),
            started_at,
            finished_at,
        ),
    )
    conn.commit()


def record_turn_start(
    conn: sqlite3.Connection,
    *,
    turn_id: str,
    job_id: str,
    round_no: int,
    agent_role: str,
    state_sha_start: str,
    prompt_path: Path,
    raw_output_path: Path,
    started_at: str,
) -> None:
    """Insert a RUNNING turn row before calling the adapter."""
    conn.execute(
        """
        INSERT INTO turns(
            turn_id, job_id, round_no, agent_role, status,
            state_sha_start, prompt_path, raw_output_path, started_at
        ) VALUES (?, ?, ?, ?, 'RUNNING', ?, ?, ?, ?)
        """,
        (
            turn_id,
            job_id,
            round_no,
            agent_role,
            state_sha_start,
            str(prompt_path),
            str(raw_output_path),
            started_at,
        ),
    )
    conn.commit()


def update_turn_complete(
    conn: sqlite3.Connection,
    *,
    turn_id: str,
    status: str,
    decision: str | None = None,
    state_sha_end: str | None = None,
    envelope: dict[str, Any] | None = None,
    finished_at: str | None = None,
) -> None:
    """Update a RUNNING turn row with final results."""
    conn.execute(
        """
        UPDATE turns SET
            status = ?, decision = ?, state_sha_end = ?,
            envelope_json = ?, finished_at = ?
        WHERE turn_id = ?
        """,
        (
            status,
            decision,
            state_sha_end,
            json.dumps(envelope, indent=2, sort_keys=True) if envelope else None,
            finished_at,
            turn_id,
        ),
    )
    conn.commit()


def update_job_status(conn: sqlite3.Connection, job_id: str, status: str, *, current_round: int | None = None, terminal_decision: str | None = None) -> None:
    updates = ["status = ?", "updated_at = ?"]
    values: list[Any] = [status, utc_now()]
    if current_round is not None:
        updates.append("current_round = ?")
        values.append(current_round)
    if terminal_decision is not None:
        updates.append("terminal_decision = ?")
        values.append(terminal_decision)
    values.append(job_id)
    conn.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?", values)
    conn.commit()


def render_job(paths: BridgePaths, conn: sqlite3.Connection, job_id: str) -> Path:
    job = read_job(conn, job_id)
    turns = conn.execute(
        "SELECT * FROM turns WHERE job_id = ? ORDER BY started_at ASC",
        (job_id,),
    ).fetchall()
    validations = conn.execute(
        "SELECT * FROM validations WHERE job_id = ? ORDER BY created_at ASC",
        (job_id,),
    ).fetchall()
    status_text = job['status']
    if job['status'] == 'AWAITING_REVIEWER_APPROVAL':
        status_text = 'PAUSED — awaiting founder review before reviewer'

    lines = [
        f"# Bridge Job {job_id}",
        "",
        f"- Status: {status_text}",
        f"- Reader: {job['reader_agent']}",
        f"- Reviewer: {job['reviewer_agent']}",
        f"- Wave class: {job['wave_class'] or '(unspecified)'}",
        f"- Allow edits: {'yes' if job['allow_edits'] else 'no'}",
        f"- Max rounds: {job['max_rounds']}",
    ]
    if job['status'] == 'AWAITING_REVIEWER_APPROVAL':
        lines.extend([
            "",
            f"> **Paused for founder review.** Reader output is available above.",
            f"> Inspect the reader's raw output, then resume with:",
            f"> `python3 mu/tools/agents/bridge_supervisor.py continue {job_id}`",
        ])
    lines.extend([
        "",
        "## Task",
        job['task_text'],
        "",
        "## Turns",
    ])
    for turn in turns:
        envelope = json.loads(turn["envelope_json"]) if turn["envelope_json"] else {}
        decision_display = turn['decision'] or '(none)'
        if decision_display == "SYNTHETIC":
            decision_display = "SYNTHETIC (founder session, not a real review)"
        lines.extend([
            f"### {turn['turn_id']} — {turn['agent_role']}",
            f"- Status: {turn['status']}",
            f"- Decision: {decision_display}",
            f"- Summary: {envelope.get('summary', '(none)')}",
            f"- Claimed files: {', '.join(envelope.get('touched_files_claimed', [])) or '(none)'}",
        ])
        findings = envelope.get("findings", [])
        if findings:
            lines.append(f"- **Findings ({len(findings)}):**")
            for fi, finding in enumerate(findings, 1):
                sev = finding.get("severity", "?")
                cls = finding.get("class", "?")
                title = finding.get("title", "(untitled)")
                file_ref = finding.get("file", "?")
                line_start = finding.get("line_start", "?")
                status = finding.get("status", "new")
                lines.append(f"  {fi}. **{cls}** ({sev}): {title}")
                lines.append(f"     - File: `{file_ref}:{line_start}` | Status: {status}")
                evidence = finding.get("evidence_result", "")
                if evidence:
                    lines.append(f"     - Evidence: {evidence[:300]}")
        request = envelope.get("request_for_next_agent", "")
        if request:
            lines.append(f"- Request for next agent: {request}")
        lines.extend([
            f"- Raw output: {turn['raw_output_path']}",
            "",
        ])
    lines.append("## Validations")
    for validation in validations:
        lines.append(f"- `{validation['command']}` => {validation['result_summary']}")
    rendered_path = paths.rendered_dir / f"{job_id}.md"
    rendered_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return rendered_path


def submit_job(
    paths: BridgePaths,
    *,
    task_text: str,
    scope_hint: str | None,
    wave_class: str | None,
    allow_edits: bool,
    reader_agent: str,
    reviewer_agent: str,
    max_rounds: int,
    acceptance_checks: list[str],
    job_id: str | None,
) -> str:
    # Fail-closed: reject unknown acceptance checks at submit time
    unknown = [cmd for cmd in acceptance_checks if cmd not in VALIDATION_WHITELIST]
    if unknown:
        raise BridgeError(
            f"Unknown acceptance check(s) rejected at submit time: {unknown}\n"
            f"Add to VALIDATION_WHITELIST in bridge_supervisor.py to allow execution.\n"
            f"Known commands: {sorted(VALIDATION_WHITELIST.keys())}"
        )
    init_db(paths)
    with open_db(paths) as conn:
        final_job_id = job_id or f"{slugify((wave_class or 'bridge') + '-' + task_text[:40])}-{uuid.uuid4().hex[:8]}"
        now = utc_now()
        conn.execute(
            """
            INSERT INTO jobs(
                job_id, created_at, updated_at, status, task_text, scope_hint,
                wave_class, allow_edits, reader_agent, reviewer_agent,
                acceptance_checks_json, max_rounds, current_round, terminal_decision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
            """,
            (
                final_job_id,
                now,
                now,
                "READY_READER",
                task_text,
                scope_hint,
                wave_class,
                1 if allow_edits else 0,
                reader_agent,
                reviewer_agent,
                json.dumps(acceptance_checks),
                max_rounds,
            ),
        )
        conn.commit()
        render_job(paths, conn, final_job_id)
        return final_job_id


def execute_agent_turn(
    conn: sqlite3.Connection,
    paths: BridgePaths,
    job: sqlite3.Row,
    *,
    round_no: int,
    agent_role: str,
    adapter_name: str,
    prompt_text: str,
    attempt: int = 1,
    stream: bool = False,
    prompt_baseline_sha: str | None = None,
) -> tuple[str, dict[str, Any], Path, Path, RepoState]:
    state_start = compute_repo_state(paths.repo_root)
    short_uuid = uuid.uuid4().hex[:8]
    turn_suffix = f"r{round_no}-{agent_role}-{short_uuid}"
    turn_id = f"{job['job_id']}--{turn_suffix}"
    prompt_path = write_prompt(paths, job["job_id"], turn_id, prompt_text)
    started_at = utc_now()

    # Validate adapter config BEFORE recording RUNNING turn to avoid phantom rows
    config = load_bridge_config(paths.config_path)
    adapter = get_adapter(config, adapter_name)
    turn_timeout_s = _bridge_turn_timeout_s(adapter.timeout_s)
    zero_output_timeout_s = BRIDGE_ZERO_OUTPUT_TIMEOUT_S if agent_role == "reviewer" else None

    # Pre-allocate raw output file so it exists from adapter start
    raw_dir = paths.raw_dir / job["job_id"]
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_output_path = raw_dir / f"{turn_id}.txt"

    # Record RUNNING turn row BEFORE calling adapter
    record_turn_start(
        conn,
        turn_id=turn_id,
        job_id=job["job_id"],
        round_no=round_no,
        agent_role=agent_role,
        state_sha_start=state_start.state_sha,
        prompt_path=prompt_path,
        raw_output_path=raw_output_path,
        started_at=started_at,
    )
    # Store prompt-baseline sha for crash recovery staleness detection
    if prompt_baseline_sha:
        conn.execute(
            "UPDATE turns SET reviewer_input_validation_sha = ? WHERE turn_id = ?",
            (prompt_baseline_sha, turn_id),
        )
        conn.commit()
    try:
        output = run_adapter(
            adapter,
            prompt_text=prompt_text,
            prompt_path=prompt_path,
            repo_root=paths.repo_root,
            job_id=job["job_id"],
            turn_id=turn_id,
            agent_role=agent_role,
            stream=stream,
            raw_output_path=raw_output_path,
            timeout_override_s=turn_timeout_s,
            zero_output_timeout_s=zero_output_timeout_s,
            stop_after_envelope=True,
        )
    except (BridgeAdapterError, Exception) as exc:
        # Update turn to FAILED on adapter error
        update_turn_complete(
            conn,
            turn_id=turn_id,
            status="FAILED",
            decision="ERROR",
            state_sha_end=compute_repo_state(paths.repo_root).state_sha,
            finished_at=utc_now(),
        )
        raise

    try:
        envelope = parse_envelope(output)
    except Exception:
        update_turn_complete(
            conn,
            turn_id=turn_id,
            status="FAILED",
            decision="ERROR",
            state_sha_end=compute_repo_state(paths.repo_root).state_sha,
            finished_at=utc_now(),
        )
        raise
    state_end = compute_repo_state(paths.repo_root)
    finished_at = utc_now()

    status = "completed"
    decision = envelope.get("decision", "ERROR")
    if decision == "STALE":
        status = "stale"
    update_turn_complete(
        conn,
        turn_id=turn_id,
        status=status,
        decision=decision,
        state_sha_end=state_end.state_sha,
        envelope=envelope,
        finished_at=finished_at,
    )
    return turn_id, envelope, prompt_path, raw_output_path, state_start


def _log(verbose: bool, msg: str) -> None:
    if verbose:
        print(f"[bridge] {msg}", flush=True)


def _print_envelope(role: str, agent_name: str, envelope: dict[str, Any]) -> None:
    """Print structured envelope content to stdout for inline dialectic visibility."""
    border = "=" * 60
    print(f"\n{border}", flush=True)
    print(f"  {role.upper()} ({agent_name})", flush=True)
    print(f"{border}", flush=True)
    print(f"Decision: {envelope.get('decision', '(none)')}", flush=True)
    print(f"Summary:  {envelope.get('summary', '(none)')}", flush=True)

    findings = envelope.get("findings", [])
    if findings:
        print(f"\nFindings ({len(findings)}):", flush=True)
        for i, finding in enumerate(findings, 1):
            sev = finding.get("severity", "?")
            cls = finding.get("class", "?")
            title = finding.get("title", "(untitled)")
            file_ref = finding.get("file", "?")
            line_start = finding.get("line_start", "?")
            status = finding.get("status", "new")
            print(f"  [{i}] {cls} ({sev}): {title}", flush=True)
            print(f"      File: {file_ref}:{line_start}  Status: {status}", flush=True)
            evidence = finding.get("evidence_result", "")
            if evidence:
                if len(evidence) > 200:
                    evidence = evidence[:200] + "..."
                print(f"      Evidence: {evidence}", flush=True)
    else:
        print(f"\nFindings: (none)", flush=True)

    touched = envelope.get("touched_files_claimed", [])
    print(f"\nTouched files: {', '.join(touched) if touched else '(none)'}", flush=True)

    request = envelope.get("request_for_next_agent", "")
    if request:
        print(f"\nRequest for next agent: {request}", flush=True)

    print(f"{border}\n", flush=True)


def run_job(paths: BridgePaths, job_id: str, *, verbose: bool = False, pause_after_reader: bool = False) -> str:
    init_db(paths)
    with _BridgeLock(paths.bus_dir / "bridge.lock"):
        return _run_job_locked(paths, job_id, verbose=verbose, pause_after_reader=pause_after_reader)


def _run_reviewer_phase(
    conn: sqlite3.Connection,
    paths: BridgePaths,
    job_id: str,
    job: sqlite3.Row,
    round_no: int,
    validation_results: list[dict[str, Any]],
    verbose: bool,
    stream: bool = False,
    include_diff: bool = True,
) -> str | None:
    """Run reviewer (with staleness retry). Returns terminal decision or None for REQUEST_CHANGES continuation."""
    reviewer_attempt = 0
    reviewer_envelope: dict[str, Any] | None = None
    while reviewer_attempt < 2:
        reviewer_attempt += 1
        try:
            update_job_status(conn, job_id, "REVIEWER_RUNNING", current_round=round_no)
            _log(verbose, f"Round {round_no}/{job['max_rounds']}: starting reviewer ({job['reviewer_agent']})...")
            review_state_start = compute_repo_state(paths.repo_root)
            reviewer_prompt = build_reviewer_prompt(conn, paths, read_job(conn, job_id), round_no, validation_results, include_diff=include_diff)
            reviewer_turn_id, reviewer_envelope, _, raw_path, _ = execute_agent_turn(
                conn,
                paths,
                read_job(conn, job_id),
                round_no=round_no,
                agent_role="reviewer",
                adapter_name=job["reviewer_agent"],
                prompt_text=reviewer_prompt,
                attempt=reviewer_attempt,
                stream=stream,
                prompt_baseline_sha=review_state_start.state_sha,
            )
        except BaseException:
            # Restore job status so continue/recovery works.
            # Catch BaseException to ensure job status is NEVER left stranded in
            # *_RUNNING regardless of exception type (PermissionError, BrokenPipeError, etc).
            update_job_status(conn, job_id, "AWAITING_REVIEWER_APPROVAL", current_round=round_no)
            raise
        review_state_end = compute_repo_state(paths.repo_root)
        # Always persist the supervisor's post-review state into the turn
        # unconditionally so crash recovery has the same view as the live
        # stale check. Without this, recovery uses the state_sha_end from
        # inside execute_agent_turn which is captured slightly earlier.
        conn.execute(
            "UPDATE turns SET state_sha_end = ? WHERE turn_id = ?",
            (review_state_end.state_sha, reviewer_turn_id),
        )
        conn.commit()
        _log(verbose, "Reviewer complete.")
        if verbose:
            _print_envelope("reviewer", job["reviewer_agent"], reviewer_envelope)
        _log(verbose, f"  Raw output: {raw_path}")
        if review_state_start.state_sha == review_state_end.state_sha:
            break
        _log(verbose, f"  State changed during review — marking stale (attempt {reviewer_attempt}/2)")
        conn.execute(
            "UPDATE turns SET status = ?, decision = ?, state_sha_end = ? WHERE turn_id = ?",
            ("stale", "STALE", review_state_end.state_sha, reviewer_turn_id),
        )
        conn.commit()
        render_job(paths, conn, job_id)
        if reviewer_attempt >= 2:
            raise BridgeError(
                "Reviewer state became stale twice. Stabilize the tree and rerun the job."
            )

    assert reviewer_envelope is not None
    render_job(paths, conn, job_id)
    decision = reviewer_envelope.get("decision")
    if decision == "GO":
        update_job_status(conn, job_id, "DONE", current_round=round_no, terminal_decision="GO")
        render_job(paths, conn, job_id)
        return "GO"
    if decision == "QUESTION":
        update_job_status(conn, job_id, "AWAITING_FOUNDER", current_round=round_no, terminal_decision="QUESTION")
        render_job(paths, conn, job_id)
        return "QUESTION"
    if decision == "NO_GO":
        update_job_status(conn, job_id, "DONE", current_round=round_no, terminal_decision="NO_GO")
        render_job(paths, conn, job_id)
        return "NO_GO"
    if decision == "REQUEST_CHANGES":
        if round_no >= job["max_rounds"]:
            update_job_status(conn, job_id, "DONE", current_round=round_no, terminal_decision="NO_GO")
            render_job(paths, conn, job_id)
            return "NO_GO"
        update_job_status(conn, job_id, "READY_READER", current_round=round_no)
        render_job(paths, conn, job_id)
        return None  # continue to next round
    update_job_status(conn, job_id, "DONE", current_round=round_no, terminal_decision=decision or "ERROR")
    render_job(paths, conn, job_id)
    return decision or "ERROR"


def _run_job_locked(paths: BridgePaths, job_id: str, *, verbose: bool = False, pause_after_reader: bool = False) -> str:
    with open_db(paths) as conn:
        job = read_job(conn, job_id)
        if job["terminal_decision"]:
            _log(verbose, f"Job already terminal: {job['terminal_decision']}")
            render_job(paths, conn, job_id)
            return job["terminal_decision"]

        acceptance_checks = json.loads(job["acceptance_checks_json"])

        # Recovery: if a previous run was interrupted mid-round, determine
        # the correct resume point based on what turns actually completed.
        if job["status"] in ("READER_RUNNING", "REVIEWER_RUNNING"):
            reader_turn = conn.execute(
                "SELECT * FROM turns WHERE job_id = ? AND round_no = ? AND agent_role = 'reader' AND status = 'completed'",
                (job_id, job["current_round"]),
            ).fetchone()
            reviewer_turn = conn.execute(
                "SELECT * FROM turns WHERE job_id = ? AND round_no = ? AND agent_role = 'reviewer' AND status = 'completed'",
                (job_id, job["current_round"]),
            ).fetchone()
            if reviewer_turn is not None:
                # Reviewer already completed — crash happened between record_turn and status update.
                # Check staleness: (1) state changed during execution, or (2) prompt was built
                # against a different state than execution started with (stale prompt).
                reviewer_sha_start = reviewer_turn["state_sha_start"]
                reviewer_sha_end = reviewer_turn["state_sha_end"]
                prompt_baseline = reviewer_turn["reviewer_input_validation_sha"]
                execution_stale = reviewer_sha_start and reviewer_sha_end and reviewer_sha_start != reviewer_sha_end
                prompt_baseline_missing = reviewer_sha_start and prompt_baseline is None
                prompt_stale = reviewer_sha_start and prompt_baseline and prompt_baseline != reviewer_sha_start
                if execution_stale or prompt_baseline_missing or prompt_stale:
                    if execution_stale:
                        reason = "state changed during execution"
                    elif prompt_baseline_missing:
                        reason = "prompt baseline was missing"
                    else:
                        reason = "prompt built against stale state"
                    _log(verbose, f"Recovering: reviewer completed but {reason} (stale). Discarding verdict and retrying.")
                    conn.execute(
                        "UPDATE turns SET status = ?, decision = ? WHERE turn_id = ?",
                        ("stale", "STALE", reviewer_turn["turn_id"]),
                    )
                    conn.commit()
                    update_job_status(conn, job_id, "AWAITING_REVIEWER_APPROVAL", current_round=job["current_round"])
                    job = read_job(conn, job_id)
                else:
                    # State was stable — apply the recorded outcome instead of rerunning.
                    envelope = json.loads(reviewer_turn["envelope_json"]) if reviewer_turn["envelope_json"] else {}
                    decision = envelope.get("decision", "ERROR")
                    _log(verbose, f"Recovering: reviewer already completed (round {job['current_round']}). Applying recorded decision: {decision}")
                    if decision in ("GO", "NO_GO", "ERROR"):
                        terminal = "GO" if decision == "GO" else decision
                        update_job_status(conn, job_id, "DONE", current_round=job["current_round"], terminal_decision=terminal)
                    elif decision == "QUESTION":
                        update_job_status(conn, job_id, "AWAITING_FOUNDER", current_round=job["current_round"], terminal_decision="QUESTION")
                    elif decision == "REQUEST_CHANGES":
                        if job["current_round"] >= job["max_rounds"]:
                            update_job_status(conn, job_id, "DONE", current_round=job["current_round"], terminal_decision="NO_GO")
                        else:
                            update_job_status(conn, job_id, "READY_READER", current_round=job["current_round"])
                    else:
                        update_job_status(conn, job_id, "DONE", current_round=job["current_round"], terminal_decision=decision or "ERROR")
                    render_job(paths, conn, job_id)
                    job = read_job(conn, job_id)
            elif reader_turn is None:
                # Reader never completed — reset round so it reruns
                retry_round = max(0, job["current_round"] - 1)
                _log(verbose, f"Recovering from interrupted reader (round {job['current_round']}). Resetting to round {retry_round}.")
                update_job_status(conn, job_id, "READY_READER", current_round=retry_round)
                job = read_job(conn, job_id)
            elif job["status"] == "REVIEWER_RUNNING":
                # Reader completed but reviewer didn't — resume at reviewer
                _log(verbose, f"Recovering from interrupted reviewer (round {job['current_round']}). Resuming at reviewer.")
                update_job_status(conn, job_id, "AWAITING_REVIEWER_APPROVAL", current_round=job["current_round"])
                job = read_job(conn, job_id)
            else:
                # Reader completed but status is still READER_RUNNING (crash between record_turn and status update).
                # Validations may not have run or may be partial — clear and rerun to ensure
                # reviewer gets complete evidence. Clearing first avoids primary key collisions
                # if some validations were committed before the crash.
                _log(verbose, f"Reader completed but status stuck at READER_RUNNING (round {job['current_round']}). Rerunning validations and resuming at reviewer.")
                _log(verbose, "Clearing partial validations and rerunning for recovery...")
                conn.execute(
                    "DELETE FROM validations WHERE job_id = ? AND turn_id = ?",
                    (job_id, reader_turn["turn_id"]),
                )
                conn.commit()
                run_validations(
                    paths,
                    conn,
                    job_id=job_id,
                    turn_id=reader_turn["turn_id"],
                    acceptance_checks=acceptance_checks,
                )
                update_job_status(conn, job_id, "AWAITING_REVIEWER_APPROVAL", current_round=job["current_round"])
                job = read_job(conn, job_id)

        # If recovery resolved the job to a terminal state, return immediately
        if job["terminal_decision"]:
            _log(verbose, f"Recovery resolved job to terminal: {job['terminal_decision']}")
            render_job(paths, conn, job_id)
            return job["terminal_decision"]

        # Resume path: reviewer phase after --pause-after-reader
        if job["status"] == "AWAITING_REVIEWER_APPROVAL":
            round_no = job["current_round"]
            _log(verbose, f"Resuming at reviewer phase (round {round_no})")
            # Reconstruct validation_results from DB for this round.
            # Look up actual reader turn_id (handles both legacy and new formats).
            reader_turn_for_resume = conn.execute(
                "SELECT turn_id FROM turns WHERE job_id = ? AND round_no = ? AND agent_role = 'reader' AND status = 'completed' ORDER BY started_at DESC LIMIT 1",
                (job_id, round_no),
            ).fetchone()
            reader_turn_id_for_query = reader_turn_for_resume["turn_id"] if reader_turn_for_resume else f"{job_id}--r{round_no}-reader"
            validations = conn.execute(
                "SELECT command, exit_code, result_summary, output_path FROM validations WHERE job_id = ? AND turn_id = ?",
                (job_id, reader_turn_id_for_query),
            ).fetchall()
            validation_results = [
                {"command": v["command"], "exit_code": v["exit_code"], "result_summary": v["result_summary"], "output_path": v["output_path"]}
                for v in validations
            ]
            result = _run_reviewer_phase(conn, paths, job_id, job, round_no, validation_results, verbose, stream=verbose)
            if result is not None:
                rendered = paths.rendered_dir / f"{job_id}.md"
                _log(verbose, f"Rendered transcript: {rendered}")
                _log(verbose, f"Terminal decision: {result}")
                return result
            # REQUEST_CHANGES — fall through to normal loop for remaining rounds

        for round_no in range(job["current_round"] + 1, job["max_rounds"] + 1):
            try:
                update_job_status(conn, job_id, "READER_RUNNING", current_round=round_no)
                job = read_job(conn, job_id)
                _log(verbose, f"Round {round_no}/{job['max_rounds']}: starting reader ({job['reader_agent']})...")
                reader_state = compute_repo_state(paths.repo_root)
                reader_prompt = build_reader_prompt(conn, paths, job, round_no, reader_state)
                reader_turn_id, reader_envelope, _, raw_path, _ = execute_agent_turn(
                    conn,
                    paths,
                    job,
                    round_no=round_no,
                    agent_role="reader",
                    adapter_name=job["reader_agent"],
                    prompt_text=reader_prompt,
                    stream=verbose,
                )
            except BaseException:
                # Restore to last completed round so the retry loop re-attempts this round.
                # Catch BaseException to ensure job status is NEVER left stranded in
                # *_RUNNING regardless of exception type (PermissionError, BrokenPipeError, etc).
                update_job_status(conn, job_id, "READY_READER", current_round=max(0, round_no - 1))
                raise
            _log(verbose, "Reader complete.")
            if verbose:
                _print_envelope("reader", job["reader_agent"], reader_envelope)
            _log(verbose, f"  Raw output: {raw_path}")
            render_job(paths, conn, job_id)
            if reader_envelope.get("decision") in {"QUESTION", "ERROR"}:
                terminal = reader_envelope.get("decision")
                update_job_status(conn, job_id, "AWAITING_FOUNDER", current_round=round_no, terminal_decision=terminal)
                render_job(paths, conn, job_id)
                _log(verbose, f"Terminal decision: {terminal}")
                return terminal

            _log(verbose, "Running validations...")
            validation_results = run_validations(
                paths,
                conn,
                job_id=job_id,
                turn_id=reader_turn_id,
                acceptance_checks=acceptance_checks,
            )
            passed = sum(1 for v in validation_results if v["exit_code"] == 0)
            _log(verbose, f"Validations complete ({passed}/{len(validation_results)} passed)")
            render_job(paths, conn, job_id)

            if pause_after_reader:
                update_job_status(conn, job_id, "AWAITING_REVIEWER_APPROVAL", current_round=round_no)
                render_job(paths, conn, job_id)
                rendered = paths.rendered_dir / f"{job_id}.md"
                _log(verbose, "PAUSED after reader (--pause-after-reader). Inspect:")
                _log(verbose, f"  Raw output: {raw_path}")
                _log(verbose, f"  Rendered:   {rendered}")
                # Always print pause info even without --verbose — this is the intervention contract
                if not verbose:
                    print(f"[bridge] PAUSED after reader. Inspect:", flush=True)
                    print(f"[bridge]   Raw output: {raw_path}", flush=True)
                    print(f"[bridge]   Rendered:   {rendered}", flush=True)
                print(f"[bridge] Resume: python3 mu/tools/agents/bridge_supervisor.py continue {job_id}", flush=True)
                return "PAUSED"

            result = _run_reviewer_phase(conn, paths, job_id, job, round_no, validation_results, verbose, stream=verbose)
            if result is not None:
                rendered = paths.rendered_dir / f"{job_id}.md"
                _log(verbose, f"Rendered transcript: {rendered}")
                _log(verbose, f"Terminal decision: {result}")
                return result
            # REQUEST_CHANGES — continue to next round

        update_job_status(conn, job_id, "DONE", current_round=job["max_rounds"], terminal_decision="NO_GO")
        render_job(paths, conn, job_id)
        return "NO_GO"


def continue_job(paths: BridgePaths, job_id: str, *, verbose: bool = False) -> str:
    """Resume a paused job from the AWAITING_REVIEWER_APPROVAL state."""
    init_db(paths)
    with open_db(paths) as conn:
        job = read_job(conn, job_id)
        if job["status"] != "AWAITING_REVIEWER_APPROVAL":
            raise BridgeError(
                f"Job '{job_id}' is not paused (status: {job['status']}). "
                "Only jobs in AWAITING_REVIEWER_APPROVAL state can be continued."
            )
    with _BridgeLock(paths.bus_dir / "bridge.lock"):
        return _run_job_locked(paths, job_id, verbose=verbose, pause_after_reader=False)


def review_job(
    paths: BridgePaths,
    *,
    task_text: str,
    reader_summary: str,
    wave_class: str | None = None,
    reviewer_agent: str = "codex",
    acceptance_checks: list[str] | None = None,
    verbose: bool = False,
    job_id: str | None = None,
    include_diff: bool = True,
) -> str:
    """Hybrid review: record synthetic reader turn from interactive session, then run reviewer."""
    init_db(paths)
    if acceptance_checks is None:
        acceptance_checks = []

    final_job_id = submit_job(
        paths,
        task_text=task_text,
        scope_hint=None,
        wave_class=wave_class,
        allow_edits=True,
        reader_agent="claude-session",
        reviewer_agent=reviewer_agent,
        max_rounds=2,
        acceptance_checks=acceptance_checks,
        job_id=job_id,
    )

    with _BridgeLock(paths.bus_dir / "bridge.lock"):
        with open_db(paths) as conn:
            job = read_job(conn, final_job_id)
            round_no = 1
            turn_id = f"{final_job_id}--r{round_no}-reader-{uuid.uuid4().hex[:8]}"

            # Build synthetic reader envelope from interactive session
            actual_staged = changed_files(paths.repo_root, staged=True)
            actual_unstaged = changed_files(paths.repo_root, staged=False)
            all_changed = sorted(set(actual_staged + actual_unstaged))
            scoped_targets = _scoped_review_targets_from_task_text(paths.repo_root, task_text)
            claimed_files = scoped_targets if scoped_targets else all_changed
            next_request = (
                "Review the plan against the task requirements."
                if "Review the plan at `" in task_text
                else "Review the implementation against the task requirements."
            )

            envelope = {
                "job_id": final_job_id,
                "turn_id": turn_id,
                "agent_role": "reader",
                "decision": "SYNTHETIC",
                "synthetic": True,
                "summary": reader_summary,
                "touched_files_claimed": claimed_files,
                "findings": [],
                "validations_claimed": [],
                "request_for_next_agent": next_request,
            }

            # Record synthetic reader turn
            state = compute_repo_state(paths.repo_root)
            now = utc_now()
            prompt_text = (
                f"[Synthetic reader turn — implementation done in interactive Claude session]\n\n"
                f"Task: {task_text}\n\nSummary: {reader_summary}"
            )
            prompt_path = write_prompt(paths, final_job_id, turn_id, prompt_text)
            raw_output = (
                f"[Interactive session implementation]\n\n{reader_summary}\n\n"
                f"BEGIN_AGENT_ENVELOPE\n{json.dumps(envelope, indent=2)}\nEND_AGENT_ENVELOPE"
            )
            raw_path = write_raw_output(paths, final_job_id, turn_id, raw_output)

            record_turn(
                conn,
                turn_id=turn_id,
                job_id=final_job_id,
                round_no=round_no,
                agent_role="reader",
                status="completed",
                decision="SYNTHETIC",
                state_sha_start=state.state_sha,
                state_sha_end=state.state_sha,
                prompt_path=prompt_path,
                raw_output_path=raw_path,
                envelope=envelope,
                started_at=now,
                finished_at=now,
            )

            if verbose:
                _print_envelope("reader", "claude-session", envelope)

            # Run validations
            update_job_status(conn, final_job_id, "READER_RUNNING", current_round=round_no)
            _log(verbose, "Running validations...")
            validation_results = run_validations(
                paths, conn,
                job_id=final_job_id,
                turn_id=turn_id,
                acceptance_checks=acceptance_checks,
            )
            passed = sum(1 for v in validation_results if v["exit_code"] == 0)
            _log(verbose, f"Validations complete ({passed}/{len(validation_results)} passed)")

            # Advance to reviewer
            update_job_status(conn, final_job_id, "AWAITING_REVIEWER_APPROVAL", current_round=round_no)
            render_job(paths, conn, final_job_id)

            result = _run_reviewer_phase(
                conn, paths, final_job_id, job, round_no,
                validation_results, verbose, stream=verbose,
                include_diff=include_diff,
            )
            if result is not None:
                rendered = paths.rendered_dir / f"{final_job_id}.md"
                _log(verbose, f"Rendered transcript: {rendered}")
                _log(verbose, f"Terminal decision: {result}")
                return result

            # REQUEST_CHANGES — caller should fix and re-review
            return "REQUEST_CHANGES"


def print_status(paths: BridgePaths, job_id: str | None = None, *, show_latest: bool = False) -> None:
    """Enhanced status: per-job detail or all-jobs summary.

    job_id semantics:
    - None + show_latest=False: all-jobs summary (--all mode)
    - None + show_latest=True: show detail for the most recent job (bare status)
    - any string: show detail for that specific job
    """
    with open_db_readonly(paths) as conn:
        if job_id is None and not show_latest:
            # --all mode: one-line-per-job summary
            jobs = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC, rowid DESC"
            ).fetchall()
            if not jobs:
                print("No bridge jobs found.")
                return
            for job in jobs:
                elapsed = _elapsed_str(job["created_at"])
                decision = job["terminal_decision"] or ""
                print(f"{job['job_id']}  {job['status']:<30s}  "
                      f"round {job['current_round']}/{job['max_rounds']}  "
                      f"{elapsed}  {decision}")
            return

        if job_id is None and show_latest:
            latest = conn.execute(
                "SELECT job_id FROM jobs ORDER BY created_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
            if not latest:
                print("No bridge jobs found.")
                return
            job_id = latest["job_id"]

        job = read_job(conn, job_id)
        info: dict[str, Any] = {
            "job_id": job["job_id"],
            "status": job["status"],
            "reader_agent": job["reader_agent"],
            "reviewer_agent": job["reviewer_agent"],
            "current_round": job["current_round"],
            "max_rounds": job["max_rounds"],
            "terminal_decision": job["terminal_decision"],
            "created_at": job["created_at"],
            "elapsed": _elapsed_str(job["created_at"]),
        }
        # In-flight turn data
        running = conn.execute(
            "SELECT * FROM turns WHERE job_id = ? AND status = 'RUNNING' "
            "ORDER BY started_at DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        if running:
            raw_path = Path(running["raw_output_path"])
            info["in_flight"] = {
                "turn_id": running["turn_id"],
                "role": running["agent_role"],
                "started_at": running["started_at"],
                "elapsed": _elapsed_str(running["started_at"]),
                "raw_file": str(raw_path),
                "raw_size_bytes": raw_path.stat().st_size if raw_path.exists() else 0,
            }
        # Last completed turn
        last = conn.execute(
            "SELECT * FROM turns WHERE job_id = ? AND status = 'completed' "
            "ORDER BY finished_at DESC, rowid DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        if last:
            envelope = json.loads(last["envelope_json"]) if last["envelope_json"] else {}
            info["last_completed"] = {
                "turn_id": last["turn_id"],
                "role": last["agent_role"],
                "decision": last["decision"],
                "finding_count": len(envelope.get("findings", [])),
            }
        # Artifact discovery — match exact job_id dir or file prefix with separator
        artifacts: dict[str, list[str]] = {}
        for subdir_name in ("prompts", "raw", "rendered"):
            subdir = paths.bus_dir / subdir_name
            if subdir.exists():
                # Match job_id exactly as directory name, or file starting with job_id
                # followed by a non-alphanumeric separator (prevents job-1 matching job-10)
                exact_dir = subdir / job_id
                matches: list[Path] = []
                if exact_dir.exists():
                    matches.append(exact_dir)
                for p in sorted(subdir.iterdir()):
                    name = p.name
                    if name == job_id:
                        continue  # Already added above
                    if name.startswith(job_id) and len(name) > len(job_id) and not name[len(job_id)].isalnum():
                        matches.append(p)
                if matches:
                    artifacts[subdir_name] = [str(m) for m in sorted(matches)]
        if artifacts:
            info["artifacts"] = artifacts
        print(json.dumps(info, indent=2))


def _elapsed_str(iso_timestamp: str) -> str:
    """Human-readable elapsed time from an ISO timestamp to now."""
    try:
        then = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - then
        secs = int(delta.total_seconds())
        if secs < 60:
            return f"{secs}s ago"
        if secs < 3600:
            return f"{secs // 60}m ago"
        return f"{secs // 3600}h {(secs % 3600) // 60}m ago"
    except (ValueError, TypeError):
        return "(unknown)"


# ---------------------------------------------------------------------------
# Phase 1: Event stream
# ---------------------------------------------------------------------------

def query_events(
    conn: sqlite3.Connection,
    job_id: str | None = None,
    *,
    after_cursor: tuple[str, int, str, int] | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Derive events from turns, validations, and job_actions tables.

    Events are pseudo-events synthesized from existing rows — no separate
    events table. Cursor ordering: (timestamp, event_seq, source_table, rowid).
    event_seq: 0=turn_started, 1=validation, 2=turn_completed, 3=job_action.
    """
    # Build per-branch filters and collect params in order
    parts = []
    params: list[Any] = []

    job_filter = ""
    if job_id:
        job_filter = "WHERE job_id = ?"

    # 0: TURN_STARTED
    parts.append(f"""
        SELECT started_at AS ts, 0 AS event_seq, 'turns' AS source_table,
               rowid AS source_rowid, job_id,
               'TURN_STARTED' AS event_type,
               agent_role || ' round ' || round_no AS description,
               turn_id AS ref_id
        FROM turns {job_filter}
    """)
    if job_id:
        params.append(job_id)

    # 1: VALIDATION
    parts.append(f"""
        SELECT created_at AS ts, 1 AS event_seq, 'validations' AS source_table,
               rowid AS source_rowid, job_id,
               'VALIDATION' AS event_type,
               CASE WHEN exit_code = 0 THEN 'pass' ELSE 'fail' END
                 || ': ' || command AS description,
               validation_id AS ref_id
        FROM validations {job_filter}
    """)
    if job_id:
        params.append(job_id)

    # 2: TURN_COMPLETED (only finished turns)
    turn_complete_filter = "WHERE finished_at IS NOT NULL"
    if job_id:
        turn_complete_filter += " AND job_id = ?"
    parts.append(f"""
        SELECT finished_at AS ts, 2 AS event_seq, 'turns' AS source_table,
               rowid AS source_rowid, job_id,
               'TURN_COMPLETED' AS event_type,
               agent_role || ' round ' || round_no || ': '
                 || COALESCE(decision, '(none)') AS description,
               turn_id AS ref_id
        FROM turns {turn_complete_filter}
    """)
    if job_id:
        params.append(job_id)

    # 3: JOB_ACTION (only if table exists — gracefully degrade for pre-v3 DBs)
    has_job_actions = conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='job_actions'"
    ).fetchone()[0] > 0
    if has_job_actions:
        parts.append(f"""
            SELECT timestamp AS ts, 3 AS event_seq, 'job_actions' AS source_table,
                   id AS source_rowid, job_id,
                   action AS event_type,
                   COALESCE(actor, '') || CASE WHEN metadata IS NOT NULL
                     THEN ': ' || metadata ELSE '' END AS description,
                   CAST(id AS TEXT) AS ref_id
            FROM job_actions {job_filter}
        """)
        if job_id:
            params.append(job_id)

    query = " UNION ALL ".join(parts)

    # Apply cursor filter
    if after_cursor:
        query = f"""
            SELECT * FROM ({query})
            WHERE (ts, event_seq, source_table, source_rowid)
                > (?, ?, ?, ?)
        """
        params.extend(after_cursor)

    query += " ORDER BY ts ASC, event_seq ASC, source_table ASC, source_rowid ASC"
    query += f" LIMIT {limit}"

    rows = conn.execute(query, params).fetchall()
    events = []
    for row in rows:
        events.append({
            "timestamp": row["ts"],
            "event_type": row["event_type"],
            "description": row["description"],
            "job_id": row["job_id"],
            "ref_id": row["ref_id"],
            "cursor": (row["ts"], row["event_seq"], row["source_table"], row["source_rowid"]),
        })
    return events


def print_events(
    paths: BridgePaths,
    job_id: str | None = None,
    *,
    follow: bool = False,
    limit: int = 50,
) -> None:
    """Print event stream. With --follow, polls at 2s intervals."""
    import time

    show_job = job_id is None  # Show job_id prefix in all-jobs mode
    with open_db_readonly(paths) as conn:
        cursor: tuple[str, int, str, int] | None = None
        events = query_events(conn, job_id, limit=limit)
        for ev in events:
            _print_event_line(ev, show_job_id=show_job)
            cursor = ev["cursor"]

        if not follow:
            if not events:
                print("No events found.")
            return

        # Follow mode: poll for new events
        try:
            while True:
                time.sleep(2)
                new_events = query_events(conn, job_id, after_cursor=cursor, limit=100)
                for ev in new_events:
                    _print_event_line(ev, show_job_id=show_job)
                    cursor = ev["cursor"]
        except KeyboardInterrupt:
            pass


def _print_event_line(ev: dict[str, Any], *, show_job_id: bool = False) -> None:
    """Format one event for terminal output."""
    ts = ev["timestamp"]
    try:
        time_part = ts[11:19]  # HH:MM:SS from ISO timestamp
    except (TypeError, IndexError):
        time_part = "??:??:??"
    job_prefix = f" [{ev['job_id']}]" if show_job_id else ""
    print(f"[{time_part}]{job_prefix} {ev['event_type']}: {ev['description']}")


# ---------------------------------------------------------------------------
# Phase 1: Doctor command
# ---------------------------------------------------------------------------

def run_doctor(paths: BridgePaths, *, probe: bool = False) -> list[dict[str, Any]]:
    """Diagnose bridge health. Returns list of check results."""
    checks: list[dict[str, Any]] = []

    # 1. DB validation
    if paths.db_path.exists():
        try:
            _check_future_version(paths.db_path)
            with open_db_readonly(paths) as conn:
                tables = {r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()}
            expected = {"jobs", "turns", "validations", "schema_version", "job_actions"}
            missing = expected - tables
            if missing:
                checks.append({"check": "database", "status": "WARN",
                               "detail": f"Missing tables: {', '.join(sorted(missing))}"})
            else:
                checks.append({"check": "database", "status": "OK",
                               "detail": f"All {len(expected)} tables present"})
        except (sqlite3.Error, MigrationVersionError) as exc:
            checks.append({"check": "database", "status": "FAIL", "detail": str(exc)})
    else:
        checks.append({"check": "database", "status": "FAIL",
                       "detail": f"DB not found at {paths.db_path}"})

    # 2. Config / adapter validation
    try:
        config = load_bridge_config(paths.config_path)
        agents_block = config.get("agents")
        if not isinstance(agents_block, dict) or not agents_block:
            checks.append({"check": "config", "status": "FAIL",
                           "detail": "Config missing or empty 'agents' object"})
        else:
            checks.append({"check": "config", "status": "OK",
                           "detail": str(paths.config_path)})
        # Validate each adapter — expand placeholders first to mirror runtime
        for agent_name in (agents_block if isinstance(agents_block, dict) else {}):
            try:
                adapter = get_adapter(config, agent_name)
                # Expand placeholders using dummy context (same as probe)
                check_context = {
                    "prompt_file": "/dev/null",
                    "repo_root": str(paths.repo_root),
                    "job_id": "doctor-check",
                    "turn_id": "doctor-check",
                    "agent_role": "reviewer",
                }
                try:
                    expanded_cmd, _ = _prepare_adapter_env(adapter, check_context)
                except BridgeAdapterError as exc:
                    checks.append({"check": f"adapter:{agent_name}", "status": "FAIL",
                                   "detail": f"Placeholder expansion failed: {exc}"})
                    continue
                cmd_str = " ".join(expanded_cmd)
                executable = expanded_cmd[0]
                exe_basename = os.path.basename(executable)

                def _check_executable(cmd_name: str) -> tuple[str, str]:
                    """Check if a command is findable and executable (not a directory)."""
                    found = shutil.which(cmd_name)
                    if found:
                        if Path(found).is_dir():
                            return ("FAIL", f"resolves to directory: {found}")
                        return ("OK", f"found at {found}")
                    # Check as absolute/relative path
                    cmd_path = Path(cmd_name)
                    if cmd_path.is_absolute() and cmd_path.exists():
                        if cmd_path.is_dir():
                            return ("FAIL", f"is a directory: {cmd_path}")
                        if os.access(str(cmd_path), os.X_OK):
                            return ("OK", f"found at {cmd_path}")
                        return ("FAIL", "found but not executable")
                    repo_path = paths.repo_root / cmd_name
                    if repo_path.exists():
                        if repo_path.is_dir():
                            return ("FAIL", f"is a directory: {repo_path}")
                        if os.access(str(repo_path), os.X_OK):
                            return ("OK", "found relative to repo root")
                        return ("FAIL", "found relative to repo root but not executable")
                    return ("FAIL", "command not found")

                # Handle bash/sh -c wrappers (including absolute paths like /bin/bash)
                if exe_basename in ("bash", "sh") and len(expanded_cmd) >= 3 and expanded_cmd[1] == "-c":
                    import shlex
                    shell_builtins = {"exec", "eval", "source", ".", "command", "builtin", "env", "cd", "set", "export", "unset", "test", "true", "false"}
                    try:
                        tokens = shlex.split(expanded_cmd[2])
                    except ValueError:
                        tokens = expanded_cmd[2].split()
                    # Skip shell builtins, env assignments (FOO=bar), and flags
                    actual_cmd = ""
                    for tok in tokens:
                        if "=" in tok and not tok.startswith("-"):
                            continue  # env assignment like FOO=1
                        if tok in shell_builtins:
                            continue
                        if tok.startswith("-"):
                            continue
                        actual_cmd = tok
                        break
                    detail_prefix = f"wrapper: {exe_basename} -c, inner: {actual_cmd or '(unparseable)'}"
                    if actual_cmd:
                        inner_status, inner_detail = _check_executable(actual_cmd)
                        checks.append({"check": f"adapter:{agent_name}", "status": inner_status,
                                       "detail": f"{detail_prefix} ({inner_detail})"})
                    else:
                        checks.append({"check": f"adapter:{agent_name}", "status": "INFO",
                                       "detail": f"{detail_prefix} (use --probe to verify)"})
                else:
                    status, detail = _check_executable(executable)
                    checks.append({"check": f"adapter:{agent_name}", "status": status,
                                   "detail": f"{cmd_str} ({detail})"})
            except BridgeAdapterError as exc:
                checks.append({"check": f"adapter:{agent_name}", "status": "FAIL",
                               "detail": str(exc)})
    except BridgeAdapterError as exc:
        checks.append({"check": "config", "status": "FAIL", "detail": str(exc)})

    # 3. Prompt template validation
    template_path = SCRIPT_DIR / "templates" / "bridge_reviewer_prompt.txt"
    if template_path.exists():
        checks.append({"check": "template", "status": "OK",
                       "detail": str(template_path)})
    else:
        checks.append({"check": "template", "status": "FAIL",
                       "detail": f"Reviewer prompt template not found at {template_path}"})

    # 4. Lock file check
    lock_path = paths.bus_dir / "bridge.lock"
    if lock_path.exists():
        try:
            fd = os.open(str(lock_path), os.O_RDONLY)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
                detail = _describe_lock_metadata(lock_path)
                checks.append({"check": "lock", "status": "OK",
                               "detail": (
                                   "Lock file exists but is not held (persistent path by design)"
                                   + (f"; {detail}" if detail else "")
                               )})
            except OSError:
                detail = _describe_lock_metadata(lock_path)
                checks.append({"check": "lock", "status": "WARN",
                               "detail": (
                                   "Lock file is currently held (bridge running?)"
                                   + (f"; {detail}" if detail else "")
                               )})
            finally:
                os.close(fd)
        except OSError as exc:
            checks.append({"check": "lock", "status": "WARN",
                           "detail": f"Cannot check lock: {exc}"})
    else:
        checks.append({"check": "lock", "status": "OK", "detail": "No lock file"})

    # 5. Working tree (informational)
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True,
            cwd=str(paths.repo_root), timeout=10,
        )
        if result.returncode != 0:
            checks.append({"check": "worktree", "status": "WARN",
                           "detail": "Not a git repository or git error"})
        else:
            dirty_count = len([l for l in result.stdout.strip().splitlines() if l.strip()])
            if dirty_count:
                checks.append({"check": "worktree", "status": "INFO",
                               "detail": f"{dirty_count} dirty file(s)"})
            else:
                checks.append({"check": "worktree", "status": "OK",
                               "detail": "Clean working tree"})
    except (subprocess.SubprocessError, OSError):
        checks.append({"check": "worktree", "status": "INFO",
                       "detail": "Could not check git status"})

    # 6. Opt-in probe (--probe)
    if probe:
        import tempfile
        try:
            config = load_bridge_config(paths.config_path)
            for agent_name in config.get("agents", {}):
                try:
                    adapter = get_adapter(config, agent_name)
                    test_prompt = "Bridge doctor probe: respond with OK"
                    # Write prompt to a temp file for file-based adapters
                    with tempfile.NamedTemporaryFile(
                        mode="w", suffix=".txt", prefix="bridge-probe-",
                        dir=str(paths.bus_dir), delete=False,
                    ) as tf:
                        tf.write(test_prompt)
                        probe_prompt_path = tf.name
                    try:
                        # Expand placeholders using the same path as run_adapter
                        # Use "reviewer" as agent_role (matches live execution roles)
                        probe_context = {
                            "prompt_file": probe_prompt_path,
                            "repo_root": str(paths.repo_root),
                            "job_id": "doctor-probe",
                            "turn_id": "doctor-probe",
                            "agent_role": "reviewer",
                        }
                        expanded_cmd, expanded_env = _prepare_adapter_env(adapter, probe_context)
                        # Respect prompt_via_stdin: only pipe input when adapter expects it
                        stdin_input = test_prompt if adapter.prompt_via_stdin else None
                        proc = subprocess.run(
                            expanded_cmd, input=stdin_input, capture_output=True,
                            text=True, timeout=adapter.timeout_s, cwd=str(paths.repo_root),
                            env=expanded_env,
                        )
                        if proc.returncode == 0:
                            checks.append({"check": f"probe:{agent_name}", "status": "OK",
                                           "detail": f"Adapter responded (exit 0, {len(proc.stdout)} chars)"})
                        else:
                            checks.append({"check": f"probe:{agent_name}", "status": "FAIL",
                                           "detail": f"Adapter failed (exit {proc.returncode})"})
                    finally:
                        Path(probe_prompt_path).unlink(missing_ok=True)
                except subprocess.TimeoutExpired:
                    checks.append({"check": f"probe:{agent_name}", "status": "FAIL",
                                   "detail": f"Adapter timed out ({adapter.timeout_s}s)"})
                except (BridgeAdapterError, OSError) as exc:
                    checks.append({"check": f"probe:{agent_name}", "status": "FAIL",
                                   "detail": str(exc)})
        except BridgeAdapterError:
            pass  # Config already reported above

    return checks


# ---------------------------------------------------------------------------
# Phase 1: Finding lifecycle tracking
# ---------------------------------------------------------------------------

def _finding_stable_key(finding: dict[str, Any], *, design_mode: bool = False) -> tuple[str, str]:
    """Compute stable key for a finding. Returns (anchor, class).

    Severity is deliberately excluded — a finding should persist across
    severity reclassification (e.g. medium → high).
    """
    cls = finding.get("class", "unknown")
    if design_mode:
        anchor = finding.get("file", "(unanchored)")
    else:
        anchor = finding.get("file", "(unknown)")
    return (anchor, cls)


def title_similarity(a: str, b: str) -> float:
    """Jaccard similarity on normalized word tokens."""
    import re
    def tokens(s: str) -> set[str]:
        # Split on whitespace and hyphens, strip punctuation, lowercase
        words = re.split(r'[\s\-_]+', s)
        return {w.lower().strip(".,;:!?()[]{}\"'") for w in words if w.strip(".,;:!?()[]{}\"'")}
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def rebuild_finding_registry(conn: sqlite3.Connection, job_id: str) -> dict[str, Any]:
    """Rebuild the finding lifecycle registry from turn history.

    Returns the registry dict with per-finding tracking across all rounds.
    """
    turns = conn.execute(
        "SELECT * FROM turns WHERE job_id = ? AND agent_role = 'reviewer' "
        "AND is_canonical = 1 AND status = 'completed' ORDER BY round_no ASC",
        (job_id,),
    ).fetchall()

    # Registry: keyed by stable_key string, value is finding lifecycle info
    registry: dict[str, dict[str, Any]] = {}
    # Track which findings appeared in each round
    round_findings: dict[int, set[str]] = {}

    for turn in turns:
        if not turn["envelope_json"]:
            continue
        envelope = json.loads(turn["envelope_json"])
        findings = envelope.get("findings", [])
        round_no = turn["round_no"]
        seen_this_round: set[str] = set()

        for finding in findings:
            sk = _finding_stable_key(finding)
            base_key = f"{sk[0]}|{sk[1]}"
            title = finding.get("title", "(untitled)")

            # Search for a matching entry from PREVIOUS rounds (not current round).
            # Check the base key first, then any suffixed variants.
            matched_key: str | None = None
            candidates = [
                k for k, v in registry.items()
                if k == base_key or k.startswith(base_key + "|")
            ]
            for cand_key in candidates:
                cand = registry[cand_key]
                if cand_key in seen_this_round:
                    continue  # Skip entries already matched in THIS round
                if cand["first_seen_round"] == round_no:
                    continue  # Skip entries created in THIS round (same-round collision)
                if title_similarity(cand["best_title"], title) >= 0.6:
                    matched_key = cand_key
                    break

            if matched_key is not None:
                entry = registry[matched_key]
                entry["last_seen_round"] = round_no
                entry["times_raised"] += 1
                if entry["current_disposition"] in ("addressed", "silent"):
                    entry["current_disposition"] = "regression"
                else:
                    entry["current_disposition"] = "persisting"
                seen_this_round.add(matched_key)
                continue

            # New finding — use base_key if free, otherwise suffix with title
            if base_key not in registry and base_key not in seen_this_round:
                new_key = base_key
            else:
                new_key = f"{base_key}|{title[:40]}"
            registry[new_key] = {
                "stable_key": new_key,
                "anchor": sk[0],
                "class": sk[1],
                "best_title": title,
                "first_seen_round": round_no,
                "last_seen_round": round_no,
                "times_raised": 1,
                "current_disposition": "new",
            }
            seen_this_round.add(new_key)

        round_findings[round_no] = seen_this_round

        # Mark findings NOT seen this round
        for key, entry in registry.items():
            if key not in seen_this_round and entry["last_seen_round"] < round_no:
                if entry["current_disposition"] in ("new", "persisting", "regression"):
                    # "addressed" = disappeared from the immediately previous round
                    # "silent" = was already absent for >1 round
                    if entry["last_seen_round"] == round_no - 1:
                        entry["current_disposition"] = "addressed"
                    else:
                        entry["current_disposition"] = "silent"

    return {
        "job_id": job_id,
        "registry_version": len(turns),
        "findings": registry,
        "summary": _lifecycle_summary(registry),
    }


def _lifecycle_summary(registry: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Summarize dispositions across the registry."""
    counts: dict[str, int] = {"new": 0, "persisting": 0, "addressed": 0, "silent": 0, "regression": 0}
    for entry in registry.values():
        disposition = entry.get("current_disposition", "new")
        counts[disposition] = counts.get(disposition, 0) + 1
    return counts


def format_lifecycle_prompt_section(registry: dict[str, Any]) -> str:
    """Format the finding lifecycle summary for injection into reviewer prompt."""
    summary = registry.get("summary", {})
    total = sum(summary.values())
    if total == 0:
        return ""
    parts = []
    for disposition in ("new", "persisting", "addressed", "silent", "regression"):
        count = summary.get(disposition, 0)
        if count > 0:
            label = disposition
            if disposition == "silent":
                label = "silent (may need re-examination)"
            parts.append(f"{count} {label}")
    return f"PRIOR FINDINGS: {', '.join(parts)}."


def _read_text_arg(text: str | None, file: str | None, name: str) -> str:
    if bool(text) == bool(file):
        raise BridgeError(f"Provide exactly one of --{name} or --{name}-file")
    if file:
        return Path(file).read_text(encoding="utf-8").strip()
    assert text is not None
    return text.strip()


def read_task_text(task: str | None, task_file: str | None) -> str:
    return _read_text_arg(task, task_file, "task")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Turn-based bridge supervisor for Claude/Codex workflows")
    parser.add_argument("--repo-root", default=os.getcwd(), help="Repo root (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create bridge runtime directories and SQLite DB")

    submit = sub.add_parser("submit", help="Create a new bridge job")
    submit.add_argument("--task")
    submit.add_argument("--task-file")
    submit.add_argument("--scope-hint")
    submit.add_argument("--wave-class")
    submit.add_argument("--allow-edits", action="store_true")
    submit.add_argument("--reader", default="claude")
    submit.add_argument("--reviewer", default="codex")
    submit.add_argument("--max-rounds", type=int, default=2)
    submit.add_argument("--check", action="append", default=[])
    submit.add_argument("--job-id")

    run = sub.add_parser("run", help="Run a submitted job to completion or founder stop")
    run.add_argument("job_id")
    run.add_argument("--verbose", "-v", action="store_true", help="Print step events, file paths, and summary excerpts")
    run.add_argument("--pause-after-reader", action="store_true", help="Stop after reader + validations for inspection before reviewer")

    cont = sub.add_parser("continue", help="Resume a paused job (AWAITING_REVIEWER_APPROVAL)")
    cont.add_argument("job_id")
    cont.add_argument("--verbose", "-v", action="store_true", help="Print step events and stream agent output")

    status = sub.add_parser("status", help="Show current job status")
    status.add_argument("job_id", nargs="?", default=None)
    status.add_argument("--all", action="store_true", help="Show all jobs summary")

    review = sub.add_parser("review", help="Hybrid review: synthetic reader turn from interactive session + live reviewer")
    review.add_argument("--task")
    review.add_argument("--task-file")
    review.add_argument("--summary", help="Reader summary of implementation done in interactive session")
    review.add_argument("--summary-file", help="File containing reader summary")
    review.add_argument("--wave-class")
    review.add_argument("--reviewer", default="codex")
    review.add_argument("--check", action="append", default=[])
    review.add_argument("--job-id")
    review.add_argument("--verbose", "-v", action="store_true", help="Print structured envelope output inline")
    review.add_argument("--no-diff", action="store_true", help="Omit git diff from reviewer prompt (for design deliberation, questions, non-code review)")

    render = sub.add_parser("render", help="Render markdown transcript for a job")
    render.add_argument("job_id")

    events = sub.add_parser("events", help="Show event stream for a job")
    events.add_argument("job_id", nargs="?", default=None)
    events.add_argument("--follow", "-f", action="store_true", help="Poll for new events")
    events.add_argument("--limit", "-n", type=int, default=50, help="Max events to show")

    doctor = sub.add_parser("doctor", help="Diagnose bridge health")
    doctor.add_argument("--probe", action="store_true",
                        help="Run end-to-end adapter probe (may invoke real API)")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    paths = bridge_paths(repo_root)

    try:
        if args.command == "init":
            init_db(paths)
            print(f"Initialized bridge runtime at {paths.bus_dir}")
            return 0
        if args.command == "submit":
            task_text = read_task_text(args.task, args.task_file)
            job_id = submit_job(
                paths,
                task_text=task_text,
                scope_hint=args.scope_hint,
                wave_class=args.wave_class,
                allow_edits=args.allow_edits,
                reader_agent=args.reader,
                reviewer_agent=args.reviewer,
                max_rounds=args.max_rounds,
                acceptance_checks=args.check,
                job_id=args.job_id,
            )
            print(job_id)
            return 0
        if args.command == "run":
            decision = run_job(
                paths,
                args.job_id,
                verbose=args.verbose,
                pause_after_reader=args.pause_after_reader,
            )
            if decision != "PAUSED":
                print(decision)
            return 0 if decision == "GO" else (2 if decision == "PAUSED" else 1)
        if args.command == "continue":
            decision = continue_job(
                paths,
                args.job_id,
                verbose=args.verbose,
            )
            print(decision)
            return 0 if decision == "GO" else 1
        if args.command == "review":
            task_text = _read_text_arg(args.task, args.task_file, "task")
            summary_text = _read_text_arg(args.summary, args.summary_file, "summary")
            decision = review_job(
                paths,
                task_text=task_text,
                reader_summary=summary_text,
                wave_class=args.wave_class,
                reviewer_agent=args.reviewer,
                acceptance_checks=args.check,
                verbose=args.verbose,
                job_id=args.job_id,
                include_diff=not args.no_diff,
            )
            print(decision)
            return 0 if decision == "GO" else 1
        if args.command == "status":
            if not paths.db_path.exists():
                raise BridgeError("No bridge database found. Run 'init' first.")
            _check_future_version(paths.db_path)
            if args.all:
                target_id = None
                show_latest = False
            elif args.job_id:
                target_id = args.job_id
                show_latest = False
            else:
                target_id = None
                show_latest = True
            print_status(paths, target_id, show_latest=show_latest)
            return 0
        if args.command == "events":
            if not paths.db_path.exists():
                raise BridgeError("No bridge database found. Run 'init' first.")
            _check_future_version(paths.db_path)
            print_events(paths, args.job_id, follow=args.follow, limit=args.limit)
            return 0
        if args.command == "doctor":
            checks = run_doctor(paths, probe=args.probe)
            has_fail = False
            for check in checks:
                icon = {"OK": "✓", "WARN": "⚠", "FAIL": "✗", "INFO": "ℹ"}.get(check["status"], "?")
                print(f"  {icon} {check['check']}: {check['detail']}")
                if check["status"] == "FAIL":
                    has_fail = True
            return 1 if has_fail else 0
        if args.command == "render":
            if not paths.db_path.exists():
                raise BridgeError("No bridge database found. Run 'init' first.")
            _check_future_version(paths.db_path)
            paths.rendered_dir.mkdir(parents=True, exist_ok=True)
            with open_db_readonly(paths) as conn:
                output = render_job(paths, conn, args.job_id)
            print(output)
            return 0
    except (BridgeError, BridgeAdapterError, MigrationVersionError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
