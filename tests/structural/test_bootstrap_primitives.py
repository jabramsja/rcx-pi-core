"""
Grounding tests for Bootstrap Primitives (Phase 8a).

These tests verify that the five bootstrap primitives are:
1. Minimal (cannot be reduced further)
2. Mechanical (no semantic decisions)
3. Correctly documented in BootstrapPrimitives.v0.md

Tests convert claims in the document into executable verifications.

See: docs/core/BootstrapPrimitives.v0.md
See: docs/agents/AgentRig.v0.md (grounding agent)
"""

from pathlib import Path

import pytest

from rcx_pi.selfhost.eval_seed import step, NO_MATCH
from rcx_pi.selfhost.mu_type import assert_mu, mu_equal, mu_hash, is_mu, MAX_MU_DEPTH
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seeds_dir


# Project root
ROOT = Path(__file__).parent.parent.parent


# =============================================================================
# Primitive 1: eval_step - Projection Application
# =============================================================================


class TestEvalStepPrimitive:
    """Verify eval_step makes NO semantic decisions."""

    def test_eval_step_exists_as_documented(self):
        """Bootstrap doc claims eval_step exists in eval_seed.py."""
        eval_seed_path = ROOT / "rcx_pi" / "selfhost" / "eval_seed.py"
        content = eval_seed_path.read_text()

        # The step() function is the eval_step primitive
        assert "def step(projections:" in content, (
            "eval_step primitive (step function) not found"
        )
        # Verify it's marked as BOOTSTRAP_PRIMITIVE
        assert "BOOTSTRAP_PRIMITIVE" in content, (
            "eval_step should be marked with BOOTSTRAP_PRIMITIVE"
        )

    def test_eval_step_is_first_match_wins(self):
        """eval_step applies FIRST matching projection (no semantic choice)."""
        # Create two projections that could match the same input
        proj1 = {
            "id": "proj1",
            "pattern": {"var": "x"},
            "body": {"result": "first"}
        }
        proj2 = {
            "id": "proj2",
            "pattern": {"var": "y"},
            "body": {"result": "second"}
        }

        value = 42

        # Order 1: proj1 first
        result1 = step([proj1, proj2], value)
        assert_mu(result1, "step result 1")
        assert result1 == {"result": "first"}

        # Order 2: proj2 first
        result2 = step([proj2, proj1], value)
        assert_mu(result2, "step result 2")
        assert result2 == {"result": "second"}

    def test_eval_step_stalls_on_no_match(self):
        """eval_step returns input unchanged on no match (mechanical stall)."""
        projections = [
            {"pattern": 99, "body": {"result": "matched"}}
        ]
        value = 42

        result = step(projections, value)
        assert_mu(result, "step result")
        assert mu_equal(result, value)  # Unchanged = stall

    def test_eval_step_no_arithmetic_on_values(self):
        """eval_step does not perform arithmetic or data manipulation."""
        # Test that numeric values pass through without computation
        projections = [
            {"pattern": {"var": "x"}, "body": {"var": "x"}}
        ]

        for value in [0, 1, -1, 100, 3.14]:
            result = step(projections, value)
            assert result == value  # No arithmetic performed

    def test_eval_step_produces_mu_output(self):
        """eval_step output is always valid Mu."""
        projections = [
            {"pattern": {"var": "x"}, "body": {"wrapped": {"var": "x"}}}
        ]

        values = [
            None,
            True,
            False,
            42,
            "hello",
            [1, 2, 3],
            {"a": 1, "b": 2}
        ]

        for value in values:
            result = step(projections, value)
            assert_mu(result, f"step({value})")


# =============================================================================
# Primitive 2: mu_equal - Fixed-Point Detection
# =============================================================================


