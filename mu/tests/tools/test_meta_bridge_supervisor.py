"""Tests for meta-bridge supervisor routing behavior.

Covers:
1. Failed validation in live mode still reaches Codex routing layer
2. Commit-capable decisions blocked when any validation gate failed
3. Codex can emit NEEDS_PHASE_A / NEEDS_PHASE_B on failed validation
4. Dry-run remains validation-only (no Codex routing)
5. Template includes validation-failure routing section when gates fail
"""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mu.tests.tools.module_loader import load_module
from tests.repo_root import REPO_ROOT


# Load bridge_adapters first (dependency)
_adapters = load_module(
    "bridge_adapters",
    REPO_ROOT / "mu" / "tools" / "agents" / "bridge_adapters.py",
)
meta = load_module(
    "meta_bridge_supervisor",
    REPO_ROOT / "mu" / "tools" / "agents" / "meta_bridge_supervisor.py",
)
commit_mod = load_module(
    "commit_executor_for_meta_bridge_tests",
    REPO_ROOT / "mu" / "tools" / "executors" / "commit_executor.py",
)


def _make_validation_results(passed_names, failed_names_errors):
    """Build ValidationResult lists for testing."""
    results = []
    for name in passed_names:
        results.append(meta.ValidationResult(name=name, passed=True, error=None))
    for name, error in failed_names_errors:
        results.append(meta.ValidationResult(name=name, passed=False, error=error))
    return results


class TestPreCommitSupervisorLifecyclePager:
    def test_pre_commit_supervisor_lifecycle_event_uses_package_identity(self, tmp_path):
        package_path = tmp_path / "pre_commit_package.json"
        package_path.write_text(
            json.dumps(
                {
                    "task_id": "[PIPELINE-AGENT-PAGER]",
                    "wave_name": "pager-lifecycle-event-coverage-2026-04-23",
                }
            ),
            encoding="utf-8",
        )
        response = meta.MetaBridgeResponse(
            status="success",
            decision=meta.Decision.COMMIT_GO.value,
            summary="ready",
        )
        calls = []

        def fake_emit(repo_root, **kwargs):
            calls.append(kwargs)
            return {"enabled": True, "event_id": "pre-commit", "attempted": []}

        with patch.object(meta, "emit_pipeline_agent_event", side_effect=fake_emit):
            meta._emit_pre_commit_supervisor_lifecycle_event(  # ANTICHEAT_OK: testing lifecycle helper
                package_path,
                event_type="pre_commit_supervisor_completed",
                state="success",
                response=response,
            )

        assert len(calls) == 1
        call = calls[0]
        assert call["event_type"] == "pre_commit_supervisor_completed"
        assert call["wave_id"] == "pager-lifecycle-event-coverage-2026-04-23"
        assert call["task_id"] == "[PIPELINE-AGENT-PAGER]"
        assert call["phase"] == "pre_commit_supervisor"
        assert call["state"] == "success"
        assert "pre-commit-supervisor:" in call["transition_key"]
        assert call["artifact_paths"]["package"].endswith("pre_commit_package.json")

    def test_main_emits_completed_error_after_receipt_write_failure(self, tmp_path):
        package_path = tmp_path / "pre_commit_package.json"
        package_path.write_text(
            json.dumps(
                {
                    "task_id": "[PIPELINE-AGENT-PAGER]",
                    "wave_name": "pager-lifecycle-event-coverage-2026-04-23",
                }
            ),
            encoding="utf-8",
        )
        response = meta.MetaBridgeResponse(
            status="success",
            decision=meta.Decision.COMMIT_GO.value,
            summary="ready",
        )
        lifecycle_calls = []

        def fake_lifecycle(*args, **kwargs):
            lifecycle_calls.append(kwargs)

        with patch.object(sys, "argv", ["meta_bridge_supervisor.py", "--package", str(package_path), "--json"]), \
             patch.object(meta, "run_meta_bridge", return_value=response), \
             patch.object(meta, "write_pre_commit_receipt", side_effect=RuntimeError("receipt disk full")), \
             patch.object(meta, "_safe_emit_pre_commit_supervisor_lifecycle_event", side_effect=fake_lifecycle):
            result = meta.main()

        assert result == 1
        completed = [
            call for call in lifecycle_calls
            if call["event_type"] == "pre_commit_supervisor_completed"
        ]
        assert len(completed) == 1
        assert completed[0]["state"] == "error"
        assert completed[0]["response"].error_code == "RECEIPT_WRITE_FAILED"
        assert not any(call.get("state") == "success" for call in completed)

    def test_main_suppresses_lifecycle_events_in_agent_review_mode(self, tmp_path):
        package_path = tmp_path / "pre_commit_package.json"
        package_path.write_text("{}", encoding="utf-8")
        lifecycle_calls = []

        def fake_lifecycle(*args, **kwargs):
            lifecycle_calls.append(kwargs)

        with patch.object(sys, "argv", ["meta_bridge_supervisor.py", "--package", str(package_path), "--json"]), \
             patch.dict(meta.os.environ, {"RCX_AGENT_REVIEW_MODE": "run_review"}, clear=False), \
             patch.object(meta, "_safe_emit_pre_commit_supervisor_lifecycle_event", side_effect=fake_lifecycle):
            result = meta.main()

        assert result == 1
        assert lifecycle_calls == []

    def test_receipt_write_failure_does_not_leave_canonical_commit_go(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        package_path = repo / "pre_commit_package.json"
        package_path.write_text("{}", encoding="utf-8")
        receipt_dir = repo / ".agent_bus" / "meta"
        receipt_dir.mkdir(parents=True)
        (receipt_dir / "pre_commit_receipts").write_text("not a directory", encoding="utf-8")
        response = meta.MetaBridgeResponse(
            status="success",
            decision=meta.Decision.COMMIT_GO.value,
            summary="ready",
        )

        with patch.object(meta, "compute_staged_sha", return_value="staged-sha"), \
             pytest.raises(FileExistsError):
            meta.write_pre_commit_receipt(response, package_path, repo_root=repo)

        assert not (receipt_dir / meta.PRE_COMMIT_RECEIPT_NAME).exists()


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

    def test_control_surface_obligations_activate_for_dot_segment_path(self):
        """Dot-segment control-surface paths must still trigger review obligations."""
        package = {
            "task_id": "TEST-1",
            "wave_name": "test-wave",
            "lane": "test-lane",
            "changed_files": ["mu/tools/executors/./phase_b_executor.py"],
        }
        results = _make_validation_results(
            passed_names=["L4 contract", "dirty_state"],
            failed_names_errors=[],
        )
        prompt = meta.build_meta_reviewer_prompt(package, results, REPO_ROOT)
        assert "CONTROL-SURFACE REVIEW MODE" in prompt
        assert "mu/tools/agents/meta_bridge_supervisor.py::write_pre_commit_receipt()" in prompt
        assert "mu/tools/agents/meta_bridge_client.py::run_meta_bridge_package()" in prompt
        assert "mu/tools/executors/phase_b_executor.py::prepare_commit_handoff()" in prompt
        assert "mu/tools/executors/commit_executor.py" in prompt
        assert "mu/tools/executors/meta_bridge_client.py" not in prompt
        assert "mu/tools/hooks/pre_commit_receipt.py" not in prompt

    def test_prompt_includes_bounded_review_contract(self):
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
        assert "Bounded Review Contract" in prompt
        assert "Use no more than 8 shell commands" in prompt
        assert "emit exactly one final `BEGIN_META_ENVELOPE ... END_META_ENVELOPE` block on stdout and stop" in prompt
        assert "Reading `FOUNDER_SESSION_BOOTSTRAP.md` remains REQUIRED" in prompt
        assert "Do not print bootstrap confirmations, contract recaps, or progress updates. Emit only the final envelope." in prompt
        assert "Do NOT invoke `founder_session_guard.sh`" in prompt
        assert "This invocation is the receipt-producing pre-commit supervisor" in prompt
        assert "Do not call `verify_pre_commit_receipt.py` or `verify_pre_commit_receipt()`" in prompt
        assert "missing or stale existing receipts are expected" in prompt
        assert "Do not inspect or cite other `.scratch/*package*.json` files as current package authority" in prompt
        assert "`bridge_status` and `blocker_report_paths` may legitimately be empty" in prompt
        assert "Do not use `set -e`/`pipefail` shell blocks" in prompt

    def test_prompt_includes_tasks_authorization_context(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "TASKS.md").write_text(
            "## NOW\n\n## NEXT\n\n"
            "- **[TASK-1]** **NEXT** (2026-04-04, founder-authorized).\n"
            "  Keep the authorization excerpt visible to the reviewer.\n"
            "  **Lane:** control-surface.\n",
            encoding="utf-8",
        )
        package = {
            "task_id": "[TASK-1]",
            "wave_name": "test-wave",
            "lane": "test-lane",
        }
        results = _make_validation_results(
            passed_names=["TASKS.md auth"],
            failed_names_errors=[],
        )
        prompt = meta.build_meta_reviewer_prompt(package, results, repo)
        assert "TASKS Authorization Context" in prompt
        assert "- **[TASK-1]** **NEXT**" in prompt
        assert "Keep the authorization excerpt visible to the reviewer." in prompt
        assert "If that gate is PASS, start from the authorization excerpt above" in prompt

    def test_reviewer_package_scope_false_positive_guard_requires_exact_staged_match(self, monkeypatch):
        package = {
            "changed_files": [
                "TASKS.md",
                "mu/tools/executors/phase_b_implementer.py",
            ],
        }
        envelope = {
            "decision": "NEEDS_PHASE_B",
            "summary": "package changed_files contradict current staged diff",
            "findings": [
                {
                    "severity": "critical",
                    "title": "Package changed_files contradict current staged diff",
                    "detail": "The package changed_files list claims a file that is not staged.",
                }
            ],
        }

        monkeypatch.setattr(
            meta,
            "git_output",
            lambda _repo, _args, text=True: (
                "TASKS.md\nmu/tools/executors/phase_b_implementer.py\n"
            ),
        )

        assert meta._reviewer_package_scope_finding_is_mechanically_refuted(  # ANTICHEAT_OK: regression for reviewer false-positive guard
            REPO_ROOT,
            package,
            envelope,
        )

        package["changed_files"].append("mu/tools/executors/phase_b_executor.py")
        assert not meta._reviewer_package_scope_finding_is_mechanically_refuted(  # ANTICHEAT_OK: regression for reviewer false-positive guard
            REPO_ROOT,
            package,
            envelope,
        )

        package["changed_files"].pop()
        envelope["findings"][0]["title"] = "Runtime behavior changed"
        envelope["findings"][0]["detail"] = "This is not a package scope drift claim."
        assert not meta._reviewer_package_scope_finding_is_mechanically_refuted(  # ANTICHEAT_OK: regression for reviewer false-positive guard
            REPO_ROOT,
            package,
            envelope,
        )

    def test_tasks_authorization_context_ignores_prose_mentions_before_task_bullet(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "TASKS.md").write_text(
            "## NOW\n\n"
            "- **[OTHER]** **NEXT** (2026-04-04, founder-authorized).\n"
            "  Follow-on structural queue unparked as [TASK-1].\n\n"
            "## NEXT\n\n"
            "- **[TASK-1]** **NEXT** (2026-04-04, founder-authorized).\n"
            "  Keep the authorization excerpt visible to the reviewer.\n",
            encoding="utf-8",
        )
        package = {
            "task_id": "[TASK-1]",
            "wave_name": "test-wave",
            "lane": "test-lane",
        }
        results = _make_validation_results(
            passed_names=["TASKS.md auth"],
            failed_names_errors=[],
        )

        prompt = meta.build_meta_reviewer_prompt(package, results, repo)

        assert "- **[TASK-1]** **NEXT**" in prompt
        assert "Keep the authorization excerpt visible to the reviewer." in prompt
        assert "Follow-on structural queue unparked as [TASK-1]." not in prompt


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

    def test_duplicate_identical_envelopes_are_accepted(self):
        output = (
            'BEGIN_META_ENVELOPE\n{"decision": "COMMIT_GO", "summary": "ok"}\nEND_META_ENVELOPE\n'
            'BEGIN_META_ENVELOPE\n{"decision": "COMMIT_GO", "summary": "ok"}\nEND_META_ENVELOPE'
        )
        envelope = meta.parse_meta_envelope(output)
        assert envelope["decision"] == "COMMIT_GO"

    def test_conflicting_multiple_envelopes_rejected(self):
        output = (
            'BEGIN_META_ENVELOPE\n{"decision": "COMMIT_GO", "summary": "ok"}\nEND_META_ENVELOPE\n'
            'BEGIN_META_ENVELOPE\n{"decision": "NEEDS_PHASE_B", "summary": "fix"}\nEND_META_ENVELOPE'
        )
        with pytest.raises(meta.MetaBridgeError, match="multiple differing envelope blocks"):
            meta.parse_meta_envelope(output)

    def test_prompt_template_echo_is_ignored_when_final_envelope_is_authoritative(self):
        output = (
            "Required output template follows.\n"
            "BEGIN_META_ENVELOPE\n"
            '{"decision": "COMMIT_GO|COMMIT_GO_HOLD_PUSH|NO_ACTION|NEEDS_PHASE_A|NEEDS_PHASE_B|STOP_FOR_FOUNDER|STOP_FOR_TRIAGE_DISCUSSION|ERROR_VALIDATION_FAILED", "summary": "template"}\n'
            "END_META_ENVELOPE\n"
            "Reviewer notes...\n"
            "BEGIN_META_ENVELOPE\n"
            '{"decision": "COMMIT_GO", "summary": "ok"}\n'
            "END_META_ENVELOPE\n"
            "Questions? Concerns? Thoughts? -- Think hard\n"
        )
        envelope = meta.parse_meta_envelope(output)
        assert envelope["decision"] == "COMMIT_GO"

    def test_replayed_stderr_envelope_is_ignored_when_stdout_is_authoritative(self):
        output = (
            "BEGIN_META_ENVELOPE\n"
            '{"decision": "COMMIT_GO", "summary": "current"}\n'
            "END_META_ENVELOPE\n"
            "\n[stderr]\n"
            "historical replay:\n"
            "BEGIN_META_ENVELOPE\n"
            '{"decision": "NEEDS_PHASE_B", "summary": "old"}\n'
            "END_META_ENVELOPE\n"
        )
        envelope = meta.parse_meta_envelope(output)
        assert envelope["decision"] == "COMMIT_GO"
        assert envelope["summary"] == "current"

    def test_stderr_only_envelope_is_rejected(self):
        output = (
            "[stderr]\n"
            "BEGIN_META_ENVELOPE\n"
            '{"decision": "COMMIT_GO", "summary": "stderr only"}\n'
            "END_META_ENVELOPE\n"
        )
        with pytest.raises(meta.MetaBridgeError, match="missing BEGIN_META_ENVELOPE"):
            meta.parse_meta_envelope(output)

    def test_run_validation_command_timeout_returns_124(self):
        with patch.object(meta.subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd=["python3"], timeout=1)):
            exit_code, output = meta.run_validation_command(REPO_ROOT, ["python3", "-c", "print('x')"])
        assert exit_code == 124
        assert "timed out" in output

    def test_git_output_timeout_raises_metabridgeerror(self):
        with patch.object(meta.subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd=["git"], timeout=1)):
            with pytest.raises(meta.MetaBridgeError, match="timed out"):
                meta.git_output(REPO_ROOT, ["status"])

    def test_bounded_timeout_env_invalid_or_out_of_range_uses_default(self):
        with patch.dict(meta.os.environ, {"RCX_META_GIT_TIMEOUT_S": "not-int"}, clear=False):
            assert meta._read_bounded_timeout_env("RCX_META_GIT_TIMEOUT_S", 30, minimum=1, maximum=300) == 30  # ANTICHEAT_OK: testing bounded timeout env helper
        with patch.dict(meta.os.environ, {"RCX_META_GIT_TIMEOUT_S": "999999"}, clear=False):
            assert meta._read_bounded_timeout_env("RCX_META_GIT_TIMEOUT_S", 30, minimum=1, maximum=300) == 30  # ANTICHEAT_OK: testing bounded timeout env helper

    def test_run_meta_bridge_blocked_in_agent_review_mode(self, tmp_path):
        package = tmp_path / "package.json"
        package.write_text("{}")
        with patch.dict(meta.os.environ, {"RCX_AGENT_REVIEW_MODE": "run_review"}, clear=False):
            response = meta.run_meta_bridge(package)
        assert response.status == "error"
        assert response.error_code == "REVIEW_MODE_BLOCKED"
        assert "agent review mode" in response.error_detail


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


