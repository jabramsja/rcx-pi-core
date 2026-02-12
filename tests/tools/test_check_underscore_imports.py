"""Grounding tests for tools/check_underscore_imports.py (AST-based checker).

Verifies the checker catches single-line, multiline, and comma-separated
underscore imports from rcx_pi, while respecting ANTICHEAT_OK and allowlists.
"""

import tempfile
import textwrap
from pathlib import Path

import pytest

# Import the checker module
import importlib.util

ROOT = Path(__file__).resolve().parent.parent.parent
spec = importlib.util.spec_from_file_location(
    "check_underscore_imports",
    ROOT / "tools" / "check_underscore_imports.py",
)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def _check_source(source: str, filename: str = "test_example.py") -> list[str]:
    """Write source to temp file, run checker, return violations."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", prefix=filename.replace(".py", "_"), delete=False
    ) as f:
        f.write(textwrap.dedent(source))
        f.flush()
        return checker.check_file(Path(f.name))


class TestSingleLineDetection:
    def test_catches_single_line_underscore_import(self):
        violations = _check_source("from rcx_pi.selfhost.step_mu import _private\n")
        assert len(violations) == 1
        assert "_private" in violations[0]

    def test_catches_underscore_after_comma(self):
        violations = _check_source("from rcx_pi.selfhost.step_mu import public, _private\n")
        assert len(violations) == 1
        assert "_private" in violations[0]


class TestMultilineDetection:
    def test_catches_multiline_underscore_import(self):
        source = """\
        from rcx_pi.selfhost.step_mu import (
            public_func,
            _private_func,
        )
        """
        violations = _check_source(source)
        assert len(violations) == 1
        assert "_private_func" in violations[0]

    def test_catches_multiple_underscored_in_multiline(self):
        source = """\
        from rcx_pi.selfhost.step_mu import (
            _foo,
            _bar,
        )
        """
        violations = _check_source(source)
        assert len(violations) == 2


class TestAnticheatOK:
    def test_respects_anticheat_ok_comment(self):
        source = "from rcx_pi.selfhost.step_mu import _private  # ANTICHEAT_OK: grounding test\n"
        violations = _check_source(source)
        assert len(violations) == 0


class TestAllowlist:
    def test_respects_file_allowlist(self):
        """Allowlisted filenames are skipped entirely."""
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_type_tag_security.py"
            filepath.write_text("from rcx_pi.selfhost.step_mu import _private\n")
            violations = checker.check_file(filepath)
        assert len(violations) == 0


class TestNonRcxpiIgnored:
    def test_ignores_non_rcx_pi_underscore_imports(self):
        violations = _check_source("from os.path import _some_private\n")
        assert len(violations) == 0

    def test_ignores_stdlib_underscore_imports(self):
        violations = _check_source("from collections import _Link\n")
        assert len(violations) == 0


class TestAliasBypass:
    def test_catches_public_imported_as_underscore(self):
        """Aliasing a public name to underscore is flagged."""
        violations = _check_source("from rcx_pi.selfhost.step_mu import run_mu as _run_mu\n")
        assert len(violations) == 1
        assert "run_mu as _run_mu" in violations[0]

    def test_ignores_public_alias_without_underscore(self):
        """Aliasing to a non-underscore name is fine."""
        violations = _check_source("from rcx_pi.selfhost.step_mu import run_mu as my_runner\n")
        assert len(violations) == 0


class TestCleanFile:
    def test_clean_file_has_no_violations(self):
        source = """\
        from rcx_pi.selfhost.step_mu import run_mu, step_mu
        from rcx_pi.selfhost.seed_integrity import load_verified_seed
        """
        violations = _check_source(source)
        assert len(violations) == 0
