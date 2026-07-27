"""S1-A D1: Stage0 VM performance profiling suite.

Two-tier profiling for VM cutover GO/NO-GO evidence:
- Tier 1: P7-c corpus vectors (diagnostic, per-projection characterization)
- Tier 2: Integration workloads through run_engine_pipeline (GO/NO-GO threshold)

Performance data is observational — recorded in test output for the indicator
artifact. No wall-clock CI gating assertions.

Tier 2 asserts EVIDENCE INTEGRITY, not performance: the emitted record must
describe the sampling that actually happened (sample count and profile mode as
derived by ``_stage0_profile_counts``, every duration a finite non-negative
number). Those checks are env-independent by construction. No latency,
throughput, or ratio threshold is asserted anywhere in this suite.

L4_ENABLER evidence: G8 (Irreducible Primitive Consensus).
"""
# SPEED_OK: Performance profiling suite intentionally runs repeated timing trials.
# Tier 1 diagnostics are fast (<10s) but Tier 2 integration workloads take ~60s.

import json
import math
import os
import time
import pytest

from rcx_pi.selfhost.step_mu import (
    step_kernel_mu,
    _step_kernel_with_vm,  # ANTICHEAT_OK: S1-A performance — VM path timing
    _load_kernel_v1_projections_shared,  # ANTICHEAT_OK: S1-A performance — partition loader
    _load_bridge_projections_shared,  # ANTICHEAT_OK: S1-A performance — partition loader
    _load_compiled_match_v2_bundle,  # ANTICHEAT_OK: S1-A performance — bundle loader
    _load_compiled_subst_v2_bundle,  # ANTICHEAT_OK: S1-A performance — bundle loader
    _load_combined_kernel_projections_shared,  # ANTICHEAT_OK: S1-A performance — combined loader
    clear_combined_kernel_cache,
    normalize_projection,
    list_to_linked,
    run_algorithm_meta_circular,
)
from rcx_pi.selfhost.match_mu import normalize_for_match
from rcx_pi.selfhost.kernel import reset_step_budget
from rcx_pi.selfhost.eval_seed import _step_trusted, NO_MATCH  # ANTICHEAT_OK: S1-A performance — host path timing
from rcx_pi.selfhost.stage0_vm import stage0_vm_step  # ANTICHEAT_OK: S1-A performance — VM step timing
from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline  # ANTICHEAT_OK: S1-A performance — integration workload


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_caches():
    clear_combined_kernel_cache()
    reset_step_budget()
    yield
    clear_combined_kernel_cache()


# ---------------------------------------------------------------------------
# Tier 1: P7-c corpus diagnostic vectors
# ---------------------------------------------------------------------------

# Reuse the same vectors from test_lower_stage0.py
# These are per-projection single-step inputs for match.v2 and subst.v2

def _match_ctx():
    return {"_match_ctx": True}

def _subst_ctx():
    return {"_subst_ctx": True}


MATCH_DIAGNOSTIC_VECTORS = [
    ("match.wrap", {
        "match": {"pattern": "hello", "value": "hello"},
        "_match_ctx": _match_ctx(),
    }),
    ("match.equal", {
        "mode": "match", "pattern_focus": "hello", "value_focus": "hello",
        "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
    }),
    ("match.var", {
        "mode": "match", "pattern_focus": {"var": "x"},
        "value_focus": "forty_two", "bindings": None,
        "stack": None, "_match_ctx": _match_ctx(),
    }),
    ("match.done", {
        "mode": "match", "pattern_focus": None, "value_focus": None,
        "bindings": {"name": "x", "value": "forty_two", "rest": None},
        "stack": None, "_match_ctx": _match_ctx(),
    }),
    ("match.fail", {
        "mode": "match", "pattern_focus": "a", "value_focus": "b",
        "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
    }),
]

SUBST_DIAGNOSTIC_VECTORS = [
    ("subst.wrap", {
        "subst": {"body": {"var": "x"}, "bindings": {"name": "x", "value": 42, "rest": None}},
        "_subst_ctx": _subst_ctx(),
    }),
    ("subst.primitive", {
        "mode": "subst", "phase": "traverse", "focus": "literal",
        "bindings": None, "context": None, "_subst_ctx": _subst_ctx(),
    }),
    ("subst.var", {
        "mode": "subst", "phase": "traverse",
        "focus": {"var": "x"},
        "bindings": {"name": "x", "value": 42, "rest": None},
        "context": None, "_subst_ctx": _subst_ctx(),
    }),
    ("subst.done", {
        "mode": "subst", "phase": "result", "focus": 42,
        "bindings": None, "context": None, "_subst_ctx": _subst_ctx(),
    }),
]


