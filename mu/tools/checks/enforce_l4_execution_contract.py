#!/usr/bin/env python3
"""
Enforce L4 Execution Contract v2 wave classification.

3-class model: L4_STRUCTURAL, L4_ENABLER, MAINTENANCE.
Anti-stagnation: rolling structural quota, NO_OP throttling, fail-closed.

Usage:
    python tools/checks/enforce_l4_execution_contract.py --staged
    python tools/checks/enforce_l4_execution_contract.py --range origin/dev...HEAD
    python tools/checks/enforce_l4_execution_contract.py --files f1 f2 ...
    python tools/checks/enforce_l4_execution_contract.py --wave-class L4_STRUCTURAL --files f1 f2 ...

Exit codes:
    0 -> compliant
    1 -> violation
    2 -> usage error
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_WAVE_CLASSES = frozenset({"L4_STRUCTURAL", "L4_ENABLER", "MAINTENANCE"})

# Historical alias — accepted in parse for old notes, rejected for new notes.
LEGACY_CLASS_ALIAS = {"L4_CLASS_A": "L4_STRUCTURAL"}

# Strict gate ID pattern
GATE_ID_RE = re.compile(r"^G[1-8]$")

# Runtime/substrate directories
RUNTIME_DIRS = (
    "mu/host/",
    "mu/substrate/",
    "mu/closures/",
    "mu/bridge/",
    "mu/programs/",
    "rcx_pi/selfhost/",
    "tools/compilers/",
)

# Comment-only patterns (Python and JS)
COMMENT_ONLY_PATTERNS = [
    re.compile(r"^\s*#"),       # Python comment
    re.compile(r"^\s*//"),      # JS comment
    re.compile(r"^\s*\*(?!\w)"),  # JS block comment line (not star-expr)
    re.compile(r"^\s*/\*"),     # JS block comment start
    re.compile(r"^\s*\*/"),     # JS block comment end
    re.compile(r'^\s*"""'),     # Python docstring delimiter
    re.compile(r"^\s*'''"),     # Python docstring delimiter
]

# Tracker note regex — captures header (date, wave_id) and body
_NOTE_HEADER_RE = re.compile(
    r"- Tracker sync note \(([^,]+),\s*([^)]+)\):\s*\*\*[^*]+\*\*\s*"
)
_NOTE_BODY_RE = re.compile(
    r"- Tracker sync note \([^)]+\):\s*\*\*[^*]+\*\*\s*(.*?)(?=\n- Tracker sync note |\n## |\Z)",
    re.DOTALL,
)

# Field extraction patterns
_CLASS_RE = re.compile(r"Class:\s*(L4_STRUCTURAL|L4_ENABLER|L4_CLASS_A|MAINTENANCE)")
_GATE_RE = re.compile(r"(?:Gate|target_gate_id):\s*(G[0-9]+)")
_NOP_RE = re.compile(r"(?:NO_OP_PROOF|no_op_proof):\s*(.+?)(?:\.\s|$)")
_EVIDENCE_CMD_RE = re.compile(r"evidence_command:\s*(.+?)(?:\.\s|$)")
_EVIDENCE_DELTA_RE = re.compile(r"evidence_delta:\s*(.+?)(?:\.\s|$)")
_HOST_DELTA_BEFORE_RE = re.compile(r"host_semantics_delta_before:\s*(.+?)(?:\.\s|$)")
_HOST_DELTA_AFTER_RE = re.compile(r"host_semantics_delta_after:\s*(.+?)(?:\.\s|$)")
_STRUCTURAL_ARTIFACT_RE = re.compile(r"structural_artifact_ref:\s*(.+?)(?:\.\s|$)")
_DEFER_REASON_RE = re.compile(r"defer_reason_code:\s*(.+?)(?:\.\s|$)")
_FOUNDER_OVERRIDE_RE = re.compile(r"FOUNDER_OVERRIDE:(\S+)")

# Rolling window size
ROLLING_WINDOW = 3


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def is_comment_line(line: str) -> bool:
    """Check if a diff line (after +/- prefix) is comment-only."""
    content = line.lstrip("+").lstrip("-")
    if not content.strip():
        return True
    return any(p.match(content) for p in COMMENT_ONLY_PATTERNS)


