# Wave 1A: Pipeline Validation Fixes (CRITICAL + HIGH)

**Status:** PHASE_A_LOCKED
**Task:** NEXT-CODEX-POST-REDTEAM deferred cleanup
**Surface:** `mu/tools/executors/phase_b_executor.py`, `mu/tools/checks/check_closeout_attestation.py`, `mu/tools/agents/meta_bridge_supervisor.py`, `mu/tools/executors/commit_executor.py`, `mu/tools/agents/bridge_adapters.py`
**Classification:** L4_ENABLER (pipeline hardening, no runtime dirs)
**Scope:** 9 items — Cluster A (5 validation) + Cluster B (4 executor)
**Source:** `reports/deferred/non_blocking/wave1_pipeline_consolidated_2026-03-31.md`

---

## Work Items

### A1. [CRITICAL] Phase B accepts invalid routing tokens
- **File:** `mu/tools/executors/phase_b_executor.py` — `validate_inputs()` function
- **Fix:** Make validation errors fatal (raise or sys.exit) unless explicit `--force` flag. Currently only logs warnings.

### A2. [HIGH] Closeout attestation GO with no behavioral proof
- **File:** `mu/tools/checks/check_closeout_attestation.py` — attestation generator
- **Fix:** Require at least one BEHAVIORAL proof entry before authorizing GO. Reject if only git-derived proofs.

### A3. [HIGH] Gate 10 never supplies validation results to attestation
- **File:** `mu/tools/agents/meta_bridge_supervisor.py` — Gate 10 section
- **Fix:** Forward validation-gate results to attestation generator. Coupled with A2.

### A4. [HIGH] Phase B sweeps unrelated dirty-worktree files
- **File:** `mu/tools/executors/phase_b_executor.py` — `_collect_changed_files()`
- **Fix:** Filter collected files against `files_to_stage` from the routing record.

### A5. [HIGH] Gate 10 can't authorize non-receipt-chain waves
- **File:** `mu/tools/agents/meta_bridge_supervisor.py` — Gate 10 proof emission
- **Fix:** Add control-surface proof type to Gate 10 output alongside gate-style proofs.

### B1. [MEDIUM] Streaming adapter timeouts orphan child processes
- **File:** `mu/tools/agents/bridge_adapters.py` — timeout handling
- **Fix:** Use process group kill (`os.killpg`) or explicit child cleanup on timeout.

### B2. [MEDIUM] Missing indicator collector treated as success
- **File:** `mu/tools/executors/commit_executor.py` — indicator collection step
- **Fix:** Fail closed (return error) when collector script is missing.

### B3. [LOW] force_add_files denylist case-sensitive on macOS
- **File:** `mu/tools/executors/commit_executor.py` — `force_add_files` denylist
- **Fix:** Normalize to lowercase for comparison.

### B4. [LOW] Commit executor comment contradicts receipt authority
- **File:** `mu/tools/executors/commit_executor.py:460`
- **Fix:** Update comment to match runtime behavior (supervisor receipt is authoritative).

---

## Acceptance Criteria

- [ ] A1: `validate_inputs()` raises on invalid routing token (test: invoke with ROUTE_PHASE_A)
- [ ] A2: Attestation rejects GO when BEHAVIORAL proof list is empty
- [ ] A3: Gate 10 passes validation results to attestation
- [ ] A4: `_collect_changed_files()` filters against routing record
- [ ] A5: Gate 10 emits control-surface proof type
- [ ] B1: Timeout kills process group, not just parent
- [ ] B2: Missing collector returns error
- [ ] B3: Denylist comparison is case-insensitive
- [ ] B4: Comment updated
- [ ] All existing tests pass (`audit_fast.sh`)
