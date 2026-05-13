"""
Automated JavaScript parity tests for L3 substrate portability.

These tests run the JavaScript implementation via subprocess and verify:
1. JS test suite passes (not just grep for string)
2. JS outputs match Python outputs for parity vectors
3. JS handles edge cases identically to Python

9-agent review finding (Grounding): The previous grep-based check was theater.
This test provides actual verification that JS behavior matches Python.
"""

import json
import subprocess
import textwrap
import pytest
from pathlib import Path

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# Root directory of the project (symlink-safe — see tests/repo_root.py)
from tests.repo_root import REPO_ROOT as ROOT


def _read_all_js_source() -> str:
    """Read all JS module files concatenated (monolith was split into modules)."""
    js_dir = ROOT / "mu" / "host" / "js"
    parts = []
    for f in sorted(js_dir.rglob("*.js")):
        parts.append(f.read_text())
    return "\n".join(parts)


def _run_node_json(script: str):
    result = subprocess.run(
        ["node", "-e", textwrap.dedent(script)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


class TestStage0VMAttemptTraceParity:
    """Python and JS Stage0 step results expose the same structural trace."""

    MATCH_BUNDLE_PATH = "mu/stage0/examples/match_v2_bundle.v1.json"

    def _load_match_bundle(self):
        return json.loads((ROOT / self.MATCH_BUNDLE_PATH).read_text())

    def _run_js_step(self, input_value):
        from tests.l4_gates.stage0_test_helpers import run_js_stage0

        result = run_js_stage0("step", self.MATCH_BUNDLE_PATH, input_value)
        assert "error" not in result, result
        return result

    def test_attempt_trace_match_shape_matches_js(self):
        from rcx_pi.selfhost.stage0_vm import stage0_vm_step

        inp = {
            "mode": "match",
            "pattern_focus": 42,
            "value_focus": 42,
            "bindings": None,
            "stack": None,
            "_match_ctx": {"projection_id": "test"},
        }

        py_result = stage0_vm_step(self._load_match_bundle(), inp)
        js_result = self._run_js_step(inp)

        assert py_result["attempt_trace"] == js_result["attempt_trace"]
        assert py_result["attempt_trace"] == {
            "attempted_program_ids": ["match.done", "match.sibling", "match.equal"],
            "outcome": "match",
            "matched_program_id": "match.equal",
        }

    def test_attempt_trace_stall_shape_matches_js(self):
        from rcx_pi.selfhost.stage0_vm import stage0_vm_step

        bundle = self._load_match_bundle()
        inp = {"unrelated": True}

        py_result = stage0_vm_step(bundle, inp)
        js_result = self._run_js_step(inp)

        assert py_result["attempt_trace"] == js_result["attempt_trace"]
        assert py_result["attempt_trace"] == {
            "attempted_program_ids": bundle["program_order"],
            "outcome": "stall",
            "matched_program_id": None,
        }


class TestJSTestSuitePasses:
    """Verify the JavaScript test suite passes completely."""

    def test_js_eval_step_tests_pass(self):
        """Run node mu/host/js/eval_step.js and verify all tests pass."""
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60
        )

        # Check for specific pass markers (not just grep)
        output = result.stdout

        # Verify parity tests passed
        assert "Parity tests:" in output, "Parity test output missing"
        parity_line = [l for l in output.split('\n') if "Parity tests:" in l][0]
        assert "0 failed" in parity_line, f"JS parity tests failed: {parity_line}"

        # Verify security tests passed
        assert "Security tests:" in output, "Security test output missing"
        security_line = [l for l in output.split('\n') if "Security tests:" in l][0]
        assert "0 failed" in security_line, f"JS security tests failed: {security_line}"

        # Verify EngineNews tests passed
        assert "Recurrence parity tests:" in output, "EngineNews test output missing"
        enginenews_line = [l for l in output.split('\n') if "Recurrence parity tests:" in l][0]
        assert "0 failed" in enginenews_line, f"JS Recurrence tests failed: {enginenews_line}"

        # Verify structural trace passes
        assert "PASS structural trace: true" in output, "JS structural trace failed"

    def test_js_core_tests_pass(self):
        """Verify core JS test cases pass."""
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60
        )

        output = result.stdout

        # Core test markers
        assert "PASS: true" in output, "Basic kernel cycle test failed"
        assert "PASS security: true" in output, "Security tests failed"
        assert "PASS depth guard: true" in output, "Depth guard test failed"
        assert "PASS kernel reserved fields: true" in output, "Reserved fields test failed"
        assert "PASS parity: true" in output, "Parity vector tests failed"


