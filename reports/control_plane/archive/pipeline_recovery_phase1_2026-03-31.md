# Pipeline Recovery Phase 1: Failure Classifier + Tier 1 Auto-Fix

**Status:** PHASE_A_LOCKED
**Task:** [PIPELINE-RECOVERY]
**Surface:** `mu/tools/executors/recovery_gate.py`, `mu/tests/tools/test_recovery_gate.py`
**Classification:** L4_ENABLER (pipeline hardening, no runtime dirs)
**Scope:** New file — recovery_gate.py Phase 1 (classifier + Tier 1 auto-fix + tests)
**Design:** `mu/docs/agents/PipelineRecovery.v0.md`

---

## What's Implemented

### recovery_gate.py (367 lines)
- **FailureClass enum** — 16 failure types across 4 tiers
- **classify_failure(result)** — pure dict classifier, no external calls
- **Tier 1 auto-fix functions:**
  - fix_stale_bridge_lock — check PID, truncate if dead
  - fix_stale_git_index_lock — unlink if exists
  - fix_stale_executor_state — compare wave_id, unlink on mismatch
  - fix_mixed_staging — git reset HEAD for mixed-state files
- **Recovery log** — .agent_bus/recovery/recovery_log.json, capped 500 entries
- **attempt_recovery()** — main entry point, 2-attempt-per-tuple bound

### test_recovery_gate.py (299 lines, 49 tests)
- All 16 failure classes tested
- Each Tier 1 fix function: happy path + edge cases
- Recovery log: round-trip, capping, corruption handling
- Integration: attempt_recovery end-to-end

## Bot Comments to Sweep (PR #703)
- P2: Match meta_bridge_supervisor before bridge_supervisor in phase detection
- P2: Fix invalid f-string in agent status timeline parsing
- P3: Check meta-bridge phase before generic bridge match

---

## Acceptance Criteria

- [ ] 49 tests pass in test_recovery_gate.py
- [ ] No imports from bridge_supervisor, bridge_adapters, or agent modules
- [ ] Recovery log schema matches design doc
- [ ] Bot comment remediation from PR #703 addressed
- [ ] All existing tests pass (audit_fast.sh)
