"""
Engine Pipeline Verification

Empirically verifies that run_engine_pipeline correctly orchestrates the
full RCX engine cycle (trace -> hash -> recurrence -> exhaustion) using
the _boundary_request algebraic effect protocol.

This test replaces the manual orchestration in test_paxos_end_to_end.py
with the actual engine projections.
"""
import pytest

from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline

from rcx_pi.selfhost.kernel import reset_step_budget


@pytest.mark.slow
def test_engine_orchestrates_paxos_closure():
    """Verify engine pipeline detects Paxos closure automatically."""
    reset_step_budget()
    
    # Load paxos projections
    paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
    projections = paxos_seed["projections"][:4]  # The livelock cycle
    
    # Initial input
    initial = {"paxos_trigger": "start_paxos"}
    
    # Run through the engine pipeline
    # The engine should:
    # 1. Run trace (via boundary request)
    # 2. Hash trace (via boundary request)
    # 3. Run recurrence (via boundary request)
    # 4. Run exhaustion (via boundary request)
    # 5. Unwrap result
    result = run_engine_pipeline(
        projections,
        initial,
        max_steps=6,  # Sufficient for 2 cycles
        max_iterations=50, # Sufficient for recurrence/exhaustion convergence
        use_boot1_recursive=False,
    )
    
    print("\nEngine Result:", result)
    
    # Assertions
    assert isinstance(result, dict)
    
    # 1. Did it detect the closure?
    assert result.get("closure_detected") is True, "Engine failed to detect closure"
    
    # 2. Did it identify the tau step?
    assert result.get("tau_step") is not None, "Engine failed to identify tau_step"
    
    # 3. Did it run exhaustion? (Paxos demo has no frozen operators, so False is correct)
    assert result.get("exhaustion_detected") is False, "Exhaustion should be False for Paxos"
    
    # 4. Did it return the final value?
    val = result.get("value")
    assert isinstance(val, dict)
    assert "node_a" in val or "paxos_mode" in val, "Result value looks wrong"

@pytest.mark.slow
def test_engine_output_composes_with_healer():
    """Verify apply_mu(healer, run_engine_pipeline(...)) produces consensus."""
    from rcx_pi.selfhost.step_mu import apply_mu
    reset_step_budget()

    paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
    cycle_projs = paxos_seed["projections"][:4]
    healer_engine_proj = paxos_seed["projections"][5]  # engine-output healer

    engine_result = run_engine_pipeline(
        cycle_projs,
        {"paxos_trigger": "start_paxos"},
        max_steps=6,
        max_engine_iterations=20,
        max_algorithm_iterations=50,
        use_boot1_recursive=False,
    )

    assert engine_result.get("closure_detected") is True, "Precondition: closure detected"

    # Healer should compose directly with engine output
    healer_result = apply_mu(healer_engine_proj, engine_result)

    assert isinstance(healer_result, dict)
    assert healer_result.get("status") == "consensus_reached"
    assert healer_result.get("leader") == "Node_A"
    assert healer_result.get("reason") == "deadlock_resolution_protocol"


@pytest.mark.slow
def test_engine_exhaustion_without_terminal_raises():
    """Verify engine fails closed when outer loop exhausts without terminal."""
    import pytest
    reset_step_budget()

    # Empty projections with non-matchable input — engine.init won't fire
    # because input doesn't have _run_engine shape
    with pytest.raises(RuntimeError, match="(stalled|exhausted).*without.*terminal"):
        run_engine_pipeline(
            [],
            {"unrelated": True},
            max_steps=5,
            max_engine_iterations=3,
            use_boot1_recursive=False,
        )


@pytest.mark.slow
def test_budget_persists_across_sub_algorithm_iterations():
    """Budget accounting persists when a caller provides an active budget.

    Verifies that step_kernel_mu piggybacks on a caller-provided budget
    (accumulating steps) rather than creating independent per-call budgets.
    _run_sub_algorithm delegates budget to step_kernel_mu; the outer loop
    is bounded by max_iterations, not budget.
    """
    from rcx_pi.selfhost.kernel import get_step_budget
    reset_step_budget()

    budget = get_step_budget()
    budget.start(limit=500_000)

    try:
        # Run the full engine pipeline — budget should accumulate across
        # all sub-algorithm phases (recurrence + exhaustion)
        paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
        projections = paxos_seed["projections"][:4]

        result = run_engine_pipeline(
            projections,
            {"paxos_trigger": "start_paxos"},
            max_steps=6,
            max_engine_iterations=20,
            max_algorithm_iterations=50,
            use_boot1_recursive=False,
        )

        # Budget should have consumed steps from all phases
        total = budget.get_total()
        assert total > 0, "Budget should have consumed steps during pipeline"
        assert budget.is_active(), "Budget should still be active (not replaced)"
    finally:
        budget.stop()


if __name__ == "__main__":
    try:
        test_engine_orchestrates_paxos_closure()
        print("PASS: Engine pipeline verification successful.")
    except Exception as e:
        print(f"FAIL: {e}")
        import traceback
        traceback.print_exc()
