"""Structural tests for rcx_engine_scheduler.v1.json."""

from __future__ import annotations

import json

from rcx_pi.selfhost.seed_integrity import get_seed_path, load_verified_seed
from tests.conftest import run_until_stable
from tests.repo_root import REPO_ROOT


SCHEDULER_SEED_NAME = "rcx_engine_scheduler.v1.json"
SCHEDULER_SEED_PATH = REPO_ROOT / "mu" / "programs" / SCHEDULER_SEED_NAME
FIXTURE_PATH = REPO_ROOT / "mu" / "tests" / "fixtures" / "rcx_enginenew_scheduler_operator_pool.json"


def _load_seed() -> dict:
    return json.loads(SCHEDULER_SEED_PATH.read_text())


def _load_vectors() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text())["vectors"]


def _vector(vector_id: str) -> dict:
    return next(v for v in _load_vectors() if v["id"] == vector_id)


def _run(vector_id: str) -> dict:
    seed = _load_seed()
    vector = _vector(vector_id)
    return run_until_stable(seed["projections"], vector["input"], max_steps=4)


def test_scheduler_seed_is_loadable_structural_artifact():
    seed = _load_seed()

    assert seed["meta"]["name"] == "RCX_ENGINE_SCHEDULER"
    assert seed["meta"]["ordering_policy"] == "strict_lexicographic_by_godel_code"
    assert [p["id"] for p in seed["projections"]] == [
        "scheduler.invalid_missing_godel_unary_map",
        "scheduler.invalid_non_godel_head",
        "scheduler.invalid_godel_missing_code",
        "scheduler.invalid_godel_missing_domain",
        "scheduler.invalid_godel_missing_codomain",
        "scheduler.invalid_godel_missing_identity_map",
        "scheduler.reject_identity_map",
        "scheduler.reject_tail_identity_map",
        "scheduler.reject_third_identity_map",
        "scheduler.reject_unhandled_three_operator_pool",
        "scheduler.order_error_0010_before_0001",
        "scheduler.order_error_0100_before_0011",
        "scheduler.skip_frozen_head",
        "scheduler.skip_frozen_tail_member",
        "scheduler.skip_frozen_tail2_member",
        "scheduler.scan_frozen_tail",
        "scheduler.select_single_operator",
        "scheduler.select_0001_before_0010",
        "scheduler.select_0011_before_0100",
        "scheduler.reject_unhandled_two_operator_pool",
        "scheduler.pool_exhausted",
        "scheduler.reject_unhandled_operator_pool_shape",
    ]
    for projection in seed["projections"]:
        assert {"id", "pattern", "body"}.issubset(projection)


def test_scheduler_seed_is_registered_with_verified_loader():
    seed = load_verified_seed(get_seed_path(SCHEDULER_SEED_NAME))

    assert [p["id"] for p in seed["projections"]] == [
        p["id"] for p in _load_seed()["projections"]
    ]


def test_scheduler_selects_lexicographic_head_from_finite_pool():
    result = _run("select_lexicographic_head")

    scheduler_result = result["scheduler_result"]
    assert scheduler_result["action"] == "run_operator"
    assert scheduler_result["operator"]["operator_id"] == "op.alpha"
    assert scheduler_result["operator"]["godel_unary_map"]["code"] == "0001"
    assert scheduler_result["remaining_pool"]["head"]["operator_id"] == "op.beta"
    assert scheduler_result["scheduler_state"]["ordering"] == "strict_lexicographic"
    assert scheduler_result["scheduler_state"]["pool_size_witness"] == "two"


def test_scheduler_selects_single_valid_operator_pool():
    result = _run("single_valid_operator")

    scheduler_result = result["scheduler_result"]
    assert scheduler_result["action"] == "run_operator"
    assert scheduler_result["operator"]["operator_id"] == "op.solo"
    assert scheduler_result["operator"]["godel_unary_map"]["code"] == "0011"
    assert scheduler_result["remaining_pool"] is None
    assert scheduler_result["scheduler_state"]["ordering"] == "strict_lexicographic"
    assert scheduler_result["scheduler_state"]["pool_size_witness"] == "one"


