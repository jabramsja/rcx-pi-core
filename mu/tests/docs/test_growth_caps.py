"""Growth cap enforcement — tracks test/tool/doc counts against baselines.

Fails if counts exceed baseline + per-wave cap without documented consolidation.
See mu/docs/core/DocGovernance.v0.md § "Growth Caps" for policy.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

# Baseline snapshot (2026-02-28, Phase 8c, dev HEAD 965c64d)
# Update these when phase boundary is crossed (founder approval required).
BASELINE_TEST_FILES = 190
BASELINE_TOOL_SCRIPTS = 68  # .py + .sh in mu/tools/ (67 + sync_native_agents.sh, 2026-03-11)
BASELINE_CORE_DOCS = 48  # .md in mu/docs/ (all subdirs) — bumped for P6 TypedNumericEnvelopes.v0.md

# Per-wave caps from DocGovernance.v0.md
CAP_TEST_FILES = 122  # +1 for test_executor_config_alignment.py; +1 for test_codex_startup_state.py (startup hardening, founder sign-off 2026-04-15); +1 for test_pipeline_agent_pager.py (pager wave, founder sign-off 2026-04-17); +1 for test_commit_executor_post_merge_cleanup.py (post-merge-cleanup wave, founder sign-off 2026-04-17); +1 for test_check_private_attr_access.py (AST-anti-cheat wave, standing pipeline-bug-fix authorization 2026-04-20); +1 for test_commit_executor_step14_conflict_precheck.py (Step 14 conflict fast-fail wave, standing pipeline-bug-fix authorization 2026-04-20); +1 for test_commit_executor_step14_autoresolve.py (Step 14 auto-resolve wave, standing pipeline-bug-fix authorization 2026-04-20); +1 for test_wave_id_derivation.py (restart-branch pre-push derivation wave, founder sign-off 2026-04-21); +1 for test_codex_autoping_watch.py (post-reentry reroute pager/autoping wave, founder sign-off 2026-04-25); +1 for test_phase_a_executor.py (pager lifecycle event coverage wave, founder sign-off 2026-04-26); +1 for test_agent_bus_namespacing.py (parallel pipeline bus namespacing wave, founder sign-off 2026-04-30); +1 for test_pane_prci_observability.py (deferred consolidation E5/E6 wave, FOUNDER_OVERRIDE:deferred-consolidation-e5-e6-2026-04-02); +3 for post-redteam engine-state/scheduler structural tests (post-redteam-engine-state-scheduler-reduction-2026-04-30)
CAP_TOOL_SCRIPTS = 48  # +1 for _resolve_live_root.sh; +2 for startup-hardening session tools (founder_learning_snapshot.py, check_codex_startup_state.py; founder sign-off 2026-04-15); +1 for pipeline_agent_pager.py (pager wave, founder sign-off 2026-04-17); +1 for check_private_attr_access.py (AST-anti-cheat wave, standing pipeline-bug-fix authorization 2026-04-20); +4 for Codex autoping session watcher scripts (codex_autoping_watch.py, codex_autoping_window.sh, ensure_codex_autoping.sh, render_codex_autoping_status.py; founder sign-off 2026-04-25); +1 for pipeline_monitor_identity.py (parallel pipeline monitor identity wave, founder sign-off 2026-04-30); +1 for seed_binary_migration.py (FOUNDER_OVERRIDE:n3-projection-loader-seed-migration-integrity-chain-2026-05-14)
CAP_CORE_DOCS = 12  # +1 for L3SubstrateArchitecture.v0.md (extracted from STATUS.md)


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