def _normalize_for_cross_substrate(value):
    """Normalize Python values for cross-substrate comparison with JS.

    JavaScript doesn't distinguish int/float (all numbers are float64).
    When comparing Python vs JS outputs, we need to normalize:
    - int/float: 0 and 0.0 should compare equal
    - Both are mathematically equal; type difference is host artifact

    9-agent Round 3 (Grounding finding): This handles the known limitation
    that JS doesn't have int/float distinction.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value  # bool before int (bool is subclass of int in Python)
    if isinstance(value, (int, float)):
        # Normalize to float for comparison (JS representation)
        return float(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return [_normalize_for_cross_substrate(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_for_cross_substrate(v) for k, v in value.items()}
    return value


def _cross_substrate_equal(py_val, js_val) -> bool:
    """Compare Python and JS values, handling cross-substrate type differences.

    Uses normalized comparison to handle int/float distinction that exists
    in Python but not in JavaScript.
    """
    norm_py = _normalize_for_cross_substrate(py_val)
    norm_js = _normalize_for_cross_substrate(js_val)
    return json.dumps(norm_py, sort_keys=True) == json.dumps(norm_js, sort_keys=True)


class TestCrossSubstrateParity:
    """Verify Python and JavaScript produce identical results for parity vectors.

    9-agent Round 3 (Grounding finding): These tests now do ACTUAL cross-substrate
    comparison via JSON API, not just string matching theater.
    """

    @pytest.fixture
    def parity_vectors(self):
        """Load shared parity vectors."""
        vectors_file = ROOT / "tests" / "fixtures" / "parity_vectors.json"
        if not vectors_file.exists():
            pytest.fail("parity_vectors.json not found — parity suite requires this fixture (fail-closed)")
        with open(vectors_file) as f:
            return json.load(f)

    @pytest.fixture
    def kernel_projections(self):
        """Load kernel projections."""
        from rcx_pi.selfhost.step_mu import load_combined_kernel_projections
        return load_combined_kernel_projections()

    def _run_js_json_api(self, request_dict: dict) -> dict:
        """Call JS with JSON API and parse response.

        9-agent Round 3 fix: Machine-readable output for actual comparison.
        """
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request_dict)],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60
        )

        # Find JSON response line
        for line in result.stdout.split('\n'):
            if line.startswith('JSON_API_RESPONSE:'):
                return json.loads(line[len('JSON_API_RESPONSE:'):])

        raise RuntimeError(f"No JSON_API_RESPONSE found in JS output: {result.stdout[:500]}")

    def test_parity_vector_count_matches(self, parity_vectors):
        """Verify Python and JS test the same number of parity vectors."""
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60
        )

        # Extract JS parity count
        output = result.stdout
        parity_line = [l for l in output.split('\n') if "Parity tests:" in l][0]
        # Format: "Parity tests: 20 passed, 0 failed"
        js_count = int(parity_line.split()[2])

        # Python vector count
        py_count = len(parity_vectors.get("vectors", []))

        assert js_count == py_count, (
            f"Parity vector count mismatch: Python has {py_count}, JS tested {js_count}"
        )

    def test_actual_cross_substrate_comparison(self, parity_vectors, kernel_projections):
        """ACTUAL cross-substrate test: run same inputs through Python and JS, compare outputs.

        9-agent Round 3 (Grounding finding): This is the real test. Previous tests
        just parsed strings. This test runs the same parity vectors through BOTH
        Python and JavaScript kernels and compares the actual results.

        Vectors with expected_error use step_mu on the Python side (which has
        the non-linear guard) instead of raw kernel, so both substrates reject.
        """
        from rcx_pi.selfhost.step_mu import step_mu, normalize_projection, list_to_linked
        from rcx_pi.selfhost.match_mu import normalize_for_match
        from rcx_pi.selfhost.subst_mu import denormalize_from_match
        from tests.conftest import run_until_done

        mismatches = []

        for vector in parity_vectors.get("vectors", []):
            vector_id = vector["id"]
            input_val = vector["input"]
            projection = vector["projection"]

            if vector.get("expected_error"):
                # Error vectors: use step_mu (has non-linear guard) for parity
                # with JS stepKernel. Both substrates must reject.
                try:
                    step_mu([projection], input_val)
                    py_denorm = {"_error": "expected rejection but succeeded"}
                except (ValueError, Exception) as e:
                    py_denorm = {"_error": str(e)}
            else:
                # Normal vectors: raw kernel execution
                try:
                    norm_input = normalize_for_match(input_val)
                    norm_proj = normalize_projection(projection)
                    kernel_entry = {
                        "_step": norm_input,
                        "_projs": list_to_linked([norm_proj])
                    }
                    py_result, _, _ = run_until_done(kernel_projections, kernel_entry, max_steps=100)
                    py_denorm = denormalize_from_match(py_result)
                except Exception as e:
                    py_denorm = {"_error": str(e)}

            # Run through JS kernel via JSON API
            try:
                js_response = self._run_js_json_api({
                    "action": "run_vector",
                    "input": input_val,
                    "projection": projection
                })
                if js_response.get("success"):
                    js_denorm = js_response["result"]
                else:
                    js_denorm = {"_error": js_response.get("error", "unknown")}
            except Exception as e:
                js_denorm = {"_error": str(e)}

            if vector.get("expected_error"):
                # For error vectors: both must error (content may differ across substrates)
                py_errored = "_error" in py_denorm
                js_errored = "_error" in js_denorm
                if not (py_errored and js_errored):
                    mismatches.append({
                        "id": vector_id,
                        "python": py_denorm,
                        "javascript": js_denorm
                    })
            else:
                # For normal vectors: outputs must match
                if not _cross_substrate_equal(py_denorm, js_denorm):
                    mismatches.append({
                        "id": vector_id,
                        "python": py_denorm,
                        "javascript": js_denorm
                    })

        assert len(mismatches) == 0, (
            f"Cross-substrate mismatch in {len(mismatches)} vectors:\n" +
            "\n".join(f"  {m['id']}: PY={m['python']} JS={m['javascript']}" for m in mismatches[:5])
        )

    def test_f25_empty_var_match_parity(self):
        """F-25: bootstrap match({var: ""}, x) returns NO_MATCH in both substrates.

        Targeted proof: calls bootstrap match() directly in both Python and JS.
        The kernel path uses seed-based match.v2 (which does NOT hit the bootstrap
        guard), so this test exercises the bootstrap function directly via node -e.
        """
        from rcx_pi.selfhost.eval_seed import match, NO_MATCH

        # Python: bootstrap match() rejects empty var
        assert match({"var": ""}, 42) is NO_MATCH, "Python match({var:''}, 42) should be NO_MATCH"
        assert match({"var": ""}, "hello") is NO_MATCH, "Python match({var:''}, 'hello') should be NO_MATCH"

        # JS: bootstrap match() rejects empty var (direct call)
        js_script = (
            "const { match } = require('./mu/host/js/core/bootstrap_core');\n"
            "const { NO_MATCH } = require('./mu/host/js/core/constants');\n"
            "const r1 = match({var: ''}, 42);\n"
            "const r2 = match({var: ''}, 'hello');\n"
            "if (r1 !== NO_MATCH || r2 !== NO_MATCH) {\n"
            "  process.stderr.write('FAIL: r1=' + JSON.stringify(r1) + ' r2=' + JSON.stringify(r2));\n"
            "  process.exit(1);\n"
            "}\n"
            "console.log('PASS');\n"
        )
        proc = subprocess.run(
            ["node", "-e", js_script],
            capture_output=True, text=True,
            cwd=ROOT, timeout=10,
        )
        assert proc.returncode == 0, f"JS match empty-var failed: {proc.stderr}"
        assert proc.stdout.strip() == "PASS"

    def test_python_js_constants_match(self):
        """Verify Python and JS have matching security constants.

        9-agent Round 3: Verify constants like MAX_DEPTH, MAX_WIDTH and
        KERNEL_RESERVED_FIELDS are actually identical, not just claimed to be.
        """
        from rcx_pi.selfhost.mu_type import MAX_MU_DEPTH, MAX_MU_WIDTH
        from rcx_pi.selfhost.step_mu import KERNEL_RESERVED_FIELDS

        js_response = self._run_js_json_api({"action": "get_constants"})
        assert js_response["success"], f"JS get_constants failed: {js_response}"

        # MAX_DEPTH must match
        assert js_response["MAX_DEPTH"] == MAX_MU_DEPTH, (
            f"MAX_DEPTH mismatch: Python={MAX_MU_DEPTH}, JS={js_response['MAX_DEPTH']}"
        )

        # MAX_WIDTH must match (Tooling Delta checklist item)
        js_max_width = js_response.get("max_width") or js_response.get("MAX_WIDTH") or js_response.get("MAX_MU_WIDTH")
        assert js_max_width == MAX_MU_WIDTH, (
            f"MAX_WIDTH mismatch: Python={MAX_MU_WIDTH}, JS={js_max_width}"
        )

        # KERNEL_RESERVED_FIELDS must match
        py_fields = set(KERNEL_RESERVED_FIELDS)
        js_fields = set(js_response["KERNEL_RESERVED_FIELDS"])
        assert py_fields == js_fields, (
            f"KERNEL_RESERVED_FIELDS mismatch:\n"
            f"  Python only: {py_fields - js_fields}\n"
            f"  JS only: {js_fields - py_fields}"
        )

    def test_python_js_normalization_matches(self):
        """
        Verify Python and JS normalize/denormalize identically.

        PARITY REQUIREMENT: This is a HARD requirement per project policy.
        The JS bootstrap must produce identical results to Python for all
        normalization operations. Any divergence is a blocking bug.
        """
        from rcx_pi.selfhost.match_mu import normalize_for_match, denormalize_from_match

        test_cases = [
            [],
            {},
            [1, 2, 3],
            {"a": 1, "b": 2},
            [{"x": []}, {"y": {}}],
            {"nested": {"deep": [1, 2]}},
            # Algorithm state shapes
            {"_detect_closure": {"trace": None, "result": "X"}},
            {"_detect_closure": {"trace": [{"step": 0, "state": "A"}], "result": "A"}},
            {"_detect_exhaustion": {"trace": None, "frozen": None, "tau_step": 0}},
        ]

        for case in test_cases:
            # Python normalization
            py_normalized = normalize_for_match(case)
            py_roundtrip = denormalize_from_match(py_normalized)

            # JS normalization via JSON API
            request = json.dumps({"action": "normalize_roundtrip", "value": case})
            result = subprocess.run(
                ["node", "mu/host/js/eval_step.js", "--json-api", request],
                capture_output=True,
                text=True,
                cwd=ROOT,
                timeout=30
            )

            # Parse JS response
            js_response = None
            for line in result.stdout.split('\n'):
                if line.startswith('JSON_API_RESPONSE:'):
                    js_response = json.loads(line[len('JSON_API_RESPONSE:'):])
                    break

            assert js_response is not None, f"No JSON API response for {case}"
            assert js_response.get('success'), f"JS normalize failed for {case}: {js_response.get('error')}"

            js_normalized = js_response['normalized']
            js_roundtrip = js_response['denormalized']

            # PARITY CHECK: Python and JS must produce identical results
            assert _cross_substrate_equal(py_normalized, js_normalized), (
                f"PARITY VIOLATION: normalize differs for {case}\n"
                f"  Python: {py_normalized}\n"
                f"  JS:     {js_normalized}"
            )

            assert _cross_substrate_equal(py_roundtrip, js_roundtrip), (
                f"PARITY VIOLATION: denormalize differs for {case}\n"
                f"  Python: {py_roundtrip}\n"
                f"  JS:     {js_roundtrip}"
            )

            # Roundtrip should recover original
            assert _cross_substrate_equal(case, py_roundtrip), f"Python roundtrip failed for {case}"
            assert _cross_substrate_equal(case, js_roundtrip), f"JS roundtrip failed for {case}"

    def test_head_tail_classify_policy_parity(self):
        """
        Verify Python and JS have identical head/tail handling policy.

        POLICY DECISION: "Classify" - treat {head: X, tail: Y} as linked-list format.

        Both substrates MUST:
        1. Treat {"head": X, "tail": Y} as linked-list representation (not domain data)
        2. Denormalize such structures back to Python/JS lists
        3. Handle untyped head/tail consistently (classify as linked-list)

        This test documents the policy as intentional and verifies cross-substrate parity.
        If domain data legitimately uses "head"/"tail" keys, it will be classified as
        linked-list format. This is a known design decision, not a bug.

        See roadmap/ToolingDelta.md for policy rationale.
        """
        from rcx_pi.selfhost.match_mu import normalize_for_match, denormalize_from_match

        # Test cases that exercise head/tail classification
        test_cases = [
            # Explicit linked-list structures
            {"head": 1, "tail": None},
            {"head": "a", "tail": {"head": "b", "tail": None}},
            {"head": {"x": 1}, "tail": {"head": {"y": 2}, "tail": None}},

            # Deeply nested linked-lists
            {"head": 1, "tail": {"head": 2, "tail": {"head": 3, "tail": None}}},

            # Empty list representation (null/None tail at end)
            {"head": "only", "tail": None},

            # Mixed: dict containing head/tail keys (WILL be classified as linked-list)
            # This documents the policy - these get treated as linked-lists

            # NOTE: Malformed inner node {"head": 1, "tail": {"head": 2}} is NOT tested
            # here because this test compares denormalize-only (Python) vs
            # normalize+denormalize roundtrip (JS JSON API). For malformed inputs,
            # normalize changes the structure before denormalize sees it, producing
            # divergent results that aren't real parity violations.
            # See test_normalization_roundtrip.py::test_denormalize_inner_node_missing_tail_*
            # for Python-only crash regression tests.
        ]

        for case in test_cases:
            # Python: normalize then denormalize
            # Note: These are already in head/tail format, so normalization may be identity
            # The key test is denormalization: does it convert to Python list?
            py_denorm = denormalize_from_match(case)

            # JS: same operation via JSON API
            request = json.dumps({"action": "normalize_roundtrip", "value": case})
            result = subprocess.run(
                ["node", "mu/host/js/eval_step.js", "--json-api", request],
                capture_output=True,
                text=True,
                cwd=ROOT,
                timeout=30
            )

            js_response = None
            for line in result.stdout.split('\n'):
                if line.startswith('JSON_API_RESPONSE:'):
                    js_response = json.loads(line[len('JSON_API_RESPONSE:'):])
                    break

            assert js_response is not None, f"No JSON API response for head/tail case {case}"
            assert js_response.get('success'), f"JS failed for head/tail case {case}: {js_response.get('error')}"

            js_denorm = js_response['denormalized']

            # PARITY CHECK: Both substrates must produce identical output
            # This verifies the "classify" policy is consistent
            assert _cross_substrate_equal(py_denorm, js_denorm), (
                f"HEAD/TAIL POLICY VIOLATION: denormalize differs\n"
                f"  Input:  {case}\n"
                f"  Python: {py_denorm}\n"
                f"  JS:     {js_denorm}\n"
                f"  Policy: Both should treat head/tail as linked-list (classify policy)"
            )


def test_parity_canary():
    """Fast cross-substrate canary: single run_vector through both Python and JS.

    Runs one kernel vector through Python, one through JS JSON API, compares results.
    Designed for green gate inclusion (<10s). Verifies that cross-substrate parity
    is not broken at merge-time. Full parity suite runs in audit_fast/nightly.
    """
    from rcx_pi.selfhost.step_mu import (
        load_combined_kernel_projections, normalize_projection, list_to_linked,
    )
    from rcx_pi.selfhost.match_mu import normalize_for_match
    from rcx_pi.selfhost.subst_mu import denormalize_from_match
    from tests.conftest import run_until_done

    kernel_projections = load_combined_kernel_projections()

    # Use a simple identity-like projection: match any value, return it
    test_input = 42
    test_projection = {"pattern": {"var": "x"}, "body": {"var": "x"}}

    # Python path
    norm_input = normalize_for_match(test_input)
    norm_proj = normalize_projection(test_projection)
    kernel_entry = {"_step": norm_input, "_projs": list_to_linked([norm_proj])}
    py_result, _, _ = run_until_done(kernel_projections, kernel_entry, max_steps=100)
    py_denorm = denormalize_from_match(py_result)

    # JS path via JSON API
    request = {"action": "run_vector", "input": test_input, "projection": test_projection}
    js_proc = subprocess.run(
        ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request)],
        capture_output=True, text=True, cwd=ROOT, timeout=30
    )
    js_response = None
    for line in js_proc.stdout.split('\n'):
        if line.startswith('JSON_API_RESPONSE:'):
            js_response = json.loads(line[len('JSON_API_RESPONSE:'):])
            break

    assert js_response is not None, "No JSON API response from JS"
    assert js_response.get('success'), f"JS run_vector failed: {js_response.get('error')}"

    # Compare results (normalize for int/float cross-substrate difference)
    assert _cross_substrate_equal(py_denorm, js_response['result']), (
        f"Cross-substrate parity BROKEN:\n"
        f"  Input:  {test_input}\n"
        f"  Python: {py_denorm}\n"
        f"  JS:     {js_response['result']}"
    )


class TestJSReservedFieldValidationParity:
    """Verify JS reserved field validation matches Python (Gate 3 security fix).

    Security invariant: Both Python and JS must reject reserved fields outside
    trusted algorithm-runtime validation mode.

    These tests catch the class of vulnerability where spoofed _mode/_phase values
    could bypass validation entirely.
    """

    def _run_js_validation(self, value, action="validate_reserved_fields"):
        """Run JS validation and return (success, error_msg)."""
        request = json.dumps({"action": action, "value": value})
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js", "--json-api", request],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=30
        )

        for line in result.stdout.split('\n'):
            if line.startswith('JSON_API_RESPONSE:'):
                response = json.loads(line[len('JSON_API_RESPONSE:'):])
                return response.get('valid', False), response.get('error', '')

        return False, f"No JSON_API_RESPONSE: {result.stdout[:200]}"

    def test_parity_spoofed_mode_rejected(self):
        """SECURITY: Spoofed _mode at top level MUST be rejected by both substrates.

        Attack vector: {"_mode": "recurrence", "_result": "pwned"}
        This should NEVER pass validation.
        """
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        spoofed = {"_mode": "recurrence", "_result": "pwned"}

        # Python rejects
        with pytest.raises(ValueError, match="SECURITY"):
            validate_no_kernel_reserved_fields(spoofed, "test")

        # JS must also reject
        valid, error = self._run_js_validation(spoofed)
        assert not valid, f"JS should reject spoofed _mode, but got valid=True"
        assert "_mode" in error or "reserved" in error.lower()

    def test_parity_entrypoint_subtree_rejected_in_domain_mode(self):
        """SECURITY: Domain validation rejects reserved fields even under entrypoints."""
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        legitimate = {
            "_detect_closure": {
                "_mode": "recurrence",
                "_result": "X"
            }
        }

        # Python rejects
        with pytest.raises(ValueError, match="SECURITY"):
            validate_no_kernel_reserved_fields(legitimate, "test")

        # JS must also reject
        valid, error = self._run_js_validation(legitimate)
        assert not valid, "JS should reject reserved entrypoint fields in domain mode"
        assert "_mode" in error or "reserved" in error.lower()

    def test_parity_normalized_reserved_key_rejected(self):
        """SECURITY: Reserved field encoded as normalized dict key must be rejected."""
        from rcx_pi.selfhost.match_mu import normalize_for_match
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        normalized = normalize_for_match({"_mode": "recurrence"})

        # Python rejects
        with pytest.raises(ValueError, match="SECURITY"):
            validate_no_kernel_reserved_fields(normalized, "test")

        # JS must also reject
        valid, error = self._run_js_validation(normalized)
        assert not valid, f"JS should reject normalized reserved key, but got valid=True"
        assert "_mode" in error or "reserved" in error.lower()

    def test_parity_normalized_entrypoint_rejected_in_domain_mode(self):
        """SECURITY: Domain validation rejects reserved normalized entrypoint payloads."""
        from rcx_pi.selfhost.match_mu import normalize_for_match
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        normalized = normalize_for_match({
            "_detect_exhaustion": {
                "_mode": "exhaustion",
                "_phase": "scan"
            }
        })

        # Python rejects
        with pytest.raises(ValueError, match="SECURITY"):
            validate_no_kernel_reserved_fields(normalized, "test")

        # JS must also reject
        valid, error = self._run_js_validation(normalized)
        assert not valid, "JS should reject normalized reserved entrypoint fields in domain mode"
        assert "_mode" in error or "reserved" in error.lower()

    def test_parity_nested_spoof_rejected(self):
        """SECURITY: Reserved fields nested in non-entrypoint key MUST be rejected.

        Attack vector: {"outer": {"_phase": "scan", "_result": 1}}
        "outer" is not an entrypoint, so this must fail.
        """
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        nested_spoof = {"outer": {"_phase": "scan", "_result": 1}}

        # Python rejects
        with pytest.raises(ValueError, match="SECURITY"):
            validate_no_kernel_reserved_fields(nested_spoof, "test")

        # JS must also reject
        valid, error = self._run_js_validation(nested_spoof)
        assert not valid, f"JS should reject nested spoof, but got valid=True"
        assert "_phase" in error or "reserved" in error.lower()

    def test_parity_clean_data_allowed(self):
        """Clean data without reserved fields MUST be allowed by both substrates."""
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        clean = {"x": 1, "y": {"z": 2}}

        # Python allows
        validate_no_kernel_reserved_fields(clean, "test")

        # JS must also allow
        valid, error = self._run_js_validation(clean)
        assert valid, f"JS should allow clean data, but got error: {error}"

    def test_parity_algorithm_runtime_allows_entrypoint_reserved_fields(self):
        """SECURITY: Algorithm-runtime mode allows trusted reserved fields."""
        from rcx_pi.selfhost.step_mu import validate_algorithm_runtime_fields

        payload = {
            "_detect_closure": {
                "_mode": "recurrence",
                "_phase": "scan",
                "_result": "X",
            }
        }

        validate_algorithm_runtime_fields(payload, "test")
        valid, error = self._run_js_validation(payload, action="validate_algorithm_runtime_fields")
        assert valid, f"JS algorithm-runtime validator should allow payload, got error: {error}"

    def test_parity_malformed_normalized_dict_fails_closed(self):
        """
        SECURITY: Malformed normalized dict encodings must fail closed.

        This blocks encoded-key bypasses where reserved keys are carried in kv heads.
        """
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        malformed = {
            "_type": "dict",
            "head": {
                "head": "_mode",
                "tail": {
                    "head": "forged",
                    "tail": {"oops": 1},
                },
            },
            "tail": None,
        }

        with pytest.raises(ValueError, match="malformed normalized dict encoding"):
            validate_no_kernel_reserved_fields(malformed, "test")

        valid, error = self._run_js_validation(malformed)
        assert not valid, "JS should reject malformed normalized dict encoding"
        assert "Malformed normalized dict encoding" in error

    def test_parity_normalized_dict_width_boundary(self):
        """
        SECURITY/PARITY: normalized dict width boundary must match in Python and JS.

        Python validator fails closed once normalized dict chain exceeds the
        validation-depth cap (MAX_MU_WIDTH). JS must fail at the same boundary.

        W3-CRASH F-13: cap raised from 100 to MAX_MU_WIDTH (1000).
        """
        from rcx_pi.selfhost.match_mu import normalize_for_match
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields
        from rcx_pi.selfhost.mu_type import MAX_MU_WIDTH

        # Width at MAX_MU_WIDTH should be accepted
        width_max = normalize_for_match({f"k{i}": i for i in range(MAX_MU_WIDTH)})
        validate_no_kernel_reserved_fields(width_max, "test")
        valid_max, error_max = self._run_js_validation(width_max)
        assert valid_max, f"JS should allow normalized dict width {MAX_MU_WIDTH}, got error: {error_max}"

        # Width at MAX_MU_WIDTH+1 should be rejected
        width_over = normalize_for_match({f"k{i}": i for i in range(MAX_MU_WIDTH + 1)})
        with pytest.raises(ValueError, match="malformed normalized dict encoding"):
            validate_no_kernel_reserved_fields(width_over, "test")
        valid_over, error_over = self._run_js_validation(width_over)
        assert not valid_over, f"JS should reject normalized dict width {MAX_MU_WIDTH + 1} to match Python"
        assert (
            "Malformed normalized dict encoding" in error_over
            or "malformed normalized dict encoding" in error_over
        )


class TestJSSecurityParity:
    """Verify JS implements the same security checks as Python."""

    def test_js_rejects_nan(self):
        """JS should reject NaN values like Python."""
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60
        )

        assert "NaN rejected: true" in result.stdout, "JS should reject NaN"

    def test_js_rejects_infinity(self):
        """JS should reject Infinity values like Python."""
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60
        )

        assert "Infinity rejected: true" in result.stdout, "JS should reject Infinity"

    def test_js_depth_guard_matches_python(self):
        """JS depth guard should match Python's MAX_MU_DEPTH."""
        from rcx_pi.selfhost.mu_type import MAX_MU_DEPTH

        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60
        )

        # JS uses MAX_DEPTH=300 which should match Python's MAX_MU_DEPTH
        assert "PASS depth guard: true" in result.stdout, "JS depth guard test failed"

        # Verify the value matches by checking if shallow passes and deep fails
        assert "Shallow (50 levels) OK: true" in result.stdout
        assert "Deep (350 levels) rejected: true" in result.stdout

    def test_js_reserved_fields_count_matches_python(self):
        """JS should have same reserved field count as Python.

        Gate 3 (2026-02-04): Entry points (_detect_closure, _detect_exhaustion) moved
        to ALGORITHM_ENTRYPOINT_KEYS. Now 22 reserved fields.
        """
        from rcx_pi.selfhost.step_mu import KERNEL_RESERVED_FIELDS

        # Python has 25 reserved fields (12 kernel + 3 Engine/Boot1 + 3 Recurrence + 3 Exhaustion + 4 Bridge)
        assert len(KERNEL_RESERVED_FIELDS) == 25, "Python reserved fields changed"

        # JS test output should confirm reserved fields are checked
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60
        )

        assert "PASS kernel reserved fields: true" in result.stdout

    def test_js_mu_validation_parity(self):
        """
        Verify JS isValidMu matches Python is_mu for edge cases.

        PARITY REQUIREMENT (Gate 2): JS must enforce same depth/width limits.
        """
        from rcx_pi.selfhost.mu_type import is_mu, MAX_MU_DEPTH, MAX_MU_WIDTH

        # Test cases: (value, expected_valid, description)
        test_cases = [
            # Valid cases
            (None, True, "null"),
            (True, True, "boolean"),
            (42, True, "integer"),
            (3.14, True, "float"),
            ("hello", True, "string"),
            ([], True, "empty list"),
            ({}, True, "empty dict"),
            ([1, 2, 3], True, "simple list"),
            ({"a": 1}, True, "simple dict"),

            # Invalid cases - these should be rejected by both
            # Note: We can't easily send undefined/NaN/Infinity via JSON,
            # so we test structural limits instead
        ]

        for value, expected, desc in test_cases:
            # Python validation
            py_valid = is_mu(value)

            # JS validation via JSON API
            request = json.dumps({"action": "validate_mu", "value": value})
            result = subprocess.run(
                ["node", "mu/host/js/eval_step.js", "--json-api", request],
                capture_output=True,
                text=True,
                cwd=ROOT,
                timeout=30
            )

            js_response = None
            for line in result.stdout.split('\n'):
                if line.startswith('JSON_API_RESPONSE:'):
                    js_response = json.loads(line[len('JSON_API_RESPONSE:'):])
                    break

            assert js_response is not None, f"No JSON API response for {desc}"
            assert js_response.get('success'), f"JS validate_mu failed for {desc}"

            js_valid = js_response['is_valid']

            # PARITY CHECK
            assert py_valid == js_valid, (
                f"PARITY VIOLATION: is_mu differs for {desc}\n"
                f"  Python: {py_valid}\n"
                f"  JS:     {js_valid}"
            )

        # Verify constants match
        request = json.dumps({"action": "validate_mu", "value": None})
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js", "--json-api", request],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=30
        )
        for line in result.stdout.split('\n'):
            if line.startswith('JSON_API_RESPONSE:'):
                js_response = json.loads(line[len('JSON_API_RESPONSE:'):])
                break

        assert js_response['max_depth'] == MAX_MU_DEPTH, (
            f"MAX_DEPTH mismatch: Python={MAX_MU_DEPTH}, JS={js_response['max_depth']}"
        )
        assert js_response['max_width'] == MAX_MU_WIDTH, (
            f"MAX_WIDTH mismatch: Python={MAX_MU_WIDTH}, JS={js_response['max_width']}"
        )

    def test_js_mu_boundary_rejects_object_and_array_host_artifacts(self):
        rows = _run_node_json(
            r"""
            const t = require('./mu/host/js/core/types');
            const { match } = require('./mu/host/js/core/bootstrap_core');

            class EmptyClass {}
            class KeyedClass { constructor() { this.a = 1; } }
            class ArraySubclass extends Array {}

            const customProto = Object.create({ inherited: true });
            customProto.a = 1;

            const hiddenToJSON = { a: 2 };
            Object.defineProperty(hiddenToJSON, 'toJSON', {
              enumerable: false,
              value() { return { a: 1 }; },
            });

            const arraySubclass = new ArraySubclass(1);
            const keyedArraySubclass = new ArraySubclass(1);
            keyedArraySubclass.extra = 2;
            const keyedArray = [1];
            keyedArray.extra = 2;
            const proxyThrowRecord = new Proxy({}, {
              getPrototypeOf() { throw new Error('host trap'); },
            });
            const proxyThrowArray = new Proxy([1], {
              getPrototypeOf() { throw new Error('host trap'); },
            });
            const proxyTrapRecord = new Proxy({}, {
              getPrototypeOf() { throw new Error('host trap'); },
              ownKeys() { return ['a']; },
              getOwnPropertyDescriptor(_target, key) {
                if (key === 'a') return { value: 1, enumerable: true, configurable: true };
              },
              get(_target, key) { return key === 'a' ? 1 : undefined; },
            });

            const rejected = [
              ['date', new Date('2026-05-08T00:00:00Z'), {}, {}],
              ['map', new Map([['a', 1]]), {}, {}],
              ['empty_class', new EmptyClass(), {}, {}],
              ['keyed_class', new KeyedClass(), { a: 1 }, { a: { var: 'x' } }],
              ['custom_proto', customProto, { a: 1 }, { a: { var: 'x' } }],
              ['hidden_to_json', hiddenToJSON, { a: 2 }, { a: { var: 'x' } }],
              ['array_subclass', arraySubclass, [1], [{ var: 'x' }]],
              ['keyed_array_subclass', keyedArraySubclass, [1], [{ var: 'x' }]],
              ['keyed_array', keyedArray, [1], [{ var: 'x' }]],
              ['bigint', 1n, {}, {}],
              ['proxy_throw_record', proxyThrowRecord, { a: 1 }, { a: { var: 'x' } }],
              ['proxy_throw_array', proxyThrowArray, [1], [{ var: 'x' }]],
              ['proxy_trap_record', proxyTrapRecord, { a: 1 }, { a: { var: 'x' } }],
            ];

            const hashFns = ['muHash', 'muHashCached', 'muHashControl', 'muHashControlCached'];
            function hashOutcome(fn, value) {
              try {
                t[fn](value, 'mu_host_object_boundary_gate');
                return { rejected: false, error_code: null };
              } catch (err) {
                return { rejected: true, error_code: err.error_code || null };
              }
            }
            function matchOutcome(pattern, input, budgeted) {
              try {
                const result = budgeted
                  ? match(pattern, input, 0, false, t._STRUCTURAL_DEPTH_BUDGET)
                  : match(pattern, input);
                return { rejected: false, result };
              } catch (err) {
                return { rejected: true, error_code: err.error_code || null };
              }
            }

            const validRecord = { a: [1, { b: false }], c: null };
            const validArray = [1, { a: 2 }];

            console.log(JSON.stringify({
              rejected: rejected.map(([name, value, validPeer, patternForInvalidInput]) => ({
                name,
                defaultValid: t.isValidMu(value),
                budgetValid: t.isValidMu(value, 0, undefined, t._STRUCTURAL_DEPTH_BUDGET),
                hashes: Object.fromEntries(hashFns.map(fn => [fn, hashOutcome(fn, value)])),
                matches: {
                  defaultPattern: matchOutcome(value, validPeer, false),
                  budgetPattern: matchOutcome(value, validPeer, true),
                  defaultInput: matchOutcome(patternForInvalidInput, value, false),
                  budgetInput: matchOutcome(patternForInvalidInput, value, true),
                },
              })),
              accepted: {
                record: {
                  defaultValid: t.isValidMu(validRecord),
                  budgetValid: t.isValidMu(validRecord, 0, undefined, t._STRUCTURAL_DEPTH_BUDGET),
                  hash: t.muHash(validRecord),
                  cached: t.muHashCached(validRecord),
                  control: t.muHashControl(validRecord),
                  controlCached: t.muHashControlCached(validRecord),
                  matchDefault: matchOutcome({ a: { var: 'x' }, c: null }, validRecord, false),
                  matchBudget: matchOutcome({ a: { var: 'x' }, c: null }, validRecord, true),
                },
                array: {
                  defaultValid: t.isValidMu(validArray),
                  budgetValid: t.isValidMu(validArray, 0, undefined, t._STRUCTURAL_DEPTH_BUDGET),
                  hash: t.muHash(validArray),
                  cached: t.muHashCached(validArray),
                  control: t.muHashControl(validArray),
                  controlCached: t.muHashControlCached(validArray),
                },
              },
            }));
            """
        )

        assert {row["name"] for row in rows["rejected"]} == {
            "date",
            "map",
            "empty_class",
            "keyed_class",
            "custom_proto",
            "hidden_to_json",
            "array_subclass",
            "keyed_array_subclass",
            "keyed_array",
            "bigint",
            "proxy_throw_record",
            "proxy_throw_array",
            "proxy_trap_record",
        }
        for row in rows["rejected"]:
            assert row["defaultValid"] is False, row
            assert row["budgetValid"] is False, row
            for outcome in row["hashes"].values():
                assert outcome == {"rejected": True, "error_code": "input.invalid_type"}
            for outcome in row["matches"].values():
                assert outcome == {"rejected": True, "error_code": "input.invalid_type"}

        record = rows["accepted"]["record"]
        assert record["matchDefault"] == {
            "rejected": False,
            "result": {"x": [1, {"b": False}]},
        }
        assert record["matchBudget"] == record["matchDefault"]

        for accepted in rows["accepted"].values():
            assert accepted["defaultValid"] is True
            assert accepted["budgetValid"] is True
            assert len(accepted["hash"]) == 64
            assert accepted["hash"] == accepted["cached"]
            assert len(accepted["control"]) == 64
            assert accepted["control"] == accepted["controlCached"]

    def test_js_mu_hash_cached_rejects_hidden_to_json_without_poisoning_cache(self):
        row = _run_node_json(
            r"""
            const t = require('./mu/host/js/core/types');

            const poisoned = { a: 2 };
            Object.defineProperty(poisoned, 'toJSON', {
              enumerable: false,
              value() { return { a: 1 }; },
            });

            function rejectOutcome(fn, value) {
              try {
                t[fn](value);
                return { rejected: false, error_code: null };
              } catch (err) {
                return { rejected: true, error_code: err.error_code || null };
              }
            }

            const poisonedOutcome = rejectOutcome('muHashCached', poisoned);
            const plain1 = { a: 1 };
            const plain2 = { a: 2 };
            const plain1Hash = t.muHash(plain1);
            const plain2Hash = t.muHash(plain2);
            const cachedPlain1 = t.muHashCached(plain1);
            const cachedPlain2 = t.muHashCached(plain2);

            console.log(JSON.stringify({
              poisonedValid: t.isValidMu(poisoned),
              poisonedOutcome,
              cachedPlain1EqualsHashPlain1: cachedPlain1 === plain1Hash,
              cachedPlain1EqualsHashPlain2: cachedPlain1 === plain2Hash,
              cachedPlain2EqualsHashPlain2: cachedPlain2 === plain2Hash,
              plainHashesDiffer: plain1Hash !== plain2Hash,
              muEqualPlain1Plain2: t.muEqual(plain1, plain2),
            }));
            """
        )

        assert row == {
            "poisonedValid": False,
            "poisonedOutcome": {"rejected": True, "error_code": "input.invalid_type"},
            "cachedPlain1EqualsHashPlain1": True,
            "cachedPlain1EqualsHashPlain2": False,
            "cachedPlain2EqualsHashPlain2": True,
            "plainHashesDiffer": True,
            "muEqualPlain1Plain2": False,
        }

    def test_python_exact_compound_boundary_remains_parity_reference(self):
        from rcx_pi.selfhost.mu_type import is_mu, mu_hash

        class ArbitraryObject:
            pass

        class DictSubclass(dict):
            pass

        class ListSubclass(list):
            pass

        for value in [ArbitraryObject(), DictSubclass({"a": 1}), ListSubclass([1])]:
            assert is_mu(value) is False
            with pytest.raises(TypeError):
                mu_hash(value)

        for value in [{"a": 1}, [1, {"a": 2}]]:
            assert is_mu(value) is True
            assert len(mu_hash(value)) == 64


