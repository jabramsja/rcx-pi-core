"""
Gate tests for Wave 11: Runtime Hardening + Infrastructure Cleanup.

Proves:
1. R5: hash_trace_for_recurrence() rejects malformed entries (fail-closed)
2. R5: JS parity — hashTraceForRecurrence rejects malformed entries
3. AST_OK annotations present on is_kernel_projection and is_kernel_intermediate
4. Seed registry cross-validation (SEED_CHECKSUMS vs EXPECTED_PROJECTION_IDS)
5. step_algorithm_with_bridge is debug-gated (not dead code — properly guarded)
"""
# SPEED_OK: run_algorithm_meta_circular imported inside test method for error-path test only (raises ValueError immediately, no slow kernel execution)

import subprocess
import textwrap

import pytest

JS_TRUST_MU_PRELUDE = """
const muContainers = require('./mu/host/js/core/container_factory');
function trustMu(value) {
  if (Array.isArray(value)) return muContainers.list(value.map(trustMu));
  if (value !== null && typeof value === 'object') {
    return muContainers.record(Object.keys(value).map(key => [key, trustMu(value[key])]));
  }
  return value;
}
"""


# =============================================================================
# R5: hash_trace_for_recurrence() fail-closed hardening
# =============================================================================

class TestR5HashTraceFailClosed:
    """Prove hash_trace_for_recurrence rejects malformed trace entries."""

    def test_rejects_entry_without_state_key(self):
        """Dict entry missing 'state' key must raise ValueError."""
        from rcx_pi.selfhost.engine_pipeline import hash_trace_for_recurrence

        malformed_trace = {"head": {"foo": 1}, "tail": None}
        with pytest.raises(ValueError, match="malformed trace entry"):
            hash_trace_for_recurrence(malformed_trace)

    def test_rejects_non_dict_entry(self):
        """Non-dict entry (string, int, etc.) must raise ValueError."""
        from rcx_pi.selfhost.engine_pipeline import hash_trace_for_recurrence

        string_entry_trace = {"head": "not_a_dict", "tail": None}
        with pytest.raises(ValueError, match="malformed trace entry"):
            hash_trace_for_recurrence(string_entry_trace)

    def test_rejects_int_entry(self):
        """Integer entry must raise ValueError."""
        from rcx_pi.selfhost.engine_pipeline import hash_trace_for_recurrence

        int_entry_trace = {"head": 42, "tail": None}
        with pytest.raises(ValueError, match="malformed trace entry"):
            hash_trace_for_recurrence(int_entry_trace)

    def test_rejects_none_entry(self):
        """None entry must raise ValueError."""
        from rcx_pi.selfhost.engine_pipeline import hash_trace_for_recurrence

        none_entry_trace = {"head": None, "tail": None}
        with pytest.raises(ValueError, match="malformed trace entry"):
            hash_trace_for_recurrence(none_entry_trace)

    def test_accepts_well_formed_entry(self):
        """Dict entry with 'state' key must be accepted and hashed."""
        from rcx_pi.selfhost.engine_pipeline import hash_trace_for_recurrence

        good_trace = {"head": {"state": {"value": 1}}, "tail": None}
        result = hash_trace_for_recurrence(good_trace)
        assert result["head"]["state_hash"] is not None
        assert result["head"]["state"] == {"value": 1}

    def test_rejects_invalid_state_value(self):
        """Entry state must be valid Mu, not just present."""
        from rcx_pi.selfhost.engine_pipeline import hash_trace_for_recurrence

        invalid_state_trace = {"head": {"state": object()}, "tail": None}
        with pytest.raises(TypeError, match="hash_trace_for_recurrence must be a Mu"):
            hash_trace_for_recurrence(invalid_state_trace)

    def test_multi_entry_trace_rejects_any_malformed(self):
        """Mixed trace with one malformed entry must fail on the malformed one."""
        from rcx_pi.selfhost.engine_pipeline import hash_trace_for_recurrence

        mixed_trace = {
            "head": {"state": {"value": 1}},
            "tail": {
                "head": {"no_state_key": True},
                "tail": None,
            },
        }
        with pytest.raises(ValueError, match="malformed trace entry"):
            hash_trace_for_recurrence(mixed_trace)


