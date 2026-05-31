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

Contract (A2, FOUNDER_OVERRIDE:role-switch-convergence-2026-05-31): the live
executor_config.json is the AUTHORITATIVE source of truth for role_agents.
DEFAULT_EXECUTOR_CONFIG in executor_common.py is only a fallback for keys the live
file omits and need NOT equal the live file. This CLI is therefore a COMPLETE role
switch on its own -- it writes role_agents and materializes backends/bridge_reviewers
into the live file, with no Python edit and no second config path required.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from executor_common import (  # noqa: E402  (path insert must precede import)
    DEFAULT_AGENT_DISPLAY_NAMES,
    DEFAULT_EXECUTOR_CONFIG,
    ROLE_AGENT_ENV_VARS,
    apply_role_agents,
    resolve_committed_role_agent,
    resolve_role_agent,
)


def _repo_root(override: str | None) -> Path:
    if override:
        return Path(override).resolve()
    # set_roles.py lives at <repo_root>/mu/tools/executors/set_roles.py
    return Path(__file__).resolve().parents[3]


def _config_path(root: Path) -> Path:
    return root / "mu" / "tools" / "executors" / "executor_config.json"


def _atomic_write_text(path: Path, text: str) -> None:
    """Write *text* to *path* atomically so readers never observe a torn write.

    The live executor_config.json is the AUTHORITATIVE role-switch source and the
    runtime loader reads it with an unguarded json.loads
    (executor_common.load_executor_config), so a partial/truncated write would break
    every later config load. Write to a temp file in the SAME directory, flush+fsync
    it, then os.replace() onto the target -- an atomic rename on the same filesystem,
    so a crash mid-switch leaves the complete old file, never invalid JSON.
    """
    directory = path.parent
    fd, tmp_name = tempfile.mkstemp(dir=str(directory), prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        # Never leave truncated temp residue behind on a failed switch.
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


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
    # Resolve the CURRENT committed roles with the same precedence the runtime
    # loader uses (explicit role_agents -> legacy backends/bridge_reviewers ->
    # default), so a partial switch preserves the un-changed role even for legacy
    # configs that predate role_agents. Env shadows are excluded on purpose: they
    # must not be baked into the written file (they surface as a warning below).
    cur_impl = resolve_committed_role_agent(raw, "implementer")
    cur_rev = resolve_committed_role_agent(raw, "reviewer")

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
    _atomic_write_text(cfg_path, json.dumps(raw, indent=2) + "\n")
    _print_state(raw, impl, rev, changed=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
