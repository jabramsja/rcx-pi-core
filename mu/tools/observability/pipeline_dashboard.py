#!/usr/bin/env python3
"""Real-time pipeline dashboard. Read-only — safe to run alongside active pipeline."""

import argparse
import glob as _glob
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
REFRESH_INTERVAL = 5
RECOVERY_LOG_REL = Path(".agent_bus") / "recovery" / "recovery_log.json"
RECOVERY_STATUS_REL = Path(".agent_bus") / "recovery" / "recovery_status.json"
_HUNG_THRESHOLD_SECONDS = 90

# Colors
R = "\033[0m"    # reset
B = "\033[1m"    # bold
D = "\033[2m"    # dim
RED = "\033[31m"
GRN = "\033[32m"
YEL = "\033[33m"
MAG = "\033[35m"
CYN = "\033[36m"
GRY = "\033[90m"

PHASE_C = {"post-merge": CYN, "phase-a": YEL, "phase-b": MAG, "commit": GRN, "dispatch": CYN, "idle": GRY}
DEC_C = {"GO": GRN, "COMMIT_GO": GRN, "COMMIT_GO_HOLD_PUSH": YEL, "REQUEST_CHANGES": YEL, "NO_GO": RED,
         "NEEDS_PHASE_B": YEL, "NEEDS_PHASE_A": YEL, "QUESTION": MAG, "ERROR": RED, "STALE": RED}
W = 72  # box width


def box_top():    return f"{B}╔{'═' * W}╗{R}"
def box_mid():    return f"{B}╠{'═' * W}╣{R}"
def box_bot():    return f"{B}╚{'═' * W}╝{R}"
def box_line(s):  return f"{B}║{R} {s}"
def box_blank():  return f"{B}║{R}"
def section(s):   return box_line(f"{B}{D}─── {s} ───{R}")


def elapsed(t):
    if not t: return "?"
    d = max(0, time.time() - t)
    m, s = divmod(int(d), 60)
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{s:02d}s"


def _read_recovery_status(repo_root: Path) -> dict[str, Any]:
    path = repo_root / RECOVERY_STATUS_REL
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_recovery_attempts(repo_root: Path) -> list[dict[str, Any]]:
    path = repo_root / RECOVERY_LOG_REL
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    attempts = data.get("attempts", [])
    return attempts if isinstance(attempts, list) else []


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_seconds(value: str, *, now: datetime) -> int | None:
    parsed = _parse_iso(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0, int((now - parsed).total_seconds()))


def _elapsed_seconds(seconds: int | None) -> str:
    if seconds is None:
        return "unknown"
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        minutes, rem = divmod(seconds, 60)
        return f"{minutes}m {rem:02d}s"
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    return f"{hours}h {minutes:02d}m"


def _excerpt(value: Any, limit: int = 110) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", "\n").strip()
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    excerpt = lines[-1] if lines else text
    if len(excerpt) <= limit:
        return excerpt
    return excerpt[: limit - 3].rstrip() + "..."


def _is_unhelpful_recovery_text(text: str) -> bool:
    cleaned = (text or "").strip()
    if not cleaned:
        return True
    if len(cleaned) <= 2 and " " not in cleaned:
        return True
    if re.fullmatch(r"[\d,\s]+", cleaned):
        return True
    if cleaned.lower().startswith("tokens used"):
        return True
    return False


def _is_generic_recovery_reason(text: str) -> bool:
    return bool(re.fullmatch(
        r"[a-z0-9_-]+:\s+(failed|error|partial|success|held|unknown)",
        (text or "").strip().lower(),
    ))


def _pid_state(pid_value: Any) -> tuple[int, str]:
    try:
        pid = int(pid_value)
    except (TypeError, ValueError):
        return 0, ""
    if pid <= 0:
        return 0, ""
    try:
        os.kill(pid, 0)
    except OSError:
        return pid, "dead"
    return pid, "alive"


