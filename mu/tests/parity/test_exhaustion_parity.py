"""
Parity tests for exhaustion.v1.json (Rule 3.1 Operator Exhaustion).

These tests verify that the structural exhaustion detection projections
produce correct results for various scenarios.

See: mu/docs/core/OperatorExhaustion.v0.md
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from rcx_pi.selfhost.eval_seed import step
from rcx_pi.selfhost.kernel import reset_step_budget
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
from rcx_pi.selfhost.step_mu import step_kernel_mu
from tests.conftest import run_until_stable

import subprocess

# JSON null -> Python None alias for readability
null = None

# Root directory of the project (symlink-safe — see tests/repo_root.py)
from tests.repo_root import REPO_ROOT as ROOT


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def exhaust_projections() -> list:
    """Load exhaustion projections from seed file."""
    seed = load_verified_seed(get_seed_path("exhaustion.v1.json"))
    return seed["projections"]


@pytest.fixture
def exhaustion_vectors() -> list:
    """Load test vectors from JSON fixture."""
    vectors_path = Path(__file__).parents[1] / "fixtures" / "exhaustion_vectors.json"
    with open(vectors_path) as f:
        data = json.load(f)
    return data["vectors"]


# =============================================================================
# Parity Tests
# =============================================================================


class TestExhaustionParity:
    """Test exhaustion detection against expected vectors."""

    def test_no_tau_continues(self, exhaust_projections, exhaustion_vectors):
        """No tau_step (null) means no exhaustion possible."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.no_tau")
        result = run_until_stable(exhaust_projections, vector["input"])
        assert result == vector["expected"], f"Expected {vector['expected']}, got {result}"

    def test_single_op_exhausted(self, exhaust_projections, exhaustion_vectors):
        """Same operator since tau_step should be frozen."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.single_op_exhausted")
        result = run_until_stable(exhaust_projections, vector["input"])
        assert result == vector["expected"], f"Expected {vector['expected']}, got {result}"

    def test_different_op_not_exhausted(self, exhaust_projections, exhaustion_vectors):
        """Different operator after tau_step means not exhausted."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.different_op")
        result = run_until_stable(exhaust_projections, vector["input"])
        assert result == vector["expected"], f"Expected {vector['expected']}, got {result}"

    def test_already_frozen_skipped(self, exhaust_projections, exhaustion_vectors):
        """Operator already in frozen list should be skipped."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.already_frozen")
        result = run_until_stable(exhaust_projections, vector["input"])
        assert result == vector["expected"], f"Expected {vector['expected']}, got {result}"

    def test_tau_not_found(self, exhaust_projections, exhaustion_vectors):
        """tau_step not found in trace should continue."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.tau_not_found")
        result = run_until_stable(exhaust_projections, vector["input"])
        assert result == vector["expected"], f"Expected {vector['expected']}, got {result}"

    def test_tau_at_end(self, exhaust_projections, exhaustion_vectors):
        """tau_step at end of trace (no subsequent entries) should freeze."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.tau_at_end")
        result = run_until_stable(exhaust_projections, vector["input"])
        assert result == vector["expected"], f"Expected {vector['expected']}, got {result}"


class TestExhaustionStructure:
    """Test that exhaustion detection is structural."""

    def test_projections_are_valid_mu(self, exhaust_projections):
        """All projections must be valid Mu (JSON-compatible)."""
        # If we got here, seed loaded and validated
        assert len(exhaust_projections) == 13, f"Expected 13 projections, got {len(exhaust_projections)}"

    def test_no_python_sets_in_frozen(self, exhaust_projections, exhaustion_vectors):
        """Frozen must be JSON-compatible list, not Python set."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.single_op_exhausted")
        result = run_until_stable(exhaust_projections, vector["input"])

        # Gate 3: Frozen is now denormalized to Python list for backwards compatibility
        # The key invariant: frozen is NOT a Python set (sets aren't JSON-serializable)
        frozen = result.get("frozen")
        assert frozen is not None, "Expected frozen list"
        assert isinstance(frozen, list), "Frozen must be list (not set)"
        assert not isinstance(frozen, set), "Frozen must NOT be Python set"

    def test_projection_order_matters(self, exhaust_projections):
        """Verify first-match-wins ordering for non-linear patterns."""
        # exhaustion.scan_same (non-linear) must come before exhaustion.scan_different
        ids = [p["id"] for p in exhaust_projections]
        same_idx = ids.index("exhaustion.scan_same")
        diff_idx = ids.index("exhaustion.scan_different")
        assert same_idx < diff_idx, "scan_same must come before scan_different"

        # exhaustion.frozen_found (non-linear) must come before exhaustion.frozen_check_tail
        found_idx = ids.index("exhaustion.frozen_found")
        check_idx = ids.index("exhaustion.frozen_check_tail")
        assert found_idx < check_idx, "frozen_found must come before frozen_check_tail"


