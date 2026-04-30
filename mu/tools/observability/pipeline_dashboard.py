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
EXECUTORS_DIR = REPO_ROOT / "mu" / "tools" / "executors"
if str(EXECUTORS_DIR) not in sys.path:
    sys.path.insert(0, str(EXECUTORS_DIR))
DEFAULT_AGENT_DISPLAY_NAMES = {
    "claude": "Claude Opus 4.7 max",
    "codex": "Codex 5.5 xhigh",
}

try:
    from executor_common import (
        ExecutorCommonError,
        agent_bus_path,
        agent_bus_relpath,
        bridge_agent_display_name,
        bridge_config_path,
        emit_pipeline_agent_event,
        load_routing_record,
        resolve_agent_bus_dir,
    )
except Exception:
    class ExecutorCommonError(RuntimeError):
        pass

    def agent_bus_relpath(bus_dir: str | Path | None = None, *parts: str | Path) -> Path:
        raw = str(bus_dir or ".agent_bus").strip().rstrip("/")
        if (
            not raw
            or "\\" in raw
            or "/" in raw
            or raw.startswith("..")
            or Path(raw).is_absolute()
            or (raw != ".agent_bus" and re.fullmatch(r"\.agent_bus-[A-Za-z0-9][A-Za-z0-9_-]*", raw) is None)
        ):
            raise ExecutorCommonError(f"Invalid --bus-dir: {raw}")
        return Path(raw).joinpath(*parts)

    def resolve_agent_bus_dir(repo_root: Path, bus_dir: str | Path | None = None) -> Path:
        rel = agent_bus_relpath(bus_dir)
        path = repo_root / rel
        if path.exists() and path.is_symlink():
            raise ExecutorCommonError(f"Invalid --bus-dir {rel}: bus directory must not be a symlink")
        return path

    def agent_bus_path(repo_root: Path, bus_dir: str | Path | None = None, *parts: str | Path) -> Path:
        return resolve_agent_bus_dir(repo_root, bus_dir).joinpath(*parts)

    def bridge_config_path(repo_root: Path, bus_dir: str | Path | None = None) -> Path:
        return agent_bus_path(repo_root, bus_dir, "bridge_config.json")

    def bridge_agent_display_name(
        repo_root: Path,
        agent_name: str,
        bus_dir: str | Path | None = None,
    ) -> str:
        config_path = bridge_config_path(repo_root, bus_dir)
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            display_name = (
                payload.get("agents", {})
                .get(agent_name, {})
                .get("display_name", "")
                .strip()
            )
            if display_name:
                return display_name
        except Exception:
            pass
        return DEFAULT_AGENT_DISPLAY_NAMES.get(agent_name, agent_name.replace("_", " ").title())

    def load_routing_record(repo_root: Path, bus_dir: str | Path | None = None) -> dict[str, Any]:
        raise ExecutorCommonError(f"Routing record not available for {repo_root}")

    def emit_pipeline_agent_event(
        repo_root: Path,
        bus_dir: str | Path | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        raise RuntimeError(f"pipeline pager emit unavailable for {repo_root}: {kwargs.get('event_type')}")
REFRESH_INTERVAL = 5
ACTIVE_BUS_DIR: Path | None = None
_HUNG_THRESHOLD_SECONDS = 90
IDLE_NON_GO_BRIDGE_DECISIONS = frozenset({"REQUEST_CHANGES"})
IDLE_NON_GO_META_DECISIONS = frozenset({"NEEDS_PHASE_B"})
IDLE_NON_GO_FAILURE_CLASSES = frozenset({"needs_phase_b", "max_rounds_reached", "terminal_policy"})

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


def _bus_path(repo_root: Path, *parts: str | Path) -> Path:
    return agent_bus_path(repo_root, ACTIVE_BUS_DIR, *parts)


def _bus_relpath(*parts: str | Path) -> Path:
    return agent_bus_relpath(ACTIVE_BUS_DIR, *parts)


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


def pid_ppid(pid):
    try:
        r = subprocess.run(["ps", "-p", str(pid), "-o", "ppid="], capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip():
            return int(r.stdout.strip())
    except Exception:
        return None
    return None


def pid_command(pid):
    try:
        r = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        return ""
    return ""


def pid_has_ancestor_matching(pid, pattern, max_depth=8):
    current = pid
    for _ in range(max_depth):
        parent = pid_ppid(current)
        if not parent or parent == 1:
            return False
        if re.search(pattern, pid_command(parent) or ""):
            return True
        current = parent
    return False


def bridge_role_for_pid(pid):
    if pid_has_ancestor_matching(pid, r"recovery_gate\.py"):
        return "recovery"
    if pid_has_ancestor_matching(pid, r"bridge_supervisor\.py review|meta_bridge_supervisor"):
        return "review"
    if pid_has_ancestor_matching(pid, r"phase_b_executor\.py|phase_a_executor\.py|commit_executor\.py"):
        return "implement"
    return "unknown"


def _bridge_agent_name_for_command(line: str) -> str | None:
    lowered = line.lower()
    if "autonomous workingrcx pipeline watchdog tick." in lowered:
        return None
    if "workingrcx pipeline pager wakeup." in lowered:
        return None
    if "codex" in lowered and " exec" in lowered and "codex.app" not in lowered and "codex helper" not in lowered:
        return "codex"
    if "claude" in lowered and "--print" in lowered:
        return "claude"
    return None


def _read_recovery_status(repo_root: Path) -> dict[str, Any]:
    path = _bus_path(repo_root, "recovery", "recovery_status.json")
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_recovery_attempts(repo_root: Path) -> list[dict[str, Any]]:
    path = _bus_path(repo_root, "recovery", "recovery_log.json")
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


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _routing_context_anchor_mtime(repo_root: Path) -> float:
    mtimes: list[float] = []
    for rel in (
        _bus_relpath("meta", "post_merge_routing.json"),
        _bus_relpath("executors", "phase_b_state.json"),
        _bus_relpath("executors", "phase_a_state.json"),
    ):
        path = repo_root / rel
        try:
            if path.exists():
                mtimes.append(path.stat().st_mtime)
        except OSError:
            continue
    return max(mtimes, default=0.0)


def _is_unhelpful_recovery_text(text: str) -> bool:
    cleaned = (text or "").strip()
    if not cleaned:
        return True
    normalized = cleaned.strip("\"'")
    if len(cleaned) <= 2 and " " not in cleaned:
        return True
    if re.fullmatch(r"[a-z0-9_-]{1,40}", normalized):
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
    except PermissionError:
        return pid, "alive"
    except ProcessLookupError:
        return pid, "dead"
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
        "needs_phase_b": "the supervisor sent work back to Phase B",
        "max_rounds_reached": "the bridge hit its maximum review rounds",
        "terminal_policy": "policy stopped automatic continuation",
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
        "tier3_waiting_on_agent": "asking the recovery agent what to try",
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
        owner_label = f"owner {owner_pid}"
        if owner_state:
            if not active and owner_state == "dead":
                owner_label += " (dead, historical)"
            else:
                owner_label += f" ({owner_state})"
        parts.append(owner_label)
    if child_pid:
        child_label = f"{child_role or 'child'} {child_pid}"
        if child_state:
            if not active and child_state == "dead":
                child_label += " (dead, historical)"
            else:
                child_label += f" ({child_state})"
        parts.append(child_label)
    return "  Process IDs: " + " · ".join(parts)


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


def _human_recovery_attempt_action(value: Any) -> str:
    cleaned = str(value or "").strip().lower()
    if not cleaned:
        return "unknown step"
    mapping = {
        "noop": "no automatic fix was attempted",
        "no_fix_registered": "no registered automatic fix was available",
        "tier1_fix": "ran the simple automatic fix",
        "tier2_fix": "ran the deterministic fix",
        "tier2_verify": "checked the deterministic fix",
        "shell": "ran a shell fix",
        "edit": "applied a file edit",
        "parse_error": "the recovery agent answered in the wrong format",
        "timeout": "the recovery agent timed out",
        "error": "the recovery agent hit an execution error",
        "skip": "recovery skipped this automatically",
        "escalate": "recovery escalated for human follow-up",
        "verify": "recovery checked whether the fix worked",
    }
    iter_match = re.fullmatch(r"tier(\d+)_iter(\d+)_(.+)", cleaned)
    if iter_match:
        _tier, iteration, suffix = iter_match.groups()
        action = mapping.get(suffix, suffix.replace("_", " "))
        return f"Try {iteration}: {action}"
    return mapping.get(cleaned, cleaned.replace("_", " "))


def _human_recovery_attempt_outcome(value: Any) -> str:
    cleaned = str(value or "").strip().lower()
    mapping = {
        "success": "worked",
        "failed": "failed",
        "retry_requested": "asked the pipeline to retry",
        "skipped": "skipped",
        "partial": "partly worked",
    }
    return mapping.get(cleaned, cleaned.replace("_", " ") if cleaned else "unknown")


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
        action = _human_recovery_attempt_action(attempt.get("action", ""))
        outcome = _human_recovery_attempt_outcome(attempt.get("outcome", ""))
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
    owner_pid, owner_state = _pid_state(status.get("owner_pid"))
    child_pid, child_state = _pid_state(status.get("child_pid"))
    stale_active_owner = (
        active
        and owner_pid > 0
        and owner_state == "dead"
        and child_pid <= 0
    )
    if stale_active_owner:
        active = False
    age = _age_seconds(status.get("updated_at", ""), now=now)
    label = "ACTIVE"
    if stale_active_owner:
        label = "STALE RECOVERY"
    elif active and age is not None and age >= _HUNG_THRESHOLD_SECONDS:
        label = "POSSIBLY HUNG"
    elif not active:
        label = "LAST RECOVERY"

    tier = status.get("tier", "?")
    failure_class = str(status.get("failure_class", "?"))
    lines.append(f"  {label} — Tier {tier} recovery")
    lines.append(f"  Problem: {_human_failure_class(failure_class)}")
    if not active:
        lines.append("  No recovery is running now.")
        if stale_active_owner:
            lines.append("  Recovery status was left active by a dead owner process.")

    wave_id = _excerpt(status.get("wave_id", ""), 80)
    if wave_id:
        lines.append(f"  Wave: {wave_id}")

    invocations = status.get("wave_invocation_count")
    tuple_attempt = status.get("tuple_attempt_index")
    if invocations or tuple_attempt:
        lines.append(
            f"  Recovery run: #{invocations or '?'} in this wave · step failure #{tuple_attempt or '?'}"
        )

    retry_target = _human_target(str(status.get("retry_target", "")))
    if retry_target:
        if active:
            prefix = "Next step if this works"
        elif status.get("recovered"):
            prefix = "Recovery sent work back to"
        else:
            prefix = "Last target"
        lines.append(f"  {prefix}: {retry_target}")

    state = _excerpt(status.get("state", ""), 80)
    current_iteration = status.get("current_iteration") or 0
    max_iterations = status.get("max_iterations") or 0
    if state:
        doing_now = _human_recovery_state(state)
        prefix = "Doing now" if active else "Last thing recovery tried"
        lines.append(f"  {prefix}: {doing_now}")
        if max_iterations:
            lines.append(f"  Current try: {current_iteration}/{max_iterations}")

    pid_line = _format_recovery_pid_line(status, active=active)
    if pid_line:
        lines.append(pid_line)

    reason, reason_source = _rendered_recovery_reason(status)
    if reason:
        lines.append(f"  Reason: {reason}")

    explanation = _excerpt(status.get("explanation", ""))
    if explanation and reason_source != "explanation":
        lines.append(f"  Note: {explanation}")

    current_command = _excerpt(status.get("current_command", ""))
    if current_command:
        lines.append(f"  Running command: {current_command}")

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
        normalized_action = last_action.strip().lower().replace(" ", "_")
        normalized_outcome = outcome.strip().lower().replace(" ", "_")
        if (
            last_action
            and outcome not in {"cleared"}
            and normalized_action not in {"", normalized_outcome, "exhausted", "later_success"}
        ):
            summary += f" via {last_action.replace('_', ' ')}"
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
        or "autonomous workingrcx pipeline watchdog tick." in lowered
        or "workingrcx pipeline pager wakeup." in lowered
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
        agent_name = _bridge_agent_name_for_command(l)
        if agent_name:
            pid = int(l.split()[1])
            role = bridge_role_for_pid(pid)
            subs.append((f"{agent_name}-{role}", pid, pid_start(pid)))
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
    raw_dir = _bus_path(REPO_ROOT, "raw")
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
    raw_dir = _bus_path(REPO_ROOT, "raw")
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


def _read_latest_envelope(path: Path, *, begin: str, end: str) -> dict[str, Any] | None:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    pattern = re.compile(rf"{re.escape(begin)}\s*\n(.*?)\n{re.escape(end)}", re.DOTALL)
    matches = list(pattern.finditer(content))
    for match in reversed(matches):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        decision = str(payload.get("decision", "")).strip()
        if decision and "|" not in decision:
            return payload
    return None


def _bridge_turn_matches_plan(repo_root: Path, job_id: str, turn_name: str, plan_path: str) -> bool:
    if not plan_path:
        return False
    prompt_path = _bus_path(repo_root, "prompts", job_id, turn_name)
    prompt_text = _read_text(prompt_path)
    return bool(prompt_text) and plan_path in prompt_text


def _latest_bridge_non_go_candidate(
    repo_root: Path,
    *,
    plan_path: str = "",
    not_before: float = 0.0,
) -> dict[str, Any] | None:
    raw_dir = _bus_path(repo_root, "raw")
    if not raw_dir.exists():
        return None
    latest_path: Path | None = None
    latest_job_id = ""
    latest_mtime = 0.0
    for directory in raw_dir.iterdir():
        if not directory.is_dir():
            continue
        for candidate in directory.iterdir():
            if "reviewer" not in candidate.name:
                continue
            try:
                mtime = candidate.stat().st_mtime
            except OSError:
                continue
            if mtime < not_before:
                continue
            if not _bridge_turn_matches_plan(repo_root, directory.name, candidate.name, plan_path):
                continue
            if mtime <= latest_mtime:
                continue
            latest_path = candidate
            latest_job_id = directory.name
            latest_mtime = mtime
    if latest_path is None:
        return None

    env = _read_latest_envelope(
        latest_path,
        begin="BEGIN_AGENT_ENVELOPE",
        end="END_AGENT_ENVELOPE",
    )
    if env is None:
        return None
    decision = str(env.get("decision", "")).strip()
    if decision not in IDLE_NON_GO_BRIDGE_DECISIONS:
        return None

    findings = env.get("findings", [])
    if not isinstance(findings, list):
        findings = []
    blocking = [item for item in findings if isinstance(item, dict) and item.get("disposition") == "blocking"]
    non_blocking = [item for item in findings if isinstance(item, dict) and item.get("disposition") != "blocking"]
    summary = _excerpt(env.get("summary", ""))
    reason = summary or f"{len(blocking)} blocking, {len(non_blocking)} advisory finding(s)"
    return {
        "category": "bridge_request_changes",
        "decision": decision,
        "timestamp": latest_mtime,
        "summary": f"tmux idle after {decision}",
        "reason": reason,
        "artifact_paths": {
            "bridge_review": str(latest_path.relative_to(repo_root)),
        },
        "transition_key": f"tmux-idle:{decision.lower()}:{latest_job_id}:{int(latest_mtime)}",
    }


def _meta_turn_matches_context(
    repo_root: Path,
    turn_name: str,
    *,
    task_id: str = "",
    wave_id: str = "",
    plan_path: str = "",
) -> bool:
    prompt_path = _bus_path(repo_root, "meta", "prompts", turn_name)
    prompt_text = _read_text(prompt_path)
    if not prompt_text:
        return False
    if task_id and task_id not in prompt_text:
        return False
    if wave_id and wave_id not in prompt_text:
        return False
    if plan_path and plan_path not in prompt_text:
        return False
    return True


def _latest_meta_non_go_candidate(
    repo_root: Path,
    *,
    task_id: str = "",
    wave_id: str = "",
    plan_path: str = "",
    not_before: float = 0.0,
) -> dict[str, Any] | None:
    raw_dir = _bus_path(repo_root, "meta", "raw")
    if not raw_dir.exists():
        return None
    candidates: list[tuple[float, Path]] = []
    for path in raw_dir.glob("meta-*.txt"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime < not_before:
            continue
        if not _meta_turn_matches_context(
            repo_root,
            path.name,
            task_id=task_id,
            wave_id=wave_id,
            plan_path=plan_path,
        ):
            continue
        candidates.append((mtime, path))
    if not candidates:
        return None
    latest_mtime, latest_path = max(candidates, key=lambda item: item[0])

    env = _read_latest_envelope(
        latest_path,
        begin="BEGIN_META_ENVELOPE",
        end="END_META_ENVELOPE",
    )
    if env is None:
        return None
    decision = str(env.get("decision", "")).strip()
    if decision not in IDLE_NON_GO_META_DECISIONS:
        return None

    findings = env.get("findings", [])
    if not isinstance(findings, list):
        findings = []
    finding_title = ""
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        finding_title = _excerpt(finding.get("title", ""))
        if finding_title:
            break
    reason = finding_title or _excerpt(env.get("request_for_claude", "")) or _excerpt(env.get("summary", ""))
    return {
        "category": "meta_needs_phase_b",
        "decision": decision,
        "timestamp": latest_mtime,
        "summary": f"tmux idle after {decision}",
        "reason": reason or _human_failure_class("needs_phase_b"),
        "artifact_paths": {
            "meta_review": str(latest_path.relative_to(repo_root)),
        },
        "transition_key": f"tmux-idle:{decision.lower()}:{latest_path.name}:{int(latest_mtime)}",
    }


def _recovery_idle_non_go_candidate(repo_root: Path, *, wave_id: str = "") -> dict[str, Any] | None:
    status = _read_recovery_status(repo_root)
    if not status or bool(status.get("active")):
        return None
    failure_class = str(status.get("failure_class", "")).strip().lower()
    if failure_class not in IDLE_NON_GO_FAILURE_CLASSES:
        return None

    status_wave_id = str(status.get("wave_id", "")).strip()
    if wave_id and status_wave_id and status_wave_id != wave_id:
        return None
    finished_at = str(status.get("finished_at", "")).strip() or str(status.get("updated_at", "")).strip()
    timestamp = 0.0
    parsed = _parse_iso(finished_at)
    if parsed is not None:
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        timestamp = parsed.timestamp()
    reason, _reason_source = _rendered_recovery_reason(status)
    return {
        "category": f"recovery_{failure_class}",
        "failure_class": failure_class,
        "timestamp": timestamp,
        "wave_id": status_wave_id,
        "summary": f"tmux idle after {_human_failure_class(failure_class)}",
        "reason": reason or _human_failure_class(failure_class),
        "artifact_paths": {
            "recovery_status": str(_bus_relpath("recovery", "recovery_status.json")),
        },
        "transition_key": (
            "tmux-idle:"
            f"{failure_class}:{status_wave_id}:{status.get('invocation_id') or finished_at or status.get('state', '')}"
        ),
    }


def latest_idle_non_go_candidate(
    repo_root: Path,
    *,
    task_id: str = "",
    wave_id: str = "",
    plan_path: str = "",
    not_before: float = 0.0,
) -> dict[str, Any] | None:
    candidates = [
        _latest_bridge_non_go_candidate(repo_root, plan_path=plan_path, not_before=not_before),
        _latest_meta_non_go_candidate(
            repo_root,
            task_id=task_id,
            wave_id=wave_id,
            plan_path=plan_path,
            not_before=not_before,
        ),
        _recovery_idle_non_go_candidate(repo_root, wave_id=wave_id),
    ]
    concrete = [candidate for candidate in candidates if candidate is not None]
    if not concrete:
        return None
    return max(concrete, key=lambda candidate: float(candidate.get("timestamp") or 0.0))


def _task_id_from_plan(repo_root: Path, plan_path: str) -> str:
    if not plan_path:
        return ""
    try:
        content = (repo_root / plan_path).read_text(encoding="utf-8")
    except OSError:
        return ""
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line.startswith("Task:"):
            continue
        return line.split(":", 1)[1].strip().strip("`")
    return ""


def _routing_context(repo_root: Path, candidate: dict[str, Any]) -> tuple[str, str, str]:
    task_id = ""
    wave_id = ""
    plan_path = ""
    try:
        routing = load_routing_record(repo_root, bus_dir=ACTIVE_BUS_DIR)
    except Exception:
        routing = {}
    if isinstance(routing, dict):
        task_id = str(routing.get("task_id", "")).strip()
        wave_id = str(routing.get("wave_name") or routing.get("wave_id") or "").strip()
        plan_path = str(routing.get("tracked_packet") or routing.get("plan_path") or "").strip()

    for state_rel in (
        _bus_relpath("executors", "phase_b_state.json"),
        _bus_relpath("executors", "phase_a_state.json"),
    ):
        if task_id and wave_id and plan_path:
            break
        state = read_json(repo_root / state_rel)
        if not isinstance(state, dict):
            continue
        if not wave_id:
            wave_id = str(state.get("wave_id", "")).strip()
        if not plan_path:
            plan_path = str(state.get("plan_path", "")).strip()

    if not wave_id:
        wave_id = str(candidate.get("wave_id", "")).strip()
    if not task_id and plan_path:
        task_id = _task_id_from_plan(repo_root, plan_path)
    return task_id, wave_id, plan_path


def emit_idle_non_go_alert(repo_root: Path, *, phase: str | None = None) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    active_phase = phase or detect_phase(ps_lines())[0]
    if active_phase != "idle":
        return {"attempted": False, "reason": "phase_not_idle", "phase": active_phase}

    active_task_id, active_wave_id, active_plan_path = _routing_context(repo_root, {})
    candidate = latest_idle_non_go_candidate(
        repo_root,
        task_id=active_task_id,
        wave_id=active_wave_id,
        plan_path=active_plan_path,
        not_before=_routing_context_anchor_mtime(repo_root),
    )
    if candidate is None:
        return {"attempted": False, "reason": "no_non_go_candidate", "phase": active_phase}

    task_id, wave_id, plan_path = _routing_context(repo_root, candidate)
    if not task_id or not wave_id:
        return {
            "attempted": False,
            "reason": "missing_routing_context",
            "phase": active_phase,
            "candidate": candidate.get("category", ""),
        }

    result = emit_pipeline_agent_event(
        repo_root,
        bus_dir=ACTIVE_BUS_DIR,
        event_type="pipeline_hard_fail",
        wave_id=wave_id,
        task_id=task_id,
        plan_path=plan_path or None,
        phase="tmux_monitor",
        state="idle_after_non_go",
        transition_key=str(candidate["transition_key"]),
        summary=str(candidate["summary"]),
        reason=str(candidate["reason"]),
        artifact_paths=candidate.get("artifact_paths", {}),
        metadata={
            "source": "tmux_idle_non_go",
            "category": candidate.get("category", ""),
            "decision": candidate.get("decision", ""),
            "failure_class": candidate.get("failure_class", ""),
            "observed_phase": active_phase,
        },
    )
    report = {
        "phase": active_phase,
        "category": candidate.get("category", ""),
        **result,
    }
    report["emitted"] = True
    return report


def agent_status():
    f = latest_file(REPO_ROOT / ".scratch" / "phase_b_agent_review_*.status.json")
    if not f:
        f = latest_file(REPO_ROOT / ".scratch" / "phase_a_agent_review_*.status.json")
    return read_json(f) if f else None


def db_latest_jobs(n=3):
    db = _bus_path(REPO_ROOT, "bridge.db")
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
            if name == "sdk-agents":
                label = f"{YEL}SDK agents{R} running"
            else:
                agent_name, _, role = name.partition("-")
                if role == "recovery":
                    label = f"{YEL}Recovery agent{R} diagnosing"
                else:
                    display_name = bridge_agent_display_name(REPO_ROOT, agent_name, bus_dir=ACTIVE_BUS_DIR)
                    color, activity = {
                        "review": (CYN, "reviewing"),
                        "implement": (MAG, "implementing"),
                        "unknown": (CYN, "working"),
                    }.get(role, (CYN, role or "working"))
                    label = f"{color}{display_name}{R} {activity}"
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
    routing = read_json(_bus_path(REPO_ROOT, "meta", "post_merge_routing.json"))
    if routing:
        out.append(section("ROUTING"))
        dec = routing.get("decision", "?")
        dc = DEC_C.get(dec, "")
        out.append(box_line(f"  Decision: {dc}{B}{dec}{R}"))
        out.append(box_line(f"  Task: {routing.get('task_id', '?')}"))
        out.append(box_line(f"  Wave: {routing.get('wave_name', '?')[:55]}"))
        out.append(box_mid())

    # Phase B state
    pb = read_json(_bus_path(REPO_ROOT, "executors", "phase_b_state.json"))
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
    global ACTIVE_BUS_DIR, REPO_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("interval", nargs="?", type=int, default=REFRESH_INTERVAL)
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="Repo root to inspect")
    parser.add_argument("--bus-dir", default=None, help="Active repo-root agent bus (.agent_bus or .agent_bus-<id>)")
    parser.add_argument("--render-recovery", action="store_true", help="Print recovery lines once and exit")
    parser.add_argument(
        "--emit-idle-non-go-alert",
        action="store_true",
        help="Emit a deduped pager event when the observed pipeline is idle after a non-GO stop.",
    )
    args = parser.parse_args(argv)
    REPO_ROOT = Path(args.repo_root).resolve()
    try:
        resolve_agent_bus_dir(REPO_ROOT, args.bus_dir)
        ACTIVE_BUS_DIR = agent_bus_relpath(args.bus_dir)
    except ExecutorCommonError as exc:
        print(f"[error] Invalid --bus-dir: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    if args.render_recovery:
        for line in render_recovery_lines(REPO_ROOT):
            print(line)
        return
    if args.emit_idle_non_go_alert:
        json.dump(emit_idle_non_go_alert(REPO_ROOT), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
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
