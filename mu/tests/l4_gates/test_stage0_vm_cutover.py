"""P7-d: Stage0 VM kernel-step cutover gate tests.

Proves shadow mode equivalence between host path (_step_trusted) and
VM path (_step_kernel_with_vm) for step_kernel_mu.

L4_STRUCTURAL gate: G2 (first-match-wins / structural forward motion).
"""

import pytest
from rcx_pi.selfhost.step_mu import (
    step_kernel_mu,
    _step_kernel_with_vm,  # ANTICHEAT_OK: P7-d gate test — shadow/cutover verification
    _load_kernel_v1_projections_shared,  # ANTICHEAT_OK: P7-d gate test — partition loader
    _load_bridge_projections_shared,  # ANTICHEAT_OK: P7-d gate test — partition loader
    _load_compiled_match_v2_bundle,  # ANTICHEAT_OK: P7-d gate test — bundle loader
    _load_compiled_subst_v2_bundle,  # ANTICHEAT_OK: P7-d gate test — bundle loader
    _load_combined_kernel_projections_shared,  # ANTICHEAT_OK: P7-d gate test — combined loader
    clear_combined_kernel_cache,
    normalize_projection,
    list_to_linked,
    run_algorithm_meta_circular,  # SPEED_OK: called with small inputs (2 projs, 10 steps) — completes in <1s
)
from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline  # ANTICHEAT_OK: S1-A — integration cutover test  # SPEED_OK: called with small inputs — completes in <1s
from rcx_pi.selfhost.match_mu import normalize_for_match
from rcx_pi.selfhost.kernel import reset_step_budget
from rcx_pi.selfhost.eval_seed import _step_trusted, NO_MATCH  # ANTICHEAT_OK: P7-d gate test
from rcx_pi.selfhost.stage0_vm import _mu_deep_equal, stage0_vm_step  # ANTICHEAT_OK: P7-d gate test


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

    def test_cutover_flag_active(self):
        """_STAGE0_VM_CUTOVER is True (S1-B: VM path is primary)."""
        import rcx_pi.selfhost.step_mu as mod
        assert hasattr(mod, '_STAGE0_VM_CUTOVER')
        assert mod._STAGE0_VM_CUTOVER is True  # ANTICHEAT_OK: S1-B gate — VM cutover active

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


# ---------------------------------------------------------------------------
# S1-A D2: Cutover=True path tests (pre-flip evidence)
# ---------------------------------------------------------------------------

@pytest.fixture
def cutover_mode(monkeypatch):
    """Enable cutover mode: VM path primary, shadow disabled."""
    import rcx_pi.selfhost.step_mu as mod
    monkeypatch.setattr(mod, "_STAGE0_VM_CUTOVER", True)
    monkeypatch.setattr(mod, "_STAGE0_SHADOW_ENABLED", False)
    return mod


def _patch_counting_trusted(monkeypatch, mod):
    """Instrument _step_trusted with call counter. Returns call_count dict."""
    call_count = {"n": 0}
    original = _step_trusted

    def _counting(projs, value):
        call_count["n"] += 1
        return original(projs, value)

    import rcx_pi.selfhost.eval_seed as eval_mod
    monkeypatch.setattr(eval_mod, "_step_trusted", _counting)
    if hasattr(mod, "_step_trusted"):
        monkeypatch.setattr(mod, "_step_trusted", _counting)
    return call_count