class TestExhaustionEdgeCases:
    """Edge case tests for exhaustion detection."""

    def test_empty_trace(self, exhaust_projections):
        """Empty trace with tau_step should not crash."""
        reset_step_budget()
        input_data = {
            "_detect_exhaustion": {
                "trace": null,
                "frozen": null,
                "tau_step": 0,
                "operator_ids": null
            }
        }
        # Should not crash - will stall or return continue
        result = run_until_stable(exhaust_projections, input_data)
        # Empty trace means tau_step won't be found → action should be "continue"
        # If stalled at intermediate, must be valid exhaust mode (not random)
        if "action" in result:
            assert result["action"] == "continue", f"Empty trace should continue, got {result}"
        else:
            # Intermediate state must be valid exhaust mode
            assert result.get("_mode") in ("exhaust", "exhaust_find", "exhaust_scan"), \
                f"Invalid intermediate state: {result}"

    def test_multiple_frozen_operators(self, exhaust_projections):
        """Test with multiple operators already frozen."""
        reset_step_budget()
        input_data = {
            "_detect_exhaustion": {
                "trace": {
                    "head": {"step": 0, "state": "A", "projection": "op2"},
                    "tail": {
                        "head": {"step": 1, "state": "B", "projection": "op2"},
                        "tail": null
                    }
                },
                "frozen": {
                    "head": "op1",
                    "tail": {"head": "op3", "tail": null}
                },
                "tau_step": 0,
                "operator_ids": {
                    "head": "op1",
                    "tail": {"head": "op2", "tail": {"head": "op3", "tail": null}}
                }
            }
        }
        result = run_until_stable(exhaust_projections, input_data)
        # op2 is not in frozen list, should be frozen
        assert result.get("exhaustion_detected") is True
        assert result.get("operator_to_freeze") == "op2"
        assert result.get("action") == "freeze"


# =============================================================================
# Cross-Substrate Parity Tests (Python vs JavaScript)
# =============================================================================


