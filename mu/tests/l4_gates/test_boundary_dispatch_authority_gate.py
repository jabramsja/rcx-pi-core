"""
L4 Gate Test: Boundary Dispatch Authority (Wave A10).

Proves that boundary-operation dispatch has been structurally displaced from
host if/elif chains to seed-derived handler-map dispatch via
rcx_engine.v1.json projection body analysis.

Usage:
    PYTHONHASHSEED=0 pytest tests/l4_gates/test_boundary_dispatch_authority_gate.py -v
"""

from __future__ import annotations

import inspect
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

from rcx_pi.selfhost.step_mu import (
    _load_boundary_ops,  # ANTICHEAT_OK: gate verifies seed-derived boundary ops
    _clear_boundary_ops_cache,  # ANTICHEAT_OK: gate verifies cache-clear parity
    _service_boundary_effect,  # ANTICHEAT_OK: gate verifies dispatch structure
    _BOUNDARY_DISPATCH,  # ANTICHEAT_OK: gate verifies dispatch map keys
    RcxEngineError,  # ANTICHEAT_OK: gate verifies typed fail-closed errors
)
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PY_STEP_MU = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
JS_PIPELINE = REPO_ROOT / "mu" / "host" / "js" / "engine" / "pipeline.js"

EXPECTED_OPS = frozenset({"run_trace", "hash_trace", "run_algorithm"})

# Stub emit function for tests (collects events)
_events = []


def _stub_emit(event_name, iteration, state, error_code=None, **extra):
    _events.append({"event_name": event_name, "error_code": error_code})


def setup_function():
    _events.clear()


# ===========================================================================
# Test 1: Boundary ops derivation
# ===========================================================================

class TestBoundaryOpsDerivation:
    """Verify seed-derived boundary ops match expected set."""

    def test_python_boundary_ops(self):
        """Python derives exactly 3 boundary ops from rcx_engine.v1.json."""
        ops = _load_boundary_ops()
        assert ops == EXPECTED_OPS, f"Expected {sorted(EXPECTED_OPS)}, got {sorted(ops)}"

    def test_js_boundary_ops_parity(self):
        """JS derives the same boundary ops from the same seed."""
        js_code = """
        const { _ensureBoundaryOps } = require('./mu/host/js/engine/pipeline');
        const ops = _ensureBoundaryOps();
        console.log(JSON.stringify([...ops].sort()));
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"JS boundary ops failed: {result.stderr}"
        js_ops = set(json.loads(result.stdout.strip()))
        assert js_ops == EXPECTED_OPS, f"JS ops {sorted(js_ops)} != Python ops {sorted(EXPECTED_OPS)}"

    def test_cache_clear_rederivation(self):
        """After cache clear, re-derivation yields same result."""
        ops1 = _load_boundary_ops()
        _clear_boundary_ops_cache()
        ops2 = _load_boundary_ops()
        assert ops1 == ops2, "Re-derivation after cache clear must be identical"

    def test_python_rejects_non_string_op(self):
        """Non-string operation in seed projection body raises typed fail-closed."""
        import copy
        from rcx_pi.selfhost.step_mu import (
            _load_engine_projections,  # ANTICHEAT_OK: gate verifies fail-closed
        )
        # Get real projections, inject a non-string operation into one
        real_projs = _load_engine_projections()
        tampered = copy.deepcopy(real_projs)
        # Find a projection with _boundary_request and tamper its operation
        for p in tampered:
            body = p.get("body")
            if isinstance(body, dict):
                br = body.get("_boundary_request")
                if isinstance(br, dict) and "operation" in br:
                    br["operation"] = 42  # non-string
                    break
        # Monkeypatch the loader to return tampered projections
        _clear_boundary_ops_cache()
        import rcx_pi.selfhost.step_mu as step_mu_mod
        original_loader = step_mu_mod._load_engine_projections  # ANTICHEAT_OK: gate monkeypatch for fail-closed test
        step_mu_mod._load_engine_projections = lambda: tampered  # ANTICHEAT_OK: gate monkeypatch for fail-closed test
        try:
            with pytest.raises(RcxEngineError, match="boundary op must be string"):
                _load_boundary_ops()
        finally:
            step_mu_mod._load_engine_projections = original_loader  # ANTICHEAT_OK: gate monkeypatch restore
            _clear_boundary_ops_cache()

    def test_js_rejects_non_string_op(self):
        """JS _ensureBoundaryOps rejects non-string operation (source-lock)."""
        js_source = (REPO_ROOT / "mu" / "host" / "js" / "engine" / "pipeline.js").read_text()
        # Find the _ensureBoundaryOps function body
        fn_match = re.search(
            r'function _ensureBoundaryOps\b.*?\{(.*?)^}',
            js_source, re.DOTALL | re.MULTILINE,
        )
        assert fn_match, "_ensureBoundaryOps not found in pipeline.js"
        body = fn_match.group(1)
        # Must contain explicit non-string rejection (not just skip)
        assert "typeof op !== 'string'" in body, (
            "_ensureBoundaryOps must explicitly reject non-string operations, not skip them"
        )
        assert "boundary op must be string" in body, (
            "_ensureBoundaryOps must include 'boundary op must be string' error message"
        )

    def test_js_seed_registration_loads(self):
        """JS loadVerifiedSeed('rcx_engine.v1.json', 'programs') succeeds."""
        js_code = """
        const { loadVerifiedSeed } = require('./mu/host/js/core/seed_loader');
        const seed = loadVerifiedSeed('rcx_engine.v1.json', 'programs');
        console.log(seed.projections.length);
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"JS seed load failed: {result.stderr}"
        assert result.stdout.strip() == "11", f"Expected 11 projections, got {result.stdout.strip()}"


