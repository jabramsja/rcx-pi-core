# Dialectic Reviewer From Config

Date: 2026-05-30
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: `[NEXT-CODEX-POST-REDTEAM]`
Wave ID: `dialectic-reviewer-from-config-2026-05-30`
Class: L4_ENABLER
Target Gate: G8
Lane: control-surface
Authorization: founder-directed (2026-05-30) — close PR #1046 bot P2 finding #2 (complete the single-switch)
Phase-A-Lock: BOOTSTRAP_PHASE_B_EXCEPTION
FOUNDER_OVERRIDE:dialectic-reviewer-from-config-2026-05-30

## Problem
`dialectic_executor.py` hardcoded `--reviewer codex` when invoking the bridge for
CONTINUE_DIALECTIC narrowing rounds. After the role-agent single-switch wave (PR #1046),
`role_agents.reviewer` is the sole reviewer control surface — but the hardcode meant a
`set_roles --reviewer claude` switch would NOT propagate to dialectic rounds (they would
stay codex). The PR #1046 Codex bot flagged this as P2 finding #2.

## Goal
Make the dialectic reviewer follow the configured reviewer role, completing the
"switch ANY LLM for reviewer" goal. Latent today (reviewer=codex matches the old
hardcode), so no current behavior change — this prevents an inconsistency the moment
the reviewer is switched to claude.

## Scope (allowed product writes)
- `mu/tools/executors/dialectic_executor.py`      (derive reviewer from config; import configured_role_agents)
- `mu/tests/tools/test_dialectic_executor.py`     (NEW — reviewer-derivation regression)
- `mu/tests/docs/test_growth_caps.py`             (CAP_TEST_FILES +1 for the new test; FOUNDER_OVERRIDE)
- `reports/control_plane/dialectic-reviewer-from-config-2026-05-30.md`  (this packet)

No runtime, substrate, seed, scheduler, registry, projection, parity, or Mu-semantic changes.

## Changes
1. `dialectic_executor.py`: added module-level `resolve_dialectic_reviewer(repo_root)` returning
   `configured_role_agents(repo_root)["reviewer"]["agent"]` (the env-aware configured reviewer),
   with a defensive fallback to `"codex"` on any resolution error (preserves prior behavior).
   The bridge `review` command now passes `--reviewer <resolved>` instead of the literal
   `"codex"`. Imported `configured_role_agents` from executor_common (try + fallback import blocks).
2. `test_dialectic_executor.py` (NEW): asserts the resolver follows the configured role
   (claude/codex) and falls back to codex on error. Public helper name (no private-attr access)
   keeps the audit_fast anti-cheat scan clean.
3. `test_growth_caps.py`: CAP_TEST_FILES 124->125 (+1 for the new test file) with a documented
   FOUNDER_OVERRIDE comment, per the file's per-wave-cap convention (pre-bumped proactively).

## Local Evidence
- `python3 -m py_compile mu/tools/executors/dialectic_executor.py` -> OK
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_dialectic_executor.py mu/tests/docs/test_growth_caps.py` -> 8 passed
- `grep -c '"--reviewer", "codex"' dialectic_executor.py` -> 0 (hardcode gone); call site uses `resolve_dialectic_reviewer(repo_root)` (count 1)
- helper verified: follows config (claude/codex), falls back to codex on error
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id dialectic-reviewer-from-config-2026-05-30 --wave-class L4_ENABLER`
- `git diff --check`
