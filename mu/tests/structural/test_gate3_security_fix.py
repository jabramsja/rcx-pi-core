"""
Gate 3 Security Fix Regression Tests

These tests verify the security fix for the context-aware validation vulnerability
identified during external review. The original implementation allowed any input
with _mode="recurrence" to bypass reserved field validation entirely.

Attack vector blocked: {"_mode": "recurrence", "_result": "pwned"}

Gate 4 hardening policy:
- Domain validation is strict: reserved kernel fields are rejected everywhere.
- Trusted algorithm state is validated separately by algorithm-runtime allowlist.
"""

import pytest
import subprocess
import json
from pathlib import Path

from rcx_pi.selfhost.step_mu import (
    validate_no_kernel_reserved_fields,
    validate_algorithm_runtime_fields,
    KERNEL_RESERVED_FIELDS,
    ALGORITHM_ENTRYPOINT_KEYS,
    _iter_normalized_dict_pairs,  # ANTICHEAT_OK: grounding test for internal security function
)


from tests.repo_root import REPO_ROOT

# Root directory for JS tests
ROOT = REPO_ROOT


class TestSpoofedModeAttack:
    """Test that spoofed _mode at top level is rejected."""

    def test_spoofed_recurrence_mode_rejected(self):
        """Spoofed _mode="recurrence" at top level MUST fail."""
        spoofed = {"_mode": "recurrence", "_result": "pwned", "_stall": True}

        with pytest.raises(ValueError, match="SECURITY.*_mode"):
            validate_no_kernel_reserved_fields(spoofed, "test")

    def test_spoofed_exhaustion_mode_rejected(self):
        """Spoofed _mode="exhaustion" at top level MUST fail."""
        spoofed = {"_mode": "exhaustion", "_result": "pwned"}

        with pytest.raises(ValueError, match="SECURITY.*_mode"):
            validate_no_kernel_reserved_fields(spoofed, "test")

    def test_spoofed_recurrence_done_mode_rejected(self):
        """Spoofed _mode="recurrence_done" at top level MUST fail."""
        spoofed = {"_mode": "recurrence_done", "_result": "pwned"}

        with pytest.raises(ValueError, match="SECURITY.*_mode"):
            validate_no_kernel_reserved_fields(spoofed, "test")

    def test_spoofed_phase_rejected(self):
        """Spoofed _phase="scan" at top level MUST fail."""
        spoofed = {"_phase": "scan", "_result": "pwned"}

        with pytest.raises(ValueError, match="SECURITY.*_phase"):
            validate_no_kernel_reserved_fields(spoofed, "test")

    def test_kernel_forgery_still_rejected(self):
        """Plain kernel forgery (_mode="done") still rejected."""
        forgery = {"_mode": "done", "_result": "pwned", "_stall": False}

        with pytest.raises(ValueError, match="SECURITY.*_mode"):
            validate_no_kernel_reserved_fields(forgery, "test")

    def test_all_reserved_fields_rejected_at_top_level(self):
        """Every reserved field is rejected at top level."""
        for field in KERNEL_RESERVED_FIELDS:
            attack = {field: "attack_value"}
            with pytest.raises(ValueError, match=f"SECURITY.*{field}"):
                validate_no_kernel_reserved_fields(attack, "test")


