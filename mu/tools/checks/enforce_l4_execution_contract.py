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

# Low-signal placeholders that should not be accepted as proof text.
LOW_SIGNAL_PROOF_TOKENS = frozenset({
    "old", "new", "before", "after", "before-state", "after-state",
    "runtime change", "runtime changes", "added function", "updated",
    "changed", "n/a", "na", "none", "todo", "tbd", "placeholder",
})

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
_BLOCKER_CLASS_RE = re.compile(r"(?<!`)primary_blocker_class:\s*([A-Z_]+)")
_SWEEP_RE = re.compile(r"post_gate_contract_sweep:\s*(.+?)(?:\.\s|$)")
_INVARIANT_ID_RE = re.compile(r"(?<!`)primary_invariant_id:\s*([A-Z_]+)")
_PROGRESS_BEFORE_RE = re.compile(r"progress_proof_before:\s*(.+?)(?:\.\s|$)")
_PROGRESS_AFTER_RE = re.compile(r"progress_proof_after:\s*(.+?)(?:\.\s|$)")
_INDICATOR_REF_RE = re.compile(r"indicator_artifact_ref:\s*(.+?)(?:\.\s|$)")
_INDICATOR_CMD_RE = re.compile(r"indicator_collection_command:\s*(.+?)(?:\.\s|$)")
_BOOTSTRAP_POLICY_RE = re.compile(r"(?<!`)bootstrap_endgame_policy:\s*([A-Z_]+)")
_BOOT0_TRACK_RE = re.compile(r"(?<!`)boot0_track_id:\s*([A-Za-z0-9]+)")
_BOOT0_PROGRESS_RE = re.compile(r"(?<!`)boot0_progress_state:\s*([A-Z]+)")

# Rolling window size
ROLLING_WINDOW = 3

# Blocker classification (required for all class-marked waves)
VALID_BLOCKER_CLASSES = frozenset({"DESIGN", "INTEGRATION", "PERFORMANCE"})

# Non-gate test domains for post-gate contract sweep validation
NON_GATE_TEST_DOMAINS = (
    "tests/engine/", "tests/parity/", "tests/structural/", "tests/tools/", "tests/docs/",
    "mu/tests/engine/", "mu/tests/parity/", "mu/tests/structural/", "mu/tests/tools/", "mu/tests/docs/",
)

# Valid primary invariant IDs (every class-marked wave must declare one)
VALID_INVARIANT_IDS = frozenset({
    "INV_BOUND_HOST_TERMINATION",
    "INV_TERMINAL_SCHEMA_LOCK",
    "INV_CROSS_SUBSTRATE_PARITY",
    "INV_STRUCTURAL_FORWARD_MOTION",
    "INV_TYPED_FAIL_CLOSED_OUTCOMES",
})

# Canonical bootstrap endgame policy (single allowed value, resolves design split)
CANONICAL_BOOTSTRAP_POLICY = "SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP"

# Canonical indicator collector script path
CANONICAL_COLLECTOR_PATH = "tools/metrics/collect_l4_wave_indicators.py"

# Required indicator JSON keys with expected Python types
INDICATOR_REQUIRED_KEYS = {
    "repeat_run_speedup_ratio": (int, float),
    "parity_diff_count": (int,),
    "net_host_semantic_delta": (int,),
    "step_growth_slope": (int, float),
}

# Valid Boot0/Hex0 track IDs (from roadmap/Hex0_Boot0_Checklist.md)
VALID_BOOT0_TRACK_IDS = frozenset({
    "N1a", "N1b", "N2", "N3", "N4", "N5", "N6a", "N6b",
    "V1", "V2", "V3", "V4", "V5",
})

# Valid Boot0 progress states
VALID_BOOT0_PROGRESS_STATES = frozenset({"ADVANCE", "HOLD", "DEFER"})

# Required provenance keys in indicator JSON (Wave 18+)
INDICATOR_PROVENANCE_KEYS = {
    "repeat_run_raw_seconds": list,
    "step_growth_points": list,
    "parity_diff_source": str,
    "collection_timestamp_utc": str,
    "collector_version": str,
}


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

def filter_to_tracked_files(files: list[str]) -> list[str]:
    """Filter file list to only git-tracked files (defense against untracked leaks).

    Scope policy: the L4 checker operates on tracked changes only.
    Untracked files are not part of any wave scope and must be excluded.
    """
    if not files:
        return files
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--"] + files,
            capture_output=True, text=True,
        )
        tracked = set(result.stdout.strip().split("\n")) if result.stdout.strip() else set()
        untracked = [f for f in files if f not in tracked]
        if untracked:
            print(f"NOTE: Stripping {len(untracked)} untracked file(s) from scope: "
                  f"{untracked[:5]}")
        return [f for f in files if f in tracked]
    except Exception:
        return files  # If git fails, pass through unchanged


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
    added, deleted, _ = compute_runtime_exec_delta(diff_text, runtime_files)
    return (added + deleted) > 0


