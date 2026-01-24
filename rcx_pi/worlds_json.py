# rcx_pi/worlds_json.py
"""
Tiny helper for RCX-π "worlds" in JSON form.

Goal:
    - Let you define worlds like rcx_core in JSON:
        {
          "rules": [
            { "pattern": "[null,_]",  "action": "ra"   },
            { "pattern": "[inf,_]",   "action": "lobe" },
            { "pattern": "[paradox,_]", "action": "sink" }
          ]
        }

    - Save them out as .mu files that the Rust REPL already understands.
    - Optionally load a .mu file and represent it as the same JSON shape.

This is deliberately dumb/textual:
    - It does NOT depend on Motif, rcx_pi core, or the Rust engine.
    - It just shuttles `pattern` / `action` strings around.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any
import json


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class JsonRule:
    pattern: str
    action: str  # "ra" | "lobe" | "sink" | "rewrite <Mu>" (future)


@dataclass
class JsonWorld:
    rules: List[JsonRule]


# ---------------------------------------------------------------------------
# JSON <-> JsonWorld
# ---------------------------------------------------------------------------


def world_from_dict(data: Dict[str, Any]) -> JsonWorld:
    """
    Convert a Python dict (e.g. json.load result) into a JsonWorld.
    """
    raw_rules = data.get("rules", [])
    rules: List[JsonRule] = []
    for r in raw_rules:
        pattern = r.get("pattern")
        action = r.get("action")
        if not isinstance(pattern, str) or not isinstance(action, str):
            raise ValueError(f"Bad rule entry: {r!r}")
        rules.append(JsonRule(pattern=pattern, action=action))
    return JsonWorld(rules=rules)


def world_to_dict(world: JsonWorld) -> Dict[str, Any]:
    """
    Convert a JsonWorld back to a plain dict (for json.dump).
    """
    return {"rules": [{"pattern": r.pattern, "action": r.action} for r in world.rules]}


def load_world_json(path: str | Path) -> JsonWorld:
    """
    Load a world description from a JSON file.
    """
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return world_from_dict(data)


def save_world_json(path: str | Path, world: JsonWorld) -> None:
    """
    Save a JsonWorld to a JSON file.
    """
    p = Path(path)
    with p.open("w", encoding="utf-8") as f:
        json.dump(world_to_dict(world), f, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# JsonWorld -> .mu text
# ---------------------------------------------------------------------------


def world_to_mu_text(world: JsonWorld) -> str:
    """
    Render a JsonWorld into .mu format that the Rust engine already uses.

    Example output:

        [null,_]    -> ra
        [inf,_]     -> lobe
        [paradox,_] -> sink
    """
    lines: List[str] = []
    for r in world.rules:
        pattern = r.pattern.strip()
        action = r.action.strip()

        # For now we accept simple "ra", "lobe", "sink" actions.
        # You can later extend this to support "rewrite <Mu>" etc.
        if action in {"ra", "lobe", "sink"}:
            lines.append(f"{pattern} -> {action}")
        else:
            # Keep it literal for now; you can tighten this later
            lines.append(f"{pattern} -> {action}")
    return "\n".join(lines) + "\n"


def save_world_as_mu(mu_path: str | Path, world: JsonWorld) -> None:
    """
    Save a JsonWorld as a .mu file.
    """
    p = Path(mu_path)
    text = world_to_mu_text(world)
    with p.open("w", encoding="utf-8") as f:
        f.write(text)


# ---------------------------------------------------------------------------
# .mu text -> JsonWorld (very simple parser)
# ---------------------------------------------------------------------------


def parse_mu_line_to_rule(line: str) -> JsonRule | None:
    """
    Parse one line of .mu into a JsonRule.

    Supports lines like:
        [null,_]    -> ra
        [omega,_]   -> lobe
        [paradox,_] -> sink
    Ignores blank lines and comments starting with '#'.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    # Split on '->'
    if "->" not in line:
        raise ValueError(f"Not a rule line: {line!r}")

    left, right = line.split("->", 1)
    pattern = left.strip()
    action = right.strip()
    return JsonRule(pattern=pattern, action=action)


def load_world_from_mu(mu_path: str | Path) -> JsonWorld:
    """
    Load a .mu file into a JsonWorld.
    """
    p = Path(mu_path)
    rules: List[JsonRule] = []
    with p.open("r", encoding="utf-8") as f:
        for raw_line in f:
            raw_line = raw_line.rstrip("\n")
            if not raw_line.strip() or raw_line.lstrip().startswith("#"):
                continue
            rule = parse_mu_line_to_rule(raw_line)
            if rule is not None:
                rules.append(rule)
    return JsonWorld(rules=rules)


# ---------------------------------------------------------------------------
# CLI helper (optional)
# ---------------------------------------------------------------------------


def _main() -> None:
    """
    Simple CLI:

        python -m rcx_pi.worlds_json to-mu rcx_core.json mu_programs/rcx_core.mu
        python -m rcx_pi.worlds_json to-json mu_programs/rcx_core.mu rcx_core.json
    """
    import sys

    if len(sys.argv) < 4:
        print(
            "usage:\n"
            "  python -m rcx_pi.worlds_json to-mu   INPUT.json OUTPUT.mu\n"
            "  python -m rcx_pi.worlds_json to-json INPUT.mu   OUTPUT.json"
        )
        raise SystemExit(1)

    mode = sys.argv[1]
    inp = sys.argv[2]
    out = sys.argv[3]

    if mode == "to-mu":
        world = load_world_json(inp)
        save_world_as_mu(out, world)
        print(f"[worlds_json] wrote .mu world to {out}")
    elif mode == "to-json":
        world = load_world_from_mu(inp)
        save_world_json(out, world)
        print(f"[worlds_json] wrote JSON world to {out}")
    else:
        print(f"unknown mode {mode!r}")
        raise SystemExit(1)


if __name__ == "__main__":
    _main()
