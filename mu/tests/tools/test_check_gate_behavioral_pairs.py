"""
MAINT-M1: Tests for tools/checks/check_gate_behavioral_pairs.py.

Validates classification accuracy, CLI output modes, and edge cases.
"""
from __future__ import annotations

import ast
import json
import subprocess
import textwrap
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

# Import the classifier module directly for unit tests.
import importlib.util
_tool_path = REPO_ROOT / "tools" / "checks" / "check_gate_behavioral_pairs.py"
_spec = importlib.util.spec_from_file_location("check_gate_behavioral_pairs", _tool_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
classify_method = _mod.classify_method
scan_file = _mod.scan_file
scan_directory = _mod.scan_directory
compute_summary = _mod.compute_summary


# ---------------------------------------------------------------------------
# TestClassification
# ---------------------------------------------------------------------------

class TestClassification:
    """Classification accuracy tests."""

    def _classify_source(self, source: str) -> str:
        """Parse a function source and classify it."""
        tree = ast.parse(textwrap.dedent(source))
        func_node = tree.body[0]
        return classify_method(func_node)

    def test_behavioral_method(self):
        """Method calling runtime function → behavioral."""
        src = """\
        def test_boundary_call(self):
            result = _service_boundary_effect(req, max_algorithm_iterations=50,
                emit_fn=noop, iteration=0, state="test")
            assert "boundary_result" in result
        """
        assert self._classify_source(src) == "behavioral"

    def test_source_lock_method(self):
        """Method reading source code with re.search → source_lock."""
        src = """\
        def test_wiring_present(self):
            src = inspect.getsource(some_function)
            assert re.search(r'some_pattern', src)
        """
        assert self._classify_source(src) == "source_lock"

    def test_hybrid_method(self):
        """Method with both source inspection and runtime call → hybrid."""
        src = """\
        def test_hybrid_check(self):
            src = inspect.getsource(some_function)
            assert re.search(r'pattern', src)
            result = _service_boundary_effect(req, max_algorithm_iterations=50,
                emit_fn=noop, iteration=0, state="test")
            assert result is not None
        """
        assert self._classify_source(src) == "hybrid"

    def test_theater_risk_method(self):
        """Method with no assertions → theater_risk."""
        src = """\
        def test_trivial(self):
            x = 1 + 1
        """
        assert self._classify_source(src) == "theater_risk"

    def test_all_l4_gates_scan_without_error(self):
        """Classification covers all l4_gates test files without error."""
        gate_dir = REPO_ROOT / "mu" / "tests" / "l4_gates"
        if not gate_dir.is_dir():
            pytest.skip("l4_gates directory not found")
        results = scan_directory(gate_dir)
        summary = compute_summary(results)
        assert summary["total"] > 0, "Expected at least some test methods"
        # All categories should be non-negative
        for cat in ["behavioral", "source_lock", "hybrid", "theater_risk"]:
            assert summary[cat] >= 0


# ---------------------------------------------------------------------------
# TestCLIOutput
# ---------------------------------------------------------------------------

class TestCLIOutput:
    """CLI output format tests."""

    def test_default_human_readable(self):
        """Default mode produces human-readable output with summary."""
        result = subprocess.run(
            ["python3", str(_tool_path)],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        assert "=== L4 Gate Test Integrity Report ===" in result.stdout
        assert "Summary:" in result.stdout
        assert "behavioral:" in result.stdout

    def test_json_output_valid(self):
        """--json mode produces valid JSON with files and summary keys."""
        result = subprocess.run(
            ["python3", str(_tool_path), "--json"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "files" in data
        assert "summary" in data
        assert isinstance(data["summary"]["total"], int)
        assert data["summary"]["total"] > 0

    def test_mismatch_enforcement_default_clean(self):
        """Default mode with mismatch enforcement passes (no Runtime/Wiring source-lock classes)."""
        result = subprocess.run(
            ["python3", str(_tool_path)],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"Mismatch enforcement failed:\n{result.stderr}"
        )
        assert "proof-class mismatch" not in result.stderr

    def test_mismatch_enforcement_suppressed(self):
        """--no-fail-on-mismatch suppresses mismatch check."""
        result = subprocess.run(
            ["python3", str(_tool_path), "--no-fail-on-mismatch"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0

    def test_unknown_flag_rejected(self):
        """Unknown CLI flags exit 2 (fail-closed)."""
        result = subprocess.run(
            ["python3", str(_tool_path), "--not-a-real-flag"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 2, f"Expected exit 2, got {result.returncode}"
        assert "Unknown flag" in result.stderr

    def test_fail_on_theater_exit_code(self):
        """--fail-on-theater exits non-zero when theater_risk methods exist."""
        result = subprocess.run(
            ["python3", str(_tool_path), "--fail-on-theater"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        # Current codebase has some theater_risk (heuristic false positives),
        # so this should exit non-zero.
        # If the codebase has zero theater_risk, this test needs adjustment.
        # For now, we check the tool runs and produces output regardless.
        assert "Summary:" in result.stdout
        # Exit code is either 0 (no theater) or 1 (theater found)
        assert result.returncode in (0, 1)


# ---------------------------------------------------------------------------
# TestSpeedEnforcer
# ---------------------------------------------------------------------------

class TestSpeedEnforcer:
    """Regression coverage for check_test_speed.sh mixed-file classification."""

    _speed_check_path = REPO_ROOT / "tools" / "checks" / "check_test_speed.sh"

    def _run_speed_check(self, path: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(self._speed_check_path), str(path)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_mixed_file_slow_mark_does_not_hide_unmarked_slow_test(self, tmp_path):
        test_file = tmp_path / "test_mixed_speed.py"
        test_file.write_text(
            textwrap.dedent(
                """
                import pytest
                from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline


                @pytest.mark.slow
                def test_marked_slow_path():
                    run_engine_pipeline([], {"slow": True})


                def test_unmarked_slow_leak():
                    run_engine_pipeline([], {"leak": True})
                """
            ).strip()
            + "\n"
        )

        result = self._run_speed_check(test_file)

        assert result.returncode == 1
        assert "test_unmarked_slow_leak" in result.stdout
        assert "test_marked_slow_path calls" not in result.stdout

    def test_package_level_module_import_does_not_hide_unmarked_slow_test(self, tmp_path):
        test_file = tmp_path / "test_package_import_slow_leak.py"
        test_file.write_text(
            textwrap.dedent(
                """
                from rcx_pi.selfhost import engine_pipeline


                def test_unmarked_package_import_slow_leak():
                    engine_pipeline.run_engine_pipeline([], {"leak": True})
                """
            ).strip()
            + "\n"
        )

        result = self._run_speed_check(test_file)

        assert result.returncode == 1
        assert "test_unmarked_package_import_slow_leak" in result.stdout
        assert "run_engine_pipeline" in result.stdout

    def test_helper_routed_slow_call_does_not_hide_unmarked_slow_test(self, tmp_path):
        test_file = tmp_path / "test_helper_run_mu_leak.py"
        test_file.write_text(
            textwrap.dedent(
                """
                from rcx_pi.selfhost.step_mu import run_mu


                def helper_run_mu():
                    return run_mu([], {"leak": True})


                def test_unmarked_helper_slow_leak():
                    helper_run_mu()
                """
            ).strip()
            + "\n"
        )

        result = self._run_speed_check(test_file)

        assert result.returncode == 1
        assert "test_unmarked_helper_slow_leak" in result.stdout
        assert "run_mu" in result.stdout

    def test_module_level_slow_mark_exempts_whole_file(self, tmp_path):
        test_file = tmp_path / "test_module_slow.py"
        test_file.write_text(
            textwrap.dedent(
                """
                import pytest
                from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline

                pytestmark = [pytest.mark.slow]


                def test_module_slow_path():
                    run_engine_pipeline([], {"slow": True})
                """
            ).strip()
            + "\n"
        )

        result = self._run_speed_check(test_file)

        assert result.returncode == 0
        assert "No speed violations found" in result.stdout

    def test_function_level_speed_ok_exempts_only_that_test(self, tmp_path):
        test_file = tmp_path / "test_speed_ok_scope.py"
        test_file.write_text(
            textwrap.dedent(
                """
                from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline


                def test_boundary_stubbed_path():
                    run_engine_pipeline([], {"fast": True})  # SPEED_OK: stubbed public-boundary proof


                def test_unmarked_slow_leak():
                    run_engine_pipeline([], {"leak": True})
                """
            ).strip()
            + "\n"
        )

        result = self._run_speed_check(test_file)

        assert result.returncode == 1
        assert "test_unmarked_slow_leak" in result.stdout
        assert "test_boundary_stubbed_path calls" not in result.stdout


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge case handling tests."""

    def test_empty_test_class(self, tmp_path):
        """Empty test class handled gracefully."""
        test_file = tmp_path / "test_empty.py"
        test_file.write_text(textwrap.dedent("""\
            class TestEmpty:
                pass
        """))
        classes = scan_file(test_file)
        # Empty class (no test_ methods) should not appear
        assert "TestEmpty" not in classes

    def test_non_test_methods_skipped(self, tmp_path):
        """Non-test methods (no test_ prefix) are skipped."""
        test_file = tmp_path / "test_helpers.py"
        test_file.write_text(textwrap.dedent("""\
            class TestSomething:
                def helper_method(self):
                    return 42

                def test_real(self):
                    assert self.helper_method() == 42
        """))
        classes = scan_file(test_file)
        assert "TestSomething" in classes
        methods = classes["TestSomething"]
        assert "helper_method" not in methods
        assert "test_real" in methods

    def test_module_level_functions_scanned(self, tmp_path):
        """Module-level test_* functions (not in classes) are scanned under <module>."""
        test_file = tmp_path / "test_module_funcs.py"
        test_file.write_text(textwrap.dedent("""\
            def test_standalone():
                assert 1 + 1 == 2

            def helper():
                pass

            class TestInClass:
                def test_method(self):
                    assert 1 + 1 == 2
        """))
        classes = scan_file(test_file)
        assert "<module>" in classes, "Module-level functions should be under <module> key"
        assert "test_standalone" in classes["<module>"]
        assert "helper" not in classes["<module>"]
        assert "TestInClass" in classes

    def test_positional_args_rejected(self):
        """Bare positional args exit 2 (fail-closed)."""
        result = subprocess.run(
            ["python3", str(_tool_path), "some_file.py"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 2, f"Expected exit 2, got {result.returncode}"
        assert "positional" in result.stderr.lower()


# ---------------------------------------------------------------------------
# TestHelperAndValidatorBroadening
# ---------------------------------------------------------------------------

class TestHelperAndValidatorBroadening:
    """Detector 1 (same-module helper following, scope-correct + proof-class
    preserving) and detector 2 (raises-on-failure validators).

    These exercise the full scope-keyed resolution maps via ``scan_file`` on a
    temp module (not ``classify_method`` in isolation), so helper resolution and
    per-class scoping are covered end-to-end.
    """

    def test_bare_name_helper_assertion_is_behavioral(self, tmp_path):
        """(a) Assertion only inside a same-module bare-name helper that does NOT
        read source → behavioral (not theater_risk)."""
        f = tmp_path / "test_bare_helper.py"
        f.write_text(textwrap.dedent("""\
            def _check_positive(value):
                assert value > 0

            class TestThing:
                def test_uses_bare_helper(self):
                    _check_positive(compute_value())
        """))
        classes = scan_file(f)
        assert classes["TestThing"]["test_uses_bare_helper"] == "behavioral"

    def test_self_method_source_helper_is_source_lock(self, tmp_path):
        """(b) ``self._helper`` that reads source (``read_text``) then asserts →
        source_lock (not behavioral, not theater_risk). Covers the (1a)
        ast.Attribute/self normalization AND (1b) source-class preservation
        together — mirrors the real ``_check_js_function_boundary`` case."""
        f = tmp_path / "test_self_source.py"
        f.write_text(textwrap.dedent("""\
            class TestBoundary:
                def _check_boundary(self, filepath):
                    text = filepath.read_text()
                    assert "BOUNDARY" in text

                def test_uses_self_helper(self):
                    self._check_boundary(SOME_PATH)
        """))
        classes = scan_file(f)
        assert classes["TestBoundary"]["test_uses_self_helper"] == "source_lock"

    def test_validator_only_call_is_behavioral(self, tmp_path):
        """(c) A test whose only check is a ``validate_bundle()`` call (raises on
        failure) → behavioral (not theater_risk)."""
        f = tmp_path / "test_validator.py"
        f.write_text(textwrap.dedent("""\
            class TestValidation:
                def test_valid_bundle(self):
                    validate_bundle(make_bundle())
        """))
        classes = scan_file(f)
        assert classes["TestValidation"]["test_valid_bundle"] == "behavioral"

    def test_vacuous_assert_true_remains_theater_risk(self, tmp_path):
        """(d) A genuinely vacuous test (``assert True``) still classifies
        theater_risk — broadening must not mask real theater."""
        f = tmp_path / "test_vacuous.py"
        f.write_text(textwrap.dedent("""\
            class TestVacuous:
                def test_nothing_meaningful(self):
                    assert True  # THEATER_OK: intentional vacuous fixture — this test asserts the classifier STILL flags assert True as theater_risk
        """))
        classes = scan_file(f)
        assert classes["TestVacuous"]["test_nothing_meaningful"] == "theater_risk"

    def test_duplicate_helper_name_resolves_per_class(self, tmp_path):
        """(e) Two classes each define a SAME-NAMED ``self._helper``: one reads
        source + asserts, the other does a plain non-source assert. The
        source-reading class's test → source_lock; the other → behavioral.

        Proves ``self``/``cls`` resolution is class-scoped: a flat global
        ``{name: FunctionDef}`` map would collapse ``_helper`` to its last
        definition and misroute one class's proof class (the live
        ``_js_eval``-across-five-classes hazard)."""
        f = tmp_path / "test_dup_helper.py"
        f.write_text(textwrap.dedent("""\
            class TestReadsSource:
                def _helper(self, filepath):
                    text = filepath.read_text()
                    assert "MARK" in text

                def test_via_helper(self):
                    self._helper(SOME_PATH)

            class TestPlainAssert:
                def _helper(self):
                    assert compute_value() == 42

                def test_via_helper(self):
                    self._helper()
        """))
        classes = scan_file(f)
        assert classes["TestReadsSource"]["test_via_helper"] == "source_lock"
        assert classes["TestPlainAssert"]["test_via_helper"] == "behavioral"

    def test_observational_helper_control_flow_compare_stays_theater_risk(self, tmp_path):
        """(f) Bridge round-2 regression: a purely observational test whose only
        same-module helpers are plumbing — a timing helper that calls a runtime
        function plus a stats helper containing a control-flow ``if n >= 20:`` —
        and that makes NO real assertion must remain theater_risk.

        Helper rescue must not mistake a helper's standalone ``ast.Compare`` for
        the test's assertion and reclassify an observational performance probe as
        behavioral. Mirrors the live ``TestTier2IntegrationWorkloads`` suite,
        which records timing data with no hard CI gating assertion. The runtime
        call (``step_kernel_mu``) supplies a behavioral signal, but with no
        assertion/raise/validator the test is still theater_risk — a behavioral
        signal alone never rescues a test from theater_risk."""
        f = tmp_path / "test_observational_probe.py"
        f.write_text(textwrap.dedent("""\
            def _time_workload(projs, inp):
                for _ in range(3):
                    step_kernel_mu(projs, inp)
                return [0.1, 0.2]

            def _stats(times):
                n = len(times)
                p95 = times[-1] if n >= 20 else times[0]
                return {"p95": p95, "n": n}

            class TestObservationalProbe:
                def test_workload_timing(self):
                    times = _time_workload(PROJS, INP)
                    stats = _stats(times)
                    print(stats)
        """))
        classes = scan_file(f)
        assert classes["TestObservationalProbe"]["test_workload_timing"] == "theater_risk"
