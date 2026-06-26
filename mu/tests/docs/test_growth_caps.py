"""Growth cap enforcement — tracks test/tool/doc counts against baselines.

Fails if counts exceed baseline + per-wave cap without documented consolidation.
See mu/docs/core/DocGovernance.v0.md § "Growth Caps" for policy.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

# Baseline snapshot (2026-02-28, Phase 8c, dev HEAD 965c64d)
# Update these when phase boundary is crossed (founder approval required).
BASELINE_TEST_FILES = 190
BASELINE_TOOL_SCRIPTS = 68  # .py + .sh in mu/tools/ (67 + sync_native_agents.sh, 2026-03-11)
BASELINE_CORE_DOCS = 48  # .md in mu/docs/ (all subdirs) — bumped for P6 TypedNumericEnvelopes.v0.md

# Per-wave caps from DocGovernance.v0.md
CAP_TEST_FILES = 154  # +1 for test_stage0_content_addressed_collapse_gate.py (stage0-content-addressed-symmetric-fence-2026-06-21c wave, FOUNDER_OVERRIDE:stage0-content-addressed-symmetric-fence-2026-06-21c); +1 for test_bridge_config_model_sync.py (bridge-config model/effort/display sync wave, FOUNDER_OVERRIDE:bridge-config-model-sync-2026-06-02); +1 for test_executor_config_alignment.py; +1 for test_codex_startup_state.py (startup hardening, founder sign-off 2026-04-15); +1 for test_pipeline_agent_pager.py (pager wave, founder sign-off 2026-04-17); +1 for test_commit_executor_post_merge_cleanup.py (post-merge-cleanup wave, founder sign-off 2026-04-17); +1 for test_check_private_attr_access.py (AST-anti-cheat wave, standing pipeline-bug-fix authorization 2026-04-20); +1 for test_commit_executor_step14_conflict_precheck.py (Step 14 conflict fast-fail wave, standing pipeline-bug-fix authorization 2026-04-20); +1 for test_commit_executor_step14_autoresolve.py (Step 14 auto-resolve wave, standing pipeline-bug-fix authorization 2026-04-20); +1 for test_wave_id_derivation.py (restart-branch pre-push derivation wave, founder sign-off 2026-04-21); +1 for test_codex_autoping_watch.py (post-reentry reroute pager/autoping wave, founder sign-off 2026-04-25); +1 for test_phase_a_executor.py (pager lifecycle event coverage wave, founder sign-off 2026-04-26); +1 for test_agent_bus_namespacing.py (parallel pipeline bus namespacing wave, founder sign-off 2026-04-30); +1 for test_pane_prci_observability.py (deferred consolidation E5/E6 wave, FOUNDER_OVERRIDE:deferred-consolidation-e5-e6-2026-04-02); +3 for post-redteam engine-state/scheduler structural tests (post-redteam-engine-state-scheduler-reduction-2026-04-30); +1 for test_commit_outcome_pager_lifetime.py (commit-outcome pager worktree-lifetime regression wave, FOUNDER_OVERRIDE:commit-outcome-pager-fix-2026-05-29); +1 for test_set_roles.py (role-agent single-switch wave, FOUNDER_OVERRIDE:role-agent-single-switch-2026-05-30); +1 for test_dialectic_executor.py (dialectic-reviewer-from-config wave, FOUNDER_OVERRIDE:dialectic-reviewer-from-config-2026-05-30); +1 for test_check_control_packet_line_refs.py (control-packet line-ref lint wave, FOUNDER_OVERRIDE:control-packet-line-ref-lint-2026-06-01); +1 for test_claude_autoping_watch.py (claude-monitor autoping route=both wave, FOUNDER_OVERRIDE:claude-monitor-autoping-route-both-2026-06-04b); +1 for test_tracker_marker_codespan_extraction.py (evidence_command fail-closed unbacktick wave, FOUNDER_OVERRIDE:evidence-command-failclosed-unbacktick-2026-06-08); +1 for test_docs_registry_agent_memory_exempt.py (docs-sync agent-memory exempt wave, FOUNDER_OVERRIDE:docs-sync-exempt-agent-memory-2026-06-09); +1 for test_pipeline_monitor_autofollow.py (default-monitor lane autofollow wave, FOUNDER_OVERRIDE:monitor-default-autofollow-bus-resolver-narrow-2026-06-10); +1 for test_kernel_driver_watchdog_accepted_boundary_gate.py (kernel-driver watchdog accepted-boundary marker-truth wave, FOUNDER_OVERRIDE:n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11); +1 for test_structural_numbers_foundation.py (structural-numbers-foundation-gate-2026-06-17 wave, FOUNDER_OVERRIDE:structural-numbers-foundation-gate-2026-06-17); +1 for test_structural_numbers_add.py (structural-numbers-arith-add-2026-06-17c wave, FOUNDER_OVERRIDE:structural-numbers-arith-add-2026-06-17c); +1 for test_structural_numbers_compare.py (structural-numbers-arith-compare-2026-06-18 wave, FOUNDER_OVERRIDE:structural-numbers-arith-compare-2026-06-18); +1 for test_structural_numbers_codec.py (structural-numbers-codec-2026-06-18 wave, FOUNDER_OVERRIDE:structural-numbers-codec-2026-06-18); +1 for test_structural_numbers_add_js_parity.py (structural-numbers-add-js-parity-2026-06-18 wave, FOUNDER_OVERRIDE:structural-numbers-add-js-parity-2026-06-18); +1 for test_structural_numbers_compare_js_parity.py (structural-numbers-compare-js-parity-2026-06-18 wave, FOUNDER_OVERRIDE:structural-numbers-compare-js-parity-2026-06-18); +1 for test_structural_numbers_codec_js_parity.py (structural-numbers-codec-js-parity-2026-06-18 wave, FOUNDER_OVERRIDE:structural-numbers-codec-js-parity-2026-06-18); +1 for test_structural_numbers_multiply.py (structural-numbers-arith-multiply-2026-06-18 wave, FOUNDER_OVERRIDE:structural-numbers-arith-multiply-2026-06-18); +1 for test_structural_numbers_multiply_js_parity.py (structural-numbers-multiply-js-parity-2026-06-18 wave, FOUNDER_OVERRIDE:structural-numbers-multiply-js-parity-2026-06-18); +1 for test_structural_numbers_subtract.py (structural-numbers-arith-subtract-2026-06-18 wave, FOUNDER_OVERRIDE:structural-numbers-arith-subtract-2026-06-18); +1 for test_structural_numbers_subtract_js_parity.py (structural-numbers-subtract-js-parity-2026-06-18 wave, FOUNDER_OVERRIDE:structural-numbers-subtract-js-parity-2026-06-18); +1 for test_launch_wave.py (pipeline-wave-launcher-builder-2026-06-18 wave, FOUNDER_OVERRIDE:pipeline-wave-launcher-builder-2026-06-18); +1 for test_land_stranded_pr.py (FOUNDER_OVERRIDE:stranded-pr-landing-op-2026-06-19); +1 for test_claude_pager_receiver.py (pager-quickack-receiver-2026-06-17 wave, FOUNDER_OVERRIDE:pager-quickack-receiver-2026-06-17); +1 for test_orchestrator_mode_switch.py (codex-mode-switch-2026-06-19 wave, FOUNDER_OVERRIDE:codex-mode-switch-2026-06-19); +1 for test_structural_numbers_gcd.py (structural-numbers-gcd-2026-06-19 wave, FOUNDER_OVERRIDE:structural-numbers-gcd-2026-06-19); +1 for test_structural_numbers_gcd_js_parity.py (structural-numbers-gcd-js-parity-2026-06-19 wave, FOUNDER_OVERRIDE:structural-numbers-gcd-js-parity-2026-06-19); +1 for test_structural_numbers_rationals.py (structural-numbers-rationals-2026-06-19 wave, FOUNDER_OVERRIDE:structural-numbers-rationals-2026-06-19); +1 for test_structural_numbers_rationals_js_parity.py (structural-numbers-rationals-js-parity-2026-06-21b wave, FOUNDER_OVERRIDE:structural-numbers-rationals-js-parity-2026-06-21b); +2 for SurrealNumbers foundation L4 gate plus docs wrapper (surreals-as-structure-2026-06-26 wave, FOUNDER_OVERRIDE:surreals-as-structure-2026-06-26)
CAP_TOOL_SCRIPTS = 56  # +1 for _resolve_live_root.sh; +2 for startup-hardening session tools (founder_learning_snapshot.py, check_codex_startup_state.py; founder sign-off 2026-04-15); +1 for pipeline_agent_pager.py (pager wave, founder sign-off 2026-04-17); +1 for check_private_attr_access.py (AST-anti-cheat wave, standing pipeline-bug-fix authorization 2026-04-20); +4 for Codex autoping session watcher scripts (codex_autoping_watch.py, codex_autoping_window.sh, ensure_codex_autoping.sh, render_codex_autoping_status.py; founder sign-off 2026-04-25); +1 for pipeline_monitor_identity.py (parallel pipeline monitor identity wave, founder sign-off 2026-04-30); +1 for seed_binary_migration.py (FOUNDER_OVERRIDE:n3-projection-loader-seed-migration-integrity-chain-2026-05-14); +1 for set_roles.py (role-agent single-switch wave, FOUNDER_OVERRIDE:role-agent-single-switch-2026-05-30); +1 for check_control_packet_line_refs.py (control-packet line-ref lint wave, FOUNDER_OVERRIDE:control-packet-line-ref-lint-2026-06-01); +1 for check_test_theater.py (FOUNDER_OVERRIDE:check-test-theater-ast-2026-06-03); +2 for claude-monitor autoping route=both session tools (claude_autoping_watch.py, ensure_claude_autoping.sh; FOUNDER_OVERRIDE:claude-monitor-autoping-route-both-2026-06-04b); +1 for launch_wave.py (pipeline-wave-launcher-builder-2026-06-18 wave, FOUNDER_OVERRIDE:pipeline-wave-launcher-builder-2026-06-18); +1 for claude_pager_receiver.py (pager-quickack-receiver-2026-06-17 wave, FOUNDER_OVERRIDE:pager-quickack-receiver-2026-06-17); +1 for set_orchestrator_mode.py (codex-mode-switch-2026-06-19 wave, FOUNDER_OVERRIDE:codex-mode-switch-2026-06-19)
CAP_CORE_DOCS = 14  # +1 for L3SubstrateArchitecture.v0.md (extracted from STATUS.md); +1 for StructuralNumbers.v0.md (numbers-as-structural-Mu design spec, FOUNDER_OVERRIDE:structural-numbers-design-doc-2026-06-17); +1 for SurrealNumbers.v0.md (Surreals-as-structure foundation contract, FOUNDER_OVERRIDE:surreals-as-structure-2026-06-26)

_L4_EXPENSIVE_SELECTOR_LOCKS = [
    (
        "tests/l4_gates/test_metabolize_cycle_gate.py",
        "TestMetabolizeCycleWiringGate",
        "test_python_metabolize_sink_to_r_null",
    ),
    (
        "tests/l4_gates/test_metabolize_cycle_gate.py",
        "TestMetabolizeCycleWiringGate",
        "test_python_metabolize_lobes_promote",
    ),
    (
        "tests/l4_gates/test_boot1_step_monotonicity_gate.py",
        "TestPythonBoot1StepMonotonicity",
        "test_multi_step_monotonic_and_grouped",
    ),
]


def _count_test_files() -> int:
    """Count test_*.py files under mu/tests/."""
    return len(list((REPO_ROOT / "mu" / "tests").rglob("test_*.py")))


def _count_tool_scripts() -> int:
    """Count .py and .sh files under mu/tools/."""
    tools_dir = REPO_ROOT / "mu" / "tools"
    return len(list(tools_dir.rglob("*.py"))) + len(list(tools_dir.rglob("*.sh")))


def _count_core_docs() -> int:
    """Count .md files under mu/docs/ (all subdirs)."""
    return len(list((REPO_ROOT / "mu" / "docs").rglob("*.md")))


def _pytest_marker_name(node: ast.AST) -> str | None:
    """Return marker name for pytest.mark.<name> decorator/pytestmark entries."""
    if isinstance(node, ast.Call):
        return _pytest_marker_name(node.func)
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "mark"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "pytest"
    ):
        return node.attr
    return None


def _pytest_marker_names_from_value(node: ast.AST) -> set[str]:
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return {
            name
            for item in node.elts
            for name in [_pytest_marker_name(item)]
            if name is not None
        }
    name = _pytest_marker_name(node)
    return {name} if name is not None else set()


def _pytestmark_names(module: ast.Module) -> set[str]:
    names: set[str] = set()
    for statement in module.body:
        if not isinstance(statement, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in statement.targets):
            names.update(_pytest_marker_names_from_value(statement.value))
    return names


def _decorator_marker_names(node: ast.ClassDef | ast.FunctionDef) -> set[str]:
    return {
        name
        for decorator in node.decorator_list
        for name in [_pytest_marker_name(decorator)]
        if name is not None
    }


def _find_class(module: ast.Module, class_name: str) -> ast.ClassDef:
    for statement in module.body:
        if isinstance(statement, ast.ClassDef) and statement.name == class_name:
            return statement
    raise AssertionError(f"Missing test class {class_name}")


def _find_method(class_node: ast.ClassDef, method_name: str) -> ast.FunctionDef:
    for statement in class_node.body:
        if isinstance(statement, ast.FunctionDef) and statement.name == method_name:
            return statement
    raise AssertionError(f"Missing test method {class_node.name}::{method_name}")


class TestGrowthCaps:
    """Enforce per-wave growth caps on tests, tools, and docs."""

    def test_test_file_count_within_cap(self):
        count = _count_test_files()
        limit = BASELINE_TEST_FILES + CAP_TEST_FILES
        assert count <= limit, (
            f"Test file count ({count}) exceeds baseline ({BASELINE_TEST_FILES}) + cap ({CAP_TEST_FILES}) = {limit}. "
            f"Consolidate or archive test files, or request GROWTH_EXCEPTION with founder sign-off."
        )

    def test_tool_script_count_within_cap(self):
        count = _count_tool_scripts()
        limit = BASELINE_TOOL_SCRIPTS + CAP_TOOL_SCRIPTS
        assert count <= limit, (
            f"Tool script count ({count}) exceeds baseline ({BASELINE_TOOL_SCRIPTS}) + cap ({CAP_TOOL_SCRIPTS}) = {limit}. "
            f"Consolidate or archive tool scripts, or request GROWTH_EXCEPTION with founder sign-off."
        )

    def test_core_docs_count_within_cap(self):
        count = _count_core_docs()
        limit = BASELINE_CORE_DOCS + CAP_CORE_DOCS
        assert count <= limit, (
            f"Core docs count ({count}) exceeds baseline ({BASELINE_CORE_DOCS}) + cap ({CAP_CORE_DOCS}) = {limit}. "
            f"Archive stale docs, or request GROWTH_EXCEPTION with founder sign-off."
        )


def test_green_gate_excludes_l4_expensive_from_merge_slow_lane():
    """Merge green gate must not run full-budget L4 evidence tests."""
    source = (REPO_ROOT / "scripts" / "green_gate.sh").read_text()
    assert '-m "slow and not l4_expensive" tests/l4_gates/' in source


def test_slow_tests_workflow_owns_l4_expensive_lane():
    """Nightly/manual slow workflow keeps the expensive evidence runnable."""
    source = (REPO_ROOT / ".github" / "workflows" / "slow_tests.yml").read_text()
    assert "timeout-minutes: 120" in source
    assert '-m "slow and not l4_expensive"' in source
    assert "-m l4_expensive" in source
    assert "--timeout=900" in source


def test_pr1017_over_budget_l4_selectors_stay_slow_l4_expensive():
    """PR #1017 over-budget selectors must stay out of merge green gate."""
    required_markers = {"slow", "l4_expensive"}
    for rel_path, class_name, method_name in _L4_EXPENSIVE_SELECTOR_LOCKS:
        module = ast.parse((REPO_ROOT / rel_path).read_text(), filename=rel_path)
        class_node = _find_class(module, class_name)
        method_node = _find_method(class_node, method_name)
        marker_names = (
            _pytestmark_names(module)
            | _decorator_marker_names(class_node)
            | _decorator_marker_names(method_node)
        )
        assert required_markers <= marker_names, (
            f"{rel_path}::{class_name}::{method_name} markers "
            f"{sorted(marker_names)} must include {sorted(required_markers)}"
        )
