#!/usr/bin/env python3
"""set_roles — one-line switch for the implementer / reviewer LLM roles.

`role_agents` in executor_config.json is the SINGLE switch. This CLI edits ONLY
that file (role_agents + the derived backends/bridge_reviewers), never any Python,
and prints the written state, the runtime-EFFECTIVE resolution (which is env-aware),
and a warning if an env override is silently shadowing the committed config.

Usage:
    python3 mu/tools/executors/set_roles.py --implementer claude --reviewer codex
    python3 mu/tools/executors/set_roles.py --reviewer claude
    python3 mu/tools/executors/set_roles.py --show

The derivation rule (role_agents -> backends/bridge_reviewers) is shared with the
runtime loader via executor_common.apply_role_agents, so the written file is exactly
the materialization fixed-point the dispatcher would compute at load time.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from executor_common import (  # noqa: E402  (path insert must precede import)
    DEFAULT_AGENT_DISPLAY_NAMES,
    DEFAULT_EXECUTOR_CONFIG,
    ROLE_AGENT_ENV_VARS,
    apply_role_agents,
    resolve_role_agent,
)


def _repo_root(override: str | None) -> Path:
    if override:
        return Path(override).resolve()
    # set_roles.py lives at <repo_root>/mu/tools/executors/set_roles.py
    return Path(__file__).resolve().parents[3]


def _config_path(root: Path) -> Path:
    return root / "mu" / "tools" / "executors" / "executor_config.json"


def _valid_agents(config: dict) -> set[str]:
    defaults = config.get("bridge_agent_defaults")
    if not isinstance(defaults, dict):
        defaults = DEFAULT_EXECUTOR_CONFIG.get("bridge_agent_defaults", {})
    names = set(defaults) if isinstance(defaults, dict) else set()
    names |= set(DEFAULT_AGENT_DISPLAY_NAMES)
    return names


def _print_state(config: dict, impl: str, rev: str, *, changed: bool) -> None:
    label = "WROTE" if changed else "CURRENT"
    print(f"{label} role_agents: implementer={impl} reviewer={rev}")
    print(f"  derived backends         : {config.get('backends')}")
    print(f"  derived bridge_reviewers : {config.get('bridge_reviewers')}")
    eff_impl = resolve_role_agent(config, "implementer", raw_overrides=config)
    eff_rev = resolve_role_agent(config, "reviewer", raw_overrides=config)
    print(f"  EFFECTIVE (env-aware)    : implementer={eff_impl} reviewer={eff_rev}")
    shadows = [
        (role, name, os.environ[name])
        for role, names in ROLE_AGENT_ENV_VARS.items()
        for name in names
        if os.environ.get(name)
    ]
    if shadows:
        print("  WARNING: env override(s) SHADOW executor_config.json (env wins):")
        for role, name, value in shadows:
            print(f"    {name}={value}  -> forces {role}={value} regardless of role_agents")
        print("  Remove the env var(s) to make executor_config.json the sole source of truth.")
    else:
        print("  No env override active — executor_config.json is the sole source of truth.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Switch the implementer/reviewer LLM roles by editing executor_config.json role_agents."
    )
    ap.add_argument("--implementer", help="Agent for implementer role (e.g. claude, codex)")
    ap.add_argument("--reviewer", help="Agent for reviewer role (e.g. claude, codex)")
    ap.add_argument("--show", action="store_true", help="Print current + effective state without changing anything")
    ap.add_argument("--repo-root", default=None, help="Repo root (defaults to this file's repo)")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    root = _repo_root(args.repo_root)
    cfg_path = _config_path(root)
    if not cfg_path.exists():
        print(f"ERROR: executor_config.json not found: {cfg_path}", file=sys.stderr)
        return 2
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    current = raw.get("role_agents") if isinstance(raw.get("role_agents"), dict) else {}
    cur_impl = current.get("implementer", "codex")
    cur_rev = current.get("reviewer", "codex")

    if not args.implementer and not args.reviewer:
        # --show or no-op: report current state, change nothing
        _print_state(raw, cur_impl, cur_rev, changed=False)
        return 0

    impl = args.implementer or cur_impl
    rev = args.reviewer or cur_rev
    valid = _valid_agents(raw)
    for role, value in (("implementer", impl), ("reviewer", rev)):
        if value not in valid:
            print(f"ERROR: unknown {role} agent {value!r}; valid agents: {sorted(valid)}", file=sys.stderr)
            return 2

    apply_role_agents(raw, impl, rev)
    cfg_path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    _print_state(raw, impl, rev, changed=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
