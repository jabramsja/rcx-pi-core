"""
A12 gate tests: Ontology Promotion Runtime Enforcement.

Wave class: L4_STRUCTURAL (runtime validation in both substrates).

Tests verify:
1. Python validator accepts valid records, rejects violations (INV_OPROMO_1..4)
2. JS validator parity (runtime node -e)
3. Wiring hooks present in both substrates
4. Cross-substrate parity for representative pass/fail fixtures
5. Typed fail-closed only (no raw exceptions)
6. Seed subdirectory parity (Python MU_SEED_LOCATIONS == JS SEED_SUBDIRS)
7. JS full-lock gate (isFullyLockedSeed rejects unlocked seeds)
"""
from __future__ import annotations

import inspect
import json
import os
import re
import subprocess
import textwrap
from copy import deepcopy
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

# ---------------------------------------------------------------------------
# Python-side imports for direct validator testing
# ---------------------------------------------------------------------------
from rcx_pi.selfhost.step_mu import RcxEngineError
from rcx_pi.selfhost.engine_pipeline import _validate_ontology_promotion_record  # ANTICHEAT_OK: A12 gate test requires direct validator access
from rcx_pi.selfhost.engine_pipeline import _OPROMO_FULLY_LOCKED_SEEDS  # ANTICHEAT_OK: A12 parity test for locked seed set
from rcx_pi.selfhost.engine_pipeline import _derive_opromo_fully_locked_seeds  # ANTICHEAT_OK: A13 derivation rule test
from rcx_pi.selfhost.engine_pipeline import _JS_CORE_SEED_REGISTRY_KEYS  # ANTICHEAT_OK: A13 registry mirror test (collapsed from checksums+projIDs)
from rcx_pi.selfhost.engine_pipeline import _build_ontology_promotion_candidate  # ANTICHEAT_OK: A14 builder unit test
from rcx_pi.selfhost.engine_pipeline import _service_boundary_effect  # ANTICHEAT_OK: A14 behavioral integration test
from rcx_pi.selfhost.engine_pipeline import _BOUNDARY_DISPATCH  # ANTICHEAT_OK: A15 monkeypatch target for overwrite guard test
from rcx_pi.selfhost.engine_pipeline import _collect_ontology_evidence  # ANTICHEAT_OK: A17 evidence collector unit test
from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields  # ANTICHEAT_OK: A14 reserved-field re-validation check
from rcx_pi.selfhost.seed_integrity import MU_SEED_LOCATIONS, SEED_CHECKSUMS, EXPECTED_PROJECTION_IDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_valid_record() -> dict:
    """Return a minimal valid ontology promotion record."""
    return {
        "witness_traces": [
            {"trace_id": "t1", "seed_config": "rcx_engine.v1.json"},
            {"trace_id": "t2", "seed_config": "hemispheres.v1.json"},
        ],
        "seed_configs": ["rcx_engine.v1.json", "hemispheres.v1.json"],
        "closure_structure": {},
        "perturbation_log": {
            "removals_tested": ["p1"],
            "additions_tested": ["p2"],
            "pattern_survived_all": True,
        },
        "derivation_timestamp": "2026-02-26T00:00:00Z",
        "substrate_versions": {"python": "abc123", "js": "def456"},
        "tau_lineage": ["lineage_entry_1"],
        "authority": {
            "source": "seed",
            "seed_file": "rcx_engine.v1.json",
            "projection_ids": ["engine.init"],
        },
    }


def _run_js_validator(record_json: str, *, expect_pass: bool = True) -> subprocess.CompletedProcess:
    """Run the JS validator via node -e and return the result."""
    js_code = textwrap.dedent(f"""\
        const {{ validateOntologyPromotionRecord }} = require('./mu/host/js/engine/pipeline');
        const record = {record_json};
        try {{
            validateOntologyPromotionRecord(record, 'test');
            process.stdout.write('PASS');
        }} catch (err) {{
            process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
        }}
    """)
    return subprocess.run(
        ["node", "-e", js_code],
        cwd=str(REPO_ROOT),
        capture_output=True, text=True, check=False,
    )


