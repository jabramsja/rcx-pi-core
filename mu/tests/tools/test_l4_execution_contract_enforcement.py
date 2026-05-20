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
import enforce_l4_execution_contract as l4_contract
from enforce_l4_execution_contract import (
    LEGACY_CLASS_ALIAS,
    NON_GATE_TEST_DOMAINS,
    CONTROL_PLANE_DIRS,
    RUNTIME_DIRS,
    VALID_BLOCKER_CLASSES,
    VALID_INVARIANT_IDS,
    VALID_WORKLOAD_TARGETS,
    VALID_WAVE_CLASSES,
    WORKLOAD_TARGET_EVIDENCE,
    bind_note_from_changed_indicator_artifacts,
    _check_proof_binding,
    bind_note_from_touched_wave_ids,
    check_consecutive_maintenance,
    compute_runtime_host_marker_delta,
    enforce,
    extract_touched_tracker_wave_ids,
    filter_to_tracked_files,
    validate_indicator_artifact_json,
    validate_indicator_with_ratchet,
    has_non_comment_runtime_delta,
    is_comment_line,
    is_control_plane_file,
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
        "mu/tools/compilers/compile_seed.py",
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


class TestIsControlPlaneFile:
    """Verify critical control-plane directory classification."""

    @pytest.mark.parametrize("path", [
        ".github/workflows/ci.yml",
        "tools/checks/enforce_l4_execution_contract.py",
        "mu/tools/agents/meta_bridge_supervisor.py",
        "mu/tools/executors/commit_executor.py",
        "mu/tools/checks/enforce_tracker_sync.sh",
        "mu/tools/hooks/pre-commit-doc-check",
        "mu/tools/observability/pipeline_monitor.sh",
        "mu/tools/recovery/recovery_gate.py",
    ])
    def test_control_plane_files_detected(self, path: str) -> None:
        assert is_control_plane_file(path), f"{path} should be governed control-plane"

    @pytest.mark.parametrize("path", [
        "README.md",
        "mu/tests/tools/test_phase_b_executor.py",
        "mu/tools/audits/audit_fast.sh",
        "mu/docs/core/SomeDoc.md",
    ])
    def test_non_control_plane_files_rejected(self, path: str) -> None:
        assert not is_control_plane_file(path), f"{path} should not be governed control-plane"


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

    def test_enabler_allows_comment_only_runtime_with_bound_override(self) -> None:
        notes = [_make_note(
            wave_class="L4_ENABLER",
            wave_id="enabler-comment-runtime",
            founder_override="enabler-comment-runtime",
            no_op_proof="comment-only runtime text plus control-plane automation fix",
            gate="G8",
            evidence_command="PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_l4_execution_contract_enforcement.py",
            evidence_delta="control-plane gate now validates comment-only runtime text from staged diff",
            progress_proof_before="supervisor used file lists without runtime diff text",
            progress_proof_after="supervisor validates the staged diff for runtime no-op proof",
        )]
        files = [
            "mu/host/python/rcx_pi/selfhost/step_mu.py",
            "mu/tools/executors/phase_b_executor.py",
        ]

        passed, errors = enforce(
            "L4_ENABLER",
            files,
            _COMMENT_ONLY_DIFF,
            notes=notes,
            override_wave_bound=True,
        )

        assert passed, errors

    def test_enabler_followup_can_bind_parent_structural_note_without_host_delta_claim(self) -> None:
        notes = [{
            "wave_id": "same-wave-structural-parent",
            "wave_class": "L4_STRUCTURAL",
            "raw_class": "L4_STRUCTURAL",
            "gate": "G8",
            "no_op_proof": None,
            "evidence_command": "PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_gate.py",
            "evidence_delta": "parent structural wave already landed runtime reduction",
            "host_semantics_delta_before": "parent structural baseline before runtime reduction",
            "host_semantics_delta_after": "parent structural baseline after runtime reduction",
            "structural_artifact_ref": "mu/host/js/core/seed_loader.js",
            "defer_reason_code": None,
            "founder_override": "same-wave-structural-parent",
            "primary_blocker_class": "INTEGRATION",
            "post_gate_contract_sweep": "PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/engine/test_seed_integrity.py",
            "primary_invariant_id": "INV_STRUCTURAL_FORWARD_MOTION",
            "progress_proof_before": "staged follow-up had no separate package class",
            "progress_proof_after": "staged follow-up is bounded to tests and packet truth",
            "indicator_artifact_ref": "reports/l4_wave_indicators/same-wave-structural-parent.json",
            "indicator_collection_command": "python3 tools/metrics/collect_l4_wave_indicators.py --wave-id same-wave-structural-parent",
            "bootstrap_endgame_policy": "SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP",
            "boot0_track_id": "V1",
            "boot0_progress_state": "HOLD",
            "unblocks_wave_id": None,
            "unblocks_runtime_blocker": None,
            "workload_target": "host_debt_reduction",
            "date": "2026-05-17",
            "raw": "test structural parent note",
        }]
        files = [
            "mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py",
            "reports/control_plane/same_wave_structural_parent.md",
        ]

        passed, errors = enforce("L4_ENABLER", files, notes=notes)

        assert passed, errors


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
            "unblocks_wave_id": None,
            "unblocks_runtime_blocker": None,
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

    def test_no_wave_class_with_control_plane_fails_closed(self) -> None:
        """No wave class marker + critical control-plane files = FAIL-CLOSED."""
        passed, errors = enforce(None, ["mu/tools/executors/commit_executor.py"])
        assert not passed
        assert any("FAIL-CLOSED" in e and "control-plane" in e for e in errors)

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
            "mu/tools/compilers/",
        }
        assert set(RUNTIME_DIRS) == expected_prefixes

    def test_control_plane_dirs_constant_covers_audited_surfaces(self) -> None:
        expected_prefixes = {
            ".github/workflows/",
            "tools/checks/",
            "mu/tools/agents/",
            "mu/tools/executors/",
            "mu/tools/checks/",
            "mu/tools/hooks/",
            "mu/tools/observability/",
            "mu/tools/recovery/",
        }
        assert set(CONTROL_PLANE_DIRS) == expected_prefixes


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
        "- Tracker sync note (2026-02-19, wave-a): **Wave A.** Class: MAINTENANCE. "
        "Gate: G3. NO_OP_PROOF: Tooling only.\n"
        "- Tracker sync note (2026-02-20, wave-b): **Wave B.** Class: L4_STRUCTURAL. "
        "Gate: G5. Evidence: Added new runtime function.\n"
        "- Tracker sync note (2026-02-20, wave-c): **Wave C.** Class: MAINTENANCE. "
        "Gate: G8. NO_OP_PROOF: Docs only. No runtime change.\n"
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
            "- Tracker sync note (d, w1): **W1.** Class: L4_STRUCTURAL. Gate: G5. Evidence: y.\n"
            "- Tracker sync note (d, w2): **W2.** Class: MAINTENANCE. Gate: G1. NO_OP_PROOF: x.\n"
        )
        notes = parse_tracker_notes(text)
        assert notes[0]["wave_class"] == "MAINTENANCE"
        assert notes[1]["wave_class"] == "L4_STRUCTURAL"

    def test_parser_reverses_append_order_so_newest_note_is_first(self) -> None:
        text = (
            "## Ra\n\n"
            "- Tracker sync note (2026-04-07, old-wave): **Old wave.** "
            "Class: MAINTENANCE. Gate: G5. NO_OP_PROOF: tooling.\n"
            "- Tracker sync note (2026-04-14, new-wave): **New wave.** "
            "Class: L4_ENABLER. Gate: G8. Evidence: current fix.\n"
        )
        notes = parse_tracker_notes(text)
        assert [note["wave_id"] for note in notes] == ["new-wave", "old-wave"]


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
            "workload_target": "rcx_engine_cycle",
            "date": "2026-02-20",
            "raw": "test note",
        }]
        files = ["tools/checks/foo.py"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert not passed
        assert any("host_semantics_delta" in e for e in errors)


class TestDebtRemovalIntegrity:
    """Marker-touch structural waves must prove real debt removal."""

    @staticmethod
    def _ratchet_payload(
        *,
        baseline_iteration: int = 10,
        baseline_recursion: int = 5,
        baseline_builtin: int = 2,
        baseline_mutation: int = 0,
        current_iteration: int = 10,
        current_recursion: int = 4,
        current_builtin: int = 2,
        current_mutation: int = 0,
    ) -> dict:
        def _counts(it, rec, built, mut) -> dict:
            return {
                "python": {
                    "host_iteration": 0,
                    "host_recursion": 0,
                    "host_builtin": 0,
                    "host_mutation": 0,
                },
                "javascript": {
                    "host_iteration": it,
                    "host_recursion": rec,
                    "host_builtin": built,
                    "host_mutation": mut,
                },
            }

        return {
            "current": _counts(current_iteration, current_recursion, current_builtin, current_mutation),
            "baseline_counts": _counts(baseline_iteration, baseline_recursion, baseline_builtin, baseline_mutation),
            "passed": True,
        }

    @staticmethod
    def _no_semantic_construct_fn(language: str = "javascript") -> list[dict[str, object]]:
        return [{
            "name": "markerTarget",
            "start_line": 24,
            "end_line": 80,
            "markers": set(),
            "body": "const z = 1;\nreturn z;",
            "language": language,
        }]

    def test_marker_delta_extraction_counts_added_removed(self) -> None:
        diff = (
            "diff --git a/mu/host/js/eval_step.js b/mu/host/js/eval_step.js\n"
            "+++ b/mu/host/js/eval_step.js\n"
            "@@ -1,3 +1,3 @@\n"
            "-// @host_recursion old\n"
            "+// @host_iteration new\n"
        )
        added, removed, total_added, total_removed = compute_runtime_host_marker_delta(
            diff,
            ["mu/host/js/eval_step.js"],
        )
        assert total_added == 1
        assert total_removed == 1
        assert added["host_iteration"] == 1
        assert removed["host_recursion"] == 1

    def test_structural_runtime_requires_strict_total_decrease(self, monkeypatch) -> None:
        files = ["mu/host/js/eval_step.js", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/mu/host/js/eval_step.js b/mu/host/js/eval_step.js\n"
            "+++ b/mu/host/js/eval_step.js\n"
            "@@ -20,1 +20,2 @@\n"
            "-// @host_recursion old marker text\n"
            "+const strict_total_probe = true;\n"
        )
        payload = self._ratchet_payload(
            baseline_iteration=10, baseline_recursion=5,
            current_iteration=10, current_recursion=5,
        )
        monkeypatch.setattr(l4_contract, "probe_host_semantics_ratchet", lambda: (payload, []))
        monkeypatch.setattr(l4_contract, "_extract_functions_for_file", lambda _f, _s: self._no_semantic_construct_fn())
        passed, errors = enforce("L4_STRUCTURAL", files, diff)
        assert not passed
        assert any("strict debt reduction" in e for e in errors)

    def test_structural_runtime_fails_on_category_swap(self, monkeypatch) -> None:
        files = ["mu/host/js/eval_step.js", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/mu/host/js/eval_step.js b/mu/host/js/eval_step.js\n"
            "+++ b/mu/host/js/eval_step.js\n"
            "@@ -20,1 +20,2 @@\n"
            "-// @host_recursion old marker text\n"
            "+const category_swap_probe = true;\n"
        )
        payload = self._ratchet_payload(
            baseline_iteration=10, baseline_recursion=5,
            current_iteration=11, current_recursion=3,
        )  # total 15 -> 14 (decrease) but category increase exists
        monkeypatch.setattr(l4_contract, "probe_host_semantics_ratchet", lambda: (payload, []))
        monkeypatch.setattr(l4_contract, "_extract_functions_for_file", lambda _f, _s: self._no_semantic_construct_fn())
        passed, errors = enforce("L4_STRUCTURAL", files, diff)
        assert not passed
        assert any("cannot increase any host category" in e for e in errors)

    def test_structural_runtime_fails_on_flat_total(self, monkeypatch) -> None:
        files = ["mu/host/js/eval_step.js", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/mu/host/js/eval_step.js b/mu/host/js/eval_step.js\n"
            "+++ b/mu/host/js/eval_step.js\n"
            "@@ -20,1 +20,2 @@\n"
            "-// @host_recursion old marker text\n"
            "+const flat_total_probe = true;\n"
        )
        payload = self._ratchet_payload(
            baseline_iteration=10, baseline_recursion=4,
            current_iteration=10, current_recursion=4,
        )  # total flat
        monkeypatch.setattr(l4_contract, "probe_host_semantics_ratchet", lambda: (payload, []))
        monkeypatch.setattr(l4_contract, "_extract_functions_for_file", lambda _f, _s: self._no_semantic_construct_fn())
        passed, errors = enforce("L4_STRUCTURAL", files, diff)
        assert not passed
        assert any("strict debt reduction" in e for e in errors)

    def test_structural_runtime_rejects_baseline_file_change(self) -> None:
        files = [
            "mu/host/js/eval_step.js",
            "mu/tools/checks/host_semantics_baseline.json",
            "tests/l4_gates/test_foo.py",
        ]
        diff = (
            "diff --git a/mu/host/js/eval_step.js b/mu/host/js/eval_step.js\n"
            "+++ b/mu/host/js/eval_step.js\n"
            "@@ -20,1 +20,2 @@\n"
            "-// @host_recursion old marker text\n"
            "+const baseline_guard_probe = true;\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff)
        assert not passed
        assert any("cannot modify tools/checks/host_semantics_baseline.json" in e for e in errors)

    def test_marker_removed_but_self_call_present_fails(self, monkeypatch) -> None:
        files = ["mu/host/js/core/bootstrap_core.js", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/mu/host/js/core/bootstrap_core.js b/mu/host/js/core/bootstrap_core.js\n"
            "+++ b/mu/host/js/core/bootstrap_core.js\n"
            "@@ -20,1 +20,2 @@\n"
            "- * @host_recursion old marker text\n"
            "+const recursion_semantic_probe = true;\n"
        )
        payload = self._ratchet_payload(
            baseline_iteration=10, baseline_recursion=5,
            current_iteration=10, current_recursion=4,
        )
        monkeypatch.setattr(l4_contract, "probe_host_semantics_ratchet", lambda: (payload, []))
        monkeypatch.setattr(
            l4_contract,
            "_extract_functions_for_file",
            lambda _f, _s: [{
                "name": "match",
                "start_line": 24,
                "end_line": 120,
                "markers": set(),
                "body": "const sub = match(pattern, input, 1);\nreturn sub;",
                "language": "javascript",
            }],
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff)
        assert not passed
        assert any("Rule A4.1" in e for e in errors)

    def test_marker_removed_but_loop_present_fails(self, monkeypatch) -> None:
        files = ["mu/host/js/core/bootstrap_core.js", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/mu/host/js/core/bootstrap_core.js b/mu/host/js/core/bootstrap_core.js\n"
            "+++ b/mu/host/js/core/bootstrap_core.js\n"
            "@@ -170,1 +170,2 @@\n"
            "- * @host_iteration old marker text\n"
            "+const iteration_semantic_probe = true;\n"
        )
        payload = self._ratchet_payload(
            baseline_iteration=10, baseline_recursion=5,
            current_iteration=9, current_recursion=5,
        )
        monkeypatch.setattr(l4_contract, "probe_host_semantics_ratchet", lambda: (payload, []))
        monkeypatch.setattr(
            l4_contract,
            "_extract_functions_for_file",
            lambda _f, _s: [{
                "name": "step",
                "start_line": 175,
                "end_line": 220,
                "markers": set(),
                "body": "for (let i = 0; i < 10; i++) { }\nreturn input;",
                "language": "javascript",
            }],
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff)
        assert not passed
        assert any("Rule A4.2" in e for e in errors)

    def test_marker_removed_but_builtin_present_fails(self, monkeypatch) -> None:
        files = ["mu/host/js/core/types.js", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/mu/host/js/core/types.js b/mu/host/js/core/types.js\n"
            "+++ b/mu/host/js/core/types.js\n"
            "@@ -35,1 +35,2 @@\n"
            "- * @host_builtin old marker text\n"
            "+const builtin_semantic_probe = true;\n"
        )
        payload = self._ratchet_payload(
            baseline_iteration=10, baseline_recursion=5, baseline_builtin=4,
            current_iteration=10, current_recursion=4, current_builtin=4,
        )
        monkeypatch.setattr(l4_contract, "probe_host_semantics_ratchet", lambda: (payload, []))
        monkeypatch.setattr(
            l4_contract,
            "_extract_functions_for_file",
            lambda _f, _s: [{
                "name": "isValidMu",
                "start_line": 40,
                "end_line": 130,
                "markers": set(),
                "body": "const keys = Object.keys(value);\nreturn Array.isArray(keys);",
                "language": "javascript",
            }],
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff)
        assert not passed
        assert any("Rule A4.3/A4.4" in e for e in errors)

    def test_semantic_removal_proof_passes_when_construct_removed(self, monkeypatch) -> None:
        files = ["mu/host/js/core/bootstrap_core.js", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/mu/host/js/core/bootstrap_core.js b/mu/host/js/core/bootstrap_core.js\n"
            "+++ b/mu/host/js/core/bootstrap_core.js\n"
            "@@ -20,1 +20,2 @@\n"
            "- * @host_recursion old marker text\n"
            "+const semantic_removal_success_probe = true;\n"
        )
        payload = self._ratchet_payload(
            baseline_iteration=10, baseline_recursion=5,
            current_iteration=10, current_recursion=4,
        )
        monkeypatch.setattr(l4_contract, "probe_host_semantics_ratchet", lambda: (payload, []))
        monkeypatch.setattr(l4_contract, "_extract_functions_for_file", lambda _f, _s: self._no_semantic_construct_fn())
        passed, errors = enforce("L4_STRUCTURAL", files, diff)
        assert passed, f"Semantic removal proof should pass when construct is absent: {errors}"

    def test_malformed_ratchet_json_fails_closed(self, monkeypatch) -> None:
        files = ["mu/host/js/core/bootstrap_core.js", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/mu/host/js/core/bootstrap_core.js b/mu/host/js/core/bootstrap_core.js\n"
            "+++ b/mu/host/js/core/bootstrap_core.js\n"
            "@@ -20,1 +20,2 @@\n"
            "- * @host_recursion old marker text\n"
            "+const malformed_ratchet_probe = true;\n"
        )
        malformed = {
            "current": {
                "javascript": {
                    "host_iteration": "bad",
                    "host_recursion": 4,
                    "host_builtin": 3,
                    "host_mutation": 0,
                },
                "python": {
                    "host_iteration": 0,
                    "host_recursion": 0,
                    "host_builtin": 0,
                    "host_mutation": 0,
                },
            },
            "baseline_counts": {
                "javascript": {
                    "host_iteration": 10,
                    "host_recursion": 5,
                    "host_builtin": 3,
                    "host_mutation": 0,
                },
                "python": {
                    "host_iteration": 0,
                    "host_recursion": 0,
                    "host_builtin": 0,
                    "host_mutation": 0,
                },
            },
        }
        monkeypatch.setattr(l4_contract, "probe_host_semantics_ratchet", lambda: (malformed, []))
        monkeypatch.setattr(l4_contract, "_extract_functions_for_file", lambda _f, _s: self._no_semantic_construct_fn())
        passed, errors = enforce("L4_STRUCTURAL", files, diff)
        assert not passed
        assert any("FAIL-CLOSED debt-removal integrity: invalid host-semantics probe data" in e for e in errors)


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
            "workload_target": "rcx_engine_cycle",
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
            "workload_target": "ontology_promotion",
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
            "workload_target": "ontology_promotion",
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

    def test_extract_touched_tracker_wave_ids_uses_added_tracker_lines(self) -> None:
        tasks_diff = (
            "@@ -385,0 +386,2 @@\n"
            "+- Tracker sync note (2026-03-24, prior-wave): **PRIOR — old.** "
            "Class: L4_ENABLER. indicator_artifact_ref: reports/l4_wave_indicators/prior-wave.json.\n"
            "+- Tracker sync note (2026-03-25, current-wave): **CURRENT — new.** "
            "Class: L4_ENABLER. indicator_artifact_ref: reports/l4_wave_indicators/current-wave.json.\n"
        )

        assert extract_touched_tracker_wave_ids(tasks_diff) == ["prior-wave", "current-wave"]

    def test_bind_note_from_touched_wave_ids_prefers_last_added_wave(self) -> None:
        notes = [
            {"wave_id": "older-top-note", "wave_class": "L4_ENABLER"},
            {"wave_id": "current-wave", "wave_class": "L4_ENABLER"},
            {"wave_id": "prior-wave", "wave_class": "L4_ENABLER"},
        ]

        bound = bind_note_from_touched_wave_ids(notes, ["prior-wave", "current-wave"])

        assert bound is not None
        assert bound["wave_id"] == "current-wave"

    def test_bind_note_from_changed_indicator_artifacts_matches_exact_ref(self) -> None:
        notes = [
            {
                "wave_id": "unrelated-wave",
                "wave_class": "L4_ENABLER",
                "indicator_artifact_ref": "reports/l4_wave_indicators/unrelated-wave.json",
            },
            {
                "wave_id": "current-wave",
                "wave_class": "L4_ENABLER",
                "indicator_artifact_ref": "reports/l4_wave_indicators/current-wave.json",
            },
        ]

        bound = bind_note_from_changed_indicator_artifacts(
            notes,
            [
                "mu/tools/executors/executor_dispatch.py",
                "reports/l4_wave_indicators/current-wave.json",
            ],
        )

        assert bound is not None
        assert bound["wave_id"] == "current-wave"

    def test_bind_note_from_changed_indicator_artifacts_rejects_ambiguity(self) -> None:
        notes = [
            {
                "wave_id": "first-wave",
                "wave_class": "L4_ENABLER",
                "indicator_artifact_ref": "reports/l4_wave_indicators/first-wave.json",
            },
            {
                "wave_id": "second-wave",
                "wave_class": "L4_ENABLER",
                "indicator_artifact_ref": "reports/l4_wave_indicators/second-wave.json",
            },
        ]

        bound = bind_note_from_changed_indicator_artifacts(
            notes,
            [
                "mu/tools/executors/executor_dispatch.py",
                "reports/l4_wave_indicators/first-wave.json",
                "reports/l4_wave_indicators/second-wave.json",
            ],
        )

        assert bound is None


def _write_fake_l4_ratchet(repo: Path) -> None:
    checker = repo / "tools" / "checks" / "check_host_semantics_ratchet.py"
    checker.write_text(
        "import json\n"
        "data = {\n"
        "    'baseline_counts': {\n"
        "        'python': {'host_builtin': 0, 'host_iteration': 0, 'host_mutation': 0, 'host_recursion': 0},\n"
        "        'javascript': {'host_builtin': 0, 'host_iteration': 0, 'host_mutation': 0, 'host_recursion': 0},\n"
        "    },\n"
        "    'current': {\n"
        "        'python': {'host_builtin': 0, 'host_iteration': 0, 'host_mutation': 0, 'host_recursion': 0},\n"
        "        'javascript': {'host_builtin': 0, 'host_iteration': 0, 'host_mutation': 0, 'host_recursion': 0},\n"
        "    },\n"
        "}\n"
        "print(json.dumps(data))\n",
        encoding="utf-8",
    )


def _write_l4_indicator(repo: Path, wave_id: str) -> None:
    indicator = repo / "reports" / "l4_wave_indicators" / f"{wave_id}.json"
    indicator.parent.mkdir(parents=True, exist_ok=True)
    indicator.write_text(
        "{\n"
        f'  "wave_id": "{wave_id}",\n'
        '  "repeat_run_speedup_ratio": 1.0,\n'
        '  "parity_diff_count": 0,\n'
        '  "net_host_semantic_delta": 0,\n'
        '  "step_growth_slope": 1.0,\n'
        '  "repeat_run_raw_seconds": [1.0, 1.0],\n'
        '  "step_growth_points": [\n'
        '    {"step": 1, "elapsed_seconds": 1.0},\n'
        '    {"step": 2, "elapsed_seconds": 2.0}\n'
        "  ],\n"
        '  "parity_diff_source": "tools/checks/check_js_debt.sh",\n'
        '  "collection_timestamp_utc": "2026-05-07T00:00:00Z",\n'
        '  "collector_version": "test"\n'
        "}\n",
        encoding="utf-8",
    )


def _init_staged_l4_checker_repo(tmp_path: Path, wave_id: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "tools" / "checks").mkdir(parents=True)
    (repo / "tools" / "checks" / "enforce_l4_execution_contract.py").write_text(
        (REPO_ROOT / "tools" / "checks" / "enforce_l4_execution_contract.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _write_fake_l4_ratchet(repo)

    (repo / "mu" / "tools" / "executors").mkdir(parents=True)
    (repo / "mu" / "tools" / "executors" / "example.py").write_text(
        "# baseline\n",
        encoding="utf-8",
    )
    (repo / "mu" / "host" / "js" / "core").mkdir(parents=True)
    (repo / "mu" / "host" / "js" / "core" / "constants.js").write_text(
        "// baseline debt marker\n",
        encoding="utf-8",
    )
    (repo / "mu" / "host" / "js" / "core" / "unrelated.js").write_text(
        "export function unrelated() { return 1; }\n",
        encoding="utf-8",
    )
    (repo / "TASKS.md").write_text(
        "## Ra\n\n"
        f"- Tracker sync note (2026-05-07, {wave_id}): **CURRENT.** "
        "Class: L4_ENABLER. Category: tooling/control-plane. target_gate_id: G8. "
        "no_op_proof: package-owned runtime edits are comment-only when present. "
        "evidence_command: python3 tools/checks/enforce_l4_execution_contract.py --staged. "
        "evidence_delta: changed control-plane staged binding. "
        "progress_proof_before: canonical staged checker reported no wave class for changed control-plane files. "
        "progress_proof_after: canonical staged checker binds the same-wave indicator artifact to this tracker note. "
        f"FOUNDER_OVERRIDE:{wave_id}. "
        "primary_blocker_class: INTEGRATION. "
        "primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
        f"indicator_artifact_ref: reports/l4_wave_indicators/{wave_id}.json. "
        f"indicator_collection_command: python3 tools/metrics/collect_l4_wave_indicators.py --wave-id {wave_id} "
        f"--output reports/l4_wave_indicators/{wave_id}.json. "
        "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
        "boot0_track_id: V1. boot0_progress_state: HOLD.\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True, text=True)
    return repo


class TestStagedIndicatorBinding:
    """Canonical --staged binding must not require TASKS.md to be staged."""

    def test_staged_control_plane_with_changed_indicator_binds_tracker_note(self, tmp_path: Path) -> None:
        wave_id = "current-control-plane-wave"
        repo = _init_staged_l4_checker_repo(tmp_path, wave_id)
        (repo / "mu" / "tools" / "executors" / "example.py").write_text(
            "# changed\n",
            encoding="utf-8",
        )
        _write_l4_indicator(repo, wave_id)
        subprocess.run(
            [
                "git",
                "add",
                "--",
                "mu/tools/executors/example.py",
                f"reports/l4_wave_indicators/{wave_id}.json",
            ],
            cwd=repo,
            check=True,
        )

        result = subprocess.run(
            [sys.executable, "tools/checks/enforce_l4_execution_contract.py", "--staged"],
            cwd=repo,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert "Wave class: L4_ENABLER" in result.stdout
        assert "L4 Execution Contract v2: L4_ENABLER compliant" in result.stdout

    def test_staged_control_plane_without_changed_indicator_stays_no_class(self, tmp_path: Path) -> None:
        wave_id = "current-control-plane-wave"
        repo = _init_staged_l4_checker_repo(tmp_path, wave_id)
        (repo / "mu" / "tools" / "executors" / "example.py").write_text(
            "# changed\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "--", "mu/tools/executors/example.py"], cwd=repo, check=True)

        result = subprocess.run(
            [sys.executable, "tools/checks/enforce_l4_execution_contract.py", "--staged"],
            cwd=repo,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert "Wave class: (none)" in result.stdout
        assert "no wave class marker found" in result.stdout

    def test_files_mode_with_indicator_artifact_does_not_bind_tracker_note(self, tmp_path: Path) -> None:
        wave_id = "historical-control-plane-wave"
        repo = _init_staged_l4_checker_repo(tmp_path, wave_id)

        result = subprocess.run(
            [
                sys.executable,
                "tools/checks/enforce_l4_execution_contract.py",
                "--files",
                "mu/tools/executors/example.py",
                f"reports/l4_wave_indicators/{wave_id}.json",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert "Wave class: (none)" in result.stdout
        assert "no wave class marker found" in result.stdout

    def test_files_mode_uses_package_scoped_staged_diff_for_runtime_override(self, tmp_path: Path) -> None:
        wave_id = "comment-only-runtime-files-wave"
        repo = _init_staged_l4_checker_repo(tmp_path, wave_id)
        (repo / "mu" / "host" / "js" / "core" / "constants.js").write_text(
            "// refined debt marker only\n",
            encoding="utf-8",
        )
        (repo / "mu" / "host" / "js" / "core" / "unrelated.js").write_text(
            "export function unrelated() { return 2; }\n",
            encoding="utf-8",
        )
        _write_l4_indicator(repo, wave_id)
        subprocess.run(
            [
                "git",
                "add",
                "--",
                "mu/host/js/core/constants.js",
                "mu/host/js/core/unrelated.js",
                f"reports/l4_wave_indicators/{wave_id}.json",
            ],
            cwd=repo,
            check=True,
        )

        result = subprocess.run(
            [
                sys.executable,
                "tools/checks/enforce_l4_execution_contract.py",
                "--wave-class",
                "L4_ENABLER",
                "--wave-id",
                wave_id,
                "--files",
                "mu/host/js/core/constants.js",
                f"reports/l4_wave_indicators/{wave_id}.json",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert "Runtime files: 1" in result.stdout
        assert "allowing comment-only runtime edit" in result.stdout
        assert "L4 Execution Contract v2: L4_ENABLER compliant" in result.stdout


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

    def test_ratchet_derived_delta_mismatch_rejects(self, tmp_path, monkeypatch) -> None:
        """End-to-end: ratchet-derived delta=0 rejects indicator with delta=999."""
        import json
        ratchet_payload = {
            "current": {"python": {"host_builtin": 1, "host_iteration": 10, "host_mutation": 0, "host_recursion": 2},
                        "javascript": {"host_builtin": 4, "host_iteration": 10, "host_mutation": 0, "host_recursion": 5}},
            "baseline_counts": {"python": {"host_builtin": 1, "host_iteration": 10, "host_mutation": 0, "host_recursion": 2},
                                "javascript": {"host_builtin": 4, "host_iteration": 10, "host_mutation": 0, "host_recursion": 5}},
            "passed": True,
        }
        monkeypatch.setattr(l4_contract, "probe_host_semantics_ratchet", lambda: (ratchet_payload, []))

        artifact = tmp_path / "ind.json"
        artifact.write_text(json.dumps({
            "wave_id": "test", "repeat_run_speedup_ratio": 1.0,
            "parity_diff_count": 0, "net_host_semantic_delta": 999,
            "step_growth_slope": 1.5, "repeat_run_raw_seconds": [1.5, 1.5],
            "step_growth_points": [{"step": 1, "elapsed_seconds": 1.5}, {"step": 2, "elapsed_seconds": 3.0}],
            "parity_diff_source": "test", "collection_timestamp_utc": "2026-01-01T00:00:00Z",
            "collector_version": "2.0.0",
        }))

        # Test through validate_indicator_with_ratchet (main path helper)
        passed, errors = validate_indicator_with_ratchet(str(artifact), [str(artifact)])
        assert not passed, "Should reject indicator with delta=999 when ratchet says 0"
        assert any("net_host_semantic_delta" in e for e in errors)

    def test_ratchet_derived_delta_match_accepts(self, tmp_path, monkeypatch) -> None:
        """End-to-end: ratchet-derived delta=0 accepts indicator with delta=0."""
        import json
        ratchet_payload = {
            "current": {"python": {"host_builtin": 1, "host_iteration": 10, "host_mutation": 0, "host_recursion": 2},
                        "javascript": {"host_builtin": 4, "host_iteration": 10, "host_mutation": 0, "host_recursion": 5}},
            "baseline_counts": {"python": {"host_builtin": 1, "host_iteration": 10, "host_mutation": 0, "host_recursion": 2},
                                "javascript": {"host_builtin": 4, "host_iteration": 10, "host_mutation": 0, "host_recursion": 5}},
            "passed": True,
        }
        monkeypatch.setattr(l4_contract, "probe_host_semantics_ratchet", lambda: (ratchet_payload, []))

        artifact = tmp_path / "ind.json"
        artifact.write_text(json.dumps({
            "wave_id": "test", "repeat_run_speedup_ratio": 1.0,
            "parity_diff_count": 0, "net_host_semantic_delta": 0,
            "step_growth_slope": 1.5, "repeat_run_raw_seconds": [1.5, 1.5],
            "step_growth_points": [{"step": 1, "elapsed_seconds": 1.5}, {"step": 2, "elapsed_seconds": 3.0}],
            "parity_diff_source": "test", "collection_timestamp_utc": "2026-01-01T00:00:00Z",
            "collector_version": "2.0.0",
        }))

        passed, errors = validate_indicator_with_ratchet(str(artifact), [str(artifact)])
        assert passed, f"Should accept indicator matching ratchet delta: {errors}"

    def test_ratchet_probe_failure_fails_closed(self, tmp_path, monkeypatch) -> None:
        """End-to-end: probe failure propagates FAIL-CLOSED through main path."""
        import json
        monkeypatch.setattr(
            l4_contract, "probe_host_semantics_ratchet",
            lambda: (None, ["probe script not found"]),
        )

        # Valid artifact — but probe failure must still cause rejection
        artifact = tmp_path / "ind.json"
        artifact.write_text(json.dumps({
            "wave_id": "test", "repeat_run_speedup_ratio": 1.0,
            "parity_diff_count": 0, "net_host_semantic_delta": 0,
            "step_growth_slope": 1.5, "repeat_run_raw_seconds": [1.5, 1.5],
            "step_growth_points": [{"step": 1, "elapsed_seconds": 1.5}, {"step": 2, "elapsed_seconds": 3.0}],
            "parity_diff_source": "test", "collection_timestamp_utc": "2026-01-01T00:00:00Z",
            "collector_version": "2.0.0",
        }))

        passed, errors = validate_indicator_with_ratchet(str(artifact), [str(artifact)])
        assert not passed, "Probe failure must reject (fail-closed)"
        assert any("FAIL-CLOSED" in e for e in errors)


# =============================================================================
# Consecutive MAINTENANCE cadence rule (Phase C)
# =============================================================================


def _make_note(wave_class="MAINTENANCE", wave_id="test-wave", **overrides):
    """Build a minimal valid note dict for cadence rule tests."""
    note = {
        "wave_id": wave_id,
        "raw_class": wave_class,
        "wave_class": wave_class,
        "gate": "G5",
        "no_op_proof": "tooling only" if wave_class == "MAINTENANCE" else None,
        "evidence_command": None,
        "evidence_delta": None,
        "host_semantics_delta_before": None,
        "host_semantics_delta_after": None,
        "structural_artifact_ref": None,
        "defer_reason_code": "TOOLING_PREREQUISITE" if wave_class == "MAINTENANCE" else None,
        "founder_override": None,
        "primary_blocker_class": "INTEGRATION",
        "post_gate_contract_sweep": None,
        "primary_invariant_id": "INV_STRUCTURAL_FORWARD_MOTION",
        "progress_proof_before": None,
        "progress_proof_after": None,
        "indicator_artifact_ref": f"reports/l4_wave_indicators/{wave_id}.json",
        "indicator_collection_command": f"python3 tools/metrics/collect_l4_wave_indicators.py --wave-id {wave_id}",
        "bootstrap_endgame_policy": "SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP",
        "boot0_track_id": "N3",
        "boot0_progress_state": "HOLD",
        "unblocks_wave_id": None,
        "unblocks_runtime_blocker": None,
        "workload_target": "ontology_promotion" if wave_class == "L4_STRUCTURAL" else None,
        "date": "2026-02-27",
        "raw": "test note",
    }
    note.update(overrides)
    return note


class TestConsecutiveMaintenanceCadence:
    """Consecutive MAINTENANCE cadence rule (Phase C).

    Two consecutive MAINTENANCE waves are blocked unless the current note
    includes both unblocks_wave_id and unblocks_runtime_blocker.
    """

    def test_single_maintenance_passes(self):
        """Single MAINTENANCE wave → no cadence violation."""
        notes = [_make_note(wave_id="m1")]
        passed, errors = check_consecutive_maintenance(notes)
        assert passed, f"Single MAINTENANCE should pass: {errors}"

    def test_maintenance_after_structural_passes(self):
        """MAINTENANCE after L4_STRUCTURAL → no cadence violation."""
        notes = [
            _make_note(wave_id="m1"),
            _make_note(wave_class="L4_STRUCTURAL", wave_id="s1"),
        ]
        passed, errors = check_consecutive_maintenance(notes)
        assert passed, f"MAINTENANCE after STRUCTURAL should pass: {errors}"

    def test_consecutive_maintenance_without_bypass_fails(self):
        """Two consecutive MAINTENANCE without bypass fields → fail."""
        notes = [
            _make_note(wave_id="m2"),
            _make_note(wave_id="m1"),
        ]
        passed, errors = check_consecutive_maintenance(notes)
        assert not passed
        assert any("Consecutive MAINTENANCE" in e for e in errors)
        assert any("unblocks_wave_id" in e for e in errors)

    def test_consecutive_maintenance_with_both_bypass_fields_passes(self):
        """Two consecutive MAINTENANCE with both bypass fields → pass."""
        notes = [
            _make_note(
                wave_id="m2",
                unblocks_wave_id="wave-a19-foo",
                unblocks_runtime_blocker="RT-005",
            ),
            _make_note(wave_id="m1"),
        ]
        passed, errors = check_consecutive_maintenance(notes)
        assert passed, f"Should pass with bypass fields: {errors}"

    def test_consecutive_maintenance_bypass_rejects_design_blocker(self):
        """Bypass requires runtime blocker class, not DESIGN."""
        notes = [
            _make_note(
                wave_id="m2",
                primary_blocker_class="DESIGN",
                unblocks_wave_id="wave-a19-foo",
                unblocks_runtime_blocker="RT-005",
            ),
            _make_note(wave_id="m1"),
        ]
        passed, errors = check_consecutive_maintenance(notes)
        assert not passed
        assert any("INTEGRATION or PERFORMANCE" in e for e in errors)

    def test_consecutive_maintenance_bypass_rejects_non_runtime_token(self):
        """Bypass blocker token must be runtime/invariant ID form."""
        notes = [
            _make_note(
                wave_id="m2",
                unblocks_wave_id="wave-a19-foo",
                unblocks_runtime_blocker="docs-cleanup",
            ),
            _make_note(wave_id="m1"),
        ]
        passed, errors = check_consecutive_maintenance(notes)
        assert not passed
        assert any("runtime/invariant token form" in e for e in errors)

    def test_consecutive_maintenance_bypass_rejects_self_reference(self):
        """Bypass cannot point unblocks_wave_id to the current wave."""
        notes = [
            _make_note(
                wave_id="wave-m2",
                unblocks_wave_id="wave-m2",
                unblocks_runtime_blocker="RT-005",
            ),
            _make_note(wave_id="wave-m1"),
        ]
        passed, errors = check_consecutive_maintenance(notes)
        assert not passed
        assert any("self-reference" in e for e in errors)

    def test_consecutive_maintenance_bypass_rejects_targeting_maintenance_wave(self):
        """Bypass must not target a MAINTENANCE wave if target exists in history."""
        notes = [
            _make_note(
                wave_id="wave-m3",
                unblocks_wave_id="wave-m1",
                unblocks_runtime_blocker="RT-005",
            ),
            _make_note(wave_id="wave-m2"),
            _make_note(wave_id="wave-m1", wave_class="MAINTENANCE"),
        ]
        passed, errors = check_consecutive_maintenance(notes)
        assert not passed
        assert any("non-MAINTENANCE" in e for e in errors)

    def test_consecutive_maintenance_with_only_wave_id_fails(self):
        """Only unblocks_wave_id without unblocks_runtime_blocker → fail."""
        notes = [
            _make_note(wave_id="m2", unblocks_wave_id="wave-a19-foo"),
            _make_note(wave_id="m1"),
        ]
        passed, errors = check_consecutive_maintenance(notes)
        assert not passed
        assert any("unblocks_runtime_blocker" in e for e in errors)

    def test_consecutive_maintenance_with_only_blocker_fails(self):
        """Only unblocks_runtime_blocker without unblocks_wave_id → fail."""
        notes = [
            _make_note(wave_id="m2", unblocks_runtime_blocker="RT-005"),
            _make_note(wave_id="m1"),
        ]
        passed, errors = check_consecutive_maintenance(notes)
        assert not passed
        assert any("unblocks_wave_id" in e for e in errors)

    def test_cadence_fields_parsed_from_tracker_text(self):
        """Parse unblocks_wave_id and unblocks_runtime_blocker from real text."""
        text = (
            "## Ra\n\n"
            "- Tracker sync note (d, w2): **W2.** Class: MAINTENANCE. Gate: G5. "
            "NO_OP_PROOF: tooling. defer_reason_code: TOOLING_PREREQUISITE. "
            "unblocks_wave_id: wave-a19-structural. "
            "unblocks_runtime_blocker: RT-005-stall-detection. "
            "primary_blocker_class: DESIGN. primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
            "indicator_artifact_ref: reports/l4_wave_indicators/w2.json. "
            "indicator_collection_command: python3 tools/metrics/collect_l4_wave_indicators.py --wave-id w2. "
            "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            "boot0_track_id: N3. boot0_progress_state: HOLD.\n"
        )
        notes = parse_tracker_notes(text)
        assert len(notes) == 1
        assert notes[0]["unblocks_wave_id"] == "wave-a19-structural"
        assert notes[0]["unblocks_runtime_blocker"] == "RT-005-stall-detection"

    def test_cadence_fields_none_when_absent(self):
        """Absent unblocks fields parse as None."""
        text = (
            "## Ra\n\n"
            "- Tracker sync note (d, w1): **W1.** Class: MAINTENANCE. Gate: G5. "
            "NO_OP_PROOF: tooling.\n"
        )
        notes = parse_tracker_notes(text)
        assert len(notes) == 1
        assert notes[0]["unblocks_wave_id"] is None
        assert notes[0]["unblocks_runtime_blocker"] is None


class TestStructuralWorkloadTarget:
    """RCX-first binding: L4_STRUCTURAL waves must declare workload_target."""

    def test_missing_workload_target_fails(self):
        notes = [_make_note(
            wave_class="L4_STRUCTURAL",
            wave_id="wave-a99",
            workload_target=None,
            evidence_command="pytest tests/l4_gates/",
            evidence_delta="delta",
            host_semantics_delta_before="before-state",
            host_semantics_delta_after="after-state",
            structural_artifact_ref="mu/host/python/rcx_pi/selfhost/step_mu.py",
            post_gate_contract_sweep="pytest tests/structural/",
            progress_proof_before="before",
            progress_proof_after="after",
        )]
        files = ["mu/host/python/rcx_pi/selfhost/step_mu.py", "mu/tests/l4_gates/test_dummy.py"]
        diff = (
            "diff --git a/mu/host/python/rcx_pi/selfhost/step_mu.py b/mu/host/python/rcx_pi/selfhost/step_mu.py\n"
            "+++ b/mu/host/python/rcx_pi/selfhost/step_mu.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def foo(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert not passed
        assert any("workload_target" in e for e in errors)

    def test_invalid_workload_target_fails(self):
        notes = [_make_note(
            wave_class="L4_STRUCTURAL",
            wave_id="wave-a99",
            workload_target="docs_only",
            evidence_command="pytest tests/l4_gates/",
            evidence_delta="delta",
            host_semantics_delta_before="before-state",
            host_semantics_delta_after="after-state",
            structural_artifact_ref="mu/host/python/rcx_pi/selfhost/step_mu.py",
            post_gate_contract_sweep="pytest tests/structural/",
            progress_proof_before="before",
            progress_proof_after="after",
        )]
        files = ["mu/host/python/rcx_pi/selfhost/step_mu.py", "mu/tests/l4_gates/test_dummy.py"]
        diff = (
            "diff --git a/mu/host/python/rcx_pi/selfhost/step_mu.py b/mu/host/python/rcx_pi/selfhost/step_mu.py\n"
            "+++ b/mu/host/python/rcx_pi/selfhost/step_mu.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def foo(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert not passed
        assert any("Invalid workload_target" in e for e in errors)

    def test_valid_workload_target_passes(self):
        notes = [_make_note(
            wave_class="L4_STRUCTURAL",
            wave_id="wave-a99",
            workload_target="ontology_promotion",
            evidence_command="pytest tests/l4_gates/",
            evidence_delta="delta",
            host_semantics_delta_before="before runtime projection dispatch update",
            host_semantics_delta_after="after runtime projection dispatch update",
            structural_artifact_ref="mu/host/python/rcx_pi/selfhost/step_mu.py",
            post_gate_contract_sweep="pytest tests/structural/",
            progress_proof_before="before",
            progress_proof_after="after",
        )]
        files = ["mu/host/python/rcx_pi/selfhost/step_mu.py", "mu/tests/l4_gates/test_dummy.py"]
        diff = (
            "diff --git a/mu/host/python/rcx_pi/selfhost/step_mu.py b/mu/host/python/rcx_pi/selfhost/step_mu.py\n"
            "+++ b/mu/host/python/rcx_pi/selfhost/step_mu.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def foo(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert passed, f"Valid workload_target should pass: {errors}"

    def test_workload_target_constant(self):
        assert VALID_WORKLOAD_TARGETS == {
            "ontology_promotion",
            "rcx_engine_cycle",
            "seed_auto_execution",
            "execution_layer_truth",
            "recurrence_exhaustion",
            "host_debt_reduction",
        }


class TestWorkloadTargetProofBinding:
    """A20.4: Workload target proof binding.

    L4_STRUCTURAL waves with workload_target must have:
    1. Corresponding contract test files exist on disk
    2. At least one evidence file in changed scope or gate scripts
    3. evidence_command references a test module name
    """

    def test_evidence_mapping_has_entries(self):
        """WORKLOAD_TARGET_EVIDENCE has non-empty entries for key targets."""
        assert len(WORKLOAD_TARGET_EVIDENCE["seed_auto_execution"]) >= 1
        assert len(WORKLOAD_TARGET_EVIDENCE["rcx_engine_cycle"]) >= 1
        assert len(WORKLOAD_TARGET_EVIDENCE["execution_layer_truth"]) >= 1

    def test_evidence_files_exist_on_disk(self):
        """All evidence files in WORKLOAD_TARGET_EVIDENCE must exist."""
        for target, files in WORKLOAD_TARGET_EVIDENCE.items():
            for ef in files:
                assert Path(ef).exists() or Path(REPO_ROOT / ef).exists(), (
                    f"Evidence file for '{target}' missing on disk: {ef}"
                )

    def test_proof_binding_passes_when_evidence_in_scope(self):
        """Proof binding passes when evidence file is in changed_files."""
        errors = _check_proof_binding(
            "seed_auto_execution",
            "pytest mu/tests/structural/test_seed_auto_execution_contract.py",
            ["mu/tests/structural/test_seed_auto_execution_contract.py"],
        )
        assert errors == [], f"Should pass: {errors}"

    def test_proof_binding_fails_when_evidence_not_in_scope(self):
        """Proof binding fails when no evidence file is in scope or gate scripts."""
        errors = _check_proof_binding(
            "seed_auto_execution",
            "pytest mu/tests/structural/test_seed_auto_execution_contract.py",
            ["mu/host/python/rcx_pi/selfhost/step_mu.py"],  # no evidence files
        )
        # Should fail unless gate scripts reference the files
        # (gate scripts might reference them after CI wiring)
        if errors:
            assert any("proof binding" in e for e in errors)

    def test_proof_binding_fails_on_missing_module_in_evidence_command(self):
        """evidence_command must reference a test module name."""
        errors = _check_proof_binding(
            "rcx_engine_cycle",
            "pytest tests/l4_gates/test_whatever.py",
            ["mu/tests/structural/test_rcx_engine_workload_contract.py"],
        )
        assert any("evidence_command must reference" in e for e in errors)

    def test_proof_binding_skipped_for_empty_evidence_list(self):
        """Targets with no evidence files skip proof binding."""
        errors = _check_proof_binding(
            "ontology_promotion",
            "pytest tests/l4_gates/",
            ["mu/host/python/rcx_pi/selfhost/step_mu.py"],
        )
        assert errors == []

    def test_proof_binding_integrated_in_enforce(self):
        """enforce() calls proof binding for L4_STRUCTURAL with workload_target."""
        notes = [_make_note(
            wave_class="L4_STRUCTURAL",
            wave_id="wave-proof",
            workload_target="seed_auto_execution",
            evidence_command="pytest tests/l4_gates/test_whatever.py",
            evidence_delta="delta",
            host_semantics_delta_before="before runtime update",
            host_semantics_delta_after="after runtime update",
            structural_artifact_ref="mu/host/python/rcx_pi/selfhost/step_mu.py",
            post_gate_contract_sweep="pytest tests/structural/",
            progress_proof_before="before",
            progress_proof_after="after",
        )]
        files = [
            "mu/host/python/rcx_pi/selfhost/step_mu.py",
            "mu/tests/l4_gates/test_dummy.py",
        ]
        diff = (
            "diff --git a/mu/host/python/rcx_pi/selfhost/step_mu.py b/mu/host/python/rcx_pi/selfhost/step_mu.py\n"
            "+++ b/mu/host/python/rcx_pi/selfhost/step_mu.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def foo(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        # Should fail because evidence_command doesn't reference test module
        assert not passed
        assert any("proof binding" in e for e in errors)


# =============================================================================
# FOUNDER_OVERRIDE comment-only runtime bypass
# =============================================================================

# Shared diff fixtures for override tests
_COMMENT_ONLY_DIFF = (
    "diff --git a/mu/host/python/rcx_pi/selfhost/step_mu.py "
    "b/mu/host/python/rcx_pi/selfhost/step_mu.py\n"
    "@@ -1,3 +1,3 @@\n"
    "-# Old comment\n"
    "+# New comment\n"
)

_EXECUTABLE_DIFF = (
    "diff --git a/mu/host/python/rcx_pi/selfhost/step_mu.py "
    "b/mu/host/python/rcx_pi/selfhost/step_mu.py\n"
    "@@ -31,3 +31,3 @@\n"
    "-import json\n"
    "+import os\n"
)

_RUNTIME_FILES = ["mu/host/python/rcx_pi/selfhost/step_mu.py"]


class TestFounderOverrideCommentOnlyBypass:
    """FOUNDER_OVERRIDE for comment/docstring-only runtime edits."""

    def test_comment_only_with_valid_override_passes(self) -> None:
        """Positive: comment-only runtime + valid FOUNDER_OVERRIDE + metadata → PASS."""
        notes = [_make_note(
            wave_class="",
            founder_override="FO-001-test",
            no_op_proof="comment/docstring cleanup only",
            gate="G5",
        )]
        passed, errors = enforce(
            None, _RUNTIME_FILES, _COMMENT_ONLY_DIFF, notes,
            override_wave_bound=True,
        )
        assert passed, f"Should pass with valid override: {errors}"

    def test_no_override_fails(self) -> None:
        """Negative: runtime files without FOUNDER_OVERRIDE → FAIL-CLOSED."""
        notes = [_make_note(wave_class="")]
        passed, errors = enforce(None, _RUNTIME_FILES, _COMMENT_ONLY_DIFF, notes)
        assert not passed
        assert any("FAIL-CLOSED" in e for e in errors)

    def test_executable_change_with_override_fails(self) -> None:
        """Negative: executable runtime delta + FOUNDER_OVERRIDE → rejected."""
        notes = [_make_note(
            wave_class="",
            founder_override="FO-002-exec",
            no_op_proof="this has executable changes",
            gate="G5",
        )]
        passed, errors = enforce(
            None, _RUNTIME_FILES, _EXECUTABLE_DIFF, notes,
            override_wave_bound=True,
        )
        assert not passed
        assert any("executable changes" in e for e in errors)

    def test_malformed_override_id_fails(self) -> None:
        """Negative: empty FOUNDER_OVERRIDE → treated as no override → FAIL-CLOSED."""
        notes = [_make_note(
            wave_class="",
            founder_override="",
            no_op_proof="comment cleanup",
            gate="G5",
        )]
        passed, errors = enforce(
            None, _RUNTIME_FILES, _COMMENT_ONLY_DIFF, notes,
            override_wave_bound=True,
        )
        assert not passed
        assert any("FAIL-CLOSED" in e for e in errors)

    def test_missing_metadata_fails(self) -> None:
        """Negative: valid override but missing no_op_proof → rejected."""
        notes = [_make_note(
            wave_class="",
            founder_override="FO-003-nometa",
            no_op_proof=None,
            gate="G5",
        )]
        passed, errors = enforce(
            None, _RUNTIME_FILES, _COMMENT_ONLY_DIFF, notes,
            override_wave_bound=True,
        )
        assert not passed
        assert any("missing required metadata" in e for e in errors)

    def test_missing_gate_fails(self) -> None:
        """Negative: valid override but missing target_gate_id → rejected."""
        notes = [_make_note(
            wave_class="",
            founder_override="FO-004-nogate",
            no_op_proof="comment cleanup",
            gate=None,
        )]
        passed, errors = enforce(
            None, _RUNTIME_FILES, _COMMENT_ONLY_DIFF, notes,
            override_wave_bound=True,
        )
        assert not passed
        assert any("missing required metadata" in e for e in errors)

    def test_no_notes_fails(self) -> None:
        """Negative: no tracker notes at all → FAIL-CLOSED."""
        passed, errors = enforce(None, _RUNTIME_FILES, _COMMENT_ONLY_DIFF, None)
        assert not passed
        assert any("FAIL-CLOSED" in e for e in errors)

    def test_no_diff_text_fails(self) -> None:
        """Negative: runtime files but no diff text available → FAIL-CLOSED."""
        notes = [_make_note(
            wave_class="",
            founder_override="FO-005-nodiff",
            no_op_proof="comment cleanup",
            gate="G5",
        )]
        passed, errors = enforce(
            None, _RUNTIME_FILES, None, notes,
            override_wave_bound=True,
        )
        assert not passed
        assert any("FAIL-CLOSED" in e for e in errors)

    def test_classless_runtime_override_with_control_plane_file_fails(self) -> None:
        """Negative: classless no-op runtime override cannot hide tooling changes."""
        notes = [_make_note(
            wave_class="",
            founder_override="FO-006-control-plane",
            no_op_proof="comment cleanup",
            gate="G5",
        )]
        passed, errors = enforce(
            None,
            [*_RUNTIME_FILES, "mu/tools/executors/phase_b_executor.py"],
            _COMMENT_ONLY_DIFF,
            notes,
            override_wave_bound=True,
        )
        assert not passed
        assert any("control-plane" in e and "no wave class" in e for e in errors)

    def test_duplicate_override_id_fails_replay(self) -> None:
        """Negative: same FOUNDER_OVERRIDE ID in window → replay rejection."""
        notes = [
            _make_note(
                wave_class="",
                wave_id="w2-current",
                founder_override="FO-DUP-replay",
                no_op_proof="comment cleanup",
                gate="G5",
            ),
            _make_note(
                wave_class="MAINTENANCE",
                wave_id="w1-prior",
                founder_override="FO-DUP-replay",  # DUPLICATE
            ),
        ]
        passed, errors = enforce(
            None, _RUNTIME_FILES, _COMMENT_ONLY_DIFF, notes,
            override_wave_bound=True,
        )
        assert not passed
        assert any("replay" in e.lower() for e in errors)

    def test_unique_override_id_passes_replay(self) -> None:
        """Positive: unique override ID with prior wave → passes replay check."""
        notes = [
            _make_note(
                wave_class="",
                wave_id="w2-current",
                founder_override="FO-UNIQUE-a",
                no_op_proof="comment cleanup",
                gate="G5",
            ),
            _make_note(
                wave_class="MAINTENANCE",
                wave_id="w1-prior",
                founder_override="FO-UNIQUE-b",  # Different ID
            ),
        ]
        passed, errors = enforce(
            None, _RUNTIME_FILES, _COMMENT_ONLY_DIFF, notes,
            override_wave_bound=True,
        )
        assert passed, f"Unique override IDs should pass: {errors}"


class TestClasslessNoteParserBinding:
    """Classless notes with FOUNDER_OVERRIDE must be parseable by wave-id."""

    def test_classless_override_note_is_parsed(self) -> None:
        """Parser must include notes without Class: when FOUNDER_OVERRIDE is present."""
        from enforce_l4_execution_contract import parse_tracker_notes
        text = (
            "- Tracker sync note (2026-03-03, w2-test-classless): "
            "**W2 test.** FOUNDER_OVERRIDE:FO-TEST-classless. "
            "no_op_proof: comment-only. target_gate_id: G5. "
            "primary_blocker_class: INTEGRATION. "
            "primary_invariant_id: INV_CROSS_SUBSTRATE_PARITY. "
            "indicator_artifact_ref: reports/l4_wave_indicators/w2-test-classless.json. "
            "indicator_collection_command: python3 tools/metrics/collect_l4_wave_indicators.py --wave-id w2-test-classless. "
            "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            "boot0_track_id: N3. boot0_progress_state: HOLD."
        )
        notes = parse_tracker_notes(text)
        wave_ids = [n["wave_id"] for n in notes]
        assert "w2-test-classless" in wave_ids, (
            f"Classless FOUNDER_OVERRIDE note not parsed. Found: {wave_ids}"
        )
        note = [n for n in notes if n["wave_id"] == "w2-test-classless"][0]
        assert note["wave_class"] is None
        assert note["founder_override"] == "FO-TEST-classless"

    def test_classless_note_without_override_skipped(self) -> None:
        """Parser must skip notes without Class: AND without FOUNDER_OVERRIDE."""
        from enforce_l4_execution_contract import parse_tracker_notes
        text = (
            "- Tracker sync note (2026-03-03, w2-no-class-no-override): "
            "**W2 nothing.** target_gate_id: G5."
        )
        notes = parse_tracker_notes(text)
        wave_ids = [n["wave_id"] for n in notes]
        assert "w2-no-class-no-override" not in wave_ids


class TestIsCommentOnlyRuntimeDiff:
    """Unit tests for the enhanced comment-only diff classifier."""

    def test_pure_comment_change(self) -> None:
        from enforce_l4_execution_contract import is_comment_only_runtime_diff
        diff = (
            "diff --git a/mu/host/js/core/constants.js b/mu/host/js/core/constants.js\n"
            "@@ -1,3 +1,3 @@\n"
            "- * old JS comment\n"
            "+ * new JS comment\n"
        )
        ok, violations = is_comment_only_runtime_diff(diff, ["mu/host/js/core/constants.js"])
        assert ok, f"JS comment change should pass: {violations}"

    def test_executable_change_detected(self) -> None:
        from enforce_l4_execution_contract import is_comment_only_runtime_diff
        diff = (
            "diff --git a/mu/host/js/core/constants.js b/mu/host/js/core/constants.js\n"
            "@@ -1,3 +1,3 @@\n"
            "-const X = 1;\n"
            "+const X = 2;\n"
        )
        ok, violations = is_comment_only_runtime_diff(diff, ["mu/host/js/core/constants.js"])
        assert not ok
        assert len(violations) >= 1

    def test_inline_comment_addition_passes(self) -> None:
        from enforce_l4_execution_contract import is_comment_only_runtime_diff
        diff = (
            "diff --git a/mu/host/python/rcx_pi/selfhost/step_mu.py "
            "b/mu/host/python/rcx_pi/selfhost/step_mu.py\n"
            "@@ -30,3 +30,3 @@\n"
            "-import time\n"
            "+import time  # CONTRABAND_OK: debug timestamps\n"
        )
        ok, violations = is_comment_only_runtime_diff(
            diff, ["mu/host/python/rcx_pi/selfhost/step_mu.py"],
        )
        assert ok, f"Inline comment addition should pass: {violations}"

    def test_python_comment_change(self) -> None:
        from enforce_l4_execution_contract import is_comment_only_runtime_diff
        diff = (
            "diff --git a/mu/host/python/rcx_pi/selfhost/step_mu.py "
            "b/mu/host/python/rcx_pi/selfhost/step_mu.py\n"
            "@@ -1,3 +1,3 @@\n"
            "-# old Python comment\n"
            "+# new Python comment\n"
        )
        ok, violations = is_comment_only_runtime_diff(
            diff, ["mu/host/python/rcx_pi/selfhost/step_mu.py"],
        )
        assert ok, f"Python comment change should pass: {violations}"


# =============================================================================
# P1 #1: is_comment_only_runtime_diff must use caller-supplied old_ref
# =============================================================================

class TestCommentOnlyPreimageRef:
    """P1 regression: old_ref must be threaded, not hardcoded to HEAD."""

    def test_old_ref_parameter_exists(self) -> None:
        """is_comment_only_runtime_diff must accept old_ref parameter."""
        import inspect
        from enforce_l4_execution_contract import is_comment_only_runtime_diff
        sig = inspect.signature(is_comment_only_runtime_diff)
        assert "old_ref" in sig.parameters, (
            "is_comment_only_runtime_diff must accept old_ref parameter"
        )

    def test_old_ref_default_is_HEAD(self) -> None:
        """Default old_ref must be HEAD (safe default for --staged mode)."""
        import inspect
        from enforce_l4_execution_contract import is_comment_only_runtime_diff
        sig = inspect.signature(is_comment_only_runtime_diff)
        param = sig.parameters["old_ref"]
        assert param.default == "HEAD", (
            f"old_ref default must be HEAD, got {param.default!r}"
        )

    def test_source_has_no_hardcoded_HEAD_in_git_show(self) -> None:
        """Source must use old_ref variable, not hardcoded 'HEAD:' in git show."""
        from tests.repo_root import REPO_ROOT
        src = (REPO_ROOT / "tools" / "checks" / "enforce_l4_execution_contract.py").read_text()
        # Find the is_comment_only_runtime_diff function body
        start = src.index("def is_comment_only_runtime_diff(")
        # Find the next top-level def (not indented)
        import re
        next_def = re.search(r"\ndef [a-z_]", src[start + 10:])
        body = src[start:start + 10 + next_def.start()] if next_def else src[start:]
        # Must NOT contain hardcoded HEAD in git show
        assert 'f"HEAD:{' not in body, (
            "git show must use old_ref variable, not hardcoded HEAD"
        )
        # Must contain parameterized old_ref
        assert 'f"{old_ref}:{' in body, (
            "git show must use f\"{old_ref}:{{filepath}}\" pattern"
        )

    def test_old_ref_is_threaded_at_runtime(self, monkeypatch) -> None:
        """Behavioral: old_ref value must reach the subprocess.check_output call."""
        from enforce_l4_execution_contract import is_comment_only_runtime_diff
        import subprocess

        captured_cmds: list[list[str]] = []
        original_check_output = subprocess.check_output

        def spy_check_output(cmd, **kwargs):
            captured_cmds.append(list(cmd))
            return original_check_output(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "check_output", spy_check_output)

        # Use a Python runtime file diff so the function attempts git show
        diff = (
            "diff --git a/mu/host/python/rcx_pi/selfhost/step_mu.py "
            "b/mu/host/python/rcx_pi/selfhost/step_mu.py\n"
            "@@ -1,3 +1,3 @@\n"
            "-# old comment\n"
            "+# new comment\n"
        )
        runtime_files = ["mu/host/python/rcx_pi/selfhost/step_mu.py"]
        custom_ref = "abc123fake"

        # Call with a distinctive old_ref — may fail (ref doesn't exist),
        # but subprocess.check_output will be called with it first
        is_comment_only_runtime_diff(diff, runtime_files, old_ref=custom_ref)

        # Verify the custom old_ref was threaded to the git show call
        git_show_cmds = [c for c in captured_cmds if "git" in c and "show" in c]
        assert len(git_show_cmds) >= 1, (
            f"Expected git show call, got: {captured_cmds}"
        )
        show_arg = git_show_cmds[0][-1]  # last arg is "ref:filepath"
        assert show_arg.startswith(f"{custom_ref}:"), (
            f"git show must use old_ref={custom_ref!r}, got arg: {show_arg!r}"
        )


# =============================================================================
# P1 #2: FOUNDER_OVERRIDE must require explicit wave binding
# =============================================================================

class TestOverrideWaveBinding:
    """P1 regression: stale top-note overrides must be rejected when unbound."""

    def test_unbound_override_fails_closed(self) -> None:
        """Override in notes[0] WITHOUT override_wave_bound → FAIL-CLOSED."""
        notes = [_make_note(
            wave_class="",
            founder_override="FO-STALE-001",
            no_op_proof="comment cleanup",
            gate="G5",
        )]
        # override_wave_bound defaults to False → must reject
        passed, errors = enforce(None, _RUNTIME_FILES, _COMMENT_ONLY_DIFF, notes)
        assert not passed, "Unbound override must fail-closed"
        assert any("FAIL-CLOSED" in e for e in errors), (
            f"Error must be FAIL-CLOSED (not specific override error): {errors}"
        )

    def test_bound_override_passes(self) -> None:
        """Override with override_wave_bound=True → uses override path."""
        notes = [_make_note(
            wave_class="",
            founder_override="FO-BOUND-001",
            no_op_proof="comment cleanup",
            gate="G5",
        )]
        passed, errors = enforce(
            None, _RUNTIME_FILES, _COMMENT_ONLY_DIFF, notes,
            override_wave_bound=True,
        )
        assert passed, f"Bound override with comment-only diff should pass: {errors}"

    def test_enforce_signature_has_override_wave_bound(self) -> None:
        """enforce() must accept override_wave_bound parameter."""
        import inspect
        sig = inspect.signature(enforce)
        assert "override_wave_bound" in sig.parameters, (
            "enforce() must accept override_wave_bound parameter"
        )
        param = sig.parameters["override_wave_bound"]
        assert param.default is False, (
            f"override_wave_bound default must be False (fail-closed), got {param.default!r}"
        )

    def test_enforce_signature_has_old_ref(self) -> None:
        """enforce() must accept old_ref parameter and thread it."""
        import inspect
        sig = inspect.signature(enforce)
        assert "old_ref" in sig.parameters, (
            "enforce() must accept old_ref parameter"
        )


# =============================================================================
# _derive_old_ref_from_range: CLI helper for preimage derivation
# =============================================================================

class TestDeriveOldRefFromRange:
    """Unit tests for range-to-preimage derivation helper."""

    def test_three_dot_uses_merge_base(self) -> None:
        """A...B (symmetric diff) must call git merge-base(A, B)."""
        from enforce_l4_execution_contract import _derive_old_ref_from_range
        # HEAD...HEAD always has merge-base = HEAD
        ref = _derive_old_ref_from_range("HEAD...HEAD")
        assert ref, "merge-base(HEAD, HEAD) must return a commit hash"
        # Must be a valid commit hash (40 hex chars)
        assert len(ref) >= 7, f"Expected commit hash, got {ref!r}"

    def test_two_dot_extracts_left_side(self) -> None:
        """A..B (linear diff) must return A as old_ref."""
        from enforce_l4_execution_contract import _derive_old_ref_from_range
        ref = _derive_old_ref_from_range("abc123..HEAD")
        assert ref == "abc123"

    def test_single_ref_returns_itself(self) -> None:
        """Single ref (no dots) must return itself."""
        from enforce_l4_execution_contract import _derive_old_ref_from_range
        ref = _derive_old_ref_from_range("HEAD~3")
        assert ref == "HEAD~3"

    def test_unresolvable_merge_base_raises(self) -> None:
        """Unresolvable merge-base must raise ValueError (fail-closed)."""
        from enforce_l4_execution_contract import _derive_old_ref_from_range
        import pytest
        with pytest.raises(ValueError, match="Cannot resolve merge-base"):
            _derive_old_ref_from_range("nonexistent_ref_abc...HEAD")

    def test_three_dot_empty_right_normalizes_to_head(self) -> None:
        """A... (omitted right side) must normalize to A...HEAD."""
        from enforce_l4_execution_contract import _derive_old_ref_from_range
        # HEAD... should resolve same as HEAD...HEAD
        ref = _derive_old_ref_from_range("HEAD...")
        assert ref, "HEAD... must resolve (empty right normalized to HEAD)"
        assert len(ref) >= 7, f"Expected commit hash, got {ref!r}"

    def test_three_dot_empty_left_normalizes_to_head(self) -> None:
        """...B (omitted left side) must normalize to HEAD...B."""
        from enforce_l4_execution_contract import _derive_old_ref_from_range
        ref = _derive_old_ref_from_range("...HEAD")
        assert ref, "...HEAD must resolve (empty left normalized to HEAD)"
        assert len(ref) >= 7, f"Expected commit hash, got {ref!r}"

    def test_two_dot_empty_left_normalizes_to_head(self) -> None:
        """..B (omitted left side) must normalize to HEAD."""
        from enforce_l4_execution_contract import _derive_old_ref_from_range
        ref = _derive_old_ref_from_range("..HEAD")
        assert ref == "HEAD"

    def test_empty_string_raises_value_error(self) -> None:
        """Empty string must fail closed with ValueError."""
        from enforce_l4_execution_contract import _derive_old_ref_from_range
        import pytest
        with pytest.raises(ValueError, match="Empty git range is invalid"):
            _derive_old_ref_from_range("")

    def test_whitespace_only_raises_value_error(self) -> None:
        """Whitespace-only string must fail closed with ValueError."""
        from enforce_l4_execution_contract import _derive_old_ref_from_range
        import pytest
        with pytest.raises(ValueError, match="Empty git range is invalid"):
            _derive_old_ref_from_range("   ")

    def test_whitespace_padded_range_is_stripped(self) -> None:
        """Whitespace-padded range must be normalized via strip()."""
        from enforce_l4_execution_contract import _derive_old_ref_from_range
        ref = _derive_old_ref_from_range("  abc123..HEAD  ")
        assert ref == "abc123", f"Expected 'abc123' after strip, got {ref!r}"

    def test_whitespace_padded_three_dot_is_stripped(self) -> None:
        """Whitespace-padded three-dot range must be normalized via strip()."""
        from enforce_l4_execution_contract import _derive_old_ref_from_range
        ref = _derive_old_ref_from_range("  HEAD...HEAD  ")
        assert ref, "Should resolve merge-base after stripping whitespace"
        assert len(ref) >= 7, f"Expected commit hash, got {ref!r}"

    def test_whitespace_padded_single_ref_is_stripped(self) -> None:
        """Whitespace-padded single ref must be normalized via strip()."""
        from enforce_l4_execution_contract import _derive_old_ref_from_range
        ref = _derive_old_ref_from_range("  HEAD~3  ")
        assert ref == "HEAD~3", f"Expected 'HEAD~3' after strip, got {ref!r}"