class TestR5HashTraceJsParity:
    """Prove JS hashTraceForRecurrence also rejects malformed entries."""

    def _run_js(self, code: str) -> subprocess.CompletedProcess:
        full = textwrap.dedent(f"""\
            const {{ hashTraceForRecurrence }} = require('./mu/host/js/engine/pipeline');
            {JS_TRUST_MU_PRELUDE}
            try {{
                {code}
            }} catch (e) {{
                console.log('ERROR:' + e.message);
            }}
        """)
        return subprocess.run(
            ["node", "-e", full],
            capture_output=True, text=True, timeout=10,
        )

    def test_js_rejects_entry_without_state(self):
        result = self._run_js(
            "hashTraceForRecurrence({head: {foo: 1}, tail: null});\n"
            "console.log('NO_ERROR');"
        )
        assert "ERROR:" in result.stdout
        assert "malformed trace entry" in result.stdout

    def test_js_rejects_string_entry(self):
        result = self._run_js(
            "hashTraceForRecurrence({head: 'not_a_dict', tail: null});\n"
            "console.log('NO_ERROR');"
        )
        assert "ERROR:" in result.stdout
        assert "malformed trace entry" in result.stdout

    def test_js_rejects_null_entry(self):
        result = self._run_js(
            "hashTraceForRecurrence({head: null, tail: null});\n"
            "console.log('NO_ERROR');"
        )
        assert "ERROR:" in result.stdout
        assert "malformed trace entry" in result.stdout

    def test_js_rejects_invalid_state_value(self):
        result = self._run_js(
            "const trace = {head: muContainers.record([['state', undefined]]), tail: null};\n"
            "const r = hashTraceForRecurrence(trace);\n"
            "console.log('OK:' + JSON.stringify(Object.hasOwn(r.head, 'state_hash')));"
        )
        assert "ERROR:" in result.stdout
        assert "trace entry state is not valid Mu" in result.stdout
        assert "OK:false" not in result.stdout

    def test_js_accepts_well_formed_entry(self):
        result = self._run_js(
            "const r = hashTraceForRecurrence(trustMu({head: {state: {v: 1}}, tail: null}));\n"
            "console.log('OK:' + [Object.hasOwn(r.head, 'state_hash'), typeof r.head.state_hash, r.head.state.v].join(':'));"
        )
        assert "OK:true:string:1" in result.stdout


# =============================================================================
# AST_OK Annotations
# =============================================================================

class TestAstOkAnnotations:
    """Prove AST_OK annotations exist on infrastructure isinstance calls."""

    def _get_source_lines(self, filename: str) -> list[str]:
        from pathlib import Path
        return Path(filename).read_text().splitlines()

    def test_is_kernel_projection_isinstance_annotated(self):
        """All isinstance calls in is_kernel_projection must have AST_OK."""
        lines = self._get_source_lines(
            "mu/host/python/rcx_pi/selfhost/step_mu.py"
        )
        in_func = False
        for line in lines:
            if "def is_kernel_projection" in line:
                in_func = True
                continue
            if in_func and line.strip() and not line.startswith(" ") and not line.startswith("\t"):
                break
            if in_func and "isinstance" in line:
                assert "AST_OK" in line, (
                    f"isinstance in is_kernel_projection missing AST_OK: {line.strip()}"
                )

    def test_is_kernel_intermediate_isinstance_annotated(self):
        """isinstance in is_kernel_intermediate must have AST_OK."""
        lines = self._get_source_lines(
            "mu/host/python/rcx_pi/selfhost/step_mu.py"
        )
        in_func = False
        for line in lines:
            if "def is_kernel_intermediate" in line:
                in_func = True
                continue
            if in_func and line.strip() and not line.startswith(" ") and not line.startswith("\t"):
                break
            if in_func and "isinstance" in line:
                assert "AST_OK" in line, (
                    f"isinstance in is_kernel_intermediate missing AST_OK: {line.strip()}"
                )


# =============================================================================
# Seed Registry Cross-Validation
# =============================================================================

