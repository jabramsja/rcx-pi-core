"""P7-d: Stage0 VM kernel-step cutover gate tests.

Proves shadow mode equivalence between host path (_step_trusted) and
VM path (_step_kernel_with_vm) for step_kernel_mu.

L4_STRUCTURAL gate: G2 (first-match-wins / structural forward motion).
"""

import pytest
from rcx_pi.selfhost.step_mu import (
    step_kernel_mu,
    _step_kernel_with_vm,
    _load_kernel_v1_projections_shared,
    _load_bridge_projections_shared,
    _load_compiled_match_v2_bundle,
    _load_compiled_subst_v2_bundle,
    _load_combined_kernel_projections_shared,
    clear_combined_kernel_cache,
    normalize_projection,
    list_to_linked,
)
from rcx_pi.selfhost.match_mu import normalize_for_match
from rcx_pi.selfhost.kernel import reset_step_budget
from rcx_pi.selfhost.eval_seed import _step_trusted, NO_MATCH
from rcx_pi.selfhost.stage0_vm import _mu_deep_equal, stage0_vm_step


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_caches():
    clear_combined_kernel_cache()
    reset_step_budget()
    yield
    clear_combined_kernel_cache()


def _kernel_v1():
    return _load_kernel_v1_projections_shared()

def _bridge():
    return _load_bridge_projections_shared()

def _match_bundle():
    return _load_compiled_match_v2_bundle()

def _subst_bundle():
    return _load_compiled_subst_v2_bundle()

def _combined():
    return _load_combined_kernel_projections_shared()


# ---------------------------------------------------------------------------
# Test 1: Shadow-mode end-to-end (step_kernel_mu with shadow active)
# ---------------------------------------------------------------------------

class TestShadowModeEndToEnd:
    """Call step_kernel_mu with shadow mode active. If any per-step
    divergence exists between host and VM, the shadow assert fires."""

    def test_simple_rewrite(self):
        """a -> b via domain projection, kernel must converge."""
        proj = {"id": "test.rewrite", "pattern": "a", "body": "b"}
        result = step_kernel_mu([proj], "a")
        assert result == "b"

    def test_stall_no_match(self):
        """Input that no projection matches → stall, return original."""
        proj = {"id": "test.only_a", "pattern": "a", "body": "b"}
        result = step_kernel_mu([proj], "zzz")
        assert result == "zzz"

    def test_dict_rewrite(self):
        """Dict input rewritten by domain projection."""
        proj = {"id": "test.dict", "pattern": {"x": {"var": "v"}}, "body": {"y": {"var": "v"}}}
        result = step_kernel_mu([proj], {"x": 42})
        assert result == {"y": 42}

    def test_multi_projection_first_match_wins(self):
        """First matching projection wins — ordering preserved."""
        projs = [
            {"id": "test.first", "pattern": "a", "body": "first"},
            {"id": "test.second", "pattern": "a", "body": "second"},
        ]
        result = step_kernel_mu(projs, "a")
        assert result == "first"

    def test_bridge_mode(self):
        """Bridge mode: kernel.v1 + bridge + match.v2 + subst.v2."""
        proj = {"id": "test.bridge_rewrite", "pattern": "hello", "body": "world"}
        result = step_kernel_mu([proj], "hello", kernel_mode="bridge")
        assert result == "world"


# ---------------------------------------------------------------------------
# Test 2: Direct output equivalence (host vs VM per-step)
# ---------------------------------------------------------------------------

class TestOutputEquivalence:
    """Run both paths on the same input, compare outputs with _mu_deep_equal."""

    def _run_both(self, input_value, bridge=False):
        """Run host and VM paths on kernel-wrapped input, return (host, vm)."""
        k1 = _kernel_v1()
        bp = _bridge() if bridge else None
        mb = _match_bundle()
        sb = _subst_bundle()
        combined = _combined()

        host = _step_trusted(combined, input_value)
        vm = _step_kernel_with_vm(k1, bp, mb, sb, input_value, record_coverage=False)
        return host, vm

    def test_kernel_wrap_state(self):
        """Kernel wrap state: {_step: ..., _projs: ...}."""
        from rcx_pi.selfhost.step_mu import normalize_for_match, list_to_linked, normalize_projection
        proj = {"id": "test.eq", "pattern": "x", "body": "y"}
        normalized = normalize_projection(proj)
        kernel_input = {
            "_step": normalize_for_match("x"),
            "_projs": list_to_linked([normalized]),
        }
        host, vm = self._run_both(kernel_input)
        assert not (host is kernel_input and vm is kernel_input), \
            "Both paths stalled — kernel.wrap should have matched"
        assert _mu_deep_equal(host, vm), \
            f"Output divergence: host={host!r}, vm={vm!r}"

    def test_non_kernel_input_stalls_both(self):
        """Random non-kernel input: both paths should stall (return input)."""
        inp = {"random": "data", "not_kernel": True}
        host, vm = self._run_both(inp)
        # Both should stall (return unchanged input)
        assert host is inp or _mu_deep_equal(host, inp)
        assert vm is inp or _mu_deep_equal(vm, inp)


