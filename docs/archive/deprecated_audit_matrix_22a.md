# Deprecated Docs/Test Audit Refresh Matrix — Round 22A

**Date**: 2026-02-14
**Scope**: Full codebase — docs, tests, deprecated modules

---

## Summary

| Classification | Count | Action Required |
|---|---|---|
| ACTIVE | ~85 docs, 2000+ tests | None |
| STALE | 5 docs | Update references |
| GAP | 0 | None (100% DOC_STATUS coverage in governed folders) |
| ORPHAN | 1 doc | Archive or remove |
| ARCHIVE_CANDIDATE | 1 doc misplaced in core/ | Move to docs/archive/ |

---

## 1. Archived Test Files (all correctly archived)

| Test File | Archive Location | Original Purpose |
|-----------|-----------------|------------------|
| test_bytecode_vm_v0.py | tests/archive/ | Bytecode VM (superseded by kernel) |
| test_kernel_v0.py | tests/archive/legacy/ | Pre-meta-circular kernel |
| test_omega_determinism.py | tests/archive/legacy/ | RCX-Omega determinism |
| test_semantic_goldens.py | tests/archive/legacy/ | Omega semantic goldens |
| test_semantic_invariants.py | tests/archive/legacy/ | Omega invariants |
| test_snapshot_integrity.py | tests/archive/legacy/ | Snapshot system |
| test_snapshot_roundtrip_v1.py | tests/archive/legacy/ | Snapshot roundtrip |
| test_trace_contract.py | tests/archive/legacy/ | Pre-MC trace format |

**Mechanism**: All blocked by `tests/archive/conftest.py::pytest_ignore_collect()`. Working correctly.

---

## 2. Stale Doc References

| Document | Stale Reference | Issue | Fix |
|----------|----------------|-------|-----|
| docs/schemas/snapshot_json_schema.md | `cd rcx_pi_rust && cargo...` | Rust build instructions for deprecated surface | Remove Rust build section |
| docs/audit/MetaCircularReadiness.v1.md | `rcx_pi_rust/src/replay_cli.rs` | References Rust replay CLI | Add note: "Rust parity deferred (rcx_pi_rust archived)" |
| docs/core/MetaCircularKernel.v0.md | `tests/archive/legacy/test_kernel_v0.py` | References archived test as active | Update to point at active kernel tests |
| docs/execution/DeepStep.v0.md | `prototypes/test_deep_eval_v0.py` | References prototype as primary | Clarify: prototype is historical, active test is tests/test_deep_eval_v0.py |
| docs/core/LegacySurfaceDecisionRecord.v0.md | `rcx_pi_rust/`, `rcx_omega/` | References deprecated surfaces | Acceptable (it's the decision record FOR those surfaces) |

---

## 3. DOC_STATUS Coverage

| Governed Folder | Files | Coverage | Status |
|----------------|-------|----------|--------|
| docs/core/ | 23 | 100% | Complete |
| docs/agents/ | 3 active | 100% | Complete |
| docs/audit/ | 3 | 100% | Complete |
| docs/execution/ | 10 | 100% | Complete |
| docs/cli/ | 5 | 100% | Complete |
| docs/schemas/ | 6 md | 100% | Complete |
| docs/reviews/ | 2 | 100% | Complete |

**No gaps found.** All governed docs have DOC_STATUS headers.

---

## 4. Orphaned Docs

| Document | Location | Status | Recommendation |
|----------|----------|--------|----------------|
| TESTING_PERFORMANCE_ISSUE.md | docs/ (root) | Not referenced by code/tests | Archive or keep as historical incident report |

---

## 5. Misplaced Docs

| Document | Current | Should Be | Reason |
|----------|---------|-----------|--------|
| LegacySurfaceDecisionRecord.v0.md | docs/core/ | docs/core/ (KEEP) | Decision record about deprecated surfaces belongs in core governance, not archive |

---

## 6. Deprecated Modules Still in Codebase

| Module | Location | Active Tests | Active Callers | Recommendation |
|--------|----------|-------------|----------------|----------------|
| bytecode_vm.py | rcx_pi/ | None (archived) | None | Archive candidate (Round 23+) |

---

## 7. L3 Parity Findings

| Seed | Python Status | JS Status | Finding |
|------|--------------|-----------|---------|
| recurrence.v2.json | Active (tests pass) | Not loaded in eval_step.js | JS needs v2 for full L3 parity |
| All others | Active | Active | Parity verified |

---

## Recommended Actions (Priority Order)

1. **P1**: Fix 4 stale doc references (items in Section 2, excluding decision record)
2. **P2**: Load recurrence.v2.json in JS substrate (L3 parity gap)
3. **P3**: Archive bytecode_vm.py after safety review (Round 23+)
4. **P4**: Consider archiving TESTING_PERFORMANCE_ISSUE.md

Items P1-P2 are addressable in Round 22B-22C alongside the docs move.
Items P3-P4 are lower priority and can be deferred.
