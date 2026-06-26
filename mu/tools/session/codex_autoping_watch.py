#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import signal
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


TMUX_SESSION = "rcx-pipeline"
TMUX_PANE = "rcx-pipeline:1.3"
DEFAULT_BUS_DIR = ".agent_bus"
BUS_DIR_RE = re.compile(r"^\.agent_bus-[A-Za-z0-9][A-Za-z0-9_-]*$")
DEFAULT_INTERVAL_S = 20.0
DEFAULT_INITIAL_DELAY_S = 30.0
DEFAULT_PING_TIMEOUT_S = 120.0
SUMMARY_PREFIX = "Autoping summary:"
CONTEXT_EXHAUSTED_STATUSES = frozenset(
    {"context_exhausted", "context_exhausted_paused", "context_exhausted_recovering"}
)
FRESH_EXEC_CONTEXT_RECOVERY_MODE = "fresh_exec_after_context_exhaustion"
CODEX_NO_TOOLS_DISABLED_FEATURES = (
    "apps",
    "apply_patch_freeform",
    "apply_patch_streaming_events",
    "artifact",
    "browser_use",
    "code_mode",
    "code_mode_only",
    "codex_git_commit",
    "computer_use",
    "image_generation",
    "js_repl",
    "js_repl_tools_only",
    "multi_agent",
    "multi_agent_v2",
    "plugins",
    "request_permissions_tool",
    "shell_snapshot",
    "shell_tool",
    "skill_mcp_dependency_install",
    "tool_call_mcp_elicitation",
    "tool_search",
    "tool_suggest",
    "unified_exec",
    "workspace_dependencies",
)
CODEX_NO_TOOLS_RESUME_ARGS = tuple(
    part
    for feature_name in CODEX_NO_TOOLS_DISABLED_FEATURES
    for part in ("--disable", feature_name)
)
CODEX_DIAGNOSTIC_RESUME_CONFIG = (
    "--ignore-user-config",
    "--ignore-rules",
    *CODEX_NO_TOOLS_RESUME_ARGS,
    "-c",
    'sandbox_mode="read-only"',
    "-c",
    'approval_policy="never"',
)
WORKTREE_SUFFIX_SCORES = {
    "/tools/agents/bridge_supervisor.py": 3,
    "/mu/tools/executors/phase_b_executor.py": 2,
    "/mu/tools/executors/phase_a_executor.py": 1,
}
WORKTREE_RE = re.compile(
    r"(?P<root>/[^\s\"']+?)"
    r"(?P<suffix>/tools/agents/bridge_supervisor\.py|/mu/tools/executors/phase_b_executor\.py|/mu/tools/executors/phase_a_executor\.py)"
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _codex_home() -> Path:
    override = os.environ.get("RCX_CODEX_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".codex"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def _autoping_state_slug(
    *,
    thread_id: str,
    repo_root: Path,
    bus_dir: str,
    tmux_session: str,
    tmux_pane: str,
) -> str:
    identity = "|".join(
        (
            str(repo_root.expanduser().resolve()),
            bus_dir,
            tmux_session,
            tmux_pane,
        )
    )
    return f"{_slug(thread_id)}__{_slug(identity)}"


def _validate_bus_dir(value: str | None) -> str:
    raw = (value or DEFAULT_BUS_DIR).strip().rstrip("/")
    if (
        not raw
        or "\\" in raw
        or "/" in raw
        or ".." in raw
        or raw.startswith("/")
        or (raw != DEFAULT_BUS_DIR and BUS_DIR_RE.fullmatch(raw) is None)
    ):
        raise ValueError(f"invalid active bus root: {raw!r}")
    return raw


def _resume_env() -> dict[str, str]:
    # Preserve the live shell environment so autoping resumes inherit the same
    # auth/session context and any repo-local RCX state overlay already in use.
    return os.environ.copy()


def _codex_resume_command(thread_id: str, prompt: str) -> list[str]:
    return [
        "codex",
        "exec",
        "resume",
        *CODEX_DIAGNOSTIC_RESUME_CONFIG,
        "--json",
        thread_id,
        prompt,
    ]


def _codex_fresh_exec_command(prompt: str) -> list[str]:
    return [
        "codex",
        "exec",
        *CODEX_DIAGNOSTIC_RESUME_CONFIG,
        "--json",
        prompt,
    ]


def _codex_ping_command(thread_id: str, prompt: str, *, fresh_exec: bool) -> list[str]:
    if fresh_exec:
        return _codex_fresh_exec_command(prompt)
    return _codex_resume_command(thread_id, prompt)


def _ping_timed_out(
    *,
    started_monotonic: float | None,
    timeout_s: float,
    now_monotonic: float | None = None,
) -> bool:
    if started_monotonic is None or timeout_s <= 0:
        return False
    now = time.monotonic() if now_monotonic is None else now_monotonic
    return now - started_monotonic >= timeout_s


def _terminate_process_group(proc: subprocess.Popen[str], *, grace_s: float = 5.0) -> None:
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return

    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=grace_s)
        return
    except subprocess.TimeoutExpired:
        pass

    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=grace_s)
    except subprocess.TimeoutExpired:
        return


