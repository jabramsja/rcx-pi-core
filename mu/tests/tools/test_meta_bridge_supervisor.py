"""Tests for meta-bridge supervisor routing behavior.

Covers:
1. Failed validation in live mode still reaches Codex routing layer
2. Commit-capable decisions blocked when any validation gate failed
3. Codex can emit NEEDS_PHASE_A / NEEDS_PHASE_B on failed validation
4. Dry-run remains validation-only (no Codex routing)
5. Template includes validation-failure routing section when gates fail
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.repo_root import REPO_ROOT


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Load bridge_adapters first (dependency)
_adapters = _load_module(
    "bridge_adapters",
    REPO_ROOT / "mu" / "tools" / "agents" / "bridge_adapters.py",
)
meta = _load_module(
    "meta_bridge_supervisor",
    REPO_ROOT / "mu" / "tools" / "agents" / "meta_bridge_supervisor.py",
)


def _make_validation_results(passed_names, failed_names_errors):
    """Build ValidationResult lists for testing."""
    results = []
    for name in passed_names:
        results.append(meta.ValidationResult(name=name, passed=True, error=None))
    for name, error in failed_names_errors:
        results.append(meta.ValidationResult(name=name, passed=False, error=error))
    return results


class TestCommitBlockedOnFailedValidation:
    """Commit-capable decisions must be impossible when validations fail."""

    def test_commit_go_blocked_when_validation_failed(self):
        """If Codex returns COMMIT_GO but validations failed, supervisor overrides."""
        envelope = {
            "decision": "COMMIT_GO",
            "summary": "Looks good",
            "findings": [],
            "request_for_claude": "Proceed with commit",
        }
        passed = ["L4 contract", "host_semantics_ratchet"]
        failed = [{"name": "dirty_state", "error": "stale files"}]
        all_passed = False

        # Simulate the enforcement logic from run_meta_bridge
        decision = envelope.get("decision", meta.Decision.ERROR_INTERNAL.value)
        if not all_passed and decision in meta.COMMIT_CAPABLE_DECISIONS:
            decision = meta.Decision.ERROR_VALIDATION_FAILED.value

        assert decision == "ERROR_VALIDATION_FAILED"

    def test_commit_go_hold_push_blocked_when_validation_failed(self):
        """COMMIT_GO_HOLD_PUSH also blocked."""
        decision = "COMMIT_GO_HOLD_PUSH"
        all_passed = False
        if not all_passed and decision in meta.COMMIT_CAPABLE_DECISIONS:
            decision = meta.Decision.ERROR_VALIDATION_FAILED.value
        assert decision == "ERROR_VALIDATION_FAILED"

    def test_no_action_blocked_when_validation_failed(self):
        """NO_ACTION also blocked — nothing to do is wrong when validations fail."""
        decision = "NO_ACTION"
        all_passed = False
        if not all_passed and decision in meta.COMMIT_CAPABLE_DECISIONS:
            decision = meta.Decision.ERROR_VALIDATION_FAILED.value
        assert decision == "ERROR_VALIDATION_FAILED"

    def test_commit_go_allowed_when_all_passed(self):
        """COMMIT_GO passes through when all validations pass."""
        decision = "COMMIT_GO"
        all_passed = True
        if not all_passed and decision in meta.COMMIT_CAPABLE_DECISIONS:
            decision = meta.Decision.ERROR_VALIDATION_FAILED.value
        assert decision == "COMMIT_GO"


class TestRoutingOnFailedValidation:
    """Codex can emit routing decisions (Phase A/B, founder stop) on failed validation."""

    def test_needs_phase_a_allowed_on_failed_validation(self):
        """NEEDS_PHASE_A passes through even when validations failed."""
        decision = "NEEDS_PHASE_A"
        all_passed = False
        if not all_passed and decision in meta.COMMIT_CAPABLE_DECISIONS:
            decision = meta.Decision.ERROR_VALIDATION_FAILED.value
        assert decision == "NEEDS_PHASE_A"

    def test_needs_phase_b_allowed_on_failed_validation(self):
        """NEEDS_PHASE_B passes through even when validations failed."""
        decision = "NEEDS_PHASE_B"
        all_passed = False
        if not all_passed and decision in meta.COMMIT_CAPABLE_DECISIONS:
            decision = meta.Decision.ERROR_VALIDATION_FAILED.value
        assert decision == "NEEDS_PHASE_B"

    def test_stop_for_founder_allowed_on_failed_validation(self):
        """STOP_FOR_FOUNDER passes through even when validations failed."""
        decision = "STOP_FOR_FOUNDER"
        all_passed = False
        if not all_passed and decision in meta.COMMIT_CAPABLE_DECISIONS:
            decision = meta.Decision.ERROR_VALIDATION_FAILED.value
        assert decision == "STOP_FOR_FOUNDER"

    def test_error_validation_failed_allowed_on_failed_validation(self):
        """ERROR_VALIDATION_FAILED passes through."""
        decision = "ERROR_VALIDATION_FAILED"
        all_passed = False
        if not all_passed and decision in meta.COMMIT_CAPABLE_DECISIONS:
            decision = meta.Decision.ERROR_VALIDATION_FAILED.value
        assert decision == "ERROR_VALIDATION_FAILED"


class TestCommitCapableDecisionSet:
    """COMMIT_CAPABLE_DECISIONS must be exactly the commit-authorizing tokens."""

    def test_commit_capable_is_exactly_three(self):
        assert meta.COMMIT_CAPABLE_DECISIONS == {"COMMIT_GO", "COMMIT_GO_HOLD_PUSH", "NO_ACTION"}

    def test_routing_decisions_not_commit_capable(self):
        routing = {"NEEDS_PHASE_A", "NEEDS_PHASE_B", "STOP_FOR_FOUNDER",
                    "STOP_FOR_TRIAGE_DISCUSSION", "ERROR_VALIDATION_FAILED"}
        assert routing.isdisjoint(meta.COMMIT_CAPABLE_DECISIONS)


class TestTemplateValidationFailureRouting:
    """Template must inject routing instructions when validations fail."""

    def test_routing_section_present_when_failed(self):
        """build_meta_reviewer_prompt includes routing section on failures."""
        package = {
            "task_id": "TEST-1",
            "wave_name": "test-wave",
            "lane": "test-lane",
        }
        results = _make_validation_results(
            passed_names=["L4 contract"],
            failed_names_errors=[("dirty_state", "stale files")],
        )
        prompt = meta.build_meta_reviewer_prompt(package, results, REPO_ROOT)
        assert "VALIDATION FAILURES DETECTED" in prompt
        assert "ROUTING MODE" in prompt
        assert "COMMIT_GO and COMMIT_GO_HOLD_PUSH are BLOCKED" in prompt
        assert "NEEDS_PHASE_A" in prompt
        assert "NEEDS_PHASE_B" in prompt
        assert "STOP_FOR_FOUNDER" in prompt

    def test_routing_section_absent_when_all_pass(self):
        """build_meta_reviewer_prompt omits routing section when all pass."""
        package = {
            "task_id": "TEST-1",
            "wave_name": "test-wave",
            "lane": "test-lane",
        }
        results = _make_validation_results(
            passed_names=["L4 contract", "dirty_state"],
            failed_names_errors=[],
        )
        prompt = meta.build_meta_reviewer_prompt(package, results, REPO_ROOT)
        assert "VALIDATION FAILURES DETECTED" not in prompt


class TestDryRunBehavior:
    """Dry-run must be validation-only and say so explicitly."""

    def test_dry_run_success_says_not_exercised(self):
        """Dry-run success response clarifies Codex routing was not exercised."""
        resp = meta.MetaBridgeResponse(
            status="success",
            decision=meta.Decision.NO_ACTION.value,
            summary="Dry run: all validations passed (Codex routing not exercised)",
            validations_passed=["a", "b"],
            validations_failed=[],
            request_for_claude="Run without --dry-run for full Codex meta-review and routing decision",
        )
        assert "not exercised" in resp.summary
        assert "--dry-run" in resp.request_for_claude

    def test_dry_run_failure_says_not_exercised(self):
        """Dry-run failure response clarifies Codex routing was not exercised."""
        resp = meta.MetaBridgeResponse(
            status="partial",
            decision=meta.Decision.ERROR_VALIDATION_FAILED.value,
            summary="Dry run: 1 of 2 validations passed (Codex routing not exercised)",
            validations_passed=["a"],
            validations_failed=[{"name": "b", "error": "fail"}],
            request_for_claude="Fix validation failures, then run without --dry-run for Codex routing decision",
        )
        assert "not exercised" in resp.summary
        assert "--dry-run" in resp.request_for_claude


class TestParseMetaEnvelope:
    """parse_meta_envelope validates decision is in template-authorized set."""

    def test_valid_routing_decision(self):
        output = 'BEGIN_META_ENVELOPE\n{"decision": "NEEDS_PHASE_A", "summary": "Plan is wrong"}\nEND_META_ENVELOPE'
        envelope = meta.parse_meta_envelope(output)
        assert envelope["decision"] == "NEEDS_PHASE_A"

    def test_invalid_decision_rejected(self):
        output = 'BEGIN_META_ENVELOPE\n{"decision": "YOLO", "summary": "bad"}\nEND_META_ENVELOPE'
        with pytest.raises(meta.MetaBridgeError, match="Invalid decision token"):
            meta.parse_meta_envelope(output)

    def test_commit_go_is_valid_template_decision(self):
        output = 'BEGIN_META_ENVELOPE\n{"decision": "COMMIT_GO", "summary": "ok"}\nEND_META_ENVELOPE'
        envelope = meta.parse_meta_envelope(output)
        assert envelope["decision"] == "COMMIT_GO"


# ---------------------------------------------------------------------------
# Integration tests: call run_meta_bridge() with mocked collaborators
# ---------------------------------------------------------------------------

def _make_valid_package():
    """Return a dict with all 11 required fields matching schema expectations."""
    return {
        "task_id": "[META-BRIDGE-S1]",
        "wave_name": "test-routing-wave",
        "lane": "hooks/agents/bridge control-surface",
        "changed_files": ["TASKS.md"],
        "scope_items": ["routing fix"],
        "fixes_implemented": ["validation routing"],
        "deferred_items": [],
        "bridge_status": {"state": "converged"},
        "evidence_handles": {"tests": "passed"},
        "blocker_report_paths": [],
        "current_judgment": "COMMIT_GO",
    }


@pytest.fixture
def pkg_in_repo(tmp_path):
    """Write a valid package JSON inside the repo (so git rev-parse works) and clean up.

    Uses tmp_path for the package file but writes it inside the repo so
    git rev-parse works. Also patches meta_bridge_paths to use tmp_path
    for lock/bus dirs to avoid parallel contention.
    """
    # Package must be inside the repo for git rev-parse
    import uuid
    unique_id = uuid.uuid4().hex[:8]
    test_dir = REPO_ROOT / ".agent_bus" / "meta" / f"_test_{unique_id}"
    test_dir.mkdir(parents=True, exist_ok=True)
    pkg_path = test_dir / "test_package.json"
    pkg_path.write_text(json.dumps(_make_valid_package()), encoding="utf-8")

    # Use tmp_path for bus/lock dirs to avoid parallel contention
    bus_dir = tmp_path / "meta_bus"
    bus_dir.mkdir(parents=True, exist_ok=True)
    isolated_paths = meta.MetaBridgePaths(
        repo_root=REPO_ROOT,
        bus_dir=bus_dir,
        db_path=bus_dir / "meta_bridge.db",
        lock_path=bus_dir / "meta_bridge.lock",
    )

    yield pkg_path, isolated_paths

    pkg_path.unlink(missing_ok=True)
    try:
        test_dir.rmdir()
    except OSError:
        pass


_FAKE_STATE = meta.RepoState(
    head_sha="aaa", staged_sha="bbb", unstaged_sha="ccc",
    untracked_sha="ddd", state_sha="stable",
)





class TestRunMetaBridgeLiveRouting:
    """Integration: run_meta_bridge() with mocked validation + Codex."""

    def test_failed_validation_still_calls_run_meta_review(self, pkg_in_repo):
        """Live mode + failed validations must reach run_meta_review, not short-circuit."""
        pkg_path, isolated_paths = pkg_in_repo
        failed_results = _make_validation_results(
            passed_names=["L4 contract"],
            failed_names_errors=[("dirty_state", "stale package")],
        )
        codex_envelope = {
            "decision": "NEEDS_PHASE_B",
            "summary": "Implementation needs rework",
            "findings": [],
            "request_for_claude": "Fix the stale changed_files and re-run",
        }

        with patch.object(meta, "compute_repo_state", return_value=_FAKE_STATE), \
             patch.object(meta, "run_validation_gates", return_value=(failed_results, False)), \
             patch.object(meta, "run_meta_review", return_value=codex_envelope) as mock_review, \
             patch.object(meta, "meta_bridge_paths", return_value=isolated_paths):
            resp = meta.run_meta_bridge(pkg_path, dry_run=False)

        # Prove run_meta_review was called (not short-circuited)
        mock_review.assert_called_once()
        assert resp.decision == "NEEDS_PHASE_B"
        assert resp.status == "partial"
        assert len(resp.validations_failed) == 1

    def test_failed_validation_commit_go_overridden(self, pkg_in_repo):
        """Live mode + failed validations + COMMIT_GO → overridden to ERROR_VALIDATION_FAILED."""
        pkg_path, isolated_paths = pkg_in_repo
        failed_results = _make_validation_results(
            passed_names=["L4 contract"],
            failed_names_errors=[("deferred_blockers", "unacknowledged blocker")],
        )
        codex_envelope = {
            "decision": "COMMIT_GO",
            "summary": "Looks fine to me",
            "findings": [],
            "request_for_claude": "Go ahead and commit",
        }

        with patch.object(meta, "compute_repo_state", return_value=_FAKE_STATE), \
             patch.object(meta, "run_validation_gates", return_value=(failed_results, False)), \
             patch.object(meta, "run_meta_review", return_value=codex_envelope) as mock_review, \
             patch.object(meta, "meta_bridge_paths", return_value=isolated_paths):
            resp = meta.run_meta_bridge(pkg_path, dry_run=False)

        mock_review.assert_called_once()
        assert resp.decision == "ERROR_VALIDATION_FAILED"
        assert "commit blocked" in resp.summary.lower() or "blocked" in resp.summary.lower()
        assert resp.status == "partial"

    def test_failed_validation_commit_go_hold_push_overridden(self, pkg_in_repo):
        """Live mode + failed validations + COMMIT_GO_HOLD_PUSH → also overridden."""
        pkg_path, isolated_paths = pkg_in_repo
        failed_results = _make_validation_results(
            passed_names=["L4 contract"],
            failed_names_errors=[("dirty_state", "stale")],
        )
        codex_envelope = {
            "decision": "COMMIT_GO_HOLD_PUSH",
            "summary": "Commit locally",
            "findings": [],
            "request_for_claude": "Commit but hold push",
        }

        with patch.object(meta, "compute_repo_state", return_value=_FAKE_STATE), \
             patch.object(meta, "run_validation_gates", return_value=(failed_results, False)), \
             patch.object(meta, "run_meta_review", return_value=codex_envelope), \
             patch.object(meta, "meta_bridge_paths", return_value=isolated_paths):
            resp = meta.run_meta_bridge(pkg_path, dry_run=False)

        assert resp.decision == "ERROR_VALIDATION_FAILED"

    def test_failed_validation_needs_phase_a_passes_through(self, pkg_in_repo):
        """Live mode + failed validations + NEEDS_PHASE_A → passes through."""
        pkg_path, isolated_paths = pkg_in_repo
        failed_results = _make_validation_results(
            passed_names=["L4 contract"],
            failed_names_errors=[("dirty_state", "stale")],
        )
        codex_envelope = {
            "decision": "NEEDS_PHASE_A",
            "summary": "Plan is fundamentally wrong",
            "findings": [{"severity": "high", "title": "bad plan", "detail": "redesign"}],
            "request_for_claude": "Re-enter Phase A with corrected scope",
        }

        with patch.object(meta, "compute_repo_state", return_value=_FAKE_STATE), \
             patch.object(meta, "run_validation_gates", return_value=(failed_results, False)), \
             patch.object(meta, "run_meta_review", return_value=codex_envelope), \
             patch.object(meta, "meta_bridge_paths", return_value=isolated_paths):
            resp = meta.run_meta_bridge(pkg_path, dry_run=False)

        assert resp.decision == "NEEDS_PHASE_A"
        assert resp.request_for_claude == "Re-enter Phase A with corrected scope"

    def test_failed_validation_no_action_overridden(self, pkg_in_repo):
        """Live mode + failed validations + NO_ACTION → overridden to ERROR_VALIDATION_FAILED."""
        pkg_path, isolated_paths = pkg_in_repo
        failed_results = _make_validation_results(
            passed_names=["L4 contract"],
            failed_names_errors=[("dirty_state", "stale")],
        )
        codex_envelope = {
            "decision": "NO_ACTION",
            "summary": "Nothing to do",
            "findings": [],
            "request_for_claude": "No changes needed",
        }

        with patch.object(meta, "compute_repo_state", return_value=_FAKE_STATE), \
             patch.object(meta, "run_validation_gates", return_value=(failed_results, False)), \
             patch.object(meta, "run_meta_review", return_value=codex_envelope), \
             patch.object(meta, "meta_bridge_paths", return_value=isolated_paths):
            resp = meta.run_meta_bridge(pkg_path, dry_run=False)

        assert resp.decision == "ERROR_VALIDATION_FAILED"

    def test_all_passed_commit_go_succeeds(self, pkg_in_repo):
        """Live mode + all validations pass + COMMIT_GO → success."""
        pkg_path, isolated_paths = pkg_in_repo
        passed_results = _make_validation_results(
            passed_names=["L4 contract", "dirty_state", "deferred_blockers"],
            failed_names_errors=[],
        )
        codex_envelope = {
            "decision": "COMMIT_GO",
            "summary": "All clear",
            "findings": [],
            "request_for_claude": "Proceed with commit protocol",
        }

        with patch.object(meta, "compute_repo_state", return_value=_FAKE_STATE), \
             patch.object(meta, "run_validation_gates", return_value=(passed_results, True)), \
             patch.object(meta, "run_meta_review", return_value=codex_envelope), \
             patch.object(meta, "meta_bridge_paths", return_value=isolated_paths):
            resp = meta.run_meta_bridge(pkg_path, dry_run=False)

        assert resp.decision == "COMMIT_GO"
        assert resp.status == "success"

    def test_dry_run_does_not_call_run_meta_review(self, pkg_in_repo):
        """Dry-run must NOT call run_meta_review regardless of validation outcome."""
        pkg_path, isolated_paths = pkg_in_repo
        passed_results = _make_validation_results(
            passed_names=["L4 contract", "dirty_state"],
            failed_names_errors=[],
        )

        with patch.object(meta, "compute_repo_state", return_value=_FAKE_STATE), \
             patch.object(meta, "run_validation_gates", return_value=(passed_results, True)), \
             patch.object(meta, "run_meta_review") as mock_review, \
             patch.object(meta, "meta_bridge_paths", return_value=isolated_paths):
            resp = meta.run_meta_bridge(pkg_path, dry_run=True)

        mock_review.assert_not_called()
        assert resp.decision == "NO_ACTION"
        assert "not exercised" in resp.summary

    def test_dry_run_failed_does_not_call_run_meta_review(self, pkg_in_repo):
        """Dry-run with failed validations must NOT call run_meta_review."""
        pkg_path, isolated_paths = pkg_in_repo
        failed_results = _make_validation_results(
            passed_names=["L4 contract"],
            failed_names_errors=[("dirty_state", "stale")],
        )

        with patch.object(meta, "compute_repo_state", return_value=_FAKE_STATE), \
             patch.object(meta, "run_validation_gates", return_value=(failed_results, False)), \
             patch.object(meta, "run_meta_review") as mock_review, \
             patch.object(meta, "meta_bridge_paths", return_value=isolated_paths):
            resp = meta.run_meta_bridge(pkg_path, dry_run=True)

        mock_review.assert_not_called()
        assert resp.decision == "ERROR_VALIDATION_FAILED"
        assert "not exercised" in resp.summary
