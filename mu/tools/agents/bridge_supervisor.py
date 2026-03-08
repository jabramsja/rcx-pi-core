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

from bridge_adapters import BridgeAdapterError, get_adapter, load_bridge_config, run_adapter

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
        "decision": "GO|NO_GO|REQUEST_CHANGES|QUESTION|STALE|ERROR",
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
    r"BEGIN_AGENT_ENVELOPE\s*(\{.*?\})\s*END_AGENT_ENVELOPE",
    re.DOTALL,
)


class BridgeError(RuntimeError):
    """Raised when supervisor execution cannot continue."""


class _BridgeLock:
    """Exclusive file lock for single-supervisor enforcement."""

    def __init__(self, lock_path: Path):
        self._lock_path = lock_path
        self._fp: Any = None

    def __enter__(self) -> "_BridgeLock":
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = open(self._lock_path, "w")
        try:
            fcntl.flock(self._fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            self._fp.close()
            raise BridgeError(
                "Another bridge supervisor is already running. "
                "Wait for it to finish or remove .agent_bus/bridge.lock if stale."
            )
        return self

    def __exit__(self, *exc: object) -> bool:
        if self._fp:
            fcntl.flock(self._fp, fcntl.LOCK_UN)
            self._fp.close()
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
    return conn


def init_db(paths: BridgePaths) -> None:
    ensure_runtime_dirs(paths)
    schema = (SCRIPT_DIR / "bridge_schema.sql").read_text(encoding="utf-8")
    with open_db(paths) as conn:
        conn.executescript(schema)
        conn.commit()
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
        proc = subprocess.run(
            command,
            shell=True,
            cwd=paths.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        output = (proc.stdout or "") + ("\n[stderr]\n" + proc.stderr if proc.stderr else "")
        output_path = out_dir / f"validation-{index}.txt"
        output_path.write_text(output, encoding="utf-8")
        validation_id = f"{turn_id}-validation-{index}"
        summary = summarize_validation_output(output, proc.returncode)
        conn.execute(
            """
            INSERT INTO validations(validation_id, job_id, turn_id, command, exit_code, result_summary, output_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (validation_id, job_id, turn_id, command, proc.returncode, summary, str(output_path), utc_now()),
        )
        results.append(
            {
                "command": command,
                "exit_code": proc.returncode,
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
    match = ENVELOPE_RE.search(output)
    if not match:
        raise BridgeError("Agent output missing BEGIN_AGENT_ENVELOPE / END_AGENT_ENVELOPE block")
    try:
        envelope = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise BridgeError(f"Agent envelope is not valid JSON: {exc}") from exc
    required = {"job_id", "turn_id", "agent_role", "decision", "summary", "touched_files_claimed", "findings", "validations_claimed", "request_for_next_agent"}
    missing = required.difference(envelope)
    if missing:
        raise BridgeError(f"Agent envelope missing keys: {sorted(missing)}")
    return envelope


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
) -> str:
    template = load_template("bridge_reviewer_prompt.txt")
    reader_envelope = latest_envelope(conn, job["job_id"], role="reader") or {}
    payload = {
        "job_id": job["job_id"],
        "round_no": round_no,
        "task_text": job["task_text"],
        "wave_class": job["wave_class"] or "(unspecified)",
        "repo_root": str(paths.repo_root),
        "changed_files_actual": _format_list(changed_files(paths.repo_root, staged=False) + changed_files(paths.repo_root, staged=True)),
        "staged_files": _format_list(changed_files(paths.repo_root, staged=True)),
        "unstaged_files": _format_list(changed_files(paths.repo_root, staged=False)),
        "validation_results": _validation_results_text(validation_results),
        "reader_summary": reader_envelope.get("summary", "(none)"),
        "staged_diff": staged_diff_content(paths.repo_root),
        "json_schema_stub": JSON_SCHEMA_STUB,
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
    lines = [
        f"# Bridge Job {job_id}",
        "",
        f"- Status: {job['status']}",
        f"- Reader: {job['reader_agent']}",
        f"- Reviewer: {job['reviewer_agent']}",
        f"- Wave class: {job['wave_class'] or '(unspecified)'}",
        f"- Allow edits: {'yes' if job['allow_edits'] else 'no'}",
        f"- Max rounds: {job['max_rounds']}",
        "",
        "## Task",
        job['task_text'],
        "",
        "## Turns",
    ]
    for turn in turns:
        envelope = json.loads(turn["envelope_json"]) if turn["envelope_json"] else {}
        lines.extend(
            [
                f"### {turn['turn_id']} — {turn['agent_role']}",
                f"- Status: {turn['status']}",
                f"- Decision: {turn['decision'] or '(none)'}",
                f"- Summary: {envelope.get('summary', '(none)')}",
                f"- Claimed files: {', '.join(envelope.get('touched_files_claimed', [])) or '(none)'}",
                f"- Raw output: {turn['raw_output_path']}",
                "",
            ]
        )
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
) -> tuple[str, dict[str, Any], Path, Path, RepoState]:
    state_start = compute_repo_state(paths.repo_root)
    turn_id = f"r{round_no}-{agent_role}" if attempt <= 1 else f"r{round_no}-{agent_role}-a{attempt}"
    prompt_path = write_prompt(paths, job["job_id"], turn_id, prompt_text)
    started_at = utc_now()

    config = load_bridge_config(paths.config_path)
    adapter = get_adapter(config, adapter_name)
    output = run_adapter(
        adapter,
        prompt_text=prompt_text,
        prompt_path=prompt_path,
        repo_root=paths.repo_root,
        job_id=job["job_id"],
        turn_id=turn_id,
        agent_role=agent_role,
    )
    raw_output_path = write_raw_output(paths, job["job_id"], turn_id, output)
    envelope = parse_envelope(output)
    state_end = compute_repo_state(paths.repo_root)
    finished_at = utc_now()

    status = "completed"
    decision = envelope.get("decision", "ERROR")
    if decision == "STALE":
        status = "stale"
    record_turn(
        conn,
        turn_id=turn_id,
        job_id=job["job_id"],
        round_no=round_no,
        agent_role=agent_role,
        status=status,
        decision=decision,
        state_sha_start=state_start.state_sha,
        state_sha_end=state_end.state_sha,
        prompt_path=prompt_path,
        raw_output_path=raw_output_path,
        envelope=envelope,
        started_at=started_at,
        finished_at=finished_at,
    )
    return turn_id, envelope, prompt_path, raw_output_path, state_start


def run_job(paths: BridgePaths, job_id: str) -> str:
    init_db(paths)
    with _BridgeLock(paths.bus_dir / "bridge.lock"):
        return _run_job_locked(paths, job_id)


def _run_job_locked(paths: BridgePaths, job_id: str) -> str:
    with open_db(paths) as conn:
        job = read_job(conn, job_id)
        if job["terminal_decision"]:
            render_job(paths, conn, job_id)
            return job["terminal_decision"]

        acceptance_checks = json.loads(job["acceptance_checks_json"])
        for round_no in range(job["current_round"] + 1, job["max_rounds"] + 1):
            update_job_status(conn, job_id, "READER_RUNNING", current_round=round_no)
            job = read_job(conn, job_id)
            reader_state = compute_repo_state(paths.repo_root)
            reader_prompt = build_reader_prompt(conn, paths, job, round_no, reader_state)
            reader_turn_id, reader_envelope, _, _, _ = execute_agent_turn(
                conn,
                paths,
                job,
                round_no=round_no,
                agent_role="reader",
                adapter_name=job["reader_agent"],
                prompt_text=reader_prompt,
            )
            render_job(paths, conn, job_id)
            if reader_envelope.get("decision") in {"QUESTION", "ERROR"}:
                terminal = reader_envelope.get("decision")
                update_job_status(conn, job_id, "AWAITING_FOUNDER", current_round=round_no, terminal_decision=terminal)
                render_job(paths, conn, job_id)
                return terminal

            validation_results = run_validations(
                paths,
                conn,
                job_id=job_id,
                turn_id=reader_turn_id,
                acceptance_checks=acceptance_checks,
            )
            render_job(paths, conn, job_id)

            reviewer_attempt = 0
            reviewer_envelope: dict[str, Any] | None = None
            while reviewer_attempt < 2:
                reviewer_attempt += 1
                update_job_status(conn, job_id, "REVIEWER_RUNNING", current_round=round_no)
                review_state_start = compute_repo_state(paths.repo_root)
                reviewer_prompt = build_reviewer_prompt(conn, paths, read_job(conn, job_id), round_no, validation_results)
                reviewer_turn_id, reviewer_envelope, _, _, _ = execute_agent_turn(
                    conn,
                    paths,
                    read_job(conn, job_id),
                    round_no=round_no,
                    agent_role="reviewer",
                    adapter_name=job["reviewer_agent"],
                    prompt_text=reviewer_prompt,
                    attempt=reviewer_attempt,
                )
                review_state_end = compute_repo_state(paths.repo_root)
                if review_state_start.state_sha == review_state_end.state_sha:
                    break
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
                continue
            update_job_status(conn, job_id, "DONE", current_round=round_no, terminal_decision=decision or "ERROR")
            render_job(paths, conn, job_id)
            return decision or "ERROR"

        update_job_status(conn, job_id, "DONE", current_round=job["max_rounds"], terminal_decision="NO_GO")
        render_job(paths, conn, job_id)
        return "NO_GO"


def print_status(paths: BridgePaths, job_id: str) -> None:
    with open_db(paths) as conn:
        job = read_job(conn, job_id)
        print(json.dumps({
            "job_id": job["job_id"],
            "status": job["status"],
            "reader_agent": job["reader_agent"],
            "reviewer_agent": job["reviewer_agent"],
            "current_round": job["current_round"],
            "max_rounds": job["max_rounds"],
            "terminal_decision": job["terminal_decision"],
        }, indent=2))


def read_task_text(task: str | None, task_file: str | None) -> str:
    if bool(task) == bool(task_file):
        raise BridgeError("Provide exactly one of --task or --task-file")
    if task_file:
        return Path(task_file).read_text(encoding="utf-8").strip()
    assert task is not None
    return task.strip()


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

    status = sub.add_parser("status", help="Show current job status")
    status.add_argument("job_id")

    render = sub.add_parser("render", help="Render markdown transcript for a job")
    render.add_argument("job_id")

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
            decision = run_job(paths, args.job_id)
            print(decision)
            return 0 if decision == "GO" else 1
        if args.command == "status":
            print_status(paths, args.job_id)
            return 0
        if args.command == "render":
            with open_db(paths) as conn:
                output = render_job(paths, conn, args.job_id)
            print(output)
            return 0
    except (BridgeError, BridgeAdapterError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
