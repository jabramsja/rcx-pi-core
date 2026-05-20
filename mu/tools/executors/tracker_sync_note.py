#!/usr/bin/env python3
"""Structured tracker sync note generation and upsert.

Renders L4-compliant tracker sync notes from typed fields,
eliminating freeform prose as the primary tracker path.

The rendered format matches the regex patterns in
tools/checks/enforce_l4_execution_contract.py exactly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# L4 wave classes (must match enforce_l4_execution_contract.py _CLASS_RE).
# A blank wave_class is also supported for the separate wave-bound
# FOUNDER_OVERRIDE comment-only runtime override path in the L4 checker.
VALID_WAVE_CLASSES = frozenset({"L4_STRUCTURAL", "L4_ENABLER", "MAINTENANCE"})

# Valid blocker classes
VALID_BLOCKER_CLASSES = frozenset({"DESIGN", "INTEGRATION", "PERFORMANCE"})

# Valid invariant IDs (must match enforce_l4_execution_contract.py VALID_INVARIANT_IDS)
VALID_INVARIANT_IDS = frozenset({
    "INV_BOUND_HOST_TERMINATION",
    "INV_TERMINAL_SCHEMA_LOCK",
    "INV_CROSS_SUBSTRATE_PARITY",
    "INV_STRUCTURAL_FORWARD_MOTION",
    "INV_TYPED_FAIL_CLOSED_OUTCOMES",
})

# Valid boot0 progress states
VALID_BOOT0_STATES = frozenset({"ADVANCE", "HOLD", "DEFER"})

# Canonical bootstrap policy
CANONICAL_BOOTSTRAP_POLICY = "SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP"

# Ra section detection
_RA_HEADER_RE = re.compile(r"^## Ra\b")
_SECTION_SEPARATOR_RE = re.compile(r"^---\s*$")
_TRACKER_NOTE_RE = re.compile(r"^- Tracker sync note \(([^,]+),\s*([^)]+)\):")


class TrackerSyncError(RuntimeError):
    """Raised when tracker note generation or upsert fails."""


@dataclass
class TrackerSyncNoteFields:
    """Typed structure for L4-compliant tracker sync note fields."""

    wave_id: str
    title: str
    wave_class: str
    target_gate_id: str

    # Required for all classes
    primary_blocker_class: str
    primary_invariant_id: str
    indicator_artifact_ref: str
    indicator_collection_command: str
    bootstrap_endgame_policy: str = CANONICAL_BOOTSTRAP_POLICY
    boot0_track_id: str = "V1"
    boot0_progress_state: str = "HOLD"

    # Evidence (required for STRUCTURAL + ENABLER)
    evidence_command: str = ""
    evidence_delta: str = ""
    progress_proof_before: str = ""
    progress_proof_after: str = ""

    # STRUCTURAL-specific
    host_semantics_delta_before: str = ""
    host_semantics_delta_after: str = ""
    structural_artifact_ref: str = ""
    post_gate_contract_sweep: str = ""
    workload_target: str = ""

    # MAINTENANCE-specific
    no_op_proof: str = ""
    defer_reason_code: str = ""

    # Consecutive MAINTENANCE bypass
    unblocks_wave_id: str = ""
    unblocks_runtime_blocker: str = ""

    # Optional
    founder_override: str = ""
    packet_ref: str = ""

    # Date (defaults to today UTC)
    date: str = ""

    def __post_init__(self) -> None:
        if not self.date:
            self.date = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def validate_fields(fields: TrackerSyncNoteFields) -> list[str]:
    """Validate tracker note fields. Returns list of errors (empty = valid)."""
    errors: list[str] = []

    if not fields.wave_id or not fields.wave_id.strip():
        errors.append("wave_id is required")
    if not fields.title or not fields.title.strip():
        errors.append("title is required")
    classless_comment_override = not fields.wave_class
    if fields.wave_class and fields.wave_class not in VALID_WAVE_CLASSES:
        errors.append(f"wave_class must be one of {sorted(VALID_WAVE_CLASSES)}, got: {fields.wave_class}")
    if classless_comment_override:
        if not fields.founder_override:
            errors.append("founder_override required for classless comment-only runtime override")
        if not fields.no_op_proof:
            errors.append("no_op_proof required for classless comment-only runtime override")
        if not fields.evidence_command:
            errors.append("evidence_command required for classless comment-only runtime override")
        if not fields.evidence_delta:
            errors.append("evidence_delta required for classless comment-only runtime override")
        if not fields.progress_proof_before:
            errors.append("progress_proof_before required for classless comment-only runtime override")
        if not fields.progress_proof_after:
            errors.append("progress_proof_after required for classless comment-only runtime override")
    if not fields.target_gate_id:
        errors.append("target_gate_id is required")
    if fields.primary_blocker_class not in VALID_BLOCKER_CLASSES:
        errors.append(f"primary_blocker_class must be one of {sorted(VALID_BLOCKER_CLASSES)}, got: {fields.primary_blocker_class}")
    if fields.primary_invariant_id not in VALID_INVARIANT_IDS:
        errors.append(f"primary_invariant_id must be one of {sorted(VALID_INVARIANT_IDS)}, got: {fields.primary_invariant_id}")
    if not fields.indicator_artifact_ref:
        errors.append("indicator_artifact_ref is required")
    if not fields.indicator_collection_command:
        errors.append("indicator_collection_command is required")
    if fields.bootstrap_endgame_policy != CANONICAL_BOOTSTRAP_POLICY:
        errors.append(f"bootstrap_endgame_policy must be {CANONICAL_BOOTSTRAP_POLICY}")
    if fields.boot0_progress_state not in VALID_BOOT0_STATES:
        errors.append(f"boot0_progress_state must be one of {sorted(VALID_BOOT0_STATES)}")

    # Class-specific validation
    if fields.wave_class in ("L4_STRUCTURAL", "L4_ENABLER"):
        if not fields.evidence_command:
            errors.append(f"evidence_command required for {fields.wave_class}")
        if not fields.evidence_delta:
            errors.append(f"evidence_delta required for {fields.wave_class}")
        if not fields.progress_proof_before:
            errors.append(f"progress_proof_before required for {fields.wave_class}")
        if not fields.progress_proof_after:
            errors.append(f"progress_proof_after required for {fields.wave_class}")

    if fields.wave_class == "L4_STRUCTURAL":
        if not fields.post_gate_contract_sweep:
            errors.append("post_gate_contract_sweep required for L4_STRUCTURAL")

    if fields.wave_class == "MAINTENANCE":
        if not fields.no_op_proof:
            errors.append("no_op_proof required for MAINTENANCE")
        if not fields.defer_reason_code:
            errors.append("defer_reason_code required for MAINTENANCE")

    return errors


def render_tracker_sync_note(fields: TrackerSyncNoteFields) -> str:
    """Render a tracker sync note string matching the L4 contract parser format.

    Format: single line starting with "- Tracker sync note (<date>, <wave_id>): **<title>.** "
    followed by field: value pairs separated by ". ".
    """
    errors = validate_fields(fields)
    if errors:
        raise TrackerSyncError(f"Invalid tracker note fields: {'; '.join(errors)}")

    parts: list[str] = []
    parts.append(f"- Tracker sync note ({fields.date}, {fields.wave_id}): **{fields.title}.**")
    if fields.wave_class:
        parts.append(f"Class: {fields.wave_class}")
    else:
        parts.append("contract_path: classless FOUNDER_OVERRIDE comment-only runtime override")
    parts.append(f"target_gate_id: {fields.target_gate_id}")
    if fields.packet_ref:
        parts.append(f"Packet: `{fields.packet_ref}`")

    # STRUCTURAL-specific fields
    if fields.workload_target:
        parts.append(f"workload_target: {fields.workload_target}")
    if fields.host_semantics_delta_before:
        parts.append(f"host_semantics_delta_before: {fields.host_semantics_delta_before}")
    if fields.host_semantics_delta_after:
        parts.append(f"host_semantics_delta_after: {fields.host_semantics_delta_after}")
    if fields.structural_artifact_ref:
        parts.append(f"structural_artifact_ref: {fields.structural_artifact_ref}")

    # MAINTENANCE-specific fields
    if fields.no_op_proof:
        parts.append(f"no_op_proof: {fields.no_op_proof}")
    if fields.defer_reason_code:
        parts.append(f"defer_reason_code: {fields.defer_reason_code}")

    # Evidence fields
    if fields.evidence_command:
        parts.append(f"evidence_command: `{fields.evidence_command}`")
    if fields.evidence_delta:
        parts.append(f"evidence_delta: {fields.evidence_delta}")

    # Progress proofs
    if fields.progress_proof_before:
        parts.append(f"progress_proof_before: {fields.progress_proof_before}")
    if fields.progress_proof_after:
        parts.append(f"progress_proof_after: {fields.progress_proof_after}")

    # Sweep
    if fields.post_gate_contract_sweep:
        parts.append(f"post_gate_contract_sweep: `{fields.post_gate_contract_sweep}`")

    # Consecutive MAINTENANCE bypass
    if fields.founder_override:
        parts.append(f"FOUNDER_OVERRIDE:{fields.founder_override}")
    if fields.unblocks_wave_id:
        parts.append(f"unblocks_wave_id: {fields.unblocks_wave_id}")
    if fields.unblocks_runtime_blocker:
        parts.append(f"unblocks_runtime_blocker: {fields.unblocks_runtime_blocker}")

    # Required trailing fields
    parts.append(f"primary_blocker_class: {fields.primary_blocker_class}")
    parts.append(f"primary_invariant_id: {fields.primary_invariant_id}")
    parts.append(f"indicator_artifact_ref: {fields.indicator_artifact_ref}")
    parts.append(f"indicator_collection_command: {fields.indicator_collection_command}")
    parts.append(f"bootstrap_endgame_policy: {fields.bootstrap_endgame_policy}")
    parts.append(f"boot0_track_id: {fields.boot0_track_id}")
    parts.append(f"boot0_progress_state: {fields.boot0_progress_state}")

    # L4 parser regexes expect fields terminated by ". " (period-space).
    # Join parts with ". " so each field value ends at the next field's period.
    return ". ".join(parts) + "."


def upsert_tracker_sync_note(
    tasks_path: Path,
    fields: TrackerSyncNoteFields,
) -> None:
    """Insert or update a tracker sync note in TASKS.md.

    - If wave_id already exists: replace the existing note
    - If wave_id does not exist: append after the last tracker note in Ra section
    - Fail closed on: missing Ra section, duplicate wave_id entries, file not found
    """
    if not tasks_path.exists():
        raise TrackerSyncError(f"TASKS.md not found: {tasks_path}")

    note_text = render_tracker_sync_note(fields)
    content = tasks_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Find Ra section
    ra_start = None
    ra_end = None
    for i, line in enumerate(lines):
        if _RA_HEADER_RE.match(line):
            ra_start = i
        elif ra_start is not None and ra_end is None:
            if _SECTION_SEPARATOR_RE.match(line) and i > ra_start + 1:
                ra_end = i
                break

    if ra_start is None:
        raise TrackerSyncError("## Ra section not found in TASKS.md")

    # Check for existing notes with this wave_id
    existing_indices: list[int] = []
    search_end = ra_end if ra_end is not None else len(lines)
    for i in range(ra_start, search_end):
        m = _TRACKER_NOTE_RE.match(lines[i])
        if m and m.group(2).strip() == fields.wave_id:
            existing_indices.append(i)

    if len(existing_indices) > 1:
        raise TrackerSyncError(
            f"Duplicate tracker notes for wave_id '{fields.wave_id}' at lines {existing_indices}"
        )

    if len(existing_indices) == 1:
        # Replace existing note
        lines[existing_indices[0]] = note_text
    else:
        # Find last tracker note in Ra section to insert after
        last_note_idx = None
        for i in range(ra_start, search_end):
            if _TRACKER_NOTE_RE.match(lines[i]):
                last_note_idx = i

        if last_note_idx is None:
            raise TrackerSyncError("No existing tracker notes found in Ra section")

        # Insert after the last note (before the blank line that follows it)
        insert_at = last_note_idx + 1
        # Skip blank lines between notes
        while insert_at < search_end and lines[insert_at].strip() == "":
            insert_at += 1
        lines.insert(insert_at, "")
        lines.insert(insert_at, note_text)

    tasks_path.write_text("\n".join(lines), encoding="utf-8")
