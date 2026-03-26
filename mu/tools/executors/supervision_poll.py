#!/usr/bin/env python3
"""Read-only supervision poller for long-running executor/reviewer runs.

Polls process state, artifact mtime/size, and output growth on a
configurable interval. Surfaces stale_run and aggregation_hang conditions.

Bridge DB inspection is not built into this helper; use sqlite3 or the
connected SQLite MCP directly for bridge job/turn state.

Usage:
    # Poll a running Phase B executor by root PID
    python3 mu/tools/executors/supervision_poll.py --pid 12345

    # Poll with custom interval and stale threshold
    python3 mu/tools/executors/supervision_poll.py --pid 12345 --interval 15 --stale 120

    # Poll artifacts only (no PID required)
    python3 mu/tools/executors/supervision_poll.py --artifacts-only

    # One-shot snapshot (no loop)
    python3 mu/tools/executors/supervision_poll.py --pid 12345 --once

This is a read-only helper. It does not modify process state or artifacts.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent

try:
    from executor_common import artifact_size_mtime_ns, process_descendants
except ImportError:
    import importlib.util as _ilu
    _common_path = SCRIPT_DIR / "executor_common.py"
    _spec = _ilu.spec_from_file_location("executor_common", str(_common_path))
    _mod = _ilu.module_from_spec(_spec)
    assert _spec.loader is not None
    _spec.loader.exec_module(_mod)
    artifact_size_mtime_ns = _mod.artifact_size_mtime_ns
    process_descendants = _mod.process_descendants


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _process_tree(root_pid: int) -> dict[str, list[int]]:
    """Return root liveness and descendant PIDs."""
    result: dict[str, list[int]] = {"alive": [], "root_alive": False}
    try:
        os.kill(root_pid, 0)
        result["root_alive"] = True
    except (ProcessLookupError, PermissionError):
        return result

    result["alive"] = sorted(process_descendants(root_pid, cwd=REPO_ROOT))
    return result


def _artifact_snapshot(path: Path) -> dict[str, object]:
    """Return size and mtime for an artifact path."""
    size, mtime_ns = artifact_size_mtime_ns(path)
    if mtime_ns is None:
        return {"exists": False, "size": 0, "mtime": None}
    return {
        "exists": True,
        "size": size,
        "mtime": datetime.fromtimestamp(mtime_ns / 1_000_000_000, tz=timezone.utc).isoformat(),
    }


def _latest_artifact(paths: list[Path]) -> Path | None:
    """Return newest artifact by mtime, not lexicographic name."""
    if not paths:
        return None
    return max(paths, key=lambda path: (path.stat().st_mtime_ns, path.name))


def _resolve_repo_path(repo_root: Path, candidate: str | Path | None) -> Path | None:
    """Resolve a candidate path and reject anything outside repo_root."""
    if not candidate:
        return None
    raw = Path(candidate)
    full = raw if raw.is_absolute() else repo_root / raw
    try:
        resolved = full.resolve(strict=False)
        resolved.relative_to(repo_root.resolve())
    except (OSError, ValueError):
        return None
    return resolved


def _load_bound_review_artifacts(
    repo_root: Path,
    *,
    status_path: str | Path | None = None,
    stdout_log: str | Path | None = None,
    stderr_log: str | Path | None = None,
) -> dict[str, Path]:
    """Bind review artifacts to an explicit run instead of global newest-file heuristics."""
    bound: dict[str, Path] = {}
    explicit = {
        "status_path": status_path,
        "stdout_log": stdout_log,
        "stderr_log": stderr_log,
    }
    for key, value in explicit.items():
        resolved = _resolve_repo_path(repo_root, value)
        if resolved is not None:
            bound[key] = resolved

    if len(bound) == len(explicit):
        return bound

    state_path = repo_root / ".agent_bus" / "executors" / "phase_b_state.json"
    if not state_path.exists():
        return bound
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return bound

    state_candidates = {
        "status_path": state.get("agent_review_status_path"),
        "stdout_log": state.get("agent_review_stdout_path"),
        "stderr_log": state.get("agent_review_stderr_path"),
    }
    for key, value in state_candidates.items():
        if key in bound:
            continue
        resolved = _resolve_repo_path(repo_root, value)
        if resolved is not None:
            bound[key] = resolved
    return bound


def _artifact_fingerprints(artifacts: dict[str, dict[str, object]]) -> dict[str, tuple[object, object]]:
    """Track both size and mtime so same-size writes still count as progress."""
    return {
        name: (info.get("size", 0), info.get("mtime"))
        for name, info in artifacts.items()
        if isinstance(info, dict)
    }


def _poll_artifacts(
    repo_root: Path,
    review_artifacts: dict[str, Path] | None = None,
) -> dict[str, dict[str, object]]:
    """Snapshot key artifacts for long-run observability."""
    paths = {
        "findings": repo_root / ".agent_memory" / "findings.json",
        "phase_b_state": repo_root / ".agent_bus" / "executors" / "phase_b_state.json",
        "phase_b_handoff": repo_root / ".agent_bus" / "executors" / "phase_b_handoff.json",
        "pre_commit_receipt": repo_root / ".agent_bus" / "meta" / "pre_commit_receipt.json",
    }
    review_artifacts = review_artifacts or {}
    # Also check .scratch for recent stdout/stderr logs
    scratch = repo_root / ".scratch"
    if scratch.exists():
        latest_stdout = review_artifacts.get("stdout_log") or _latest_artifact(
            list(scratch.glob("phase_b_agent_review_*.stdout.log"))
        )
        latest_stderr = review_artifacts.get("stderr_log") or _latest_artifact(
            list(scratch.glob("phase_b_agent_review_*.stderr.log"))
        )
        latest_status = review_artifacts.get("status_path") or _latest_artifact(
            list(scratch.glob("phase_b_agent_review_*.status.json"))
        )
        if latest_stdout is not None:
            paths["latest_stdout_log"] = latest_stdout
        if latest_stderr is not None:
            paths["latest_stderr_log"] = latest_stderr
        if latest_status is not None:
            paths["latest_status"] = latest_status

    return {name: _artifact_snapshot(p) for name, p in paths.items()}


def _read_status_file(
    repo_root: Path,
    review_artifacts: dict[str, Path] | None = None,
) -> dict[str, object]:
    """Read the bound review status file, falling back to newest only when unbound."""
    review_artifacts = review_artifacts or {}
    status_path = review_artifacts.get("status_path")
    if status_path is None:
        scratch = repo_root / ".scratch"
        if not scratch.exists():
            return {}
        status_path = _latest_artifact(list(scratch.glob("phase_b_agent_review_*.status.json")))
    if status_path is None:
        return {}
    try:
        return json.loads(status_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def poll_snapshot(
    root_pid: int | None,
    repo_root: Path,
    *,
    review_artifacts: dict[str, Path] | None = None,
) -> dict[str, object]:
    """Produce a single supervision snapshot."""
    snapshot: dict[str, object] = {"timestamp": _timestamp()}

    if root_pid is not None:
        tree = _process_tree(root_pid)
        snapshot["process"] = {
            "root_pid": root_pid,
            "root_alive": tree["root_alive"],
            "child_pids": tree["alive"],
            "child_count": len(tree["alive"]),
        }

    snapshot["artifacts"] = _poll_artifacts(repo_root, review_artifacts)
    status = _read_status_file(repo_root, review_artifacts)
    if status:
        snapshot["review_status"] = {
            "phase_label": status.get("phase_label", ""),
            "running_agents": status.get("running_agents", []),
            "completed_agents": list((status.get("completed_agents") or {}).keys()),
            "last_progress_timestamp": status.get("last_progress_timestamp", ""),
        }

    return snapshot


def poll_loop(
    root_pid: int | None,
    repo_root: Path,
    *,
    interval: float = 30.0,
    stale_threshold: float = 300.0,
    once: bool = False,
    review_artifacts: dict[str, Path] | None = None,
) -> None:
    """Continuously poll and print supervision snapshots."""
    last_artifact_fingerprints: dict[str, tuple[object, object]] = {}
    last_review_status: dict[str, object] = {}
    last_child_pids: list[int] = []
    last_progress_at = time.monotonic()

    while True:
        if review_artifacts is None:
            snap = poll_snapshot(root_pid, repo_root)
        else:
            snap = poll_snapshot(root_pid, repo_root, review_artifacts=review_artifacts)

        # Current state signals
        artifacts = snap.get("artifacts", {})
        current_fingerprints = _artifact_fingerprints(artifacts)
        review_status_content = snap.get("review_status", {})
        proc = snap.get("process", {})
        child_pids = proc.get("child_pids", []) if isinstance(proc, dict) else []

        # Progress detection: three independent semantic signals
        # 1. Non-status artifact changed (findings, handoff, logs, etc.)
        non_status_artifact_changed = any(
            current_fingerprints.get(k) != last_artifact_fingerprints.get(k)
            for k in set(current_fingerprints) | set(last_artifact_fingerprints)
            if k != "latest_status"
        )
        # 2. Review status semantic content changed (phase, agents, etc.)
        #    A pure heartbeat rewrite (mtime changed, same semantic content)
        #    is NOT real progress — only semantic changes count.
        review_status_changed = (
            bool(review_status_content) and review_status_content != last_review_status
        )
        # 3. Child PID set changed (new/exited children = real progress)
        child_pids_changed = child_pids != last_child_pids

        output_changed = (
            non_status_artifact_changed
            or review_status_changed
            or child_pids_changed
        )

        if output_changed:
            last_progress_at = time.monotonic()
        idle_for = time.monotonic() - last_progress_at

        snap["supervision"] = {
            "output_changed": output_changed,
            "idle_seconds": round(idle_for, 1),
        }

        if idle_for >= stale_threshold:
            snap["supervision"]["warning"] = "stale_run"

        # Check aggregation hang: root alive, no children, idle
        if (isinstance(proc, dict)
                and proc.get("root_alive")
                and proc.get("child_count", 0) == 0
                and idle_for >= 120.0):
            snap["supervision"]["warning"] = "aggregation_hang"

        # Check process exited
        if isinstance(proc, dict) and root_pid is not None and not proc.get("root_alive"):
            snap["supervision"]["info"] = "process_exited"

        print(json.dumps(snap, indent=2, default=str), flush=True)
        last_artifact_fingerprints = current_fingerprints
        last_review_status = review_status_content
        last_child_pids = child_pids

        if once:
            break

        # Stop if process is gone
        if isinstance(proc, dict) and root_pid is not None and not proc.get("root_alive"):
            print(f"[supervision] Root process {root_pid} exited. Stopping poll.", flush=True)
            break

        time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only supervision poller for long-running executor runs",
    )
    parser.add_argument("--pid", type=int, help="Root PID to monitor")
    parser.add_argument("--interval", type=float, default=30.0,
                        help="Poll interval in seconds (default: 30)")
    parser.add_argument("--stale", type=float, default=300.0,
                        help="Stale-run threshold in seconds (default: 300)")
    parser.add_argument("--once", action="store_true",
                        help="Single snapshot, no loop")
    parser.add_argument("--artifacts-only", action="store_true",
                        help="Poll artifacts only (no PID required)")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT,
                        help="Repository root (default: auto-detected)")
    parser.add_argument("--status-path", type=str,
                        help="Bind supervision to a specific SDK status artifact")
    parser.add_argument("--stdout-log", type=str,
                        help="Bind supervision to a specific SDK stdout log")
    parser.add_argument("--stderr-log", type=str,
                        help="Bind supervision to a specific SDK stderr log")
    args = parser.parse_args()

    if not args.pid and not args.artifacts_only:
        parser.error("--pid or --artifacts-only required")

    review_artifacts = _load_bound_review_artifacts(
        args.repo_root,
        status_path=args.status_path,
        stdout_log=args.stdout_log,
        stderr_log=args.stderr_log,
    )

    poll_loop(
        args.pid if not args.artifacts_only else None,
        args.repo_root,
        interval=args.interval,
        stale_threshold=args.stale,
        once=args.once,
        review_artifacts=review_artifacts,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