def _time_fn(fn, arg1, arg2, n_runs=10, warmup=5):
    """Time N runs of fn(arg1, arg2), return list of durations."""
    for _ in range(warmup):
        fn(arg1, arg2)
    times = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        fn(arg1, arg2)
        times.append(time.perf_counter() - t0)
    return times


def _stats(times):
    """Compute median, p95, stdev from a list of times."""
    import statistics
    s = sorted(times)
    n = len(s)
    median = s[n // 2]
    p95 = s[int(n * 0.95)] if n >= 20 else s[-1]
    stdev = statistics.stdev(s) if n > 1 else 0.0
    return {"median": median, "p95": p95, "stdev": stdev, "n": n}


_FULL_PROFILING_ENV = "RCX_STAGE0_VM_FULL_PROFILING"

# Closed vocabulary of profile modes emitted by _stage0_profile_counts. Tier 2
# locks the mode field of its evidence record to this set. Env-INDEPENDENT: the
# concrete mode varies by environment ("default" locally, "ci_bounded" under
# RCX_CI=1, "full" under the opt-in), so a test must never assert one literal
# mode — only membership here, plus equality against a derivation that used the
# same arguments as the timing helper.
_PROFILE_MODES = frozenset({"full", "ci_bounded", "default"})


def _stage0_profile_counts(default_runs, default_warmup):
    """Bound CI sampling while preserving full profiling behind an explicit opt-in."""
    if os.environ.get(_FULL_PROFILING_ENV) == "1":
        return default_runs, default_warmup, "full"
    if os.environ.get("RCX_CI") == "1":
        return min(default_runs, 3), min(default_warmup, 1), "ci_bounded"
    return default_runs, default_warmup, "default"


def _assert_durations_valid(times):
    """Every recorded duration is a finite, non-negative real number.

    A validity floor, NOT a time budget: there is no upper bound, so no
    wall-clock/latency/throughput threshold is introduced. Callers also keep an
    inline ``assert`` of their own so each test carries its own check.
    """
    assert times, "timing helper recorded no samples"
    for t in times:
        assert isinstance(t, float), f"duration is not a float: {t!r}"
        assert math.isfinite(t), f"duration is not finite: {t!r}"
        assert t >= 0.0, f"duration is negative: {t!r}"


class TestTier1MatchDiagnostics:
    """Tier 1: Per-projection timing for match.v2 corpus vectors.
    Diagnostic only — no CI gating assertions."""

    @pytest.mark.parametrize("proj_id,inp", MATCH_DIAGNOSTIC_VECTORS,
                             ids=[v[0] for v in MATCH_DIAGNOSTIC_VECTORS])
    def test_match_vm_timing(self, proj_id, inp):
        """Record VM timing for match.v2 projection."""
        bundle = _load_compiled_match_v2_bundle()
        vm_times = _time_fn(stage0_vm_step, bundle, inp, n_runs=10)
        vm_stats = _stats(vm_times)

        # Also time host path for comparison
        combined = _load_combined_kernel_projections_shared()
        host_times = _time_fn(_step_trusted, combined, inp, n_runs=10)
        host_stats = _stats(host_times)

        ratio = vm_stats["median"] / host_stats["median"] if host_stats["median"] > 0 else float("inf")

        # Observational: print for indicator artifact, no assertion
        print(json.dumps({
            "tier": 1,
            "projection": proj_id,
            "vm": vm_stats,
            "host": host_stats,
            "ratio": round(ratio, 2),
        }))


class TestTier1SubstDiagnostics:
    """Tier 1: Per-projection timing for subst.v2 corpus vectors."""

    @pytest.mark.parametrize("proj_id,inp", SUBST_DIAGNOSTIC_VECTORS,
                             ids=[v[0] for v in SUBST_DIAGNOSTIC_VECTORS])
    def test_subst_vm_timing(self, proj_id, inp):
        """Record VM timing for subst.v2 projection."""
        bundle = _load_compiled_subst_v2_bundle()
        vm_times = _time_fn(stage0_vm_step, bundle, inp, n_runs=10)
        vm_stats = _stats(vm_times)

        combined = _load_combined_kernel_projections_shared()
        host_times = _time_fn(_step_trusted, combined, inp, n_runs=10)
        host_stats = _stats(host_times)

        ratio = vm_stats["median"] / host_stats["median"] if host_stats["median"] > 0 else float("inf")

        print(json.dumps({
            "tier": 1,
            "projection": proj_id,
            "vm": vm_stats,
            "host": host_stats,
            "ratio": round(ratio, 2),
        }))


# ---------------------------------------------------------------------------
# Tier 2: Integration workloads (GO/NO-GO threshold evidence)
# ---------------------------------------------------------------------------

def _time_kernel_mu(projections, input_value, n_runs=30, kernel_mode="core"):
    """Time N runs of step_kernel_mu through the full kernel path."""
    n_runs, warmup, _profile_mode = _stage0_profile_counts(n_runs, 5)
    for _ in range(warmup):
        step_kernel_mu(projections, input_value, kernel_mode=kernel_mode)
    times = []
    for _ in range(n_runs):
        clear_combined_kernel_cache()
        reset_step_budget()
        t0 = time.perf_counter()
        step_kernel_mu(projections, input_value, kernel_mode=kernel_mode)
        times.append(time.perf_counter() - t0)
    return times


def _time_engine_pipeline(projections, input_value, *, n_runs=10, warmup=3):
    """Time run_engine_pipeline with CI-bounded observational sampling."""
    n_runs, warmup, profile_mode = _stage0_profile_counts(n_runs, warmup)
    for _ in range(warmup):
        reset_step_budget()
        run_engine_pipeline(
            projections,
            input_value,
            max_steps=10,
            max_engine_iterations=20,
            max_algorithm_iterations=50,
        )

    times = []
    for _ in range(n_runs):
        reset_step_budget()
        t0 = time.perf_counter()
        run_engine_pipeline(
            projections,
            input_value,
            max_steps=10,
            max_engine_iterations=20,
            max_algorithm_iterations=50,
        )
        times.append(time.perf_counter() - t0)
    return times, profile_mode


@pytest.mark.l4_expensive
@pytest.mark.slow
class TestTier2IntegrationWorkloads:
    """Tier 2: Full pipeline timing with statistical analysis.
    Records data for GO/NO-GO memo. No hard CI gating assertions.

    Benchmarks BOTH shadow mode (default) AND actual cutover mode."""

    def test_workload_a_cycling(self):
        """Workload A: Cycling A<->B through step_kernel_mu."""
        projs = [
            {"id": "c.ab", "pattern": {"state": "A"}, "body": {"state": "B"}},
            {"id": "c.ba", "pattern": {"state": "B"}, "body": {"state": "A"}},
        ]
        inp = {"state": "A"}

        # Derived, never hardcoded: _time_kernel_mu bounds its own sampling via
        # _stage0_profile_counts(n_runs, 5), so the same call here yields the
        # count/mode this run must report (30 by default, 3 under RCX_CI=1).
        expected_runs, _warmup, profile_mode = _stage0_profile_counts(30, 5)
        times = _time_kernel_mu(projs, inp, n_runs=30)
        stats = _stats(times)

        # Evidence integrity — shape/count/validity only, no wall-clock budget.
        assert len(times) == expected_runs
        assert stats["n"] == expected_runs
        assert profile_mode in _PROFILE_MODES
        _assert_durations_valid(times)

        print(json.dumps({
            "tier": 2,
            "workload": "cycling_ab",
            "profile_mode": profile_mode,
            "stats": stats,
        }))
        # Timing values themselves remain observational — data feeds GO/NO-GO memo

    def test_workload_b_bridge_mode(self):
        """Workload B: Bridge mode with variable binding."""
        projs = [
            {"id": "b.var", "pattern": {"x": {"var": "v"}}, "body": {"y": {"var": "v"}}},
        ]
        inp = {"x": "hello"}

        # Same argument pair the helper uses internally: (n_runs=30, warmup=5).
        expected_runs, _warmup, profile_mode = _stage0_profile_counts(30, 5)
        times = _time_kernel_mu(projs, inp, n_runs=30, kernel_mode="bridge")
        stats = _stats(times)

        # Evidence integrity — shape/count/validity only, no wall-clock budget.
        assert len(times) == expected_runs
        assert stats["n"] == expected_runs
        assert profile_mode in _PROFILE_MODES
        _assert_durations_valid(times)

        print(json.dumps({
            "tier": 2,
            "workload": "bridge_var_bind",
            "profile_mode": profile_mode,
            "stats": stats,
        }))

    def test_workload_engine_pipeline(self):
        """Workload: Full engine pipeline (run_engine_pipeline) — canonical cycling closure."""
        projs = [
            {"id": "c.ab", "pattern": {"state": "A"}, "body": {"state": "B"}},
            {"id": "c.ba", "pattern": {"state": "B"}, "body": {"state": "A"}},
        ]
        inp = {"state": "A"}

        # Same argument pair the helper uses internally: (n_runs=10, warmup=3).
        expected_runs, _warmup, expected_mode = _stage0_profile_counts(10, 3)
        times, profile_mode = _time_engine_pipeline(projs, inp, n_runs=10, warmup=3)
        stats = _stats(times)

        # Evidence integrity — shape/count/validity only, no wall-clock budget.
        # profile_mode is returned BY the helper, so equality against an
        # independent derivation is a real cross-check, not a tautology.
        assert len(times) == expected_runs
        assert stats["n"] == expected_runs
        assert profile_mode == expected_mode
        assert profile_mode in _PROFILE_MODES
        _assert_durations_valid(times)

        print(json.dumps({
            "tier": 2,
            "workload": "engine_pipeline_cycling_shadow",
            "profile_mode": profile_mode,
            "stats": stats,
        }))

    def test_workload_cutover_kernel(self, monkeypatch):
        """Cutover mode: step_kernel_mu with VM primary (no shadow)."""
        import rcx_pi.selfhost.step_mu as mod
        monkeypatch.setattr(mod, "_STAGE0_VM_CUTOVER", True)
        monkeypatch.setattr(mod, "_STAGE0_SHADOW_ENABLED", False)

        projs = [
            {"id": "c.ab", "pattern": {"state": "A"}, "body": {"state": "B"}},
            {"id": "c.ba", "pattern": {"state": "B"}, "body": {"state": "A"}},
        ]
        inp = {"state": "A"}

        # Same argument pair the helper uses internally: (n_runs=30, warmup=5).
        expected_runs, _warmup, profile_mode = _stage0_profile_counts(30, 5)
        times = _time_kernel_mu(projs, inp, n_runs=30)
        stats = _stats(times)

        # Evidence integrity — shape/count/validity only, no wall-clock budget.
        assert len(times) == expected_runs
        assert stats["n"] == expected_runs
        assert profile_mode in _PROFILE_MODES
        _assert_durations_valid(times)

        print(json.dumps({
            "tier": 2,
            "workload": "cycling_ab_cutover",
            "profile_mode": profile_mode,
            "stats": stats,
        }))

    def test_workload_cutover_engine_pipeline(self, monkeypatch):
        """Cutover mode: full engine pipeline with VM primary."""
        import rcx_pi.selfhost.step_mu as mod
        monkeypatch.setattr(mod, "_STAGE0_VM_CUTOVER", True)
        monkeypatch.setattr(mod, "_STAGE0_SHADOW_ENABLED", False)

        projs = [
            {"id": "c.ab", "pattern": {"state": "A"}, "body": {"state": "B"}},
            {"id": "c.ba", "pattern": {"state": "B"}, "body": {"state": "A"}},
        ]
        inp = {"state": "A"}

        # Same argument pair the helper uses internally: (n_runs=10, warmup=3).
        expected_runs, _warmup, expected_mode = _stage0_profile_counts(10, 3)
        times, profile_mode = _time_engine_pipeline(projs, inp, n_runs=10, warmup=3)
        stats = _stats(times)

        # Evidence integrity — shape/count/validity only, no wall-clock budget.
        assert len(times) == expected_runs
        assert stats["n"] == expected_runs
        assert profile_mode == expected_mode
        assert profile_mode in _PROFILE_MODES
        _assert_durations_valid(times)

        print(json.dumps({
            "tier": 2,
            "workload": "engine_pipeline_cycling_cutover",
            "profile_mode": profile_mode,
            "stats": stats,
        }))


def _has_mark(obj, mark_name):
    marks = getattr(obj, "pytestmark", [])
    if not isinstance(marks, (list, tuple)):
        marks = [marks]
    return any(getattr(mark, "name", None) == mark_name for mark in marks)


def test_stage0_vm_performance_tier2_remains_l4_expensive_marked():
    """Lock repeated full-pipeline timing workloads into the l4_expensive lane."""
    assert _has_mark(TestTier2IntegrationWorkloads, "slow")
    assert _has_mark(TestTier2IntegrationWorkloads, "l4_expensive")