class TestSeedRegistryCrossValidation:
    """Prove seed registries are mutually consistent."""

    def test_python_checksums_vs_projection_ids(self):
        """Every seed in SEED_CHECKSUMS must also be in EXPECTED_PROJECTION_IDS."""
        from rcx_pi.selfhost.seed_integrity import (
            SEED_CHECKSUMS,
            EXPECTED_PROJECTION_IDS,
        )
        missing = set(SEED_CHECKSUMS.keys()) - set(EXPECTED_PROJECTION_IDS.keys())
        assert not missing, (
            f"Seeds in SEED_CHECKSUMS but not EXPECTED_PROJECTION_IDS: {missing}"
        )

    def test_python_projection_ids_vs_checksums(self):
        """Every seed in EXPECTED_PROJECTION_IDS must also be in SEED_CHECKSUMS."""
        from rcx_pi.selfhost.seed_integrity import (
            SEED_CHECKSUMS,
            EXPECTED_PROJECTION_IDS,
        )
        missing = set(EXPECTED_PROJECTION_IDS.keys()) - set(SEED_CHECKSUMS.keys())
        assert not missing, (
            f"Seeds in EXPECTED_PROJECTION_IDS but not SEED_CHECKSUMS: {missing}"
        )

    def test_python_mu_seed_locations_vs_checksums(self):
        """Every seed in MU_SEED_LOCATIONS must also be in SEED_CHECKSUMS."""
        from rcx_pi.selfhost.seed_integrity import (
            SEED_CHECKSUMS,
            MU_SEED_LOCATIONS,
        )
        missing = set(MU_SEED_LOCATIONS.keys()) - set(SEED_CHECKSUMS.keys())
        assert not missing, (
            f"Seeds in MU_SEED_LOCATIONS but not SEED_CHECKSUMS: {missing}"
        )

    def test_python_checksums_vs_mu_seed_locations(self):
        """Every seed in SEED_CHECKSUMS must also be in MU_SEED_LOCATIONS."""
        from rcx_pi.selfhost.seed_integrity import (
            SEED_CHECKSUMS,
            MU_SEED_LOCATIONS,
        )
        missing = set(SEED_CHECKSUMS.keys()) - set(MU_SEED_LOCATIONS.keys())
        assert not missing, (
            f"Seeds in SEED_CHECKSUMS but not MU_SEED_LOCATIONS: {missing}"
        )

    def test_js_checksums_vs_projection_ids(self):
        """JS CORE_SEED_CHECKSUMS and CORE_SEED_PROJECTION_IDS must have same keys.

        These are not exported, so we parse the source file directly.
        """
        import re
        from pathlib import Path

        source = Path("mu/host/js/core/seed_loader.js").read_text()

        # Extract keys from CORE_SEED_CHECKSUMS block
        cs_match = re.search(
            r"const CORE_SEED_CHECKSUMS\s*=\s*\{(.*?)\};",
            source, re.DOTALL,
        )
        assert cs_match, "Could not find CORE_SEED_CHECKSUMS in seed_loader.js"
        cs_keys = set(re.findall(r"'([^']+\.json)'", cs_match.group(1)))

        # Extract keys from CORE_SEED_PROJECTION_IDS block
        pi_match = re.search(
            r"const CORE_SEED_PROJECTION_IDS\s*=\s*\{(.*?)\n\};",
            source, re.DOTALL,
        )
        assert pi_match, "Could not find CORE_SEED_PROJECTION_IDS in seed_loader.js"
        # Only get top-level keys (seed names), not projection ID values
        pi_block = pi_match.group(1)
        pi_keys = set()
        for line in pi_block.splitlines():
            m = re.match(r"\s+'([^']+\.json)':", line)
            if m:
                pi_keys.add(m.group(1))

        cs_only = cs_keys - pi_keys
        pi_only = pi_keys - cs_keys
        assert not cs_only, f"JS seeds in CHECKSUMS but not PROJECTION_IDS: {cs_only}"
        assert not pi_only, f"JS seeds in PROJECTION_IDS but not CHECKSUMS: {pi_only}"


# =============================================================================
# step_algorithm_with_bridge debug gate proof
# =============================================================================

class TestStepAlgorithmWithBridgeGated:
    """Prove step_algorithm_with_bridge is properly gated behind debug flag."""

    def test_bootstrap_mode_requires_explicit_flag(self):
        """execution_mode='bootstrap' must raise without allow_bootstrap_fallback."""
        from rcx_pi.selfhost.step_mu import run_algorithm_meta_circular

        # Use a minimal valid projection (doesn't need real seeds for this test)
        proj = {"id": "test.noop", "pattern": {"x": {"var": "x"}}, "body": {"x": {"var": "x"}}}
        state = {"_detect_closure": {"trace": None, "seen": None}}
        with pytest.raises(ValueError, match="bootstrap fallback is disabled"):
            run_algorithm_meta_circular(
                [proj], state,
                execution_mode="bootstrap",
            )

    def test_source_proof_bridge_gated(self):
        """Source must show step_algorithm_with_bridge only called under bootstrap gate."""
        import inspect
        from rcx_pi.selfhost.step_mu import run_algorithm_meta_circular

        source = inspect.getsource(run_algorithm_meta_circular)
        assert "allow_bootstrap_fallback" in source
        assert "step_algorithm_with_bridge" in source
        # The call must be inside an if block requiring the flag
        lines = source.splitlines()
        bridge_call_line = None
        for i, line in enumerate(lines):
            if "step_algorithm_with_bridge" in line and "return" in line:
                bridge_call_line = i
                break
        assert bridge_call_line is not None
        # Check preceding lines for the guard
        preceding = "\n".join(lines[max(0, bridge_call_line - 5):bridge_call_line])
        assert "allow_bootstrap_fallback" in preceding, (
            "step_algorithm_with_bridge call must be guarded by allow_bootstrap_fallback check"
        )