class TestPreCommitPackageSchema:
    """Schema validation for the 11-field pre-commit package."""

    def test_rejects_unexpected_extra_top_level_field(self):
        pkg = _make_valid_package()
        pkg["surprise"] = {"oops": True}
        valid, errors = meta.validate_package_schema(pkg)
        assert not valid
        assert any("Unexpected field" in e for e in errors)

    def test_rejects_non_string_scope_and_deferred_items(self):
        pkg = _make_valid_package()
        pkg["scope_items"] = ["routing fix", {"bad": True}]
        pkg["deferred_items"] = [123]
        valid, errors = meta.validate_package_schema(pkg)
        assert not valid
        assert "scope_items[1] must be a string, got dict" in errors
        assert "deferred_items[0] must be a string, got int" in errors

    def test_accepts_tracker_evidence_transport_fields(self):
        pkg = _make_valid_package()
        pkg["tracker_note_text"] = "evidence_command: `echo ok`. evidence_delta: ok."
        pkg["evidence_command"] = "echo ok"
        valid, errors = meta.validate_package_schema(pkg)
        assert valid, errors


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


def test_meta_bridge_lock_keeps_inode_stable_for_waiter_contention(tmp_path):
    lock_path = tmp_path / "meta_bridge.lock"
    waiter = None
    contender = None
    waiter_script = """
import fcntl
import os
import sys
import time

path = sys.argv[1]
fp = open(path, "w")
print(f"opened {os.fstat(fp.fileno()).st_ino}", flush=True)
fcntl.flock(fp, fcntl.LOCK_EX)
print(f"acquired {os.fstat(fp.fileno()).st_ino}", flush=True)
time.sleep(1.0)
"""
    try:
        with meta._MetaBridgeLock(lock_path):  # ANTICHEAT_OK: same-path contention proof
            waiter = subprocess.Popen(
                [sys.executable, "-c", waiter_script, str(lock_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert waiter.stdout is not None
            assert waiter.stdout.readline().strip().startswith("opened ")

        acquired = waiter.stdout.readline().strip()
        assert acquired.startswith("acquired ")
        waiter_inode = int(acquired.split()[1])

        contender = open(lock_path, "w")
        contender_inode = os.fstat(contender.fileno()).st_ino
        assert contender_inode == waiter_inode
        with pytest.raises(BlockingIOError):
            fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)

        out, err = waiter.communicate(timeout=5)
        assert waiter.returncode == 0, f"{out}\n{err}"
    finally:
        if contender is not None:
            contender.close()
        if waiter is not None and waiter.poll() is None:
            waiter.kill()
            waiter.communicate(timeout=5)


def test_meta_bridge_lock_persists_owner_metadata(tmp_path):
    lock_path = tmp_path / "meta_bridge.lock"

    with meta._MetaBridgeLock(lock_path):  # ANTICHEAT_OK: lock metadata coverage
        # While held: metadata is present
        assert lock_path.stat().st_size > 0
        metadata = json.loads(lock_path.read_text(encoding="utf-8"))

    # After release: file exists but is empty (metadata cleared to prevent stale PID)
    assert lock_path.exists()
    assert lock_path.stat().st_size == 0
    # Metadata was correct while held
    assert metadata["holder"] == "meta_bridge_supervisor"
    assert metadata["pid"] == os.getpid()
    assert metadata["lock_path"] == str(lock_path)


def test_meta_bridge_lock_error_clarifies_persistent_path(tmp_path, monkeypatch):
    # Bounded-wait fail-closed: a live holder that NEVER releases makes a second
    # __enter__ WAIT the bounded timeout and then raise (fail-closed preserved),
    # rather than failing immediately. Drive a tiny timeout so the regression is
    # fast and deterministic.
    monkeypatch.setattr(meta, "META_LOCK_WAIT_TIMEOUT_S", 0.3)
    monkeypatch.setattr(meta, "META_LOCK_WAIT_BACKOFF_MS", 20)
    lock_path = tmp_path / "meta_bridge.lock"
    fp = open(lock_path, "w")
    try:
        fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        start = time.monotonic()
        with pytest.raises(meta.MetaBridgeError, match="persists by design") as excinfo:
            with meta._MetaBridgeLock(lock_path):  # ANTICHEAT_OK: lock error-path coverage
                pass
        elapsed = time.monotonic() - start
    finally:
        fcntl.flock(fp, fcntl.LOCK_UN)
        fp.close()

    # It WAITED (bounded) for the held flock before failing closed — it did not
    # raise immediately on contention.
    assert elapsed >= 0.2
    assert "Bounded-waited" in str(excinfo.value)
    assert "if stale" not in str(excinfo.value)


def test_meta_bridge_lock_waits_then_succeeds_when_holder_releases(tmp_path, monkeypatch):
    """A live holder makes a second __enter__ WAIT (bounded) and then SUCCEED.

    Regression for the parallel-pipeline collision: two waves reaching the bridge
    must serialize on the kernel flock instead of the second failing immediately.
    """
    # Generous timeout (never reached); small backoff so reacquire is snappy.
    monkeypatch.setattr(meta, "META_LOCK_WAIT_TIMEOUT_S", 10.0)
    monkeypatch.setattr(meta, "META_LOCK_WAIT_BACKOFF_MS", 20)
    lock_path = tmp_path / "meta_bridge.lock"

    holding = threading.Event()
    hold_seconds = 0.4

    def _hold_then_release():
        # Separate open file description in the same process: flock contends
        # across OFDs, so this faithfully blocks the _MetaBridgeLock acquire.
        holder_fp = open(lock_path, "w")
        fcntl.flock(holder_fp, fcntl.LOCK_EX)
        holding.set()
        time.sleep(hold_seconds)
        fcntl.flock(holder_fp, fcntl.LOCK_UN)
        holder_fp.close()

    holder = threading.Thread(target=_hold_then_release)
    holder.start()
    try:
        assert holding.wait(timeout=5.0), "holder thread never acquired the flock"
        start = time.monotonic()
        with meta._MetaBridgeLock(lock_path):  # ANTICHEAT_OK: bounded-wait serialize proof
            elapsed = time.monotonic() - start
            # It WAITED for the holder to release (did not fail immediately) and
            # then acquired successfully — parallel waves serialize.
            assert elapsed >= 0.2
            assert lock_path.stat().st_size > 0  # holder metadata re-written
    finally:
        holder.join(timeout=5.0)
    assert not holder.is_alive()


def test_meta_bridge_lock_acquires_immediately_despite_stale_dead_pid_metadata(
    tmp_path, monkeypatch
):
    """Acquisition depends on the FREE kernel flock, not on metadata PID liveness.

    A lockfile holding only stale (dead-PID) metadata but NO held flock is
    acquired on the first non-blocking attempt, and the lockfile is never
    unlinked/recreated (inode preserved). This locks in the Round-1 review fix:
    the metadata PID is never parsed to clear or bypass the lock.
    """
    # Make any wait expensive so "immediate" is a strong assertion: a single
    # backoff would cost 5s, but a free flock acquires on the first try (~0s).
    monkeypatch.setattr(meta, "META_LOCK_WAIT_TIMEOUT_S", 30.0)
    monkeypatch.setattr(meta, "META_LOCK_WAIT_BACKOFF_MS", 5000)
    lock_path = tmp_path / "meta_bridge.lock"

    # A definitely-dead PID: spawn a trivial subprocess and reap it.
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    dead_pid = proc.pid

    stale_metadata = {
        "holder": "meta_bridge_supervisor",
        "pid": dead_pid,
        "lock_path": str(lock_path),
        "acquired_at_utc": "2026-06-21T00:00:00+00:00",
    }
    lock_path.write_text(json.dumps(stale_metadata, sort_keys=True) + "\n", encoding="utf-8")
    inode_before = lock_path.stat().st_ino

    start = time.monotonic()
    with meta._MetaBridgeLock(lock_path):  # ANTICHEAT_OK: free-flock acquire proof
        elapsed = time.monotonic() - start
        # Acquired on the FIRST non-blocking attempt (no backoff sleep) — proves
        # acquisition ignores the stale metadata PID entirely.
        assert elapsed < 1.0
        inode_held = lock_path.stat().st_ino
        # The new holder's own metadata overwrote the stale entry.
        held_metadata = json.loads(lock_path.read_text(encoding="utf-8"))
        assert held_metadata["pid"] == os.getpid()
    inode_after = lock_path.stat().st_ino

    # The lockfile inode never changed — never unlinked/recreated (flock mutual
    # exclusion is per-inode, so an inode swap would break single-supervisor).
    assert inode_before == inode_held == inode_after
    assert lock_path.exists()



class TestRunMetaBridgeLiveRouting:
    """Integration: run_meta_bridge() with mocked validation + Codex."""

    @pytest.fixture(autouse=True)
    def _allow_live_run(self):
        with patch.object(meta, "ensure_not_agent_review_mode", return_value=None):
            yield

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


def test_run_meta_review_recovers_authoritative_envelope_from_raw_output(pkg_in_repo):
    pkg_path, isolated_paths = pkg_in_repo
    validation_results = _make_validation_results(["dirty_state"], [])
    package = json.loads(pkg_path.read_text(encoding="utf-8"))
    recovered = (
        "BEGIN_META_ENVELOPE\n"
        '{"decision": "COMMIT_GO", "summary": "Recovered", "findings": [], "request_for_claude": "Proceed"}\n'
        "END_META_ENVELOPE\n"
    )

    def _failing_adapter(*args, **kwargs):
        raw_output_path = kwargs["raw_output_path"]
        raw_output_path.write_text(recovered, encoding="utf-8")
        raise _adapters.BridgeAdapterError("Adapter 'codex' exited 1")

    with patch.object(meta, "load_bridge_config", return_value={"agents": {}}), \
         patch.object(meta, "get_adapter", return_value=MagicMock()), \
         patch.object(meta, "run_adapter", side_effect=_failing_adapter):
        envelope = meta.run_meta_review(isolated_paths, package, validation_results)

    assert envelope["decision"] == "COMMIT_GO"
    assert envelope["summary"] == "Recovered"


def test_run_meta_review_recovers_from_unparseable_success_output(pkg_in_repo):
    pkg_path, isolated_paths = pkg_in_repo
    validation_results = _make_validation_results(["dirty_state"], [])
    package = json.loads(pkg_path.read_text(encoding="utf-8"))
    recovered = (
        "BEGIN_META_ENVELOPE\n"
        '{"decision": "COMMIT_GO", "summary": "Recovered from raw", "findings": [], "request_for_claude": "Proceed"}\n'
        "END_META_ENVELOPE\n"
    )

    def _successful_adapter(*args, **kwargs):
        raw_output_path = kwargs["raw_output_path"]
        raw_output_path.write_text(recovered, encoding="utf-8")
        return "thread.started without final envelope"

    with patch.object(meta, "load_bridge_config", return_value={"agents": {}}), \
         patch.object(meta, "get_adapter", return_value=MagicMock()), \
         patch.object(meta, "run_adapter", side_effect=_successful_adapter):
        envelope = meta.run_meta_review(isolated_paths, package, validation_results)

    assert envelope["decision"] == "COMMIT_GO"
    assert envelope["summary"] == "Recovered from raw"


def test_run_meta_review_recovers_from_codex_event_stream_output(pkg_in_repo):
    pkg_path, isolated_paths = pkg_in_repo
    validation_results = _make_validation_results(["dirty_state"], [])
    package = json.loads(pkg_path.read_text(encoding="utf-8"))
    codex_stream = "\n".join([
        json.dumps({"type": "thread.started", "thread_id": "t1"}),
        json.dumps({
            "type": "item.completed",
            "item": {
                "id": "item_13",
                "type": "agent_message",
                "text": (
                    "BEGIN_META_ENVELOPE\n"
                    '{"decision": "COMMIT_GO", "summary": "Recovered from codex stream", "findings": [], "request_for_claude": "Proceed"}\n'
                    "END_META_ENVELOPE"
                ),
            },
        }),
    ]) + "\n"

    def _successful_adapter(*args, **kwargs):
        raw_output_path = kwargs["raw_output_path"]
        raw_output_path.write_text(codex_stream, encoding="utf-8")
        return codex_stream

    with patch.object(meta, "load_bridge_config", return_value={"agents": {}}), \
         patch.object(meta, "get_adapter", return_value=MagicMock()), \
         patch.object(meta, "run_adapter", side_effect=_successful_adapter):
        envelope = meta.run_meta_review(isolated_paths, package, validation_results)

    assert envelope["decision"] == "COMMIT_GO"
    assert envelope["summary"] == "Recovered from codex stream"


def test_run_meta_review_rejects_stderr_only_recovery_envelope(pkg_in_repo):
    pkg_path, isolated_paths = pkg_in_repo
    validation_results = _make_validation_results(["dirty_state"], [])
    package = json.loads(pkg_path.read_text(encoding="utf-8"))
    stderr_only = (
        "[stderr]\n"
        "BEGIN_META_ENVELOPE\n"
        '{"decision": "COMMIT_GO", "summary": "stderr only", "findings": [], "request_for_claude": "Proceed"}\n'
        "END_META_ENVELOPE\n"
    )

    def _failing_adapter(*args, **kwargs):
        raw_output_path = kwargs["raw_output_path"]
        raw_output_path.write_text(stderr_only, encoding="utf-8")
        raise _adapters.BridgeAdapterError("Adapter 'codex' exited 1", output=stderr_only)

    with patch.object(meta, "load_bridge_config", return_value={"agents": {}}), \
         patch.object(meta, "get_adapter", return_value=MagicMock()), \
         patch.object(meta, "run_adapter", side_effect=_failing_adapter):
        with pytest.raises(meta.MetaBridgeError, match="recovery also failed"):
            meta.run_meta_review(isolated_paths, package, validation_results)


def test_run_meta_review_threads_timeout_and_watchdogs_into_adapter(pkg_in_repo):
    pkg_path, isolated_paths = pkg_in_repo
    validation_results = _make_validation_results(["dirty_state"], [])
    package = json.loads(pkg_path.read_text(encoding="utf-8"))
    envelope = (
        "BEGIN_META_ENVELOPE\n"
        '{"decision": "COMMIT_GO", "summary": "ok", "findings": [], "request_for_claude": "Proceed"}\n'
        "END_META_ENVELOPE\n"
    )

    with patch.object(meta, "load_bridge_config", return_value={"agents": {}}), \
         patch.object(meta, "get_adapter", return_value=MagicMock()), \
         patch.object(meta, "run_adapter", return_value=envelope) as mock_run:
        parsed = meta.run_meta_review(isolated_paths, package, validation_results, timeout_s=90)

    assert parsed["decision"] == "COMMIT_GO"
    kwargs = mock_run.call_args.kwargs
    assert kwargs["timeout_override_s"] == 90
    assert kwargs["stale_timeout_s"] == 90
    assert kwargs["stop_after_envelope"] is True
    assert "zero_output_timeout_s" not in kwargs or kwargs["zero_output_timeout_s"] is None


def test_run_meta_review_ignores_scoped_reviewer_env_for_other_repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    cfg_dir = repo_root / "mu" / "tools" / "executors"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "executor_config.json").write_text(
        json.dumps(
            {
                "role_agents": {"implementer": "codex", "reviewer": "codex"},
                "bridge_agent_defaults": {"codex": {}, "claude": {}},
            }
        ),
        encoding="utf-8",
    )
    bus_dir = tmp_path / "bus"
    bus_dir.mkdir()
    paths = meta.MetaBridgePaths(
        repo_root=repo_root,
        bus_dir=bus_dir,
        db_path=bus_dir / "meta_bridge.db",
        lock_path=bus_dir / "meta_bridge.lock",
    )
    monkeypatch.setenv("RCX_REVIEWER_AGENT_OVERRIDE", "claude")
    monkeypatch.setenv("RCX_ROLE_AGENT_OVERRIDE_REPO_ROOT", str(tmp_path / "other"))
    package = _make_valid_package()
    validation_results = _make_validation_results(["dirty_state"], [])
    envelope = (
        "BEGIN_META_ENVELOPE\n"
        '{"decision": "COMMIT_GO", "summary": "ok", "findings": [], "request_for_claude": "Proceed"}\n'
        "END_META_ENVELOPE\n"
    )
    selected: list[str] = []

    def fake_get_adapter(config, name):
        selected.append(name)
        return MagicMock(name=name)

    with patch.object(meta, "load_bridge_config_with_worktree_heal_at", return_value={"agents": {}}), \
         patch.object(meta, "get_adapter", side_effect=fake_get_adapter), \
         patch.object(meta, "run_adapter", return_value=envelope):
        parsed = meta.run_meta_review(paths, package, validation_results, timeout_s=90)

    assert parsed["decision"] == "COMMIT_GO"
    assert selected == ["codex"]


def test_run_meta_review_sanitizes_slash_task_ids_for_prompt_paths(pkg_in_repo):
    pkg_path, isolated_paths = pkg_in_repo
    validation_results = _make_validation_results(["dirty_state"], [])
    package = json.loads(pkg_path.read_text(encoding="utf-8"))
    package["task_id"] = "[PIPELINE-RECOVERY/pipeline-monitor-worktree-rebind-2026-04-03]"
    envelope = (
        "BEGIN_META_ENVELOPE\n"
        '{"decision": "COMMIT_GO", "summary": "ok", "findings": [], "request_for_claude": "Proceed"}\n'
        "END_META_ENVELOPE\n"
    )

    with patch.object(meta, "load_bridge_config", return_value={"agents": {}}), \
         patch.object(meta, "get_adapter", return_value=MagicMock()), \
         patch.object(meta, "run_adapter", return_value=envelope) as mock_run:
        parsed = meta.run_meta_review(isolated_paths, package, validation_results, timeout_s=90)

    assert parsed["decision"] == "COMMIT_GO"
    kwargs = mock_run.call_args.kwargs
    assert "/" not in kwargs["job_id"]
    assert "/" not in kwargs["turn_id"]
    assert kwargs["prompt_path"].exists()
    assert kwargs["raw_output_path"].parent.exists()


def test_load_bridge_config_with_worktree_heal_copies_from_main_repo(tmp_path):
    main_repo = tmp_path / "main"
    main_repo.mkdir()
    (main_repo / ".agent_bus").mkdir()
    (main_repo / ".agent_bus" / "bridge_config.json").write_text(
        '{"agents": {}}',
        encoding="utf-8",
    )

    worktree = tmp_path / "worktree"
    worktree.mkdir()
    gitdir = main_repo / ".git" / "worktrees" / "worktree"
    gitdir.mkdir(parents=True)
    (worktree / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")

    config = meta.load_bridge_config_with_worktree_heal(worktree)

    assert config == {"agents": {}}
    healed = worktree / ".agent_bus" / "bridge_config.json"
    assert healed.exists()
    assert healed.read_text(encoding="utf-8") == '{"agents": {}}'


def test_run_post_merge_review_recovers_authoritative_envelope_from_raw_output(tmp_path):
    bus_dir = tmp_path / "meta_bus"
    bus_dir.mkdir(parents=True, exist_ok=True)
    paths = meta.MetaBridgePaths(
        repo_root=REPO_ROOT,
        bus_dir=bus_dir,
        db_path=bus_dir / "meta_bridge.db",
        lock_path=bus_dir / "meta_bridge.lock",
    )
    package = {
        "task_id": "[POST-MERGE]",
        "wave_name": "wave",
        "lane": "hooks/agents/bridge control-surface",
        "merged_pr": 1,
        "merge_sha": "abc1234",
        "rollout_packet_path": "reports/control_plane/post_merge_supervisor_plan_2026-03-21.md",
        "deferred_items": [],
        "next_candidates": [],
        "tracker_state_summary": "stable",
        "blocker_report_paths": [],
    }
    validation_results = _make_validation_results(["gate1"], [])
    recovered = (
        "BEGIN_META_ENVELOPE\n"
        '{"decision": "CONTINUE_DIALECTIC", "summary": "Recovered post-merge", "findings": [], "request_for_claude": "Continue"}\n'
        "END_META_ENVELOPE\n"
    )

    def _failing_adapter(*args, **kwargs):
        raw_output_path = kwargs["raw_output_path"]
        raw_output_path.write_text(recovered, encoding="utf-8")
        raise _adapters.BridgeAdapterError("Adapter 'codex' exited 1")

    with patch.object(meta, "build_post_merge_prompt", return_value="prompt"), \
         patch.object(meta, "load_bridge_config", return_value={"agents": {}}), \
         patch.object(meta, "get_adapter", return_value=MagicMock()), \
         patch.object(meta, "run_adapter", side_effect=_failing_adapter):
        envelope = meta.run_post_merge_review(
            paths,
            package,
            validation_results,
            derived_files=["TASKS.md"],
            rollout_order="1. Continue",
        )

    assert envelope["decision"] == "CONTINUE_DIALECTIC"
    assert envelope["summary"] == "Recovered post-merge"


def test_run_post_merge_review_recovers_from_unparseable_success_output(tmp_path):
    bus_dir = tmp_path / "meta_bus"
    bus_dir.mkdir(parents=True, exist_ok=True)
    paths = meta.MetaBridgePaths(
        repo_root=REPO_ROOT,
        bus_dir=bus_dir,
        db_path=bus_dir / "meta_bridge.db",
        lock_path=bus_dir / "meta_bridge.lock",
    )
    package = {
        "task_id": "[POST-MERGE]",
        "wave_name": "wave",
        "lane": "hooks/agents/bridge control-surface",
        "merged_pr": 1,
        "merge_sha": "abc1234",
        "rollout_packet_path": "reports/control_plane/post_merge_supervisor_plan_2026-03-21.md",
        "deferred_items": [],
        "next_candidates": [],
        "tracker_state_summary": "stable",
        "blocker_report_paths": [],
    }
    validation_results = _make_validation_results(["gate1"], [])
    recovered = (
        "BEGIN_META_ENVELOPE\n"
        '{"decision": "CONTINUE_DIALECTIC", "summary": "Recovered post-merge from raw", "findings": [], "request_for_claude": "Continue"}\n'
        "END_META_ENVELOPE\n"
    )

    def _successful_adapter(*args, **kwargs):
        raw_output_path = kwargs["raw_output_path"]
        raw_output_path.write_text(recovered, encoding="utf-8")
        return "thread.started without final envelope"

    with patch.object(meta, "build_post_merge_prompt", return_value="prompt"), \
         patch.object(meta, "load_bridge_config", return_value={"agents": {}}), \
         patch.object(meta, "get_adapter", return_value=MagicMock()), \
         patch.object(meta, "run_adapter", side_effect=_successful_adapter):
        envelope = meta.run_post_merge_review(
            paths,
            package,
            validation_results,
            derived_files=["TASKS.md"],
            rollout_order="1. Continue",
        )

    assert envelope["decision"] == "CONTINUE_DIALECTIC"
    assert envelope["summary"] == "Recovered post-merge from raw"


def test_run_post_merge_review_rejects_stderr_only_recovery_envelope(tmp_path):
    bus_dir = tmp_path / "meta_bus"
    bus_dir.mkdir(parents=True, exist_ok=True)
    paths = meta.MetaBridgePaths(
        repo_root=REPO_ROOT,
        bus_dir=bus_dir,
        db_path=bus_dir / "meta_bridge.db",
        lock_path=bus_dir / "meta_bridge.lock",
    )
    package = {
        "task_id": "[POST-MERGE]",
        "wave_name": "wave",
        "lane": "hooks/agents/bridge control-surface",
        "merged_pr": 1,
        "merge_sha": "abc1234",
        "rollout_packet_path": "reports/control_plane/post_merge_supervisor_plan_2026-03-21.md",
        "deferred_items": [],
        "next_candidates": [],
        "tracker_state_summary": "stable",
        "blocker_report_paths": [],
    }
    validation_results = _make_validation_results(["gate1"], [])
    stderr_only = (
        "[stderr]\n"
        "BEGIN_META_ENVELOPE\n"
        '{"decision": "CONTINUE_DIALECTIC", "summary": "stderr only", "findings": [], "request_for_claude": "Continue"}\n'
        "END_META_ENVELOPE\n"
    )

    def _failing_adapter(*args, **kwargs):
        raw_output_path = kwargs["raw_output_path"]
        raw_output_path.write_text(stderr_only, encoding="utf-8")
        raise _adapters.BridgeAdapterError("Adapter 'codex' exited 1", output=stderr_only)

    with patch.object(meta, "build_post_merge_prompt", return_value="prompt"), \
         patch.object(meta, "load_bridge_config", return_value={"agents": {}}), \
         patch.object(meta, "get_adapter", return_value=MagicMock()), \
         patch.object(meta, "run_adapter", side_effect=_failing_adapter):
        with pytest.raises(meta.MetaBridgeError, match="recovery also failed"):
            meta.run_post_merge_review(
                paths,
                package,
                validation_results,
                derived_files=["TASKS.md"],
                rollout_order="1. Continue",
            )


def test_run_post_merge_review_threads_timeout_and_watchdogs_into_adapter(tmp_path):
    bus_dir = tmp_path / "meta_bus"
    bus_dir.mkdir(parents=True, exist_ok=True)
    paths = meta.MetaBridgePaths(
        repo_root=REPO_ROOT,
        bus_dir=bus_dir,
        db_path=bus_dir / "meta_bridge.db",
        lock_path=bus_dir / "meta_bridge.lock",
    )
    package = {
        "task_id": "[POST-MERGE]",
        "wave_name": "wave",
        "lane": "hooks/agents/bridge control-surface",
        "merged_pr": 1,
        "merge_sha": "abc1234",
        "rollout_packet_path": "reports/control_plane/post_merge_supervisor_plan_2026-03-21.md",
        "deferred_items": [],
        "next_candidates": [],
        "tracker_state_summary": "stable",
        "blocker_report_paths": [],
    }
    validation_results = _make_validation_results(["gate1"], [])
    envelope = (
        "BEGIN_META_ENVELOPE\n"
        '{"decision": "CONTINUE_DIALECTIC", "summary": "ok", "findings": [], "request_for_claude": "Continue"}\n'
        "END_META_ENVELOPE\n"
    )

    with patch.object(meta, "build_post_merge_prompt", return_value="prompt"), \
         patch.object(meta, "load_bridge_config", return_value={"agents": {}}), \
         patch.object(meta, "get_adapter", return_value=MagicMock()), \
         patch.object(meta, "run_adapter", return_value=envelope) as mock_run:
        parsed = meta.run_post_merge_review(
            paths,
            package,
            validation_results,
            derived_files=["TASKS.md"],
            rollout_order="1. Continue",
            timeout_s=75,
        )

    assert parsed["decision"] == "CONTINUE_DIALECTIC"
    kwargs = mock_run.call_args.kwargs
    assert kwargs["timeout_override_s"] == 75
    assert kwargs["stale_timeout_s"] == 75
    assert kwargs["stop_after_envelope"] is True
    assert "zero_output_timeout_s" not in kwargs or kwargs["zero_output_timeout_s"] is None


def test_run_post_merge_review_ignores_scoped_reviewer_env_for_other_repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    cfg_dir = repo_root / "mu" / "tools" / "executors"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "executor_config.json").write_text(
        json.dumps(
            {
                "role_agents": {"implementer": "codex", "reviewer": "codex"},
                "bridge_agent_defaults": {"codex": {}, "claude": {}},
            }
        ),
        encoding="utf-8",
    )
    bus_dir = tmp_path / "meta_bus"
    bus_dir.mkdir()
    paths = meta.MetaBridgePaths(
        repo_root=repo_root,
        bus_dir=bus_dir,
        db_path=bus_dir / "meta_bridge.db",
        lock_path=bus_dir / "meta_bridge.lock",
    )
    package = {
        "task_id": "[POST-MERGE]",
        "wave_name": "wave",
        "lane": "hooks/agents/bridge control-surface",
        "merged_pr": 1,
        "merge_sha": "abc1234",
        "rollout_packet_path": "reports/control_plane/post_merge_supervisor_plan_2026-03-21.md",
        "deferred_items": [],
        "next_candidates": [],
        "tracker_state_summary": "stable",
        "blocker_report_paths": [],
    }
    validation_results = _make_validation_results(["gate1"], [])
    envelope = (
        "BEGIN_META_ENVELOPE\n"
        '{"decision": "CONTINUE_DIALECTIC", "summary": "ok", "findings": [], "request_for_claude": "Continue"}\n'
        "END_META_ENVELOPE\n"
    )
    selected: list[str] = []
    monkeypatch.setenv("RCX_REVIEWER_AGENT_OVERRIDE", "claude")
    monkeypatch.setenv("RCX_ROLE_AGENT_OVERRIDE_REPO_ROOT", str(tmp_path / "other"))

    def fake_get_adapter(config, name):
        selected.append(name)
        return MagicMock(name=name)

    with patch.object(meta, "build_post_merge_prompt", return_value="prompt"), \
         patch.object(meta, "load_bridge_config_with_worktree_heal_at", return_value={"agents": {}}), \
         patch.object(meta, "get_adapter", side_effect=fake_get_adapter), \
         patch.object(meta, "run_adapter", return_value=envelope):
        parsed = meta.run_post_merge_review(
            paths,
            package,
            validation_results,
            derived_files=["TASKS.md"],
            rollout_order="1. Continue",
            timeout_s=75,
        )

    assert parsed["decision"] == "CONTINUE_DIALECTIC"
    assert selected == ["codex"]


def test_post_merge_prompt_requires_silent_bootstrap_read(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "mu").mkdir()
    package = {
        "task_id": "[POST-MERGE]",
        "wave_name": "wave",
        "lane": "hooks/agents/bridge control-surface",
        "merged_pr": 1,
        "merge_sha": "abc1234",
        "rollout_packet_path": "reports/control_plane/post_merge_supervisor_plan_2026-03-21.md",
        "deferred_items": [],
        "next_candidates": [],
        "tracker_state_summary": "stable",
        "blocker_report_paths": [],
    }
    results = _make_validation_results(["gate1"], [])
    prompt = meta.build_post_merge_prompt(
        package,
        results,
        REPO_ROOT,
        ["TASKS.md"],
        "1. Continue",
    )
    assert "Do this silently." in prompt
    assert "emit only the final envelope" in prompt


def test_run_post_merge_review_sanitizes_slash_task_ids_for_prompt_paths(tmp_path):
    bus_dir = tmp_path / "meta_bus"
    bus_dir.mkdir(parents=True, exist_ok=True)
    paths = meta.MetaBridgePaths(
        repo_root=REPO_ROOT,
        bus_dir=bus_dir,
        db_path=bus_dir / "meta_bridge.db",
        lock_path=bus_dir / "meta_bridge.lock",
    )
    package = {
        "task_id": "[POST-MERGE/parallel-pipeline]",
        "wave_name": "wave",
        "lane": "hooks/agents/bridge control-surface",
        "merged_pr": 1,
        "merge_sha": "abc1234",
        "rollout_packet_path": "reports/control_plane/post_merge_supervisor_plan_2026-03-21.md",
        "deferred_items": [],
        "next_candidates": [],
        "tracker_state_summary": "stable",
        "blocker_report_paths": [],
    }
    validation_results = _make_validation_results(["gate1"], [])
    envelope = (
        "BEGIN_META_ENVELOPE\n"
        '{"decision": "CONTINUE_DIALECTIC", "summary": "ok", "findings": [], "request_for_claude": "Continue"}\n'
        "END_META_ENVELOPE\n"
    )

    with patch.object(meta, "build_post_merge_prompt", return_value="prompt"), \
         patch.object(meta, "load_bridge_config", return_value={"agents": {}}), \
         patch.object(meta, "get_adapter", return_value=MagicMock()), \
         patch.object(meta, "run_adapter", return_value=envelope) as mock_run:
        parsed = meta.run_post_merge_review(
            paths,
            package,
            validation_results,
            derived_files=["TASKS.md"],
            rollout_order="1. Continue",
            timeout_s=75,
        )

    assert parsed["decision"] == "CONTINUE_DIALECTIC"
    kwargs = mock_run.call_args.kwargs
    assert "/" not in kwargs["job_id"]
    assert "/" not in kwargs["turn_id"]
    assert kwargs["prompt_path"].exists()
    assert kwargs["raw_output_path"].parent.exists()


# ===========================================================================
# Post-merge supervisor tests
# ===========================================================================


class TestPostMergePackageSchema:
    """Post-merge package schema validation."""

    def test_valid_package_passes(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        rollout = repo / "reports" / "control_plane" / "rollout.md"
        rollout.write_text("# rollout")
        # Make it tracked
        import subprocess
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        subprocess.run(["git", "add", str(rollout.relative_to(repo))], cwd=repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init", "--allow-empty"], cwd=repo, capture_output=True, env={**__import__("os").environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})

        pkg = {
            "task_id": "[TEST-1]",
            "merged_pr": 100,
            "merge_sha": "abc123",
            "wave_name": "test-wave",
            "lane": "test-lane",
            "rollout_packet_path": "reports/control_plane/rollout.md",
            "deferred_items": [],
            "next_candidates": [{"candidate": "next thing", "bounded": True, "tracked_packet": None}],
            "tracker_state_summary": "NEXT: [TEST-1]",
            "blocker_report_paths": [],
        }
        valid, errors = meta.validate_post_merge_package_schema(pkg, repo)
        assert valid, errors

    def test_valid_package_passes_without_rollout_packet_path(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        pkg = {
            "task_id": "[TEST-1]",
            "merged_pr": 100,
            "merge_sha": "abc123",
            "wave_name": "test-wave",
            "lane": "test-lane",
            "deferred_items": [],
            "next_candidates": [{"candidate": "next thing", "bounded": True, "tracked_packet": None}],
            "tracker_state_summary": "NEXT: [TEST-1]",
            "blocker_report_paths": [],
        }
        valid, errors = meta.validate_post_merge_package_schema(pkg, repo)
        assert valid, errors

    def test_missing_fields_fails(self):
        valid, errors = meta.validate_post_merge_package_schema({"task_id": "[X]"}, Path("/tmp"))
        assert not valid
        assert any("Missing" in e for e in errors)

    def test_unbracketted_task_id_fails(self):
        pkg = {
            "task_id": "NO-BRACKETS",
            "merged_pr": 1, "merge_sha": "a", "wave_name": "w", "lane": "l",
            "rollout_packet_path": "reports/control_plane/x.md",
            "deferred_items": [], "next_candidates": [],
            "tracker_state_summary": "s", "blocker_report_paths": [],
        }
        valid, errors = meta.validate_post_merge_package_schema(pkg, Path("/tmp"))
        assert not valid
        assert any("bracketed" in e for e in errors)

    def test_malformed_blocker_paths_fails(self):
        """Bridge R1 finding #3: dict elements in blocker_report_paths must fail schema, not crash Gate 4."""
        pkg = {
            "task_id": "[X]",
            "merged_pr": 1, "merge_sha": "a", "wave_name": "w", "lane": "l",
            "rollout_packet_path": "reports/control_plane/x.md",
            "deferred_items": [], "next_candidates": [],
            "tracker_state_summary": "s",
            "blocker_report_paths": [{"not": "a string"}],
        }
        valid, errors = meta.validate_post_merge_package_schema(pkg, Path("/tmp"))
        assert not valid
        assert any("string" in e for e in errors)


class TestPostMergeModeScoping:
    """Post-merge tokens are mode-scoped — no cross-mode leakage."""

    def test_pre_commit_token_rejected_in_post_merge(self):
        """COMMIT_GO is not a valid post-merge token."""
        output = 'BEGIN_META_ENVELOPE\n{"decision": "COMMIT_GO", "summary": "ok"}\nEND_META_ENVELOPE'
        with pytest.raises(meta.MetaBridgeError, match="Invalid post-merge decision"):
            meta.parse_post_merge_envelope(output)

    def test_post_merge_token_rejected_in_pre_commit(self):
        """ROUTE_PHASE_A is not a valid pre-commit token."""
        output = 'BEGIN_META_ENVELOPE\n{"decision": "ROUTE_PHASE_A", "summary": "ok"}\nEND_META_ENVELOPE'
        with pytest.raises(meta.MetaBridgeError, match="Invalid decision token"):
            meta.parse_meta_envelope(output)

    def test_valid_post_merge_token_accepted(self):
        """CONTINUE_DIALECTIC is a valid post-merge token."""
        output = 'BEGIN_META_ENVELOPE\n{"decision": "CONTINUE_DIALECTIC", "summary": "needs narrowing"}\nEND_META_ENVELOPE'
        envelope = meta.parse_post_merge_envelope(output)
        assert envelope["decision"] == "CONTINUE_DIALECTIC"

    def test_all_post_merge_tokens_accepted(self):
        for token in meta.POST_MERGE_AUTHORIZED_DECISIONS:
            output = f'BEGIN_META_ENVELOPE\n{{"decision": "{token}", "summary": "test"}}\nEND_META_ENVELOPE'
            envelope = meta.parse_post_merge_envelope(output)
            assert envelope["decision"] == token

    def test_post_merge_conflicting_multiple_envelopes_rejected(self):
        output = (
            'BEGIN_META_ENVELOPE\n{"decision": "CONTINUE_DIALECTIC", "summary": "ok"}\nEND_META_ENVELOPE\n'
            'BEGIN_META_ENVELOPE\n{"decision": "ROUTE_PHASE_B", "summary": "route"}\nEND_META_ENVELOPE'
        )
        with pytest.raises(meta.MetaBridgeError, match="multiple differing envelope blocks"):
            meta.parse_post_merge_envelope(output)


class TestPostMergeGate1:
    """Gate 1: merge verification (HARD)."""

    def test_not_on_dev_fails(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        import subprocess
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=repo, capture_output=True,
                       env={**__import__("os").environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
        # Default branch is not "dev"
        result = meta.check_merge_verification(repo, "abc123")
        assert not result.passed
        assert "dev" in result.error.lower() or "not on dev" in result.error.lower() or "ancestor" in result.error.lower()


class TestPostMergeExtractRolloutOrder:
    """Rollout order extraction with standing-invariant classification."""

    def test_standing_invariant_tagged(self, tmp_path):
        rollout = tmp_path / "rollout.md"
        rollout.write_text(
            "## Canonical rollout order\n\n"
            "1. ~~Step 1~~ **(done)**\n"
            "2. **Standing invariant:** Keep gate live\n"
            "3. **Active next step:** Do the thing\n"
        )
        result = meta.extract_rollout_order(tmp_path, "rollout.md")
        assert "[DONE]" in result
        assert "[STANDING_INVARIANT]" in result
        assert "Active next step" in result

    def test_bare_strikethrough_marked_done(self, tmp_path):
        """Fuzzer finding: bare strikethrough without 'done' annotation should still be DONE."""
        rollout = tmp_path / "rollout.md"
        rollout.write_text(
            "## Canonical rollout order\n\n"
            "1. ~~Completed task~~\n"
        )
        result = meta.extract_rollout_order(tmp_path, "rollout.md")
        assert "[DONE]" in result


class TestPostMergeIntegration:
    """Integration tests for run_post_merge_bridge and supporting functions."""

    def test_run_post_merge_validation_gates_gate1_hard(self, tmp_path):
        """Gate 1 failure blocks all routing."""
        repo = tmp_path / "repo"
        repo.mkdir()
        import subprocess
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        env = {**__import__("os").environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=repo, capture_output=True, env=env)

        pkg = {"merge_sha": "0000000000000000000000000000000000000000", "task_id": "[X]",
               "rollout_packet_path": "x", "blocker_report_paths": []}
        results, all_passed, gate1_passed = meta.run_post_merge_validation_gates(repo, pkg)
        assert not gate1_passed
        assert not all_passed

    def test_derive_changed_files_valid_sha(self):
        """derive_changed_files works on a real merge SHA."""
        from tests.repo_root import REPO_ROOT
        # Use the known merge commit from PR #655
        files, err = meta.derive_changed_files(REPO_ROOT, "ac714fa")
        # Should return files or empty (depending on how far back ac714fa is)
        assert isinstance(files, list)

    def test_validate_post_merge_schema_rejects_non_dict(self):
        """Package must be a dict."""
        valid, errors = meta.validate_post_merge_package_schema("not a dict", Path("/tmp"))
        assert not valid
        assert any("JSON object" in e for e in errors)

    def test_parse_post_merge_envelope_rejects_missing_keys(self):
        """Envelope must have decision + summary."""
        output = 'BEGIN_META_ENVELOPE\n{"decision": "ROUTE_PHASE_A"}\nEND_META_ENVELOPE'
        with pytest.raises(meta.MetaBridgeError, match="missing keys"):
            meta.parse_post_merge_envelope(output)

    def test_build_post_merge_prompt_includes_rollout(self, tmp_path):
        """Prompt template renders with rollout order and Phase-A-Lock."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "mu" / "tools" / "agents" / "templates").mkdir(parents=True)
        template_src = REPO_ROOT / "mu" / "tools" / "agents" / "templates" / "post_merge_task.txt"
        (repo / "mu" / "tools" / "agents" / "templates" / "post_merge_task.txt").write_text(
            template_src.read_text()
        )

        pkg = {"task_id": "[T]", "wave_name": "w", "lane": "l", "merged_pr": 1,
               "merge_sha": "abc", "rollout_packet_path": "reports/control_plane/r.md",
               "next_candidates": []}
        results = [meta.ValidationResult("g1", True)]
        # Should not crash
        prompt = meta.build_post_merge_prompt(pkg, results, repo, ["f1.py"], "1. Step 1")
        assert "ROUTE_PHASE_A" in prompt
        assert "Step 1" in prompt
        assert "Bounded Review Contract" in prompt
        assert "Use no more than 8 shell commands" in prompt

    def test_decide_post_merge_route_locally_routes_phase_a_when_packet_unlocked(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "roundtrip.md").write_text(
            "# Roundtrip\nStatus: In progress\nPhase-A-Lock: UNLOCKED\n",
            encoding="utf-8",
        )
        package = {
            "next_candidates": [
                {
                    "candidate": "[TASK] Run the routed proof.",
                    "bounded": True,
                    "tracked_packet": "reports/control_plane/roundtrip.md",
                }
            ]
        }
        results = [meta.ValidationResult("merge_verification", True)]

        envelope = meta._decide_post_merge_route_locally(  # ANTICHEAT_OK: testing internal supervisor functions
            repo,
            package,
            results,
            "(no 'Canonical rollout order' section found)",
        )

        assert envelope["decision"] == "ROUTE_PHASE_A"
        assert "Phase A" in envelope["summary"]

    def test_decide_post_merge_route_locally_routes_phase_b_when_packet_locked(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "roundtrip.md").write_text(
            "# Roundtrip\nStatus: In progress\nPhase-A-Lock: LOCKED\n",
            encoding="utf-8",
        )
        package = {
            "next_candidates": [
                {
                    "candidate": "[TASK] Run the routed proof.",
                    "bounded": True,
                    "tracked_packet": "reports/control_plane/roundtrip.md",
                }
            ]
        }
        results = [meta.ValidationResult("merge_verification", True)]

        envelope = meta._decide_post_merge_route_locally(  # ANTICHEAT_OK: testing internal supervisor functions
            repo,
            package,
            results,
            "1. Canonical next step",
        )

        assert envelope["decision"] == "ROUTE_PHASE_B"
        assert "Phase B" in envelope["summary"]

    def test_decide_post_merge_route_locally_skips_completed_packet(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "roundtrip.md").write_text(
            "# Roundtrip\nStatus: COMPLETED (commit-ready, supervisor COMMIT_GO)\nPhase-A-Lock: LOCKED\n",
            encoding="utf-8",
        )
        package = {
            "next_candidates": [
                {
                    "candidate": "[TASK] Run the routed proof.",
                    "bounded": True,
                    "tracked_packet": "reports/control_plane/roundtrip.md",
                }
            ]
        }
        results = [meta.ValidationResult("merge_verification", True)]

        envelope = meta._decide_post_merge_route_locally(  # ANTICHEAT_OK: testing internal supervisor functions
            repo,
            package,
            results,
            "1. Canonical next step",
        )

        assert envelope["decision"] == "UPDATE_TRACKER_ONLY"
        assert "no remaining open bounded next candidate" in envelope["summary"]
        assert envelope["findings"][0]["title"] == "Completed next candidate removed from routing"

    def test_check_rollout_packet_canonical_derives_when_path_missing(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        rollout = repo / "reports" / "control_plane" / "canonical.md"
        rollout.write_text("# rollout\n")
        (repo / "TASKS.md").write_text(
            "## NOW\n\n## NEXT\n\n"
            "- **[TASK-1]** Simple test. **Tracked packet:** `reports/control_plane/canonical.md`.\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
        env = {
            **__import__("os").environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
        }
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True, check=True, env=env)
        result = meta.check_rollout_packet_canonical(repo, "", "[TASK-1]")
        assert result.passed

    def test_get_canonical_rollout_packet_for_task_reads_tasks_entry(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "TASKS.md").write_text(
            "## NOW\n\n## NEXT\n\n"
            "- **[TASK-1]** Simple test. **Tracked packet:** `reports/control_plane/canonical.md`.\n",
            encoding="utf-8",
        )

        packet, err = meta.get_canonical_rollout_packet_for_task(repo, "[TASK-1]")
        assert err is None
        assert packet == "reports/control_plane/canonical.md"

    def test_check_rollout_packet_canonical_derives_path_must_still_be_tracked(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "canonical.md").write_text("# rollout\n")
        (repo / "TASKS.md").write_text(
            "## NOW\n\n## NEXT\n\n"
            "- **[TASK-1]** Simple test. **Tracked packet:** `reports/control_plane/canonical.md`.\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, capture_output=True, check=True)
        env = {
            **__import__("os").environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
        }
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True, check=True, env=env)

        result = meta.check_rollout_packet_canonical(repo, "", "[TASK-1]")
        assert not result.passed
        assert "not a git-tracked file" in (result.error or "")


class TestGate3TaskBound:
    """Gate 3 must bind to the exact Tracked packet: value, not any path in the entry."""

    def test_rejects_non_tracked_packet_path(self, tmp_path):
        """Bridge R1 regression: Gate 3 must extract exact Tracked packet: not any mention."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "canonical.md").write_text("# canonical")
        (repo / "reports" / "control_plane" / "other.md").write_text("# other")

        import subprocess
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        env = {**__import__("os").environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True, env=env)

        # TASKS.md: task tracks canonical.md but mentions other.md in prose
        tasks = repo / "TASKS.md"
        tasks.write_text(
            "## NOW\n\n## NEXT\n\n"
            "- **[TASK-1]** Some task. **Tracked packet:** `reports/control_plane/canonical.md`. "
            "See also reports/control_plane/other.md for context.\n"
        )

        # Should PASS for canonical.md
        r1 = meta.check_rollout_packet_canonical(repo, "reports/control_plane/canonical.md", "[TASK-1]")
        assert r1.passed

        # Should FAIL for other.md (merely mentioned, not the Tracked packet:)
        r2 = meta.check_rollout_packet_canonical(repo, "reports/control_plane/other.md", "[TASK-1]")
        assert not r2.passed


class TestGate5CommentResistance:
    """Gate 5 must not be spoofed by commented-out exec lines."""

    def test_commented_exec_fails(self, tmp_path):
        """Bridge R1 regression: comment mentioning pre-commit-doc-check must not pass."""
        repo = tmp_path / "repo"
        repo.mkdir()
        import subprocess
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        env = {**__import__("os").environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=repo, capture_output=True, env=env)

        # Create a fake hook with only a comment mentioning pre-commit-doc-check
        hooks_dir = repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        hook = hooks_dir / "pre-commit"
        hook.write_text("#!/bin/bash\n# exec $SCRIPT_DIR/hooks/pre-commit-doc-check\nexit 0\n")
        hook.chmod(0o755)

        # Also need the verifier to exist
        verifier_dir = repo / "mu" / "tools" / "agents"
        verifier_dir.mkdir(parents=True)
        (verifier_dir / "verify_pre_commit_receipt.py").write_text("# stub")

        result = meta.check_pre_commit_gate(repo)
        assert not result.passed, f"Gate 5 should fail on commented-out exec, got: {result}"

    def test_non_exec_active_line_fails(self, tmp_path):
        """Bridge R2 regression: active non-exec line mentioning the path must fail."""
        repo = tmp_path / "repo"
        repo.mkdir()
        import subprocess
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        env = {**__import__("os").environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=repo, capture_output=True, env=env)

        hooks_dir = repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        hook = hooks_dir / "pre-commit"
        # Active line that mentions the path but is NOT an exec statement
        hook.write_text('#!/bin/bash\necho "hooks/pre-commit-doc-check is cool"\nexit 0\n')
        hook.chmod(0o755)

        verifier_dir = repo / "mu" / "tools" / "agents"
        verifier_dir.mkdir(parents=True)
        (verifier_dir / "verify_pre_commit_receipt.py").write_text("# stub")

        result = meta.check_pre_commit_gate(repo)
        assert not result.passed, f"Gate 5 should fail on non-exec mention, got: {result}"

    def test_real_exec_passes(self, tmp_path):
        """Real exec delegation should pass."""
        repo = tmp_path / "repo"
        repo.mkdir()
        import subprocess
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        env = {**__import__("os").environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=repo, capture_output=True, env=env)

        hooks_dir = repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        hook = hooks_dir / "pre-commit"
        hook.write_text('#!/bin/bash\nexec "$SCRIPT_DIR/hooks/pre-commit-doc-check" "$@"\n')
        hook.chmod(0o755)

        # Create canonical hook file (Gate 5 checks it exists)
        canonical_hook_dir = repo / "tools" / "hooks"
        canonical_hook_dir.mkdir(parents=True)
        (canonical_hook_dir / "pre-commit-doc-check").write_text("#!/bin/bash\nexit 0\n")

        verifier_dir = repo / "mu" / "tools" / "agents"
        verifier_dir.mkdir(parents=True)
        (verifier_dir / "verify_pre_commit_receipt.py").write_text("# stub")

        result = meta.check_pre_commit_gate(repo)
        assert result.passed, f"Gate 5 should pass on real exec, got: {result.error}"

    def test_linked_worktree_shared_managed_hook_passes(self, tmp_path):
        """Linked worktrees should accept the shared managed hook in the common git dir."""
        primary = tmp_path / "primary"
        linked = tmp_path / "linked"
        primary.mkdir()
        import subprocess
        subprocess.run(["git", "init"], cwd=primary, check=True, capture_output=True)
        env = {**__import__("os").environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

        canonical_hook_dir = primary / "tools" / "hooks"
        canonical_hook_dir.mkdir(parents=True)
        canonical_hook = canonical_hook_dir / "pre-commit-doc-check"
        canonical_hook.write_text("#!/bin/bash\nexit 0\n")
        canonical_hook.chmod(0o755)

        verifier_dir = primary / "mu" / "tools" / "agents"
        verifier_dir.mkdir(parents=True)
        (verifier_dir / "verify_pre_commit_receipt.py").write_text("# stub\n")

        subprocess.run(
            ["git", "add", "tools/hooks/pre-commit-doc-check", "mu/tools/agents/verify_pre_commit_receipt.py"],
            cwd=primary,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "commit", "-m", "seed"], cwd=primary, check=True, capture_output=True, env=env)

        hook = primary / ".git" / "hooks" / "pre-commit"
        if hook.exists() or hook.is_symlink():
            hook.unlink()
        hook.symlink_to("../../tools/hooks/pre-commit-doc-check")

        subprocess.run(
            ["git", "worktree", "add", str(linked), "-b", "linked"],
            cwd=primary,
            check=True,
            capture_output=True,
            env=env,
        )

        result = meta.check_pre_commit_gate(linked)
        assert result.passed, f"Gate 5 should pass for linked worktree shared hook, got: {result.error}"


class TestValidationResultFieldAccess:
    """ValidationResult must only use fields that exist on the dataclass.

    Bridge R1 finding: Gate 10 accessed r.message which doesn't exist —
    ValidationResult has 'error', not 'message'. This caused AttributeError
    on control-surface waves.
    """

    def test_validation_result_has_error_not_message(self):
        """ValidationResult dataclass has 'error' field, not 'message'."""
        vr = meta.ValidationResult("test_gate", True, error="some detail")
        assert hasattr(vr, "error")
        assert not hasattr(vr, "message")
        assert vr.error == "some detail"

    def test_validation_result_error_default_empty(self):
        """ValidationResult.error defaults to empty string."""
        vr = meta.ValidationResult("test_gate", True)
        assert vr.error == ""

    def test_gate10_validation_commands_uses_error_field(self):
        """Gate 10 code path must use r.error, not r.message.

        This is a source-level check to prevent regression of the
        AttributeError that crashed Gate 10 on control-surface waves.
        """
        source = (REPO_ROOT / "mu" / "tools" / "agents" / "meta_bridge_supervisor.py").read_text()
        # Find the Gate 10 section (closeout attestation)
        gate10_start = source.find("Gate 10: Closeout attestation")
        assert gate10_start > 0, "Gate 10 section not found in source"
        # Check the relevant code section after Gate 10 marker
        gate10_section = source[gate10_start:gate10_start + 1500]
        assert "r.message" not in gate10_section, (
            "Gate 10 still uses r.message — ValidationResult has 'error', not 'message'. "
            "This causes AttributeError on control-surface waves."
        )
        assert "r.error" in gate10_section, (
            "Gate 10 should use r.error for ValidationResult output"
        )


class TestDeferredBlockerWarningFormats:
    """Deferred-blocker warning summaries must count both active packet formats."""

    def test_active_blockers_format_counts_open_items(self, tmp_path):
        repo = tmp_path / "repo"
        blocking_dir = repo / "reports" / "deferred" / "blocking"
        blocking_dir.mkdir(parents=True)
        packet = blocking_dir / "packet.md"
        packet.write_text(
            "# Packet\n"
            "**Status:** ACTIVE BLOCKERS\n\n"
            "## One\n**Status:** OPEN\n\n"
            "## Two\n**Status:** OPEN\n",
            encoding="utf-8",
        )
        result = meta.check_deferred_blockers(repo, ["reports/deferred/blocking/packet.md"])
        assert result.passed is True
        assert "2 OPEN items" in result.error

    def test_status_open_remaining_format_counts_open_items(self, tmp_path):
        repo = tmp_path / "repo"
        blocking_dir = repo / "reports" / "deferred" / "blocking"
        blocking_dir.mkdir(parents=True)
        packet = blocking_dir / "packet.md"
        packet.write_text(
            "# Packet\n"
            "Status: OPEN (2 remaining)\n\n"
            "## OPEN Items\n\n"
            "### 1. First open item\n"
            "Body.\n\n"
            "### ~~2. Fixed item~~\n"
            "Resolved.\n\n"
            "### 3. Second open item\n"
            "Body.\n",
            encoding="utf-8",
        )
        result = meta.check_deferred_blockers(repo, ["reports/deferred/blocking/packet.md"])
        assert result.passed is True
        assert "2 OPEN items" in result.error


class TestGate10ReceiptChainProof:
    """Gate 10 must emit a receipt_chain behavioral proof for receipt-chain waves.

    When changed_files include receipt-chain files (commit_executor.py, phase_b_executor.py,
    meta_bridge_client.py, meta_bridge_supervisor.py), Gate 10 must pass a receipt_chain
    validation command to check_closeout_attestation.py so that GO can be authorized.
    """

    def test_receipt_chain_proof_emitted_for_receipt_chain_files(self, tmp_path):
        """Gate 10 must include a receipt_chain validation command when receipt-chain files touched."""
        source = (REPO_ROOT / "mu" / "tools" / "agents" / "meta_bridge_supervisor.py").read_text()
        # The receipt_chain proof section must exist in the Gate 10 code
        gate10_start = source.find("Gate 10: Closeout attestation")
        assert gate10_start > 0
        gate10_section = source[gate10_start:gate10_start + 3000]
        assert "receipt_chain" in gate10_section, (
            "Gate 10 must emit a receipt_chain validation command for receipt-chain waves. "
            "Without this, check_closeout_attestation.py rejects GO for control-surface waves "
            "that touch receipt-chain files."
        )
        assert "test_commit_executor_receipt" in gate10_section, (
            "Gate 10 must run the receipt chain test to provide BEHAVIORAL proof"
        )

    def test_receipt_chain_validation_command_in_gate10_output(self, tmp_path):
        """Structural: validation_commands_for_att includes receipt_chain when receipt files touched."""
        # Build a package with receipt-chain files
        package = {
            "changed_files": [
                "mu/tools/executors/commit_executor.py",
                "mu/tools/executors/phase_b_executor.py",
            ],
            "task_id": "[TEST]",
            "wave_name": "test",
            "lane": "test",
            "scope_items": [],
            "fixes_implemented": [],
            "deferred_items": [],
            "bridge_status": {},
            "evidence_handles": {},
            "blocker_report_paths": [],
            "current_judgment": "COMMIT_GO",
        }
        # Run validation gates — Gate 10 should include receipt_chain command
        # We mock run_validation_command to avoid running real scripts
        gate_results = []

        def mock_run_validation(repo_root, cmd, **kw):
            cmd_str = " ".join(str(c) for c in cmd)
            if "check_closeout_attestation" in cmd_str:
                # Check that the validation commands file includes receipt_chain
                val_cmds_path = None
                for i, c in enumerate(cmd):
                    if str(c) == "--validation-commands" and i + 1 < len(cmd):
                        val_cmds_path = Path(cmd[i + 1])
                        break
                if val_cmds_path and val_cmds_path.exists():
                    val_cmds = json.loads(val_cmds_path.read_text())
                    rc_cmds = [v for v in val_cmds if "receipt_chain" in v.get("command", "")]
                    gate_results.append(("receipt_chain_found", len(rc_cmds) > 0))
                return 0, json.dumps({"authorized": True, "attestation": {"blockers": []}, "issues": []})
            # Default: pass
            return 0, "passed"

        with patch.object(meta, "run_validation_command", side_effect=mock_run_validation), \
             patch.object(meta, "check_dirty_state", return_value=meta.ValidationResult("dirty_state", True)), \
             patch.object(meta, "check_deferred_blockers", return_value=meta.ValidationResult("deferred_blockers", True)), \
             patch.object(meta, "check_tasks_authorization", return_value=meta.ValidationResult("tasks_auth", True)):
            results, all_passed = meta.run_validation_gates(REPO_ROOT, package, verbose=True)

        # Verify receipt_chain command was included in the validation commands file
        assert any(name == "receipt_chain_found" and found for name, found in gate_results), (
            f"Gate 10 must include receipt_chain validation command for receipt-chain waves. "
            f"Gate results: {gate_results}"
        )


class TestGate10PackageScoped:
    """Bridge R1 NO_GO fix: Gate 10 must NOT pass --files (caller-declared).

    Passing --files with caller-declared changed_files produces DECLARED proof
    class in check_closeout_attestation.py, which rejects GO. Attestation must
    derive changed files from git (BEHAVIORAL proof class) for GO authorization.
    """

    def test_gate10_does_not_pass_files_flag_to_attestation(self):
        """Gate 10 must NOT pass --files — let attestation derive from git (BEHAVIORAL proof)."""
        source = Path(meta.__file__).read_text()
        gate10_start = source.find("Gate 10: Closeout attestation")
        assert gate10_start > 0, "Gate 10 section not found in source"
        gate10_section = source[gate10_start:gate10_start + 10000]
        # The att_cmd construction must NOT include --files
        # Find the att_cmd list construction
        att_cmd_start = gate10_section.find("att_cmd = [")
        assert att_cmd_start > 0, "att_cmd construction not found"
        att_cmd_section = gate10_section[att_cmd_start:att_cmd_start + 500]
        assert '"--files"' not in att_cmd_section and "'--files'" not in att_cmd_section, (
            "Gate 10 must NOT pass --files to check_closeout_attestation.py. "
            "Caller-declared files produce DECLARED proof class, which rejects GO. "
            "Attestation must derive changed files from git (BEHAVIORAL proof)."
        )

    def test_gate10_parses_json_on_nonzero_exit(self):
        """Gate 10 must try to parse JSON even on nonzero exit codes.

        Bridge R6 finding: Gate 10 dropped actionable attestation issues on failure,
        surfacing only truncated raw output. Fix: parse JSON on all exits.
        """
        source = Path(meta.__file__).read_text()
        gate10_start = source.find("Gate 10: Closeout attestation")
        assert gate10_start > 0
        gate10_section = source[gate10_start:gate10_start + 8500]
        # The code must parse JSON regardless of exit code using att_data pattern
        assert "att_data is not None" in gate10_section, (
            "Gate 10 must attempt JSON parse on nonzero exits using att_data pattern, "
            "not just parse inside 'if exit_code == 0:'"
        )


class TestGate10NonReceiptChainControlSurface:
    """Gate 10 must provide BEHAVIORAL proof for control-surface waves
    that do NOT touch receipt-chain files.

    Without this, the attestation checker rejects GO because gate-style
    validations ('gate:...') are filtered out and no qualifying BEHAVIORAL
    validation-command proof exists.
    """

    def test_gate10_adds_behavioral_proof_for_non_receipt_chain_cs_wave(self):
        """Source must have a block that adds a control_surface behavioral proof
        when receipt-chain files are NOT touched."""
        source = Path(meta.__file__).read_text()
        # The fix adds a block that checks `not (set(changed) & _receipt_chain_files)`
        # and runs either test_control_surface_review.py or the checker script
        assert "control_surface: invariant_tests" in source or "control_surface: invariant_checker" in source, (
            "Gate 10 must add a 'control_surface:' BEHAVIORAL proof for non-receipt-chain "
            "control-surface waves so the attestation checker can authorize GO."
        )

    def test_gate10_behavioral_proof_not_gate_prefixed(self):
        """The control-surface behavioral proof must NOT use 'gate:' prefix,
        because the attestation checker filters those out."""
        source = Path(meta.__file__).read_text()
        # Find the control_surface proof command strings
        for marker in ("control_surface: invariant_tests", "control_surface: invariant_checker"):
            if marker in source:
                assert not marker.startswith("gate:"), (
                    f"Control-surface proof '{marker}' must not use 'gate:' prefix"
                )
                break
        else:
            pytest.fail("Neither control_surface proof marker found in source")


class TestGate10GeneratedAttestationShape:
    """Gate 10 must understand the JSON shape emitted by --generate --json."""

    def _package(self):
        return {
            "task_id": "[TEST]",
            "wave_name": "test-wave",
            "lane": "hooks/agents/bridge control-surface",
            "changed_files": ["mu/tools/executors/phase_b_executor.py"],
            "scope_items": [],
            "fixes_implemented": [],
            "deferred_items": [],
            "bridge_status": {},
            "evidence_handles": {},
            "blocker_report_paths": [],
            "current_judgment": "COMMIT_GO",
        }

    def test_gate10_accepts_go_authorized_generate_output(self):
        package = self._package()

        def mock_run_validation(repo_root, cmd, **kw):
            cmd_str = " ".join(str(c) for c in cmd)
            if "check_closeout_attestation" in cmd_str:
                return 0, json.dumps({
                    "go_authorized": True,
                    "blockers": [],
                    "validation_issues": [],
                })
            return 0, "passed"

        with patch.object(meta, "run_validation_command", side_effect=mock_run_validation), \
             patch.object(meta, "check_dirty_state", return_value=meta.ValidationResult("dirty_state", True)), \
             patch.object(meta, "check_deferred_blockers", return_value=meta.ValidationResult("deferred_blockers", True)), \
             patch.object(meta, "check_tasks_authorization", return_value=meta.ValidationResult("tasks_auth", True)):
            results, all_passed = meta.run_validation_gates(REPO_ROOT, package, verbose=False)

        gate10 = next(r for r in results if r.name == "closeout_attestation")
        assert gate10.passed
        assert all_passed

    def test_gate10_surfaces_validation_issues_from_generate_output(self):
        package = self._package()

        def mock_run_validation(repo_root, cmd, **kw):
            cmd_str = " ".join(str(c) for c in cmd)
            if "check_closeout_attestation" in cmd_str:
                return 1, json.dumps({
                    "go_authorized": False,
                    "blockers": [],
                    "validation_issues": ["missing behavioral proof"],
                })
            return 0, "passed"

        with patch.object(meta, "run_validation_command", side_effect=mock_run_validation), \
             patch.object(meta, "check_dirty_state", return_value=meta.ValidationResult("dirty_state", True)), \
             patch.object(meta, "check_deferred_blockers", return_value=meta.ValidationResult("deferred_blockers", True)), \
             patch.object(meta, "check_tasks_authorization", return_value=meta.ValidationResult("tasks_auth", True)):
            results, all_passed = meta.run_validation_gates(REPO_ROOT, package, verbose=False)

        gate10 = next(r for r in results if r.name == "closeout_attestation")
        assert not gate10.passed
        assert "missing behavioral proof" in gate10.error
        assert not all_passed


# ===========================================================================
# META-BRIDGE-BOUNDED-REVIEW-FIX regression tests
# Covers: slash task-ID path safety, zero-match probe envelope, startup-flow
# suppression.  Wave: meta-bridge-taskid-path-safety-2026-04-03.
# ===========================================================================


class TestFilesystemSafeToken:
    """_filesystem_safe_token must neutralize all OS-unsafe characters."""

    def test_forward_slash_replaced(self):
        assert "/" not in meta._filesystem_safe_token("PIPELINE-RECOVERY/monitor-rebind")  # ANTICHEAT_OK: testing path-safety helper

    def test_backslash_replaced(self):
        assert "\\" not in meta._filesystem_safe_token("FOO\\BAR")  # ANTICHEAT_OK: testing path-safety helper

    def test_colon_replaced(self):
        token = meta._filesystem_safe_token("task:sub:id")  # ANTICHEAT_OK: testing path-safety helper
        assert ":" not in token

    def test_pipe_replaced(self):
        token = meta._filesystem_safe_token("a|b|c")  # ANTICHEAT_OK: testing path-safety helper
        assert "|" not in token

    def test_space_replaced(self):
        token = meta._filesystem_safe_token("task with spaces")  # ANTICHEAT_OK: testing path-safety helper
        assert " " not in token

    def test_brackets_preserved(self):
        """Bracketed task IDs like [TASK-ID] keep their brackets."""
        token = meta._filesystem_safe_token("[META-BRIDGE-S1]")  # ANTICHEAT_OK: testing path-safety helper
        assert "[" in token and "]" in token

    def test_empty_returns_unknown(self):
        assert meta._filesystem_safe_token("") == "unknown"  # ANTICHEAT_OK: testing path-safety helper

    def test_none_returns_unknown(self):
        assert meta._filesystem_safe_token(None) == "unknown"  # ANTICHEAT_OK: testing path-safety helper

    def test_dots_and_hyphens_preserved(self):
        token = meta._filesystem_safe_token("task-2026.04.03")  # ANTICHEAT_OK: testing path-safety helper
        assert token == "task-2026.04.03"

    def test_realistic_slash_bearing_task_id(self):
        """Exact reproduction of the crash-causing task ID from the plan."""
        task_id = "[PIPELINE-RECOVERY/pipeline-monitor-worktree-rebind-2026-04-03]"
        token = meta._filesystem_safe_token(task_id)  # ANTICHEAT_OK: testing path-safety helper
        assert "/" not in token
        assert "\\" not in token
        # Must still be non-empty and recognizable
        assert "PIPELINE-RECOVERY" in token
        assert "pipeline-monitor-worktree-rebind" in token

    def test_multiple_consecutive_slashes_collapse(self):
        token = meta._filesystem_safe_token("a///b")  # ANTICHEAT_OK: testing path-safety helper
        assert "/" not in token
        # Multiple slashes should become a single hyphen
        assert "a-b" == token

    def test_result_is_valid_filename_component(self):
        """Token must be usable as a filename on POSIX and macOS."""
        unsafe = "[TASK/sub\\path:colon|pipe <angle> ?question *star]"
        token = meta._filesystem_safe_token(unsafe)  # ANTICHEAT_OK: testing path-safety helper
        # Must not contain any OS-unsafe characters
        for ch in "/\\:*?\"<>|":
            assert ch not in token, f"Unsafe char {ch!r} found in token {token!r}"


class TestZeroMatchProbeTemplateGuidance:
    """Template must instruct Codex not to abort on zero-match probe commands.

    Regression for Problem B: the reviewer self-aborted when probe commands
    like `rg` returned zero matches (exit code 1 with set -e).
    """

    def test_template_warns_against_set_e_pipefail(self):
        package = {"task_id": "T", "wave_name": "w", "lane": "l"}
        results = _make_validation_results(["gate1"], [])
        prompt = meta.build_meta_reviewer_prompt(package, results, REPO_ROOT)
        assert "set -e" in prompt
        assert "pipefail" in prompt
        assert "zero-match probe" in prompt

    def test_template_says_empty_fields_are_legitimate(self):
        package = {"task_id": "T", "wave_name": "w", "lane": "l"}
        results = _make_validation_results(["gate1"], [])
        prompt = meta.build_meta_reviewer_prompt(package, results, REPO_ROOT)
        assert "bridge_status" in prompt
        assert "blocker_report_paths" in prompt
        assert "legitimately be empty" in prompt

    def test_template_uses_existing_archived_rollout_packet_path(self):
        package = {"task_id": "T", "wave_name": "w", "lane": "l"}
        results = _make_validation_results(["gate1"], [])
        prompt = meta.build_meta_reviewer_prompt(package, results, REPO_ROOT)
        assert "reports/control_plane/archive/meta_bridge_rollout_2026-03-20.md" in prompt
        assert "reports/control_plane/meta_bridge_rollout_2026-03-20.md" not in prompt


class TestStartupFlowSuppressionTemplate:
    """Template must suppress founder guard/attest startup flows in meta-review.

    Regression for Problem A: the pre-commit meta-review path was rerunning
    founder guard/attest startup flows that should only execute once during
    session bootstrap.
    """

    def test_template_suppresses_founder_session_guard(self):
        package = {"task_id": "T", "wave_name": "w", "lane": "l"}
        results = _make_validation_results(["gate1"], [])
        prompt = meta.build_meta_reviewer_prompt(package, results, REPO_ROOT)
        assert "founder_session_guard.sh" in prompt
        assert "Do NOT invoke" in prompt

    def test_template_suppresses_founder_session_attest(self):
        package = {"task_id": "T", "wave_name": "w", "lane": "l"}
        results = _make_validation_results(["gate1"], [])
        prompt = meta.build_meta_reviewer_prompt(package, results, REPO_ROOT)
        assert "founder_session_attest.sh" in prompt

    def test_template_suppresses_skill_startup_workflows(self):
        package = {"task_id": "T", "wave_name": "w", "lane": "l"}
        results = _make_validation_results(["gate1"], [])
        prompt = meta.build_meta_reviewer_prompt(package, results, REPO_ROOT)
        assert "skill startup workflows" in prompt

    def test_template_still_requires_bootstrap_read(self):
        """FOUNDER_SESSION_BOOTSTRAP.md reading must remain required."""
        package = {"task_id": "T", "wave_name": "w", "lane": "l"}
        results = _make_validation_results(["gate1"], [])
        prompt = meta.build_meta_reviewer_prompt(package, results, REPO_ROOT)
        assert "FOUNDER_SESSION_BOOTSTRAP.md" in prompt
        assert "REQUIRED" in prompt

    def test_template_requires_silent_bootstrap(self):
        """Bootstrap read must be silent — no echoed confirmations."""
        package = {"task_id": "T", "wave_name": "w", "lane": "l"}
        results = _make_validation_results(["gate1"], [])
        prompt = meta.build_meta_reviewer_prompt(package, results, REPO_ROOT)
        assert "silently" in prompt.lower() or "Do this silently" in prompt
        assert "Do not print bootstrap confirmations" in prompt


class TestStartupFlowSuppressionGatePath:
    """run_validation_gates() must skip Gate 6 (attestation) when skip_startup_gates=True.

    Regression for bridge round 1 finding: the staged tests only called
    build_meta_reviewer_prompt() (template text), but the actual
    run_validation_gates() path still invoked founder_session_attest.sh
    before reviewer execution, contradicting the startup-flow suppression.
    """

    def _make_package(self):
        return {
            "task_id": "TEST-TASK",
            "wave_name": "test-wave",
            "lane": "test",
            "scope_items": [],
            "fixes_implemented": [],
            "deferred_items": [],
            "bridge_status": {},
            "evidence_handles": {},
            "blocker_report_paths": [],
            "current_judgment": "COMMIT_GO",
            "changed_files": [],
        }

    def test_gate6_skipped_when_skip_startup_gates_true(self):
        """Gate 6 (attestation) must NOT call founder_session_attest.sh
        when skip_startup_gates=True."""
        package = self._make_package()
        invoked_commands = []

        def mock_run_validation(repo_root, cmd, **kw):
            cmd_str = " ".join(str(c) for c in cmd)
            invoked_commands.append(cmd_str)
            return 0, "passed"

        with patch.object(meta, "run_validation_command", side_effect=mock_run_validation), \
             patch.object(meta, "check_dirty_state", return_value=meta.ValidationResult("dirty_state", True)), \
             patch.object(meta, "check_deferred_blockers", return_value=meta.ValidationResult("deferred_blockers", True)), \
             patch.object(meta, "check_tasks_authorization", return_value=meta.ValidationResult("tasks_auth", True)):
            results, all_passed = meta.run_validation_gates(
                REPO_ROOT, package, verbose=True, skip_startup_gates=True
            )

        # Attestation script must NOT appear in invoked commands.
        attest_cmds = [c for c in invoked_commands if "founder_session_attest" in c]
        assert attest_cmds == [], (
            f"Gate 6 invoked founder_session_attest.sh despite skip_startup_gates=True: {attest_cmds}"
        )
        # Gate 6 must still produce a result (auto-pass).
        gate6 = [r for r in results if r.name == "attestation"]
        assert len(gate6) == 1, f"Expected exactly one attestation result, got {len(gate6)}"
        assert gate6[0].passed is True

    def test_l4_contract_gate_forwards_package_wave_identity(self):
        package = self._make_package()
        package.update({
            "wave_name": "test-wave",
            "wave_class": "L4_STRUCTURAL",
            "changed_files": ["mu/host/js/engine/pipeline.js"],
        })
        invoked_commands = []

        def mock_run_validation(repo_root, cmd, **kw):
            invoked_commands.append([str(c) for c in cmd])
            return 0, "passed"

        with patch.object(meta, "run_validation_command", side_effect=mock_run_validation), \
             patch.object(meta, "check_dirty_state", return_value=meta.ValidationResult("dirty_state", True)), \
             patch.object(meta, "check_deferred_blockers", return_value=meta.ValidationResult("deferred_blockers", True)), \
             patch.object(meta, "check_tasks_authorization", return_value=meta.ValidationResult("tasks_auth", True)):
            results, all_passed = meta.run_validation_gates(
                REPO_ROOT, package, verbose=False, skip_startup_gates=True
            )

        assert any(r.name == "L4 contract" and r.passed for r in results)
        assert all_passed is True
        assert invoked_commands[0] == [
            "python3",
            "tools/checks/enforce_l4_execution_contract.py",
            "--wave-class",
            "L4_STRUCTURAL",
            "--wave-id",
            "test-wave",
            "--files",
            "mu/host/js/engine/pipeline.js",
        ]

    def test_l4_contract_gate_uses_package_scope_for_classless_runtime_override(self):
        package = self._make_package()
        package.update({
            "wave_name": "comment-only-wave",
            "wave_class": "",
            "changed_files": ["mu/host/js/core/constants.js"],
        })
        invoked_commands = []

        def mock_run_validation(repo_root, cmd, **kw):
            invoked_commands.append([str(c) for c in cmd])
            return 0, "passed"

        with patch.object(meta, "run_validation_command", side_effect=mock_run_validation), \
             patch.object(meta, "check_dirty_state", return_value=meta.ValidationResult("dirty_state", True)), \
             patch.object(meta, "check_deferred_blockers", return_value=meta.ValidationResult("deferred_blockers", True)), \
             patch.object(meta, "check_tasks_authorization", return_value=meta.ValidationResult("tasks_auth", True)):
            results, all_passed = meta.run_validation_gates(
                REPO_ROOT, package, verbose=False, skip_startup_gates=True
            )

        assert any(r.name == "L4 contract" and r.passed for r in results)
        assert all_passed is True
        assert invoked_commands[0] == [
            "python3",
            "tools/checks/enforce_l4_execution_contract.py",
            "--wave-id",
            "comment-only-wave",
            "--files",
            "mu/host/js/core/constants.js",
        ]

    def test_l4_contract_gate_uses_package_scope_for_enabler_runtime_override(self):
        package = self._make_package()
        package.update({
            "wave_name": "comment-only-tooling-wave",
            "wave_class": "L4_ENABLER",
            "changed_files": [
                "mu/host/js/core/constants.js",
            ],
        })
        invoked_commands = []

        def mock_run_validation(repo_root, cmd, **kw):
            invoked_commands.append([str(c) for c in cmd])
            return 0, "passed"

        with patch.object(meta, "run_validation_command", side_effect=mock_run_validation), \
             patch.object(meta, "check_dirty_state", return_value=meta.ValidationResult("dirty_state", True)), \
             patch.object(meta, "check_deferred_blockers", return_value=meta.ValidationResult("deferred_blockers", True)), \
             patch.object(meta, "check_tasks_authorization", return_value=meta.ValidationResult("tasks_auth", True)):
            results, all_passed = meta.run_validation_gates(
                REPO_ROOT, package, verbose=False, skip_startup_gates=True
            )

        assert any(r.name == "L4 contract" and r.passed for r in results)
        assert all_passed is True
        assert invoked_commands[0] == [
            "python3",
            "tools/checks/enforce_l4_execution_contract.py",
            "--wave-class",
            "L4_ENABLER",
            "--wave-id",
            "comment-only-tooling-wave",
            "--files",
            "mu/host/js/core/constants.js",
        ]

    def test_gate6_runs_when_skip_startup_gates_false(self):
        """Gate 6 (attestation) must call founder_session_attest.sh
        when skip_startup_gates=False (default)."""
        package = self._make_package()
        invoked_commands = []

        def mock_run_validation(repo_root, cmd, **kw):
            cmd_str = " ".join(str(c) for c in cmd)
            invoked_commands.append(cmd_str)
            return 0, "passed"

        with patch.object(meta, "run_validation_command", side_effect=mock_run_validation), \
             patch.object(meta, "check_dirty_state", return_value=meta.ValidationResult("dirty_state", True)), \
             patch.object(meta, "check_deferred_blockers", return_value=meta.ValidationResult("deferred_blockers", True)), \
             patch.object(meta, "check_tasks_authorization", return_value=meta.ValidationResult("tasks_auth", True)):
            results, all_passed = meta.run_validation_gates(
                REPO_ROOT, package, verbose=True, skip_startup_gates=False
            )

        # Attestation script MUST appear in invoked commands.
        attest_cmds = [c for c in invoked_commands if "founder_session_attest" in c]
        assert len(attest_cmds) == 1, (
            f"Gate 6 must invoke founder_session_attest.sh when skip_startup_gates=False. "
            f"Invoked: {invoked_commands}"
        )

    def test_all_gates_still_produce_results_when_skipping(self):
        """All 8+ gates must produce results even when startup gates are skipped."""
        package = self._make_package()

        def mock_run_validation(repo_root, cmd, **kw):
            return 0, "passed"

        with patch.object(meta, "run_validation_command", side_effect=mock_run_validation), \
             patch.object(meta, "check_dirty_state", return_value=meta.ValidationResult("dirty_state", True)), \
             patch.object(meta, "check_deferred_blockers", return_value=meta.ValidationResult("deferred_blockers", True)), \
             patch.object(meta, "check_tasks_authorization", return_value=meta.ValidationResult("tasks_auth", True)):
            results, all_passed = meta.run_validation_gates(
                REPO_ROOT, package, verbose=False, skip_startup_gates=True
            )

        # Must have at least 8 gate results.
        assert len(results) >= 8, (
            f"Expected at least 8 gate results, got {len(results)}: "
            f"{[r.name for r in results]}"
        )
        assert all_passed is True


def _tracker_note_with_evidence(command: str | None) -> str:
    evidence_part = (
        f"evidence_command: `{command}`. "
        if command is not None
        else ""
    )
    return (
        "- Tracker sync note (2026-06-05, test-wave): "
        "**NEXT-CODEX-POST-REDTEAM -- test.**. "
        "Class: L4_ENABLER. target_gate_id: G8. "
        "Packet: `reports/control_plane/test.md`. "
        f"{evidence_part}"
        "evidence_delta: test. progress_proof_before: before. "
        "progress_proof_after: after. "
        "FOUNDER_OVERRIDE:test-wave. primary_blocker_class: INTEGRATION. "
        "primary_invariant_id: INV_TYPED_FAIL_CLOSED_OUTCOMES. "
        "indicator_artifact_ref: reports/l4_wave_indicators/test-wave.json. "
        "indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py "
        "--wave-id test-wave --output reports/l4_wave_indicators/test-wave.json. "
        "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
        "boot0_track_id: V1. boot0_progress_state: HOLD."
    )


def _make_wave_evidence_package(
    *,
    tracker_command: str | None,
    package_command: str | None,
    changed_files: list[str] | None = None,
) -> dict[str, Any]:
    package = _make_valid_package()
    package.update({
        "wave_name": "test-wave",
        "wave_class": "L4_ENABLER",
        "changed_files": changed_files or ["docs/test-wave.md"],
        "tracker_note_text": _tracker_note_with_evidence(tracker_command),
    })
    if package_command is not None:
        package["evidence_command"] = package_command
    else:
        package.pop("evidence_command", None)
    return package


def _run_validation_gates_for_wave_evidence(
    package: dict[str, Any],
    run_validation,
    *,
    repo_root: Path,
) -> tuple[list[meta.ValidationResult], bool]:
    with patch.object(meta, "run_validation_command", side_effect=run_validation), \
         patch.object(meta, "check_dirty_state", return_value=meta.ValidationResult("dirty_state", True)), \
         patch.object(meta, "check_deferred_blockers", return_value=meta.ValidationResult("deferred_blockers", True)), \
         patch.object(meta, "check_tasks_authorization", return_value=meta.ValidationResult("tasks_auth", True)):
        return meta.run_validation_gates(
            repo_root,
            package,
            verbose=False,
            skip_startup_gates=True,
        )


@pytest.fixture
def wave_evidence_repo(tmp_path):
    """Per-test isolated git repo for the wave_evidence gate tests.

    Mirrors the isolated pattern proven by
    ``test_evidence_restore_preserves_unstaged_tracked_and_preexisting_untracked``:
    a minimal tmp git repo (``git init`` + user config + one committed tracked
    file) with its OWN repo_root and its OWN meta_bridge.lock. Routing every
    wave_evidence test through this fixture keeps the supervisor's
    ``_run_wave_evidence_with_restore`` snapshot/restore + lock off the live
    REPO_ROOT, so concurrent ``-n auto`` workers never transiently unlink the
    live ``mu/host/js`` sources nor contend on REPO_ROOT's meta_bridge.lock.
    ``tmp_path`` is unique per test, so each test gets an independent repo and
    lock that pytest auto-cleans.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    tracked = repo / "tracked.txt"
    tracked.write_text("committed\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True, text=True)
    return repo


class TestWaveEvidenceGate:
    def test_matching_declared_and_provided_shell_command_runs_exact_bash_c_once(self, wave_evidence_repo):
        command = "ENV_FLAG=1 python3 -c 'print(1)' && echo done"
        package = _make_wave_evidence_package(
            tracker_command=command,
            package_command=command,
        )
        invoked_commands = []

        def mock_run_validation(repo_root, cmd, **kw):
            invoked_commands.append([str(part) for part in cmd])
            return 0, "passed"

        results, all_passed = _run_validation_gates_for_wave_evidence(
            package,
            mock_run_validation,
            repo_root=wave_evidence_repo,
        )

        evidence_calls = [
            cmd for cmd in invoked_commands
            if cmd == ["bash", "-c", command]
        ]
        assert evidence_calls == [["bash", "-c", command]]
        gate = next(r for r in results if r.name == "wave_evidence")
        assert gate.passed
        assert all_passed

    def test_tracker_declared_evidence_preserves_marker_text_inside_shell_command(self, wave_evidence_repo):
        command = "true && echo evidence_delta: should_not_be_truncated"
        package = _make_wave_evidence_package(
            tracker_command=command,
            package_command=command,
        )
        invoked_commands = []

        def mock_run_validation(repo_root, cmd, **kw):
            invoked_commands.append([str(part) for part in cmd])
            return 0, "passed"

        results, all_passed = _run_validation_gates_for_wave_evidence(
            package,
            mock_run_validation,
            repo_root=wave_evidence_repo,
        )

        assert ["bash", "-c", command] in invoked_commands
        gate = next(r for r in results if r.name == "wave_evidence")
        assert gate.passed
        assert all_passed

    def test_matching_declared_and_provided_nonzero_forces_needs_phase_b(self, pkg_in_repo, wave_evidence_repo):
        command = "echo fail && exit 7"
        package = _make_wave_evidence_package(
            tracker_command=command,
            package_command=command,
        )

        def mock_run_validation(repo_root, cmd, **kw):
            if [str(part) for part in cmd] == ["bash", "-c", command]:
                return 7, "evidence failed"
            return 0, "passed"

        results, all_passed = _run_validation_gates_for_wave_evidence(
            package,
            mock_run_validation,
            repo_root=wave_evidence_repo,
        )

        gate = next(r for r in results if r.name == "wave_evidence")
        assert not gate.passed
        assert "evidence failed" in gate.error
        assert not all_passed

        pkg_path, isolated_paths = pkg_in_repo
        failed_results = _make_validation_results(
            passed_names=["dirty_state"],
            failed_names_errors=[("wave_evidence", "evidence failed")],
        )
        with patch.object(meta, "compute_repo_state", return_value=_FAKE_STATE), \
             patch.object(meta, "run_validation_gates", return_value=(failed_results, False)), \
             patch.object(meta, "run_meta_review") as mock_review, \
             patch.object(meta, "meta_bridge_paths", return_value=isolated_paths), \
             patch.object(meta, "ensure_not_agent_review_mode", return_value=None):
            response = meta.run_meta_bridge(pkg_path, dry_run=False)

        mock_review.assert_not_called()
        assert response.status == "partial"
        assert response.decision == "NEEDS_PHASE_B"
        assert "wave_evidence failed before commit" in response.summary

    def test_declared_but_omitted_fails_closed_without_evidence_run(self, wave_evidence_repo):
        command = "echo should-not-run"
        package = _make_wave_evidence_package(
            tracker_command=command,
            package_command=None,
        )
        invoked_commands = []

        def mock_run_validation(repo_root, cmd, **kw):
            invoked_commands.append([str(part) for part in cmd])
            return 0, "passed"

        results, all_passed = _run_validation_gates_for_wave_evidence(
            package,
            mock_run_validation,
            repo_root=wave_evidence_repo,
        )

        assert ["bash", "-c", command] not in invoked_commands
        gate = next(r for r in results if r.name == "wave_evidence")
        assert not gate.passed
        assert gate.error == "tracker note declares evidence_command but package omitted it"
        assert not all_passed

    def test_provided_but_not_declared_fails_closed_without_evidence_run(self, wave_evidence_repo):
        command = "echo should-not-run"
        package = _make_wave_evidence_package(
            tracker_command=None,
            package_command=command,
        )
        invoked_commands = []

        def mock_run_validation(repo_root, cmd, **kw):
            invoked_commands.append([str(part) for part in cmd])
            return 0, "passed"

        results, all_passed = _run_validation_gates_for_wave_evidence(
            package,
            mock_run_validation,
            repo_root=wave_evidence_repo,
        )

        assert ["bash", "-c", command] not in invoked_commands
        gate = next(r for r in results if r.name == "wave_evidence")
        assert not gate.passed
        assert gate.error == "package provided evidence_command but tracker note omitted it"
        assert not all_passed

    def test_provided_but_mismatched_fails_closed_without_evidence_run(self, wave_evidence_repo):
        declared = "echo declared"
        provided = "echo provided"
        package = _make_wave_evidence_package(
            tracker_command=declared,
            package_command=provided,
        )
        invoked_commands = []

        def mock_run_validation(repo_root, cmd, **kw):
            invoked_commands.append([str(part) for part in cmd])
            return 0, "passed"

        results, all_passed = _run_validation_gates_for_wave_evidence(
            package,
            mock_run_validation,
            repo_root=wave_evidence_repo,
        )

        assert ["bash", "-c", declared] not in invoked_commands
        assert ["bash", "-c", provided] not in invoked_commands
        gate = next(r for r in results if r.name == "wave_evidence")
        assert not gate.passed
        assert gate.error == "package evidence_command does not match tracker-declared evidence_command"
        assert not all_passed

    def test_not_declared_and_not_provided_skips_wave_evidence(self, wave_evidence_repo):
        package = _make_wave_evidence_package(
            tracker_command=None,
            package_command=None,
        )
        invoked_commands = []

        def mock_run_validation(repo_root, cmd, **kw):
            invoked_commands.append([str(part) for part in cmd])
            return 0, "passed"

        results, all_passed = _run_validation_gates_for_wave_evidence(
            package,
            mock_run_validation,
            repo_root=wave_evidence_repo,
        )

        assert not any(cmd[:2] == ["bash", "-c"] for cmd in invoked_commands)
        assert not any(r.name == "wave_evidence" for r in results)
        assert all_passed

    def test_non_control_surface_package_still_runs_wave_evidence(self, wave_evidence_repo):
        command = "echo non-control-surface"
        package = _make_wave_evidence_package(
            tracker_command=command,
            package_command=command,
            changed_files=["docs/non-control-surface.md"],
        )
        invoked_commands = []

        def mock_run_validation(repo_root, cmd, **kw):
            invoked_commands.append([str(part) for part in cmd])
            return 0, "passed"

        results, all_passed = _run_validation_gates_for_wave_evidence(
            package,
            mock_run_validation,
            repo_root=wave_evidence_repo,
        )

        assert ["bash", "-c", command] in invoked_commands
        gate = next(r for r in results if r.name == "wave_evidence")
        assert gate.passed
        assert all_passed

    def test_evidence_restore_is_guarded_by_supervisor_lock(self, tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        repo.mkdir()
        # Bounded-wait: the held lock makes __enter__ wait then fail closed; drive
        # a tiny timeout so the propagation path stays fast and deterministic.
        monkeypatch.setattr(meta, "META_LOCK_WAIT_TIMEOUT_S", 0.3)
        monkeypatch.setattr(meta, "META_LOCK_WAIT_BACKOFF_MS", 20)
        command = "echo should-not-run"
        package = _make_wave_evidence_package(
            tracker_command=command,
            package_command=command,
        )
        invoked_commands = []

        def mock_run_validation(repo_root, cmd, **kw):
            invoked_commands.append([str(part) for part in cmd])
            return 0, "passed"

        paths = meta.meta_bridge_paths(repo)
        paths.lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_fp = open(paths.lock_path, "w")
        try:
            fcntl.flock(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(meta, "meta_bridge_paths", return_value=paths):
                # Lock contention must PROPAGATE as a MetaBridgeError so the caller's
                # wait_for_lock_seconds retry loop (run_meta_bridge_package) can wait and
                # retry, NOT become a failed wave_evidence gate that would falsely route a
                # healthy wave to NEEDS_PHASE_B (#54 / PR #1082 bot P2).
                with pytest.raises(
                    meta.MetaBridgeError, match="Another meta-bridge supervisor is running"
                ):
                    _run_validation_gates_for_wave_evidence(
                        package,
                        mock_run_validation,
                        repo_root=repo,
                    )
        finally:
            fcntl.flock(lock_fp, fcntl.LOCK_UN)
            lock_fp.close()

        # The evidence command must not have run — the lock blocked it before run_validation_command.
        assert ["bash", "-c", command] not in invoked_commands

    def test_evidence_restore_preserves_unstaged_tracked_and_preexisting_untracked(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)

        tracked = repo / "tracked.txt"
        tracked.write_text("committed\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True, text=True)

        tracked.write_text("preexisting unstaged\n", encoding="utf-8")
        preexisting = repo / "preexisting.sh"
        preexisting.write_text("preexisting untracked\n", encoding="utf-8")
        os.chmod(preexisting, 0o755)
        target_before = repo / "target-before.txt"
        target_before.write_text("target before\n", encoding="utf-8")
        link = repo / "preexisting.link"
        os.symlink("target-before.txt", link)

        pre_state = meta.compute_repo_state(repo)
        pre_cached = subprocess.run(
            ["git", "diff", "--cached", "--binary"],
            cwd=repo,
            check=True,
            capture_output=True,
        ).stdout
        command = "MUTATE=1 sh -c 'echo mutating' && echo done"
        package = _make_wave_evidence_package(
            tracker_command=command,
            package_command=command,
            changed_files=["docs/non-control-surface.md"],
        )

        def mock_run_validation(repo_root, cmd, **kw):
            if [str(part) for part in cmd] == ["bash", "-c", command]:
                tracked.write_text("evidence changed tracked\n", encoding="utf-8")
                subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
                (repo / "created-by-evidence.txt").write_text("new\n", encoding="utf-8")
                (repo / "evidence-empty-dir").mkdir()
                preexisting.write_text("evidence changed untracked\n", encoding="utf-8")
                os.chmod(preexisting, 0o644)
                target_before.unlink()
                link.unlink()
                (repo / "target-after.txt").write_text("target after\n", encoding="utf-8")
                os.symlink("target-after.txt", link)
                return 0, "evidence mutated worktree"
            return 0, "passed"

        results, all_passed = _run_validation_gates_for_wave_evidence(
            package,
            mock_run_validation,
            repo_root=repo,
        )

        gate = next(r for r in results if r.name == "wave_evidence")
        assert gate.passed
        assert all_passed
        post_cached = subprocess.run(
            ["git", "diff", "--cached", "--binary"],
            cwd=repo,
            check=True,
            capture_output=True,
        ).stdout
        assert post_cached == pre_cached
        assert tracked.read_text(encoding="utf-8") == "preexisting unstaged\n"
        assert not (repo / "created-by-evidence.txt").exists()
        assert not (repo / "evidence-empty-dir").exists()
        assert preexisting.read_text(encoding="utf-8") == "preexisting untracked\n"
        assert os.stat(preexisting).st_mode & 0o777 == 0o755
        assert target_before.read_text(encoding="utf-8") == "target before\n"
        assert link.is_symlink()
        assert os.readlink(link) == "target-before.txt"
        assert not (repo / "target-after.txt").exists()
        assert meta.compute_repo_state(repo) == pre_state


class TestCheckTasksAuthorizationFounderOverride:
    """Gate 8 FOUNDER_OVERRIDE branch: non-structural waves with an
    externally-validated override token may auto-pass Gate 8
    even when task_id lacks a live NOW/NEXT anchor."""

    def _write_tasks_without_wave_local_id(self, repo_dir, *, founder_override: str | None = None):
        """Fixture: TASKS.md has NOW/NEXT but not [WAVE-LOCAL-ID]."""
        tracker = ""
        if founder_override:
            tracker = (
                "- Tracker sync note (2026-04-21, test-wave): "
                "**TEST-WAVE — bounded override.** "
                "Class: L4_ENABLER. "
                "target_gate_id: G8. "
                f"FOUNDER_OVERRIDE:{founder_override}. "
                "primary_blocker_class: INTEGRATION. "
                "primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
                "indicator_artifact_ref: reports/l4_wave_indicators/test-wave.json. "
                "indicator_collection_command: python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id test-wave. "
                "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
                "boot0_track_id: V1. "
                "boot0_progress_state: HOLD.\n\n"
            )
        (repo_dir / "TASKS.md").write_text(
            tracker +
            "## NOW\n\n"
            "- **[OTHER-TASK]** **NOW** (unrelated).\n"
            "  Unrelated body.\n\n"
            "## NEXT\n\n"
            "- **[OTHER-NEXT]** **NEXT** (unrelated).\n"
            "  Unrelated body.\n",
            encoding="utf-8",
        )

    def test_check_tasks_authorization_passes_when_external_override_validator_exits_zero_non_structural(
        self, tmp_path, monkeypatch
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        self._write_tasks_without_wave_local_id(
            repo,
            founder_override="test-wave-restart-branch-continuation",
        )

        monkeypatch.setattr(
            meta,
            "_run_external_override_validator",
            lambda repo_root, wave_name, wave_class: (0, ""),
        )

        result = meta.check_tasks_authorization(
            repo,
            "[WAVE-LOCAL-ID]",
            founder_override_token="FOUNDER_OVERRIDE:test-wave-restart-branch-continuation",
            wave_name="test-wave",
            wave_class="L4_ENABLER",
        )

        assert result.passed is True
        assert "FOUNDER_OVERRIDE" in result.name

    def test_check_tasks_authorization_accepts_continuation_specific_override_ids(
        self, tmp_path, monkeypatch
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        self._write_tasks_without_wave_local_id(
            repo,
            founder_override="test-wave-restart-branch-continuation",
        )

        calls = []

        def stub_validator(repo_root, wave_name, wave_class):
            calls.append((repo_root, wave_name, wave_class))
            return (0, "")

        monkeypatch.setattr(
            meta,
            "_run_external_override_validator",
            stub_validator,
        )

        result = meta.check_tasks_authorization(
            repo,
            "[WAVE-LOCAL-ID]",
            founder_override_token="FOUNDER_OVERRIDE:test-wave-restart-branch-continuation",
            wave_name="test-wave",
            wave_class="L4_ENABLER",
        )
        assert result.passed is True
        assert "FOUNDER_OVERRIDE" in result.name
        assert calls == [(repo, "test-wave", "L4_ENABLER")]

    def test_check_tasks_authorization_falls_through_when_package_token_mismatches_staged_tracker_token(
        self, tmp_path, monkeypatch
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        self._write_tasks_without_wave_local_id(
            repo,
            founder_override="test-wave-tracker-token",
        )

        calls = []

        def stub_validator(repo_root, wave_name, wave_class):
            calls.append((repo_root, wave_name, wave_class))
            return (0, "")

        monkeypatch.setattr(
            meta,
            "_run_external_override_validator",
            stub_validator,
        )
        result = meta.check_tasks_authorization(
            repo,
            "[WAVE-LOCAL-ID]",
            founder_override_token="FOUNDER_OVERRIDE:test-wave-package-token",
            wave_name="test-wave",
            wave_class="L4_ENABLER",
        )
        assert result.passed is False
        assert "not found in active NOW or NEXT" in (result.error or "")
        assert calls == []

    def test_check_tasks_authorization_falls_through_when_override_validator_fails(
        self, tmp_path, monkeypatch
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        self._write_tasks_without_wave_local_id(
            repo,
            founder_override="test-wave-restart-branch-continuation",
        )

        monkeypatch.setattr(
            meta,
            "_run_external_override_validator",
            lambda repo_root, wave_name, wave_class: (1, "boom"),
        )
        result = meta.check_tasks_authorization(
            repo,
            "[WAVE-LOCAL-ID]",
            founder_override_token="FOUNDER_OVERRIDE:test-wave-restart-branch-continuation",
            wave_name="test-wave",
            wave_class="L4_ENABLER",
        )
        assert result.passed is False
        assert "not found in active NOW or NEXT" in (result.error or "")

    def test_check_tasks_authorization_refuses_override_for_l4_structural(
        self, tmp_path, monkeypatch
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        self._write_tasks_without_wave_local_id(
            repo,
            founder_override="test-wave",
        )

        calls = []

        def stub_validator(repo_root, wave_name, wave_class):
            calls.append((repo_root, wave_name, wave_class))
            return (0, "")

        monkeypatch.setattr(meta, "_run_external_override_validator", stub_validator)

        result = meta.check_tasks_authorization(
            repo,
            "[WAVE-LOCAL-ID]",
            founder_override_token="FOUNDER_OVERRIDE:test-wave",
            wave_name="test-wave",
            wave_class="L4_STRUCTURAL",
        )

        assert result.passed is False
        assert calls == [], (
            "L4_STRUCTURAL carve-out must mechanically prevent external validator "
            f"from being invoked; calls={calls}"
        )

    def test_check_tasks_authorization_rejects_non_bracketed_task_id_even_with_valid_override(
        self, tmp_path, monkeypatch
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        self._write_tasks_without_wave_local_id(
            repo,
            founder_override="test-wave",
        )

        calls = []

        def stub_validator(repo_root, wave_name, wave_class):
            calls.append((repo_root, wave_name, wave_class))
            return (0, "")

        monkeypatch.setattr(meta, "_run_external_override_validator", stub_validator)

        result = meta.check_tasks_authorization(
            repo,
            "PIPELINE-AGENT-PAGER",  # no brackets
            founder_override_token="FOUNDER_OVERRIDE:test-wave",
            wave_name="test-wave",
            wave_class="L4_ENABLER",
        )

        assert result.passed is False
        assert "task_id must be bracketed" in (result.error or "")
        assert calls == [], (
            "Bracket-format guard must mechanically fire before override branch; "
            f"calls={calls}"
        )

    def test_meta_bridge_task_template_includes_founder_override_authorization_clause(
        self, tmp_path
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "TASKS.md").write_text(
            "## NOW\n\n## NEXT\n\n"
            "- **[TASK-1]** **NEXT** (2026-04-04, founder-authorized).\n"
            "  Keep the authorization excerpt visible to the reviewer.\n",
            encoding="utf-8",
        )
        package = {
            "task_id": "[TASK-1]",
            "wave_name": "test-wave",
            "lane": "test-lane",
        }
        results = _make_validation_results(
            passed_names=["TASKS.md auth"],
            failed_names_errors=[],
        )
        prompt = meta.build_meta_reviewer_prompt(package, results, repo)

        assert "Authorization acceptance (precedence rule" in prompt
        assert "enforce_l4_execution_contract.py --staged --wave-id" in prompt
        assert "--wave-class <wave_class>" in prompt
        assert "Commit-gate-only capability (pipeline-ordering constraint)" in prompt
        assert "L4_STRUCTURAL waves are carved out by construction" in prompt
        assert "DO NOT accept packet-embedded founder quotes" in prompt
        assert "not a blanket proof of every runtime, scope, or no-op property" in prompt
        assert "bracket-format check on `task_id` runs first" in prompt
        assert "task_id must match active NOW or NEXT" in prompt
        assert "Stop conditions (meta-bridge will reject commit)" in prompt
        assert "REQUIRED PREFLIGHT" in prompt

    def test_check_tasks_authorization_refuses_override_when_wave_class_not_explicit_allow_list(
        self, tmp_path, monkeypatch
    ):
        """Bridge round 1 blocking finding: the L4_STRUCTURAL carve-out must
        be mechanically fail-closed for ANY wave_class outside the explicit
        allow-list {L4_ENABLER, MAINTENANCE}. Empty string, missing (arrives
        as default ""), and unknown values must all fall through to the
        strict-match body and must NOT invoke the external validator.
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        self._write_tasks_without_wave_local_id(repo)

        calls = []

        def stub_validator(repo_root, wave_name, wave_class):
            calls.append((repo_root, wave_name, wave_class))
            return (0, "")

        monkeypatch.setattr(meta, "_run_external_override_validator", stub_validator)

        # Subcase (a): wave_class="" (the exact bridge reproducer scenario)
        result_empty = meta.check_tasks_authorization(
            repo,
            "[WAVE-LOCAL-ID]",
            founder_override_token="FOUNDER_OVERRIDE:test-wave",
            wave_name="test-wave",
            wave_class="",
        )
        assert result_empty.passed is False
        assert "not found in active NOW or NEXT" in (result_empty.error or "")

        # Subcase (b): wave_class omitted entirely (default "")
        result_missing = meta.check_tasks_authorization(
            repo,
            "[WAVE-LOCAL-ID]",
            founder_override_token="FOUNDER_OVERRIDE:test-wave",
            wave_name="test-wave",
            # wave_class defaulted to ""
        )
        assert result_missing.passed is False
        assert "not found in active NOW or NEXT" in (result_missing.error or "")

        # Subcase (c): wave_class unknown value
        result_unknown = meta.check_tasks_authorization(
            repo,
            "[WAVE-LOCAL-ID]",
            founder_override_token="FOUNDER_OVERRIDE:test-wave",
            wave_name="test-wave",
            wave_class="UNKNOWN_CLASS",
        )
        assert result_unknown.passed is False
        assert "not found in active NOW or NEXT" in (result_unknown.error or "")

        # Allow-list is mechanical: validator MUST NEVER be invoked for any of
        # the above subcases. This proves the fail-closed property at the code
        # level (not just at the result level).
        assert calls == [], (
            "wave_class allow-list must mechanically prevent external "
            f"validator invocation for empty/missing/unknown values; calls={calls}"
        )

    def test_validate_package_schema_rejects_founder_override_without_explicit_allow_list_wave_class(
        self,
    ):
        """Schema cross-field: a non-empty founder_override_token paired with
        an omitted, empty, L4_STRUCTURAL, or unknown wave_class must fail
        schema validation. Defense in depth for the Gate 8 allow-list —
        catches malformed packages before Gate 8 runs.
        """
        base = {
            "task_id": "[TASK-1]",
            "wave_name": "test-wave",
            "lane": "lane",
            "changed_files": [],
            "scope_items": [],
            "fixes_implemented": [],
            "deferred_items": [],
            "bridge_status": {},
            "evidence_handles": {},
            "blocker_report_paths": [],
            "current_judgment": "COMMIT_GO",
            "founder_override_token": "FOUNDER_OVERRIDE:test-wave",
        }

        # Subcase (a): wave_class omitted entirely
        valid_missing, errors_missing = meta.validate_package_schema(dict(base))
        assert valid_missing is False
        assert any(
            "founder_override_token requires wave_class" in e for e in errors_missing
        ), f"expected schema error about wave_class requirement, got {errors_missing}"

        # Subcase (b): wave_class empty string
        pkg_empty = dict(base, wave_class="")
        valid_empty, errors_empty = meta.validate_package_schema(pkg_empty)
        assert valid_empty is False
        assert any(
            "founder_override_token requires wave_class" in e for e in errors_empty
        )

        # Subcase (c): wave_class="L4_STRUCTURAL" (structural cannot smuggle override)
        pkg_struct = dict(base, wave_class="L4_STRUCTURAL")
        valid_struct, errors_struct = meta.validate_package_schema(pkg_struct)
        assert valid_struct is False
        assert any(
            "founder_override_token requires wave_class" in e for e in errors_struct
        )

        # Subcase (d): wave_class="L4_ENABLER" (legit override) passes
        pkg_enabler = dict(base, wave_class="L4_ENABLER")
        valid_enabler, errors_enabler = meta.validate_package_schema(pkg_enabler)
        assert valid_enabler is True, (
            f"legit L4_ENABLER package must pass schema; errors={errors_enabler}"
        )

        # Subcase (e): wave_class="MAINTENANCE" (legit override) passes
        pkg_maint = dict(base, wave_class="MAINTENANCE")
        valid_maint, errors_maint = meta.validate_package_schema(pkg_maint)
        assert valid_maint is True, (
            f"legit MAINTENANCE package must pass schema; errors={errors_maint}"
        )

        # Subcase (f): no override token at all — wave_class constraint does NOT apply
        pkg_no_override = dict(base)
        pkg_no_override.pop("founder_override_token")
        valid_no_ovr, errors_no_ovr = meta.validate_package_schema(pkg_no_override)
        assert valid_no_ovr is True, (
            f"package without override must not trigger cross-field check; "
            f"errors={errors_no_ovr}"
        )

        # Subcase (g): empty string override token — cross-field also does NOT apply
        pkg_empty_tok = dict(base, founder_override_token="", wave_class="")
        valid_empty_tok, errors_empty_tok = meta.validate_package_schema(pkg_empty_tok)
        assert valid_empty_tok is True, (
            f"empty token + empty wave_class must pass (producer default); "
            f"errors={errors_empty_tok}"
        )


class TestCommitSupervisorNeedsPhaseBRouting:
    def test_commit_supervisor_needs_phase_b_payload_preserves_full_evidence_detail(self):
        summary = (
            "wave_evidence failed before commit; routing to Phase B for rework. "
            "pytest session starts here\n"
            + ("x" * 260)
            + "\nFAILED mu/tests/tools/test_meta_bridge_supervisor.py::test_example "
            "- assertion details survive"
        )
        result = commit_mod._commit_supervisor_rejection_result(  # ANTICHEAT_OK: locks Step 6 NEEDS_PHASE_B routing payload
            decision="NEEDS_PHASE_B",
            summary=summary,
            steps_completed=["validate_inputs", "restore_commit_retry_state"],
            handoff={
                "tracked_packet": (
                    "reports/control_plane/"
                    "supervisor_run_wave_evidence_trusted_v8_2026-06-05.md"
                ),
            },
            wave_id="supervisor-run-wave-evidence-trusted-v8-2026-06-05",
            changed_files=["mu/tests/tools/test_meta_bridge_supervisor.py"],
        )

        assert result["status"] == "error"
        assert result["failure_class"] == "needs_phase_b"
        assert result["resume_after"] == "needs_phase_b_reentry"
        assert result["plan_path"] == (
            "reports/control_plane/"
            "supervisor_run_wave_evidence_trusted_v8_2026-06-05.md"
        )
        assert result["pre_commit_decision"] == "NEEDS_PHASE_B"
        assert "assertion details survive" in result["errors"][0]
        assert "assertion details survive" in result["reason"]

    def test_commit_supervisor_needs_phase_b_is_standalone_recoverable(self):
        result = commit_mod._commit_supervisor_rejection_result(  # ANTICHEAT_OK: locks Step 6 NEEDS_PHASE_B recovery routing
            decision="NEEDS_PHASE_B",
            summary="wave_evidence failed before commit",
            steps_completed=["restore_commit_retry_state"],
            handoff={
                "tracked_packet": (
                    "reports/control_plane/"
                    "supervisor_run_wave_evidence_trusted_v8_2026-06-05.md"
                ),
            },
            wave_id="supervisor-run-wave-evidence-trusted-v8-2026-06-05",
            changed_files=["mu/tests/tools/test_meta_bridge_supervisor.py"],
        )

        assert commit_mod._should_attempt_standalone_recovery(result)  # ANTICHEAT_OK: recovery classifier guard

    def test_commit_retry_demotion_accepts_needs_phase_b_status_before_git_commit(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)

        wave_id = "supervisor-run-wave-evidence-trusted-v8-2026-06-05"
        packet_rel = "reports/control_plane/supervisor_run_wave_evidence_trusted_v8_2026-06-05.md"
        packet_path = repo / packet_rel
        packet_path.parent.mkdir(parents=True)
        packet_path.write_text(
            "# Packet\n\n"
            f"Status: {commit_mod.COMMIT_RETRY_RESTORED_STATUS}\n"
            f"Wave ID: {wave_id}\n",
            encoding="utf-8",
        )
        tasks_path = repo / "TASKS.md"
        tasks_path.write_text(
            "## Ra\n"
            "  6. **[FOUNDER-ORDERED-REDTEAM-WAVE-EVIDENCE] "
            f"{commit_mod.COMMIT_RETRY_RESTORED_STATUS} (2026-06-05).** "
            "Task: `[NEXT-CODEX-POST-REDTEAM]`. "
            f"Wave ID: `{wave_id}`. "
            f"Packet: `{packet_rel}`.\n",
            encoding="utf-8",
        )
        result = {
            "status": "needs_phase_b",
            "step": "build_and_run_supervisor",
            "errors": ["Supervisor returned NEEDS_PHASE_B: wave_evidence failed"],
            "steps_completed": [
                "validate_inputs",
                "ensure_feature_branch",
                "restore_commit_retry_state",
            ],
        }

        commit_mod._maybe_demote_completed_handoff_state_for_commit_retry(  # ANTICHEAT_OK: locks retry-state demotion guard
            repo_root=repo,
            handoff={"wave_id": wave_id, "tracked_packet": packet_rel},
            result=result,
        )

        assert set(result["commit_retry_state_demotion"]["changed"]) == {
            packet_rel,
            "TASKS.md",
        }
        assert (
            f"Status: {commit_mod.COMMIT_RETRY_PENDING_STATUS}"
            in packet_path.read_text(encoding="utf-8")
        )
        assert (
            f"{commit_mod.COMMIT_RETRY_PENDING_STATUS} / LOCAL EVIDENCE (2026-06-05)"
            in tasks_path.read_text(encoding="utf-8")
        )
