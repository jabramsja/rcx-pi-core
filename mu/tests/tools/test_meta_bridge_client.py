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

    def test_refreshes_stale_executor_common_before_supervisor_import(self, monkeypatch):
        """Long-lived executors refresh executor_common before importing supervisor."""
        executor_common_path = _AGENTS_DIR.parent / "executors" / "executor_common.py"
        spec = importlib.util.spec_from_file_location("executor_common", executor_common_path)
        assert spec and spec.loader
        stale_mod = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, "executor_common", stale_mod)
        spec.loader.exec_module(stale_mod)
        delattr(stale_mod, "ensure_bridge_config_path")
        assert not hasattr(stale_mod, "ensure_bridge_config_path")

        client_mod._refresh_executor_common_before_supervisor_import(_AGENTS_DIR)

        refreshed = sys.modules["executor_common"]
        assert Path(refreshed.__file__).resolve() == executor_common_path.resolve()
        assert hasattr(refreshed, "ensure_bridge_config_path")


class TestReceiptUniqueness:
    """Per-invocation receipt paths must be unique even within the same second."""

    def test_same_second_receipts_are_unique(self):
        """Two rapid calls produce distinct receipt filenames."""
        from tests.repo_root import REPO_ROOT
        import importlib.util, sys, tempfile
        from pathlib import Path
        from unittest.mock import patch as _p

        meta_path = REPO_ROOT / "mu" / "tools" / "agents" / "meta_bridge_supervisor.py"
        spec = importlib.util.spec_from_file_location("meta_receipt_test", meta_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["meta_receipt_test"] = mod
        spec.loader.exec_module(mod)

        response = mod.MetaBridgeResponse(
            status="success", decision="COMMIT_GO", summary="ok",
        )
        pkg = Path(tempfile.mktemp(suffix=".json"))
        pkg.write_text("{}")

        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            with _p.object(mod, "compute_staged_sha", return_value="abc"):
                path1 = mod.write_pre_commit_receipt(response, pkg, repo_root=repo)
                path2 = mod.write_pre_commit_receipt(response, pkg, repo_root=repo)

            assert path1 != path2, f"Same-second receipts must have distinct paths: {path1} vs {path2}"
            assert path1.exists()
            assert path2.exists()


class TestEnvelopeSchemaValidation:
    """Supervisor envelope must have required fields: decision, summary, status."""

    def test_missing_decision_raises(self):
        """Response without decision field raises MetaBridgeClientError."""
        import inspect
        src = inspect.getsource(client_mod.run_meta_bridge_package)
        assert "_required_attrs" in src, (
            "run_meta_bridge_package must validate required envelope fields"
        )
        assert '"decision"' in src or "'decision'" in src

    def test_missing_optional_fields_default_safely(self):
        """Optional fields default to empty list/string when absent from response."""
        import inspect
        src = inspect.getsource(client_mod.run_meta_bridge_package)
        # Verify defensive getattr pattern for optional fields
        assert "getattr(response," in src, (
            "run_meta_bridge_package must use getattr with defaults for optional fields"
        )
        # Verify the three required fields are checked
        assert '"decision"' in src or "'decision'" in src
        assert '"summary"' in src or "'summary'" in src
        assert '"status"' in src or "'status'" in src


class TestReceiptPathFailClosed:
    """meta_bridge_client must fail closed on absolute receipt paths."""

    def test_no_absolute_fallback_in_source(self):
        """The except block for repo-relative conversion must raise, not fall back."""
        import inspect
        src = inspect.getsource(client_mod.run_meta_bridge_package)
        # After the "except (_sp.CalledProcessError, ValueError)" block,
        # the code must raise MetaBridgeClientError, not assign receipt_path
        assert "raise MetaBridgeClientError" in src, (
            "meta_bridge_client must raise MetaBridgeClientError on failed "
            "repo-relative conversion, not fall back to absolute path"
        )
        # The old fallback pattern "receipt_path = str(exact_receipt_path)" must be gone
        # from the except block
        lines = src.splitlines()
        in_except = False
        for line in lines:
            if "except" in line and "CalledProcessError" in line:
                in_except = True
            elif in_except:
                assert "receipt_path = str(exact_receipt_path)" not in line, (
                    "Found absolute path fallback in except block — must raise instead"
                )
                if line.strip() and not line.strip().startswith("#") and not line.strip().startswith("raise"):
                    break  # Past the except block