def _human_target(target: str) -> str:
    cleaned = (target or "").strip()
    mapping = {
        "phase_a_executor": "Phase A",
        "phase_a": "Phase A",
        "phase_b_executor": "Phase B",
        "phase_b": "Phase B",
        "commit_executor": "Commit",
        "commit": "Commit",
        "executor_dispatch": "Dispatch",
    }
    return mapping.get(cleaned, cleaned.replace("_", " "))


def _human_failure_class(value: str) -> str:
    cleaned = (value or "").strip()
    mapping = {
        "process_timeout": "a step timed out",
        "agent_review_crash": "a review subprocess crashed",
        "test_failure": "a validation step failed",
        "transient_kill": "a process was killed unexpectedly",
        "mixed_staging": "git staging got into a mixed state",
        "stale_bridge_lock": "a stale bridge lock blocked progress",
        "stale_executor_state": "stale executor state blocked progress",
        "stale_continuation": "a stale continuation file blocked progress",
        "pr_merge_conflict": "the PR could not merge cleanly after the base branch moved",
        "git_staging_conflict": "git staging failed",
        "aggregation_hang": "bridge aggregation stalled",
        "implementer_stale": "the implementer output went stale",
        "unknown_error": "an unknown control-plane error happened",
    }
    return mapping.get(cleaned, cleaned.replace("_", " "))


def _human_recovery_state(value: str) -> str:
    cleaned = (value or "").strip()
    mapping = {
        "tier1_unhandled": "could not apply the simple automatic fix",
        "tier2_fixing": "applying a deterministic fix",
        "tier2_fixed": "applied the deterministic fix",
        "tier2_failed": "the deterministic fix failed",
        "tier2_unhandled": "no safe deterministic fix was available",
        "tier3_waiting_on_claude": "asking the recovery agent what to try",
        "tier3_timeout": "the recovery agent timed out",
        "tier3_error": "the recovery agent hit an execution error",
        "tier3_parse_error": "the recovery agent answered in the wrong format",
        "tier3_running_shell": "running a shell fix",
        "tier3_applying_edit": "applying a file edit",
        "tier3_verifying": "checking whether the fix worked",
        "tier3_verify_pass": "verified that the fix worked",
        "tier3_verify_failed": "the proposed fix did not verify",
        "tier3_retry_requested": "asked the pipeline to retry the failed step",
        "tier3_skipped": "decided recovery should not touch this",
        "tier3_escalated": "gave the problem back for human follow-up",
        "tier3_exhausted": "used all allowed recovery tries",
        "tier4_escalated": "stopped because policy says not to recover this",
    }
    return mapping.get(cleaned, cleaned.replace("_", " "))


def _human_recovery_outcome(value: str, *, recovered: bool) -> str:
    cleaned = (value or "").strip().lower()
    if cleaned == "cleared":
        return "a later success cleared the earlier issue"
    if cleaned == "success":
        return "recovery worked"
    if cleaned == "failed":
        return "recovery failed"
    if cleaned == "exhausted":
        return "recovery ran out of tries"
    if cleaned == "escalated":
        return "recovery stopped for human follow-up"
    if cleaned and recovered:
        return f"recovery finished with {cleaned}"
    if cleaned:
        return cleaned.replace("_", " ")
    return "completed"


def _rendered_recovery_reason(status: dict[str, Any]) -> tuple[str, str]:
    reason = _excerpt(status.get("reason", ""))
    detail = _excerpt(status.get("detail", ""))
    explanation = _excerpt(status.get("explanation", ""))
    if reason and not _is_unhelpful_recovery_text(reason) and not _is_generic_recovery_reason(reason):
        return reason, "reason"
    if detail and not _is_unhelpful_recovery_text(detail):
        return detail, "detail"
    if reason and not _is_unhelpful_recovery_text(reason):
        return reason, "reason"
    if explanation and not _is_unhelpful_recovery_text(explanation):
        return explanation, "explanation"
    return "", ""


