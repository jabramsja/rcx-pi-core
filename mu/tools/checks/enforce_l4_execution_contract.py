#!/usr/bin/env python3
"""
Enforce L4 Execution Contract wave classification.

Checks that waves claiming L4 progress have appropriate runtime deltas,
and maintenance waves don't touch runtime files.

Usage:
    python tools/checks/enforce_l4_execution_contract.py --staged
    python tools/checks/enforce_l4_execution_contract.py --range origin/dev...HEAD
    python tools/checks/enforce_l4_execution_contract.py --files f1 f2 ...
    python tools/checks/enforce_l4_execution_contract.py --wave-class L4_CLASS_A --files f1 f2 ...

Exit codes:
    0 -> compliant (or no wave class marker found)
    1 -> violation
    2 -> usage error
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Runtime/substrate directories that L4_CLASS_A must touch
RUNTIME_DIRS = (
    "mu/host/",
    "mu/substrate/",
    "mu/closures/",
    "mu/bridge/",
    "mu/programs/",
    "rcx_pi/selfhost/",
    "tools/compilers/",
)

# Directories that MAINTENANCE must not touch
MAINTENANCE_FORBIDDEN = RUNTIME_DIRS

# Comment-only patterns (Python and JS)
COMMENT_ONLY_PATTERNS = [
    re.compile(r"^\s*#"),       # Python comment
    re.compile(r"^\s*//"),      # JS comment
    re.compile(r"^\s*\*"),      # JS block comment line
    re.compile(r"^\s*/\*"),     # JS block comment start
    re.compile(r"^\s*\*/"),     # JS block comment end
    re.compile(r'^\s*"""'),     # Python docstring delimiter
    re.compile(r"^\s*'''"),     # Python docstring delimiter
]

# Pattern to extract individual tracker sync notes with Class: markers
_TRACKER_NOTE_RE = re.compile(
    r"- Tracker sync note \([^)]+\):\s*\*\*[^*]+\*\*\s*(.*?)(?=\n- Tracker sync note |\n## |\Z)",
    re.DOTALL,
)


def is_comment_line(line: str) -> bool:
    """Check if a diff line (after +/- prefix) is comment-only."""
    content = line.lstrip("+").lstrip("-")
    if not content.strip():
        return True  # blank line
    return any(p.match(content) for p in COMMENT_ONLY_PATTERNS)


def is_runtime_file(filepath: str) -> bool:
    """Check if a file is in a runtime/substrate directory."""
    return any(filepath.startswith(d) for d in RUNTIME_DIRS)


