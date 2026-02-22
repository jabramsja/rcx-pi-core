"""
L4 Governance Contract Tests — No-stagnation enforcement.

Tests all 7 mandatory constraints (1-7) plus valid examples for all 3 classes.

Usage:
    PYTHONHASHSEED=0 pytest tests/l4_gates/test_l4_governance_contract.py -v
"""

from __future__ import annotations

import sys

import pytest

from tests.repo_root import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "tools" / "checks"))

from enforce_l4_execution_contract import (
    CANONICAL_BOOTSTRAP_POLICY,
    CANONICAL_COLLECTOR_PATH,
    GATE_ID_RE,
    INDICATOR_REQUIRED_KEYS,
    LEGACY_CLASS_ALIAS,
    NON_GATE_TEST_DOMAINS,
    VALID_BLOCKER_CLASSES,
    VALID_INVARIANT_IDS,
    VALID_WAVE_CLASSES,
    check_consecutive_maintenance,
    check_founder_override_replay,
    check_legacy_alias_in_new_notes,
    check_non_structural_adjacency,
    check_noop_throttle,
    check_rolling_window,
    enforce,
    is_runtime_file,
    parse_tracker_notes,
    validate_indicator_artifact_json,
)


# ---------------------------------------------------------------------------
# Helpers — build tracker notes for testing
# ---------------------------------------------------------------------------

def _note(wave_class, gate="G8", raw_class=None, no_op_proof=None,
          evidence_command="pytest tests/l4_gates/", evidence_delta="delta",
          hd_before=None, hd_after=None, sa_ref=None,
          defer_reason=None, founder_override=None, wave_id="test-wave",
          blocker_class="INTEGRATION", sweep=None,
          invariant_id="INV_STRUCTURAL_FORWARD_MOTION",
          pp_before="before-state", pp_after="after-state",
          indicator_ref="reports/l4_wave_indicators/test-wave.json",
          indicator_cmd="python3 tools/metrics/collect_l4_wave_indicators.py --wave-id test-wave",
          bootstrap_policy="SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP"):
    """Build a mock tracker note dict."""
    return {
        "wave_id": wave_id,
        "raw_class": raw_class or wave_class,
        "wave_class": wave_class,
        "gate": gate,
        "no_op_proof": no_op_proof,
        "evidence_command": evidence_command,
        "evidence_delta": evidence_delta,
        "host_semantics_delta_before": hd_before,
        "host_semantics_delta_after": hd_after,
        "structural_artifact_ref": sa_ref,
        "defer_reason_code": defer_reason,
        "founder_override": founder_override,
        "primary_blocker_class": blocker_class,
        "post_gate_contract_sweep": sweep,
        "primary_invariant_id": invariant_id,
        "progress_proof_before": pp_before,
        "progress_proof_after": pp_after,
        "indicator_artifact_ref": indicator_ref,
        "indicator_collection_command": indicator_cmd,
        "bootstrap_endgame_policy": bootstrap_policy,
        "date": "2026-02-20",
        "raw": f"Class: {raw_class or wave_class}",
    }


# =============================================================================
# Constraint 1: L4_ENABLER runtime prohibition
# =============================================================================

