"""
Engine pipeline entry discipline and observer event contract guard.

Verifies:
1. run_engine_pipeline callsite inventory (AST-based, fail-closed).
2. run_hemisphere_routing callsite inventory (AST-based, fail-closed).
3. Observer event schema enforcement (mandatory fields).
4. Pipeline parameter defaults haven't drifted.
5. Engine/hemisphere result shape contracts (cross-substrate).
6. JS engine module shape and seed-derived boundary-operation authority.

What this checker PROVES:
- No new raw callers of run_engine_pipeline without inventory update.
- No new raw callers of run_hemisphere_routing without inventory update.
- Observer events always contain the 6 mandatory fields.
- Pipeline defaults (max_engine_iterations, use_boot1_recursive) are stable.
- Engine terminal keys and hemisphere keys match between Python and JS.
- JS engine dependency direction stays acyclic and does not gain host-only
  loaders or JS-only boundary-operation dispatch.

What this checker does NOT prove:
- Semantic correctness of pipeline execution.
- Observer event ordering or content accuracy.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest
from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline


# ── Source paths ─────────────────────────────────────────────────────────

_REPO = Path(__file__).resolve().parents[3]
_STEP_MU_PATH = _REPO / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "engine_pipeline.py"
_PY_STEP_MU_PATH = _REPO / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
_JS_KERNEL_PATH = _REPO / "mu" / "host" / "js" / "engine" / "kernel.js"
_JS_PIPELINE_PATH = _REPO / "mu" / "host" / "js" / "engine" / "pipeline.js"


def _read_all_js_source() -> str:
    """Read all JS module files from mu/host/js/ recursively."""
    js_dir = _REPO / "mu" / "host" / "js"
    parts = []
    for f in sorted(js_dir.rglob("*.js")):
        parts.append(f.read_text())
    return "\n".join(parts)


def _extract_js_function_body(source: str, function_name: str) -> str:
    """Extract a top-level JS function body for source-contract guards."""
    signature = f"function {function_name}"
    start = source.find(signature)
    assert start != -1, f"Could not find {function_name} function"
    opening_brace = source.find("{", start)
    assert opening_brace != -1, f"Could not find {function_name} opening brace"
    depth = 0
    for index in range(opening_brace, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[opening_brace + 1:index]
    raise AssertionError(f"Could not find {function_name} closing brace")


def _numeric_json_leaf_paths(value, path: str = "$") -> list[str]:
    """Return paths to JSON int/float leaves, excluding bool."""
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [path]
    if isinstance(value, list):
        paths: list[str] = []
        for index, item in enumerate(value):
            paths.extend(_numeric_json_leaf_paths(item, f"{path}[{index}]"))
        return paths
    if isinstance(value, dict):
        paths: list[str] = []
        for key, item in value.items():
            paths.extend(_numeric_json_leaf_paths(item, f"{path}.{key}"))
        return paths
    return []

# ── Known callsite inventory ─────────────────────────────────────────────

# All functions that call run_engine_pipeline() directly.
# If you add a new caller, add it here. This is a fail-closed guard.
# Note: _run_engine_recursive re-implements pipeline logic internally
# (it does NOT call run_engine_pipeline), so it's not in this set.
KNOWN_PIPELINE_CALLERS = {
    "run_engine_with_routing",    # Chains pipeline → hemisphere routing
    "run_engine_pipeline",        # Self-call: trampoline meta path (return_meta=True)
}


# ── AST callsite inventory ───────────────────────────────────────────────


class TestPipelineCallsiteInventory:
    """run_engine_pipeline must only be called from known locations."""

    def test_no_unknown_callers(self):
        """Fail-closed: any new caller must be added to KNOWN_PIPELINE_CALLERS."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_engine_pipeline")
        unknown = actual - KNOWN_PIPELINE_CALLERS
        assert not unknown, (
            f"Unknown run_engine_pipeline callers: {unknown}. "
            "Add to KNOWN_PIPELINE_CALLERS if intentional."
        )

    def test_no_stale_inventory(self):
        """Known callers must actually exist in source."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_engine_pipeline")
        stale = KNOWN_PIPELINE_CALLERS - actual
        assert not stale, (
            f"Stale entries in KNOWN_PIPELINE_CALLERS: {stale}. "
            "Remove if callers were deleted."
        )

    def test_caller_count_locked(self):
        """Exact caller count as documentation."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_engine_pipeline")
        assert len(actual) == 2, (
            f"Expected 2 callers, found {len(actual)}: {actual}"
        )


# ── Pipeline parameter defaults ─────────────────────────────────────────


class TestPipelineDefaults:
    """Pipeline parameter defaults must remain stable."""

    def test_max_engine_iterations_default(self):
        """Default max_engine_iterations must be 20."""
        sig = inspect.signature(run_engine_pipeline)
        param = sig.parameters.get("max_engine_iterations")
        assert param is not None, "max_engine_iterations parameter missing"
        assert param.default == 20, (
            f"max_engine_iterations default changed from 20 to {param.default}"
        )

    def test_observer_default_none(self):
        """Observer must default to None (opt-in only)."""
        sig = inspect.signature(run_engine_pipeline)
        param = sig.parameters.get("observer")
        assert param is not None, "observer parameter missing"
        assert param.default is None, (
            f"observer default changed from None to {param.default}"
        )

    def test_frozen_default_none(self):
        """Frozen must default to None."""
        sig = inspect.signature(run_engine_pipeline)
        param = sig.parameters.get("frozen")
        assert param is not None, "frozen parameter missing"
        assert param.default is None, (
            f"frozen default changed from None to {param.default}"
        )


# ── Stage 4 StructuralNumbers cutover discipline ─────────────────────────


class TestStage4StructuralNumbersCutover:
    """Matcher-facing numeric facts must be structural numerals."""

    def test_migrated_seed_files_have_no_host_numeric_leaves(self):
        seed_paths = [
            _REPO / "mu" / "closures" / "fix.v1.json",
            _REPO / "mu" / "programs" / "rcx_engine.v1.json",
        ]
        offenders: dict[str, list[str]] = {}
        for seed_path in seed_paths:
            paths = _numeric_json_leaf_paths(json.loads(seed_path.read_text()))
            if paths:
                offenders[str(seed_path.relative_to(_REPO))] = paths
        assert not offenders, (
            "Stage 4 seed migration must not leave host int/float JSON leaves: "
            f"{offenders}"
        )

    @pytest.mark.slow
    def test_public_engine_path_rejects_host_numeric_domain_input(self):
        from rcx_pi.selfhost.step_mu import RcxEngineError  # ANTICHEAT_OK: public error type assertion

        projs = [{"id": "t.id", "pattern": {"var": "x"}, "body": {"var": "x"}}]
        with pytest.raises(RcxEngineError, match="stalled"):
            run_engine_pipeline(projs, 7, max_steps=3, use_boot1_recursive=False)

    @pytest.mark.slow
    def test_public_engine_path_accepts_structural_numeral_input(self):
        one = {"_num": {"xH": None}}
        projs = [{"id": "t.id", "pattern": {"var": "x"}, "body": {"var": "x"}}]
        result = run_engine_pipeline(projs, one, max_steps=3, use_boot1_recursive=False)
        assert result["value"] == one


