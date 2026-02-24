"""
Tests for the L4 Execution Contract enforcement checker.

Validates that enforce_l4_execution_contract.py correctly classifies
L4_STRUCTURAL, L4_ENABLER, and MAINTENANCE waves (v2 3-class model),
including anti-loophole rules. Legacy L4_CLASS_A alias is tested for
backward compatibility.

Usage:
    PYTHONHASHSEED=0 pytest tests/tools/test_l4_execution_contract_enforcement.py -v
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

from tests.repo_root import REPO_ROOT
sys.path.insert(0, str(REPO_ROOT))

# Import the enforcement module directly
sys.path.insert(0, str(REPO_ROOT / "tools" / "checks"))
from enforce_l4_execution_contract import (
    LEGACY_CLASS_ALIAS,
    NON_GATE_TEST_DOMAINS,
    RUNTIME_DIRS,
    VALID_BLOCKER_CLASSES,
    VALID_INVARIANT_IDS,
    VALID_WAVE_CLASSES,
    enforce,
    filter_to_tracked_files,
    validate_indicator_artifact_json,
    has_non_comment_runtime_delta,
    is_comment_line,
    is_runtime_file,
    parse_tracker_notes,
)


def _run_checker_cli(args: list[str], *, clean_index: bool = False) -> subprocess.CompletedProcess:
    """Run checker CLI with optional temporary clean git index."""
    cmd = ["python3", "tools/checks/enforce_l4_execution_contract.py"] + args
    env = os.environ.copy()
    if not clean_index:
        return subprocess.run(cmd, capture_output=True, text=True)

    with tempfile.NamedTemporaryFile(delete=False) as tf:
        index_path = tf.name
    try:
        env["GIT_INDEX_FILE"] = index_path
        subprocess.run(["git", "read-tree", "HEAD"], check=True, capture_output=True, env=env)
        return subprocess.run(cmd, capture_output=True, text=True, env=env)
    finally:
        Path(index_path).unlink(missing_ok=True)


# =============================================================================
# is_runtime_file
# =============================================================================


class TestIsRuntimeFile:
    """Verify runtime directory classification."""

    @pytest.mark.parametrize("path", [
        "mu/host/js/eval_step.js",
        "mu/substrate/kernel.v1.json",
        "mu/closures/recurrence.v1.json",
        "mu/bridge/bootstrap_structural.v1.json",
        "mu/programs/hemispheres.v1.json",
        "rcx_pi/selfhost/eval_seed.py",
        "tools/compilers/compile_seed.py",
    ])
    def test_runtime_files_detected(self, path: str) -> None:
        assert is_runtime_file(path), f"{path} should be classified as runtime"

    @pytest.mark.parametrize("path", [
        "README.md",
        "STATUS.md",
        "TASKS.md",
        "tests/test_foo.py",
        "tools/checks/check_foo.sh",
        "mu/docs/core/SomeDoc.md",
        ".github/workflows/ci.yml",
    ])
    def test_non_runtime_files_rejected(self, path: str) -> None:
        assert not is_runtime_file(path), f"{path} should NOT be classified as runtime"


# =============================================================================
# is_comment_line
# =============================================================================


class TestIsCommentLine:
    """Verify comment-only line detection."""

    @pytest.mark.parametrize("line", [
        "+# This is a Python comment",
        "-// JS single-line comment",
        "+ * JS block comment line",
        "+/* block start",
        "+*/ block end",
        '+"""docstring"""',
        "+    # indented comment",
        "+",  # blank added line
        "-",  # blank removed line
    ])
    def test_comment_lines_detected(self, line: str) -> None:
        assert is_comment_line(line), f"Should be comment-only: {line!r}"

    @pytest.mark.parametrize("line", [
        "+def foo():",
        "-return 42",
        "+x = 1  # with trailing comment",
        "+const y = 2; // trailing comment",
        "+RUNTIME_DIRS = ('mu/host/',)",
    ])
    def test_code_lines_not_comment(self, line: str) -> None:
        assert not is_comment_line(line), f"Should NOT be comment-only: {line!r}"


# =============================================================================
# L4_STRUCTURAL enforcement (v2 — replaces L4_CLASS_A)
# =============================================================================


class TestL4StructuralEnforcement:
    """L4_STRUCTURAL waves must touch runtime with executable delta."""

    def test_structural_with_runtime_files_passes(self) -> None:
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_foo.py"]
        passed, errors = enforce("L4_STRUCTURAL", files)
        assert passed, f"Should pass: {errors}"

    def test_structural_no_runtime_files_fails(self) -> None:
        files = ["README.md", "STATUS.md", "tests/l4_gates/test_foo.py"]
        passed, errors = enforce("L4_STRUCTURAL", files)
        assert not passed
        assert any("no runtime/substrate files" in e for e in errors)

    def test_structural_comment_only_runtime_delta_fails(self) -> None:
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "--- a/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,3 @@\n"
            "-# Old comment\n"
            "+# New comment\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff)
        assert not passed
        assert any("comment-only" in e for e in errors)

    def test_structural_executable_runtime_delta_passes(self) -> None:
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "--- a/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -10,3 +10,4 @@\n"
            "+def new_function(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff)
        assert passed, f"Should pass with executable delta: {errors}"

    def test_structural_missing_gate_test_fails(self) -> None:
        """L4_STRUCTURAL without tests/l4_gates/ change fails (AND rule)."""
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/test_foo.py"]
        passed, errors = enforce("L4_STRUCTURAL", files)
        assert not passed
        assert any("tests/l4_gates/" in e for e in errors)


# =============================================================================
# L4_ENABLER enforcement (v2 — new class)
# =============================================================================


class TestL4EnablerEnforcement:
    """L4_ENABLER waves MUST NOT touch runtime/substrate dirs."""

    def test_enabler_no_runtime_passes(self) -> None:
        files = ["tools/checks/foo.py", "tests/l4_gates/test_bar.py"]
        passed, errors = enforce("L4_ENABLER", files)
        assert passed, f"Should pass: {errors}"

    def test_enabler_touching_runtime_fails(self) -> None:
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_bar.py"]
        passed, errors = enforce("L4_ENABLER", files)
        assert not passed
        assert any("L4_ENABLER" in e and "runtime" in e for e in errors)

    def test_enabler_touching_mu_host_fails(self) -> None:
        files = ["mu/host/js/eval_step.js"]
        passed, errors = enforce("L4_ENABLER", files)
        assert not passed
        assert any("runtime" in e for e in errors)

    def test_enabler_touching_substrate_fails(self) -> None:
        files = ["mu/substrate/kernel.v1.json", "tests/l4_gates/test_bar.py"]
        passed, errors = enforce("L4_ENABLER", files)
        assert not passed
        assert any("L4_ENABLER" in e for e in errors)


# =============================================================================
# MAINTENANCE enforcement
# =============================================================================


class TestMaintenanceEnforcement:
    """MAINTENANCE waves must NOT touch runtime.

    Note: These tests mock check_consecutive_maintenance and
    check_maintenance_metadata to isolate from TASKS.md state.
    """

    def test_maintenance_no_runtime_passes(self) -> None:
        """MAINTENANCE with no runtime files and valid notes passes."""
        files = ["README.md", "STATUS.md", "TASKS.md"]
        notes = [{
            "wave_id": "test",
            "raw_class": "MAINTENANCE",
            "wave_class": "MAINTENANCE",
            "gate": "G8",
            "no_op_proof": "docs only",
            "evidence_command": None,
            "evidence_delta": None,
            "host_semantics_delta_before": None,
            "host_semantics_delta_after": None,
            "structural_artifact_ref": None,
            "defer_reason_code": "ENABLER_PREREQUISITE",
            "founder_override": None,
            "primary_blocker_class": "INTEGRATION",
            "post_gate_contract_sweep": None,
            "primary_invariant_id": "INV_STRUCTURAL_FORWARD_MOTION",
            "progress_proof_before": None,
            "progress_proof_after": None,
            "indicator_artifact_ref": "reports/l4_wave_indicators/test-wave.json",
            "indicator_collection_command": "python3 tools/metrics/collect_l4_wave_indicators.py --wave-id test-wave",
            "bootstrap_endgame_policy": "SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP",
            "boot0_track_id": "N6b",
            "boot0_progress_state": "ADVANCE",
            "date": "2026-02-20",
            "raw": "test note",
        }]
        passed, errors = enforce("MAINTENANCE", files, notes=notes)
        assert passed, f"Should pass: {errors}"

    def test_maintenance_touching_runtime_fails(self) -> None:
        files = ["rcx_pi/selfhost/eval_seed.py", "README.md"]
        passed, errors = enforce("MAINTENANCE", files)
        assert not passed
        assert any("touches runtime" in e for e in errors)

    def test_maintenance_touching_mu_host_fails(self) -> None:
        files = ["mu/host/js/eval_step.js"]
        passed, errors = enforce("MAINTENANCE", files)
        assert not passed
        assert any("touches runtime" in e for e in errors)


# =============================================================================
# Edge cases
# =============================================================================


class TestEnforceEdgeCases:
    """Edge cases and boundaries."""

    def test_no_wave_class_no_runtime_passes(self) -> None:
        """No wave class marker + no runtime files = skip."""
        passed, errors = enforce(None, ["README.md", "tests/test_foo.py"])
        assert passed
        assert not errors

    def test_no_wave_class_with_runtime_fails_closed(self) -> None:
        """No wave class marker + runtime files = FAIL-CLOSED."""
        passed, errors = enforce(None, ["rcx_pi/selfhost/eval_seed.py"])
        assert not passed
        assert any("FAIL-CLOSED" in e for e in errors)

    def test_unknown_wave_class_fails(self) -> None:
        passed, errors = enforce("UNKNOWN_CLASS", ["README.md"])
        assert not passed
        assert any("Unknown wave class" in e for e in errors)

    def test_runtime_dirs_constant_covers_all_documented_paths(self) -> None:
        """RUNTIME_DIRS must cover all 7 documented paths."""
        expected_prefixes = {
            "mu/host/",
            "mu/substrate/",
            "mu/closures/",
            "mu/bridge/",
            "mu/programs/",
            "rcx_pi/selfhost/",
            "tools/compilers/",
        }
        assert set(RUNTIME_DIRS) == expected_prefixes


# =============================================================================
# has_non_comment_runtime_delta
# =============================================================================


class TestHasNonCommentRuntimeDelta:
    """Verify diff parsing for runtime deltas."""

    def test_added_code_line_detected(self) -> None:
        diff = (
            "diff --git a/mu/host/js/eval_step.js b/mu/host/js/eval_step.js\n"
            "+++ b/mu/host/js/eval_step.js\n"
            "@@ -1,3 +1,4 @@\n"
            "+function newFunc() { return 42; }\n"
        )
        assert has_non_comment_runtime_delta(diff, ["mu/host/js/eval_step.js"])

    def test_only_comment_changes_not_detected(self) -> None:
        diff = (
            "diff --git a/mu/host/js/eval_step.js b/mu/host/js/eval_step.js\n"
            "+++ b/mu/host/js/eval_step.js\n"
            "@@ -1,3 +1,3 @@\n"
            "-// old comment\n"
            "+// new comment\n"
        )
        assert not has_non_comment_runtime_delta(diff, ["mu/host/js/eval_step.js"])

    def test_non_runtime_file_ignored(self) -> None:
        diff = (
            "diff --git a/README.md b/README.md\n"
            "+++ b/README.md\n"
            "@@ -1,3 +1,4 @@\n"
            "+New executable line\n"
        )
        assert not has_non_comment_runtime_delta(diff, [])


# =============================================================================
# Wave-scoped metadata parsing
# =============================================================================


class TestParseTrackerNotes:
    """Verify wave-scoped metadata parsing from tracker sync notes."""

    SAMPLE_RA = (
        "## Ra (Resolved / Merged)\n\n"
        "- Tracker sync note (2026-02-20, wave-c): **Wave C.** Class: MAINTENANCE. "
        "Gate: G8. NO_OP_PROOF: Docs only. No runtime change.\n"
        "- Tracker sync note (2026-02-20, wave-b): **Wave B.** Class: L4_STRUCTURAL. "
        "Gate: G5. Evidence: Added new runtime function.\n"
        "- Tracker sync note (2026-02-19, wave-a): **Wave A.** Class: MAINTENANCE. "
        "Gate: G3. NO_OP_PROOF: Tooling only.\n"
        "- Tracker sync note (2026-02-18, no-class): **No class marker wave.** "
        "No phase/debt change.\n"
    )

    def test_parses_notes_in_document_order(self) -> None:
        notes = parse_tracker_notes(self.SAMPLE_RA)
        assert len(notes) == 3  # only notes with Class: markers
        assert notes[0]["wave_class"] == "MAINTENANCE"
        assert notes[1]["wave_class"] == "L4_STRUCTURAL"
        assert notes[2]["wave_class"] == "MAINTENANCE"

    def test_extracts_gate_per_note(self) -> None:
        notes = parse_tracker_notes(self.SAMPLE_RA)
        assert notes[0]["gate"] == "G8"
        assert notes[1]["gate"] == "G5"
        assert notes[2]["gate"] == "G3"

    def test_extracts_no_op_proof_only_for_maintenance(self) -> None:
        notes = parse_tracker_notes(self.SAMPLE_RA)
        assert notes[0]["no_op_proof"] is not None  # MAINTENANCE
        assert notes[1]["no_op_proof"] is None       # L4_STRUCTURAL
        assert notes[2]["no_op_proof"] is not None  # MAINTENANCE

    def test_skips_notes_without_class_marker(self) -> None:
        notes = parse_tracker_notes(self.SAMPLE_RA)
        raw_texts = [n["raw"] for n in notes]
        assert not any("no-class" in r for r in raw_texts)

    def test_empty_text_returns_empty(self) -> None:
        assert parse_tracker_notes("") == []
        assert parse_tracker_notes("No tracker sync notes here.") == []

    def test_consecutive_maintenance_detected(self) -> None:
        """Two consecutive MAINTENANCE notes → consecutive cap hit."""
        text = (
            "## Ra\n\n"
            "- Tracker sync note (d, w2): **W2.** Class: MAINTENANCE. Gate: G1. NO_OP_PROOF: x.\n"
            "- Tracker sync note (d, w1): **W1.** Class: MAINTENANCE. Gate: G1. NO_OP_PROOF: y.\n"
        )
        notes = parse_tracker_notes(text)
        assert len(notes) == 2
        assert notes[0]["wave_class"] == "MAINTENANCE"
        assert notes[1]["wave_class"] == "MAINTENANCE"

    def test_no_consecutive_when_structural_intervenes(self) -> None:
        """MAINTENANCE then L4_STRUCTURAL → no consecutive cap."""
        text = (
            "## Ra\n\n"
            "- Tracker sync note (d, w2): **W2.** Class: MAINTENANCE. Gate: G1. NO_OP_PROOF: x.\n"
            "- Tracker sync note (d, w1): **W1.** Class: L4_STRUCTURAL. Gate: G5. Evidence: y.\n"
        )
        notes = parse_tracker_notes(text)
        assert notes[0]["wave_class"] == "MAINTENANCE"
        assert notes[1]["wave_class"] == "L4_STRUCTURAL"


# =============================================================================
# Legacy backward compatibility
# =============================================================================


class TestLegacyBackwardCompat:
    """Historical L4_CLASS_A notes must parse correctly via alias."""

    def test_legacy_alias_maps_to_structural(self) -> None:
        assert LEGACY_CLASS_ALIAS == {"L4_CLASS_A": "L4_STRUCTURAL"}

    def test_legacy_notes_parse_with_alias(self) -> None:
        text = (
            "## Ra\n\n"
            "- Tracker sync note (2026-02-20, old-wave): **Old wave.** "
            "Class: L4_CLASS_A. Gate: G8. Evidence: runtime fix.\n"
        )
        notes = parse_tracker_notes(text)
        assert len(notes) == 1
        assert notes[0]["raw_class"] == "L4_CLASS_A"
        assert notes[0]["wave_class"] == "L4_STRUCTURAL"

    def test_three_class_model_defined(self) -> None:
        assert VALID_WAVE_CLASSES == frozenset({"L4_STRUCTURAL", "L4_ENABLER", "MAINTENANCE"})

    def test_l4_class_a_not_in_valid_classes(self) -> None:
        """L4_CLASS_A is NOT a valid new class — only parsed as legacy alias."""
        assert "L4_CLASS_A" not in VALID_WAVE_CLASSES


# =============================================================================
# Negative tests for loopholes
# =============================================================================


class TestLoopholeDetection:
    """Verify anti-loophole rules are enforced."""

    def test_maintenance_plus_runtime_touch_fails(self) -> None:
        """MAINTENANCE wave touching runtime file = violation."""
        passed, errors = enforce("MAINTENANCE", ["mu/substrate/kernel.v1.json"])
        assert not passed
        assert any("touches runtime" in e for e in errors)

    def test_structural_comment_only_in_js_fails(self) -> None:
        """L4_STRUCTURAL with only JS comment changes = violation."""
        files = ["mu/host/js/eval_step.js", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/mu/host/js/eval_step.js b/mu/host/js/eval_step.js\n"
            "+++ b/mu/host/js/eval_step.js\n"
            "@@ -1,3 +1,3 @@\n"
            "-// Same 5 bootstrap primitives\n"
            "+// Same 4 bootstrap primitives\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff)
        assert not passed
        assert any("comment-only" in e for e in errors)

    def test_structural_docstring_only_fails(self) -> None:
        """L4_STRUCTURAL with only Python docstring changes = violation."""
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,3 @@\n"
            '-\"\"\"Old docstring.\"\"\"\n'
            '+\"\"\"New docstring.\"\"\"\n'
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff)
        assert not passed
        assert any("comment-only" in e for e in errors)

    def test_enabler_cannot_claim_host_delta(self) -> None:
        """L4_ENABLER claiming host_semantics_delta without runtime is a violation."""
        notes = [{
            "wave_id": "test",
            "raw_class": "L4_ENABLER",
            "wave_class": "L4_ENABLER",
            "gate": "G8",
            "no_op_proof": None,
            "evidence_command": "pytest tests/",
            "evidence_delta": "new tooling",
            "host_semantics_delta_before": "some delta",
            "host_semantics_delta_after": "some after",
            "structural_artifact_ref": None,
            "defer_reason_code": None,
            "founder_override": None,
            "primary_blocker_class": "INTEGRATION",
            "post_gate_contract_sweep": None,
            "primary_invariant_id": "INV_STRUCTURAL_FORWARD_MOTION",
            "progress_proof_before": "before-state",
            "progress_proof_after": "after-state",
            "indicator_artifact_ref": "reports/l4_wave_indicators/test-wave.json",
            "indicator_collection_command": "python3 tools/metrics/collect_l4_wave_indicators.py --wave-id test-wave",
            "bootstrap_endgame_policy": "SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP",
            "boot0_track_id": "N6b",
            "boot0_progress_state": "ADVANCE",
            "date": "2026-02-20",
            "raw": "test note",
        }]
        files = ["tools/checks/foo.py"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert not passed
        assert any("host_semantics_delta" in e for e in errors)


# =============================================================================
# Fix D: evidence_command must reference tests/l4_gates/
# =============================================================================


class TestEvidenceCommandTarget:
    """L4_STRUCTURAL evidence_command must reference tests/l4_gates/ target."""

    def test_evidence_command_without_l4_gates_fails(self) -> None:
        notes = [{
            "wave_id": "test",
            "raw_class": "L4_STRUCTURAL",
            "wave_class": "L4_STRUCTURAL",
            "gate": "G8",
            "no_op_proof": None,
            "evidence_command": "pytest tests/engine/",
            "evidence_delta": "added function",
            "host_semantics_delta_before": "before runtime projection dispatch update",
            "host_semantics_delta_after": "after runtime projection dispatch update",
            "structural_artifact_ref": "mu/substrate/kernel.v1.json",
            "defer_reason_code": None,
            "founder_override": None,
            "primary_blocker_class": "INTEGRATION",
            "post_gate_contract_sweep": "pytest tests/structural/",
            "primary_invariant_id": "INV_STRUCTURAL_FORWARD_MOTION",
            "progress_proof_before": "before-state",
            "progress_proof_after": "after-state",
            "indicator_artifact_ref": "reports/l4_wave_indicators/test-wave.json",
            "indicator_collection_command": "python3 tools/metrics/collect_l4_wave_indicators.py --wave-id test-wave",
            "bootstrap_endgame_policy": "SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP",
            "boot0_track_id": "N6b",
            "boot0_progress_state": "ADVANCE",
            "date": "2026-02-20",
            "raw": "test note",
        }]
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def foo(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert not passed
        assert any("tests/l4_gates/" in e for e in errors)

    def test_evidence_command_with_l4_gates_passes(self) -> None:
        notes = [{
            "wave_id": "test",
            "raw_class": "L4_STRUCTURAL",
            "wave_class": "L4_STRUCTURAL",
            "gate": "G8",
            "no_op_proof": None,
            "evidence_command": "pytest tests/l4_gates/test_gate.py",
            "evidence_delta": "added function",
            "host_semantics_delta_before": "before runtime projection dispatch update",
            "host_semantics_delta_after": "after runtime projection dispatch update",
            "structural_artifact_ref": "mu/substrate/kernel.v1.json",
            "defer_reason_code": None,
            "founder_override": None,
            "primary_blocker_class": "INTEGRATION",
            "post_gate_contract_sweep": "pytest tests/structural/ tests/engine/",
            "primary_invariant_id": "INV_STRUCTURAL_FORWARD_MOTION",
            "progress_proof_before": "before-state",
            "progress_proof_after": "after-state",
            "indicator_artifact_ref": "reports/l4_wave_indicators/test-wave.json",
            "indicator_collection_command": "python3 tools/metrics/collect_l4_wave_indicators.py --wave-id test-wave",
            "bootstrap_endgame_policy": "SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP",
            "boot0_track_id": "N6b",
            "boot0_progress_state": "ADVANCE",
            "date": "2026-02-20",
            "raw": "test note",
        }]
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def foo(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert passed, f"Should pass with l4_gates ref: {errors}"

    def test_mu_physical_gate_test_path_accepted(self) -> None:
        """mu/tests/l4_gates/ physical path accepted for L4_STRUCTURAL file evidence."""
        files = ["mu/host/js/eval_step.js", "mu/tests/l4_gates/test_boot1.py"]
        diff = (
            "diff --git a/mu/host/js/eval_step.js b/mu/host/js/eval_step.js\n"
            "+++ b/mu/host/js/eval_step.js\n"
            "@@ -1,3 +1,4 @@\n"
            "+const x = true;\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff)
        assert passed, f"mu/tests/l4_gates/ path should be accepted: {errors}"

    def test_mu_physical_evidence_command_accepted(self) -> None:
        """mu/tests/l4_gates/ in evidence_command accepted for L4_STRUCTURAL."""
        notes = [{
            "wave_id": "test",
            "raw_class": "L4_STRUCTURAL",
            "wave_class": "L4_STRUCTURAL",
            "gate": "G8",
            "no_op_proof": None,
            "evidence_command": "pytest mu/tests/l4_gates/test_boot1_default_routing_gate.py -q",
            "evidence_delta": "flipped boot1 default",
            "host_semantics_delta_before": "trampoline default",
            "host_semantics_delta_after": "boot1 default",
            "structural_artifact_ref": "mu/programs/rcx_engine.v1.json",
            "defer_reason_code": None,
            "founder_override": None,
            "primary_blocker_class": "INTEGRATION",
            "post_gate_contract_sweep": "pytest tests/structural/",
            "primary_invariant_id": "INV_STRUCTURAL_FORWARD_MOTION",
            "progress_proof_before": "before-state",
            "progress_proof_after": "after-state",
            "indicator_artifact_ref": "reports/l4_wave_indicators/test-wave.json",
            "indicator_collection_command": "python3 tools/metrics/collect_l4_wave_indicators.py --wave-id test-wave",
            "bootstrap_endgame_policy": "SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP",
            "boot0_track_id": "N6b",
            "boot0_progress_state": "ADVANCE",
            "date": "2026-02-20",
            "raw": "test note",
        }]
        files = ["mu/host/js/eval_step.js", "mu/tests/l4_gates/test_boot1.py"]
        diff = (
            "diff --git a/mu/host/js/eval_step.js b/mu/host/js/eval_step.js\n"
            "+++ b/mu/host/js/eval_step.js\n"
            "@@ -1,3 +1,4 @@\n"
            "+const x = true;\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert passed, f"mu/ evidence path should pass: {errors}"


# =============================================================================
# Host-delta anti-theater signal checks
# =============================================================================


class TestHostSemanticsDeltaSignal:
    """Placeholder host delta proofs must fail for L4_STRUCTURAL."""

    def test_low_signal_host_semantics_delta_fails(self) -> None:
        notes = [{
            "wave_id": "test",
            "raw_class": "L4_STRUCTURAL",
            "wave_class": "L4_STRUCTURAL",
            "gate": "G8",
            "no_op_proof": None,
            "evidence_command": "pytest tests/l4_gates/test_gate.py",
            "evidence_delta": "runtime control-path extraction",
            "host_semantics_delta_before": "old",
            "host_semantics_delta_after": "new",
            "structural_artifact_ref": "mu/substrate/kernel.v1.json",
            "defer_reason_code": None,
            "founder_override": None,
            "primary_blocker_class": "INTEGRATION",
            "post_gate_contract_sweep": "pytest tests/structural/ tests/engine/",
            "primary_invariant_id": "INV_STRUCTURAL_FORWARD_MOTION",
            "progress_proof_before": "before-state",
            "progress_proof_after": "after-state",
            "indicator_artifact_ref": "reports/l4_wave_indicators/test-wave.json",
            "indicator_collection_command": "python3 tools/metrics/collect_l4_wave_indicators.py --wave-id test-wave",
            "bootstrap_endgame_policy": "SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP",
            "boot0_track_id": "N6b",
            "boot0_progress_state": "ADVANCE",
            "date": "2026-02-20",
            "raw": "test note",
        }]
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def foo(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert not passed
        assert any("low-signal" in e for e in errors)


# =============================================================================
# Fix B: Wave binding (notes ordering)
# =============================================================================


class TestWaveBinding:
    """Verify that bound note at position 0 drives class/metadata checks."""

    def test_bound_note_drives_class(self) -> None:
        """When bound note is at [0], enforce uses its wave_class."""
        bound = {
            "wave_id": "target-wave",
            "raw_class": "L4_ENABLER",
            "wave_class": "L4_ENABLER",
            "gate": "G8",
            "no_op_proof": None,
            "evidence_command": "pytest tests/l4_gates/",
            "evidence_delta": "new gate",
            "host_semantics_delta_before": None,
            "host_semantics_delta_after": None,
            "structural_artifact_ref": None,
            "defer_reason_code": None,
            "founder_override": None,
            "primary_blocker_class": "INTEGRATION",
            "post_gate_contract_sweep": None,
            "primary_invariant_id": "INV_STRUCTURAL_FORWARD_MOTION",
            "progress_proof_before": "before-state",
            "progress_proof_after": "after-state",
            "indicator_artifact_ref": "reports/l4_wave_indicators/test-wave.json",
            "indicator_collection_command": "python3 tools/metrics/collect_l4_wave_indicators.py --wave-id test-wave",
            "bootstrap_endgame_policy": "SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP",
            "boot0_track_id": "N6b",
            "boot0_progress_state": "ADVANCE",
            "date": "2026-02-20",
            "raw": "test",
        }
        other = {
            "wave_id": "other-wave",
            "raw_class": "L4_STRUCTURAL",
            "wave_class": "L4_STRUCTURAL",
            "gate": "G5",
            "no_op_proof": None,
            "evidence_command": "pytest tests/l4_gates/",
            "evidence_delta": "runtime change",
            "host_semantics_delta_before": "before runtime projection dispatch update",
            "host_semantics_delta_after": "after runtime projection dispatch update",
            "structural_artifact_ref": "ref",
            "defer_reason_code": None,
            "founder_override": None,
            "primary_blocker_class": "INTEGRATION",
            "post_gate_contract_sweep": "pytest tests/structural/",
            "primary_invariant_id": "INV_STRUCTURAL_FORWARD_MOTION",
            "progress_proof_before": "before-state",
            "progress_proof_after": "after-state",
            "indicator_artifact_ref": "reports/l4_wave_indicators/test-wave.json",
            "indicator_collection_command": "python3 tools/metrics/collect_l4_wave_indicators.py --wave-id test-wave",
            "bootstrap_endgame_policy": "SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP",
            "boot0_track_id": "N6b",
            "boot0_progress_state": "ADVANCE",
            "date": "2026-02-20",
            "raw": "test",
        }
        # Bound note (L4_ENABLER) at [0] — non-runtime files should pass
        notes = [bound, other]
        files = ["tools/checks/foo.py", "TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert passed, f"Bound L4_ENABLER with no runtime should pass: {errors}"

    def test_wrong_note_order_causes_failure(self) -> None:
        """If STRUCTURAL note is at [0] but files are non-runtime, should fail."""
        structural = {
            "wave_id": "structural-wave",
            "raw_class": "L4_STRUCTURAL",
            "wave_class": "L4_STRUCTURAL",
            "gate": "G5",
            "no_op_proof": None,
            "evidence_command": "pytest tests/l4_gates/",
            "evidence_delta": "runtime change",
            "host_semantics_delta_before": "before runtime projection dispatch update",
            "host_semantics_delta_after": "after runtime projection dispatch update",
            "structural_artifact_ref": "ref",
            "defer_reason_code": None,
            "founder_override": None,
            "primary_blocker_class": "INTEGRATION",
            "post_gate_contract_sweep": "pytest tests/structural/",
            "primary_invariant_id": "INV_STRUCTURAL_FORWARD_MOTION",
            "progress_proof_before": "before-state",
            "progress_proof_after": "after-state",
            "indicator_artifact_ref": "reports/l4_wave_indicators/test-wave.json",
            "indicator_collection_command": "python3 tools/metrics/collect_l4_wave_indicators.py --wave-id test-wave",
            "bootstrap_endgame_policy": "SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP",
            "boot0_track_id": "N6b",
            "boot0_progress_state": "ADVANCE",
            "date": "2026-02-20",
            "raw": "test",
        }
        notes = [structural]
        files = ["tools/checks/foo.py", "TASKS.md"]
        passed, errors = enforce("L4_STRUCTURAL", files, notes=notes)
        assert not passed  # No runtime files for STRUCTURAL


# =============================================================================
# Fix 3: Empty-scope policy (wave-id + empty range/staged)
# =============================================================================


class TestEmptyScopePolicy:
    """Empty range/staged with wave-id must fail; without wave-id may skip."""

    def test_empty_range_with_wave_id_fails(self) -> None:
        """--range with no files + --wave-id => cannot certify, exit 1."""
        result = _run_checker_cli(
            ["--range", "HEAD...HEAD", "--wave-id", "l4-governance-hardening-wave2"],
        )
        assert result.returncode == 1
        assert "Cannot verify wave against empty change set" in result.stdout

    def test_empty_range_without_wave_id_skips(self) -> None:
        """--range with no files + no wave-id => non-blocking skip."""
        result = _run_checker_cli(["--range", "HEAD...HEAD"])
        assert result.returncode == 0
        assert "skipping enforcement" in result.stdout.lower()

    def test_empty_staged_with_wave_id_fails(self) -> None:
        """--staged with nothing staged + --wave-id => cannot certify, exit 1."""
        result = _run_checker_cli(
            ["--staged", "--wave-id", "l4-governance-hardening-wave2"],
            clean_index=True,
        )
        assert result.returncode == 1
        assert "Cannot verify wave against empty change set" in result.stdout

    def test_empty_staged_without_wave_id_skips(self) -> None:
        """--staged with nothing staged + no wave-id => non-blocking skip."""
        result = _run_checker_cli(["--staged"], clean_index=True)
        assert result.returncode == 0
        assert "skipping enforcement" in result.stdout.lower()


# =============================================================================
# Scope policy: untracked files must never false-positive
# =============================================================================


class TestScopePolicy:
    """Verify scope policy: untracked files are excluded from checker scope."""

    def test_filter_to_tracked_files_strips_untracked(self) -> None:
        """filter_to_tracked_files removes files not tracked by git."""
        # README.md is always tracked; a random name is not
        result = filter_to_tracked_files(["README.md", "nonexistent_untracked_xyz.py"])
        assert "README.md" in result
        assert "nonexistent_untracked_xyz.py" not in result

    def test_filter_to_tracked_files_empty_input(self) -> None:
        """Empty input returns empty output."""
        assert filter_to_tracked_files([]) == []

    def test_filter_to_tracked_files_all_tracked(self) -> None:
        """All-tracked input passes through unchanged."""
        tracked = ["README.md", "STATUS.md"]
        result = filter_to_tracked_files(tracked)
        assert result == tracked

    def test_files_mode_strips_untracked_via_cli(self) -> None:
        """--files with an untracked path strips it from scope.

        Note: overall pass/fail may depend on TASKS.md anti-stagnation state.
        The scope invariant is that untracked files are stripped (Stripping msg).
        """
        import subprocess
        result = subprocess.run(
            ["python3", "tools/checks/enforce_l4_execution_contract.py",
             "--files", "README.md", "nonexistent_untracked_xyz.py"],
            capture_output=True, text=True,
        )
        assert "Stripping" in result.stdout
        assert "Changed files: 1" in result.stdout

    def test_range_mode_ignores_untracked(self) -> None:
        """--range uses only committed changes (untracked files cannot appear).

        We only check that the filter_to_tracked_files stripping message never
        appears — range mode uses git diff, not --files, so the filter is
        never invoked. The overall pass/fail depends on TASKS.md state which
        is not relevant to this scope policy test.
        """
        import subprocess
        result = subprocess.run(
            ["python3", "tools/checks/enforce_l4_execution_contract.py",
             "--range", "HEAD~1...HEAD"],
            capture_output=True, text=True,
        )
        # Range mode only sees committed files — untracked stripping never fires
        assert "Stripping" not in result.stdout

    def test_staged_mode_ignores_untracked(self) -> None:
        """--staged uses only staged tracked files (untracked never enter scope)."""
        result = _run_checker_cli(["--staged"], clean_index=True)
        # Staged mode only sees git diff --cached — untracked never enter scope
        assert result.returncode == 0
        assert "Stripping" not in result.stdout

    def test_files_all_untracked_with_wave_id_fails(self) -> None:
        """--files with only untracked files + --wave-id => FAIL (exit 1).

        This is the P1 loophole: filter_to_tracked_files() empties the list,
        but the old guard `not args.files` was truthy, skipping fail-closed.
        """
        import subprocess
        result = subprocess.run(
            ["python3", "tools/checks/enforce_l4_execution_contract.py",
             "--files", "nonexistent_untracked_xyz.py",
             "--wave-id", "test-wave",
             "--wave-class", "MAINTENANCE"],
            capture_output=True, text=True,
        )
        assert result.returncode == 1
        assert "Cannot verify wave against empty change set" in result.stdout

    def test_files_all_untracked_no_wave_id_skips(self) -> None:
        """--files with only untracked files + no wave-id => non-blocking skip."""
        import subprocess
        result = subprocess.run(
            ["python3", "tools/checks/enforce_l4_execution_contract.py",
             "--files", "nonexistent_untracked_xyz.py"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "skipping enforcement" in result.stdout.lower()

    def test_files_mixed_tracked_untracked_enforces_tracked(self) -> None:
        """--files with mixed tracked+untracked => tracked subset enforced.

        Note: overall pass/fail may depend on TASKS.md anti-stagnation state.
        The scope invariant is that untracked files are stripped and tracked
        files proceed to enforcement (Changed files: 1, not 0 or 2).
        """
        import subprocess
        result = subprocess.run(
            ["python3", "tools/checks/enforce_l4_execution_contract.py",
             "--files", "README.md", "nonexistent_untracked_xyz.py"],
            capture_output=True, text=True,
        )
        assert "Stripping" in result.stdout
        assert "Changed files: 1" in result.stdout


class TestIndicatorDerivationAntiTheater:
    """Indicator artifact derivation values must match raw provenance data."""

    def test_speedup_ratio_mismatch_fails(self, tmp_path) -> None:
        """Artifact with ratio not matching raw seconds is rejected."""
        import json
        artifact = tmp_path / "indicators.json"
        artifact.write_text(json.dumps({
            "wave_id": "test",
            "repeat_run_speedup_ratio": 99.0,  # wrong — raw says 1.0
            "parity_diff_count": 21,
            "net_host_semantic_delta": 0,
            "step_growth_slope": 1.5,
            "repeat_run_raw_seconds": [1.5, 1.5],
            "step_growth_points": [
                {"step": 1, "elapsed_seconds": 1.5},
                {"step": 2, "elapsed_seconds": 3.0},
            ],
            "parity_diff_source": "tools/checks/check_js_debt.sh",
            "collection_timestamp_utc": "2026-02-22T12:00:00Z",
            "collector_version": "2.0.0",
        }))
        passed, errors = validate_indicator_artifact_json(str(artifact))
        assert not passed, "Should reject mismatched derivation"
        assert any("Derivation mismatch" in e and "repeat_run_speedup_ratio" in e for e in errors)

    def test_slope_mismatch_fails(self, tmp_path) -> None:
        """Artifact with slope not matching growth points is rejected."""
        import json
        artifact = tmp_path / "indicators.json"
        artifact.write_text(json.dumps({
            "wave_id": "test",
            "repeat_run_speedup_ratio": 1.0,
            "parity_diff_count": 21,
            "net_host_semantic_delta": 0,
            "step_growth_slope": 999.0,  # wrong — points say 1.5
            "repeat_run_raw_seconds": [1.5, 1.5],
            "step_growth_points": [
                {"step": 1, "elapsed_seconds": 1.5},
                {"step": 2, "elapsed_seconds": 3.0},
            ],
            "parity_diff_source": "tools/checks/check_js_debt.sh",
            "collection_timestamp_utc": "2026-02-22T12:00:00Z",
            "collector_version": "2.0.0",
        }))
        passed, errors = validate_indicator_artifact_json(str(artifact))
        assert not passed, "Should reject mismatched slope"
        assert any("Derivation mismatch" in e and "step_growth_slope" in e for e in errors)

    def test_valid_derivation_passes(self, tmp_path) -> None:
        """Artifact with correct derivations passes."""
        import json
        artifact = tmp_path / "indicators.json"
        artifact.write_text(json.dumps({
            "wave_id": "test",
            "repeat_run_speedup_ratio": round(1.5 / 1.5, 6),
            "parity_diff_count": 21,
            "net_host_semantic_delta": 0,
            "step_growth_slope": round((3.0 - 1.5) / (2 - 1), 6),
            "repeat_run_raw_seconds": [1.5, 1.5],
            "step_growth_points": [
                {"step": 1, "elapsed_seconds": 1.5},
                {"step": 2, "elapsed_seconds": 3.0},
            ],
            "parity_diff_source": "tools/checks/check_js_debt.sh",
            "collection_timestamp_utc": "2026-02-22T12:00:00Z",
            "collector_version": "2.0.0",
        }))
        passed, errors = validate_indicator_artifact_json(str(artifact))
        assert passed, f"Should pass: {errors}"

    def test_net_host_delta_mismatch_fails(self, tmp_path) -> None:
        """Artifact net_host_semantic_delta must match executable runtime diff net."""
        import json
        artifact = tmp_path / "indicators.json"
        artifact.write_text(json.dumps({
            "wave_id": "test",
            "repeat_run_speedup_ratio": 1.0,
            "parity_diff_count": 21,
            "net_host_semantic_delta": 4,
            "step_growth_slope": 1.5,
            "repeat_run_raw_seconds": [1.5, 1.5],
            "step_growth_points": [
                {"step": 1, "elapsed_seconds": 1.5},
                {"step": 2, "elapsed_seconds": 3.0},
            ],
            "parity_diff_source": "tools/checks/check_js_debt.sh",
            "collection_timestamp_utc": "2026-02-22T12:00:00Z",
            "collector_version": "2.2.0",
        }))
        passed, errors = validate_indicator_artifact_json(
            str(artifact),
            expected_net_host_delta=3,
        )
        assert not passed, "Should reject mismatched net_host_semantic_delta"
        assert any("Indicator mismatch: net_host_semantic_delta" in e for e in errors)

    def test_net_host_delta_match_passes(self, tmp_path) -> None:
        """Artifact net_host_semantic_delta passes when matching executable diff net."""
        import json
        artifact = tmp_path / "indicators.json"
        artifact.write_text(json.dumps({
            "wave_id": "test",
            "repeat_run_speedup_ratio": 1.0,
            "parity_diff_count": 21,
            "net_host_semantic_delta": 3,
            "step_growth_slope": 1.5,
            "repeat_run_raw_seconds": [1.5, 1.5],
            "step_growth_points": [
                {"step": 1, "elapsed_seconds": 1.5},
                {"step": 2, "elapsed_seconds": 3.0},
            ],
            "parity_diff_source": "tools/checks/check_js_debt.sh",
            "collection_timestamp_utc": "2026-02-22T12:00:00Z",
            "collector_version": "2.2.0",
        }))
        passed, errors = validate_indicator_artifact_json(
            str(artifact),
            expected_net_host_delta=3,
        )
        assert passed, f"Should pass with matching net delta: {errors}"