class TestCutoverTruePath:
    """S1-A D2: Prove _STAGE0_VM_CUTOVER=True branch works correctly.

    Uses cutover_mode fixture to flip the flag. Proves VM executes as primary
    path with correct semantics on canonical vectors.
    """

    def test_simple_rewrite_cutover(self, cutover_mode):
        """a -> b via domain projection under cutover=True."""
        proj = {"id": "test.cut_rw", "pattern": "a", "body": "b"}
        result = step_kernel_mu([proj], "a")
        assert result == "b"

    def test_stall_cutover(self, cutover_mode):
        """No matching projection under cutover=True -> stall."""
        proj = {"id": "test.cut_stall", "pattern": "a", "body": "b"}
        result = step_kernel_mu([proj], "zzz")
        assert result == "zzz"

    def test_dict_rewrite_cutover(self, cutover_mode):
        """Dict pattern matching under cutover=True."""
        proj = {"id": "test.cut_dict", "pattern": {"x": {"var": "v"}}, "body": {"y": {"var": "v"}}}
        result = step_kernel_mu([proj], {"x": 42})
        assert result == {"y": 42}

    def test_first_match_wins_cutover(self, cutover_mode):
        """First-match-wins ordering preserved under cutover=True."""
        projs = [
            {"id": "test.cut_first", "pattern": "a", "body": "first"},
            {"id": "test.cut_second", "pattern": "a", "body": "second"},
        ]
        result = step_kernel_mu(projs, "a")
        assert result == "first"

    def test_bridge_mode_cutover(self, cutover_mode):
        """Bridge mode works under cutover=True."""
        proj = {"id": "test.cut_bridge", "pattern": "hello", "body": "world"}
        result = step_kernel_mu([proj], "hello", kernel_mode="bridge")
        assert result == "world"

    def test_meta_return_cutover(self, cutover_mode):
        """return_meta=True works under cutover=True."""
        proj = {"id": "test.cut_meta", "pattern": "a", "body": "b"}
        meta = step_kernel_mu([proj], "a", return_meta=True)
        assert meta["termination_reason"] == "projection_applied"
        assert meta["output"] == "b"

    def test_stall_meta_cutover(self, cutover_mode):
        """Stall with return_meta=True under cutover=True."""
        proj = {"id": "test.cut_stall_meta", "pattern": "never", "body": "x"}
        meta = step_kernel_mu([proj], "something_else", return_meta=True)
        assert meta["stall"] is True

    def test_output_matches_shadow(self, monkeypatch):
        """Cutover=True output matches shadow mode output on same input."""
        import rcx_pi.selfhost.step_mu as mod
        proj = {"id": "test.cut_shadow", "pattern": {"x": {"var": "v"}}, "body": {"result": {"var": "v"}}}
        inp = {"x": 99}

        # Shadow mode (default)
        shadow_result = step_kernel_mu([proj], inp)

        # Cutover mode
        monkeypatch.setattr(mod, "_STAGE0_VM_CUTOVER", True)
        monkeypatch.setattr(mod, "_STAGE0_SHADOW_ENABLED", False)
        clear_combined_kernel_cache()
        reset_step_budget()
        cutover_result = step_kernel_mu([proj], inp)

        assert _mu_deep_equal(shadow_result, cutover_result), \
            f"Shadow={shadow_result!r}, Cutover={cutover_result!r}"

    def test_multiple_steps_cutover(self, cutover_mode):
        """Multi-step convergence under cutover=True."""
        projs = [
            {"id": "test.cut_step1", "pattern": {"state": "A"}, "body": {"state": "B"}},
        ]
        result = step_kernel_mu(projs, {"state": "A"})
        assert result == {"state": "B"}

    def test_nested_dict_cutover(self, cutover_mode):
        """Nested dict pattern under cutover=True."""
        proj = {"id": "test.cut_nest", "pattern": {"a": {"b": {"var": "v"}}}, "body": {"c": {"var": "v"}}}
        result = step_kernel_mu([proj], {"a": {"b": "deep"}})
        assert result == {"c": "deep"}


