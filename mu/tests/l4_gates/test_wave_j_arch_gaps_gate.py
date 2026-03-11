"""
Wave J: Architectural Gaps Gate Tests

L4_STRUCTURAL gate: validates seed dependency registry, projection-order
enforcement, control hash coverage, and hemisphere tie-break documentation.

Evidence command:
    PYTHONHASHSEED=0 pytest mu/tests/l4_gates/test_wave_j_arch_gaps_gate.py -v
"""

import pytest


# ---------------------------------------------------------------------------
# J1: Seed Dependency Registry
# ---------------------------------------------------------------------------

class TestSeedDependencyRegistry:
    """SEED_DEPENDENCIES must be consistent and validated."""

    def test_registry_exists(self):
        """SEED_DEPENDENCIES dict is importable and non-empty."""
        from rcx_pi.selfhost.seed_integrity import SEED_DEPENDENCIES
        assert isinstance(SEED_DEPENDENCIES, dict)
        assert len(SEED_DEPENDENCIES) > 0

    def test_all_dependency_targets_are_registered_seeds(self):
        """Every seed listed as a dependency must itself be a registered seed."""
        from rcx_pi.selfhost.seed_integrity import (
            SEED_DEPENDENCIES, SEED_CHECKSUMS,
        )
        for seed_name, deps in SEED_DEPENDENCIES.items():
            assert seed_name in SEED_CHECKSUMS, (
                f"Dependent seed {seed_name} not in SEED_CHECKSUMS"
            )
            for dep in deps:
                assert dep in SEED_CHECKSUMS, (
                    f"Dependency {dep} (required by {seed_name}) not in SEED_CHECKSUMS"
                )

    def test_no_circular_dependencies(self):
        """Dependency graph must be a DAG (no cycles)."""
        from rcx_pi.selfhost.seed_integrity import SEED_DEPENDENCIES

        def has_cycle(node, visited, rec_stack):
            visited.add(node)
            rec_stack.add(node)
            for dep in SEED_DEPENDENCIES.get(node, []):
                if dep not in visited:
                    if has_cycle(dep, visited, rec_stack):
                        return True
                elif dep in rec_stack:
                    return True
            rec_stack.discard(node)
            return False

        visited = set()
        for seed_name in SEED_DEPENDENCIES:
            if seed_name not in visited:
                assert not has_cycle(seed_name, visited, set()), (
                    f"Circular dependency detected involving {seed_name}"
                )

    def test_validate_seed_dependencies_catches_missing(self):
        """validate_seed_dependencies flags missing prerequisites."""
        from rcx_pi.selfhost.seed_integrity import validate_seed_dependencies
        # Load kernel.v1 without match.v2 or subst.v2 → should report errors
        errors = validate_seed_dependencies({"kernel.v1.json"})
        assert len(errors) >= 2, f"Expected ≥2 errors, got {errors}"
        assert any("match.v2.json" in e for e in errors)
        assert any("subst.v2.json" in e for e in errors)

    def test_validate_seed_dependencies_passes_complete_set(self):
        """Full production seed set should have no dependency errors."""
        from rcx_pi.selfhost.seed_integrity import (
            validate_seed_dependencies, SEED_CHECKSUMS,
        )
        all_seeds = set(SEED_CHECKSUMS.keys())
        errors = validate_seed_dependencies(all_seeds)
        assert errors == [], f"Full seed set has unsatisfied deps: {errors}"

    def test_engine_requires_recurrence_exhaustion_fix(self):
        """rcx_engine.v1 depends on recurrence.v2, exhaustion.v1, fix.v1."""
        from rcx_pi.selfhost.seed_integrity import SEED_DEPENDENCIES
        engine_deps = SEED_DEPENDENCIES.get("rcx_engine.v1.json", [])
        assert "recurrence.v2.json" in engine_deps
        assert "exhaustion.v1.json" in engine_deps
        assert "fix.v1.json" in engine_deps

    def test_kernel_requires_match_v2_subst_v2(self):
        """kernel.v1 depends on match.v2, subst.v2."""
        from rcx_pi.selfhost.seed_integrity import SEED_DEPENDENCIES
        kernel_deps = SEED_DEPENDENCIES.get("kernel.v1.json", [])
        assert "match.v2.json" in kernel_deps
        assert "subst.v2.json" in kernel_deps


# ---------------------------------------------------------------------------
# J2: Projection-Order Enforcement (Attack Resilience)
# ---------------------------------------------------------------------------

