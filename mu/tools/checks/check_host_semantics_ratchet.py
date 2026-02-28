#!/usr/bin/env python3
"""Host-Semantics Ratchet Checker (A20.3).

Scans Python and JavaScript runtime surfaces for @host_* markers.
Counts per category per substrate and compares to a baseline.
Fails (exit 1) if any count INCREASES vs baseline (ratchet: can only decrease).

Fail-closed on:
  - Invalid baseline schema
  - Zero markers found (path failure)
  - Scan surface below minimum threshold

Usage:
    python3 tools/checks/check_host_semantics_ratchet.py
    python3 tools/checks/check_host_semantics_ratchet.py --json
    python3 tools/checks/check_host_semantics_ratchet.py --baseline path/to/baseline.json
    python3 tools/checks/check_host_semantics_ratchet.py --update-baseline
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


def _find_repo_root() -> Path:
    """Find repo root by searching upward for pyproject.toml."""
    d = Path(__file__).resolve().parent
    for _ in range(10):
        if (d / "pyproject.toml").is_file():
            return d
        d = d.parent
    raise RuntimeError("Cannot find repo root (no pyproject.toml)")


REPO_ROOT = _find_repo_root()
DEFAULT_BASELINE = REPO_ROOT / "tools" / "checks" / "host_semantics_baseline.json"

# Scan surfaces
PY_RUNTIME_DIR = REPO_ROOT / "rcx_pi" / "selfhost"
JS_RUNTIME_DIR = REPO_ROOT / "mu" / "host" / "js"

# Marker patterns
PY_DECORATOR_RE = re.compile(r"""^\s*@(host_\w+)\(""")
PY_INLINE_RE = re.compile(r"""#\s*@(host_\w+)""")
JS_MARKER_RE = re.compile(r"""(?://|\*)\s*@(host_\w+)""")

# Valid categories
VALID_CATEGORIES = frozenset({
    "host_iteration", "host_recursion", "host_builtin", "host_mutation",
})

# Minimum scan thresholds (fail-closed on truncated/missing surface)
MIN_PY_MARKERS = 3
MIN_JS_MARKERS = 3
MIN_TOTAL_MARKERS = 10


# ---------------------------------------------------------------------------
# Baseline loading + validation
# ---------------------------------------------------------------------------

def validate_baseline(data: object) -> list[str]:
    """Validate baseline schema. Returns list of errors (empty = valid)."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f"baseline must be a dict, got {type(data).__name__}"]
    if data.get("schema_version") != 1:
        errors.append(f"schema_version must be 1, got {data.get('schema_version')}")
    counts = data.get("counts")
    if not isinstance(counts, dict):
        errors.append(f"'counts' must be a dict, got {type(counts).__name__}")
        return errors
    for substrate in ("python", "javascript"):
        sub_counts = counts.get(substrate)
        if not isinstance(sub_counts, dict):
            errors.append(f"counts.{substrate} must be a dict")
            continue
        for cat, val in sub_counts.items():
            if cat not in VALID_CATEGORIES:
                errors.append(f"counts.{substrate}.{cat}: unknown category")
            if not isinstance(val, int) or val < 0:
                errors.append(f"counts.{substrate}.{cat}: must be non-negative int, got {val}")
    return errors


def load_baseline(path: Path) -> dict:
    """Load and validate baseline. Exits on schema errors."""
    if not path.is_file():
        print(f"ERROR: Baseline not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(path.read_text())
    errors = validate_baseline(data)
    if errors:
        print("ERROR: Baseline schema validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)
    return data


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def _collect_py_files() -> list[Path]:
    """Collect Python runtime files."""
    if not PY_RUNTIME_DIR.is_dir():
        return []
    return sorted(PY_RUNTIME_DIR.glob("*.py"))


def _collect_js_files() -> list[Path]:
    """Collect JS runtime files (excluding tests)."""
    if not JS_RUNTIME_DIR.is_dir():
        return []
    files = sorted(JS_RUNTIME_DIR.rglob("*.js"))
    return [f for f in files if "/tests/" not in str(f)]


def scan_markers(py_files: list[Path], js_files: list[Path]) -> dict[str, dict[str, int]]:
    """Scan runtime files for @host_* markers.

    Returns {"python": {cat: count, ...}, "javascript": {cat: count, ...}}.
    """
    py_counts: dict[str, int] = {cat: 0 for cat in sorted(VALID_CATEGORIES)}
    js_counts: dict[str, int] = {cat: 0 for cat in sorted(VALID_CATEGORIES)}

    for fpath in py_files:
        try:
            lines = fpath.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line in lines:
            # Decorators
            m = PY_DECORATOR_RE.search(line)
            if m and m.group(1) in VALID_CATEGORIES:
                py_counts[m.group(1)] += 1
                continue
            # Inline comments
            m = PY_INLINE_RE.search(line)
            if m and m.group(1) in VALID_CATEGORIES:
                py_counts[m.group(1)] += 1

    for fpath in js_files:
        try:
            lines = fpath.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line in lines:
            m = JS_MARKER_RE.search(line)
            if m and m.group(1) in VALID_CATEGORIES:
                js_counts[m.group(1)] += 1

    return {"python": py_counts, "javascript": js_counts}


# ---------------------------------------------------------------------------
# Ratchet logic
# ---------------------------------------------------------------------------

def check_ratchet(current: dict[str, dict[str, int]], baseline: dict) -> dict:
    """Compare current counts vs baseline.

    Returns dict with: increases, decreases, current, baseline_counts, passed.
    Fails if any count INCREASES (ratchet: can only decrease).
    """
    baseline_counts = baseline.get("counts", {})
    increases: list[dict] = []
    decreases: list[dict] = []

    for substrate in ("python", "javascript"):
        curr_sub = current.get(substrate, {})
        base_sub = baseline_counts.get(substrate, {})
        for cat in sorted(VALID_CATEGORIES):
            curr_val = curr_sub.get(cat, 0)
            base_val = base_sub.get(cat, 0)
            if curr_val > base_val:
                increases.append({
                    "substrate": substrate,
                    "category": cat,
                    "baseline": base_val,
                    "current": curr_val,
                    "delta": curr_val - base_val,
                })
            elif curr_val < base_val:
                decreases.append({
                    "substrate": substrate,
                    "category": cat,
                    "baseline": base_val,
                    "current": curr_val,
                    "delta": base_val - curr_val,
                })

    return {
        "increases": increases,
        "decreases": decreases,
        "current": current,
        "baseline_counts": baseline_counts,
        "passed": len(increases) == 0,
    }


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_human(result: dict, py_count: int, js_count: int) -> str:
    """Format result for human output."""
    lines = []
    lines.append(f"Scanned: {py_count} Python + {js_count} JS markers")

    for substrate in ("python", "javascript"):
        curr = result["current"].get(substrate, {})
        base = result["baseline_counts"].get(substrate, {})
        lines.append(f"  {substrate}:")
        for cat in sorted(VALID_CATEGORIES):
            c = curr.get(cat, 0)
            b = base.get(cat, 0)
            delta = c - b
            marker = ""
            if delta > 0:
                marker = f" (+{delta} INCREASE)"
            elif delta < 0:
                marker = f" ({delta} decrease)"
            lines.append(f"    {cat}: {c} (baseline: {b}){marker}")

    if result["passed"]:
        lines.append("PASS: No host-semantics footprint increase detected.")
    else:
        lines.append(f"FAIL: {len(result['increases'])} category increase(s) detected:")
        for inc in result["increases"]:
            lines.append(
                f"  {inc['substrate']}.{inc['category']}: "
                f"{inc['baseline']} → {inc['current']} (+{inc['delta']})"
            )
    return "\n".join(lines)


def format_json(result: dict) -> str:
    """Format result as JSON."""
    return json.dumps(result, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# Update mode
# ---------------------------------------------------------------------------

def update_baseline(current: dict[str, dict[str, int]], output_path: Path) -> None:
    """Write current counts as new baseline."""
    total_py = sum(current.get("python", {}).values())
    total_js = sum(current.get("javascript", {}).values())
    out = {
        "schema_version": 1,
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "counts": current,
        "total_python": total_py,
        "total_javascript": total_js,
        "total": total_py + total_js,
    }
    output_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"Baseline written to {output_path}")
    print(f"  Python: {total_py}  JavaScript: {total_js}  Total: {total_py + total_js}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Host-semantics ratchet checker")
    parser.add_argument("--json", action="store_true", help="JSON output mode")
    parser.add_argument("--baseline", type=str, default=None, help="Custom baseline path")
    parser.add_argument("--update-baseline", action="store_true", help="Write current as baseline")
    args = parser.parse_args()

    # Block --update-baseline in CI
    if args.update_baseline and os.environ.get("RCX_CI") == "1":
        print("ERROR: --update-baseline is forbidden in CI", file=sys.stderr)
        sys.exit(1)

    # Collect files
    py_files = _collect_py_files()
    js_files = _collect_js_files()

    # Scan
    current = scan_markers(py_files, js_files)
    total_py = sum(current["python"].values())
    total_js = sum(current["javascript"].values())

    # Zero-scan guard
    if total_py < MIN_PY_MARKERS:
        print(
            f"ERROR: zero-scan guard: found {total_py} Python markers "
            f"(expected >= {MIN_PY_MARKERS}). Path failure?",
            file=sys.stderr,
        )
        sys.exit(1)
    if total_js < MIN_JS_MARKERS:
        print(
            f"ERROR: zero-scan guard: found {total_js} JS markers "
            f"(expected >= {MIN_JS_MARKERS}). Path failure?",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.update_baseline:
        bl_path = Path(args.baseline) if args.baseline else DEFAULT_BASELINE
        update_baseline(current, bl_path)
        return

    # Load baseline
    bl_path = Path(args.baseline) if args.baseline else DEFAULT_BASELINE
    baseline = load_baseline(bl_path)

    # Ratchet check
    result = check_ratchet(current, baseline)

    if args.json:
        print(format_json(result))
    else:
        print(format_human(result, total_py, total_js))

    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
