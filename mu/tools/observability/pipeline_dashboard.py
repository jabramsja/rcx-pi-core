#!/usr/bin/env python3
"""Real-time pipeline dashboard. Read-only — safe to run alongside active pipeline."""

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

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
REFRESH_INTERVAL = 5

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


def _parse_agent_envelope(text):
    matches = list(re.finditer(r"BEGIN_AGENT_ENVELOPE\s*\n(.*?)\nEND_AGENT_ENVELOPE", text, re.DOTALL))
    if not matches:
        return None
    for match in reversed(matches):
        try:
            env = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        decision = env.get("decision", "")
        if decision and "|" not in decision:
            return env
    return None


def _parse_rendered_reviewer_section(text):
    section_re = re.compile(r"(?ms)^### .*? — reviewer\n(.*?)(?=^### |\Z)")
    decision_re = re.compile(
        r"(?m)^\s*-\s*Decision:\s*"
        r"(GO|REQUEST_CHANGES|NO_GO|QUESTION|STALE|ERROR|SYNTHETIC)\b"
    )
    summary_re = re.compile(r"(?m)^\s*-\s*Summary:\s*(.*)")
    finding_re = re.compile(
        r"(?m)^\s*\d+\.\s+\*\*(DEFECT|POLICY_BOUND|DOC_ACCURACY)\*\* "
        r"\(([^)]+)\):\s*(.*)$"
    )
    sections = list(section_re.finditer(text))
    for section in reversed(sections):
        block = section.group(1)
        decision_match = decision_re.search(block)
        if not decision_match:
            continue
        decision = decision_match.group(1)
        if decision == "SYNTHETIC":
            continue
        summary_match = summary_re.search(block)
        disposition = "non_blocking" if decision == "GO" else "blocking"
        findings = [
            {
                "class": cls,
                "severity": severity.strip().lower(),
                "title": title.strip(),
                "disposition": disposition,
            }
            for cls, severity, title in finding_re.findall(block)
        ]
        return {
            "decision": decision,
            "summary": (summary_match.group(1).strip() if summary_match else ""),
            "findings": findings,
        }
    return None


def _parse_review_payload(text):
    return _parse_agent_envelope(text) or _parse_rendered_reviewer_section(text)


def _is_bridge_round_dir(name):
    return (
        name.startswith("phase-a-r")
        or name.startswith("phase-b-r")
        or name.startswith("phase-a-reentry-r")
        or name.startswith("phase-b-reentry-r")
    )


def _bridge_review_artifact(job_id, reviewer_file):
    rendered = REPO_ROOT / ".agent_bus" / "rendered" / f"{job_id}.md"
    candidates = [rendered]
    if reviewer_file is not None:
        candidates.append(reviewer_file)
    for path in candidates:
        if path is None or not path.exists():
            continue
        try:
            env = _parse_review_payload(path.read_text())
        except Exception:
            continue
        if env is not None:
            return env, path.stat().st_mtime
    return None, None


def detect_phase(lines):
    for name, pattern in [("phase-a", "phase_a_executor"), ("phase-b", "phase_b_executor"),
                          ("commit", "commit_executor")]:
        for l in lines:
            if pattern in l and "grep" not in l and "test_" not in l:
                pid = int(l.split()[1])
                return name, pid, pid_start(pid)
    for l in lines:
        if "meta_bridge_supervisor" in l and "grep" not in l and "test_" not in l:
            pid = int(l.split()[1])
            phase = "post-merge" if "--mode post-merge" in l or " post-merge " in l else "commit"
            return phase, pid, pid_start(pid)
    for l in lines:
        if "executor_dispatch" in l and "grep" not in l:
            return "dispatch", int(l.split()[1]), pid_start(int(l.split()[1]))
    return "idle", None, None


def detect_subs(lines):
    subs = []
    for l in lines:
        if "grep" in l: continue
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
        if not d.is_dir() or not _is_bridge_round_dir(d.name):
            continue
        reviewer_files = sorted(
            (f for f in d.iterdir() if "reviewer" in f.name),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        reviewer_file = reviewer_files[0] if reviewer_files else None
        env, mtime = _bridge_review_artifact(d.name, reviewer_file)
        if env is None or mtime is None:
            continue
        findings = env.get("findings", [])
        blk = [x for x in findings if x.get("disposition") == "blocking"]
        nblk = [x for x in findings if x.get("disposition") != "blocking"]
        rounds.append({
            "job_id": d.name,
            "decision": env.get("decision", ""),
            "blocking": blk,
            "non_blocking": nblk,
            "timestamp": mtime,
        })
    rounds.sort(key=lambda r: r["timestamp"])
    return rounds


def latest_bridge_summary():
    """Return (job_id, decision, summary, blocking_findings, non_blocking_findings) from most recent reviewer."""
    raw_dir = REPO_ROOT / ".agent_bus" / "raw"
    if not raw_dir.exists():
        return None
    latest = None
    latest_mtime = 0.0
    for d in raw_dir.iterdir():
        if not d.is_dir() or not _is_bridge_round_dir(d.name):
            continue
        reviewer_files = sorted(
            (f for f in d.iterdir() if "reviewer" in f.name),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        reviewer_file = reviewer_files[0] if reviewer_files else None
        env, mtime = _bridge_review_artifact(d.name, reviewer_file)
        if env is None or mtime is None or mtime <= latest_mtime:
            continue
        latest_mtime = mtime
        latest = (d.name, env)
    if not latest:
        return None
    env = latest[1]
    dec = env.get("decision", "")
    summary = env.get("summary", "")
    findings = env.get("findings", [])
    blk = [x for x in findings if x.get("disposition") == "blocking"]
    nblk = [x for x in findings if x.get("disposition") != "blocking"]
    return latest[0], dec, summary, blk, nblk


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


def main():
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else REFRESH_INTERVAL
    try:
        while True:
            os.system("clear")
            print(render())
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nDashboard stopped.")


if __name__ == "__main__":
    main()
