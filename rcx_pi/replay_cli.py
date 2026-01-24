from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping

from rcx_pi.trace_canon import canon_event_json, canon_events


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    out: List[Dict[str, Any]] = []
    for idx, ln in enumerate(lines):
        if not ln.strip():
            continue
        try:
            obj = json.loads(ln)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}:{idx + 1}: invalid JSON: {e}") from e
        if not isinstance(obj, dict):
            raise ValueError(f"{path}:{idx + 1}: expected object/dict per line")
        out.append(obj)
    return out


def _canon_jsonl(events: List[Mapping[str, Any]]) -> str:
    # Enforces v1 contiguity rules via canon_events
    canon = canon_events(events)
    # Serialize canon events deterministically (top-level order already stabilized by canon_event)
    return "".join(canon_event_json(ev) + "\n" for ev in canon)


def replay_main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rcx replay", add_help=True)
    ap.add_argument("--trace", required=True, help="Input trace JSONL path")
    ap.add_argument(
        "--out",
        default=None,
        help="Optional output path to write canonicalized JSONL (artifact emit for skeleton)",
    )
    ap.add_argument(
        "--expect",
        default=None,
        help="Optional expected canonical JSONL path. If provided, mismatch => non-zero exit.",
    )
    ap.add_argument(
        "--check-canon",
        action="store_true",
        help="Fail if the input trace is not already canonical JSONL (byte-identical to canonical form).",
    )

    args = ap.parse_args(argv)

    trace_path = Path(args.trace)
    if not trace_path.exists():
        print(f"ERROR: missing --trace file: {trace_path}", file=sys.stderr)
        return 2

    try:
        raw_events = _read_jsonl(trace_path)
        canon_text = _canon_jsonl(raw_events)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    # Optional: enforce that input already equals canonical form
    if args.check_canon:
        original = trace_path.read_text(encoding="utf-8")
        if original != canon_text:
            print(
                "REPLAY_MISMATCH: input trace is not canonical (diff vs canonicalized form).",
                file=sys.stderr,
            )
            return 1

    # Optional: write canonical “artifact”
    if args.out:
        Path(args.out).write_text(canon_text, encoding="utf-8")

    # Optional: compare to expected canonical file
    if args.expect:
        exp_path = Path(args.expect)
        if not exp_path.exists():
            print(f"ERROR: missing --expect file: {exp_path}", file=sys.stderr)
            return 2
        expected = exp_path.read_text(encoding="utf-8")
        if expected != canon_text:
            print(
                "REPLAY_MISMATCH: canonical replay output differs from --expect.",
                file=sys.stderr,
            )
            return 1

    return 0
