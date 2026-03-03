"""Tests for check_simulated_production_logic.py (RT2 anti-theater guardrail).

Verifies the checker correctly detects inline JS helper simulation vs
production-bound tests, and respects THEATER_OK exceptions.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = PROJECT_ROOT / "tools" / "checks" / "check_simulated_production_logic.py"

# Import check_file from the checker module
_spec = importlib.util.spec_from_file_location(
    "check_simulated_production_logic", str(CHECKER_PATH)
)
_mod = importlib.util.module_from_spec(_spec)
# Temporarily suppress main() execution during import
_orig_argv = sys.argv
sys.argv = ["check_simulated_production_logic"]
_spec.loader.exec_module(_mod)
sys.argv = _orig_argv
check_file = _mod.check_file


class TestSimulatedProductionLogicChecker:
    """Unit tests for the simulated production logic checker."""

    def test_production_bound_snippet_passes(self, tmp_path):
        """JS snippet using require('./mu/host/js/...') passes."""
        f = tmp_path / "test_ok.py"
        f.write_text(
            'def test_example(self):\n'
            '    js_code = """\n'
            "    const { loadVerifiedSeed } = require('./mu/host/js/core/seed_loader');\n"
            "    loadVerifiedSeed('test.json', 'utilities');\n"
            '    """\n'
        )
        violations = check_file(f)
        assert violations == [], f"Expected no violations, got: {violations}"

    def test_simulated_inline_helper_fails(self, tmp_path):
        """Inline validateSeedStructure without production binding fails."""
        f = tmp_path / "test_bad.py"
        f.write_text(
            'def test_example(self):\n'
            '    js_code = """\n'
            '    function validateSeedStructure(seedName, seed) {\n'
            '        // simulated logic\n'
            '    }\n'
            '    """\n'
        )
        violations = check_file(f)
        assert len(violations) == 1, f"Expected 1 violation, got: {violations}"
        assert 'validateSeedStructure' in violations[0]['desc']

    def test_simulated_loadVerifiedSeed_fails(self, tmp_path):
        """Inline loadVerifiedSeed function definition without binding fails."""
        f = tmp_path / "test_bad2.py"
        f.write_text(
            'def test_example(self):\n'
            '    js_code = """\n'
            '    function loadVerifiedSeed(name, dir) {\n'
            '        return {};\n'
            '    }\n'
            '    """\n'
        )
        violations = check_file(f)
        assert len(violations) == 1, f"Expected 1 violation, got: {violations}"
        assert 'loadVerifiedSeed' in violations[0]['desc']

    def test_guard_loop_without_binding_fails(self, tmp_path):
        """Inline projection guard loop without production binding fails."""
        f = tmp_path / "test_bad3.py"
        f.write_text(
            'def test_example(self):\n'
            '    js_code = """\n'
            '    const seed = {projections: [null]};\n'
            '    for (let i = 0; i < seed.projections.length; i++) {\n'
            '        const p = seed.projections[i];\n'
            "        if (p === null || typeof p !== 'object') {\n"
            '            console.log("rejected");\n'
            '        }\n'
            '    }\n'
            '    """\n'
        )
        violations = check_file(f)
        assert len(violations) == 1, f"Expected 1 violation, got: {violations}"
        assert 'guard loop' in violations[0]['desc']

    def test_theater_ok_source_lock_with_reason_passes(self, tmp_path):
        """THEATER_OK: source-lock-only with reason text passes."""
        f = tmp_path / "test_ok2.py"
        f.write_text(
            'def test_example(self):\n'
            '    # THEATER_OK: source-lock-only validates guard predicate presence\n'
            '    js_code = """\n'
            '    function validateSeedStructure(seedName, seed) {\n'
            '        // simulated logic\n'
            '    }\n'
            '    """\n'
        )
        violations = check_file(f)
        assert violations == [], f"Expected no violations, got: {violations}"

    def test_malformed_theater_ok_missing_reason_fails(self, tmp_path):
        """THEATER_OK without reason text fails."""
        f = tmp_path / "test_bad4.py"
        f.write_text(
            'def test_example(self):\n'
            '    # THEATER_OK: source-lock-only\n'
            '    js_code = """\n'
            '    function validateSeedStructure(seedName, seed) {\n'
            '        // simulated logic\n'
            '    }\n'
            '    """\n'
        )
        violations = check_file(f)
        # Should have at least 2 violations: malformed marker + simulated logic
        assert len(violations) >= 2, f"Expected >=2 violations, got: {violations}"
        descs = [v['desc'] for v in violations]
        assert any('missing reason' in d for d in descs), (
            f"Expected malformed marker violation, got: {descs}"
        )
        assert any('validateSeedStructure' in d for d in descs), (
            f"Expected simulated logic violation (not exempted), got: {descs}"
        )

    def test_production_binding_exempts_guard_loop(self, tmp_path):
        """Guard loop in a snippet with production require is not flagged."""
        f = tmp_path / "test_ok3.py"
        f.write_text(
            'def test_example(self):\n'
            '    js_code = """\n'
            "    const { loadVerifiedSeed } = require('./mu/host/js/core/seed_loader');\n"
            '    const seed = {projections: [null]};\n'
            '    for (let i = 0; i < seed.projections.length; i++) {\n'
            '        const p = seed.projections[i];\n'
            "        if (p === null || typeof p !== 'object') {\n"
            '            console.log("rejected");\n'
            '        }\n'
            '    }\n'
            '    """\n'
        )
        violations = check_file(f)
        assert violations == [], f"Expected no violations, got: {violations}"

    def test_no_js_snippets_passes(self, tmp_path):
        """File with no JS snippets passes."""
        f = tmp_path / "test_clean.py"
        f.write_text(
            'def test_example(self):\n'
            '    assert 1 + 1 == 2\n'
        )
        violations = check_file(f)
        assert violations == []

    def test_python_source_lock_string_not_flagged(self, tmp_path):
        """Python-side source-lock using single-line string is not flagged."""
        f = tmp_path / "test_source_lock.py"
        f.write_text(
            'def test_example(self):\n'
            '    guard = "proj === null || typeof proj != \'object\'"\n'
            '    assert guard in some_source\n'
        )
        violations = check_file(f)
        assert violations == []