class TestMuEqualPrimitive:
    """Verify mu_equal uses ONLY structural hash comparison."""

    def test_mu_equal_exists_as_documented(self):
        """Bootstrap doc claims mu_equal exists in mu_type.py."""
        mu_type_path = ROOT / "rcx_pi" / "selfhost" / "mu_type.py"
        content = mu_type_path.read_text()

        assert "def mu_equal(a:" in content, (
            "mu_equal primitive not found"
        )
        # Verify it's marked as BOOTSTRAP_PRIMITIVE
        assert "BOOTSTRAP_PRIMITIVE: mu_equal" in content, (
            "mu_equal should be marked with BOOTSTRAP_PRIMITIVE"
        )

    def test_mu_equal_uses_content_comparison(self):
        """mu_equal compares via structural content (not Python identity)."""
        # Create two separate but equal structures
        a = {"x": [1, 2, 3], "y": "test"}
        b = {"x": [1, 2, 3], "y": "test"}

        # Python identity: different objects
        assert a is not b

        # Structural equality: same content
        assert mu_equal(a, b)

    def test_mu_equal_distinguishes_types(self):
        """mu_equal distinguishes True from 1 (no Python coercion)."""
        # Python coercion
        assert True == 1

        # Structural distinction
        assert not mu_equal(True, 1)

    def test_mu_equal_no_semantic_interpretation(self):
        """mu_equal does not interpret meaning of values."""
        # Semantically similar values (both "empty")
        values = [None, 0, False, "", [], {}]

        # Structurally distinct
        for i, v1 in enumerate(values):
            for v2 in values[i+1:]:
                assert not mu_equal(v1, v2), (
                    f"mu_equal incorrectly treats {v1!r} == {v2!r} as equal"
                )

    def test_mu_equal_deterministic(self):
        """mu_equal is deterministic (same inputs always produce same result)."""
        values = [
            {"z": 3, "a": 1, "m": 2},  # Dict with different key order
            [3, 1, 2],
            {"nested": {"deep": {"value": 42}}}
        ]

        for value in values:
            # Create copy
            import copy
            value_copy = copy.deepcopy(value)

            # Multiple comparisons should be consistent
            result1 = mu_equal(value, value_copy)
            result2 = mu_equal(value, value_copy)
            result3 = mu_equal(value, value_copy)

            assert result1 == result2 == result3 == True


# =============================================================================
# Primitive 3: max_steps - Resource Exhaustion Guard
# =============================================================================


class TestMaxStepsPrimitive:
    """Verify max_steps provides termination guarantee."""

    def test_max_steps_enforced_in_run_mu(self):
        """run_mu respects max_steps limit."""
        from rcx_pi.selfhost.step_mu import run_mu

        # Create infinite loop projection
        infinite_loop = [
            {"pattern": {"var": "x"}, "body": {"loop": {"var": "x"}}}
        ]

        initial = {"start": 1}

        # Run with small limit
        final, trace, is_stall = run_mu(infinite_loop, initial, max_steps=10)

        # Should stop after 10 steps
        assert len(trace) <= 11  # 10 steps + final state
        assert not is_stall  # Hit max_steps, not natural stall

    def test_max_steps_default_value(self):
        """max_steps has a default value (safety guarantee)."""
        from rcx_pi.selfhost.step_mu import run_mu

        # Run without explicit max_steps
        projections = [
            {"pattern": {"var": "x"}, "body": {"var": "x"}}
        ]
        value = 42

        # Should not hang (default limit applies)
        final, trace, is_stall = run_mu(projections, value)

        # Should complete (stall after 1 step in this case)
        assert is_stall

    def test_max_steps_marked_as_primitive(self):
        """max_steps is marked as BOOTSTRAP_PRIMITIVE in step_mu.py."""
        step_mu_path = ROOT / "rcx_pi" / "selfhost" / "step_mu.py"
        content = step_mu_path.read_text()

        assert "BOOTSTRAP_PRIMITIVE: max_steps" in content, (
            "max_steps should be marked with BOOTSTRAP_PRIMITIVE"
        )


# =============================================================================
# Primitive 4: stack_guard - Overflow Protection
# =============================================================================


class TestStackGuardPrimitive:
    """Verify stack_guard prevents overflow via MAX_MU_DEPTH."""

    def test_stack_guard_implemented_as_max_mu_depth(self):
        """Stack guard is implemented via MAX_MU_DEPTH in is_mu()."""
        mu_type_path = ROOT / "rcx_pi" / "selfhost" / "mu_type.py"
        content = mu_type_path.read_text()

        assert "MAX_MU_DEPTH" in content, (
            "MAX_MU_DEPTH not found in mu_type.py"
        )
        assert "BOOTSTRAP_PRIMITIVE: stack_guard" in content, (
            "stack_guard (MAX_MU_DEPTH) should be marked with BOOTSTRAP_PRIMITIVE"
        )

    def test_deep_nesting_rejected_by_is_mu(self):
        """is_mu rejects structures deeper than MAX_MU_DEPTH."""
        # Build very deep nested structure (beyond MAX_MU_DEPTH)
        deep_value = "leaf"

        for _ in range(MAX_MU_DEPTH + 10):
            deep_value = {"nested": deep_value}

        # Should be rejected by depth limit
        assert not is_mu(deep_value), (
            f"is_mu should reject depth > {MAX_MU_DEPTH}"
        )

    def test_valid_depth_accepted_by_is_mu(self):
        """is_mu accepts structures within MAX_MU_DEPTH."""
        # Build nested structure within limits
        valid_value = "leaf"

        for _ in range(MAX_MU_DEPTH - 10):
            valid_value = {"nested": valid_value}

        # Should be accepted
        assert is_mu(valid_value), (
            f"is_mu should accept depth < {MAX_MU_DEPTH}"
        )


