"""L4 gate: kernel-driver watchdog ACCEPTED-IRREDUCIBLE boundary record.

Wave: n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11
Authority: locked decision (B) ACCEPTED-IRREDUCIBLE in the decision packet
reports/control_plane/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11_2026-06-11.md
(budget-source census: 33/33 no-fuel caller rows HOST-COUNT-DETERMINED).

Read-only text-truth gate (core tier; file-content assertions only; no kernel
execution). Three assertion groups:
(a) the marker-truth docs carry the accepted-boundary record citing the wave
    id and the decision packet;
(b) the two residual @host_iteration marker strings exist verbatim in their
    runtime files and remain attached to their kernel drivers, so a future
    silent marker removal/demotion fails this gate;
(c) the host-semantics ratchet baseline still tracks exactly one
    host_iteration marker per substrate, so any future marker movement on
    this frontier fails this gate.

This frontier is CLOSED as an open reduction. Relaxing any assertion below
requires a founder-authorized reversal of the locked decision (B).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

WAVE_ID = "n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11"
DECISION_PACKET = (
    "reports/control_plane/"
    "n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11_2026-06-11.md"
)

L3_ARCH_PATH = REPO_ROOT / "mu" / "docs" / "core" / "L3SubstrateArchitecture.v0.md"
PRIMITIVES_PATH = REPO_ROOT / "mu" / "docs" / "core" / "BootstrapPrimitives.v0.md"
PY_STEP_MU_PATH = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
JS_KERNEL_PATH = REPO_ROOT / "mu" / "host" / "js" / "engine" / "kernel.js"
BASELINE_PATH = REPO_ROOT / "mu" / "tools" / "checks" / "host_semantics_baseline.json"

# Verbatim full-line marker strings (locked decision B; founder reversal
# required before either may be removed, reworded, or demoted).
PY_HOST_ITERATION_MARKER = (
    '@host_iteration("Kernel execution loop - residual watchdog; '
    'supplied Mu fuel owns progress")'
)
JS_HOST_ITERATION_MARKER = (
    " * @host_iteration — single-step host transition marker "
    "retained until ratchet baseline update."
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _next_significant_line(
    lines: list[str], start: int, skip_prefixes: tuple[str, ...]
) -> str:
    """Return the first line at/after ``start`` that is not blank and does not
    begin (stripped) with one of ``skip_prefixes``."""
    for line in lines[start:]:
        stripped = line.strip()
        if not stripped or stripped.startswith(skip_prefixes):
            continue
        return line
    pytest.fail(f"No significant line found after index {start}")


# --- group (a): marker-truth doc records -----------------------------------


def test_l3_architecture_doc_records_accepted_watchdog_boundary() -> None:
    """L3 doc carries the accepted-boundary record adjacent to canonical truth."""
    text = _read(L3_ARCH_PATH)

    assert "Accepted kernel-driver watchdog boundary" in text, (
        "L3SubstrateArchitecture.v0.md lost the accepted kernel-driver "
        "watchdog boundary record (locked decision B)."
    )
    assert WAVE_ID in text, (
        "L3 accepted-boundary record must cite the recording wave id."
    )
    assert DECISION_PACKET in text, (
        "L3 accepted-boundary record must cite the locked decision packet path."
    )
    assert "ACCEPTED-IRREDUCIBLE" in text, (
        "L3 accepted-boundary record must state the ACCEPTED-IRREDUCIBLE status."
    )
    assert "step_kernel_mu" in text and "_stepKernelCore" in text, (
        "L3 accepted-boundary record must name both residual kernel drivers."
    )
    assert "HOST-COUNT-DETERMINED" in text, (
        "L3 accepted-boundary record must state the census result: every "
        "no-fuel caller budget is a host numeric bound by design."
    )
    assert "founder-authorized reversal" in text, (
        "L3 accepted-boundary record must state the frontier is closed absent "
        "a founder-authorized reversal."
    )


def test_bootstrap_primitives_doc_records_accepted_watchdog_boundary() -> None:
    """BootstrapPrimitives max_steps entry carries the locked ACCEPTED status."""
    text = _read(PRIMITIVES_PATH)

    assert "cannot be structural fuel" in text, (
        "BootstrapPrimitives.v0.md lost the max_steps termination-clock row "
        "('cannot be structural fuel')."
    )
    assert "accepted kernel-driver watchdog boundary" in text, (
        "BootstrapPrimitives.v0.md lost the max_steps accepted-boundary note."
    )
    assert WAVE_ID in text, (
        "BootstrapPrimitives accepted-boundary note must cite the recording wave id."
    )
    assert DECISION_PACKET in text, (
        "BootstrapPrimitives accepted-boundary note must cite the locked "
        "decision packet path."
    )
    assert "ACCEPTED-IRREDUCIBLE" in text, (
        "BootstrapPrimitives must state the ACCEPTED-IRREDUCIBLE status for "
        "the max_steps watchdog boundary."
    )
    assert "step_kernel_mu" in text and "_stepKernelCore" in text, (
        "BootstrapPrimitives accepted-boundary note must name both residual "
        "kernel drivers."
    )
    assert "founder-authorized reversal" in text, (
        "BootstrapPrimitives accepted-boundary note must state that "
        "re-attempting the reduction requires a founder-authorized reversal."
    )


# --- group (b): verbatim runtime marker strings (read-only) ----------------


def test_python_residual_watchdog_marker_verbatim_on_driver() -> None:
    """Python step_kernel_mu keeps its @host_iteration marker verbatim."""
    lines = _read(PY_STEP_MU_PATH).splitlines()

    assert PY_HOST_ITERATION_MARKER in lines, (
        "Verbatim Python @host_iteration watchdog marker line is missing from "
        "step_mu.py. Silent marker removal/demotion is locked out by decision "
        f"(B) in {DECISION_PACKET}; a founder-authorized reversal is required."
    )
    marker_index = lines.index(PY_HOST_ITERATION_MARKER)
    following = _next_significant_line(lines, marker_index + 1, ("@", "#"))
    assert following.startswith("def step_kernel_mu("), (
        "Python @host_iteration watchdog marker is no longer attached to "
        f"step_kernel_mu (next significant line: {following!r})."
    )


def test_js_residual_watchdog_marker_verbatim_on_driver() -> None:
    """JS _stepKernelCore keeps its @host_iteration marker verbatim."""
    lines = _read(JS_KERNEL_PATH).splitlines()

    assert JS_HOST_ITERATION_MARKER in lines, (
        "Verbatim JS @host_iteration watchdog marker line is missing from "
        "kernel.js. Silent marker removal/demotion is locked out by decision "
        f"(B) in {DECISION_PACKET}; a founder-authorized reversal is required."
    )
    marker_index = lines.index(JS_HOST_ITERATION_MARKER)
    following = _next_significant_line(lines, marker_index + 1, ("*",))
    assert following.startswith("function _stepKernelCore("), (
        "JS @host_iteration watchdog marker is no longer attached to "
        f"_stepKernelCore (next significant line: {following!r})."
    )


# --- group (c): host-semantics baseline tracks the accepted frontier -------


def test_baseline_tracks_exactly_one_host_iteration_per_substrate() -> None:
    """Baseline keeps exactly one tracked host_iteration marker per substrate."""
    data = json.loads(_read(BASELINE_PATH))
    counts = data["counts"]

    assert counts["python"]["host_iteration"] == 1, (
        "host_semantics_baseline.json no longer tracks exactly one Python "
        "host_iteration marker. Marker movement on the kernel-driver watchdog "
        f"frontier is locked out by decision (B) in {DECISION_PACKET}; a "
        "founder-authorized reversal is required."
    )
    assert counts["javascript"]["host_iteration"] == 1, (
        "host_semantics_baseline.json no longer tracks exactly one JavaScript "
        "host_iteration marker. Marker movement on the kernel-driver watchdog "
        f"frontier is locked out by decision (B) in {DECISION_PACKET}; a "
        "founder-authorized reversal is required."
    )