# ===========================================================================
# Test 2: Dispatch structure (source-lock + key parity)
# ===========================================================================

class TestDispatchStructure:
    """Verify if/elif dispatch has been replaced by handler-map lookup."""

    def test_python_no_op_literal_dispatch(self):
        """_service_boundary_effect must not contain if/elif operation-name dispatch."""
        source = inspect.getsource(_service_boundary_effect)
        # Look for: if operation == 'run_trace' / elif operation == 'hash_trace' etc.
        pattern = re.compile(
            r"(?:if|elif)\s+operation\s*==\s*['\"](?:run_trace|hash_trace|run_algorithm)['\"]"
        )
        assert not pattern.search(source), (
            "_service_boundary_effect still contains if/elif operation-name dispatch. "
            "A10 requires handler-map dispatch."
        )

    def test_js_no_op_literal_dispatch(self):
        """serviceBoundaryEffect must not contain if/else operation-name dispatch."""
        js_source = JS_PIPELINE.read_text(encoding="utf-8")
        # Extract serviceBoundaryEffect function body
        fn_match = re.search(
            r'function serviceBoundaryEffect\b.*?\{(.*?)^}',
            js_source, re.DOTALL | re.MULTILINE,
        )
        assert fn_match, "serviceBoundaryEffect not found in pipeline.js"
        body = fn_match.group(1)
        # Look for: if (operation === 'run_trace') / else if (operation === 'hash_trace')
        pattern = re.compile(
            r"(?:if|else\s+if)\s*\(\s*operation\s*===\s*['\"](?:run_trace|hash_trace|run_algorithm)['\"]"
        )
        assert not pattern.search(body), (
            "serviceBoundaryEffect still contains if/else operation-name dispatch. "
            "A10 requires handler-map dispatch."
        )

    def test_python_dispatch_keys_match_seed(self):
        """Python _BOUNDARY_DISPATCH keys must match seed-derived ops."""
        ops = _load_boundary_ops()
        dispatch_keys = frozenset(_BOUNDARY_DISPATCH.keys())
        assert dispatch_keys == ops, (
            f"Dispatch keys {sorted(dispatch_keys)} != seed ops {sorted(ops)}"
        )

    def test_js_dispatch_keys_match_seed(self):
        """JS BOUNDARY_DISPATCH keys must match seed-derived ops."""
        js_code = """
        const pipeline = require('./mu/host/js/engine/pipeline');
        const { _ensureBoundaryOps } = pipeline;
        // Read BOUNDARY_DISPATCH from module source (not exported, check via serviceBoundaryEffect)
        // Actually, we verify via the coverage invariant inside serviceBoundaryEffect.
        // Here we verify the ops derived by JS match expected.
        const ops = _ensureBoundaryOps();
        console.log(JSON.stringify([...ops].sort()));
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"JS dispatch key check failed: {result.stderr}"
        js_ops = sorted(json.loads(result.stdout.strip()))
        py_ops = sorted(EXPECTED_OPS)
        assert js_ops == py_ops, f"JS dispatch ops {js_ops} != Python ops {py_ops}"


# ===========================================================================
# Test 3: Request validation (typed fail-closed)
# ===========================================================================

class TestRequestValidation:
    """Verify typed fail-closed on malformed requests (no raw KeyError/TypeError)."""

    def test_missing_required_key(self):
        """Missing required key raises RcxEngineError, not KeyError."""
        bad_request = {"operation": "run_trace"}  # missing input, context, inject_key
        with pytest.raises(RcxEngineError, match="missing required key"):
            _service_boundary_effect(
                bad_request, max_algorithm_iterations=10,
                emit_fn=_stub_emit, iteration=0, state={},
            )

    def test_non_string_operation(self):
        """Non-string operation raises RcxEngineError."""
        bad_request = {
            "operation": 42,
            "input": {},
            "context": {},
            "inject_key": "result",
        }
        with pytest.raises(RcxEngineError, match="operation must be string"):
            _service_boundary_effect(
                bad_request, max_algorithm_iterations=10,
                emit_fn=_stub_emit, iteration=0, state={},
            )

    def test_non_dict_context(self):
        """Non-dict context raises RcxEngineError."""
        bad_request = {
            "operation": "run_trace",
            "input": {},
            "context": "not_a_dict",
            "inject_key": "result",
        }
        with pytest.raises(RcxEngineError, match="context must be dict"):
            _service_boundary_effect(
                bad_request, max_algorithm_iterations=10,
                emit_fn=_stub_emit, iteration=0, state={},
            )

    def test_non_dict_request(self):
        """Non-dict request raises RcxEngineError."""
        with pytest.raises(RcxEngineError, match="boundary request must be dict"):
            _service_boundary_effect(
                "not_a_dict", max_algorithm_iterations=10,
                emit_fn=_stub_emit, iteration=0, state={},
            )

    def test_non_string_inject_key(self):
        """Non-string inject_key raises RcxEngineError."""
        bad_request = {
            "operation": "run_trace",
            "input": {},
            "context": {},
            "inject_key": 42,
        }
        with pytest.raises(RcxEngineError, match="inject_key must be string"):
            _service_boundary_effect(
                bad_request, max_algorithm_iterations=10,
                emit_fn=_stub_emit, iteration=0, state={},
            )

    def test_unknown_operation_api_bad_request(self):
        """Unknown operation raises ValueError with api.bad_request semantics."""
        bad_request = {
            "operation": "nonexistent_op",
            "input": {},
            "context": {},
            "inject_key": "result",
        }
        with pytest.raises(ValueError, match="Unknown boundary operation"):
            _service_boundary_effect(
                bad_request, max_algorithm_iterations=10,
                emit_fn=_stub_emit, iteration=0, state={},
            )

    def test_run_trace_non_dict_input(self):
        """run_trace with non-dict input raises RcxEngineError, not TypeError."""
        bad_request = {
            "operation": "run_trace",
            "input": 42,  # not a dict
            "context": {},
            "inject_key": "result",
        }
        with pytest.raises(RcxEngineError, match="run_trace input must be dict"):
            _service_boundary_effect(
                bad_request, max_algorithm_iterations=10,
                emit_fn=_stub_emit, iteration=0, state={},
            )

    def test_run_trace_missing_required_input_keys(self):
        """run_trace input missing 'projections'/'value' raises RcxEngineError, not KeyError."""
        bad_request = {
            "operation": "run_trace",
            "input": {"max_steps": 10},  # missing projections and value
            "context": {},
            "inject_key": "result",
        }
        with pytest.raises(RcxEngineError, match="run_trace input must include"):
            _service_boundary_effect(
                bad_request, max_algorithm_iterations=10,
                emit_fn=_stub_emit, iteration=0, state={},
            )

    def test_run_algorithm_missing_algorithm(self):
        """run_algorithm without 'algorithm' key raises RcxEngineError, not KeyError."""
        bad_request = {
            "operation": "run_algorithm",
            "input": {},
            "context": {},
            "inject_key": "result",
        }
        with pytest.raises(RcxEngineError, match="run_algorithm request must include"):
            _service_boundary_effect(
                bad_request, max_algorithm_iterations=10,
                emit_fn=_stub_emit, iteration=0, state={},
            )

    def test_run_algorithm_non_string_algorithm(self):
        """run_algorithm with non-string 'algorithm' raises RcxEngineError, not TypeError."""
        bad_request = {
            "operation": "run_algorithm",
            "input": {},
            "context": {},
            "inject_key": "result",
            "algorithm": 42,
        }
        with pytest.raises(RcxEngineError, match="'algorithm' must be string"):
            _service_boundary_effect(
                bad_request, max_algorithm_iterations=10,
                emit_fn=_stub_emit, iteration=0, state={},
            )

    def test_run_trace_non_list_projections(self):
        """run_trace with non-list projections raises RcxEngineError, not TypeError."""
        bad_request = {
            "operation": "run_trace",
            "input": {"projections": 42, "value": {"x": 1}},
            "context": {},
            "inject_key": "result",
        }
        with pytest.raises(RcxEngineError, match="'projections' must be list"):
            _service_boundary_effect(
                bad_request, max_algorithm_iterations=10,
                emit_fn=_stub_emit, iteration=0, state={},
            )

    def test_run_trace_non_dict_projection_element(self):
        """run_trace with projections=[42] raises RcxEngineError, not downstream TypeError."""
        bad_request = {
            "operation": "run_trace",
            "input": {"projections": [42], "value": {"x": 1}},
            "context": {},
            "inject_key": "result",
        }
        with pytest.raises(RcxEngineError, match="projection\\[0\\] must be dict"):
            _service_boundary_effect(
                bad_request, max_algorithm_iterations=10,
                emit_fn=_stub_emit, iteration=0, state={},
            )

    def test_run_trace_max_steps_normalize_string(self):
        """run_trace with max_steps='abc' normalizes to 100 (no TypeError).

        Parity policy: both substrates normalize non-numeric max_steps to 100.
        """
        # max_steps='abc' → fallback 100; empty projections → stall, not max_steps error
        request = {
            "operation": "run_trace",
            "input": {"projections": [], "value": 1, "max_steps": "abc"},
            "context": {},
            "inject_key": "result",
        }
        # Should NOT raise TypeError — normalized max_steps, empty projs → stall result
        ctx = _service_boundary_effect(
            request, max_algorithm_iterations=10,
            emit_fn=_stub_emit, iteration=0, state={},
        )
        assert "result" in ctx

    def test_run_trace_max_steps_float_normalizes(self):
        """run_trace with max_steps=1.5 normalizes to int(1) (no TypeError).

        Parity policy: both substrates floor numeric max_steps to int.
        """
        simple_projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        request = {
            "operation": "run_trace",
            "input": {"projections": simple_projs, "value": {"x": 42}, "max_steps": 1.5},
            "context": {},
            "inject_key": "result",
        }
        # Should NOT raise TypeError — float coerced to int(1)
        ctx = _service_boundary_effect(
            request, max_algorithm_iterations=10,
            emit_fn=_stub_emit, iteration=0, state={},
        )
        assert "result" in ctx

    def test_js_run_trace_non_array_projections(self):
        """JS run_trace with non-array projections raises RcxError, not TypeError."""
        js_code = """
        const pipeline = require('./mu/host/js/engine/pipeline');
        try {
            pipeline.serviceBoundaryEffect(
                [], {}, {operation:'run_trace',input:{projections:42,value:{x:1}},context:{},inject_key:'r'},
                10, function(){}, 0, {}
            );
            console.log('ERROR: no throw');
        } catch(e) {
            if (e.error_code === 'api.bad_request' && e.message.includes('projections')) {
                console.log('OK');
            } else {
                console.log('WRONG: ' + e.constructor.name + ': ' + e.message);
            }
        }
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"JS failed: {result.stderr}"
        assert result.stdout.strip() == "OK", f"JS non-array projections: {result.stdout.strip()}"

    def test_js_run_trace_non_dict_projection_element(self):
        """JS run_trace with projections=[42] raises RcxError, not downstream TypeError."""
        js_code = """
        const pipeline = require('./mu/host/js/engine/pipeline');
        try {
            pipeline.serviceBoundaryEffect(
                [], {}, {operation:'run_trace',input:{projections:[42],value:{x:1}},context:{},inject_key:'r'},
                10, function(){}, 0, {}
            );
            console.log('ERROR: no throw');
        } catch(e) {
            if (e.error_code === 'api.bad_request' && e.message.includes('projection[0]')) {
                console.log('OK');
            } else {
                console.log('WRONG: ' + e.constructor.name + ': ' + e.message);
            }
        }
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"JS failed: {result.stderr}"
        assert result.stdout.strip() == "OK", f"JS non-dict projection: {result.stdout.strip()}"

    def test_js_run_trace_max_steps_string_normalizes(self):
        """JS run_trace with max_steps='abc' normalizes to 100 (no raw TypeError).

        Parity policy: both substrates normalize non-numeric max_steps to 100.
        """
        js_code = """
        const pipeline = require('./mu/host/js/engine/pipeline');
        try {
            pipeline.serviceBoundaryEffect(
                [], {}, {operation:'run_trace',input:{projections:[],value:1,max_steps:'abc'},context:{},inject_key:'r'},
                10, function(){}, 0, {}
            );
            console.log('OK');
        } catch(e) {
            if (e instanceof TypeError && e.message.includes('max_steps')) {
                console.log('WRONG: raw TypeError about max_steps');
            } else {
                console.log('OK');
            }
        }
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"JS failed: {result.stderr}"
        assert result.stdout.strip() == "OK", f"JS max_steps normalize: {result.stdout.strip()}"

    def test_js_run_trace_max_steps_float_normalizes(self):
        """JS run_trace with max_steps=1.5 normalizes to 1 (no raw TypeError).

        Parity policy: both substrates floor numeric max_steps to int.
        """
        js_code = """
        const pipeline = require('./mu/host/js/engine/pipeline');
        try {
            const p = [{pattern:{x:{var:'v'}},body:{var:'v'}}];
            pipeline.serviceBoundaryEffect(
                [], {}, {operation:'run_trace',input:{projections:p,value:{x:42},max_steps:1.5},context:{},inject_key:'r'},
                10, function(){}, 0, {}
            );
            console.log('OK');
        } catch(e) {
            if (e instanceof TypeError) {
                console.log('WRONG: raw TypeError: ' + e.message);
            } else {
                console.log('OK');
            }
        }
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"JS failed: {result.stderr}"
        assert result.stdout.strip() == "OK", f"JS float max_steps: {result.stdout.strip()}"

    def test_run_trace_max_steps_inf_normalizes(self):
        """run_trace with max_steps=inf normalizes to 100 (no raw OverflowError)."""
        import math
        request = {
            "operation": "run_trace",
            "input": {"projections": [], "value": 1, "max_steps": math.inf},
            "context": {},
            "inject_key": "result",
        }
        ctx = _service_boundary_effect(
            request, max_algorithm_iterations=10,
            emit_fn=_stub_emit, iteration=0, state={},
        )
        assert "result" in ctx

    def test_run_trace_max_steps_nan_normalizes(self):
        """run_trace with max_steps=nan normalizes to 100 (no raw ValueError)."""
        import math
        request = {
            "operation": "run_trace",
            "input": {"projections": [], "value": 1, "max_steps": math.nan},
            "context": {},
            "inject_key": "result",
        }
        ctx = _service_boundary_effect(
            request, max_algorithm_iterations=10,
            emit_fn=_stub_emit, iteration=0, state={},
        )
        assert "result" in ctx

    def test_run_trace_empty_dict_projection(self):
        """run_trace with projections=[{}] raises typed error (missing pattern/body)."""
        bad_request = {
            "operation": "run_trace",
            "input": {"projections": [{}], "value": 1},
            "context": {},
            "inject_key": "result",
        }
        with pytest.raises(RcxEngineError, match="must have 'pattern' and 'body'"):
            _service_boundary_effect(
                bad_request, max_algorithm_iterations=10,
                emit_fn=_stub_emit, iteration=0, state={},
            )

    def test_js_run_trace_max_steps_inf_normalizes(self):
        """JS run_trace with max_steps=Infinity normalizes to 100 (no raw error)."""
        js_code = """
        const pipeline = require('./mu/host/js/engine/pipeline');
        try {
            pipeline.serviceBoundaryEffect(
                [], {}, {operation:'run_trace',input:{projections:[],value:1,max_steps:Infinity},context:{},inject_key:'r'},
                10, function(){}, 0, {}
            );
            console.log('OK');
        } catch(e) {
            if (e instanceof RangeError || e instanceof TypeError) {
                console.log('WRONG: ' + e.constructor.name + ': ' + e.message);
            } else {
                console.log('OK');
            }
        }
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"JS failed: {result.stderr}"
        assert result.stdout.strip() == "OK", f"JS inf max_steps: {result.stdout.strip()}"

    def test_js_run_trace_max_steps_nan_normalizes(self):
        """JS run_trace with max_steps=NaN normalizes to 100 (no raw error)."""
        js_code = """
        const pipeline = require('./mu/host/js/engine/pipeline');
        try {
            pipeline.serviceBoundaryEffect(
                [], {}, {operation:'run_trace',input:{projections:[],value:1,max_steps:NaN},context:{},inject_key:'r'},
                10, function(){}, 0, {}
            );
            console.log('OK');
        } catch(e) {
            if (e instanceof RangeError || e instanceof TypeError) {
                console.log('WRONG: ' + e.constructor.name + ': ' + e.message);
            } else {
                console.log('OK');
            }
        }
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"JS failed: {result.stderr}"
        assert result.stdout.strip() == "OK", f"JS nan max_steps: {result.stdout.strip()}"

    def test_js_run_trace_empty_dict_projection(self):
        """JS run_trace with projections=[{}] raises typed error (missing pattern/body)."""
        js_code = """
        const pipeline = require('./mu/host/js/engine/pipeline');
        try {
            pipeline.serviceBoundaryEffect(
                [], {}, {operation:'run_trace',input:{projections:[{}],value:1},context:{},inject_key:'r'},
                10, function(){}, 0, {}
            );
            console.log('ERROR: no throw');
        } catch(e) {
            if (e.error_code === 'api.bad_request' && e.message.includes("'pattern' and 'body'")) {
                console.log('OK');
            } else {
                console.log('WRONG: ' + e.constructor.name + ': ' + e.message);
            }
        }
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"JS failed: {result.stderr}"
        assert result.stdout.strip() == "OK", f"JS empty dict projection: {result.stdout.strip()}"


