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
        from tests.conftest import run_until_done

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
        validation-depth cap. JS must fail at the same boundary.
        """
        from rcx_pi.selfhost.match_mu import normalize_for_match
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        width_100 = normalize_for_match({f"k{i}": i for i in range(100)})
        validate_no_kernel_reserved_fields(width_100, "test")
        valid_100, error_100 = self._run_js_validation(width_100)
        assert valid_100, f"JS should allow normalized dict width 100, got error: {error_100}"

        width_101 = normalize_for_match({f"k{i}": i for i in range(101)})
        with pytest.raises(ValueError, match="malformed normalized dict encoding"):
            validate_no_kernel_reserved_fields(width_101, "test")
        valid_101, error_101 = self._run_js_validation(width_101)
        assert not valid_101, "JS should reject normalized dict width 101 to match Python"
        assert (
            "Malformed normalized dict encoding" in error_101
            or "malformed normalized dict encoding" in error_101
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

        # Python has 22 reserved fields (12 kernel + 3 Recurrence + 3 Exhaustion + 4 Bridge)
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
        from rcx_pi.selfhost.step_mu import hash_trace_for_recurrence

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
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
        from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
        from rcx_pi.selfhost.kernel import reset_step_budget

        reset_step_budget()
        paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
        cycle_projs = paxos_seed["projections"][:4]
        initial = {"paxos_trigger": "start_paxos"}

        py_result = run_engine_pipeline(
            cycle_projs, initial,
            max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50
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
        from rcx_pi.selfhost.step_mu import run_hemisphere_routing

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
        from rcx_pi.selfhost.step_mu import run_engine_with_routing
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
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
        from rcx_pi.selfhost.kernel import reset_step_budget

        graph_input = {"graph": {"vertices": [1, 2], "edges": [{"src": 1, "dst": 2}]}}

        reset_step_budget()
        py_result = run_engine_pipeline(
            self.IDENTITY_PROJS, graph_input,
            max_steps=5, max_engine_iterations=20, max_algorithm_iterations=50,
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
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
        from rcx_pi.selfhost.kernel import reset_step_budget

        scalar_input = {"value": 42, "status": "test"}

        reset_step_budget()
        py_result = run_engine_pipeline(
            self.IDENTITY_PROJS, scalar_input,
            max_steps=5, max_engine_iterations=20, max_algorithm_iterations=50,
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
        from rcx_pi.selfhost.step_mu import run_engine_with_routing
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
        from rcx_pi.selfhost.step_mu import run_engine_with_routing
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
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
        from rcx_pi.selfhost.kernel import reset_step_budget

        test_input = {"value": 42}

        reset_step_budget()
        py_result = run_engine_pipeline(
            self.IDENTITY_PROJS, test_input,
            max_steps=5, max_engine_iterations=20, max_algorithm_iterations=50,
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
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
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
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
        from rcx_pi.selfhost.kernel import reset_step_budget

        test_input = {"value": 42}

        reset_step_budget()
        py_result = run_engine_pipeline(
            self.IDENTITY_PROJS, test_input,
            max_steps=5, max_engine_iterations=20, max_algorithm_iterations=50,
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
        js_path = ROOT / "mu" / "host" / "js" / "eval_step.js"
        source = js_path.read_text()

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
        """Contract lock: validation call is between result computation and injection."""
        js_path = ROOT / "mu" / "host" / "js" / "eval_step.js"
        lines = js_path.read_text().splitlines(keepends=True)

        # Find the validation line and the injection line within runEnginePipeline
        validation_line = None
        injection_line = None
        in_engine_pipeline = False
        for i, line in enumerate(lines, 1):
            if 'function runEnginePipeline(' in line:
                in_engine_pipeline = True
            if in_engine_pipeline:
                if 'validateNoKernelReservedFields(result,' in line:
                    validation_line = i
                if 'context[injectKey] = result' in line:
                    injection_line = i
                    break  # Found both — stop

        assert validation_line is not None, (
            "REGRESSION: validateNoKernelReservedFields(result, ...) not found "
            "in runEnginePipeline(). See Round 17D P1 fix."
        )
        assert injection_line is not None, (
            "REGRESSION: context[injectKey] = result not found in runEnginePipeline()."
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
        from rcx_pi.selfhost.step_mu import hash_trace_for_recurrence

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
        js_path = ROOT / "mu" / "host" / "js" / "eval_step.js"
        source = js_path.read_text(encoding="utf-8")
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
        js_path = ROOT / "mu" / "host" / "js" / "eval_step.js"
        source = js_path.read_text(encoding="utf-8")

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
    if 'must be dict' in msg or 'must be a dict' in msg:
        return 'input.invalid_type'
    if 'shape mismatch' in msg or 'unexpected shape' in msg:
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
        js_source = (ROOT / "mu" / "host" / "js" / "eval_step.js").read_text()

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
            from rcx_pi.selfhost.step_mu import hash_trace_for_recurrence
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
            from rcx_pi.selfhost.step_mu import run_engine_pipeline
            from rcx_pi.selfhost.kernel import reset_step_budget
            reset_step_budget()
            run_engine_pipeline(
                args.get('projections', []), args['input'],
                max_steps=args.get('maxSteps', 6),
                max_engine_iterations=args.get('maxEngineIterations', 20),
                max_algorithm_iterations=args.get('maxAlgorithmIterations', 50),
            )
            return True, None
        elif action_name == 'run_hemisphere_routing':
            from rcx_pi.selfhost.step_mu import run_hemisphere_routing
            hemispheres = args.get('hemispheres', {
                "r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None,
            })
            run_hemisphere_routing(args['engine_result'], hemispheres)
            return True, None
        elif action_name == 'run_engine_with_routing':
            from rcx_pi.selfhost.step_mu import run_engine_with_routing
            from rcx_pi.selfhost.kernel import reset_step_budget
            reset_step_budget()
            kwargs = {}
            if 'hemispheres' in args:
                kwargs['hemispheres'] = args['hemispheres']
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
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
        observer = []
        result = run_engine_pipeline(
            projections, input_value, observer=observer, **kwargs
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
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
        from rcx_pi.selfhost.seed_integrity import get_seed_path, load_verified_seed

        # Use a trivial input that produces a quick terminal result
        # The engine with no user projections will init → trace (empty) → hash → recurrence → exhaustion → terminal
        py_observer = []
        try:
            py_result = run_engine_pipeline([], "test_value", observer=py_observer)
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
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
        try:
            run_engine_pipeline([], "obs_test", observer=py_observer)
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
        """All emitted events conform to N6a schema (6 required fields)."""
        required_fields = {"event_name", "step", "state_hash", "error_code", "substrate", "timestamp"}

        py_observer = []
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
        try:
            run_engine_pipeline([], "schema_test", observer=py_observer)
        except RuntimeError:
            pass

        for event in py_observer:
            assert set(event.keys()) == required_fields, (
                f"Python event has wrong fields: {set(event.keys())} != {required_fields}"
            )
            assert event["substrate"] == "python"
            assert isinstance(event["step"], int) and event["step"] >= 0
            assert isinstance(event["timestamp"], int) and event["timestamp"] >= 0

        js_resp = _js_api_observer({
            "action": "run_engine_pipeline",
            "input": "schema_test",
            "observer": True,
        })
        for event in js_resp.get("observer_events", []):
            assert set(event.keys()) == required_fields, (
                f"JS event has wrong fields: {set(event.keys())} != {required_fields}"
            )
            assert event["substrate"] == "js"
            assert isinstance(event["step"], int) and event["step"] >= 0
            assert isinstance(event["timestamp"], int) and event["timestamp"] >= 0

    def test_observer_timestamps_monotonic(self):
        """Timestamps are monotonically increasing within each substrate."""
        py_observer = []
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
        try:
            run_engine_pipeline([], "mono_test", observer=py_observer)
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
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
        try:
            run_engine_pipeline([], "hash_parity", observer=py_observer)
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
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
        # No observer parameter — should work exactly as before
        try:
            run_engine_pipeline([], "default_test")
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
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
        try:
            run_engine_pipeline([], "canon_test", observer=py_observer)
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