class TestProjectionOrderEnforcement:
    """Projection reordering must be caught at load time (first-match-wins security)."""

    def test_reordered_projections_rejected(self):
        """Swapping two projection IDs causes load-time rejection."""
        from rcx_pi.selfhost.seed_integrity import (
            EXPECTED_PROJECTION_IDS, validate_projection_ids,
        )
        # Take kernel.v1 and swap first two projections
        kernel_ids = EXPECTED_PROJECTION_IDS["kernel.v1.json"]
        assert len(kernel_ids) >= 2, "Need ≥2 projections to test reordering"

        # Build a fake seed with swapped order
        reordered = list(kernel_ids)
        reordered[0], reordered[1] = reordered[1], reordered[0]
        fake_seed = {
            "meta": {"version": "1.0", "name": "test", "description": "test"},
            "projections": [
                {"id": pid, "pattern": {}, "body": {}} for pid in reordered
            ],
        }

        with pytest.raises(ValueError, match="projection order mismatch"):
            validate_projection_ids("kernel.v1.json", fake_seed)

    def test_extra_projection_rejected(self):
        """Adding an unknown projection causes load-time rejection."""
        from rcx_pi.selfhost.seed_integrity import (
            EXPECTED_PROJECTION_IDS, validate_projection_ids,
        )
        kernel_ids = EXPECTED_PROJECTION_IDS["kernel.v1.json"]
        extended = list(kernel_ids) + ["kernel.injected"]
        fake_seed = {
            "meta": {"version": "1.0", "name": "test", "description": "test"},
            "projections": [
                {"id": pid, "pattern": {}, "body": {}} for pid in extended
            ],
        }

        with pytest.raises(ValueError):
            validate_projection_ids("kernel.v1.json", fake_seed)

    def test_missing_projection_rejected(self):
        """Removing a projection causes load-time rejection."""
        from rcx_pi.selfhost.seed_integrity import (
            EXPECTED_PROJECTION_IDS, validate_projection_ids,
        )
        kernel_ids = EXPECTED_PROJECTION_IDS["kernel.v1.json"]
        truncated = list(kernel_ids)[:-1]  # Remove last
        fake_seed = {
            "meta": {"version": "1.0", "name": "test", "description": "test"},
            "projections": [
                {"id": pid, "pattern": {}, "body": {}} for pid in truncated
            ],
        }

        with pytest.raises(ValueError):
            validate_projection_ids("kernel.v1.json", fake_seed)

    def test_all_seeds_have_projection_id_registry(self):
        """Every registered seed must have an EXPECTED_PROJECTION_IDS entry."""
        from rcx_pi.selfhost.seed_integrity import (
            SEED_CHECKSUMS, EXPECTED_PROJECTION_IDS,
        )
        for seed_name in SEED_CHECKSUMS:
            assert seed_name in EXPECTED_PROJECTION_IDS, (
                f"Seed {seed_name} has no EXPECTED_PROJECTION_IDS entry — "
                f"projection ordering is NOT validated (fail-open gap)"
            )


# ---------------------------------------------------------------------------
# J3: Control Hash Coverage (Policy B.1 Audit)
# ---------------------------------------------------------------------------

class TestControlHashCoverage:
    """All control paths must use mu_hash_control_cached, not mu_hash_cached.

    These tests use inspect.getsource() to audit source code — they do NOT
    call the imported functions at runtime.
    """

    def test_step_kernel_mu_uses_control_hash(self):
        """step_kernel_mu must use mu_hash_control_cached for stall detection."""
        import inspect
        from rcx_pi.selfhost.step_mu import step_kernel_mu  # SPEED_OK: inspect.getsource only
        source = inspect.getsource(step_kernel_mu)
        assert "mu_hash_control_cached" in source, (
            "step_kernel_mu must use mu_hash_control_cached (Policy B.1)"
        )

    def test_run_mu_uses_control_hash(self):
        """run_mu must use mu_hash_control_cached for convergence check."""
        import inspect
        from rcx_pi.selfhost.step_mu import run_mu  # SPEED_OK: inspect.getsource only
        source = inspect.getsource(run_mu)
        assert "mu_hash_control_cached" in source, (
            "run_mu must use mu_hash_control_cached (Policy B.1)"
        )

    def test_run_mu_structural_uses_control_hash(self):
        """run_mu_structural must use mu_hash_control_cached."""
        import inspect
        from rcx_pi.selfhost.step_mu import run_mu_structural  # SPEED_OK: inspect.getsource only
        source = inspect.getsource(run_mu_structural)
        assert "mu_hash_control_cached" in source, (
            "run_mu_structural must use mu_hash_control_cached (Policy B.1)"
        )

    def test_projection_runner_uses_control_hash(self):
        """projection_runner module must use mu_hash_control_cached."""
        import inspect
        import rcx_pi.selfhost.projection_runner as pr_mod
        source = inspect.getsource(pr_mod)
        assert "mu_hash_control_cached" in source, (
            "projection_runner must use mu_hash_control_cached (Policy B.1)"
        )

    def test_nonlinear_binding_uses_data_hash(self):
        """Non-linear binding conflict detection must use mu_hash_cached (NOT control).

        eval_seed module uses mu_hash_cached for binding conflict detection
        (not mu_hash_control_cached). Control hash would break int/float type
        distinction needed for correct non-linear conflict detection.
        """
        import inspect
        import rcx_pi.selfhost.eval_seed as es_mod
        source = inspect.getsource(es_mod)
        # Module must import mu_hash_cached (used for non-linear binding)
        assert "mu_hash_cached" in source, (
            "eval_seed must use mu_hash_cached for non-linear binding (not control hash)"
        )
        # Verify the comment explaining WHY (not control hash) exists
        assert "NOT mu_hash_control_cached" in source, (
            "eval_seed should document why mu_hash_cached is used instead of control hash"
        )