def get_changed_files_staged() -> list[str]:
    """Get staged file paths."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=True,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def get_changed_files_range(git_range: str) -> list[str]:
    """Get changed file paths in a git range."""
    result = subprocess.run(
        ["git", "diff", "--name-only", git_range],
        capture_output=True, text=True, check=True,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def get_diff_staged() -> str:
    """Get staged diff content."""
    result = subprocess.run(
        ["git", "diff", "--cached", "-U0"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def get_diff_range(git_range: str) -> str:
    """Get diff content for a range."""
    result = subprocess.run(
        ["git", "diff", "-U0", git_range],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def has_non_comment_runtime_delta(diff_text: str, runtime_files: list[str]) -> bool:
    """Check if any runtime file has non-comment changes."""
    current_file = None
    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            # Extract b/ path
            parts = line.split(" b/")
            current_file = parts[-1] if len(parts) >= 2 else None
        elif current_file and current_file in runtime_files:
            if line.startswith("+") and not line.startswith("+++"):
                if not is_comment_line(line):
                    return True
            elif line.startswith("-") and not line.startswith("---"):
                if not is_comment_line(line):
                    return True
    return False


def parse_tracker_notes(text: str) -> list[dict[str, str | None]]:
    """
    Parse ordered tracker sync notes from TASKS.md Ra section.

    Returns list of dicts in document order (first = most recent),
    each with keys: 'wave_class', 'gate', 'no_op_proof', 'raw'.
    Only includes notes that have a Class: marker.
    """
    notes = []
    for m in _TRACKER_NOTE_RE.finditer(text):
        body = m.group(0)
        cls_match = re.search(r"Class:\s*(L4_CLASS_A|MAINTENANCE)", body)
        if not cls_match:
            continue
        gate_match = re.search(r"Gate:\s*([A-Za-z0-9]+)", body)
        nop_match = re.search(r"NO_OP_PROOF:\s*(.+?)(?:\.|$)", body)
        notes.append({
            "wave_class": cls_match.group(1),
            "gate": gate_match.group(1) if gate_match else None,
            "no_op_proof": nop_match.group(1).strip() if nop_match else None,
            "raw": body,
        })
    return notes


def detect_wave_class_from_tasks() -> str | None:
    """Detect wave class from the most recent tracker sync note in TASKS.md."""
    tasks_path = Path("TASKS.md")
    if not tasks_path.exists():
        return None
    text = tasks_path.read_text(encoding="utf-8")
    notes = parse_tracker_notes(text)
    return notes[0]["wave_class"] if notes else None


def check_consecutive_maintenance() -> bool:
    """Check if the two most recent Class-marked waves are both MAINTENANCE."""
    tasks_path = Path("TASKS.md")
    if not tasks_path.exists():
        return False
    text = tasks_path.read_text(encoding="utf-8")
    notes = parse_tracker_notes(text)
    if len(notes) < 2:
        return False
    return notes[0]["wave_class"] == "MAINTENANCE" and notes[1]["wave_class"] == "MAINTENANCE"


def check_maintenance_metadata() -> tuple[bool, list[str]]:
    """Check if the most recent MAINTENANCE wave note has required metadata."""
    tasks_path = Path("TASKS.md")
    if not tasks_path.exists():
        return False, ["TASKS.md not found"]
    text = tasks_path.read_text(encoding="utf-8")
    notes = parse_tracker_notes(text)
    if not notes:
        return True, []
    current = notes[0]
    if current["wave_class"] != "MAINTENANCE":
        return True, []
    errors = []
    if current["no_op_proof"] is None:
        errors.append("MAINTENANCE wave missing NO_OP_PROOF in tracker sync note")
    if current["gate"] is None:
        errors.append("MAINTENANCE wave missing Gate in tracker sync note")
    return len(errors) == 0, errors


def enforce(
    wave_class: str | None,
    changed_files: list[str],
    diff_text: str | None = None,
) -> tuple[bool, list[str]]:
    """
    Enforce L4 execution contract.

    Returns (passed, errors).
    """
    if not wave_class:
        # No wave class marker — not an L4-classified wave, skip enforcement
        return True, []

    errors = []
    runtime_files = [f for f in changed_files if is_runtime_file(f)]

    if wave_class == "L4_CLASS_A":
        # Must touch runtime/substrate
        if not runtime_files:
            errors.append(
                f"L4_CLASS_A wave has no runtime/substrate files. "
                f"Changed: {changed_files[:5]}..."
            )
        # Must have non-comment delta in runtime files
        elif diff_text and not has_non_comment_runtime_delta(diff_text, runtime_files):
            errors.append(
                "L4_CLASS_A wave touches runtime files but all changes are "
                "comment-only. Must have executable runtime delta."
            )
    elif wave_class == "MAINTENANCE":
        # Must NOT touch runtime/substrate
        if runtime_files:
            errors.append(
                f"MAINTENANCE wave touches runtime/substrate files: "
                f"{runtime_files[:5]}"
            )
        # Check consecutive cap
        if check_consecutive_maintenance():
            errors.append(
                "Consecutive MAINTENANCE cap exceeded. "
                "Max 1 consecutive MAINTENANCE wave without L4_CLASS_A."
            )
        # Check required metadata
        meta_ok, meta_errors = check_maintenance_metadata()
        if not meta_ok:
            errors.extend(meta_errors)
    else:
        errors.append(f"Unknown wave class: {wave_class}")

    return len(errors) == 0, errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enforce L4 Execution Contract wave classification"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true", help="Check staged files")
    group.add_argument("--range", type=str, help="Git range (e.g., origin/dev...HEAD)")
    group.add_argument("--files", nargs="+", help="Explicit file list")
    parser.add_argument(
        "--wave-class", type=str, choices=["L4_CLASS_A", "MAINTENANCE"],
        help="Override wave class (for testing). If not set, auto-detects from TASKS.md."
    )
    args = parser.parse_args()

    # Get changed files
    if args.staged:
        changed_files = get_changed_files_staged()
        diff_text = get_diff_staged()
    elif args.range:
        changed_files = get_changed_files_range(args.range)
        diff_text = get_diff_range(args.range)
    else:
        changed_files = args.files or []
        diff_text = None

    if not changed_files:
        print("No changed files — skipping L4 contract enforcement.")
        return 0

    # Determine wave class
    wave_class = args.wave_class or detect_wave_class_from_tasks()
    if not wave_class:
        print("No wave class marker found in TASKS.md — skipping L4 contract enforcement.")
        return 0

    print(f"Wave class: {wave_class}")
    print(f"Changed files: {len(changed_files)}")
    print(f"Runtime files: {sum(1 for f in changed_files if is_runtime_file(f))}")

    passed, errors = enforce(wave_class, changed_files, diff_text)

    if passed:
        print(f"✅ L4 Execution Contract: {wave_class} compliant")
        return 0
    else:
        print(f"❌ L4 Execution Contract VIOLATION ({wave_class}):")
        for e in errors:
            print(f"   - {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
