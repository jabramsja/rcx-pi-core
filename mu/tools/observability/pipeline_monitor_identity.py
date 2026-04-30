#!/usr/bin/env python3
"""Resolve configured pipeline monitor identity for observability surfaces."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_BUS_DIR = ".agent_bus"
DEFAULT_DASHBOARD_PORT = 8099
DEFAULT_TMUX_SESSION = "rcx-pipeline"
CONFIG_ENV = "RCX_PIPELINE_MONITOR_CONFIG"
LANE_ENV = "RCX_PIPELINE_MONITOR_LANE"
BUS_ENV = "RCX_AGENT_BUS_DIR"
TMUX_SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
LANE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
BUS_DIR_RE = re.compile(r"^\.agent_bus-[A-Za-z0-9][A-Za-z0-9_-]*$")


class MonitorIdentityError(ValueError):
    """Raised when monitor identity configuration is unsafe or incomplete."""


@dataclass(frozen=True)
class MonitorIdentity:
    lane: str
    bus_dir: str
    active_bus_root: Path
    dashboard_port: int
    tmux_session: str
    configured: bool
    named: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "lane": self.lane,
            "bus_dir": self.bus_dir,
            "active_bus_root": str(self.active_bus_root),
            "dashboard_port": self.dashboard_port,
            "tmux_session": self.tmux_session,
            "configured": self.configured,
            "named": self.named,
        }


def default_config_path(repo_root: Path) -> Path:
    override = os.environ.get(CONFIG_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return repo_root / "mu" / "tools" / "executors" / "executor_config.json"


def validate_bus_dir(value: str | Path | None) -> str:
    raw = str(value or DEFAULT_BUS_DIR).strip().rstrip("/")
    if (
        not raw
        or "\\" in raw
        or "/" in raw
        or ".." in raw
        or Path(raw).is_absolute()
        or (raw != DEFAULT_BUS_DIR and BUS_DIR_RE.fullmatch(raw) is None)
    ):
        raise MonitorIdentityError(
            f"invalid active bus root {raw!r}; expected .agent_bus or .agent_bus-<id>"
        )
    return raw


def validate_tmux_session(value: object, *, lane: str) -> str:
    raw = str(value or "").strip()
    if TMUX_SESSION_RE.fullmatch(raw) is None:
        raise MonitorIdentityError(
            f"invalid tmux session for monitor lane {lane!r}: {raw!r}; "
            "use letters, numbers, dot, underscore, or hyphen, starting with a letter or number"
        )
    return raw


def validate_port(value: object, *, lane: str) -> int:
    if isinstance(value, bool) or value in (None, ""):
        raise MonitorIdentityError(f"missing dashboard_port for monitor lane {lane!r}")
    if isinstance(value, int):
        port = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw.isdecimal():
            raise MonitorIdentityError(
                f"invalid dashboard_port for monitor lane {lane!r}: {value!r}"
            )
        port = int(raw)
    else:
        raise MonitorIdentityError(
            f"invalid dashboard_port for monitor lane {lane!r}: {value!r}"
        )
    if port < 1 or port > 65535:
        raise MonitorIdentityError(
            f"invalid dashboard_port for monitor lane {lane!r}: {port}; expected 1-65535"
        )
    return port


def _load_json_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        if os.environ.get(CONFIG_ENV, "").strip():
            raise MonitorIdentityError(f"monitor identity config not found: {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MonitorIdentityError(
            f"monitor identity config is invalid JSON at {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise MonitorIdentityError(f"monitor identity config at {path} must be a JSON object")
    return payload


def _monitor_config_block(payload: dict[str, Any]) -> dict[str, Any]:
    block = payload.get("pipeline_monitor", {})
    if block in (None, ""):
        return {}
    if not isinstance(block, dict):
        raise MonitorIdentityError("executor config key pipeline_monitor must be an object")
    return block


def load_monitor_lanes(repo_root: Path) -> dict[str, dict[str, object]]:
    payload = _load_json_config(default_config_path(repo_root))
    block = _monitor_config_block(payload)
    lanes = block.get("lanes", {})
    if lanes in (None, ""):
        lanes = {}
    if not isinstance(lanes, dict):
        raise MonitorIdentityError("pipeline_monitor.lanes must be an object")

    normalized: dict[str, dict[str, object]] = {}
    seen_sessions: dict[str, str] = {DEFAULT_TMUX_SESSION: "default"}
    seen_ports: dict[int, str] = {DEFAULT_DASHBOARD_PORT: "default"}
    seen_buses: dict[str, str] = {}

    for raw_name, raw_config in lanes.items():
        lane = str(raw_name).strip()
        if LANE_NAME_RE.fullmatch(lane) is None:
            raise MonitorIdentityError(
                f"invalid monitor lane name {raw_name!r}; "
                "use letters, numbers, dot, underscore, or hyphen"
            )
        if not isinstance(raw_config, dict):
            raise MonitorIdentityError(f"monitor lane {lane!r} must be an object")

        if "bus_dir" not in raw_config or raw_config.get("bus_dir") in (None, ""):
            raise MonitorIdentityError(f"missing active bus root for monitor lane {lane!r}")
        if "dashboard_port" not in raw_config:
            raise MonitorIdentityError(f"missing dashboard_port for monitor lane {lane!r}")
        if "tmux_session" not in raw_config or raw_config.get("tmux_session") in (None, ""):
            raise MonitorIdentityError(f"missing tmux_session for monitor lane {lane!r}")

        bus_dir = validate_bus_dir(raw_config.get("bus_dir"))
        if bus_dir == DEFAULT_BUS_DIR:
            raise MonitorIdentityError(
                f"monitor lane {lane!r} uses default active bus root; omit the lane or use .agent_bus-<id>"
            )
        port = validate_port(raw_config.get("dashboard_port"), lane=lane)
        session = validate_tmux_session(raw_config.get("tmux_session"), lane=lane)

        if session in seen_sessions:
            raise MonitorIdentityError(
                f"duplicate tmux session {session!r} for lanes {seen_sessions[session]!r} and {lane!r}"
            )
        if port in seen_ports:
            raise MonitorIdentityError(
                f"duplicate dashboard port {port} for lanes {seen_ports[port]!r} and {lane!r}"
            )
        if bus_dir in seen_buses:
            raise MonitorIdentityError(
                f"duplicate active bus root {bus_dir!r} for lanes {seen_buses[bus_dir]!r} and {lane!r}"
            )

        seen_sessions[session] = lane
        seen_ports[port] = lane
        seen_buses[bus_dir] = lane
        normalized[lane] = {
            "bus_dir": bus_dir,
            "dashboard_port": port,
            "tmux_session": session,
        }

    return normalized


def _default_identity(repo_root: Path, *, port: int | None = None) -> MonitorIdentity:
    dashboard_port = DEFAULT_DASHBOARD_PORT if port is None else validate_port(port, lane="default")
    return MonitorIdentity(
        lane="default",
        bus_dir=DEFAULT_BUS_DIR,
        active_bus_root=repo_root / DEFAULT_BUS_DIR,
        dashboard_port=dashboard_port,
        tmux_session=DEFAULT_TMUX_SESSION,
        configured=False,
        named=False,
    )


def _identity_from_lane(repo_root: Path, lane: str, config: dict[str, object]) -> MonitorIdentity:
    bus_dir = str(config["bus_dir"])
    return MonitorIdentity(
        lane=lane,
        bus_dir=bus_dir,
        active_bus_root=repo_root / bus_dir,
        dashboard_port=int(config["dashboard_port"]),
        tmux_session=str(config["tmux_session"]),
        configured=True,
        named=True,
    )


def resolve_monitor_identity(
    repo_root: Path,
    *,
    lane: str | None = None,
    bus_dir: str | Path | None = None,
    port: int | str | None = None,
    require_configured_named: bool = True,
) -> MonitorIdentity:
    repo_root = Path(repo_root)
    env_lane = os.environ.get(LANE_ENV, "").strip()
    requested_lane = (lane or env_lane or "").strip()
    requested_bus = validate_bus_dir(bus_dir or os.environ.get(BUS_ENV) or DEFAULT_BUS_DIR)
    requested_port = None if port in (None, "") else validate_port(port, lane=requested_lane or "default")
    lanes = load_monitor_lanes(repo_root)

    if requested_lane:
        if requested_lane == "default":
            if requested_bus != DEFAULT_BUS_DIR:
                raise MonitorIdentityError("default monitor lane cannot use a namespaced active bus root")
            return _default_identity(repo_root, port=requested_port)
        if requested_lane not in lanes:
            raise MonitorIdentityError(f"monitor lane {requested_lane!r} is not configured")
        identity = _identity_from_lane(repo_root, requested_lane, lanes[requested_lane])
        if requested_bus != DEFAULT_BUS_DIR and requested_bus != identity.bus_dir:
            raise MonitorIdentityError(
                f"monitor lane {requested_lane!r} is configured for {identity.bus_dir}, not {requested_bus}"
            )
        if requested_port is not None and requested_port != identity.dashboard_port:
            raise MonitorIdentityError(
                f"monitor lane {requested_lane!r} is configured for dashboard port "
                f"{identity.dashboard_port}, not {requested_port}"
            )
        return identity

    if requested_bus == DEFAULT_BUS_DIR:
        return _default_identity(repo_root, port=requested_port)

    matches = [
        _identity_from_lane(repo_root, name, config)
        for name, config in lanes.items()
        if config.get("bus_dir") == requested_bus
    ]
    if len(matches) == 1:
        identity = matches[0]
        if requested_port is not None and requested_port != identity.dashboard_port:
            raise MonitorIdentityError(
                f"active bus root {requested_bus} is configured for dashboard port "
                f"{identity.dashboard_port}, not {requested_port}"
            )
        return identity
    if len(matches) > 1:
        raise MonitorIdentityError(f"active bus root {requested_bus} matches multiple monitor lanes")
    if require_configured_named:
        raise MonitorIdentityError(
            f"active bus root {requested_bus} has no configured monitor identity; "
            "named lanes require bus_dir, dashboard_port, and tmux_session"
        )
    return MonitorIdentity(
        lane=requested_bus.removeprefix(".agent_bus-") or requested_bus,
        bus_dir=requested_bus,
        active_bus_root=repo_root / requested_bus,
        dashboard_port=DEFAULT_DASHBOARD_PORT if requested_port is None else requested_port,
        tmux_session=DEFAULT_TMUX_SESSION,
        configured=False,
        named=True,
    )


def _shell_assignments(identity: MonitorIdentity) -> str:
    values = {
        "RCX_MONITOR_LANE": identity.lane,
        "RCX_MONITOR_BUS_DIR": identity.bus_dir,
        "RCX_MONITOR_BUS_PATH": str(identity.active_bus_root),
        "RCX_MONITOR_DASHBOARD_PORT": str(identity.dashboard_port),
        "RCX_MONITOR_TMUX_SESSION": identity.tmux_session,
        "RCX_MONITOR_NAMED": "1" if identity.named else "0",
    }
    return "\n".join(f"{key}={shlex.quote(value)}" for key, value in values.items()) + "\n"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve RCX pipeline monitor identity")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--lane", default=None)
    parser.add_argument("--bus-dir", default=None)
    parser.add_argument("--port", default=None)
    parser.add_argument("--allow-unconfigured-named-bus", action="store_true")
    parser.add_argument("--format", choices=("json", "shell"), default="json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        identity = resolve_monitor_identity(
            Path(args.repo_root),
            lane=args.lane,
            bus_dir=args.bus_dir,
            port=args.port,
            require_configured_named=not args.allow_unconfigured_named_bus,
        )
    except MonitorIdentityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.format == "shell":
        sys.stdout.write(_shell_assignments(identity))
    else:
        sys.stdout.write(json.dumps(identity.as_dict(), sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
