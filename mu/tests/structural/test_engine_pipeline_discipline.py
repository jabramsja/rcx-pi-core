"""
Engine pipeline entry discipline and observer event contract guard.

Verifies:
1. run_engine_pipeline callsite inventory (AST-based, fail-closed).
2. run_hemisphere_routing callsite inventory (AST-based, fail-closed).
3. Observer event schema enforcement (mandatory fields).
4. Pipeline parameter defaults haven't drifted.
5. Engine/hemisphere result shape contracts (cross-substrate).

What this checker PROVES:
- No new raw callers of run_engine_pipeline without inventory update.
- No new raw callers of run_hemisphere_routing without inventory update.
- Observer events always contain the 6 mandatory fields.
- Pipeline defaults (max_engine_iterations, use_boot1_recursive) are stable.
- Engine terminal keys and hemisphere keys match between Python and JS.

What this checker does NOT prove:
- Semantic correctness of pipeline execution.
- Observer event ordering or content accuracy.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from rcx_pi.selfhost.step_mu import run_engine_pipeline

# ── Source paths ─────────────────────────────────────────────────────────

_REPO = Path(__file__).resolve().parents[3]
_STEP_MU_PATH = _REPO / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"


def _read_all_js_source() -> str:
    """Read all JS module files from mu/host/js/ recursively."""
    js_dir = _REPO / "mu" / "host" / "js"
    parts = []
    for f in sorted(js_dir.rglob("*.js")):
        parts.append(f.read_text())
    return "\n".join(parts)

# ── Known callsite inventory ─────────────────────────────────────────────

# All functions that call run_engine_pipeline() directly.
# If you add a new caller, add it here. This is a fail-closed guard.
# Note: _run_engine_recursive re-implements pipeline logic internally
# (it does NOT call run_engine_pipeline), so it's not in this set.
KNOWN_PIPELINE_CALLERS = {
    "run_engine_with_routing",    # Chains pipeline → hemisphere routing
    "run_engine_pipeline",        # Self-call: trampoline meta path (return_meta=True)
}


# ── AST callsite inventory ───────────────────────────────────────────────


class TestPipelineCallsiteInventory:
    """run_engine_pipeline must only be called from known locations."""

    def test_no_unknown_callers(self):
        """Fail-closed: any new caller must be added to KNOWN_PIPELINE_CALLERS."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_engine_pipeline")
        unknown = actual - KNOWN_PIPELINE_CALLERS
        assert not unknown, (
            f"Unknown run_engine_pipeline callers: {unknown}. "
            "Add to KNOWN_PIPELINE_CALLERS if intentional."
        )

    def test_no_stale_inventory(self):
        """Known callers must actually exist in source."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_engine_pipeline")
        stale = KNOWN_PIPELINE_CALLERS - actual
        assert not stale, (
            f"Stale entries in KNOWN_PIPELINE_CALLERS: {stale}. "
            "Remove if callers were deleted."
        )

    def test_caller_count_locked(self):
        """Exact caller count as documentation."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_engine_pipeline")
        assert len(actual) == 2, (
            f"Expected 2 callers, found {len(actual)}: {actual}"
        )


# ── Pipeline parameter defaults ─────────────────────────────────────────


class TestPipelineDefaults:
    """Pipeline parameter defaults must remain stable."""

    def test_max_engine_iterations_default(self):
        """Default max_engine_iterations must be 20."""
        sig = inspect.signature(run_engine_pipeline)
        param = sig.parameters.get("max_engine_iterations")
        assert param is not None, "max_engine_iterations parameter missing"
        assert param.default == 20, (
            f"max_engine_iterations default changed from 20 to {param.default}"
        )

    def test_observer_default_none(self):
        """Observer must default to None (opt-in only)."""
        sig = inspect.signature(run_engine_pipeline)
        param = sig.parameters.get("observer")
        assert param is not None, "observer parameter missing"
        assert param.default is None, (
            f"observer default changed from None to {param.default}"
        )

    def test_frozen_default_none(self):
        """Frozen must default to None."""
        sig = inspect.signature(run_engine_pipeline)
        param = sig.parameters.get("frozen")
        assert param is not None, "frozen parameter missing"
        assert param.default is None, (
            f"frozen default changed from None to {param.default}"
        )


# ── Observer event contract ──────────────────────────────────────────────

OBSERVER_MANDATORY_FIELDS = {"event_name", "step", "state_hash", "error_code", "substrate", "timestamp"}


