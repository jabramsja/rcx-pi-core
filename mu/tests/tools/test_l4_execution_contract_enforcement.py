"""
Tests for the L4 Execution Contract enforcement checker.

Validates that enforce_l4_execution_contract.py correctly classifies
L4_CLASS_A and MAINTENANCE waves, including anti-loophole rules.

Usage:
    PYTHONHASHSEED=0 pytest tests/tools/test_l4_execution_contract_enforcement.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(REPO_ROOT))

# Import the enforcement module directly
sys.path.insert(0, str(REPO_ROOT / "tools" / "checks"))
import enforce_l4_execution_contract as _mod
from enforce_l4_execution_contract import (
    enforce,
    has_non_comment_runtime_delta,
    is_comment_line,
    is_runtime_file,
    parse_tracker_notes,
    RUNTIME_DIRS,
)


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
# L4_CLASS_A enforcement
# =============================================================================


class TestL4ClassAEnforcement:
    """L4_CLASS_A waves must touch runtime with executable delta."""

    def test_class_a_with_runtime_files_passes(self) -> None:
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/test_foo.py"]
        passed, errors = enforce("L4_CLASS_A", files)
        assert passed, f"Should pass: {errors}"

    def test_class_a_no_runtime_files_fails(self) -> None:
        files = ["README.md", "STATUS.md", "tests/test_foo.py"]
        passed, errors = enforce("L4_CLASS_A", files)
        assert not passed
        assert any("no runtime/substrate files" in e for e in errors)

    def test_class_a_comment_only_runtime_delta_fails(self) -> None:
        files = ["rcx_pi/selfhost/eval_seed.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "--- a/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,3 @@\n"
            "-# Old comment\n"
            "+# New comment\n"
        )
        passed, errors = enforce("L4_CLASS_A", files, diff)
        assert not passed
        assert any("comment-only" in e for e in errors)

    def test_class_a_executable_runtime_delta_passes(self) -> None:
        files = ["rcx_pi/selfhost/eval_seed.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "--- a/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -10,3 +10,4 @@\n"
            "+def new_function(): pass\n"
        )
        passed, errors = enforce("L4_CLASS_A", files, diff)
        assert passed, f"Should pass with executable delta: {errors}"


# =============================================================================
# MAINTENANCE enforcement
# =============================================================================


class TestMaintenanceEnforcement:
    """MAINTENANCE waves must NOT touch runtime.

    Note: These tests mock check_consecutive_maintenance and
    check_maintenance_metadata to isolate from TASKS.md state.
    """

    @patch.object(_mod, "check_consecutive_maintenance", return_value=False)
    @patch.object(_mod, "check_maintenance_metadata", return_value=(True, []))
    def test_maintenance_no_runtime_passes(self, _meta, _consec) -> None:
        files = ["README.md", "STATUS.md", "TASKS.md"]
        passed, errors = enforce("MAINTENANCE", files)
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

    def test_no_wave_class_passes(self) -> None:
        """No wave class marker = not an L4-classified wave, skip."""
        passed, errors = enforce(None, ["rcx_pi/selfhost/eval_seed.py"])
        assert passed
        assert not errors

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
        "- Tracker sync note (2026-02-20, wave-b): **Wave B.** Class: L4_CLASS_A. "
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
        assert notes[1]["wave_class"] == "L4_CLASS_A"
        assert notes[2]["wave_class"] == "MAINTENANCE"

    def test_extracts_gate_per_note(self) -> None:
        notes = parse_tracker_notes(self.SAMPLE_RA)
        assert notes[0]["gate"] == "G8"
        assert notes[1]["gate"] == "G5"
        assert notes[2]["gate"] == "G3"

    def test_extracts_no_op_proof_only_for_maintenance(self) -> None:
        notes = parse_tracker_notes(self.SAMPLE_RA)
        assert notes[0]["no_op_proof"] is not None  # MAINTENANCE
        assert notes[1]["no_op_proof"] is None       # L4_CLASS_A
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

    def test_no_consecutive_when_class_a_intervenes(self) -> None:
        """MAINTENANCE then L4_CLASS_A → no consecutive cap."""
        text = (
            "## Ra\n\n"
            "- Tracker sync note (d, w2): **W2.** Class: MAINTENANCE. Gate: G1. NO_OP_PROOF: x.\n"
            "- Tracker sync note (d, w1): **W1.** Class: L4_CLASS_A. Gate: G5. Evidence: y.\n"
        )
        notes = parse_tracker_notes(text)
        assert notes[0]["wave_class"] == "MAINTENANCE"
        assert notes[1]["wave_class"] == "L4_CLASS_A"


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

    def test_class_a_comment_only_in_js_fails(self) -> None:
        """L4_CLASS_A with only JS comment changes = violation."""
        files = ["mu/host/js/eval_step.js"]
        diff = (
            "diff --git a/mu/host/js/eval_step.js b/mu/host/js/eval_step.js\n"
            "+++ b/mu/host/js/eval_step.js\n"
            "@@ -1,3 +1,3 @@\n"
            "-// Same 5 bootstrap primitives\n"
            "+// Same 4 bootstrap primitives\n"
        )
        passed, errors = enforce("L4_CLASS_A", files, diff)
        assert not passed
        assert any("comment-only" in e for e in errors)

    def test_class_a_docstring_only_fails(self) -> None:
        """L4_CLASS_A with only Python docstring changes = violation."""
        files = ["rcx_pi/selfhost/eval_seed.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,3 @@\n"
            '-\"\"\"Old docstring.\"\"\"\n'
            '+\"\"\"New docstring.\"\"\"\n'
        )
        passed, errors = enforce("L4_CLASS_A", files, diff)
        assert not passed
        assert any("comment-only" in e for e in errors)
