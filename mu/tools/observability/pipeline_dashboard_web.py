#!/usr/bin/env python3
"""RCX Pipeline Web Dashboard v2. Read-only. No dependencies beyond stdlib."""

import glob as _glob
import http.server
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

_resolved = Path(__file__).resolve()
# tools/ is a symlink to mu/tools/, so resolved path is mu/tools/observability/file.py (4 levels)
# Handle both real path (mu/tools/observability/) and symlink path (tools/observability/)
REPO_ROOT = _resolved.parent.parent.parent
if REPO_ROOT.name == "mu":
    REPO_ROOT = REPO_ROOT.parent
PORT = 8099


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
        return None


def _is_observability_noise(line):
    lowered = line.lower()
    return (
        "tail -f " in lowered
        or "rcx_log_watcher.sh" in lowered
        or "_pane_" in lowered
        or "pipeline_monitor.sh" in lowered
    )


def detect_phase(lines):
    for name, pattern in [("phase-a", "phase_a_executor"), ("phase-b", "phase_b_executor"),
                          ("commit", "commit_executor"), ("post-merge", "meta_bridge_supervisor"),
                          ("bridge", "bridge_supervisor")]:
        for l in lines:
            if pattern in l and "grep" not in l and "test_" not in l and not _is_observability_noise(l):
                pid = int(l.split()[1])
                return {"phase": name, "pid": pid, "started": pid_start(pid)}
    for l in lines:
        if "executor_dispatch" in l and "grep" not in l and not _is_observability_noise(l):
            return {"phase": "dispatch", "pid": int(l.split()[1]), "started": pid_start(int(l.split()[1]))}
    return {"phase": "idle", "pid": None, "started": None}


def detect_subs(lines):
    subs = []
    for l in lines:
        if "grep" in l or _is_observability_noise(l):
            continue
        # Codex CLI reviewer: must have "codex exec" + "gpt" (not Codex.app desktop helpers)
        if "codex" in l.lower() and "exec" in l and "gpt" in l and "Codex.app" not in l and "Codex Helper" not in l:
            pid = int(l.split()[1])
            subs.append({"name": "Codex 5.4 xhigh", "role": "reviewer", "pid": pid, "started": pid_start(pid)})
        # Claude implementer: must have --print (not interactive sessions)
        elif "claude" in l.lower() and "--print" in l:
            pid = int(l.split()[1])
            subs.append({"name": "Claude opus 4.6", "role": "implementer", "pid": pid, "started": pid_start(pid)})
        # SDK agents
        elif "run_review.py" in l:
            pid = int(l.split()[1])
            subs.append({"name": "SDK Agents", "role": "auditor", "pid": pid, "started": pid_start(pid)})
    return subs


def read_json_safe(path):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return None


def bridge_round_history():
    raw_dir = REPO_ROOT / ".agent_bus" / "raw"
    if not raw_dir.exists():
        return []
    rounds = []
    for d in sorted(raw_dir.iterdir()):
        if not d.is_dir() or not (d.name.startswith("phase-b-r") or d.name.startswith("phase-a-r")):
            continue
        for f in d.iterdir():
            if "reviewer" not in f.name:
                continue
            try:
                content = f.read_text()
                matches = list(re.finditer(r"BEGIN_AGENT_ENVELOPE\s*\n(.*?)\nEND_AGENT_ENVELOPE", content, re.DOTALL))
                if not matches:
                    continue
                env = None
                for m in reversed(matches):
                    try:
                        candidate = json.loads(m.group(1))
                        if "|" not in candidate.get("decision", ""):
                            env = candidate
                            break
                    except (json.JSONDecodeError, KeyError):
                        continue
                if env is None:
                    continue
                dec = env.get("decision", "")
                if not dec:
                    continue
                findings = env.get("findings", [])
                blk = [x for x in findings if x.get("disposition") == "blocking"]
                nblk = [x for x in findings if x.get("disposition") != "blocking"]
                rounds.append({
                    "job_id": d.name,
                    "decision": dec,
                    "summary": env.get("summary", ""),
                    "blocking": blk,
                    "non_blocking": nblk,
                    "timestamp": f.stat().st_mtime,
                    "time_str": datetime.fromtimestamp(f.stat().st_mtime).strftime("%H:%M:%S"),
                })
            except Exception:
                pass
    rounds.sort(key=lambda r: r["timestamp"])
    return rounds


def agent_status():
    scratch = REPO_ROOT / ".scratch"
    latest = None
    latest_mtime = 0
    for pattern in ["phase_b_agent_review_*.status.json", "phase_a_agent_review_*.status.json"]:
        for f in scratch.glob(pattern):
            if f.stat().st_mtime > latest_mtime:
                latest_mtime = f.stat().st_mtime
                latest = f
    return read_json_safe(latest) if latest else None


def db_latest_jobs(n=8):
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
        r = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=5, cwd=REPO_ROOT)
        return [l for l in r.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def git_branch():
    try:
        r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=3, cwd=REPO_ROOT)
        return r.stdout.strip()
    except Exception:
        return "unknown"


def git_log_short(n=5):
    try:
        r = subprocess.run(["git", "log", "--oneline", f"-{n}"], capture_output=True, text=True, timeout=5, cwd=REPO_ROOT)
        return r.stdout.strip().splitlines()
    except Exception:
        return []


def deferred_count():
    d = REPO_ROOT / "reports" / "deferred" / "non_blocking"
    if not d.exists():
        return 0
    return len([f for f in d.iterdir() if f.is_file() and f.name != "README.md"])


def active_log_tail(n=40):
    """Find the most recently modified pipeline log and return last n lines."""
    candidates = []
    scratch = REPO_ROOT / ".scratch"
    for pattern in ["*_executor_live.log", "phase_*_bridge_*.stdout.log",
                    "phase_*_agent_review_*.stdout.log"]:
        candidates.extend(scratch.glob(pattern))
    # Also check /tmp
    for pattern in ["phase_b_*.txt", "commit_*.txt", "phase_a_*.txt"]:
        candidates.extend(Path("/tmp").glob(pattern))
    live = Path("/tmp/rcx_pipeline_live.txt")
    if live.exists():
        candidates.append(live)

    if not candidates:
        return {"file": None, "lines": [], "age": None}

    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    age = time.time() - newest.stat().st_mtime
    if age > 600:
        return {"file": None, "lines": [], "age": None}

    try:
        lines = newest.read_text().splitlines()[-n:]
    except Exception:
        lines = []
    return {"file": newest.name, "lines": lines, "age": round(age)}


def _newest_file(paths):
    """Return (path, mtime) of newest file from glob results, or (None, 0)."""
    best, best_t = None, 0
    for p in paths:
        try:
            t = p.stat().st_mtime
            if t > best_t:
                best, best_t = p, t
        except OSError:
            pass
    return best, best_t


def _tail_lines(path, n=30):
    """Read last n lines of a file safely."""
    try:
        return path.read_text(errors="replace").splitlines()[-n:]
    except Exception:
        return []