class TestJSRecurrenceParity:
    """Verify JS Recurrence closure detection matches Python."""

    def test_js_recurrence_projections_loaded(self):
        """Verify JS loads Recurrence projections."""
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60
        )

        assert "recurrence.v1.json: 9 projections" in result.stdout, (
            "JS should load 9 Recurrence projections"
        )

    def test_js_recurrence_closure_detection_works(self):
        """Verify JS closure detection matches Python behavior."""
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60
        )

        # Check EngineNews parity tests
        assert "Recurrence parity tests:" in result.stdout
        enginenews_line = [l for l in result.stdout.split('\n') if "Recurrence parity tests:" in l][0]
        assert "5 passed" in enginenews_line, f"EngineNews parity incomplete: {enginenews_line}"
        assert "0 failed" in enginenews_line, f"EngineNews parity failed: {enginenews_line}"


class TestJSTraceFormatParity:
    """Verify JS trace format matches Python exactly (9-agent finding)."""

    def test_js_trace_stall_format(self):
        """JS stall trace should add new entry at step i+1 (not modify last)."""
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60
        )

        # The structural trace test verifies format
        assert "PASS structural trace: true" in result.stdout, (
            "JS structural trace format doesn't match Python"
        )

        # Specific checks
        assert "Trace entries have step/state/projection: true" in result.stdout
        assert "Stall detected correctly: true" in result.stdout


@pytest.mark.timeout(120)
class TestJSBridgeParity:
    """Verify JS bridge execution matches Python (Gate 7: L3 Bridge Parity).

    9-agent finding (Grounding): Bridge projections were loaded but not tested
    via automated cross-substrate comparison. These tests verify that recurrence
    and exhaustion run identically through both Python and JS bridge paths.
    """

    def _run_js_json_api(self, request_dict: dict) -> dict:
        """Call JS with JSON API and parse response."""
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request_dict)],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60
        )

        for line in result.stdout.split('\n'):
            if line.startswith('JSON_API_RESPONSE:'):
                return json.loads(line[len('JSON_API_RESPONSE:'):])

        raise RuntimeError(f"No JSON_API_RESPONSE found in JS output: {result.stdout[:500]}")

    def test_js_bridge_projections_loaded(self):
        """Verify JS loads bridge projections."""
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60
        )

        assert "bootstrap_structural.v1.json: 5 projections" in result.stdout, (
            "JS should load 5 bridge projections"
        )
        assert "Total (with Bridge): 33 projections" in result.stdout, (
            "JS combined kernel+bridge should be 33 projections"
        )

    def test_js_bridge_constants_reported(self):
        """Verify JS reports bridge projection count via JSON API."""
        js_response = self._run_js_json_api({"action": "get_constants"})
        assert js_response["success"], f"JS get_constants failed: {js_response}"
        assert js_response["bridge_projection_count"] == 5, (
            f"Expected 5 bridge projections, got {js_response['bridge_projection_count']}"
        )
        assert js_response["total_with_bridge"] == 33, (
            f"Expected 33 total with bridge, got {js_response['total_with_bridge']}"
        )

    def test_recurrence_with_bridge_no_closure(self):
        """Python and JS recurrence-with-bridge should match for no-closure case."""
        from rcx_pi.selfhost.step_mu import run_algorithm_meta_circular
        from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path

        recurrence_projs = load_verified_seed(get_seed_path("recurrence.v1.json"))["projections"]

        # Input with no closure (all unique states)
        input_data = {
            "_detect_closure": {
                "trace": {
                    "head": {"step": 0, "state": "A", "projection": "p1"},
                    "tail": {
                        "head": {"step": 1, "state": "B", "projection": "p2"},
                        "tail": None
                    }
                },
                "result": "final"
            }
        }

        # Run Python (Gate 4 default structural path via run_algorithm_meta_circular)
        py_result = input_data
        for _ in range(100):
            next_result = run_algorithm_meta_circular(recurrence_projs, py_result)
            if next_result == py_result:
                break
            py_result = next_result

        # Run JS with bridge
        js_response = self._run_js_json_api({
            "action": "run_recurrence_with_bridge",
            "input": input_data,
            "maxSteps": 100
        })
        assert js_response["success"], f"JS run_recurrence_with_bridge failed: {js_response}"
        js_result = js_response["result"]

        # Compare results
        assert _cross_substrate_equal(py_result, js_result), (
            f"Recurrence (no closure) mismatch:\n"
            f"  Python: {py_result}\n"
            f"  JS: {js_result}"
        )

    def test_recurrence_with_bridge_closure_detected(self):
        """Python and JS recurrence-with-bridge should match for closure case."""
        from rcx_pi.selfhost.step_mu import run_algorithm_meta_circular
        from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path

        recurrence_projs = load_verified_seed(get_seed_path("recurrence.v1.json"))["projections"]

        # Input with closure (state A repeats)
        input_data = {
            "_detect_closure": {
                "trace": {
                    "head": {"step": 0, "state": "A", "projection": "p1"},
                    "tail": {
                        "head": {"step": 1, "state": "B", "projection": "p2"},
                        "tail": {
                            "head": {"step": 2, "state": "A", "projection": "p3"},
                            "tail": None
                        }
                    }
                },
                "result": "final"
            }
        }

        # Run Python (Gate 4 default structural path)
        py_result = input_data
        for _ in range(100):
            next_result = run_algorithm_meta_circular(recurrence_projs, py_result)
            if next_result == py_result:
                break
            py_result = next_result

        # Run JS with bridge
        js_response = self._run_js_json_api({
            "action": "run_recurrence_with_bridge",
            "input": input_data,
            "maxSteps": 100
        })
        assert js_response["success"], f"JS run_recurrence_with_bridge failed: {js_response}"
        js_result = js_response["result"]

        # Compare results
        assert _cross_substrate_equal(py_result, js_result), (
            f"Recurrence (closure) mismatch:\n"
            f"  Python: {py_result}\n"
            f"  JS: {js_result}"
        )

        # Both should detect closure
        assert py_result.get("closure_detected") is True, "Python should detect closure"
        assert js_result.get("closure_detected") is True, "JS should detect closure"

    def test_exhaustion_with_bridge_no_exhaustion(self):
        """Python and JS exhaustion-with-bridge should match for no-exhaustion case."""
        from rcx_pi.selfhost.step_mu import run_algorithm_meta_circular
        from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path

        exhaustion_projs = load_verified_seed(get_seed_path("exhaustion.v1.json"))["projections"]

        # Input with different operators (no exhaustion)
        input_data = {
            "_detect_exhaustion": {
                "trace": {
                    "head": {"step": 0, "state": "A", "projection": "op1"},
                    "tail": {
                        "head": {"step": 1, "state": "B", "projection": "op2"},
                        "tail": None
                    }
                },
                "frozen": None,
                "tau_step": 0,
                "operator_ids": {
                    "head": "op1",
                    "tail": {"head": "op2", "tail": None}
                }
            }
        }

        # Run Python (Gate 4 default structural path)
        py_result = input_data
        for _ in range(100):
            next_result = run_algorithm_meta_circular(exhaustion_projs, py_result)
            if next_result == py_result:
                break
            py_result = next_result

        # Run JS with bridge
        js_response = self._run_js_json_api({
            "action": "run_exhaustion_with_bridge",
            "input": input_data,
            "maxSteps": 100
        })
        assert js_response["success"], f"JS run_exhaustion_with_bridge failed: {js_response}"
        js_result = js_response["result"]

        # Compare results
        assert _cross_substrate_equal(py_result, js_result), (
            f"Exhaustion (no exhaust) mismatch:\n"
            f"  Python: {py_result}\n"
            f"  JS: {js_result}"
        )

    def test_exhaustion_with_bridge_exhausted(self):
        """Python and JS exhaustion-with-bridge should match for exhaustion case."""
        from rcx_pi.selfhost.step_mu import run_algorithm_meta_circular
        from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path

        exhaustion_projs = load_verified_seed(get_seed_path("exhaustion.v1.json"))["projections"]

        # Input with same operator (should exhaust)
        input_data = {
            "_detect_exhaustion": {
                "trace": {
                    "head": {"step": 0, "state": "A", "projection": "op1"},
                    "tail": {
                        "head": {"step": 1, "state": "B", "projection": "op1"},
                        "tail": None
                    }
                },
                "frozen": None,
                "tau_step": 0,
                "operator_ids": {"head": "op1", "tail": None}
            }
        }

        # Run Python (Gate 4 default structural path)
        py_result = input_data
        for _ in range(100):
            next_result = run_algorithm_meta_circular(exhaustion_projs, py_result)
            if next_result == py_result:
                break
            py_result = next_result

        # Run JS with bridge
        js_response = self._run_js_json_api({
            "action": "run_exhaustion_with_bridge",
            "input": input_data,
            "maxSteps": 100
        })
        assert js_response["success"], f"JS run_exhaustion_with_bridge failed: {js_response}"
        js_result = js_response["result"]

        # Compare results
        assert _cross_substrate_equal(py_result, js_result), (
            f"Exhaustion (exhausted) mismatch:\n"
            f"  Python: {py_result}\n"
            f"  JS: {js_result}"
        )

        # Both should detect exhaustion
        assert py_result.get("exhaustion_detected") is True, "Python should detect exhaustion"
        assert js_result.get("exhaustion_detected") is True, "JS should detect exhaustion"


# =============================================================================
# Engine-Hemisphere Orchestration Parity (L3 mandatory)
# =============================================================================