def compute_runtime_exec_delta(diff_text: str, runtime_files: list[str]) -> tuple[int, int, int]:
    """Compute runtime executable delta from diff text.

    Returns:
        (added_lines, deleted_lines, net_delta)
    """
    added = 0
    deleted = 0
    current_file = None
    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            parts = line.split(" b/")
            current_file = parts[-1] if len(parts) >= 2 else None
        elif current_file and current_file in runtime_files:
            if line.startswith("+") and not line.startswith("+++"):
                if not is_comment_line(line):
                    added += 1
            elif line.startswith("-") and not line.startswith("---"):
                if not is_comment_line(line):
                    deleted += 1
    return added, deleted, (added - deleted)


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
        blocker_match = _BLOCKER_CLASS_RE.search(body_text)
        sweep_match = _SWEEP_RE.search(body_text)
        invariant_match = _INVARIANT_ID_RE.search(body_text)
        progress_before_match = _PROGRESS_BEFORE_RE.search(body_text)
        progress_after_match = _PROGRESS_AFTER_RE.search(body_text)
        indicator_ref_match = _INDICATOR_REF_RE.search(body_text)
        indicator_cmd_match = _INDICATOR_CMD_RE.search(body_text)
        bootstrap_policy_match = _BOOTSTRAP_POLICY_RE.search(body_text)
        boot0_track_match = _BOOT0_TRACK_RE.search(body_text)
        boot0_progress_match = _BOOT0_PROGRESS_RE.search(body_text)

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
            "primary_blocker_class": blocker_match.group(1).strip() if blocker_match else None,
            "post_gate_contract_sweep": sweep_match.group(1).strip() if sweep_match else None,
            "primary_invariant_id": invariant_match.group(1).strip() if invariant_match else None,
            "progress_proof_before": progress_before_match.group(1).strip() if progress_before_match else None,
            "progress_proof_after": progress_after_match.group(1).strip() if progress_after_match else None,
            "indicator_artifact_ref": indicator_ref_match.group(1).strip() if indicator_ref_match else None,
            "indicator_collection_command": indicator_cmd_match.group(1).strip() if indicator_cmd_match else None,
            "bootstrap_endgame_policy": bootstrap_policy_match.group(1).strip() if bootstrap_policy_match else None,
            "boot0_track_id": boot0_track_match.group(1).strip() if boot0_track_match else None,
            "boot0_progress_state": boot0_progress_match.group(1).strip() if boot0_progress_match else None,
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
        if notes[0].get("founder_override"):
            print(f"  FOUNDER_OVERRIDE active — allowing rolling window without STRUCTURAL")
            return True, []
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


def check_non_structural_adjacency(notes: list[dict]) -> tuple[bool, list[str]]:
    """Non-structural adjacency cap: last 2 class-marked waves cannot both be non-STRUCTURAL.

    Founder override on current wave grants bypass.
    """
    if len(notes) < 2:
        return True, []
    if notes[0]["wave_class"] != "L4_STRUCTURAL" and notes[1]["wave_class"] != "L4_STRUCTURAL":
        if notes[0].get("founder_override"):
            print(f"  FOUNDER_OVERRIDE active — allowing non-structural adjacency")
            return True, []
        return False, [
            f"Non-structural adjacency cap violated: last 2 waves are "
            f"{notes[0]['wave_class']} and {notes[1]['wave_class']}. "
            f"At least 1 must be L4_STRUCTURAL. Use FOUNDER_OVERRIDE:<id> to bypass."
        ]
    return True, []


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
# Indicator artifact validation
# ---------------------------------------------------------------------------

def _is_numeric_not_bool(val: object) -> bool:
    """Check if value is numeric (int or float) but not bool."""
    return not isinstance(val, bool) and isinstance(val, (int, float))


def _is_low_signal_proof(text: str | None) -> bool:
    """Detect placeholder/theater proof text."""
    if text is None:
        return True
    normalized = " ".join(text.strip().lower().split())
    if len(normalized) < 12:
        return True
    return normalized in LOW_SIGNAL_PROOF_TOKENS