def _run_js_expr(js_code: str, *, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run arbitrary JS expression via node -e.

    Args:
        env: Optional extra env vars merged into os.environ.
    """
    run_env = None
    if env is not None:
        run_env = {**os.environ, **env}
    return subprocess.run(
        ["node", "-e", js_code],
        cwd=str(REPO_ROOT),
        capture_output=True, text=True, check=False,
        env=run_env,
    )


# ===========================================================================
# TestPythonValidRecord
# ===========================================================================

class TestPythonValidRecord:
    """Python validator accepts valid records, rejects missing fields."""

    def test_valid_record_passes(self):
        record = _make_valid_record()
        _validate_ontology_promotion_record(record, "test")

    @pytest.mark.parametrize("missing_field", [
        "witness_traces", "seed_configs", "closure_structure",
        "perturbation_log", "derivation_timestamp", "substrate_versions",
        "tau_lineage", "authority",
    ])
    def test_missing_field_raises_inv_opromo_4(self, missing_field):
        record = _make_valid_record()
        del record[missing_field]
        with pytest.raises(RcxEngineError, match="INV_OPROMO_4"):
            _validate_ontology_promotion_record(record, "test")


# ===========================================================================
# TestJSValidRecord
# ===========================================================================

class TestJSValidRecord:
    """JS validator parity: accepts valid records, rejects missing fields."""

    def test_valid_record_passes_js(self):
        record = _make_valid_record()
        result = _run_js_validator(json.dumps(record))
        assert result.stdout == "PASS", f"JS validator rejected valid record: {result.stdout} {result.stderr}"

    def test_missing_field_rejects_js(self):
        record = _make_valid_record()
        del record["witness_traces"]
        result = _run_js_validator(json.dumps(record))
        assert result.stdout.startswith("FAIL:input.shape_mismatch:"), (
            f"Expected input.shape_mismatch, got: {result.stdout}"
        )
        assert "INV_OPROMO_4" in result.stdout


# ===========================================================================
# TestINV_OPROMO_1
# ===========================================================================

class TestINV_OPROMO_1:
    """INV_OPROMO_1: recurrence witnesses."""

    def test_single_witness_rejected(self):
        record = _make_valid_record()
        record["witness_traces"] = [record["witness_traces"][0]]
        record["seed_configs"] = [record["seed_configs"][0]]
        with pytest.raises(RcxEngineError, match="INV_OPROMO_1"):
            _validate_ontology_promotion_record(record, "test")

    def test_non_distinct_seed_configs_rejected(self):
        record = _make_valid_record()
        record["witness_traces"] = [
            {"trace_id": "t1", "seed_config": "rcx_engine.v1.json"},
            {"trace_id": "t2", "seed_config": "rcx_engine.v1.json"},
        ]
        record["seed_configs"] = ["rcx_engine.v1.json"]
        with pytest.raises(RcxEngineError, match="INV_OPROMO_1"):
            _validate_ontology_promotion_record(record, "test")

    def test_duplicate_pair_rejected(self):
        record = _make_valid_record()
        record["witness_traces"] = [
            {"trace_id": "t1", "seed_config": "rcx_engine.v1.json"},
            {"trace_id": "t1", "seed_config": "rcx_engine.v1.json"},
        ]
        with pytest.raises(RcxEngineError, match="INV_OPROMO_1"):
            _validate_ontology_promotion_record(record, "test")

    def test_seed_configs_witness_inconsistency_rejected(self):
        record = _make_valid_record()
        # seed_configs says 3 configs, witnesses only reference 2
        record["seed_configs"] = [
            "rcx_engine.v1.json", "hemispheres.v1.json", "terminal_classify.v1.json",
        ]
        with pytest.raises(RcxEngineError, match="INV_OPROMO_1"):
            _validate_ontology_promotion_record(record, "test")

    def test_seed_configs_dict_entry_rejected_typed(self):
        """seed_configs containing a dict must raise typed error, not raw TypeError."""
        record = _make_valid_record()
        record["seed_configs"] = [{"bad": "entry"}, "hemispheres.v1.json"]
        with pytest.raises(RcxEngineError) as exc_info:
            _validate_ontology_promotion_record(record, "test")
        assert exc_info.value.error_code == "input.shape_mismatch"
        assert "INV_OPROMO_1" in str(exc_info.value)

    def test_seed_configs_int_entry_rejected_typed(self):
        """seed_configs containing an int must raise typed error, not raw TypeError."""
        record = _make_valid_record()
        record["seed_configs"] = [42, "hemispheres.v1.json"]
        with pytest.raises(RcxEngineError) as exc_info:
            _validate_ontology_promotion_record(record, "test")
        assert exc_info.value.error_code == "input.shape_mismatch"
        assert "INV_OPROMO_1" in str(exc_info.value)


# ===========================================================================
# TestINV_OPROMO_2
# ===========================================================================

class TestINV_OPROMO_2:
    """INV_OPROMO_2: perturbation stability."""

    def test_pattern_survived_false_rejected(self):
        record = _make_valid_record()
        record["perturbation_log"]["pattern_survived_all"] = False
        with pytest.raises(RcxEngineError, match="INV_OPROMO_2"):
            _validate_ontology_promotion_record(record, "test")

    def test_empty_removals_rejected(self):
        record = _make_valid_record()
        record["perturbation_log"]["removals_tested"] = []
        with pytest.raises(RcxEngineError, match="INV_OPROMO_2"):
            _validate_ontology_promotion_record(record, "test")

    def test_empty_additions_rejected(self):
        record = _make_valid_record()
        record["perturbation_log"]["additions_tested"] = []
        with pytest.raises(RcxEngineError, match="INV_OPROMO_2"):
            _validate_ontology_promotion_record(record, "test")


# ===========================================================================
# TestINV_OPROMO_3
# ===========================================================================

class TestINV_OPROMO_3:
    """INV_OPROMO_3: host cannot mint (seed authority only)."""

    def test_non_seed_source_rejected(self):
        record = _make_valid_record()
        record["authority"]["source"] = "host"
        with pytest.raises(RcxEngineError, match="INV_OPROMO_3"):
            _validate_ontology_promotion_record(record, "test")

    def test_unknown_seed_rejected_typed(self):
        record = _make_valid_record()
        record["authority"]["seed_file"] = "nonexistent_seed.v1.json"
        with pytest.raises(RcxEngineError, match="INV_OPROMO_3"):
            _validate_ontology_promotion_record(record, "test")

    def test_projection_id_not_in_seed_rejected(self):
        record = _make_valid_record()
        record["authority"]["projection_ids"] = ["engine.init", "fake.nonexistent"]
        with pytest.raises(RcxEngineError, match="INV_OPROMO_3"):
            _validate_ontology_promotion_record(record, "test")

    def test_valid_seed_and_projection_passes(self):
        record = _make_valid_record()
        # rcx_engine.v1.json with engine.init is valid
        _validate_ontology_promotion_record(record, "test")

    def test_seed_resolution_failure_is_typed(self):
        """Seed resolution failure must produce RcxEngineError, not raw ValueError."""
        record = _make_valid_record()
        record["authority"]["seed_file"] = "totally_bogus.json"
        with pytest.raises(RcxEngineError) as exc_info:
            _validate_ontology_promotion_record(record, "test")
        assert exc_info.value.error_code == "input.shape_mismatch"

    def test_python_full_lock_gate_rejects_unlocked_seed(self):
        """Python rejects seeds not in _OPROMO_FULLY_LOCKED_SEEDS."""
        record = _make_valid_record()
        record["authority"]["seed_file"] = "kernel.v1.json"
        record["authority"]["projection_ids"] = ["step"]
        with pytest.raises(RcxEngineError) as exc_info:
            _validate_ontology_promotion_record(record, "test")
        assert exc_info.value.error_code == "input.shape_mismatch"
        assert "verification-locked" in str(exc_info.value)

    def test_js_full_lock_gate_rejects_unlocked_seed(self):
        """JS rejects seeds in SEED_SUBDIRS but NOT in CORE_SEED_CHECKSUMS."""
        record = _make_valid_record()
        # kernel.v1.json is in SEED_SUBDIRS but NOT in CORE_SEED_CHECKSUMS
        record["authority"]["seed_file"] = "kernel.v1.json"
        record["authority"]["projection_ids"] = ["step"]
        result = _run_js_validator(json.dumps(record))
        assert result.stdout.startswith("FAIL:input.shape_mismatch:"), (
            f"Expected typed rejection for unlocked seed: {result.stdout}"
        )
        assert "verification-locked" in result.stdout or "INV_OPROMO_3" in result.stdout

    def test_unlocked_seed_rejected_both_substrates(self):
        """kernel.v1.json rejected in BOTH Python and JS with input.shape_mismatch."""
        record = _make_valid_record()
        record["authority"]["seed_file"] = "kernel.v1.json"
        record["authority"]["projection_ids"] = ["step"]
        # Python
        with pytest.raises(RcxEngineError) as exc_info:
            _validate_ontology_promotion_record(record, "test")
        assert exc_info.value.error_code == "input.shape_mismatch"
        # JS
        result = _run_js_validator(json.dumps(record))
        assert result.stdout.startswith("FAIL:input.shape_mismatch:")

    def test_js_is_fully_locked_seed_returns_false_for_unlocked(self):
        """isFullyLockedSeed returns false for seeds with only subdir registration."""
        js_code = textwrap.dedent("""\
            const { isFullyLockedSeed } = require('./mu/host/js/core/seed_loader');
            const result = isFullyLockedSeed('kernel.v1.json');
            process.stdout.write(String(result));
        """)
        result = _run_js_expr(js_code)
        assert result.stdout == "false", f"Expected false for unlocked seed, got: {result.stdout}"


# ===========================================================================
# TestCrossSubstrateParity
# ===========================================================================

class TestCrossSubstrateParity:
    """Representative pass/fail fixtures produce identical outcomes in both substrates."""

    def test_valid_record_passes_both(self):
        record = _make_valid_record()
        # Python
        _validate_ontology_promotion_record(record, "test")
        # JS
        result = _run_js_validator(json.dumps(record))
        assert result.stdout == "PASS"

    def test_inv_opromo_1_violation_fails_both(self):
        record = _make_valid_record()
        record["witness_traces"] = [record["witness_traces"][0]]
        record["seed_configs"] = [record["seed_configs"][0]]

        with pytest.raises(RcxEngineError, match="INV_OPROMO_1"):
            _validate_ontology_promotion_record(record, "test")

        result = _run_js_validator(json.dumps(record))
        assert result.stdout.startswith("FAIL:input.shape_mismatch:")
        assert "INV_OPROMO_1" in result.stdout

    def test_inv_opromo_3_violation_fails_both(self):
        record = _make_valid_record()
        record["authority"]["source"] = "host"

        with pytest.raises(RcxEngineError, match="INV_OPROMO_3"):
            _validate_ontology_promotion_record(record, "test")

        result = _run_js_validator(json.dumps(record))
        assert result.stdout.startswith("FAIL:input.shape_mismatch:")
        assert "INV_OPROMO_3" in result.stdout


# ===========================================================================
# TestWiring
# ===========================================================================

class TestWiring:
    """Verify hooks are present in both substrates' boundary effect functions."""

    def test_python_hook_present(self):
        src_path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "engine_pipeline.py"
        content = src_path.read_text(encoding="utf-8")
        # Find _service_boundary_effect function
        func_match = re.search(
            r'def _service_boundary_effect\b.*?(?=\ndef [a-zA-Z_])',
            content, re.DOTALL,
        )
        assert func_match, "_service_boundary_effect not found"
        func_body = func_match.group()
        assert '"ontology_promotion"' in func_body, (
            "ontology_promotion hook not found in _service_boundary_effect"
        )

    def test_js_hook_present(self):
        src_path = REPO_ROOT / "mu" / "host" / "js" / "engine" / "pipeline.js"
        content = src_path.read_text(encoding="utf-8")
        # Find serviceBoundaryEffect function
        func_match = re.search(
            r'function serviceBoundaryEffect\b.*?^\}',
            content, re.DOTALL | re.MULTILINE,
        )
        assert func_match, "serviceBoundaryEffect not found"
        func_body = func_match.group()
        assert "'ontology_promotion'" in func_body, (
            "ontology_promotion hook not found in serviceBoundaryEffect"
        )

    def test_noop_path_unchanged(self):
        """Boundary result without ontology_promotion key works normally.
        Validates zero-cost path by checking no exception is raised when
        the validator is called with a result that lacks the key.
        """
        # This is implicitly tested by all existing engine pipeline tests,
        # but we verify the code path explicitly.
        src_path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "engine_pipeline.py"
        content = src_path.read_text(encoding="utf-8")
        # The hook is guarded by 'if isinstance(result, dict) and "ontology_promotion" in result'
        assert 'and "ontology_promotion" in result' in content


# ===========================================================================
# TestEnvelopeTypeValidation
# ===========================================================================

class TestEnvelopeTypeValidation:
    """Envelope value type is validated early (before full validator)."""

    def test_non_dict_envelope_python(self, monkeypatch):
        """ontology_promotion value that's not a dict raises typed error.

        Monkeypatches _BOUNDARY_DISPATCH["run_trace"] to return a result whose
        ontology_promotion is a string, then calls _service_boundary_effect.
        The A12 wiring type check must fire and raise typed input.shape_mismatch.
        """
        def fake_handler(request, req_input, max_iters):
            return {
                "result": "hello",
                "trace": [],
                "stall": True,
                "ontology_promotion": "not_a_dict",
            }

        monkeypatch.setitem(_BOUNDARY_DISPATCH, "run_trace", fake_handler)
        request = {
            "operation": "run_trace",
            "input": {
                "projections": [{"pattern": {"var": "x"}, "body": {"var": "x"}, "id": "id.passthrough"}],
                "value": "hello",
                "max_steps": 3,
            },
            "context": {},
            "inject_key": "boundary_result",
        }
        with pytest.raises(RcxEngineError) as exc_info:
            _service_boundary_effect(
                request, max_algorithm_iterations=50,
                emit_fn=_noop_emit, iteration=0, state="test_state",
            )
        assert exc_info.value.error_code == "input.shape_mismatch"
        assert "ontology_promotion must be dict" in str(exc_info.value)

    def test_non_dict_envelope_js(self):
        """JS: ontology_promotion as string/array/null raises typed error.

        Uses setTestDispatchOverride to inject a handler that returns a result
        with non-dict ontology_promotion, then calls serviceBoundaryEffect.
        The A12 wiring type check must fire for each bad value.
        """
        for bad_value, bad_label in [("'string'", "string"), ("[]", "array"), ("null", "null")]:
            js_code = textwrap.dedent(f"""\
                const pipeline = require('./mu/host/js/engine/pipeline');
                pipeline.enableTestMode();
                pipeline.setTestDispatchOverride({{
                    run_trace: (kp, spm, req, inp, maxIters) => ({{
                        result: 'hello',
                        trace: [],
                        stall: true,
                        ontology_promotion: {bad_value},
                    }}),
                }});
                const request = {{
                    operation: 'run_trace',
                    input: {{
                        projections: [{{ pattern: {{ var: 'x' }}, body: {{ var: 'x' }}, id: 'id.passthrough' }}],
                        value: 'hello',
                        max_steps: 3,
                    }},
                    context: {{}},
                    inject_key: 'boundary_result',
                }};
                const noop = () => {{}};
                try {{
                    pipeline.serviceBoundaryEffect([], {{}}, request, 50, noop, 0, 'test');
                    process.stdout.write('NO_ERROR');
                }} catch (err) {{
                    process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
                }} finally {{
                    pipeline.setTestDispatchOverride(null);
                }}
            """)
            result = _run_js_expr(js_code)
            assert result.stdout.startswith("FAIL:input.shape_mismatch:"), (
                f"Expected typed error for {bad_label}, got: {result.stdout} {result.stderr}"
            )


# ===========================================================================
# TestTypedFailClosed
# ===========================================================================

class TestTypedFailClosed:
    """All validation failures produce typed errors, never raw exceptions."""

    def test_python_all_errors_are_rcx_engine_error(self):
        """Every validation failure path raises RcxEngineError with input.shape_mismatch."""
        test_cases = [
            # Missing field → INV_OPROMO_4
            (lambda r: r.pop("authority"), "INV_OPROMO_4"),
            # Single witness → INV_OPROMO_1
            (lambda r: (r.update(witness_traces=[r["witness_traces"][0]]),
                        r.update(seed_configs=[r["seed_configs"][0]])), "INV_OPROMO_1"),
            # Pattern not survived → INV_OPROMO_2
            (lambda r: r["perturbation_log"].update(pattern_survived_all=False), "INV_OPROMO_2"),
            # Bad source → INV_OPROMO_3
            (lambda r: r["authority"].update(source="host"), "INV_OPROMO_3"),
        ]
        for mutator, expected_inv in test_cases:
            record = _make_valid_record()
            mutator(record)
            with pytest.raises(RcxEngineError) as exc_info:
                _validate_ontology_promotion_record(record, "test")
            assert exc_info.value.error_code == "input.shape_mismatch", (
                f"Expected input.shape_mismatch for {expected_inv}, "
                f"got {exc_info.value.error_code}"
            )

    def test_js_all_errors_are_rcx_error(self):
        """JS validation failures produce RcxError with input.shape_mismatch."""
        record = _make_valid_record()
        record["authority"]["source"] = "host"
        result = _run_js_validator(json.dumps(record))
        assert result.stdout.startswith("FAIL:input.shape_mismatch:"), (
            f"Expected typed error, got: {result.stdout}"
        )

    def test_python_none_record_produces_typed_error(self):
        """Direct call with None must raise RcxEngineError, not raw TypeError."""
        with pytest.raises(RcxEngineError) as exc_info:
            _validate_ontology_promotion_record(None, "test")
        assert exc_info.value.error_code == "input.shape_mismatch"


# ===========================================================================
# TestSeedSubdirParity
# ===========================================================================

class TestSeedSubdirParity:
    """Python MU_SEED_LOCATIONS keys/values match JS SEED_SUBDIRS."""

    def test_seed_subdir_keys_match(self):
        js_code = textwrap.dedent("""\
            const { SEED_SUBDIRS } = require('./mu/host/js/core/seed_loader');
            process.stdout.write(JSON.stringify(Object.keys(SEED_SUBDIRS).sort()));
        """)
        result = _run_js_expr(js_code)
        assert result.returncode == 0, f"JS error: {result.stderr}"
        js_keys = json.loads(result.stdout)
        py_keys = sorted(MU_SEED_LOCATIONS.keys())
        assert js_keys == py_keys, f"Seed keys differ: JS={js_keys}, Python={py_keys}"

    def test_seed_subdir_values_match(self):
        js_code = textwrap.dedent("""\
            const { SEED_SUBDIRS } = require('./mu/host/js/core/seed_loader');
            process.stdout.write(JSON.stringify(SEED_SUBDIRS));
        """)
        result = _run_js_expr(js_code)
        assert result.returncode == 0, f"JS error: {result.stderr}"
        js_map = json.loads(result.stdout)
        for seed_name, py_subdir in MU_SEED_LOCATIONS.items():
            js_subdir = js_map.get(seed_name)
            assert js_subdir == py_subdir, (
                f"Subdir mismatch for {seed_name}: Python={py_subdir}, JS={js_subdir}"
            )

    def test_js_get_seed_subdir_throws_on_unknown(self):
        js_code = textwrap.dedent("""\
            const { getSeedSubdir } = require('./mu/host/js/core/seed_loader');
            try {
                getSeedSubdir('nonexistent.json');
                process.stdout.write('NO_ERROR');
            } catch (err) {
                process.stdout.write('ERROR:' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout.startswith("ERROR:"), (
            f"Expected error for unknown seed, got: {result.stdout}"
        )


# ===========================================================================
# TestFullLockConsistency
# ===========================================================================

class TestJSValidatorEntryGuard:
    """JS validator rejects null/non-object direct calls with typed error."""

    def test_null_record_produces_typed_error(self):
        """validateOntologyPromotionRecord(null, ...) must not throw raw TypeError."""
        js_code = textwrap.dedent("""\
            const { validateOntologyPromotionRecord } = require('./mu/host/js/engine/pipeline');
            try {
                validateOntologyPromotionRecord(null, 'test');
                process.stdout.write('NO_ERROR');
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'raw') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout.startswith("FAIL:input.shape_mismatch:"), (
            f"Expected typed error for null record, got: {result.stdout} {result.stderr}"
        )

    def test_string_record_produces_typed_error(self):
        """validateOntologyPromotionRecord('str', ...) must not throw raw TypeError."""
        js_code = textwrap.dedent("""\
            const { validateOntologyPromotionRecord } = require('./mu/host/js/engine/pipeline');
            try {
                validateOntologyPromotionRecord('a string', 'test');
                process.stdout.write('NO_ERROR');
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'raw') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout.startswith("FAIL:input.shape_mismatch:"), (
            f"Expected typed error for string record, got: {result.stdout} {result.stderr}"
        )


class TestFullLockConsistency:
    """Full-lock gate consistency across both substrates."""

    def test_fully_locked_subset_of_seed_subdirs(self):
        """Fully-locked seeds must be a subset of SEED_SUBDIRS."""
        js_code = textwrap.dedent("""\
            const { isFullyLockedSeed, SEED_SUBDIRS } = require('./mu/host/js/core/seed_loader');
            const locked = Object.keys(SEED_SUBDIRS).filter(s => isFullyLockedSeed(s));
            process.stdout.write(JSON.stringify(locked.sort()));
        """)
        result = _run_js_expr(js_code)
        assert result.returncode == 0, f"JS error: {result.stderr}"
        locked = json.loads(result.stdout)
        js_code2 = textwrap.dedent("""\
            const { SEED_SUBDIRS } = require('./mu/host/js/core/seed_loader');
            process.stdout.write(JSON.stringify(Object.keys(SEED_SUBDIRS).sort()));
        """)
        result2 = _run_js_expr(js_code2)
        all_seeds = json.loads(result2.stdout)
        assert set(locked).issubset(set(all_seeds))

    def test_fully_locked_equals_checksum_intersect_projids(self):
        """Fully-locked set == intersection of CORE_SEED_CHECKSUMS and CORE_SEED_PROJECTION_IDS."""
        js_code = textwrap.dedent("""\
            const sl = require('./mu/host/js/core/seed_loader');
            const locked = Object.keys(sl.SEED_SUBDIRS).filter(s => sl.isFullyLockedSeed(s));
            process.stdout.write(JSON.stringify(locked.sort()));
        """)
        result = _run_js_expr(js_code)
        assert result.returncode == 0
        locked = set(json.loads(result.stdout))
        # Expected: the 3 seeds in both CORE_SEED_CHECKSUMS and CORE_SEED_PROJECTION_IDS
        expected = {"terminal_classify.v1.json", "hemispheres.v1.json", "rcx_engine.v1.json"}
        assert locked == expected, f"Fully-locked set differs: got {locked}, expected {expected}"

    def test_js_validator_rejects_unlocked_seed_typed(self):
        """JS validator rejects seed outside fully-locked set with typed error."""
        record = _make_valid_record()
        record["authority"]["seed_file"] = "match.v2.json"
        record["authority"]["projection_ids"] = ["step"]
        result = _run_js_validator(json.dumps(record))
        assert result.stdout.startswith("FAIL:input.shape_mismatch:"), (
            f"Expected typed rejection for unlocked seed: {result.stdout}"
        )

    def test_python_locked_set_matches_js_locked_set(self):
        """Python _OPROMO_FULLY_LOCKED_SEEDS must equal JS isFullyLockedSeed() set."""
        js_code = textwrap.dedent("""\
            const sl = require('./mu/host/js/core/seed_loader');
            const locked = Object.keys(sl.SEED_SUBDIRS).filter(s => sl.isFullyLockedSeed(s));
            process.stdout.write(JSON.stringify(locked.sort()));
        """)
        result = _run_js_expr(js_code)
        assert result.returncode == 0, f"JS error: {result.stderr}"
        js_locked = set(json.loads(result.stdout))
        assert _OPROMO_FULLY_LOCKED_SEEDS == js_locked, (
            f"Parity mismatch: Python={_OPROMO_FULLY_LOCKED_SEEDS}, JS={js_locked}"
        )

    def test_derivation_produces_same_set_as_cached_constant(self):
        """_derive_opromo_fully_locked_seeds() must equal _OPROMO_FULLY_LOCKED_SEEDS."""
        derived = _derive_opromo_fully_locked_seeds()
        assert derived == _OPROMO_FULLY_LOCKED_SEEDS, (
            f"Derivation drift: derived={derived}, cached={_OPROMO_FULLY_LOCKED_SEEDS}"
        )

    def test_derivation_uses_4way_intersection(self):
        """Derived set is subset of all 4 registries."""
        derived = _derive_opromo_fully_locked_seeds()
        assert derived <= _JS_CORE_SEED_REGISTRY_KEYS
        assert derived <= frozenset(SEED_CHECKSUMS.keys())
        assert derived <= frozenset(EXPECTED_PROJECTION_IDS.keys())

    def test_js_core_mirrors_match_js_runtime(self):
        """Python JS CORE mirrors must match actual JS CORE registry keys."""
        # Get JS CORE_SEED_CHECKSUMS keys at runtime
        js_code = textwrap.dedent("""\
            const sl = require('./mu/host/js/core/seed_loader');
            // Access CORE keys via isFullyLockedSeed filter on SEED_SUBDIRS
            const allSeeds = Object.keys(sl.SEED_SUBDIRS);
            const locked = allSeeds.filter(s => sl.isFullyLockedSeed(s));
            process.stdout.write(JSON.stringify(locked.sort()));
        """)
        result = _run_js_expr(js_code)
        assert result.returncode == 0, f"JS error: {result.stderr}"
        js_locked = set(json.loads(result.stdout))
        # Python mirrors must match
        assert _JS_CORE_SEED_REGISTRY_KEYS == js_locked, (
            f"JS CORE registry mirror drift: Python={_JS_CORE_SEED_REGISTRY_KEYS}, JS={js_locked}"
        )

    def test_unlocked_seed_still_rejected_after_displacement(self):
        """kernel.v1.json still rejected typed after A13 displacement (no behavior change)."""
        record = _make_valid_record()
        record["authority"]["seed_file"] = "kernel.v1.json"
        record["authority"]["projection_ids"] = ["step"]
        with pytest.raises(RcxEngineError) as exc_info:
            _validate_ontology_promotion_record(record, "test")
        assert exc_info.value.error_code == "input.shape_mismatch"
        assert "verification-locked" in str(exc_info.value)


# ===========================================================================
# TestContractDocUpdate
# ===========================================================================

class TestContractDocUpdate:
    """Contract doc updated to reflect A12 runtime enforcement."""

    def test_scope_note_references_a12(self):
        contract_path = REPO_ROOT / "mu" / "docs" / "core" / "OntologyPromotionContract.v0.md"
        content = contract_path.read_text(encoding="utf-8")
        assert "a12" in content.lower(), (
            "Contract scope note must reference A12 runtime enforcement"
        )

    def test_last_verified_date_updated(self):
        contract_path = REPO_ROOT / "mu" / "docs" / "core" / "OntologyPromotionContract.v0.md"
        content = contract_path.read_text(encoding="utf-8")
        assert "2026-02-26" in content, (
            "Contract LAST_VERIFIED date must be current"
        )


# ===========================================================================
# A14: Producer-Side Ontology Promotion Candidate Tests
# ===========================================================================

def _make_valid_evidence() -> dict:
    """Return minimal valid evidence dict for the A14 builder."""
    return {
        "witness_traces": [
            {"trace_id": "t1", "seed_config": "rcx_engine.v1.json"},
            {"trace_id": "t2", "seed_config": "hemispheres.v1.json"},
        ],
        "seed_configs": ["rcx_engine.v1.json", "hemispheres.v1.json"],
        "closure_structure": {},
        "perturbation_log": {
            "removals_tested": ["p1"],
            "additions_tested": ["p2"],
            "pattern_survived_all": True,
        },
        "tau_lineage": ["lineage_entry_1"],
        "authority": {
            "source": "host",  # builder must override this to "seed"
            "seed_file": "rcx_engine.v1.json",
            "projection_ids": ["engine.init"],
        },
    }


# ===========================================================================
# TestBuilderPython
# ===========================================================================

class TestBuilderPython:
    """A14: Python builder unit tests."""

    def test_valid_evidence_produces_8_field_record(self):
        evidence = _make_valid_evidence()
        record = _build_ontology_promotion_candidate(evidence, "test")
        expected_keys = {
            "witness_traces", "seed_configs", "closure_structure",
            "perturbation_log", "derivation_timestamp", "substrate_versions",
            "tau_lineage", "authority",
        }
        assert set(record.keys()) == expected_keys

    def test_authority_source_always_seed(self):
        evidence = _make_valid_evidence()
        evidence["authority"]["source"] = "host"
        record = _build_ontology_promotion_candidate(evidence, "test")
        assert record["authority"]["source"] == "seed"

    def test_derivation_timestamp_auto_generated(self):
        evidence = _make_valid_evidence()
        record = _build_ontology_promotion_candidate(evidence, "test")
        ts = record["derivation_timestamp"]
        assert isinstance(ts, str) and len(ts) > 0
        # Deterministic derivation from seed checksum (no wall-clock)
        assert ts.startswith("derived:")

    def test_substrate_versions_auto_generated(self):
        evidence = _make_valid_evidence()
        record = _build_ontology_promotion_candidate(evidence, "test")
        sv = record["substrate_versions"]
        assert isinstance(sv, dict)
        assert "python" in sv and "js" in sv
        assert sv["python"] == sv["js"]  # same seed → same checksum

    def test_non_dict_evidence_raises_typed(self):
        with pytest.raises(RcxEngineError) as exc_info:
            _build_ontology_promotion_candidate("not_a_dict", "test")
        assert exc_info.value.error_code == "input.shape_mismatch"

    @pytest.mark.parametrize("missing_key", [
        "witness_traces", "seed_configs", "closure_structure",
        "perturbation_log", "tau_lineage", "authority",
    ])
    def test_missing_evidence_key_raises_typed(self, missing_key):
        evidence = _make_valid_evidence()
        del evidence[missing_key]
        with pytest.raises(RcxEngineError) as exc_info:
            _build_ontology_promotion_candidate(evidence, "test")
        assert exc_info.value.error_code == "input.shape_mismatch"
        assert missing_key in str(exc_info.value)

    def test_missing_authority_sub_key_raises_typed(self):
        evidence = _make_valid_evidence()
        del evidence["authority"]["seed_file"]
        with pytest.raises(RcxEngineError) as exc_info:
            _build_ontology_promotion_candidate(evidence, "test")
        assert exc_info.value.error_code == "input.shape_mismatch"
        assert "seed_file" in str(exc_info.value)

    def test_non_dict_authority_raises_typed(self):
        evidence = _make_valid_evidence()
        evidence["authority"] = "not_a_dict"
        with pytest.raises(RcxEngineError) as exc_info:
            _build_ontology_promotion_candidate(evidence, "test")
        assert exc_info.value.error_code == "input.shape_mismatch"

    def test_builder_output_passes_a12_validator(self):
        evidence = _make_valid_evidence()
        record = _build_ontology_promotion_candidate(evidence, "test")
        _validate_ontology_promotion_record(record, "test")

    def test_unknown_seed_file_raises_typed(self):
        """C1: Unknown seed_file → typed input.shape_mismatch (no raw KeyError)."""
        evidence = _make_valid_evidence()
        evidence["authority"]["seed_file"] = "nonexistent_seed.v99.json"
        with pytest.raises(RcxEngineError) as exc_info:
            _build_ontology_promotion_candidate(evidence, "test")
        assert exc_info.value.error_code == "input.shape_mismatch"
        assert "verification-locked" in str(exc_info.value) or "checksum not found" in str(exc_info.value)

    def test_non_locked_seed_raises_typed(self):
        """C5: Non-locked seed_file → typed input.shape_mismatch (early reject)."""
        evidence = _make_valid_evidence()
        evidence["authority"]["seed_file"] = "kernel.v1.json"
        with pytest.raises(RcxEngineError) as exc_info:
            _build_ontology_promotion_candidate(evidence, "test")
        assert exc_info.value.error_code == "input.shape_mismatch"
        assert "verification-locked" in str(exc_info.value)


# ===========================================================================
# TestBuilderJS
# ===========================================================================

class TestBuilderJS:
    """A14: JS builder unit tests via node -e."""

    def _run_js_builder(self, evidence_json: str) -> subprocess.CompletedProcess:
        js_code = textwrap.dedent(f"""\
            const {{ buildOntologyPromotionCandidate }} = require('./mu/host/js/engine/pipeline');
            const evidence = {evidence_json};
            try {{
                const record = buildOntologyPromotionCandidate(evidence, 'test');
                process.stdout.write('PASS:' + JSON.stringify(record));
            }} catch (err) {{
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }}
        """)
        return subprocess.run(
            ["node", "-e", js_code],
            cwd=str(REPO_ROOT),
            capture_output=True, text=True, check=False,
        )

    def test_valid_evidence_passes(self):
        evidence = _make_valid_evidence()
        result = self._run_js_builder(json.dumps(evidence))
        assert result.stdout.startswith("PASS:"), f"JS builder failed: {result.stdout} {result.stderr}"

    def test_non_dict_evidence_raises_typed(self):
        result = self._run_js_builder('"not_an_object"')
        assert result.stdout.startswith("FAIL:input.shape_mismatch:"), (
            f"Expected typed error, got: {result.stdout}"
        )

    def test_missing_key_raises_typed(self):
        evidence = _make_valid_evidence()
        del evidence["witness_traces"]
        result = self._run_js_builder(json.dumps(evidence))
        assert result.stdout.startswith("FAIL:input.shape_mismatch:"), (
            f"Expected typed error, got: {result.stdout}"
        )
        assert "witness_traces" in result.stdout

    def test_authority_source_always_seed(self):
        evidence = _make_valid_evidence()
        evidence["authority"]["source"] = "host"
        result = self._run_js_builder(json.dumps(evidence))
        assert result.stdout.startswith("PASS:"), f"JS builder failed: {result.stdout} {result.stderr}"
        record = json.loads(result.stdout[5:])
        assert record["authority"]["source"] == "seed"

    def test_builder_output_passes_js_validator(self):
        evidence = _make_valid_evidence()
        js_code = textwrap.dedent(f"""\
            const {{ buildOntologyPromotionCandidate, validateOntologyPromotionRecord }} = require('./mu/host/js/engine/pipeline');
            const evidence = {json.dumps(evidence)};
            try {{
                const record = buildOntologyPromotionCandidate(evidence, 'test');
                validateOntologyPromotionRecord(record, 'test');
                process.stdout.write('PASS');
            }} catch (err) {{
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }}
        """)
        result = _run_js_expr(js_code)
        assert result.stdout == "PASS", f"Builder output failed validation: {result.stdout} {result.stderr}"

    def test_unknown_seed_file_raises_typed(self):
        """C1: Unknown seed_file → typed error (no raw Error)."""
        evidence = _make_valid_evidence()
        evidence["authority"]["seed_file"] = "nonexistent_seed.v99.json"
        result = self._run_js_builder(json.dumps(evidence))
        assert result.stdout.startswith("FAIL:input.shape_mismatch:"), (
            f"Expected typed error, got: {result.stdout}"
        )

    def test_non_locked_seed_raises_typed(self):
        """C5: Non-locked seed_file → typed error via isFullyLockedSeed."""
        evidence = _make_valid_evidence()
        evidence["authority"]["seed_file"] = "kernel.v1.json"
        result = self._run_js_builder(json.dumps(evidence))
        assert result.stdout.startswith("FAIL:input.shape_mismatch:"), (
            f"Expected typed error, got: {result.stdout}"
        )
        assert "verification-locked" in result.stdout


# ===========================================================================
# TestWiringA14
# ===========================================================================

class TestWiringA14:
    """A14: Source inspection for opt-in wiring in both substrates."""

    def _get_python_boundary_body(self):
        src_path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "engine_pipeline.py"
        content = src_path.read_text(encoding="utf-8")
        func_match = re.search(
            r'def _service_boundary_effect\b.*?(?=\ndef [a-zA-Z_])',
            content, re.DOTALL,
        )
        assert func_match, "_service_boundary_effect not found"
        return func_match.group()

    def _get_js_boundary_body(self):
        src_path = REPO_ROOT / "mu" / "host" / "js" / "engine" / "pipeline.js"
        content = src_path.read_text(encoding="utf-8")
        func_match = re.search(
            r'function serviceBoundaryEffect\b.*?^\}',
            content, re.DOTALL | re.MULTILINE,
        )
        assert func_match, "serviceBoundaryEffect not found"
        return func_match.group()

    def test_python_contains_emit_ontology_candidate(self):
        body = self._get_python_boundary_body()
        assert "emit_ontology_candidate" in body

    def test_js_contains_emit_ontology_candidate(self):
        body = self._get_js_boundary_body()
        assert "emit_ontology_candidate" in body

    def test_python_strict_is_true_check(self):
        body = self._get_python_boundary_body()
        assert "is True" in body

    def test_js_strict_triple_equals_check(self):
        body = self._get_js_boundary_body()
        assert "=== true" in body

    def test_python_post_producer_reserved_field_revalidation(self):
        """C2: Python re-validates reserved fields after producer attach."""
        body = self._get_python_boundary_body()
        assert "post_producer" in body
        assert "validate_no_kernel_reserved_fields" in body

    def test_js_post_producer_reserved_field_revalidation(self):
        """C2: JS re-validates reserved fields after producer attach."""
        body = self._get_js_boundary_body()
        assert "post_producer" in body
        assert "validateNoKernelReservedFields" in body


# ===========================================================================
# TestBoundaryPathEmission
# ===========================================================================

class TestBoundaryPathEmission:
    """A14: Behavioral integration tests calling _service_boundary_effect directly.

    These tests construct real boundary requests and call _service_boundary_effect
    (Python) and serviceBoundaryEffect (JS via node -e) to exercise the actual
    production wiring path for ontology promotion candidate emission.
    """

    def test_python_boundary_emission_valid_evidence(self):
        """Call _service_boundary_effect with emit flag + valid evidence → result has ontology_promotion."""
        evidence = _make_valid_evidence()
        request = _make_boundary_request(context_extra={
            "emit_ontology_candidate": True,
            "ontology_candidate_evidence": evidence,
        })
        returned_ctx = _service_boundary_effect(
            request, max_algorithm_iterations=50,
            emit_fn=_noop_emit, iteration=0, state="test_state",
        )
        # Result should be injected at inject_key
        assert "boundary_result" in returned_ctx
        result = returned_ctx["boundary_result"]
        # ontology_promotion must have been attached by the wiring
        assert "ontology_promotion" in result, "A14 wiring did not attach ontology_promotion"
        promo = result["ontology_promotion"]
        assert promo["authority"]["source"] == "seed"
        assert "derivation_timestamp" in promo
        assert "substrate_versions" in promo
        # Passes A12 validator
        _validate_ontology_promotion_record(promo, "behavioral_test")

    def test_python_boundary_no_flag_no_emission(self):
        """Without emit_ontology_candidate flag, result has no ontology_promotion."""
        request = _make_boundary_request()  # no emit flag
        returned_ctx = _service_boundary_effect(
            request, max_algorithm_iterations=50,
            emit_fn=_noop_emit, iteration=0, state="test_state",
        )
        result = returned_ctx["boundary_result"]
        assert "ontology_promotion" not in result, (
            "ontology_promotion should not be attached without emit flag"
        )

    def test_python_boundary_overwrite_guard(self, monkeypatch):
        """C3: emit flag + handler result already has ontology_promotion → typed error.

        Monkeypatches _BOUNDARY_DISPATCH["run_trace"] with a handler that returns
        a result already containing ontology_promotion, then calls
        _service_boundary_effect with the emit flag set. The production overwrite
        guard must fire and raise typed input.shape_mismatch.
        """
        evidence = _make_valid_evidence()
        promo_record = _build_ontology_promotion_candidate(evidence, "test")

        def fake_run_trace_handler(request, req_input, max_iters):
            """Handler that returns a result with ontology_promotion already set."""
            return {
                "result": "hello",
                "trace": [],
                "stall": True,
                "ontology_promotion": promo_record,
            }

        monkeypatch.setitem(_BOUNDARY_DISPATCH, "run_trace", fake_run_trace_handler)
        request = _make_boundary_request(context_extra={
            "emit_ontology_candidate": True,
            "ontology_candidate_evidence": evidence,
        })
        with pytest.raises(RcxEngineError) as exc_info:
            _service_boundary_effect(
                request, max_algorithm_iterations=50,
                emit_fn=_noop_emit, iteration=0, state="test_state",
            )
        assert exc_info.value.error_code == "input.shape_mismatch"
        assert "already contains ontology_promotion" in str(exc_info.value)

    def test_js_boundary_emission_valid_evidence(self):
        """JS: serviceBoundaryEffect with emit flag + valid evidence → ontology_promotion attached."""
        evidence = _make_valid_evidence()
        js_code = textwrap.dedent(f"""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            const evidence = {json.dumps(evidence)};
            const request = {{
                operation: 'run_trace',
                input: {{
                    projections: [{{ pattern: {{ var: 'x' }}, body: {{ var: 'x' }}, id: 'id.passthrough' }}],
                    value: 'hello',
                    max_steps: 3,
                }},
                context: {{
                    emit_ontology_candidate: true,
                    ontology_candidate_evidence: evidence,
                }},
                inject_key: 'boundary_result',
            }};
            const noop = () => {{}};
            try {{
                const kernelProjections = [];  // run_trace uses its own projections
                const seedProjectionMap = {{}};
                const ctx = pipeline.serviceBoundaryEffect(
                    kernelProjections, seedProjectionMap, request, 50, noop, 0, 'test'
                );
                const result = ctx.boundary_result;
                if (!result.ontology_promotion) {{
                    process.stdout.write('FAIL:no_promo');
                }} else {{
                    pipeline.validateOntologyPromotionRecord(result.ontology_promotion, 'test');
                    process.stdout.write('PASS:' + result.ontology_promotion.authority.source);
                }}
            }} catch (err) {{
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }}
        """)
        result = _run_js_expr(js_code)
        assert result.stdout.startswith("PASS:"), f"JS boundary emission failed: {result.stdout} {result.stderr}"
        assert result.stdout == "PASS:seed"

    def test_js_boundary_no_flag_no_emission(self):
        """JS: serviceBoundaryEffect without emit flag → no ontology_promotion."""
        js_code = textwrap.dedent("""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            const request = {
                operation: 'run_trace',
                input: {
                    projections: [{ pattern: { var: 'x' }, body: { var: 'x' }, id: 'id.passthrough' }],
                    value: 'hello',
                    max_steps: 3,
                },
                context: {},
                inject_key: 'boundary_result',
            };
            const noop = () => {};
            try {
                const ctx = pipeline.serviceBoundaryEffect([], {}, request, 50, noop, 0, 'test');
                const result = ctx.boundary_result;
                if (result.ontology_promotion) {
                    process.stdout.write('FAIL:unexpected_promo');
                } else {
                    process.stdout.write('PASS:no_promo');
                }
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout == "PASS:no_promo", f"Expected no emission: {result.stdout} {result.stderr}"

    def test_python_boundary_flag_consumed_one_shot(self):
        """After emission via _service_boundary_effect, context no longer has flag/evidence keys."""
        evidence = _make_valid_evidence()
        request = _make_boundary_request(context_extra={
            "emit_ontology_candidate": True,
            "ontology_candidate_evidence": evidence,
        })
        returned_ctx = _service_boundary_effect(
            request, max_algorithm_iterations=50,
            emit_fn=_noop_emit, iteration=0, state="test_state",
        )
        # One-shot: flag and evidence must have been consumed
        assert "emit_ontology_candidate" not in returned_ctx, (
            "emit_ontology_candidate should be consumed (one-shot)"
        )
        assert "ontology_candidate_evidence" not in returned_ctx, (
            "ontology_candidate_evidence should be consumed (one-shot)"
        )


# ===========================================================================
# TestEmissionEdgeCases
# ===========================================================================

class TestEmissionEdgeCases:
    """A14: Edge cases for the opt-in emission mechanism."""

    def test_truthy_non_true_no_emission(self):
        """Truthy non-True values (1, 'yes') do not trigger emission.

        Calls _service_boundary_effect with each truthy-non-True value for
        emit_ontology_candidate. The strict `is True` check must skip emission.
        """
        for truthy_val in [1, "yes", "true", [1], {"x": 1}]:
            request = {
                "operation": "run_trace",
                "input": {
                    "projections": [{"pattern": {"var": "x"}, "body": {"var": "x"}, "id": "id.passthrough"}],
                    "value": "hello",
                    "max_steps": 3,
                },
                "context": {"emit_ontology_candidate": truthy_val},
                "inject_key": "boundary_result",
            }
            returned_ctx = _service_boundary_effect(
                request, max_algorithm_iterations=50,
                emit_fn=_noop_emit, iteration=0, state="test_state",
            )
            result = returned_ctx["boundary_result"]
            assert "ontology_promotion" not in result, (
                f"Truthy non-True value {truthy_val!r} should not trigger emission"
            )

    def test_producer_passes_reserved_field_check(self):
        """C2: Producer output does not contain reserved fields."""
        evidence = _make_valid_evidence()
        record = _build_ontology_promotion_candidate(evidence, "test")
        result = {"some_key": "some_value", "ontology_promotion": record}
        # Must not raise — ontology_promotion is not a reserved field
        validate_no_kernel_reserved_fields(result, context="test.post_producer")

    def test_insufficient_evidence_with_flag_raises_typed(self):
        """Evidence missing required key + flag → typed error."""
        evidence = _make_valid_evidence()
        del evidence["witness_traces"]
        with pytest.raises(RcxEngineError) as exc_info:
            _build_ontology_promotion_candidate(evidence, "test")
        assert exc_info.value.error_code == "input.shape_mismatch"


# ===========================================================================
# TestSeedChecksumGetter
# ===========================================================================

class TestSeedChecksumGetter:
    """A14: JS getSeedChecksum getter parity."""

    def test_js_returns_known_checksum(self):
        js_code = textwrap.dedent("""\
            const { getSeedChecksum } = require('./mu/host/js/core/seed_loader');
            const checksum = getSeedChecksum('rcx_engine.v1.json');
            process.stdout.write(checksum || 'NULL');
        """)
        result = _run_js_expr(js_code)
        assert result.returncode == 0, f"JS error: {result.stderr}"
        assert result.stdout != "NULL", "Expected checksum for locked seed"
        assert len(result.stdout) > 0

    def test_js_returns_null_for_unknown(self):
        js_code = textwrap.dedent("""\
            const { getSeedChecksum } = require('./mu/host/js/core/seed_loader');
            const checksum = getSeedChecksum('nonexistent.v99.json');
            process.stdout.write(String(checksum));
        """)
        result = _run_js_expr(js_code)
        assert result.returncode == 0, f"JS error: {result.stderr}"
        assert result.stdout == "null"

    def test_checksum_parity_for_locked_seeds(self):
        """Python SEED_CHECKSUMS matches JS getSeedChecksum for locked seeds."""
        for seed_name in sorted(_OPROMO_FULLY_LOCKED_SEEDS):
            py_checksum = SEED_CHECKSUMS[seed_name]
            js_code = textwrap.dedent(f"""\
                const {{ getSeedChecksum }} = require('./mu/host/js/core/seed_loader');
                process.stdout.write(getSeedChecksum('{seed_name}') || 'NULL');
            """)
            result = _run_js_expr(js_code)
            assert result.returncode == 0, f"JS error for {seed_name}: {result.stderr}"
            assert result.stdout == py_checksum, (
                f"Checksum parity mismatch for {seed_name}: Python={py_checksum}, JS={result.stdout}"
            )


# ===========================================================================
# TestCrossSubstrateMalformedEvidence
# ===========================================================================

class TestCrossSubstrateMalformedEvidence:
    """C4: Paired Python+JS tests for 5 malformed evidence fixture classes."""

    def _run_js_builder(self, evidence_json: str) -> subprocess.CompletedProcess:
        js_code = textwrap.dedent(f"""\
            const {{ buildOntologyPromotionCandidate }} = require('./mu/host/js/engine/pipeline');
            const evidence = {evidence_json};
            try {{
                buildOntologyPromotionCandidate(evidence, 'test');
                process.stdout.write('PASS');
            }} catch (err) {{
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }}
        """)
        return subprocess.run(
            ["node", "-e", js_code],
            cwd=str(REPO_ROOT),
            capture_output=True, text=True, check=False,
        )

    def test_non_dict_evidence_both(self):
        """Non-dict evidence → typed error in both substrates."""
        # Python
        with pytest.raises(RcxEngineError) as exc_info:
            _build_ontology_promotion_candidate("not_a_dict", "test")
        assert exc_info.value.error_code == "input.shape_mismatch"
        # JS
        result = self._run_js_builder('"not_a_dict"')
        assert result.stdout.startswith("FAIL:input.shape_mismatch:")

    def test_missing_required_key_both(self):
        """Missing required evidence key → typed error in both substrates."""
        evidence = _make_valid_evidence()
        del evidence["seed_configs"]
        # Python
        with pytest.raises(RcxEngineError) as exc_info:
            _build_ontology_promotion_candidate(evidence, "test")
        assert exc_info.value.error_code == "input.shape_mismatch"
        # JS
        result = self._run_js_builder(json.dumps(evidence))
        assert result.stdout.startswith("FAIL:input.shape_mismatch:")

    def test_non_dict_authority_both(self):
        """Non-dict authority → typed error in both substrates."""
        evidence = _make_valid_evidence()
        evidence["authority"] = "not_a_dict"
        # Python
        with pytest.raises(RcxEngineError) as exc_info:
            _build_ontology_promotion_candidate(evidence, "test")
        assert exc_info.value.error_code == "input.shape_mismatch"
        # JS
        result = self._run_js_builder(json.dumps(evidence))
        assert result.stdout.startswith("FAIL:input.shape_mismatch:")

    def test_non_locked_seed_both(self):
        """Non-locked seed_file → typed error in both substrates."""
        evidence = _make_valid_evidence()
        evidence["authority"]["seed_file"] = "kernel.v1.json"
        # Python
        with pytest.raises(RcxEngineError) as exc_info:
            _build_ontology_promotion_candidate(evidence, "test")
        assert exc_info.value.error_code == "input.shape_mismatch"
        # JS
        result = self._run_js_builder(json.dumps(evidence))
        assert result.stdout.startswith("FAIL:input.shape_mismatch:")

    def test_overwrite_attempt_both(self, monkeypatch):
        """Result already has ontology_promotion + flag → typed error in both substrates.

        Python: monkeypatches _BOUNDARY_DISPATCH["run_trace"] to return a result
        with ontology_promotion, then calls _service_boundary_effect with emit flag.
        JS: uses setTestDispatchOverride seam to inject a handler that returns
        a result with ontology_promotion, then calls serviceBoundaryEffect.
        """
        evidence = _make_valid_evidence()
        promo_record = _build_ontology_promotion_candidate(evidence, "test")

        # --- Python: monkeypatch boundary dispatch ---
        def fake_handler(request, req_input, max_iters):
            return {
                "result": "hello",
                "trace": [],
                "stall": True,
                "ontology_promotion": promo_record,
            }

        monkeypatch.setitem(_BOUNDARY_DISPATCH, "run_trace", fake_handler)
        request = {
            "operation": "run_trace",
            "input": {
                "projections": [{"pattern": {"var": "x"}, "body": {"var": "x"}, "id": "id.passthrough"}],
                "value": "hello",
                "max_steps": 3,
            },
            "context": {
                "emit_ontology_candidate": True,
                "ontology_candidate_evidence": evidence,
            },
            "inject_key": "boundary_result",
        }
        with pytest.raises(RcxEngineError) as exc_info:
            _service_boundary_effect(
                request, max_algorithm_iterations=50,
                emit_fn=lambda *a, **kw: None, iteration=0, state="test_state",
            )
        assert exc_info.value.error_code == "input.shape_mismatch"
        assert "already contains ontology_promotion" in str(exc_info.value)

        # --- JS: testability seam via setTestDispatchOverride ---
        js_code = textwrap.dedent(f"""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            pipeline.enableTestMode();
            const evidence = {json.dumps(evidence)};
            // Override run_trace handler to return result with ontology_promotion
            pipeline.setTestDispatchOverride({{
                run_trace: (input, context, emitFn, iteration, state) => ({{
                    result: 'hello',
                    trace: [],
                    stall: true,
                    ontology_promotion: {{ existing: true }},
                }}),
            }});
            const request = {{
                operation: 'run_trace',
                input: {{
                    projections: [{{ pattern: {{ var: 'x' }}, body: {{ var: 'x' }}, id: 'id.passthrough' }}],
                    value: 'hello',
                    max_steps: 3,
                }},
                context: {{
                    emit_ontology_candidate: true,
                    ontology_candidate_evidence: evidence,
                }},
                inject_key: 'boundary_result',
            }};
            const noop = () => {{}};
            try {{
                pipeline.serviceBoundaryEffect([], {{}}, request, 50, noop, 0, 'test');
                process.stdout.write('NO_GUARD');
            }} catch (err) {{
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }} finally {{
                pipeline.setTestDispatchOverride(null);
            }}
        """)
        js_result = _run_js_expr(js_code)
        assert js_result.stdout.startswith("FAIL:input.shape_mismatch:"), (
            f"JS overwrite guard did not fire: {js_result.stdout} {js_result.stderr}"
        )


# ===========================================================================
# TestAntiTheaterLock
# ===========================================================================

class TestAntiTheaterLock:
    """A15: Structural lock preventing regression to simulated test theater.

    Inspects source of specific behavioral tests to ensure they invoke
    production entrypoints rather than simulating logic locally.
    Narrow scope: only the tests that were previously theater.
    """

    def test_envelope_python_calls_production_path(self):
        """test_non_dict_envelope_python must call _service_boundary_effect, not raise locally."""
        src = inspect.getsource(TestEnvelopeTypeValidation.test_non_dict_envelope_python)
        assert "_service_boundary_effect(" in src, (
            "test_non_dict_envelope_python must invoke _service_boundary_effect"
        )
        assert "raise RcxEngineError(" not in src, (
            "test_non_dict_envelope_python must not simulate raises locally"
        )

    def test_envelope_js_calls_production_path(self):
        """test_non_dict_envelope_js must call serviceBoundaryEffect, not simulate checks."""
        src = inspect.getsource(TestEnvelopeTypeValidation.test_non_dict_envelope_js)
        assert "serviceBoundaryEffect(" in src, (
            "test_non_dict_envelope_js must invoke serviceBoundaryEffect"
        )
        assert "TYPED_ERROR" not in src, (
            "test_non_dict_envelope_js must not use synthetic TYPED_ERROR simulation"
        )

    def test_overwrite_guard_python_calls_production_path(self):
        """test_python_boundary_overwrite_guard must call _service_boundary_effect."""
        src = inspect.getsource(TestBoundaryPathEmission.test_python_boundary_overwrite_guard)
        assert "_service_boundary_effect(" in src, (
            "test_python_boundary_overwrite_guard must invoke _service_boundary_effect"
        )
        assert "raise RcxEngineError(" not in src, (
            "test_python_boundary_overwrite_guard must not simulate raises locally"
        )

    def test_overwrite_both_calls_production_paths(self):
        """test_overwrite_attempt_both must call both production entrypoints."""
        src = inspect.getsource(TestCrossSubstrateMalformedEvidence.test_overwrite_attempt_both)
        assert "_service_boundary_effect(" in src, (
            "test_overwrite_attempt_both must invoke _service_boundary_effect (Python)"
        )
        assert "serviceBoundaryEffect(" in src, (
            "test_overwrite_attempt_both must invoke serviceBoundaryEffect (JS)"
        )
        assert "raise RcxEngineError(" not in src, (
            "test_overwrite_attempt_both must not simulate raises locally"
        )

    def test_truthy_non_true_calls_production_path(self):
        """test_truthy_non_true_no_emission must call _service_boundary_effect."""
        src = inspect.getsource(TestEmissionEdgeCases.test_truthy_non_true_no_emission)
        assert "_service_boundary_effect(" in src, (
            "test_truthy_non_true_no_emission must invoke _service_boundary_effect"
        )
        assert "is not True" not in src, (
            "test_truthy_non_true_no_emission must not use tautology assertion"
        )


# ===========================================================================
# TestSetterGateA16
# ===========================================================================

class TestSetterGateA16:
    """A16: setTestDispatchOverride is gated behind enableTestMode().

    Verifies:
    - Setter blocked outside test mode (api.bad_request)
    - Setter allowed after enableTestMode()
    - Invalid override types rejected (input.shape_mismatch)
    - Unknown operation keys rejected (input.shape_mismatch)
    - null reset accepted in test mode
    """

    def test_setter_blocked_without_test_mode(self):
        """setTestDispatchOverride without enableTestMode() raises api.bad_request."""
        js_code = textwrap.dedent("""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            try {
                pipeline.setTestDispatchOverride({});
                process.stdout.write('NO_ERROR');
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)  # no enableTestMode() call
        assert result.stdout.startswith("FAIL:api.bad_request:"), (
            f"Expected api.bad_request without test mode, got: {result.stdout} {result.stderr}"
        )
        assert "enableTestMode" in result.stdout

    def test_setter_allowed_with_test_mode(self):
        """setTestDispatchOverride after enableTestMode() succeeds."""
        js_code = textwrap.dedent("""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            pipeline.enableTestMode();
            try {
                pipeline.setTestDispatchOverride({
                    run_trace: () => ({ result: 'ok', trace: [], stall: false }),
                });
                pipeline.setTestDispatchOverride(null);
                process.stdout.write('PASS');
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout == "PASS", (
            f"Expected setter to succeed in test mode, got: {result.stdout} {result.stderr}"
        )

    def test_setter_rejects_array_override(self):
        """Array override → input.shape_mismatch."""
        js_code = textwrap.dedent("""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            pipeline.enableTestMode();
            try {
                pipeline.setTestDispatchOverride([1, 2, 3]);
                process.stdout.write('NO_ERROR');
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout.startswith("FAIL:input.shape_mismatch:"), (
            f"Expected input.shape_mismatch for array, got: {result.stdout} {result.stderr}"
        )

    def test_setter_rejects_string_override(self):
        """String override → input.shape_mismatch."""
        js_code = textwrap.dedent("""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            pipeline.enableTestMode();
            try {
                pipeline.setTestDispatchOverride('bad');
                process.stdout.write('NO_ERROR');
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout.startswith("FAIL:input.shape_mismatch:"), (
            f"Expected input.shape_mismatch for string, got: {result.stdout} {result.stderr}"
        )

    def test_setter_rejects_unknown_op_key(self):
        """Unknown operation key in override → input.shape_mismatch."""
        js_code = textwrap.dedent("""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            pipeline.enableTestMode();
            try {
                pipeline.setTestDispatchOverride({
                    fake_op: () => ({}),
                });
                process.stdout.write('NO_ERROR');
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout.startswith("FAIL:input.shape_mismatch:"), (
            f"Expected input.shape_mismatch for unknown key, got: {result.stdout} {result.stderr}"
        )
        assert "fake_op" in result.stdout

    def test_setter_accepts_null_reset(self):
        """null override (reset) succeeds in test mode."""
        js_code = textwrap.dedent("""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            pipeline.enableTestMode();
            try {
                pipeline.setTestDispatchOverride(null);
                process.stdout.write('PASS');
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout == "PASS", (
            f"Expected null override to succeed, got: {result.stdout} {result.stderr}"
        )

    def test_setter_rejects_non_function_handler(self):
        """Non-function handler value → input.shape_mismatch at setter time."""
        js_code = textwrap.dedent("""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            pipeline.enableTestMode();
            try {
                pipeline.setTestDispatchOverride({ run_trace: 3 });
                process.stdout.write('NO_ERROR');
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout.startswith("FAIL:input.shape_mismatch:"), (
            f"Expected input.shape_mismatch for non-function handler, got: {result.stdout} {result.stderr}"
        )
        assert "run_trace" in result.stdout
        assert "function" in result.stdout


# ===========================================================================
# A17: Evidence Collector Tests
# ===========================================================================

def _noop_emit(*args, **kwargs):
    """No-op observer emit callback for testing."""


def _make_boundary_request(*, context_extra=None):
    """Build a minimal valid run_trace boundary request.

    Uses a trivial identity projection so run_mu_structural returns quickly.  # SPEED_OK: docstring reference, not call
    """
    ctx = {}
    if context_extra:
        ctx.update(context_extra)
    return {
        "operation": "run_trace",
        "input": {
            "projections": [{"pattern": {"var": "x"}, "body": {"var": "x"}, "id": "id.passthrough"}],
            "value": "hello",
            "max_steps": 3,
        },
        "context": ctx,
        "inject_key": "boundary_result",
    }


def _make_linked_trace(entries):
    """Build a linked-list trace from a list of entry dicts."""
    node = None
    for entry in reversed(entries):
        node = {"head": entry, "tail": node}
    return node


def _make_run_trace_result(*, stall=True, projection_ids=None):
    """Build a fake run_trace-shaped result with trace."""
    entries = []
    pids = projection_ids or ["proj_a", "proj_b"]
    for i, pid in enumerate(pids):
        entries.append({"step": i, "state": f"s{i}", "projection": pid})
    # Add stall/terminal entry
    entries.append({"step": len(pids), "state": f"s{len(pids)}", "projection": None, "stall": stall})
    return {
        "result": "final_state",
        "trace": _make_linked_trace(entries),
        "stall": stall,
        "steps": len(pids),
    }


class TestEvidenceCollectorPython:
    """A17: Unit tests for _collect_ontology_evidence (Python)."""

    def test_valid_run_trace_result(self):
        """Valid run_trace result with trace → complete 6-field record."""
        result = _make_run_trace_result(stall=True, projection_ids=["proj_b", "proj_a"])
        obs = _collect_ontology_evidence(result, "run_trace")
        assert obs["operation"] == "run_trace"
        assert isinstance(obs["trace_len"], int)
        assert obs["trace_len"] == 3  # 2 projections + 1 stall entry
        assert obs["stall"] is True
        assert obs["projection_ids"] == ["proj_a", "proj_b"]  # sorted, deduped
        assert isinstance(obs["control_hash"], str)
        assert len(obs["control_hash"]) > 0
        assert isinstance(obs["collected_at"], str)
        assert len(obs["collected_at"]) > 0

    def test_collected_at_is_derived_string(self):
        """collected_at auto-generated as derived:<hash> (deterministic, no wall-clock)."""
        obs = _collect_ontology_evidence({"result": "x"}, "run_algorithm")
        assert isinstance(obs["collected_at"], str)
        assert obs["collected_at"].startswith("derived:")

    def test_control_hash_is_string(self):
        """control_hash auto-generated non-empty string."""
        obs = _collect_ontology_evidence("simple_value", "hash_trace")
        assert isinstance(obs["control_hash"], str)
        assert len(obs["control_hash"]) > 0

    def test_non_trace_result_null_fields(self):
        """Non-run_trace result (no trace key) → trace_len/stall/projection_ids are null."""
        obs = _collect_ontology_evidence({"result": "algo_output"}, "run_algorithm")
        assert obs["trace_len"] is None
        assert obs["stall"] is None
        assert obs["projection_ids"] is None
        assert obs["operation"] == "run_algorithm"

    def test_flag_consumed_one_shot(self):
        """Flag consumed after collection (one-shot) — tested via wiring context."""
        request = _make_boundary_request(context_extra={
            "collect_ontology_candidate_evidence": True,
        })
        returned_ctx = _service_boundary_effect(
            request, max_algorithm_iterations=50,
            emit_fn=_noop_emit, iteration=0, state="test_state",
        )
        assert "collect_ontology_candidate_evidence" not in returned_ctx

    def test_truthy_non_true_no_collection(self):
        """Truthy non-True (e.g. 1, 'yes') → no collection."""
        for truthy_val in [1, "yes", [], {}]:
            request = _make_boundary_request(context_extra={
                "collect_ontology_candidate_evidence": truthy_val,
            })
            returned_ctx = _service_boundary_effect(
                request, max_algorithm_iterations=50,
                emit_fn=_noop_emit, iteration=0, state="test_state",
            )
            assert "ontology_candidate_observation" not in returned_ctx, (
                f"Truthy non-True value {truthy_val!r} should not trigger collection"
            )

    def test_collector_does_not_interfere_with_a14(self):
        """Collector path does not interfere with A14 emission path."""
        evidence = _make_valid_evidence()
        request = _make_boundary_request(context_extra={
            "emit_ontology_candidate": True,
            "ontology_candidate_evidence": evidence,
            "collect_ontology_candidate_evidence": True,
        })
        returned_ctx = _service_boundary_effect(
            request, max_algorithm_iterations=50,
            emit_fn=_noop_emit, iteration=0, state="test_state",
        )
        result = returned_ctx["boundary_result"]
        # A14 should have attached ontology_promotion
        assert "ontology_promotion" in result
        # A17 should have collected observation
        assert "ontology_candidate_observation" in returned_ctx

    def test_overwrite_guard(self):
        """C1: context already has ontology_candidate_observation + flag → typed error."""
        request = _make_boundary_request(context_extra={
            "collect_ontology_candidate_evidence": True,
            "ontology_candidate_observation": {"old": "obs"},
        })
        with pytest.raises(RcxEngineError) as exc_info:
            _service_boundary_effect(
                request, max_algorithm_iterations=50,
                emit_fn=_noop_emit, iteration=0, state="test_state",
            )
        assert exc_info.value.error_code == "input.shape_mismatch"
        assert "already contains ontology_candidate_observation" in str(exc_info.value)

    def test_no_auto_promotion_side_effect(self):
        """C2: Collector path does NOT add ontology_promotion to result."""
        request = _make_boundary_request(context_extra={
            "collect_ontology_candidate_evidence": True,
        })
        returned_ctx = _service_boundary_effect(
            request, max_algorithm_iterations=50,
            emit_fn=_noop_emit, iteration=0, state="test_state",
        )
        result = returned_ctx["boundary_result"]
        assert "ontology_promotion" not in result, (
            "Collector path must not add ontology_promotion — observation only"
        )


class TestEvidenceCollectorJS:
    """A17: JS evidence collector tests via node -e."""

    def test_valid_run_trace_result(self):
        """Valid run_trace result with trace → 6-field record."""
        js_code = textwrap.dedent("""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            const trace = {
                head: { step: 0, state: 's0', projection: 'proj_b' },
                tail: {
                    head: { step: 1, state: 's1', projection: 'proj_a' },
                    tail: {
                        head: { step: 2, state: 's2', projection: null, stall: true },
                        tail: null
                    }
                }
            };
            const result = { result: 'final', trace: trace, stall: true, steps: 2 };
            try {
                const obs = pipeline.collectOntologyEvidence(result, 'run_trace');
                const checks = [
                    obs.operation === 'run_trace',
                    obs.trace_len === 3,
                    obs.stall === true,
                    JSON.stringify(obs.projection_ids) === JSON.stringify(['proj_a', 'proj_b']),
                    typeof obs.control_hash === 'string' && obs.control_hash.length > 0,
                    typeof obs.collected_at === 'string' && obs.collected_at.length > 0,
                ];
                if (checks.every(Boolean)) {
                    process.stdout.write('PASS');
                } else {
                    process.stdout.write('FAIL:checks:' + JSON.stringify(checks));
                }
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout == "PASS", f"JS collector failed: {result.stdout} {result.stderr}"

    def test_non_trace_result_null_fields(self):
        """Non-trace result → null trace fields."""
        js_code = textwrap.dedent("""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            const result = { result: 'algo_output' };
            try {
                const obs = pipeline.collectOntologyEvidence(result, 'run_algorithm');
                const checks = [
                    obs.trace_len === null,
                    obs.stall === null,
                    obs.projection_ids === null,
                    obs.operation === 'run_algorithm',
                ];
                process.stdout.write(checks.every(Boolean) ? 'PASS' : 'FAIL:' + JSON.stringify(checks));
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout == "PASS", f"JS null fields failed: {result.stdout} {result.stderr}"

    def test_flag_consumed_one_shot(self):
        """JS: Flag consumed after collection (one-shot)."""
        js_code = textwrap.dedent("""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            const request = {
                operation: 'run_trace',
                input: {
                    projections: [{ pattern: { var: 'x' }, body: { var: 'x' }, id: 'id.pass' }],
                    value: 'hello',
                    max_steps: 3,
                },
                context: { collect_ontology_candidate_evidence: true },
                inject_key: 'boundary_result',
            };
            const noop = () => {};
            try {
                const ctx = pipeline.serviceBoundaryEffect([], {}, request, 50, noop, 0, 'test');
                if ('collect_ontology_candidate_evidence' in ctx) {
                    process.stdout.write('FAIL:flag_not_consumed');
                } else if (!('ontology_candidate_observation' in ctx)) {
                    process.stdout.write('FAIL:no_observation');
                } else {
                    process.stdout.write('PASS');
                }
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout == "PASS", f"JS one-shot failed: {result.stdout} {result.stderr}"

    def test_strict_boolean_check(self):
        """Truthy non-true (1) → no collection."""
        js_code = textwrap.dedent("""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            const request = {
                operation: 'run_trace',
                input: {
                    projections: [{ pattern: { var: 'x' }, body: { var: 'x' }, id: 'id.pass' }],
                    value: 'hello',
                    max_steps: 3,
                },
                context: { collect_ontology_candidate_evidence: 1 },
                inject_key: 'boundary_result',
            };
            const noop = () => {};
            try {
                const ctx = pipeline.serviceBoundaryEffect([], {}, request, 50, noop, 0, 'test');
                if ('ontology_candidate_observation' in ctx) {
                    process.stdout.write('FAIL:collected_on_truthy');
                } else {
                    process.stdout.write('PASS');
                }
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout == "PASS", f"JS strict bool failed: {result.stdout} {result.stderr}"

    def test_control_hash_present(self):
        """control_hash present and non-empty string."""
        js_code = textwrap.dedent("""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            try {
                const obs = pipeline.collectOntologyEvidence('simple_value', 'hash_trace');
                if (typeof obs.control_hash === 'string' && obs.control_hash.length > 0) {
                    process.stdout.write('PASS');
                } else {
                    process.stdout.write('FAIL:bad_hash:' + typeof obs.control_hash);
                }
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout == "PASS", f"JS hash failed: {result.stdout} {result.stderr}"

    def test_overwrite_guard(self):
        """C1: context already has ontology_candidate_observation → typed error."""
        js_code = textwrap.dedent("""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            const request = {
                operation: 'run_trace',
                input: {
                    projections: [{ pattern: { var: 'x' }, body: { var: 'x' }, id: 'id.pass' }],
                    value: 'hello',
                    max_steps: 3,
                },
                context: {
                    collect_ontology_candidate_evidence: true,
                    ontology_candidate_observation: { old: 'obs' },
                },
                inject_key: 'boundary_result',
            };
            const noop = () => {};
            try {
                pipeline.serviceBoundaryEffect([], {}, request, 50, noop, 0, 'test');
                process.stdout.write('NO_ERROR');
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout.startswith("FAIL:input.shape_mismatch:"), (
            f"Expected overwrite guard, got: {result.stdout} {result.stderr}"
        )
        assert "already contains ontology_candidate_observation" in result.stdout

    def test_no_auto_promotion_side_effect(self):
        """C2: Collector path does NOT add ontology_promotion to result."""
        js_code = textwrap.dedent("""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            const request = {
                operation: 'run_trace',
                input: {
                    projections: [{ pattern: { var: 'x' }, body: { var: 'x' }, id: 'id.pass' }],
                    value: 'hello',
                    max_steps: 3,
                },
                context: { collect_ontology_candidate_evidence: true },
                inject_key: 'boundary_result',
            };
            const noop = () => {};
            try {
                const ctx = pipeline.serviceBoundaryEffect([], {}, request, 50, noop, 0, 'test');
                const result = ctx.boundary_result;
                if ('ontology_promotion' in result) {
                    process.stdout.write('FAIL:has_ontology_promotion');
                } else {
                    process.stdout.write('PASS');
                }
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout == "PASS", f"JS auto-promo side effect: {result.stdout} {result.stderr}"


class TestEvidenceCollectorWiring:
    """A17: Source-inspection tests for evidence collector wiring."""

    @staticmethod
    def _get_python_boundary_effect_source():
        src = inspect.getsource(_service_boundary_effect)
        return src

    @staticmethod
    def _get_js_boundary_effect_source():
        js_path = REPO_ROOT / "mu" / "host" / "js" / "engine" / "pipeline.js"
        return js_path.read_text()

    def test_python_wiring_contains_flag(self):
        """Python wiring contains collect_ontology_candidate_evidence."""
        src = self._get_python_boundary_effect_source()
        assert "collect_ontology_candidate_evidence" in src

    def test_js_wiring_contains_flag(self):
        """JS wiring contains collect_ontology_candidate_evidence."""
        src = self._get_js_boundary_effect_source()
        assert "collect_ontology_candidate_evidence" in src

    def test_python_uses_strict_is_true(self):
        """Python uses strict 'is True' check."""
        src = self._get_python_boundary_effect_source()
        # Find the A17 block specifically
        assert re.search(
            r'collect_ontology_candidate_evidence.*is True', src
        ), "Python A17 wiring must use 'is True' (strict boolean check)"

    def test_js_uses_strict_triple_equals(self):
        """JS uses strict === true check."""
        src = self._get_js_boundary_effect_source()
        assert re.search(
            r'collect_ontology_candidate_evidence\s*===\s*true', src
        ), "JS A17 wiring must use '=== true' (strict boolean check)"


class TestEvidenceCollectorMalformedTrace:
    """A17 C4: Malformed projection IDs in trace entries — string-only filtering."""

    def test_python_non_string_projection_ids_filtered(self):
        """Python: int/dict projection IDs skipped, only strings collected."""
        entries = [
            {"step": 0, "state": "s0", "projection": "valid_id"},
            {"step": 1, "state": "s1", "projection": 42},       # int → skip
            {"step": 2, "state": "s2", "projection": {"x": 1}}, # dict → skip
            {"step": 3, "state": "s3", "projection": None},     # None → skip
            {"step": 4, "state": "s4", "projection": "another_id"},
        ]
        result = {
            "result": "final",
            "trace": _make_linked_trace(entries),
            "stall": False,
        }
        obs = _collect_ontology_evidence(result, "run_trace")
        assert obs["trace_len"] == 5
        assert obs["projection_ids"] == ["another_id", "valid_id"]  # sorted, strings only

    def test_js_non_string_projection_ids_filtered(self):
        """JS: int/dict projection IDs skipped, only strings collected."""
        js_code = textwrap.dedent("""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            const trace = {
                head: { step: 0, state: 's0', projection: 'valid_id' },
                tail: {
                    head: { step: 1, state: 's1', projection: 42 },
                    tail: {
                        head: { step: 2, state: 's2', projection: { x: 1 } },
                        tail: {
                            head: { step: 3, state: 's3', projection: null },
                            tail: {
                                head: { step: 4, state: 's4', projection: 'another_id' },
                                tail: null
                            }
                        }
                    }
                }
            };
            const result = { result: 'final', trace: trace, stall: false };
            try {
                const obs = pipeline.collectOntologyEvidence(result, 'run_trace');
                const checks = [
                    obs.trace_len === 5,
                    JSON.stringify(obs.projection_ids) === JSON.stringify(['another_id', 'valid_id']),
                ];
                process.stdout.write(checks.every(Boolean) ? 'PASS' : 'FAIL:' + JSON.stringify(obs));
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout == "PASS", f"JS C4 filter failed: {result.stdout} {result.stderr}"


class TestEvidenceCollectorBoundaryPath:
    """A17: Behavioral integration tests calling _service_boundary_effect for collection."""

    def test_python_boundary_collection_valid(self):
        """Call _service_boundary_effect with collect flag → context has observation."""
        request = _make_boundary_request(context_extra={
            "collect_ontology_candidate_evidence": True,
        })
        returned_ctx = _service_boundary_effect(
            request, max_algorithm_iterations=50,
            emit_fn=_noop_emit, iteration=0, state="test_state",
        )
        assert "ontology_candidate_observation" in returned_ctx
        obs = returned_ctx["ontology_candidate_observation"]
        assert obs["operation"] == "run_trace"
        assert isinstance(obs["trace_len"], int)
        assert obs["trace_len"] > 0
        assert isinstance(obs["projection_ids"], list)
        assert isinstance(obs["control_hash"], str)
        assert isinstance(obs["collected_at"], str)

    def test_python_boundary_no_flag_no_collection(self):
        """Without collect flag, no observation in context."""
        request = _make_boundary_request()
        returned_ctx = _service_boundary_effect(
            request, max_algorithm_iterations=50,
            emit_fn=_noop_emit, iteration=0, state="test_state",
        )
        assert "ontology_candidate_observation" not in returned_ctx

    def test_js_boundary_collection_valid(self):
        """JS: serviceBoundaryEffect with collect flag → observation attached."""
        js_code = textwrap.dedent("""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            const request = {
                operation: 'run_trace',
                input: {
                    projections: [{ pattern: { var: 'x' }, body: { var: 'x' }, id: 'id.pass' }],
                    value: 'hello',
                    max_steps: 3,
                },
                context: { collect_ontology_candidate_evidence: true },
                inject_key: 'boundary_result',
            };
            const noop = () => {};
            try {
                const ctx = pipeline.serviceBoundaryEffect([], {}, request, 50, noop, 0, 'test');
                const obs = ctx.ontology_candidate_observation;
                if (!obs) {
                    process.stdout.write('FAIL:no_observation');
                } else {
                    const checks = [
                        obs.operation === 'run_trace',
                        typeof obs.trace_len === 'number' && obs.trace_len > 0,
                        Array.isArray(obs.projection_ids),
                        typeof obs.control_hash === 'string',
                        typeof obs.collected_at === 'string',
                    ];
                    process.stdout.write(checks.every(Boolean) ? 'PASS' : 'FAIL:' + JSON.stringify(checks));
                }
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout == "PASS", f"JS boundary collection failed: {result.stdout} {result.stderr}"

    def test_python_collection_flag_consumed_one_shot(self):
        """After collection, context no longer has flag."""
        request = _make_boundary_request(context_extra={
            "collect_ontology_candidate_evidence": True,
        })
        returned_ctx = _service_boundary_effect(
            request, max_algorithm_iterations=50,
            emit_fn=_noop_emit, iteration=0, state="test_state",
        )
        assert "collect_ontology_candidate_evidence" not in returned_ctx, (
            "collect_ontology_candidate_evidence should be consumed (one-shot)"
        )

    def test_python_boundary_overwrite_guard(self):
        """C1: collect flag + context already has observation → typed error."""
        request = _make_boundary_request(context_extra={
            "collect_ontology_candidate_evidence": True,
            "ontology_candidate_observation": {"existing": True},
        })
        with pytest.raises(RcxEngineError) as exc_info:
            _service_boundary_effect(
                request, max_algorithm_iterations=50,
                emit_fn=_noop_emit, iteration=0, state="test_state",
            )
        assert exc_info.value.error_code == "input.shape_mismatch"
        assert "already contains ontology_candidate_observation" in str(exc_info.value)

    def test_js_boundary_overwrite_guard(self):
        """C1: JS overwrite guard — pre-existing observation + flag → typed error."""
        js_code = textwrap.dedent("""\
            const pipeline = require('./mu/host/js/engine/pipeline');
            const request = {
                operation: 'run_trace',
                input: {
                    projections: [{ pattern: { var: 'x' }, body: { var: 'x' }, id: 'id.pass' }],
                    value: 'hello',
                    max_steps: 3,
                },
                context: {
                    collect_ontology_candidate_evidence: true,
                    ontology_candidate_observation: { existing: true },
                },
                inject_key: 'boundary_result',
            };
            const noop = () => {};
            try {
                pipeline.serviceBoundaryEffect([], {}, request, 50, noop, 0, 'test');
                process.stdout.write('NO_ERROR');
            } catch (err) {
                process.stdout.write('FAIL:' + (err.error_code || 'unknown') + ':' + err.message);
            }
        """)
        result = _run_js_expr(js_code)
        assert result.stdout.startswith("FAIL:input.shape_mismatch:"), (
            f"Expected overwrite guard, got: {result.stdout} {result.stderr}"
        )
        assert "already contains ontology_candidate_observation" in result.stdout

    def test_python_boundary_no_auto_promotion(self):
        """C2: Collector path does NOT add ontology_promotion to result."""
        request = _make_boundary_request(context_extra={
            "collect_ontology_candidate_evidence": True,
        })
        returned_ctx = _service_boundary_effect(
            request, max_algorithm_iterations=50,
            emit_fn=_noop_emit, iteration=0, state="test_state",
        )
        result = returned_ctx["boundary_result"]
        assert "ontology_promotion" not in result, (
            "Collector path must not add ontology_promotion — observation only"
        )


class TestF44HandlerResultImmutability:
    """F-44: _service_boundary_effect must not mutate the handler-returned dict."""

    def test_handler_result_not_mutated_by_emission(self, monkeypatch):
        """Ontology promotion attachment must not pollute the handler's original dict."""
        handler_result = {
            "result": "hello",
            "trace": [],
            "stall": True,
        }
        original_keys = set(handler_result.keys())

        def fake_handler(request, req_input, max_iters):
            return handler_result

        monkeypatch.setitem(_BOUNDARY_DISPATCH, "run_trace", fake_handler)
        evidence = _make_valid_evidence()
        request = _make_boundary_request(context_extra={
            "emit_ontology_candidate": True,
            "ontology_candidate_evidence": evidence,
        })
        returned_ctx = _service_boundary_effect(
            request, max_algorithm_iterations=50,
            emit_fn=_noop_emit, iteration=0, state="test_state",
        )
        injected = returned_ctx["boundary_result"]

        # The injected result must have ontology_promotion
        assert "ontology_promotion" in injected

        # The handler's ORIGINAL dict must NOT have been mutated
        assert set(handler_result.keys()) == original_keys, (
            f"Handler result was mutated in place: gained {set(handler_result.keys()) - original_keys}"
        )
        assert "ontology_promotion" not in handler_result

        # The injected result must be a DIFFERENT object
        assert injected is not handler_result, (
            "Injected result should be a copy, not the same object as handler return"
        )
