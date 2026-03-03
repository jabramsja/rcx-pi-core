"""Tests for check_simulated_production_logic.py (RT2+RT3 anti-theater guardrail).

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
        """JS snippet using require + call passes."""
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
        """Guard loop in snippet with production require + call is not flagged."""
        f = tmp_path / "test_ok3.py"
        f.write_text(
            'def test_example(self):\n'
            '    js_code = """\n'
            "    const { loadVerifiedSeed } = require('./mu/host/js/core/seed_loader');\n"
            "    const seed = loadVerifiedSeed('test.json', 'utilities');\n"
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


class TestRT3BypassFixtures:
    """RT3: Tests for bypass vectors that RT2 checker missed."""

    def test_require_present_but_never_called_fails(self, tmp_path):
        """FAIL: require('./mu/host/js/...') present but imported symbol never called."""
        f = tmp_path / "test_import_no_call.py"
        f.write_text(
            'def test_example(self):\n'
            '    js_code = """\n'
            "    const { loadVerifiedSeed } = require('./mu/host/js/core/seed_loader');\n"
            '    function loadVerifiedSeed(name, dir) {\n'
            '        return {projections: []};\n'
            '    }\n'
            '    // loadVerifiedSeed is imported but the inline redefines it\n'
            '    """\n'
        )
        violations = check_file(f)
        assert len(violations) >= 1, f"Expected violation, got: {violations}"
        # Should detect the inline function definition despite require presence
        descs = ' '.join(v['desc'] for v in violations)
        assert 'loadVerifiedSeed' in descs

    def test_concatenated_string_with_simulated_helper_fails(self, tmp_path):
        """FAIL: JS snippet built via concatenated Python strings with inline helper."""
        f = tmp_path / "test_concat.py"
        f.write_text(
            'def test_example(self):\n'
            '    js_code = (\n'
            "        'function validateSeedStructure(seedName, seed) {\\n'\n"
            "        '    if (!seed.projections) throw new Error(\"missing\");\\n'\n"
            "        '}\\n'\n"
            '    )\n'
        )
        violations = check_file(f)
        assert len(violations) >= 1, f"Expected violation, got: {violations}"
        descs = ' '.join(v['desc'] for v in violations)
        assert 'validateSeedStructure' in descs

    def test_fstring_with_simulated_helper_fails(self, tmp_path):
        """FAIL: f-string JS snippet with inline simulated helper."""
        f = tmp_path / "test_fstring.py"
        f.write_text(
            'def test_example(self):\n'
            '    seed_name = "test"\n'
            "    js_code = f'''\n"
            '    function loadVerifiedSeed(name) {{\n'
            '        return {{}};\n'
            '    }}\n'
            '    loadVerifiedSeed("{seed_name}");\n'
            "    '''\n"
        )
        violations = check_file(f)
        assert len(violations) >= 1, f"Expected violation, got: {violations}"
        descs = ' '.join(v['desc'] for v in violations)
        assert 'loadVerifiedSeed' in descs

    def test_require_plus_call_passes(self, tmp_path):
        """PASS: production require + actual call expression."""
        f = tmp_path / "test_require_call.py"
        f.write_text(
            'def test_example(self):\n'
            '    js_code = """\n'
            "    const { loadVerifiedSeed } = require('./mu/host/js/core/seed_loader');\n"
            "    const seed = loadVerifiedSeed('test.json', 'utilities');\n"
            '    console.log(seed.projections.length);\n'
            '    """\n'
        )
        violations = check_file(f)
        assert violations == [], f"Expected no violations, got: {violations}"

    def test_source_lock_with_theater_ok_passes(self, tmp_path):
        """PASS: source-lock-only with proper THEATER_OK marker."""
        f = tmp_path / "test_source_lock_ok.py"
        f.write_text(
            'def test_example(self):\n'
            '    # THEATER_OK: source-lock-only validates guard predicate exists in source\n'
            '    js_code = """\n'
            '    function validateSeedStructure(seedName, seed) {\n'
            '        // checking source shape only\n'
            '    }\n'
            '    """\n'
        )
        violations = check_file(f)
        assert violations == [], f"Expected no violations, got: {violations}"

    def test_arrow_function_alias_fails(self, tmp_path):
        """FAIL: arrow function alias for production helper."""
        f = tmp_path / "test_arrow.py"
        f.write_text(
            'def test_example(self):\n'
            '    js_code = """\n'
            '    const validateSeedStructure = (seedName, seed) => {\n'
            '        if (!seed.projections) throw new Error("missing");\n'
            '    };\n'
            '    """\n'
        )
        violations = check_file(f)
        assert len(violations) >= 1, f"Expected violation, got: {violations}"
        descs = ' '.join(v['desc'] for v in violations)
        assert 'arrow' in descs or 'validateSeedStructure' in descs

    def test_module_level_require_plus_member_call_passes(self, tmp_path):
        """PASS: module-level require + member call (pipeline.runStructural)."""
        f = tmp_path / "test_module_call.py"
        f.write_text(
            'def test_example(self):\n'
            '    js_code = """\n'
            "    const pipeline = require('./mu/host/js/engine/pipeline');\n"
            "    const result = pipeline.runStructural(kp, dp, input);\n"
            '    """\n'
        )
        violations = check_file(f)
        assert violations == [], f"Expected no violations, got: {violations}"


class TestRT3CIPathLock:
    """RT3: Verify checker is wired into audit scripts."""

    def test_audit_fast_includes_checker(self):
        """audit_fast.sh must invoke check_simulated_production_logic.py."""
        audit_fast = PROJECT_ROOT / "tools" / "audits" / "audit_fast.sh"
        content = audit_fast.read_text()
        assert 'check_simulated_production_logic.py' in content, (
            "audit_fast.sh must include check_simulated_production_logic.py"
        )

    def test_audit_all_includes_checker(self):
        """audit_all.sh must invoke check_simulated_production_logic.py."""
        audit_all = PROJECT_ROOT / "tools" / "audits" / "audit_all.sh"
        content = audit_all.read_text()
        assert 'check_simulated_production_logic.py' in content, (
            "audit_all.sh must include check_simulated_production_logic.py"
        )