# ---------------------------------------------------------------------------
# J4: Hemisphere Routing Tie-Break (Policy D — Documented Undefined)
# ---------------------------------------------------------------------------

class TestHemisphereRoutingTieBreak:
    """Hemisphere routing tie-break behavior must be documented as undefined.

    Uses structural analysis (projection IDs, seed data) rather than calling
    run_hemisphere_routing or run_mu directly — keeps tests fast/core-tier.
    """

    def test_hemisphere_bucket_names_are_fixed(self):
        """Hemisphere seed produces exactly 5 fixed bucket names."""
        from rcx_pi.selfhost.seed_integrity import EXPECTED_PROJECTION_IDS
        hemi_ids = EXPECTED_PROJECTION_IDS["hemispheres.v1.json"]
        # The "add" projections define the bucket names
        add_ids = [pid for pid in hemi_ids if pid.startswith("hemisphere.add.")]
        expected_buckets = {"r_null", "r_inf", "r_a", "lobes", "sink"}
        actual_buckets = {pid.replace("hemisphere.add.", "") for pid in add_ids}
        assert actual_buckets == expected_buckets, (
            f"Expected buckets {expected_buckets}, got {actual_buckets}"
        )

    def test_hemisphere_classify_order_is_stable(self):
        """Hemisphere classification projections have a fixed priority order.

        Order matters: exhaustion before null before closure before stall before default.
        This IS the tie-break — it's defined by projection order (first-match-wins).
        Policy D notes this order is structural but the tie-break WITHIN a bucket
        (when two entries both route to the same bucket) uses insertion order, which
        is host-language-dependent and thus undefined.
        """
        from rcx_pi.selfhost.seed_integrity import EXPECTED_PROJECTION_IDS
        hemi_ids = EXPECTED_PROJECTION_IDS["hemispheres.v1.json"]
        classify_ids = [pid for pid in hemi_ids if pid.startswith("hemisphere.classify.")]
        # Expected priority order (projection position = priority)
        expected_order = [
            "hemisphere.classify.exhaustion",
            "hemisphere.classify.null",
            "hemisphere.classify.closure",
            "hemisphere.classify.stall",
            "hemisphere.classify.default",
        ]
        assert classify_ids == expected_order, (
            f"Hemisphere classify priority order changed! "
            f"Expected {expected_order}, got {classify_ids}"
        )


# ---------------------------------------------------------------------------
# J5: Seed Dependency Parity (Python ↔ JS)
# ---------------------------------------------------------------------------

class TestSeedDependencyParity:
    """Python and JS seed dependency registries must match."""

    def test_js_seed_dependencies_match_python(self):
        """JS SEED_DEPENDENCIES must mirror Python SEED_DEPENDENCIES."""
        import json
        from pathlib import Path
        from rcx_pi.selfhost.seed_integrity import SEED_DEPENDENCIES

        # Read JS seed_loader.js and extract SEED_DEPENDENCIES
        js_path = Path(__file__).parent.parent.parent / "host" / "js" / "core" / "seed_loader.js"
        js_content = js_path.read_text()

        # For each Python dependency, verify the JS file mentions it
        for seed_name, deps in SEED_DEPENDENCIES.items():
            assert seed_name in js_content, (
                f"JS seed_loader.js missing dependency entry for {seed_name}"
            )
            for dep in deps:
                assert dep in js_content, (
                    f"JS seed_loader.js missing dependency {dep} for {seed_name}"
                )