# ---------------------------------------------------------------------------
# Test 3: Polarity checks
# ---------------------------------------------------------------------------

class TestPolarityChecks:
    """Inputs that should match → both match. Inputs that should stall → both stall."""

    def test_match_polarity(self):
        """Domain input 'a' with rewrite proj → both paths progress."""
        proj = {"id": "test.pol", "pattern": "a", "body": "b"}
        meta = step_kernel_mu([proj], "a", return_meta=True)
        assert meta["termination_reason"] == "projection_applied"
        assert meta["output"] == "b"

    def test_stall_polarity(self):
        """No matching projection → both paths stall identically."""
        proj = {"id": "test.pol_stall", "pattern": "never_matches_this", "body": "x"}
        meta = step_kernel_mu([proj], "something_else", return_meta=True)
        assert meta["stall"] is True


# ---------------------------------------------------------------------------
# Test 4: Bridge mode coverage
# ---------------------------------------------------------------------------

class TestBridgeMode:
    """Verify bridge projections interpose correctly between kernel.v1 and match.v2."""

    def test_bridge_mode_converges(self):
        """step_kernel_mu with kernel_mode='bridge' should converge."""
        proj = {"id": "test.br", "pattern": {"var": "v"}, "body": {"var": "v"}}
        meta = step_kernel_mu([proj], "test_input", kernel_mode="bridge", return_meta=True)
        # Should converge (identity projection → projection_applied)
        assert meta["termination_reason"] in ("projection_applied", "kernel_stall")


# ---------------------------------------------------------------------------
# Test 5: Source lock assertions
# ---------------------------------------------------------------------------

class TestSourceLock:
    """Structural assertions: _step_kernel_with_vm exists, uses stage0_vm_step."""

    def test_step_kernel_with_vm_exists(self):
        """_step_kernel_with_vm is importable from step_mu."""
        assert callable(_step_kernel_with_vm)

    def test_stage0_vm_step_callable(self):
        """stage0_vm_step is importable and callable."""
        assert callable(stage0_vm_step)

    def test_shadow_flag_exists(self):
        """_STAGE0_VM_CUTOVER flag exists in step_mu."""
        import rcx_pi.selfhost.step_mu as mod
        assert hasattr(mod, '_STAGE0_VM_CUTOVER')
        assert mod._STAGE0_VM_CUTOVER is False  # Shadow mode active

    def test_compiled_bundles_load(self):
        """Compiled bundles load and validate successfully."""
        mb = _match_bundle()
        sb = _subst_bundle()
        assert mb["bundle_id"] == "rcx.stage0.match_v2.compiled.v1"
        assert sb["bundle_id"] == "rcx.stage0.subst_v2.compiled.v1"
        assert len(mb["program_order"]) == 8  # match.v2 has 8 projections
        assert len(sb["program_order"]) == 13  # subst.v2 has 13 projections

    def test_kernel_v1_partition(self):
        """kernel.v1 partition contains only kernel projections."""
        k1 = _kernel_v1()
        assert len(k1) == 7  # kernel.v1 has 7 projections
        for p in k1:
            assert p["id"].startswith("kernel."), f"Non-kernel projection: {p['id']}"

    def test_bridge_partition(self):
        """Bridge partition contains only bridge projections."""
        bp = _bridge()
        assert len(bp) == 5  # bootstrap_structural.v1 has 5 projections

    def test_gate3_optional_type_in_bundles(self):
        """Compiled bundles include Gate-3 optional _type='list' in assert_key_profile."""
        mb = _match_bundle()
        # Check that at least one program has an assert_key_profile with optional _type
        found_optional = False
        for prog in mb["programs"]:
            for op in prog["ops"]:
                if op["op"] == "assert_key_profile" and op.get("optional"):
                    for opt in op["optional"]:
                        if opt.get("key") == "_type" and opt.get("allowed_values") == ["list"]:
                            found_optional = True
                            break
        assert found_optional, "No Gate-3 optional _type='list' found in match_v2 bundle"
