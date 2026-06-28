#!/usr/bin/env python3
"""Switch the active operator orchestrator without changing pipeline roles.

This command owns only the operator-facing orchestration surface:

* bus-local ``orchestrator_mode.json`` used by the pager as the effective route;
* committed ``pipeline_agent_pager.route`` narrowed to the single selected
  orchestrator (the lowest-precedence fallback resolved below
  ``orchestrator_mode.json``, so a checkout without the bus-local state file no
  longer falls through to the ``"both"`` fan-out);
* stale pending pager targets for the opposite orchestrator;
* selected Codex/Claude autoping restart and opposite autoping stop;
* tmux monitor rebuild for the selected root/bus/session.

It deliberately does not call ``set_roles.py`` and does not write
``role_agents``, ``backends``, or ``bridge_reviewers``. Implementer/reviewer
selection remains the separate role switch.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import inspect
import json
import os
import re
import shlex
import signal
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
EXECUTORS_DIR = SCRIPT_DIR.parent / "executors"
OBSERVABILITY_TOOLS_DIR = SCRIPT_DIR.parent / "observability"
if str(EXECUTORS_DIR) not in sys.path:
    sys.path.insert(0, str(EXECUTORS_DIR))
if str(OBSERVABILITY_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(OBSERVABILITY_TOOLS_DIR))

from executor_common import (  # noqa: E402
    DEFAULT_EXECUTOR_CONFIG,
    agent_bus_relpath,
    bridge_agent_display_name,
    configured_role_agents,
    load_executor_config,
    normalize_agent_bus_dir,
    resolve_agent_bus_dir,
)
from pipeline_agent_pager import (  # noqa: E402
    _ACTIVE_BUS_DIR as PAGER_ACTIVE_BUS_DIR,
    _PagerLock as PagerLock,
    _append_skip_receipt as pager_append_skip_receipt,
    _load_state as pager_load_state,
    _refresh_pending_targets as pager_refresh_pending_targets,
    _save_state as pager_save_state,
    _resolve_route as pager_resolve_route,
)


MODE_CHOICES = ("codex", "claude")
STATE_VERSION = 1
ORCHESTRATOR_STATE_NAME = "orchestrator_mode.json"
PAGER_STATE_NAME = "pipeline_agent_pager_state.json"
PAGER_SKIP_REASON_PREFIX = "orchestrator_mode_switched_to_"
SESSION_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
BUS_MARKER_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(?P<bus>\.agent_bus(?:-[A-Za-z0-9][A-Za-z0-9_-]*)?)"
    r"(?=$|[/'\"\s:=])"
)


class OrchestratorModeError(RuntimeError):
    """Raised when the orchestrator switch cannot complete safely."""


@dataclass(frozen=True)
class CommandOutcome:
    args: list[str]
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class AutopingRecord:
    kind: str
    path: Path
    watcher_pid: int | None
    active_pid: int | None
    repo_root: str
    bus_dir: str
    label: str

    @property
    def pids(self) -> tuple[int, ...]:
        values: list[int] = []
        for pid in (self.watcher_pid, self.active_pid):
            if pid is not None and pid > 1 and pid not in values:
                values.append(pid)
        return tuple(values)


@dataclass(frozen=True)
class LiveAutopingProcess:
    kind: str
    pid: int
    label: str
    process_type: str
    command: str


@dataclass(frozen=True)
class LiveBridgeWorker:
    pid: int
    provider: str
    role: str
    command: str


@dataclass
class SwitchReport:
    mode: str
    repo_root: Path
    bus_dir: str
    tmux_session: str
    provider: dict[str, Any]
    role_agents: dict[str, dict[str, str]]
    config_changed: bool = False
    state_changed: bool = False
    skipped_pager_targets: list[dict[str, str]] = field(default_factory=list)
    stopped_autoping: list[str] = field(default_factory=list)
    commands: list[list[str]] = field(default_factory=list)
    command_results: list[CommandOutcome] = field(default_factory=list)
    verify_failures: list[str] = field(default_factory=list)
    verify_warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.verify_failures


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _repo_root(override: str | None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def _config_path(repo_root: Path) -> Path:
    return repo_root / "mu" / "tools" / "executors" / "executor_config.json"


def _observability_dir(repo_root: Path, bus_dir: str) -> Path:
    return repo_root / bus_dir / "observability"


def _orchestrator_state_path(repo_root: Path, bus_dir: str) -> Path:
    return _observability_dir(repo_root, bus_dir) / ORCHESTRATOR_STATE_NAME


def _pager_state_path(repo_root: Path, bus_dir: str) -> Path:
    return _observability_dir(repo_root, bus_dir) / PAGER_STATE_NAME


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        preserve_mode: int | None = stat.S_IMODE(os.stat(path).st_mode)
    except FileNotFoundError:
        preserve_mode = None
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if preserve_mode is None:
            current_umask = os.umask(0)
            os.umask(current_umask)
            preserve_mode = 0o666 & ~current_umask
        os.chmod(tmp_path, preserve_mode)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, payload: Any) -> None:
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _validate_tmux_session(value: str) -> str:
    clean = str(value or "").strip()
    if not SESSION_NAME_RE.fullmatch(clean):
        raise OrchestratorModeError(f"invalid --tmux-session: {value!r}")
    return clean


def _validate_mode_in_registry(repo_root: Path, mode: str) -> dict[str, Any]:
    config = load_executor_config(repo_root)
    defaults = config.get("bridge_agent_defaults")
    if not isinstance(defaults, dict):
        defaults = DEFAULT_EXECUTOR_CONFIG.get("bridge_agent_defaults", {})
    provider = defaults.get(mode)
    if not isinstance(provider, dict):
        raise OrchestratorModeError(
            f"orchestrator mode {mode!r} is missing from bridge_agent_defaults"
        )
    merged = dict(provider)
    merged.setdefault("display_name", bridge_agent_display_name(repo_root, mode))
    return merged


def _provider_summary(provider: dict[str, Any]) -> str:
    parts = [str(provider.get("display_name") or "").strip()]
    for key in ("model", "effort", "reasoning_effort"):
        value = str(provider.get(key) or "").strip()
        if value:
            parts.append(f"{key}={value}")
    return " ".join(part for part in parts if part)


def _load_raw_executor_config(repo_root: Path) -> dict[str, Any]:
    path = _config_path(repo_root)
    if not path.exists():
        raise OrchestratorModeError(f"executor_config.json not found: {path}")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise OrchestratorModeError("executor_config.json must be a JSON object")
    return loaded


def _set_pager_route(
    repo_root: Path,
    mode: str,
    *,
    dry_run: bool,
) -> bool:
    """Narrow the committed ``pipeline_agent_pager.route`` to the single orchestrator.

    The pager resolves its effective route (``pipeline_agent_pager._resolve_route``)
    with precedence: explicit arg -> env override -> bus-local
    ``orchestrator_mode.json`` -> committed ``executor_config.json`` route. The
    orchestrator switch already writes ``orchestrator_mode.json`` (``mode=X``), which
    narrows the LIVE bus to X. But a checkout or process WITHOUT that bus-local state
    file falls through to the committed route, which ships as ``"both"`` and pages
    BOTH orchestrators even when X is the sole selected one. Set the committed route to
    the single selected orchestrator X so ``--mode X`` yields
    ``_requested_targets(route) == [X]`` on every path, while the higher-precedence
    ``orchestrator_mode.json`` resolution above is preserved unchanged (this only
    rewrites the lowest-precedence committed fallback).

    Returns whether the committed route would change. The write is skipped under
    ``dry_run`` (parity with :func:`_write_orchestrator_state`), and an in-place edit
    of only ``pager["route"]`` preserves the file's existing key order. ``mode`` is
    pre-validated to ``MODE_CHOICES`` by :func:`apply_orchestrator_mode`, and both
    members are valid single-provider pager routes.
    """
    config = _load_raw_executor_config(repo_root)
    pager = config.setdefault("pipeline_agent_pager", {})
    if not isinstance(pager, dict):
        raise OrchestratorModeError("pipeline_agent_pager must be a JSON object")
    if pager.get("route") == mode:
        return False
    if not dry_run:
        pager["route"] = mode
        _atomic_write_text(_config_path(repo_root), json.dumps(config, indent=2) + "\n")
    return True


def _role_agent_visibility(repo_root: Path, bus_dir: str) -> dict[str, dict[str, str]]:
    try:
        return configured_role_agents(repo_root, bus_dir=bus_dir)
    except Exception:
        return {}


def _build_orchestrator_state(
    *,
    repo_root: Path,
    bus_dir: str,
    tmux_session: str,
    mode: str,
    provider: dict[str, Any],
    role_agents: dict[str, dict[str, str]],
) -> dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "mode": mode,
        "repo_root": str(repo_root),
        "bus_dir": bus_dir,
        "tmux_session": tmux_session,
        "provider": provider,
        "role_agents": role_agents,
        "updated_at": _utcnow(),
    }


def _write_orchestrator_state(
    *,
    repo_root: Path,
    bus_dir: str,
    tmux_session: str,
    mode: str,
    provider: dict[str, Any],
    role_agents: dict[str, dict[str, str]],
    dry_run: bool,
) -> bool:
    state_path = _orchestrator_state_path(repo_root, bus_dir)
    prior = _read_json(state_path, {})
    next_state = _build_orchestrator_state(
        repo_root=repo_root,
        bus_dir=bus_dir,
        tmux_session=tmux_session,
        mode=mode,
        provider=provider,
        role_agents=role_agents,
    )
    comparable_prior = dict(prior) if isinstance(prior, dict) else {}
    comparable_prior.pop("updated_at", None)
    comparable_next = dict(next_state)
    comparable_next.pop("updated_at", None)
    changed = comparable_prior != comparable_next
    if changed and not dry_run:
        _write_json(state_path, next_state)
    return changed


def _list_targets(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    targets: list[str] = []
    for item in value:
        target = str(item or "").strip()
        if target and target not in targets:
            targets.append(target)
    return targets


def _pending_targets(entry: dict[str, Any]) -> list[str]:
    pending = _list_targets(entry.get("pending_targets"))
    if pending:
        return pending
    delivered = entry.get("delivered_targets")
    skipped = entry.get("skipped_targets")
    delivered_names = set(delivered) if isinstance(delivered, dict) else set()
    skipped_names = set(skipped) if isinstance(skipped, dict) else set()
    return [
        target
        for target in _list_targets(entry.get("requested_targets"))
        if target not in delivered_names and target not in skipped_names
    ]


@contextmanager
def _pager_locked_bus(repo_root: Path, bus_dir: str) -> Iterable[None]:
    token = PAGER_ACTIVE_BUS_DIR.set(agent_bus_relpath(bus_dir))
    try:
        with PagerLock(repo_root):
            yield
    finally:
        PAGER_ACTIVE_BUS_DIR.reset(token)


def stale_opposite_pager_targets(
    repo_root: Path,
    bus_dir: str,
    mode: str,
) -> list[dict[str, str]]:
    opposite = "claude" if mode == "codex" else "codex"
    state = _read_json(_pager_state_path(repo_root, bus_dir), {})
    events = state.get("events") if isinstance(state, dict) else None
    if not isinstance(events, dict):
        return []
    stale: list[dict[str, str]] = []
    for event_id, entry in events.items():
        if not isinstance(entry, dict):
            continue
        if opposite not in _pending_targets(entry):
            continue
        stale.append({"event_id": str(event_id), "target": opposite})
    return stale


def terminally_skip_opposite_pager_targets(
    repo_root: Path,
    bus_dir: str,
    mode: str,
    *,
    dry_run: bool,
) -> list[dict[str, str]]:
    opposite = "claude" if mode == "codex" else "codex"
    reason = f"{PAGER_SKIP_REASON_PREFIX}{mode}"
    if dry_run:
        state = _read_json(_pager_state_path(repo_root, bus_dir), {})
        return _terminally_skip_opposite_pager_targets_in_state(
            state,
            opposite=opposite,
            reason=reason,
        )[0]

    with _pager_locked_bus(repo_root, bus_dir):
        state = pager_load_state(repo_root)
        skipped_records, skip_receipts = _terminally_skip_opposite_pager_targets_in_state(
            state,
            opposite=opposite,
            reason=reason,
        )
        if skipped_records:
            pager_save_state(repo_root, state)
            for receipt in skip_receipts:
                pager_append_skip_receipt(
                    repo_root,
                    event_id=receipt["event_id"],
                    target=receipt["target"],
                    skip_reason=receipt["skip_reason"],
                )
        return skipped_records


def _terminally_skip_opposite_pager_targets_in_state(
    state: Any,
    *,
    opposite: str,
    reason: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    events = state.get("events") if isinstance(state, dict) else None
    if not isinstance(events, dict):
        return [], []

    skipped_records: list[dict[str, str]] = []
    skip_receipts: list[dict[str, str]] = []
    for event_id, entry in events.items():
        if not isinstance(entry, dict):
            continue
        if opposite not in _pending_targets(entry):
            continue
        skipped_targets = entry.setdefault("skipped_targets", {})
        if not isinstance(skipped_targets, dict):
            skipped_targets = {}
            entry["skipped_targets"] = skipped_targets
        already_skipped = opposite in skipped_targets
        if not already_skipped:
            skipped_targets[opposite] = {
                "skip_reason": reason,
                "skipped_at": _utcnow(),
            }
            skip_receipts.append(
                {
                    "event_id": str(entry.get("event_id") or event_id),
                    "target": opposite,
                    "skip_reason": reason,
                    "recorded_at": _utcnow(),
                }
            )
        pager_refresh_pending_targets(entry)
        skipped_records.append(
            {
                "event_id": str(entry.get("event_id") or event_id),
                "target": opposite,
                "skip_reason": reason,
            }
        )

    return skipped_records, skip_receipts


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def _codex_home() -> Path:
    override = os.environ.get("RCX_CODEX_HOME") or os.environ.get("CODEX_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".codex"


def _pid_from_payload(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    try:
        pid = int(value)
    except (TypeError, ValueError):
        return None
    return pid if pid > 1 else None


def _same_root(value: Any, repo_root: Path) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        return Path(value).expanduser().resolve() == repo_root.resolve()
    except OSError:
        return False


def collect_autoping_records(
    kind: str,
    *,
    repo_root: Path,
    bus_dir: str,
    codex_home: Path | None = None,
) -> list[AutopingRecord]:
    records: list[AutopingRecord] = []
    if kind == "codex":
        state_dir = (codex_home or _codex_home()) / "state"
        paths = sorted(state_dir.glob("rcx_autoping_*.json")) if state_dir.is_dir() else []
    elif kind == "claude":
        obs_dir = _observability_dir(repo_root, bus_dir)
        paths = sorted(obs_dir.glob("claude_autoping_*.json")) if obs_dir.is_dir() else []
    else:
        raise OrchestratorModeError(f"unsupported autoping kind: {kind!r}")

    for path in paths:
        payload = _read_json(path, {})
        if not isinstance(payload, dict):
            continue
        payload_bus = str(payload.get("bus_dir") or "").strip()
        if payload_bus and payload_bus != bus_dir:
            continue
        if kind == "codex":
            bridge_state = payload.get("bridge_state")
            bridge_root = bridge_state.get("wave_root") if isinstance(bridge_state, dict) else None
            if not (_same_root(payload.get("repo_root"), repo_root) or _same_root(payload.get("wave_root"), repo_root) or _same_root(bridge_root, repo_root)):
                continue
            label = str(payload.get("thread_id") or path.stem)
        else:
            if not _same_root(payload.get("repo_root"), repo_root):
                continue
            label = str(payload.get("session_id") or path.stem)
        records.append(
            AutopingRecord(
                kind=kind,
                path=path,
                watcher_pid=_pid_from_payload(payload, "watcher_pid"),
                active_pid=_pid_from_payload(payload, "active_pid"),
                repo_root=str(repo_root),
                bus_dir=bus_dir,
                label=label,
            )
        )
    return records


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _kill_pid(pid: int) -> None:
    os.kill(pid, signal.SIGTERM)


def _pid_command_line(pid: int) -> str:
    proc_cmdline = Path(f"/proc/{pid}/cmdline")
    try:
        if proc_cmdline.exists():
            raw = proc_cmdline.read_bytes()
            command = " ".join(
                part.decode(errors="replace")
                for part in raw.split(b"\0")
                if part
            ).strip()
            if command:
                return command
    except OSError:
        pass
    try:
        proc = subprocess.run(
            ["ps", "-ww", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _split_command(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def _flag_value(tokens: list[str], flag: str) -> str | None:
    prefix = f"{flag}="
    for index, token in enumerate(tokens):
        if token == flag and index + 1 < len(tokens):
            return tokens[index + 1]
        if token.startswith(prefix):
            return token.split("=", 1)[1]
    return None


def _token_matches_path(token: str, expected: Path) -> bool:
    if not token:
        return False
    try:
        if Path(token).expanduser().resolve() == expected.expanduser().resolve():
            return True
    except OSError:
        pass
    return Path(token).name == expected.name


def _command_has_script(tokens: list[str], script: Path) -> bool:
    return any(_token_matches_path(token, script) for token in tokens)


def _flag_matches_path(tokens: list[str], flag: str, expected: Path) -> bool:
    value = _flag_value(tokens, flag)
    if value is None:
        return False
    try:
        return Path(value).expanduser().resolve() == expected.expanduser().resolve()
    except OSError:
        return Path(value).expanduser().absolute() == expected.expanduser().absolute()


def _flag_matches_text(tokens: list[str], flag: str, expected: str) -> bool:
    return _flag_value(tokens, flag) == expected


def _watch_script_for_kind(kind: str, repo_root: Path) -> Path:
    if kind == "codex":
        return _existing_script(
            repo_root,
            (
                "mu/tools/session/codex_autoping_watch.py",
                "tools/session/codex_autoping_watch.py",
            ),
        )
    if kind == "claude":
        return _existing_script(
            repo_root,
            (
                "mu/tools/session/claude_autoping_watch.py",
                "tools/session/claude_autoping_watch.py",
            ),
        )
    raise OrchestratorModeError(f"unsupported autoping kind: {kind!r}")


def _watch_script_for_record(record: AutopingRecord) -> Path:
    return _watch_script_for_kind(record.kind, Path(record.repo_root))


def _watcher_command_matches_record(record: AutopingRecord, command: str) -> bool:
    tokens = _split_command(command)
    if not _command_has_script(tokens, _watch_script_for_record(record)):
        return False
    if not _flag_matches_path(tokens, "--repo-root", Path(record.repo_root)):
        return False
    if not _flag_matches_text(tokens, "--bus-dir", record.bus_dir):
        return False
    if record.kind == "codex":
        return _flag_matches_text(tokens, "--thread-id", record.label)
    if record.kind == "claude":
        return _flag_matches_text(tokens, "--session-id", record.label)
    return False


def _active_ping_command_matches_record(record: AutopingRecord, command: str) -> bool:
    lowered = command.lower()
    if record.kind == "codex":
        return (
            "codex" in lowered
            and "exec" in lowered
            and "autonomous workingrcx pipeline watchdog tick." in lowered
            and record.label in command
            and f"Active bus root: {record.bus_dir}" in command
        )
    if record.kind == "claude":
        tokens = _split_command(command)
        return (
            any(Path(token).name == "claude" for token in tokens)
            and _flag_matches_text(tokens, "--resume", record.label)
            and "workingrcx dedicated claude monitor keepalive tick." in lowered
            and f"Active bus root: {record.bus_dir}" in command
        )
    return False


def _autoping_pid_matches_record(
    record: AutopingRecord,
    pid: int,
    *,
    command_reader: Callable[[int], str] = _pid_command_line,
) -> bool:
    command = command_reader(pid)
    if not command:
        return False
    return _watcher_command_matches_record(record, command) or _active_ping_command_matches_record(
        record, command
    )


def _autoping_watcher_pid_matches_record(
    record: AutopingRecord,
    *,
    pid_exists: Callable[[int], bool] = _pid_exists,
    command_reader: Callable[[int], str] = _pid_command_line,
) -> int | None:
    pid = record.watcher_pid
    if pid is None or not pid_exists(pid):
        return None
    command = command_reader(pid)
    if not command or not _watcher_command_matches_record(record, command):
        return None
    return pid


def _read_process_table() -> tuple[dict[int, str], dict[int, int]]:
    try:
        proc = subprocess.run(
            ["ps", "-ww", "-Ao", "pid=,ppid=,command="],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return {}, {}
    if proc.returncode not in (0, 1) and not proc.stdout:
        return {}, {}
    commands: dict[int, str] = {}
    ppid: dict[int, int] = {}
    for raw in proc.stdout.splitlines():
        parts = raw.strip().split(None, 2)
        if len(parts) != 3:
            continue
        try:
            pid = int(parts[0])
            parent = int(parts[1])
        except ValueError:
            continue
        commands[pid] = parts[2]
        ppid[pid] = parent
    return commands, ppid


def _watcher_label_from_command(
    *,
    kind: str,
    command: str,
    repo_root: Path,
    bus_dir: str,
) -> str | None:
    tokens = _split_command(command)
    if not _command_has_script(tokens, _watch_script_for_kind(kind, repo_root)):
        return None
    if not _flag_matches_path(tokens, "--repo-root", repo_root):
        return None
    if not _flag_matches_text(tokens, "--bus-dir", bus_dir):
        return None
    label_flag = "--thread-id" if kind == "codex" else "--session-id"
    return _flag_value(tokens, label_flag) or "unknown"


def _codex_active_label(tokens: list[str]) -> str:
    if "resume" not in tokens:
        return "fresh-exec"
    try:
        json_index = tokens.index("--json")
    except ValueError:
        return "unknown"
    if json_index + 1 >= len(tokens):
        return "unknown"
    return tokens[json_index + 1] or "unknown"


def _active_label_from_command(kind: str, command: str, bus_dir: str) -> str | None:
    lowered = command.lower()
    if f"Active bus root: {bus_dir}" not in command:
        return None
    tokens = _split_command(command)
    if kind == "codex":
        if (
            "codex" not in lowered
            or "exec" not in lowered
            or "autonomous workingrcx pipeline watchdog tick." not in lowered
        ):
            return None
        return _codex_active_label(tokens)
    if kind == "claude":
        if (
            not any(Path(token).name == "claude" for token in tokens)
            or "workingrcx dedicated claude monitor keepalive tick." not in lowered
        ):
            return None
        return _flag_value(tokens, "--resume") or "unknown"
    raise OrchestratorModeError(f"unsupported autoping kind: {kind!r}")


def scan_live_autoping_processes(
    kind: str,
    *,
    repo_root: Path,
    bus_dir: str,
) -> list[LiveAutopingProcess]:
    """Find autoping processes from process truth, independent of state files."""
    if kind not in MODE_CHOICES:
        raise OrchestratorModeError(f"unsupported autoping kind: {kind!r}")
    commands, ppid = _read_process_table()
    processes: list[LiveAutopingProcess] = []
    cwd_cache: dict[int, str | None] = {}
    for pid, command in commands.items():
        watcher_label = _watcher_label_from_command(
            kind=kind,
            command=command,
            repo_root=repo_root,
            bus_dir=bus_dir,
        )
        if watcher_label is not None:
            processes.append(
                LiveAutopingProcess(
                    kind=kind,
                    pid=pid,
                    label=watcher_label,
                    process_type="watcher",
                    command=command,
                )
            )
            continue

        active_label = _active_label_from_command(kind, command, bus_dir)
        if active_label is None:
            continue
        if not _process_chain_matches_repo(
            pid=pid,
            repo_root=repo_root,
            ppid=ppid,
            commands=commands,
            cwd_cache=cwd_cache,
        ):
            continue
        processes.append(
            LiveAutopingProcess(
                kind=kind,
                pid=pid,
                label=active_label,
                process_type="active_ping",
                command=command,
            )
        )
    return processes


def stop_autoping_records(
    records: Iterable[AutopingRecord],
    *,
    dry_run: bool,
    pid_exists: Callable[[int], bool] = _pid_exists,
    killer: Callable[[int], None] = _kill_pid,
    command_reader: Callable[[int], str] = _pid_command_line,
) -> list[str]:
    stopped: list[str] = []
    current_pid = os.getpid()
    for record in records:
        for pid in record.pids:
            if pid == current_pid or not pid_exists(pid):
                continue
            if not _autoping_pid_matches_record(
                record,
                pid,
                command_reader=command_reader,
            ):
                continue
            stopped.append(f"{record.kind}:{record.label}:pid={pid}")
            if not dry_run:
                killer(pid)
    return stopped


def stop_wrong_autoping_processes(
    records: Iterable[AutopingRecord],
    live_processes: Iterable[LiveAutopingProcess],
    *,
    dry_run: bool,
    pid_exists: Callable[[int], bool] = _pid_exists,
    killer: Callable[[int], None] = _kill_pid,
    command_reader: Callable[[int], str] = _pid_command_line,
) -> list[str]:
    candidates: list[tuple[str, str, int]] = []
    current_pid = os.getpid()
    for record in records:
        for pid in record.pids:
            if pid == current_pid or not pid_exists(pid):
                continue
            if not _autoping_pid_matches_record(
                record,
                pid,
                command_reader=command_reader,
            ):
                continue
            candidates.append((record.kind, record.label, pid))
    for process in live_processes:
        if process.pid == current_pid or not pid_exists(process.pid):
            continue
        candidates.append((process.kind, process.label, process.pid))

    stopped: list[str] = []
    stopped_pids: set[int] = set()
    for kind, label, pid in candidates:
        if pid in stopped_pids:
            continue
        stopped_pids.add(pid)
        stopped.append(f"{kind}:{label}:pid={pid}")
        if not dry_run:
            killer(pid)
    return stopped


def _selected_autoping_live(
    mode: str,
    *,
    repo_root: Path,
    bus_dir: str,
    pid_exists: Callable[[int], bool] = _pid_exists,
    command_reader: Callable[[int], str] = _pid_command_line,
) -> bool:
    for record in collect_autoping_records(mode, repo_root=repo_root, bus_dir=bus_dir):
        if (
            _autoping_watcher_pid_matches_record(
                record,
                pid_exists=pid_exists,
                command_reader=command_reader,
            )
            is not None
        ):
            return True
    return False


def _default_autoping_wait_seconds(runner: Callable[..., Any]) -> float:
    override = os.environ.get("RCX_ORCHESTRATOR_SWITCH_AUTOPING_WAIT_S")
    if override is not None:
        try:
            return max(float(override), 0.0)
        except ValueError:
            return 0.0
    return 5.0 if runner is subprocess.run else 0.0


def _wait_for_selected_autoping(
    mode: str,
    *,
    repo_root: Path,
    bus_dir: str,
    timeout_s: float,
    pid_exists: Callable[[int], bool] = _pid_exists,
    command_reader: Callable[[int], str] = _pid_command_line,
) -> None:
    if timeout_s <= 0:
        return
    deadline = time.monotonic() + timeout_s
    while True:
        if _selected_autoping_live(
            mode,
            repo_root=repo_root,
            bus_dir=bus_dir,
            pid_exists=pid_exists,
            command_reader=command_reader,
        ):
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(0.2, remaining))


def _existing_script(repo_root: Path, rel_options: tuple[str, ...]) -> Path:
    for rel in rel_options:
        candidate = repo_root / rel
        if candidate.exists():
            return candidate
    return repo_root / rel_options[0]


def build_autoping_command(
    mode: str,
    *,
    repo_root: Path,
    bus_dir: str,
    tmux_session: str,
    codex_thread_id: str = "",
    claude_session_id: str = "",
) -> list[str]:
    if mode == "codex":
        launcher = _existing_script(
            repo_root,
            (
                "mu/tools/session/ensure_codex_autoping.sh",
                "tools/session/ensure_codex_autoping.sh",
            ),
        )
        cmd = [
            "bash",
            str(launcher),
            "--repo",
            str(repo_root),
            "--bus-dir",
            bus_dir,
            "--tmux-session",
            tmux_session,
            "--tmux-pane",
            f"{tmux_session}:1.3",
            "--force-restart",
        ]
        thread_id = codex_thread_id or os.environ.get("CODEX_THREAD_ID", "")
        if thread_id:
            cmd.extend(["--thread-id", thread_id])
        return cmd
    if mode == "claude":
        launcher = _existing_script(
            repo_root,
            (
                "mu/tools/session/ensure_claude_autoping.sh",
                "tools/session/ensure_claude_autoping.sh",
            ),
        )
        cmd = [
            "bash",
            str(launcher),
            "--repo",
            str(repo_root),
            "--bus-dir",
            bus_dir,
            "--force-restart",
        ]
        if claude_session_id:
            cmd.extend(["--session-id", claude_session_id])
        return cmd
    raise OrchestratorModeError(f"unsupported mode: {mode!r}")


def build_monitor_commands(
    *,
    repo_root: Path,
    bus_dir: str,
    tmux_session: str,
    mode: str,
) -> list[list[str]]:
    monitor = _existing_script(
        repo_root,
        (
            "mu/tools/observability/pipeline_monitor.sh",
            "tools/observability/pipeline_monitor.sh",
        ),
    )
    base = [
        "bash",
        str(monitor),
        "--bus-dir",
        bus_dir,
        "--tmux-session",
        tmux_session,
        "--orchestrator-mode",
        mode,
    ]
    return [base + ["stop"], base + ["start", "--detach"]]


def _run_command(
    cmd: list[str],
    *,
    cwd: Path,
    runner: Callable[..., Any] = subprocess.run,
) -> CommandOutcome:
    result = runner(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return CommandOutcome(
        args=list(cmd),
        returncode=int(getattr(result, "returncode", 0)),
        stdout=str(getattr(result, "stdout", "") or ""),
        stderr=str(getattr(result, "stderr", "") or ""),
    )


def _command_failed(outcome: CommandOutcome) -> bool:
    # monitor stop is idempotent and returns success in the real script for no session.
    return outcome.returncode != 0


def _process_provider(command: str) -> str | None:
    lowered = command.lower()
    if _is_control_plane_resume_command(command):
        return None
    if "codex exec" in lowered and "codex.app" not in lowered and "codex helper" not in lowered:
        return "codex"
    if "claude" in lowered and "--print" in lowered:
        return "claude"
    return None


def _is_control_plane_resume_command(command: str) -> bool:
    lowered = command.lower()
    return any(
        marker in lowered
        for marker in (
            "autonomous workingrcx pipeline watchdog tick.",
            "workingrcx pipeline pager wakeup.",
            "workingrcx dedicated claude monitor keepalive tick.",
        )
    )


def _ancestor_role(pid: int, ppid: dict[int, int], commands: dict[int, str]) -> str:
    current = pid
    for _ in range(8):
        parent = ppid.get(current)
        if parent is None or parent == 1:
            return "unknown"
        cmd = commands.get(parent, "")
        if re.search(r"bridge_supervisor\.py.*(^|[ ]+)review([ ]+|$)|meta_bridge_supervisor", cmd):
            return "review"
        if re.search(r"phase_b_executor\.py|phase_a_executor\.py|commit_executor\.py", cmd):
            return "implement"
        current = parent
    return "unknown"


def _pid_cwd(pid: int) -> str | None:
    proc_cwd = Path("/proc") / str(pid) / "cwd"
    try:
        value = os.readlink(proc_cwd)
        if value:
            return value
    except OSError:
        pass
    try:
        proc = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for raw in proc.stdout.splitlines():
        if raw.startswith("n") and raw[1:].strip():
            return raw[1:].strip()
    return None


def _normalize_path_text(value: str | Path) -> str:
    try:
        return str(Path(value).expanduser().resolve(strict=False))
    except (OSError, RuntimeError):
        return str(Path(value).expanduser().absolute())


def _process_chain(pid: int, ppid: dict[int, int]) -> list[int]:
    chain = [pid]
    current = pid
    for _ in range(8):
        parent = ppid.get(current)
        if parent is None or parent == 1:
            break
        chain.append(parent)
        current = parent
    return chain


def _process_chain_matches_repo(
    *,
    pid: int,
    repo_root: Path,
    ppid: dict[int, int],
    commands: dict[int, str],
    cwd_cache: dict[int, str | None],
) -> bool:
    root_text = str(repo_root)
    root_normalized = _normalize_path_text(repo_root)
    chain = _process_chain(pid, ppid)
    if any(root_text in commands.get(item, "") for item in chain):
        return True
    for item in chain:
        if item not in cwd_cache:
            cwd_cache[item] = _pid_cwd(item)
        cwd = cwd_cache[item]
        if cwd and _normalize_path_text(cwd) == root_normalized:
            return True
    return False


def _normalize_bus_text(value: str) -> str:
    try:
        return normalize_agent_bus_dir(value).as_posix()
    except Exception:
        return str(value)


def _bus_markers_from_command(command: str) -> list[str]:
    markers: list[str] = []
    tokens = _split_command(command)
    flag_value = _flag_value(tokens, "--bus-dir")
    if flag_value:
        markers.append(_normalize_bus_text(flag_value))
    for match in BUS_MARKER_RE.finditer(command):
        marker = _normalize_bus_text(match.group("bus"))
        if marker not in markers:
            markers.append(marker)
    return markers


def _process_chain_matches_bus(
    *,
    pid: int,
    bus_dir: str,
    ppid: dict[int, int],
    commands: dict[int, str],
) -> bool:
    expected = _normalize_bus_text(bus_dir)
    saw_marker = False
    for item in _process_chain(pid, ppid):
        for marker in _bus_markers_from_command(commands.get(item, "")):
            saw_marker = True
            if marker != expected:
                return False
    return saw_marker or expected == ".agent_bus"


def scan_live_bridge_workers(
    repo_root: Path,
    *,
    bus_dir: str = ".agent_bus",
) -> list[LiveBridgeWorker]:
    try:
        proc = subprocess.run(
            ["ps", "-Ao", "pid=,ppid=,command="],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    commands: dict[int, str] = {}
    ppid: dict[int, int] = {}
    for raw in proc.stdout.splitlines():
        parts = raw.strip().split(None, 2)
        if len(parts) != 3:
            continue
        try:
            pid = int(parts[0])
            parent = int(parts[1])
        except ValueError:
            continue
        ppid[pid] = parent
        commands[pid] = parts[2]

    workers: list[LiveBridgeWorker] = []
    cwd_cache: dict[int, str | None] = {}
    for pid, command in commands.items():
        provider = _process_provider(command)
        if provider is None:
            continue
        role = _ancestor_role(pid, ppid, commands)
        if not _process_chain_matches_repo(
            pid=pid,
            repo_root=repo_root,
            ppid=ppid,
            commands=commands,
            cwd_cache=cwd_cache,
        ):
            continue
        if not _process_chain_matches_bus(
            pid=pid,
            bus_dir=bus_dir,
            ppid=ppid,
            commands=commands,
        ):
            continue
        workers.append(
            LiveBridgeWorker(pid=pid, provider=provider, role=role, command=command)
        )
    return workers


def _call_worker_scanner(
    worker_scanner: Callable[..., list[LiveBridgeWorker]],
    repo_root: Path,
    bus_dir: str,
) -> list[LiveBridgeWorker]:
    try:
        signature = inspect.signature(worker_scanner)
    except (TypeError, ValueError):
        return worker_scanner(repo_root, bus_dir=bus_dir)
    accepts_bus = any(
        param.kind == inspect.Parameter.VAR_KEYWORD or name == "bus_dir"
        for name, param in signature.parameters.items()
    )
    if accepts_bus:
        return worker_scanner(repo_root, bus_dir=bus_dir)
    return worker_scanner(repo_root)


def _run_pane_processes_once(
    *,
    repo_root: Path,
    bus_dir: str,
    runner: Callable[..., Any],
) -> CommandOutcome:
    script = _existing_script(
        repo_root,
        (
            "mu/tools/observability/_pane_processes.sh",
            "tools/observability/_pane_processes.sh",
        ),
    )
    env = os.environ.copy()
    env.update(
        {
            "RCX_PANE_ONESHOT": "1",
            "RCX_PANE_ENABLE_PROCESS_SCAN": "1",
            "RCX_AGENT_BUS_DIR": bus_dir,
            "BUS_DIR": bus_dir,
            "TERM": env.get("TERM", "xterm"),
        }
    )
    result = runner(
        ["bash", str(script)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=15,
    )
    return CommandOutcome(
        args=["bash", str(script)],
        returncode=int(getattr(result, "returncode", 0)),
        stdout=str(getattr(result, "stdout", "") or ""),
        stderr=str(getattr(result, "stderr", "") or ""),
    )


def _verify_codex_autoping_window(
    *,
    repo_root: Path,
    bus_dir: str,
    tmux_session: str,
    selected_records: list[AutopingRecord],
) -> list[str]:
    if not selected_records:
        return []
    try:
        has_session = subprocess.run(
            ["tmux", "has-session", "-t", tmux_session],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if has_session.returncode != 0:
        return []
    try:
        pane = subprocess.run(
            ["tmux", "capture-pane", "-p", "-t", f"{tmux_session}:AUTO-PING"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return [f"{tmux_session}:AUTO-PING could not be inspected"]
    if pane.returncode != 0:
        return [f"{tmux_session}:AUTO-PING is missing or unreadable"]
    output = pane.stdout
    failures: list[str] = []
    if str(repo_root) not in output:
        failures.append(f"{tmux_session}:AUTO-PING is not rooted at selected repo")
    if bus_dir not in output:
        failures.append(f"{tmux_session}:AUTO-PING is not using selected bus")
    if not any(record.label and record.label in output for record in selected_records):
        failures.append(f"{tmux_session}:AUTO-PING is not showing selected Codex thread")
    return failures


def verify_state(
    *,
    repo_root: Path,
    bus_dir: str,
    mode: str,
    tmux_session: str,
    provider: dict[str, Any],
    role_agents: dict[str, dict[str, str]],
    runner: Callable[..., Any] = subprocess.run,
    pid_exists: Callable[[int], bool] = _pid_exists,
    command_reader: Callable[[int], str] = _pid_command_line,
    worker_scanner: Callable[..., list[LiveBridgeWorker]] = scan_live_bridge_workers,
    autoping_scanner: Callable[..., list[LiveAutopingProcess]] = scan_live_autoping_processes,
) -> tuple[list[str], list[str]]:
    del role_agents  # visible in reports; not a verification authority.
    failures: list[str] = []
    warnings: list[str] = []

    config = load_executor_config(repo_root)
    token = PAGER_ACTIVE_BUS_DIR.set(normalize_agent_bus_dir(bus_dir))
    try:
        route = pager_resolve_route(repo_root, config, None)
    finally:
        PAGER_ACTIVE_BUS_DIR.reset(token)
    if route != mode:
        failures.append(f"effective pager route is {route!r}, expected {mode!r}")

    state = _read_json(_orchestrator_state_path(repo_root, bus_dir), {})
    if not isinstance(state, dict) or state.get("mode") != mode:
        failures.append("orchestrator state file does not match selected mode")
    else:
        if state.get("repo_root") != str(repo_root):
            failures.append("orchestrator state file has the wrong repo_root")
        if state.get("bus_dir") != bus_dir:
            failures.append("orchestrator state file has the wrong bus_dir")
        if state.get("tmux_session") != tmux_session:
            failures.append("orchestrator state file has the wrong tmux_session")

    stale = stale_opposite_pager_targets(repo_root, bus_dir, mode)
    if stale:
        rendered = ", ".join(f"{item['event_id']}:{item['target']}" for item in stale)
        failures.append(f"stale opposite-orchestrator pager targets remain pending: {rendered}")

    wrong = "claude" if mode == "codex" else "codex"
    wrong_live_by_label: dict[tuple[str, str], list[int]] = {}
    for record in collect_autoping_records(wrong, repo_root=repo_root, bus_dir=bus_dir):
        key = (record.kind, record.label)
        for pid in record.pids:
            if not pid_exists(pid) or not _autoping_pid_matches_record(
                record,
                pid,
                command_reader=command_reader,
            ):
                continue
            wrong_live_by_label.setdefault(key, [])
            if pid not in wrong_live_by_label[key]:
                wrong_live_by_label[key].append(pid)
    for process in autoping_scanner(wrong, repo_root=repo_root, bus_dir=bus_dir):
        if not pid_exists(process.pid):
            continue
        key = (process.kind, process.label)
        wrong_live_by_label.setdefault(key, [])
        if process.pid not in wrong_live_by_label[key]:
            wrong_live_by_label[key].append(process.pid)
    for (kind, label), live_pids in sorted(wrong_live_by_label.items()):
        if live_pids:
            failures.append(
                f"wrong orchestrator autoping still live: {kind}:{label} pids={live_pids}"
            )

    selected_records = collect_autoping_records(mode, repo_root=repo_root, bus_dir=bus_dir)
    if selected_records:
        live_selected = [
            f"{record.kind}:{record.label}:watcher_pid={pid}"
            for record in selected_records
            for pid in [
                _autoping_watcher_pid_matches_record(
                    record,
                    pid_exists=pid_exists,
                    command_reader=command_reader,
                )
            ]
            if pid is not None
        ]
        if not live_selected:
            failures.append(f"{mode} autoping state exists but no watcher pid is live")
    else:
        failures.append(f"no {mode} autoping state file found for selected root/bus")
    if mode == "codex" and runner is subprocess.run:
        failures.extend(
            _verify_codex_autoping_window(
                repo_root=repo_root,
                bus_dir=bus_dir,
                tmux_session=tmux_session,
                selected_records=selected_records,
            )
        )

    workers = _call_worker_scanner(worker_scanner, repo_root, bus_dir)
    if workers:
        pane = _run_pane_processes_once(repo_root=repo_root, bus_dir=bus_dir, runner=runner)
        if pane.returncode != 0:
            failures.append(f"pane process verification failed: {pane.stderr.strip() or pane.returncode}")
        else:
            output = pane.stdout
            if "WHO'S WORKING" not in output:
                failures.append("Who's Working is blank while a live bridge-agent subprocess exists")
            for worker in workers:
                display = bridge_agent_display_name(repo_root, worker.provider, bus_dir)
                if display and display not in output:
                    failures.append(
                        f"Who's Working did not label live {worker.provider} worker as {display!r}"
                    )
                if worker.role == "review" and "REVIEWING" not in output:
                    failures.append("live review worker was not classified as reviewing")
                if worker.role == "implement" and "IMPLEMENTING" not in output:
                    failures.append("live implement worker was not classified as implementing")
                if worker.provider == "codex" and "REVIEWING  Claude" in output:
                    failures.append("live Codex worker is displayed as Claude")

    if provider.get("display_name") is None:
        failures.append(f"{mode} provider metadata is missing display_name")
    return failures, warnings


def apply_orchestrator_mode(
    *,
    mode: str,
    repo_root: Path,
    bus_dir: str,
    tmux_session: str,
    dry_run: bool,
    verify: bool,
    runner: Callable[..., Any] = subprocess.run,
    pid_exists: Callable[[int], bool] = _pid_exists,
    killer: Callable[[int], None] = _kill_pid,
    command_reader: Callable[[int], str] = _pid_command_line,
    worker_scanner: Callable[..., list[LiveBridgeWorker]] = scan_live_bridge_workers,
    autoping_scanner: Callable[..., list[LiveAutopingProcess]] = scan_live_autoping_processes,
    codex_thread_id: str = "",
    claude_session_id: str = "",
    autoping_wait_s: float | None = None,
) -> SwitchReport:
    if mode not in MODE_CHOICES:
        raise OrchestratorModeError(f"unsupported mode: {mode!r}")
    bus_dir = normalize_agent_bus_dir(bus_dir).as_posix()
    resolve_agent_bus_dir(repo_root, bus_dir)
    tmux_session = _validate_tmux_session(tmux_session)
    provider = _validate_mode_in_registry(repo_root, mode)
    role_agents = _role_agent_visibility(repo_root, bus_dir)
    report = SwitchReport(
        mode=mode,
        repo_root=repo_root,
        bus_dir=bus_dir,
        tmux_session=tmux_session,
        provider=provider,
        role_agents=role_agents,
    )

    report.config_changed = _set_pager_route(repo_root, mode, dry_run=dry_run)
    report.state_changed = _write_orchestrator_state(
        repo_root=repo_root,
        bus_dir=bus_dir,
        tmux_session=tmux_session,
        mode=mode,
        provider=provider,
        role_agents=role_agents,
        dry_run=dry_run,
    )
    report.skipped_pager_targets = terminally_skip_opposite_pager_targets(
        repo_root,
        bus_dir,
        mode,
        dry_run=dry_run,
    )

    wrong = "claude" if mode == "codex" else "codex"
    wrong_records = collect_autoping_records(wrong, repo_root=repo_root, bus_dir=bus_dir)
    wrong_processes = autoping_scanner(wrong, repo_root=repo_root, bus_dir=bus_dir)
    report.stopped_autoping = stop_wrong_autoping_processes(
        wrong_records,
        wrong_processes,
        dry_run=dry_run,
        pid_exists=pid_exists,
        killer=killer,
        command_reader=command_reader,
    )

    autoping_cmd = build_autoping_command(
        mode,
        repo_root=repo_root,
        bus_dir=bus_dir,
        tmux_session=tmux_session,
        codex_thread_id=codex_thread_id,
        claude_session_id=claude_session_id,
    )
    monitor_cmds = build_monitor_commands(
        repo_root=repo_root,
        bus_dir=bus_dir,
        tmux_session=tmux_session,
        mode=mode,
    )
    report.commands = [*monitor_cmds, autoping_cmd]

    if not dry_run:
        for cmd in monitor_cmds:
            outcome = _run_command(cmd, cwd=repo_root, runner=runner)
            report.command_results.append(outcome)
            if _command_failed(outcome):
                report.verify_failures.append(
                    f"command failed ({outcome.returncode}): {' '.join(cmd)}"
                )
        outcome = _run_command(autoping_cmd, cwd=repo_root, runner=runner)
        report.command_results.append(outcome)
        if _command_failed(outcome):
            report.verify_failures.append(
                f"command failed ({outcome.returncode}): {' '.join(autoping_cmd)}"
            )
        if verify and not report.verify_failures:
            wait_s = (
                _default_autoping_wait_seconds(runner)
                if autoping_wait_s is None
                else max(float(autoping_wait_s), 0.0)
            )
            _wait_for_selected_autoping(
                mode,
                repo_root=repo_root,
                bus_dir=bus_dir,
                timeout_s=wait_s,
                pid_exists=pid_exists,
                command_reader=command_reader,
            )

    if verify and not dry_run:
        failures, warnings = verify_state(
            repo_root=repo_root,
            bus_dir=bus_dir,
            mode=mode,
            tmux_session=tmux_session,
            provider=provider,
            role_agents=role_agents,
            runner=runner,
            pid_exists=pid_exists,
            command_reader=command_reader,
            worker_scanner=worker_scanner,
            autoping_scanner=autoping_scanner,
        )
        report.verify_failures.extend(failures)
        report.verify_warnings.extend(warnings)
    return report


def verify_orchestrator_mode(
    *,
    mode: str,
    repo_root: Path,
    bus_dir: str,
    tmux_session: str,
    runner: Callable[..., Any] = subprocess.run,
    pid_exists: Callable[[int], bool] = _pid_exists,
    command_reader: Callable[[int], str] = _pid_command_line,
    worker_scanner: Callable[..., list[LiveBridgeWorker]] = scan_live_bridge_workers,
    autoping_scanner: Callable[..., list[LiveAutopingProcess]] = scan_live_autoping_processes,
) -> SwitchReport:
    bus_dir = normalize_agent_bus_dir(bus_dir).as_posix()
    resolve_agent_bus_dir(repo_root, bus_dir)
    tmux_session = _validate_tmux_session(tmux_session)
    provider = _validate_mode_in_registry(repo_root, mode)
    role_agents = _role_agent_visibility(repo_root, bus_dir)
    failures, warnings = verify_state(
        repo_root=repo_root,
        bus_dir=bus_dir,
        mode=mode,
        tmux_session=tmux_session,
        provider=provider,
        role_agents=role_agents,
        runner=runner,
        pid_exists=pid_exists,
        command_reader=command_reader,
        worker_scanner=worker_scanner,
        autoping_scanner=autoping_scanner,
    )
    return SwitchReport(
        mode=mode,
        repo_root=repo_root,
        bus_dir=bus_dir,
        tmux_session=tmux_session,
        provider=provider,
        role_agents=role_agents,
        verify_failures=failures,
        verify_warnings=warnings,
    )


def render_report(report: SwitchReport, *, dry_run: bool) -> str:
    lines: list[str] = []
    prefix = "DRY-RUN" if dry_run else "APPLIED"
    lines.append(f"{prefix} orchestrator_mode={report.mode}")
    lines.append(f"  effective_pager_route={report.mode}")
    lines.append(f"  repo_root={report.repo_root}")
    lines.append(f"  bus_dir={report.bus_dir}")
    lines.append(f"  tmux_session={report.tmux_session}")
    lines.append(f"  selected_provider={_provider_summary(report.provider)}")
    if report.role_agents:
        impl = report.role_agents.get("implementer", {})
        rev = report.role_agents.get("reviewer", {})
        lines.append(
            "  role_agents_visible="
            f"implementer={impl.get('agent', '?')} reviewer={rev.get('agent', '?')}"
        )
    lines.append(f"  config_change={'yes' if report.config_changed else 'no'}")
    lines.append(f"  state_change={'yes' if report.state_changed else 'no'}")
    if report.skipped_pager_targets:
        rendered = ", ".join(
            f"{item['event_id']}:{item['target']}" for item in report.skipped_pager_targets
        )
        lines.append(f"  stale_pager_targets_terminally_skipped={rendered}")
    else:
        lines.append("  stale_pager_targets_terminally_skipped=none")
    if report.stopped_autoping:
        lines.append("  stopped_wrong_autoping=" + ", ".join(report.stopped_autoping))
    else:
        lines.append("  stopped_wrong_autoping=none")
    if report.commands:
        lines.append("  commands:")
        for cmd in report.commands:
            lines.append("    " + " ".join(cmd))
    if report.command_results:
        lines.append("  command_results:")
        for outcome in report.command_results:
            status = "ok" if outcome.returncode == 0 else f"exit={outcome.returncode}"
            lines.append(f"    {status}: {' '.join(outcome.args)}")
    if report.verify_warnings:
        lines.append("  verify_warnings:")
        lines.extend(f"    {item}" for item in report.verify_warnings)
    if report.verify_failures:
        lines.append("  verify_failures:")
        lines.extend(f"    {item}" for item in report.verify_failures)
    else:
        lines.append("  verify=ok")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Switch active orchestrator mode for pager, tmux monitor, and "
            "autoping without changing implementer/reviewer roles."
        )
    )
    parser.add_argument("--mode", choices=MODE_CHOICES, required=True)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--bus-dir", default=os.environ.get("RCX_AGENT_BUS_DIR", ".agent_bus"))
    parser.add_argument("--tmux-session", default="rcx-pipeline")
    parser.add_argument("--thread-id", default="", help="Codex thread id for codex autoping")
    parser.add_argument("--codex-thread-id", default="", help=argparse.SUPPRESS)
    parser.add_argument("--claude-session-id", default="", help="Claude monitor session id override")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--dry-run", action="store_true", help="Show exact changes without applying them")
    action.add_argument("--show", action="store_true", help="Alias for --dry-run")
    action.add_argument("--apply", action="store_true", help="Apply switch, restart surfaces, then verify")
    action.add_argument("--verify", action="store_true", help="Verify current state only")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        repo_root = _repo_root(args.repo_root)
        if args.verify:
            report = verify_orchestrator_mode(
                mode=args.mode,
                repo_root=repo_root,
                bus_dir=args.bus_dir,
                tmux_session=args.tmux_session,
            )
            print(render_report(report, dry_run=False))
            return 0 if report.ok else 1

        dry_run = args.dry_run or args.show or not args.apply
        report = apply_orchestrator_mode(
            mode=args.mode,
            repo_root=repo_root,
            bus_dir=args.bus_dir,
            tmux_session=args.tmux_session,
            dry_run=dry_run,
            verify=args.apply,
            codex_thread_id=args.codex_thread_id or args.thread_id,
            claude_session_id=args.claude_session_id,
        )
        print(render_report(report, dry_run=dry_run))
        return 0 if report.ok else 1
    except OrchestratorModeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
