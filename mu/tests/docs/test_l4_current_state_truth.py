"""
Current-state truth checks for L4 / Stage0 meta-circular docs.

These assertions are intentionally narrow and opinionated:
- full L4 completion remains blocked / long-horizon
- bounded L4 reduction work is active right now
- active L4 doctrine docs must reflect current G8/P7 truth
- Stage0 VM docs must match the live shadow-path wiring
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.repo_root import REPO_ROOT

STATUS_PATH = REPO_ROOT / "STATUS.md"
TASKS_PATH = REPO_ROOT / "TASKS.md"
L4_EXIT_CHECKLIST_PATH = REPO_ROOT / "mu" / "docs" / "core" / "L4ExitChecklist.v0.md"
L4_MICRO_ABI_PATH = REPO_ROOT / "mu" / "docs" / "core" / "L4MicroAbi.v0.md"
G8_FEASIBILITY_PATH = REPO_ROOT / "mu" / "docs" / "core" / "G8CpsFeasibility.v0.md"
PY_STAGE0_VM_PATH = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "stage0_vm.py"
JS_STAGE0_VM_PATH = REPO_ROOT / "mu" / "host" / "js" / "core" / "stage0_vm.js"
PY_STEP_MU_PATH = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
JS_KERNEL_PATH = REPO_ROOT / "mu" / "host" / "js" / "engine" / "kernel.js"

_NEXT_SECTION_RE = re.compile(
    r"## NEXT \(short, bounded follow-ups\)\n(.*?)\n## VECTOR ",
    re.DOTALL,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _header_field(text: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}:\s*(.+)$", text, re.MULTILINE)
    assert match, f"Missing header field {name!r}"
    return match.group(1).strip()


def test_status_distinguishes_full_l4_completion_from_active_reduction() -> None:
    text = _read(STATUS_PATH)

    assert "SINK (full completion research; bounded reduction active)" in text, (
        "STATUS.md L4 row must distinguish full-completion SINK status from "
        "active bounded reduction work."
    )
    assert "full L4 completion remains in SINK, but bounded reduction work is active" in text, (
        "STATUS.md L4 section must explicitly state the current distinction."
    )
    assert "P7 Meta-Circular Reduction Chain" in text, (
        "STATUS.md must keep the active Stage0 reduction chain visible."
    )


def test_tasks_s1_sched_reflects_completed_cutover() -> None:
    """S1-SCHED is COMPLETE — NEXT must reflect that, not claim pending GO."""
    text = _read(TASKS_PATH)
    next_match = _NEXT_SECTION_RE.search(text)
    assert next_match, "Could not isolate TASKS.md NEXT section."
    next_section = next_match.group(1)

    assert "[S1-SCHED]" in next_section, "TASKS.md NEXT must retain the S1-SCHED label."
    # Find S1-SCHED within NEXT and check it's marked COMPLETE
    sched_pos = next_section.find("[S1-SCHED]")
    assert sched_pos >= 0, "[S1-SCHED] not found in NEXT section."
    after_sched = next_section[sched_pos:sched_pos + 200]
    assert "COMPLETE" in after_sched, (
        "[S1-SCHED] in NEXT must be marked COMPLETE (founder GO 2026-03-15, cutover active)."
    )


def test_cutover_active_no_pending_go_in_prose() -> None:
    """If VM cutover is active in code, STATUS.md must not claim it awaits founder GO."""
    py_step = _read(PY_STEP_MU_PATH)
    if "_STAGE0_VM_CUTOVER = True" not in py_step:
        return  # cutover not active, skip

    status = _read(STATUS_PATH)
    # Extract L4 section (from "### L4 Research" to next "### " heading on its own line)
    l4_match = re.search(r"### L4 Research.*?(?=\n### |\n## |\Z)", status, re.DOTALL)
    if not l4_match:
        return
    l4_section = l4_match.group(0)

    assert not re.search(r"requires.*founder GO", l4_section, re.IGNORECASE), (
        "STATUS.md L4 section says 'requires founder GO' but _STAGE0_VM_CUTOVER = True in code. "
        "Cutover already happened."
    )
    assert not re.search(r"awaits.*founder GO", l4_section, re.IGNORECASE), (
        "STATUS.md L4 section says 'awaits founder GO' but _STAGE0_VM_CUTOVER = True in code. "
        "Cutover already happened."
    )


def test_kernel_path_reflects_all_vm_cutover() -> None:
    """If all 33 projections are on VM, STATUS.md must not describe host path as primary kernel path."""
    py_step = _read(PY_STEP_MU_PATH)
    if "_STAGE0_VM_CUTOVER = True" not in py_step:
        return  # cutover not active

    status = _read(STATUS_PATH)
    # After S1-C, the kernel path goes through _step_kernel_with_vm for ALL projections.
    # STATUS.md must not describe _step_trusted as the primary kernel path.
    assert "Kernel path:" not in status or "_step_kernel_with_vm" in status.split("Kernel path:")[1][:200], (
        "STATUS.md describes a kernel path that doesn't include _step_kernel_with_vm, "
        "but _STAGE0_VM_CUTOVER = True and all 33 projections execute via VM."
    )
    # _step_kernel_with_vm must not be described as partial (host for kernel.v1/bridge)
    assert "host for kernel.v1" not in status, (
        "STATUS.md still says _step_kernel_with_vm uses 'host for kernel.v1' "
        "but S1-C moved all 4 seed groups to VM."
    )


def test_js_nonmeta_core_not_described_as_live() -> None:
    """If _stepKernelCoreNonMeta is deleted from JS, STATUS.md must not describe split paths."""
    js_kernel = _read(JS_KERNEL_PATH)
    if re.search(r"function\s+_stepKernelCoreNonMeta", js_kernel):
        return  # function still defined, skip

    status = _read(STATUS_PATH)
    assert "_stepKernelCoreNonMeta" not in status, (
        "STATUS.md references _stepKernelCoreNonMeta but it has been deleted from kernel.js."
    )


def test_active_l4_docs_have_grounding_and_current_classification_truth() -> None:
    exit_text = _read(L4_EXIT_CHECKLIST_PATH)
    abi_text = _read(L4_MICRO_ABI_PATH)
    g8_text = _read(G8_FEASIBILITY_PATH)

    for label, text in (
        ("L4ExitChecklist", exit_text),
        ("L4MicroAbi", abi_text),
        ("G8CpsFeasibility", g8_text),
    ):
        grounding = _header_field(text, "GROUNDING_TESTS")
        assert grounding != "none", (
            f"{label} must declare grounding tests now that it carries live current-state claims."
        )

    assert "BLOCKED — circular dependency" not in exit_text, (
        "L4ExitChecklist still contains the pre-D001/D005 circular-dependency blocker claim."
    )
    assert "production reduction remains gated" in exit_text, (
        "L4ExitChecklist must state that classification success is not production reduction."
    )

    assert "BLOCKED (circular dependency)" not in abi_text, (
        "L4MicroAbi still contains the obsolete pre-G8 eval_step blocker claim."
    )
    assert "REDUCIBLE_WITH staged bootstrap" in abi_text, (
        "L4MicroAbi must reflect current eval_step classification truth."
    )
    assert "PARTIALLY CONFIRMED" in abi_text, (
        "L4MicroAbi must reflect the current fuel-threading status for rcx_run."
    )

    assert "**G8 remains UNPROVEN**" not in g8_text, (
        "G8CpsFeasibility still claims G8 is unproven."
    )
    assert "G8 PASS" in g8_text, (
        "G8CpsFeasibility must acknowledge the current G8 PASS classification state."
    )
    assert "Production reduction remains unproven" in g8_text, (
        "G8CpsFeasibility must preserve the current boundary: classification PASS is not production proof."
    )


def test_stage0_vm_docs_match_shadow_path_wiring_and_l4_boundary() -> None:
    py_vm = _read(PY_STAGE0_VM_PATH)
    js_vm = _read(JS_STAGE0_VM_PATH)
    py_step = _read(PY_STEP_MU_PATH)
    js_kernel = _read(JS_KERNEL_PATH)

    assert "NOT wired into production" not in py_vm, (
        "Python Stage0 VM header still claims it is not wired into production."
    )
    assert "shadow path" in py_vm.lower(), (
        "Python Stage0 VM header must describe the live shadow-path wiring."
    )
    assert "NOT wired into production" not in js_vm, (
        "JS Stage0 VM header still claims it is not wired into production."
    )
    assert "cutover active" in js_vm.lower() or "shadow" in js_vm.lower(), (
        "JS Stage0 VM header must describe the cutover or shadow status."
    )

    assert "_STAGE0_VM_CUTOVER = True" in py_step  # S1-B: cutover active
    assert "_STAGE0_SHADOW_ENABLED = False" in py_step  # S1-B: shadow disabled
    assert "for step_i in range(max_steps)" not in py_step, (
        "Python runtime reintroduced the old max_steps-owned kernel driver loop."
    )
    assert '@host_iteration("Kernel execution loop - residual watchdog; supplied Mu fuel owns progress")' in py_step, (
        "Python runtime must keep the residual no-fuel kernel loop honestly marked."
    )
    assert "while (not caller_supplied_fuel) or (fuel_cursor is not None):" not in py_step, (
        "Python runtime reintroduced the old no-fuel kernel loop instead of continuation packets."
    )
    assert "list_to_linked([None] * (max_steps + 1))" not in py_step, (
        "Python runtime must not construct host-counted no-fuel compatibility fuel."
    )
    assert "if caller_supplied_fuel:" in py_step and 'fuel_cursor = fuel_cursor["tail"]' in py_step, (
        "Python runtime must consume Mu fuel only on the explicit supplied-fuel path."
    )
    assert "if steps_used >= watchdog_cap:" in py_step, (
        "Python runtime must keep max_steps/watchdog_cap as a watchdog boundary."
    )
    assert '"kind": "continuation"' in py_step and '"result": None' in py_step, (
        "Python runtime must expose nonterminal kernel progress as continuation packets."
    )
    assert "BOUNDARY: legacy public no-fuel behavior" in py_step, (
        "Python public no-fuel compatibility must be explicitly classified outside the driver."
    )
    assert 'state = packet["continuation"]' in py_step, (
        "Python compatibility boundary must drive self-returned continuation data."
    )
    assert 'current = state["kernel_state"]' in py_step and 'domain_input = state["domain_input"]' in py_step, (
        "Python compatibility boundary must resume inside the prepared caller context."
    )
    assert 'continuation_state=packet["continuation"]' not in py_step, (
        "Python compatibility boundary must not re-enter public validation with self-returned continuation data."
    )

    assert "const _STAGE0_VM_CUTOVER = true;" in js_kernel  # S1-B: cutover active
    assert "let _STAGE0_SHADOW_ENABLED = false;" in js_kernel  # S1-B: shadow disabled
    js_kernel_core = js_kernel[
        js_kernel.index("function _stepKernelCore("):
        js_kernel.index("// _stepKernelCoreNonMeta DELETED")
    ]
    assert "for (let i = 0; i < maxSteps; i++) {" not in js_kernel_core, (
        "JS runtime reintroduced the old maxSteps-owned kernel driver loop."
    )
    assert "@host_iteration" in js_kernel[:js_kernel.index("function _stepKernelCore(")], (
        "JS runtime must keep the residual no-fuel kernel loop honestly marked."
    )
    assert "while (!callerSuppliedFuel || fuelCursor !== null)" not in js_kernel_core, (
        "JS runtime reintroduced the old no-fuel kernel loop instead of continuation packets."
    )
    assert "compatibilityFuelNode <= maxSteps" not in js_kernel_core, (
        "JS runtime must not construct host-counted no-fuel compatibility fuel."
    )
    assert "if (callerSuppliedFuel)" in js_kernel_core and "fuelCursor = fuelCursor.tail" in js_kernel_core, (
        "JS runtime must consume Mu fuel only on the explicit supplied-fuel path."
    )
    assert "if (stepsUsed >= watchdogCap)" in js_kernel_core, (
        "JS runtime must keep maxSteps/watchdogCap as a watchdog boundary."
    )
    assert "kind: 'continuation'" in js_kernel_core and "result: null" in js_kernel_core, (
        "JS runtime must expose nonterminal kernel progress as continuation packets."
    )
    assert "BOUNDARY: public compatibility driver over explicit Mu continuation data" in js_kernel, (
        "JS public no-fuel compatibility must be explicitly classified outside the driver."
    )
    assert "while (packet.kind === 'continuation')" in js_kernel, (
        "JS compatibility boundary must drive explicit returned continuation packets."
    )
    assert "packet.continuation" in js_kernel, (
        "JS compatibility boundary must resume from Mu continuation data."
    )


L3_ARCH_PATH = REPO_ROOT / "mu" / "docs" / "core" / "L3SubstrateArchitecture.v0.md"


def test_l3_architecture_doc_contains_structural_content() -> None:
    """L3 architecture doc must retain key structural content extracted from STATUS.md.

    STATUS.md was optimized (489->166 lines) and structural details moved to this doc.
    These assertions prevent the extracted content from being lost or deleted.
    """
    assert L3_ARCH_PATH.exists(), (
        "L3SubstrateArchitecture.v0.md must exist — it holds structural content "
        "extracted from STATUS.md."
    )
    text = _read(L3_ARCH_PATH)

    # Core L3 definition
    assert "projections run on minimal, auditable substrate" in text, (
        "L3 architecture doc must define L3 as projections on minimal substrate."
    )

    # Seed categories
    assert "Substrate (Core)" in text, (
        "L3 architecture doc must list seed categories."
    )

    # Bootstrap primitives
    assert "eval_step" in text and "max_steps" in text and "stack_guard" in text, (
        "L3 architecture doc must list all bootstrap primitives."
    )

    # JS contraband patterns
    assert "contraband_js.sh" in text, (
        "L3 architecture doc must reference JS contraband enforcement."
    )

    # L4 research
    assert "Can bootstrap primitives be eliminated" in text, (
        "L3 architecture doc must retain the L4 research question."
    )

    # Cross-substrate testing
    assert "parity_vectors.json" in text, (
        "L3 architecture doc must reference the shared parity test vectors."
    )