def is_runtime_file(filepath: str) -> bool:
    """Check if a file is in a runtime/substrate directory."""
    return any(filepath.startswith(d) for d in RUNTIME_DIRS)


def is_l4_gate_test(filepath: str) -> bool:
    """Check if a file is under tests/l4_gates/ (canonical or physical mu/ path)."""
    return filepath.startswith("tests/l4_gates/") or filepath.startswith("mu/tests/l4_gates/")


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Tracker note parsing
# ---------------------------------------------------------------------------

def parse_tracker_notes(text: str) -> list[dict[str, str | None]]:
    """
    Parse ordered tracker sync notes from TASKS.md Ra section.

    Returns list of dicts in document order (first = most recent).
    Only includes notes that have a Class: marker.
    Historical L4_CLASS_A is aliased to L4_STRUCTURAL.
    """
    notes: list[dict[str, str | None]] = []

    for header_m in _NOTE_HEADER_RE.finditer(text):
        date_str = header_m.group(1).strip()
        wave_id = header_m.group(2).strip()

        # Find body for this note
        body_m = _NOTE_BODY_RE.match(text, header_m.start())
        if not body_m:
            continue
        body_text = body_m.group(1)  # body after **title**, not full match
        body = body_m.group(0)      # full match for raw storage

        cls_match = _CLASS_RE.search(body_text)
        if not cls_match:
            continue

        raw_class = cls_match.group(1)
        wave_class = LEGACY_CLASS_ALIAS.get(raw_class, raw_class)

        gate_match = _GATE_RE.search(body_text)
        nop_match = _NOP_RE.search(body_text)
        ev_cmd_match = _EVIDENCE_CMD_RE.search(body_text)
        ev_delta_match = _EVIDENCE_DELTA_RE.search(body_text)
        hd_before_match = _HOST_DELTA_BEFORE_RE.search(body_text)
        hd_after_match = _HOST_DELTA_AFTER_RE.search(body_text)
        sa_match = _STRUCTURAL_ARTIFACT_RE.search(body_text)
        defer_match = _DEFER_REASON_RE.search(body_text)
        override_match = _FOUNDER_OVERRIDE_RE.search(body_text)

        notes.append({
            "wave_id": wave_id,
            "raw_class": raw_class,
            "wave_class": wave_class,
            "gate": gate_match.group(1) if gate_match else None,
            "no_op_proof": nop_match.group(1).strip() if nop_match else None,
            "evidence_command": ev_cmd_match.group(1).strip() if ev_cmd_match else None,
            "evidence_delta": ev_delta_match.group(1).strip() if ev_delta_match else None,
            "host_semantics_delta_before": hd_before_match.group(1).strip() if hd_before_match else None,
            "host_semantics_delta_after": hd_after_match.group(1).strip() if hd_after_match else None,
            "structural_artifact_ref": sa_match.group(1).strip() if sa_match else None,
            "defer_reason_code": defer_match.group(1).strip() if defer_match else None,
            "founder_override": override_match.group(1).strip() if override_match else None,
            "date": date_str,
            "raw": body,
        })

    return notes


# ---------------------------------------------------------------------------
# Anti-stagnation checks
# ---------------------------------------------------------------------------

def check_consecutive_maintenance(notes: list[dict]) -> bool:
    """Check if the two most recent Class-marked waves are both MAINTENANCE."""
    if len(notes) < 2:
        return False
    return notes[0]["wave_class"] == "MAINTENANCE" and notes[1]["wave_class"] == "MAINTENANCE"


def check_rolling_window(notes: list[dict]) -> tuple[bool, list[str]]:
    """
    Rolling structural quota: in last ROLLING_WINDOW class-marked waves,
    at least 1 must be L4_STRUCTURAL.

    Skips if fewer than ROLLING_WINDOW notes exist (bootstrap grace).
    """
    if len(notes) < ROLLING_WINDOW:
        return True, []

    window = notes[:ROLLING_WINDOW]
    has_structural = any(n["wave_class"] == "L4_STRUCTURAL" for n in window)
    if not has_structural:
        classes = [n["wave_class"] for n in window]
        return False, [
            f"Rolling structural quota violated: last {ROLLING_WINDOW} waves "
            f"have no L4_STRUCTURAL. Classes: {classes}"
        ]
    return True, []