def _format_recovery_pid_line(status: dict[str, Any], *, active: bool) -> str:
    owner_pid, owner_state = _pid_state(status.get("owner_pid"))
    child_pid, child_state = _pid_state(status.get("child_pid"))
    child_role = _excerpt(status.get("child_role", ""), 24)
    if not owner_pid and not child_pid:
        return ""

    parts: list[str] = []
    if owner_pid:
        owner_label = f"Owner PID: {owner_pid}"
        if owner_state:
            if not active and owner_state == "dead":
                owner_label += " (dead, historical)"
            else:
                owner_label += f" ({owner_state})"
        parts.append(owner_label)
    if child_pid:
        child_label = f"{child_role or 'child'} PID: {child_pid}"
        if child_state:
            if not active and child_state == "dead":
                child_label += " (dead, historical)"
            else:
                child_label += f" ({child_state})"
        parts.append(child_label)
    return "  " + " · ".join(parts)


def _attempt_matches_wave_step(attempt: dict[str, Any], wave_id: str, step: str) -> bool:
    if wave_id and str(attempt.get("wave_id", "")).strip() != wave_id:
        return False
    if step and str(attempt.get("step", "")).strip() != step:
        return False
    return True


def _is_trivial_recovery_attempt(attempt: dict[str, Any]) -> bool:
    action = str(attempt.get("action", "")).strip().lower()
    outcome = str(attempt.get("outcome", "")).strip().lower()
    return action in {"noop", "no_fix_registered"} and outcome in {"failed", "skipped"}


def _recent_recovery_attempt_lines(
    repo_root: Path, status: dict[str, Any], *, limit: int = 3,
) -> list[str]:
    attempts = _read_recovery_attempts(repo_root)
    if not attempts:
        return []

    invocation_id = str(status.get("invocation_id", "")).strip()
    wave_id = str(status.get("wave_id", "")).strip()
    step = str(status.get("step", "")).strip()
    failure_class = str(status.get("failure_class", "")).strip()

    matches: list[dict[str, Any]] = []
    for attempt in reversed(attempts):
        if invocation_id:
            if str(attempt.get("invocation_id", "")).strip() != invocation_id:
                continue
        else:
            if wave_id and str(attempt.get("wave_id", "")).strip() != wave_id:
                continue
            if step and str(attempt.get("step", "")).strip() != step:
                continue
            if failure_class and str(attempt.get("failure_class", "")).strip() != failure_class:
                continue
        matches.append(attempt)
        if len(matches) >= limit:
            break

    used_wave_fallback = False
    if (
        invocation_id
        and not bool(status.get("active"))
        and (not matches or all(_is_trivial_recovery_attempt(attempt) for attempt in matches))
    ):
        matches = []
        for attempt in reversed(attempts):
            if not _attempt_matches_wave_step(attempt, wave_id, step):
                continue
            matches.append(attempt)
            if len(matches) >= limit:
                break
        used_wave_fallback = bool(matches)

    if not matches:
        return []

    lines = ["  Recent attempts in wave:" if used_wave_fallback else "  Recent attempts:"]
    for attempt in reversed(matches):
        action = _excerpt(attempt.get("action", ""), 40) or "unknown"
        outcome = _excerpt(attempt.get("outcome", ""), 32) or "unknown"
        detail = _excerpt(attempt.get("detail", ""), 72)
        duration = attempt.get("duration_s")
        summary = f"  - {action} -> {outcome}"
        if isinstance(duration, (int, float)):
            summary += f" ({duration:.3f}s)"
        if detail:
            summary += f": {detail}"
        lines.append(summary)
    return lines