class TestObserverEventContract:
    """Observer events must follow a strict schema."""

    @pytest.mark.slow
    def test_observer_events_have_mandatory_fields(self):
        """Every observer event must contain all 6 mandatory fields."""
        observer: list = []
        # Run a minimal pipeline to generate observer events
        projections = [
            {"id": "test.identity", "pattern": {"var": "x"}, "body": {"var": "x"}}
        ]
        run_engine_pipeline(
            projections=projections,
            input_value=42,
            max_steps=3,
            observer=observer,
        )
        assert len(observer) > 0, "No observer events emitted"
        for i, event in enumerate(observer):
            missing = OBSERVER_MANDATORY_FIELDS - set(event.keys())
            assert not missing, (
                f"Observer event [{i}] missing fields: {missing}. "
                f"Event: {event}"
            )

    @pytest.mark.slow
    def test_observer_substrate_is_python(self):
        """All observer events from Python pipeline must report substrate='python'."""
        observer: list = []
        projections = [
            {"id": "test.identity", "pattern": {"var": "x"}, "body": {"var": "x"}}
        ]
        run_engine_pipeline(
            projections=projections,
            input_value="hello",
            max_steps=3,
            observer=observer,
        )
        for i, event in enumerate(observer):
            assert event.get("substrate") == "python", (
                f"Observer event [{i}] substrate is '{event.get('substrate')}', expected 'python'"
            )

    @pytest.mark.slow
    def test_observer_timestamps_monotonic(self):
        """Observer timestamps must be strictly monotonically increasing."""
        observer: list = []
        projections = [
            {"id": "test.identity", "pattern": {"var": "x"}, "body": {"var": "x"}}
        ]
        run_engine_pipeline(
            projections=projections,
            input_value=[1, 2, 3],
            max_steps=5,
            observer=observer,
        )
        assert len(observer) >= 2, "Need at least 2 events to check monotonicity"
        for i in range(1, len(observer)):
            assert observer[i]["timestamp"] > observer[i - 1]["timestamp"], (
                f"Timestamps not monotonic at events [{i-1}] and [{i}]: "
                f"{observer[i-1]['timestamp']} >= {observer[i]['timestamp']}"
            )

    @pytest.mark.slow
    def test_observer_step_is_nonnegative(self):
        """Observer step values must be non-negative integers."""
        observer: list = []
        projections = [
            {"id": "test.identity", "pattern": {"var": "x"}, "body": {"var": "x"}}
        ]
        run_engine_pipeline(
            projections=projections,
            input_value={"a": 1},
            max_steps=3,
            observer=observer,
        )
        for i, event in enumerate(observer):
            assert isinstance(event["step"], int) and event["step"] >= 0, (
                f"Observer event [{i}] step is {event['step']}, expected non-negative int"
            )


# ── Hemisphere routing callsite inventory ────────────────────────────────

# All functions that call run_hemisphere_routing() directly in production.
KNOWN_HEMISPHERE_ROUTING_CALLERS = {
    "run_engine_with_routing",    # Only production caller
}


def _find_callers(source: str, target_func: str) -> set[str]:
    """Find all functions that call target_func() via AST walk."""
    tree = ast.parse(source)
    callers: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        func_name = node.name
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name) and child.func.id == target_func:
                    callers.add(func_name)
    return callers


