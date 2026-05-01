"""Structural tests for rcx_engine_state.v1.json."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from rcx_pi.selfhost.mu_type import mu_equal
from rcx_pi.selfhost.seed_integrity import get_seed_path, load_verified_seed
from tests.conftest import run_until_stable
from tests.repo_root import REPO_ROOT


STATE_SEED_PATH = REPO_ROOT / "mu" / "programs" / "rcx_engine_state.v1.json"
FIXTURE_PATH = REPO_ROOT / "mu" / "tests" / "fixtures" / "rcx_engine_state_minimal.json"


def _load_seed() -> dict:
    return json.loads(STATE_SEED_PATH.read_text())


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


def test_state_seed_is_loadable_structural_artifact():
    seed = _load_seed()

    assert seed["meta"]["name"] == "RCX_ENGINE_STATE"
    assert [p["id"] for p in seed["projections"]] == [
        "engine_state.shape_valid",
        "engine_state.identity_stable",
        "engine_state.next_id_monotone",
        "engine_state.shape_invalid_missing_graph",
        "engine_state.shape_invalid_missing_omega",
        "engine_state.shape_invalid_missing_l_map",
        "engine_state.shape_invalid_missing_xi",
        "engine_state.shape_invalid_missing_rho",
        "engine_state.shape_invalid_missing_next_id",
    ]
    for projection in seed["projections"]:
        assert {"id", "pattern", "body"}.issubset(projection)


def test_state_seed_is_registered_with_verified_loader():
    seed = load_verified_seed(get_seed_path("rcx_engine_state.v1.json"))

    assert [p["id"] for p in seed["projections"]] == [
        p["id"] for p in _load_seed()["projections"]
    ]


def test_minimal_state_validates_graph_maps_rank_and_next_id():
    seed = _load_seed()
    fixture = _load_fixture()

    result = run_until_stable(seed["projections"], fixture["valid_minimal_state"], max_steps=2)

    validation = result["engine_state_validation"]
    assert validation["valid"] is True
    assert validation["shape"] == "G=(V,E)+Omega+L-map+Xi+rho+NextID"
    assert validation["graph_state"]["V"] == fixture["valid_minimal_state"]["validate_engine_state"]["state"]["G"]["V"]
    assert validation["graph_state"]["E"] is None
    assert set(validation["bookkeeping_maps"]) == {"Omega", "Lambda", "Xi"}
    assert validation["rho"] == {"zero": None}
    assert validation["NextID"] == {"succ": {"zero": None}}


def test_identity_stability_projection_requires_same_structural_id():
    seed = _load_seed()
    fixture = _load_fixture()

    result = run_until_stable(seed["projections"], fixture["identity_stability"], max_steps=2)

    assert result == {
        "engine_state_identity": {
            "valid": True,
            "identity_stable": True,
            "id": {"zero": None},
        }
    }


def test_monotone_next_id_projection_uses_successor_witness():
    seed = _load_seed()
    fixture = _load_fixture()

    result = run_until_stable(seed["projections"], fixture["next_id_monotone"], max_steps=2)

    assert result["engine_state_next_id"]["valid"] is True
    assert result["engine_state_next_id"]["allocated"] == {"succ": {"zero": None}}
    assert result["engine_state_next_id"]["next"] == {"succ": {"succ": {"zero": None}}}
    assert result["engine_state_next_id"]["monotone_allocation"] is True


def test_invalid_state_shape_is_rejected_structurally():
    seed = _load_seed()
    fixture = _load_fixture()

    result = run_until_stable(seed["projections"], fixture["invalid_missing_graph"], max_steps=2)

    assert result == {
        "engine_state_validation": {
            "valid": False,
            "reason": "missing_graph_state_G",
            "required": "G=(V,E)",
        }
    }


def test_each_required_state_field_omission_is_rejected_structurally():
    seed = _load_seed()
    fixture = _load_fixture()
    expected = {
        "Omega": ("missing_bookkeeping_map_Omega", "Omega"),
        "Lambda": ("missing_bookkeeping_map_L", "L-map"),
        "Xi": ("missing_bookkeeping_map_Xi", "Xi"),
        "rho": ("missing_rank_rho", "rho"),
        "NextID": ("missing_next_id", "NextID"),
    }

    for field, (reason, required) in expected.items():
        probe = deepcopy(fixture["valid_minimal_state"])
        del probe["validate_engine_state"]["state"][field]

        result = run_until_stable(seed["projections"], probe, max_steps=2)

        assert result == {
            "engine_state_validation": {
                "valid": False,
                "reason": reason,
                "required": required,
            }
        }


def test_identity_drift_does_not_pass_identity_stability_projection():
    seed = _load_seed()
    fixture = _load_fixture()

    result = run_until_stable(seed["projections"], fixture["invalid_identity_drift"], max_steps=2)

    assert mu_equal(result, fixture["invalid_identity_drift"])