def check_noop_throttle(notes: list[dict]) -> tuple[bool, list[str]]:
    """
    NO_OP throttling: same target_gate_id cannot use no_op_proof twice
    in the last ROLLING_WINDOW class-marked waves.

    Founder override grants exactly one exception per gate:
    - count <= 1: pass (no throttle)
    - count == 2: pass only if exactly one valid override for that same gate
    - count > 2: fail even with override (one exception only)
    """
    window = notes[:ROLLING_WINDOW]
    gate_noop_count: dict[str, int] = {}
    gate_override_count: dict[str, int] = {}

    for n in window:
        if n["no_op_proof"] and n["gate"]:
            gate_noop_count[n["gate"]] = gate_noop_count.get(n["gate"], 0) + 1
        if n["founder_override"] and n["gate"]:
            gate_override_count[n["gate"]] = gate_override_count.get(n["gate"], 0) + 1

    errors = []
    for gate_id, count in gate_noop_count.items():
        if count == 2 and gate_override_count.get(gate_id, 0) == 1:
            print(f"  FOUNDER_OVERRIDE active for {gate_id} — "
                  f"allowing one NO_OP repeat")
        elif count >= 2:
            if gate_override_count.get(gate_id, 0) == 0:
                errors.append(
                    f"NO_OP throttle violated: gate {gate_id} has {count} "
                    f"NO_OP_PROOF entries in last {ROLLING_WINDOW} waves. "
                    f"Requires FOUNDER_OVERRIDE:<id> on the same gate to bypass."
                )
            else:
                errors.append(
                    f"NO_OP throttle violated: gate {gate_id} has {count} "
                    f"NO_OP_PROOF entries in last {ROLLING_WINDOW} waves. "
                    f"Override grants one exception only (count <= 2)."
                )

    return len(errors) == 0, errors


def check_founder_override_replay(notes: list[dict]) -> tuple[bool, list[str]]:
    """Founder override replay protection: duplicate IDs in window must fail."""
    window = notes[:ROLLING_WINDOW]
    seen: dict[str, int] = {}
    for n in window:
        oid = n["founder_override"]
        if oid:
            seen[oid] = seen.get(oid, 0) + 1

    errors = []
    for oid, count in seen.items():
        if count > 1:
            errors.append(
                f"FOUNDER_OVERRIDE replay detected: '{oid}' used {count} times "
                f"in last {ROLLING_WINDOW} waves. Each override ID is single-use."
            )
    return len(errors) == 0, errors


def check_maintenance_metadata(notes: list[dict]) -> tuple[bool, list[str]]:
    """Check if the most recent MAINTENANCE wave note has required metadata."""
    if not notes:
        return True, []
    current = notes[0]
    if current["wave_class"] != "MAINTENANCE":
        return True, []
    errors = []
    if current["no_op_proof"] is None:
        errors.append("MAINTENANCE wave missing no_op_proof in tracker sync note")
    if current["gate"] is None:
        errors.append("MAINTENANCE wave missing target_gate_id in tracker sync note")
    if current["defer_reason_code"] is None:
        errors.append("MAINTENANCE wave missing defer_reason_code in tracker sync note")
    return len(errors) == 0, errors


def check_legacy_alias_in_new_notes(notes: list[dict]) -> tuple[bool, list[str]]:
    """New notes using L4_CLASS_A must fail. Only historical parsing allowed."""
    if not notes:
        return True, []
    current = notes[0]
    if current["raw_class"] == "L4_CLASS_A":
        return False, [
            "New tracker note uses legacy class L4_CLASS_A. "
            "Use L4_STRUCTURAL, L4_ENABLER, or MAINTENANCE instead."
        ]
    return True, []


# ---------------------------------------------------------------------------
# Core enforcement
# ---------------------------------------------------------------------------