def model_activity():
    """Get real-time activity from all three model output streams."""
    now = time.time()
    feeds = []

    # 1. Codex reviewer: session JSONL (structured events)
    codex_sessions = Path.home() / ".codex" / "sessions"
    codex_jsonl = None
    if codex_sessions.exists():
        today = datetime.now().strftime("%Y/%m/%d")
        today_dir = codex_sessions / today
        if today_dir.exists():
            codex_jsonl, codex_mtime = _newest_file(today_dir.glob("*.jsonl"))
    codex_events = []
    if codex_jsonl and (now - codex_jsonl.stat().st_mtime) < 1800:
        try:
            lines = codex_jsonl.read_text(errors="replace").splitlines()[-50:]
            for line in lines:
                try:
                    evt = json.loads(line)
                    etype = evt.get("type", "")
                    payload = evt.get("payload", {})
                    ts = evt.get("timestamp", "")
                    time_short = ts[11:19] if len(ts) > 19 else ""

                    if etype == "response_item":
                        ptype = payload.get("type", "")
                        if ptype == "function_call":
                            name = payload.get("name", "?")
                            args_raw = payload.get("arguments", "")
                            # Summarize args
                            args_summary = ""
                            try:
                                args = json.loads(args_raw) if args_raw else {}
                                if "path" in args:
                                    args_summary = args["path"]
                                elif "file_path" in args:
                                    args_summary = args["file_path"]
                                elif "command" in args:
                                    cmd = args["command"]
                                    args_summary = cmd[:80] if len(cmd) > 80 else cmd
                                elif "plan" in args and isinstance(args["plan"], list):
                                    args_summary = f"{len(args['plan'])} steps"
                                elif args_raw:
                                    args_summary = args_raw[:60]
                            except (json.JSONDecodeError, TypeError):
                                args_summary = args_raw[:60] if args_raw else ""
                            codex_events.append({
                                "time": time_short,
                                "action": f"call {name}",
                                "detail": args_summary,
                                "kind": "tool",
                            })
                        elif ptype == "message":
                            text = payload.get("content", [{}])
                            if isinstance(text, list) and text:
                                msg = text[0].get("text", "")[:100]
                            elif isinstance(text, str):
                                msg = text[:100]
                            else:
                                msg = ""
                            if msg:
                                codex_events.append({
                                    "time": time_short,
                                    "action": "message",
                                    "detail": msg,
                                    "kind": "text",
                                })
                    elif etype == "event_msg":
                        ptype = payload.get("type", "")
                        if ptype == "token_count":
                            info = payload.get("info", {}).get("total_token_usage", {})
                            inp = info.get("input_tokens", 0)
                            out = info.get("output_tokens", 0)
                            reasoning = info.get("reasoning_tokens", 0)
                            codex_events.append({
                                "time": time_short,
                                "action": "tokens",
                                "detail": f"in:{inp:,} out:{out:,} reasoning:{reasoning:,}",
                                "kind": "meta",
                            })
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass
        except Exception:
            pass

    if codex_events:
        age = round(now - codex_jsonl.stat().st_mtime)
        feeds.append({
            "source": "Codex GPT-5.4 xhigh",
            "role": "reviewer",
            "file": codex_jsonl.name,
            "age": age,
            "events": codex_events[-20:],  # Last 20 events
            "status": "active" if age < 60 else "stale" if age < 300 else "idle",
        })

    # 2. Raw reviewer output (plain text from Codex stdout)
    raw_dir = REPO_ROOT / ".agent_bus" / "raw"
    if raw_dir.exists():
        reviewer_file, reviewer_mtime = _newest_file(
            p for d in sorted(raw_dir.iterdir(), reverse=True)[:3]
            if d.is_dir()
            for p in d.glob("*reviewer*.txt")
        )
        if reviewer_file and (now - reviewer_mtime) < 1800 and reviewer_file.stat().st_size > 0:
            lines = _tail_lines(reviewer_file, 20)
            feeds.append({
                "source": "Codex Review Output",
                "role": "reviewer_raw",
                "file": reviewer_file.name,
                "age": round(now - reviewer_mtime),
                "lines": lines,
                "size": reviewer_file.stat().st_size,
                "status": "active" if (now - reviewer_mtime) < 60 else "stale" if (now - reviewer_mtime) < 300 else "done",
            })

    # 3. Implementer output (Claude stream-JSON)
    scratch = REPO_ROOT / ".scratch"
    impl_file, impl_mtime = _newest_file(scratch.glob("phase_b_implementer_output_*.txt"))
    if impl_file and (now - impl_mtime) < 1800 and impl_file.stat().st_size > 0:
        impl_events = _parse_claude_stream_json(impl_file)
        feeds.append({
            "source": "Claude Opus 4.6 max",
            "role": "implementer",
            "file": impl_file.name,
            "age": round(now - impl_mtime),
            "events": impl_events[-25:],
            "size": impl_file.stat().st_size,
            "status": "active" if (now - impl_mtime) < 60 else "stale" if (now - impl_mtime) < 300 else "done",
        })

    return feeds


def _parse_claude_stream_json(path, tail=80):
    """Parse Claude --output-format stream-json into human-readable events."""
    events = []
    try:
        lines = path.read_text(errors="replace").splitlines()[-tail:]
    except Exception:
        return events
    for line in lines:
        try:
            evt = json.loads(line.strip())
            etype = evt.get("type", "")
            if etype == "assistant":
                msg = evt.get("message", {})
                for block in msg.get("content", []):
                    btype = block.get("type", "")
                    if btype == "text":
                        text = block.get("text", "").strip()
                        if not text:
                            continue
                        # Truncate long text, take first meaningful line
                        first_line = text.split("\n")[0][:120]
                        if first_line:
                            events.append({
                                "time": "",
                                "action": "thinking",
                                "detail": first_line,
                                "kind": "text",
                            })
                    elif btype == "tool_use":
                        name = block.get("name", "?")
                        inp = block.get("input", {})
                        detail = ""
                        if "file_path" in inp:
                            detail = inp["file_path"].replace(str(REPO_ROOT) + "/", "")
                        elif "command" in inp:
                            cmd = inp["command"]
                            detail = cmd[:90] if len(cmd) > 90 else cmd
                        elif "pattern" in inp:
                            detail = inp["pattern"][:60]
                            if "path" in inp:
                                detail += f" in {inp['path'].replace(str(REPO_ROOT) + '/', '')}"
                        elif "old_string" in inp:
                            detail = inp.get("file_path", "").replace(str(REPO_ROOT) + "/", "")
                        else:
                            # Generic: show first string value
                            for v in inp.values():
                                if isinstance(v, str) and v:
                                    detail = v[:60]
                                    break
                        events.append({
                            "time": "",
                            "action": name,
                            "detail": detail,
                            "kind": "tool",
                        })
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    return events


def wave_context():
    """Try to determine what wave/task is being worked on."""
    # Check phase_b_state
    pb = read_json_safe(REPO_ROOT / ".agent_bus" / "executors" / "phase_b_state.json")
    if pb:
        return {
            "wave_id": pb.get("wave_id", ""),
            "task_id": pb.get("task_id", ""),
            "step": pb.get("completed_step", ""),
            "bridge_rounds": pb.get("bridge_rounds", 0),
            "max_rounds": pb.get("max_bridge_rounds", 0),
            "target_branch": pb.get("target_branch", ""),
        }
    # Check routing
    routing = read_json_safe(REPO_ROOT / ".agent_bus" / "meta" / "post_merge_routing.json")
    if routing:
        return {
            "wave_id": routing.get("wave_name", ""),
            "task_id": routing.get("task_id", ""),
            "step": "routing:" + (routing.get("decision", "") or ""),
            "bridge_rounds": 0,
            "max_rounds": 0,
            "target_branch": "",
        }
    return None