def _compute_slope(points: list[dict]) -> float:
    """Compute step_growth_slope from step_growth_points via linear fit.

    Formula: slope = (elapsed_last - elapsed_first) / (step_last - step_first)
    """
    first, last = points[0], points[-1]
    dx = last["step"] - first["step"]
    if dx == 0:
        return 0.0
    return (last["elapsed_seconds"] - first["elapsed_seconds"]) / dx


def validate_indicator_artifact_json(
    artifact_path: str,
    *,
    expected_net_host_delta: int | None = None,
) -> tuple[bool, list[str]]:
    """Validate indicator artifact JSON: required keys, types, provenance, derivation."""
    import json as _json
    errors: list[str] = []
    path = Path(artifact_path)
    if not path.exists():
        return False, [f"Indicator artifact '{artifact_path}' does not exist on disk."]
    try:
        data = _json.loads(path.read_text(encoding="utf-8"))
    except (_json.JSONDecodeError, OSError) as exc:
        return False, [f"Indicator artifact '{artifact_path}' invalid JSON: {exc}"]

    # --- Core metric keys ---
    for key, types in INDICATOR_REQUIRED_KEYS.items():
        if key not in data:
            errors.append(f"Indicator artifact missing required key: '{key}'")
        else:
            val = data[key]
            if isinstance(val, bool) or not isinstance(val, types):
                errors.append(
                    f"Indicator key '{key}': got {type(val).__name__}, "
                    f"expected {'/'.join(t.__name__ for t in types)}"
                )

    # --- Provenance keys ---
    for key, expected_type in INDICATOR_PROVENANCE_KEYS.items():
        if key not in data:
            errors.append(f"Indicator artifact missing provenance key: '{key}'")
        else:
            val = data[key]
            if not isinstance(val, expected_type):
                errors.append(
                    f"Provenance key '{key}': got {type(val).__name__}, "
                    f"expected {expected_type.__name__}"
                )

    # --- repeat_run_raw_seconds shape ---
    raw_secs = data.get("repeat_run_raw_seconds")
    if isinstance(raw_secs, list):
        if len(raw_secs) != 2:
            errors.append(
                f"repeat_run_raw_seconds must have exactly 2 elements, got {len(raw_secs)}"
            )
        else:
            for i, v in enumerate(raw_secs):
                if not _is_numeric_not_bool(v):
                    errors.append(
                        f"repeat_run_raw_seconds[{i}]: got {type(v).__name__}, "
                        f"expected numeric (not bool)"
                    )
                elif v <= 0:
                    errors.append(f"repeat_run_raw_seconds[{i}]: must be > 0, got {v}")

    # --- step_growth_points shape ---
    sgp = data.get("step_growth_points")
    sgp_valid = False
    if isinstance(sgp, list):
        if len(sgp) < 2:
            errors.append(
                f"step_growth_points must have >= 2 elements, got {len(sgp)}"
            )
        else:
            sgp_valid = True
            prev_step = None
            for i, pt in enumerate(sgp):
                if not isinstance(pt, dict):
                    errors.append(f"step_growth_points[{i}]: must be object, got {type(pt).__name__}")
                    sgp_valid = False
                    continue
                for fld in ("step", "elapsed_seconds"):
                    fv = pt.get(fld)
                    if fv is None:
                        errors.append(f"step_growth_points[{i}] missing '{fld}'")
                        sgp_valid = False
                    elif not _is_numeric_not_bool(fv):
                        errors.append(
                            f"step_growth_points[{i}].{fld}: got {type(fv).__name__}, "
                            f"expected numeric (not bool)"
                        )
                        sgp_valid = False
                if sgp_valid and prev_step is not None:
                    if pt["step"] <= prev_step:
                        errors.append(
                            f"step_growth_points[{i}].step ({pt['step']}) must be "
                            f"strictly greater than previous ({prev_step})"
                        )
                        sgp_valid = False
                if sgp_valid:
                    prev_step = pt["step"]

    # --- String provenance: non-empty ---
    for skey in ("parity_diff_source", "collection_timestamp_utc", "collector_version"):
        sv = data.get(skey)
        if isinstance(sv, str) and not sv.strip():
            errors.append(f"Provenance key '{skey}' must be non-empty string")

    # --- Derivation check: repeat_run_speedup_ratio ---
    if (isinstance(raw_secs, list) and len(raw_secs) == 2
            and all(_is_numeric_not_bool(v) and v > 0 for v in raw_secs)):
        expected_ratio = round(raw_secs[0] / raw_secs[1], 6)
        actual_ratio = data.get("repeat_run_speedup_ratio")
        if _is_numeric_not_bool(actual_ratio) and round(actual_ratio, 6) != expected_ratio:
            errors.append(
                f"Derivation mismatch: repeat_run_speedup_ratio={actual_ratio} "
                f"but round(raw[0]/raw[1], 6)={expected_ratio}"
            )

    # --- Derivation check: step_growth_slope ---
    if sgp_valid and isinstance(sgp, list) and len(sgp) >= 2:
        expected_slope = round(_compute_slope(sgp), 6)
        actual_slope = data.get("step_growth_slope")
        if _is_numeric_not_bool(actual_slope) and round(actual_slope, 6) != expected_slope:
            errors.append(
                f"Derivation mismatch: step_growth_slope={actual_slope} "
                f"but computed from points={expected_slope}"
            )

    # --- Scope consistency check: net_host_semantic_delta ---
    if expected_net_host_delta is not None:
        actual_net = data.get("net_host_semantic_delta")
        if _is_numeric_not_bool(actual_net):
            if int(actual_net) != int(expected_net_host_delta):
                errors.append(
                    "Indicator mismatch: net_host_semantic_delta="
                    f"{actual_net} but executable runtime diff net={expected_net_host_delta}"
                )

    return len(errors) == 0, errors


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
            if current["evidence_delta"] is None:
                errors.append("L4_STRUCTURAL missing evidence_delta in tracker note")
            if current["host_semantics_delta_before"] is None:
                errors.append("L4_STRUCTURAL missing host_semantics_delta_before in tracker note")
            if current["host_semantics_delta_after"] is None:
                errors.append("L4_STRUCTURAL missing host_semantics_delta_after in tracker note")
            if _is_low_signal_proof(current["host_semantics_delta_before"]):
                errors.append(
                    "L4_STRUCTURAL host_semantics_delta_before is low-signal/placeholder text"
                )
            if _is_low_signal_proof(current["host_semantics_delta_after"]):
                errors.append(
                    "L4_STRUCTURAL host_semantics_delta_after is low-signal/placeholder text"
                )
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
            # Post-gate contract sweep (must reference non-gate test domains)
            if current.get("post_gate_contract_sweep") is None:
                errors.append("L4_STRUCTURAL missing post_gate_contract_sweep in tracker note")
            else:
                sweep_cmd = current["post_gate_contract_sweep"]
                if not any(d in sweep_cmd for d in NON_GATE_TEST_DOMAINS):
                    errors.append(
                        "L4_STRUCTURAL post_gate_contract_sweep must reference at least one "
                        "non-gate test domain (tests/engine/, tests/structural/, etc.). "
                        f"Got: {sweep_cmd!r}"
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

        # Primary blocker classification (all classes)
        blocker = current.get("primary_blocker_class")
        if blocker is None:
            errors.append(
                "Missing primary_blocker_class in tracker note "
                "(required: DESIGN, INTEGRATION, or PERFORMANCE)"
            )
        elif blocker not in VALID_BLOCKER_CLASSES:
            errors.append(
                f"Invalid primary_blocker_class: '{blocker}'. "
                f"Must be one of: {sorted(VALID_BLOCKER_CLASSES)}"
            )

        # Primary invariant ID (all classes)
        invariant_id = current.get("primary_invariant_id")
        if invariant_id is None:
            errors.append(
                "Missing primary_invariant_id in tracker note "
                "(required: one of " + ", ".join(sorted(VALID_INVARIANT_IDS)) + ")"
            )
        elif invariant_id not in VALID_INVARIANT_IDS:
            errors.append(
                f"Invalid primary_invariant_id: '{invariant_id}'. "
                f"Must be one of: {sorted(VALID_INVARIANT_IDS)}"
            )

        # Progress proof (required for STRUCTURAL + ENABLER)
        if wave_class in ("L4_STRUCTURAL", "L4_ENABLER"):
            pp_before = current.get("progress_proof_before")
            pp_after = current.get("progress_proof_after")
            if pp_before is None:
                errors.append(
                    f"{wave_class} missing progress_proof_before in tracker note"
                )
            if pp_after is None:
                errors.append(
                    f"{wave_class} missing progress_proof_after in tracker note"
                )
            if pp_before and pp_after and pp_before == pp_after:
                errors.append(
                    f"{wave_class} progress_proof_before and progress_proof_after "
                    f"must not be identical (anti-theater)"
                )

        # Indicator artifact and collection command (all classes)
        indicator_ref = current.get("indicator_artifact_ref")
        indicator_cmd = current.get("indicator_collection_command")
        if indicator_ref is None:
            errors.append("Missing indicator_artifact_ref in tracker note")
        if indicator_cmd is None:
            errors.append("Missing indicator_collection_command in tracker note")
        elif CANONICAL_COLLECTOR_PATH not in indicator_cmd:
            errors.append(
                f"indicator_collection_command must reference canonical collector "
                f"'{CANONICAL_COLLECTOR_PATH}'. Got: {indicator_cmd!r}"
            )

        # Bootstrap endgame policy (all classes)
        policy = current.get("bootstrap_endgame_policy")
        if policy is None:
            errors.append(
                "Missing bootstrap_endgame_policy in tracker note "
                f"(required: {CANONICAL_BOOTSTRAP_POLICY})"
            )
        elif policy != CANONICAL_BOOTSTRAP_POLICY:
            errors.append(
                f"Invalid bootstrap_endgame_policy: '{policy}'. "
                f"Must be exactly: {CANONICAL_BOOTSTRAP_POLICY}"
            )

        # Boot0 track ID (all classes)
        boot0_track = current.get("boot0_track_id")
        if boot0_track is None:
            errors.append(
                "Missing boot0_track_id in tracker note "
                f"(required: one of {sorted(VALID_BOOT0_TRACK_IDS)})"
            )
        elif boot0_track not in VALID_BOOT0_TRACK_IDS:
            errors.append(
                f"Invalid boot0_track_id: '{boot0_track}'. "
                f"Must be one of: {sorted(VALID_BOOT0_TRACK_IDS)}"
            )

        # Boot0 progress state (all classes)
        boot0_progress = current.get("boot0_progress_state")
        if boot0_progress is None:
            errors.append(
                "Missing boot0_progress_state in tracker note "
                f"(required: one of {sorted(VALID_BOOT0_PROGRESS_STATES)})"
            )
        elif boot0_progress not in VALID_BOOT0_PROGRESS_STATES:
            errors.append(
                f"Invalid boot0_progress_state: '{boot0_progress}'. "
                f"Must be one of: {sorted(VALID_BOOT0_PROGRESS_STATES)}"
            )

        # Non-structural adjacency cap
        adj_ok, adj_errors = check_non_structural_adjacency(notes)
        if not adj_ok:
            errors.extend(adj_errors)

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
        changed_files = filter_to_tracked_files(args.files or [])
        diff_text = None

    # Empty-scope policy — applies AFTER untracked filtering
    if not changed_files:
        if args.wave_id:
            # wave-id provided but no tracked files to verify — cannot certify
            scope_desc = (
                f"--files (all untracked)" if args.files
                else f"--range={args.range!r}" if args.range
                else "--staged" if args.staged
                else "(no scope)"
            )
            print(f"ERROR: --wave-id '{args.wave_id}' provided but no tracked files "
                  f"found ({scope_desc}). "
                  f"Cannot verify wave against empty change set.")
            return 1
        if args.files:
            print("No tracked files after filtering — skipping enforcement.")
            return 0
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
    # Only auto-detect from notes if TASKS.md is in the changed files (meaning
    # this PR includes a tracker note update) or --wave-id was explicitly given.
    # Otherwise non-wave PRs inherit the latest wave's class — false positives.
    tasks_in_changed = any(f in ("TASKS.md",) for f in changed_files)
    wave_class = args.wave_class
    if not wave_class and notes and (bound_note or tasks_in_changed):
        wave_class = notes[0]["wave_class"] if notes else None

    runtime_count = sum(1 for f in changed_files if is_runtime_file(f))

    print(f"Wave class: {wave_class or '(none)'}")
    print(f"Changed files: {len(changed_files)}")
    print(f"Runtime files: {runtime_count}")

    passed, errors = enforce(wave_class, changed_files, diff_text, notes)

    # Indicator artifact file-level validation (CLI only)
    # Only validate when wave_class is active (skip for non-wave PRs)
    if notes and wave_class:
        indicator_ref = notes[0].get("indicator_artifact_ref")
        if indicator_ref:
            if indicator_ref not in changed_files:
                passed = False
                errors.append(
                    f"indicator_artifact_ref '{indicator_ref}' not in changed files. "
                    f"Artifact must be committed as part of the wave."
                )
            expected_net_delta = None
            if diff_text is not None:
                runtime_files = [f for f in changed_files if is_runtime_file(f)]
                _, _, expected_net_delta = compute_runtime_exec_delta(diff_text, runtime_files)

            art_ok, art_errors = validate_indicator_artifact_json(
                indicator_ref,
                expected_net_host_delta=expected_net_delta,
            )
            if not art_ok:
                passed = False
                errors.extend(art_errors)

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
