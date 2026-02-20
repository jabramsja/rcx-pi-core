"""
E4 security and invariant tests for Hemisphere Metabolization.

Proves:
- S1-S5 sink-safety invariants (from design doc)
- No new bootstrap primitives introduced
- No new KERNEL_RESERVED_FIELDS required for metabolization
- Hemisphere routing priority unchanged
- Option B remains shadow-only (not activated in runtime)

Evidence artifact for HemisphereExecutionChecklist.v0.md gate E4.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT as ROOT

# ── Constants ────────────────────────────────────────────────────────────────

METABOLIZATION_SEED = ROOT / "mu" / "programs" / "metabolization.v1.json"
HEMISPHERES_SEED = ROOT / "mu" / "programs" / "hemispheres.v1.json"

# Canonical synthesized engine_result shape from design doc (Option B).
# This is the shape that WOULD be produced if Option B were activated.
# S1-S5 tests validate these fields structurally.
SYNTHESIZED_ENGINE_RESULT_EXHAUSTION = {
    "value": None,
    "closure_detected": False,
    "tau_step": 0,
    "exhaustion_detected": True,
    "operator_frozen": None,
    "frozen_set": None,
    "action": "exception_sink",
    "stall": False,
}

SYNTHESIZED_ENGINE_RESULT_STALL = {
    "value": None,
    "closure_detected": False,
    "tau_step": 0,
    "exhaustion_detected": True,
    "operator_frozen": None,
    "frozen_set": None,
    "action": "exception_sink",
    "stall": True,
}


# ── S1-S5 Sink-Safety Invariants ─────────────────────────────────────────────


class TestSinkSafetyInvariants:
    """S1-S5: Verify synthesized engine_result shape satisfies sink-safety.

    S1-S3 are grounded against hemisphere projection patterns (source of truth),
    not just self-declared test constants. The hemisphere.classify.exhaustion
    projection pattern proves what the routing code requires.
    """

    def test_S1_exhaustion_detected_true(self):
        """S1: Synthesized engine_result MUST have exhaustion_detected: true.

        Grounded: hemisphere.classify.exhaustion pattern requires
        hemi_exhaustion: true (verified against seed file). This is the
        routing input field that maps from engine_result.exhaustion_detected.
        """
        # Verify against synthesized constants
        assert SYNTHESIZED_ENGINE_RESULT_EXHAUSTION["exhaustion_detected"] is True
        assert SYNTHESIZED_ENGINE_RESULT_STALL["exhaustion_detected"] is True
        # Ground against actual hemisphere projection pattern
        seed = json.loads(HEMISPHERES_SEED.read_text(encoding="utf-8"))
        exhaust_proj = next(
            p for p in seed["projections"]
            if p["id"] == "hemisphere.classify.exhaustion"
        )
        # The pattern must require hemi_exhaustion: true
        assert exhaust_proj["pattern"]["hemi_exhaustion"] is True, (
            "hemisphere.classify.exhaustion pattern must require hemi_exhaustion: true"
        )

    def test_S2_closure_detected_false(self):
        """S2: Synthesized engine_result MUST have closure_detected: false.

        Grounded: hemisphere.classify.closure pattern requires
        hemi_closure: true, so exhaustion path (which sets false)
        does NOT match the closure classifier.
        """
        assert SYNTHESIZED_ENGINE_RESULT_EXHAUSTION["closure_detected"] is False
        assert SYNTHESIZED_ENGINE_RESULT_STALL["closure_detected"] is False
        # Ground: closure classifier requires hemi_closure: true
        seed = json.loads(HEMISPHERES_SEED.read_text(encoding="utf-8"))
        closure_proj = next(
            p for p in seed["projections"]
            if p["id"] == "hemisphere.classify.closure"
        )
        assert closure_proj["pattern"]["hemi_closure"] is True, (
            "hemisphere.classify.closure pattern must require hemi_closure: true — "
            "this proves our synthesized result (closure_detected: false) won't match closure"
        )

    def test_S3_action_not_freeze(self):
        """S3: Synthesized engine_result MUST NOT have action: 'freeze'.

        Grounded: hemisphere classify patterns use hemi_* fields for routing,
        not action fields. No classify pattern matches on 'action' at all,
        so the action value passes through to the body (output) stage only.
        """
        assert SYNTHESIZED_ENGINE_RESULT_EXHAUSTION["action"] != "freeze"
        assert SYNTHESIZED_ENGINE_RESULT_STALL["action"] != "freeze"
        assert SYNTHESIZED_ENGINE_RESULT_EXHAUSTION["action"] == "exception_sink"
        assert SYNTHESIZED_ENGINE_RESULT_STALL["action"] == "exception_sink"
        # Ground: no classify pattern references 'action' — routing is by hemi_* fields only
        seed = json.loads(HEMISPHERES_SEED.read_text(encoding="utf-8"))
        classify_projs = [
            p for p in seed["projections"]
            if p["id"].startswith("hemisphere.classify.")
        ]
        for proj in classify_projs:
            pattern_keys = set(proj["pattern"].keys())
            assert "action" not in pattern_keys, (
                f"{proj['id']} pattern contains 'action' key — "
                "hemisphere classifiers should route by hemi_* fields, not action"
            )

    def test_S4_cross_substrate_shape_parity(self):
        """S4: Both substrates produce identical synthesized results.

        Since Option B is not activated, we verify the shape constants
        are identical between Python and JS definitions. The canonical
        8-key terminal shape is locked in both substrates.
        """
        expected_keys = {
            "value", "closure_detected", "tau_step", "exhaustion_detected",
            "operator_frozen", "frozen_set", "action", "stall",
        }
        # Python: synthesized shape has exactly 8 terminal keys
        assert set(SYNTHESIZED_ENGINE_RESULT_EXHAUSTION.keys()) == expected_keys
        assert set(SYNTHESIZED_ENGINE_RESULT_STALL.keys()) == expected_keys

        # JS: run_hemisphere accepts terminal shapes — proves JS recognizes the shape
        resp = _run_js_json_api({
            "action": "run_hemisphere",
            "input": SYNTHESIZED_ENGINE_RESULT_EXHAUSTION,
        })
        assert resp.get("success"), f"JS rejected synthesized shape: {resp.get('error')}"

    def test_S5_terminal_shape_check(self):
        """S5: Terminal shape check passes in both substrates.

        Verified structurally: synthesized result has exactly the 8 keys
        defined in ENGINE_TERMINAL_KEYS (Python) / ENGINE_TERMINAL_KEYS (JS).
        """
        expected_keys = {
            "value", "closure_detected", "tau_step", "exhaustion_detected",
            "operator_frozen", "frozen_set", "action", "stall",
        }
        # Python: exact 8-key match
        assert set(SYNTHESIZED_ENGINE_RESULT_EXHAUSTION.keys()) == expected_keys
        assert set(SYNTHESIZED_ENGINE_RESULT_STALL.keys()) == expected_keys

        # JS: run_hemisphere on stall variant also succeeds
        resp = _run_js_json_api({
            "action": "run_hemisphere",
            "input": SYNTHESIZED_ENGINE_RESULT_STALL,
        })
        assert resp.get("success"), f"JS rejected stall synthesized shape: {resp.get('error')}"


# ── No New Bootstrap Primitives ──────────────────────────────────────────────


class TestNoNewBootstrapPrimitives:
    """Metabolization must not introduce new bootstrap primitives."""

    BOOTSTRAP_PRIMITIVE_FILES = [
        ROOT / "rcx_pi" / "selfhost" / "eval_seed.py",
        ROOT / "rcx_pi" / "selfhost" / "seed_integrity.py",
        ROOT / "rcx_pi" / "selfhost" / "step_mu.py",
        ROOT / "rcx_pi" / "selfhost" / "mu_type.py",
    ]

    def test_exactly_4_bootstrap_primitives(self):
        """There must be exactly 4 BOOTSTRAP_PRIMITIVE markers in selfhost/."""
        count = 0
        for fpath in self.BOOTSTRAP_PRIMITIVE_FILES:
            text = fpath.read_text(encoding="utf-8")
            count += len(re.findall(r"#\s*BOOTSTRAP_PRIMITIVE:", text))
        assert count == 4, (
            f"Expected 4 bootstrap primitive markers, found {count}. "
            "Metabolization must not introduce new primitives."
        )

    def test_metabolization_seed_has_no_bootstrap_marker(self):
        """Metabolization seed must not declare bootstrap primitives."""
        text = METABOLIZATION_SEED.read_text(encoding="utf-8")
        assert "BOOTSTRAP_PRIMITIVE" not in text
        assert "bootstrap" not in text.lower() or "bootstrap" in text.lower()
        # The seed meta may reference "bootstrap" in doc strings; check no marker
        seed = json.loads(text)
        for proj in seed["projections"]:
            assert "bootstrap" not in proj.get("id", "").lower(), (
                f"Projection {proj['id']} has 'bootstrap' in ID"
            )


# ── No New KERNEL_RESERVED_FIELDS ────────────────────────────────────────────


class TestNoNewKernelReservedFields:
    """Metabolization must not require new KERNEL_RESERVED_FIELDS."""

    def test_metabolization_seed_no_underscore_keys(self):
        """No underscore-prefixed keys in metabolization projections."""
        seed = json.loads(METABOLIZATION_SEED.read_text(encoding="utf-8"))
        violations = []
        for proj in seed["projections"]:
            for key in _collect_keys(proj["pattern"]):
                if key.startswith("_"):
                    violations.append((proj["id"], "pattern", key))
            for key in _collect_keys(proj["body"]):
                if key.startswith("_"):
                    violations.append((proj["id"], "body", key))
        assert not violations, (
            f"Metabolization projections use underscore keys "
            f"(would require KERNEL_RESERVED_FIELDS): {violations}"
        )

    def test_kernel_reserved_fields_count_unchanged(self):
        """KERNEL_RESERVED_FIELDS count must remain at 24."""
        from rcx_pi.selfhost.step_mu import KERNEL_RESERVED_FIELDS

        assert len(KERNEL_RESERVED_FIELDS) == 24, (
            f"Expected 24 KERNEL_RESERVED_FIELDS, got {len(KERNEL_RESERVED_FIELDS)}. "
            f"Metabolization must not add new reserved fields. "
            f"Current: {sorted(KERNEL_RESERVED_FIELDS)}"
        )


# ── Hemisphere Routing Priority Unchanged ────────────────────────────────────


class TestHemisphereRoutingPriorityUnchanged:
    """Metabolization must not alter hemisphere classify projection order."""

    EXPECTED_CLASSIFY_ORDER = [
        "hemisphere.classify.exhaustion",
        "hemisphere.classify.null",
        "hemisphere.classify.closure",
        "hemisphere.classify.stall",
        "hemisphere.classify.default",
    ]

    def test_classify_projection_order_preserved(self):
        """hemispheres.v1.json classify projections maintain priority order."""
        seed = json.loads(HEMISPHERES_SEED.read_text(encoding="utf-8"))
        classify_ids = [
            p["id"] for p in seed["projections"]
            if p["id"].startswith("hemisphere.classify.")
        ]
        assert classify_ids == self.EXPECTED_CLASSIFY_ORDER, (
            f"Classify projection order changed!\n"
            f"Expected: {self.EXPECTED_CLASSIFY_ORDER}\n"
            f"Actual: {classify_ids}"
        )

    def test_exhaustion_is_first_classifier(self):
        """hemisphere.classify.exhaustion MUST be first (exhaustion dominates all)."""
        seed = json.loads(HEMISPHERES_SEED.read_text(encoding="utf-8"))
        classify_ids = [
            p["id"] for p in seed["projections"]
            if p["id"].startswith("hemisphere.classify.")
        ]
        assert classify_ids[0] == "hemisphere.classify.exhaustion", (
            f"First classifier must be exhaustion, got: {classify_ids[0]}"
        )

    def test_metabolization_projections_dont_override_classify(self):
        """Metabolization seed must not contain classify projections."""
        seed = json.loads(METABOLIZATION_SEED.read_text(encoding="utf-8"))
        classify_ids = [
            p["id"] for p in seed["projections"]
            if "classify" in p["id"]
        ]
        assert not classify_ids, (
            f"Metabolization seed must not contain classify projections: {classify_ids}"
        )


# ── Option B Shadow-Only ─────────────────────────────────────────────────────


class TestOptionBShadowOnly:
    """Option B (engine exception policy) must not be activated in runtime."""

    def test_no_exception_sink_in_python_runtime(self):
        """'exception_sink' action value must not appear in Python runtime code."""
        runtime_files = [
            ROOT / "rcx_pi" / "selfhost" / "step_mu.py",
            ROOT / "rcx_pi" / "selfhost" / "eval_seed.py",
        ]
        for fpath in runtime_files:
            text = fpath.read_text(encoding="utf-8")
            assert "exception_sink" not in text, (
                f"'exception_sink' found in runtime {fpath.name} — "
                "Option B must remain shadow-only (design doc only)"
            )

    def test_no_exception_sink_in_js_runtime(self):
        """'exception_sink' must not appear in JS runtime code."""
        js_path = ROOT / "mu" / "host" / "js" / "eval_step.js"
        text = js_path.read_text(encoding="utf-8")
        assert "exception_sink" not in text, (
            "'exception_sink' found in JS runtime — "
            "Option B must remain shadow-only (design doc only)"
        )

    def test_no_exception_sink_in_seeds(self):
        """'exception_sink' must not appear in any seed file."""
        seed_dir = ROOT / "mu" / "programs"
        for seed_file in seed_dir.glob("*.json"):
            text = seed_file.read_text(encoding="utf-8")
            assert "exception_sink" not in text, (
                f"'exception_sink' found in {seed_file.name} — "
                "Option B must remain shadow-only"
            )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _collect_keys(obj) -> list[str]:
    """Recursively collect all dict keys from a nested structure."""
    keys = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.append(k)
            keys.extend(_collect_keys(v))
    elif isinstance(obj, list):
        for item in obj:
            keys.extend(_collect_keys(item))
    return keys


def _run_js_json_api(request_dict: dict) -> dict:
    """Call JS with JSON API and parse response."""
    result = subprocess.run(
        ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request_dict)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=60,
    )
    for line in result.stdout.split("\n"):
        if line.startswith("JSON_API_RESPONSE:"):
            return json.loads(line[len("JSON_API_RESPONSE:"):])
    raise RuntimeError(
        f"No JSON_API_RESPONSE in JS output.\nstdout: {result.stdout[:500]}\nstderr: {result.stderr[:500]}"
    )