class TestL4EnablerRuntimeProhibition:
    """L4_ENABLER cannot touch runtime/substrate dirs."""

    def test_enabler_runtime_touch_fails(self):
        files = ["rcx_pi/selfhost/eval_seed.py", "TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files)
        assert not passed
        assert any("L4_ENABLER" in e and "runtime" in e.lower() for e in errors)

    def test_enabler_no_runtime_passes(self):
        notes = [_note("L4_ENABLER")]
        files = ["TASKS.md", "CLAUDE.md", "tests/l4_gates/test_foo.py"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert passed, f"Should pass: {errors}"


# =============================================================================
# Constraint 2: NO_OP throttling
# =============================================================================

class TestNoopThrottle:
    """Same gate cannot use NO_OP_PROOF twice in rolling window."""

    def test_repeated_noop_same_gate_fails(self):
        notes = [
            _note("MAINTENANCE", gate="G8", no_op_proof="reason1", defer_reason="d1"),
            _note("L4_STRUCTURAL", gate="G8"),
            _note("MAINTENANCE", gate="G8", no_op_proof="reason2", defer_reason="d2"),
        ]
        passed, errors = check_noop_throttle(notes)
        assert not passed
        assert any("NO_OP throttle" in e for e in errors)

    def test_noop_different_gates_passes(self):
        notes = [
            _note("MAINTENANCE", gate="G8", no_op_proof="r1", defer_reason="d1"),
            _note("L4_STRUCTURAL", gate="G5"),
            _note("MAINTENANCE", gate="G5", no_op_proof="r2", defer_reason="d2"),
        ]
        passed, errors = check_noop_throttle(notes)
        assert passed, f"Different gates should pass: {errors}"


# =============================================================================
# Constraint 3: Founder override
# =============================================================================

class TestFounderOverride:
    """FOUNDER_OVERRIDE token grants one exception; replays fail."""

    def test_override_allows_noop_repeat(self):
        notes = [
            _note("MAINTENANCE", gate="G8", no_op_proof="r1", defer_reason="d1",
                  founder_override="2026-02-20-exception"),
            _note("L4_STRUCTURAL", gate="G8"),
            _note("MAINTENANCE", gate="G8", no_op_proof="r2", defer_reason="d2"),
        ]
        passed, _ = check_noop_throttle(notes)
        assert passed  # Override active

    def test_override_does_not_cover_triple_noop(self):
        """3 NO_OP for same gate fails even with override (one exception only)."""
        notes = [
            _note("MAINTENANCE", gate="G8", no_op_proof="r1", defer_reason="d1",
                  founder_override="2026-02-20-exception"),
            _note("MAINTENANCE", gate="G8", no_op_proof="r2", defer_reason="d2"),
            _note("MAINTENANCE", gate="G8", no_op_proof="r3", defer_reason="d3"),
        ]
        passed, errors = check_noop_throttle(notes)
        assert not passed
        assert any("one exception only" in e for e in errors)

    def test_override_cross_gate_isolation(self):
        """Override on G8 must not suppress G5 throttle."""
        notes = [
            _note("MAINTENANCE", gate="G8", no_op_proof="r1", defer_reason="d1",
                  founder_override="override-g8"),
            _note("MAINTENANCE", gate="G5", no_op_proof="r2", defer_reason="d2"),
            _note("MAINTENANCE", gate="G5", no_op_proof="r3", defer_reason="d3"),
        ]
        passed, errors = check_noop_throttle(notes)
        assert not passed
        assert any("G5" in e for e in errors)

    def test_override_replay_fails(self):
        notes = [
            _note("MAINTENANCE", gate="G8", founder_override="same-id", defer_reason="d1"),
            _note("L4_STRUCTURAL", gate="G8"),
            _note("MAINTENANCE", gate="G5", founder_override="same-id", defer_reason="d2"),
        ]
        passed, errors = check_founder_override_replay(notes)
        assert not passed
        assert any("replay" in e.lower() for e in errors)


# =============================================================================
# Constraint 4: Rolling window quota (tested in TestRollingWindowQuota below)

# Constraint 5: Legacy alias lock
# =============================================================================

class TestLegacyAliasLock:
    """L4_CLASS_A accepted for historical parse only; new notes must fail."""

    def test_new_note_with_l4_class_a_fails(self):
        notes = [_note("L4_STRUCTURAL", raw_class="L4_CLASS_A")]
        passed, errors = check_legacy_alias_in_new_notes(notes)
        assert not passed
        assert any("legacy" in e.lower() or "L4_CLASS_A" in e for e in errors)

    def test_historical_alias_parses_correctly(self):
        text = (
            "## Ra\n\n"
            "- Tracker sync note (2026-02-20, old-wave): **Old wave.** "
            "Class: L4_CLASS_A. Gate: G8. Evidence: old stuff.\n"
        )
        notes = parse_tracker_notes(text)
        assert len(notes) == 1
        assert notes[0]["wave_class"] == "L4_STRUCTURAL"
        assert notes[0]["raw_class"] == "L4_CLASS_A"


# =============================================================================
# Constraint 6: L4_STRUCTURAL anti-theater (AND rule)
# =============================================================================

class TestStructuralAntiTheater:
    """L4_STRUCTURAL requires runtime touch + l4_gates test + host delta."""

    def test_structural_missing_l4_gates_change_fails(self):
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/test_foo.py"]
        passed, errors = enforce("L4_STRUCTURAL", files)
        assert not passed
        assert any("tests/l4_gates/" in e for e in errors)

    def test_structural_missing_host_delta_fails(self):
        notes = [_note("L4_STRUCTURAL", hd_before=None, hd_after=None, sa_ref=None)]
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_gate.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def new_func(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert not passed
        assert any("host_semantics_delta_before" in e for e in errors)

    def test_structural_missing_evidence_command_fails(self):
        notes = [_note("L4_STRUCTURAL", hd_before="old", hd_after="new",
                       sa_ref="ref", evidence_command=None)]
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_gate.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def new_func(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert not passed
        assert any("evidence_command" in e for e in errors)

    def test_structural_no_runtime_fails(self):
        files = ["TASKS.md", "tests/l4_gates/test_gate.py"]
        passed, errors = enforce("L4_STRUCTURAL", files)
        assert not passed
        assert any("no runtime" in e.lower() for e in errors)

    def test_structural_evidence_command_must_reference_l4_gates(self):
        """evidence_command without tests/l4_gates/ reference fails."""
        notes = [_note("L4_STRUCTURAL", hd_before="old", hd_after="new",
                       sa_ref="ref", evidence_command="pytest tests/")]
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_gate.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def new_func(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert not passed
        assert any("tests/l4_gates/" in e for e in errors)

    def test_structural_evidence_command_with_l4_gates_passes(self):
        """evidence_command referencing tests/l4_gates/ passes."""
        notes = [_note("L4_STRUCTURAL", hd_before="old", hd_after="new",
                       sa_ref="ref", evidence_command="pytest tests/l4_gates/",
                       sweep="pytest tests/structural/ tests/engine/")]
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_gate.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def new_func(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert passed, f"Should pass with l4_gates ref: {errors}"


# =============================================================================
# Constraint 7: No empty-scope auto-pass (tested at unit level)
# =============================================================================

class TestFailClosedOnMissingMarker:
    """Runtime changes without class marker must fail."""

    def test_runtime_no_class_fails(self):
        files = ["rcx_pi/selfhost/eval_seed.py"]
        passed, errors = enforce(None, files)
        assert not passed
        assert any("FAIL-CLOSED" in e for e in errors)

    def test_no_runtime_no_class_passes(self):
        files = ["README.md", "TASKS.md"]
        passed, errors = enforce(None, files)
        assert passed


# =============================================================================
# Rolling structural quota
# =============================================================================

class TestRollingWindowQuota:
    """Last 3 class-marked waves must include >=1 L4_STRUCTURAL."""

    def test_rolling_window_no_structural_fails(self):
        notes = [
            _note("L4_ENABLER"),
            _note("MAINTENANCE", no_op_proof="r", defer_reason="d"),
            _note("L4_ENABLER"),
        ]
        passed, errors = check_rolling_window(notes)
        assert not passed
        assert any("Rolling structural quota" in e for e in errors)

    def test_rolling_window_with_structural_passes(self):
        notes = [
            _note("L4_ENABLER"),
            _note("L4_STRUCTURAL"),
            _note("MAINTENANCE", no_op_proof="r", defer_reason="d"),
        ]
        passed, errors = check_rolling_window(notes)
        assert passed, f"Should pass: {errors}"

    def test_rolling_window_bootstrap_grace(self):
        """Fewer than 3 notes = bootstrap grace, skip check."""
        notes = [_note("L4_ENABLER"), _note("MAINTENANCE", no_op_proof="r", defer_reason="d")]
        passed, errors = check_rolling_window(notes)
        assert passed


# =============================================================================
# Strict validation
# =============================================================================

class TestStrictValidation:
    """Strict enum and gate ID validation."""

    def test_3_class_model_defined(self):
        assert VALID_WAVE_CLASSES == {"L4_STRUCTURAL", "L4_ENABLER", "MAINTENANCE"}

    def test_legacy_alias_mapping(self):
        assert LEGACY_CLASS_ALIAS == {"L4_CLASS_A": "L4_STRUCTURAL"}

    def test_invalid_class_fails(self):
        passed, errors = enforce("UNKNOWN_CLASS", ["README.md"])
        assert not passed
        assert any("Unknown wave class" in e for e in errors)

    @pytest.mark.parametrize("gate_id", ["G0", "G9", "G10", "GX", "g1", ""])
    def test_invalid_gate_id_rejected(self, gate_id):
        assert not GATE_ID_RE.match(gate_id)

    @pytest.mark.parametrize("gate_id", ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"])
    def test_valid_gate_id_accepted(self, gate_id):
        assert GATE_ID_RE.match(gate_id)

    def test_maintenance_runtime_touch_fails(self):
        passed, errors = enforce("MAINTENANCE", ["mu/host/js/eval_step.js"])
        assert not passed
        assert any("touches runtime" in e for e in errors)

    def test_consecutive_maintenance_cap(self):
        notes = [
            _note("MAINTENANCE", no_op_proof="r1", defer_reason="d1"),
            _note("MAINTENANCE", no_op_proof="r2", defer_reason="d2"),
        ]
        assert check_consecutive_maintenance(notes) is True


# =============================================================================
# Valid examples for all 3 classes
# =============================================================================

class TestValidExamples:
    """Valid waves for all 3 classes must pass."""

    def test_valid_l4_structural(self):
        notes = [_note("L4_STRUCTURAL", hd_before="old", hd_after="new",
                       sa_ref="mu/substrate/kernel.v1.json",
                       evidence_command="pytest tests/l4_gates/",
                       sweep="pytest tests/structural/ tests/engine/")]
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_gate.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def new_func(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert passed, f"Valid L4_STRUCTURAL should pass: {errors}"

    def test_valid_l4_enabler(self):
        notes = [_note("L4_ENABLER")]
        files = ["tools/checks/enforce_l4_execution_contract.py", "TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert passed, f"Valid L4_ENABLER should pass: {errors}"

    def test_valid_maintenance(self):
        notes = [
            _note("MAINTENANCE", no_op_proof="docs only", defer_reason="not_needed",
                  evidence_command=None, evidence_delta=None),
            _note("L4_STRUCTURAL"),  # Not consecutive
        ]
        files = ["TASKS.md", "STATUS.md"]
        passed, errors = enforce("MAINTENANCE", files, notes=notes)
        assert passed, f"Valid MAINTENANCE should pass: {errors}"


# =============================================================================
# Constraint 8: Primary blocker classification (all classes)
# =============================================================================

class TestBlockerClassification:
    """Every class-marked wave must declare primary_blocker_class."""

    def test_missing_blocker_class_fails(self):
        notes = [_note("L4_ENABLER", blocker_class=None)]
        files = ["TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert not passed
        assert any("primary_blocker_class" in e for e in errors)

    def test_invalid_blocker_class_fails(self):
        notes = [_note("L4_ENABLER", blocker_class="INVALID")]
        files = ["TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert not passed
        assert any("Invalid primary_blocker_class" in e for e in errors)

    @pytest.mark.parametrize("cls", sorted(VALID_BLOCKER_CLASSES))
    def test_valid_blocker_classes_accepted(self, cls):
        notes = [_note("L4_ENABLER", blocker_class=cls)]
        files = ["TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert passed, f"Blocker class {cls} should be accepted: {errors}"

    def test_blocker_class_required_for_structural(self):
        notes = [_note("L4_STRUCTURAL", hd_before="old", hd_after="new",
                       sa_ref="ref", sweep="pytest tests/structural/",
                       blocker_class=None)]
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def foo(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert not passed
        assert any("primary_blocker_class" in e for e in errors)

    def test_blocker_class_required_for_maintenance(self):
        notes = [
            _note("MAINTENANCE", no_op_proof="docs", defer_reason="d",
                  evidence_command=None, evidence_delta=None, blocker_class=None),
            _note("L4_STRUCTURAL"),  # Not consecutive
        ]
        files = ["TASKS.md"]
        passed, errors = enforce("MAINTENANCE", files, notes=notes)
        assert not passed
        assert any("primary_blocker_class" in e for e in errors)

    def test_valid_blocker_classes_constant(self):
        assert VALID_BLOCKER_CLASSES == {"DESIGN", "INTEGRATION", "PERFORMANCE"}


# =============================================================================
# Constraint 9: Post-gate contract sweep (L4_STRUCTURAL only)
# =============================================================================

class TestPostGateContractSweep:
    """L4_STRUCTURAL must include post_gate_contract_sweep with non-gate targets."""

    def test_missing_sweep_fails(self):
        notes = [_note("L4_STRUCTURAL", hd_before="old", hd_after="new",
                       sa_ref="ref", sweep=None)]
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def foo(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert not passed
        assert any("post_gate_contract_sweep" in e for e in errors)

    def test_sweep_with_only_l4_gates_fails(self):
        notes = [_note("L4_STRUCTURAL", hd_before="old", hd_after="new",
                       sa_ref="ref", sweep="pytest tests/l4_gates/")]
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def foo(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert not passed
        assert any("non-gate test domain" in e for e in errors)

    def test_sweep_with_non_gate_target_passes(self):
        notes = [_note("L4_STRUCTURAL", hd_before="old", hd_after="new",
                       sa_ref="ref", sweep="pytest tests/structural/ tests/engine/")]
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def foo(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert passed, f"Sweep with non-gate target should pass: {errors}"

    def test_sweep_with_mu_path_passes(self):
        notes = [_note("L4_STRUCTURAL", hd_before="old", hd_after="new",
                       sa_ref="ref", sweep="pytest mu/tests/structural/")]
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def foo(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert passed, f"Sweep with mu/ path should pass: {errors}"

    def test_sweep_not_required_for_enabler(self):
        notes = [_note("L4_ENABLER", sweep=None)]
        files = ["TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert passed, f"L4_ENABLER should not require sweep: {errors}"

    def test_sweep_not_required_for_maintenance(self):
        notes = [
            _note("MAINTENANCE", no_op_proof="docs", defer_reason="d",
                  evidence_command=None, evidence_delta=None, sweep=None),
            _note("L4_STRUCTURAL"),
        ]
        files = ["TASKS.md"]
        passed, errors = enforce("MAINTENANCE", files, notes=notes)
        assert passed, f"MAINTENANCE should not require sweep: {errors}"

    def test_non_gate_test_domains_constant(self):
        assert "tests/engine/" in NON_GATE_TEST_DOMAINS
        assert "tests/structural/" in NON_GATE_TEST_DOMAINS
        assert "mu/tests/engine/" in NON_GATE_TEST_DOMAINS
        assert len(NON_GATE_TEST_DOMAINS) == 10


# =============================================================================
# Constraint 10: Primary invariant ID (all classes)
# =============================================================================

class TestInvariantId:
    """Every class-marked wave must declare primary_invariant_id."""

    def test_missing_invariant_id_fails(self):
        notes = [_note("L4_ENABLER", invariant_id=None)]
        files = ["TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert not passed
        assert any("primary_invariant_id" in e for e in errors)

    def test_invalid_invariant_id_fails(self):
        notes = [_note("L4_ENABLER", invariant_id="INV_BOGUS")]
        files = ["TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert not passed
        assert any("Invalid primary_invariant_id" in e for e in errors)

    @pytest.mark.parametrize("inv_id", sorted(VALID_INVARIANT_IDS))
    def test_valid_invariant_ids_accepted(self, inv_id):
        notes = [_note("L4_ENABLER", invariant_id=inv_id)]
        files = ["TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert passed, f"Invariant ID {inv_id} should be accepted: {errors}"

    def test_invariant_id_required_for_structural(self):
        notes = [_note("L4_STRUCTURAL", hd_before="old", hd_after="new",
                       sa_ref="ref", sweep="pytest tests/structural/",
                       invariant_id=None)]
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def foo(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert not passed
        assert any("primary_invariant_id" in e for e in errors)

    def test_valid_invariant_ids_constant(self):
        assert VALID_INVARIANT_IDS == {
            "INV_BOUND_HOST_TERMINATION",
            "INV_TERMINAL_SCHEMA_LOCK",
            "INV_CROSS_SUBSTRATE_PARITY",
            "INV_STRUCTURAL_FORWARD_MOTION",
            "INV_TYPED_FAIL_CLOSED_OUTCOMES",
        }


# =============================================================================
# Constraint 11: Progress proof (STRUCTURAL + ENABLER)
# =============================================================================

class TestProgressProof:
    """STRUCTURAL and ENABLER must declare progress_proof_before/after."""

    def test_missing_progress_proof_before_fails(self):
        notes = [_note("L4_ENABLER", pp_before=None)]
        files = ["TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert not passed
        assert any("progress_proof_before" in e for e in errors)

    def test_missing_progress_proof_after_fails(self):
        notes = [_note("L4_ENABLER", pp_after=None)]
        files = ["TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert not passed
        assert any("progress_proof_after" in e for e in errors)

    def test_identical_progress_proof_fails(self):
        notes = [_note("L4_ENABLER", pp_before="same", pp_after="same")]
        files = ["TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert not passed
        assert any("anti-theater" in e for e in errors)

    def test_valid_progress_proof_passes(self):
        notes = [_note("L4_ENABLER", pp_before="no invariant check",
                       pp_after="invariant check enforced")]
        files = ["TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert passed, f"Valid progress proof should pass: {errors}"

    def test_progress_proof_not_required_for_maintenance(self):
        notes = [
            _note("MAINTENANCE", no_op_proof="docs", defer_reason="d",
                  evidence_command=None, evidence_delta=None,
                  pp_before=None, pp_after=None),
            _note("L4_STRUCTURAL"),  # Not consecutive
        ]
        files = ["TASKS.md"]
        passed, errors = enforce("MAINTENANCE", files, notes=notes)
        assert passed, f"MAINTENANCE should not require progress proof: {errors}"

    def test_progress_proof_required_for_structural(self):
        notes = [_note("L4_STRUCTURAL", hd_before="old", hd_after="new",
                       sa_ref="ref", sweep="pytest tests/structural/",
                       pp_before=None, pp_after=None)]
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def foo(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert not passed
        assert any("progress_proof_before" in e for e in errors)


# =============================================================================
# Constraint 12: Non-structural adjacency cap
# =============================================================================

class TestNonStructuralAdjacency:
    """Last 2 class-marked waves cannot both be non-STRUCTURAL."""

    def test_two_enablers_fails(self):
        notes = [
            _note("L4_ENABLER", wave_id="w2"),
            _note("L4_ENABLER", wave_id="w1"),
        ]
        passed, errors = check_non_structural_adjacency(notes)
        assert not passed
        assert any("Non-structural adjacency" in e for e in errors)

    def test_enabler_then_maintenance_fails(self):
        notes = [
            _note("MAINTENANCE", no_op_proof="x", defer_reason="d", wave_id="w2"),
            _note("L4_ENABLER", wave_id="w1"),
        ]
        passed, errors = check_non_structural_adjacency(notes)
        assert not passed
        assert any("Non-structural adjacency" in e for e in errors)

    def test_structural_then_enabler_passes(self):
        notes = [
            _note("L4_ENABLER", wave_id="w2"),
            _note("L4_STRUCTURAL", wave_id="w1"),
        ]
        passed, errors = check_non_structural_adjacency(notes)
        assert passed, f"STRUCTURAL then ENABLER should pass: {errors}"

    def test_enabler_then_structural_passes(self):
        notes = [
            _note("L4_STRUCTURAL", wave_id="w2"),
            _note("L4_ENABLER", wave_id="w1"),
        ]
        passed, errors = check_non_structural_adjacency(notes)
        assert passed, f"ENABLER then STRUCTURAL should pass: {errors}"

    def test_founder_override_bypasses_adjacency(self):
        notes = [
            _note("L4_ENABLER", wave_id="w2",
                  founder_override="2026-02-22-wave15-bootstrap"),
            _note("L4_ENABLER", wave_id="w1"),
        ]
        passed, errors = check_non_structural_adjacency(notes)
        assert passed, f"Founder override should bypass adjacency: {errors}"

    def test_bootstrap_grace_with_one_note(self):
        notes = [_note("L4_ENABLER")]
        passed, errors = check_non_structural_adjacency(notes)
        assert passed, f"Single note = bootstrap grace: {errors}"


# =============================================================================
# Constraint 13: Indicator artifact (all classes)
# =============================================================================

class TestIndicatorArtifact:
    """Every class-marked wave must declare indicator_artifact_ref and indicator_collection_command."""

    def test_missing_indicator_ref_fails(self):
        notes = [_note("L4_ENABLER", indicator_ref=None)]
        files = ["TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert not passed
        assert any("indicator_artifact_ref" in e for e in errors)

    def test_missing_indicator_cmd_fails(self):
        notes = [_note("L4_ENABLER", indicator_cmd=None)]
        files = ["TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert not passed
        assert any("indicator_collection_command" in e for e in errors)

    def test_wrong_collector_path_fails(self):
        notes = [_note("L4_ENABLER", indicator_cmd="python3 wrong/path.py --wave-id x")]
        files = ["TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert not passed
        assert any("canonical collector" in e for e in errors)

    def test_correct_indicator_fields_pass(self):
        notes = [_note("L4_ENABLER")]
        files = ["TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert passed, f"Valid indicator fields should pass: {errors}"

    def test_indicator_required_for_structural(self):
        notes = [_note("L4_STRUCTURAL", hd_before="old", hd_after="new",
                       sa_ref="ref", sweep="pytest tests/structural/",
                       indicator_ref=None)]
        files = ["rcx_pi/selfhost/eval_seed.py", "tests/l4_gates/test_foo.py"]
        diff = (
            "diff --git a/rcx_pi/selfhost/eval_seed.py b/rcx_pi/selfhost/eval_seed.py\n"
            "+++ b/rcx_pi/selfhost/eval_seed.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def foo(): pass\n"
        )
        passed, errors = enforce("L4_STRUCTURAL", files, diff, notes)
        assert not passed
        assert any("indicator_artifact_ref" in e for e in errors)

    def test_indicator_required_for_maintenance(self):
        notes = [
            _note("MAINTENANCE", no_op_proof="docs", defer_reason="d",
                  evidence_command=None, evidence_delta=None,
                  indicator_ref=None),
            _note("L4_STRUCTURAL"),
        ]
        files = ["TASKS.md"]
        passed, errors = enforce("MAINTENANCE", files, notes=notes)
        assert not passed
        assert any("indicator_artifact_ref" in e for e in errors)

    def test_canonical_collector_path_constant(self):
        assert CANONICAL_COLLECTOR_PATH == "tools/metrics/collect_l4_wave_indicators.py"

    def test_indicator_required_keys_constant(self):
        assert set(INDICATOR_REQUIRED_KEYS.keys()) == {
            "repeat_run_speedup_ratio", "parity_diff_count",
            "net_host_semantic_delta", "step_growth_slope",
        }


# =============================================================================
# Constraint 14: Bootstrap endgame policy (all classes)
# =============================================================================

class TestBootstrapPolicy:
    """Every class-marked wave must declare bootstrap_endgame_policy."""

    def test_missing_bootstrap_policy_fails(self):
        notes = [_note("L4_ENABLER", bootstrap_policy=None)]
        files = ["TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert not passed
        assert any("bootstrap_endgame_policy" in e for e in errors)

    def test_wrong_bootstrap_policy_fails(self):
        notes = [_note("L4_ENABLER", bootstrap_policy="WRONG_POLICY")]
        files = ["TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert not passed
        assert any("Invalid bootstrap_endgame_policy" in e for e in errors)

    def test_correct_bootstrap_policy_passes(self):
        notes = [_note("L4_ENABLER")]
        files = ["TASKS.md"]
        passed, errors = enforce("L4_ENABLER", files, notes=notes)
        assert passed, f"Valid bootstrap policy should pass: {errors}"

    def test_canonical_policy_constant(self):
        assert CANONICAL_BOOTSTRAP_POLICY == "SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP"


# =============================================================================
# Constraint 15: Rolling window founder override
# =============================================================================

class TestRollingWindowFounderOverride:
    """Founder override on most recent note bypasses rolling window quota."""

    def test_founder_override_bypasses_rolling_window(self):
        notes = [
            _note("L4_ENABLER", wave_id="w3",
                  founder_override="2026-02-22-wave16-rolling-window-bootstrap"),
            _note("L4_ENABLER", wave_id="w2"),
            _note("L4_ENABLER", wave_id="w1"),
        ]
        passed, errors = check_rolling_window(notes)
        assert passed, f"Founder override should bypass rolling window: {errors}"

    def test_rolling_window_without_override_fails(self):
        notes = [
            _note("L4_ENABLER", wave_id="w3"),
            _note("L4_ENABLER", wave_id="w2"),
            _note("L4_ENABLER", wave_id="w1"),
        ]
        passed, errors = check_rolling_window(notes)
        assert not passed
        assert any("Rolling structural quota" in e for e in errors)


# =============================================================================
# Constraint 16: Indicator artifact JSON validation
# =============================================================================

class TestValidateIndicatorJson:
    """validate_indicator_artifact_json validates file content."""

    def test_valid_artifact(self, tmp_path):
        import json
        artifact = tmp_path / "indicators.json"
        artifact.write_text(json.dumps({
            "wave_id": "test",
            "repeat_run_speedup_ratio": 1.0,
            "parity_diff_count": 21,
            "net_host_semantic_delta": 0,
            "step_growth_slope": 0.0,
        }))
        passed, errors = validate_indicator_artifact_json(str(artifact))
        assert passed, f"Valid artifact should pass: {errors}"

    def test_missing_key_fails(self, tmp_path):
        import json
        artifact = tmp_path / "indicators.json"
        artifact.write_text(json.dumps({
            "wave_id": "test",
            "repeat_run_speedup_ratio": 1.0,
            "net_host_semantic_delta": 0,
            "step_growth_slope": 0.0,
        }))
        passed, errors = validate_indicator_artifact_json(str(artifact))
        assert not passed
        assert any("parity_diff_count" in e for e in errors)

    def test_wrong_type_fails(self, tmp_path):
        import json
        artifact = tmp_path / "indicators.json"
        artifact.write_text(json.dumps({
            "wave_id": "test",
            "repeat_run_speedup_ratio": "not_a_number",
            "parity_diff_count": 21,
            "net_host_semantic_delta": 0,
            "step_growth_slope": 0.0,
        }))
        passed, errors = validate_indicator_artifact_json(str(artifact))
        assert not passed
        assert any("repeat_run_speedup_ratio" in e for e in errors)

    def test_nonexistent_file_fails(self):
        passed, errors = validate_indicator_artifact_json("/nonexistent/path.json")
        assert not passed
        assert any("does not exist" in e for e in errors)

    def test_invalid_json_fails(self, tmp_path):
        artifact = tmp_path / "indicators.json"
        artifact.write_text("not valid json {{{")
        passed, errors = validate_indicator_artifact_json(str(artifact))
        assert not passed
        assert any("invalid json" in e.lower() for e in errors)

    def test_boolean_type_rejected(self, tmp_path):
        """Python bool is subclass of int — must be explicitly rejected."""
        import json
        artifact = tmp_path / "indicators.json"
        artifact.write_text(json.dumps({
            "wave_id": "test",
            "repeat_run_speedup_ratio": 1.0,
            "parity_diff_count": True,
            "net_host_semantic_delta": 0,
            "step_growth_slope": 0.0,
        }))
        passed, errors = validate_indicator_artifact_json(str(artifact))
        assert not passed
        assert any("parity_diff_count" in e for e in errors)