class TestStage4ReentryMaxStepsStructuralDiscipline:
    """Re-entry max_steps must stay exact StructuralNumbers Mu data."""

    @staticmethod
    def _structural_num(n: int) -> dict:
        if n < 0:
            raise ValueError("StructuralNumbers helper requires non-negative integer")
        if n == 0:
            return {"_num": None}
        lower_bits = []
        while n > 1:
            lower_bits.append(n & 1)
            n >>= 1
        node = {"xH": None}
        for bit in reversed(lower_bits):
            node = {"xI": node} if bit else {"xO": node}
        return {"_num": node}

    def test_python_run_trace_over_cap_budget_rejects_before_structural_reduction(self, monkeypatch):
        import rcx_pi.selfhost.engine_pipeline as engine_pipeline
        from rcx_pi.selfhost.engine_pipeline import _service_boundary_effect  # ANTICHEAT_OK: boundary fast-reject regression path
        from rcx_pi.selfhost.step_mu import RcxEngineError  # ANTICHEAT_OK: typed fail-closed assertion

        def reject_structural_step(*args, **kwargs):
            raise AssertionError("over-cap run_trace budget used structural reduction")

        monkeypatch.setattr(engine_pipeline, "_step_trusted", reject_structural_step)
        request = {
            "operation": "run_trace",
            "input": {
                "projections": [
                    {"pattern": "A", "body": "B"},
                    {"pattern": "B", "body": "A"},
                ],
                "value": "A",
                "max_steps": self._structural_num(10001),
            },
            "context": {},
            "inject_key": "trace",
        }
        with pytest.raises(RcxEngineError) as exc:
            _service_boundary_effect(
                request,
                max_algorithm_iterations=10,
                emit_fn=lambda *args, **kwargs: None,
                step=0,
                state={},
            )
        assert exc.value.error_code == "api.bad_request"
        assert "10000" in str(exc.value)

    def test_python_public_max_steps_requires_add_projection_table(self, monkeypatch):
        import rcx_pi.selfhost.engine_pipeline as engine_pipeline
        from rcx_pi.selfhost.step_mu import RcxEngineError  # ANTICHEAT_OK: typed fail-closed assertion

        monkeypatch.setattr(engine_pipeline, "_STRUCTURAL_NUMBER_ADD_PROJECTIONS", ())
        with pytest.raises(RcxEngineError, match="ADD produced malformed numeral") as exc:
            run_engine_pipeline(
                [],
                None,
                max_steps=1,
                max_engine_iterations=2,
                max_algorithm_iterations=1,
                use_boot1_recursive=False,
            )
        assert exc.value.error_code == "execution.invalid_result"

    def test_js_run_trace_over_cap_budget_rejects_without_projection_tables(self):
        import subprocess

        script = """
        const kernel = require('./mu/host/js/engine/kernel');
        kernel.STRUCTURAL_NUMBER_ADD_PROJECTIONS = Object.freeze([]);
        kernel.STRUCTURAL_NUMBER_COMPARE_PROJECTIONS = Object.freeze([]);
        const pipeline = require('./mu/host/js/engine/pipeline');
        function structuralNum(n) {
          if (n === 0) return {_num: null};
          const lowerBits = [];
          while (n > 1) {
            lowerBits.push(n & 1);
            n = Math.floor(n / 2);
          }
          let node = {xH: null};
          for (let i = lowerBits.length - 1; i >= 0; i--) {
            node = lowerBits[i] ? {xI: node} : {xO: node};
          }
          return {_num: node};
        }
        const request = {
          operation: 'run_trace',
          input: {
            projections: [
              {pattern: 'A', body: 'B'},
              {pattern: 'B', body: 'A'}
            ],
            value: 'A',
            max_steps: structuralNum(10001)
          },
          context: {},
          inject_key: 'trace'
        };
        try {
          pipeline.serviceBoundaryEffect([], new Map(), request, 1, () => {}, 0, {}, null);
          console.log(JSON.stringify({ok: true}));
        } catch (e) {
          console.log(JSON.stringify({
            ok: false,
            error_code: e.error_code || null,
            message: e.message
          }));
        }
        """
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert payload["error_code"] == "api.bad_request"
        assert "10000" in payload["message"]

    def test_js_public_max_steps_requires_add_projection_table(self):
        import subprocess

        script = """
        const kernel = require('./mu/host/js/engine/kernel');
        kernel.STRUCTURAL_NUMBER_ADD_PROJECTIONS = Object.freeze([]);
        const pipeline = require('./mu/host/js/engine/pipeline');
        try {
          pipeline.runEnginePipeline([], new Map(), [], [], null, {
            maxSteps: 1,
            maxEngineIterations: 2,
            maxAlgorithmIterations: 1
          });
          console.log(JSON.stringify({ok: true}));
        } catch (e) {
          console.log(JSON.stringify({
            ok: false,
            error_code: e.error_code || null,
            message: e.message
          }));
        }
        """
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert payload["error_code"] == "execution.invalid_result"
        assert "ADD produced malformed numeral" in payload["message"]

    def test_runtime_counter_sources_do_not_reintroduce_host_bit_codecs(self):
        forbidden = (
            "lower_bits",
            "p & 1",
            "p >>=",
            "trace_max_steps +=",
            "weight <<",
            "weight *=",
            "BigInt(",
        )
        offenders: dict[str, list[str]] = {}
        for path in (_PY_STEP_MU_PATH, _STEP_MU_PATH, _JS_KERNEL_PATH, _JS_PIPELINE_PATH):
            text = path.read_text()
            hits = [needle for needle in forbidden if needle in text]
            if hits:
                offenders[str(path.relative_to(_REPO))] = hits
        assert not offenders, (
            "Stage 4 runtime counters must use StructuralNumbers compare/add "
            f"projection helpers, not host bit codecs: {offenders}"
        )

    def test_python_js_structural_number_projection_tables_are_equivalent(self):
        import subprocess
        from rcx_pi.selfhost.eval_seed import step
        from rcx_pi.selfhost.step_mu import (
            STRUCTURAL_NUMBER_ADD_PROJECTIONS,
            STRUCTURAL_NUMBER_COMPARE_PROJECTIONS,
            SN_ONE,
            SN_PROJECTION_STEP_LIMIT,
        )

        def settle(projections, initial):
            current = initial
            from rcx_pi.selfhost.mu_type import mu_hash_control_cached  # ANTICHEAT_OK: projection-settle parity helper
            current_hash = mu_hash_control_cached(current, "test.structural_number.initial")
            for _ in range(SN_PROJECTION_STEP_LIMIT):
                result = step(projections, current)
                result_hash = mu_hash_control_cached(result, "test.structural_number.stall")
                if result_hash == current_hash:
                    return result
                current = result
                current_hash = result_hash
            raise AssertionError("StructuralNumbers projection did not settle")

        py_two = settle(
            STRUCTURAL_NUMBER_ADD_PROJECTIONS,
            {"_add": {"a": SN_ONE, "b": SN_ONE}},
        )
        assert py_two == {"_num": {"xO": {"xH": None}}}
        py_ord = settle(
            STRUCTURAL_NUMBER_COMPARE_PROJECTIONS,
            {"_cmp": {"a": SN_ONE, "b": py_two}},
        )
        assert py_ord == {"_ord": {"lt": None}}

        script = """
        const kernel = require('./mu/host/js/engine/kernel');
        const { _stepTrusted } = require('./mu/host/js/core/bootstrap_core');
        const { muHashControlCached } = require('./mu/host/js/core/types');
        const muContainers = require('./mu/host/js/core/container_factory');
        function settle(projections, initial, context) {
          let current = initial;
          let currentHash = muHashControlCached(current, `${context}.initial`);
          for (let guard = 0; guard < kernel.SN_PROJECTION_STEP_LIMIT; guard++) {
            const result = _stepTrusted(projections, current);
            const resultHash = muHashControlCached(result, `${context}.stall`);
            if (resultHash === currentHash) return result;
            current = result;
            currentHash = resultHash;
          }
          throw new Error(`${context}: did not settle`);
        }
        const two = settle(
          kernel.STRUCTURAL_NUMBER_ADD_PROJECTIONS,
          muContainers.record([['_add', muContainers.record([['a', kernel.SN_ONE], ['b', kernel.SN_ONE]])]]),
          'test.add'
        );
        const ord = settle(
          kernel.STRUCTURAL_NUMBER_COMPARE_PROJECTIONS,
          muContainers.record([['_cmp', muContainers.record([['a', kernel.SN_ONE], ['b', two]])]]),
          'test.compare'
        );
        console.log(JSON.stringify({two, ord}));
        """
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload == {"two": py_two, "ord": py_ord}

    def test_python_reentry_rejects_dirty_structural_max_steps_wrapper(self):
        from rcx_pi.selfhost.engine_pipeline import _validate_reentry_payload  # ANTICHEAT_OK: exported validator parity regression
        from rcx_pi.selfhost.step_mu import RcxEngineError  # ANTICHEAT_OK: typed fail-closed assertion

        dirty_payload = {
            "projections": [],
            "input": None,
            "max_steps": {"_num": None, "extra": True},
        }
        with pytest.raises(RcxEngineError, match="StructuralNumbers numeral") as exc:
            _validate_reentry_payload(dirty_payload, "probe")
        assert exc.value.error_code == "input.invalid_type"

    @pytest.mark.parametrize("digit", ["xO", "xI"])
    def test_python_reentry_rejects_malformed_positive_structural_max_steps_tail(self, digit):
        from rcx_pi.selfhost.engine_pipeline import _validate_reentry_payload  # ANTICHEAT_OK: exported validator parity regression
        from rcx_pi.selfhost.step_mu import RcxEngineError  # ANTICHEAT_OK: typed fail-closed assertion

        dirty_payload = {
            "projections": [],
            "input": None,
            "max_steps": {"_num": {digit: None}},
        }
        with pytest.raises(RcxEngineError, match="malformed StructuralNumbers numeral") as exc:
            _validate_reentry_payload(dirty_payload, "probe")
        assert exc.value.error_code == "input.invalid_type"

    def test_js_reentry_rejects_dirty_structural_max_steps_wrapper(self):
        import subprocess

        script = """
        const pipeline = require('./mu/host/js/engine/pipeline');
        try {
          pipeline.validateReentryPayload(
            {projections: [], input: null, max_steps: {_num: null, extra: true}},
            'probe'
          );
          console.log(JSON.stringify({ok: true}));
        } catch (e) {
          console.log(JSON.stringify({
            ok: false,
            error_code: e.error_code || null,
            message: e.message
          }));
        }
        """
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert payload["error_code"] == "input.invalid_type"
        assert "StructuralNumbers numeral" in payload["message"]

    @pytest.mark.parametrize("digit", ["xO", "xI"])
    def test_js_reentry_rejects_malformed_positive_structural_max_steps_tail(self, digit):
        import subprocess

        script = f"""
        const pipeline = require('./mu/host/js/engine/pipeline');
        try {{
          pipeline.validateReentryPayload(
            {{projections: [], input: null, max_steps: {{_num: {{{digit}: null}}}}}},
            'probe'
          );
          console.log(JSON.stringify({{ok: true}}));
        }} catch (e) {{
          console.log(JSON.stringify({{
            ok: false,
            error_code: e.error_code || null,
            message: e.message
          }}));
        }}
        """
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert payload["error_code"] == "input.invalid_type"
        assert "malformed StructuralNumbers numeral" in payload["message"]

    @pytest.mark.parametrize("digit", ["xO", "xI"])
    def test_python_run_trace_rejects_malformed_positive_structural_max_steps_tail(self, digit):
        from rcx_pi.selfhost.engine_pipeline import _service_boundary_effect  # ANTICHEAT_OK: boundary-handler regression path
        from rcx_pi.selfhost.step_mu import RcxEngineError  # ANTICHEAT_OK: typed fail-closed assertion

        request = {
            "operation": "run_trace",
            "input": {
                "projections": [],
                "value": None,
                "max_steps": {"_num": {digit: None}},
            },
            "context": {},
            "inject_key": "trace",
        }
        with pytest.raises(RcxEngineError, match="malformed StructuralNumbers numeral") as exc:
            _service_boundary_effect(
                request,
                max_algorithm_iterations=1,
                emit_fn=lambda *args, **kwargs: None,
                step=0,
                state={},
            )
        assert exc.value.error_code == "api.bad_request"

    @pytest.mark.parametrize("digit", ["xO", "xI"])
    def test_js_run_trace_rejects_malformed_positive_structural_max_steps_tail(self, digit):
        import subprocess

        script = f"""
        const pipeline = require('./mu/host/js/engine/pipeline');
        const request = {{
          operation: 'run_trace',
          input: {{projections: [], value: null, max_steps: {{_num: {{{digit}: null}}}}}},
          context: {{}},
          inject_key: 'trace'
        }};
        try {{
          pipeline.serviceBoundaryEffect([], new Map(), request, 1, () => {{}}, 0, {{}}, null);
          console.log(JSON.stringify({{ok: true}}));
        }} catch (e) {{
          console.log(JSON.stringify({{
            ok: false,
            error_code: e.error_code || null,
            message: e.message
          }}));
        }}
        """
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert payload["error_code"] == "api.bad_request"
        assert "malformed StructuralNumbers numeral" in payload["message"]

    def test_python_run_trace_rejects_cyclic_structural_max_steps(self):
        from rcx_pi.selfhost.engine_pipeline import _service_boundary_effect  # ANTICHEAT_OK: boundary-handler regression path
        from rcx_pi.selfhost.step_mu import RcxEngineError  # ANTICHEAT_OK: typed fail-closed assertion

        node = {}
        node["xO"] = node
        request = {
            "operation": "run_trace",
            "input": {
                "projections": [],
                "value": None,
                "max_steps": {"_num": node},
            },
            "context": {},
            "inject_key": "trace",
        }
        with pytest.raises(RcxEngineError, match="cyclic StructuralNumbers numeral") as exc:
            _service_boundary_effect(
                request,
                max_algorithm_iterations=1,
                emit_fn=lambda *args, **kwargs: None,
                step=0,
                state={},
            )
        assert exc.value.error_code == "api.bad_request"

    def test_js_run_trace_rejects_cyclic_structural_max_steps(self):
        import subprocess

        script = """
        const pipeline = require('./mu/host/js/engine/pipeline');
        const node = {};
        node.xO = node;
        const request = {
          operation: 'run_trace',
          input: {projections: [], value: null, max_steps: {_num: node}},
          context: {},
          inject_key: 'trace'
        };
        try {
          pipeline.serviceBoundaryEffect([], new Map(), request, 1, () => {}, 0, {}, null);
          console.log(JSON.stringify({ok: true}));
        } catch (e) {
          console.log(JSON.stringify({
            ok: false,
            error_code: e.error_code || null,
            message: e.message
          }));
        }
        """
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert payload["error_code"] == "api.bad_request"
        assert "cyclic StructuralNumbers numeral" in payload["message"]