class TestHemisphereRoutingCallsiteInventory:
    """run_hemisphere_routing must only be called from known locations."""

    def test_no_unknown_callers(self):
        """Fail-closed: any new caller must be added to KNOWN_HEMISPHERE_ROUTING_CALLERS."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_hemisphere_routing")
        unknown = actual - KNOWN_HEMISPHERE_ROUTING_CALLERS
        assert not unknown, (
            f"Unknown run_hemisphere_routing callers: {unknown}. "
            "Add to KNOWN_HEMISPHERE_ROUTING_CALLERS if intentional."
        )

    def test_no_stale_inventory(self):
        """Known callers must actually exist in source."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_hemisphere_routing")
        stale = KNOWN_HEMISPHERE_ROUTING_CALLERS - actual
        assert not stale, (
            f"Stale entries in KNOWN_HEMISPHERE_ROUTING_CALLERS: {stale}. "
            "Remove if callers were deleted."
        )

    def test_caller_count_locked(self):
        """Exactly 1 production caller."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_hemisphere_routing")
        assert len(actual) == 1, (
            f"Expected 1 caller, found {len(actual)}: {actual}"
        )


# ── Engine/hemisphere result shape parity ────────────────────────────────

import re


def _extract_js_set_literal(source: str, var_name: str) -> set[str]:
    """Extract a new Set([...]) constant from JS source."""
    pattern = rf"const\s+{re.escape(var_name)}\s*=\s*new\s+Set\(\[(.*?)\]\)"
    m = re.search(pattern, source, re.DOTALL)
    if not m:
        pytest.fail(f"Could not find {var_name} in eval_step.js")
    block = m.group(1)
    return set(re.findall(r"'([^']+)'", block))


class TestEngineResultShapeParity:
    """Engine terminal keys must match between Python and JS."""

    def test_python_engine_terminal_keys_locked(self):
        """Seed-derived engine terminal keys must have exactly 8 keys."""
        from rcx_pi.selfhost.step_mu import _load_tc_key_sets  # ANTICHEAT_OK: grounding test for engine shape contract
        engine_keys = _load_tc_key_sets()["tc.engine"]
        assert len(engine_keys) == 8, (
            f"Expected 8 engine terminal keys, got {len(engine_keys)}: "
            f"{sorted(engine_keys)}"
        )

    def test_python_engine_terminal_keys_content(self):
        """Seed-derived engine terminal keys must contain the expected keys."""
        from rcx_pi.selfhost.step_mu import _load_tc_key_sets  # ANTICHEAT_OK: grounding test for engine shape contract
        engine_keys = _load_tc_key_sets()["tc.engine"]
        expected = {
            "value", "closure_detected", "tau_step", "exhaustion_detected",
            "operator_frozen", "frozen_set", "action", "stall",
        }
        assert engine_keys == expected, (
            f"Engine terminal keys drift!\n"
            f"  Missing: {expected - engine_keys}\n"
            f"  Extra: {engine_keys - expected}"
        )

    def test_js_engine_terminal_keys_match_python(self):
        """JS ENGINE_TERMINAL_KEYS must match seed-derived Python keys."""
        from rcx_pi.selfhost.step_mu import _load_tc_key_sets  # ANTICHEAT_OK: grounding test for engine shape contract
        engine_keys = _load_tc_key_sets()["tc.engine"]
        js_keys = _extract_js_set_literal(_read_all_js_source(), "ENGINE_TERMINAL_KEYS")
        assert js_keys == engine_keys, (
            f"Engine terminal key drift!\n"
            f"  Python-only: {engine_keys - js_keys}\n"
            f"  JS-only: {js_keys - engine_keys}"
        )


class TestHemisphereKeysParity:
    """Hemisphere keys must match between Python and JS."""

    def test_python_hemisphere_keys_locked(self):
        """Python _HEMISPHERE_KEYS must have exactly 5 keys."""
        from rcx_pi.selfhost.step_mu import _HEMISPHERE_KEYS  # ANTICHEAT_OK: grounding test for hemisphere shape contract
        assert len(_HEMISPHERE_KEYS) == 5, (
            f"Expected 5 hemisphere keys, got {len(_HEMISPHERE_KEYS)}: "
            f"{sorted(_HEMISPHERE_KEYS)}"
        )

    def test_python_hemisphere_keys_content(self):
        """Python _HEMISPHERE_KEYS must contain the expected keys."""
        from rcx_pi.selfhost.step_mu import _HEMISPHERE_KEYS  # ANTICHEAT_OK: grounding test for hemisphere shape contract
        expected = {"r_null", "r_inf", "r_a", "lobes", "sink"}
        assert _HEMISPHERE_KEYS == expected, (
            f"Hemisphere keys drift!\n"
            f"  Missing: {expected - _HEMISPHERE_KEYS}\n"
            f"  Extra: {_HEMISPHERE_KEYS - expected}"
        )

    def test_js_hemisphere_keys_match_python(self):
        """JS HEMISPHERE_KEYS must match Python exactly."""
        from rcx_pi.selfhost.step_mu import _HEMISPHERE_KEYS  # ANTICHEAT_OK: grounding test for hemisphere shape contract
        js_source = _read_all_js_source()
        # HEMISPHERE_KEYS derived from HEMISPHERE_KEY_ORDER array
        pattern = r"const\s+HEMISPHERE_KEY_ORDER\s*=\s*\[(.*?)\]"
        m = re.search(pattern, js_source, re.DOTALL)
        assert m, "Could not find HEMISPHERE_KEY_ORDER in eval_step.js"
        js_keys = set(re.findall(r"'([^']+)'", m.group(1)))
        assert js_keys == _HEMISPHERE_KEYS, (
            f"Hemisphere key drift!\n"
            f"  Python-only: {_HEMISPHERE_KEYS - js_keys}\n"
            f"  JS-only: {js_keys - _HEMISPHERE_KEYS}"
        )


# ── Pipeline parameter signature lock ────────────────────────────────────


class TestPipelineSignatureLock:
    """All run_engine_pipeline parameter defaults must remain stable."""

    def test_max_steps_default(self):
        sig = inspect.signature(run_engine_pipeline)
        assert sig.parameters["max_steps"].default == 100

    def test_max_algorithm_iterations_default(self):
        sig = inspect.signature(run_engine_pipeline)
        assert sig.parameters["max_algorithm_iterations"].default == 50

    def test_max_iterations_default_none(self):
        sig = inspect.signature(run_engine_pipeline)
        assert sig.parameters["max_iterations"].default is None

    def test_use_boot1_recursive_default_true(self):
        sig = inspect.signature(run_engine_pipeline)
        assert sig.parameters["use_boot1_recursive"].default is True

    def test_keyword_only_after_input_value(self):
        """Parameters after input_value must be keyword-only."""
        sig = inspect.signature(run_engine_pipeline)
        params = list(sig.parameters.values())
        # First two (projections, input_value) are positional-or-keyword
        # Rest must be keyword-only
        for param in params[2:]:
            assert param.kind == inspect.Parameter.KEYWORD_ONLY, (
                f"Parameter '{param.name}' should be keyword-only, "
                f"got {param.kind.name}"
            )


# ── Pipeline return shape contract ───────────────────────────────────────


class TestPipelineReturnContract:
    """run_engine_pipeline must return a dict with exactly 8 terminal keys."""

    @pytest.mark.slow
    def test_return_is_dict(self):
        result = run_engine_pipeline(
            projections=[{"id": "t.id", "pattern": {"var": "x"}, "body": {"var": "x"}}],
            input_value=42,
            max_steps=3,
            use_boot1_recursive=False,
        )
        assert isinstance(result, dict), f"Expected dict, got {type(result).__name__}"

    @pytest.mark.slow
    def test_return_has_terminal_keys(self):
        from rcx_pi.selfhost.step_mu import _load_tc_key_sets  # ANTICHEAT_OK: grounding test for return shape
        engine_keys = _load_tc_key_sets()["tc.engine"]
        result = run_engine_pipeline(
            projections=[{"id": "t.id", "pattern": {"var": "x"}, "body": {"var": "x"}}],
            input_value=42,
            max_steps=3,
            use_boot1_recursive=False,
        )
        assert set(result.keys()) == engine_keys, (
            f"Return keys mismatch.\n"
            f"  Missing: {engine_keys - set(result.keys())}\n"
            f"  Extra: {set(result.keys()) - engine_keys}"
        )


# ── Hemisphere routing error paths ───────────────────────────────────────


class TestHemisphereRoutingErrors:
    """run_hemisphere_routing must reject invalid inputs."""

    def test_engine_result_not_dict_raises(self):
        from rcx_pi.selfhost.step_mu import run_hemisphere_routing
        with pytest.raises(ValueError, match="engine_result must be a dict"):
            run_hemisphere_routing("not a dict", {"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None})

    def test_engine_result_list_raises(self):
        from rcx_pi.selfhost.step_mu import run_hemisphere_routing
        with pytest.raises(ValueError, match="engine_result must be a dict"):
            run_hemisphere_routing([1, 2, 3], {"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None})

    def test_engine_result_none_raises(self):
        from rcx_pi.selfhost.step_mu import run_hemisphere_routing
        with pytest.raises(ValueError, match="engine_result must be a dict"):
            run_hemisphere_routing(None, {"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None})


# ── Engine-with-routing validation ───────────────────────────────────────


class TestEngineWithRoutingValidation:
    """run_engine_with_routing must validate hemispheres parameter."""

    def test_hemispheres_not_dict_raises_typeerror(self):
        from rcx_pi.selfhost.step_mu import run_engine_with_routing
        with pytest.raises(TypeError, match="hemispheres must be dict"):
            run_engine_with_routing(
                [{"id": "t.id", "pattern": {"var": "x"}, "body": {"var": "x"}}],
                42,
                hemispheres="not a dict",
            )

    def test_hemispheres_missing_keys_raises_valueerror(self):
        from rcx_pi.selfhost.step_mu import run_engine_with_routing
        with pytest.raises(ValueError, match="hemispheres shape mismatch"):
            run_engine_with_routing(
                [{"id": "t.id", "pattern": {"var": "x"}, "body": {"var": "x"}}],
                42,
                hemispheres={"r_null": None},  # missing 4 keys
            )

    def test_hemispheres_extra_keys_raises_valueerror(self):
        from rcx_pi.selfhost.step_mu import run_engine_with_routing
        with pytest.raises(ValueError, match="hemispheres shape mismatch"):
            run_engine_with_routing(
                [{"id": "t.id", "pattern": {"var": "x"}, "body": {"var": "x"}}],
                42,
                hemispheres={"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None, "extra": None},
            )


# ── Engine-with-routing return shape lock ─────────────────────────────────


class TestEngineWithRoutingReturnShape:
    """run_engine_with_routing must return exactly 2 keys with correct sub-shapes."""

    @pytest.mark.slow
    def test_return_has_exactly_two_keys(self):
        """Return dict must have exactly {engine_result, hemispheres}."""
        from rcx_pi.selfhost.step_mu import run_engine_with_routing
        result = run_engine_with_routing(
            [{"id": "t.id", "pattern": {"var": "x"}, "body": {"var": "x"}}],
            42,
            max_steps=3,
        )
        assert set(result.keys()) == {"engine_result", "hemispheres"}, (
            f"Return shape drift! Keys: {sorted(result.keys())}"
        )

    @pytest.mark.slow
    def test_engine_result_has_terminal_keys(self):
        """engine_result sub-dict must have exactly 8 terminal keys."""
        from rcx_pi.selfhost.step_mu import run_engine_with_routing, _load_tc_key_sets  # ANTICHEAT_OK: grounding test for return shape
        engine_keys = _load_tc_key_sets()["tc.engine"]
        result = run_engine_with_routing(
            [{"id": "t.id", "pattern": {"var": "x"}, "body": {"var": "x"}}],
            42,
            max_steps=3,
        )
        assert set(result["engine_result"].keys()) == engine_keys, (
            f"engine_result sub-shape drift!\n"
            f"  Missing: {engine_keys - set(result['engine_result'].keys())}\n"
            f"  Extra: {set(result['engine_result'].keys()) - engine_keys}"
        )

    @pytest.mark.slow
    def test_hemispheres_has_hemisphere_keys(self):
        """hemispheres sub-dict must have exactly 5 hemisphere keys."""
        from rcx_pi.selfhost.step_mu import run_engine_with_routing, _HEMISPHERE_KEYS  # ANTICHEAT_OK: grounding test for return shape
        result = run_engine_with_routing(
            [{"id": "t.id", "pattern": {"var": "x"}, "body": {"var": "x"}}],
            42,
            max_steps=3,
        )
        assert set(result["hemispheres"].keys()) == _HEMISPHERE_KEYS, (
            f"hemispheres sub-shape drift!\n"
            f"  Missing: {_HEMISPHERE_KEYS - set(result['hemispheres'].keys())}\n"
            f"  Extra: {set(result['hemispheres'].keys()) - _HEMISPHERE_KEYS}"
        )

# ── run_mu callsite inventory ─────────────────────────────────────────────

# All functions that call run_mu() directly in production code.
KNOWN_RUN_MU_CALLERS = {
    "run_hemisphere_routing",  # Only production caller (hemispheres.v1 routing)
}


class TestRunMuCallsiteInventory:
    """run_mu must only be called from known locations."""

    def test_no_unknown_callers(self):
        """Fail-closed: any new caller must be added to KNOWN_RUN_MU_CALLERS."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_mu")
        unknown = actual - KNOWN_RUN_MU_CALLERS
        assert not unknown, (
            f"Unknown run_mu callers: {unknown}. "
            "Add to KNOWN_RUN_MU_CALLERS if intentional."
        )

    def test_no_stale_inventory(self):
        """Known callers must actually exist in source."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_mu")
        stale = KNOWN_RUN_MU_CALLERS - actual
        assert not stale, (
            f"Stale entries in KNOWN_RUN_MU_CALLERS: {stale}. "
            "Remove if callers were deleted."
        )

    def test_caller_count_locked(self):
        """Exactly 1 production caller of run_mu."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_mu")
        assert len(actual) == 1, (
            f"Expected 1 run_mu caller, found {len(actual)}: {actual}"
        )


