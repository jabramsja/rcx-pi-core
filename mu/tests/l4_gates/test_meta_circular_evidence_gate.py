"""Wave I Phase 2: Meta-Circular Execution Evidence Gate Tests.

Proves that match.v2 and subst.v2 projections execute STRUCTURALLY within
the kernel loop (`step_kernel_mu` -> `_step_trusted` -> `_apply_projection_trusted`
-> Stage0 bootstrap). The trusted path uses Stage0 host functions
(`_stage0_match`, `_stage0_substitute`) as the irreducible bootstrap.

Evidence for: L4 Gate G8, Wave I Phase 2 (L4_ENABLER).

Seven test categories (24 tests total):
1. Step count evidence (structural == 10 literal / == 11 var-bind, host-side <= 4)
2. Stage0 routing lock (runtime proof: _stage0_match called, _match_inner not called)
3. Static seed pipeline proof (kernel -> match -> subst handoff via JSON)
4. Combined kernel projection count lock (28 = 7 + 8 + 13)
5. Trusted-path call-graph proof (two-layer AST scan)
6. Cross-substrate parity (JS stepKernel same step count + result)
7. Dict pattern meta-circular execution (higher step count for complex matching)
"""

import ast
import inspect
import json
import subprocess
import textwrap

import pytest

from rcx_pi.selfhost.step_mu import (
    step_kernel_mu,
    _load_combined_kernel_projections_shared,  # ANTICHEAT_OK: projection count lock gate test
)
from rcx_pi.selfhost.eval_seed import (
    _step_trusted,  # ANTICHEAT_OK: trusted-path AST inspection for meta-circular gate
    _apply_projection_trusted,  # ANTICHEAT_OK: trusted-path AST inspection for meta-circular gate
)

from rcx_pi.selfhost import eval_seed as _eval_seed_module  # ANTICHEAT_OK: routing lock proof

from tests.repo_root import REPO_ROOT

JS_RUNTIME = REPO_ROOT / "mu" / "host" / "js" / "eval_step.js"
SEED_DIR = REPO_ROOT / "mu" / "substrate"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_function_source(func):
    """Return dedented source of a function."""
    return textwrap.dedent(inspect.getsource(func))


