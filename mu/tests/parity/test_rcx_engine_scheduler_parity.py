"""Python/JS parity for the rcx_engine_scheduler run_algorithm seed path."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from rcx_pi.selfhost.engine_pipeline import _service_boundary_effect  # ANTICHEAT_OK: parity probe for boundary dispatch path
from tests.repo_root import REPO_ROOT


SCHEDULER_SEED_NAME = "rcx_engine_scheduler.v1.json"
FIXTURE_PATH = REPO_ROOT / "mu" / "tests" / "fixtures" / "rcx_enginenew_scheduler_operator_pool.json"
SLOW_SCHEDULER_JS_TIMEOUT_SECONDS = 180


def _has_slow_mark(obj):
    marks = getattr(obj, "pytestmark", [])
    if not isinstance(marks, (list, tuple)):
        marks = [marks]
    return any(getattr(mark, "name", None) == "slow" for mark in marks)


def _load_vector(vector_id: str) -> dict:
    vectors = json.loads(FIXTURE_PATH.read_text())["vectors"]
    return next(v for v in vectors if v["id"] == vector_id)


def _request(input_value: dict) -> dict:
    return {
        "operation": "run_algorithm",
        "algorithm": SCHEDULER_SEED_NAME,
        "input": input_value,
        "context": {
            "parity_probe": "scheduler_seed_path"
        },
        "inject_key": "scheduler_result",
    }


def _run_python_scheduler(input_value: dict) -> dict:
    events = []

    def emit(event_name, step, state, error_code=None, **extra):
        events.append({
            "event_name": event_name,
            "step": step,
            "state": state,
            "error_code": error_code,
            **extra,
        })

    result = _service_boundary_effect(
        _request(input_value),
        max_algorithm_iterations=8,
        emit_fn=emit,
        step=0,
        state={"test": "scheduler"},
    )
    assert events == []
    return result["scheduler_result"]


def _run_js_scheduler(input_value: dict, *, timeout: int = 60) -> dict:
    script = r"""
const fs = require('fs');
const path = require('path');
const pipeline = require('./mu/host/js/engine/pipeline');
const { muCopy } = require('./mu/host/js/core/stage0_vm');

function loadProjections(relPath) {
  return muCopy(
    JSON.parse(fs.readFileSync(path.join(process.cwd(), relPath), 'utf8')).projections,
    true,
    `scheduler parity projections ${relPath}`
  );
}

const kernel = loadProjections('mu/substrate/kernel.v1.json');
const bridge = loadProjections('mu/bridge/bootstrap_structural.v1.json');
const match = loadProjections('mu/substrate/match.v2.json');
const subst = loadProjections('mu/substrate/subst.v2.json');
const allProjectionsWithBridge = [...kernel, ...bridge, ...match, ...subst];
const inputValue = muCopy(JSON.parse(process.argv[1]), true, 'scheduler parity input');

const request = {
  operation: 'run_algorithm',
  algorithm: 'rcx_engine_scheduler.v1.json',
  input: inputValue,
  context: { parity_probe: 'scheduler_seed_path' },
  inject_key: 'scheduler_result',
};

const result = pipeline.serviceBoundaryEffect(
  allProjectionsWithBridge,
  Object.create(null),
  request,
  8,
  () => {},
  0,
  { test: 'scheduler' },
  null
);
console.log(JSON.stringify({ success: true, result: result.scheduler_result }));
"""
    proc = subprocess.run(
        ["node", "-e", script, json.dumps(input_value)],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    assert proc.returncode == 0, f"JS scheduler failed\nstdout={proc.stdout}\nstderr={proc.stderr}"
    response = json.loads(proc.stdout)
    assert response["success"] is True
    return response["result"]


@pytest.mark.slow
def test_python_js_agree_on_scheduler_seed_path_selection():
    vector = _load_vector("select_lexicographic_head")

    py_result = _run_python_scheduler(vector["input"])
    js_result = _run_js_scheduler(
        vector["input"],
        timeout=SLOW_SCHEDULER_JS_TIMEOUT_SECONDS,
    )

    assert py_result == js_result
    assert py_result["scheduler_result"]["action"] == "run_operator"
    assert py_result["scheduler_result"]["operator"]["operator_id"] == "op.alpha"


@pytest.mark.slow
def test_python_js_agree_on_scheduler_negative_order_rejection():
    vector = _load_vector("reject_non_lexicographic_order")

    py_result = _run_python_scheduler(vector["input"])
    js_result = _run_js_scheduler(vector["input"])

    assert py_result == js_result
    assert py_result["scheduler_result"]["action"] == "reject_pool"
    assert py_result["scheduler_result"]["reason"] == "non_lexicographic_operator_order"


@pytest.mark.slow
def test_python_js_agree_on_scheduler_fail_closed_pair_rejection():
    vector = _load_vector("reject_unhandled_lexicographic_pair")

    py_result = _run_python_scheduler(vector["input"])
    js_result = _run_js_scheduler(vector["input"])

    assert py_result == js_result
    assert py_result["scheduler_result"]["action"] == "reject_pool"
    assert py_result["scheduler_result"]["reason"] == "unhandled_lexicographic_operator_pair"


@pytest.mark.slow
def test_python_js_agree_on_scheduler_longer_pool_rejection():
    vector = _load_vector("reject_longer_pool_unchecked_suffix")

    py_result = _run_python_scheduler(vector["input"])
    js_result = _run_js_scheduler(vector["input"])

    assert py_result == js_result
    assert py_result["scheduler_result"]["action"] == "reject_pool"
    assert py_result["scheduler_result"]["reason"] == "unhandled_operator_pool_width"


@pytest.mark.slow
def test_python_js_agree_on_scheduler_malformed_tail_rejection():
    vector = _load_vector("reject_malformed_tail_operator")

    py_result = _run_python_scheduler(vector["input"])
    js_result = _run_js_scheduler(vector["input"])

    assert py_result == js_result
    assert py_result["scheduler_result"]["action"] == "reject_pool"
    assert py_result["scheduler_result"]["reason"] == "unhandled_operator_pool_shape"


def test_scheduler_js_parity_vectors_remain_slow_marked():
    """Lock full JS scheduler parity vectors out of fast PR shards."""
    js_parity_vectors = (
        test_python_js_agree_on_scheduler_seed_path_selection,
        test_python_js_agree_on_scheduler_negative_order_rejection,
        test_python_js_agree_on_scheduler_fail_closed_pair_rejection,
        test_python_js_agree_on_scheduler_longer_pool_rejection,
        test_python_js_agree_on_scheduler_malformed_tail_rejection,
    )
    for test_func in js_parity_vectors:
        assert _has_slow_mark(test_func), test_func.__name__
