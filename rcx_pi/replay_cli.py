from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping

from rcx_pi.trace_canon import canon_event_json, canon_events

# v2 execution event types
_EXECUTION_STALL = "execution.stall"
_EXECUTION_FIX = "execution.fix"
_EXECUTION_FIXED = "execution.fixed"


def _validate_v2_execution_sequence(events: List[Dict[str, Any]]) -> None:
    """
    Validate v2 execution event sequence (trace-consumption only).

    Rules:
    - execution.stall: must not already be stalled (no double stall)
    - execution.fix (optional): must follow stall, target_hash must match value_hash
    - execution.fixed: must follow stall (with or without explicit fix)
    - execution.fixed before_hash must match stall value_hash
    - Stall without fixed before trace end is valid (normal form termination)

    Raises ValueError on invalid sequence.
    """
    # Check if any v2 execution events exist
    exec_events = [e for e in events if e.get("type", "").startswith("execution.")]
    if not exec_events:
        return  # No v2 execution events, nothing to validate

    # State machine: track stall/fix state
    is_stalled = False
    stall_value_hash: str | None = None
    has_pending_fix = False  # explicit fix event seen, awaiting fixed

    for ev in events:
        ev_type = ev.get("type", "")
        ev_idx = ev.get("i", "?")

        if ev_type == _EXECUTION_STALL:
            if is_stalled:
                raise ValueError(
                    f"execution.stall at i={ev_idx}: already stalled (double stall)"
                )
            mu = ev.get("mu", {})
            if not isinstance(mu, dict):
                raise ValueError(
                    f"execution.stall at i={ev_idx}: mu must be object"
                )
            stall_value_hash = mu.get("value_hash")
            if not stall_value_hash:
                raise ValueError(
                    f"execution.stall at i={ev_idx}: missing mu.value_hash"
                )
            is_stalled = True
            has_pending_fix = False

        elif ev_type == _EXECUTION_FIX:
            # execution.fix is optional but if present must be valid
            if not is_stalled:
                raise ValueError(
                    f"execution.fix at i={ev_idx}: not stalled (fix without stall)"
                )
            if has_pending_fix:
                raise ValueError(
                    f"execution.fix at i={ev_idx}: already have pending fix"
                )
            mu = ev.get("mu", {})
            if not isinstance(mu, dict):
                raise ValueError(
                    f"execution.fix at i={ev_idx}: mu must be object"
                )
            target_hash = mu.get("target_hash")
            if target_hash != stall_value_hash:
                raise ValueError(
                    f"execution.fix at i={ev_idx}: target_hash mismatch "
                    f"(expected {stall_value_hash}, got {target_hash})"
                )
            has_pending_fix = True

        elif ev_type == _EXECUTION_FIXED:
            # execution.fixed must follow stall (with or without explicit fix)
            if not is_stalled:
                raise ValueError(
                    f"execution.fixed at i={ev_idx}: not stalled (fixed without stall)"
                )
            # Validate before_hash matches stall value_hash
            mu = ev.get("mu", {})
            if isinstance(mu, dict):
                before_hash = mu.get("before_hash")
                if before_hash and before_hash != stall_value_hash:
                    raise ValueError(
                        f"execution.fixed at i={ev_idx}: before_hash mismatch "
                        f"(expected {stall_value_hash}, got {before_hash})"
                    )
            # Transition back to active
            is_stalled = False
            stall_value_hash = None
            has_pending_fix = False

    # End of trace: stalled with no fixed is valid (normal form termination)
    # But if we have a pending explicit fix without fixed, that's suspicious
    # (we allow it for now since the fix might be deferred)


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

        # Validate v2 execution event sequence (if present)
        try:
            _validate_v2_execution_sequence(raw_events)
        except ValueError as e:
            print(f"REPLAY_EXECUTION_ERROR: {e}", file=sys.stderr)
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


def main(argv: list[str] | None = None) -> int:
    """Module entrypoint for `python -m rcx_pi.replay_cli`.

    We delegate to replay_main() to keep rcx_cli routing stable.
    argparse prints help by raising SystemExit(0); convert that to rc=0.
    """
    try:
        return replay_main(argv)
    except SystemExit as e:
        code = e.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