class TestStrictDomainValidation:
    """Domain-mode validator must reject reserved fields everywhere."""

    def test_detect_closure_with_reserved_fields_rejected(self):
        payload = {
            "_detect_closure": {
                "_mode": "recurrence",
                "_phase": "scan",
                "_seen": {"head": "A", "tail": None},
                "_current": None,
                "_result": "final"
            }
        }
        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(payload, "test")

    def test_detect_exhaustion_with_reserved_fields_rejected(self):
        payload = {
            "_detect_exhaustion": {
                "_mode": "exhaustion",
                "_phase": "find_tau",
                "_frozen": None,
                "_tau_step": 0,
                "_operator_ids": None
            }
        }
        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(payload, "test")

    def test_nested_algorithm_state_rejected(self):
        payload = {
            "_detect_closure": {
                "_mode": "recurrence",
                "_seen": {"head": {"_mode": "recurrence"}, "tail": None}
            }
        }
        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(payload, "test")

    def test_real_recurrence_input_allowed(self):
        """Real recurrence algorithm input passes validation."""
        real_input = {
            "_detect_closure": {
                "trace": {
                    "head": {"step": 0, "state": "A", "projection": "p1"},
                    "tail": {
                        "head": {"step": 1, "state": "B", "projection": "p2"},
                        "tail": None
                    }
                },
                "result": "B"
            }
        }

        # No reserved fields in this payload, so domain validation should pass.
        validate_no_kernel_reserved_fields(real_input, "test")

    def test_normalized_reserved_key_rejected(self):
        """Reserved fields in normalized dict keys MUST be rejected."""
        from rcx_pi.selfhost.match_mu import normalize_for_match

        normalized = normalize_for_match({"_mode": "recurrence"})

        with pytest.raises(ValueError, match="SECURITY.*_mode"):
            validate_no_kernel_reserved_fields(normalized, "test")

    def test_normalized_entrypoint_with_reserved_rejected(self):
        """Reserved fields inside normalized entrypoint subtree are rejected in domain mode."""
        from rcx_pi.selfhost.match_mu import normalize_for_match

        normalized = normalize_for_match({
            "_detect_closure": {
                "_mode": "recurrence",
                "_phase": "scan"
            }
        })

        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(normalized, "test")

    def test_malformed_normalized_dict_rejected_fail_closed(self):
        """
        Malformed normalized dict encoding must fail closed.

        If kv-tail shape is invalid, validator must not fall back to regular
        dict recursion because encoded key values would bypass reserved-field checks.
        """
        malformed = {
            "_type": "dict",
            "head": {
                "head": "_mode",
                "tail": {
                    "head": "forged",
                    "tail": {"oops": 1},  # invalid kv-tail; should be null
                },
            },
            "tail": None,
        }

        with pytest.raises(ValueError, match="malformed normalized dict encoding"):
            validate_no_kernel_reserved_fields(malformed, "test")


class TestMixedScenarios:
    """Test mixed scenarios combining legitimate and attack patterns."""

    def test_reserved_outside_entrypoint_still_rejected(self):
        """Reserved fields outside entrypoint subtree are rejected even if entrypoint exists."""
        mixed = {
            "_detect_closure": {"trace": None, "result": "X"},
            "_mode": "recurrence"  # Attack: reserved field OUTSIDE entrypoint
        }

        with pytest.raises(ValueError, match="SECURITY.*_mode"):
            validate_no_kernel_reserved_fields(mixed, "test")

    def test_sibling_attack_rejected(self):
        """Reserved fields in sibling of entrypoint are rejected."""
        sibling_attack = {
            "_detect_closure": {"trace": None, "result": "X"},
            "other_key": {"_result": "pwned"}  # Attack in sibling
        }

        with pytest.raises(ValueError, match="SECURITY.*_result"):
            validate_no_kernel_reserved_fields(sibling_attack, "test")

    def test_nested_spoof_outside_entrypoint_rejected(self):
        """Reserved fields nested in non-entrypoint key MUST fail.

        Security invariant: {"outer": {"_phase": "scan", "_result": 1}} must be rejected
        because "outer" is not an algorithm entrypoint key.
        """
        nested_spoof = {"outer": {"_phase": "scan", "_result": 1}}

        with pytest.raises(ValueError, match="SECURITY.*_phase"):
            validate_no_kernel_reserved_fields(nested_spoof, "test")

    def test_clean_data_with_entrypoint_passes(self):
        """Clean data alongside entrypoint passes."""
        clean = {
            "_detect_closure": {"trace": None, "result": "X"},
            "metadata": {"timestamp": 12345, "version": "1.0"}
        }

        # Should NOT raise
        validate_no_kernel_reserved_fields(clean, "test")


class TestNormalizedDictCycleHandling:
    """Cycle handling for normalized dict validation helper."""

    def test_iter_normalized_dict_pairs_rejects_cycle(self):
        """Cyclic normalized dict-like structures must fail closed."""
        kv = {"head": "safe_key", "tail": {"head": 1, "tail": None}}
        root = {"_type": "dict", "head": kv}
        root["tail"] = root  # explicit cycle

        assert _iter_normalized_dict_pairs(root) is None