def build_narrative(phase, subs, wave, lock, history):
    """Build a plain-English explanation of what the pipeline is doing right now."""
    ph = (phase or {}).get("phase", "idle")
    started = (phase or {}).get("started")
    elapsed_s = (time.time() - started) if started else 0
    elapsed_str = ""
    if elapsed_s > 0:
        m, s = divmod(int(elapsed_s), 60)
        h, m = divmod(m, 60)
        elapsed_str = f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"

    # Count distinct model types in subprocesses
    reviewers = [s for s in subs if s.get("role") == "reviewer"]
    implementers = [s for s in subs if s.get("role") == "implementer"]

    br = (wave or {}).get("bridge_rounds", 0)
    mr = (wave or {}).get("max_rounds", 0)
    step = (wave or {}).get("step", "")

    lines = []

    if ph == "idle":
        lines.append({"text": "Pipeline is idle. No active work.", "style": "dim"})
    elif ph == "dispatch":
        lines.append({"text": "Dispatcher is selecting the next wave to run.", "style": "normal"})
    elif ph == "phase-a":
        lines.append({"text": "Phase A: Planning what to fix.", "style": "normal"})
        if reviewers:
            lines.append({"text": f"Codex (GPT-5.4 xhigh) is analyzing the codebase to produce a fix plan.", "style": "detail"})
        lines.append({"text": f"Running for {elapsed_str}.", "style": "dim"})
    elif ph == "phase-b":
        if "bridge" in step or lock:
            # Bridge review is active
            if reviewers:
                lines.append({"text": f"Codex (GPT-5.4 xhigh) is reviewing Claude's implementation.", "style": "reviewer"})
                lines.append({"text": f"Bridge review round {br} of {mr}.", "style": "detail"})
                lines.append({"text": f"The reviewer checks for bugs, security issues, and protocol violations.", "style": "dim"})
            elif implementers:
                lines.append({"text": f"Claude (Opus 4.6 max) is writing the code changes.", "style": "implementer"})
                lines.append({"text": f"Implementing fixes based on the Phase A plan.", "style": "dim"})
            else:
                lines.append({"text": f"Phase B: Implementation + review cycle.", "style": "normal"})
                lines.append({"text": f"Bridge round {br} of {mr}.", "style": "detail"})
        else:
            lines.append({"text": f"Phase B: Claude (Opus 4.6 max) is implementing fixes.", "style": "implementer"})
            if step:
                lines.append({"text": f"Current step: {step}", "style": "detail"})
        lines.append({"text": f"Running for {elapsed_str}.", "style": "dim"})
    elif ph == "bridge":
        lines.append({"text": f"Bridge supervisor is coordinating review round {br}.", "style": "normal"})
        if reviewers:
            lines.append({"text": f"Codex (GPT-5.4 xhigh) is reviewing — {len(reviewers)} process(es) active.", "style": "reviewer"})
        lines.append({"text": f"Running for {elapsed_str}.", "style": "dim"})
    elif ph == "commit":
        lines.append({"text": "Commit executor: pushing code through the 15-step gate.", "style": "normal"})
        lines.append({"text": "Running pre-commit checks, creating PR, waiting for CI + bot review.", "style": "detail"})
        lines.append({"text": f"Running for {elapsed_str}.", "style": "dim"})
    elif ph == "post-merge":
        lines.append({"text": "Post-merge: supervisor is deciding what to do next.", "style": "normal"})
        lines.append({"text": f"Running for {elapsed_str}.", "style": "dim"})

    # Add last bridge decision if we have history
    if history:
        last = history[-1]
        dec = last.get("decision", "")
        blk_n = len(last.get("blocking", []))
        nb_n = len(last.get("non_blocking", []))
        if dec:
            verdict = f"Last review verdict: {dec}"
            if blk_n:
                verdict += f" ({blk_n} blocking issue{'s' if blk_n != 1 else ''})"
            if nb_n:
                verdict += f" ({nb_n} non-blocking)"
            lines.append({"text": verdict, "style": "verdict"})

    return lines


