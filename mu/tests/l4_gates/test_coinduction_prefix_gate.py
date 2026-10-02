"""Execute the registered finite-prefix Mu program through the production kernel.

Helpers drive the existing kernel only. Expected observations are assertions in
the shared fixture; no host lookup, selector or Coinduction validator runs here.
"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
from time import perf_counter

import pytest

from rcx_pi.selfhost.seed_integrity import (
    EXPECTED_PROJECTION_IDS,
    RUN_ALGORITHM_AUTHORITY_SEEDS,
    SEED_REGISTRY_MANIFEST,
    get_seed_path,
    load_verified_seed,
)
from rcx_pi.selfhost.step_mu import run_mu_structural
from tests.repo_root import REPO_ROOT


SEED_NAME = "coinduction_prefix.v1.json"
FIXTURE = json.loads(
    (REPO_ROOT / "mu/tests/fixtures/coinduction_prefix_vectors.json").read_text()
)
VECTORS = {vector["id"]: vector for vector in FIXTURE["vectors"]}


def test_fixture_inputs_satisfy_matcher_numeric_cutover():
    """Catch unsupported host numerals before running the expensive kernels."""
    from rcx_pi.selfhost.stage0_vm import _check_no_floats  # ANTICHEAT_OK: existing matcher admission rule

    for vector in FIXTURE["vectors"]:
        _check_no_floats(vector["input"], reject_numbers=True, depth_limit=None)
        if "resume" in vector:
            _check_no_floats(
                vector["resume"]["window"], reject_numbers=True, depth_limit=None,
            )


@pytest.mark.parametrize("vector_id, path, raw_number", [
    ("numeric_demand", ("window", "_co_window", "demand"), 2),
    ("malformed_next_reference",
     ("tail", "_co_tail", "obligation", "machine", "transition", "next", "next"), 7),
])
def test_raw_host_numeric_fixture_regression(vector_id, path, raw_number):
    """The archived encodings fail admission, not a Mu semantic rejection."""
    from rcx_pi.selfhost.stage0_vm import _check_no_floats  # ANTICHEAT_OK: existing matcher admission rule

    request = deepcopy(VECTORS[vector_id]["input"])
    _check_no_floats(request, reject_numbers=True, depth_limit=None)
    cursor = request["coinduction_prefix"]
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = raw_number
    with pytest.raises(ValueError, match="Host numeric values unsupported in matcher domain"):
        _check_no_floats(request, reject_numbers=True, depth_limit=None)


def trace_entries(outcome):
    """Read the kernel's linked trace for assertions, never for computation."""
    cursor = outcome["trace"]
    while cursor is not None:
        yield cursor["head"]
        cursor = cursor["tail"]


@lru_cache(maxsize=None)
def run_python(vector_id, *, omit_emission=False, max_steps=None):
    # SPEED_OK: bounded production structural-kernel execution is the proof target.
    projections = load_verified_seed(get_seed_path(SEED_NAME), verify=True)["projections"]
    if omit_emission:
        projections = [p for p in projections if p["id"] != "co_prefix.emit"]
    vector = VECTORS[vector_id]
    initial = vector["input"]
    limit = FIXTURE["max_steps"] if max_steps is None else max_steps
    started = perf_counter()
    outcome = run_mu_structural(
        projections, initial, max_steps=limit, kernel_mode="core",
        validation_mode="domain", trace_output=True, reject_nonlinear=True,
    )
    outcomes = [outcome]
    if "resume" in vector:
        # Transfer the actual returned tail verbatim, without selecting a state
        # or reading an expected result. The seed validates the new request.
        initial = {"coinduction_prefix": {
            "tail": outcome["result"]["coinduction_prefix_result"]["tail"],
            "window": vector["resume"]["window"],
        }}
        outcomes.append(run_mu_structural(
            projections, initial, max_steps=limit, kernel_mode="core",
            validation_mode="domain", trace_output=True, reject_nonlinear=True,
        ))
    return outcomes, perf_counter() - started


def assert_complete_outcomes(vector, outcomes):
    """Require a semantic result as well as termination; stall alone proves none."""
    assertions = [vector] + ([vector["resume"]] if "resume" in vector else [])
    assert len(outcomes) == len(assertions)
    for outcome, assertion in zip(outcomes, assertions, strict=True):
        assert outcome["stall"] is True
        assert 0 < outcome["steps"] < FIXTURE["max_steps"]
        assert outcome["result"] == assertion["expected"]
        entries = list(trace_entries(outcome))
        assert sum(e["projection"] == "co_prefix.emit" for e in entries) == assertion["emissions"]
        assert not any(e.get("max_steps") for e in entries)