def enforce(
    wave_class: str | None,
    changed_files: list[str],
    diff_text: str | None = None,
    notes: list[dict] | None = None,
) -> tuple[bool, list[str]]:
    """
    Enforce L4 execution contract v2.

    Returns (passed, errors).
    """
    errors: list[str] = []
    runtime_files = [f for f in changed_files if is_runtime_file(f)]

    # Fail-closed: runtime changes without class marker
    if not wave_class:
        if runtime_files:
            errors.append(
                f"FAIL-CLOSED: Runtime/core files changed but no wave class marker found. "
                f"Runtime files: {runtime_files[:5]}"
            )
            return False, errors
        return True, []

    # Validate class is in strict enum
    if wave_class not in VALID_WAVE_CLASSES:
        errors.append(f"Unknown wave class: {wave_class}")
        return False, errors

    # --- L4_STRUCTURAL ---
    if wave_class == "L4_STRUCTURAL":
        if not runtime_files:
            errors.append(
                f"L4_STRUCTURAL wave has no runtime/substrate files. "
                f"Changed: {changed_files[:5]}"
            )
        elif diff_text and not has_non_comment_runtime_delta(diff_text, runtime_files):
            errors.append(
                "L4_STRUCTURAL wave touches runtime files but all changes are "
                "comment-only. Must have executable runtime delta."
            )

        # Gate test evidence AND rule
        gate_test_files = [f for f in changed_files if is_l4_gate_test(f)]
        if not gate_test_files:
            errors.append(
                "L4_STRUCTURAL wave missing changed file under tests/l4_gates/ "
                "(or mu/tests/l4_gates/). Must include gate-linked test evidence."
            )

        # Host semantics delta fields (checked via notes if available)
        if notes:
            current = notes[0]
            if current["host_semantics_delta_before"] is None:
                errors.append("L4_STRUCTURAL missing host_semantics_delta_before in tracker note")
            if current["host_semantics_delta_after"] is None:
                errors.append("L4_STRUCTURAL missing host_semantics_delta_after in tracker note")
            if current["structural_artifact_ref"] is None:
                errors.append("L4_STRUCTURAL missing structural_artifact_ref in tracker note")
            if current["evidence_command"] is None:
                errors.append("L4_STRUCTURAL missing evidence_command in tracker note")
            elif ("tests/l4_gates/" not in current["evidence_command"]
                  and "mu/tests/l4_gates/" not in current["evidence_command"]):
                errors.append(
                    "L4_STRUCTURAL evidence_command must reference tests/l4_gates/ "
                    f"(or mu/tests/l4_gates/) target. Got: {current['evidence_command']!r}"
                )

    # --- L4_ENABLER ---
    elif wave_class == "L4_ENABLER":
        if runtime_files:
            errors.append(
                f"L4_ENABLER wave touches runtime/substrate files (forbidden). "
                f"Runtime files: {runtime_files[:5]}. Use L4_STRUCTURAL instead."
            )
        if notes:
            current = notes[0]
            if current["gate"] is None:
                errors.append("L4_ENABLER missing target_gate_id in tracker note")
            if current["evidence_command"] is None:
                errors.append("L4_ENABLER missing evidence_command in tracker note")
            if current["evidence_delta"] is None:
                errors.append("L4_ENABLER missing evidence_delta in tracker note")
            if current.get("host_semantics_delta_before") is not None or current.get("host_semantics_delta_after") is not None:
                errors.append(
                    "L4_ENABLER cannot claim host_semantics_delta without runtime file changes."
                )

    # --- MAINTENANCE ---
    elif wave_class == "MAINTENANCE":
        if runtime_files:
            errors.append(
                f"MAINTENANCE wave touches runtime/substrate files: "
                f"{runtime_files[:5]}"
            )

    # --- Cross-class checks using notes ---
    if notes:
        current = notes[0]

        # Strict gate ID validation
        if current["gate"] and not GATE_ID_RE.match(current["gate"]):
            errors.append(
                f"Invalid target_gate_id: '{current['gate']}'. Must match G1-G8."
            )

        # Legacy alias lock
        alias_ok, alias_errors = check_legacy_alias_in_new_notes(notes)
        if not alias_ok:
            errors.extend(alias_errors)

        # Consecutive maintenance cap
        if wave_class == "MAINTENANCE" and check_consecutive_maintenance(notes):
            errors.append(
                "Consecutive MAINTENANCE cap exceeded. "
                "Max 1 consecutive MAINTENANCE without L4_STRUCTURAL or L4_ENABLER."
            )

        # MAINTENANCE metadata
        if wave_class == "MAINTENANCE":
            meta_ok, meta_errors = check_maintenance_metadata(notes)
            if not meta_ok:
                errors.extend(meta_errors)

        # Rolling structural quota
        rw_ok, rw_errors = check_rolling_window(notes)
        if not rw_ok:
            errors.extend(rw_errors)

        # NO_OP throttle
        nt_ok, nt_errors = check_noop_throttle(notes)
        if not nt_ok:
            errors.extend(nt_errors)

        # Founder override replay protection
        or_ok, or_errors = check_founder_override_replay(notes)
        if not or_ok:
            errors.extend(or_errors)

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enforce L4 Execution Contract v2 wave classification"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true", help="Check staged files")
    group.add_argument("--range", type=str, help="Git range (e.g., origin/dev...HEAD)")
    group.add_argument("--files", nargs="+", help="Explicit file list")
    parser.add_argument(
        "--wave-class", type=str,
        choices=sorted(VALID_WAVE_CLASSES),
        help="Override wave class (for testing). If not set, auto-detects from TASKS.md."
    )
    parser.add_argument(
        "--wave-id", type=str,
        help="Bind to specific wave_id in tracker notes (not global latest)."
    )
    args = parser.parse_args()

    # Get changed files
    if args.staged:
        changed_files = get_changed_files_staged()
        diff_text = get_diff_staged() if changed_files else None
    elif args.range:
        changed_files = get_changed_files_range(args.range)
        diff_text = get_diff_range(args.range) if changed_files else None
    else:
        changed_files = args.files or []
        diff_text = None

    # Empty-scope policy
    if not changed_files and not args.files:
        if args.wave_id:
            # wave-id provided but no files to verify — cannot certify compliance
            print(f"ERROR: --wave-id '{args.wave_id}' provided but no changed files "
                  f"found (--range={args.range!r}, --staged={args.staged}). "
                  f"Cannot verify wave against empty change set.")
            return 1
        if args.range:
            print(f"No changed files in range '{args.range}' — skipping enforcement.")
            return 0
        if args.staged:
            print("No staged files — skipping enforcement.")
            return 0
        # Truly unknown scope — fall back to HEAD~1...HEAD
        print("WARNING: Empty scope detected. Falling back to HEAD~1...HEAD.")
        try:
            changed_files = get_changed_files_range("HEAD~1...HEAD")
            diff_text = get_diff_range("HEAD~1...HEAD") if changed_files else None
        except subprocess.CalledProcessError:
            print("WARNING: HEAD~1...HEAD fallback failed (new repo?). "
                  "Cannot verify — treating as non-blocking.")
            return 0
        if not changed_files:
            print("No changed files even after fallback — skipping enforcement.")
            return 0

    # Parse tracker notes
    tasks_path = Path("TASKS.md")
    all_notes: list[dict] = []
    if tasks_path.exists():
        text = tasks_path.read_text(encoding="utf-8")
        all_notes = parse_tracker_notes(text)

    # Wave binding: select note for this wave_id
    bound_note: dict | None = None
    if args.wave_id:
        for n in all_notes:
            if n["wave_id"] == args.wave_id:
                bound_note = n
                break
        if bound_note is None:
            print(f"ERROR: --wave-id '{args.wave_id}' not found in any tracker sync note.")
            print(f"  Available wave_ids: {[n['wave_id'] for n in all_notes[:10]]}")
            return 1

    # Build notes list with bound note at position 0 (for cross-class checks)
    notes: list[dict] | None = None
    if bound_note:
        # Put the bound note first, keep the rest for window checks
        notes = [bound_note] + [n for n in all_notes if n["wave_id"] != args.wave_id]
    elif all_notes:
        notes = all_notes

    # Determine wave class
    wave_class = args.wave_class
    if not wave_class and notes:
        wave_class = notes[0]["wave_class"] if notes else None

    runtime_count = sum(1 for f in changed_files if is_runtime_file(f))

    print(f"Wave class: {wave_class or '(none)'}")
    print(f"Changed files: {len(changed_files)}")
    print(f"Runtime files: {runtime_count}")

    passed, errors = enforce(wave_class, changed_files, diff_text, notes)

    if passed:
        print(f"✅ L4 Execution Contract v2: {wave_class or 'no-class'} compliant")
        return 0
    else:
        print(f"❌ L4 Execution Contract v2 VIOLATION ({wave_class or 'no-class'}):")
        for e in errors:
            print(f"   - {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
