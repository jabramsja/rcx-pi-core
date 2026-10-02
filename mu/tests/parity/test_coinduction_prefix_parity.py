"""Complete Python/JS kernel outcomes for the verified guarded-prefix seed."""

from __future__ import annotations

import json
import subprocess

import pytest

from tests.l4_gates.test_coinduction_prefix_gate import (
    FIXTURE, VECTORS, assert_complete_outcomes, run_python,
)
from tests.repo_root import REPO_ROOT


pytestmark = [pytest.mark.slow, pytest.mark.l4_expensive]

JS_KERNEL_SETUP = r"""
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const { runStructural } = require('./mu/host/js/engine/kernel');
const { muCopy, validateBundle } = require('./mu/host/js/core/stage0_vm');
const {
  loadVerifiedSeed, loadVerifiedSeedImage, getSeedSubdir,
  SEED_IMAGE_VERIFICATION_MODES, SEED_CHECKSUMS,
} = require('./mu/host/js/core/seed_loader');

// The production CLI verification view pins these structural substrate seeds.
const kernel = ['kernel.v1.json', 'match.v2.json', 'subst.v2.json'].flatMap(name => {
  const bytes = fs.readFileSync(path.join('mu', getSeedSubdir(name), name));
  return loadVerifiedSeedImage(name, bytes, SEED_IMAGE_VERIFICATION_MODES.CLI).projections;
});
const vmConfig = {};
for (const [slot, file, seedName] of [
  ['kernelBundle', 'kernel_v1.compiled.v1.json', 'kernel.v1.json'],
  ['matchBundle', 'match_v2.compiled.v1.json', 'match.v2.json'],
  ['substBundle', 'subst_v2.compiled.v1.json', 'subst.v2.json'],
]) {
  const bundle = JSON.parse(fs.readFileSync(path.join('mu/stage0/compiled', file), 'utf8'));
  validateBundle(bundle);
  assert.strictEqual(bundle.source_digest, 'sha256:' + SEED_CHECKSUMS[seedName]);
  vmConfig[slot] = bundle;
}
"""

JS_RUNNER = JS_KERNEL_SETUP + r"""
const request = muCopy(JSON.parse(fs.readFileSync(0, 'utf8')), true, 'prefix parity request');
let domain = loadVerifiedSeed('coinduction_prefix.v1.json', 'programs').projections;
if (request.omit_emission) {
  domain = domain.filter(p => p.id !== 'co_prefix.emit');
}
const started = performance.now();
const outcomes = [runStructural(kernel, domain, request.input, request.max_steps, vmConfig)];
if (request.resume_window !== null) {
  const nextRequest = muCopy({coinduction_prefix: {
    tail: outcomes[0].result.coinduction_prefix_result.tail,
    window: request.resume_window,
  }}, true, 'prefix resumed request');
  outcomes.push(runStructural(kernel, domain, nextRequest, request.max_steps, vmConfig));
}
console.log(JSON.stringify({outcomes, elapsed_seconds: (performance.now() - started) / 1000}));
"""


def run_js(vector_id, *, omit_emission=False, max_steps=None):
    # SPEED_OK: actual JS structural kernel, verified substrate and domain seed loads.
    vector = VECTORS[vector_id]
    # Expected results never cross the execution boundary.
    request = {
        "input": vector["input"],
        "resume_window": vector.get("resume", {}).get("window"),
        "omit_emission": omit_emission,
        "max_steps": FIXTURE["max_steps"] if max_steps is None else max_steps,
    }
    process = subprocess.run(
        ["node", "-e", JS_RUNNER], input=json.dumps(request), cwd=REPO_ROOT,
        text=True, capture_output=True, timeout=900, check=False,
    )
    assert process.returncode == 0, f"JS kernel failed:\n{process.stdout}\n{process.stderr}"
    response = json.loads(process.stdout)
    return response["outcomes"], response["elapsed_seconds"]


@pytest.mark.parametrize("vector_id", list(VECTORS))
def test_complete_guarded_prefix_outcome_parity(vector_id, record_property):
    # SPEED_OK: shared positive/rejection/resumption vectors execute in both kernels.
    py_outcomes, py_elapsed = run_python(vector_id)
    assert_complete_outcomes(VECTORS[vector_id], py_outcomes)
    js_outcomes, js_elapsed = run_js(vector_id)
    assert_complete_outcomes(VECTORS[vector_id], js_outcomes)
    # Compare result, full structural trace, stall and step count, not just labels.
    assert js_outcomes == py_outcomes
    assert py_elapsed > 0 and js_elapsed > 0
    record_property("python_kernel_seconds", py_elapsed)
    record_property("javascript_kernel_seconds", js_elapsed)
    record_property("domain_steps", [o["steps"] for o in py_outcomes])


@pytest.mark.parametrize("controls", [{"omit_emission": True}, {"max_steps": 1}])
def test_negative_controls_agree_without_claiming_success(controls):
    # SPEED_OK: the same projection mutation and watchdog control run on both substrates.
    py_outcomes, _ = run_python("finite_open_tail", **controls)
    js_outcomes, _ = run_js("finite_open_tail", **controls)
    assert py_outcomes == js_outcomes
    assert "coinduction_prefix_result" not in py_outcomes[0]["result"]


def test_split_resume_matches_the_uninterrupted_window():
    # SPEED_OK: use real returned continuations and compare the full observation witnesses.
    whole, _ = run_python("alternating_three")
    split, _ = run_python("split_resumed")
    whole_result = whole[0]["result"]["coinduction_prefix_result"]
    first = split[0]["result"]["coinduction_prefix_result"]
    second = split[1]["result"]["coinduction_prefix_result"]
    first_cell = first["window"]["_co_window"]["prefix"]["_co_prefix"]
    assert first_cell["rest"] == {"_co_prefix": None}
    combined = {"_co_prefix": {
        "observation": first_cell["observation"], "step": first_cell["step"],
        "rest": second["window"]["_co_window"]["prefix"],
    }}
    assert combined == whole_result["window"]["_co_window"]["prefix"]
    assert second["tail"] == whole_result["tail"]
    assert second["window"]["_co_window"]["through"] == whole_result["window"]["_co_window"]["through"]