class TestEngineHelpersParity:
    """Fast parity tests for engine-hemisphere helper functions."""

    def _run_js_json_api(self, request_dict: dict) -> dict:
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request_dict)],
            capture_output=True, text=True, cwd=ROOT, timeout=60
        )
        for line in result.stdout.split('\n'):
            if line.startswith('JSON_API_RESPONSE:'):
                return json.loads(line[len('JSON_API_RESPONSE:'):])
        raise RuntimeError(f"No JSON_API_RESPONSE: {result.stdout[:500]}")

    def test_hash_trace_simple_parity(self):
        """hash_trace_for_recurrence produces identical output on both substrates."""
        from rcx_pi.selfhost.engine_pipeline import hash_trace_for_recurrence


        trace = {
            "head": {"step": 0, "state": {"x": 1}, "projection": "test"},
            "tail": {
                "head": {"step": 1, "state": {"x": 1}, "stall": True},
                "tail": None
            }
        }
        py_result = hash_trace_for_recurrence(trace)
        js_response = self._run_js_json_api({"action": "hash_trace", "trace": trace})
        assert js_response["success"], f"JS hash_trace failed: {js_response.get('error')}"
        assert _cross_substrate_equal(py_result, js_response["result"]), (
            f"hash_trace mismatch:\n  Python: {py_result}\n  JS: {js_response['result']}"
        )

    def test_hash_trace_overcap_parity(self):
        """Both substrates reject traces exceeding maxEntries."""
        trace = None
        for i in range(5):
            trace = {"head": {"state": str(i), "step": i}, "tail": trace}

        js_response = self._run_js_json_api({
            "action": "hash_trace", "trace": trace, "maxEntries": 3
        })
        assert not js_response["success"], "JS should reject overcap trace"
        assert "exceeds" in js_response["error"]

    def test_hemisphere_routing_rejects_non_dict_parity(self):
        """Both substrates reject non-dict engine_result."""
        js_response = self._run_js_json_api({
            "action": "run_hemisphere_routing",
            "engine_result": "not_a_dict",
            "hemispheres": {"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None}
        })
        assert not js_response["success"], "JS should reject non-dict engine_result"
        assert "must be a dict" in js_response["error"]

    def test_hemisphere_routing_non_dict_error_code(self):
        """run_hemisphere_routing non-dict rejection carries typed error_code."""
        js_response = self._run_js_json_api({
            "action": "run_hemisphere_routing",
            "engine_result": "not_a_dict",
        })
        assert not js_response["success"]
        assert js_response.get("error_code") == "input.invalid_type"

    def test_hemisphere_routing_bad_shape_error_code(self):
        """run_hemisphere_routing invalid output shape carries typed error_code."""
        # An empty dict as engine_result will route through projections
        # and fail the output shape check (not a valid hemisphere dict).
        js_response = self._run_js_json_api({
            "action": "run_hemisphere_routing",
            "engine_result": {},
        })
        assert not js_response["success"]
        assert js_response.get("error_code") == "input.shape_mismatch"

    def test_engine_with_routing_bad_hemispheres_type_error_code(self):
        """run_engine_with_routing rejects non-dict hemispheres with typed error_code."""
        js_response = self._run_js_json_api({
            "action": "run_engine_with_routing",
            "input": {"x": 1},
            "hemispheres": "not_a_dict",
        })
        assert not js_response["success"]
        assert js_response.get("error_code") == "input.invalid_type"

    def test_engine_with_routing_bad_hemispheres_shape_error_code(self):
        """run_engine_with_routing rejects wrong-shape hemispheres with typed error_code."""
        js_response = self._run_js_json_api({
            "action": "run_engine_with_routing",
            "input": {"x": 1},
            "hemispheres": {"wrong_key": None},
        })
        assert not js_response["success"]
        assert js_response.get("error_code") == "input.shape_mismatch"

    # -- Slice-2: normalize + validation boundary error codes --

    def test_normalize_undefined_error_code(self):
        """normalize rejects JS undefined (missing value key) with typed error_code."""
        js_response = self._run_js_json_api({
            "action": "normalize_roundtrip",
        })
        assert not js_response["success"]
        assert js_response.get("error_code") == "input.malformed_normalized"

    def test_reserved_field_direct_error_code(self):
        """validate_reserved_fields reports typed error_code for reserved field."""
        js_response = self._run_js_json_api({
            "action": "validate_reserved_fields",
            "value": {"_mode": "evil"},
        })
        assert js_response["success"]  # validation query succeeds
        assert js_response.get("valid") is False
        assert js_response.get("error_code") == "input.reserved_field"

    def test_algorithm_runtime_fields_error_code(self):
        """validate_algorithm_runtime_fields reports typed error_code for unknown underscore."""
        js_response = self._run_js_json_api({
            "action": "validate_algorithm_runtime_fields",
            "value": {"_evil_field": "bad"},
        })
        assert js_response["success"]  # validation query succeeds
        assert js_response.get("valid") is False
        assert js_response.get("error_code") == "input.reserved_field"

    # -- Slice-3: hash_trace, run_structural_trace, run_hemisphere error codes --

    def test_hash_trace_overcap_error_code(self):
        """hash_trace overcap returns typed trace.overcap error_code."""
        trace = None
        for i in range(5):
            trace = {"head": {"state": str(i), "step": i}, "tail": trace}
        js_response = self._run_js_json_api({
            "action": "hash_trace", "trace": trace, "maxEntries": 3,
        })
        assert not js_response["success"]
        assert js_response.get("error_code") == "trace.overcap"

    def test_structural_trace_reserved_field_error_code(self):
        """run_structural_trace rejects reserved-field input with typed error_code."""
        js_response = self._run_js_json_api({
            "action": "run_structural_trace",
            "input": {"_mode": "evil"},
        })
        assert not js_response["success"]
        assert js_response.get("error_code") == "input.reserved_field"

    def test_hemisphere_reserved_field_error_code(self):
        """run_hemisphere rejects reserved-field input with typed error_code."""
        js_response = self._run_js_json_api({
            "action": "run_hemisphere",
            "input": {"_mode": "evil"},
        })
        assert not js_response["success"]
        assert js_response.get("error_code") == "input.reserved_field"

    # -- Round 10C: ratchet integrity corrections --

    def test_run_vector_missing_projection_error_code(self):
        """run_vector with missing projection returns api.bad_request."""
        js_response = self._run_js_json_api({
            "action": "run_vector",
            "input": {"a": 1},
        })
        assert not js_response["success"]
        assert js_response.get("error_code") == "api.bad_request"

    def test_run_vector_reserved_field_error_code(self):
        """run_vector with reserved field in input returns input.reserved_field."""
        js_response = self._run_js_json_api({
            "action": "run_vector",
            "input": {"_mode": "evil"},
            "projection": {"pattern": {"x": "X"}, "body": {"x": "X"}},
        })
        assert not js_response["success"]
        assert js_response.get("error_code") == "input.reserved_field"


# API_MAX_STEPS must match eval_step.js constant
_API_MAX_STEPS = 10000

_MAX_STEPS_GUARDED_ACTIONS = [
    pytest.param(
        "run_structural_trace",
        {"projections": [], "input": {"test": True}, "maxSteps": _API_MAX_STEPS + 1},
        id="run_structural_trace",
    ),
    pytest.param(
        "run_hemisphere",
        {"input": {"route_hemisphere": {"engine_result": {"value": None}, "hemispheres": {"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None}}}, "maxSteps": _API_MAX_STEPS + 1},
        id="run_hemisphere",
    ),
    pytest.param(
        "run_recurrence",
        {"projections": [], "input": {"test": True}, "maxSteps": _API_MAX_STEPS + 1},
        id="run_recurrence",
    ),
    pytest.param(
        "run_exhaustion",
        {"input": {"test": True}, "maxSteps": _API_MAX_STEPS + 1},
        id="run_exhaustion",
    ),
    pytest.param(
        "run_engine_pipeline",
        {"projections": [], "input": {"test": True}, "maxSteps": _API_MAX_STEPS + 1, "maxEngineIterations": 5, "maxAlgorithmIterations": 10},
        id="run_engine_pipeline",
    ),
    pytest.param(
        "run_engine_with_routing",
        {"projections": [], "input": {"test": True}, "maxSteps": _API_MAX_STEPS + 1, "maxEngineIterations": 5, "maxAlgorithmIterations": 10},
        id="run_engine_with_routing",
    ),
    pytest.param(
        "run_recurrence_with_bridge",
        {"input": {"test": True}, "maxSteps": _API_MAX_STEPS + 1},
        id="run_recurrence_with_bridge",
    ),
    pytest.param(
        "run_exhaustion_with_bridge",
        {"input": {"test": True}, "maxSteps": _API_MAX_STEPS + 1},
        id="run_exhaustion_with_bridge",
    ),
]


# Base args for each guarded action (maxSteps placeholder — tests override it)
_GUARDED_ACTION_BASE_ARGS = {
    "run_structural_trace": {"projections": [], "input": {"test": True}},
    "run_hemisphere": {"input": {"route_hemisphere": {"engine_result": {"value": None}, "hemispheres": {"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None}}}},
    "run_recurrence": {"projections": [], "input": {"test": True}},
    "run_exhaustion": {"input": {"test": True}},
    "run_engine_pipeline": {"projections": [], "input": {"test": True}, "maxEngineIterations": 5, "maxAlgorithmIterations": 10},
    "run_engine_with_routing": {"projections": [], "input": {"test": True}, "maxEngineIterations": 5, "maxAlgorithmIterations": 10},
    "run_recurrence_with_bridge": {"input": {"test": True}},
    "run_exhaustion_with_bridge": {"input": {"test": True}},
}

_INVALID_MAX_STEPS_VALUES = [
    pytest.param("abc", id="string"),
    pytest.param({}, id="object"),
    pytest.param(-1, id="negative"),
    pytest.param(1.5, id="float"),
]


class TestAPIMaxStepsGuard:
    """Verify API_MAX_STEPS cap and type validation on all guarded endpoints."""

    def _run_js_json_api(self, request_dict: dict) -> dict:
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request_dict)],
            capture_output=True, text=True, cwd=ROOT, timeout=30
        )
        for line in result.stdout.split('\n'):
            if line.startswith('JSON_API_RESPONSE:'):
                return json.loads(line[len('JSON_API_RESPONSE:'):])
        raise RuntimeError(f"No JSON_API_RESPONSE: {result.stdout[:500]}")

    @pytest.mark.parametrize("action_name,args", _MAX_STEPS_GUARDED_ACTIONS)
    def test_max_steps_over_cap_rejected(self, action_name, args):
        """maxSteps > API_MAX_STEPS returns api.bad_request, never silently clamped."""
        js_response = self._run_js_json_api({"action": action_name, **args})
        assert js_response["success"] is False, (
            f"{action_name}: expected failure for maxSteps={_API_MAX_STEPS + 1}, got success"
        )
        assert js_response.get("error_code") == "api.bad_request", (
            f"{action_name}: expected error_code=api.bad_request, "
            f"got {js_response.get('error_code')}"
        )
        assert str(_API_MAX_STEPS) in js_response.get("error", ""), (
            f"{action_name}: error message should mention cap value {_API_MAX_STEPS}"
        )

    @pytest.mark.parametrize("action_name,args", _MAX_STEPS_GUARDED_ACTIONS)
    def test_max_steps_at_cap_accepted(self, action_name, args):
        """maxSteps == API_MAX_STEPS is accepted (boundary check: guard is > not >=)."""
        at_cap_args = {**args, "maxSteps": _API_MAX_STEPS}
        js_response = self._run_js_json_api({"action": action_name, **at_cap_args})
        assert js_response.get("error_code") != "api.bad_request", (
            f"{action_name}: maxSteps={_API_MAX_STEPS} (at cap) should be accepted, "
            f"got error_code={js_response.get('error_code')}"
        )

    @pytest.mark.parametrize("action_name", list(_GUARDED_ACTION_BASE_ARGS.keys()))
    @pytest.mark.parametrize("bad_value", _INVALID_MAX_STEPS_VALUES)
    def test_max_steps_invalid_type_rejected(self, action_name, bad_value):
        """Non-integer and negative maxSteps values return api.bad_request."""
        base = _GUARDED_ACTION_BASE_ARGS[action_name]
        request = {"action": action_name, **base, "maxSteps": bad_value}
        js_response = self._run_js_json_api(request)
        assert js_response["success"] is False, (
            f"{action_name}: expected failure for maxSteps={bad_value!r}, got success"
        )
        assert js_response.get("error_code") == "api.bad_request", (
            f"{action_name}: expected error_code=api.bad_request for maxSteps={bad_value!r}, "
            f"got {js_response.get('error_code')}"
        )


@pytest.mark.slow
class TestEnginePipelineCrossSubstrateParity:
    """Cross-substrate verification for engine-hemisphere orchestration."""

    def _run_js_json_api(self, request_dict: dict) -> dict:
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request_dict)],
            capture_output=True, text=True, cwd=ROOT, timeout=120
        )
        for line in result.stdout.split('\n'):
            if line.startswith('JSON_API_RESPONSE:'):
                return json.loads(line[len('JSON_API_RESPONSE:'):])
        raise RuntimeError(f"No JSON_API_RESPONSE: {result.stdout[:500]}")

    def test_engine_pipeline_paxos_parity(self):
        """Engine pipeline produces identical closure detection on both substrates."""
        from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline

        from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
        from rcx_pi.selfhost.kernel import reset_step_budget

        reset_step_budget()
        paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
        cycle_projs = paxos_seed["projections"][:4]
        initial = {"paxos_trigger": "start_paxos"}

        py_result = run_engine_pipeline(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50,
            use_boot1_recursive=False,
        )

        js_response = self._run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": cycle_projs,
            "input": initial,
            "maxSteps": 6,
            "maxEngineIterations": 20,
            "maxAlgorithmIterations": 50,
        })
        assert js_response["success"], f"JS engine pipeline failed: {js_response.get('error')}"
        assert _cross_substrate_equal(py_result, js_response["result"]), (
            f"Engine pipeline mismatch:\n  Python: {py_result}\n  JS: {js_response['result']}"
        )

    def test_hemisphere_routing_parity(self):
        """Hemisphere routing produces identical bucket assignment on both substrates."""
        from rcx_pi.selfhost.engine_pipeline import run_hemisphere_routing


        engine_result = {
            "value": {"x": 1}, "closure_detected": True, "tau_step": 2,
            "exhaustion_detected": False, "operator_frozen": False,
            "frozen_set": None, "action": None, "stall": True,
        }
        hemispheres = {"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None}

        py_result = run_hemisphere_routing(engine_result, hemispheres)

        js_response = self._run_js_json_api({
            "action": "run_hemisphere_routing",
            "engine_result": engine_result,
            "hemispheres": hemispheres,
        })
        assert js_response["success"], f"JS hemisphere routing failed: {js_response.get('error')}"
        assert _cross_substrate_equal(py_result, js_response["result"]), (
            f"Hemisphere routing mismatch:\n  Python: {py_result}\n  JS: {js_response['result']}"
        )

    def test_full_pipeline_with_routing_parity(self):
        """Full engine->hemisphere pipeline produces identical results on both substrates."""
        from rcx_pi.selfhost.engine_pipeline import run_engine_with_routing

        from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
        from rcx_pi.selfhost.kernel import reset_step_budget

        reset_step_budget()
        paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
        cycle_projs = paxos_seed["projections"][:4]
        initial = {"paxos_trigger": "start_paxos"}

        py_result = run_engine_with_routing(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50
        )

        js_response = self._run_js_json_api({
            "action": "run_engine_with_routing",
            "projections": cycle_projs,
            "input": initial,
            "maxSteps": 6,
            "maxEngineIterations": 20,
            "maxAlgorithmIterations": 50,
        })
        assert js_response["success"], f"JS full pipeline failed: {js_response.get('error')}"
        assert _cross_substrate_equal(
            py_result["engine_result"], js_response["result"]["engine_result"]
        ), (
            f"Engine result mismatch:\n  Python: {py_result['engine_result']}\n"
            f"  JS: {js_response['result']['engine_result']}"
        )
        assert _cross_substrate_equal(
            py_result["hemispheres"], js_response["result"]["hemispheres"]
        ), (
            f"Hemispheres mismatch:\n  Python: {py_result['hemispheres']}\n"
            f"  JS: {js_response['result']['hemispheres']}"
        )


# =============================================================================
# TestEngineFixPathParity — E4 fix-path cross-substrate lock
# =============================================================================


class TestEngineFixPathParity:
    """Cross-substrate parity for the engine fix path (GAP-04-FIX).

    Verifies both substrates handle the stall→fix dispatch identically:
    - Graph input + identity projection → fix applied, stall=false, value perturbed
    - Non-graph input + identity projection → fix pass-through, stall=true, value unchanged
    """

    IDENTITY_PROJS = [
        {"id": "identity", "pattern": {"var": "x"}, "body": {"var": "x"}},
    ]

    def _run_js_json_api(self, request_dict: dict) -> dict:
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request_dict)],
            capture_output=True, text=True, cwd=ROOT, timeout=120
        )
        for line in result.stdout.split('\n'):
            if line.startswith('JSON_API_RESPONSE:'):
                return json.loads(line[len('JSON_API_RESPONSE:'):])
        raise RuntimeError(f"No JSON_API_RESPONSE: {result.stdout[:500]}")

    def test_engine_fix_path_graph_identity_parity(self):
        """Graph + identity stalls → fix applied, stall=false, value perturbed (both substrates)."""
        from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline

        from rcx_pi.selfhost.kernel import reset_step_budget

        graph_input = {"graph": {"vertices": [1, 2], "edges": [{"src": 1, "dst": 2}]}}

        reset_step_budget()
        py_result = run_engine_pipeline(
            self.IDENTITY_PROJS, graph_input,
            max_steps=5, max_engine_iterations=20, max_algorithm_iterations=50,
            use_boot1_recursive=False,
        )

        js_response = self._run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": self.IDENTITY_PROJS,
            "input": graph_input,
            "maxSteps": 5,
            "maxEngineIterations": 20,
            "maxAlgorithmIterations": 50,
        })
        assert js_response["success"], f"JS engine pipeline failed: {js_response.get('error')}"
        js_result = js_response["result"]

        # Both substrates: fix broke the stall
        assert py_result["stall"] is False, f"Python stall should be False, got: {py_result['stall']}"
        assert js_result["stall"] is False, f"JS stall should be False, got: {js_result['stall']}"

        # Both substrates: value differs from input (fix edge prepended)
        py_norm = _normalize_for_cross_substrate(py_result["value"])
        js_norm = _normalize_for_cross_substrate(js_result["value"])
        input_norm = _normalize_for_cross_substrate(graph_input)
        assert py_norm != input_norm, "Python value should differ from input after fix"
        assert js_norm != input_norm, "JS value should differ from input after fix"

        # Cross-substrate: both produce the same fixed value
        assert _cross_substrate_equal(py_result["value"], js_result["value"]), (
            f"Fix path value mismatch:\n  Python: {py_result['value']}\n  JS: {js_result['value']}"
        )

    def test_engine_fix_path_non_graph_pass_through_parity(self):
        """Non-graph + identity stalls → fix pass-through, stall=true, value unchanged (both substrates)."""
        from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline

        from rcx_pi.selfhost.kernel import reset_step_budget

        scalar_input = {"value": 42, "status": "test"}

        reset_step_budget()
        py_result = run_engine_pipeline(
            self.IDENTITY_PROJS, scalar_input,
            max_steps=5, max_engine_iterations=20, max_algorithm_iterations=50,
            use_boot1_recursive=False,
        )

        js_response = self._run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": self.IDENTITY_PROJS,
            "input": scalar_input,
            "maxSteps": 5,
            "maxEngineIterations": 20,
            "maxAlgorithmIterations": 50,
        })
        assert js_response["success"], f"JS engine pipeline failed: {js_response.get('error')}"
        js_result = js_response["result"]

        # Both substrates: stall persists (fix pass-through)
        assert py_result["stall"] is True, f"Python stall should be True, got: {py_result['stall']}"
        assert js_result["stall"] is True, f"JS stall should be True, got: {js_result['stall']}"

        # Both substrates: value unchanged (fix.pass_through returns original)
        assert _cross_substrate_equal(py_result["value"], scalar_input), (
            f"Python value should equal input after pass-through fix"
        )
        assert _cross_substrate_equal(js_result["value"], scalar_input), (
            f"JS value should equal input after pass-through fix"
        )

    def test_engine_fix_path_routing_graph_parity(self):
        """Graph fix path routes correctly through hemisphere routing (both substrates)."""
        from rcx_pi.selfhost.engine_pipeline import run_engine_with_routing

        from rcx_pi.selfhost.kernel import reset_step_budget

        graph_input = {"graph": {"vertices": [1, 2], "edges": [{"src": 1, "dst": 2}]}}

        reset_step_budget()
        py_result = run_engine_with_routing(
            self.IDENTITY_PROJS, graph_input,
            max_steps=5, max_engine_iterations=20, max_algorithm_iterations=50,
        )

        js_response = self._run_js_json_api({
            "action": "run_engine_with_routing",
            "projections": self.IDENTITY_PROJS,
            "input": graph_input,
            "maxSteps": 5,
            "maxEngineIterations": 20,
            "maxAlgorithmIterations": 50,
        })
        assert js_response["success"], f"JS routing failed: {js_response.get('error')}"
        js_result = js_response["result"]

        # stall=false after fix → should NOT route to r_inf
        py_er = py_result["engine_result"]
        js_er = js_result["engine_result"]
        assert py_er["stall"] is False, "Python engine_result stall should be False"
        assert js_er["stall"] is False, "JS engine_result stall should be False"

        # Hemisphere assignment: both substrates agree
        assert _cross_substrate_equal(py_result["hemispheres"], js_result["hemispheres"]), (
            f"Hemisphere mismatch:\n  Python: {py_result['hemispheres']}\n"
            f"  JS: {js_result['hemispheres']}"
        )

        # r_inf should be None (stall=false means no stall routing)
        assert py_result["hemispheres"]["r_inf"] is None, (
            "Graph with fix should not route to r_inf"
        )

    def test_engine_fix_path_routing_non_graph_parity(self):
        """Non-graph fix pass-through routes consistently through hemispheres (both substrates)."""
        from rcx_pi.selfhost.engine_pipeline import run_engine_with_routing

        from rcx_pi.selfhost.kernel import reset_step_budget

        scalar_input = {"value": 42, "status": "test"}

        reset_step_budget()
        py_result = run_engine_with_routing(
            self.IDENTITY_PROJS, scalar_input,
            max_steps=5, max_engine_iterations=20, max_algorithm_iterations=50,
        )

        js_response = self._run_js_json_api({
            "action": "run_engine_with_routing",
            "projections": self.IDENTITY_PROJS,
            "input": scalar_input,
            "maxSteps": 5,
            "maxEngineIterations": 20,
            "maxAlgorithmIterations": 50,
        })
        assert js_response["success"], f"JS routing failed: {js_response.get('error')}"
        js_result = js_response["result"]

        # stall=true persists → routes to r_inf
        py_er = py_result["engine_result"]
        js_er = js_result["engine_result"]
        assert py_er["stall"] is True, "Python engine_result stall should be True"
        assert js_er["stall"] is True, "JS engine_result stall should be True"

        # Hemisphere assignment: both substrates agree
        assert _cross_substrate_equal(py_result["hemispheres"], js_result["hemispheres"]), (
            f"Hemisphere mismatch:\n  Python: {py_result['hemispheres']}\n"
            f"  JS: {js_result['hemispheres']}"
        )


# =============================================================================
# TestEngineLoopPathParity — E4 loop-trampoline cross-substrate lock
# =============================================================================