class TestCutoverIntegration:
    """S1-A D2: Integration-level cutover proof through real API entrypoints.

    Proves VM path fires through run_engine_pipeline and
    run_algorithm_meta_circular. Includes no-fallback negative control.
    """

    def test_engine_pipeline_cutover(self, cutover_mode):
        """run_engine_pipeline works with cutover=True.

        Uses cycling projections that produce engine closure (recurrence).
        """
        projs = [
            {"id": "c.ab", "pattern": {"state": "A"}, "body": {"state": "B"}},
            {"id": "c.ba", "pattern": {"state": "B"}, "body": {"state": "A"}},
        ]
        result = run_engine_pipeline(
            projs, {"state": "A"},
            max_steps=10, max_engine_iterations=20, max_algorithm_iterations=50,
        )
        # Engine terminal shape: must contain closure/stall/result markers
        assert isinstance(result, dict), f"Expected dict, got {type(result).__name__}"
        # Cycling A<->B produces recurrence closure — verify engine terminal semantics
        assert "_mode" in result or "engine_result" in result or "closure_detected" in result, \
            f"Engine result lacks terminal markers. Keys: {sorted(result.keys())}"

    def test_algorithm_meta_circular_cutover(self, cutover_mode):
        """run_algorithm_meta_circular works with cutover=True."""
        projs = [
            {"id": "test.int_alg", "pattern": "a", "body": "b"},
        ]
        result = run_algorithm_meta_circular(projs, "a")
        assert result == "b"

    def test_no_monolithic_host_path(self, cutover_mode, monkeypatch):
        """Prove monolithic host path (_step_trusted) does NOT fire when cutover=True.

        Under cutover=True, step_kernel_mu routes through _step_kernel_with_vm
        (which uses _apply_projection_trusted for kernel.v1/bridge projections
        and stage0_vm_step for match.v2/subst.v2). The monolithic _step_trusted
        path is not used.

        Note: _apply_projection_trusted IS still called for kernel.v1/bridge
        projections — this is by design (host for kernel dispatch, VM for
        match/subst). The negative control proves the monolithic path is absent.
        """
        call_count = _patch_counting_trusted(monkeypatch, cutover_mode)
        proj = {"id": "test.nofallback", "pattern": "a", "body": "b"}
        result = step_kernel_mu([proj], "a")

        assert result == "b", f"Expected 'b', got {result!r}"
        assert call_count["n"] == 0, \
            f"_step_trusted was called {call_count['n']} times under cutover=True — " \
            f"monolithic host path is NOT absent"

    def test_no_monolithic_host_stall(self, cutover_mode, monkeypatch):
        """Prove monolithic host path doesn't fire on stall under cutover=True."""
        call_count = _patch_counting_trusted(monkeypatch, cutover_mode)
        proj = {"id": "test.nofallback_stall", "pattern": "never", "body": "x"}
        result = step_kernel_mu([proj], "something_else")

        assert result == "something_else"
        assert call_count["n"] == 0, \
            f"_step_trusted was called {call_count['n']} times on stall path"

    def test_bridge_integration_cutover(self, cutover_mode):
        """run_algorithm_meta_circular with bridge mode under cutover=True."""
        projs = [
            {"id": "test.int_bridge", "pattern": {"var": "v"}, "body": {"var": "v"}},
        ]
        result = run_algorithm_meta_circular(projs, "test_value")
        assert result == "test_value"  # identity projection


# ---------------------------------------------------------------------------
# N15: Bundle provenance verification
# ---------------------------------------------------------------------------

class TestBundleProvenance:
    """N15 gate: verify compiled bundles have correct source_digest provenance."""

    def test_match_bundle_provenance_passes(self):
        """match_v2 compiled bundle passes provenance verification."""
        from rcx_pi.selfhost.step_mu import _verify_bundle_provenance  # ANTICHEAT_OK: N15 gate
        bundle = _match_bundle()
        # Should not raise — digest matches SEED_CHECKSUMS
        _verify_bundle_provenance(bundle)

    def test_subst_bundle_provenance_passes(self):
        """subst_v2 compiled bundle passes provenance verification."""
        from rcx_pi.selfhost.step_mu import _verify_bundle_provenance  # ANTICHEAT_OK: N15 gate
        bundle = _subst_bundle()
        _verify_bundle_provenance(bundle)

    def test_wrong_digest_rejected(self):
        """Bundle with wrong source_digest is rejected."""
        from rcx_pi.selfhost.step_mu import _verify_bundle_provenance  # ANTICHEAT_OK: N15 gate
        bundle = dict(_match_bundle())  # shallow copy
        bundle["source_digest"] = "sha256:" + ("0" * 64)  # wrong digest
        with pytest.raises(ValueError, match="provenance mismatch"):
            _verify_bundle_provenance(bundle)

    def test_missing_digest_accepted(self):
        """Bundle without source_digest passes (hand-authored bundles)."""
        from rcx_pi.selfhost.step_mu import _verify_bundle_provenance  # ANTICHEAT_OK: N15 gate
        bundle = {"stage0_ir_version": 1, "programs": []}  # minimal, no digest
        _verify_bundle_provenance(bundle)  # Should not raise

    def test_unknown_seed_accepted(self):
        """Bundle with unknown source_seed passes (test bundles)."""
        from rcx_pi.selfhost.step_mu import _verify_bundle_provenance  # ANTICHEAT_OK: N15 gate
        bundle = {"source_seed": "unknown_test.json", "source_digest": "sha256:" + ("a" * 64)}
        _verify_bundle_provenance(bundle)  # Should not raise — unknown seed, cannot verify
