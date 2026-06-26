"""
L4 Gate: GPT bot findings wave (PR #500 + PR #504) — structural fixes.

Proves:
1. evidence_walker stall fallback exists in engine_pipeline.py (AST proof)
2. Walker stalls on head-only trace nodes (behavioral proof of fix necessity)
3. bridge_supervisor open_db_readonly uses SQLite URI read-only mode (source proof)
4. JS seed_loader verifies checksum BEFORE JSON.parse for known seeds (source proof)

Usage:
    PYTHONHASHSEED=0 pytest mu/tests/l4_gates/test_gpt_findings_wave4_gate.py -v
"""

from __future__ import annotations

import ast

import pytest

from tests.repo_root import REPO_ROOT
from rcx_pi.selfhost.step_mu import run_mu  # SPEED_OK: used in slow tests only
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path

ZERO = {"_num": None}


# ---------------------------------------------------------------------------
# Source proof helpers
# ---------------------------------------------------------------------------

def _read_source(module_path: str) -> str:
    """Read source file from mu/ path."""
    return (REPO_ROOT / module_path).read_text()


# ---------------------------------------------------------------------------
# Gate Tests: Evidence Walker Stall Fallback (PR #504)
# ---------------------------------------------------------------------------

class TestEvidenceWalkerStallFallback:
    """Gate: engine_pipeline.py has fallback for walker stall on malformed traces."""

    def test_source_has_fallback_branch(self):
        """AST proof: _collect_ontology_evidence contains the stall fallback elif."""
        src = _read_source("mu/host/python/rcx_pi/selfhost/engine_pipeline.py")
        tree = ast.parse(src)
        found_fallback = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_collect_ontology_evidence":
                # Walk the function body looking for the fallback comment
                func_src = ast.get_source_segment(src, node)
                if func_src and "boundary fallback" in func_src:
                    found_fallback = True
                break
        assert found_fallback, (
            "_collect_ontology_evidence must contain 'boundary fallback' branch "
            "for walker stall on head-only trace nodes"
        )

    def test_fallback_comment_marker_present(self):
        """Source proof: AST_OK: infra — boundary fallback marker exists."""
        src = _read_source("mu/host/python/rcx_pi/selfhost/engine_pipeline.py")
        assert "AST_OK: infra — boundary fallback" in src, (
            "engine_pipeline.py must have AST_OK marker for walker stall fallback"
        )


@pytest.mark.slow
class TestWalkerStallBehavior:
    """Gate: evidence walker stalls on head-only trace nodes (proving fix necessity)."""

    def test_head_only_trace_stalls_walker(self):
        """Walker cannot match head-only nodes — no evidence_done in output."""
        projs = load_verified_seed(get_seed_path("evidence_walker.v1.json"))["projections"]
        # Head-only trace node (no 'tail' key) — walker init pattern requires {head, tail}
        trace = {"head": {"state": "a", "step": ZERO, "projection": "test.stall"}}
        wrapped = {"evidence_walk": {"trace": trace}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=20)
        # Walker stalls: no evidence_done because init pattern doesn't match
        if isinstance(result, dict):
            assert "evidence_done" not in result, (
                "Walker should stall on head-only trace (no tail key) — "
                "if it doesn't stall, the fallback is unnecessary"
            )

    def test_wellformed_trace_does_not_stall(self):
        """Confirm {head, tail} traces work normally (control case)."""
        projs = load_verified_seed(get_seed_path("evidence_walker.v1.json"))["projections"]
        trace = {"head": {"state": "a", "step": ZERO, "projection": "test.ok"}, "tail": None}
        wrapped = {"evidence_walk": {"trace": trace}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=20)
        assert isinstance(result, dict)
        assert "evidence_done" in result, "Well-formed trace should produce evidence_done"


# ---------------------------------------------------------------------------
# Gate Tests: Bridge Supervisor Read-Only DB (PR #500)
# ---------------------------------------------------------------------------

class TestBridgeSupervisorReadOnly:
    """Gate: open_db_readonly uses SQLite URI read-only mode."""

    def test_source_uses_uri_mode(self):
        """Source proof: open_db_readonly uses file:...?mode=ro URI."""
        src = _read_source("mu/tools/agents/bridge_supervisor.py")
        assert "?mode=ro" in src, (
            "open_db_readonly must use SQLite URI read-only mode (file:...?mode=ro)"
        )
        assert "uri=True" in src, (
            "open_db_readonly must pass uri=True to sqlite3.connect"
        )

    def test_no_pragma_query_only(self):
        """Source proof: PRAGMA query_only removed (superseded by URI mode)."""
        src = _read_source("mu/tools/agents/bridge_supervisor.py")
        # open_db_readonly should NOT use PRAGMA query_only anymore
        # Find the function and check it doesn't contain the pragma
        in_readonly = False
        for line in src.splitlines():
            if "def open_db_readonly" in line:
                in_readonly = True
            elif in_readonly and line.strip().startswith("def "):
                break
            elif in_readonly and "query_only" in line:
                pytest.fail(
                    "open_db_readonly should not use PRAGMA query_only — "
                    "URI mode=ro provides true read-only at connection level"
                )


# ---------------------------------------------------------------------------
# Gate Tests: JS Seed Loader Checksum-Before-Parse (bot sweep finding)
# ---------------------------------------------------------------------------

class TestSeedLoaderChecksumOrdering:
    """Gate: JS seed_loader verifies checksum BEFORE JSON.parse for known seeds."""

    def test_checksum_before_parse_for_known_seeds(self):
        """Source proof: hash comparison occurs before JSON.parse call."""
        src = _read_source("mu/host/js/core/seed_loader.js")
        # Find positions of key operations in loadVerifiedSeed
        hash_check_pos = src.find("hash !== expected")
        json_parse_pos = src.find("JSON.parse(raw)")
        assert hash_check_pos > 0, "seed_loader.js must contain hash !== expected check"
        assert json_parse_pos > 0, "seed_loader.js must contain JSON.parse(raw) call"
        assert hash_check_pos < json_parse_pos, (
            "Checksum verification (hash !== expected) must appear BEFORE JSON.parse(raw) "
            f"in source — found at positions {hash_check_pos} and {json_parse_pos}"
        )

    def test_known_seed_early_reject_comment(self):
        """Source proof: security comment documents checksum-before-parse rationale."""
        src = _read_source("mu/host/js/core/seed_loader.js")
        assert "SECURITY: For known seeds, verify checksum BEFORE JSON.parse" in src, (
            "seed_loader.js must document the checksum-before-parse security rationale"
        )

    def test_verified_seed_parse_reuses_mu_copy_without_bypass_marker(self):
        """Source proof: verified seed ingress uses existing Mu copy without a new contraband bypass."""
        src = _read_source("mu/host/js/core/seed_loader.js")
        assert "const { muCopy } = require('./stage0_vm');" in src, (
            "seed_loader.js must reuse the existing Stage0 muCopy boundary for verified parse-tree ingress"
        )
        assert "muCopy(JSON.parse(raw), true" in src, (
            "checksum-verified seed parse-tree ingress must become trusted Mu through muCopy"
        )
        for line in src.splitlines():
            if "stage0_vm" in line:
                assert "CONTRABAND_OK" not in line, (
                    "local stage0_vm imports should not need a new CONTRABAND_OK bypass"
                )