def _normalize_for_cross_substrate(value):
    """Normalize Python values for cross-substrate comparison with JS.

    JavaScript doesn't distinguish int/float (all numbers are float64).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return [_normalize_for_cross_substrate(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_for_cross_substrate(v) for k, v in value.items()}
    return value


def _run_js_exhaustion(input_data: dict) -> dict:
    """Run exhaustion detection via JS JSON API."""
    request = {"action": "run_exhaustion", "input": input_data}
    result = subprocess.run(
        ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=60
    )

    for line in result.stdout.split('\n'):
        if line.startswith('JSON_API_RESPONSE:'):
            response = json.loads(line[len('JSON_API_RESPONSE:'):])
            if response.get("success"):
                return response["result"]
            raise RuntimeError(f"JS API error: {response.get('error')}")

    raise RuntimeError(f"No JSON_API_RESPONSE found: {result.stdout[:500]}")


class TestCrossSubstrateExhaustion:
    """Verify Python and JavaScript produce identical exhaustion results."""

    def test_js_loads_exhaustion_seed(self):
        """Verify JS loads exhaustion.v1.json correctly."""
        request = {"action": "get_constants"}
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request)],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60
        )

        for line in result.stdout.split('\n'):
            if line.startswith('JSON_API_RESPONSE:'):
                response = json.loads(line[len('JSON_API_RESPONSE:'):])
                assert response.get("success"), f"API failed: {response}"
                assert response.get("exhaustion_projection_count") == 13, \
                    f"Expected 13 exhaustion projections, got {response.get('exhaustion_projection_count')}"
                return

        pytest.fail("No JSON_API_RESPONSE found")

    def test_cross_substrate_no_tau(self, exhaust_projections, exhaustion_vectors):
        """Cross-substrate: no tau_step produces same result."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.no_tau")

        # Python result
        py_result = run_until_stable(exhaust_projections, vector["input"])

        # JS result
        js_result = _run_js_exhaustion(vector["input"])

        # Normalize and compare
        py_norm = _normalize_for_cross_substrate(py_result)
        js_norm = _normalize_for_cross_substrate(js_result)

        assert json.dumps(py_norm, sort_keys=True) == json.dumps(js_norm, sort_keys=True), \
            f"Cross-substrate mismatch:\nPython: {py_result}\nJS: {js_result}"

    def test_cross_substrate_exhaustion_detected(self, exhaust_projections, exhaustion_vectors):
        """Cross-substrate: exhaustion detection produces same result."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.single_op_exhausted")

        py_result = run_until_stable(exhaust_projections, vector["input"])
        js_result = _run_js_exhaustion(vector["input"])

        py_norm = _normalize_for_cross_substrate(py_result)
        js_norm = _normalize_for_cross_substrate(js_result)

        assert json.dumps(py_norm, sort_keys=True) == json.dumps(js_norm, sort_keys=True), \
            f"Cross-substrate mismatch:\nPython: {py_result}\nJS: {js_result}"

    def test_cross_substrate_different_op(self, exhaust_projections, exhaustion_vectors):
        """Cross-substrate: different operator produces same result."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.different_op")

        py_result = run_until_stable(exhaust_projections, vector["input"])
        js_result = _run_js_exhaustion(vector["input"])

        py_norm = _normalize_for_cross_substrate(py_result)
        js_norm = _normalize_for_cross_substrate(js_result)

        assert json.dumps(py_norm, sort_keys=True) == json.dumps(js_norm, sort_keys=True), \
            f"Cross-substrate mismatch:\nPython: {py_result}\nJS: {js_result}"

    def test_cross_substrate_already_frozen(self, exhaust_projections, exhaustion_vectors):
        """Cross-substrate: already frozen produces same result."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.already_frozen")

        py_result = run_until_stable(exhaust_projections, vector["input"])
        js_result = _run_js_exhaustion(vector["input"])

        py_norm = _normalize_for_cross_substrate(py_result)
        js_norm = _normalize_for_cross_substrate(js_result)

        assert json.dumps(py_norm, sort_keys=True) == json.dumps(js_norm, sort_keys=True), \
            f"Cross-substrate mismatch:\nPython: {py_result}\nJS: {js_result}"

    def test_cross_substrate_all_vectors(self, exhaust_projections, exhaustion_vectors):
        """Cross-substrate: all exhaustion vectors produce same results."""
        mismatches = []

        for vector in exhaustion_vectors:
            py_result = run_until_stable(exhaust_projections, vector["input"])
            try:
                js_result = _run_js_exhaustion(vector["input"])
            except Exception as e:
                mismatches.append(f"{vector['id']}: JS error - {e}")
                continue

            py_norm = _normalize_for_cross_substrate(py_result)
            js_norm = _normalize_for_cross_substrate(js_result)

            if json.dumps(py_norm, sort_keys=True) != json.dumps(js_norm, sort_keys=True):
                mismatches.append(f"{vector['id']}: Python={py_result}, JS={js_result}")

        assert not mismatches, f"Cross-substrate mismatches:\n" + "\n".join(mismatches)

# ---------------------------------------------------------------------------
# D006 JavaScript structural fuel-threading parity proof
# ---------------------------------------------------------------------------


def _load_research_module(relative_path: str, module_name: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader, f"unable to load {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D006 = _load_research_module(
    "tests/research/test_d006_h1_fuel_threading.py",
    "d006_h1_fuel_threading_reference",
)
D007 = _load_research_module(
    "tests/research/test_d007_h3_negative_control.py",
    "d007_h3_negative_control_reference",
)


JS_D006_FUEL_BRIDGE = r"""
const fs = require('fs');
const { step } = require('./mu/host/js/core/bootstrap_core');
const { muHashCached } = require('./mu/host/js/core/types');
const muContainers = require('./mu/host/js/core/container_factory');

function trustMu(value) {
  if (Array.isArray(value)) {
    return muContainers.list(value.map(item => trustMu(item)));
  }
  if (value !== null && typeof value === 'object') {
    return muContainers.record(Object.keys(value).map(key => [key, trustMu(value[key])]));
  }
  return value;
}