def test_scheduler_selects_second_bounded_lexicographic_witness():
    result = _run("valid_order_other_codes")

    scheduler_result = result["scheduler_result"]
    assert scheduler_result["action"] == "run_operator"
    assert scheduler_result["operator"]["operator_id"] == "op.gamma"
    assert scheduler_result["operator"]["godel_unary_map"]["code"] == "0011"
    assert scheduler_result["remaining_pool"]["head"]["operator_id"] == "op.delta"
    assert scheduler_result["scheduler_state"]["ordering"] == "strict_lexicographic"


def test_scheduler_returns_promotion_and_freeze_lifecycle_hooks():
    result = _run("select_lexicographic_head")

    lifecycle = result["scheduler_result"]["lifecycle"]
    assert lifecycle["promotion_hook"] == {
        "action": "promote_candidate",
        "operator_id": "op.alpha",
        "source": SCHEDULER_SEED_NAME,
    }
    assert lifecycle["freeze_hook"] == {
        "action": "freeze_on_exhaustion",
        "operator_id": "op.alpha",
        "source": "exhaustion.v1.json",
    }


def test_scheduler_skips_frozen_operator_structurally():
    result = _run("skip_frozen_head")

    scheduler_result = result["scheduler_result"]
    assert scheduler_result["action"] == "skip_operator"
    assert scheduler_result["operator_id"] == "op.alpha"
    assert scheduler_result["remaining_pool"]["head"]["operator_id"] == "op.beta"
    assert scheduler_result["lifecycle"]["freeze_hook"] == {
        "action": "skip_frozen",
        "source": "exhaustion.v1.json",
        "operator_id": "op.alpha",
    }


def test_scheduler_skips_operator_when_frozen_list_tail_matches():
    result = _run("skip_frozen_tail_member")

    scheduler_result = result["scheduler_result"]
    assert scheduler_result["action"] == "skip_operator"
    assert scheduler_result["operator_id"] == "op.alpha"
    assert scheduler_result["remaining_pool"]["head"]["operator_id"] == "op.beta"
    assert scheduler_result["lifecycle"]["freeze_hook"]["operator_id"] == "op.alpha"


def test_scheduler_skips_operator_when_deep_frozen_list_tail_matches():
    result = _run("skip_frozen_deep_tail_member")

    scheduler_result = result["scheduler_result"]
    assert scheduler_result["action"] == "skip_operator"
    assert scheduler_result["operator_id"] == "op.alpha"
    assert scheduler_result["remaining_pool"]["head"]["operator_id"] == "op.beta"
    assert scheduler_result["lifecycle"]["freeze_hook"]["operator_id"] == "op.alpha"


def test_scheduler_scans_frozen_list_beyond_fixed_prefix():
    result = _run("skip_frozen_fourth_tail_member")

    scheduler_result = result["scheduler_result"]
    assert scheduler_result["action"] == "skip_operator"
    assert scheduler_result["operator_id"] == "op.alpha"
    assert scheduler_result["remaining_pool"]["head"]["operator_id"] == "op.beta"
    assert scheduler_result["lifecycle"]["freeze_hook"]["operator_id"] == "op.alpha"


def test_scheduler_rejects_identity_map_safeguard():
    result = _run("reject_identity_map")

    scheduler_result = result["scheduler_result"]
    assert scheduler_result["action"] == "reject_operator"
    assert scheduler_result["reason"] == "identity_map_safeguard"
    assert scheduler_result["operator_id"] == "op.identity"


def test_scheduler_rejects_tail_identity_map_safeguard():
    result = _run("reject_tail_identity_map")

    scheduler_result = result["scheduler_result"]
    assert scheduler_result["action"] == "reject_operator"
    assert scheduler_result["reason"] == "identity_map_safeguard"
    assert scheduler_result["operator_id"] == "op.identity_tail"


def test_scheduler_rejects_deeper_identity_map_safeguard():
    result = _run("reject_third_identity_map")

    scheduler_result = result["scheduler_result"]
    assert scheduler_result["action"] == "reject_operator"
    assert scheduler_result["reason"] == "identity_map_safeguard"
    assert scheduler_result["operator_id"] == "op.identity_deep"


def test_scheduler_rejects_non_godel_coded_operator():
    result = _run("reject_non_godel_operator")

    scheduler_result = result["scheduler_result"]
    assert scheduler_result["action"] == "reject_operator"
    assert scheduler_result["reason"] == "non_godel_coded_unary_map"
    assert scheduler_result["operator_id"] == "op.raw"