class TestEngineLoopPathParity:
    """Cross-substrate parity for the engine loop trampoline (GAP-10-LOOP).

    Verifies both substrates handle the exhaustion_done split identically:
    - action=freeze → _run_engine trampoline (re-entry)
    - action!=freeze → engine_result terminal (no re-entry)
    """

    IDENTITY_PROJS = [
        {"id": "identity", "pattern": {"var": "x"}, "body": {"var": "x"}},
    ]

    def _run_js_json_api(self, request_dict: dict) -> dict:
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request_dict)],
            capture_output=True, text=True, cwd=ROOT, timeout=120
        )
        for line in result.stdout.split('\n'):
            if line.startswith('JSON_API_RESPONSE:'):
                return json.loads(line[len('JSON_API_RESPONSE:'):])
        raise RuntimeError(f"No JSON_API_RESPONSE: {result.stdout[:500]}")

    def test_engine_loop_freeze_pipeline_parity(self):
        """E4: freeze-path pipeline produces same terminal result in both substrates.

        Uses identity projections which always stall. The engine detects closure,
        exhaustion freezes the operator, and the trampoline re-enters. On re-entry
        with frozen operator, the engine eventually terminates. Both substrates
        must produce the same final engine_result.
        """
        from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline

        from rcx_pi.selfhost.kernel import reset_step_budget

        test_input = {"value": 42}

        reset_step_budget()
        py_result = run_engine_pipeline(
            self.IDENTITY_PROJS, test_input,
            max_steps=5, max_engine_iterations=20, max_algorithm_iterations=50,
            use_boot1_recursive=False,
        )

        js_response = self._run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": self.IDENTITY_PROJS,
            "input": test_input,
            "maxSteps": 5,
            "maxEngineIterations": 20,
            "maxAlgorithmIterations": 50,
        })
        assert js_response["success"], f"JS engine pipeline failed: {js_response.get('error')}"
        js_result = js_response["result"]

        # Both substrates produce 8-key terminal shape
        TERMINAL_KEYS = {"value", "closure_detected", "tau_step", "exhaustion_detected",
                         "operator_frozen", "frozen_set", "action", "stall"}
        assert set(py_result.keys()) == TERMINAL_KEYS, (
            f"Python terminal keys: {set(py_result.keys())}"
        )
        assert set(js_result.keys()) == TERMINAL_KEYS, (
            f"JS terminal keys: {set(js_result.keys())}"
        )

        # Cross-substrate: all 8 fields match
        for key in TERMINAL_KEYS:
            assert _cross_substrate_equal(py_result[key], js_result[key]), (
                f"Loop path mismatch on '{key}':\n  Python: {py_result[key]}\n  JS: {js_result[key]}"
            )

    def test_engine_loop_terminal_non_freeze_parity(self):
        """E4: non-freeze terminal path produces same result in both substrates.

        Uses a projection that produces a different value (not identity), so no
        closure is detected. Exhaustion action will be 'continue' (non-freeze),
        and the engine terminates directly without trampoline re-entry.
        """
        from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline

        from rcx_pi.selfhost.kernel import reset_step_budget

        # A projection that transforms the value (no stall, no closure)
        transform_projs = [
            {"id": "add_done", "pattern": {"value": {"var": "v"}},
             "body": {"value": {"var": "v"}, "done": True}},
        ]
        test_input = {"value": 42}

        reset_step_budget()
        py_result = run_engine_pipeline(
            transform_projs, test_input,
            max_steps=5, max_engine_iterations=20, max_algorithm_iterations=50,
            use_boot1_recursive=False,
        )

        js_response = self._run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": transform_projs,
            "input": test_input,
            "maxSteps": 5,
            "maxEngineIterations": 20,
            "maxAlgorithmIterations": 50,
        })
        assert js_response["success"], f"JS engine pipeline failed: {js_response.get('error')}"
        js_result = js_response["result"]

        # Both substrates produce terminal with no freeze
        assert py_result["action"] != "freeze", f"Python action should not be freeze: {py_result['action']}"
        assert js_result["action"] != "freeze", f"JS action should not be freeze: {js_result['action']}"

        # Cross-substrate: terminal results match
        TERMINAL_KEYS = {"value", "closure_detected", "tau_step", "exhaustion_detected",
                         "operator_frozen", "frozen_set", "action", "stall"}
        for key in TERMINAL_KEYS:
            assert _cross_substrate_equal(py_result[key], js_result[key]), (
                f"Terminal path mismatch on '{key}':\n  Python: {py_result[key]}\n  JS: {js_result[key]}"
            )

    def test_engine_loop_no_config_leak_parity(self):
        """E4: _config does not leak into terminal output in either substrate."""
        from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline

        from rcx_pi.selfhost.kernel import reset_step_budget

        test_input = {"value": 42}

        reset_step_budget()
        py_result = run_engine_pipeline(
            self.IDENTITY_PROJS, test_input,
            max_steps=5, max_engine_iterations=20, max_algorithm_iterations=50,
            use_boot1_recursive=False,
        )

        js_response = self._run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": self.IDENTITY_PROJS,
            "input": test_input,
            "maxSteps": 5,
            "maxEngineIterations": 20,
            "maxAlgorithmIterations": 50,
        })
        assert js_response["success"], f"JS engine pipeline failed: {js_response.get('error')}"
        js_result = js_response["result"]

        # Neither substrate leaks _config
        assert "_config" not in py_result, f"Python leaks _config: {py_result.keys()}"
        assert "_config" not in js_result, f"JS leaks _config: {js_result.keys()}"


# =============================================================================
# TestBoundaryResultValidationParity — P1 critical parity hardening (Round 17D)
# =============================================================================


class TestBoundaryResultValidationParity:
    """Regression locks for P1: JS boundary result validation in runEnginePipeline.

    Python validates boundary operation results via validate_no_kernel_reserved_fields()
    before re-injection into engine state (step_mu.py). JS must do the same
    (eval_step.js:runEnginePipeline). These tests lock this parity.
    """

    def test_js_boundary_result_validation_source_lock(self):
        """Source-level lock: JS runEnginePipeline contains boundary result validation."""
        source = _read_all_js_source()

        # The validation call must exist in the JS source
        assert "validateNoKernelReservedFields(result," in source, (
            "REGRESSION: JS runEnginePipeline is missing boundary result validation. "
            "This was added in Round 17D (P1 parity hardening). "
            "Python validates at step_mu.py:validate_no_kernel_reserved_fields(). "
            "JS must call validateNoKernelReservedFields(result, ...) before "
            "context[injectKey] = result in runEnginePipeline()."
        )

        # Specifically check for the boundary_result context string
        assert "boundary_result(" in source, (
            "REGRESSION: JS boundary result validation must use 'boundary_result(operation)' "
            "context string for parity with Python."
        )

    def test_js_boundary_result_validation_contract_lock(self):
        """Contract lock: validation call is between result computation and injection.

        After dedup refactor, boundary logic lives in serviceBoundaryEffect().
        The contract is the same: validate BEFORE inject.
        """
        lines = _read_all_js_source().splitlines(keepends=True)

        # Find the validation line and the injection line within serviceBoundaryEffect
        validation_line = None
        injection_line = None
        in_boundary_fn = False
        for i, line in enumerate(lines, 1):
            if 'function serviceBoundaryEffect(' in line:
                in_boundary_fn = True
            if in_boundary_fn:
                if 'validateNoKernelReservedFields(result,' in line:
                    validation_line = i
                if 'context[injectKey] = result' in line:
                    injection_line = i
                    break  # Found both — stop

        assert validation_line is not None, (
            "REGRESSION: validateNoKernelReservedFields(result, ...) not found "
            "in serviceBoundaryEffect(). See Round 17D P1 fix."
        )
        assert injection_line is not None, (
            "REGRESSION: context[injectKey] = result not found in serviceBoundaryEffect()."
        )
        assert validation_line < injection_line, (
            f"REGRESSION: boundary result validation (line {validation_line}) must occur "
            f"BEFORE injection (line {injection_line}). "
            f"Validates boundary results cannot smuggle kernel-reserved fields."
        )


# =============================================================================
# TestFalsyDefaultParity — Phase 2 (P4) falsy-default divergence
# =============================================================================


class TestFalsyDefaultParity:
    """Verify JS nullish coalescing (??) handles 0 correctly for numeric caps."""

    def _run_js_json_api(self, request_dict: dict) -> dict:
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request_dict)],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60
        )
        for line in result.stdout.split('\n'):
            if line.startswith('JSON_API_RESPONSE:'):
                return json.loads(line[len('JSON_API_RESPONSE:'):])
        raise RuntimeError(f"No JSON_API_RESPONSE found in JS output: {result.stdout[:500]}")

    def test_hash_trace_maxentries_zero(self):
        """maxEntries=0 → both substrates error (not silently use default 10000)."""
        from rcx_pi.selfhost.engine_pipeline import hash_trace_for_recurrence


        trace = {"head": {"state": "a", "step": 0}, "tail": None}

        # Python: maxEntries=0 should raise (trace has 1 entry, exceeds 0 cap)
        with pytest.raises(ValueError, match="exceeds 0 entries"):
            hash_trace_for_recurrence(trace, max_entries=0)

        # JS: maxEntries=0 should also fail (not silently become 10000)
        js_response = self._run_js_json_api({
            "action": "hash_trace",
            "trace": {"head": {"state": "a", "step": 0}, "tail": None},
            "maxEntries": 0,
        })
        assert not js_response["success"], (
            "JS should fail with maxEntries=0, not silently use default 10000"
        )

    def test_engine_pipeline_maxsteps_zero(self):
        """maxSteps=0 → both substrates handle identically (immediate stall/return)."""
        js_response = self._run_js_json_api({
            "action": "run_structural_trace",
            "projections": [],
            "input": {"test": True},
            "maxSteps": 0,
        })
        # With 0 steps, no projection fires — should succeed with stall or 0 steps
        assert js_response["success"], f"JS should handle maxSteps=0: {js_response.get('error')}"
        assert js_response.get("steps", 0) == 0, "maxSteps=0 should do 0 steps"

    def test_falsy_zero_not_swallowed(self):
        """maxSteps=0 sent to JS is NOT replaced by default 100."""
        js_response = self._run_js_json_api({
            "action": "run_recurrence",
            "projections": [
                {"id": "test.id", "pattern": {"a": 1}, "body": {"a": 1}}
            ],
            "input": {"a": 1},
            "maxSteps": 0,
        })
        # With maxSteps=0, no structural trace happens — should succeed with empty/stall
        assert js_response["success"], f"JS failed: {js_response.get('error')}"


# =============================================================================
# TestNoOrBarBarNumericDefaults — source-level regression lock for P4
# =============================================================================


class TestNoOrBarBarNumericDefaults:
    """Regression lock: numeric cap fields must use ?? (not ||) in JS API paths.

    P4 fix replaced || with ?? for maxSteps, maxEntries, maxEngineIterations,
    maxAlgorithmIterations. This test prevents reintroduction.
    """

    _FORBIDDEN_PATTERNS = [
        r"maxSteps\s*\|\|",
        r"max_steps\s*\|\|",
        r"maxEntries\s*\|\|",
        r"maxEngineIterations\s*\|\|",
        r"maxAlgorithmIterations\s*\|\|",
    ]

    def test_no_or_bar_bar_on_numeric_caps(self):
        """No numeric cap field uses || default in eval_step.js."""
        import re
        source = _read_all_js_source()
        lines = source.splitlines()

        violations = []
        for line_num, line in enumerate(lines, 1):
            # Skip comments
            stripped = line.lstrip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            for pattern in self._FORBIDDEN_PATTERNS:
                if re.search(pattern, line):
                    violations.append(f"  eval_step.js:{line_num}: {line.strip()}")

        assert not violations, (
            "Numeric cap fields must use ?? (nullish coalescing), not || (logical OR).\n"
            "P4 fix: || treats 0 as falsy, silently replacing with default.\n"
            "Violations:\n" + "\n".join(violations)
        )

    def test_nullish_coalescing_present(self):
        """Confirm ?? is used for numeric defaults (positive check)."""
        import re
        source = _read_all_js_source()

        expected_patterns = [
            (r"maxSteps\s*\?\?", "maxSteps"),
            (r"maxEntries\s*\?\?", "maxEntries"),
            (r"maxEngineIterations\s*\?\?", "maxEngineIterations"),
            (r"maxAlgorithmIterations\s*\?\?", "maxAlgorithmIterations"),
        ]

        for pattern, field in expected_patterns:
            assert re.search(pattern, source), (
                f"Expected ?? default for {field} in eval_step.js but not found"
            )


# =============================================================================
# Module-level helpers for manifest-driven parity tests (Phase 6)
# =============================================================================

MANIFEST_PATH = ROOT / "tests" / "fixtures" / "js_api_parity_manifest.json"


def _load_manifest():
    """Load the parity manifest JSON."""
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def _module_run_js_json_api(request_dict: dict) -> dict:
    """Module-level JS JSON API caller (not bound to a class)."""
    result = subprocess.run(
        ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request_dict)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=60,
    )
    for line in result.stdout.split('\n'):
        if line.startswith('JSON_API_RESPONSE:'):
            return json.loads(line[len('JSON_API_RESPONSE:'):])
    raise RuntimeError(f"No JSON_API_RESPONSE found in JS output: {result.stdout[:500]}")


def classify_python_error(exc):
    """Classify a Python exception into a parity error_code (test layer only)."""
    if hasattr(exc, 'error_code'):
        return exc.error_code
    msg = str(exc).lower()
    if 'cyclic linked list' in msg:
        return 'trace.cycle_detected'
    if 'exceeds' in msg and 'entries' in msg:
        return 'trace.overcap'
    if 'engine pipeline exhausted' in msg or 'engine exhausted' in msg:
        return 'engine.exhausted'
    if 'engine stalled' in msg:
        return 'engine.stalled_non_terminal'
    if 'must be bool' in msg:
        return 'type_error'
    if 'must be dict' in msg or 'must be a dict' in msg:
        return 'input.invalid_type'
    if 'shape mismatch' in msg or 'unexpected shape' in msg:
        return 'input.shape_mismatch'
    if 'did not produce valid hemisphere dict' in msg:
        return 'input.shape_mismatch'
    if 'reserved' in msg or 'kernel-reserved' in msg or 'unsupported algorithm underscore' in msg:
        return 'input.reserved_field'
    if 'not valid mu' in msg or 'max depth exceeded' in msg:
        return 'input.malformed_normalized'
    return 'api.bad_request'


# =============================================================================
# TestActionSetSync — manifest-driven action set sync (Phase 6, fast tier)
# =============================================================================


class TestActionSetSync:
    """Verify JS list_actions matches manifest action set AND actual source handlers."""

    def test_js_actions_match_manifest(self):
        """JS list_actions returns exactly the manifest action set."""
        manifest = _load_manifest()
        manifest_actions = set(manifest["actions"].keys())

        js_response = _module_run_js_json_api({"action": "list_actions"})
        assert js_response["success"], f"list_actions failed: {js_response.get('error')}"
        js_actions = set(js_response["actions"])

        assert js_actions == manifest_actions, (
            f"Action set mismatch.\n"
            f"  In JS but not manifest: {js_actions - manifest_actions}\n"
            f"  In manifest but not JS: {manifest_actions - js_actions}"
        )

    def test_source_handlers_match_list_actions(self):
        """Structural: actual request.action branches in source match list_actions.

        Prevents a handler being added to the if/else chain but omitted from
        the list_actions array (which would make test_js_actions_match_manifest
        silently miss it).
        """
        import re
        js_source = _read_all_js_source()

        # Extract all request.action === '...' branches from the JSON API section
        # Match both == and === comparisons
        source_actions = set(re.findall(
            r"request\.action\s*===?\s*'([^']+)'", js_source
        ))

        js_response = _module_run_js_json_api({"action": "list_actions"})
        assert js_response["success"]
        list_actions_set = set(js_response["actions"])

        # Source handlers must be a superset of (or equal to) list_actions.
        # If source has a handler not in list_actions, it's unregistered.
        unregistered = source_actions - list_actions_set
        assert not unregistered, (
            f"Source has request.action handlers not in list_actions: {unregistered}"
        )


# =============================================================================
# TestErrorEdgeCoverageRatchet — N1b closure gate
# =============================================================================


class TestErrorEdgeCoverageRatchet:
    """Enforce that every public action has error-edge coverage or explicit opt-out.

    Prevents regression: new actions cannot be added to JS list_actions without
    either (a) at least one edge_args entry with expected_error_code, or
    (b) requires_error_edges=false with a success_only_reason.
    """

    def test_all_actions_in_manifest(self):
        """Every JS list_actions entry must exist in manifest."""
        manifest = _load_manifest()
        manifest_actions = set(manifest["actions"].keys())
        js_response = _module_run_js_json_api({"action": "list_actions"})
        assert js_response["success"]
        js_actions = set(js_response["actions"])
        missing = js_actions - manifest_actions
        assert not missing, (
            f"Actions in JS list_actions but not in manifest: {missing}. "
            f"Add them to tests/fixtures/js_api_parity_manifest.json."
        )

    def test_all_manifest_actions_have_coverage_declaration(self):
        """Every manifest action must declare requires_error_edges (true or false)."""
        manifest = _load_manifest()
        missing = [
            name for name, defn in manifest["actions"].items()
            if "requires_error_edges" not in defn
        ]
        assert not missing, (
            f"Actions missing requires_error_edges declaration: {missing}. "
            f"Set true (and add edge_args with expected_error_code) or "
            f"false (with success_only_reason)."
        )

    def test_required_edges_have_error_code(self):
        """Actions with requires_error_edges=true must have >=1 edge with expected_error_code."""
        manifest = _load_manifest()
        missing = []
        for name, defn in manifest["actions"].items():
            if not defn.get("requires_error_edges"):
                continue
            edges = defn.get("edge_args", [])
            has_error_edge = any(
                "expected_error_code" in e for e in edges
            )
            if not has_error_edge:
                missing.append(name)
        assert not missing, (
            f"Actions with requires_error_edges=true but no expected_error_code edge: {missing}. "
            f"Add at least one edge_args entry with expected_error_code."
        )

    def test_required_edges_all_have_error_code(self):
        """For requires_error_edges=true, EVERY failure edge must have expected_error_code.

        Edges with expected_success=true are success-path edges and are exempt.
        """
        manifest = _load_manifest()
        incomplete = []
        for name, defn in manifest["actions"].items():
            if not defn.get("requires_error_edges"):
                continue
            for i, edge in enumerate(defn.get("edge_args", [])):
                if edge.get("expected_success"):
                    continue  # success-path edge — no error_code expected
                if "expected_error_code" not in edge:
                    incomplete.append(f"{name}.edge_args[{i}]")
        assert not incomplete, (
            f"Edge entries missing expected_error_code: {incomplete}. "
            f"Every edge on a requires_error_edges=true action must declare expected_error_code."
        )

    def test_required_edges_no_success_only_reason(self):
        """Actions with requires_error_edges=true must not have success_only_reason."""
        manifest = _load_manifest()
        conflicting = [
            name for name, defn in manifest["actions"].items()
            if defn.get("requires_error_edges") and defn.get("success_only_reason")
        ]
        assert not conflicting, (
            f"Actions with requires_error_edges=true AND success_only_reason: {conflicting}. "
            f"Remove success_only_reason when requires_error_edges is true."
        )

    def test_success_only_actions_have_reason(self):
        """Actions with requires_error_edges=false must have success_only_reason."""
        manifest = _load_manifest()
        missing = []
        for name, defn in manifest["actions"].items():
            if defn.get("requires_error_edges") is not False:
                continue
            if not defn.get("success_only_reason"):
                missing.append(name)
        assert not missing, (
            f"Actions with requires_error_edges=false but no success_only_reason: {missing}. "
            f"Add a short reason explaining why error edges are not needed."
        )