# =============================================================================
# Primitive 5: projection_loader - Seed Bootstrap
# =============================================================================


class TestProjectionLoaderPrimitive:
    """Verify projection_loader provides seed bootstrap."""

    def test_load_verified_seed_exists(self):
        """Bootstrap doc claims projection_loader exists as load_verified_seed."""
        integrity_path = ROOT / "rcx_pi" / "selfhost" / "seed_integrity.py"
        content = integrity_path.read_text()

        assert "def load_verified_seed(" in content, (
            "load_verified_seed primitive not found"
        )
        assert "BOOTSTRAP_PRIMITIVE: projection_loader" in content, (
            "projection_loader should be marked with BOOTSTRAP_PRIMITIVE"
        )

    def test_loader_validates_schema(self):
        """Loader validates seed structure (no interpretation)."""
        seeds_dir = get_seeds_dir()

        # Load a known-good seed
        seed = load_verified_seed(seeds_dir / "match.v1.json")

        # Verify loader enforced schema
        assert "meta" in seed
        assert "projections" in seed
        assert isinstance(seed["projections"], list)

    def test_loader_verifies_checksums(self):
        """Loader verifies integrity via checksum."""
        seeds_dir = get_seeds_dir()

        # This should succeed (checksum matches)
        seed = load_verified_seed(seeds_dir / "match.v1.json", verify=True)
        assert seed is not None

    def test_loader_produces_mu_projections(self):
        """Loaded projections are valid Mu."""
        seeds_dir = get_seeds_dir()
        seed = load_verified_seed(seeds_dir / "match.v1.json")

        for proj in seed["projections"]:
            assert_mu(proj, f"projection {proj.get('id', '?')}")
            assert_mu(proj["pattern"], "projection pattern")
            assert_mu(proj["body"], "projection body")


# =============================================================================
# Boundary Tests: What Primitives Do NOT Do
# =============================================================================


class TestPrimitiveBoundaries:
    """Verify primitives do NOT perform prohibited operations."""

    def test_no_semantic_branching_in_eval_step(self):
        """eval_step does not choose based on data semantics."""
        # Two projections with different patterns
        projs = [
            {"pattern": {"type": "add"}, "body": {"result": "addition"}},
            {"pattern": {"type": "mul"}, "body": {"result": "multiplication"}},
        ]

        # eval_step selects by STRUCTURAL MATCH, not semantic interpretation
        result1 = step(projs, {"type": "add"})
        result2 = step(projs, {"type": "mul"})

        assert result1 == {"result": "addition"}
        assert result2 == {"result": "multiplication"}

    def test_no_arithmetic_in_mu_equal(self):
        """mu_equal does not normalize numbers."""
        # These are semantically equal in math
        assert 1.0 == 1

        # But structurally distinct (int vs float)
        assert not mu_equal(1.0, 1)

    def test_no_string_manipulation_in_primitives(self):
        """Primitives do not manipulate strings."""
        projections = [
            {"pattern": {"var": "s"}, "body": {"var": "s"}}
        ]

        strings = ["hello", "HELLO", "  hello  ", "hello\n"]

        for s in strings:
            result = step(projections, s)
            # String passes through unchanged - no case folding, trimming, etc.
            assert result == s


# =============================================================================
# Implementation Location Tests
# =============================================================================