# ── Observer event contract ──────────────────────────────────────────────

OBSERVER_MANDATORY_FIELDS = {"event_name", "step", "state_hash", "error_code", "substrate", "timestamp"}


class TestObserverEventContract:
    """Observer events must follow a strict schema."""

    @pytest.mark.slow
    def test_observer_events_have_mandatory_fields(self):
        """Every observer event must contain all 6 mandatory fields."""
        observer: list = []
        # Run a minimal pipeline to generate observer events
        projections = [
            {"id": "test.identity", "pattern": {"var": "x"}, "body": {"var": "x"}}
        ]
        run_engine_pipeline(
            projections=projections,
            input_value="payload",
            max_steps=3,
            observer=observer,
        )
        assert len(observer) > 0, "No observer events emitted"
        for i, event in enumerate(observer):
            missing = OBSERVER_MANDATORY_FIELDS - set(event.keys())
            assert not missing, (
                f"Observer event [{i}] missing fields: {missing}. "
                f"Event: {event}"
            )

    @pytest.mark.slow
    def test_observer_substrate_is_python(self):
        """All observer events from Python pipeline must report substrate='python'."""
        observer: list = []
        projections = [
            {"id": "test.identity", "pattern": {"var": "x"}, "body": {"var": "x"}}
        ]
        run_engine_pipeline(
            projections=projections,
            input_value="hello",
            max_steps=3,
            observer=observer,
        )
        for i, event in enumerate(observer):
            assert event.get("substrate") == "python", (
                f"Observer event [{i}] substrate is '{event.get('substrate')}', expected 'python'"
            )

    @pytest.mark.slow
    def test_observer_timestamps_monotonic(self):
        """Observer timestamps must be strictly monotonically increasing."""
        observer: list = []
        projections = [
            {"id": "test.identity", "pattern": {"var": "x"}, "body": {"var": "x"}}
        ]
        run_engine_pipeline(
            projections=projections,
            input_value=["one", "two", "three"],
            max_steps=5,
            observer=observer,
        )
        assert len(observer) >= 2, "Need at least 2 events to check monotonicity"
        for i in range(1, len(observer)):
            assert observer[i]["timestamp"] > observer[i - 1]["timestamp"], (
                f"Timestamps not monotonic at events [{i-1}] and [{i}]: "
                f"{observer[i-1]['timestamp']} >= {observer[i]['timestamp']}"
            )

    @pytest.mark.slow
    def test_observer_step_is_nonnegative(self):
        """Observer step values must be non-negative integers."""
        observer: list = []
        projections = [
            {"id": "test.identity", "pattern": {"var": "x"}, "body": {"var": "x"}}
        ]
        run_engine_pipeline(
            projections=projections,
            input_value={"a": "one"},
            max_steps=3,
            observer=observer,
        )
        for i, event in enumerate(observer):
            assert isinstance(event["step"], int) and event["step"] >= 0, (
                f"Observer event [{i}] step is {event['step']}, expected non-negative int"
            )