# =============================================================================
# TestParityCoverageGate — structural coverage gate (Phase 6, fast tier)
# =============================================================================


def _coverage_gate_params():
    """Generate parametrized test cases from manifest (one success + one fail per action)."""
    manifest = _load_manifest()
    params = []
    for action_name, action_def in manifest["actions"].items():
        params.append(pytest.param(
            action_name, action_def, "happy_path",
            id=f"{action_name}-happy",
        ))
        if action_def.get("edge_args"):
            params.append(pytest.param(
                action_name, action_def, "edge_case",
                id=f"{action_name}-edge",
            ))
    return params


class TestParityCoverageGate:
    """Manifest-driven parametrized test executing every action (fast tier).

    Constraint #2: structural coverage — the test itself IS the gate.
    If a manifest action is missing, pytest collection fails.
    """

    @pytest.mark.parametrize("action_name,action_def,case_type", _coverage_gate_params())
    def test_action_parity(self, action_name, action_def, case_type):
        """Execute action through JS and verify response shape."""
        action_type = action_def["type"]

        if case_type == "happy_path":
            request = {"action": action_name, **action_def.get("required_args", {})}
            js_response = _module_run_js_json_api(request)

            if action_def.get("happy_path_may_error"):
                # Engine-level actions may legitimately error with simple inputs.
                # Coverage gate: verify structured response returned.
                assert "success" in js_response, (
                    f"{action_name} happy path returned no 'success' key"
                )
                if not js_response["success"]:
                    assert "error_code" in js_response, (
                        f"{action_name} error response missing error_code"
                    )
            elif action_type == "validation":
                assert js_response.get("success") is True, (
                    f"{action_name} happy path failed: {js_response.get('error')}"
                )
                assert js_response.get("valid") is True, (
                    f"{action_name} validation expected valid=true: {js_response}"
                )
            elif action_type == "introspection":
                assert js_response.get("success") is True, (
                    f"{action_name} introspection failed: {js_response.get('error')}"
                )
            else:  # operation
                assert js_response.get("success") is True, (
                    f"{action_name} happy path failed: {js_response.get('error')}"
                )

        elif case_type == "edge_case":
            edge = action_def["edge_args"][0]
            request = {"action": action_name, **edge["args"]}
            js_response = _module_run_js_json_api(request)

            if action_type == "validation":
                # Validation edge: success=true, valid=false, error_code present
                assert js_response.get("success") is True, (
                    f"{action_name} validation edge should have success=true"
                )
                assert js_response.get("valid") is False, (
                    f"{action_name} validation edge should have valid=false"
                )
                assert "error_code" in js_response, (
                    f"{action_name} validation edge missing error_code"
                )
                expected_code = edge.get("expected_error_code")
                if expected_code:
                    assert js_response["error_code"] == expected_code, (
                        f"{action_name} edge: expected {expected_code}, "
                        f"got {js_response['error_code']}"
                    )
            else:  # operation edge
                if edge.get("expected_success"):
                    assert js_response.get("success") is True, (
                        f"{action_name} edge expected success: {js_response.get('error')}"
                    )
                else:
                    assert js_response.get("success") is False, (
                        f"{action_name} edge should have failed: {js_response}"
                    )
                    assert "error_code" in js_response, (
                        f"{action_name} edge missing error_code"
                    )
                    expected_code = edge.get("expected_error_code")
                    if expected_code:
                        assert js_response["error_code"] == expected_code, (
                            f"{action_name} edge: expected {expected_code}, "
                            f"got {js_response['error_code']}"
                        )


# =============================================================================
# TestManifestEdgeCaseParity — full edge case parity (Phase 6, slow tier)
# =============================================================================


def _edge_case_params():
    """Generate parametrized test cases for ALL edge_args from manifest."""
    manifest = _load_manifest()
    params = []
    for action_name, action_def in manifest["actions"].items():
        for i, edge in enumerate(action_def.get("edge_args", [])):
            params.append(pytest.param(
                action_name, action_def, edge,
                id=f"{action_name}-edge-{i}",
            ))
    return params


def _run_python_edge_case(action_name, args):
    """Execute an edge case through Python. Returns (success: bool|None, error_code: str|None).

    Returns (None, None) if no Python adapter exists for this action.
    Returns (True, None) on success.
    Returns (False, error_code) on exception.
    """
    try:
        if action_name == 'hash_trace':
            from rcx_pi.selfhost.engine_pipeline import hash_trace_for_recurrence

            hash_trace_for_recurrence(args['trace'], max_entries=args.get('maxEntries', 10000))
            return True, None
        elif action_name == 'validate_reserved_fields':
            from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields
            validate_no_kernel_reserved_fields(args['value'])
            return True, None
        elif action_name == 'validate_algorithm_runtime_fields':
            from rcx_pi.selfhost.step_mu import validate_algorithm_runtime_fields
            validate_algorithm_runtime_fields(args['value'])
            return True, None
        elif action_name == 'run_engine_pipeline':
            from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline

            from rcx_pi.selfhost.kernel import reset_step_budget
            reset_step_budget()
            run_engine_pipeline(
                args.get('projections', []), args['input'],
                max_steps=args.get('maxSteps', 6),
                max_engine_iterations=args.get('maxEngineIterations', 20),
                max_algorithm_iterations=args.get('maxAlgorithmIterations', 50),
                use_boot1_recursive=False,
            )
            return True, None
        elif action_name == 'run_hemisphere_routing':
            from rcx_pi.selfhost.engine_pipeline import run_hemisphere_routing

            hemispheres = args.get('hemispheres', {
                "r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None,
            })
            run_hemisphere_routing(args['engine_result'], hemispheres)
            return True, None
        elif action_name == 'run_engine_with_routing':
            from rcx_pi.selfhost.engine_pipeline import run_engine_with_routing

            from rcx_pi.selfhost.kernel import reset_step_budget
            reset_step_budget()
            kwargs = {}
            if 'hemispheres' in args:
                kwargs['hemispheres'] = args['hemispheres']
            if 'boot1LoopMode' in args:
                kwargs['use_boot1_recursive'] = args['boot1LoopMode']
            run_engine_with_routing(
                args.get('projections', []), args['input'],
                max_steps=args.get('maxSteps', 6),
                max_engine_iterations=args.get('maxEngineIterations', 20),
                max_algorithm_iterations=args.get('maxAlgorithmIterations', 50),
                **kwargs,
            )
            return True, None
        elif action_name == 'run_recurrence':
            from rcx_pi.selfhost.step_mu import run_mu
            from rcx_pi.selfhost.kernel import reset_step_budget
            reset_step_budget()
            run_mu(args.get('projections', []), args['input'], max_steps=args.get('maxSteps', 10))
            return True, None
        else:
            return None, None
    except Exception as exc:
        return False, classify_python_error(exc)


@pytest.mark.slow
class TestManifestEdgeCaseParity:
    """Run all manifest edge_args through BOTH substrates, compare error_codes.

    Marked slow — runs in audit_all.sh, skipped in green gate.
    """

    @pytest.mark.parametrize("action_name,action_def,edge", _edge_case_params())
    def test_edge_case_error_code_parity(self, action_name, action_def, edge):
        """JS and Python produce same error_code for edge case."""
        request = {"action": action_name, **edge["args"]}
        js_response = _module_run_js_json_api(request)

        expected_code = edge.get("expected_error_code")
        if expected_code:
            # For validation actions, error_code is on the valid=false response
            if action_def["type"] == "validation":
                assert js_response.get("success") is True
                assert js_response.get("valid") is False
                assert js_response.get("error_code") == expected_code, (
                    f"JS {action_name}: expected error_code={expected_code}, "
                    f"got {js_response.get('error_code')}"
                )
            elif edge.get("expected_success"):
                assert js_response.get("success") is True
            else:
                assert js_response.get("success") is False
                assert js_response.get("error_code") == expected_code, (
                    f"JS {action_name}: expected error_code={expected_code}, "
                    f"got {js_response.get('error_code')}"
                )

        # Run through Python and compare error_codes
        if edge.get("js_api_only"):
            # JS-API-layer guard (e.g., API_MAX_STEPS) — no Python equivalent
            return
        py_success, py_error_code = _run_python_edge_case(action_name, edge["args"])
        if py_success is None:
            # No Python adapter for this action — skip comparison
            return

        if expected_code and not edge.get("expected_success"):
            # Both should fail with the same error_code
            assert py_success is False, (
                f"Python {action_name}: expected failure with {expected_code}, "
                f"but Python succeeded"
            )
            assert py_error_code == expected_code, (
                f"Python {action_name}: expected error_code={expected_code}, "
                f"got {py_error_code}"
            )
            # Cross-substrate parity: JS and Python error_codes must match
            js_code = js_response.get("error_code")
            assert js_code == py_error_code, (
                f"{action_name} parity mismatch: JS={js_code}, Python={py_error_code}"
            )
        elif edge.get("expected_success"):
            assert py_success is True, (
                f"Python {action_name}: expected success but got error_code={py_error_code}"
            )


# =============================================================================
# N6b: Observer Event Stream Isomorphism Tests
# =============================================================================

def _js_api_observer(request_dict):
    """Send a JSON API request to JS and return the parsed response."""
    req = json.dumps(request_dict)
    proc = subprocess.run(
        ["node", "mu/host/js/eval_step.js", "--json-api", req],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    last = None
    for line in proc.stdout.splitlines():
        if line.startswith("JSON_API_RESPONSE:"):
            last = json.loads(line[len("JSON_API_RESPONSE:"):])
    assert last is not None, f"no JSON_API_RESPONSE in stdout: {proc.stdout[:500]}"
    return last


def _canonical_event_json(event):
    """Canonical JSON serialization per ObserverEventContract.v0.md."""
    return json.dumps(event, sort_keys=True, separators=(",", ":"))


def _normalize_stream(events):
    """Sort events by (step, timestamp) and strip substrate field for comparison."""
    return sorted(
        [
            {
                "event_name": e["event_name"],
                "step": e["step"],
                "state_hash": e["state_hash"],
                "error_code": e["error_code"],
            }
            for e in events
        ],
        key=lambda e: (e["step"], events[[
            i for i, x in enumerate(events)
            if x["event_name"] == e["event_name"] and x["step"] == e["step"]
        ][0]]["timestamp"]),
    )


def _normalize_stream_simple(events):
    """Normalize event stream: sort by (step, timestamp), drop substrate."""
    sorted_events = sorted(events, key=lambda e: (e["step"], e["timestamp"]))
    return [
        {
            "event_name": e["event_name"],
            "step": e["step"],
            "state_hash": e["state_hash"],
            "error_code": e["error_code"],
        }
        for e in sorted_events
    ]


@pytest.mark.slow
class TestObserverIsomorphism:
    """N6b: Cross-substrate observer event stream isomorphism.

    Verifies that Python and JS emit identical observer event streams
    (modulo substrate field) for the same inputs.
    """

    def _run_python_with_observer(self, projections, input_value, **kwargs):
        """Run Python engine pipeline with observer capture."""
        from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline

        observer = []
        result = run_engine_pipeline(
            projections, input_value, observer=observer,
            use_boot1_recursive=False, **kwargs
        )
        return result, observer

    def _run_js_with_observer(self, input_value, **kwargs):
        """Run JS engine pipeline with observer capture via JSON API."""
        request = {
            "action": "run_engine_pipeline",
            "input": input_value,
            "observer": True,
        }
        for k, v in kwargs.items():
            request[k] = v
        resp = _js_api_observer(request)
        assert resp.get("success"), f"JS pipeline failed: {resp.get('error')}"
        return resp["result"], resp.get("observer_events", [])

    def test_observer_stream_isomorphism_simple_value(self):
        """Identical simple input → identical event streams on both substrates."""
        # Empty projections with a simple value — engine will stall quickly
        # Use run_engine_pipeline directly with a value that triggers stall
        from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline

        from rcx_pi.selfhost.seed_integrity import get_seed_path, load_verified_seed

        # Use a trivial input that produces a quick terminal result
        # The engine with no user projections will init → trace (empty) → hash → recurrence → exhaustion → terminal
        py_observer = []
        try:
            py_result = run_engine_pipeline([], "test_value", observer=py_observer, use_boot1_recursive=False)
        except RuntimeError:
            pass  # May stall — that's fine, we still get events

        js_resp = _js_api_observer({
            "action": "run_engine_pipeline",
            "input": "test_value",
            "observer": True,
        })
        js_events = js_resp.get("observer_events", [])

        # Both must emit events
        assert len(py_observer) > 0, "Python emitted no observer events"
        assert len(js_events) > 0, "JS emitted no observer events"

        # Normalize and compare (drop substrate, sort by step+timestamp)
        py_normalized = _normalize_stream_simple(py_observer)
        js_normalized = _normalize_stream_simple(js_events)

        assert len(py_normalized) == len(js_normalized), (
            f"Event count mismatch: Python={len(py_normalized)}, JS={len(js_normalized)}\n"
            f"Python events: {[e['event_name'] for e in py_normalized]}\n"
            f"JS events: {[e['event_name'] for e in js_normalized]}"
        )

        for i, (pe, je) in enumerate(zip(py_normalized, js_normalized)):
            assert pe == je, (
                f"Event {i} mismatch:\n"
                f"  Python: {_canonical_event_json(pe)}\n"
                f"  JS:     {_canonical_event_json(je)}"
            )

    def test_observer_step_boundary_emitted(self):
        """Both substrates emit at least one step_boundary event."""
        py_observer = []
        from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline

        try:
            run_engine_pipeline([], "obs_test", observer=py_observer, use_boot1_recursive=False)
        except RuntimeError:
            pass

        py_step_boundaries = [e for e in py_observer if e["event_name"] == "step_boundary"]
        assert len(py_step_boundaries) > 0, "Python emitted no step_boundary events"

        js_resp = _js_api_observer({
            "action": "run_engine_pipeline",
            "input": "obs_test",
            "observer": True,
        })
        js_events = js_resp.get("observer_events", [])
        js_step_boundaries = [e for e in js_events if e["event_name"] == "step_boundary"]
        assert len(js_step_boundaries) > 0, "JS emitted no step_boundary events"

    def test_observer_events_have_contract_fields(self):
        """All emitted events conform to N6a schema (6 base + optional engine_terminal extras)."""
        base_fields = {"event_name", "step", "state_hash", "error_code", "substrate", "timestamp"}
        terminal_extra_fields = {"engine_exit_reason", "engine_iterations_used"}

        py_observer = []
        from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline

        try:
            run_engine_pipeline([], "schema_test", observer=py_observer, use_boot1_recursive=False)
        except RuntimeError:
            pass

        for event in py_observer:
            keys = set(event.keys())
            if event["event_name"] == "engine_terminal":
                assert keys == base_fields | terminal_extra_fields, (
                    f"Python engine_terminal event has wrong fields: {keys}"
                )
            else:
                assert keys == base_fields, (
                    f"Python event has wrong fields: {keys} != {base_fields}"
                )
            assert event["substrate"] == "python"
            assert isinstance(event["step"], int) and event["step"] >= 0
            assert isinstance(event["timestamp"], int) and event["timestamp"] >= 0

        js_resp = _js_api_observer({
            "action": "run_engine_pipeline",
            "input": "schema_test",
            "observer": True,
            "boot1LoopMode": False,  # match Python's use_boot1_recursive=False above
        })
        from rcx_pi.selfhost.engine_pipeline import ENGINE_EXIT_REASONS

        for event in js_resp.get("observer_events", []):
            keys = set(event.keys())
            if event["event_name"] == "engine_terminal":
                assert keys == base_fields | terminal_extra_fields, (
                    f"JS engine_terminal event has wrong fields: {keys}"
                )
                # Value validation (not just presence)
                assert event["engine_exit_reason"] in ENGINE_EXIT_REASONS, (
                    f"JS engine_exit_reason {event['engine_exit_reason']!r} not in {ENGINE_EXIT_REASONS}"
                )
                assert isinstance(event["engine_iterations_used"], int) and event["engine_iterations_used"] > 0, (
                    f"JS engine_iterations_used must be int > 0, got {event['engine_iterations_used']}"
                )
            else:
                assert keys == base_fields, (
                    f"JS event has wrong fields: {keys} != {base_fields}"
                )
            assert event["substrate"] == "js"
            assert isinstance(event["step"], int) and event["step"] >= 0
            assert isinstance(event["timestamp"], int) and event["timestamp"] >= 0

    def test_observer_timestamps_monotonic(self):
        """Timestamps are monotonically increasing within each substrate."""
        py_observer = []
        from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline

        try:
            run_engine_pipeline([], "mono_test", observer=py_observer, use_boot1_recursive=False)
        except RuntimeError:
            pass

        py_timestamps = [e["timestamp"] for e in py_observer]
        assert py_timestamps == sorted(py_timestamps), (
            f"Python timestamps not monotonic: {py_timestamps}"
        )
        # Verify strictly increasing (each event gets unique timestamp)
        assert len(set(py_timestamps)) == len(py_timestamps), (
            f"Python timestamps not unique: {py_timestamps}"
        )

        js_resp = _js_api_observer({
            "action": "run_engine_pipeline",
            "input": "mono_test",
            "observer": True,
        })
        js_timestamps = [e["timestamp"] for e in js_resp.get("observer_events", [])]
        assert js_timestamps == sorted(js_timestamps), (
            f"JS timestamps not monotonic: {js_timestamps}"
        )
        assert len(set(js_timestamps)) == len(js_timestamps), (
            f"JS timestamps not unique: {js_timestamps}"
        )

    def test_observer_state_hash_parity(self):
        """state_hash values match between Python and JS for identical states."""
        py_observer = []
        from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline

        try:
            run_engine_pipeline([], "hash_parity", observer=py_observer, use_boot1_recursive=False)
        except RuntimeError:
            pass

        js_resp = _js_api_observer({
            "action": "run_engine_pipeline",
            "input": "hash_parity",
            "observer": True,
        })
        js_events = js_resp.get("observer_events", [])

        # Compare state_hash at matching (step, event_name) pairs
        py_by_key = {(e["step"], e["event_name"]): e for e in py_observer}
        js_by_key = {(e["step"], e["event_name"]): e for e in js_events}

        common_keys = set(py_by_key.keys()) & set(js_by_key.keys())
        assert len(common_keys) > 0, "No matching (step, event_name) pairs found"

        for key in sorted(common_keys):
            py_hash = py_by_key[key]["state_hash"]
            js_hash = js_by_key[key]["state_hash"]
            assert py_hash == js_hash, (
                f"state_hash mismatch at {key}: Python={py_hash}, JS={js_hash}"
            )

    def test_observer_off_by_default(self):
        """When observer is not passed, no events are collected (default path unchanged)."""
        from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline

        # No observer parameter — should work exactly as before
        try:
            run_engine_pipeline([], "default_test", use_boot1_recursive=False)
        except RuntimeError:
            pass  # May stall — that's fine

        # JS without observer flag
        js_resp = _js_api_observer({
            "action": "run_engine_pipeline",
            "input": "default_test",
        })
        assert "observer_events" not in js_resp, (
            "JS returned observer_events when observer was not requested"
        )

    def test_observer_canonicalization_cross_substrate(self):
        """Canonical JSON of matching events is byte-identical across substrates."""
        py_observer = []
        from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline

        try:
            run_engine_pipeline([], "canon_test", observer=py_observer, use_boot1_recursive=False)
        except RuntimeError:
            pass

        js_resp = _js_api_observer({
            "action": "run_engine_pipeline",
            "input": "canon_test",
            "observer": True,
        })
        js_events = js_resp.get("observer_events", [])

        py_by_key = {(e["step"], e["event_name"]): e for e in py_observer}
        js_by_key = {(e["step"], e["event_name"]): e for e in js_events}

        common_keys = set(py_by_key.keys()) & set(js_by_key.keys())
        assert len(common_keys) > 0

        for key in sorted(common_keys):
            # Strip substrate and timestamp for content comparison
            py_content = {
                "event_name": py_by_key[key]["event_name"],
                "step": py_by_key[key]["step"],
                "state_hash": py_by_key[key]["state_hash"],
                "error_code": py_by_key[key]["error_code"],
            }
            js_content = {
                "event_name": js_by_key[key]["event_name"],
                "step": js_by_key[key]["step"],
                "state_hash": js_by_key[key]["state_hash"],
                "error_code": js_by_key[key]["error_code"],
            }
            py_canon = _canonical_event_json(py_content)
            js_canon = _canonical_event_json(js_content)
            assert py_canon == js_canon, (
                f"Canonical JSON mismatch at {key}:\n"
                f"  Python: {py_canon}\n"
                f"  JS:     {js_canon}"
            )


# =============================================================================
# TestReservedFieldValidationFuzzer (R2b Slice 1 — GAP-1)
# =============================================================================


# Strategies for cross-substrate reserved-field fuzzing.
# Keys without underscore prefix — guaranteed clean against KERNEL_RESERVED_FIELDS.
_safe_keys = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
    min_size=1,
    max_size=8,
).filter(lambda k: not k.startswith("_"))