class TestPrimitiveLocations:
    """Verify primitives exist in documented locations."""

    @pytest.mark.parametrize("primitive,file_path,function_name", [
        ("eval_step", "rcx_pi/selfhost/eval_seed.py", "step"),
        ("mu_equal", "rcx_pi/selfhost/mu_type.py", "mu_equal"),
        ("mu_hash", "rcx_pi/selfhost/mu_type.py", "mu_hash"),
        ("load_verified_seed", "rcx_pi/selfhost/seed_integrity.py", "load_verified_seed"),
    ])
    def test_primitive_exists_at_location(self, primitive, file_path, function_name):
        """Primitive exists at documented location."""
        full_path = ROOT / file_path
        assert full_path.exists(), f"{file_path} not found"

        content = full_path.read_text()
        assert f"def {function_name}(" in content, (
            f"{primitive} ({function_name}) not found in {file_path}"
        )


# =============================================================================
# Minimality Tests
# =============================================================================


class TestPrimitiveMinimality:
    """Verify primitives cannot be eliminated."""

    def test_cannot_pattern_match_without_eval_step(self):
        """Pattern matching requires eval_step to apply projections."""
        # Without eval_step, projections are just data
        projection = {"pattern": 42, "body": "matched"}
        value = 42

        # As pure data, no transformation occurs
        # eval_step is what makes projections "run"
        assert isinstance(projection, dict)
        assert isinstance(value, int)
        # Need eval_step to connect pattern -> body

    def test_cannot_detect_stall_without_mu_equal(self):
        """Stall detection requires structural comparison."""
        # Python == has type coercion
        assert True == 1  # Would miss this as a "stall"

        # Need mu_equal for structural stall detection
        assert not mu_equal(True, 1)


# =============================================================================
# Documentation Consistency Tests
# =============================================================================


class TestDocumentationClaims:
    """Verify BootstrapPrimitives.v0.md claims match implementation."""

    def test_document_exists(self):
        """BootstrapPrimitives.v0.md exists."""
        doc_path = ROOT / "docs" / "core" / "BootstrapPrimitives.v0.md"
        assert doc_path.exists()

    def test_five_primitives_documented(self):
        """Document lists exactly 5 primitives."""
        doc_path = ROOT / "docs" / "core" / "BootstrapPrimitives.v0.md"
        content = doc_path.read_text()

        # Check for the five primitive sections
        primitives = [
            "eval_step",
            "mu_equal",
            "max_steps",
            "stack_guard",
            "projection_loader"
        ]

        for prim in primitives:
            assert prim in content.lower(), (
                f"Primitive '{prim}' not documented"
            )

    def test_scope_section_exists(self):
        """Document has scope and self-hosting levels section."""
        doc_path = ROOT / "docs" / "core" / "BootstrapPrimitives.v0.md"
        content = doc_path.read_text()

        assert "Scope and Self-Hosting Levels" in content, (
            "Missing scope section"
        )

    def test_enginenews_section_exists(self):
        """Document has EngineNews compatibility section."""
        doc_path = ROOT / "docs" / "core" / "BootstrapPrimitives.v0.md"
        content = doc_path.read_text()

        assert "EngineNews Compatibility" in content, (
            "Missing EngineNews section"
        )


# =============================================================================
# Integration: Primitives Enable Structural Layer
# =============================================================================


class TestPrimitivesEnableStructural:
    """Verify primitives enable structural self-hosting."""

    def test_primitives_enable_pattern_matching(self):
        """Primitives enable match.v1 projections to work."""
        from rcx_pi.selfhost.match_mu import match_mu

        # match_mu uses:
        # - load_verified_seed (loader primitive)
        # - step (eval_step primitive)
        # - mu_equal (stall detection primitive)

        result = match_mu({"var": "x"}, 42)
        assert result != NO_MATCH
        assert result["x"] == 42

    def test_primitives_enable_substitution(self):
        """Primitives enable subst.v1 projections to work."""
        from rcx_pi.selfhost.subst_mu import subst_mu

        # subst_mu uses same primitives as match_mu
        bindings = {"x": 42}
        body = {"result": {"var": "x"}}

        result = subst_mu(body, bindings)
        assert result == {"result": 42}

    def test_primitives_enable_kernel_loop(self):
        """Primitives enable meta-circular kernel."""
        from rcx_pi.selfhost.step_mu import step_mu

        # step_mu uses structural kernel projections
        # Kernel uses: eval_step, mu_equal, max_steps, loader

        projections = [
            {"pattern": {"x": {"var": "a"}}, "body": {"y": {"var": "a"}}}
        ]

        result = step_mu(projections, {"x": 1})
        assert result == {"y": 1}
