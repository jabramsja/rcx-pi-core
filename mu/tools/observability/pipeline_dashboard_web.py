#!/usr/bin/env python3
"""RCX Pipeline Web Dashboard. Read-only. No dependencies beyond stdlib."""

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

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
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


def detect_phase(lines):
    for name, pattern in [("phase-a", "phase_a_executor"), ("phase-b", "phase_b_executor"),
                          ("commit", "commit_executor"), ("post-merge", "meta_bridge_supervisor")]:
        for l in lines:
            if pattern in l and "grep" not in l and "test_" not in l:
                pid = int(l.split()[1])
                return {"phase": name, "pid": pid, "started": pid_start(pid)}
    for l in lines:
        if "executor_dispatch" in l and "grep" not in l:
            return {"phase": "dispatch", "pid": int(l.split()[1]), "started": pid_start(int(l.split()[1]))}
    return {"phase": "idle", "pid": None, "started": None}


def detect_subs(lines):
    subs = []
    for l in lines:
        if "grep" in l:
            continue
        if "codex exec" in l:
            pid = int(l.split()[1])
            subs.append({"name": "Codex 5.4 xhigh", "role": "reviewing", "pid": pid, "started": pid_start(pid)})
        elif "claude --print" in l:
            pid = int(l.split()[1])
            subs.append({"name": "Claude opus max", "role": "implementing", "pid": pid, "started": pid_start(pid)})
        elif "run_review.py" in l:
            pid = int(l.split()[1])
            subs.append({"name": "SDK Agents", "role": "reviewing", "pid": pid, "started": pid_start(pid)})
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
                env = json.loads(matches[-1].group(1))
                dec = env.get("decision", "")
                if "|" in dec:
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


def db_latest_jobs(n=6):
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


def deferred_count():
    d = REPO_ROOT / "reports" / "deferred" / "non_blocking"
    if not d.exists():
        return 0
    return len([f for f in d.iterdir() if f.is_file() and f.name != "README.md"])


