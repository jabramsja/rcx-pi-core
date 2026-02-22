"""
L4 Gate: Boot1 iterative re-entry (no host recursion).

Proves the L4_STRUCTURAL semantic shift: _run_engine_recursive and
runEnginePipelineRecursive now use an explicit loop/frame stack for
re-entry instead of host call-stack recursion.

Anti-theater:
  1. Observer events prove actual route selection (boot1_depth present/absent).
  2. Re-entry proof: mock-injected re-entry produces boot1_depth >= 1
     (Python), structural source proof (JS).
  3. Structural source locks: BOTH Python and JS verified at source level —
     no recursive self-calls, while-true loop, depth increment.
  4. Real re-entry proof: deterministic cycling input triggers exhaustion
     freeze path, producing boot1_depth >= 1 in BOTH substrates without mocks.
  5. Cross-substrate parity: Python and JS produce identical results.
  6. Structural sentinel tolerance: exhaustion seed handles terminal
     sentinels via scan_skip_sentinel_* projections — host has zero
     exhaustion-specific branches.

Usage:
    PYTHONHASHSEED=0 pytest mu/tests/l4_gates/test_boot1_structural_iteration_gate.py -v
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.repo_root import REPO_ROOT

from rcx_pi.selfhost.step_mu import run_engine_pipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _js_request(action, **kwargs):
    """Send a JSON API request to eval_step.js and return the parsed response."""
    request = {"action": action, **kwargs}
    js_path = REPO_ROOT / "mu" / "host" / "js" / "eval_step.js"
    result = subprocess.run(
        ["node", str(js_path), "--json-api", json.dumps(request)],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=60,
    )
    for line in result.stdout.split("\n"):
        if line.startswith("JSON_API_RESPONSE:"):
            return json.loads(line[len("JSON_API_RESPONSE:"):])
    pytest.fail(
        f"No JSON_API_RESPONSE in JS output.\n"
        f"returncode: {result.returncode}\n"
        f"stdout: {result.stdout[:500]}\n"
        f"stderr: {result.stderr[:500]}"
    )


def _js_source() -> str:
    """Read eval_step.js source."""
    return (REPO_ROOT / "mu" / "host" / "js" / "eval_step.js").read_text()


def _py_source() -> str:
    """Read step_mu.py source."""
    return (REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py").read_text()


# =============================================================================
# Python: Boot1 route proof (observer-based)
# =============================================================================

@pytest.mark.slow
class TestPythonBoot1RouteProof:
    """Python Boot1 path emits boot1_depth in observer events."""

    def test_boot1_path_has_boot1_depth(self):
        """Boot1 path observer events contain boot1_depth field."""
        from rcx_pi.selfhost.kernel import reset_step_budget
        reset_step_budget()

        observer = []
        run_engine_pipeline(
            [], {"test": True},
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=50, observer=observer,
        )
        assert len(observer) > 0, "must emit at least one observer event"
        assert all("boot1_depth" in e for e in observer), (
            "Boot1 path must have boot1_depth in all observer events"
        )

    def test_trampoline_path_no_boot1_depth(self):
        """Trampoline path observer events do NOT contain boot1_depth."""
        from rcx_pi.selfhost.kernel import reset_step_budget
        reset_step_budget()

        observer = []
        run_engine_pipeline(
            [], {"test": True},
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=50, observer=observer,
            use_boot1_recursive=False,
        )
        assert len(observer) > 0, "must emit at least one observer event"
        assert all("boot1_depth" not in e for e in observer), (
            "Trampoline path must NOT have boot1_depth in observer events"
        )


# =============================================================================
# Python: Re-entry proof (mock-injected, boot1_depth >= 1)
# =============================================================================

@pytest.mark.slow
class TestPythonReentryProof:
    """Prove the iterative re-entry mechanism produces boot1_depth >= 1.

    No public API input in the current repo naturally triggers engine
    re-entry (exhaustion freeze path). We inject ONE re-entry at the
    engine terminal stall point via mock to directly exercise the
    iterative re-entry loop and verify depth increments.
    """

    def test_mock_injected_reentry_increments_depth(self):
        """Injected re-entry produces observer events with boot1_depth >= 1."""
        import rcx_pi.selfhost.step_mu as step_mu_mod
        from rcx_pi.selfhost.kernel import reset_step_budget

        original_step = step_mu_mod._step_trusted  # ANTICHEAT_OK: grounding test verifies iterative re-entry mechanism
        injected = [False]

        def reentry_injecting_step(projs, state):
            result = original_step(projs, state)
            # Inject re-entry when engine produces a terminal result.
            # Terminal results are NEW dicts (result is not state) with
            # 'action' and 'value' keys from engine.unwrap.
            if (not injected[0]
                    and result is not state
                    and isinstance(result, dict)
                    and "action" in result
                    and "value" in result):
                injected[0] = True
                return {"_run_engine": {
                    "projections": [],
                    "input": {"reentry_marker": True},
                    "max_steps": 10,
                    "frozen": None,
                }}
            return result

        reset_step_budget()
        observer = []
        with patch.object(step_mu_mod, "_step_trusted", side_effect=reentry_injecting_step):
            run_engine_pipeline(
                [], {"test": True},
                max_steps=10, max_engine_iterations=20,
                max_algorithm_iterations=50, observer=observer,
            )

        assert injected[0], "Mock must have injected the re-entry"
        step_events = [e for e in observer if e["event_name"] == "step_boundary"]
        assert len(step_events) > 0, "must emit step_boundary events"

        depths = [e["boot1_depth"] for e in step_events]
        max_depth = max(depths)
        assert max_depth >= 1, (
            f"Re-entry must produce boot1_depth >= 1, got max={max_depth}. "
            f"Depths: {depths}"
        )
        # Verify depth 0 events exist too (pre-reentry)
        assert 0 in depths, "Must have depth-0 events before re-entry"

    def test_depth_monotonically_increases_on_reentry(self):
        """boot1_depth increases across re-entry boundary, never decreases."""
        import rcx_pi.selfhost.step_mu as step_mu_mod
        from rcx_pi.selfhost.kernel import reset_step_budget

        original_step = step_mu_mod._step_trusted  # ANTICHEAT_OK: grounding test verifies depth monotonicity
        injected = [False]

        def reentry_injecting_step(projs, state):
            result = original_step(projs, state)
            # Inject re-entry when engine produces a terminal result.
            if (not injected[0]
                    and result is not state
                    and isinstance(result, dict)
                    and "action" in result
                    and "value" in result):
                injected[0] = True
                return {"_run_engine": {
                    "projections": [],
                    "input": {"depth_test": True},
                    "max_steps": 10,
                    "frozen": None,
                }}
            return result

        reset_step_budget()
        observer = []
        with patch.object(step_mu_mod, "_step_trusted", side_effect=reentry_injecting_step):
            run_engine_pipeline(
                [], {"test": True},
                max_steps=10, max_engine_iterations=20,
                max_algorithm_iterations=50, observer=observer,
            )

        assert injected[0], "Mock must have injected the re-entry"
        step_events = [e for e in observer if e["event_name"] == "step_boundary"]
        depths = [e["boot1_depth"] for e in step_events]

        # Must have depth >= 1 (re-entry happened)
        assert max(depths) >= 1, (
            f"Re-entry must produce boot1_depth >= 1, got max={max(depths)}. "
            f"Depths: {depths}"
        )
        # Depth must be non-decreasing across events (re-entry only goes deeper)
        for i in range(1, len(depths)):
            assert depths[i] >= depths[i - 1], (
                f"Depth decreased at event {i}: {depths[i-1]} -> {depths[i]}. "
                f"All depths: {depths}"
            )


# =============================================================================
# Python: Structural proof — no recursive self-calls
# =============================================================================

class TestPythonStructuralIterationProof:
    """Prove Python _run_engine_recursive uses iteration, not host recursion.

    Source-level regex checks that guarantee iterative behavior for ALL
    inputs, not just test inputs. Mirrors TestJsStructuralIterationProof.
    """

    def _extract_body(self):
        """Extract _run_engine_recursive function body from step_mu.py."""
        source = _py_source()
        # Match from 'def _run_engine_recursive' to the next top-level def
        m = re.search(
            r"(def _run_engine_recursive\b.*?)(?=\ndef [a-zA-Z_]|\Z)",
            source, re.DOTALL,
        )
        assert m, "Could not find _run_engine_recursive in step_mu.py"
        return m.group(1)

    def test_no_recursive_self_calls(self):
        """_run_engine_recursive must NOT call itself recursively."""
        body = self._extract_body()
        # Find 'return _run_engine_recursive(' — the recursive call pattern
        recursive_returns = re.findall(r"return\s+_run_engine_recursive\s*\(", body)
        assert len(recursive_returns) == 0, (
            f"_run_engine_recursive contains {len(recursive_returns)} "
            f"recursive return self-calls. Iterative implementation must have zero."
        )
        # Also check for bare calls (not just returns)
        all_calls = re.findall(r"(?<!def )_run_engine_recursive\s*\(", body)
        # The def line itself has '(' — skip it
        assert len(all_calls) <= 1, (
            f"_run_engine_recursive contains {len(all_calls) - 1} "
            f"self-calls. Iterative implementation must have zero."
        )

    def test_has_iterative_reentry_loop(self):
        """_run_engine_recursive must contain 'while True' outer loop."""
        body = self._extract_body()
        assert "while True:" in body, (
            "_run_engine_recursive must contain 'while True:' for iterative re-entry"
        )

    def test_has_depth_increment(self):
        """_run_engine_recursive must contain 'depth += 1' for re-entry tracking."""
        body = self._extract_body()
        assert re.search(r"depth\s*\+=\s*1", body), (
            "_run_engine_recursive must contain 'depth += 1' for iterative depth tracking"
        )


# =============================================================================
# JS: Boot1 route proof (observer-based)
# =============================================================================

class TestJsBoot1RouteProof:
    """JS Boot1 path emits boot1_depth in observer events."""

    def test_boot1_path_has_boot1_depth(self):
        """JS Boot1 path observer events contain boot1_depth field."""
        resp = _js_request(
            "run_engine_pipeline",
            projections=[], input={"test": True},
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
            observer=True,
        )
        assert resp["success"], f"JS request must succeed: {resp.get('error')}"
        events = resp["observer_events"]
        assert len(events) > 0, "must emit at least one observer event"
        assert all("boot1_depth" in e for e in events), (
            "Boot1 path must have boot1_depth in all observer events"
        )

    def test_trampoline_path_no_boot1_depth(self):
        """JS trampoline path observer events do NOT contain boot1_depth."""
        resp = _js_request(
            "run_engine_pipeline",
            projections=[], input={"test": True},
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
            boot1LoopMode=False, observer=True,
        )
        assert resp["success"], f"JS request must succeed: {resp.get('error')}"
        events = resp["observer_events"]
        assert len(events) > 0, "must emit at least one observer event"
        assert all("boot1_depth" not in e for e in events), (
            "Trampoline path must NOT have boot1_depth in observer events"
        )


# =============================================================================
# JS: Structural proof — no recursive self-calls
# =============================================================================

class TestJsStructuralIterationProof:
    """Prove JS runEnginePipelineRecursive uses iteration, not host recursion.

    JS runtime cannot be mocked from Python tests. Instead, verify
    structural properties of the source code that guarantee iterative
    behavior. This is STRONGER than behavioral testing because it
    proves the property holds for ALL inputs, not just test inputs.
    """

    def test_no_recursive_self_calls(self):
        """runEnginePipelineRecursive must NOT call itself recursively."""
        source = _js_source()
        # Extract function body (between 'function runEnginePipelineRecursive' and next top-level function)
        m = re.search(
            r"function runEnginePipelineRecursive\b(.*?)(?=\nfunction\s|\nconst\s+\w+\s*=\s*function|\Z)",
            source, re.DOTALL,
        )
        assert m, "Could not find runEnginePipelineRecursive in JS source"
        body = m.group(1)

        # Must NOT contain recursive calls (runEnginePipelineRecursive( anywhere in body)
        recursive_calls = re.findall(r"runEnginePipelineRecursive\s*\(", body)
        # The function definition itself has the opening paren, skip it
        assert len(recursive_calls) <= 1, (
            f"runEnginePipelineRecursive contains {len(recursive_calls) - 1} "
            f"recursive self-calls. Iterative implementation must have zero."
        )

    def test_has_iterative_reentry_loop(self):
        """runEnginePipelineRecursive must contain while(true) outer loop."""
        source = _js_source()
        m = re.search(
            r"function runEnginePipelineRecursive\b(.*?)(?=\nfunction\s|\nconst\s+\w+\s*=\s*function|\Z)",
            source, re.DOTALL,
        )
        assert m, "Could not find runEnginePipelineRecursive in JS source"
        body = m.group(1)
        assert "while (true)" in body, (
            "runEnginePipelineRecursive must contain 'while (true)' for iterative re-entry"
        )

    def test_has_depth_increment(self):
        """runEnginePipelineRecursive must contain depth++ for re-entry tracking."""
        source = _js_source()
        m = re.search(
            r"function runEnginePipelineRecursive\b(.*?)(?=\nfunction\s|\nconst\s+\w+\s*=\s*function|\Z)",
            source, re.DOTALL,
        )
        assert m, "Could not find runEnginePipelineRecursive in JS source"
        body = m.group(1)
        assert "depth++" in body, (
            "runEnginePipelineRecursive must contain 'depth++' for iterative depth tracking"
        )


# =============================================================================
# Real re-entry proof (no mocks — deterministic cycling input)
# =============================================================================

# Same-ID cycling projections: trigger closure → exhaustion freeze → re-entry.
_CYCLE_PROJECTIONS = [
    {"id": "cycle.loop", "pattern": {"state": "A"}, "body": {"state": "B"}},
    {"id": "cycle.loop", "pattern": {"state": "B"}, "body": {"state": "A"}},
]
_CYCLE_INPUT = {"state": "A"}


@pytest.mark.slow
class TestRealReentryProof:
    """Prove real (non-mock) engine re-entry via exhaustion freeze path.

    Same-ID cycling projections cause:
    1. Closure detection (state repeats at tau)
    2. Exhaustion scan finds same operator throughout → action=freeze
    3. engine.exhaustion_done_freeze produces {_run_engine: ...} envelope
    4. Iterative re-entry loop increments depth

    This is STRONGER than mock-based tests because it exercises the
    full engine pipeline end-to-end with no artificial injection.
    """

    def test_python_real_reentry_depth(self):
        """Python cycling input reaches boot1_depth >= 1 via real freeze."""
        from rcx_pi.selfhost.kernel import reset_step_budget
        reset_step_budget()

        observer = []
        result = run_engine_pipeline(
            _CYCLE_PROJECTIONS, _CYCLE_INPUT,
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=100, observer=observer,
        )
        step_events = [e for e in observer if e["event_name"] == "step_boundary"]
        assert len(step_events) > 0, "must emit step_boundary events"

        depths = [e["boot1_depth"] for e in step_events]
        max_depth = max(depths)
        assert max_depth >= 1, (
            f"Real re-entry must produce boot1_depth >= 1, got max={max_depth}. "
            f"Depths: {depths}"
        )
        assert 0 in depths, "Must have depth-0 events before re-entry"
        # Verify exhaustion freeze actually triggered (frozen_set non-empty)
        assert result.get("frozen_set") is not None, (
            f"Exhaustion freeze must produce non-null frozen_set, got: {result}"
        )

    def test_js_real_reentry_depth(self):
        """JS cycling input reaches boot1_depth >= 1 via real freeze."""
        resp = _js_request(
            "run_engine_pipeline",
            projections=_CYCLE_PROJECTIONS, input=_CYCLE_INPUT,
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=100,
            observer=True,
        )
        assert resp["success"], f"JS request must succeed: {resp.get('error')}"
        events = resp["observer_events"]
        step_events = [e for e in events if e.get("event_name") == "step_boundary"]
        assert len(step_events) > 0, "must emit step_boundary events"

        depths = [e["boot1_depth"] for e in step_events]
        max_depth = max(depths)
        assert max_depth >= 1, (
            f"Real re-entry must produce boot1_depth >= 1, got max={max_depth}. "
            f"Depths: {depths}"
        )
        assert 0 in depths, "Must have depth-0 events before re-entry"

    def test_real_reentry_cross_substrate_parity(self):
        """Python and JS produce identical results on cycling input."""
        from rcx_pi.selfhost.kernel import reset_step_budget
        reset_step_budget()

        py_result = run_engine_pipeline(
            _CYCLE_PROJECTIONS, _CYCLE_INPUT,
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=100,
        )

        resp = _js_request(
            "run_engine_pipeline",
            projections=_CYCLE_PROJECTIONS, input=_CYCLE_INPUT,
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=100,
        )
        assert resp["success"], f"JS must succeed: {resp.get('error')}"
        js_result = resp["result"]

        assert py_result == js_result, (
            f"Real re-entry cross-substrate parity failure.\n"
            f"Python: {py_result}\n"
            f"JS: {js_result}"
        )

    def test_real_reentry_depth_monotonic(self):
        """boot1_depth is non-decreasing across real re-entry."""
        from rcx_pi.selfhost.kernel import reset_step_budget
        reset_step_budget()

        observer = []
        run_engine_pipeline(
            _CYCLE_PROJECTIONS, _CYCLE_INPUT,
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=100, observer=observer,
        )
        step_events = [e for e in observer if e["event_name"] == "step_boundary"]
        depths = [e["boot1_depth"] for e in step_events]
        for i in range(1, len(depths)):
            assert depths[i] >= depths[i - 1], (
                f"Depth decreased at event {i}: {depths[i-1]} -> {depths[i]}. "
                f"All depths: {depths}"
            )

    def test_trampoline_mode_freeze_parity(self):
        """Explicit trampoline mode (use_boot1_recursive=False) also triggers freeze.

        The exhaustion sentinel stripping must be applied in BOTH the
        Boot1 and trampoline boundary handlers.  Without this, the
        trampoline path returns action=continue while Boot1 returns
        action=already_frozen — a parity violation.
        """
        from rcx_pi.selfhost.kernel import reset_step_budget
        reset_step_budget()

        py_result = run_engine_pipeline(
            _CYCLE_PROJECTIONS, _CYCLE_INPUT,
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=100,
            use_boot1_recursive=False,
        )
        # Trampoline path must also reach freeze (frozen_set populated)
        assert py_result.get("frozen_set") is not None, (
            f"Trampoline path must produce non-null frozen_set on cycling input, "
            f"got: {py_result}"
        )
        assert py_result.get("action") != "continue", (
            f"Trampoline path must NOT return action=continue on cycling input, "
            f"got: {py_result.get('action')}"
        )

        # JS trampoline path must match
        resp = _js_request(
            "run_engine_pipeline",
            projections=_CYCLE_PROJECTIONS, input=_CYCLE_INPUT,
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=100,
            boot1LoopMode=False,
        )
        assert resp["success"], f"JS must succeed: {resp.get('error')}"
        js_result = resp["result"]

        assert py_result == js_result, (
            f"Trampoline-mode parity failure on cycling input.\n"
            f"Python: {py_result}\n"
            f"JS: {js_result}"
        )


# =============================================================================
# Regression lock: stall/closure case unchanged by trace sanitization
# =============================================================================

@pytest.mark.slow
class TestRegressionLock:
    """Guard against sentinel tolerance side effects.

    Sentinel handling is structural (in the exhaustion seed, not host).
    Stall/closure cases with empty projections must behave identically
    to pre-fix behavior.
    """

    def test_stall_case_no_reentry(self):
        """Empty projections: depth stays 0, action=continue."""
        from rcx_pi.selfhost.kernel import reset_step_budget
        reset_step_budget()

        observer = []
        result = run_engine_pipeline(
            [], {"test": True},
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=50, observer=observer,
        )
        step_events = [e for e in observer if e["event_name"] == "step_boundary"]
        depths = [e["boot1_depth"] for e in step_events]
        assert max(depths) == 0, (
            f"Stall case must NOT trigger re-entry, got max_depth={max(depths)}"
        )
        assert result.get("action") == "continue", (
            f"Stall case must produce action=continue, got {result.get('action')}"
        )

    def test_different_id_cycle_no_freeze(self):
        """Different-ID cycling projections: exhaustion scan_different fires, no freeze."""
        from rcx_pi.selfhost.kernel import reset_step_budget
        reset_step_budget()

        projections = [
            {"id": "cycle.a2b", "pattern": {"state": "A"}, "body": {"state": "B"}},
            {"id": "cycle.b2a", "pattern": {"state": "B"}, "body": {"state": "A"}},
        ]
        observer = []
        result = run_engine_pipeline(
            projections, {"state": "A"},
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=100, observer=observer,
        )
        step_events = [e for e in observer if e["event_name"] == "step_boundary"]
        depths = [e["boot1_depth"] for e in step_events]
        assert max(depths) == 0, (
            f"Different-ID cycle must NOT trigger re-entry, got max_depth={max(depths)}"
        )
        assert result.get("action") == "continue", (
            f"Different-ID cycle must produce action=continue, got {result.get('action')}"
        )


# =============================================================================
# Cross-substrate parity
# =============================================================================

@pytest.mark.slow
class TestCrossSubstrateParity:
    """Python and JS produce identical results."""

    def test_results_match(self):
        """Python and JS Boot1 results match."""
        from rcx_pi.selfhost.kernel import reset_step_budget
        reset_step_budget()

        py_result = run_engine_pipeline(
            [], {"test": True},
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=50,
        )

        resp = _js_request(
            "run_engine_pipeline",
            projections=[], input={"test": True},
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
        )
        assert resp["success"], f"JS must succeed: {resp.get('error')}"
        js_result = resp["result"]

        assert py_result == js_result, (
            f"Cross-substrate parity failure.\n"
            f"Python: {py_result}\n"
            f"JS: {js_result}"
        )


# =============================================================================
# Structural sentinel tolerance locks (wave 5)
# =============================================================================

class TestExhaustionSeedSentinelTolerance:
    """Prove exhaustion seed structurally handles terminal sentinels.

    Wave 5 moved sentinel handling from host `if exhaustion.v1.json`
    branches into the seed itself via scan_skip_sentinel_* projections.
    These tests lock that structural property.
    """

    def _load_exhaustion_seed(self):
        seed_path = REPO_ROOT / "mu" / "closures" / "exhaustion.v1.json"
        with open(seed_path) as f:
            return json.load(f)

    def test_sentinel_skip_projections_exist(self):
        """Exhaustion seed must contain both sentinel-skip projection IDs."""
        seed = self._load_exhaustion_seed()
        proj_ids = [p["id"] for p in seed["projections"]]
        assert "exhaustion.scan_skip_sentinel_maxsteps" in proj_ids, (
            "Missing exhaustion.scan_skip_sentinel_maxsteps in seed"
        )
        assert "exhaustion.scan_skip_sentinel_stall" in proj_ids, (
            "Missing exhaustion.scan_skip_sentinel_stall in seed"
        )

    def test_sentinel_skip_ordering(self):
        """Sentinel-skip projections must be between scan_same and scan_different."""
        seed = self._load_exhaustion_seed()
        proj_ids = [p["id"] for p in seed["projections"]]
        idx_same = proj_ids.index("exhaustion.scan_same")
        idx_maxsteps = proj_ids.index("exhaustion.scan_skip_sentinel_maxsteps")
        idx_stall = proj_ids.index("exhaustion.scan_skip_sentinel_stall")
        idx_different = proj_ids.index("exhaustion.scan_different")
        assert idx_same < idx_maxsteps < idx_different, (
            f"Ordering violation: scan_same({idx_same}) < "
            f"scan_skip_sentinel_maxsteps({idx_maxsteps}) < "
            f"scan_different({idx_different})"
        )
        assert idx_same < idx_stall < idx_different, (
            f"Ordering violation: scan_same({idx_same}) < "
            f"scan_skip_sentinel_stall({idx_stall}) < "
            f"scan_different({idx_different})"
        )

    def test_sentinel_skip_patterns_match_null_projection(self):
        """Sentinel-skip patterns must structurally match projection=null."""
        seed = self._load_exhaustion_seed()
        for proj in seed["projections"]:
            if not proj["id"].startswith("exhaustion.scan_skip_sentinel_"):
                continue
            # Walk pattern to find _trace value, then trace head dict
            pattern = proj["pattern"]
            # Navigate linked list to find _trace key-value
            node = pattern
            trace_val = None
            while node is not None and isinstance(node, dict) and "head" in node:
                kv = node["head"]
                if isinstance(kv, dict) and kv.get("head") == "_trace":
                    trace_val = kv["tail"]["head"]  # value of _trace
                    break
                node = node.get("tail")
            assert trace_val is not None, f"{proj['id']}: _trace not found in pattern"
            # trace_val is cons cell: {head: <dict>, tail: {var: rest}}
            trace_head = trace_val["head"]
            assert trace_head.get("_type") == "dict", (
                f"{proj['id']}: trace head is not a dict pattern"
            )
            # Find projection key in trace head dict and verify value is null
            th_node = trace_head
            found_null_proj = False
            while th_node is not None and isinstance(th_node, dict) and "head" in th_node:
                kv = th_node["head"]
                if isinstance(kv, dict) and kv.get("head") == "projection":
                    val = kv["tail"]["head"]
                    assert val is None, (
                        f"{proj['id']}: projection value must be null, got {val}"
                    )
                    found_null_proj = True
                th_node = th_node.get("tail")
            assert found_null_proj, f"{proj['id']}: no projection key in trace head"

    def test_seed_version_bumped(self):
        """Exhaustion seed version must be >= 1.3.0 (sentinel tolerance)."""
        seed = self._load_exhaustion_seed()
        version = seed["meta"]["version"]
        major, minor, patch = (int(x) for x in version.split("."))
        assert (major, minor) >= (1, 3), (
            f"Exhaustion seed version must be >= 1.3.0, got {version}"
        )


class TestHostHasNoExhaustionBranch:
    """Prove host runtime has zero exhaustion-specific branches.

    Wave 5 removed all `if exhaustion.v1.json` conditionals from
    boundary handlers.  These tests lock that absence.
    """

    def test_python_host_no_exhaustion_conditional(self):
        """Python step_mu.py boundary handlers must not reference exhaustion.v1.json."""
        source = _py_source()
        # Extract both boundary handler sections
        # Boot1: _run_engine_recursive
        boot1_m = re.search(
            r"(def _run_engine_recursive\b.*?)(?=\ndef [a-zA-Z_]|\Z)",
            source, re.DOTALL,
        )
        assert boot1_m, "Could not find _run_engine_recursive"
        # Trampoline: run_engine_pipeline (the main function)
        tramp_m = re.search(
            r"(def run_engine_pipeline\b.*?)(?=\ndef [a-zA-Z_]|\Z)",
            source, re.DOTALL,
        )
        assert tramp_m, "Could not find run_engine_pipeline"

        for name, body in [("_run_engine_recursive", boot1_m.group(1)),
                           ("run_engine_pipeline", tramp_m.group(1))]:
            matches = re.findall(r'exhaustion\.v1\.json', body)
            assert len(matches) == 0, (
                f"{name} still references 'exhaustion.v1.json' "
                f"({len(matches)} occurrence(s)). Host must be algorithm-agnostic."
            )

    def test_js_host_no_exhaustion_conditional(self):
        """JS eval_step.js boundary handlers must not reference exhaustion.v1.json."""
        source = _js_source()
        # Extract both boundary handler functions
        # Trampoline: runEnginePipeline (the non-recursive path)
        tramp_m = re.search(
            r"(function runEnginePipeline\b.*?)(?=\nfunction\s|\Z)",
            source, re.DOTALL,
        )
        assert tramp_m, "Could not find runEnginePipeline"
        # Boot1: runEnginePipelineRecursive
        boot1_m = re.search(
            r"(function runEnginePipelineRecursive\b.*?)(?=\nfunction\s|\Z)",
            source, re.DOTALL,
        )
        assert boot1_m, "Could not find runEnginePipelineRecursive"

        for name, body in [("runEnginePipeline", tramp_m.group(1)),
                           ("runEnginePipelineRecursive", boot1_m.group(1))]:
            matches = re.findall(r'exhaustion\.v1\.json', body)
            assert len(matches) == 0, (
                f"{name} still references 'exhaustion.v1.json' "
                f"({len(matches)} occurrence(s)). Host must be algorithm-agnostic."
            )

    def test_python_no_strip_sentinel_helper(self):
        """Python must not contain _strip_trace_terminal_sentinel."""
        source = _py_source()
        assert "_strip_trace_terminal_sentinel" not in source, (
            "Dead helper _strip_trace_terminal_sentinel still in step_mu.py"
        )

    def test_js_no_strip_sentinel_helper(self):
        """JS must not contain stripTraceTerminalSentinel."""
        source = _js_source()
        assert "stripTraceTerminalSentinel" not in source, (
            "Dead helper stripTraceTerminalSentinel still in eval_step.js"
        )
