"""
Rule Motifs v0 - Observability-only rule representations.

This module provides static rule motif definitions for all rules in rules_pure.py.
It emits rule.loaded v2 trace events. No execution semantics, no matching, no application.

See docs/RuleAsMotif.v0.md for the design specification.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List


# Canonical list of all rule IDs from rules_pure.py.
# This MUST be kept in sync with the actual rules.
# Tests verify this list matches emitted rule motifs.
RULE_IDS: tuple[str, ...] = (
    "add.zero",
    "add.succ",
    "mult.zero",
    "mult.succ",
    "pred.zero",
    "pred.succ",
    "activation",
    "classify",
)


def rule_motifs_v0() -> List[Dict[str, Any]]:
    """
    Return the complete list of rule motifs for all rules in rules_pure.py.

    This is a pure function with no side effects. Output is deterministic
    under PYTHONHASHSEED=0.

    Returns:
        List of rule motif dicts, one per rule.
    """
    return [
        # add.zero: 0 + b → b
        {
            "rule": {
                "id": "add.zero",
                "pattern": {
                    "op": "add",
                    "a": {"value": 0},
                    "b": {"var": "b"},
                },
                "body": {"var": "b"},
            }
        },
        # add.succ: succ(n) + b → succ(n + b)
        {
            "rule": {
                "id": "add.succ",
                "pattern": {
                    "op": "add",
                    "a": {"op": "succ", "n": {"var": "n"}},
                    "b": {"var": "b"},
                },
                "body": {
                    "op": "succ",
                    "n": {"op": "add", "a": {"var": "n"}, "b": {"var": "b"}},
                },
            }
        },
        # mult.zero: 0 * b → 0
        {
            "rule": {
                "id": "mult.zero",
                "pattern": {
                    "op": "mult",
                    "a": {"value": 0},
                    "b": {"var": "b"},
                },
                "body": {"value": 0},
            }
        },
        # mult.succ: succ(n) * b → b + (n * b)
        {
            "rule": {
                "id": "mult.succ",
                "pattern": {
                    "op": "mult",
                    "a": {"op": "succ", "n": {"var": "n"}},
                    "b": {"var": "b"},
                },
                "body": {
                    "op": "add",
                    "a": {"var": "b"},
                    "b": {"op": "mult", "a": {"var": "n"}, "b": {"var": "b"}},
                },
            }
        },
        # pred.zero: pred(0) → 0
        {
            "rule": {
                "id": "pred.zero",
                "pattern": {
                    "op": "pred",
                    "arg": {"value": 0},
                },
                "body": {"value": 0},
            }
        },
        # pred.succ: pred(succ(n)) → n
        {
            "rule": {
                "id": "pred.succ",
                "pattern": {
                    "op": "pred",
                    "arg": {"op": "succ", "n": {"var": "n"}},
                },
                "body": {"var": "n"},
            }
        },
        # activation: apply(closure(projection), arg) → projection(arg)
        {
            "rule": {
                "id": "activation",
                "pattern": {
                    "op": "activation",
                    "func": {"op": "closure", "projection": {"var": "proj"}},
                    "arg": {"var": "arg"},
                },
                "body": {
                    "op": "apply_projection",
                    "projection": {"var": "proj"},
                    "arg": {"var": "arg"},
                },
            }
        },
        # classify: classify(target) → tagged(target)
        {
            "rule": {
                "id": "classify",
                "pattern": {
                    "op": "classify",
                    "target": {"var": "target"},
                },
                "body": {
                    "op": "classify_result",
                    "target": {"var": "target"},
                },
            }
        },
    ]


def _deep_sort(obj: Any) -> Any:
    """Recursively sort dict keys for deterministic JSON output."""
    if isinstance(obj, dict):
        return {k: _deep_sort(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_deep_sort(item) for item in obj]
    return obj


def emit_rule_loaded_events() -> List[Dict[str, Any]]:
    """
    Generate rule.loaded v2 trace events for all rule motifs.

    Returns:
        List of v2 trace events with type "rule.loaded".
    """
    motifs = rule_motifs_v0()
    events = []
    for i, motif in enumerate(motifs):
        event = {
            "v": 2,
            "type": "rule.loaded",
            "i": i,
            "mu": _deep_sort(motif),
        }
        events.append(event)
    return events


def rules_main(argv: List[str] | None = None) -> int:
    """
    CLI entry point for rule motif commands.

    Usage:
        python3 -m rcx_pi.rcx_cli rules --print-rule-motifs
    """
    ap = argparse.ArgumentParser(prog="rcx rules", add_help=True)
    ap.add_argument(
        "--print-rule-motifs",
        action="store_true",
        help="Print rule.loaded v2 trace events as JSONL to stdout.",
    )

    args = ap.parse_args(argv)

    if args.print_rule_motifs:
        events = emit_rule_loaded_events()
        for event in events:
            # Deterministic JSON: sorted keys, compact separators
            print(json.dumps(event, sort_keys=True, separators=(",", ":")))
        return 0

    # No flag specified, show help
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(rules_main())