def get_state():
    psl = ps_lines()
    phase = detect_phase(psl)
    subs = detect_subs(psl)
    routing = read_json_safe(REPO_ROOT / ".agent_bus" / "meta" / "post_merge_routing.json")
    pb_state = read_json_safe(REPO_ROOT / ".agent_bus" / "executors" / "phase_b_state.json")
    history = bridge_round_history()
    agents = agent_status()
    jobs = db_latest_jobs()
    gs = git_status()
    dc = deferred_count()

    # Clean up pb_state for JSON (remove large lists)
    if pb_state:
        for key in ["all_non_blocking", "finding_history", "implementer_changed",
                     "executor_created", "baseline_wave_files"]:
            pb_state.pop(key, None)

    return {
        "timestamp": datetime.now().isoformat(),
        "phase": phase,
        "subprocesses": subs,
        "routing": routing,
        "phase_b_state": pb_state,
        "bridge_history": history[-12:],
        "agents": agents,
        "db_jobs": jobs,
        "git_status": gs,
        "deferred_count": dc,
    }


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>RCX Pipeline Dashboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace; background: #0d1117; color: #c9d1d9; font-size: 13px; }
.container { max-width: 1200px; margin: 0 auto; padding: 16px; }
header { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #30363d; margin-bottom: 16px; }
header h1 { font-size: 18px; color: #58a6ff; }
header .time { color: #8b949e; }
.refresh-btn { background: #21262d; border: 1px solid #30363d; color: #c9d1d9; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-family: inherit; }
.refresh-btn:hover { background: #30363d; }
.auto-label { color: #8b949e; font-size: 11px; margin-left: 8px; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.full-width { grid-column: 1 / -1; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
.card h2 { font-size: 13px; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; border-bottom: 1px solid #21262d; padding-bottom: 8px; }
.phase-badge { display: inline-block; padding: 4px 12px; border-radius: 12px; font-weight: bold; font-size: 14px; }
.phase-idle { background: #21262d; color: #8b949e; }
.phase-phase-a { background: #2d1f00; color: #d29922; }
.phase-phase-b { background: #2d1032; color: #bc8cff; }
.phase-commit { background: #0d2818; color: #3fb950; }
.phase-post-merge { background: #0d2d3d; color: #58a6ff; }
.phase-dispatch { background: #0d2d3d; color: #58a6ff; }
.sub { padding: 6px 0; border-bottom: 1px solid #21262d; }
.sub:last-child { border-bottom: none; }
.sub-name { color: #58a6ff; font-weight: bold; }
.sub-role { color: #8b949e; }
.pid { color: #484f58; font-size: 11px; }
.elapsed { color: #8b949e; }
.decision { display: inline-block; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; }
.dec-GO, .dec-COMMIT_GO { background: #0d2818; color: #3fb950; }
.dec-REQUEST_CHANGES, .dec-NEEDS_PHASE_B, .dec-NEEDS_PHASE_A, .dec-COMMIT_GO_HOLD_PUSH { background: #2d1f00; color: #d29922; }
.dec-NO_GO, .dec-ERROR, .dec-STALE { background: #3d0d0d; color: #f85149; }
.dec-QUESTION { background: #2d1032; color: #bc8cff; }
.round-row { padding: 8px 0; border-bottom: 1px solid #21262d; cursor: pointer; }
.round-row:hover { background: #1c2128; }
.round-row:last-child { border-bottom: none; }
.round-time { color: #484f58; width: 60px; display: inline-block; }
.round-counts { display: inline-block; margin-left: 8px; }
.blocking-count { color: #f85149; font-weight: bold; }
.nonblocking-count { color: #d29922; }
.finding { padding: 6px 8px; margin: 4px 0; border-radius: 4px; font-size: 12px; }
.finding-blocking { background: #3d0d0d; border-left: 3px solid #f85149; }
.finding-nonblocking { background: #2d1f00; border-left: 3px solid #d29922; }
.finding-title { font-weight: bold; }
.finding-detail { color: #8b949e; margin-top: 4px; font-size: 11px; line-height: 1.4; display: none; }
.finding.expanded .finding-detail { display: block; }
.finding-sev { font-size: 10px; padding: 1px 4px; border-radius: 3px; margin-right: 4px; }
.sev-critical { background: #f85149; color: #fff; }
.sev-high { background: #da3633; color: #fff; }
.sev-medium { background: #d29922; color: #000; }
.sev-low { background: #484f58; color: #c9d1d9; }
.agent-row { padding: 4px 0; }
.agent-pass { color: #3fb950; }
.agent-fail { color: #f85149; }
.verdict { color: #8b949e; font-size: 11px; }
.db-row { padding: 4px 0; font-size: 11px; border-bottom: 1px solid #21262d; }
.db-row:last-child { border-bottom: none; }
.job-id { color: #58a6ff; }
.git-file { color: #8b949e; font-size: 11px; padding: 2px 0; }
.summary-text { color: #8b949e; font-size: 12px; line-height: 1.5; margin: 8px 0; padding: 8px; background: #0d1117; border-radius: 4px; }
.section-label { color: #f85149; font-weight: bold; margin: 8px 0 4px; }
.section-label.nb { color: #d29922; }
.meta { color: #484f58; font-size: 11px; }
</style>
</head>
<body>
<div class="container">
<header>
  <h1>RCX Pipeline Dashboard</h1>
  <div>
    <button class="refresh-btn" onclick="refresh()">Refresh</button>
    <label class="auto-label"><input type="checkbox" id="autoRefresh" checked onchange="toggleAuto()"> Auto (5s)</label>
    <span class="time" id="clock"></span>
  </div>
</header>
<div id="dashboard"></div>
</div>
<script>
let autoTimer = null;

function elapsed(ts) {
  if (!ts) return '';
  const d = (Date.now()/1000 - ts);
  const m = Math.floor(d/60), s = Math.floor(d%60), h = Math.floor(m/60);
  if (h) return h+'h'+String(m%60).padStart(2,'0')+'m';
  return m+'m'+String(s).padStart(2,'0')+'s';
}

function decClass(d) { return 'dec-'+(d||'').replace(/[^A-Z_]/g,''); }

function sevClass(s) { return 'sev-'+(s||'medium'); }

function renderFinding(f, type) {
  const cls = type === 'blocking' ? 'finding-blocking' : 'finding-nonblocking';
  const detail = f.detail ? `<div class="finding-detail">${esc(f.detail)}</div>` : '';
  return `<div class="finding ${cls}" onclick="this.classList.toggle('expanded')">
    <span class="finding-sev ${sevClass(f.severity)}">${f.severity||'?'}</span>
    <span class="finding-title">${esc(f.title||'?')}</span>
    ${detail}
  </div>`;
}

function esc(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function render(data) {
  const p = data.phase || {};
  const subs = data.subprocesses || [];
  const routing = data.routing;
  const pb = data.phase_b_state;
  const history = data.bridge_history || [];
  const agents = data.agents;
  const jobs = data.db_jobs || [];
  const gs = data.git_status || [];
  const dc = data.deferred_count || 0;

  let html = '<div class="grid">';

  // Phase card
  html += `<div class="card">
    <h2>Current Phase</h2>
    <div><span class="phase-badge phase-${p.phase}">${(p.phase||'idle').toUpperCase()}</span>
    ${p.pid ? `<span class="pid">PID ${p.pid}</span>` : ''}
    <span class="elapsed">${elapsed(p.started)}</span></div>`;
  subs.forEach(s => {
    html += `<div class="sub">
      <span class="sub-name">${s.name}</span> <span class="sub-role">${s.role}</span>
      <span class="pid">PID ${s.pid}</span> <span class="elapsed">${elapsed(s.started)}</span>
    </div>`;
  });
  if (!subs.length) html += '<div class="sub"><span class="sub-role">No active subprocess</span></div>';
  html += '</div>';

  // State card
  html += '<div class="card"><h2>Pipeline State</h2>';
  if (routing) {
    html += `<div>Route: <span class="decision ${decClass(routing.decision)}">${routing.decision}</span></div>
      <div class="meta">Task: ${routing.task_id||'?'}</div>
      <div class="meta">Wave: ${(routing.wave_name||'?').slice(0,50)}</div>`;
  }
  if (pb) {
    html += `<div style="margin-top:8px">Step: <b>${pb.completed_step||'?'}</b></div>
      <div>Bridge Rounds: <b>${pb.bridge_rounds||0}</b></div>`;
    if (pb.deferred_packet_path) html += `<div class="meta">Deferred: ${pb.deferred_packet_path}</div>`;
  }
  html += '</div>';

  // Bridge History (full width)
  if (history.length) {
    html += '<div class="card full-width"><h2>Bridge Round History</h2>';
    history.forEach((r, i) => {
      const blk = r.blocking||[], nb = r.non_blocking||[];
      html += `<div class="round-row" onclick="document.getElementById('detail-${i}').style.display=document.getElementById('detail-${i}').style.display==='none'?'block':'none'">
        <span class="round-time">${r.time_str}</span>
        <span class="decision ${decClass(r.decision)}">${r.decision}</span>
        <span class="round-counts">
          <span class="blocking-count">${blk.length}B</span>
          <span class="nonblocking-count">${nb.length}NB</span>
        </span>
        <span class="pid">${r.job_id.split('-').slice(-1)[0].slice(0,8)}</span>
      </div>
      <div id="detail-${i}" style="display:${i===history.length-1?'block':'none'}; padding: 4px 0 8px 12px;">`;
      if (r.summary) html += `<div class="summary-text">${esc(r.summary)}</div>`;
      if (blk.length) {
        html += '<div class="section-label">Blocking</div>';
        blk.forEach(f => { html += renderFinding(f, 'blocking'); });
      }
      if (nb.length) {
        html += '<div class="section-label nb">Non-blocking</div>';
        nb.forEach(f => { html += renderFinding(f, 'nonblocking'); });
      }
      html += '</div>';
    });
    html += '</div>';
  }

  // Agents
  if (agents) {
    html += '<div class="card"><h2>SDK Agents</h2>';
    const running = agents.running_agents || [];
    const completed = agents.completed_agents || {};
    if (running.length) html += `<div>Running: ${running.join(', ')}</div>`;
    Object.entries(completed).forEach(([name, info]) => {
      const cls = info.passed ? 'agent-pass' : 'agent-fail';
      const mark = info.passed ? '✓' : '✗';
      html += `<div class="agent-row"><span class="${cls}">${mark}</span> ${name} <span class="verdict">${info.verdict}</span></div>`;
    });
    html += '</div>';
  }

  // DB Jobs
  if (jobs.length) {
    html += '<div class="card"><h2>Bridge DB</h2>';
    jobs.forEach(j => {
      const dec = j.terminal_decision || '';
      html += `<div class="db-row">
        <span class="job-id">${j.job_id}</span>
        ${j.status}
        ${dec ? `<span class="decision ${decClass(dec)}">${dec}</span>` : ''}
        R${j.current_round||'?'}
        <span class="meta">${j.reviewer_agent}</span>
      </div>`;
    });
    html += '</div>';
  }

  // Repo state
  html += `<div class="card"><h2>Repo State</h2>
    <div>Modified: ${gs.length} files | Deferred: ${dc} non-blocking</div>`;
  gs.slice(0,8).forEach(l => { html += `<div class="git-file">${esc(l)}</div>`; });
  if (gs.length > 8) html += `<div class="git-file">... +${gs.length-8} more</div>`;
  html += '</div>';

  html += '</div>';
  document.getElementById('dashboard').innerHTML = html;
  document.getElementById('clock').textContent = new Date().toLocaleTimeString();
}

function refresh() {
  fetch('/api/state').then(r=>r.json()).then(render).catch(e=>console.error(e));
}

function toggleAuto() {
  if (document.getElementById('autoRefresh').checked) {
    autoTimer = setInterval(refresh, 5000);
  } else {
    clearInterval(autoTimer);
  }
}

refresh();
autoTimer = setInterval(refresh, 5000);
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
        pass  # Suppress request logging


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
