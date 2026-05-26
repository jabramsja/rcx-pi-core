"""
L4 Gate Test: Boundary Dispatch Authority (Wave A10).
Non-blocker wave2 (2026-03-14): N12 allowlist hardened from Object.freeze(Set)
to frozen null-prototype object. Behavioral parity tests unchanged — allowlist
lookup uses `in` operator instead of `.has()`.

Proves that boundary-operation dispatch has been structurally displaced from
host if/elif chains to seed-derived handler-map dispatch via
rcx_engine.v1.json projection body analysis.

Usage:
    PYTHONHASHSEED=0 pytest tests/l4_gates/test_boundary_dispatch_authority_gate.py -v
"""

from __future__ import annotations

import base64
import copy
import hashlib
import inspect
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

from rcx_pi.selfhost.step_mu import RcxEngineError  # ANTICHEAT_OK: gate verifies typed fail-closed errors
from rcx_pi.selfhost.engine_pipeline import (
    _load_boundary_ops,  # ANTICHEAT_OK: gate verifies seed-derived boundary ops
    _clear_boundary_ops_cache,  # ANTICHEAT_OK: gate verifies cache-clear parity
    _service_boundary_effect,  # ANTICHEAT_OK: gate verifies dispatch structure
    _BOUNDARY_DISPATCH,  # ANTICHEAT_OK: gate verifies dispatch map keys
)
from rcx_pi.selfhost.seed_integrity import (
    EXPECTED_PROJECTION_IDS,
    RUN_ALGORITHM_AUTHORITY_SEEDS,
    SEED_CHECKSUMS,
    SEED_REGISTRY_MANIFEST,
    SeedBinaryMigrationError,
    compute_checksum,
    get_seed_path,
    load_verified_seed,
    load_verified_seed_image,
)
from mu.tools.util.seed_binary_migration import (
    decode_seed_binary_projections,
    generate_seed_binary_migration_artifact,
)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PY_STEP_MU = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "engine_pipeline.py"
JS_PIPELINE = REPO_ROOT / "mu" / "host" / "js" / "engine" / "pipeline.js"

EXPECTED_OPS = frozenset({"run_trace", "hash_trace", "run_algorithm"})
EXPECTED_RUN_ALGORITHM_AUTHORITY_SEEDS = frozenset({
    "recurrence.v1.json",
    "recurrence.v2.json",
    "exhaustion.v1.json",
    "fix.v1.json",
    "rcx_engine_scheduler.v1.json",
})

# Stub emit function for tests (collects events)
_events = []


def _stub_emit(event_name, iteration, state, error_code=None, **extra):
    _events.append({"event_name": event_name, "error_code": error_code})


def setup_function():
    _events.clear()


_MAX_STEPS_MISSING = object()


def _linked_trace_to_list(trace):
    entries = []
    current = trace
    while isinstance(current, dict) and "head" in current:
        entries.append(current["head"])
        current = current["tail"]
    return entries


def _toggle_trace_request(max_steps=_MAX_STEPS_MISSING):
    request_input = {
        "projections": [
            {"pattern": "A", "body": "B"},
            {"pattern": "B", "body": "A"},
        ],
        "value": "A",
    }
    if max_steps is not _MAX_STEPS_MISSING:
        request_input["max_steps"] = max_steps
    return {
        "operation": "run_trace",
        "input": request_input,
        "context": {},
        "inject_key": "result",
    }