def implementer_changes():
    """Get list of files the implementer changed, from the latest implementer output."""
    scratch = REPO_ROOT / ".scratch"
    outputs = sorted(scratch.glob("phase_b_implementer_output_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not outputs:
        return []
    try:
        content = outputs[0].read_text()
        # Look for file paths that were edited
        files = set()
        for m in re.finditer(r'(?:Edit|Write|Read)\s+(/[^\s]+)', content):
            path = m.group(1)
            # Make relative to repo root
            try:
                rel = str(Path(path).relative_to(REPO_ROOT))
                files.add(rel)
            except ValueError:
                files.add(path)
        # Also check git status for actual changes
        return sorted(files)[:20]
    except Exception:
        return []


def session_timeline():
    """Build a chronological timeline of pipeline events."""
    events = []
    now = time.time()
    cutoff = now - 6 * 3600  # last 6 hours

    def add(ts, label, style="normal"):
        if ts and ts > cutoff:
            events.append({"ts": ts, "time": datetime.fromtimestamp(ts).strftime("%H:%M"), "label": label, "style": style})

    # Implementer runs
    scratch = REPO_ROOT / ".scratch"
    for f in sorted(scratch.glob("phase_b_implementer_output_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
        ts = f.stat().st_mtime
        size = f.stat().st_size
        if size > 100000:
            add(ts, f"Claude done — {size // 1024}KB output", "implementer")
        else:
            add(ts, "Claude implementing...", "implementer")

    # Agent reviews
    for f in sorted(scratch.glob("phase_b_agent_review_*.status.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
        ts = f.stat().st_mtime
        data = read_json_safe(f)
        if not data:
            continue
        completed = data.get("completed_agents", {})
        running = data.get("running_agents", [])
        passed = sum(1 for v in completed.values() if v.get("passed"))
        failed = sum(1 for v in completed.values() if not v.get("passed"))
        if data.get("status") == "completed" or (completed and not running):
            if failed:
                add(ts, f"Agents: {passed} pass, {failed} need work", "warning")
            else:
                add(ts, f"Agents: all {len(completed)} passed", "good")
        elif running:
            add(ts, f"Agents running: {', '.join(running)}", "active")

    # Bridge rounds
    raw_dir = REPO_ROOT / ".agent_bus" / "raw"
    if raw_dir.exists():
        for d in sorted(raw_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:8]:
            if not d.is_dir():
                continue
            for rf in d.glob("*reviewer*.txt"):
                if rf.stat().st_size == 0:
                    continue
                ts = rf.stat().st_mtime
                try:
                    content = rf.read_text(errors="replace")
                    matches = list(re.finditer(r"BEGIN_AGENT_ENVELOPE\s*\n(.*?)\nEND_AGENT_ENVELOPE", content, re.DOTALL))
                    if not matches:
                        add(ts, "Codex reviewing...", "active")
                        continue
                    env = json.loads(matches[-1].group(1))
                    dec = env.get("decision", "?")
                    findings = env.get("findings", [])
                    blk = sum(1 for f in findings if f.get("disposition") == "blocking")
                    nb = sum(1 for f in findings if f.get("disposition") != "blocking")
                    if dec in ("GO", "COMMIT_GO"):
                        add(ts, f"Codex: GO ({nb} advisory)", "good")
                    elif dec == "NO_GO":
                        add(ts, f"Codex: NO_GO ({blk} blocker, {nb} advisory)", "bad")
                    elif dec == "REQUEST_CHANGES":
                        add(ts, f"Codex: REQUEST_CHANGES ({blk}B {nb}NB)", "warning")
                    else:
                        add(ts, f"Codex: {dec}", "normal")
                except Exception:
                    pass
            # Review start time from reader file
            for rf in d.glob("*reader*.txt"):
                add(rf.stat().st_mtime, "Codex reviewing...", "active")

    # Git commits
    try:
        r = subprocess.run(
            ["git", "log", "--format=%ct|%s", "--since=6 hours ago", "-8"],
            capture_output=True, text=True, timeout=5, cwd=REPO_ROOT,
        )
        for line in r.stdout.strip().splitlines():
            parts = line.split("|", 1)
            if len(parts) == 2:
                add(int(parts[0]), f"Committed: {parts[1]}", "good")
    except Exception:
        pass

    # Sort chronologically and add "you are here" marker
    events.sort(key=lambda e: e["ts"])

    # Determine current activity for the marker
    marker = "idle"
    try:
        subprocess.run(["pgrep", "-f", "codex.*exec.*gpt"], capture_output=True, timeout=3).returncode == 0 and (marker := "Codex reviewing now")
        subprocess.run(["pgrep", "-f", "claude.*--print"], capture_output=True, timeout=3).returncode == 0 and (marker := "Claude implementing now")
        subprocess.run(["pgrep", "-f", "run_review.py"], capture_output=True, timeout=3).returncode == 0 and (marker := "SDK agents running now")
    except Exception:
        pass

    return {"events": events[-20:], "current": marker}


def lock_status():
    for lock_path in [REPO_ROOT / ".agent_bus" / "bridge.lock",
                      REPO_ROOT / ".agent_bus" / "meta" / "meta_bridge.lock"]:
        if lock_path.exists() and lock_path.stat().st_size > 0:
            data = read_json_safe(lock_path)
            if data:
                pid = data.get("pid", 0)
                alive = False
                try:
                    os.kill(int(pid), 0)
                    alive = True
                except (OSError, ValueError):
                    pass
                return {"holder": data.get("holder", "?"), "pid": pid, "alive": alive}
    return None


def _parse_iso8601(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_seconds(value):
    parsed = _parse_iso8601(value)
    if parsed is None:
        return None
    return max(0, int(time.time() - parsed.timestamp()))


def _human_recovery_target(target):
    mapping = {
        "phase_a_executor": "Phase A",
        "phase_a": "Phase A",
        "phase_b_executor": "Phase B",
        "phase_b": "Phase B",
        "commit_executor": "Commit",
        "commit": "Commit",
        "executor_dispatch": "Dispatch",
    }
    cleaned = (target or "").strip()
    return mapping.get(cleaned, cleaned.replace("_", " "))


def recovery_snapshot():
    status = read_json_safe(REPO_ROOT / ".agent_bus" / "recovery" / "recovery_status.json")
    if not isinstance(status, dict) or not status:
        return None
    active = bool(status.get("active"))
    age = _age_seconds(status.get("updated_at", ""))
    label = "ACTIVE"
    if active and age is not None and age >= 90:
        label = "POSSIBLY HUNG"
    elif not active:
        label = "LAST RECOVERY"
    return {
        "label": label,
        "active": active,
        "tier": status.get("tier"),
        "failure_class": status.get("failure_class", ""),
        "wave_id": status.get("wave_id", ""),
        "wave_invocation_count": status.get("wave_invocation_count", 0),
        "tuple_attempt_index": status.get("tuple_attempt_index", 0),
        "retry_target": _human_recovery_target(status.get("retry_target", "")),
        "state": status.get("state", ""),
        "reason": status.get("reason", ""),
        "explanation": status.get("explanation", ""),
        "detail": status.get("detail", ""),
        "outcome": status.get("outcome", ""),
        "last_action": status.get("last_action", ""),
        "current_iteration": status.get("current_iteration", 0),
        "max_iterations": status.get("max_iterations", 0),
        "owner_pid": status.get("owner_pid", 0),
        "child_pid": status.get("child_pid", 0),
        "child_role": status.get("child_role", ""),
        "current_command": status.get("current_command", ""),
        "updated_age_seconds": age,
    }


def get_state():
    psl = ps_lines()
    phase = detect_phase(psl)
    subs = detect_subs(psl)
    agents = agent_status()
    jobs = db_latest_jobs()
    gs = git_status()
    dc = deferred_count()
    log = active_log_tail()
    wave = wave_context()
    lock = lock_status()
    recovery = recovery_snapshot()
    branch = git_branch()
    commits = git_log_short()

    history = bridge_round_history()
    narrative = build_narrative(phase, subs, wave, lock, history)
    if recovery and recovery.get("active"):
        loop = ""
        if recovery.get("max_iterations"):
            loop = (
                f" Loop {recovery.get('current_iteration', 0)}"
                f"/{recovery.get('max_iterations', 0)}."
            )
        narrative.append({
            "text": (
                f"Recovery agent active: Tier {recovery.get('tier')} "
                f"{recovery.get('failure_class')} for {recovery.get('retry_target')}.{loop}"
            ),
            "style": "detail",
        })
        if recovery.get("reason"):
            narrative.append({
                "text": f"Recovery reason: {recovery.get('reason')}",
                "style": "dim",
            })
    impl_files = implementer_changes()
    activity = model_activity()
    timeline = session_timeline()

    return {
        "timestamp": datetime.now().isoformat(),
        "phase": phase,
        "subprocesses": subs,
        "bridge_history": history[-12:],
        "agents": agents,
        "db_jobs": jobs,
        "git_status": gs,
        "git_branch": branch,
        "git_log": commits,
        "deferred_count": dc,
        "log_tail": log,
        "wave": wave,
        "lock": lock,
        "recovery": recovery,
        "narrative": narrative,
        "impl_files": impl_files,
        "model_activity": activity,
        "timeline": timeline,
    }


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>RCX Pipeline</title>
<style>
:root {
  --bg-0: #0a0e14; --bg-1: #11151c; --bg-2: #1a1f2b; --bg-3: #242a38;
  --border: #2a3040; --text: #d4dae4; --text-dim: #6b7590; --text-muted: #4a5268;
  --accent: #5b9cf5; --green: #4ec88b; --yellow: #e6b450; --red: #ef6b73;
  --purple: #c39cf5; --orange: #f5a76c; --cyan: #73d0ff;
  --mono: 'SF Mono', 'Fira Code', 'JetBrains Mono', 'Cascadia Code', monospace;
  --sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: var(--mono); background: var(--bg-0); color: var(--text); font-size: 12px; line-height: 1.5; }

.layout { display: grid; grid-template-columns: 300px 1fr; grid-template-rows: auto auto 1fr; height: 100vh; }
.header { grid-column: 1 / -1; display: flex; align-items: center; justify-content: space-between; padding: 10px 20px; background: var(--bg-1); border-bottom: 1px solid var(--border); }
.header h1 { font-size: 14px; color: var(--accent); font-weight: 600; letter-spacing: 0.5px; }
.header .meta { color: var(--text-dim); font-size: 11px; }
.header .controls { display: flex; align-items: center; gap: 12px; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot-green { background: var(--green); box-shadow: 0 0 6px var(--green); }
.dot-yellow { background: var(--yellow); box-shadow: 0 0 6px var(--yellow); }
.dot-red { background: var(--red); box-shadow: 0 0 6px var(--red); }
.dot-dim { background: var(--text-muted); }

/* Narrative banner — full width below header */
.narrative-bar { grid-column: 1 / -1; background: var(--bg-1); border-bottom: 1px solid var(--border); padding: 12px 20px; }
.narrative-line { padding: 2px 0; font-size: 13px; font-family: var(--sans); }
.narrative-line.normal { color: var(--text); }
.narrative-line.dim { color: var(--text-muted); font-size: 11px; }
.narrative-line.detail { color: var(--text-dim); font-size: 12px; }
.narrative-line.reviewer { color: var(--yellow); font-weight: 600; }
.narrative-line.implementer { color: var(--purple); font-weight: 600; }
.narrative-line.verdict { color: var(--cyan); font-size: 11px; margin-top: 4px; }

/* Timeline */
.timeline { display: flex; align-items: center; gap: 0; margin-top: 10px; }
.tl-step { display: flex; align-items: center; gap: 0; }
.tl-node { width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; border: 2px solid var(--border); color: var(--text-muted); background: var(--bg-0); position: relative; }
.tl-node.done { border-color: var(--green); color: var(--green); background: #0f2818; }
.tl-node.active { border-color: var(--yellow); color: var(--yellow); background: #2a1f0a; animation: pulse 2s ease-in-out infinite; }
.tl-node.future { border-color: var(--bg-3); color: var(--text-muted); }
.tl-connector { width: 40px; height: 2px; background: var(--bg-3); }
.tl-connector.done { background: var(--green); }
.tl-connector.active { background: var(--yellow); animation: pulse 2s ease-in-out infinite; }
.tl-label { font-size: 9px; color: var(--text-muted); position: absolute; top: 32px; white-space: nowrap; }
.tl-node.done .tl-label { color: var(--green); }
.tl-node.active .tl-label { color: var(--yellow); }

.sidebar { background: var(--bg-1); border-right: 1px solid var(--border); overflow-y: auto; padding: 0; }
.main { overflow-y: auto; padding: 16px 20px; }

.section { margin-bottom: 2px; }
.section-header { padding: 8px 16px; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: var(--text-muted); background: var(--bg-0); position: sticky; top: 0; z-index: 1; }
.section-body { padding: 8px 16px 12px; }

.phase-pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 4px; font-weight: 700; font-size: 13px; letter-spacing: 0.5px; }
.phase-idle { background: var(--bg-3); color: var(--text-muted); }
.phase-dispatch { background: #1a2540; color: var(--accent); }
.phase-phase-a { background: #2a1f0a; color: var(--yellow); }
.phase-phase-b { background: #241a30; color: var(--purple); }
.phase-bridge { background: #1a2a2a; color: var(--cyan); }
.phase-commit { background: #0f2818; color: var(--green); }
.phase-post-merge { background: #1a2540; color: var(--accent); }

.kv { display: flex; justify-content: space-between; padding: 3px 0; }
.kv .k { color: var(--text-dim); }
.kv .v { color: var(--text); text-align: right; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Model cards */
.model-card { display: flex; align-items: center; gap: 10px; padding: 10px; margin: 4px 0; border-radius: 6px; border: 1px solid var(--border); }
.model-card.active { border-color: var(--yellow); }
.model-avatar { width: 36px; height: 36px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 16px; font-weight: 800; }
.model-avatar.reviewer { background: linear-gradient(135deg, #2a1f0a, #3a2f1a); color: var(--yellow); }
.model-avatar.implementer { background: linear-gradient(135deg, #241a30, #342a40); color: var(--purple); }
.model-avatar.agents { background: linear-gradient(135deg, #1a2a2a, #2a3a3a); color: var(--cyan); }
.model-info { flex: 1; }
.model-name { font-weight: 700; font-size: 12px; }
.model-role { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; }
.model-role.reviewing { color: var(--yellow); }
.model-role.implementing { color: var(--purple); }
.model-role.auditing { color: var(--cyan); }
.model-meta { color: var(--text-muted); font-size: 10px; }

.decision { display: inline-block; padding: 1px 6px; border-radius: 3px; font-weight: 700; font-size: 10px; letter-spacing: 0.5px; }
.dec-go, .dec-commit_go { background: #0f2818; color: var(--green); }
.dec-request_changes, .dec-needs_phase_b, .dec-needs_phase_a, .dec-commit_go_hold_push { background: #2a1f0a; color: var(--yellow); }
.dec-no_go, .dec-error, .dec-stale { background: #2a0f0f; color: var(--red); }

.round { padding: 8px 0; border-bottom: 1px solid var(--bg-0); cursor: pointer; }
.round:last-child { border-bottom: none; }
.round:hover { background: var(--bg-2); margin: 0 -16px; padding: 8px 16px; }
.round-top { display: flex; align-items: center; gap: 8px; }
.round-time { color: var(--text-muted); font-size: 10px; min-width: 55px; }
.round-id { color: var(--text-dim); font-size: 10px; }
.round-counts { font-size: 10px; margin-left: auto; }
.round-counts .blk { color: var(--red); font-weight: 700; }
.round-counts .nb { color: var(--yellow); }
.round-summary { color: var(--text-dim); font-size: 11px; padding: 6px 0 0 63px; line-height: 1.6; display: none; }
.round.expanded .round-summary { display: block; }
.round-findings { padding: 4px 0 0 63px; display: none; }
.round.expanded .round-findings { display: block; }

.finding { padding: 4px 8px; margin: 3px 0; border-radius: 3px; font-size: 11px; border-left: 3px solid transparent; }
.finding-blk { background: #1f0f0f; border-left-color: var(--red); }
.finding-nb { background: #1f1a0a; border-left-color: var(--yellow); }
.finding-sev { font-size: 9px; padding: 0 4px; border-radius: 2px; font-weight: 700; margin-right: 4px; }
.sev-critical { background: var(--red); color: #fff; }
.sev-high { background: #a03030; color: #fff; }
.sev-medium { background: #6b5020; color: var(--text); }
.sev-low { background: var(--bg-3); color: var(--text-dim); }

.log-pane { background: var(--bg-0); border: 1px solid var(--border); border-radius: 6px; padding: 0; overflow: hidden; }
.log-header { display: flex; justify-content: space-between; padding: 8px 12px; background: var(--bg-2); border-bottom: 1px solid var(--border); font-size: 10px; }
.log-header .file { color: var(--cyan); font-weight: 600; }
.log-header .age { color: var(--text-muted); }
.log-body { padding: 8px 12px; max-height: 350px; overflow-y: auto; font-size: 11px; line-height: 1.6; color: var(--text-dim); white-space: pre-wrap; word-break: break-all; }
.log-body .highlight { color: var(--green); }
.log-body .warn { color: var(--yellow); }
.log-body .err { color: var(--red); }

.job-row { display: grid; grid-template-columns: 1fr auto auto auto; gap: 8px; padding: 4px 0; border-bottom: 1px solid var(--bg-0); font-size: 11px; align-items: center; }
.job-row:last-child { border-bottom: none; }
.job-id { color: var(--accent); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.job-status { color: var(--text-dim); }
.job-round { color: var(--text-muted); }

.git-row { color: var(--text-dim); font-size: 11px; padding: 1px 0; }
.git-modified { color: var(--yellow); }
.git-added { color: var(--green); }
.git-deleted { color: var(--red); }
.git-untracked { color: var(--text-muted); }

.commit-row { color: var(--text-dim); font-size: 11px; padding: 2px 0; }
.commit-sha { color: var(--accent); }

.empty { color: var(--text-muted); font-style: italic; padding: 8px 0; }

.progress-bar { height: 3px; background: var(--bg-3); border-radius: 2px; margin: 8px 0; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 2px; transition: width 0.5s ease; }
.progress-fill.active { animation: pulse 2s ease-in-out infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }

.agent-row { display: flex; align-items: center; gap: 6px; padding: 3px 0; font-size: 11px; }
.agent-pass { color: var(--green); }
.agent-fail { color: var(--red); }
.agent-running { color: var(--yellow); animation: pulse 1.5s ease-in-out infinite; }

.lock-badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 3px; font-size: 10px; font-weight: 600; }
.lock-active { background: #2a1f0a; color: var(--yellow); }
.lock-stale { background: #2a0f0f; color: var(--red); }
.lock-clear { background: var(--bg-3); color: var(--text-muted); }

.impl-files { margin-top: 8px; }
.impl-file { color: var(--text-dim); font-size: 10px; padding: 1px 0; }
</style>
</head>
<body>
<div class="layout">
  <div class="header">
    <div style="display:flex;align-items:center;gap:12px">
      <h1>RCX PIPELINE</h1>
      <span id="phaseBadge" class="phase-pill phase-idle">IDLE</span>
      <span id="lockBadge" class="lock-badge lock-clear">UNLOCKED</span>
    </div>
    <div class="controls">
      <span id="statusDot" class="dot dot-dim"></span>
      <span class="meta" id="clock"></span>
    </div>
  </div>

  <div class="narrative-bar" id="narrativeBar"></div>
  <div class="sidebar" id="sidebar"></div>
  <div class="main" id="main"></div>
</div>

<script>
let autoTimer = null;
let lastData = null;

function elapsed(ts) {
  if (!ts) return '';
  const d = (Date.now()/1000 - ts);
  if (d < 0) return '';
  const h = Math.floor(d/3600), m = Math.floor((d%3600)/60), s = Math.floor(d%60);
  if (h) return h+'h '+String(m).padStart(2,'0')+'m';
  if (m) return m+'m '+String(s).padStart(2,'0')+'s';
  return s+'s';
}

function esc(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }
function decClass(d) { return 'dec-'+(d||'').toLowerCase().replace(/[^a-z_]/g,''); }

function colorLogLine(line) {
  const l = line.toLowerCase();
  if (l.includes('error') || l.includes('fail') || l.includes('traceback'))
    return '<span class="err">'+esc(line)+'</span>';
  if (l.includes('warn') || l.includes('timeout') || l.includes('retry'))
    return '<span class="warn">'+esc(line)+'</span>';
  if (l.includes('pass') || l.includes('success') || l.includes('go') || l.includes('complete'))
    return '<span class="highlight">'+esc(line)+'</span>';
  return '<span class="line">'+esc(line)+'</span>';
}

function renderNarrative(data) {
  const narr = data.narrative || [];
  const p = data.phase || {};
  const wave = data.wave;
  const lock = data.lock;

  // Update header badges
  const phaseName = (p.phase||'idle').toUpperCase();
  document.getElementById('phaseBadge').className = 'phase-pill phase-'+(p.phase||'idle');
  document.getElementById('phaseBadge').innerHTML = phaseName + (p.started ? ' <span style="font-weight:400;font-size:11px;opacity:0.7">'+elapsed(p.started)+'</span>' : '');

  const dot = document.getElementById('statusDot');
  dot.className = 'dot ' + (p.phase === 'idle' ? 'dot-dim' : 'dot-green');

  if (lock) {
    const lb = document.getElementById('lockBadge');
    lb.className = 'lock-badge ' + (lock.alive ? 'lock-active' : 'lock-stale');
    lb.textContent = lock.alive ? 'BRIDGE LOCKED' : 'STALE LOCK';
  } else {
    document.getElementById('lockBadge').className = 'lock-badge lock-clear';
    document.getElementById('lockBadge').textContent = 'UNLOCKED';
  }

  let html = '';

  // Narrative lines
  narr.forEach(n => {
    html += `<div class="narrative-line ${n.style||'normal'}">${esc(n.text)}</div>`;
  });

  // Timeline
  const ph = (p.phase||'idle');
  const stages = [
    {id:'dispatch', label:'Dispatch', short:'D'},
    {id:'phase-a', label:'Plan', short:'A'},
    {id:'phase-b', label:'Implement', short:'B'},
    {id:'bridge', label:'Review', short:'R'},
    {id:'commit', label:'Commit', short:'C'},
    {id:'post-merge', label:'Route', short:'M'},
  ];
  const phaseOrder = stages.map(s => s.id);
  const currentIdx = phaseOrder.indexOf(ph);

  html += '<div class="timeline">';
  stages.forEach((s, i) => {
    let cls = 'future';
    if (i < currentIdx) cls = 'done';
    else if (i === currentIdx) cls = 'active';
    // Special: if in phase-b, bridge counts as the same stage
    if (ph === 'phase-b' && s.id === 'bridge') cls = 'active';
    if (ph === 'bridge' && s.id === 'phase-b') cls = 'done';

    html += `<div class="tl-step">`;
    if (i > 0) html += `<div class="tl-connector ${cls === 'future' ? '' : cls}"></div>`;
    html += `<div class="tl-node ${cls}">${s.short}<span class="tl-label">${s.label}</span></div>`;
    html += `</div>`;
  });
  html += '</div>';

  document.getElementById('narrativeBar').innerHTML = html;
}

function renderSidebar(data) {
  const p = data.phase || {};
  const subs = data.subprocesses || [];
  const wave = data.wave;
  const recovery = data.recovery;
  const agents = data.agents;
  const jobs = data.db_jobs || [];
  const gs = data.git_status || [];
  const branch = data.git_branch || '?';
  const commits = data.git_log || [];
  const dc = data.deferred_count || 0;
  const implFiles = data.impl_files || [];

  let html = '';

  // Who's Working — model cards
  html += '<div class="section"><div class="section-header">Who\'s Working</div><div class="section-body">';
  // Deduplicate subs by role
  const reviewerSubs = subs.filter(s => s.role === 'reviewer');
  const implSubs = subs.filter(s => s.role === 'implementer');
  const auditorSubs = subs.filter(s => s.role === 'auditor');

  if (reviewerSubs.length) {
    const oldest = reviewerSubs.reduce((a,b) => (a.started||Infinity) < (b.started||Infinity) ? a : b);
    html += `<div class="model-card active">
      <div class="model-avatar reviewer">Cx</div>
      <div class="model-info">
        <div class="model-role reviewing">REVIEWING</div>
        <div class="model-name">Codex GPT-5.4 xhigh</div>
        <div class="model-meta">${reviewerSubs.length} process${reviewerSubs.length>1?'es':''} &middot; ${elapsed(oldest.started)}</div>
      </div>
    </div>`;
  }
  if (implSubs.length) {
    const oldest = implSubs.reduce((a,b) => (a.started||Infinity) < (b.started||Infinity) ? a : b);
    html += `<div class="model-card active">
      <div class="model-avatar implementer">Cl</div>
      <div class="model-info">
        <div class="model-role implementing">IMPLEMENTING</div>
        <div class="model-name">Claude Opus 4.6 max</div>
        <div class="model-meta">${implSubs.length} process${implSubs.length>1?'es':''} &middot; ${elapsed(oldest.started)}</div>
      </div>
    </div>`;
  }
  if (auditorSubs.length) {
    const oldest = auditorSubs.reduce((a,b) => (a.started||Infinity) < (b.started||Infinity) ? a : b);
    html += `<div class="model-card active">
      <div class="model-avatar agents">9</div>
      <div class="model-info">
        <div class="model-role auditing">AUDITING</div>
        <div class="model-name">9 Native SDK Agents</div>
        <div class="model-meta">${auditorSubs.length} process${auditorSubs.length>1?'es':''} &middot; PID ${oldest.pid} &middot; ${elapsed(oldest.started)}</div>
      </div>
    </div>`;
  }
  // SDK agents status details (from status.json, complements the process card above)
  if (agents) {
    const running = agents.running_agents || [];
    const completed = agents.completed_agents || {};
    const total = running.length + Object.keys(completed).length;
    const passed = Object.values(completed).filter(v => v.passed).length;
    const failed = Object.values(completed).filter(v => !v.passed).length;
    if (total) {
      html += `<div class="model-card${running.length ? ' active' : ''}">
        <div class="model-avatar agents">9</div>
        <div class="model-info">
          <div class="model-role auditing">SDK AGENTS</div>
          <div class="model-name">9 Native Agents</div>
          <div class="model-meta">${running.length ? running.length+' running' : ''} ${passed ? passed+' passed' : ''} ${failed ? failed+' failed' : ''}</div>
        </div>
      </div>`;
      // Show individual agent results
      Object.entries(completed).forEach(([name, info]) => {
        const cls = info.passed ? 'agent-pass' : 'agent-fail';
        const mark = info.passed ? '&#x2713;' : '&#x2717;';
        html += `<div class="agent-row" style="padding-left:46px"><span class="${cls}">${mark}</span> ${esc(name)}</div>`;
      });
    }
  }
  if (!subs.length && !agents && p.pid) {
    html += `<div class="model-card">
      <div class="model-avatar implementer" style="font-size:12px">?</div>
      <div class="model-info">
        <div class="model-role implementing">${(p.phase||'').toUpperCase()}</div>
        <div class="model-name">PID ${p.pid}</div>
        <div class="model-meta">${elapsed(p.started)}</div>
      </div>
    </div>`;
  }
  if (!subs.length && !agents && !p.pid) {
    html += '<div class="empty">No active processes</div>';
  }
  html += '</div></div>';

  // Wave context
  if (wave) {
    html += '<div class="section"><div class="section-header">Current Wave</div><div class="section-body">';
    const waveShort = (wave.wave_id||'').replace(/^jabramsja\//, '').replace(/_/g,' ').slice(0,45);
    html += `<div class="kv"><span class="k">Wave</span><span class="v" title="${esc(wave.wave_id)}">${esc(waveShort)}</span></div>`;
    if (wave.task_id) html += `<div class="kv"><span class="k">Task</span><span class="v">${esc(wave.task_id)}</span></div>`;
    html += `<div class="kv"><span class="k">Step</span><span class="v">${esc(wave.step)}</span></div>`;
    if (wave.max_rounds) {
      html += `<div class="kv"><span class="k">Bridge</span><span class="v">${wave.bridge_rounds} / ${wave.max_rounds} rounds</span></div>`;
      const pct = Math.min(100, Math.round(wave.bridge_rounds / wave.max_rounds * 100));
      html += `<div class="progress-bar"><div class="progress-fill active" style="width:${pct}%;background:var(--purple)"></div></div>`;
    }
    if (wave.target_branch) html += `<div class="kv"><span class="k">Branch</span><span class="v" style="color:var(--accent)">${esc(wave.target_branch)}</span></div>`;
    html += '</div></div>';
  }

  if (recovery) {
    const summary = `${recovery.label} — Tier ${recovery.tier} ${recovery.failure_class || ''}`.trim();
    html += '<div class="section"><div class="section-header">Recovery</div><div class="section-body">';
    html += `<div style="font-size:11px;font-weight:700;color:${recovery.active ? 'var(--yellow)' : 'var(--cyan)'};margin-bottom:6px">${esc(summary)}</div>`;
    if (recovery.retry_target) html += `<div class="kv"><span class="k">Target</span><span class="v">${esc(recovery.retry_target)}</span></div>`;
    if (recovery.wave_invocation_count || recovery.tuple_attempt_index) {
      html += `<div class="kv"><span class="k">Count</span><span class="v">${recovery.wave_invocation_count||'?'} in wave · try ${recovery.tuple_attempt_index||'?'}</span></div>`;
    }
    if (recovery.state) {
      const loop = recovery.max_iterations ? ` · ${recovery.current_iteration||0}/${recovery.max_iterations}` : '';
      html += `<div class="kv"><span class="k">State</span><span class="v">${esc(recovery.state + loop)}</span></div>`;
    }
    if (recovery.owner_pid) {
      let pidText = `owner ${recovery.owner_pid}`;
      if (recovery.child_pid) pidText += ` · ${(recovery.child_role||'child')} ${recovery.child_pid}`;
      html += `<div class="kv"><span class="k">PIDs</span><span class="v">${esc(pidText)}</span></div>`;
    }
    if (recovery.reason) html += `<div style="margin-top:6px;font-size:11px;color:var(--text-dim)">Reason: ${esc(recovery.reason)}</div>`;
    if (recovery.explanation) html += `<div style="margin-top:4px;font-size:11px;color:var(--text-dim)">Note: ${esc(recovery.explanation)}</div>`;
    if (recovery.current_command) html += `<div style="margin-top:4px;font-size:10px;color:var(--text-muted)">Cmd: ${esc(recovery.current_command)}</div>`;
    if (!recovery.active && recovery.outcome) {
      let outcome = recovery.outcome;
      if (recovery.last_action) outcome += ` via ${recovery.last_action}`;
      html += `<div style="margin-top:6px;font-size:11px;color:var(--cyan)">Outcome: ${esc(outcome)}</div>`;
    }
    if (recovery.detail && recovery.detail !== recovery.reason && recovery.detail !== recovery.explanation) {
      html += `<div style="margin-top:4px;font-size:10px;color:var(--text-muted)">Detail: ${esc(recovery.detail)}</div>`;
    }
    html += '</div></div>';
  }

  // Files changed by implementer
  if (implFiles.length) {
    html += '<div class="section"><div class="section-header">Files Changed</div><div class="section-body">';
    implFiles.slice(0,15).forEach(f => {
      html += `<div class="impl-file">${esc(f)}</div>`;
    });
    if (implFiles.length > 15) html += `<div class="impl-file" style="color:var(--text-muted)">+${implFiles.length-15} more</div>`;
    html += '</div></div>';
  }

  // Bridge DB
  if (jobs.length) {
    html += '<div class="section"><div class="section-header">Bridge History</div><div class="section-body">';
    jobs.forEach(j => {
      const dec = j.terminal_decision || '';
      const id = (j.job_id||'').split('-').slice(-1)[0].slice(0,10);
      html += `<div class="job-row">
        <span class="job-id" title="${esc(j.job_id)}">${esc(id)}</span>
        <span class="job-status">${esc(j.status)}</span>
        ${dec ? '<span class="decision '+decClass(dec)+'">'+esc(dec)+'</span>' : '<span></span>'}
        <span class="job-round">R${j.current_round||'?'}</span>
      </div>`;
    });
    html += '</div></div>';
  }

  // Git
  html += '<div class="section"><div class="section-header">Repository</div><div class="section-body">';
  html += `<div class="kv"><span class="k">Branch</span><span class="v" style="color:var(--accent)">${esc(branch)}</span></div>`;
  html += `<div class="kv"><span class="k">Modified</span><span class="v">${gs.length} files</span></div>`;
  html += `<div class="kv"><span class="k">Deferred</span><span class="v">${dc} items</span></div>`;
  if (gs.length) {
    html += '<div style="margin-top:6px">';
    gs.slice(0,10).forEach(l => {
      const status = l.trim().charAt(0);
      const cls = status==='M'?'git-modified':status==='A'?'git-added':status==='D'?'git-deleted':'git-untracked';
      html += `<div class="git-row ${cls}">${esc(l)}</div>`;
    });
    if (gs.length > 10) html += `<div class="git-row git-untracked">+${gs.length-10} more</div>`;
    html += '</div>';
  }
  html += '<div style="margin-top:8px">';
  commits.slice(0,3).forEach(c => {
    const parts = c.split(' ', 2);
    html += `<div class="commit-row"><span class="commit-sha">${esc(parts[0])}</span> ${esc(parts[1]||'')}</div>`;
  });
  html += '</div></div></div>';

  document.getElementById('sidebar').innerHTML = html;
}

function statusDot(status) {
  if (status === 'active') return '<span class="dot dot-green" style="margin-right:6px"></span>';
  if (status === 'stale') return '<span class="dot dot-yellow" style="margin-right:6px"></span>';
  return '<span class="dot dot-dim" style="margin-right:6px"></span>';
}

function renderMain(data) {
  const history = data.bridge_history || [];
  const log = data.log_tail || {};
  const activity = data.model_activity || [];

  let html = '';

  // Model Activity Feeds — the main event
  if (activity.length) {
    activity.forEach(feed => {
      html += '<div class="log-pane" style="margin-bottom:16px">';

      const roleColor = feed.role === 'implementer' ? 'var(--purple)' :
                        feed.role.includes('reviewer') ? 'var(--yellow)' : 'var(--cyan)';
      const statusText = feed.status === 'active' ? 'LIVE' :
                         feed.status === 'stale' ? `${feed.age}s ago` :
                         feed.status === 'done' ? 'DONE' : '';
      const sizeStr = feed.size ? ` (${Math.round(feed.size/1024)}KB)` : '';

      html += `<div class="log-header">
        <span>${statusDot(feed.status)}<span style="color:${roleColor};font-weight:700">${esc(feed.source)}</span></span>
        <span class="age">${statusText}${sizeStr}</span>
      </div>`;

      html += '<div class="log-body" style="max-height:250px">';

      if (feed.events) {
        // Structured Codex events
        feed.events.forEach(evt => {
          const kindColor = evt.kind === 'tool' ? 'var(--cyan)' :
                           evt.kind === 'text' ? 'var(--text)' : 'var(--text-muted)';
          const actionColor = evt.kind === 'tool' ? 'var(--green)' : 'var(--text-dim)';
          html += `<div style="padding:2px 0;border-bottom:1px solid var(--bg-2)">`;
          html += `<span style="color:var(--text-muted);font-size:10px;min-width:55px;display:inline-block">${evt.time}</span>`;
          html += `<span style="color:${actionColor};font-weight:600;font-size:11px">${esc(evt.action)}</span>`;
          if (evt.detail) {
            html += ` <span style="color:var(--text-dim);font-size:10px">${esc(evt.detail)}</span>`;
          }
          html += `</div>`;
        });
        if (!feed.events.length) {
          html += '<span class="line" style="color:var(--text-muted)">Waiting for events...</span>';
        }
      } else if (feed.lines) {
        // Raw text output
        feed.lines.forEach(l => { html += colorLogLine(l) + '\n'; });
        if (!feed.lines.length) {
          html += '<span class="line" style="color:var(--text-muted)">No output yet...</span>';
        }
      }

      html += '</div></div>';
    });
  }

  // Executor log (if no model activity, or as supplement)
  if (!activity.length) {
    html += '<div class="log-pane" style="margin-bottom:16px">';
    if (log.file) {
      html += `<div class="log-header"><span class="file">${esc(log.file)}</span><span class="age">${log.age}s ago</span></div>`;
      html += '<div class="log-body" id="logBody">';
      (log.lines||[]).forEach(l => { html += colorLogLine(l) + '\n'; });
      html += '</div>';
    } else {
      html += '<div class="log-header"><span class="file">Live Output</span><span class="age">waiting</span></div>';
      html += '<div class="log-body"><span class="line" style="color:var(--text-muted)">Waiting for pipeline activity...</span></div>';
    }
    html += '</div>';
  }

  // Latest Review Round — only show the newest, fully expanded with all findings
  if (history.length) {
    const r = history[history.length - 1]; // newest is last (sorted by timestamp)
    const blk = r.blocking||[], nb = r.non_blocking||[];
    html += '<div style="margin-bottom:20px">';
    html += '<div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--text-muted);margin-bottom:8px">Latest Review</div>';
    html += `<div class="round expanded">
      <div class="round-top">
        <span class="round-time">${r.time_str}</span>
        <span class="decision ${decClass(r.decision)}">${esc(r.decision)}</span>
        <span class="round-counts">
          ${blk.length ? '<span class="blk">'+blk.length+' blocking</span> ' : ''}
          ${nb.length ? '<span class="nb">'+nb.length+' advisory</span>' : ''}
        </span>
      </div>`;
    if (r.summary) html += `<div class="round-summary">${esc(r.summary)}</div>`;
    if (blk.length || nb.length) {
      html += '<div class="round-findings">';
      blk.forEach(f => {
        const sev = f.severity || 'medium';
        html += `<div class="finding finding-blk"><span class="finding-sev sev-${sev}">${sev}</span> ${esc(f.title||f.description||'')}</div>`;
      });
      nb.forEach(f => {
        const sev = f.severity || 'low';
        html += `<div class="finding finding-nb"><span class="finding-sev sev-${sev}">${sev}</span> ${esc(f.title||f.description||'')}</div>`;
      });
      html += '</div>';
    }
    html += '</div></div>';
  }

  // Session Timeline
  const tl = data.timeline || {};
  const tlEvents = tl.events || [];
  if (tlEvents.length) {
    html += '<div style="margin-bottom:20px">';
    html += '<div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--text-muted);margin-bottom:8px">Session Timeline</div>';
    html += '<div style="padding:8px 0">';
    tlEvents.forEach(e => {
      let color = 'var(--text-dim)';
      if (e.style === 'good') color = 'var(--green)';
      else if (e.style === 'bad') color = 'var(--red)';
      else if (e.style === 'warning') color = 'var(--yellow)';
      else if (e.style === 'implementer') color = 'var(--purple)';
      else if (e.style === 'active') color = 'var(--cyan)';
      html += `<div style="padding:2px 0;font-size:11px"><span style="color:var(--text-muted);min-width:40px;display:inline-block">${e.time}</span> <span style="color:${color}">${esc(e.label)}</span></div>`;
    });
    // "You are here" marker
    const now = new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',hour12:false});
    const current = tl.current || 'idle';
    html += `<div style="padding:4px 0;font-size:11px"><span style="color:var(--text-muted)">${now}</span> <span style="color:var(--cyan);font-weight:600">&larr; ${esc(current)}</span></div>`;
    html += '</div></div>';
  }

  // Guidance
  html += `<div style="margin-top:12px;padding:10px;background:var(--bg-2);border-radius:6px;font-size:11px;color:var(--text-muted);line-height:1.7">
    <span style="font-weight:600">What's normal:</span>
    Claude implements (5-15m) &rarr; SDK agents check (3-5m) &rarr; Codex reviews (10-20m) &rarr; repeat if needed.<br>
    NO_GO is normal &mdash; usually takes 2-3 rounds to converge. GO means ready to commit.
  </div>`;

  document.getElementById('main').innerHTML = html;
}

function render(data) {
  lastData = data;
  document.getElementById('clock').textContent = new Date().toLocaleTimeString();
  renderNarrative(data);
  renderSidebar(data);
  renderMain(data);
}

function refresh() {
  fetch('/api/state').then(r=>r.json()).then(render).catch(e=>console.error('fetch error',e));
}

refresh();
autoTimer = setInterval(refresh, 3000);
</script>
</body>
</html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/state":
            data = get_state()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data, default=str).encode())
        elif self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    print(f"RCX Pipeline Dashboard: http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