def render_recovery_lines(repo_root: Path, *, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    status = _read_recovery_status(repo_root)
    lines = [
        "RECOVERY",
        "─────────────────────────────────────",
    ]
    if not status:
        lines.append("  No recovery activity recorded yet.")
        return lines

    active = bool(status.get("active"))
    age = _age_seconds(status.get("updated_at", ""), now=now)
    label = "ACTIVE"
    if active and age is not None and age >= _HUNG_THRESHOLD_SECONDS:
        label = "POSSIBLY HUNG"
    elif not active:
        label = "LAST RECOVERY"

    tier = status.get("tier", "?")
    failure_class = str(status.get("failure_class", "?"))
    lines.append(f"  {label} — Tier {tier} recovery ({failure_class})")
    lines.append(f"  Problem: {_human_failure_class(failure_class)}")
    if not active:
        lines.append("  No recovery is running now.")

    wave_id = _excerpt(status.get("wave_id", ""), 80)
    if wave_id:
        lines.append(f"  Wave: {wave_id}")

    invocations = status.get("wave_invocation_count")
    tuple_attempt = status.get("tuple_attempt_index")
    if invocations or tuple_attempt:
        lines.append(
            f"  Invocation: {invocations or '?'} in wave · tuple attempt {tuple_attempt or '?'}"
        )

    retry_target = _human_target(str(status.get("retry_target", "")))
    if retry_target:
        if active:
            prefix = "If recovery works, go back to"
        elif status.get("recovered"):
            prefix = "Recovery sent work back to"
        else:
            prefix = "Last retry target"
        lines.append(f"  {prefix}: {retry_target}")

    state = _excerpt(status.get("state", ""), 80)
    current_iteration = status.get("current_iteration") or 0
    max_iterations = status.get("max_iterations") or 0
    if state:
        doing_now = _human_recovery_state(state)
        prefix = "Doing now" if active else "Last state"
        if max_iterations:
            lines.append(f"  {prefix}: {doing_now} · loop {current_iteration}/{max_iterations}")
        else:
            lines.append(f"  {prefix}: {doing_now}")

    pid_line = _format_recovery_pid_line(status, active=active)
    if pid_line:
        lines.append(pid_line)

    reason, reason_source = _rendered_recovery_reason(status)
    if reason:
        lines.append(f"  Reason: {reason}")

    explanation = _excerpt(status.get("explanation", ""))
    if explanation and reason_source != "explanation":
        lines.append(f"  Recovery note: {explanation}")

    current_command = _excerpt(status.get("current_command", ""))
    if current_command:
        lines.append(f"  Command: {current_command}")

    lines.extend(_recent_recovery_attempt_lines(repo_root, status))

    last_action = _excerpt(status.get("last_action", ""), 60)
    outcome = _excerpt(status.get("outcome", ""), 60)
    detail = _excerpt(status.get("detail", ""))
    if active:
        lines.append(f"  Updated: {_elapsed_seconds(age)} ago")
    else:
        finished_age = _age_seconds(
            status.get("finished_at", "") or status.get("updated_at", ""),
            now=now,
        )
        summary = _human_recovery_outcome(outcome, recovered=bool(status.get("recovered")))
        if last_action and outcome not in {"cleared"}:
            summary += f" via {last_action}"
        lines.append(f"  Outcome: {summary} · {_elapsed_seconds(finished_age)} ago")
    if detail and detail != reason and detail != explanation and reason_source != "detail":
        lines.append(f"  Detail: {detail}")

    return lines


def ps_lines():
    try:
        return subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5).stdout.splitlines()
    except Exception:
        return []


