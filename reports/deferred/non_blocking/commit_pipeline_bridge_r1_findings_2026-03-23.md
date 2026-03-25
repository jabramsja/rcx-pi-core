# Deferred: Commit Pipeline Bridge R1 Findings (1-11)

**Source:** Bridge review commit-pipeline-impl-r1-0bf683fe (Codex reviewer, 2026-03-23)
**Classification:** NON-BLOCKING (control-surface hardening, not commit-pipeline logic)
**Wave:** commit-pipeline-automation

Finding #12 (test failures) was fixed inline. Finding #5 (post-merge dirty tree) was fixed inline in commit_executor.py. Remaining findings (1-4, 6-11) are deferred below.

---

## Finding 1 (CRITICAL): Phase B accepts invalid routing tokens and unlocked plans

**File:** `mu/tools/executors/phase_b_executor.py:380`
**Issue:** `validate_inputs()` only logs warnings for wrong routing tokens (ROUTE_PHASE_A) and unlocked plans. Execution continues to `commit_ready`.
**Impact:** Direct invocation bypasses the routing guard.
**Fix path:** Make validation errors fatal unless explicit `--force` flag is provided. Separate wave — touches Phase B control surface.

## Finding 2 (HIGH): Closeout attestation authorizes GO with no behavioral validation proof

**File:** `mu/tools/checks/check_closeout_attestation.py:174`
**Issue:** Generated attestation reports `"go_authorized": true` with only git-derived `changed_files` proof and `SOURCE_LOCK` invariant proofs, zero `BEHAVIORAL` proof entries.
**Impact:** Attestation GO is structurally valid but semantically empty for behavioral validation.
**Fix path:** Attestation generator must require at least one BEHAVIORAL proof entry for GO. Separate wave — touches attestation control surface.

## Finding 3 (HIGH): Gate 10 never supplies validation results to attestation generator

**File:** `mu/tools/agents/meta_bridge_supervisor.py:783`
**Issue:** Gate 10 runs attestation checker with `--generate --json` only. Does not forward validation-gate results, so attestation cannot gain BEHAVIORAL proof.
**Fix path:** Gate 10 must pass validation results to attestation generator. Coupled with finding 2.

## Finding 4 (HIGH): Phase B sweeps unrelated dirty-worktree files into supervisor package

**File:** `mu/tools/executors/phase_b_executor.py:199`
**Issue:** `_collect_changed_files()` returns all dirty worktree files, not just wave-scoped files. Unfiltered list passed to supervisor/handoff.
**Impact:** Supervisor sees unrelated files; handoff may stage unintended files.
**Fix path:** Filter `_collect_changed_files()` against `files_to_stage` from routing record. Separate wave — Phase B control surface.

## Finding 5 (HIGH): Commit executor reports success when post-merge tree is dirty — FIXED

**File:** `mu/tools/executors/commit_executor.py:784`
**Issue:** Post-merge verification did not fail-closed on dirty working tree.
**Status:** FIXED inline — added `status_output` check that returns error if working tree is dirty after merge.

## Finding 6 (MEDIUM): Closeout attestation check not wired into pre-commit hook

**File:** `mu/tools/hooks/pre-commit-doc-check`
**Issue:** `check_closeout_attestation.py` exists but is not called by the pre-commit hook.
**Impact:** Attestation is generated but not enforced mechanically.
**Fix path:** Wire into pre-commit hook or add as step in commit_executor. Separate wave.

## Finding 7 (MEDIUM): Control surface invariant checker not wired into pipeline

**File:** `mu/tools/checks/check_control_surface_invariants.py`
**Issue:** Checker exists with tests but is not called by any gate or hook.
**Impact:** Control-surface invariants are tested but not enforced in the pipeline.
**Fix path:** Wire into pre-commit hook or supervisor gate. Separate wave.

## Finding 8 (MEDIUM): Bridge adapter hardcoded review mode despite plan prohibition

**File:** `mu/tools/agents/bridge_adapters.py`
**Issue:** Bridge adapter may still use review mode for implementer invocations in some code paths.
**Impact:** Violates plan requirement that implementer is invoked via bridge adapter, not review mode.
**Fix path:** Audit all bridge adapter call sites. Separate wave — bridge control surface.

## Finding 9 (MEDIUM): meta_bridge_client does not validate supervisor envelope schema

**File:** `mu/tools/agents/meta_bridge_client.py`
**Issue:** Client trusts supervisor envelope without schema validation.
**Impact:** Malformed envelope could propagate bad decisions.
**Fix path:** Add envelope schema validation in client. Separate wave.

## Finding 10 (LOW): executor_config.json has stale entries

**File:** `mu/tools/executors/executor_config.json`
**Issue:** Config references may be stale after the commit pipeline rewrite.
**Impact:** Low — config is advisory, not load-bearing for the pipeline.
**Fix path:** Audit and update config entries. Can be done in maintenance wave.

## Finding 11 (LOW): shared_agent_utils has unused imports after refactor

**File:** `mu/tools/runners/shared_agent_utils.py`
**Issue:** Unused imports remain after bridge adapter refactor.
**Impact:** Dead code, no functional impact.
**Fix path:** Clean up in maintenance wave.