# ── Hemisphere routing callsite inventory ────────────────────────────────

# All functions that call run_hemisphere_routing() directly in production.
KNOWN_HEMISPHERE_ROUTING_CALLERS = {
    "run_engine_with_routing",    # Only production caller
}


def _find_callers(source: str, target_func: str) -> set[str]:
    """Find all functions that call target_func() via AST walk."""
    tree = ast.parse(source)
    callers: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        func_name = node.name
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name) and child.func.id == target_func:
                    callers.add(func_name)
    return callers


class TestHemisphereRoutingCallsiteInventory:
    """run_hemisphere_routing must only be called from known locations."""

    def test_no_unknown_callers(self):
        """Fail-closed: any new caller must be added to KNOWN_HEMISPHERE_ROUTING_CALLERS."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_hemisphere_routing")
        unknown = actual - KNOWN_HEMISPHERE_ROUTING_CALLERS
        assert not unknown, (
            f"Unknown run_hemisphere_routing callers: {unknown}. "
            "Add to KNOWN_HEMISPHERE_ROUTING_CALLERS if intentional."
        )

    def test_no_stale_inventory(self):
        """Known callers must actually exist in source."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_hemisphere_routing")
        stale = KNOWN_HEMISPHERE_ROUTING_CALLERS - actual
        assert not stale, (
            f"Stale entries in KNOWN_HEMISPHERE_ROUTING_CALLERS: {stale}. "
            "Remove if callers were deleted."
        )

    def test_caller_count_locked(self):
        """Exactly 1 production caller."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_hemisphere_routing")
        assert len(actual) == 1, (
            f"Expected 1 caller, found {len(actual)}: {actual}"
        )


# ── Engine/hemisphere result shape parity ────────────────────────────────

import re


def _extract_js_set_literal(source: str, var_name: str) -> set[str]:
    """Extract a new Set([...]) constant from JS source."""
    pattern = rf"const\s+{re.escape(var_name)}\s*=\s*new\s+Set\(\[(.*?)\]\)"
    m = re.search(pattern, source, re.DOTALL)
    if not m:
        pytest.fail(f"Could not find {var_name} in eval_step.js")
    block = m.group(1)
    return set(re.findall(r"'([^']+)'", block))


class TestEngineResultShapeParity:
    """Engine terminal keys must match between Python and JS."""

    def test_python_engine_terminal_keys_locked(self):
        """Seed-derived engine terminal keys must have exactly 8 keys."""
        from rcx_pi.selfhost.step_mu import _load_tc_key_sets  # ANTICHEAT_OK: grounding test for engine shape contract
        engine_keys = _load_tc_key_sets()["tc.engine"]
        assert len(engine_keys) == 8, (
            f"Expected 8 engine terminal keys, got {len(engine_keys)}: "
            f"{sorted(engine_keys)}"
        )

    def test_python_engine_terminal_keys_content(self):
        """Seed-derived engine terminal keys must contain the expected keys."""
        from rcx_pi.selfhost.step_mu import _load_tc_key_sets  # ANTICHEAT_OK: grounding test for engine shape contract
        engine_keys = _load_tc_key_sets()["tc.engine"]
        expected = {
            "value", "closure_detected", "tau_step", "exhaustion_detected",
            "operator_frozen", "frozen_set", "action", "stall",
        }
        assert engine_keys == expected, (
            f"Engine terminal keys drift!\n"
            f"  Missing: {expected - engine_keys}\n"
            f"  Extra: {engine_keys - expected}"
        )

    def test_js_engine_terminal_keys_match_python(self):
        """JS ENGINE_TERMINAL_KEYS must match seed-derived Python keys (A7: both seed-derived)."""
        import json as _json
        import subprocess
        from rcx_pi.selfhost.step_mu import _load_tc_key_sets  # ANTICHEAT_OK: grounding test for engine shape contract
        from tests.repo_root import REPO_ROOT
        engine_keys = _load_tc_key_sets()["tc.engine"]
        script = (
            "const tc = require('./mu/host/js/core/terminal_classification');\n"
            "console.log(JSON.stringify([...tc.ENGINE_TERMINAL_KEYS]));\n"
        )
        result = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True,
            cwd=str(REPO_ROOT), timeout=10,
        )
        assert result.returncode == 0, f"JS error: {result.stderr}"
        js_keys = set(_json.loads(result.stdout.strip()))
        assert js_keys == engine_keys, (
            f"Engine terminal key drift!\n"
            f"  Python-only: {engine_keys - js_keys}\n"
            f"  JS-only: {js_keys - engine_keys}"
        )


class TestHemisphereKeysParity:
    """Hemisphere keys must match between Python and JS."""

    def test_python_hemisphere_keys_locked(self):
        """Python hemisphere keys (seed-derived) must have exactly 5 keys."""
        from rcx_pi.selfhost.step_mu import _get_hemisphere_keys  # ANTICHEAT_OK: grounding test for hemisphere shape contract
        hemi_keys = _get_hemisphere_keys()
        assert len(hemi_keys) == 5, (
            f"Expected 5 hemisphere keys, got {len(hemi_keys)}: "
            f"{sorted(hemi_keys)}"
        )

    def test_python_hemisphere_keys_content(self):
        """Python hemisphere keys (seed-derived) must contain the expected keys."""
        from rcx_pi.selfhost.step_mu import _get_hemisphere_keys  # ANTICHEAT_OK: grounding test for hemisphere shape contract
        hemi_keys = _get_hemisphere_keys()
        expected = {"r_null", "r_inf", "r_a", "lobes", "sink"}
        assert hemi_keys == expected, (
            f"Hemisphere keys drift!\n"
            f"  Missing: {expected - hemi_keys}\n"
            f"  Extra: {hemi_keys - expected}"
        )

    def test_js_hemisphere_keys_match_python(self):
        """JS HEMISPHERE_KEYS must match Python exactly."""
        import json
        import subprocess
        from rcx_pi.selfhost.step_mu import _get_hemisphere_keys  # ANTICHEAT_OK: grounding test for hemisphere shape contract
        py_keys = _get_hemisphere_keys()
        result = subprocess.run(
            ["node", "-e",
             "const tc = require('./mu/host/js/core/terminal_classification');\n"
             "console.log(JSON.stringify([...tc.HEMISPHERE_KEYS]));"],
            capture_output=True, text=True,
            cwd=str(Path(__file__).resolve().parents[3]),
            timeout=10,
        )
        assert result.returncode == 0, f"JS error: {result.stderr}"
        js_keys = set(json.loads(result.stdout.strip()))
        assert js_keys == py_keys, (
            f"Hemisphere key drift!\n"
            f"  Python-only: {py_keys - js_keys}\n"
            f"  JS-only: {js_keys - py_keys}"
        )


# ── Pipeline parameter signature lock ────────────────────────────────────


class TestPipelineSignatureLock:
    """All run_engine_pipeline parameter defaults must remain stable."""

    def test_max_steps_default(self):
        sig = inspect.signature(run_engine_pipeline)
        assert sig.parameters["max_steps"].default == 100

    def test_max_algorithm_iterations_default(self):
        sig = inspect.signature(run_engine_pipeline)
        assert sig.parameters["max_algorithm_iterations"].default == 50

    def test_max_iterations_default_none(self):
        sig = inspect.signature(run_engine_pipeline)
        assert sig.parameters["max_iterations"].default is None

    def test_use_boot1_recursive_default_true(self):
        sig = inspect.signature(run_engine_pipeline)
        assert sig.parameters["use_boot1_recursive"].default is True

    def test_keyword_only_after_input_value(self):
        """Parameters after input_value must be keyword-only."""
        sig = inspect.signature(run_engine_pipeline)
        params = list(sig.parameters.values())
        # First two (projections, input_value) are positional-or-keyword
        # Rest must be keyword-only
        for param in params[2:]:
            assert param.kind == inspect.Parameter.KEYWORD_ONLY, (
                f"Parameter '{param.name}' should be keyword-only, "
                f"got {param.kind.name}"
            )


# ── Pipeline return shape contract ───────────────────────────────────────


class TestPipelineReturnContract:
    """run_engine_pipeline must return a dict with exactly 8 terminal keys."""

    @pytest.mark.slow
    def test_return_is_dict(self):
        result = run_engine_pipeline(
            projections=[{"id": "t.id", "pattern": {"var": "x"}, "body": {"var": "x"}}],
            input_value="payload",
            max_steps=3,
            use_boot1_recursive=False,
        )
        assert isinstance(result, dict), f"Expected dict, got {type(result).__name__}"

    @pytest.mark.slow
    def test_return_has_terminal_keys(self):
        from rcx_pi.selfhost.step_mu import _load_tc_key_sets  # ANTICHEAT_OK: grounding test for return shape
        engine_keys = _load_tc_key_sets()["tc.engine"]
        result = run_engine_pipeline(
            projections=[{"id": "t.id", "pattern": {"var": "x"}, "body": {"var": "x"}}],
            input_value="payload",
            max_steps=3,
            use_boot1_recursive=False,
        )
        assert set(result.keys()) == engine_keys, (
            f"Return keys mismatch.\n"
            f"  Missing: {engine_keys - set(result.keys())}\n"
            f"  Extra: {set(result.keys()) - engine_keys}"
        )


# ── Hemisphere routing error paths ───────────────────────────────────────


class TestHemisphereRoutingErrors:
    """run_hemisphere_routing must reject invalid inputs."""

    def test_engine_result_not_dict_raises(self):
        from rcx_pi.selfhost.engine_pipeline import run_hemisphere_routing

        with pytest.raises(ValueError, match="engine_result must be a dict"):
            run_hemisphere_routing("not a dict", {"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None})

    def test_engine_result_list_raises(self):
        from rcx_pi.selfhost.engine_pipeline import run_hemisphere_routing

        with pytest.raises(ValueError, match="engine_result must be a dict"):
            run_hemisphere_routing([1, 2, 3], {"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None})

    def test_engine_result_none_raises(self):
        from rcx_pi.selfhost.engine_pipeline import run_hemisphere_routing

        with pytest.raises(ValueError, match="engine_result must be a dict"):
            run_hemisphere_routing(None, {"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None})


# ── Engine-with-routing validation ───────────────────────────────────────


class TestEngineWithRoutingValidation:
    """run_engine_with_routing must validate hemispheres parameter."""

    def test_hemispheres_not_dict_raises_typeerror(self):
        from rcx_pi.selfhost.engine_pipeline import run_engine_with_routing

        with pytest.raises(TypeError, match="hemispheres must be dict"):
            run_engine_with_routing(
                [{"id": "t.id", "pattern": {"var": "x"}, "body": {"var": "x"}}],
                "payload",
                hemispheres="not a dict",
            )

    def test_hemispheres_missing_keys_raises_valueerror(self):
        from rcx_pi.selfhost.engine_pipeline import run_engine_with_routing

        with pytest.raises(ValueError, match="hemispheres shape mismatch"):
            run_engine_with_routing(
                [{"id": "t.id", "pattern": {"var": "x"}, "body": {"var": "x"}}],
                "payload",
                hemispheres={"r_null": None},  # missing 4 keys
            )

    def test_hemispheres_extra_keys_raises_valueerror(self):
        from rcx_pi.selfhost.engine_pipeline import run_engine_with_routing

        with pytest.raises(ValueError, match="hemispheres shape mismatch"):
            run_engine_with_routing(
                [{"id": "t.id", "pattern": {"var": "x"}, "body": {"var": "x"}}],
                "payload",
                hemispheres={"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None, "extra": None},
            )


# ── Engine-with-routing return shape lock ─────────────────────────────────


class TestEngineWithRoutingReturnShape:
    """run_engine_with_routing must return exactly 2 keys with correct sub-shapes."""

    @pytest.mark.slow
    def test_return_has_exactly_two_keys(self):
        """Return dict must have exactly {engine_result, hemispheres}."""
        from rcx_pi.selfhost.engine_pipeline import run_engine_with_routing

        result = run_engine_with_routing(
            [{"id": "t.id", "pattern": {"var": "x"}, "body": {"var": "x"}}],
            "payload",
            max_steps=3,
        )
        assert set(result.keys()) == {"engine_result", "hemispheres"}, (
            f"Return shape drift! Keys: {sorted(result.keys())}"
        )

    @pytest.mark.slow
    def test_engine_result_has_terminal_keys(self):
        """engine_result sub-dict must have exactly 8 terminal keys."""
        from rcx_pi.selfhost.step_mu import _load_tc_key_sets  # ANTICHEAT_OK: grounding test for terminal key shape
        from rcx_pi.selfhost.engine_pipeline import run_engine_with_routing  # ANTICHEAT_OK: grounding test for return shape
        engine_keys = _load_tc_key_sets()["tc.engine"]
        result = run_engine_with_routing(
            [{"id": "t.id", "pattern": {"var": "x"}, "body": {"var": "x"}}],
            "payload",
            max_steps=3,
        )
        assert set(result["engine_result"].keys()) == engine_keys, (
            f"engine_result sub-shape drift!\n"
            f"  Missing: {engine_keys - set(result['engine_result'].keys())}\n"
            f"  Extra: {set(result['engine_result'].keys()) - engine_keys}"
        )

    @pytest.mark.slow
    def test_hemispheres_has_hemisphere_keys(self):
        """hemispheres sub-dict must have exactly 5 hemisphere keys."""
        from rcx_pi.selfhost.step_mu import _get_hemisphere_keys  # ANTICHEAT_OK: grounding test for hemisphere key shape
        from rcx_pi.selfhost.engine_pipeline import run_engine_with_routing  # ANTICHEAT_OK: grounding test for return shape
        hemi_keys = _get_hemisphere_keys()
        result = run_engine_with_routing(
            [{"id": "t.id", "pattern": {"var": "x"}, "body": {"var": "x"}}],
            "payload",
            max_steps=3,
        )
        assert set(result["hemispheres"].keys()) == hemi_keys, (
            f"hemispheres sub-shape drift!\n"
            f"  Missing: {hemi_keys - set(result['hemispheres'].keys())}\n"
            f"  Extra: {set(result['hemispheres'].keys()) - hemi_keys}"
        )

# ── run_mu callsite inventory ─────────────────────────────────────────────

# All functions that call run_mu() directly in production code.
KNOWN_RUN_MU_CALLERS = {
    "run_metabolization_cycle",  # metabolize_cycle.v1 structural walker
    "_collect_ontology_evidence",  # evidence_walker.v1 trace walker
}


class TestRunMuCallsiteInventory:
    """run_mu must only be called from known locations."""

    def test_no_unknown_callers(self):
        """Fail-closed: any new caller must be added to KNOWN_RUN_MU_CALLERS."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_mu")
        unknown = actual - KNOWN_RUN_MU_CALLERS
        assert not unknown, (
            f"Unknown run_mu callers: {unknown}. "
            "Add to KNOWN_RUN_MU_CALLERS if intentional."
        )

    def test_no_stale_inventory(self):
        """Known callers must actually exist in source."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_mu")
        stale = KNOWN_RUN_MU_CALLERS - actual
        assert not stale, (
            f"Stale entries in KNOWN_RUN_MU_CALLERS: {stale}. "
            "Remove if callers were deleted."
        )

    def test_caller_count_locked(self):
        """Exactly 2 production callers of run_mu."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_mu")
        assert len(actual) == 2, (
            f"Expected 2 run_mu callers, found {len(actual)}: {actual}"
        )


