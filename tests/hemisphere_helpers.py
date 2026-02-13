"""
Shared helpers for hemisphere routing tests.

Used by: test_hemisphere_routing.py, test_hemisphere_adversarial.py,
         structural/test_hemisphere_parity.py
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.slow]

from rcx_pi.selfhost.seed_integrity import get_seed_path, load_verified_seed
from rcx_pi.selfhost.step_mu import run_mu


def load_hemisphere_projections() -> list[dict]:
    seed = load_verified_seed(get_seed_path("hemispheres.v1.json"))
    return seed["projections"]


def make_engine_result(
    value=None,
    closure_detected=False,
    tau_step=None,
    exhaustion_detected=False,
    operator_frozen=None,
    frozen_set=None,
    action="continue",
    stall=False,
) -> dict:
    return {
        "value": value,
        "closure_detected": closure_detected,
        "tau_step": tau_step,
        "exhaustion_detected": exhaustion_detected,
        "operator_frozen": operator_frozen,
        "frozen_set": frozen_set,
        "action": action,
        "stall": stall,
    }


def empty_hemispheres() -> dict:
    return {
        "r_null": None,
        "r_inf": None,
        "r_a": None,
        "lobes": None,
        "sink": None,
    }


def route(projs, engine_result, hemispheres=None):
    if hemispheres is None:
        hemispheres = empty_hemispheres()
    input_val = {
        "route_hemisphere": {
            "engine_result": engine_result,
            "hemispheres": hemispheres,
        }
    }
    result, trace, stall = run_mu(projs, input_val, max_steps=20)
    return result
