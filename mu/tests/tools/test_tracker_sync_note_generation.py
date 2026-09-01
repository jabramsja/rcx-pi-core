"""Tests for structured tracker sync note generation and upsert."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

# Load tracker_sync_note module
_EXECUTORS_DIR = Path(__file__).resolve().parent.parent.parent / "tools" / "executors"
_spec = importlib.util.spec_from_file_location(
    "tracker_sync_note", _EXECUTORS_DIR / "tracker_sync_note.py"
)
assert _spec and _spec.loader
tracker_mod = importlib.util.module_from_spec(_spec)
sys.modules["tracker_sync_note"] = tracker_mod
_spec.loader.exec_module(tracker_mod)

TrackerSyncNoteFields = tracker_mod.TrackerSyncNoteFields
render_tracker_sync_note = tracker_mod.render_tracker_sync_note
upsert_tracker_sync_note = tracker_mod.upsert_tracker_sync_note
validate_fields = tracker_mod.validate_fields
TrackerSyncError = tracker_mod.TrackerSyncError

# Load L4 contract enforcer patterns for round-trip validation
_CHECKS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "tools" / "checks"
_l4_spec = importlib.util.spec_from_file_location(
    "enforce_l4", _CHECKS_DIR / "enforce_l4_execution_contract.py"
)
assert _l4_spec and _l4_spec.loader
l4_mod = importlib.util.module_from_spec(_l4_spec)
sys.modules["enforce_l4"] = l4_mod
_l4_spec.loader.exec_module(l4_mod)

# ANTICHEAT_OK: L4 enforcer regex aliases for round-trip testing
L4_NOTE_HEADER_RE = l4_mod._NOTE_HEADER_RE  # ANTICHEAT_OK: round-trip test
L4_CLASS_RE = l4_mod._CLASS_RE  # ANTICHEAT_OK: round-trip test
L4_GATE_RE = l4_mod._GATE_RE  # ANTICHEAT_OK: round-trip test
L4_NOP_RE = l4_mod._NOP_RE  # ANTICHEAT_OK: round-trip test
L4_DEFER_REASON_RE = l4_mod._DEFER_REASON_RE  # ANTICHEAT_OK: round-trip test
L4_BLOCKER_CLASS_RE = l4_mod._BLOCKER_CLASS_RE  # ANTICHEAT_OK: round-trip test
L4_INVARIANT_ID_RE = l4_mod._INVARIANT_ID_RE  # ANTICHEAT_OK: round-trip test
L4_INDICATOR_REF_RE = l4_mod._INDICATOR_REF_RE  # ANTICHEAT_OK: round-trip test
L4_INDICATOR_CMD_RE = l4_mod._INDICATOR_CMD_RE  # ANTICHEAT_OK: round-trip test
L4_BOOTSTRAP_POLICY_RE = l4_mod._BOOTSTRAP_POLICY_RE  # ANTICHEAT_OK: round-trip test
L4_BOOT0_TRACK_RE = l4_mod._BOOT0_TRACK_RE  # ANTICHEAT_OK: round-trip test
L4_BOOT0_PROGRESS_RE = l4_mod._BOOT0_PROGRESS_RE  # ANTICHEAT_OK: round-trip test
L4_EVIDENCE_CMD_RE = l4_mod._EVIDENCE_CMD_RE  # ANTICHEAT_OK: round-trip test
L4_EVIDENCE_DELTA_RE = l4_mod._EVIDENCE_DELTA_RE  # ANTICHEAT_OK: round-trip test
L4_PROGRESS_BEFORE_RE = l4_mod._PROGRESS_BEFORE_RE  # ANTICHEAT_OK: round-trip test
L4_PROGRESS_AFTER_RE = l4_mod._PROGRESS_AFTER_RE  # ANTICHEAT_OK: round-trip test
L4_FOUNDER_OVERRIDE_RE = l4_mod._FOUNDER_OVERRIDE_RE  # ANTICHEAT_OK: round-trip test
L4_UNBLOCKS_WAVE_RE = l4_mod._UNBLOCKS_WAVE_RE  # ANTICHEAT_OK: round-trip test
L4_UNBLOCKS_BLOCKER_RE = l4_mod._UNBLOCKS_BLOCKER_RE  # ANTICHEAT_OK: round-trip test


def _make_maintenance_fields(**overrides: str) -> TrackerSyncNoteFields:
    defaults = dict(
        wave_id="test-wave",
        title="TEST — maintenance wave",
        wave_class="MAINTENANCE",
        target_gate_id="G8",
        no_op_proof="docs-only changes, no runtime files",
        defer_reason_code="DOC_SYNC",
        primary_blocker_class="INTEGRATION",
        primary_invariant_id="INV_STRUCTURAL_FORWARD_MOTION",
        indicator_artifact_ref="reports/l4_wave_indicators/test-wave.json",
        indicator_collection_command="python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id test-wave --output reports/l4_wave_indicators/test-wave.json",
        date="2026-03-23",
    )
    defaults.update(overrides)
    return TrackerSyncNoteFields(**defaults)


def _make_enabler_fields(**overrides: str) -> TrackerSyncNoteFields:
    defaults = dict(
        wave_id="test-enabler",
        title="TEST — enabler wave",
        wave_class="L4_ENABLER",
        target_gate_id="G8",
        evidence_command="PYTHONHASHSEED=0 pytest mu/tests/tools/ -q",
        evidence_delta="(1) New helper module. (2) Updated handoff schema",
        progress_proof_before="No structured tracker generation existed",
        progress_proof_after="Structured tracker generation with L4 round-trip",
        primary_blocker_class="INTEGRATION",
        primary_invariant_id="INV_STRUCTURAL_FORWARD_MOTION",
        indicator_artifact_ref="reports/l4_wave_indicators/test-enabler.json",
        indicator_collection_command="python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id test-enabler --output reports/l4_wave_indicators/test-enabler.json",
        date="2026-03-23",
    )
    defaults.update(overrides)
    return TrackerSyncNoteFields(**defaults)


def _make_classless_comment_override_fields(**overrides: str) -> TrackerSyncNoteFields:
    defaults = dict(
        wave_id="test-classless-comment-runtime",
        title="TEST — classless runtime comment override",
        wave_class="",
        target_gate_id="G8",
        no_op_proof="comment-only runtime text update",
        evidence_command="python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id test-classless-comment-runtime --output reports/l4_wave_indicators/test-classless-comment-runtime.json",
        evidence_delta="(1) Runtime file text changed only in comments. (2) No executable delta.",
        progress_proof_before="Debt map named the stale marker owner",
        progress_proof_after="Debt map names the active marker owner",
        founder_override="test-classless-comment-runtime",
        primary_blocker_class="INTEGRATION",
        primary_invariant_id="INV_STRUCTURAL_FORWARD_MOTION",
        indicator_artifact_ref="reports/l4_wave_indicators/test-classless-comment-runtime.json",
        indicator_collection_command="python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id test-classless-comment-runtime --output reports/l4_wave_indicators/test-classless-comment-runtime.json",
        date="2026-03-23",
    )
    defaults.update(overrides)
    return TrackerSyncNoteFields(**defaults)


class TestRenderTrackerSyncNote:
    """Test that rendered notes match L4 contract parser expectations."""

    def test_maintenance_note_accepted_by_l4_parser(self):
        fields = _make_maintenance_fields()
        note = render_tracker_sync_note(fields)

        # Verify the L4 parser can extract all required fields
        assert L4_NOTE_HEADER_RE.search(note), "L4 header regex must match"
        assert L4_CLASS_RE.search(note), "L4 class regex must match"
        assert L4_GATE_RE.search(note), "L4 gate regex must match"
        assert L4_NOP_RE.search(note), "L4 no_op_proof regex must match"
        assert L4_DEFER_REASON_RE.search(note), "L4 defer_reason regex must match"
        assert L4_BLOCKER_CLASS_RE.search(note), "L4 blocker_class regex must match"
        assert L4_INVARIANT_ID_RE.search(note), "L4 invariant_id regex must match"
        assert L4_INDICATOR_REF_RE.search(note), "L4 indicator_ref regex must match"
        assert L4_INDICATOR_CMD_RE.search(note), "L4 indicator_cmd regex must match"
        assert L4_BOOTSTRAP_POLICY_RE.search(note), "L4 bootstrap_policy regex must match"
        assert L4_BOOT0_TRACK_RE.search(note), "L4 boot0_track regex must match"
        assert L4_BOOT0_PROGRESS_RE.search(note), "L4 boot0_progress regex must match"

    def test_enabler_note_has_evidence_fields(self):
        fields = _make_enabler_fields()
        note = render_tracker_sync_note(fields)

        assert L4_EVIDENCE_CMD_RE.search(note), "evidence_command must be present"
        assert L4_EVIDENCE_DELTA_RE.search(note), "evidence_delta must be present"
        assert L4_PROGRESS_BEFORE_RE.search(note), "progress_proof_before must be present"
        assert L4_PROGRESS_AFTER_RE.search(note), "progress_proof_after must be present"

    def test_note_starts_with_canonical_prefix(self):
        fields = _make_maintenance_fields()
        note = render_tracker_sync_note(fields)
        assert note.startswith("- Tracker sync note (2026-03-23, test-wave): **TEST")

    def test_wave_id_extracted_correctly(self):
        fields = _make_maintenance_fields(wave_id="my-custom-wave")
        note = render_tracker_sync_note(fields)
        m = L4_NOTE_HEADER_RE.search(note)
        assert m
        assert m.group(2) == "my-custom-wave"

    def test_founder_override_rendered(self):
        fields = _make_maintenance_fields(
            founder_override="test-override",
            unblocks_wave_id="wave-next-thing",
            unblocks_runtime_blocker="RT-TEST-BLOCKER",
        )
        note = render_tracker_sync_note(fields)
        assert L4_FOUNDER_OVERRIDE_RE.search(note)
        assert L4_UNBLOCKS_WAVE_RE.search(note)
        assert L4_UNBLOCKS_BLOCKER_RE.search(note)

    def test_classless_comment_runtime_override_note_has_no_class_marker(self):
        fields = _make_classless_comment_override_fields()
        note = render_tracker_sync_note(fields)

        assert L4_NOTE_HEADER_RE.search(note), "L4 header regex must match"
        assert not L4_CLASS_RE.search(note), "classless override must not emit Class:"
        assert "contract_path: classless FOUNDER_OVERRIDE comment-only runtime override" in note
        assert L4_GATE_RE.search(note), "target gate regex must match"
        assert L4_NOP_RE.search(note), "no_op_proof regex must match"
        assert L4_EVIDENCE_CMD_RE.search(note), "evidence_command must be present"
        assert L4_EVIDENCE_DELTA_RE.search(note), "evidence_delta must be present"
        assert L4_PROGRESS_BEFORE_RE.search(note), "progress_proof_before must be present"
        assert L4_PROGRESS_AFTER_RE.search(note), "progress_proof_after must be present"
        assert L4_FOUNDER_OVERRIDE_RE.search(note), "FOUNDER_OVERRIDE must be present"


class TestValidateFields:
    """Test field validation catches missing/invalid fields."""

    def test_valid_maintenance_fields(self):
        fields = _make_maintenance_fields()
        errors = validate_fields(fields)
        assert errors == []

    def test_valid_classless_comment_runtime_override_fields(self):
        fields = _make_classless_comment_override_fields()
        errors = validate_fields(fields)
        assert errors == []

    def test_missing_wave_id(self):
        fields = _make_maintenance_fields(wave_id="")
        errors = validate_fields(fields)
        assert any("wave_id" in e for e in errors)

    def test_invalid_wave_class(self):
        fields = _make_maintenance_fields(wave_class="INVALID")
        errors = validate_fields(fields)
        assert any("wave_class" in e for e in errors)

    def test_missing_no_op_proof_for_maintenance(self):
        fields = _make_maintenance_fields(no_op_proof="")
        errors = validate_fields(fields)
        assert any("no_op_proof" in e for e in errors)

    def test_missing_evidence_for_enabler(self):
        fields = _make_enabler_fields(evidence_command="")
        errors = validate_fields(fields)
        assert any("evidence_command" in e for e in errors)

    def test_invalid_target_gate_id_rejected(self):
        fields = _make_enabler_fields(target_gate_id="none")
        errors = validate_fields(fields)
        assert any("target_gate_id must match G1-G8" in e for e in errors)

    def test_render_rejects_invalid_target_gate_id(self):
        fields = _make_enabler_fields(target_gate_id="none")
        with pytest.raises(TrackerSyncError, match="target_gate_id must match G1-G8"):
            render_tracker_sync_note(fields)

    def test_invalid_invariant_id(self):
        fields = _make_maintenance_fields(primary_invariant_id="INVALID")
        errors = validate_fields(fields)
        assert any("primary_invariant_id" in e for e in errors)

    def test_render_raises_on_invalid_fields(self):
        fields = _make_maintenance_fields(wave_id="")
        with pytest.raises(TrackerSyncError, match="Invalid tracker note fields"):
            render_tracker_sync_note(fields)


class TestUpsertTrackerSyncNote:
    """Test TASKS.md upsert behavior."""

    _TASKS_TEMPLATE = """# RCX Task List