def _run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            cmd,
            124,
            exc.stdout or "",
            f"TimeoutExpired: {exc}",
        )
    except OSError as exc:
        return subprocess.CompletedProcess(cmd, 127, "", f"{type(exc).__name__}: {exc}")


def _candidate_score_for_command(command: str) -> int:
    for suffix, score in WORKTREE_SUFFIX_SCORES.items():
        if suffix in command or suffix.lstrip("/") in command:
            return score
    return 0


def _repo_root_arg_from_command(command: str) -> Path | None:
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    for index, token in enumerate(tokens):
        if token == "--repo-root" and index + 1 < len(tokens):
            return Path(tokens[index + 1]).expanduser()
        if token.startswith("--repo-root="):
            return Path(token.split("=", 1)[1]).expanduser()
    return None


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.expanduser().resolve() == right.expanduser().resolve()
    except OSError:
        return left.expanduser().absolute() == right.expanduser().absolute()


def _extract_worktree_candidates(ps_output: str) -> list[tuple[int, int, Path]]:
    candidates: list[tuple[int, int, Path]] = []
    for raw_line in ps_output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        pid_text, _, command = line.partition(" ")
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        seen_roots: set[str] = set()
        match = WORKTREE_RE.search(command)
        if match:
            suffix = match.group("suffix")
            score = WORKTREE_SUFFIX_SCORES.get(suffix, 0)
            root = Path(match.group("root"))
            candidates.append((score, pid, root))
            seen_roots.add(str(root))
        repo_root_arg = _repo_root_arg_from_command(command)
        repo_root_score = _candidate_score_for_command(command)
        if repo_root_arg is not None and repo_root_score > 0:
            key = str(repo_root_arg)
            if key not in seen_roots:
                candidates.append((repo_root_score, pid, repo_root_arg))
    return candidates


def _discover_active_wave_root(
    repo_root: Path | None = None,
    *,
    bus_dir: str = DEFAULT_BUS_DIR,
) -> Path | None:
    resolved_repo_root = repo_root.expanduser().resolve() if repo_root else None
    proc = _run(["ps", "-Ao", "pid=,command="], timeout=15)
    if proc.returncode == 0:
        candidates = _extract_worktree_candidates(proc.stdout)
        if resolved_repo_root is not None:
            candidates = [
                candidate for candidate in candidates
                if _same_path(candidate[2], resolved_repo_root)
            ]
        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
            return candidates[0][2]

    if resolved_repo_root is not None:
        bridge_db = resolved_repo_root / bus_dir / "bridge.db"
        return resolved_repo_root if bridge_db.exists() else None

    fallback_roots: list[Path] = []
    for base in (Path("/private/tmp"), Path("/tmp")):
        if not base.exists():
            continue
        fallback_roots.extend(base.glob(f"workingrcx*/{bus_dir}/bridge.db"))

    if not fallback_roots:
        return None

    fallback_roots.sort(
        key=lambda path: path.stat().st_mtime if path.exists() else 0.0,
        reverse=True,
    )
    return fallback_roots[0].parents[1]