# ── run_mu_structural callsite inventory ──────────────────────────────────

# All functions that call run_mu_structural() directly.
# _boundary_op_run_trace: handler for run_trace boundary op (A10: extracted from _service_boundary_effect)
KNOWN_RUN_MU_STRUCTURAL_CALLERS = {
    "_boundary_op_run_trace",
    "run_hemisphere_routing",  # hemispheres.v1 routing uses structural boundary validation
}


class TestRunMuStructuralCallsiteInventory:
    """run_mu_structural must only be called from known locations."""

    def test_no_unknown_callers(self):
        """Fail-closed: any new caller must be added to KNOWN_RUN_MU_STRUCTURAL_CALLERS."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_mu_structural")
        unknown = actual - KNOWN_RUN_MU_STRUCTURAL_CALLERS
        assert not unknown, (
            f"Unknown run_mu_structural callers: {unknown}. "
            "Add to KNOWN_RUN_MU_STRUCTURAL_CALLERS if intentional."
        )

    def test_no_stale_inventory(self):
        """Known callers must actually exist in source."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_mu_structural")
        stale = KNOWN_RUN_MU_STRUCTURAL_CALLERS - actual
        assert not stale, (
            f"Stale entries in KNOWN_RUN_MU_STRUCTURAL_CALLERS: {stale}. "
            "Remove if callers were deleted."
        )

    def test_caller_count_locked(self):
        """Exactly 2 callers of run_mu_structural."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_mu_structural")
        assert len(actual) == 2, (
            f"Expected 2 run_mu_structural callers, found {len(actual)}: {actual}"
        )


# ── JS JSON API action list parity ────────────────────────────────────────

# Expected JS JSON API actions (22 total, extracted from dispatch branches)
EXPECTED_JS_ACTIONS = {
    "run_vector", "run_all_vectors", "run_recurrence", "run_exhaustion",
    "get_constants", "normalize_roundtrip", "validate_mu",
    "run_recurrence_with_bridge", "run_exhaustion_with_bridge",
    "validate_reserved_fields", "validate_algorithm_runtime_fields",
    "run_structural_trace", "run_hemisphere", "run_engine_pipeline",
    "hash_trace", "run_hemisphere_routing", "run_engine_with_routing",
    "run_metabolization_cycle", "step_metabolization",
    "step_kernel_meta", "run_engine_pipeline_meta",
    "list_actions",
}


def _extract_js_dispatch_actions(source: str) -> set[str]:
    """Extract all action names from request.action === '...' branches."""
    return set(re.findall(r"request\.action\s*===\s*'([^']+)'", source))


def _extract_js_list_actions(source: str) -> set[str]:
    """Extract the actions array from the list_actions response."""
    pattern = r"request\.action\s*===\s*'list_actions'.*?actions:\s*\[(.*?)\]"
    m = re.search(pattern, source, re.DOTALL)
    if not m:
        pytest.fail("Could not find list_actions response in eval_step.js")
    return set(re.findall(r"'([^']+)'", m.group(1)))


class TestJsActionListParity:
    """JS JSON API action dispatch must be self-consistent and locked."""

    def test_action_count_locked(self):
        """JS must have exactly 22 JSON API actions."""
        source = _read_all_js_source()
        actual = _extract_js_dispatch_actions(source)
        assert len(actual) == 22, (
            f"Expected 22 JS actions, found {len(actual)}: {sorted(actual)}"
        )

    def test_dispatch_matches_list_actions(self):
        """Dispatch branches must exactly match list_actions response."""
        source = _read_all_js_source()
        dispatch = _extract_js_dispatch_actions(source)
        listed = _extract_js_list_actions(source)
        dispatch_only = dispatch - listed
        listed_only = listed - dispatch
        assert not dispatch_only and not listed_only, (
            f"JS action list drift!\n"
            f"  In dispatch but not list_actions: {dispatch_only}\n"
            f"  In list_actions but not dispatch: {listed_only}"
        )

    def test_actions_match_expected_set(self):
        """JS actions must match the hardcoded expected set."""
        source = _read_all_js_source()
        actual = _extract_js_dispatch_actions(source)
        missing = EXPECTED_JS_ACTIONS - actual
        extra = actual - EXPECTED_JS_ACTIONS
        assert not missing and not extra, (
            f"JS action set drift!\n"
            f"  Missing: {missing}\n"
            f"  Extra: {extra}"
        )


# ── Boot1 mode routing contract ────────────────────────────────────────


class TestBoot1ModeRoutingContract:
    """Boot1 mode routing must be explicit, observable, and fail-closed.

    Tests that:
    1. Python default is literally False at the AST level (not a variable).
    2. JS boot1LoopMode defaults to false via ?? operator.
    3. Routing is conditional — recursive path gated behind explicit flag.
    4. Observer events differ between paths (observable routing contract).

    These prevent accidental default-flip, unconditional routing bypass,
    and implicit mode changes without observable evidence.
    """

    def test_python_default_is_literal_true_ast(self):
        """Python use_boot1_recursive default must be the literal True at AST level."""
        source = _STEP_MU_PATH.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run_engine_pipeline":
                for arg, default in zip(
                    reversed(node.args.kwonlyargs),
                    reversed(node.args.kw_defaults),
                ):
                    if arg.arg == "use_boot1_recursive":
                        assert isinstance(default, ast.Constant), (
                            f"use_boot1_recursive default must be a literal constant, "
                            f"got {type(default).__name__}"
                        )
                        assert default.value is True, (
                            f"use_boot1_recursive default must be True, "
                            f"got {default.value!r}"
                        )
                        return
                pytest.fail("use_boot1_recursive parameter not found in run_engine_pipeline")
        pytest.fail("run_engine_pipeline function not found in engine_pipeline.py")

    def test_js_boot1_defaults_to_true(self):
        """JS boot1LoopMode must default to true via ?? operator."""
        source = _read_all_js_source()
        assert re.search(r"request\.boot1LoopMode\s*\?\?\s*true", source), (
            "JS must default boot1LoopMode to true via "
            "`request.boot1LoopMode ?? true`"
        )

    def test_python_routing_is_conditional_on_flag(self):
        """_run_engine_recursive call must be inside if use_boot1_recursive branch."""
        source = _STEP_MU_PATH.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run_engine_pipeline":
                for child in ast.walk(node):
                    if isinstance(child, ast.If):
                        if isinstance(child.test, ast.Name) and child.test.id == "use_boot1_recursive":
                            for inner in ast.walk(child):
                                if isinstance(inner, ast.Call):
                                    func = inner.func
                                    if isinstance(func, ast.Name) and func.id == "_run_engine_recursive":
                                        return
                            pytest.fail(
                                "_run_engine_recursive not found inside "
                                "if use_boot1_recursive branch"
                            )
                pytest.fail(
                    "No `if use_boot1_recursive:` branch found in run_engine_pipeline"
                )
        pytest.fail("run_engine_pipeline not found in engine_pipeline.py")

    def test_js_routing_is_conditional_on_boot1mode(self):
        """JS must conditionally route: boot1Mode → recursive vs trampoline."""
        source = _read_all_js_source()
        # Either ternary or if/else is acceptable
        has_ternary = re.search(
            r"boot1Mode\s*\?\s*runEnginePipelineRecursive", source
        )
        has_if_else = re.search(
            r"if\s*\(boot1Mode\)", source
        ) and "runEnginePipelineRecursive" in source and "runEnginePipeline" in source
        assert has_ternary or has_if_else, (
            "JS must route via boot1Mode conditional "
            "(ternary or if/else) to runEnginePipelineRecursive / runEnginePipeline"
        )

    @pytest.mark.slow
    def test_trampoline_observer_has_no_boot1_depth(self):
        """Trampoline path observer events must NOT have boot1_depth field.

        This is the negative half of the observable routing contract:
        if boot1_depth appears on trampoline, routing is not differentiated.
        """
        observer: list = []
        projs = [{"pattern": {"test": {"var": "v"}}, "body": {"var": "v"}}]
        run_engine_pipeline(
            projs, {"test": "payload"},
            max_steps=5, use_boot1_recursive=False, observer=observer,
        )
        assert len(observer) > 0, "No observer events emitted"
        for i, event in enumerate(observer):
            assert "boot1_depth" not in event, (
                f"Trampoline observer event [{i}] has boot1_depth="
                f"{event['boot1_depth']} — boot1_depth must only appear "
                "on recursive path"
            )

    @pytest.mark.slow
    def test_recursive_observer_has_boot1_depth(self):
        """Recursive path step_boundary events must have boot1_depth field.

        This is the positive half of the observable routing contract:
        boot1_depth proves the recursive path was actually taken.
        """
        from rcx_pi.selfhost.kernel import reset_step_budget
        reset_step_budget()
        observer: list = []
        projs = [{"pattern": {"test": {"var": "v"}}, "body": {"var": "v"}}]
        run_engine_pipeline(
            projs, {"test": "payload"},
            max_steps=5, use_boot1_recursive=True, observer=observer,
        )
        step_events = [e for e in observer if e["event_name"] == "step_boundary"]
        assert len(step_events) > 0, "No step_boundary events emitted"
        for i, event in enumerate(step_events):
            assert "boot1_depth" in event, (
                f"Recursive step_boundary event [{i}] missing boot1_depth"
            )
            assert isinstance(event["boot1_depth"], int)
            assert event["boot1_depth"] >= 0


# ── Boot1 type hardening ────────────────────────────────────────────────


class TestBoot1TypeHardening:
    """Non-bool use_boot1_recursive must be rejected fail-closed (TypeError).

    Prevents truthy-string routing bugs: "true" (string) is truthy in Python,
    which would silently route to the recursive path without explicit intent.
    """

    def test_pipeline_rejects_string_true(self):
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError, match="use_boot1_recursive must be bool"):
            run_engine_pipeline(projs, {"x": "one"}, max_steps=5, use_boot1_recursive="true")

    def test_pipeline_rejects_string_false(self):
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError, match="use_boot1_recursive must be bool"):
            run_engine_pipeline(projs, {"x": "one"}, max_steps=5, use_boot1_recursive="false")

    def test_pipeline_rejects_int_one(self):
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError, match="use_boot1_recursive must be bool"):
            run_engine_pipeline(projs, {"x": "one"}, max_steps=5, use_boot1_recursive=1)

    def test_pipeline_rejects_int_zero(self):
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError, match="use_boot1_recursive must be bool"):
            run_engine_pipeline(projs, {"x": "one"}, max_steps=5, use_boot1_recursive=0)

    def test_pipeline_rejects_none(self):
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError, match="use_boot1_recursive must be bool"):
            run_engine_pipeline(projs, {"x": "one"}, max_steps=5, use_boot1_recursive=None)

    def test_routing_rejects_string(self):
        """run_engine_with_routing rejects non-bool use_boot1_recursive."""
        from rcx_pi.selfhost.engine_pipeline import run_engine_with_routing

        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError, match="use_boot1_recursive must be bool"):
            run_engine_with_routing(projs, {"x": "one"}, use_boot1_recursive="true")

    def test_routing_rejects_int(self):
        from rcx_pi.selfhost.engine_pipeline import run_engine_with_routing

        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError, match="use_boot1_recursive must be bool"):
            run_engine_with_routing(projs, {"x": "one"}, use_boot1_recursive=1)


# ── I1: Boundary Mu validation ──────────────────────────────────────────


class TestPipelineBoundaryMuValidation:
    """run_engine_pipeline and _run_engine_recursive reject non-Mu inputs at boundary."""

    def test_pipeline_rejects_nan(self):
        """NaN is not valid Mu — pipeline must reject at entry."""
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError):
            run_engine_pipeline(projs, float("nan"), max_steps=5)

    def test_pipeline_rejects_function(self):
        """Functions are not valid Mu — pipeline must reject at entry."""
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError):
            run_engine_pipeline(projs, lambda x: x, max_steps=5)

    def test_pipeline_rejects_inf(self):
        """Infinity is not valid Mu — pipeline must reject at entry."""
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError):
            run_engine_pipeline(projs, float("inf"), max_steps=5)

    def test_recursive_rejects_nan(self):
        """Boot1 recursive path also validates input at boundary."""
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError):
            run_engine_pipeline(projs, float("nan"), max_steps=5, use_boot1_recursive=True)

    def test_recursive_rejects_function(self):
        """Boot1 recursive path also validates input at boundary."""
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError):
            run_engine_pipeline(projs, lambda x: x, max_steps=5, use_boot1_recursive=True)

    def test_pipeline_accepts_valid_mu(self, monkeypatch):
        """Valid Mu inputs pass public boundary checks without full engine runs."""
        import rcx_pi.selfhost.engine_pipeline as engine_pipeline

        accepted_inputs = []

        def fake_recursive_engine(projections, input_value, **kwargs):
            accepted_inputs.append(input_value)
            return {"value": input_value, "boundary_probe": True}

        monkeypatch.setattr(
            engine_pipeline,
            "_run_engine_recursive",  # ANTICHEAT_OK: boundary-only speed proof; public API remains run_engine_pipeline
            fake_recursive_engine,
        )
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        valid_inputs = [{"x": 1}, 42, None, "hello"]
        for value in valid_inputs:
            # SPEED_OK: _run_engine_recursive is stubbed; this exercises public boundary validation only.
            assert run_engine_pipeline(projs, value, max_steps=5)["value"] == value

        assert accepted_inputs == valid_inputs


# ── I1/I2: Source contract locks for JS boundary checks ─────────────────


class TestJsBoundaryContractLock:
    """JS source must contain explicit boundary checks (fail-closed contract)."""

    def test_js_run_engine_pipeline_has_isvalidmu_check(self):
        """runEnginePipeline must call isValidMu on inputValue."""
        source = _read_all_js_source()
        assert "isValidMu(inputValue)" in source, (
            "runEnginePipeline missing isValidMu(inputValue) boundary check"
        )

    def test_js_run_engine_pipeline_recursive_has_isvalidmu_check(self):
        """runEnginePipelineRecursive must call isValidMu on inputValue."""
        source = _read_all_js_source()
        # Both functions should have the check
        import re
        matches = re.findall(r"function\s+runEnginePipeline(?:Recursive)?\b.*?isValidMu\(inputValue\)", source, re.DOTALL)
        assert len(matches) >= 2, (
            f"Expected isValidMu(inputValue) in both pipeline functions, found {len(matches)}"
        )

    def test_js_validate_seed_uses_key_presence(self):
        """Seed image validation must use 'key' in obj, not falsy checks."""
        source = (_REPO / "mu" / "host" / "js" / "core" / "seed_loader.js").read_text()
        func_body = _extract_js_function_body(source, "loadVerifiedSeedImage")
        assert "'id' in proj" in func_body, "loadVerifiedSeedImage must use key-presence for 'id'"
        assert "'pattern' in proj" in func_body, "loadVerifiedSeedImage must use key-presence for 'pattern'"
        assert "'body' in proj" in func_body, "loadVerifiedSeedImage must use key-presence for 'body'"
        assert "'meta' in seed" in func_body, "loadVerifiedSeedImage must use key-presence for 'meta'"

    def test_js_validate_seed_no_falsy_pattern(self):
        """Old falsy patterns must not exist in seed image validation."""
        source = (_REPO / "mu" / "host" / "js" / "core" / "seed_loader.js").read_text()
        func_body = _extract_js_function_body(source, "loadVerifiedSeedImage")
        assert "!proj.id" not in func_body, "loadVerifiedSeedImage still uses falsy !proj.id"
        assert "!proj.pattern" not in func_body, "loadVerifiedSeedImage still uses falsy !proj.pattern"
        assert "!proj.body" not in func_body, "loadVerifiedSeedImage still uses falsy !proj.body"
        assert "!seed.meta" not in func_body, "loadVerifiedSeedImage still uses falsy !seed.meta"


# ── JS engine pipeline shape governance ─────────────────────────────────


_JS_ENGINE_DIR = _REPO / "mu" / "host" / "js" / "engine"
_JS_CORE_DIR = _REPO / "mu" / "host" / "js" / "core"
_ENGINE_SEED_PATH = _REPO / "mu" / "programs" / "rcx_engine.v1.json"

_REQUIRE_RE = re.compile(r"""\brequire\s*\(\s*['"]([^'"]+)['"]\s*\)""")
_DYNAMIC_REQUIRE_RE = re.compile(r"""\brequire\s*\((?!\s*['"])""")

_EXPECTED_ENGINE_REQUIRES = {
    "routing.js": {
        "../core/constants",
        "../core/container_factory",
        "../core/terminal_classification",
        "./kernel",
        "./pipeline",
    },
    "pipeline.js": {
        "../core/bootstrap_core",
        "../core/constants",
        "../core/container_factory",
        "../core/normalize",
        "../core/security",
        "../core/seed_loader",
        "../core/terminal_classification",
        "../core/types",
        "./kernel",
    },
    "kernel.js": {
        "../core/bootstrap_core",
        "../core/constants",
        "../core/container_factory",
        "../core/normalize",
        "../core/security",
        "../core/stage0_vm",
        "../core/types",
    },
}

_EXPECTED_BOUNDARY_OPS = {"run_trace", "hash_trace", "run_algorithm"}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _require_specs(path: Path) -> list[str]:
    return _REQUIRE_RE.findall(_read_text(path))


def _repo_relative(path: Path) -> str:
    return str(path.relative_to(_REPO))


def _resolve_local_require(path: Path, spec: str) -> Path | None:
    if not spec.startswith("."):
        return None
    resolved = (path.parent / spec).resolve()
    if resolved.suffix != ".js":
        resolved = resolved.with_suffix(".js")
    return resolved


def _scoped_js_files() -> list[Path]:
    return sorted(_JS_CORE_DIR.glob("*.js")) + sorted(_JS_ENGINE_DIR.glob("*.js"))


def _local_dependency_graph() -> dict[Path, list[Path]]:
    scoped = {path.resolve() for path in _scoped_js_files()}
    graph: dict[Path, list[Path]] = {}
    for path in _scoped_js_files():
        deps = {
            resolved
            for spec in _require_specs(path)
            if (resolved := _resolve_local_require(path, spec)) in scoped
        }
        graph[path.resolve()] = sorted(deps)
    return graph


def _find_local_cycles(graph: dict[Path, list[Path]]) -> list[str]:
    color: dict[Path, str] = {}
    stack: list[Path] = []
    cycles: list[str] = []

    def visit(node: Path) -> None:
        color[node] = "gray"
        stack.append(node)
        for dep in graph.get(node, []):
            if color.get(dep) == "gray":
                cycle = stack[stack.index(dep) :] + [dep]
                cycles.append(" -> ".join(_repo_relative(item) for item in cycle))
            elif color.get(dep) is None:
                visit(dep)
        stack.pop()
        color[node] = "black"

    for node in sorted(graph):
        if color.get(node) is None:
            visit(node)
    return cycles


def _seed_boundary_ops() -> set[str]:
    import json

    seed = json.loads(_read_text(_ENGINE_SEED_PATH))
    ops: set[str] = set()
    for projection in seed.get("projections", []):
        body = projection.get("body") if isinstance(projection, dict) else None
        if not isinstance(body, dict):
            continue
        request = body.get("_boundary_request")
        if isinstance(request, dict) and isinstance(request.get("operation"), str):
            ops.add(request["operation"])
    return ops


def _boundary_dispatch_keys(source: str) -> set[str]:
    match = re.search(
        r"const\s+BOUNDARY_DISPATCH\s*=\s*Object\.freeze\(\{(?P<body>.*?)\}\);",
        source,
        re.DOTALL,
    )
    assert match, "BOUNDARY_DISPATCH map is missing from pipeline.js"
    return set(
        re.findall(
            r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*boundaryOp[A-Za-z0-9_]+",
            match.group("body"),
            re.MULTILINE,
        )
    )


def _function_region(source: str, start_name: str, next_name: str) -> str:
    start = source.index(f"function {start_name}")
    end = source.index(f"function {next_name}", start)
    return source[start:end]


class TestJsEnginePipelineShapeGovernance:
    """JS engine module shape must remain a structural guard, not JS semantics."""

    def test_require_scanners_include_whitespace_before_call_paren(self) -> None:
        """Require scanners must catch spaced calls without hiding dynamic imports."""
        static_source = "const fs = require ('fs');\nconst local = require ( './kernel' );"
        dynamic_source = "const moduleName = './kernel';\nconst local = require (moduleName);"

        assert _REQUIRE_RE.findall(static_source) == ["fs", "./kernel"]
        assert _DYNAMIC_REQUIRE_RE.findall(static_source) == []
        assert _DYNAMIC_REQUIRE_RE.findall(dynamic_source) == ["require ("]

    def test_dependency_direction_and_boundary_authority(self) -> None:
        engine_files = {path.name: path for path in _JS_ENGINE_DIR.glob("*.js")}
        assert set(engine_files) == set(_EXPECTED_ENGINE_REQUIRES), (
            "JS engine module set drifted. Helper extraction requires an updated "
            f"governance packet before landing. Actual: {sorted(engine_files)}"
        )

        actual_requires = {
            name: set(_require_specs(path))
            for name, path in sorted(engine_files.items())
        }
        assert actual_requires == _EXPECTED_ENGINE_REQUIRES, (
            "JS engine dependency direction changed.\n"
            f"Expected: {_EXPECTED_ENGINE_REQUIRES}\n"
            f"Actual: {actual_requires}"
        )

        external_engine_requires = {
            name: sorted(spec for spec in _require_specs(path) if not spec.startswith("."))
            for name, path in sorted(engine_files.items())
        }
        assert not any(external_engine_requires.values()), (
            "JS engine modules must not import host bootstrap loaders or Node "
            f"builtins directly: {external_engine_requires}"
        )

        dynamic_requires = {
            name: _DYNAMIC_REQUIRE_RE.findall(_read_text(path))
            for name, path in sorted(engine_files.items())
        }
        assert not any(dynamic_requires.values()), (
            "JS engine modules must keep loader dependencies statically visible: "
            f"{dynamic_requires}"
        )

        graph = _local_dependency_graph()
        cycles = _find_local_cycles(graph)
        assert not cycles, "JS engine/core module graph must stay acyclic: " + "; ".join(cycles)

        kernel_deps = {
            dep.name
            for dep in graph[(_JS_ENGINE_DIR / "kernel.js").resolve()]
            if dep.parent == _JS_ENGINE_DIR
        }
        assert not (kernel_deps & {"pipeline.js", "routing.js"}), (
            "kernel.js must not depend on pipeline.js or routing.js: "
            f"{sorted(kernel_deps)}"
        )

        pipeline_source = _read_text(_JS_ENGINE_DIR / "pipeline.js")
        seed_ops = _seed_boundary_ops()
        assert seed_ops == _EXPECTED_BOUNDARY_OPS, (
            "rcx_engine.v1.json boundary operations drifted; update the governance "
            f"guard only with same-wave seed/projection authority. Actual: {sorted(seed_ops)}"
        )
        assert _boundary_dispatch_keys(pipeline_source) == seed_ops, (
            "BOUNDARY_DISPATCH handlers must match seed-derived boundary operations"
        )
        assert "loadVerifiedSeed('rcx_engine.v1.json', 'programs')" in pipeline_source, (
            "pipeline.js must derive boundary-operation authority from the engine seed"
        )

        service_source = _function_region(
            pipeline_source,
            "serviceBoundaryEffect",
            "validateReentryPayload",
        )
        authority_index = service_source.index("const validOps = _ensureBoundaryOps();")
        dispatch_index = service_source.index(
            "const handler = (testDispatchOverride ?? BOUNDARY_DISPATCH)[operation];"
        )
        assert authority_index < dispatch_index, (
            "Boundary operation authority must be checked before JS handler dispatch"
        )
        assert "validOps.has(operation)" in service_source
        assert "setsEqual(dispatchKeys, validOps)" in service_source
        assert not re.search(r"\bswitch\s*\(\s*operation\s*\)", service_source), (
            "Boundary operations must not move to JS-only switch dispatch"
        )
        assert not re.search(r"operation\s*={2,3}\s*['\"]", service_source), (
            "Boundary operations must not move to JS-only string branch dispatch"
        )
