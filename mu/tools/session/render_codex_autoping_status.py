#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


def _codex_home() -> Path:
    override = os.environ.get("RCX_CODEX_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".codex"


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def _tail_lines(path: Path, limit: int) -> list[str]:
    text = _read_text(path)
    if not text:
        return []
    return text.splitlines()[-limit:]


def _stringify(value: object) -> str:
    if value in (None, ""):
        return "-"
    return str(value)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render WorkingRCX autoping pane status")
    parser.add_argument("--thread-id", required=True)
    parser.add_argument("--log-tail-lines", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    codex_home = _codex_home()
    thread_slug = _slug(args.thread_id)
    state_path = codex_home / "state" / f"rcx_autoping_{thread_slug}.json"
    summary_path = codex_home / "state" / f"rcx_autoping_{thread_slug}_summary.txt"
    runner_log = codex_home / "log" / "autoping" / f"rcx_autoping_{thread_slug}.runner.log"

    state = _read_json(state_path)
    summary = _read_text(summary_path) or "(no completed ping summary yet)"
    tail = _tail_lines(runner_log, args.log_tail_lines)

    print("AUTO-PING")
    print(f"thread_id: {_stringify(args.thread_id)}")
    print(f"watcher_pid: {_stringify(state.get('watcher_pid'))}")
    print(f"status: {_stringify(state.get('status'))}")
    print(f"last_dispatched_at: {_stringify(state.get('last_dispatched_at'))}")
    print(f"last_completed_at: {_stringify(state.get('last_completed_at'))}")
    print(f"last_exit_code: {_stringify(state.get('last_exit_code'))}")
    print(f"repo_root: {_stringify(state.get('repo_root'))}")
    print(f"bus_dir: {_stringify(state.get('bus_dir'))}")
    print(f"active_pid: {_stringify(state.get('active_pid'))}")
    print(f"active_log: {_stringify(state.get('active_log'))}")
    print(f"state_path: {state_path}")
    print(f"summary_path: {summary_path}")
    print("display_message: tmux bottom status line flash; pane below is the durable surface")
    print()
    print("Last summary:")
    print(summary)
    print()
    print("Recent runner log:")
    if tail:
        for line in tail:
            print(line)
    else:
        print("(runner log empty)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