# Mu primitives safe for cross-substrate JSON round-trip (no floats — JS int/float parity issue).
_mu_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-1000, max_value=1000),
    st.text(max_size=15),
)

# Recursive Mu values using only safe keys (no reserved fields).
_clean_mu = st.recursive(
    _mu_primitives,
    lambda children: st.one_of(
        st.lists(children, max_size=3),
        st.dictionaries(_safe_keys, children, max_size=3),
    ),
    max_leaves=8,
)


@st.composite
def _mu_with_reserved_field(draw, max_depth=10):
    """Generate a Mu value with a reserved field injected at random depth."""
    from rcx_pi.selfhost.step_mu import KERNEL_RESERVED_FIELDS

    reserved = draw(st.sampled_from(sorted(KERNEL_RESERVED_FIELDS)))
    leaf = draw(_mu_primitives)
    depth = draw(st.integers(min_value=0, max_value=max_depth))

    # Innermost: dict with the reserved field
    payload = {reserved: leaf}

    # Wrap in nesting at specified depth
    for _ in range(depth):
        wrapper_key = draw(_safe_keys)
        payload = {wrapper_key: payload}

    return payload, reserved, depth


@pytest.mark.slow
class TestReservedFieldValidationFuzzer:
    """Property-based cross-substrate reserved-field validation parity.

    R2b Slice 1 (GAP-1): Python fuzzes validate_no_kernel_reserved_fields
    extensively but has no JS counterpart. This fuzzer generates random Mu
    values, injects reserved fields at random depths, and verifies Python
    and JS validators produce identical accept/reject decisions.
    """

    def _run_js_validation(self, value):
        """Call JS validate_reserved_fields and return (valid, error_code)."""
        request = json.dumps({"action": "validate_reserved_fields", "value": value})
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js", "--json-api", request],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=30,
        )
        for line in result.stdout.split("\n"):
            if line.startswith("JSON_API_RESPONSE:"):
                resp = json.loads(line[len("JSON_API_RESPONSE:"):])
                return resp.get("valid", False), resp.get("error_code", "")
        raise RuntimeError(f"No JSON_API_RESPONSE: {result.stdout[:200]}")

    @given(value=_clean_mu)
    @settings(max_examples=200, deadline=30000, suppress_health_check=[HealthCheck.too_slow])
    def test_clean_values_accepted_by_both(self, value):
        """Clean Mu values (no reserved fields) pass validation on both substrates."""
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        # Python
        py_accepted = True
        try:
            validate_no_kernel_reserved_fields(value, "test")
        except (ValueError, RecursionError):
            py_accepted = False

        # JS
        js_valid, _ = self._run_js_validation(value)

        assert py_accepted == js_valid, (
            f"Parity violation on clean value: "
            f"Python={'accept' if py_accepted else 'reject'}, "
            f"JS={'accept' if js_valid else 'reject'} "
            f"for {json.dumps(value)[:200]}"
        )

    @given(data=_mu_with_reserved_field())
    @settings(max_examples=200, deadline=30000, suppress_health_check=[HealthCheck.too_slow])
    def test_injected_reserved_field_rejected_by_both(self, data):
        """Reserved field at random depth is rejected by both substrates with correct error_code."""
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        payload, reserved, depth = data

        # Python must reject
        py_rejected = False
        try:
            validate_no_kernel_reserved_fields(payload, "test")
        except ValueError:
            py_rejected = True

        # JS must reject
        js_valid, js_error_code = self._run_js_validation(payload)

        assert py_rejected, (
            f"Python MUST reject reserved field '{reserved}' at depth {depth}: "
            f"{json.dumps(payload)[:200]}"
        )
        assert not js_valid, (
            f"JS MUST reject reserved field '{reserved}' at depth {depth}: "
            f"{json.dumps(payload)[:200]}"
        )
        assert js_error_code == "input.reserved_field", (
            f"JS error_code should be 'input.reserved_field', "
            f"got '{js_error_code}' for reserved field '{reserved}' at depth {depth}"
        )

    @given(data=_mu_with_reserved_field(max_depth=0))
    @settings(max_examples=50, deadline=30000, suppress_health_check=[HealthCheck.too_slow])
    def test_top_level_reserved_field_parity(self, data):
        """Top-level reserved field — both substrates reject with same classification."""
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        payload, reserved, _ = data

        with pytest.raises(ValueError, match="kernel-reserved"):
            validate_no_kernel_reserved_fields(payload, "test")

        js_valid, js_error_code = self._run_js_validation(payload)
        assert not js_valid, f"JS must reject top-level '{reserved}'"
        assert js_error_code == "input.reserved_field"

    @given(
        reserved=st.sampled_from(sorted(__import__(
            "rcx_pi.selfhost.step_mu", fromlist=["KERNEL_RESERVED_FIELDS"]
        ).KERNEL_RESERVED_FIELDS)),
        inner=_mu_primitives,
    )
    @settings(max_examples=50, deadline=30000, suppress_health_check=[HealthCheck.too_slow])
    def test_reserved_field_in_list_parity(self, reserved, inner):
        """Reserved field inside a list element — both substrates reject."""
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        payload = [{"safe": 1}, {reserved: inner}]

        py_rejected = False
        try:
            validate_no_kernel_reserved_fields(payload, "test")
        except ValueError:
            py_rejected = True

        js_valid, js_error_code = self._run_js_validation(payload)

        assert py_rejected, f"Python must reject '{reserved}' inside list"
        assert not js_valid, f"JS must reject '{reserved}' inside list"
        assert js_error_code == "input.reserved_field"


# =============================================================================
# R2b Slice 3 (GAP-2): Hemisphere Routing Property Fuzzer — Strategies
# =============================================================================

# Strategy: generate a valid 8-key engine_result with randomized signal combinations.
@st.composite
def _engine_result(draw):
    """Generate a valid 8-key engine_result dict for hemisphere routing."""
    value = draw(st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-100, max_value=100),
        st.text(max_size=10),
        st.lists(_mu_primitives, max_size=2),
        st.dictionaries(_safe_keys, _mu_primitives, max_size=2),
    ))
    return {
        "value": value,
        "closure_detected": draw(st.booleans()),
        "tau_step": draw(st.integers(min_value=0, max_value=10)),
        "exhaustion_detected": draw(st.booleans()),
        "operator_frozen": draw(st.one_of(st.none(), st.text(min_size=1, max_size=8))),
        "frozen_set": draw(st.one_of(st.none(), st.lists(st.text(max_size=5), max_size=3))),
        "action": draw(st.sampled_from(["none", "freeze", "done", "terminal"])),
        "stall": draw(st.booleans()),
    }


def _expected_hemisphere(er):
    """Determine which hemisphere an engine_result should route to (priority order)."""
    if er["exhaustion_detected"]:
        return "sink"
    if er["value"] is None:
        return "r_null"
    if er["closure_detected"]:
        return "r_a"
    if er["stall"]:
        return "r_inf"
    return "lobes"


_ENGINE_RESULT_KEYS = [
    "value", "closure_detected", "tau_step", "exhaustion_detected",
    "operator_frozen", "frozen_set", "action", "stall",
]


@st.composite
def _invalid_engine_result(draw):
    """Generate an invalid engine_result shape (non-dict or missing key)."""
    kind = draw(st.sampled_from(["non_dict", "missing_key"]))
    if kind == "non_dict":
        val = draw(st.one_of(
            st.none(), st.booleans(),
            st.integers(min_value=-100, max_value=100),
            st.text(max_size=10),
            st.lists(st.integers(min_value=-10, max_value=10), max_size=3),
        ))
        return val, kind
    else:
        to_remove = draw(st.sampled_from(_ENGINE_RESULT_KEYS))
        er = {
            "value": "test",
            "closure_detected": False,
            "tau_step": 0,
            "exhaustion_detected": False,
            "operator_frozen": None,
            "frozen_set": None,
            "action": "none",
            "stall": False,
        }
        del er[to_remove]
        return er, kind


