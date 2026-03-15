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


def test_tasks_s1_sched_has_concrete_next_item() -> None:
    text = _read(TASKS_PATH)
    next_match = _NEXT_SECTION_RE.search(text)
    assert next_match, "Could not isolate TASKS.md NEXT section."
    next_section = next_match.group(1)

    assert "[S1-SCHED]" in text, "TASKS.md must retain the S1-SCHED label."
    assert "[S1-SCHED]" in next_section, (
        "TASKS.md NEXT must contain a concrete [S1-SCHED] item, not only a SINK reference."
    )
    assert "_STAGE0_VM_CUTOVER" in next_section, (
        "[S1-SCHED] must track the real cutover-follow-through scope."
    )
    assert "founder GO" in next_section or "founder go" in next_section.lower(), (
        "[S1-SCHED] must state the founder GO requirement for cutover."
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
    assert "for step_i in range(max_steps)" in py_step, (
        "Python runtime no longer shows the host loop that keeps L4 incomplete."
    )

    assert "const _STAGE0_VM_CUTOVER = true;" in js_kernel  # S1-B: cutover active
    assert "let _STAGE0_SHADOW_ENABLED = false;" in js_kernel  # S1-B: shadow disabled
    assert "for (let i = 0; i < maxSteps; i++) {" in js_kernel, (
        "JS runtime no longer shows the host loop that keeps L4 incomplete."
    )