# ── run_mu_structural callsite inventory ──────────────────────────────────

# All functions that call run_mu_structural() directly.
# _service_boundary_effect: shared boundary effect handler (called by both paths below)
# run_engine_pipeline: main engine loop (trampoline path, delegates boundary to shared helper)
# _run_engine_recursive: Boot1 engine loop (recursive path, delegates boundary to shared helper)
KNOWN_RUN_MU_STRUCTURAL_CALLERS = {
    "_service_boundary_effect",
}


class TestRunMuStructuralCallsiteInventory:
    """run_mu_structural must only be called from known locations."""

    def test_no_unknown_callers(self):
        """Fail-closed: any new caller must be added to KNOWN_RUN_MU_STRUCTURAL_CALLERS."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_mu_structural")
        unknown = actual - KNOWN_RUN_MU_STRUCTURAL_CALLERS
        assert not unknown, (
            f"Unknown run_mu_structural callers: {unknown}. "
            "Add to KNOWN_RUN_MU_STRUCTURAL_CALLERS if intentional."
        )

    def test_no_stale_inventory(self):
        """Known callers must actually exist in source."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_mu_structural")
        stale = KNOWN_RUN_MU_STRUCTURAL_CALLERS - actual
        assert not stale, (
            f"Stale entries in KNOWN_RUN_MU_STRUCTURAL_CALLERS: {stale}. "
            "Remove if callers were deleted."
        )

    def test_caller_count_locked(self):
        """Exactly 1 caller of run_mu_structural (shared boundary handler)."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_callers(source, "run_mu_structural")
        assert len(actual) == 1, (
            f"Expected 1 run_mu_structural caller, found {len(actual)}: {actual}"
        )


# ── JS JSON API action list parity ────────────────────────────────────────

# Expected JS JSON API actions (21 total, extracted from dispatch branches)
EXPECTED_JS_ACTIONS = {
    "run_vector", "run_all_vectors", "run_recurrence", "run_exhaustion",
    "get_constants", "normalize_roundtrip", "validate_mu",
    "run_recurrence_with_bridge", "run_exhaustion_with_bridge",
    "validate_reserved_fields", "validate_algorithm_runtime_fields",
    "run_structural_trace", "run_hemisphere", "run_engine_pipeline",
    "hash_trace", "run_hemisphere_routing", "run_engine_with_routing",
    "step_metabolization", "step_kernel_meta", "run_engine_pipeline_meta",
    "list_actions",
}


def _extract_js_dispatch_actions(source: str) -> set[str]:
    """Extract all action names from request.action === '...' branches."""
    return set(re.findall(r"request\.action\s*===\s*'([^']+)'", source))


def _extract_js_list_actions(source: str) -> set[str]:
    """Extract the actions array from the list_actions response."""
    pattern = r"request\.action\s*===\s*'list_actions'.*?actions:\s*\[(.*?)\]"
    m = re.search(pattern, source, re.DOTALL)
    if not m:
        pytest.fail("Could not find list_actions response in eval_step.js")
    return set(re.findall(r"'([^']+)'", m.group(1)))


class TestJsActionListParity:
    """JS JSON API action dispatch must be self-consistent and locked."""

    def test_action_count_locked(self):
        """JS must have exactly 21 JSON API actions."""
        source = _read_all_js_source()
        actual = _extract_js_dispatch_actions(source)
        assert len(actual) == 21, (
            f"Expected 21 JS actions, found {len(actual)}: {sorted(actual)}"
        )

    def test_dispatch_matches_list_actions(self):
        """Dispatch branches must exactly match list_actions response."""
        source = _read_all_js_source()
        dispatch = _extract_js_dispatch_actions(source)
        listed = _extract_js_list_actions(source)
        dispatch_only = dispatch - listed
        listed_only = listed - dispatch
        assert not dispatch_only and not listed_only, (
            f"JS action list drift!\n"
            f"  In dispatch but not list_actions: {dispatch_only}\n"
            f"  In list_actions but not dispatch: {listed_only}"
        )

    def test_actions_match_expected_set(self):
        """JS actions must match the hardcoded expected set."""
        source = _read_all_js_source()
        actual = _extract_js_dispatch_actions(source)
        missing = EXPECTED_JS_ACTIONS - actual
        extra = actual - EXPECTED_JS_ACTIONS
        assert not missing and not extra, (
            f"JS action set drift!\n"
            f"  Missing: {missing}\n"
            f"  Extra: {extra}"
        )


# ── Boot1 mode routing contract ────────────────────────────────────────


class TestBoot1ModeRoutingContract:
    """Boot1 mode routing must be explicit, observable, and fail-closed.

    Tests that:
    1. Python default is literally False at the AST level (not a variable).
    2. JS boot1LoopMode defaults to false via ?? operator.
    3. Routing is conditional — recursive path gated behind explicit flag.
    4. Observer events differ between paths (observable routing contract).

    These prevent accidental default-flip, unconditional routing bypass,
    and implicit mode changes without observable evidence.
    """

    def test_python_default_is_literal_true_ast(self):
        """Python use_boot1_recursive default must be the literal True at AST level."""
        source = _STEP_MU_PATH.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run_engine_pipeline":
                for arg, default in zip(
                    reversed(node.args.kwonlyargs),
                    reversed(node.args.kw_defaults),
                ):
                    if arg.arg == "use_boot1_recursive":
                        assert isinstance(default, ast.Constant), (
                            f"use_boot1_recursive default must be a literal constant, "
                            f"got {type(default).__name__}"
                        )
                        assert default.value is True, (
                            f"use_boot1_recursive default must be True, "
                            f"got {default.value!r}"
                        )
                        return
                pytest.fail("use_boot1_recursive parameter not found in run_engine_pipeline")
        pytest.fail("run_engine_pipeline function not found in step_mu.py")

    def test_js_boot1_defaults_to_true(self):
        """JS boot1LoopMode must default to true via ?? operator."""
        source = _read_all_js_source()
        assert re.search(r"request\.boot1LoopMode\s*\?\?\s*true", source), (
            "JS must default boot1LoopMode to true via "
            "`request.boot1LoopMode ?? true`"
        )

    def test_python_routing_is_conditional_on_flag(self):
        """_run_engine_recursive call must be inside if use_boot1_recursive branch."""
        source = _STEP_MU_PATH.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run_engine_pipeline":
                for child in ast.walk(node):
                    if isinstance(child, ast.If):
                        if isinstance(child.test, ast.Name) and child.test.id == "use_boot1_recursive":
                            for inner in ast.walk(child):
                                if isinstance(inner, ast.Call):
                                    func = inner.func
                                    if isinstance(func, ast.Name) and func.id == "_run_engine_recursive":
                                        return
                            pytest.fail(
                                "_run_engine_recursive not found inside "
                                "if use_boot1_recursive branch"
                            )
                pytest.fail(
                    "No `if use_boot1_recursive:` branch found in run_engine_pipeline"
                )
        pytest.fail("run_engine_pipeline not found in step_mu.py")

    def test_js_routing_is_conditional_on_boot1mode(self):
        """JS must conditionally route: boot1Mode → recursive vs trampoline."""
        source = _read_all_js_source()
        # Either ternary or if/else is acceptable
        has_ternary = re.search(
            r"boot1Mode\s*\?\s*runEnginePipelineRecursive", source
        )
        has_if_else = re.search(
            r"if\s*\(boot1Mode\)", source
        ) and "runEnginePipelineRecursive" in source and "runEnginePipeline" in source
        assert has_ternary or has_if_else, (
            "JS must route via boot1Mode conditional "
            "(ternary or if/else) to runEnginePipelineRecursive / runEnginePipeline"
        )

    @pytest.mark.slow
    def test_trampoline_observer_has_no_boot1_depth(self):
        """Trampoline path observer events must NOT have boot1_depth field.

        This is the negative half of the observable routing contract:
        if boot1_depth appears on trampoline, routing is not differentiated.
        """
        observer: list = []
        projs = [{"pattern": {"test": {"var": "v"}}, "body": {"var": "v"}}]
        run_engine_pipeline(
            projs, {"test": 42},
            max_steps=5, use_boot1_recursive=False, observer=observer,
        )
        assert len(observer) > 0, "No observer events emitted"
        for i, event in enumerate(observer):
            assert "boot1_depth" not in event, (
                f"Trampoline observer event [{i}] has boot1_depth="
                f"{event['boot1_depth']} — boot1_depth must only appear "
                "on recursive path"
            )

    @pytest.mark.slow
    def test_recursive_observer_has_boot1_depth(self):
        """Recursive path step_boundary events must have boot1_depth field.

        This is the positive half of the observable routing contract:
        boot1_depth proves the recursive path was actually taken.
        """
        from rcx_pi.selfhost.kernel import reset_step_budget
        reset_step_budget()
        observer: list = []
        projs = [{"pattern": {"test": {"var": "v"}}, "body": {"var": "v"}}]
        run_engine_pipeline(
            projs, {"test": 42},
            max_steps=5, use_boot1_recursive=True, observer=observer,
        )
        step_events = [e for e in observer if e["event_name"] == "step_boundary"]
        assert len(step_events) > 0, "No step_boundary events emitted"
        for i, event in enumerate(step_events):
            assert "boot1_depth" in event, (
                f"Recursive step_boundary event [{i}] missing boot1_depth"
            )
            assert isinstance(event["boot1_depth"], int)
            assert event["boot1_depth"] >= 0


# ── Boot1 type hardening ────────────────────────────────────────────────


class TestBoot1TypeHardening:
    """Non-bool use_boot1_recursive must be rejected fail-closed (TypeError).

    Prevents truthy-string routing bugs: "true" (string) is truthy in Python,
    which would silently route to the recursive path without explicit intent.
    """

    def test_pipeline_rejects_string_true(self):
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError, match="use_boot1_recursive must be bool"):
            run_engine_pipeline(projs, {"x": 1}, max_steps=5, use_boot1_recursive="true")

    def test_pipeline_rejects_string_false(self):
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError, match="use_boot1_recursive must be bool"):
            run_engine_pipeline(projs, {"x": 1}, max_steps=5, use_boot1_recursive="false")

    def test_pipeline_rejects_int_one(self):
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError, match="use_boot1_recursive must be bool"):
            run_engine_pipeline(projs, {"x": 1}, max_steps=5, use_boot1_recursive=1)

    def test_pipeline_rejects_int_zero(self):
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError, match="use_boot1_recursive must be bool"):
            run_engine_pipeline(projs, {"x": 1}, max_steps=5, use_boot1_recursive=0)

    def test_pipeline_rejects_none(self):
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError, match="use_boot1_recursive must be bool"):
            run_engine_pipeline(projs, {"x": 1}, max_steps=5, use_boot1_recursive=None)

    def test_routing_rejects_string(self):
        """run_engine_with_routing rejects non-bool use_boot1_recursive."""
        from rcx_pi.selfhost.step_mu import run_engine_with_routing
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError, match="use_boot1_recursive must be bool"):
            run_engine_with_routing(projs, {"x": 1}, use_boot1_recursive="true")

    def test_routing_rejects_int(self):
        from rcx_pi.selfhost.step_mu import run_engine_with_routing
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError, match="use_boot1_recursive must be bool"):
            run_engine_with_routing(projs, {"x": 1}, use_boot1_recursive=1)


# ── I1: Boundary Mu validation ──────────────────────────────────────────


class TestPipelineBoundaryMuValidation:
    """run_engine_pipeline and _run_engine_recursive reject non-Mu inputs at boundary."""

    def test_pipeline_rejects_nan(self):
        """NaN is not valid Mu — pipeline must reject at entry."""
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError):
            run_engine_pipeline(projs, float("nan"), max_steps=5)

    def test_pipeline_rejects_function(self):
        """Functions are not valid Mu — pipeline must reject at entry."""
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError):
            run_engine_pipeline(projs, lambda x: x, max_steps=5)

    def test_pipeline_rejects_inf(self):
        """Infinity is not valid Mu — pipeline must reject at entry."""
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError):
            run_engine_pipeline(projs, float("inf"), max_steps=5)

    def test_recursive_rejects_nan(self):
        """Boot1 recursive path also validates input at boundary."""
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError):
            run_engine_pipeline(projs, float("nan"), max_steps=5, use_boot1_recursive=True)

    def test_recursive_rejects_function(self):
        """Boot1 recursive path also validates input at boundary."""
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        with pytest.raises(TypeError):
            run_engine_pipeline(projs, lambda x: x, max_steps=5, use_boot1_recursive=True)

    def test_pipeline_accepts_valid_mu(self):
        """Valid Mu inputs pass boundary check (regression guard)."""
        from rcx_pi.selfhost.kernel import reset_step_budget
        reset_step_budget()
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"var": "v"}}]
        # These should not raise — they are valid Mu
        run_engine_pipeline(projs, {"x": 1}, max_steps=5)
        run_engine_pipeline(projs, 42, max_steps=5)
        run_engine_pipeline(projs, None, max_steps=5)
        run_engine_pipeline(projs, "hello", max_steps=5)


# ── I1/I2: Source contract locks for JS boundary checks ─────────────────


class TestJsBoundaryContractLock:
    """JS source must contain explicit boundary checks (fail-closed contract)."""

    def test_js_run_engine_pipeline_has_isvalidmu_check(self):
        """runEnginePipeline must call isValidMu on inputValue."""
        source = _read_all_js_source()
        assert "isValidMu(inputValue)" in source, (
            "runEnginePipeline missing isValidMu(inputValue) boundary check"
        )

    def test_js_run_engine_pipeline_recursive_has_isvalidmu_check(self):
        """runEnginePipelineRecursive must call isValidMu on inputValue."""
        source = _read_all_js_source()
        # Both functions should have the check
        import re
        matches = re.findall(r"function\s+runEnginePipeline(?:Recursive)?\b.*?isValidMu\(inputValue\)", source, re.DOTALL)
        assert len(matches) >= 2, (
            f"Expected isValidMu(inputValue) in both pipeline functions, found {len(matches)}"
        )

    def test_js_validate_seed_uses_key_presence(self):
        """validateSeedStructure must use 'key' in obj, not falsy checks."""
        source = _read_all_js_source()
        assert "'id' in proj" in source, "validateSeedStructure must use key-presence for 'id'"
        assert "'pattern' in proj" in source, "validateSeedStructure must use key-presence for 'pattern'"
        assert "'body' in proj" in source, "validateSeedStructure must use key-presence for 'body'"
        assert "'meta' in seed" in source, "validateSeedStructure must use key-presence for 'meta'"

    def test_js_validate_seed_no_falsy_pattern(self):
        """Old falsy patterns must not exist in validateSeedStructure."""
        source = _read_all_js_source()
        # Extract just the validateSeedStructure function body
        import re
        match = re.search(r"function validateSeedStructure\(.*?\{(.*?)\n\}", source, re.DOTALL)
        assert match, "Could not find validateSeedStructure function"
        func_body = match.group(1)
        assert "!proj.id" not in func_body, "validateSeedStructure still uses falsy !proj.id"
        assert "!proj.pattern" not in func_body, "validateSeedStructure still uses falsy !proj.pattern"
        assert "!proj.body" not in func_body, "validateSeedStructure still uses falsy !proj.body"
        assert "!seed.meta" not in func_body, "validateSeedStructure still uses falsy !seed.meta"
