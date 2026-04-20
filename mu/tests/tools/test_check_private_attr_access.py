"""Grounding tests for tools/checks/linters/check_private_attr_access.py.

Verifies the AST-based checker catches private-attr access in test
code while skipping docstring contents (the false-positive class
captured in 2026-04-20 learning entry on routing-api-plus-write-gate
wave retry 1).

Allowlist parity with legacy grep:
  - self._foo            skipped (instance attribute access)
  - sys._getframe        skipped (stdlib)
  - # ANTICHEAT_OK line  skipped
  - _getframe + CONTRABAND_OK line skipped
  - test_contraband_detection.py filename allowlisted
  - __pycache__ dir skipped during discovery
  - __init__ and other dunders skipped (legacy grep required
    [a-zA-Z0-9]+ after the leading `_`, so `.__init__` was not
    matched either).
"""

import importlib.util
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
spec = importlib.util.spec_from_file_location(
    "check_private_attr_access",
    ROOT / "tools" / "checks" / "linters" / "check_private_attr_access.py",
)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def _write_and_check(source: str, filename: str = "test_example.py") -> list[str]:
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        prefix=filename.replace(".py", "_"),
        delete=False,
    ) as f:
        f.write(textwrap.dedent(source))
        f.flush()
        return checker.check_file(Path(f.name))


class TestDocstringFalsePositiveElimination:
    """The regression that motivated this wave: docstring references to
    private helpers were false-flagged by the grep-based scan."""

    def test_private_attr_inside_class_docstring_is_not_flagged(self):
        source = '''
        class Foo:
            """Documents the deliberate divergence from
            meta_bridge_supervisor._check_control_plane_path helper.
            """

            def test_thing(self):
                pass
        '''
        violations = _write_and_check(source)
        assert violations == [], f"docstring citation false-flagged: {violations}"

    def test_private_attr_inside_function_docstring_is_not_flagged(self):
        source = '''
        def test_thing():
            """Asserts pager_mod._read_orchestrator_session_id returns id."""
            pass
        '''
        violations = _write_and_check(source)
        assert violations == []

    def test_private_attr_inside_module_docstring_is_not_flagged(self):
        source = '''
        """Module explaining the wiring through foo._private_api behaviour."""
        from module import foo
        foo.public_api()
        '''
        violations = _write_and_check(source)
        assert violations == []


class TestRealPrivateAttrDetection:
    def test_catches_private_attr_access_in_code(self):
        source = """
        from module import foo
        foo._private_attr = 1
        """
        violations = _write_and_check(source)
        assert len(violations) == 1
        assert "_private_attr" in violations[0]

    def test_catches_private_method_call(self):
        source = """
        from module import foo
        foo._internal_helper()
        """
        violations = _write_and_check(source)
        assert len(violations) == 1
        assert "_internal_helper" in violations[0]


class TestAllowlistParity:
    def test_self_access_is_skipped(self):
        source = """
        class Foo:
            def bar(self):
                self._x = 1
                self._y()
        """
        violations = _write_and_check(source)
        assert violations == []

    def test_sys_getframe_is_skipped(self):
        source = """
        import sys
        f = sys._getframe()
        c = sys._current_frames()
        """
        violations = _write_and_check(source)
        assert violations == []

    def test_anticheat_ok_comment_is_skipped(self):
        source = """
        from module import foo
        foo._bar()  # ANTICHEAT_OK: grounding test
        """
        violations = _write_and_check(source)
        assert violations == []

    def test_getframe_with_contraband_ok_is_skipped(self):
        source = """
        class C:
            def _getframe(self):
                pass
        c = C()
        c._getframe()  # CONTRABAND_OK: testing the guard itself
        """
        violations = _write_and_check(source)
        assert violations == []

    def test_dunder_access_is_skipped(self):
        source = """
        class Foo:
            def __init__(self):
                pass

        f = Foo()
        repr_val = f.__repr__()
        init_val = f.__init__
        """
        violations = _write_and_check(source)
        assert violations == []

    def test_file_allowlist_skips_whole_file(self, tmp_path):
        src = tmp_path / "test_contraband_detection.py"
        src.write_text(
            "from module import foo\n"
            "foo._this_would_normally_be_flagged_but_file_is_allowlisted()\n"
        )
        violations = checker.check_file(src)
        assert violations == []


class TestScanIntegration:
    def test_scan_on_fixture_tree_reports_only_real_violations(self, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_clean.py").write_text(
            '"""Clean test: foo.public_api() only."""\n'
            "from module import foo\n"
            "foo.public_api()\n"
        )
        (tests_dir / "test_doc_only.py").write_text(
            '"""Test citing pager._read_orchestrator_session_id in docstring only."""\n'
            "from module import pager\n"
            "pager.read_orchestrator_session_id()\n"
        )
        (tests_dir / "test_dirty.py").write_text(
            "from module import foo\n"
            "foo._real_violation()\n"
        )
        violations = checker.scan(tmp_path)
        assert len(violations) == 1
        assert "_real_violation" in violations[0]
        assert "test_dirty.py" in violations[0]

    def test_scan_skips_pycache_dir(self, tmp_path):
        tests_dir = tmp_path / "tests" / "__pycache__"
        tests_dir.mkdir(parents=True)
        (tests_dir / "test_cached.cpython-313.py").write_text(
            "from module import foo\nfoo._private()\n"
        )
        violations = checker.scan(tmp_path)
        assert violations == []


class TestMainEntrypoint:
    def test_main_exits_0_on_clean(self, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_clean.py").write_text("pass\n")
        code = checker.main(["check_private_attr_access.py", str(tmp_path)])
        assert code == 0

    def test_main_exits_1_on_violation(self, tmp_path, capsys):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_dirty.py").write_text(
            "from module import foo\nfoo._bad()\n"
        )
        code = checker.main(["check_private_attr_access.py", str(tmp_path)])
        assert code == 1
        captured = capsys.readouterr()
        assert "_bad" in captured.out