def _read_bridge_state(
    wave_root: Path | None,
    *,
    bus_dir: str = DEFAULT_BUS_DIR,
) -> dict[str, object]:
    if wave_root is None:
        return {
            "wave_root": None,
            "bridge_db": None,
            "bus_dir": bus_dir,
            "job": None,
            "turn": None,
            "wave_root_missing": True,
        }

    bridge_db = wave_root / bus_dir / "bridge.db"
    result: dict[str, object] = {
        "wave_root": str(wave_root),
        "bridge_db": str(bridge_db),
        "bus_dir": bus_dir,
        "job": None,
        "turn": None,
    }
    if not bridge_db.exists():
        result["bridge_db_missing"] = True
        return result

    try:
        conn = sqlite3.connect(str(bridge_db))
        conn.row_factory = sqlite3.Row
        try:
            job = conn.execute(
                "SELECT job_id, status, COALESCE(terminal_decision, '-') AS decision "
                "FROM jobs ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            turn = None
            if job:
                turn = conn.execute(
                    "SELECT turn_id, job_id, agent_role, status, "
                    "COALESCE(decision, '-') AS decision "
                    "FROM turns WHERE job_id = ? ORDER BY rowid DESC LIMIT 1",
                    (job["job_id"],),
                ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        result["bridge_db_degraded"] = True
        result["bridge_db_error"] = f"{type(exc).__name__}: {exc}"
        return result

    if job:
        result["job"] = dict(job)
    if turn:
        result["turn"] = dict(turn)
    return result


def _read_tmux_tail(pane: str) -> list[str]:
    proc = _run(["tmux", "capture-pane", "-p", "-t", pane], timeout=10)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "tmux capture failed").strip()
        return [detail]
    return [line.rstrip() for line in proc.stdout.splitlines()[-12:]]


def _bridge_state_signature(bridge_state: dict[str, object], tmux_tail: list[str]) -> str:
    payload = {
        "job": bridge_state.get("job"),
        "turn": bridge_state.get("turn"),
        "bus_dir": bridge_state.get("bus_dir"),
        "wave_root": bridge_state.get("wave_root"),
        "tmux_tail": [line for line in tmux_tail if line.strip()],
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _attention_required_summary(
    bridge_state: dict[str, object],
    tmux_tail: list[str] | None = None,
) -> str | None:
    tail_text = "\n".join(tmux_tail or [])
    hard_fail_markers = ("executor_hard_fail", "pipeline_hard_fail")
    for marker in hard_fail_markers:
        if marker not in tail_text:
            continue
        job = bridge_state.get("job")
        job_id = "unknown-job"
        if isinstance(job, dict):
            job_id = str(job.get("job_id") or job_id).strip()
        return _clip_summary(
            "attention required: "
            f"tmux/pager tail reports `{marker}` for latest visible pipeline "
            f"state while bridge latest job is `{job_id}`; foreground operator "
            "diagnosis is required"
        )

    job = bridge_state.get("job")
    turn = bridge_state.get("turn")
    if not isinstance(job, dict) or not isinstance(turn, dict):
        return None

    turn_status = str(turn.get("status") or "").strip()
    turn_decision = str(turn.get("decision") or "").strip()
    failed_turn = turn_status.lower() in {"failed", "stale"} or turn_decision.upper() in {
        "ERROR",
        "STALE",
    }
    if not failed_turn:
        return None

    job_id = str(job.get("job_id") or "unknown-job").strip()
    turn_job_id = str(turn.get("job_id") or "").strip()
    if turn_job_id and turn_job_id != job_id:
        return None

    job_status = str(job.get("status") or "unknown").strip()
    turn_id = str(turn.get("turn_id") or "unknown-turn").strip()
    role = str(turn.get("agent_role") or "agent").strip()
    return _clip_summary(
        "attention required: "
        f"job `{job_id}` is `{job_status}` while latest {role} turn "
        f"`{turn_id}` is `{turn_status or 'unknown'}`/"
        f"`{turn_decision or '-'}`; foreground operator action is required"
    )


def _idle_no_wave_summary(
    *,
    repo_root: Path,
    bus_dir: str,
    bridge_state: dict[str, object],
) -> str:
    wave_root = bridge_state.get("wave_root")
    if wave_root:
        reason = "no latest bridge job"
        context_name = "wave_root"
        context_value = str(wave_root)
    else:
        reason = "no active wave root"
        context_name = "repo_root"
        context_value = str(repo_root)
    return _clip_summary(
        "idle/no active wave; no foreground action required: "
        f"{reason} using bus `{bus_dir}` for {context_name} `{context_value}`",
        limit=500,
    )


def _strip_message_preamble(text: str) -> str:
    cleaned = text.replace("\r", "\n").strip()
    if cleaned.startswith("Contract active: founder XML + repo protocol in force."):
        parts = cleaned.split("\n\n", 1)
        cleaned = parts[1] if len(parts) == 2 else ""
    return cleaned


def _flatten_message_text(text: str) -> str:
    cleaned = _strip_message_preamble(text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _extract_summary_line(text: str) -> str | None:
    cleaned = _strip_message_preamble(text)
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line.startswith(SUMMARY_PREFIX):
            continue
        summary = line[len(SUMMARY_PREFIX):].strip()
        if summary:
            return summary
    return None


def _clip_summary(text: str, limit: int = 220) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _extract_last_agent_summary(log_path: Path) -> str | None:
    if not log_path.exists():
        return None

    last_summary: str | None = None
    for raw_line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if payload.get("type") != "item.completed":
            continue
        item = payload.get("item") or {}
        if item.get("type") not in {"agent_message", "message"}:
            continue
        text = item.get("text")
        if not text and item.get("content"):
            parts: list[str] = []
            for chunk in item["content"]:
                if chunk.get("type") == "output_text":
                    parts.append(str(chunk.get("text") or ""))
            text = "\n".join(parts)
        if not text:
            continue
        summary = _extract_summary_line(str(text))
        if summary:
            last_summary = summary

    if not last_summary:
        return None
    return _clip_summary(last_summary)


def _extract_ping_error_summary(log_path: Path) -> str | None:
    if not log_path.exists():
        return None

    last_error = ""
    for raw_line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if payload.get("type") == "error":
            last_error = str(payload.get("message") or "").strip()
        elif payload.get("type") == "turn.failed":
            error = payload.get("error") or {}
            if isinstance(error, dict):
                last_error = str(error.get("message") or "").strip()
    if not last_error:
        return None
    if "context window" in last_error.lower() or "ran out of room" in last_error.lower():
        return (
            "autoping primary Codex thread context window is exhausted; "
            "switching future watchdog ticks to fresh exec diagnostic mode"
        )
    return _clip_summary(f"autoping wake failed: {last_error}")


def _is_context_exhausted_summary(summary: str | None) -> bool:
    return bool(summary and "context window is exhausted" in summary.lower())


def _state_context_exhausted_for_thread(state: dict[str, object], thread_id: str) -> bool:
    recorded_thread = str(state.get("thread_id") or "").strip()
    if recorded_thread != thread_id:
        return False
    status = str(state.get("status") or "").strip().lower()
    return status in CONTEXT_EXHAUSTED_STATUSES


def _state_requires_fresh_exec_for_thread(state: dict[str, object], thread_id: str) -> bool:
    recorded_thread = str(state.get("thread_id") or "").strip()
    if recorded_thread != thread_id:
        return False
    return (
        _state_context_exhausted_for_thread(state, thread_id)
        or state.get("primary_thread_context_exhausted") is True
    )


def _initial_status_for_state(state: dict[str, object], thread_id: str) -> str:
    if _state_requires_fresh_exec_for_thread(state, thread_id):
        return "context_exhausted_recovering"
    return "initial_delay"


def _notify_tmux_summary(session: str, summary: str) -> None:
    if not summary:
        return
    _run(
        ["tmux", "display-message", "-d", "8000", "-t", session, f"AUTO-PING: {summary}"],
        timeout=5,
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_state(path: Path, payload: dict[str, object]) -> None:
    merged = _read_state(path)
    merged.update(payload)
    _write_text(path, json.dumps(merged, indent=2, sort_keys=True) + "\n")


def _status_for_ping_summary(summary: str | None, *, timed_out: bool = False) -> str:
    if not _is_context_exhausted_summary(summary):
        return "prior_ping_timed_out" if timed_out else "prior_ping_finished"
    if timed_out:
        return "context_exhausted_paused"
    return "context_exhausted"


def _should_suppress_unchanged_state(
    state: dict[str, object],
    bridge_signature: str,
    *,
    recovering_context_now: bool,
) -> bool:
    return (
        not recovering_context_now
        and state.get("last_bridge_signature") == bridge_signature
        and bool(state.get("last_summary"))
    )


def _render_prompt(
    *,
    bridge_state: dict[str, object],
    tmux_tail: list[str],
    summary_path: Path,
    bus_dir: str = DEFAULT_BUS_DIR,
) -> str:
    return (
        "Autonomous WorkingRCX pipeline watchdog tick.\n"
        "Continue monitoring the live pipeline without waiting for the user.\n"
        "Do not run shell commands, tests, preflight checks, or tools from this watchdog wake path; use only the bridge state and tmux tail embedded in this prompt.\n"
        "If the pipeline is moving normally, do not ask the user anything and do not mutate it.\n"
        "If the pipeline is stalled, broken, or needs intervention, diagnose it and summarize the narrowest operator-visible next action without mutating repo files.\n"
        "Do not edit files, run git add/commit/push, or apply structural fixes from this watchdog wake path.\n"
        "Do not run pytest, docs consistency, preflight, or other broad validation suites from this watchdog wake path; inspect only the provided state, lightweight process status, tmux pane text, and existing logs/artifacts.\n"
        "Do not launch or relaunch executor_dispatch.py, phase_a_executor.py, phase_b_executor.py, commit_executor.py, or bridge_supervisor.py from this watchdog wake path.\n"
        "Do not background a new pipeline process from this headless resumed turn.\n"
        "Do not interrupt an active healthy supervisor or reviewer just because it is still running.\n"
        f"Always end with one concise final summary sentence beginning '{SUMMARY_PREFIX}' "
        "that states what you checked and whether you intervened. The watcher will persist that final summary; do not write the summary file yourself.\n\n"
        f"Active bus root: {bus_dir}\n"
        f"Latest bridge state: {json.dumps(bridge_state, ensure_ascii=True)}\n"
        f"Latest tmux tail: {json.dumps(tmux_tail, ensure_ascii=True)}\n"
        f"Watcher summary path: {summary_path}\n"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WorkingRCX Codex autoping watcher")
    parser.add_argument("--repo-root", default=str(_repo_root()))
    parser.add_argument("--thread-id", default=os.environ.get("CODEX_THREAD_ID", ""))
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_S)
    parser.add_argument("--initial-delay", type=float, default=DEFAULT_INITIAL_DELAY_S)
    parser.add_argument("--ping-timeout", type=float, default=DEFAULT_PING_TIMEOUT_S)
    parser.add_argument("--bus-dir", default=os.environ.get("RCX_AGENT_BUS_DIR", DEFAULT_BUS_DIR))
    parser.add_argument("--tmux-session", default=TMUX_SESSION)
    parser.add_argument("--tmux-pane", default=TMUX_PANE)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.thread_id:
        print("[autoping] CODEX_THREAD_ID is required", flush=True)
        return 2

    try:
        bus_dir = _validate_bus_dir(args.bus_dir)
    except ValueError as exc:
        print(f"[autoping] {exc}", flush=True)
        return 2
    if args.tmux_pane == TMUX_PANE and args.tmux_session != TMUX_SESSION:
        args.tmux_pane = f"{args.tmux_session}:1.3"

    repo_root = Path(args.repo_root).resolve()
    codex_home = _codex_home()
    state_dir = codex_home / "state"
    log_dir = codex_home / "log" / "autoping"
    state_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    thread_slug = _autoping_state_slug(
        thread_id=args.thread_id,
        repo_root=repo_root,
        bus_dir=bus_dir,
        tmux_session=args.tmux_session,
        tmux_pane=args.tmux_pane,
    )
    state_path = state_dir / f"rcx_autoping_{thread_slug}.json"
    summary_path = state_dir / f"rcx_autoping_{thread_slug}_summary.txt"

    print(
        f"[autoping] initial_delay_s={args.initial_delay} "
        f"thread_id={args.thread_id} repo_root={repo_root} bus_dir={bus_dir}",
        flush=True,
    )
    initial_status = _initial_status_for_state(_read_state(state_path), args.thread_id)
    _write_state(
        state_path,
        {
            "updated_at": _now(),
            "watcher_pid": os.getpid(),
            "thread_id": args.thread_id,
            "state_key": thread_slug,
            "status": initial_status,
            "active_pid": None,
            "active_log": None,
            "active_mode": None,
            "last_exit_code": None,
            "repo_root": str(repo_root),
            "bus_dir": bus_dir,
            "tmux_session": args.tmux_session,
            "tmux_pane": args.tmux_pane,
            "primary_thread_context_exhausted": (
                initial_status == "context_exhausted_recovering"
            ),
            "pause_reason": (
                "current Codex thread context window is exhausted; using fresh exec diagnostics"
                if initial_status == "context_exhausted_recovering"
                else ""
            ),
            "summary_path": str(summary_path),
        },
    )
    time.sleep(args.initial_delay)

    active_proc: subprocess.Popen[str] | None = None
    active_log: Path | None = None
    active_mode: str | None = None
    active_started_monotonic: float | None = None

    while True:
        if active_proc is not None:
            exit_code = active_proc.poll()
            if exit_code is None:
                elapsed_s = (
                    time.monotonic() - active_started_monotonic
                    if active_started_monotonic is not None
                    else 0.0
                )
                summary = _extract_last_agent_summary(active_log) if active_log else None
                if summary:
                    completed_pid = active_proc.pid
                    _terminate_process_group(active_proc)
                    _write_text(summary_path, summary + "\n")
                    _notify_tmux_summary(args.tmux_session, summary)
                    status = _status_for_ping_summary(summary)
                    _write_state(
                        state_path,
                        {
                            "updated_at": _now(),
                            "watcher_pid": os.getpid(),
                            "thread_id": args.thread_id,
                            "status": status,
                            "active_pid": None,
                            "active_log": None,
                            "active_mode": active_mode,
                            "last_exit_code": 0,
                            "last_completed_at": _now(),
                            "last_completed_pid": completed_pid,
                            "last_completed_log": str(active_log or ""),
                            "last_summary": summary,
                            "last_summary_elapsed_s": round(elapsed_s, 1),
                            "terminated_after_summary": True,
                            "summary_path": str(summary_path),
                        },
                    )
                    print(
                        "[autoping] prior_ping_summary_received "
                        f"pid={completed_pid} elapsed_s={elapsed_s:.1f} "
                        f"active_log={active_log}",
                        flush=True,
                    )
                    active_proc = None
                    active_log = None
                    active_mode = None
                    active_started_monotonic = None
                    if status == "context_exhausted":
                        _write_state(
                            state_path,
                            {
                                "primary_thread_context_exhausted": True,
                                "recovery_mode": FRESH_EXEC_CONTEXT_RECOVERY_MODE,
                                "pause_reason": (
                                    "current Codex thread context window is exhausted; "
                                    "using fresh exec diagnostics"
                                ),
                            },
                        )
                        time.sleep(args.interval)
                        continue
                    time.sleep(args.interval)
                    continue

                if _ping_timed_out(
                    started_monotonic=active_started_monotonic,
                    timeout_s=args.ping_timeout,
                ):
                    timed_out_pid = active_proc.pid
                    _terminate_process_group(active_proc)
                    exit_code = active_proc.returncode
                    summary = _extract_last_agent_summary(active_log) if active_log else None
                    if summary is None and active_log is not None:
                        summary = _extract_ping_error_summary(active_log)
                    if summary is None:
                        summary = (
                            "autoping wake timed out after "
                            f"{int(elapsed_s)}s without an Autoping summary; "
                            f"terminated stale resume pid={timed_out_pid}"
                        )
                    _write_text(summary_path, summary + "\n")
                    _notify_tmux_summary(args.tmux_session, summary)
                    status = _status_for_ping_summary(summary, timed_out=True)
                    state_update = {
                        "updated_at": _now(),
                        "watcher_pid": os.getpid(),
                        "thread_id": args.thread_id,
                        "status": status,
                        "active_pid": None,
                        "active_log": None,
                        "active_mode": active_mode,
                        "last_exit_code": exit_code if exit_code is not None else 124,
                        "last_completed_at": _now(),
                        "last_completed_pid": timed_out_pid,
                        "last_completed_log": str(active_log or ""),
                        "last_summary": summary,
                        "last_timeout_elapsed_s": round(elapsed_s, 1),
                        "summary_path": str(summary_path),
                    }
                    if status == "context_exhausted_paused":
                        state_update.update(
                            {
                                "primary_thread_context_exhausted": True,
                                "recovery_mode": FRESH_EXEC_CONTEXT_RECOVERY_MODE,
                                "last_paused_at": _now(),
                                "pause_reason": (
                                    "current Codex thread context window is exhausted; "
                                    "using fresh exec diagnostics"
                                ),
                            }
                        )
                    _write_state(
                        state_path,
                        state_update,
                    )
                    print(
                        f"[autoping] {status} "
                        f"pid={timed_out_pid} elapsed_s={elapsed_s:.1f} "
                        f"active_log={active_log}",
                        flush=True,
                    )
                    active_proc = None
                    active_log = None
                    active_mode = None
                    active_started_monotonic = None
                    if status == "context_exhausted_paused":
                        time.sleep(args.interval)
                        continue
                    time.sleep(args.interval)
                    continue

                _write_state(
                    state_path,
                    {
                        "updated_at": _now(),
                        "watcher_pid": os.getpid(),
                        "thread_id": args.thread_id,
                        "status": "waiting_for_prior_ping",
                        "active_pid": active_proc.pid,
                        "active_log": str(active_log or ""),
                        "active_mode": active_mode,
                        "last_exit_code": None,
                        "active_elapsed_s": round(elapsed_s, 1),
                        "summary_path": str(summary_path),
                    },
                )
                print(
                    f"[autoping] waiting active_pid={active_proc.pid} active_log={active_log}",
                    flush=True,
                )
                time.sleep(args.interval)
                continue

            summary = _extract_last_agent_summary(active_log) if active_log else None
            if summary is None and active_log is not None:
                summary = _extract_ping_error_summary(active_log)
            if summary:
                _write_text(summary_path, summary + "\n")
                _notify_tmux_summary(args.tmux_session, summary)
                print(f"[autoping][summary] {summary}", flush=True)
            status = _status_for_ping_summary(summary)
            _write_state(
                state_path,
                {
                    "updated_at": _now(),
                    "watcher_pid": os.getpid(),
                    "thread_id": args.thread_id,
                    "status": status,
                    "active_pid": None,
                    "active_log": None,
                    "active_mode": active_mode,
                    "last_exit_code": exit_code,
                    "last_completed_at": _now(),
                    "last_completed_pid": active_proc.pid,
                    "last_completed_log": str(active_log or ""),
                    "last_summary": summary or "",
                    "summary_path": str(summary_path),
                },
            )
            print(
                f"[autoping] prior_ping_finished pid={active_proc.pid} exit_code={exit_code}",
                flush=True,
            )
            active_proc = None
            active_log = None
            active_mode = None
            active_started_monotonic = None
            if status == "context_exhausted":
                _write_state(
                    state_path,
                    {
                        "primary_thread_context_exhausted": True,
                        "recovery_mode": FRESH_EXEC_CONTEXT_RECOVERY_MODE,
                        "pause_reason": (
                            "current Codex thread context window is exhausted; "
                            "using fresh exec diagnostics"
                        ),
                    },
                )
                time.sleep(args.interval)
                continue

        state = _read_state(state_path)
        use_fresh_exec = _state_requires_fresh_exec_for_thread(state, args.thread_id)
        recovering_context_now = _state_context_exhausted_for_thread(state, args.thread_id)

        wave_root = _discover_active_wave_root(repo_root, bus_dir=bus_dir)
        bridge_state = _read_bridge_state(wave_root, bus_dir=bus_dir)
        tmux_tail = _read_tmux_tail(args.tmux_pane)
        bridge_signature = _bridge_state_signature(bridge_state, tmux_tail)

        if wave_root is None or bridge_state.get("job") is None:
            idle_summary = _idle_no_wave_summary(
                repo_root=repo_root,
                bus_dir=bus_dir,
                bridge_state=bridge_state,
            )
            _write_text(summary_path, idle_summary + "\n")
            _write_state(
                state_path,
                {
                    "updated_at": _now(),
                    "watcher_pid": os.getpid(),
                    "thread_id": args.thread_id,
                    "status": "idle_no_wave",
                    "active_pid": None,
                    "active_log": None,
                    "active_mode": None,
                    "last_exit_code": None,
                    "wave_root": str(wave_root) if wave_root else None,
                    "last_idle_at": _now(),
                    "last_bridge_signature": bridge_signature,
                    "last_summary": idle_summary,
                    "summary_path": str(summary_path),
                    "bridge_state": bridge_state,
                    "tmux_tail": tmux_tail,
                },
            )
            time.sleep(args.interval)
            continue

        attention_summary = _attention_required_summary(bridge_state, tmux_tail)
        if attention_summary:
            _write_text(summary_path, attention_summary + "\n")
            _notify_tmux_summary(args.tmux_session, attention_summary)
            _write_state(
                state_path,
                {
                    "updated_at": _now(),
                    "watcher_pid": os.getpid(),
                    "thread_id": args.thread_id,
                    "status": "attention_required",
                    "active_pid": None,
                    "active_log": None,
                    "active_mode": None,
                    "last_exit_code": None,
                    "last_attention_at": _now(),
                    "last_bridge_signature": bridge_signature,
                    "last_summary": attention_summary,
                    "summary_path": str(summary_path),
                    "bridge_state": bridge_state,
                    "tmux_tail": tmux_tail,
                },
            )
            print(
                "[autoping] attention_required "
                f"wave_root={wave_root} job={bridge_state.get('job')} "
                f"turn={bridge_state.get('turn')}",
                flush=True,
            )
            time.sleep(args.interval)
            continue

        state = _read_state(state_path)
        if _should_suppress_unchanged_state(
            state,
            bridge_signature,
            recovering_context_now=recovering_context_now,
        ):
            _write_state(
                state_path,
                {
                    "updated_at": _now(),
                    "watcher_pid": os.getpid(),
                    "thread_id": args.thread_id,
                    "status": "idle_unchanged_state",
                    "active_pid": None,
                    "active_log": None,
                    "active_mode": None,
                    "last_exit_code": None,
                    "last_skipped_at": _now(),
                    "last_bridge_signature": bridge_signature,
                    "summary_path": str(summary_path),
                    "bridge_state": bridge_state,
                    "tmux_tail": tmux_tail,
                },
            )
            print(
                "[autoping] unchanged_state_suppressed "
                f"wave_root={wave_root} job={bridge_state.get('job')} "
                f"turn={bridge_state.get('turn')}",
                flush=True,
            )
            time.sleep(args.interval)
            continue

        prompt = _render_prompt(
            bridge_state=bridge_state,
            tmux_tail=tmux_tail,
            summary_path=summary_path,
            bus_dir=bus_dir,
        )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        active_mode = FRESH_EXEC_CONTEXT_RECOVERY_MODE if use_fresh_exec else "resume"
        active_log = log_dir / f"autoping_{active_mode}_{stamp}.jsonl"
        with active_log.open("w", encoding="utf-8") as sink:
            active_proc = subprocess.Popen(
                _codex_ping_command(args.thread_id, prompt, fresh_exec=use_fresh_exec),
                cwd=str(repo_root),
                stdin=subprocess.DEVNULL,
                stdout=sink,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
                env=_resume_env(),
            )
        active_started_monotonic = time.monotonic()
        _write_state(
            state_path,
            {
                "updated_at": _now(),
                "watcher_pid": os.getpid(),
                "thread_id": args.thread_id,
                "status": "fresh_exec_ping_dispatched" if use_fresh_exec else "ping_dispatched",
                "active_pid": active_proc.pid,
                "active_log": str(active_log),
                "active_mode": active_mode,
                "last_exit_code": None,
                "last_dispatched_at": _now(),
                "last_dispatched_pid": active_proc.pid,
                "summary_path": str(summary_path),
                "bridge_state": bridge_state,
                "last_bridge_signature": bridge_signature,
                "tmux_tail": tmux_tail,
                "primary_thread_context_exhausted": bool(use_fresh_exec),
                "recovery_mode": active_mode if use_fresh_exec else "",
            },
        )
        print(
            "[autoping] dispatched "
            f"mode={active_mode} pid={active_proc.pid} wave_root={wave_root} job={bridge_state.get('job')} "
            f"turn={bridge_state.get('turn')} log={active_log} summary={summary_path}",
            flush=True,
        )
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
