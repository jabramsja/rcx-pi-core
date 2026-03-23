"""Tests for pre-commit receipt writing and verification.

Covers:
1. Receipt written on COMMIT_GO
2. Receipt verifier accepts matching staged state
3. Receipt verifier rejects missing receipt
4. Receipt verifier rejects stale receipt (staged state changed)
5. Receipt not written on non-commit decisions
6. CLAUDE.md contains canonical pre-commit supervisor command
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.repo_root import REPO_ROOT


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_adapters = _load_module(
    "bridge_adapters",
    REPO_ROOT / "mu" / "tools" / "agents" / "bridge_adapters.py",
)
meta = _load_module(
    "meta_bridge_supervisor",
    REPO_ROOT / "mu" / "tools" / "agents" / "meta_bridge_supervisor.py",
)


class TestReceiptWriting:
    """Receipt is written on commit-capable decisions only."""

    def test_receipt_written_on_commit_go(self, tmp_path):
        response = meta.MetaBridgeResponse(
            status="success",
            decision="COMMIT_GO",
            summary="All clear",
        )
        pkg_path = tmp_path / "pkg.json"
        pkg_path.write_text("{}", encoding="utf-8")

        with patch.object(meta, "META_BUS_DIR_NAME", ".agent_bus/meta"), \
             patch.object(meta, "compute_staged_sha", return_value="abc123"):
            path = meta.write_pre_commit_receipt(response, pkg_path, repo_root=tmp_path)

        assert path.exists()
        data = json.loads(path.read_text())
        assert data["decision"] == "COMMIT_GO"
        assert data["staged_sha"] == "abc123"
        assert "timestamp_utc" in data
        assert len(data) == 5  # decision, staged_sha, timestamp_utc, package_digest, package_path

    def test_receipt_written_on_commit_go_hold_push(self, tmp_path):
        response = meta.MetaBridgeResponse(
            status="success",
            decision="COMMIT_GO_HOLD_PUSH",
            summary="Commit locally",
        )
        pkg_path = tmp_path / "pkg.json"
        pkg_path.write_text("{}", encoding="utf-8")

        with patch.object(meta, "META_BUS_DIR_NAME", ".agent_bus/meta"), \
             patch.object(meta, "compute_staged_sha", return_value="def456"):
            path = meta.write_pre_commit_receipt(response, pkg_path, repo_root=tmp_path)

        data = json.loads(path.read_text())
        assert data["decision"] == "COMMIT_GO_HOLD_PUSH"

    def test_receipt_refused_for_non_commit_decision(self):
        response = meta.MetaBridgeResponse(
            status="partial",
            decision="NEEDS_PHASE_B",
            summary="Rework needed",
        )
        with pytest.raises(meta.MetaBridgeError, match="Cannot write receipt"):
            meta.write_pre_commit_receipt(response, Path("/fake"))

    def test_receipt_refused_for_no_action(self):
        response = meta.MetaBridgeResponse(
            status="success",
            decision="NO_ACTION",
            summary="Nothing to do",
        )
        with pytest.raises(meta.MetaBridgeError, match="Cannot write receipt"):
            meta.write_pre_commit_receipt(response, Path("/fake"))


class TestReceiptVerification:
    """Verifier checks receipt existence, freshness, and state match."""

    def _write_receipt(self, repo_root, staged_sha="abc123", decision="COMMIT_GO"):
        receipt_dir = repo_root / ".agent_bus" / "meta"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        receipt = {
            "decision": decision,
            "staged_sha": staged_sha,
            "timestamp_utc": meta.utc_now(),
        }
        receipt_path = receipt_dir / meta.PRE_COMMIT_RECEIPT_NAME
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        return receipt_path

    def test_accepts_matching_state(self, tmp_path):
        self._write_receipt(tmp_path, staged_sha="abc123")
        with patch.object(meta, "META_BUS_DIR_NAME", ".agent_bus/meta"), \
             patch.object(meta, "compute_staged_sha", return_value="abc123"):
            passed, msg = meta.verify_pre_commit_receipt(tmp_path)
        assert passed
        assert "valid" in msg.lower()

    def test_rejects_missing_receipt(self, tmp_path):
        with patch.object(meta, "META_BUS_DIR_NAME", ".agent_bus/meta"):
            passed, msg = meta.verify_pre_commit_receipt(tmp_path)
        assert not passed
        assert "No pre-commit receipt" in msg

    def test_rejects_stale_staged_state(self, tmp_path):
        self._write_receipt(tmp_path, staged_sha="abc123")
        with patch.object(meta, "META_BUS_DIR_NAME", ".agent_bus/meta"), \
             patch.object(meta, "compute_staged_sha", return_value="DIFFERENT"):
            passed, msg = meta.verify_pre_commit_receipt(tmp_path)
        assert not passed
        assert "stale" in msg.lower()

    def test_rejects_non_commit_decision_in_receipt(self, tmp_path):
        self._write_receipt(tmp_path, decision="NEEDS_PHASE_B")
        with patch.object(meta, "META_BUS_DIR_NAME", ".agent_bus/meta"), \
             patch.object(meta, "compute_staged_sha", return_value="abc123"):
            passed, msg = meta.verify_pre_commit_receipt(tmp_path)
        assert not passed
        assert "does not authorize" in msg.lower()

    def test_rejects_expired_receipt(self, tmp_path):
        receipt_dir = tmp_path / ".agent_bus" / "meta"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        receipt = {
            "decision": "COMMIT_GO",
            "staged_sha": "abc123",
            "timestamp_utc": "2020-01-01T00:00:00+00:00",
        }
        (receipt_dir / meta.PRE_COMMIT_RECEIPT_NAME).write_text(json.dumps(receipt))
        with patch.object(meta, "META_BUS_DIR_NAME", ".agent_bus/meta"), \
             patch.object(meta, "compute_staged_sha", return_value="abc123"):
            passed, msg = meta.verify_pre_commit_receipt(tmp_path)
        assert not passed
        assert "too old" in msg.lower()

    def test_rejects_missing_timestamp(self, tmp_path):
        receipt_dir = tmp_path / ".agent_bus" / "meta"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        receipt = {"decision": "COMMIT_GO", "staged_sha": "abc123"}
        (receipt_dir / meta.PRE_COMMIT_RECEIPT_NAME).write_text(json.dumps(receipt))
        with patch.object(meta, "META_BUS_DIR_NAME", ".agent_bus/meta"), \
             patch.object(meta, "compute_staged_sha", return_value="abc123"):
            passed, msg = meta.verify_pre_commit_receipt(tmp_path)
        assert not passed
        assert "no timestamp" in msg.lower()

    def test_rejects_garbage_timestamp(self, tmp_path):
        receipt_dir = tmp_path / ".agent_bus" / "meta"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        receipt = {"decision": "COMMIT_GO", "staged_sha": "abc123", "timestamp_utc": "NOT_A_TIMESTAMP"}
        (receipt_dir / meta.PRE_COMMIT_RECEIPT_NAME).write_text(json.dumps(receipt))
        with patch.object(meta, "META_BUS_DIR_NAME", ".agent_bus/meta"), \
             patch.object(meta, "compute_staged_sha", return_value="abc123"):
            passed, msg = meta.verify_pre_commit_receipt(tmp_path)
        assert not passed
        assert "unparseable" in msg.lower()

    def test_rejects_future_timestamp(self, tmp_path):
        receipt_dir = tmp_path / ".agent_bus" / "meta"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        receipt = {"decision": "COMMIT_GO", "staged_sha": "abc123", "timestamp_utc": "2099-01-01T00:00:00+00:00"}
        (receipt_dir / meta.PRE_COMMIT_RECEIPT_NAME).write_text(json.dumps(receipt))
        with patch.object(meta, "META_BUS_DIR_NAME", ".agent_bus/meta"), \
             patch.object(meta, "compute_staged_sha", return_value="abc123"):
            passed, msg = meta.verify_pre_commit_receipt(tmp_path)
        assert not passed
        assert "future" in msg.lower()


class TestReceiptCapableDecisions:
    """Only COMMIT_GO and COMMIT_GO_HOLD_PUSH can produce receipts."""

    def test_receipt_capable_set(self):
        assert meta.RECEIPT_CAPABLE_DECISIONS == {"COMMIT_GO", "COMMIT_GO_HOLD_PUSH"}

    def test_no_action_not_receipt_capable(self):
        assert "NO_ACTION" not in meta.RECEIPT_CAPABLE_DECISIONS


class TestClaudeMdPreCommitCommand:
    """CLAUDE.md must contain the canonical pre-commit supervisor command."""

    def test_claude_md_has_pre_commit_step(self):
        claude_md = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        # CLAUDE.md should reference the structured client or the commit executor
        assert "meta_bridge_client" in claude_md or "commit_executor" in claude_md
        assert "commit protocol" in claude_md.lower() or "pre-commit" in claude_md.lower()