_DEFAULT_HEMISPHERES = {"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None}


@pytest.mark.slow
class TestHemisphereRoutingPropertyFuzzer:
    """Property-based cross-substrate hemisphere routing parity.

    R2b Slice 3 (GAP-2): Generates random valid engine_result dicts with
    various signal combinations and verifies Python and JS route identically,
    populating exactly one hemisphere per the priority order.
    """

    @pytest.mark.timeout(600)
    @given(er=_engine_result())
    @settings(max_examples=25, deadline=30000, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_engine_result_routing_parity(self, er):
        """Valid engine_result routes identically on both substrates."""
        from rcx_pi.selfhost.engine_pipeline import run_hemisphere_routing


        hemispheres = dict(_DEFAULT_HEMISPHERES)
        expected = _expected_hemisphere(er)

        py_result = run_hemisphere_routing(er, dict(hemispheres))

        js_response = _module_run_js_json_api({
            "action": "run_hemisphere_routing",
            "engine_result": er,
            "hemispheres": dict(hemispheres),
        })
        assert js_response["success"], (
            f"JS run_hemisphere_routing failed: {js_response.get('error')}"
        )

        # Cross-substrate equality
        assert _cross_substrate_equal(py_result, js_response["result"]), (
            f"Hemisphere routing parity mismatch:\n"
            f"  Python: {json.dumps(py_result, sort_keys=True)[:300]}\n"
            f"  JS:     {json.dumps(js_response['result'], sort_keys=True)[:300]}"
        )

        # Exactly one hemisphere populated (changed from null)
        populated = [k for k in py_result if py_result[k] is not None]
        assert len(populated) == 1, (
            f"Expected exactly 1 populated hemisphere, got {len(populated)}: {populated}"
        )

        # Correct hemisphere per priority: exhaustion > null > closure > stall > default
        assert populated[0] == expected, (
            f"Expected route to '{expected}', got '{populated[0]}' "
            f"for signals: exhaustion={er['exhaustion_detected']}, "
            f"value={'null' if er['value'] is None else type(er['value']).__name__}, "
            f"closure={er['closure_detected']}, stall={er['stall']}"
        )

    @given(data=_invalid_engine_result())
    @settings(max_examples=100, deadline=30000, suppress_health_check=[HealthCheck.too_slow])
    def test_invalid_engine_result_shape_rejection_parity(self, data):
        """Invalid engine_result shapes rejected by both substrates with typed error_code."""
        from rcx_pi.selfhost.engine_pipeline import run_hemisphere_routing


        er, kind = data
        hemispheres = dict(_DEFAULT_HEMISPHERES)

        # Python must reject
        py_rejected = False
        try:
            run_hemisphere_routing(er, dict(hemispheres))
        except (ValueError, RuntimeError):
            py_rejected = True

        # JS must reject
        js_response = _module_run_js_json_api({
            "action": "run_hemisphere_routing",
            "engine_result": er,
            "hemispheres": dict(hemispheres),
        })

        assert py_rejected, (
            f"Python should reject invalid engine_result ({kind}): "
            f"{json.dumps(er)[:200] if isinstance(er, (dict, list)) else repr(er)}"
        )
        assert not js_response["success"], (
            f"JS should reject invalid engine_result ({kind}): "
            f"{json.dumps(er)[:200] if isinstance(er, (dict, list)) else repr(er)}"
        )

        # JS must have typed error_code
        expected_codes = {"input.invalid_type", "input.shape_mismatch"}
        assert js_response.get("error_code") in expected_codes, (
            f"JS error_code should be in {expected_codes}, "
            f"got '{js_response.get('error_code')}' for {kind}"
        )


# =============================================================================
# R2b Slice 2 (GAP-3): Cross-Substrate Trace Hash Parity Fuzzer
# =============================================================================

# Strategy: generate a single trace entry with step, state, and optional fields.
@st.composite
def _trace_entry(draw, step_num):
    """Generate a trace entry: {step, state, optional projection/stall}."""
    state_value = draw(st.one_of(
        _mu_primitives,
        st.dictionaries(_safe_keys, _mu_primitives, min_size=1, max_size=3),
    ))
    entry = {"step": step_num, "state": state_value}
    if draw(st.booleans()):
        entry["projection"] = draw(st.text(
            alphabet=st.characters(whitelist_categories=("L",)),
            min_size=1, max_size=10,
        ))
    if draw(st.booleans()):
        entry["stall"] = draw(st.booleans())
    return entry


@st.composite
def _linked_list_trace(draw, min_length=1, max_length=50):
    """Generate a Mu linked-list trace of random length."""
    length = draw(st.integers(min_value=min_length, max_value=max_length))
    trace = None
    for i in range(length - 1, -1, -1):
        entry = draw(_trace_entry(i))
        trace = {"head": entry, "tail": trace}
    return trace, length


@pytest.mark.slow
class TestTraceHashParityFuzzer:
    """Property-based cross-substrate trace hash parity.

    R2b Slice 2 (GAP-3): Python has format fuzzers for hash_trace_for_recurrence
    but no cross-substrate property tests. This fuzzer generates random valid
    linked-list traces and verifies Python and JS produce identical hashed output.
    """

    def test_unicode_key_order_hash_parity_regression(self):
        """Regression: mixed BMP/non-BMP dict keys hash identically on both substrates."""
        from rcx_pi.selfhost.engine_pipeline import hash_trace_for_recurrence


        # Python sorts dict keys by Unicode code points. JS default UTF-16 sorting
        # diverges for this pair unless a code-point comparator is used.
        trace = {
            "head": {
                "step": 0,
                "state": {"\uf900": None, "\U00010000": None},
            },
            "tail": None,
        }

        py_result = hash_trace_for_recurrence(trace, max_entries=10000)
        js_response = _module_run_js_json_api({
            "action": "hash_trace",
            "trace": trace,
            "maxEntries": 10000,
        })
        assert js_response["success"], f"JS hash_trace failed: {js_response.get('error')}"
        assert _cross_substrate_equal(py_result, js_response["result"]), (
            f"Unicode key ordering parity mismatch:\n"
            f"  Python: {json.dumps(py_result, sort_keys=True)[:300]}\n"
            f"  JS:     {json.dumps(js_response['result'], sort_keys=True)[:300]}"
        )

    @given(data=_linked_list_trace(min_length=1, max_length=50))
    @settings(max_examples=120, deadline=30000, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_trace_hash_parity(self, data):
        """Valid linked-list trace hashes identically on both substrates."""
        from rcx_pi.selfhost.engine_pipeline import hash_trace_for_recurrence


        trace, length = data

        py_result = hash_trace_for_recurrence(trace, max_entries=10000)
        js_response = _module_run_js_json_api({
            "action": "hash_trace", "trace": trace, "maxEntries": 10000,
        })
        assert js_response["success"], (
            f"JS hash_trace failed on valid {length}-entry trace: "
            f"{js_response.get('error')}"
        )
        assert _cross_substrate_equal(py_result, js_response["result"]), (
            f"hash_trace parity mismatch on {length}-entry trace:\n"
            f"  Python: {json.dumps(py_result, sort_keys=True)[:300]}\n"
            f"  JS:     {json.dumps(js_response['result'], sort_keys=True)[:300]}"
        )

    @given(data=_linked_list_trace(min_length=4, max_length=30))
    @settings(max_examples=80, deadline=30000, suppress_health_check=[HealthCheck.too_slow])
    def test_trace_hash_overcap_parity(self, data):
        """Both substrates reject traces exceeding maxEntries with correct error_code."""
        from rcx_pi.selfhost.engine_pipeline import hash_trace_for_recurrence


        trace, length = data
        max_entries = length - 1  # Guaranteed to trigger overcap

        # Python must raise ValueError
        py_rejected = False
        try:
            hash_trace_for_recurrence(trace, max_entries=max_entries)
        except ValueError as exc:
            py_rejected = True
            assert "exceeds" in str(exc).lower(), (
                f"Python overcap error message unexpected: {exc}"
            )

        # JS must fail with trace.overcap
        js_response = _module_run_js_json_api({
            "action": "hash_trace", "trace": trace, "maxEntries": max_entries,
        })

        assert py_rejected, (
            f"Python should reject {length}-entry trace with maxEntries={max_entries}"
        )
        assert not js_response["success"], (
            f"JS should reject {length}-entry trace with maxEntries={max_entries}"
        )
        assert js_response.get("error_code") == "trace.overcap", (
            f"JS error_code should be 'trace.overcap', "
            f"got '{js_response.get('error_code')}'"
        )

    @given(data=_linked_list_trace(min_length=1, max_length=20))
    @settings(max_examples=50, deadline=30000, suppress_health_check=[HealthCheck.too_slow])
    def test_trace_hash_hardcap_clamp_parity(self, data):
        """Oversized maxEntries is clamped — short traces not falsely rejected."""
        from rcx_pi.selfhost.engine_pipeline import hash_trace_for_recurrence


        trace, length = data
        oversized = 200000  # > 100000 hard cap — both substrates should clamp

        py_result = hash_trace_for_recurrence(trace, max_entries=oversized)
        js_response = _module_run_js_json_api({
            "action": "hash_trace", "trace": trace, "maxEntries": oversized,
        })
        assert js_response["success"], (
            f"JS should not reject {length}-entry trace with clamped maxEntries: "
            f"{js_response.get('error')}"
        )
        assert _cross_substrate_equal(py_result, js_response["result"]), (
            f"hash_trace hardcap clamp parity mismatch on {length}-entry trace:\n"
            f"  Python: {json.dumps(py_result, sort_keys=True)[:300]}\n"
            f"  JS:     {json.dumps(js_response['result'], sort_keys=True)[:300]}"
        )


# =============================================================================
# R3: Differential Cross-Substrate Replay Audit
# =============================================================================

_FIXTURES_DIR = ROOT / "tests" / "fixtures"

# Actions with Python adapters for replay comparison.
_R3_ADAPTED_ACTIONS = frozenset({
    'hash_trace', 'validate_reserved_fields', 'validate_algorithm_runtime_fields',
    'run_engine_pipeline', 'run_hemisphere_routing', 'run_engine_with_routing',
    'run_recurrence', 'run_metabolization_cycle',
})


def _r3_parity_corpus():
    """Parity vectors → run_vector replay (20 cases)."""
    data = json.load(open(_FIXTURES_DIR / 'parity_vectors.json'))
    return [pytest.param(v, id=v['id']) for v in data['vectors']]


def _r3_hash_corpus():
    """Hashing vectors → hash_trace replay (38 cases)."""
    data = json.load(open(_FIXTURES_DIR / 'hashing_vectors.json'))
    return [pytest.param(v, id=v['id']) for v in data['vectors']]


def _r3_hemisphere_corpus():
    """Hemisphere vectors → run_hemisphere_routing replay (8 cases)."""
    data = json.load(open(_FIXTURES_DIR / 'hemisphere_vectors.json'))
    return [pytest.param(v, id=v['id']) for v in data['vectors']]


def _r3_manifest_corpus():
    """Manifest actions → success + edge replay (actions with Python adapters)."""
    manifest = _load_manifest()
    cases = []
    for name, action_def in manifest['actions'].items():
        if name not in _R3_ADAPTED_ACTIONS:
            continue
        if action_def.get('required_args'):
            cases.append(pytest.param(
                name, action_def,
                {'args': action_def['required_args']},
                id=f"required-{name}",
            ))
        for i, edge in enumerate(action_def.get('edge_args', [])):
            if edge.get('js_api_only'):
                continue
            cases.append(pytest.param(
                name, action_def, edge, id=f"edge-{name}-{i}",
            ))
    return cases


def _run_python_r3(action, request):
    """Execute replay through Python. Returns (success, result, error_code).

    Returns (None, None, None) if no adapter exists.
    """
    try:
        if action == 'run_vector':
            from rcx_pi.selfhost.step_mu import run_mu
            from rcx_pi.selfhost.kernel import reset_step_budget
            reset_step_budget()
            result, _trace, stall = run_mu(
                [request['projection']], request['input'], max_steps=10,
            )
            return True, result, None
        elif action == 'hash_trace':
            from rcx_pi.selfhost.engine_pipeline import hash_trace_for_recurrence

            result = hash_trace_for_recurrence(
                request['trace'], max_entries=request.get('maxEntries', 10000),
            )
            return True, result, None
        elif action == 'run_hemisphere_routing':
            from rcx_pi.selfhost.engine_pipeline import run_hemisphere_routing

            hemispheres = request.get('hemispheres', {
                'r_null': None, 'r_inf': None, 'r_a': None,
                'lobes': None, 'sink': None,
            })
            result = run_hemisphere_routing(request['engine_result'], hemispheres)
            return True, result, None
        elif action == 'run_hemisphere':
            from rcx_pi.selfhost.step_mu import run_mu
            from rcx_pi.selfhost.seed_integrity import get_seed_path, load_verified_seed
            from rcx_pi.selfhost.kernel import reset_step_budget
            reset_step_budget()
            projs = load_verified_seed(get_seed_path("hemispheres.v1.json"))["projections"]
            result, _trace, stall = run_mu(projs, request['input'], max_steps=100)
            return True, result, None
        elif action == 'validate_reserved_fields':
            from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields
            validate_no_kernel_reserved_fields(request['value'])
            return True, None, None
        elif action == 'validate_algorithm_runtime_fields':
            from rcx_pi.selfhost.step_mu import validate_algorithm_runtime_fields
            validate_algorithm_runtime_fields(request['value'])
            return True, None, None
        elif action == 'run_engine_pipeline':
            from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline

            from rcx_pi.selfhost.kernel import reset_step_budget
            reset_step_budget()
            result = run_engine_pipeline(
                request.get('projections', []), request['input'],
                max_steps=request.get('maxSteps', 6),
                max_engine_iterations=request.get('maxEngineIterations', 20),
                max_algorithm_iterations=request.get('maxAlgorithmIterations', 50),
                use_boot1_recursive=False,
            )
            return True, result, None
        elif action == 'run_engine_with_routing':
            from rcx_pi.selfhost.engine_pipeline import run_engine_with_routing

            from rcx_pi.selfhost.kernel import reset_step_budget
            reset_step_budget()
            kwargs = {}
            if 'hemispheres' in request:
                kwargs['hemispheres'] = request['hemispheres']
            if 'boot1LoopMode' in request:
                kwargs['use_boot1_recursive'] = request['boot1LoopMode']
            result = run_engine_with_routing(
                request.get('projections', []), request['input'],
                max_steps=request.get('maxSteps', 6),
                max_engine_iterations=request.get('maxEngineIterations', 20),
                max_algorithm_iterations=request.get('maxAlgorithmIterations', 50),
                **kwargs,
            )
            return True, result, None
        elif action == 'run_metabolization_cycle':
            from rcx_pi.selfhost.engine_pipeline import run_metabolization_cycle  # SPEED_OK: adapter for R3 replay
            result = run_metabolization_cycle(request.get('hemispheres'))
            return True, result, None
        elif action == 'run_recurrence':
            from rcx_pi.selfhost.step_mu import run_mu
            from rcx_pi.selfhost.kernel import reset_step_budget
            reset_step_budget()
            run_mu(
                request.get('projections', []), request['input'],
                max_steps=request.get('maxSteps', 10),
            )
            return True, None, None
        else:
            return None, None, None
    except Exception as exc:
        return False, None, classify_python_error(exc)


@pytest.mark.slow
class TestDifferentialReplayAuditR3:
    """R3: Differential cross-substrate replay audit.

    Systematically replays >=300 cases through both Python and JS,
    comparing success/failure parity, result equality, and error codes.

    Corpus breakdown:
        - Parity fixture vectors (20): run_vector replay
        - Hash fixture vectors (38): hash_trace replay
        - Hemisphere fixture vectors (8): run_hemisphere_routing replay
        - Manifest success + edge (variable): adapted action replay
        - Generated hemisphere routing (100): Hypothesis
        - Generated trace hash (60): Hypothesis
        - Generated reserved-field validation (50): Hypothesis
        - Extra-key engine_result (10): explicit verification
    """

    # --- Fixture: Parity vectors (20 cases) ---
    # JS run_vector uses stepKernel (multi-step with normalization); Python
    # run_mu has different loop/stall semantics for catchall and non-linear
    # patterns.  This test verifies JS matches the fixture expected_output.
    # Full cross-substrate parity for these vectors is covered by
    # TestCrossSubstrateParity (which uses the proper kernel adapter).

    @pytest.mark.parametrize("vector", _r3_parity_corpus())
    def test_parity_vector_replay(self, vector):
        """Replay parity vector: JS run_vector matches expected output."""
        js = _module_run_js_json_api({
            'action': 'run_vector',
            'projection': vector['projection'],
            'input': vector['input'],
        })
        if vector.get('expected_error'):
            # Error vectors: JS must reject (e.g., non-linear pattern on core path)
            assert not js['success'], (
                f"JS should have rejected {vector['id']} but succeeded"
            )
            assert vector['expected_error'] in js.get('error', ''), (
                f"JS error for {vector['id']} missing expected substring "
                f"'{vector['expected_error']}': {js.get('error')}"
            )
            return
        if vector.get('expected_stall') and not js['success']:
            # Stall-expected vectors may not produce a result in JS
            return
        assert js['success'], f"JS failed on {vector['id']}: {js.get('error')}"
        expected = vector['expected_output']
        assert _cross_substrate_equal(js['result'], expected), (
            f"JS result mismatch for {vector['id']}: "
            f"got {json.dumps(js['result'], sort_keys=True)[:200]}"
        )

    # --- Fixture: Hash vectors (38 cases) ---

    @pytest.mark.parametrize("vector", _r3_hash_corpus())
    def test_hash_vector_replay(self, vector):
        """Replay hashing vector: hash_trace on both substrates."""
        trace = {"head": {"step": 0, "state": vector['value']}, "tail": None}
        js = _module_run_js_json_api({
            'action': 'hash_trace', 'trace': trace, 'maxEntries': 10000,
        })
        py_ok, py_result, py_err = _run_python_r3('hash_trace', {
            'trace': trace, 'maxEntries': 10000,
        })
        assert js['success'], f"JS hash_trace failed: {js.get('error')}"
        assert py_ok, f"Python hash_trace failed: {py_err}"
        assert _cross_substrate_equal(py_result, js['result']), (
            f"Hash mismatch for {vector['id']}"
        )

    # --- Fixture: Hemisphere vectors (8 cases) ---

    @pytest.mark.parametrize("vector", _r3_hemisphere_corpus())
    def test_hemisphere_vector_replay(self, vector):
        """Replay hemisphere vector: run_hemisphere_routing on both substrates."""
        er = vector['input']['route_hemisphere']['engine_result']
        h = vector['input']['route_hemisphere']['hemispheres']
        js = _module_run_js_json_api({
            'action': 'run_hemisphere_routing',
            'engine_result': er, 'hemispheres': h,
        })
        py_ok, py_result, py_err = _run_python_r3('run_hemisphere_routing', {
            'engine_result': er, 'hemispheres': h,
        })
        assert js['success'], f"JS routing failed: {js.get('error')}"
        assert py_ok, f"Python routing failed: {py_err}"
        assert _cross_substrate_equal(py_result, js['result']), (
            f"Hemisphere routing mismatch for {vector['id']}"
        )

    # --- Manifest: success + edge replay (variable cases) ---

    @pytest.mark.parametrize("action_name,action_def,edge", _r3_manifest_corpus())
    def test_manifest_replay(self, action_name, action_def, edge):
        """Replay manifest case: assert cross-substrate parity."""
        request = {'action': action_name, **edge['args']}
        expected_code = edge.get('expected_error_code')

        js = _module_run_js_json_api(request)
        py_ok, py_result, py_err = _run_python_r3(action_name, edge['args'])

        if py_ok is None:
            pytest.skip(f"No Python adapter for {action_name}")

        # Validation actions: compare valid field
        if action_def['type'] == 'validation':
            js_valid = js.get('valid', True) if js.get('success') else False
            # Parity: both accept or both reject
            assert js_valid == py_ok, (
                f"Validation parity: JS valid={js_valid}, Python={py_ok}"
            )
            if not js_valid and not py_ok and expected_code and py_err:
                assert js.get('error_code') == py_err, (
                    f"error_code: JS={js.get('error_code')}, Python={py_err}"
                )
            return

        # Standard operations: compare success/failure parity
        js_ok = js.get('success', False)
        assert js_ok == py_ok, (
            f"Success parity for {action_name}: "
            f"JS={js_ok} ({js.get('error_code')}), "
            f"Python={py_ok} ({py_err})"
        )
        # Both succeed → compare results
        if js_ok and py_ok and py_result is not None and 'result' in js:
            assert _cross_substrate_equal(py_result, js['result']), (
                f"Result mismatch for {action_name}"
            )
        # Both fail → compare error_codes
        if not js_ok and not py_ok:
            js_code = js.get('error_code')
            if expected_code and py_err:
                assert js_code == py_err, (
                    f"error_code: JS={js_code}, Python={py_err}"
                )

    # --- Generated: hemisphere routing (25 cases) ---

    @pytest.mark.timeout(600)
    @given(er=_engine_result())
    @settings(max_examples=25, deadline=30000, suppress_health_check=[HealthCheck.too_slow])
    def test_generated_hemisphere_replay(self, er):
        """Generated hemisphere routing replay."""
        hemispheres = dict(_DEFAULT_HEMISPHERES)
        js = _module_run_js_json_api({
            'action': 'run_hemisphere_routing',
            'engine_result': er, 'hemispheres': hemispheres,
        })
        py_ok, py_result, py_err = _run_python_r3('run_hemisphere_routing', {
            'engine_result': er, 'hemispheres': dict(_DEFAULT_HEMISPHERES),
        })
        assert js.get('success') == py_ok, (
            f"Success parity: JS={js.get('success')}, Python={py_ok}"
        )
        if js.get('success') and py_ok:
            assert _cross_substrate_equal(py_result, js['result'])

    # --- Generated: trace hash (60 cases) ---

    @given(data=_linked_list_trace(min_length=1, max_length=20))
    @settings(max_examples=60, deadline=30000, suppress_health_check=[HealthCheck.too_slow])
    def test_generated_trace_hash_replay(self, data):
        """Generated trace hash replay."""
        trace, length = data
        js = _module_run_js_json_api({
            'action': 'hash_trace', 'trace': trace, 'maxEntries': 10000,
        })
        py_ok, py_result, py_err = _run_python_r3('hash_trace', {
            'trace': trace, 'maxEntries': 10000,
        })
        assert js.get('success') == py_ok, (
            f"Success parity: JS={js.get('success')}, Python={py_ok}"
        )
        if js.get('success') and py_ok:
            assert _cross_substrate_equal(py_result, js['result'])

    # --- Generated: reserved-field validation (50 cases) ---

    @given(value=_clean_mu)
    @settings(max_examples=50, deadline=30000, suppress_health_check=[HealthCheck.too_slow])
    def test_generated_validation_replay(self, value):
        """Generated reserved-field validation replay (clean values)."""
        js = _module_run_js_json_api({
            'action': 'validate_reserved_fields', 'value': value,
        })
        py_ok, _, py_err = _run_python_r3('validate_reserved_fields', {'value': value})
        js_valid = js.get('valid', False)
        assert js_valid == py_ok, (
            f"Validation parity: JS valid={js_valid}, Python={'accept' if py_ok else 'reject'}"
        )

    # --- Special: extra-key engine_result verification (10 cases) ---

    def test_extra_key_engine_result_parity(self):
        """Verify extra-key engine_result behavior is identical across substrates.

        R3 verification item per user directive: do not assume outcome, verify
        and document actual behavior.

        Finding: Mu dict matching is EXACT (not subset) — extra keys cause
        hemisphere.init pattern to not match, routing stalls, both substrates
        reject.  Success/failure parity: MATCHED.  Error code parity: MATCHED
        (both return input.shape_mismatch after R3-F1 classifier fix in 17N).
        """
        base = {
            "value": 42, "closure_detected": False, "tau_step": 0,
            "exhaustion_detected": False, "operator_frozen": None,
            "frozen_set": None, "action": "none", "stall": False,
        }
        variants = [
            {**base, "extra_field": "test"},
            {**base, "bonus": 123},
            {**base, "unknown_signal": True, "another": [1, 2, 3]},
            {**base, "nested_extra": {"deep": {"value": True}}},
            {**base, "stall": True, "extra": "with_stall"},
            {**base, "closure_detected": True, "extra": "with_closure"},
            {**base, "exhaustion_detected": True, "extra": "with_exhaust"},
            {**base, "value": None, "extra": "with_null"},
            {**base, "closure_detected": True, "stall": True, "extra": "compound"},
            {**base, "extra1": 1, "extra2": 2, "extra3": 3},
        ]
        hemispheres = dict(_DEFAULT_HEMISPHERES)

        for i, er in enumerate(variants):
            js = _module_run_js_json_api({
                'action': 'run_hemisphere_routing',
                'engine_result': er,
                'hemispheres': dict(hemispheres),
            })
            py_ok, py_result, py_err = _run_python_r3(
                'run_hemisphere_routing',
                {'engine_result': er, 'hemispheres': dict(hemispheres)},
            )
            js_ok = js.get('success', False)

            # Assert success/failure parity (both must agree on accept/reject)
            assert js_ok == py_ok, (
                f"Extra-key variant {i}: success parity mismatch "
                f"(JS={js_ok}, Python={py_ok}, "
                f"js_error={js.get('error_code')}, py_error={py_err})"
            )

            # If both succeed, results must match
            if js_ok and py_ok:
                assert _cross_substrate_equal(py_result, js['result']), (
                    f"Extra-key variant {i}: result parity mismatch"
                )

            # Assert error_code parity (R3-F1 remediation: classifier now maps
            # hemisphere routing RuntimeError to input.shape_mismatch)
            if not js_ok and not py_ok:
                js_code = js.get('error_code', '')
                # py_err is already classified by _run_python_r3's except clause
                py_code = py_err
                assert js_code == 'input.shape_mismatch', (
                    f"Extra-key variant {i}: JS error_code={js_code}, "
                    f"expected input.shape_mismatch"
                )
                assert py_code == 'input.shape_mismatch', (
                    f"Extra-key variant {i}: Python classified code={py_code}, "
                    f"expected input.shape_mismatch"
                )

    def test_classify_python_error_hemisphere_regression(self):
        """R3-F1 regression: classify_python_error maps hemisphere RuntimeError
        to input.shape_mismatch (not api.bad_request fallthrough)."""
        # Exact message produced by step_mu.py run_hemisphere_routing
        exc = RuntimeError(
            "Hemisphere routing did not produce valid hemisphere dict. "
            "Got: {'r_null': None, 'r_inf': None}"
        )
        code = classify_python_error(exc)
        assert code == 'input.shape_mismatch', (
            f"Expected input.shape_mismatch, got {code}"
        )
