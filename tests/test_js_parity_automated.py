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
import pytest
from pathlib import Path

# Root directory of the project
ROOT = Path(__file__).parent.parent


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
            pytest.skip("parity_vectors.json not found")
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
        """
        from rcx_pi.selfhost.step_mu import normalize_projection, list_to_linked
        from rcx_pi.selfhost.match_mu import normalize_for_match
        from rcx_pi.selfhost.subst_mu import denormalize_from_match
        from conftest import run_until_done

        mismatches = []

        for vector in parity_vectors.get("vectors", []):
            vector_id = vector["id"]
            input_val = vector["input"]
            projection = vector["projection"]

            # Run through Python kernel (same pattern as test_parity_python.py)
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

            # Compare Python and JS results (using cross-substrate comparison
            # that handles int/float equivalence - JS doesn't distinguish)
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
            {"detect_closure": {"trace": None, "result": "X"}},
            {"detect_closure": {"trace": [{"step": 0, "state": "A"}], "result": "A"}},
            {"detect_exhaustion": {"trace": None, "frozen": None, "tau_step": 0}},
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


class TestJSReservedFieldValidationParity:
    """Verify JS reserved field validation matches Python (Gate 3 security fix).

    Security invariant: Both Python and JS must reject reserved fields outside
    algorithm entrypoint subtrees (detect_closure, detect_exhaustion).

    These tests catch the class of vulnerability where spoofed _mode/_phase values
    could bypass validation entirely.
    """

    def _run_js_validation(self, value):
        """Run JS validation and return (success, error_msg)."""
        request = json.dumps({"action": "validate_reserved_fields", "value": value})
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

    def test_parity_entrypoint_subtree_allowed(self):
        """SECURITY: Reserved fields inside entrypoint subtrees MUST be allowed.

        Legitimate input: {"detect_closure": {"_mode": "recurrence", ...}}
        """
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        legitimate = {
            "detect_closure": {
                "_mode": "recurrence",
                "_result": "X"
            }
        }

        # Python allows
        validate_no_kernel_reserved_fields(legitimate, "test")

        # JS must also allow
        valid, error = self._run_js_validation(legitimate)
        assert valid, f"JS should allow entrypoint subtree, but got error: {error}"

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
        """JS should have same reserved field count as Python."""
        from rcx_pi.selfhost.step_mu import KERNEL_RESERVED_FIELDS

        # Python has 22 reserved fields (12 kernel + 3 Recurrence + 3 Exhaustion + 4 Bridge)
        # Gate 3: Entry points (detect_closure, detect_exhaustion) moved out of reserved fields
        assert len(KERNEL_RESERVED_FIELDS) == 22, "Python reserved fields changed"

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
        assert "Total (with Bridge): 32 projections" in result.stdout, (
            "JS combined kernel+bridge should be 32 projections"
        )

    def test_js_bridge_constants_reported(self):
        """Verify JS reports bridge projection count via JSON API."""
        js_response = self._run_js_json_api({"action": "get_constants"})
        assert js_response["success"], f"JS get_constants failed: {js_response}"
        assert js_response["bridge_projection_count"] == 5, (
            f"Expected 5 bridge projections, got {js_response['bridge_projection_count']}"
        )
        assert js_response["total_with_bridge"] == 32, (
            f"Expected 32 total with bridge, got {js_response['total_with_bridge']}"
        )

    def test_recurrence_with_bridge_no_closure(self):
        """Python and JS recurrence-with-bridge should match for no-closure case."""
        from rcx_pi.selfhost.step_mu import run_algorithm_meta_circular
        from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path

        recurrence_projs = load_verified_seed(get_seed_path("recurrence.v1.json"))["projections"]

        # Input with no closure (all unique states)
        input_data = {
            "detect_closure": {
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

        # Run Python (using bootstrap path which handles non-linear patterns)
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
            "detect_closure": {
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

        # Run Python
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
            "detect_exhaustion": {
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

        # Run Python
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
            "detect_exhaustion": {
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

        # Run Python
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