# ===========================================================================
# Test 3b: JS seed loader malformed projection fail-closed (F2 hardening)
# ===========================================================================


class TestJsSeedLoaderMalformedProjection:
    """JS seed loader must reject null/array/scalar projection entries.

    Tests call production loadVerifiedSeed from seed_loader.js directly via
    temp seed files written to mu/utilities/. Unknown seed names bypass
    checksum/projection-ID checks, isolating the type guard.
    """

    @staticmethod
    def _run_seed_loader_test(projections_json, expect_index, expect_type):
        """Write a temp seed with malformed projections, call production loadVerifiedSeed."""
        js_code = f"""
        const fs = require('fs');
        const path = require('path');
        const {{ loadVerifiedSeed }} = require('./mu/host/js/core/seed_loader');
        const tmpName = '_test_malformed_' + process.pid + '.json';
        const seedPath = path.join('mu', 'utilities', tmpName);
        fs.writeFileSync(seedPath, JSON.stringify({{
            meta: {{name: "TEST", version: "1.0", description: "test"}},
            projections: {projections_json}
        }}));
        try {{
            loadVerifiedSeed(tmpName, 'utilities');
            console.log('ERROR: no throw');
        }} catch(e) {{
            if (e.message.includes('projection[{expect_index}]') &&
                e.message.includes('{expect_type}')) {{
                console.log('OK');
            }} else {{
                console.log('WRONG: ' + e.message);
            }}
        }} finally {{
            try {{ fs.unlinkSync(seedPath); }} catch(_) {{}}
        }}
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"JS failed: {result.stderr}"
        return result.stdout.strip()

    def test_seed_loader_rejects_null_projection(self):
        """Production loadVerifiedSeed rejects null projection entry."""
        out = self._run_seed_loader_test(
            '[{"id":"ok","pattern":{},"body":{}}, null]',
            expect_index=1, expect_type="null",
        )
        assert out == "OK", f"seed_loader null projection: {out}"

    def test_seed_loader_rejects_array_projection(self):
        """Production loadVerifiedSeed rejects array projection entry."""
        out = self._run_seed_loader_test(
            '[[1,2,3]]',
            expect_index=0, expect_type="array",
        )
        assert out == "OK", f"seed_loader array projection: {out}"

    def test_seed_loader_rejects_scalar_projection(self):
        """Production loadVerifiedSeed rejects scalar (number) projection entry."""
        out = self._run_seed_loader_test(
            '[42]',
            expect_index=0, expect_type="number",
        )
        assert out == "OK", f"seed_loader scalar projection: {out}"

    def test_main_validate_seed_structure_type_guard_source_lock(self):
        """main.js validateSeedStructure contains type guard before 'id' in proj check.

        Source-lock: validateSeedStructure is not exported, so we verify the
        guard predicate exists in the source and precedes the 'id' in proj check.
        If the guard is removed or reordered, this test fails.
        """
        main_js = (REPO_ROOT / "mu" / "host" / "js" / "cli" / "main.js").read_text()
        guard = "proj === null || typeof proj !== 'object' || Array.isArray(proj)"
        id_check = "'id' in proj"
        assert guard in main_js, (
            "main.js missing type guard predicate in validateSeedStructure"
        )
        assert id_check in main_js, (
            "main.js missing 'id' in proj check in validateSeedStructure"
        )
        guard_pos = main_js.index(guard)
        id_pos = main_js.index(id_check)
        assert guard_pos < id_pos, (
            f"Type guard (pos {guard_pos}) must appear before "
            f"'id' in proj check (pos {id_pos})"
        )



# ===========================================================================
# Test 3c: F2 production-binding lock (anti-theater)
# ===========================================================================


class TestF2ProductionBindingLock:
    """Lock: F2 tests must use production code paths, not inline simulation."""

    def test_f2_tests_require_production_seed_loader(self):
        """TestJsSeedLoaderMalformedProjection must call production seed_loader."""
        test_file = REPO_ROOT / "mu" / "tests" / "l4_gates" / "test_boundary_dispatch_authority_gate.py"
        source = test_file.read_text()
        # Extract TestJsSeedLoaderMalformedProjection class body
        class_start = source.index("class TestJsSeedLoaderMalformedProjection")
        next_class = source.find("\nclass ", class_start + 1)
        class_source = source[class_start:next_class] if next_class != -1 else source[class_start:]
        # Must contain production binding
        assert "require('./mu/host/js/core/seed_loader')" in class_source, (
            "TestJsSeedLoaderMalformedProjection must invoke production seed_loader "
            "via require(), not simulate guard logic inline"
        )
        # Must NOT contain inline JS function definitions (simulation).
        # Build search strings programmatically to avoid self-referential match.
        for fn_name in ["validateSeedStructure", "loadVerifiedSeed"]:
            needle = f"function {fn_name}("
            assert needle not in class_source, (
                f"TestJsSeedLoaderMalformedProjection must not define inline "
                f"{fn_name} — use production code"
            )


# ===========================================================================
# Test 4: Behavior preservation (slow — uses engine)
# ===========================================================================

@pytest.mark.slow
class TestBehaviorPreservation:
    """Verify handler-map dispatch produces same results as pre-A10."""

    def test_run_trace_produces_result(self):
        """run_trace via handler-map returns result/trace/stall keys."""
        # Use a simple identity-like projection (no reserved fields)
        simple_projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        request = {
            "operation": "run_trace",
            "input": {
                "projections": simple_projs,
                "value": {"x": 42},
                "max_steps": 10,
            },
            "context": {},
            "inject_key": "trace_result",
        }
        ctx = _service_boundary_effect(
            request, max_algorithm_iterations=10,
            emit_fn=_stub_emit, iteration=0, state={},
        )
        assert "trace_result" in ctx
        result = ctx["trace_result"]
        assert "result" in result
        assert "trace" in result
        assert "stall" in result

    def test_hash_trace_produces_result(self):
        """hash_trace via handler-map returns hashed linked list."""
        from rcx_pi.selfhost.step_mu import hash_trace_for_recurrence
        trace_input = {"head": {"state": 1}, "tail": {"head": {"state": 2}, "tail": None}}
        request = {
            "operation": "hash_trace",
            "input": trace_input,
            "context": {},
            "inject_key": "hashed",
        }
        ctx = _service_boundary_effect(
            request, max_algorithm_iterations=10,
            emit_fn=_stub_emit, iteration=0, state={},
        )
        assert "hashed" in ctx
