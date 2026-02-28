#!/usr/bin/env python3
"""Anti-Theater Ratchet Checker (MAINT-M2).

Compares current theater_risk classifier results against a curated allowlist.
Fails (exit 1) if:
  - New theater_risk methods appear that are not in the allowlist
  - Allowlist entries have expired (expires_on < today)
  - Allowlist entries are classified as "real" (must be fixed, not allowlisted)

Usage:
    python3 tools/checks/check_theater_risk_ratchet.py
    python3 tools/checks/check_theater_risk_ratchet.py --classifier-json /tmp/current.json
    python3 tools/checks/check_theater_risk_ratchet.py --allowlist path/to/allowlist.json
    python3 tools/checks/check_theater_risk_ratchet.py --update-allowlist
    python3 tools/checks/check_theater_risk_ratchet.py --json
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, datetime
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
DEFAULT_ALLOWLIST = REPO_ROOT / "tools" / "checks" / "theater_allowlist.json"
CLASSIFIER_SCRIPT = REPO_ROOT / "tools" / "checks" / "check_gate_behavioral_pairs.py"

VALID_CLASSIFICATIONS = frozenset({"heuristic_false_positive", "uncertain"})
REQUIRED_ENTRY_FIELDS = frozenset({
    "file", "class", "method", "classification",
    "defer_reason", "owner", "expires_on", "target_wave",
})


# ---------------------------------------------------------------------------
# Allowlist loading + validation
# ---------------------------------------------------------------------------

def validate_allowlist(data: dict) -> list[str]:
    """Validate allowlist schema strictly.  Returns list of errors (empty = valid)."""
    errors: list[str] = []

    if data.get("schema_version") != 1:
        errors.append(f"schema_version must be 1, got {data.get('schema_version')!r}")

    entries = data.get("entries")
    if not isinstance(entries, list):
        errors.append("'entries' must be a list")
        return errors

    seen: set[tuple[str, str, str]] = set()
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"entries[{i}]: must be a dict")
            continue

        # Required fields
        missing = REQUIRED_ENTRY_FIELDS - set(entry.keys())
        if missing:
            errors.append(f"entries[{i}]: missing fields: {sorted(missing)}")
            continue

        # Classification enum
        cls = entry["classification"]
        if cls == "real":
            errors.append(
                f"entries[{i}]: classification 'real' is forbidden in allowlist "
                f"(must be fixed, not allowlisted): "
                f"{entry['file']}::{entry['class']}::{entry['method']}"
            )
        elif cls not in VALID_CLASSIFICATIONS:
            errors.append(
                f"entries[{i}]: classification must be one of "
                f"{sorted(VALID_CLASSIFICATIONS)}, got {cls!r}"
            )

        # Path validation
        file_path = entry["file"]
        normalized = Path(file_path).as_posix()
        if ".." in Path(file_path).parts:
            errors.append(f"entries[{i}]: path traversal (..) forbidden: {file_path!r}")
        elif not normalized.startswith("mu/tests/"):
            errors.append(f"entries[{i}]: file must start with 'mu/tests/', got {file_path!r}")

        # Duplicate check
        key = (entry["file"], entry["class"], entry["method"])
        if key in seen:
            errors.append(f"entries[{i}]: duplicate entry: {key}")
        seen.add(key)

    return errors


def load_allowlist(path: Path) -> dict:
    """Load and validate allowlist.  Exits on schema errors."""
    if not path.exists():
        print(f"ERROR: Allowlist not found: {path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(path.read_text())
    errors = validate_allowlist(data)
    if errors:
        print("ERROR: Allowlist schema validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)

    return data


# ---------------------------------------------------------------------------
# Classifier results — loading + strict schema validation
# ---------------------------------------------------------------------------

# Minimum number of scanned methods to accept (zero-scan guard)
MIN_CLASSIFIER_METHODS = 10

VALID_CLASSIFIER_CATEGORIES = frozenset({
    "behavioral", "source_lock", "hybrid", "theater_risk",
})


def validate_classifier_results(data: object) -> list[str]:
    """Validate classifier JSON schema strictly.  Returns list of errors."""
    errors: list[str] = []

    if not isinstance(data, dict):
        return [f"classifier payload must be a dict, got {type(data).__name__}"]

    # Top-level keys
    if "files" not in data:
        errors.append("classifier payload missing required key: 'files'")
    if "summary" not in data:
        errors.append("classifier payload missing required key: 'summary'")

    files = data.get("files")
    if not isinstance(files, dict):
        errors.append(f"'files' must be a dict, got {type(files).__name__}")
        return errors  # Can't continue without files

    total_methods = 0
    for filepath, file_data in files.items():
        if not isinstance(file_data, dict):
            errors.append(f"files[{filepath!r}]: must be a dict")
            continue
        classes = file_data.get("classes")
        if not isinstance(classes, dict):
            errors.append(f"files[{filepath!r}]: 'classes' must be a dict")
            continue
        for class_name, methods in classes.items():
            if not isinstance(methods, dict):
                errors.append(
                    f"files[{filepath!r}].classes[{class_name!r}]: must be a dict"
                )
                continue
            for method_name, classification in methods.items():
                total_methods += 1
                if not method_name.startswith("test_"):
                    errors.append(
                        f"method name must start with 'test_': "
                        f"{filepath}::{class_name}::{method_name}"
                    )
                if classification not in VALID_CLASSIFIER_CATEGORIES:
                    errors.append(
                        f"unknown classification {classification!r} for "
                        f"{filepath}::{class_name}::{method_name}"
                    )

    # Zero-scan guard
    if total_methods < MIN_CLASSIFIER_METHODS:
        errors.append(
            f"zero-scan guard: classifier reports {total_methods} methods "
            f"(minimum {MIN_CLASSIFIER_METHODS}). Likely malformed payload."
        )

    return errors


def load_classifier_results(json_path: Path | None) -> dict:
    """Load classifier JSON, either from file or by invoking the classifier."""
    if json_path is not None:
        data = json.loads(json_path.read_text())
    else:
        result = subprocess.run(
            [sys.executable, str(CLASSIFIER_SCRIPT), "--json"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        if result.returncode != 0:
            print(f"ERROR: Classifier failed:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)
        data = json.loads(result.stdout)

    errors = validate_classifier_results(data)
    if errors:
        print("ERROR: Classifier payload validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)

    return data


def extract_theater_risk_set(classifier: dict) -> set[tuple[str, str, str]]:
    """Extract (file, class, method) tuples for all theater_risk methods."""
    items: set[tuple[str, str, str]] = set()
    for filepath, file_data in classifier.get("files", {}).items():
        for class_name, methods in file_data.get("classes", {}).items():
            for method_name, classification in methods.items():
                if classification == "theater_risk":
                    items.add((filepath, class_name, method_name))
    return items


# ---------------------------------------------------------------------------
# Ratchet comparison
# ---------------------------------------------------------------------------

def check_ratchet(current: set[tuple[str, str, str]], allowlist: dict) -> dict:
    """Compare current theater_risk set vs allowlist.

    Returns dict with: new, expired, removals, real, passed.
    """
    today = date.today()

    allowlist_set: set[tuple[str, str, str]] = set()
    expired: list[dict] = []
    real: list[dict] = []

    for entry in allowlist.get("entries", []):
        key = (entry["file"], entry["class"], entry["method"])
        allowlist_set.add(key)

        # Check expiry
        try:
            exp = date.fromisoformat(entry["expires_on"])
            if exp < today:
                expired.append(entry)
        except (ValueError, KeyError):
            expired.append(entry)

        # Defense-in-depth: classification "real" (should be caught by validation)
        if entry.get("classification") == "real":
            real.append(entry)

    new_items = sorted(current - allowlist_set)
    removals = sorted(allowlist_set - current)

    passed = len(new_items) == 0 and len(expired) == 0 and len(real) == 0

    return {
        "new": [{"file": f, "class": c, "method": m} for f, c, m in new_items],
        "expired": expired,
        "removals": [{"file": f, "class": c, "method": m} for f, c, m in removals],
        "real": real,
        "passed": passed,
        "current_count": len(current),
        "allowlist_count": len(allowlist_set),
    }


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_human(result: dict) -> str:
    """Format ratchet result for human-readable output."""
    lines = ["=== Anti-Theater Ratchet Check ===", ""]
    lines.append(f"Current theater_risk: {result['current_count']}")
    lines.append(f"Allowlist entries:    {result['allowlist_count']}")
    lines.append("")

    if result["new"]:
        lines.append(f"NEW (unallowlisted) — {len(result['new'])} method(s):")
        for item in result["new"]:
            lines.append(f"  {item['file']}::{item['class']}::{item['method']}")
        lines.append("")

    if result["expired"]:
        lines.append(f"EXPIRED — {len(result['expired'])} entry/entries:")
        for item in result["expired"]:
            lines.append(
                f"  {item['file']}::{item['class']}::{item['method']} "
                f"(expired {item.get('expires_on', '?')})"
            )
        lines.append("")

    if result["real"]:
        lines.append(f"REAL (must fix) — {len(result['real'])} entry/entries:")
        for item in result["real"]:
            lines.append(f"  {item['file']}::{item['class']}::{item['method']}")
        lines.append("")

    if result["removals"]:
        lines.append(f"REMOVALS (good delta) — {len(result['removals'])} entry/entries:")
        for item in result["removals"]:
            lines.append(f"  {item['file']}::{item['class']}::{item['method']}")
        lines.append("")

    if result["passed"]:
        lines.append("PASS: No new unallowlisted theater_risk, no expired, no real.")
    else:
        reasons = []
        if result["new"]:
            reasons.append(f"{len(result['new'])} new unallowlisted")
        if result["expired"]:
            reasons.append(f"{len(result['expired'])} expired")
        if result["real"]:
            reasons.append(f"{len(result['real'])} real")
        lines.append(f"FAIL: {', '.join(reasons)}.")

    return "\n".join(lines)


def format_json(result: dict) -> str:
    """Format ratchet result as deterministic JSON."""
    return json.dumps(result, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# Update allowlist (normalize-only)
# ---------------------------------------------------------------------------

def update_allowlist(
    current: set[tuple[str, str, str]],
    allowlist: dict,
    output_path: Path,
) -> None:
    """Normalize-only: sort existing entries, remove stale ones.

    Does NOT auto-add new methods — those must be manually triaged.
    """
    kept: list[dict] = []
    removed: list[tuple[str, str, str]] = []

    for entry in allowlist.get("entries", []):
        key = (entry["file"], entry["class"], entry["method"])
        if key in current:
            kept.append(entry)
        else:
            removed.add(key) if False else removed.append(key)

    # Sort by (file, class, method)
    kept.sort(key=lambda e: (e["file"], e["class"], e["method"]))

    output = {
        "schema_version": 1,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_theater_risk": len(kept),
        "entries": kept,
    }

    output_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")

    print(f"Updated allowlist: {output_path}")
    print(f"  Kept:    {len(kept)}")
    print(f"  Removed: {len(removed)}")
    if removed:
        for f, c, m in sorted(removed):
            print(f"    - {f}::{c}::{m}")

    new_in_current = current - {(e["file"], e["class"], e["method"]) for e in kept}
    if new_in_current:
        print(f"\n  {len(new_in_current)} new theater_risk method(s) NOT added "
              "(must be manually triaged):")
        for f, c, m in sorted(new_in_current):
            print(f"    + {f}::{c}::{m}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]
    json_mode = "--json" in args
    do_update = "--update-allowlist" in args

    # Parse --classifier-json
    classifier_json_path: Path | None = None
    if "--classifier-json" in args:
        idx = args.index("--classifier-json")
        if idx + 1 >= len(args):
            print("ERROR: --classifier-json requires a path argument", file=sys.stderr)
            sys.exit(2)
        classifier_json_path = Path(args[idx + 1])

    # Parse --allowlist
    allowlist_path = DEFAULT_ALLOWLIST
    if "--allowlist" in args:
        idx = args.index("--allowlist")
        if idx + 1 >= len(args):
            print("ERROR: --allowlist requires a path argument", file=sys.stderr)
            sys.exit(2)
        allowlist_path = Path(args[idx + 1])

    # Safety guard: --update-allowlist blocked in CI
    if do_update and os.environ.get("RCX_CI") == "1":
        print("ERROR: --update-allowlist is forbidden in CI (RCX_CI=1)", file=sys.stderr)
        sys.exit(1)

    # Load data
    allowlist = load_allowlist(allowlist_path)
    classifier = load_classifier_results(classifier_json_path)
    current = extract_theater_risk_set(classifier)

    if do_update:
        update_allowlist(current, allowlist, allowlist_path)
        return

    # Ratchet check
    result = check_ratchet(current, allowlist)

    if json_mode:
        print(format_json(result))
    else:
        print(format_human(result))

    if not result["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