function makeFuel(n) {
  let fuel = null;
  for (let i = 0; i < n; i++) {
    fuel = muContainers.record([['head', null], ['tail', fuel]]);
  }
  return fuel;
}

function fuelRemaining(fuel) {
  let count = 0;
  let cursor = fuel;
  while (cursor !== null) {
    if (typeof cursor !== 'object' || !Object.hasOwn(cursor, 'head') || !Object.hasOwn(cursor, 'tail')) {
      throw new Error('fuel must be a Mu linked list');
    }
    count += 1;
    cursor = cursor.tail;
  }
  return count;
}

function fuelStep(projections, state, fuel, counters) {
  if (fuel === null) {
    return { state, fuel: null, status: 'fuel_exhausted' };
  }

  counters.stepCalls += 1;
  const newState = step(projections, state);
  const remaining = fuel.tail;

  if (muHashCached(newState) === muHashCached(state)) {
    return { state: newState, fuel: remaining, status: 'stall' };
  }

  return { state: newState, fuel: remaining, status: 'ok' };
}

function fuelRun(projections, state, fuel) {
  const counters = { stepCalls: 0 };
  const trace = [];
  const statuses = [];
  const remainingCounts = [fuelRemaining(fuel)];
  let current = state;
  let currentFuel = fuel;
  let i = 0;

  while (true) {
    trace.push({ step: i, value: current });
    const result = fuelStep(projections, current, currentFuel, counters);
    currentFuel = result.fuel;
    statuses.push(result.status);
    remainingCounts.push(fuelRemaining(currentFuel));

    if (result.status === 'stall') {
      trace.push({ step: i + 1, value: result.state, stall: true });
      return {
        finalState: result.state,
        reason: 'stall',
        trace,
        stateSequence: trace.map(entry => entry.value),
        statuses,
        remainingCounts,
        remainingFuel: fuelRemaining(currentFuel),
        stepCalls: counters.stepCalls,
      };
    }

    if (result.status === 'fuel_exhausted') {
      return {
        finalState: current,
        reason: 'fuel_exhausted',
        trace,
        stateSequence: trace.map(entry => entry.value),
        statuses,
        remainingCounts,
        remainingFuel: fuelRemaining(currentFuel),
        stepCalls: counters.stepCalls,
      };
    }

    current = result.state;
    i += 1;
  }
}

function singleStepRun(projections, state) {
  return step(projections, state);
}

function unrolledRun3(projections, state) {
  const s1 = step(projections, state);
  const s2 = step(projections, s1);
  const s3 = step(projections, s2);
  return s3;
}

function unrolledRun5(projections, state) {
  const s1 = step(projections, state);
  const s2 = step(projections, s1);
  const s3 = step(projections, s2);
  const s4 = step(projections, s3);
  const s5 = step(projections, s4);
  return s5;
}

function recursiveRun(projections, state) {
  const result = step(projections, state);
  if (muHashCached(result) === muHashCached(state)) {
    return result;
  }
  return recursiveRun(projections, result);
}

function composeN(fn, n) {
  return function composed(x) {
    let result = x;
    for (let i = 0; i < n; i++) {
      result = fn(result);
    }
    return result;
  };
}

