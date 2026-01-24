"""
Bridge from Python (rcx_pi) to the Rust RCX-π engine.

This module shells out to the Rust examples in rcx_pi_rust/ so that
Python code can:

  - classify Mu terms under a given world
  - inspect rewrite orbits / ω-limit behavior under a world
"""

from __future__ import annotations

import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple


def _run_rust_example(args: List[str]) -> Tuple[int, str]:
    """
    Internal helper: run `cargo run --example <...> -- <args...>`
    inside rcx_pi_rust/, return (exit_code, stdout+stderr text).
    """
    cmd = ["cargo", "run", "--example"] + args
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd="rcx_pi_rust",
    )
    return proc.returncode, proc.stdout + proc.stderr


# ---------------------------------------------------------------------------
# Classification bridge
# ---------------------------------------------------------------------------


def classify_with_world(world_name: str, mu_terms: List[str]) -> Tuple[int, str]:
    """
    Ask the Rust classify_cli example to classify a list of Mu terms under a world.

    Args:
        world_name: name of the .mu world (e.g. "rcx_core", "news", "pingpong").
        mu_terms:   list of Mu term strings, e.g. ["[null,a]", "[inf,a]"].

    Returns:
        (exit_code, output_text)
    """
    args = ["classify_cli", "--", world_name] + mu_terms
    return _run_rust_example(args)


# ---------------------------------------------------------------------------
# Orbit / ω-limit bridge (raw)
# ---------------------------------------------------------------------------


def orbit_with_world(
    world_name: str, seed: str, max_steps: int = 12
) -> Tuple[int, str]:
    """
    Ask the Rust orbit_cli example to compute the rewrite orbit of a Mu term
    under a given world.

    Args:
        world_name: name of the .mu world, e.g. "pingpong" or "rcx_core".
        seed:       Mu term string, e.g. "ping" or "[omega,[a,b]]".
        max_steps:  max number of orbit steps to compute (default 12).

    Returns:
        (exit_code, output_text)

    The output_text looks roughly like:

        [world] loaded mu_programs/pingpong.mu

        [ω] seed: ping
        [ω] max steps: 12
        [ω] orbit (13 states):
            0: ping
            1: pong
            ...
        [ω] classification: pure limit cycle (period = 2)
    """
    args = ["orbit_cli", "--", world_name, seed, str(max_steps)]
    return _run_rust_example(args)


# ---------------------------------------------------------------------------
# Orbit output parsing
# ---------------------------------------------------------------------------


def parse_orbit_output(text: str) -> Dict[str, Any]:
    """
    Parse the text output from orbit_cli into a structured dict.

    Returns a dict with keys:

        {
            "seed": str | None,
            "max_steps": int | None,
            "states": List[str],
            "classification_raw": str | None,
            "kind": str | None,      # e.g. "limit_cycle", "fixed_point", "transient"
            "period": int | None,    # if kind == "limit_cycle"
        }

    The parser is intentionally tolerant: if it can't find something, it leaves
    that field as None instead of exploding.
    """
    seed: Optional[str] = None
    max_steps: Optional[int] = None
    states: List[str] = []
    classification_raw: Optional[str] = None
    kind: Optional[str] = None
    period: Optional[int] = None

    lines = text.splitlines()

    # 1) seed + max_steps
    for line in lines:
        line = line.strip()
        if line.startswith("[ω] seed:"):
            # e.g. "[ω] seed: ping"
            seed = line[len("[ω] seed:") :].strip()
        elif line.startswith("[ω] max steps:"):
            # e.g. "[ω] max steps: 12"
            value = line[len("[ω] max steps:") :].strip()
            try:
                max_steps = int(value)
            except ValueError:
                pass

    # 2) orbit states: lines like "    0: ping"
    in_orbit_block = False
    for line in lines:
        if "[ω] orbit" in line:
            in_orbit_block = True
            continue
        if in_orbit_block:
            if not line.strip():
                # blank line: end of orbit block
                break
            m = re.match(r"^\s*\d+:\s*(.*)$", line)
            if m:
                states.append(m.group(1).strip())
            else:
                # Non-matching line probably means the orbit block is over
                # (but we don't break aggressively in case formatting changes).
                continue

    # 3) classification line
    for line in lines:
        line = line.strip()
        if line.startswith("[ω] classification:"):
            classification_raw = line[len("[ω] classification:") :].strip()
            break

    # 4) derive coarse "kind" + period from the classification string
    if classification_raw:
        lower = classification_raw.lower()
        if "limit cycle" in lower:
            kind = "limit_cycle"
            # e.g. "pure limit cycle (period = 2)"
            m = re.search(r"period\s*=\s*(\d+)", lower)
            if m:
                try:
                    period = int(m.group(1))
                except ValueError:
                    period = None
        elif "fixed point" in lower:
            kind = "fixed_point"
        elif "transient" in lower:
            kind = "transient"
        else:
            kind = "other"

    return {
        "seed": seed,
        "max_steps": max_steps,
        "states": states,
        "classification_raw": classification_raw,
        "kind": kind,
        "period": period,
    }


def orbit_with_world_parsed(
    world_name: str,
    seed: str,
    max_steps: int = 12,
) -> Tuple[int, str, Dict[str, Any]]:
    """
    Convenience wrapper:

        code, raw, parsed = orbit_with_world_parsed("pingpong", "ping", 12)

    Returns:
        (exit_code, raw_output_text, parsed_dict)

    If exit_code != 0, parsed_dict will still be returned, but is likely empty
    or partially filled.
    """
    code, out = orbit_with_world(world_name, seed, max_steps)
    parsed = parse_orbit_output(out)
    return code, out, parsed
