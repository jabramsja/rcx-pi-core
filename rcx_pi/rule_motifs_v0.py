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
from typing import Any, Dict, List, Set


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
        return {k: _deep_sort(v) for k, v in sorted(obj.items())}  # AST_OK: infra
    if isinstance(obj, list):
        return [_deep_sort(item) for item in obj]  # AST_OK: infra
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


def _collect_var_names(obj: Any, found: Set[str]) -> None:
    """Recursively collect variable names from a motif structure."""
    if isinstance(obj, dict):
        # Check if this is a variable site: exactly {"var": "<name>"}
        if set(obj.keys()) == {"var"} and isinstance(obj.get("var"), str):
            found.add(obj["var"])
        else:
            for v in obj.values():
                _collect_var_names(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _collect_var_names(item, found)


def _check_json_types(obj: Any, path: str = "") -> List[str]:
    """Check that obj uses only JSON-compatible types recursively."""
    errors = []
    if obj is None:
        pass
    elif isinstance(obj, bool):
        pass
    elif isinstance(obj, int):
        pass
    elif isinstance(obj, float):
        pass
    elif isinstance(obj, str):
        pass
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                errors.append(f"{path}: dict key {k!r} is not a string")
            errors.extend(_check_json_types(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            errors.extend(_check_json_types(item, f"{path}[{i}]"))
    else:
        errors.append(f"{path}: value {type(obj).__name__} is not JSON-compatible")
    return errors


def validate_rule_motifs_v0(rule_motifs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate a list of rule motifs against v0 invariants.

    This is a pure function with deterministic output under PYTHONHASHSEED=0.

    Validation rules:
    - Structure: each motif must be {"rule":{"id":str,"pattern":<motif>,"body":<motif>}}
    - rule.id: non-empty string, unique across the set
    - Variables: every var referenced in body must be bound in pattern
    - Host leakage guard: reject non-JSON-serializable values
    - Canonicalization guard: json.dumps must be stable

    Args:
        rule_motifs: List of rule motif dicts to validate.

    Returns:
        A deterministic report dict:
        {
            "v": 1,
            "rule_count": N,
            "ok": true/false,
            "errors": [{"rule_id": "...", "code": "...", "detail": "..."} ...]
        }
    """
    errors: List[Dict[str, str]] = []
    seen_ids: Set[str] = set()

    for idx, motif in enumerate(rule_motifs):
        rule_id = f"<index:{idx}>"

        # Structure check: must have "rule" key
        if not isinstance(motif, dict):
            errors.append({
                "rule_id": rule_id,
                "code": "INVALID_STRUCTURE",
                "detail": f"motif is not a dict, got {type(motif).__name__}",
            })
            continue

        if "rule" not in motif:
            errors.append({
                "rule_id": rule_id,
                "code": "MISSING_RULE_KEY",
                "detail": "motif missing 'rule' key",
            })
            continue

        rule = motif["rule"]
        if not isinstance(rule, dict):
            errors.append({
                "rule_id": rule_id,
                "code": "INVALID_RULE_TYPE",
                "detail": f"'rule' is not a dict, got {type(rule).__name__}",
            })
            continue

        # Check required fields
        if "id" not in rule:
            errors.append({
                "rule_id": rule_id,
                "code": "MISSING_ID",
                "detail": "rule missing 'id' field",
            })
        else:
            rid = rule["id"]
            if not isinstance(rid, str) or rid == "":
                errors.append({
                    "rule_id": rule_id,
                    "code": "INVALID_ID",
                    "detail": f"rule.id must be non-empty string, got {rid!r}",
                })
            else:
                rule_id = rid
                if rid in seen_ids:
                    errors.append({
                        "rule_id": rule_id,
                        "code": "DUPLICATE_ID",
                        "detail": f"rule.id '{rid}' appears more than once",
                    })
                seen_ids.add(rid)

        if "pattern" not in rule:
            errors.append({
                "rule_id": rule_id,
                "code": "MISSING_PATTERN",
                "detail": "rule missing 'pattern' field",
            })

        if "body" not in rule:
            errors.append({
                "rule_id": rule_id,
                "code": "MISSING_BODY",
                "detail": "rule missing 'body' field",
            })

        # If we have both pattern and body, check variable binding
        if "pattern" in rule and "body" in rule:
            pattern_vars: Set[str] = set()
            body_vars: Set[str] = set()
            _collect_var_names(rule["pattern"], pattern_vars)
            _collect_var_names(rule["body"], body_vars)

            unbound = body_vars - pattern_vars
            if unbound:
                errors.append({
                    "rule_id": rule_id,
                    "code": "UNBOUND_VAR",
                    "detail": f"body references unbound vars: {sorted(unbound)}",
                })

        # Host leakage guard: check JSON-compatible types
        type_errors = _check_json_types(motif, "motif")
        for te in type_errors:
            errors.append({
                "rule_id": rule_id,
                "code": "HOST_LEAKAGE",
                "detail": te,
            })

        # Host leakage guard: try json.dumps
        try:
            json.dumps(motif, sort_keys=True)
        except TypeError as e:
            errors.append({
                "rule_id": rule_id,
                "code": "NOT_JSON_SERIALIZABLE",
                "detail": str(e),
            })

        # Canonicalization guard: ensure stable output
        try:
            s1 = json.dumps(motif, sort_keys=True, separators=(",", ":"))
            s2 = json.dumps(motif, sort_keys=True, separators=(",", ":"))
            if s1 != s2:
                errors.append({
                    "rule_id": rule_id,
                    "code": "CANONICALIZATION_UNSTABLE",
                    "detail": "json.dumps produced different output on repeated calls",
                })
        except TypeError:
            pass  # Already caught above

    # Sort errors deterministically
    errors.sort(key=lambda e: (e["rule_id"], e["code"], e["detail"]))  # AST_OK: infra

    return {
        "v": 1,
        "rule_count": len(rule_motifs),
        "ok": len(errors) == 0,
        "errors": errors,
    }


def rules_main(argv: List[str] | None = None) -> int:
    """
    CLI entry point for rule motif commands.

    Usage:
        python3 -m rcx_pi.rcx_cli rules --print-rule-motifs
        python3 -m rcx_pi.rcx_cli rules --check-rule-motifs
        python3 -m rcx_pi.rcx_cli rules --check-rule-motifs-from <path>
    """
    ap = argparse.ArgumentParser(prog="rcx rules", add_help=True)
    ap.add_argument(
        "--print-rule-motifs",
        action="store_true",
        help="Print rule.loaded v2 trace events as JSONL to stdout.",
    )
    ap.add_argument(
        "--check-rule-motifs",
        action="store_true",
        help="Validate built-in rule motifs and print validation report.",
    )
    ap.add_argument(
        "--check-rule-motifs-from",
        metavar="PATH",
        help="Validate rule motifs from a JSON file and print validation report.",
    )

    args = ap.parse_args(argv)

    if args.print_rule_motifs:
        events = emit_rule_loaded_events()
        for event in events:
            # Deterministic JSON: sorted keys, compact separators
            print(json.dumps(event, sort_keys=True, separators=(",", ":")))
        return 0

    if args.check_rule_motifs:
        motifs = rule_motifs_v0()
        report = validate_rule_motifs_v0(motifs)
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
        return 0 if report["ok"] else 1

    if args.check_rule_motifs_from:
        path = args.check_rule_motifs_from
        try:
            with open(path, "r", encoding="utf-8") as f:
                motifs = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            report = {
                "v": 1,
                "rule_count": 0,
                "ok": False,
                "errors": [{"rule_id": "<file>", "code": "LOAD_ERROR", "detail": str(e)}],
            }
            print(json.dumps(report, sort_keys=True, separators=(",", ":")))
            return 1
        if not isinstance(motifs, list):
            report = {
                "v": 1,
                "rule_count": 0,
                "ok": False,
                "errors": [{"rule_id": "<file>", "code": "INVALID_FORMAT", "detail": "expected JSON array"}],
            }
            print(json.dumps(report, sort_keys=True, separators=(",", ":")))
            return 1
        report = validate_rule_motifs_v0(motifs)
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
        return 0 if report["ok"] else 1

    # No flag specified, show help
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(rules_main())