def test_scheduler_rejects_missing_map_and_godel_shape():
    result = _run("missing_map_and_godel")

    scheduler_result = result["scheduler_result"]
    assert scheduler_result["action"] == "reject_operator"
    assert scheduler_result["reason"] == "non_godel_coded_unary_map"
    assert scheduler_result["operator_id"] == "op.missing"


def test_scheduler_rejects_malformed_godel_missing_identity_flag():
    result = _run("malformed_godel_missing_identity")

    scheduler_result = result["scheduler_result"]
    assert scheduler_result["action"] == "reject_operator"
    assert scheduler_result["reason"] == "non_godel_coded_unary_map"
    assert scheduler_result["operator_id"] == "op.partial"


def test_scheduler_rejects_known_non_lexicographic_order():
    result = _run("reject_non_lexicographic_order")

    scheduler_result = result["scheduler_result"]
    assert scheduler_result["action"] == "reject_pool"
    assert scheduler_result["reason"] == "non_lexicographic_operator_order"
    assert scheduler_result["expected_order"] == ["0001", "0010"]
    assert scheduler_result["observed_order"] == ["0010", "0001"]


def test_scheduler_rejects_second_bounded_non_lexicographic_order():
    result = _run("reversed_other_codes")

    scheduler_result = result["scheduler_result"]
    assert scheduler_result["action"] == "reject_pool"
    assert scheduler_result["reason"] == "non_lexicographic_operator_order"
    assert scheduler_result["expected_order"] == ["0011", "0100"]
    assert scheduler_result["observed_order"] == ["0100", "0011"]


def test_scheduler_rejects_longer_pool_without_full_order_witness():
    result = _run("reject_longer_pool_unchecked_suffix")

    scheduler_result = result["scheduler_result"]
    assert scheduler_result["action"] == "reject_pool"
    assert scheduler_result["reason"] == "unhandled_operator_pool_width"
    assert scheduler_result["observed_order"] == ["0001", "0010", "0000"]


def test_scheduler_rejects_malformed_non_head_operator_fail_closed():
    result = _run("reject_malformed_tail_operator")

    scheduler_result = result["scheduler_result"]
    assert scheduler_result["action"] == "reject_pool"
    assert scheduler_result["reason"] == "unhandled_operator_pool_shape"
    assert scheduler_result["observed_pool"]["tail"]["head"]["operator_id"] == "op.bad"


def test_scheduler_rejects_unhandled_two_operator_pool_fail_closed():
    result = _run("reject_unhandled_lexicographic_pair")

    scheduler_result = result["scheduler_result"]
    assert scheduler_result["action"] == "reject_pool"
    assert scheduler_result["reason"] == "unhandled_lexicographic_operator_pair"
    assert scheduler_result["observed_order"] == ["0011", "0001"]
    assert scheduler_result["operator_ids"] == ["op.gamma", "op.alpha"]


def test_scheduler_pool_exhausted_is_explicit_mu_result():
    result = _run("pool_exhausted")

    scheduler_result = result["scheduler_result"]
    assert scheduler_result["action"] == "pool_exhausted"
    assert scheduler_result["frozen"] == {"head": "op.alpha", "tail": None}


def test_python_run_algorithm_boundary_loads_scheduler_seed_path(monkeypatch):
    from rcx_pi.selfhost import engine_pipeline

    captured: dict[str, object] = {}

    def fake_load_verified_seed(seed_path):
        captured["seed_path"] = seed_path
        return _load_seed()

    def fake_run_sub_algorithm(projections, initial, max_iterations):
        captured["ids"] = [p["id"] for p in projections]
        captured["initial"] = initial
        captured["max_iterations"] = max_iterations
        return {"scheduler_result": {"action": "captured"}}

    monkeypatch.setattr(engine_pipeline, "load_verified_seed", fake_load_verified_seed)
    monkeypatch.setattr(engine_pipeline, "_run_sub_algorithm", fake_run_sub_algorithm)
    vector = _vector("select_lexicographic_head")

    result = engine_pipeline._boundary_op_run_algorithm(
        {"algorithm": SCHEDULER_SEED_NAME},
        vector["input"],
        7,
    )

    assert result == {"scheduler_result": {"action": "captured"}}
    assert captured["seed_path"].name == SCHEDULER_SEED_NAME
    assert captured["ids"] == [p["id"] for p in _load_seed()["projections"]]
    assert captured["initial"] == vector["input"]
    assert captured["max_iterations"] == 7