def pid_start(pid):
    try:
        r = subprocess.run(["ps", "-p", str(pid), "-o", "lstart="], capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip():
            return datetime.strptime(r.stdout.strip(), "%c").timestamp()
    except Exception:
        pass
    return None


def _is_observability_noise(line: str) -> bool:
    lowered = line.lower()
    return (
        "tail -f " in lowered
        or "rcx_log_watcher.sh" in lowered
        or "_pane_" in lowered
        or "pipeline_monitor.sh" in lowered
    )


def detect_phase(lines):
    for name, pattern in [("phase-a", "phase_a_executor"), ("phase-b", "phase_b_executor"),
                          ("commit", "commit_executor"), ("post-merge", "meta_bridge_supervisor")]:
        for l in lines:
            if pattern in l and "grep" not in l and "test_" not in l and not _is_observability_noise(l):
                pid = int(l.split()[1])
                return name, pid, pid_start(pid)
    for l in lines:
        if "executor_dispatch" in l and "grep" not in l and not _is_observability_noise(l):
            return "dispatch", int(l.split()[1]), pid_start(int(l.split()[1]))
    return "idle", None, None


def detect_subs(lines):
    subs = []
    for l in lines:
        if "grep" in l or _is_observability_noise(l):
            continue
        if "codex exec" in l:
            pid = int(l.split()[1])
            subs.append(("codex-review", pid, pid_start(pid)))
        elif "claude --print" in l:
            pid = int(l.split()[1])
            subs.append(("claude-impl", pid, pid_start(pid)))
        elif "run_review.py" in l:
            pid = int(l.split()[1])
            subs.append(("sdk-agents", pid, pid_start(pid)))
    return subs


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return None


def latest_file(pattern):
    files = sorted(_glob.glob(str(pattern)), key=os.path.getmtime)
    return files[-1] if files else None


def bridge_round_history():
    """Scan all bridge reviewer outputs for the current wave.

    Returns list of dicts with job_id, decision, blocking (list), non_blocking (list), timestamp.
    """
    raw_dir = REPO_ROOT / ".agent_bus" / "raw"
    if not raw_dir.exists():
        return []
    rounds = []
    for d in sorted(raw_dir.iterdir()):
        if not d.is_dir() or not d.name.startswith("phase-b-r"):
            continue
        for f in d.iterdir():
            if "reviewer" not in f.name:
                continue
            try:
                content = f.read_text()
                matches = list(re.finditer(r"BEGIN_AGENT_ENVELOPE\s*\n(.*?)\nEND_AGENT_ENVELOPE", content, re.DOTALL))
                if not matches:
                    continue
                env = json.loads(matches[-1].group(1))
                dec = env.get("decision", "")
                if "|" in dec:
                    continue
                findings = env.get("findings", [])
                blk = [x for x in findings if x.get("disposition") == "blocking"]
                nblk = [x for x in findings if x.get("disposition") != "blocking"]
                mtime = f.stat().st_mtime
                rounds.append({
                    "job_id": d.name,
                    "decision": dec,
                    "blocking": blk,
                    "non_blocking": nblk,
                    "timestamp": mtime,
                })
            except Exception:
                pass
    return rounds


def latest_bridge_summary():
    """Return (job_id, decision, summary, blocking_findings, non_blocking_findings) from most recent reviewer."""
    raw_dir = REPO_ROOT / ".agent_bus" / "raw"
    if not raw_dir.exists():
        return None
    latest = None
    latest_mtime = 0
    for d in raw_dir.iterdir():
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if "reviewer" in f.name and f.stat().st_mtime > latest_mtime:
                latest_mtime = f.stat().st_mtime
                latest = (d.name, f)
    if not latest:
        return None
    try:
        content = latest[1].read_text()
        matches = list(re.finditer(r"BEGIN_AGENT_ENVELOPE\s*\n(.*?)\nEND_AGENT_ENVELOPE", content, re.DOTALL))
        if not matches:
            return None
        env = json.loads(matches[-1].group(1))
        dec = env.get("decision", "")
        if "|" in dec:
            return None
        summary = env.get("summary", "")
        findings = env.get("findings", [])
        blk = [x for x in findings if x.get("disposition") == "blocking"]
        nblk = [x for x in findings if x.get("disposition") != "blocking"]
        return latest[0], dec, summary, blk, nblk
    except Exception:
        return None


def agent_status():
    f = latest_file(REPO_ROOT / ".scratch" / "phase_b_agent_review_*.status.json")
    if not f:
        f = latest_file(REPO_ROOT / ".scratch" / "phase_a_agent_review_*.status.json")
    return read_json(f) if f else None


def db_latest_jobs(n=3):
    db = REPO_ROOT / ".agent_bus" / "bridge.db"
    if not db.exists():
        return []
    try:
        conn = sqlite3.connect(str(db), timeout=1)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT job_id, status, terminal_decision, reviewer_agent, current_round, created_at "
            "FROM jobs ORDER BY rowid DESC LIMIT ?", (n,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def git_status():
    try:
        r = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=5,
                           cwd=REPO_ROOT)
        lines = [l for l in r.stdout.splitlines() if l.strip() and not l.strip().startswith("??")]
        return lines
    except Exception:
        return []


def deferred_count():
    d = REPO_ROOT / "reports" / "deferred" / "non_blocking"
    if not d.exists():
        return 0
    return len([f for f in d.iterdir() if f.is_file() and f.name != "README.md"])


def render():
    now = datetime.now().strftime("%H:%M:%S")
    psl = ps_lines()
    phase, pid, start = detect_phase(psl)
    subs = detect_subs(psl)

    out = []
    out.append(box_top())
    out.append(box_line(f"{B}RCX Pipeline Dashboard{R}{'':>30}{D}{now}{R}"))
    out.append(box_mid())

    # Phase
    pc = PHASE_C.get(phase, "")
    out.append(section("CURRENT PHASE"))
    out.append(box_line(f"  {pc}{B}{phase.upper()}{R}  {'PID '+str(pid) if pid else ''}  {elapsed(start)}"))

    # Subprocesses
    if subs:
        for name, spid, sstart in subs:
            label = {"codex-review": f"{CYN}Codex 5.4 xhigh{R} reviewing",
                     "claude-impl": f"{MAG}Claude opus max{R} implementing",
                     "sdk-agents": f"{YEL}SDK agents{R} running"}.get(name, name)
            out.append(box_line(f"  {label}  PID {spid}  {elapsed(sstart)}"))
    else:
        out.append(box_line(f"  {GRY}(no active subprocess){R}"))

    out.append(box_mid())

    recovery_lines = render_recovery_lines(REPO_ROOT)
    if len(recovery_lines) > 2:
        out.append(section("RECOVERY"))
        for line in recovery_lines[2:]:
            out.append(box_line(line))
        out.append(box_mid())

    # Routing
    routing = read_json(REPO_ROOT / ".agent_bus" / "meta" / "post_merge_routing.json")
    if routing:
        out.append(section("ROUTING"))
        dec = routing.get("decision", "?")
        dc = DEC_C.get(dec, "")
        out.append(box_line(f"  Decision: {dc}{B}{dec}{R}"))
        out.append(box_line(f"  Task: {routing.get('task_id', '?')}"))
        out.append(box_line(f"  Wave: {routing.get('wave_name', '?')[:55]}"))
        out.append(box_mid())

    # Phase B state
    pb = read_json(REPO_ROOT / ".agent_bus" / "executors" / "phase_b_state.json")
    if pb:
        out.append(section("PHASE B STATE"))
        out.append(box_line(f"  Step: {B}{pb.get('completed_step', '?')}{R}"))
        out.append(box_line(f"  Bridge Rounds: {B}{pb.get('bridge_rounds', 0)}{R}  "
                            f"Max: {pb.get('max_bridge_rounds', '?')}"))
        dp = pb.get("deferred_packet_path")
        if dp:
            out.append(box_line(f"  Deferred: {dp}"))
        out.append(box_mid())

    # Bridge round history with findings
    history = bridge_round_history()
    if history:
        out.append(section("BRIDGE ROUNDS"))
        for rnd in history[-8:]:
            dec = rnd["decision"]
            blk = rnd["blocking"]
            nblk = rnd["non_blocking"]
            dc = DEC_C.get(dec, "")
            ts = datetime.fromtimestamp(rnd["timestamp"]).strftime("%H:%M")
            blk_s = f"{RED}{len(blk)}B{R}" if blk else f"{GRN}0B{R}"
            nblk_s = f"{YEL}{len(nblk)}NB{R}"
            short_id = rnd["job_id"].split("-")[-1][:8]
            out.append(box_line(f"  {ts} {dc}{dec:18s}{R} {blk_s} {nblk_s}  {D}{short_id}{R}"))
            # Show blocking finding titles inline
            for f in blk[:2]:
                out.append(box_line(f"       {RED}✗ {f.get('title','')[:58]}{R}"))
            if len(blk) > 2:
                out.append(box_line(f"       {RED}... +{len(blk)-2} more blocking{R}"))
        out.append(box_mid())

    # Latest review detail (most recent round with full context)
    bridge = latest_bridge_summary()
    if bridge:
        job_id, dec, summary, blk, nblk = bridge
        out.append(section("LATEST REVIEW DETAIL"))
        dc = DEC_C.get(dec, "")
        out.append(box_line(f"  {dc}{B}{dec}{R}  {RED}{len(blk)} blocking{R}  {YEL}{len(nblk)} non-blocking{R}"))
        out.append(box_blank())
        if summary:
            words = summary.split()
            line = "  "
            for w in words:
                if len(line) + len(w) > 65:
                    out.append(box_line(f"{D}{line}{R}"))
                    line = "  "
                line += w + " "
            if line.strip():
                out.append(box_line(f"{D}{line}{R}"))
            out.append(box_blank())
        if blk:
            out.append(box_line(f"  {RED}{B}BLOCKING (must fix):{R}"))
            for i, f in enumerate(blk, 1):
                sev = f.get("severity", "?")
                title = f.get("title", "?")
                out.append(box_line(f"  {RED}{i}. [{sev}] {title[:60]}{R}"))
                detail = f.get("detail", "")
                if detail:
                    # First ~120 chars of detail
                    d = detail[:120].replace("\n", " ")
                    out.append(box_line(f"     {D}{d}{R}"))
            out.append(box_blank())
        if nblk:
            out.append(box_line(f"  {YEL}NON-BLOCKING (deferred):{R}"))
            for i, f in enumerate(nblk, 1):
                sev = f.get("severity", "?")
                title = f.get("title", "?")
                out.append(box_line(f"  {YEL}{i}. [{sev}] {title[:60]}{R}"))
            if len(nblk) > 6:
                out.append(box_line(f"  {YEL}   ... showing 6 of {len(nblk)}{R}"))
        out.append(box_mid())

    # Agents
    agents = agent_status()
    if agents:
        out.append(section("SDK AGENTS"))
        running = agents.get("running_agents", [])
        completed = agents.get("completed_agents", {})
        if running:
            out.append(box_line(f"  {YEL}Running:{R} {', '.join(running)}"))
        for name, info in completed.items():
            v = info.get("verdict", "?")
            passed = info.get("passed", False)
            mark = f"{GRN}✓{R}" if passed else f"{RED}✗{R}"
            out.append(box_line(f"  {mark} {name}: {v}"))
        out.append(box_mid())

    # DB jobs
    jobs = db_latest_jobs(4)
    if jobs:
        out.append(section("BRIDGE DB (recent)"))
        for j in jobs:
            jid = j["job_id"][:35]
            st = j["status"][:20]
            td = j.get("terminal_decision") or ""
            ra = j.get("reviewer_agent", "?")
            rnd = j.get("current_round", "?")
            dc = DEC_C.get(td, "")
            out.append(box_line(f"  {jid:36s} {st:20s} {dc}{td:10s}{R} R{rnd} {D}{ra}{R}"))
        out.append(box_mid())

    # Git + deferred
    gs = git_status()
    dc = deferred_count()
    out.append(section("REPO STATE"))
    out.append(box_line(f"  Modified: {len(gs)} files  Deferred: {dc} non-blocking"))
    if gs:
        for l in gs[:5]:
            out.append(box_line(f"  {D}{l}{R}"))
        if len(gs) > 5:
            out.append(box_line(f"  {D}... +{len(gs)-5} more{R}"))

    out.append(box_bot())
    return "\n".join(out)


def main(argv: list[str] | None = None):
    global REPO_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("interval", nargs="?", type=int, default=REFRESH_INTERVAL)
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="Repo root to inspect")
    parser.add_argument("--render-recovery", action="store_true", help="Print recovery lines once and exit")
    args = parser.parse_args(argv)
    REPO_ROOT = Path(args.repo_root).resolve()

    if args.render_recovery:
        for line in render_recovery_lines(REPO_ROOT):
            print(line)
        return

    interval = args.interval
    try:
        while True:
            os.system("clear")
            print(render())
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nDashboard stopped.")


if __name__ == "__main__":
    main()
