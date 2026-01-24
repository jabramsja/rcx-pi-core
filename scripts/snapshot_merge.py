#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _uniq_sorted(xs: List[Any]) -> List[Any]:
    # deterministic: stringify for ordering, but keep original values
    seen = set()
    out = []
    for x in xs:
        key = json.dumps(x, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    out.sort(key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False))
    return out


def merge_snapshots(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    # hard compatibility checks (v1)
    for k in ("schema", "world"):
        if a.get(k) != b.get(k):
            raise ValueError(f"mismatch: {k}: {a.get(k)!r} vs {b.get(k)!r}")

    a_rules = (((a.get("program") or {}).get("rules")) or [])
    b_rules = (((b.get("program") or {}).get("rules")) or [])
    if a_rules != b_rules:
        raise ValueError("mismatch: program.rules (merge requires identical program rules in v1)")

    a_state = a.get("state") or {}
    b_state = b.get("state") or {}

    def get_list(st: Dict[str, Any], key: str) -> List[Any]:
        v = st.get(key)
        return list(v) if isinstance(v, list) else []

    merged_state: Dict[str, Any] = dict(a_state)  # base (doesn't matter much; we overwrite key fields)
    for key in ("ra", "lobes", "sink", "null_reg", "inf_reg"):
        merged_state[key] = _uniq_sorted(get_list(a_state, key) + get_list(b_state, key))

    # v1 rule: merged snapshot is a "fresh start" (not a stitched timeline)
    merged_state["current"] = None
    merged_state["trace"] = []
    merged_state["step_counter"] = 0

    out: Dict[str, Any] = {
        "schema": a["schema"],
        "world": a["world"],
        "program": {"rules": a_rules},
        "state": merged_state,
    }
    return out


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="Merge two rcx.snapshot.v1 JSON files deterministically (tool-layer).")
    ap.add_argument("a", type=Path)
    ap.add_argument("b", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    args = ap.parse_args(argv)

    a = _load_json(args.a)
    b = _load_json(args.b)

    try:
        merged = merge_snapshots(a, b)
    except Exception as e:
        print(f"snapshot-merge: error: {e}", file=sys.stderr)
        return 1

    _dump_json(merged, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
