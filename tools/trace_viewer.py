#!/usr/bin/env python3
"""
Simple Trace Viewer for RCX

Visualizes trace files in a readable format showing state transitions.

Usage:
    python tools/trace_viewer.py <trace.jsonl>
    python tools/trace_viewer.py <trace.jsonl> --compact
    python tools/trace_viewer.py <trace.jsonl> --filter step
"""

import argparse
import json
import sys
from pathlib import Path


def format_value(value, max_len=60):
    """Format a value for display, truncating if needed."""
    s = json.dumps(value, separators=(',', ':'))
    if len(s) > max_len:
        return s[:max_len-3] + "..."
    return s


def format_event(event, compact=False):
    """Format a trace event for display."""
    lines = []

    event_type = event.get("type", event.get("event", "unknown"))

    if compact:
        # Single line format
        if event_type == "trace.start":
            lines.append(f"▶ START: {format_value(event.get('initial_state', {}), 80)}")
        elif event_type == "step":
            before = format_value(event.get("before", {}), 40)
            after = format_value(event.get("after", {}), 40)
            changed = "→" if event.get("before") != event.get("after") else "="
            lines.append(f"  {before} {changed} {after}")
        elif event_type == "execution.stall":
            lines.append(f"⏸ STALL: pattern={event.get('pattern_id', '?')}")
        elif event_type == "execution.fix":
            lines.append(f"🔧 FIX: target={format_value(event.get('target', {}), 40)}")
        elif event_type == "execution.fixed":
            lines.append(f"✓ FIXED: result={format_value(event.get('result', {}), 40)}")
        elif event_type == "trace.end":
            lines.append(f"■ END: {format_value(event.get('final_state', {}), 80)}")
        else:
            lines.append(f"? {event_type}: {format_value(event, 60)}")
    else:
        # Multi-line format
        if event_type == "trace.start":
            lines.append("╔══════════════════════════════════════════════════════════════")
            lines.append("║ TRACE START")
            lines.append("╠══════════════════════════════════════════════════════════════")
            lines.append(f"║ Initial: {json.dumps(event.get('initial_state', {}), indent=2).replace(chr(10), chr(10) + '║ ')}")
            lines.append("╚══════════════════════════════════════════════════════════════")

        elif event_type == "step":
            step_num = event.get("step", "?")
            before = event.get("before", {})
            after = event.get("after", {})
            changed = before != after

            lines.append(f"┌─ Step {step_num} {'(changed)' if changed else '(unchanged)'}")
            lines.append(f"│ Before: {format_value(before, 70)}")
            lines.append(f"│ After:  {format_value(after, 70)}")
            lines.append("└─")

        elif event_type == "execution.stall":
            lines.append("┌─ STALL ⏸")
            lines.append(f"│ Value Hash: {event.get('value_hash', '?')}")
            lines.append(f"│ Pattern ID: {event.get('pattern_id', '?')}")
            lines.append("└─")

        elif event_type == "execution.fix":
            lines.append("┌─ FIX 🔧")
            lines.append(f"│ Target: {format_value(event.get('target', {}), 60)}")
            lines.append("└─")

        elif event_type == "execution.fixed":
            lines.append("┌─ FIXED ✓")
            lines.append(f"│ Result: {format_value(event.get('result', {}), 60)}")
            lines.append("└─")

        elif event_type == "trace.end":
            lines.append("╔══════════════════════════════════════════════════════════════")
            lines.append("║ TRACE END")
            lines.append("╠══════════════════════════════════════════════════════════════")
            lines.append(f"║ Final: {json.dumps(event.get('final_state', {}), indent=2).replace(chr(10), chr(10) + '║ ')}")
            lines.append("╚══════════════════════════════════════════════════════════════")

        elif event_type == "evidence.closure":
            lines.append("┌─ CLOSURE EVIDENCE 🎯")
            lines.append(f"│ Value Hash: {event.get('value_hash', '?')}")
            lines.append(f"│ Pattern ID: {event.get('pattern_id', '?')}")
            lines.append(f"│ Reason: {event.get('reason', '?')}")
            lines.append("└─")

        else:
            lines.append(f"┌─ {event_type}")
            lines.append(f"│ {json.dumps(event, indent=2).replace(chr(10), chr(10) + '│ ')}")
            lines.append("└─")

    return "\n".join(lines)


def view_trace(trace_path, compact=False, filter_type=None, limit=None):
    """View a trace file."""
    path = Path(trace_path)

    if not path.exists():
        print(f"Error: File not found: {trace_path}", file=sys.stderr)
        sys.exit(1)

    print(f"═══ Trace: {path.name} ═══\n")

    count = 0
    with open(path) as f:
        for line in f:
            if not line.strip():
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                print(f"Warning: Skipping invalid JSON line", file=sys.stderr)
                continue

            event_type = event.get("type", event.get("event", "unknown"))

            # Apply filter
            if filter_type and filter_type not in event_type:
                continue

            # Apply limit
            if limit and count >= limit:
                print(f"\n... (truncated at {limit} events)")
                break

            print(format_event(event, compact))
            count += 1

    print(f"\n═══ {count} events ═══")


def main():
    parser = argparse.ArgumentParser(description="RCX Trace Viewer")
    parser.add_argument("trace", help="Path to trace JSONL file")
    parser.add_argument("--compact", "-c", action="store_true",
                        help="Compact single-line output")
    parser.add_argument("--filter", "-f", type=str, default=None,
                        help="Filter to events containing this string")
    parser.add_argument("--limit", "-n", type=int, default=None,
                        help="Limit number of events shown")

    args = parser.parse_args()
    view_trace(args.trace, compact=args.compact, filter_type=args.filter, limit=args.limit)


if __name__ == "__main__":
    main()