class TestAlgorithmEntrypointKeys:
    """Test the ALGORITHM_ENTRYPOINT_KEYS constant."""

    def test_entrypoint_keys_are_correct(self):
        """Verify entrypoint keys match expected values."""
        expected = {"_detect_closure", "_detect_exhaustion"}
        assert ALGORITHM_ENTRYPOINT_KEYS == expected

    def test_entrypoint_keys_not_in_reserved(self):
        """Entrypoint keys themselves are NOT reserved (they're entry points)."""
        for key in ALGORITHM_ENTRYPOINT_KEYS:
            assert key not in KERNEL_RESERVED_FIELDS


class TestAlgorithmRuntimeValidation:
    """Gate 4 algorithm-runtime validation hardening."""

    def test_algorithm_runtime_allows_reserved_inside_detect_closure(self):
        payload = {
            "_detect_closure": {
                "_mode": "recurrence",
                "_phase": "scan",
                "_result": "X",
            }
        }
        validate_algorithm_runtime_fields(payload, "test")

    def test_algorithm_runtime_allows_reserved_inside_detect_exhaustion(self):
        payload = {
            "_detect_exhaustion": {
                "_mode": "exhaustion",
                "_phase": "scan",
                "_tau_step": 0,
            }
        }
        validate_algorithm_runtime_fields(payload, "test")

    def test_algorithm_runtime_rejects_unknown_underscore(self):
        with pytest.raises(ValueError, match="unsupported algorithm underscore field"):
            validate_algorithm_runtime_fields({"_detect_closure": {"_evil": 1}}, "test")

    def test_algorithm_runtime_rejects_malformed_normalized_dict(self):
        malformed = {
            "_type": "dict",
            "head": {
                "head": "_evil",
                "tail": {
                    "head": 1,
                    "tail": {"oops": 1},  # invalid kv-tail; should be null
                },
            },
            "tail": None,
        }

        with pytest.raises(ValueError, match="malformed normalized dict encoding"):
            validate_algorithm_runtime_fields(malformed, "test")


class TestCrossSubstrateParity:
    """Verify Python and JS validation accept/reject the same shapes."""

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
        """Both Python and JS reject spoofed _mode."""
        spoofed = {"_mode": "recurrence", "_result": "pwned"}

        # Python rejects
        with pytest.raises(ValueError):
            validate_no_kernel_reserved_fields(spoofed, "test")

        # JS should also reject
        valid, error = self._run_js_validation(spoofed)
        assert not valid, f"JS should reject spoofed _mode, but got valid=True"
        assert "_mode" in error or "reserved" in error.lower()

    def test_parity_strict_domain_rejects_entrypoint_reserved_fields(self):
        """Both Python and JS reject reserved fields in strict domain mode."""
        payload = {
            "_detect_closure": {
                "_mode": "recurrence",
                "_result": "X"
            }
        }

        # Python rejects
        with pytest.raises(ValueError):
            validate_no_kernel_reserved_fields(payload, "test")

        # JS should also reject
        valid, error = self._run_js_validation(payload)
        assert not valid, f"JS should reject reserved fields in domain mode, got valid=True"
        assert "reserved" in error.lower() or "_mode" in error

    def test_parity_nested_spoof_rejected(self):
        """Both Python and JS reject nested spoof outside entrypoint."""
        nested_spoof = {"outer": {"_phase": "scan", "_result": 1}}

        # Python rejects
        with pytest.raises(ValueError):
            validate_no_kernel_reserved_fields(nested_spoof, "test")

        # JS should also reject
        valid, error = self._run_js_validation(nested_spoof)
        assert not valid, f"JS should reject nested spoof, but got valid=True"

    def test_parity_clean_data_allowed(self):
        """Both Python and JS allow clean data."""
        clean = {"x": 1, "y": {"z": 2}}

        # Python allows
        validate_no_kernel_reserved_fields(clean, "test")

        # JS should also allow
        valid, error = self._run_js_validation(clean)
        assert valid, f"JS should allow clean data, but got error: {error}"

    def test_parity_algorithm_runtime_allows_entrypoint_reserved_fields(self):
        """Both Python and JS algorithm-runtime validators allow trusted entrypoint state."""
        payload = {
            "_detect_closure": {
                "_mode": "recurrence",
                "_phase": "scan",
                "_result": "X",
            }
        }

        validate_algorithm_runtime_fields(payload, "test")
        valid, error = self._run_js_validation(payload, action="validate_algorithm_runtime_fields")
        assert valid, f"JS algorithm-runtime validation should allow payload: {error}"
