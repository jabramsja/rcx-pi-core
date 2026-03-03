"""
L4 gate tests for W1-GATE: Gate Blindness remediation.

Verifies:
- F-01: green gate fast path includes parity canary and does not fully ignore parity file.
- F-20: JS linter scripts default to full substrate scan (mu/host/js/).
- F-21: no new Date() in pipeline.js.
- F-04: missing parity vectors causes test failure, not skip.
"""
from tests.repo_root import REPO_ROOT


class TestF01GreenGateParityCanary:
    """F-01: Green gate must include parity canary at merge-time."""

    def test_green_gate_has_parity_canary_step(self):
        """green_gate.sh must include test_parity_canary invocation."""
        gate = (REPO_ROOT / "scripts" / "green_gate.sh").read_text()
        assert "test_parity_canary" in gate, (
            "green_gate.sh must run test_parity_canary for cross-substrate parity"
        )

    def test_green_gate_fast_path_not_fully_ignoring_parity(self):
        """green_gate.sh fast path must not ignore entire parity file without canary.

        The fast path may still --ignore the full file for the main pytest run
        (to avoid 54s overhead), but must compensate with a canary step.
        """
        gate = (REPO_ROOT / "scripts" / "green_gate.sh").read_text()
        # Must have EITHER:
        # 1. No --ignore of test_js_parity_automated.py at all, OR
        # 2. A separate canary step that runs test_parity_canary
        has_canary = "test_parity_canary" in gate
        assert has_canary, (
            "green_gate.sh must have parity canary step when fast path ignores parity file"
        )


class TestF20JsLintersFullSubstrateScan:
    """F-20: JS contraband/AST scripts must scan full substrate by default."""

    def test_contraband_js_defaults_to_directory(self):
        """contraband_js.sh must default to mu/host/js/ directory, not single file."""
        script = (REPO_ROOT / "tools" / "checks" / "linters" / "contraband_js.sh").read_text()
        assert "mu/host/js/" in script, (
            "contraband_js.sh must default to mu/host/js/ directory"
        )
        # Must not default to eval_step.js only
        lines = script.split('\n')
        default_lines = [l for l in lines if 'TARGET=' in l or 'JS_FILE=' in l]
        for line in default_lines:
            assert "eval_step.js" not in line or ":-" not in line, (
                f"contraband_js.sh must not default to eval_step.js: {line}"
            )

    def test_ast_police_js_defaults_to_directory(self):
        """ast_police_js.sh must default to mu/host/js/ directory, not single file."""
        script = (REPO_ROOT / "tools" / "checks" / "linters" / "ast_police_js.sh").read_text()
        assert "mu/host/js/" in script, (
            "ast_police_js.sh must default to mu/host/js/ directory"
        )

    def test_contraband_js_supports_marker(self):
        """contraband_js.sh must support CONTRABAND_OK marker."""
        script = (REPO_ROOT / "tools" / "checks" / "linters" / "contraband_js.sh").read_text()
        assert "CONTRABAND_OK" in script, (
            "contraband_js.sh must support CONTRABAND_OK marker for intentional exceptions"
        )

    def test_ast_police_js_supports_marker(self):
        """ast_police_js.sh must support AST_OK_JS marker."""
        script = (REPO_ROOT / "tools" / "checks" / "linters" / "ast_police_js.sh").read_text()
        assert "AST_OK_JS" in script, (
            "ast_police_js.sh must support AST_OK_JS marker for intentional exceptions"
        )


class TestF21NoDeterminismInPipeline:
    """F-21: pipeline.js must not contain wall-clock nondeterminism."""

    def test_no_new_date_in_pipeline(self):
        """pipeline.js must have zero new Date() calls."""
        pipeline = (REPO_ROOT / "mu" / "host" / "js" / "engine" / "pipeline.js").read_text()
        # Count non-comment occurrences of new Date(
        import re
        matches = []
        for i, line in enumerate(pipeline.split('\n'), 1):
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('*'):
                continue
            if 'new Date(' in line and 'CONTRABAND_OK' not in line:
                matches.append(f"L{i}: {line.strip()}")
        assert len(matches) == 0, (
            f"pipeline.js contains {len(matches)} unmarkered new Date() call(s):\n"
            + "\n".join(matches)
        )


class TestF04FailClosedParityVectors:
    """F-04: missing parity vectors must cause failure, not silent skip."""

    def test_parity_fixture_uses_fail_not_skip(self):
        """test_js_parity_automated.py must use pytest.fail, not pytest.skip, for missing vectors."""
        parity_test = (REPO_ROOT / "mu" / "tests" / "parity" / "test_js_parity_automated.py").read_text()
        # Must NOT have pytest.skip for missing parity_vectors
        assert "pytest.skip" not in parity_test or "parity_vectors" not in parity_test.split("pytest.skip")[1][:100], (
            "test_js_parity_automated.py must use pytest.fail, not pytest.skip, for missing parity_vectors.json"
        )
        # Must have pytest.fail for missing parity_vectors
        assert "pytest.fail" in parity_test, (
            "test_js_parity_automated.py must use pytest.fail for missing parity_vectors.json"
        )
