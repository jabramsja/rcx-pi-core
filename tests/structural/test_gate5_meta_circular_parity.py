"""
Gate 5 meta-circular parity tests.

This suite is dedicated to Gate 5 verification:
- Structural path remains default for algorithm execution.
- Bootstrap fallback requires explicit opt-in.
- Python and JS bridge-backed algorithm runtimes agree on canonical vectors.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from rcx_pi.selfhost.mu_type import mu_equal
from rcx_pi.selfhost.seed_integrity import get_seed_path, load_verified_seed
from rcx_pi.selfhost.step_mu import run_algorithm_meta_circular


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"


def _load_projections(seed_name: str) -> list[dict]:
    seed = load_verified_seed(get_seed_path(seed_name))
    return seed["projections"]


def _run_python_until_stall(projections: list[dict], initial: dict, max_steps: int = 200) -> dict:
    current = initial
    for _ in range(max_steps):
        nxt = run_algorithm_meta_circular(projections, current)
        if mu_equal(nxt, current):
            return nxt
        current = nxt
    return current


def _run_js_action(action: str, initial: dict, max_steps: int = 200) -> dict:
    req = json.dumps({"action": action, "input": initial, "maxSteps": max_steps})
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
    assert last.get("success"), f"js action failed: {last.get('error')}"
    return last["result"]


def test_gate5_bootstrap_fallback_requires_explicit_opt_in():
    state = {"_detect_closure": {"trace": None, "result": "A"}}
    with pytest.raises(ValueError, match="allow_bootstrap_fallback=True"):
        run_algorithm_meta_circular([], state, execution_mode="bootstrap")


def test_gate5_bootstrap_fallback_runs_when_opted_in():
    state = {"_detect_closure": {"trace": None, "result": "A"}}
    result = run_algorithm_meta_circular(
        [],
        state,
        execution_mode="bootstrap",
        allow_bootstrap_fallback=True,
    )
    assert isinstance(result, dict)


def test_gate5_recurrence_python_js_parity_vectors():
    rec_projs = _load_projections("recurrence.v1.json")
    vectors = json.loads((FIXTURES / "recurrence_vectors.json").read_text(encoding="utf-8"))["vectors"]
    # Keep this suite focused and fast: one positive and one negative canonical vector.
    selected = [vectors[0], vectors[1]]
    for vec in selected:
        py = _run_python_until_stall(rec_projs, vec["input"], max_steps=200)
        js = _run_js_action("run_recurrence_with_bridge", vec["input"], max_steps=200)
        assert mu_equal(py, js), f"recurrence parity mismatch for vector {vec['id']}: py={py} js={js}"


def test_gate5_exhaustion_python_js_parity_vectors():
    exh_projs = _load_projections("exhaustion.v1.json")
    vectors = json.loads((FIXTURES / "exhaustion_vectors.json").read_text(encoding="utf-8"))["vectors"]
    selected = [vectors[0], vectors[1]]
    for vec in selected:
        py = _run_python_until_stall(exh_projs, vec["input"], max_steps=200)
        js = _run_js_action("run_exhaustion_with_bridge", vec["input"], max_steps=200)
        assert mu_equal(py, js), f"exhaustion parity mismatch for vector {vec['id']}: py={py} js={js}"