def test_verified_program_registration_and_authority():
    seed = load_verified_seed(get_seed_path(SEED_NAME), verify=True)
    record = SEED_REGISTRY_MANIFEST["seeds"][SEED_NAME]
    ids = [p["id"] for p in seed["projections"]]
    assert ids == EXPECTED_PROJECTION_IDS[SEED_NAME]
    assert len(ids) == len(set(ids)) == 32
    assert record["subdir"] == "programs"
    assert record["status"] == "production"
    assert record["dependencies"] == []  # No companion domain projections.
    assert record["js_cli_registered"] is True
    assert record["js_core_locked"] is True
    assert SEED_NAME not in RUN_ALGORITHM_AUTHORITY_SEEDS
    assert "authority" not in record


@pytest.mark.slow
def test_guarded_progress_is_visible_in_the_actual_kernel_trace(record_property):
    # SPEED_OK: three nontrivial observations prove guarded progress in the real kernel.
    outcomes, elapsed = run_python("alternating_three")
    assert_complete_outcomes(VECTORS["alternating_three"], outcomes)
    outcome = outcomes[0]
    entries = list(trace_entries(outcome))
    guarded = [e for e in entries if e["projection"] == "co_prefix.guarded"]
    assert len(guarded) == 3
    assert outcome["steps"] == 42
    for i, entry in enumerate(entries):
        if entry["projection"] != "co_prefix.emit":
            continue
        before = entry["state"]["co_emit"]
        after = entries[i + 1]["state"]["co_run"]
        cell = after["prefix"]["_co_prefix"]
        observation = cell["observation"]["_co_observation"]
        witness = cell["step"]["_co_guarded_step"]
        assert entries[i - 1]["projection"] == "co_prefix.ref_zero"
        assert observation["payload"] == before["payload"]
        assert observation["position"] == {"_co_position": {"path": before["context"]["path"]}}
        assert witness["observation"] == cell["observation"]
        assert witness["guard"] == "observed-before-tail"
        assert witness["source"] == before["context"]["source"]
        assert witness["next"] == after["next"] == before["next"]
        assert after["path"] == {"_co_position_path": {
            "step": "next", "rest": before["context"]["path"],
        }}
    assert elapsed > 0
    record_property("kernel_elapsed_seconds", elapsed)
    record_property("domain_steps", outcome["steps"])


@pytest.mark.slow
def test_emission_projection_is_causally_necessary():
    # SPEED_OK: removing the emission rule must stop the real finite-prefix computation.
    outcomes, _ = run_python("finite_open_tail", omit_emission=True)
    outcome = outcomes[0]
    assert outcome["stall"] is True
    assert "co_emit" in outcome["result"]
    assert "coinduction_prefix_result" not in outcome["result"]
    assert outcome["result"] != VECTORS["finite_open_tail"]["expected"]
    assert all(e["projection"] != "co_prefix.emit" for e in trace_entries(outcome))


@pytest.mark.slow
def test_driver_exhaustion_is_not_a_semantic_result():
    # SPEED_OK: one real kernel step distinguishes the watchdog from a Mu result.
    outcomes, _ = run_python("finite_open_tail", max_steps=1)
    assert outcomes[0]["stall"] is False
    assert outcomes[0]["steps"] == 1
    assert "coinduction_prefix_result" not in outcomes[0]["result"]
    assert list(trace_entries(outcomes[0]))[-1]["max_steps"] is True


def test_bounded_contract_is_grounded_and_discoverable():
    doc = (REPO_ROOT / "mu/docs/core/CoinductionPrefix.v0.md").read_text()
    assert "TYPE: IMPLEMENTATION" in doc[:500]
    assert "workload_target: execution_layer_truth" in doc
    assert "run_mu_structural" in doc and "runStructural" in doc
    assert "test_execution_layer_truth_contract.py" in doc
    assert "infinite productivity" in doc and "bisimulation" in doc
    assert "CoinductionPrefix.v0.md" in (REPO_ROOT / "roadmap/MANIFEST.md").read_text()