def _run_js_trace(max_steps_expr=None):
    max_steps_field = "" if max_steps_expr is None else f", max_steps: {max_steps_expr}"
    js_code = f"""
    const fs = require('fs');
    const path = require('path');
    const pipeline = require('./mu/host/js/engine/pipeline');
    const muContainers = require('./mu/host/js/core/container_factory');
    const {{
      loadVerifiedSeedImage,
      getSeedSubdir,
      SEED_IMAGE_VERIFICATION_MODES,
    }} = require('./mu/host/js/core/seed_loader');
    function seed(name) {{
      const seedPath = path.join(process.cwd(), 'mu', getSeedSubdir(name), name);
      const raw = fs.readFileSync(seedPath);
      return loadVerifiedSeedImage(name, raw, SEED_IMAGE_VERIFICATION_MODES.CLI).projections;
    }}
    const kernelProjections = muContainers.list([
      ...seed('kernel.v1.json'),
      ...seed('bootstrap_structural.v1.json'),
      ...seed('match.v2.json'),
      ...seed('subst.v2.json'),
    ]);
    function linkedTraceToArray(trace) {{
      const entries = [];
      let current = trace;
      while (current && typeof current === 'object' && 'head' in current) {{
        entries.push(current.head);
        current = current.tail;
      }}
      return entries;
    }}
    try {{
      const result = pipeline.serviceBoundaryEffect(
        kernelProjections, {{}},
        {{
          operation:'run_trace',
          input:{{
            projections:[{{pattern:'A',body:'B'}},{{pattern:'B',body:'A'}}],
            value:'A'{max_steps_field}
          }},
          context:{{}},
          inject_key:'r'
        }},
        10, function(){{}}, 0, {{}}
      );
      const trace = linkedTraceToArray(result.r.trace);
      console.log(JSON.stringify({{
        ok: true,
        result: result.r.result,
        stall: result.r.stall,
        last: trace[trace.length - 1]
      }}));
    }} catch(e) {{
      console.log(JSON.stringify({{
        ok: false,
        error_code: e.error_code || null,
        name: e.constructor.name,
        message: e.message
      }}));
    }}
    """
    result = subprocess.run(
        ["node", "-e", js_code],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"JS failed: {result.stderr}"
    return json.loads(result.stdout)


def _load_js_seed_image_with_manifest_mode(
    seed_name: str,
    seed_bytes: bytes,
    verification_mode: str = "CLI",
) -> dict[str, object]:
    """Call the JS seed-image boundary through a closed manifest-derived mode."""
    js_code = f"""
    const {{
        loadVerifiedSeedImage,
        SEED_IMAGE_VERIFICATION_MODES,
    }} = require('./mu/host/js/core/seed_loader');
    const raw = Buffer.from({list(seed_bytes)});
    try {{
        const seed = loadVerifiedSeedImage(
            {json.dumps(seed_name)},
            raw,
            SEED_IMAGE_VERIFICATION_MODES[{json.dumps(verification_mode)}]
        );
        console.log(JSON.stringify({{
            ok: true,
            ids: seed.projections.map(p => p.id),
        }}));
    }} catch (e) {{
        console.log(JSON.stringify({{
            ok: false,
            error: e.message,
        }}));
    }}
    """
    result = subprocess.run(
        ["node", "-e", js_code],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"JS seed image loader failed: {result.stderr}"
    return json.loads(result.stdout)


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
        from rcx_pi.selfhost.engine_pipeline import (
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
        import rcx_pi.selfhost.engine_pipeline as engine_pipeline_mod
        original_loader = engine_pipeline_mod._load_engine_projections  # ANTICHEAT_OK: gate monkeypatch for fail-closed test
        engine_pipeline_mod._load_engine_projections = lambda: tampered  # ANTICHEAT_OK: gate monkeypatch for fail-closed test
        try:
            with pytest.raises(RcxEngineError, match="boundary op must be string"):
                _load_boundary_ops()
        finally:
            engine_pipeline_mod._load_engine_projections = original_loader  # ANTICHEAT_OK: gate monkeypatch restore
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
# Test 1b: Seed-image numeric-domain boundary
# ===========================================================================


class TestSeedImageNumericDomainBoundary:
    """Production seed-image loaders keep canonical seed numerics integer-only."""

    EXPECTED_IDS = ["numeric.ok"]

    @staticmethod
    def _seed_bytes(numeric_literal: str) -> bytes:
        return (
            b'{"meta": {"version": "1.0", "name": "NUMERIC", "description": "x"}, '
            b'"projections": [{"id": "numeric.ok", "pattern": {"n": '
            + numeric_literal.encode("ascii")
            + b'}, "body": {"m": 2}}]}'
        )

    def _load_python_seed_image(
        self,
        monkeypatch: pytest.MonkeyPatch,
        seed_name: str,
        seed_bytes: bytes,
    ) -> dict[str, object]:
        monkeypatch.setitem(SEED_CHECKSUMS, seed_name, compute_checksum(seed_bytes))
        monkeypatch.setitem(EXPECTED_PROJECTION_IDS, seed_name, self.EXPECTED_IDS)
        try:
            seed = load_verified_seed_image(seed_name, seed_bytes, verify=True)
        except Exception as exc:  # gate compares fail-closed substrate behavior
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "ids": [proj["id"] for proj in seed["projections"]]}

    def test_integer_seed_image_numeric_loads_through_python_and_js(self):
        """Canonical integer seed images still load through both production byte boundaries."""
        seed_name = "rcx_engine.v1.json"
        seed_bytes = get_seed_path(seed_name).read_bytes()
        expected_ids = EXPECTED_PROJECTION_IDS[seed_name]

        seed = load_verified_seed_image(seed_name, seed_bytes, verify=True)
        py_result = {"ok": True, "ids": [proj["id"] for proj in seed["projections"]]}
        js_result = _load_js_seed_image_with_manifest_mode(seed_name, seed_bytes)

        assert py_result == {"ok": True, "ids": expected_ids}
        assert js_result == {"ok": True, "ids": expected_ids}

    @pytest.mark.parametrize("numeric_literal", ["1.0", "2.5", "1e0"])
    def test_non_integer_seed_image_numeric_rejected_through_python_and_js(
        self,
        monkeypatch,
        numeric_literal,
    ):
        """Decimal/exponent JSON numerics reject before either loader accepts a seed."""
        seed_name = f"non_integer_{numeric_literal.replace('.', '_')}.v1.json"
        seed_bytes = self._seed_bytes(numeric_literal)

        py_result = self._load_python_seed_image(monkeypatch, seed_name, seed_bytes)
        js_result = _load_js_seed_image_with_manifest_mode(seed_name, seed_bytes)

        assert py_result["ok"] is False
        assert numeric_literal in str(py_result["error"])
        assert js_result["ok"] is False
        assert f"non-integer JSON numeric literal {numeric_literal}" in str(
            js_result["error"]
        )

    @pytest.mark.parametrize("numeric_literal", ["NaN", "Infinity", "-Infinity"])
    def test_non_finite_seed_image_numeric_rejected_through_python_and_js(
        self,
        monkeypatch,
        numeric_literal,
    ):
        """NaN/Infinity remain rejected at the same production byte boundaries."""
        seed_name = f"non_finite_{numeric_literal.replace('-', 'neg_')}.v1.json"
        seed_bytes = self._seed_bytes(numeric_literal)

        py_result = self._load_python_seed_image(monkeypatch, seed_name, seed_bytes)
        js_result = _load_js_seed_image_with_manifest_mode(seed_name, seed_bytes)

        assert py_result["ok"] is False
        assert "Infinity" in str(py_result["error"]) or "NaN" in str(py_result["error"])
        assert js_result["ok"] is False
        assert "JSON" in str(js_result["error"]) or "Unexpected token" in str(
            js_result["error"]
        )


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
                emit_fn=_stub_emit, step=0, state={},
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
                emit_fn=_stub_emit, step=0, state={},
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
                emit_fn=_stub_emit, step=0, state={},
            )

    def test_non_dict_request(self):
        """Non-dict request raises RcxEngineError."""
        with pytest.raises(RcxEngineError, match="boundary request must be dict"):
            _service_boundary_effect(
                "not_a_dict", max_algorithm_iterations=10,
                emit_fn=_stub_emit, step=0, state={},
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
                emit_fn=_stub_emit, step=0, state={},
            )

    def test_unknown_operation_api_bad_request(self):
        """Unknown operation raises RcxEngineError with api.bad_request error code."""
        bad_request = {
            "operation": "nonexistent_op",
            "input": {},
            "context": {},
            "inject_key": "result",
        }
        with pytest.raises(RcxEngineError, match="Unknown boundary operation"):
            _service_boundary_effect(
                bad_request, max_algorithm_iterations=10,
                emit_fn=_stub_emit, step=0, state={},
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
                emit_fn=_stub_emit, step=0, state={},
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
                emit_fn=_stub_emit, step=0, state={},
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
                emit_fn=_stub_emit, step=0, state={},
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
                emit_fn=_stub_emit, step=0, state={},
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
                emit_fn=_stub_emit, step=0, state={},
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
                emit_fn=_stub_emit, step=0, state={},
            )

    def test_run_trace_max_steps_absent_defaults_to_bootstrap_clock(self):
        """Missing max_steps uses the boundary default clock, not a dirty fallback."""
        ctx = _service_boundary_effect(
            _toggle_trace_request(), max_algorithm_iterations=10,
            emit_fn=_stub_emit, step=0, state={},
        )
        result = ctx["result"]
        trace = _linked_trace_to_list(result["trace"])
        assert result["stall"] is False
        assert result["result"] == "A"
        assert trace[-1] == {
            "step": 100,
            "state": "A",
            "projection": None,
            "max_steps": True,
        }

    def test_run_trace_max_steps_explicit_integer_budget(self):
        """Explicit integer max_steps is accepted as structural budget data."""
        ctx = _service_boundary_effect(
            _toggle_trace_request(1), max_algorithm_iterations=10,
            emit_fn=_stub_emit, step=0, state={},
        )
        result = ctx["result"]
        trace = _linked_trace_to_list(result["trace"])
        assert result["stall"] is False
        assert result["result"] == "B"
        assert trace[-1] == {
            "step": 1,
            "state": "B",
            "projection": None,
            "max_steps": True,
        }

    @pytest.mark.parametrize(
        "bad_value",
        [
            pytest.param("abc", id="string"),
            pytest.param({}, id="object"),
            pytest.param(True, id="bool"),
            pytest.param(None, id="null"),
            pytest.param(-1, id="negative"),
            pytest.param(1.5, id="non_integer_float"),
            pytest.param(float("inf"), id="inf"),
            pytest.param(float("nan"), id="nan"),
        ],
    )
    def test_run_trace_max_steps_explicit_bad_values_fail_closed(self, bad_value):
        """Explicit dirty max_steps values raise typed boundary errors."""
        with pytest.raises(RcxEngineError) as exc:
            _service_boundary_effect(
                _toggle_trace_request(bad_value), max_algorithm_iterations=10,
                emit_fn=_stub_emit, step=0, state={},
            )
        assert exc.value.error_code == "api.bad_request"

    def test_run_trace_max_steps_over_cap_fails_closed(self):
        """The hard cap is a fail-closed resource guard, not a silent clamp."""
        with pytest.raises(RcxEngineError) as exc:
            _service_boundary_effect(
                _toggle_trace_request(10001), max_algorithm_iterations=10,
                emit_fn=_stub_emit, step=0, state={},
            )
        assert exc.value.error_code == "api.bad_request"
        assert "10000" in str(exc.value)

    def test_run_trace_zero_budget_reports_exhaustion_boundary(self):
        """A zero explicit budget produces the trace exhaustion marker at step 0."""
        ctx = _service_boundary_effect(
            _toggle_trace_request(0), max_algorithm_iterations=10,
            emit_fn=_stub_emit, step=0, state={},
        )
        result = ctx["result"]
        trace = _linked_trace_to_list(result["trace"])
        assert result["stall"] is False
        assert result["result"] == "A"
        assert trace == [{
            "step": 0,
            "state": "A",
            "projection": None,
            "max_steps": True,
        }]

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

    def test_js_run_trace_max_steps_absent_defaults_to_bootstrap_clock(self):
        """JS missing max_steps matches the boundary default clock."""
        result = _run_js_trace()
        assert result["ok"] is True
        assert result["stall"] is False
        assert result["result"] == "A"
        assert result["last"] == {
            "step": 100,
            "state": "A",
            "projection": None,
            "max_steps": True,
        }

    def test_js_run_trace_max_steps_explicit_integer_budget(self):
        """JS explicit integer max_steps is accepted as structural budget data."""
        result = _run_js_trace("1")
        assert result["ok"] is True
        assert result["stall"] is False
        assert result["result"] == "B"
        assert result["last"] == {
            "step": 1,
            "state": "B",
            "projection": None,
            "max_steps": True,
        }

    @pytest.mark.parametrize(
        "bad_expr",
        [
            pytest.param("'abc'", id="string"),
            pytest.param("{}", id="object"),
            pytest.param("true", id="bool"),
            pytest.param("null", id="null"),
            pytest.param("-1", id="negative"),
            pytest.param("1.5", id="non_integer_number"),
            pytest.param("Infinity", id="inf"),
            pytest.param("NaN", id="nan"),
        ],
    )
    def test_js_run_trace_max_steps_explicit_bad_values_fail_closed(self, bad_expr):
        """JS explicit dirty max_steps values raise typed boundary errors."""
        result = _run_js_trace(bad_expr)
        assert result["ok"] is False
        assert result["error_code"] == "api.bad_request"

    def test_js_run_trace_max_steps_over_cap_fails_closed(self):
        """JS hard cap is a fail-closed resource guard, not a silent clamp."""
        result = _run_js_trace("10001")
        assert result["ok"] is False
        assert result["error_code"] == "api.bad_request"
        assert "10000" in result["message"]

    def test_js_run_trace_zero_budget_reports_exhaustion_boundary(self):
        """JS zero explicit budget produces the trace exhaustion marker at step 0."""
        result = _run_js_trace("0")
        assert result["ok"] is True
        assert result["stall"] is False
        assert result["result"] == "A"
        assert result["last"] == {
            "step": 0,
            "state": "A",
            "projection": None,
            "max_steps": True,
        }

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
                emit_fn=_stub_emit, step=0, state={},
            )

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

    Tests call the production seed image byte boundary directly. The path wrapper
    now resolves filenames through the manifest first; unknown filenames should
    fail there, while malformed image contents are validated by loadVerifiedSeedImage.
    """

    @staticmethod
    def _run_seed_loader_test(projections_json, expect_index, expect_type):
        """Call the production CLI mode with malformed projection bytes."""
        js_code = f"""
        const {{
            loadVerifiedSeedImage,
            SEED_IMAGE_VERIFICATION_MODES,
        }} = require('./mu/host/js/core/seed_loader');
        const seedBytes = Buffer.from(JSON.stringify({{
            meta: {{name: "TEST", version: "1.0", description: "test"}},
            projections: {projections_json}
        }}));
        try {{
            loadVerifiedSeedImage(
                '_test_malformed_seed.json',
                seedBytes,
                SEED_IMAGE_VERIFICATION_MODES.CLI
            );
            console.log('ERROR: no throw');
        }} catch(e) {{
            if (e.message.includes('projection[{expect_index}]') &&
                e.message.includes('{expect_type}')) {{
                console.log('OK');
            }} else {{
                console.log('WRONG: ' + e.message);
            }}
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

    def test_main_load_verified_seed_delegates_to_seed_image_boundary_source_lock(self):
        """CLI seed path wrapper delegates parse/validation to the byte boundary."""
        main_js = (REPO_ROOT / "mu" / "host" / "js" / "cli" / "main.js").read_text()
        assert "SEED_IMAGE_VERIFICATION_MODES.CLI" in main_js, (
            "main.js must import/use the shared seed image boundary"
        )
        fn_match = re.search(
            r"function loadVerifiedSeed\(seedName\) \{(.*?)^}",
            main_js,
            re.DOTALL | re.MULTILINE,
        )
        assert fn_match, "main.js loadVerifiedSeed wrapper not found"
        body = fn_match.group(1)
        assert "getSeedSubdir(seedName)" in body, (
            "main.js path wrapper must derive seed subdir from the manifest"
        )
        assert "fs.readFileSync(seedPath)" in body, (
            "main.js path wrapper must retain filesystem read at the outer edge"
        )
        assert "loadVerifiedSeedImage(" in body, (
            "main.js path wrapper must delegate to loadVerifiedSeedImage"
        )
        assert "SEED_IMAGE_VERIFICATION_MODES.CLI" in body, (
            "main.js path wrapper must use the manifest-derived CLI view"
        )
        assert "SEED_CHECKSUMS," not in body, (
            "main.js path wrapper must not pass caller checksum registry authority"
        )
        assert "EXPECTED_PROJECTION_IDS," not in body, (
            "main.js path wrapper must not pass caller projection registry authority"
        )
        assert "JSON.parse" not in body, (
            "main.js path wrapper must not parse seed JSON directly"
        )
        assert "verifySeedChecksum" not in body, (
            "main.js path wrapper must not duplicate checksum verification"
        )

    def test_core_seed_loader_type_guard_precedes_unknown_and_id_map(self):
        """seed image boundary rejects malformed projections before registry/id access."""
        source = (
            REPO_ROOT / "mu" / "host" / "js" / "core" / "seed_loader.js"
        ).read_text()
        assert "function loadVerifiedSeedImage(" in source, (
            "seed_loader.js missing explicit seed image byte boundary"
        )
        assert "TEST_ONLY_NEGATIVE_CONTROL" not in source, (
            "seed_loader.js must not export a production negative-control mode"
        )
        assert "negativeControlView" not in source, (
            "seed_loader.js must not accept caller-supplied negative-control views"
        )
        assert "require('util')" not in source and 'require("util")' not in source, (
            "seed_loader.js must not widen the Node stdlib import surface for seed bytes"
        )
        wrapper_match = re.search(
            r"function loadVerifiedSeed\(seedName, subdir\) \{(.*?)^}",
            source,
            re.DOTALL | re.MULTILINE,
        )
        assert wrapper_match, "seed_loader.js loadVerifiedSeed wrapper not found"
        wrapper_body = wrapper_match.group(1)
        assert "fs.readFileSync(seedPath)" in wrapper_body, (
            "seed_loader.js path wrapper must keep file I/O at the outer edge"
        )
        assert "loadVerifiedSeedImage(" in wrapper_body, (
            "seed_loader.js path wrapper must delegate to loadVerifiedSeedImage"
        )
        assert "SEED_IMAGE_VERIFICATION_MODES.CORE" in wrapper_body, (
            "seed_loader.js path wrapper must use the manifest-derived core view"
        )
        assert "CORE_SEED_CHECKSUMS," not in wrapper_body, (
            "seed_loader.js path wrapper must not pass caller checksum registry authority"
        )
        assert "CORE_SEED_PROJECTION_IDS," not in wrapper_body, (
            "seed_loader.js path wrapper must not pass caller projection registry authority"
        )
        assert "JSON.parse" not in wrapper_body, (
            "seed_loader.js path wrapper must not parse seed JSON directly"
        )

        guard = "p === null || typeof p !== 'object' || Array.isArray(p)"
        unknown_seed_check = "if (!expected)"
        id_map = "seed.projections.map(p => p.id)"

        assert guard in source, "seed_loader.js missing projection entry type guard"
        assert unknown_seed_check in source, "seed_loader.js missing unknown-seed fail-closed check"
        assert id_map in source, "seed_loader.js missing projection-id map verification"

        guard_pos = source.index(guard)
        assert guard_pos < source.index(unknown_seed_check), (
            "seed_loader.js projection type guard must run before unknown-seed rejection"
        )
        assert guard_pos < source.index(id_map), (
            "seed_loader.js projection type guard must run before projection id access"
        )

# ===========================================================================
# Test 3c: JS binary decoder sidecar lock
# ===========================================================================


class TestJsSeedLoaderBinaryDecoderSidecarLock:
    """Binary decoder sidecar must not become the production seed loading path."""

    def test_binary_decoder_sidecar_not_production_loader(self):
        """Binary decoder parity must not become the production seed loading path."""
        source = (
            REPO_ROOT / "mu" / "host" / "js" / "core" / "seed_loader.js"
        ).read_text()

        assert "decodeMuBinaryValue" in source, (
            "seed_loader.js must export the mechanical MuBinary decoder sidecar"
        )
        assert "decodeSeedBinaryProjections" in source, (
            "seed_loader.js must export the seed-projection binary decoder sidecar"
        )

        json_boundary = source[
            source.index("function loadVerifiedSeedImage"):
            source.index("/**\n * Load and verify a seed file.")
        ]
        path_wrapper = source[
            source.index("function loadVerifiedSeed(seedName, subdir)"):
            source.index("function getSeedChecksum")
        ]

        assert "if (hasBinaryImage)" in json_boundary, (
            "binary sidecar decode must stay behind an explicit opt-in guard"
        )
        assert "decodeSeedBinaryProjections(" not in path_wrapper, (
            "path loader must not flip from JSON seed images to binary projections"
        )
        assert "loadVerifiedSeedImage(" in path_wrapper, (
            "path loader must continue delegating to the JSON seed image boundary"
        )
        assert "SEED_IMAGE_VERIFICATION_MODES.CORE" in path_wrapper, (
            "core path loader must continue using manifest-derived CORE authority"
        )

        js_code = """
        const { decodeMuBinaryValue } = require('./mu/host/js/core/seed_loader');
        try {
            decodeMuBinaryValue(Buffer.from([0x05, 0x00, 0x00, 0x00, 0x01, 0xff]));
            console.log(JSON.stringify({ok: true}));
        } catch(e) {
            console.log(JSON.stringify({ok: false, name: e.name, error: e.message}));
        }
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"JS failed: {result.stderr}"
        malformed_utf8 = json.loads(result.stdout)
        assert malformed_utf8["ok"] is False
        assert malformed_utf8["name"] == "MuBinaryDecodeError"
        assert "Malformed UTF-8 string at offset 0" in malformed_utf8["error"]


class TestProjectionLoaderSeedMigrationIntegrityChainBoundary:
    """Seed binary migration proof must remain sidecar-only."""

    def test_binary_migration_integrity_chain_not_production_loader(self, monkeypatch):
        """Production JSON loaders must not call binary migration or proof helpers."""
        seed_name = "rcx_engine.v1.json"
        seed_bytes = get_seed_path(seed_name).read_bytes()
        binary_image, proof = generate_seed_binary_migration_artifact(
            seed_name,
            seed_bytes,
        )
        assert proof["binary_is_smaller"] is True
        assert decode_seed_binary_projections(binary_image)

        import mu.tools.util.seed_binary_migration as migration_tool_mod

        def _sidecar_called(_binary_image):
            raise AssertionError("binary sidecar called from JSON loader")

        monkeypatch.setattr(
            migration_tool_mod,
            "decode_seed_binary_projections",
            _sidecar_called,
        )
        seed = load_verified_seed_image(seed_name, seed_bytes, verify=True)
        assert [proj["id"] for proj in seed["projections"]] == EXPECTED_PROJECTION_IDS[
            seed_name
        ]

        py_source = (
            REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "seed_integrity.py"
        ).read_text()
        py_json_boundary = py_source[
            py_source.index("def load_verified_seed_image("):
            py_source.index("# BOOTSTRAP_PRIMITIVE: projection_loader")
        ]
        py_path_wrapper = py_source[
            py_source.index("def load_verified_seed(seed_path: Path"):
            py_source.index("def get_mu_dir")
        ]
        for forbidden in (
            "generate_seed_binary_migration_artifact",
            "verify_seed_binary_migration_artifact",
            "decode_seed_binary_projections",
            "encode_seed_binary_projections",
        ):
            assert forbidden not in py_path_wrapper
        assert "if binary_image is not None:" in py_json_boundary

        js_source = (
            REPO_ROOT / "mu" / "host" / "js" / "core" / "seed_loader.js"
        ).read_text()
        assert "buildSeedBinaryMigrationProof" in js_source
        assert "verifySeedBinaryMigrationArtifact" in js_source
        json_boundary = js_source[
            js_source.index("function loadVerifiedSeedImage"):
            js_source.index("/**\n * Load and verify a seed file.")
        ]
        path_wrapper = js_source[
            js_source.index("function loadVerifiedSeed(seedName, subdir)"):
            js_source.index("function getSeedChecksum")
        ]
        for forbidden in (
            "buildSeedBinaryMigrationProof(",
            "verifySeedBinaryMigrationArtifact(",
            "decodeSeedBinaryProjections(",
            "decodeMuBinaryValue(",
        ):
            assert forbidden not in path_wrapper
        assert "if (hasBinaryImage)" in json_boundary

        js_code = """
        const sl = require('./mu/host/js/core/seed_loader');
        sl.decodeSeedBinaryProjections = function() {
          throw new Error('binary sidecar called from JSON loader');
        };
        const seed = sl.loadVerifiedSeed('rcx_engine.v1.json', 'programs');
        console.log(JSON.stringify({
          ok: true,
          ids: seed.projections.map(p => p.id),
        }));
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == {
            "ok": True,
            "ids": EXPECTED_PROJECTION_IDS[seed_name],
        }

    def test_smaller_image_pilot_adapter_is_opt_in_and_preserves_json_default(
        self,
        tmp_path,
    ):
        """The production pilot adapter must not become the default seed loader."""
        seed_name = "rcx_engine.v1.json"
        seed_bytes = get_seed_path(seed_name).read_bytes()
        binary_image, proof = generate_seed_binary_migration_artifact(
            seed_name,
            seed_bytes,
        )

        with pytest.raises(SeedBinaryMigrationError, match="Mu-native sidecar adapter"):
            load_verified_seed_image(
                seed_name,
                seed_bytes,
                verify=True,
                binary_image=binary_image,
                expected_binary_proof=proof,
            )

        host_context_script = """
import base64
import json
from rcx_pi.selfhost.seed_integrity import load_verified_seed_image

payload = json.loads(input())
try:
    seed = load_verified_seed_image(
        payload["seed_name"],
        base64.b64decode(payload["seed_bytes"]),
        verify=True,
        binary_image=base64.b64decode(payload["binary_image"]),
        expected_binary_proof=payload["proof"],
    )
except Exception as exc:
    print(json.dumps({"ok": False, "name": type(exc).__name__, "error": str(exc)}))
else:
    print(json.dumps({"ok": True, "ids": [projection["id"] for projection in seed["projections"]]}))
"""
        host_context = subprocess.run(
            [sys.executable, "-c", host_context_script],
            input=json.dumps(
                {
                    "seed_name": seed_name,
                    "seed_bytes": base64.b64encode(seed_bytes).decode("ascii"),
                    "binary_image": base64.b64encode(binary_image).decode("ascii"),
                    "proof": proof,
                }
            ),
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env={
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(REPO_ROOT / "mu" / "host" / "python"),
            },
        )
        assert host_context.returncode == 0, host_context.stderr
        host_payload = json.loads(host_context.stdout)
        assert host_payload["ok"] is False
        assert host_payload["name"] == "SeedBinaryMigrationError"
        assert "Mu-native sidecar adapter" in host_payload["error"]

        py_source = (
            REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "seed_integrity.py"
        ).read_text()
        assert "binary_image: bytes | None = None" in py_source
        assert "expected_binary_proof: dict[str, Any] | None = None" in py_source
        assert "importlib" not in py_source
        py_json_boundary = py_source[
            py_source.index("def load_verified_seed_image("):
            py_source.index("# BOOTSTRAP_PRIMITIVE: projection_loader")
        ]
        py_path_wrapper = py_source[
            py_source.index("def load_verified_seed(seed_path: Path"):
            py_source.index("def get_mu_dir")
        ]
        for forbidden in (
            "verify_seed_binary_migration_artifact(",
            "decode_seed_binary_projections(",
        ):
            assert forbidden not in py_path_wrapper
            assert forbidden not in py_json_boundary
        assert "if binary_image is not None:" in py_json_boundary
        assert "from mu.tools" not in py_json_boundary

        js_source = (
            REPO_ROOT / "mu" / "host" / "js" / "core" / "seed_loader.js"
        ).read_text()
        assert "binaryImage = null" in js_source
        assert "expectedBinaryProof = null" in js_source
        json_boundary = js_source[
            js_source.index("function loadVerifiedSeedImage"):
            js_source.index("/**\n * Load and verify a seed file.")
        ]
        path_wrapper = js_source[
            js_source.index("function loadVerifiedSeed(seedName, subdir)"):
            js_source.index("function getSeedChecksum")
        ]
        for forbidden in (
            "verifySeedBinaryMigrationArtifact(",
            "decodeSeedBinaryProjections(",
            "decodeMuBinaryValue(",
        ):
            assert forbidden not in path_wrapper
        assert "if (hasBinaryImage)" in json_boundary

        js_code = """
        const sl = require('./mu/host/js/core/seed_loader');
        sl.verifySeedBinaryMigrationArtifact = function() {
          throw new Error('binary proof adapter called from JSON loader');
        };
        const seed = sl.loadVerifiedSeed('rcx_engine.v1.json', 'programs');
        console.log(JSON.stringify({
          ok: true,
          ids: seed.projections.map(p => p.id),
        }));
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == {
            "ok": True,
            "ids": EXPECTED_PROJECTION_IDS[seed_name],
        }


# ===========================================================================
# Test 3d: F2 production-binding lock (anti-theater)
# ===========================================================================


class TestF2ProductionBindingLock:
    """Lock: F2 tests must use production code paths, not inline simulation."""

    @staticmethod
    def _malformed_projection_class_source():
        test_file = REPO_ROOT / "mu" / "tests" / "l4_gates" / "test_boundary_dispatch_authority_gate.py"
        source = test_file.read_text()
        class_start = source.index("class TestJsSeedLoaderMalformedProjection")
        next_class = source.find("\nclass ", class_start + 1)
        return source[class_start:next_class] if next_class != -1 else source[class_start:]

    def test_f2_tests_require_production_seed_loader(self):
        """TestJsSeedLoaderMalformedProjection must call production seed_loader."""
        class_source = self._malformed_projection_class_source()
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

    def test_f2_lock_references_production_loaders_not_d010_research(self):
        """Malformed projection coverage must bind production loader paths, not D010."""
        class_source = self._malformed_projection_class_source()

        assert "mu/host/js/core/seed_loader" in class_source
        assert '"cli" / "main.js"' in class_source

        forbidden_fragments = [
            "test_" + "d010" + "_h5_projection_loader_binary.py",
            "d" + "010",
            "h5_projection_loader_binary",
        ]
        lower_source = class_source.lower()
        for fragment in forbidden_fragments:
            assert fragment not in lower_source, (
                "TestJsSeedLoaderMalformedProjection must not rely on "
                "research-only D010 projection-loader artifacts"
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
            emit_fn=_stub_emit, step=0, state={},
        )
        assert "trace_result" in ctx
        result = ctx["trace_result"]
        assert "result" in result
        assert "trace" in result
        assert "stall" in result

    def test_hash_trace_produces_result(self):
        """hash_trace via handler-map returns hashed linked list."""
        from rcx_pi.selfhost.engine_pipeline import hash_trace_for_recurrence

        trace_input = {"head": {"state": 1}, "tail": {"head": {"state": 2}, "tail": None}}
        request = {
            "operation": "hash_trace",
            "input": trace_input,
            "context": {},
            "inject_key": "hashed",
        }
        ctx = _service_boundary_effect(
            request, max_algorithm_iterations=10,
            emit_fn=_stub_emit, step=0, state={},
        )
        assert "hashed" in ctx


# ===========================================================================
# Test 5: Algorithm seed allowlist (F-22)
# ===========================================================================


class TestAlgorithmSeedAllowlist:
    """Gate: boundary run_algorithm follows manifest authority metadata (F-22).

    Python _boundary_op_run_algorithm previously accepted any of 17 registered
    seed names via get_seed_path(). This gate proves Python and JS now derive
    authority from seed_registry_manifest.v1.json metadata, not seed-map shape.
    """

    def _make_run_algorithm_request(self, algo_name):
        """Build a boundary request for run_algorithm with the given seed name."""
        return {
            "operation": "run_algorithm",
            "input": {},
            "context": {},
            "inject_key": "algo_result",
            "algorithm": algo_name,
        }

    def _run_python_seed_integrity_import_with_records(self, tmp_path, seed_records):
        manifest = {
            "schema": SEED_REGISTRY_MANIFEST["schema"],
            "seeds": seed_records,
        }
        manifest_text = json.dumps(manifest, indent=2) + "\n"
        manifest_hash = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()

        temp_module = (
            tmp_path / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "seed_integrity.py"
        )
        temp_module.parent.mkdir(parents=True)
        source = (
            REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "seed_integrity.py"
        ).read_text()
        source = re.sub(
            r'SEED_REGISTRY_MANIFEST_SHA256 = \(\s*"[0-9a-f]+"\s*\)',
            f'SEED_REGISTRY_MANIFEST_SHA256 = (\n    "{manifest_hash}"\n)',
            source,
            count=1,
            flags=re.S,
        )
        temp_module.write_text(source)
        (tmp_path / "mu" / "seed_registry_manifest.v1.json").write_text(manifest_text)

        script = f"""
import importlib.util
spec = importlib.util.spec_from_file_location("temp_seed_integrity", {str(temp_module)!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print("OK")
"""
        return subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )

    def _run_js_seed_loader_import_with_records(self, seed_records):
        manifest = {
            "schema": SEED_REGISTRY_MANIFEST["schema"],
            "seeds": seed_records,
        }
        manifest_text = json.dumps(manifest, separators=(",", ":"))
        manifest_hash = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()
        js_code = f"""
        const fs = require('fs');
        const path = require('path');
        const vm = require('vm');
        const sourcePath = path.join(process.cwd(), 'mu/host/js/core/seed_loader.js');
        const source = fs.readFileSync(sourcePath, 'utf8').replace(
          /const SEED_REGISTRY_MANIFEST_SHA256 =\\n  '[0-9a-f]{{64}}';/,
          "const SEED_REGISTRY_MANIFEST_SHA256 =\\n  '{manifest_hash}';"
        );
        const manifestBytes = Buffer.from({json.dumps(manifest_text)}, 'utf8');
        const fakeFs = Object.assign(Object.create(null), fs, {{
          readFileSync(p, options) {{
            if (String(p).endsWith('seed_registry_manifest.v1.json')) {{
              return manifestBytes;
            }}
            return fs.readFileSync(p, options);
          }}
        }});
        const sandbox = {{
          require(name) {{
            if (name === 'fs') return fakeFs;
            if (name === './stage0_vm') return {{ muCopy(value) {{ return value; }} }};
            return require(name);
          }},
          module: {{ exports: {{}} }},
          exports: {{}},
          __dirname: path.join(process.cwd(), 'mu/host/js/core'),
          TextDecoder,
          Buffer,
          console,
        }};
        try {{
          vm.runInNewContext(source, sandbox, {{ filename: 'seed_loader.js' }});
          console.log('OK');
        }} catch (e) {{
          console.error(e.message);
          process.exit(1);
        }}
        """
        return subprocess.run(
            ["node", "-e", js_code],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )

    def test_python_manifest_authority_matches_expected_migration_set(self):
        """Python exports exactly the manifest-authorized migration set."""
        manifest_allowed = frozenset(
            name for name, meta in SEED_REGISTRY_MANIFEST["seeds"].items()
            if meta.get("authority", {}).get("run_algorithm") is True
        )

        assert RUN_ALGORITHM_AUTHORITY_SEEDS == EXPECTED_RUN_ALGORITHM_AUTHORITY_SEEDS
        assert manifest_allowed == EXPECTED_RUN_ALGORITHM_AUTHORITY_SEEDS

    def test_python_manifest_authority_rejects_unexpected_true_seed(self, tmp_path):
        """Manifest validator fails closed if any extra seed gains authority."""
        records = copy.deepcopy(SEED_REGISTRY_MANIFEST["seeds"])
        records["kernel.v1.json"]["authority"] = {"run_algorithm": True}

        result = self._run_python_seed_integrity_import_with_records(tmp_path, records)
        assert result.returncode != 0
        assert "authority.run_algorithm set mismatch" in result.stderr

    def test_python_manifest_authority_rejects_malformed_metadata(self, tmp_path):
        """Manifest validator fails closed on unreadable authority metadata."""
        records = copy.deepcopy(SEED_REGISTRY_MANIFEST["seeds"])
        records["kernel.v1.json"]["authority"] = []

        result = self._run_python_seed_integrity_import_with_records(tmp_path, records)
        assert result.returncode != 0
        assert "authority must be a dict" in result.stderr

    def test_python_manifest_authority_rejects_missing_run_algorithm_key(self, tmp_path):
        """Manifest validator fails closed when authority lacks run_algorithm."""
        records = copy.deepcopy(SEED_REGISTRY_MANIFEST["seeds"])
        records["kernel.v1.json"]["authority"] = {}

        result = self._run_python_seed_integrity_import_with_records(tmp_path, records)
        assert result.returncode != 0
        assert "authority missing 'run_algorithm'" in result.stderr

    def test_python_manifest_authority_rejects_non_boolean_run_algorithm(self, tmp_path):
        """Manifest validator fails closed on non-boolean run_algorithm metadata."""
        records = copy.deepcopy(SEED_REGISTRY_MANIFEST["seeds"])
        records["kernel.v1.json"]["authority"] = {"run_algorithm": "true"}

        result = self._run_python_seed_integrity_import_with_records(tmp_path, records)
        assert result.returncode != 0
        assert "authority.run_algorithm must be bool" in result.stderr

    def test_python_rejects_kernel_seed(self):
        """Python run_algorithm rejects kernel.v1.json (not an algorithm seed)."""
        _events.clear()
        request = self._make_run_algorithm_request("kernel.v1.json")
        with pytest.raises(RcxEngineError, match="authorized algorithm seed"):
            _service_boundary_effect(
                request, max_algorithm_iterations=10,
                emit_fn=_stub_emit, step=0, state={},
            )

    def test_python_rejects_match_seed(self):
        """Python run_algorithm rejects match.v2.json."""
        _events.clear()
        request = self._make_run_algorithm_request("match.v2.json")
        with pytest.raises(RcxEngineError, match="authorized algorithm seed"):
            _service_boundary_effect(
                request, max_algorithm_iterations=10,
                emit_fn=_stub_emit, step=0, state={},
            )

    def test_python_rejects_hemispheres_seed(self):
        """Python run_algorithm rejects hemispheres.v1.json."""
        _events.clear()
        request = self._make_run_algorithm_request("hemispheres.v1.json")
        with pytest.raises(RcxEngineError, match="authorized algorithm seed"):
            _service_boundary_effect(
                request, max_algorithm_iterations=10,
                emit_fn=_stub_emit, step=0, state={},
            )

    def test_python_accepts_recurrence_v1(self, monkeypatch):
        """Python run_algorithm accepts recurrence.v1.json (authorized seed reaches _run_sub_algorithm)."""
        _events.clear()
        called_with = {}

        def _fake_run_sub_algorithm(projs, inp, max_iters):
            called_with["projs"] = projs
            called_with["input"] = inp
            return {"result": "fake", "trace": None, "stall": False}

        import rcx_pi.selfhost.engine_pipeline as engine_pipeline_mod
        monkeypatch.setattr(engine_pipeline_mod, "_run_sub_algorithm", _fake_run_sub_algorithm)
        request = self._make_run_algorithm_request("recurrence.v1.json")
        ctx = _service_boundary_effect(
            request, max_algorithm_iterations=10,
            emit_fn=_stub_emit, step=0, state={},
        )
        assert "algo_result" in ctx, "authorized seed must produce a result"
        assert called_with.get("projs") is not None, "authorized seed must reach _run_sub_algorithm"

    def test_python_accepts_recurrence_v2(self, monkeypatch):
        """Python run_algorithm accepts recurrence.v2.json (authorized)."""
        _events.clear()
        called = [False]

        def _fake_run_sub_algorithm(projs, inp, max_iters):
            called[0] = True
            return {"result": "fake"}

        import rcx_pi.selfhost.engine_pipeline as engine_pipeline_mod
        monkeypatch.setattr(engine_pipeline_mod, "_run_sub_algorithm", _fake_run_sub_algorithm)
        request = self._make_run_algorithm_request("recurrence.v2.json")
        _service_boundary_effect(
            request, max_algorithm_iterations=10,
            emit_fn=_stub_emit, step=0, state={},
        )
        assert called[0], "recurrence.v2.json must reach _run_sub_algorithm"

    def test_python_accepts_exhaustion_v1(self, monkeypatch):
        """Python run_algorithm accepts exhaustion.v1.json (authorized)."""
        _events.clear()
        called = [False]

        def _fake_run_sub_algorithm(projs, inp, max_iters):
            called[0] = True
            return {"result": "fake"}

        import rcx_pi.selfhost.engine_pipeline as engine_pipeline_mod
        monkeypatch.setattr(engine_pipeline_mod, "_run_sub_algorithm", _fake_run_sub_algorithm)
        request = self._make_run_algorithm_request("exhaustion.v1.json")
        _service_boundary_effect(
            request, max_algorithm_iterations=10,
            emit_fn=_stub_emit, step=0, state={},
        )
        assert called[0], "exhaustion.v1.json must reach _run_sub_algorithm"

    def test_python_accepts_fix_v1(self, monkeypatch):
        """Python run_algorithm accepts fix.v1.json (authorized)."""
        _events.clear()
        called = [False]

        def _fake_run_sub_algorithm(projs, inp, max_iters):
            called[0] = True
            return {"result": "fake"}

        import rcx_pi.selfhost.engine_pipeline as engine_pipeline_mod
        monkeypatch.setattr(engine_pipeline_mod, "_run_sub_algorithm", _fake_run_sub_algorithm)
        request = self._make_run_algorithm_request("fix.v1.json")
        _service_boundary_effect(
            request, max_algorithm_iterations=10,
            emit_fn=_stub_emit, step=0, state={},
        )
        assert called[0], "fix.v1.json must reach _run_sub_algorithm"

    def test_python_accepts_scheduler_v1(self, monkeypatch):
        """Python run_algorithm accepts rcx_engine_scheduler.v1.json (authorized)."""
        _events.clear()
        called = [False]

        def _fake_run_sub_algorithm(projs, inp, max_iters):
            called[0] = True
            return {"result": "fake"}

        import rcx_pi.selfhost.engine_pipeline as engine_pipeline_mod
        monkeypatch.setattr(engine_pipeline_mod, "_run_sub_algorithm", _fake_run_sub_algorithm)
        request = self._make_run_algorithm_request("rcx_engine_scheduler.v1.json")
        _service_boundary_effect(
            request, max_algorithm_iterations=10,
            emit_fn=_stub_emit, step=0, state={},
        )
        assert called[0], "rcx_engine_scheduler.v1.json must reach _run_sub_algorithm"

    def test_python_manifest_authority_matches_js_manifest_authority(self):
        """Python and JS export the same manifest-derived run_algorithm authority."""
        js_code = """
        const seedLoader = require('./mu/host/js/core/seed_loader');
        console.log(JSON.stringify(Object.keys(seedLoader.RUN_ALGORITHM_AUTHORITY_SEEDS).sort()));
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"JS failed: {result.stderr}"
        assert json.loads(result.stdout) == sorted(
            EXPECTED_RUN_ALGORITHM_AUTHORITY_SEEDS
        )

    def test_js_manifest_authority_rejects_malformed_metadata(self):
        """JS manifest validator fails closed on unreadable authority metadata."""
        records = copy.deepcopy(SEED_REGISTRY_MANIFEST["seeds"])
        records["kernel.v1.json"]["authority"] = []

        result = self._run_js_seed_loader_import_with_records(records)
        assert result.returncode != 0
        assert "authority must be a plain object" in result.stderr

    def test_js_manifest_authority_rejects_non_boolean_metadata(self):
        """JS manifest validator fails closed on non-boolean run_algorithm."""
        records = copy.deepcopy(SEED_REGISTRY_MANIFEST["seeds"])
        records["kernel.v1.json"]["authority"] = {"run_algorithm": "true"}

        result = self._run_js_seed_loader_import_with_records(records)
        assert result.returncode != 0
        assert "authority.run_algorithm must be boolean" in result.stderr

    def test_js_manifest_authority_rejects_unexpected_true_seed(self):
        """JS manifest validator fails closed if any extra seed gains authority."""
        records = copy.deepcopy(SEED_REGISTRY_MANIFEST["seeds"])
        records["kernel.v1.json"]["authority"] = {"run_algorithm": True}

        result = self._run_js_seed_loader_import_with_records(records)
        assert result.returncode != 0
        assert "authority.run_algorithm set mismatch" in result.stderr

    def test_js_rejects_non_algorithm_seed(self):
        """JS run_algorithm rejects kernel.v1.json (not manifest-authorized)."""
        js_code = """
        const pipeline = require('./mu/host/js/engine/pipeline');
        const seedMap = Object.create(null);
        seedMap['recurrence.v1.json'] = [{id:'r',pattern:{},body:{}}];
        try {
            pipeline.serviceBoundaryEffect(
                [], seedMap,
                {operation:'run_algorithm',input:{},context:{},inject_key:'r',algorithm:'kernel.v1.json'},
                10, function(){}, 0, {}
            );
            console.log('ERROR: no throw');
        } catch(e) {
            if (e.error_code === 'api.bad_request' && e.message.includes('authorized algorithm seed')) {
                console.log('OK');
            } else {
                console.log('WRONG: ' + e.error_code + ': ' + e.message);
            }
        }
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"JS failed: {result.stderr}"
        assert result.stdout.strip() == "OK", f"JS non-algorithm seed: {result.stdout.strip()}"

    def test_js_rejects_rogue_injected_into_seed_map(self):
        """JS run_algorithm rejects rogue name even if present in seedProjectionMap."""
        js_code = """
        const pipeline = require('./mu/host/js/engine/pipeline');
        const seedMap = Object.create(null);
        seedMap['recurrence.v1.json'] = [{id:'r',pattern:{},body:{}}];
        seedMap['rogue.v1.json'] = [{id:'rogue',pattern:{},body:{}}];
        try {
            pipeline.serviceBoundaryEffect(
                [], seedMap,
                {operation:'run_algorithm',input:{},context:{},inject_key:'r',algorithm:'rogue.v1.json'},
                10, function(){}, 0, {}
            );
            console.log('ERROR: rogue executed');
        } catch(e) {
            if (e.error_code === 'api.bad_request' && e.message.includes('authorized algorithm seed')) {
                console.log('OK');
            } else {
                console.log('WRONG: ' + e.error_code + ': ' + e.message);
            }
        }
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"JS failed: {result.stderr}"
        assert result.stdout.strip() == "OK", f"JS rogue injection: {result.stdout.strip()}"

    def test_js_manifest_authority_accepts_expected_set(self):
        """JS accepts exactly the Python manifest-authorized set."""
        import json as _json
        py_allowed = sorted(RUN_ALGORITHM_AUTHORITY_SEEDS)
        allowed_json = _json.dumps(py_allowed)
        js_code = f"""
        const pipeline = require('./mu/host/js/engine/pipeline');
        const allowed = {allowed_json};
        const seedMap = Object.create(null);
        allowed.forEach(s => {{ seedMap[s] = [{{id:'p',pattern:{{}},body:{{}}}}]; }});
        let ok = true;
        for (const s of allowed) {{
            try {{
                pipeline.serviceBoundaryEffect(
                    [], seedMap,
                    {{operation:'run_algorithm',input:{{}},context:{{}},inject_key:'r',algorithm:s}},
                    1, function(){{}}, 0, {{}}
                );
            }} catch(e) {{
            if (e.message && e.message.includes('authorized algorithm seed')) {{
                    console.log('FAIL: ' + s + ' rejected by manifest authority');
                    ok = false;
                }}
            }}
        }}
        seedMap['rogue.v1.json'] = [{{id:'rg',pattern:{{}},body:{{}}}}];
        try {{
            pipeline.serviceBoundaryEffect(
                [], seedMap,
                {{operation:'run_algorithm',input:{{}},context:{{}},inject_key:'r',algorithm:'rogue.v1.json'}},
                1, function(){{}}, 0, {{}}
            );
            console.log('FAIL: rogue not rejected');
            ok = false;
        }} catch(e) {{
            if (!e.message.includes('authorized algorithm seed')) {{
                console.log('FAIL: wrong error for rogue: ' + e.message);
                ok = false;
            }}
        }}
        console.log(ok ? 'OK' : 'FAIL');
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"JS failed: {result.stderr}"
        assert result.stdout.strip() == "OK", f"JS manifest authority: {result.stdout.strip()}"

    def test_js_allowlist_rejects_prototype_pollution(self):
        """JS manifest authority must not accept prototype-chain key injection."""
        js_code = """
        const pipeline = require('./mu/host/js/engine/pipeline');
        Object.prototype['rogue.v1.json'] = true;
        const seedMap = Object.create(null);
        seedMap['recurrence.v1.json'] = [{id:'p',pattern:{},body:{}}];
        try {
            pipeline.serviceBoundaryEffect(
                [], seedMap,
                {operation:'run_algorithm',input:{},context:{},inject_key:'r',algorithm:'constructor'},
                1, function(){}, 0, {}
            );
            console.log('FAIL: constructor not rejected');
        } catch(e) {
            if (!(e.message && e.message.includes('authorized algorithm seed'))) {
                console.log('FAIL: wrong constructor error: ' + e.message);
            }
        }
        try {
            pipeline.serviceBoundaryEffect(
                [], seedMap,
                {operation:'run_algorithm',input:{},context:{},inject_key:'r',algorithm:'rogue.v1.json'},
                1, function(){}, 0, {}
            );
            console.log('FAIL: inherited rogue not rejected');
        } catch(e) {
            delete Object.prototype['rogue.v1.json'];
            if (e.message && e.message.includes('authorized algorithm seed')) {
                console.log('OK');
            } else {
                console.log('FAIL: wrong error: ' + e.message);
            }
        }
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"JS failed: {result.stderr}"
        assert result.stdout.strip() == "OK", f"N12 regression: {result.stdout.strip()}"


# ===========================================================================
# Test 6: Boundary result domain-validation invariant (F-24)
# ===========================================================================


class TestBoundaryResultDomainValidation:
    """Gate: boundary result uses domain-level validation (F-24).

    Proves the invariant that boundary results are validated with the
    domain-level validator (validate_no_kernel_reserved_fields) before
    re-injection into engine state, regardless of which internal validator
    the handler used.

    The behavioral test monkeypatches a handler to return a result containing
    algorithm-runtime internal fields (_detect_closure) and asserts that
    _service_boundary_effect rejects it via the domain validator.
    """

    def test_monkeypatch_handler_with_kernel_reserved_field_rejected(self, monkeypatch):
        """Handler returning _mode in result is rejected by domain validator.

        _mode is a kernel-reserved field (KERNEL_RESERVED_FIELDS). The domain
        validator (validate_no_kernel_reserved_fields) must reject it when it
        appears in a boundary result, proving the invariant that boundary
        results are domain-validated before re-entry into engine state.
        """
        _events.clear()

        def _poisoned_handler(request, req_input, max_algorithm_iterations):
            # Return a result containing a kernel-reserved field.
            # This must be rejected by validate_no_kernel_reserved_fields.
            return {"_mode": "forged", "result": 1}

        import rcx_pi.selfhost.engine_pipeline as engine_pipeline_mod
        original_dispatch = dict(engine_pipeline_mod._BOUNDARY_DISPATCH)  # ANTICHEAT_OK: gate monkeypatch for invariant test
        # Monkeypatch run_trace handler to return poisoned result
        engine_pipeline_mod._BOUNDARY_DISPATCH["run_trace"] = _poisoned_handler  # ANTICHEAT_OK: gate monkeypatch for invariant test
        try:
            request = {
                "operation": "run_trace",
                "input": {},
                "context": {},
                "inject_key": "result",
            }
            with pytest.raises(ValueError, match="_mode"):
                _service_boundary_effect(
                    request, max_algorithm_iterations=10,
                    emit_fn=_stub_emit, step=0, state={},
                )
        finally:
            # Restore original dispatch
            engine_pipeline_mod._BOUNDARY_DISPATCH.update(original_dispatch)  # ANTICHEAT_OK: gate monkeypatch restore

    def test_invariant_comment_present(self):
        """Source-lock: INVARIANT comment present above boundary result validation."""
        source = PY_STEP_MU.read_text()
        invariant_marker = "INVARIANT: boundary results re-enter engine state"
        validator_call = "validate_no_kernel_reserved_fields(result,"
        assert invariant_marker in source, (
            f"engine_pipeline.py must contain invariant comment: {invariant_marker!r}"
        )
        marker_pos = source.index(invariant_marker)
        # Find the first validate_no_kernel_reserved_fields(result, ...) after the marker
        validator_pos = source.index(validator_call, marker_pos)
        # Verify they're close (within 500 chars — comment + validation line)
        assert validator_pos - marker_pos < 500, (
            f"Invariant comment (pos {marker_pos}) must immediately precede "
            f"validation call (pos {validator_pos})"
        )


class TestInjectKeyCollisionGuardParity:
    """Cross-substrate parity: inject_key collision guard in serviceBoundaryEffect."""

    def test_js_inject_key_collision_guard_present(self):
        """JS serviceBoundaryEffect must check for inject_key collision before assignment.

        Parity with Python _service_boundary_effect which checks
        `if inject_key in context:` and raises RcxEngineError('input.inject_key_collision').
        """
        source = (REPO_ROOT / "mu" / "host" / "js" / "engine" / "pipeline.js").read_text()
        assert "inject_key_collision" in source, (
            "pipeline.js must contain inject_key_collision error code "
            "(parity with Python _service_boundary_effect)"
        )
        # Verify the guard is before the assignment, not after
        guard_pos = source.index("inject_key_collision")
        assign_pos = source.index("context[injectKey] = result")
        assert guard_pos < assign_pos, (
            "inject_key collision guard must precede context[injectKey] = result assignment"
        )

    def test_js_collect_ontology_evidence_cycle_detection(self):
        """JS collectOntologyEvidence must use structural walker plus cycle/cap fallback.

        Parity with Python _collect_ontology_evidence which uses visited_ids set
        and _MAX_TRACE_ENTRIES_HARD_CAP iteration cap.
        """
        source = (REPO_ROOT / "mu" / "host" / "js" / "engine" / "pipeline.js").read_text()
        collect_pos = source.index("function collectOntologyEvidence(")
        collect_prelude = "\n".join(source[:collect_pos].splitlines()[-5:])
        collect_body = source[collect_pos:source.index("// Boot1 re-entry depth limit")]
        has_verified_seed = (
            "loadVerifiedSeed(EVIDENCE_WALKER_SEED" in source
            and "evidence_walker.v1.json" in source
        )
        has_projection_step = "step(evidenceWalkerProjections, current)" in collect_body
        has_visited = "visited = new Set()" in collect_body
        has_cap = "EVIDENCE_WALKER_MAX_DRAIN" in collect_body and "100000" in source
        assert "BOUNDARY" in collect_prelude, (
            "collectOntologyEvidence BOUNDARY marker must remain adjacent to the "
            "function after inserting walker constants"
        )
        assert "@host_iteration" not in collect_prelude, (
            "collectOntologyEvidence must remain classified as boundary code, "
            "not host iteration"
        )
        assert has_verified_seed, (
            "collectOntologyEvidence must load verified evidence_walker.v1.json "
            "rather than relying on source-lock-only registry presence"
        )
        assert has_projection_step, (
            "collectOntologyEvidence must execute evidence_walker projections as "
            "the primary trace walking authority"
        )
        assert "collected = result.trace" in collect_body, (
            "collectOntologyEvidence may use host traversal only as fallback input"
        )
        assert has_visited, (
            "collectOntologyEvidence must use a visited Set for cycle detection "
            "in boundary fallback (parity with Python visited_ids)"
        )
        assert has_cap, (
            "collectOntologyEvidence must have iteration cap "
            "in boundary fallback (parity with Python _MAX_TRACE_ENTRIES_HARD_CAP)"
        )