## Ra (Resolved / Merged)

Items here are done.

- Tracker sync note (2026-03-22, existing-wave): **EXISTING — test note.** Class: MAINTENANCE. target_gate_id: G8. no_op_proof: test. defer_reason_code: TEST. primary_blocker_class: INTEGRATION. primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. indicator_artifact_ref: reports/l4_wave_indicators/existing-wave.json. indicator_collection_command: test. bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. boot0_track_id: V1. boot0_progress_state: HOLD.

---

## NEXT (short, bounded follow-ups)

- Some NEXT item
"""

    def test_append_new_note(self, tmp_path):
        tasks = tmp_path / "TASKS.md"
        tasks.write_text(self._TASKS_TEMPLATE)

        fields = _make_maintenance_fields(wave_id="new-wave")
        upsert_tracker_sync_note(tasks, fields)

        content = tasks.read_text()
        assert "new-wave" in content
        assert content.count("new-wave") == 1
        # Original note still present
        assert "existing-wave" in content

    @pytest.mark.parametrize(
        "blank_count",
        [
            pytest.param(0, id="zero-blank-lines"),
            pytest.param(1, id="one-blank-line"),
            pytest.param(3, id="multiple-blank-lines"),
        ],
    )
    def test_tracker_block_adjacency_preserves_indented_evidence_children(
        self,
        tmp_path,
        blank_count,
    ):
        tasks = tmp_path / "TASKS.md"
        parent = (
            "- Tracker sync note (2026-03-22, existing-wave): **EXISTING — test "
            "note.** Class: MAINTENANCE. target_gate_id: G8."
        )
        child = "  - Recovery evidence: the prior wave retained this child."
        prefix = (
            "# RCX Task List\n\n"
            "## Ra (Resolved / Merged)\n\n"
            f"{parent}\n"
            + ("\n" * blank_count)
            + f"{child}\n\n"
        )
        suffix = "---\n\n## NEXT (short, bounded follow-ups)\n\n- Some NEXT item\n"
        original = prefix + suffix
        tasks.write_text(original, encoding="utf-8")
        fields = _make_maintenance_fields(wave_id="new-wave")
        rendered_note = render_tracker_sync_note(fields)

        upsert_tracker_sync_note(tasks, fields)

        content = tasks.read_text(encoding="utf-8")
        assert content == prefix + rendered_note + "\n\n" + suffix
        assert content.index(parent) < content.index(child) < content.index(rendered_note)

    def test_update_existing_note(self, tmp_path):
        tasks = tmp_path / "TASKS.md"
        tasks.write_text(self._TASKS_TEMPLATE)

        fields = _make_maintenance_fields(wave_id="existing-wave", title="UPDATED — new title")
        upsert_tracker_sync_note(tasks, fields)

        content = tasks.read_text()
        assert "UPDATED — new title" in content
        # Should not duplicate
        assert content.count("existing-wave") == 1

    def test_fail_on_duplicate_entries(self, tmp_path):
        # Create TASKS.md with duplicate wave_id
        dup_content = self._TASKS_TEMPLATE.replace(
            "---\n\n## NEXT",
            "- Tracker sync note (2026-03-22, existing-wave): **DUPLICATE.** Class: MAINTENANCE. target_gate_id: G8. no_op_proof: x. defer_reason_code: x. primary_blocker_class: INTEGRATION. primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. indicator_artifact_ref: x. indicator_collection_command: x. bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. boot0_track_id: V1. boot0_progress_state: HOLD.\n\n---\n\n## NEXT",
        )
        tasks = tmp_path / "TASKS.md"
        tasks.write_text(dup_content)

        fields = _make_maintenance_fields(wave_id="existing-wave")
        with pytest.raises(TrackerSyncError, match="Duplicate"):
            upsert_tracker_sync_note(tasks, fields)

    def test_fail_on_missing_ra_section(self, tmp_path):
        tasks = tmp_path / "TASKS.md"
        tasks.write_text("# No Ra section here\n## NEXT\n")

        fields = _make_maintenance_fields()
        with pytest.raises(TrackerSyncError, match="Ra section not found"):
            upsert_tracker_sync_note(tasks, fields)

    def test_note_inserted_in_ra_not_next(self, tmp_path):
        tasks = tmp_path / "TASKS.md"
        tasks.write_text(self._TASKS_TEMPLATE)

        fields = _make_maintenance_fields(wave_id="new-wave")
        upsert_tracker_sync_note(tasks, fields)

        content = tasks.read_text()
        ra_pos = content.index("## Ra")
        next_pos = content.index("## NEXT")
        new_wave_pos = content.index("new-wave")
        assert ra_pos < new_wave_pos < next_pos