function runNegativeControls() {
  const multiProjections = trustMu([
    { id: 'multi.1', pattern: { phase: 'a' }, body: { phase: 'b' } },
    { id: 'multi.2', pattern: { phase: 'b' }, body: { phase: 'c' } },
    { id: 'multi.3', pattern: { phase: 'c' }, body: { phase: 'done' } },
  ]);
  const chainProjections = trustMu([
    { id: 'chain.1', pattern: { n: 0 }, body: { n: 1 } },
    { id: 'chain.2', pattern: { n: 1 }, body: { n: 2 } },
    { id: 'chain.3', pattern: { n: 2 }, body: { n: 3 } },
    { id: 'chain.4', pattern: { n: 3 }, body: { n: 4 } },
    { id: 'chain.5', pattern: { n: 4 }, body: { n: 5 } },
  ]);
  const chainStep = state => step(chainProjections, state);
  const recursiveSource = recursiveRun.toString();

  return {
    singleMulti: singleStepRun(multiProjections, trustMu({ phase: 'a' })),
    singleChain: singleStepRun(chainProjections, trustMu({ n: 0 })),
    unrolled3Multi: unrolledRun3(multiProjections, trustMu({ phase: 'a' })),
    unrolled3Chain: unrolledRun3(chainProjections, trustMu({ n: 0 })),
    unrolled5Multi: unrolledRun5(multiProjections, trustMu({ phase: 'a' })),
    recursiveMulti: recursiveRun(multiProjections, trustMu({ phase: 'a' })),
    recursiveSourceHasSelfCall: /return recursiveRun\(/.test(recursiveSource),
    recursiveSourceHasFuel: /\bfuel\b/.test(recursiveSource),
    recursiveSourceHasBound: /\bbound\b|\bmaxSteps\b|\blimit\b/.test(recursiveSource),
    compose3Chain: composeN(chainStep, 3)(trustMu({ n: 0 })),
    compose5Chain: composeN(chainStep, 5)(trustMu({ n: 0 })),
    composeSourceHasLoop: /for\s*\(/.test(composeN.toString()),
  };
}

function sourceProof() {
  const fuelStepSource = fuelStep.toString();
  const fuelRunSource = fuelRun.toString();
  const stepCallMatches = fuelStepSource.match(/\bstep\s*\(/g) || [];
  return {
    fuelShapeThree: makeFuel(3),
    fuelStepCallsStepCount: stepCallMatches.length,
    fuelStepMentionsFuelExhausted: fuelStepSource.includes('fuel_exhausted'),
    fuelRunHasWhile: /while\s*\(/.test(fuelRunSource),
  };
}

const request = JSON.parse(fs.readFileSync(0, 'utf8'));

if (request.action === 'fuel_run') {
  const projections = trustMu(request.projections);
  const state = trustMu(request.state);
  process.stdout.write(JSON.stringify(fuelRun(projections, state, makeFuel(request.fuelCount))));
} else if (request.action === 'source_proof') {
  process.stdout.write(JSON.stringify(sourceProof()));
} else if (request.action === 'negative_controls') {
  process.stdout.write(JSON.stringify(runNegativeControls()));
} else {
  throw new Error(`unknown action: ${request.action}`);
}
"""


def _run_js_d006_fuel_bridge(input_value: dict) -> dict:
    result = subprocess.run(
        ["node", "-e", JS_D006_FUEL_BRIDGE],
        input=json.dumps(input_value),
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _make_js_kernel_fuel(count: int):
    fuel = None
    for _ in range(count):
        fuel = {"head": None, "tail": fuel}
    return fuel


def _js_kernel_fuel_remaining_count(fuel) -> int:
    count = 0
    cursor = fuel
    while cursor is not None:
        assert isinstance(cursor, dict), f"fuel cursor must be dict/null, got {type(cursor).__name__}"
        assert set(cursor) == {"head", "tail"}
        count += 1
        cursor = cursor["tail"]
    return count


def _run_js_step_kernel_meta_response(payload: dict) -> dict:
    result = subprocess.run(
        ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(payload)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    marker = "JSON_API_RESPONSE:"
    idx = result.stdout.find(marker)
    assert idx >= 0, f"No JSON_API_RESPONSE in output: {result.stdout[-200:]}"
    return json.loads(result.stdout[idx + len(marker):].strip())


def _run_js_step_kernel_meta(payload: dict) -> dict:
    response = _run_js_step_kernel_meta_response(payload)
    assert response.get("success"), response.get("error")
    return response["result"]


def _assert_js_kernel_fuel_success_matches_python(
    projections,
    state,
    fuel_count: int,
    max_steps: int = 100,
) -> dict:
    js_meta = _run_js_step_kernel_meta({
        "action": "step_kernel_meta",
        "projections": projections,
        "input": state,
        "maxSteps": max_steps,
        "kernelFuel": _make_js_kernel_fuel(fuel_count),
    })
    py_meta = step_kernel_mu(
        projections,
        state,
        return_meta=True,
        max_steps=max_steps,
        kernel_fuel=_make_js_kernel_fuel(fuel_count),
    )

    shared_fields = ("output", "stall", "termination_reason", "steps_used", "max_steps")
    for field in shared_fields:
        assert js_meta[field] == py_meta[field], field
    assert js_meta["fuel_supplied"] is True
    assert py_meta["fuel_supplied"] is True
    assert js_meta["fuel_exhausted"] is False
    assert py_meta["fuel_exhausted"] is False
    assert _js_kernel_fuel_remaining_count(js_meta["fuel_remaining"]) == (
        fuel_count - py_meta["steps_used"]
    )
    assert _js_kernel_fuel_remaining_count(py_meta["fuel_remaining"]) == (
        fuel_count - py_meta["steps_used"]
    )
    return js_meta


def _assert_js_kernel_fuel_exhaustion_matches_python_budget(
    projections,
    state,
    fuel_count: int,
    max_steps: int = 100,
) -> dict:
    js_meta = _run_js_step_kernel_meta({
        "action": "step_kernel_meta",
        "projections": projections,
        "input": state,
        "maxSteps": max_steps,
        "kernelFuel": _make_js_kernel_fuel(fuel_count),
    })
    py_meta = step_kernel_mu(
        projections,
        state,
        return_meta=True,
        max_steps=max_steps,
        kernel_fuel=_make_js_kernel_fuel(fuel_count),
    )

    assert js_meta["output"] == py_meta["output"]
    assert js_meta["stall"] == py_meta["stall"] is True
    assert js_meta["steps_used"] == py_meta["steps_used"] == fuel_count
    assert js_meta["termination_reason"] == "fuel_exhausted"
    assert py_meta["termination_reason"] == "fuel_exhausted"
    assert js_meta["max_steps"] == py_meta["max_steps"] == max_steps
    assert js_meta["fuel_supplied"] is True
    assert py_meta["fuel_supplied"] is True
    assert js_meta["fuel_remaining"] is None
    assert py_meta["fuel_remaining"] is None
    assert js_meta["fuel_exhausted"] is True
    assert py_meta["fuel_exhausted"] is True
    return js_meta


def _python_d006_fuel_run_observed(projections, state, fuel_count: int) -> dict:
    fuel = D006.make_fuel(fuel_count)
    trace = []
    statuses = []
    remaining_counts = [D006.fuel_remaining(fuel)]
    current = state
    step_calls = 0
    i = 0

    while True:
        trace.append({"step": i, "value": current})
        fuel_before = fuel
        new_state, fuel, status = D006.fuel_step(projections, current, fuel)
        if fuel_before is not None:
            step_calls += 1
        statuses.append(status)
        remaining_counts.append(D006.fuel_remaining(fuel))

        if status == "stall":
            trace.append({"step": i + 1, "value": new_state, "stall": True})
            return {
                "finalState": new_state,
                "reason": "stall",
                "trace": trace,
                "stateSequence": [entry["value"] for entry in trace],
                "statuses": statuses,
                "remainingCounts": remaining_counts,
                "remainingFuel": D006.fuel_remaining(fuel),
                "stepCalls": step_calls,
            }

        if status == "fuel_exhausted":
            return {
                "finalState": current,
                "reason": "fuel_exhausted",
                "trace": trace,
                "stateSequence": [entry["value"] for entry in trace],
                "statuses": statuses,
                "remainingCounts": remaining_counts,
                "remainingFuel": D006.fuel_remaining(fuel),
                "stepCalls": step_calls,
            }

        current = new_state
        i += 1


def _js_d006_fuel_run(projections, state, fuel_count: int) -> dict:
    return _run_js_d006_fuel_bridge(
        {
            "action": "fuel_run",
            "projections": projections,
            "state": state,
            "fuelCount": fuel_count,
        }
    )


def _assert_js_matches_python_d006_fuel(projections, state, fuel_count: int) -> dict:
    expected = _python_d006_fuel_run_observed(projections, state, fuel_count)
    actual = _js_d006_fuel_run(projections, state, fuel_count)
    assert actual == expected
    assert set(actual["statuses"]) <= {"ok", "stall", "fuel_exhausted"}
    return actual


def _extract_js_function(source: str, name: str) -> str:
    match = re.search(rf"function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", source)
    assert match, f"{name} not found"
    depth = 0
    for index in range(match.end() - 1, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : index + 1]
    raise AssertionError(f"{name} body was not closed")


@pytest.mark.parametrize(
    ("name", "projections", "state", "fuel_count", "reason", "final_state"),
    [
        ("identity_stall", D006.V1_PROJECTIONS, D006.V1_INPUT, 10, "stall", D006.V1_INPUT),
        (
            "single_match",
            D006.V2_PROJECTIONS,
            D006.V2_INPUT,
            10,
            "stall",
            {"status": "done", "value": 1},
        ),
        (
            "multi_step_convergence",
            D006.V3_PROJECTIONS,
            D006.V3_INPUT,
            10,
            "stall",
            {"phase": "done"},
        ),
        (
            "fuel_exhaustion",
            D006.V4_PROJECTIONS,
            D006.V4_INPUT,
            D006.V4_FUEL,
            "fuel_exhausted",
            {"n": 3},
        ),
        (
            "nested_mu_structure",
            D006.V5_PROJECTIONS,
            D006.V5_INPUT,
            10,
            "stall",
            {"result": "unwrapped", "depth": 2},
        ),
        ("zero_fuel", D006.V2_PROJECTIONS, D006.V2_INPUT, 0, "fuel_exhausted", D006.V2_INPUT),
        ("one_fuel", D006.V3_PROJECTIONS, D006.V3_INPUT, 1, "fuel_exhausted", {"phase": "b"}),
    ],
)
def test_js_d006_fuel_run_matches_python_research_vectors(
    name,
    projections,
    state,
    fuel_count,
    reason,
    final_state,
):
    result = _assert_js_matches_python_d006_fuel(projections, state, fuel_count)
    assert result["reason"] == reason, name
    assert result["finalState"] == final_state, name


def test_js_d006_fuel_consumption_is_structural_and_monotonic():
    result = _assert_js_matches_python_d006_fuel(D006.V3_PROJECTIONS, D006.V3_INPUT, 5)
    deltas = [
        before - after
        for before, after in zip(result["remainingCounts"], result["remainingCounts"][1:])
    ]
    assert deltas == [1, 1, 1, 1]
    assert result["remainingFuel"] == 1


def test_js_d006_fuel_adapter_calls_existing_step_once_per_fuel_node():
    result = _assert_js_matches_python_d006_fuel(D006.V3_PROJECTIONS, D006.V3_INPUT, 10)
    proof = _run_js_d006_fuel_bridge({"action": "source_proof"})
    assert result["stepCalls"] == len(result["statuses"])
    assert result["stepCalls"] == result["remainingCounts"][0] - result["remainingCounts"][-1]
    assert proof["fuelStepCallsStepCount"] == 1


def test_js_d006_production_step_kernel_meta_consumes_kernel_fuel_nodes():
    fuel_count = 3
    meta = _assert_js_kernel_fuel_exhaustion_matches_python_budget(
        D006.V3_PROJECTIONS,
        D006.V3_INPUT,
        fuel_count,
        max_steps=fuel_count,
    )
    assert meta["termination_reason"] == "fuel_exhausted"
    assert meta["stall"] is True
    assert meta["steps_used"] == fuel_count
    assert meta["fuel_supplied"] is True
    assert meta["fuel_remaining"] is None
    assert meta["fuel_exhausted"] is True


def test_js_d006_production_step_kernel_meta_reports_remaining_kernel_fuel():
    fuel_count = 80
    meta = _assert_js_kernel_fuel_success_matches_python(
        D006.V2_PROJECTIONS,
        D006.V2_INPUT,
        fuel_count,
    )
    assert meta["termination_reason"] == "projection_applied"
    assert meta["stall"] is False
    assert meta["output"] == {"status": "done", "value": 1}
    assert meta["fuel_supplied"] is True
    assert meta["fuel_exhausted"] is False
    assert 0 < meta["steps_used"] < fuel_count
    assert _js_kernel_fuel_remaining_count(meta["fuel_remaining"]) == fuel_count - meta["steps_used"]


def test_js_d006_production_step_kernel_meta_rejects_bad_kernel_fuel():
    response = _run_js_step_kernel_meta_response({
        "action": "step_kernel_meta",
        "projections": D006.V2_PROJECTIONS,
        "input": D006.V2_INPUT,
        "maxSteps": 100,
        "kernelFuel": {"head": None, "tail": 0},
    })
    assert response["success"] is False
    assert response["error_code"] == "api.bad_request"
    assert "kernelFuel" in response["error"]
    with pytest.raises(TypeError, match="kernel_fuel"):
        step_kernel_mu(
            D006.V2_PROJECTIONS,
            D006.V2_INPUT,
            return_meta=True,
            max_steps=100,
            kernel_fuel={"head": None, "tail": 0},
        )


def test_js_d006_production_default_path_has_no_kernel_fuel_metadata():
    meta = _run_js_step_kernel_meta({
        "action": "step_kernel_meta",
        "projections": D006.V2_PROJECTIONS,
        "input": D006.V2_INPUT,
        "maxSteps": 100,
    })
    assert meta["termination_reason"] == "projection_applied"
    assert {"fuel_supplied", "fuel_remaining", "fuel_exhausted"}.isdisjoint(meta)


def test_js_d006_step_path_does_not_inspect_fuel():
    step_source = _extract_js_function(
        (ROOT / "mu/host/js/core/bootstrap_core.js").read_text(),
        "step",
    )
    identifiers = set(re.findall(r"\b[A-Za-z_]\w*\b", step_source))
    assert not ({"fuel", "head", "tail", "fuelRemaining"} & identifiers)


def test_js_d006_fuel_is_mu_linked_list_not_integer_counter():
    proof = _run_js_d006_fuel_bridge({"action": "source_proof"})
    assert proof["fuelShapeThree"] == {
        "head": None,
        "tail": {"head": None, "tail": {"head": None, "tail": None}},
    }
    assert proof["fuelStepMentionsFuelExhausted"] is True
    assert "request.fuelCount--" not in JS_D006_FUEL_BRIDGE
    assert "fuel -= 1" not in JS_D006_FUEL_BRIDGE


def test_js_d006_fuel_parity_harness_rejects_host_escape_mechanisms():
    for forbidden in (
        "setTimeout",
        "setInterval",
        "Date.now",
        "performance.",
        "process.hrtime",
        "worker_threads",
        "Worker(",
        "Atomics.wait",
        "constructor.name",
        "catchTable",
        "exceptionTable",
        "new Set",
        "acceptedStatuses",
        "acceptedResults",
        "allowedResults",
    ):
        assert forbidden not in JS_D006_FUEL_BRIDGE


def test_js_d006_single_step_negative_control_fails_multi_step():
    controls = _run_js_d006_fuel_bridge({"action": "negative_controls"})
    assert controls["singleMulti"] == D007.single_step_run(D007.MULTI_PROJECTIONS, D007.MULTI_INPUT)
    assert controls["singleMulti"] != D007.MULTI_EXPECTED
    assert controls["singleMulti"] == {"phase": "b"}
    assert controls["singleChain"] == {"n": 1}


def test_js_d006_fixed_unroll_negative_control_is_not_general():
    controls = _run_js_d006_fuel_bridge({"action": "negative_controls"})
    assert controls["unrolled3Multi"] == D007.unrolled_run_3(D007.MULTI_PROJECTIONS, D007.MULTI_INPUT)
    assert controls["unrolled3Multi"] == D007.MULTI_EXPECTED
    assert controls["unrolled3Chain"] == D007.unrolled_run_3(D007.CHAIN_PROJECTIONS, D007.CHAIN_INPUT)
    assert controls["unrolled3Chain"] != D007.CHAIN_EXPECTED
    assert controls["unrolled3Chain"] == {"n": 3}
    assert controls["unrolled5Multi"] == D007.unrolled_run_5(D007.MULTI_PROJECTIONS, D007.MULTI_INPUT)


def test_js_d006_recursion_negative_control_is_host_iteration_not_structural_fuel():
    controls = _run_js_d006_fuel_bridge({"action": "negative_controls"})
    assert controls["recursiveMulti"] == D007.recursive_run(D007.MULTI_PROJECTIONS, D007.MULTI_INPUT)
    assert controls["recursiveMulti"] == D007.MULTI_EXPECTED
    assert controls["recursiveSourceHasSelfCall"] is True
    assert controls["recursiveSourceHasFuel"] is False
    assert controls["recursiveSourceHasBound"] is False


def test_js_d006_compose_n_negative_control_exposes_host_iteration():
    controls = _run_js_d006_fuel_bridge({"action": "negative_controls"})
    step_fn = lambda state: D007.step_mu(D007.CHAIN_PROJECTIONS, state)  # noqa: E731
    assert controls["compose3Chain"] == D007.compose_n(step_fn, 3)(D007.CHAIN_INPUT)
    assert controls["compose3Chain"] != D007.CHAIN_EXPECTED
    assert controls["compose5Chain"] == D007.compose_n(step_fn, 5)(D007.CHAIN_INPUT)
    assert controls["compose5Chain"] == D007.CHAIN_EXPECTED
    assert controls["composeSourceHasLoop"] is True
