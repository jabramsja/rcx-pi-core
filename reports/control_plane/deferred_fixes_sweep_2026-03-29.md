# Deferred Fixes Sweep

**Phase-A-Lock: LOCKED**
**Task:** [NEXT-CODEX-POST-REDTEAM]
**Wave class:** L4_ENABLER
**Target gate:** G8
**BOOTSTRAP_PHASE_B_EXCEPTION:** Yes — most fixes touch executor/supervisor surfaces

---

## Scope (10 fixes from 7 deferred reports)

### Fix 1: Gate 10 reads wrong attestation field (trivial)
- `meta_bridge_supervisor.py:850` reads `issues` instead of `validation_issues`
- **Source:** commit_pipeline_bridge_r1_findings_2026-03-23.md

### Fix 2: Phase B classification logs contaminate JSON stdout (trivial)
- Remove unconditional finding-classification prints from JSON-mode output
- **Source:** commit_pipeline_hardening_2026-03-23.md

### Fix 3: Agent-compliance hook fails open on missing transcript (small)
- `.claude/hooks/validate-agent-compliance.sh` exits 0 on missing/empty transcript
- Must emit block JSON when transcript is missing/empty
- **Source:** hook_soft_gate_residue.md

### Fix 4: Validator accepts garbage as compliant (small)
- `tools/runners/validate_agent_compliance.py` --strict allows compliant:true with zero findings
- Must require at least one structured finding or explicit verdict
- **Source:** hook_soft_gate_residue.md

### Fix 5: Terminal escape injection via bot comment bodies (small)
- `mu/tools/observability/_pane_prci.sh:47` echoes unsanitized bot comments
- Must sanitize before terminal output
- **Source:** deferred-cleanup-2026-03-29_bridge_nonblockers.md

### Fix 6: Gate 10 never forwards validation results to attestation (medium)
- `meta_bridge_supervisor.py:783` runs attestation without validation-gate results
- Attestation can't produce BEHAVIORAL proof entries without them
- **Source:** commit_pipeline_bridge_r1_findings_2026-03-23.md

### Fix 7: Closeout attestation authorizes GO with no behavioral proof (small)
- `check_closeout_attestation.py:174` must require at least one BEHAVIORAL proof for GO
- Coupled with Fix 6
- **Source:** commit_pipeline_bridge_r1_findings_2026-03-23.md

### Fix 8: Phase B sweeps unrelated dirty-worktree files (small)
- `_collect_changed_files()` returns all dirty files, not wave-scoped
- Must filter against plan-declared or routing-record files
- **Source:** commit_pipeline_hardening_2026-03-23.md

### Fix 9: Re-entry refresh drops deferred packet paths (medium)
- Re-entry doesn't propagate newly-created deferred packet paths back into supervisor package
- **Source:** commit_pipeline_hardening_2026-03-23.md

### Fix 10: W5A gate test missing re-entry coverage (small)
- Gate test doesn't exercise actual re-entry (boot1_depth > 0)
- Add mock-injected re-entry variant
- **Source:** w5a_reentry_gate_coverage.md

## Files changed (expected)
- `mu/tools/agents/meta_bridge_supervisor.py`
- `mu/tools/executors/phase_b_executor.py`
- `mu/tools/checks/check_closeout_attestation.py`
- `mu/tools/observability/_pane_prci.sh`
- `.claude/hooks/validate-agent-compliance.sh`
- `tools/runners/validate_agent_compliance.py`
- `tests/l4_gates/test_boot1_step_monotonicity_gate.py`

## Validation
```bash
PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/ tests/l4_gates/ -k "phase_b or meta_bridge or attestation or boot1_step" 2>&1 | tail -20
./tools/audit_fast.sh
```

## Post-wave
Archive deferred reports whose items are fully resolved by this wave.
