"""
Report contract utilities.

We have two JSON "shapes" emitted by CLI tools:

1) trace_cli payload ("trace"):
   - has "steps": list[...]
   - usually also includes input/result motif-shaped JSON and stats

2) omega_cli payload ("omega"):
   - may NOT have "steps"
   - includes "classification" and/or other summary fields

Downstream tooling (analyze_cli) should accept BOTH without crashing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class ReportKind:
    kind: str  # "trace" | "omega" | "unknown"


def detect_kind(payload: Dict[str, Any]) -> ReportKind:
    # Trace payloads are stepful and must include steps as a list
    steps = payload.get("steps", None)
    if isinstance(steps, list):
        return ReportKind("trace")

    # Omega payloads are summary-shaped; typically include "classification"
    if isinstance(payload.get("classification", None), dict):
        return ReportKind("omega")

    # Otherwise unknown, but still structured JSON
    return ReportKind("unknown")


def extract_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a small, stable summary dict regardless of payload kind.
    This is meant for analyze_cli to print something useful without
    assuming the presence of steps.
    """
    kind = detect_kind(payload).kind
    out: Dict[str, Any] = {"kind": kind}

    # Prefer explicit stats if available
    if isinstance(payload.get("stats", None), dict):
        out["stats"] = payload["stats"]

    # Omega classification summary if present
    if isinstance(payload.get("classification", None), dict):
        out["classification"] = payload["classification"]

    # Trace: include step count
    if isinstance(payload.get("steps", None), list):
        out["steps"] = len(payload["steps"])

    # Echo input/result if they exist (motif-shaped or strings)
    if "input" in payload:
        out["input"] = payload["input"]
    if "result" in payload:
        out["result"] = payload["result"]

    return out
