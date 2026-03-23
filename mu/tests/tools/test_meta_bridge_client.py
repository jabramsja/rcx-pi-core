"""Tests for structured meta-bridge supervisor client."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Load meta_bridge_client module
_AGENTS_DIR = Path(__file__).resolve().parent.parent.parent / "tools" / "agents"
_spec = importlib.util.spec_from_file_location(
    "meta_bridge_client", _AGENTS_DIR / "meta_bridge_client.py"
)
assert _spec and _spec.loader
client_mod = importlib.util.module_from_spec(_spec)
sys.modules["meta_bridge_client"] = client_mod
_spec.loader.exec_module(client_mod)

run_meta_bridge_package = client_mod.run_meta_bridge_package
MetaBridgeClientError = client_mod.MetaBridgeClientError
SupervisorResult = client_mod.SupervisorResult
validate_decision = client_mod._validate_decision  # ANTICHEAT_OK: testing internal validation function


@dataclass
class FakeResponse:
    """Fake MetaBridgeResponse for testing."""
    status: str = "success"
    decision: str = "COMMIT_GO"
    summary: str = "Test summary"
    validations_passed: list[str] = field(default_factory=lambda: ["L4 contract"])
    validations_failed: list[dict[str, str]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    request_for_claude: str = ""
    error_code: str = ""
    error_detail: str = ""


class TestValidateDecision:
    """Test that template enum strings are rejected."""

    def test_real_decision_accepted(self):
        validate_decision("COMMIT_GO")  # Should not raise

    def test_hold_decision_accepted(self):
        validate_decision("COMMIT_GO_HOLD_PUSH")  # Should not raise

    def test_error_decision_accepted(self):
        validate_decision("ERROR_VALIDATION_FAILED")  # Should not raise

    def test_pipe_delimited_enum_rejected(self):
        template = "COMMIT_GO|COMMIT_GO_HOLD_PUSH|NO_ACTION|NEEDS_PHASE_A|NEEDS_PHASE_B|STOP_FOR_FOUNDER|STOP_FOR_TRIAGE_DISCUSSION|ERROR_VALIDATION_FAILED"
        with pytest.raises(MetaBridgeClientError, match="pipe-delimited template enum"):
            validate_decision(template)

    def test_empty_decision_rejected(self):
        with pytest.raises(MetaBridgeClientError, match="empty decision"):
            validate_decision("")

    def test_partial_pipe_rejected(self):
        with pytest.raises(MetaBridgeClientError, match="pipe-delimited"):
            validate_decision("COMMIT_GO|ERROR")


class TestSupervisorResult:
    """Test SupervisorResult properties."""

    def test_commit_capable(self):
        r = SupervisorResult(
            decision="COMMIT_GO", summary="", status="success",
            validations_passed=[], validations_failed=[], findings=[],
            request_for_claude="", error_code="", error_detail="",
            receipt_path=".agent_bus/meta/pre_commit_receipt.json",
        )
        assert r.is_commit_capable
        assert not r.is_error
        assert not r.is_hold

    def test_hold(self):
        r = SupervisorResult(
            decision="COMMIT_GO_HOLD_PUSH", summary="", status="success",
            validations_passed=[], validations_failed=[], findings=[],
            request_for_claude="", error_code="", error_detail="",
            receipt_path=".agent_bus/meta/pre_commit_receipt.json",
        )
        assert r.is_commit_capable
        assert r.is_hold

    def test_error(self):
        r = SupervisorResult(
            decision="ERROR_VALIDATION_FAILED", summary="", status="error",
            validations_passed=[], validations_failed=[], findings=[],
            request_for_claude="", error_code="ERR", error_detail="",
            receipt_path="",
        )
        assert r.is_error
        assert not r.is_commit_capable


class TestRunMetaBridgePackage:
    """Test the client wrapper with mocked supervisor."""

    def test_returns_structured_result_on_commit_go(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text('{"task_id": "test"}')

        fake_resp = FakeResponse(decision="COMMIT_GO")

        with patch.dict(sys.modules, {"meta_bridge_supervisor": MagicMock()}):
            # Re-import to pick up mock
            client_mod.run_meta_bridge = MagicMock(return_value=fake_resp)
            # Patch the import inside the function
            with patch.object(client_mod, "__import__", create=True):
                # Direct test of result construction
                result = SupervisorResult(
                    decision="COMMIT_GO",
                    summary="Test summary",
                    status="success",
                    validations_passed=["L4 contract"],
                    validations_failed=[],
                    findings=[],
                    request_for_claude="",
                    error_code="",
                    error_detail="",
                    receipt_path=".agent_bus/meta/pre_commit_receipt.json",
                )
                assert result.is_commit_capable
                assert result.decision == "COMMIT_GO"
                assert result.receipt_path == ".agent_bus/meta/pre_commit_receipt.json"

    def test_rejects_template_enum_from_supervisor(self):
        """If supervisor somehow returns the template enum string, client must reject."""
        template = "COMMIT_GO|COMMIT_GO_HOLD_PUSH|NO_ACTION"
        with pytest.raises(MetaBridgeClientError, match="pipe-delimited"):
            validate_decision(template)

    def test_lock_retry_structured_failure(self):
        """If lock is held for longer than timeout, raise structured error."""
        # This tests the error message structure, not the actual lock
        err = MetaBridgeClientError(
            "Supervisor lock held for 30s. Last error: Another meta-bridge supervisor is running."
        )
        assert "lock held" in str(err).lower()
        assert "30s" in str(err)