def _run_js_api(request_dict: dict, *, timeout: int = 60) -> dict:
    """Call JS eval_step.js JSON API and return parsed response."""
    result = subprocess.run(
        ["node", str(JS_RUNTIME), "--json-api", json.dumps(request_dict)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=timeout,
    )
    for line in result.stdout.split("\n"):
        if line.startswith("JSON_API_RESPONSE:"):
            return json.loads(line[len("JSON_API_RESPONSE:"):])
    raise RuntimeError(f"No JSON_API_RESPONSE in JS output: {result.stdout[:500]}")


def _load_seed(name: str) -> dict:
    """Load a seed JSON file from mu/substrate/."""
    path = SEED_DIR / name
    with open(path) as f:
        return json.load(f)


def _find_projection(seed: dict, proj_id: str) -> dict | None:
    """Find a projection by ID in a seed."""
    for proj in seed.get("projections", []):
        if proj.get("id") == proj_id:
            return proj
    return None


# ===========================================================================
# Test 1: Step Count Evidence
# ===========================================================================

class TestStepCountEvidence:
    """Structural execution requires exactly 10 kernel steps (literal) or 11 (var-bind).

    Host-side match+subst would be 3-4 steps (wrap, match, subst, unwrap).
    Structural execution runs match.v2 and subst.v2 projections individually,
    requiring kernel.wrap -> kernel.try -> match.wrap -> match.equal ->
    match.done -> kernel.match_success -> subst.wrap -> subst.var ->
    subst.lookup.found -> subst.done -> kernel.subst_success -> kernel.unwrap.
    """

    def test_simple_literal_match_step_count(self):
        """Simple literal match: step count proves structural execution."""
        proj = {"id": "lit", "pattern": "x", "body": "y"}
        meta = step_kernel_mu([proj], "x", return_meta=True)
        assert meta["stall"] is False
        assert meta["output"] == "y"
        # Structural execution: kernel.wrap -> kernel.try -> match.wrap ->
        # match.equal -> match.done -> kernel.match_success -> subst.wrap ->
        # subst.primitive -> subst.done -> kernel.subst_success
        # That's 10 steps. Host-side would be ~3 (match, subst, done).
        assert meta["steps_used"] == 10, (
            f"Literal match step count changed: got {meta['steps_used']}, "
            f"expected exactly 10 (structural execution lock)"
        )

    def test_stage0_routing_lock(self):
        """Runtime proof: Stage0 VM executes projections, not legacy _match_inner.

        S1-C: ALL kernel step projections execute via stage0_vm_step (compiled bundles).
        Neither _stage0_match (host Stage0) nor _match_inner (legacy) should be called
        on the step_kernel_mu path.
        """
        from unittest.mock import patch
        import rcx_pi.selfhost.stage0_vm as _vm_module  # ANTICHEAT_OK: routing lock proof
        proj = {"id": "lit", "pattern": "x", "body": "y"}
        with (  # ANTICHEAT_OK: routing lock proof requires observing internal dispatch
            patch.object(_vm_module, 'stage0_vm_step', wraps=_vm_module.stage0_vm_step) as vm_step,  # ANTICHEAT_OK
            patch.object(_eval_seed_module, '_match_inner', wraps=_eval_seed_module._match_inner) as mi,  # ANTICHEAT_OK
        ):
            step_kernel_mu([proj], "x", return_meta=True)
            assert vm_step.call_count > 0, (
                "stage0_vm_step was never called — gate is not exercising "
                "the production VM path"
            )
            assert mi.call_count == 0, (
                f"_match_inner was called {mi.call_count} times — gate is "
                f"exercising legacy path instead of production Stage0 VM"
            )

    def test_var_bind_step_count(self):
        """Variable binding: step count proves structural execution."""
        proj = {"id": "var", "pattern": {"var": "a"}, "body": {"var": "a"}}
        meta = step_kernel_mu([proj], 42, return_meta=True)
        assert meta["stall"] is False
        assert meta["output"] == 42
        assert meta["steps_used"] == 11, (
            f"Var-bind step count changed: got {meta['steps_used']}, "
            f"expected exactly 11 (structural execution lock)"
        )


# ===========================================================================
# Test 2: Static Seed Pipeline Proof
# ===========================================================================

class TestStaticSeedPipelineProof:
    """Verify kernel -> match -> subst handoff is wired structurally in seed JSON.

    This is a static proof: we inspect the seed JSON to verify that:
    - kernel.try produces {"match": ...} consumed by match.wrap
    - kernel.match_success produces {"subst": ...} consumed by subst.wrap
    - match.done produces {"_mode": "match_done"} consumed by kernel.match_success
    - subst.done produces {"_mode": "subst_done"} consumed by kernel.subst_success
    """

    @pytest.fixture(autouse=True)
    def load_seeds(self):
        self.kernel = _load_seed("kernel.v1.json")
        self.match = _load_seed("match.v2.json")
        self.subst = _load_seed("subst.v2.json")

    def test_kernel_try_produces_match_request(self):
        """kernel.try body contains 'match' key — consumed by match.wrap."""
        proj = _find_projection(self.kernel, "kernel.try")
        assert proj is not None, "kernel.try projection missing"
        body = proj["body"]
        assert "match" in body, "kernel.try body must produce {'match': ...}"
        assert "_match_ctx" in body, "kernel.try body must produce {'_match_ctx': ...}"

    def test_match_wrap_consumes_match_request(self):
        """match.wrap pattern contains 'match' key — consumes kernel.try output."""
        proj = _find_projection(self.match, "match.wrap")
        assert proj is not None, "match.wrap projection missing"
        pattern = proj["pattern"]
        assert "match" in pattern, "match.wrap pattern must match {'match': ...}"
        assert "_match_ctx" in pattern, "match.wrap pattern must match {'_match_ctx': ...}"

    def test_match_done_produces_kernel_compatible_output(self):
        """match.done body produces {"_mode": "match_done", "_status": "success", ...}."""
        proj = _find_projection(self.match, "match.done")
        assert proj is not None, "match.done projection missing"
        body = proj["body"]
        assert body.get("_mode") == "match_done"
        assert body.get("_status") == "success"
        assert "_bindings" in body
        assert "_match_ctx" in body

    def test_kernel_match_success_consumes_match_done(self):
        """kernel.match_success pattern matches match.done output shape."""
        proj = _find_projection(self.kernel, "kernel.match_success")
        assert proj is not None, "kernel.match_success projection missing"
        pattern = proj["pattern"]
        assert pattern.get("_mode") == "match_done"
        assert pattern.get("_status") == "success"
        assert "_bindings" in pattern
        assert "_match_ctx" in pattern

    def test_kernel_match_success_produces_subst_request(self):
        """kernel.match_success body contains 'subst' key — consumed by subst.wrap."""
        proj = _find_projection(self.kernel, "kernel.match_success")
        assert proj is not None
        body = proj["body"]
        assert "subst" in body, "kernel.match_success body must produce {'subst': ...}"
        assert "_subst_ctx" in body, "kernel.match_success body must produce {'_subst_ctx': ...}"

    def test_subst_wrap_consumes_subst_request(self):
        """subst.wrap pattern contains 'subst' key — consumes kernel.match_success output."""
        proj = _find_projection(self.subst, "subst.wrap")
        assert proj is not None, "subst.wrap projection missing"
        pattern = proj["pattern"]
        assert "subst" in pattern, "subst.wrap pattern must match {'subst': ...}"
        assert "_subst_ctx" in pattern, "subst.wrap pattern must match {'_subst_ctx': ...}"

    def test_subst_done_produces_kernel_compatible_output(self):
        """subst.done body produces {"_mode": "subst_done", "_result": ...}."""
        proj = _find_projection(self.subst, "subst.done")
        assert proj is not None, "subst.done projection missing"
        body = proj["body"]
        assert body.get("_mode") == "subst_done"
        assert "_result" in body
        assert "_subst_ctx" in body

    def test_kernel_subst_success_consumes_subst_done(self):
        """kernel.subst_success pattern matches subst.done output shape."""
        proj = _find_projection(self.kernel, "kernel.subst_success")
        assert proj is not None, "kernel.subst_success projection missing"
        pattern = proj["pattern"]
        assert pattern.get("_mode") == "subst_done"
        assert "_result" in pattern


# ===========================================================================
# Test 3: Combined Kernel Projection Count Lock
# ===========================================================================

class TestCombinedKernelProjectionCountLock:
    """Lock the combined kernel projection count and ordering.

    28 projections = 7 kernel.v1 + 8 match.v2 + 13 subst.v2.
    Ordering is security-critical: kernel first, then match, then subst.
    """

    def test_total_count(self):
        """Combined kernel projections must be exactly 28."""
        projs = _load_combined_kernel_projections_shared()
        assert len(projs) == 28, (
            f"Expected 28 combined kernel projections (7+8+13), got {len(projs)}"
        )

    def test_kernel_count(self):
        """First 7 projections must be kernel.v1."""
        projs = _load_combined_kernel_projections_shared()
        kernel_projs = [p for p in projs[:7] if p.get("id", "").startswith("kernel.")]
        assert len(kernel_projs) == 7, (
            f"First 7 projections must all be kernel.*, "
            f"found {len(kernel_projs)} kernel projections"
        )

    def test_match_count(self):
        """Projections 7-14 must be match.v2 (8 projections)."""
        projs = _load_combined_kernel_projections_shared()
        match_projs = [p for p in projs[7:15] if p.get("id", "").startswith("match.")]
        assert len(match_projs) == 8, (
            f"Projections 7-14 must all be match.*, "
            f"found {len(match_projs)} match projections"
        )

    def test_subst_count(self):
        """Projections 15-27 must be subst.v2 (13 projections)."""
        projs = _load_combined_kernel_projections_shared()
        subst_projs = [p for p in projs[15:28] if p.get("id", "").startswith("subst.")]
        assert len(subst_projs) == 13, (
            f"Projections 15-27 must all be subst.*, "
            f"found {len(subst_projs)} subst projections"
        )

    def test_ordering_kernel_before_match_before_subst(self):
        """Security-critical: kernel first, match second, subst third."""
        projs = _load_combined_kernel_projections_shared()
        ids = [p.get("id", "") for p in projs]
        # Find boundaries
        last_kernel = max(i for i, pid in enumerate(ids) if pid.startswith("kernel."))
        first_match = min(i for i, pid in enumerate(ids) if pid.startswith("match."))
        last_match = max(i for i, pid in enumerate(ids) if pid.startswith("match."))
        first_subst = min(i for i, pid in enumerate(ids) if pid.startswith("subst."))
        assert last_kernel < first_match, "kernel projections must come before match"
        assert last_match < first_subst, "match projections must come before subst"


# ===========================================================================
# Test 4: Trusted-Path Call-Graph Proof
# ===========================================================================

class TestTrustedPathCallGraphProof:
    """Two-layer AST proof of the trusted execution path.

    Layer 1: _step_trusted is a projection loop (for-loop iterating projections
             via _apply_projection_trusted, plus coverage hooks).
    Layer 2: _apply_projection_trusted extracts pattern/body and delegates to
             Stage0 match/subst (the irreducible bootstrap).

    Claim: trusted path = projection loop + coverage hooks + Stage0 bootstrap.
    NOT "zero host interception" — Stage0 IS host code, but it's the
    irreducible bootstrap that makes no semantic decisions.
    """

    def test_step_trusted_is_projection_loop(self):
        """_step_trusted must be a projection loop with _apply_projection_trusted as core."""
        source = _get_function_source(_step_trusted)
        tree = ast.parse(source)

        # Find all function calls in the AST
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.append(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.append(node.func.attr)

        # _step_trusted must call _apply_projection_trusted
        assert "_apply_projection_trusted" in calls, (
            "_step_trusted must call _apply_projection_trusted"
        )

        # Must NOT call match, substitute, _match_inner, _stage0_match, _stage0_substitute
        # (those would indicate host-side interception at this layer)
        forbidden = {"match", "substitute", "_match_inner", "_stage0_match", "_stage0_substitute"}
        found_forbidden = forbidden & set(calls)
        assert not found_forbidden, (
            f"_step_trusted calls {found_forbidden} directly — "
            f"projection application should go through _apply_projection_trusted"
        )

    def test_step_trusted_has_for_loop(self):
        """_step_trusted must contain a for-loop (the projection iteration)."""
        source = _get_function_source(_step_trusted)
        tree = ast.parse(source)
        for_loops = [n for n in ast.walk(tree) if isinstance(n, ast.For)]
        assert len(for_loops) >= 1, (
            "_step_trusted must contain at least one for-loop (projection iteration)"
        )

    def test_apply_projection_trusted_delegates_to_stage0(self):
        """_apply_projection_trusted must delegate to Stage0 match and substitute.

        Stage0 is the sole production path (flag removed Wave 4, 2026-03-12).
        The test verifies Stage0 functions are called directly.
        """
        source = _get_function_source(_apply_projection_trusted)
        # Stage0 is production default — require Stage0 functions, not fallbacks
        assert "_stage0_match" in source, (
            "_apply_projection_trusted must call _stage0_match "
            "(Stage0 is production default since Wave H)"
        )
        assert "_stage0_substitute" in source, (
            "_apply_projection_trusted must call _stage0_substitute "
            "(Stage0 is production default since Wave H)"
        )

    def test_apply_projection_trusted_extracts_pattern_body(self):
        """_apply_projection_trusted must extract pattern and body from projection dict."""
        source = _get_function_source(_apply_projection_trusted)
        assert '"pattern"' in source or "['pattern']" in source or '["pattern"]' in source, (
            "_apply_projection_trusted must extract 'pattern' from projection"
        )
        assert '"body"' in source or "['body']" in source or '["body"]' in source, (
            "_apply_projection_trusted must extract 'body' from projection"
        )


# ===========================================================================
# Test 5: Cross-Substrate Parity
# ===========================================================================

class TestCrossSubstrateParity:
    """JS stepKernel must produce identical step count and result for same inputs.

    Proves meta-circularity is not a Python artifact — JS uses the same
    kernel.v1 + match.v2 + subst.v2 projections structurally.
    """

    def test_literal_match_parity(self):
        """Same literal match+subst through both substrates."""
        # Python
        proj = {"id": "lit", "pattern": "x", "body": "y"}
        py_meta = step_kernel_mu([proj], "x", return_meta=True)

        # JS
        js_resp = _run_js_api({
            "action": "step_kernel_meta",
            "input": "x",
            "projections": [proj],
        })
        assert js_resp["success"], f"JS step_kernel_meta failed: {js_resp.get('error')}"
        js_meta = js_resp["result"]

        # Both must produce same result
        assert py_meta["output"] == js_meta["output"], (
            f"Output mismatch: Python={py_meta['output']}, JS={js_meta['output']}"
        )
        assert py_meta["stall"] == js_meta["stall"], (
            f"Stall mismatch: Python={py_meta['stall']}, JS={js_meta['stall']}"
        )

        # Both must use identical structural step counts
        assert py_meta["steps_used"] == js_meta["steps_used"], (
            f"Step count divergence: Python={py_meta['steps_used']}, "
            f"JS={js_meta['steps_used']} (must be identical for linear projections)"
        )
        assert py_meta["steps_used"] == 10, (
            f"Literal match step count changed: got {py_meta['steps_used']}, expected 10"
        )

    def test_var_bind_parity(self):
        """Variable binding through both substrates."""
        proj = {"id": "var", "pattern": {"var": "a"}, "body": {"var": "a"}}

        # Python
        py_meta = step_kernel_mu([proj], 42, return_meta=True)

        # JS
        js_resp = _run_js_api({
            "action": "step_kernel_meta",
            "input": 42,
            "projections": [proj],
        })
        assert js_resp["success"], f"JS step_kernel_meta failed: {js_resp.get('error')}"
        js_meta = js_resp["result"]

        assert py_meta["output"] == js_meta["output"]
        assert py_meta["stall"] == js_meta["stall"]
        # Both must use identical structural step counts
        assert py_meta["steps_used"] == js_meta["steps_used"], (
            f"Step count divergence: Python={py_meta['steps_used']}, "
            f"JS={js_meta['steps_used']} (must be identical for linear projections)"
        )
        assert py_meta["steps_used"] == 11, (
            f"Var-bind step count changed: got {py_meta['steps_used']}, expected 11"
        )


# ===========================================================================
# Test 6: Dict Pattern Meta-Circular Execution
# ===========================================================================

class TestDictPatternMetaCircularExecution:
    """Dict patterns require more kernel steps (match.dict.descend etc.).

    A dict pattern exercises deeper match.v2 projections. Step count should
    be higher than simple literal match, proving dict matching is also
    structural (not host-side isinstance checks).
    """

    def test_dict_pattern_higher_step_count(self):
        """Dict pattern match takes more steps than literal match."""
        lit_proj = {"id": "lit", "pattern": "x", "body": "y"}
        lit_meta = step_kernel_mu([lit_proj], "x", return_meta=True)

        dict_proj = {
            "id": "dict",
            "pattern": {"k": {"var": "v"}},
            "body": {"out": {"var": "v"}},
        }
        dict_meta = step_kernel_mu([dict_proj], {"k": 99}, return_meta=True)

        assert dict_meta["stall"] is False
        assert dict_meta["output"] == {"out": 99}
        assert dict_meta["steps_used"] > lit_meta["steps_used"], (
            f"Dict pattern ({dict_meta['steps_used']} steps) should take more "
            f"steps than literal ({lit_meta['steps_used']} steps) — "
            f"dict matching exercises more match.v2 projections"
        )

    def test_dict_pattern_step_count_structural(self):
        """Dict pattern must use structural step count."""
        proj = {
            "id": "dict",
            "pattern": {"k": {"var": "v"}},
            "body": {"out": {"var": "v"}},
        }
        meta = step_kernel_mu([proj], {"k": 99}, return_meta=True)
        # Dict matching: kernel.wrap -> kernel.try -> match.wrap ->
        # match.dict.descend (head/tail) -> match.var/match.equal (keys+values) ->
        # match.sibling -> ... -> match.done -> kernel.match_success ->
        # subst.wrap -> subst.descend -> ... -> subst.done ->
        # kernel.subst_success -> kernel.unwrap
        # This is significantly more than 8 steps.
        assert meta["steps_used"] >= 10, (
            f"Dict pattern step count {meta['steps_used']} too low for structural "
            f"dict matching (expected >= 10)"
        )
