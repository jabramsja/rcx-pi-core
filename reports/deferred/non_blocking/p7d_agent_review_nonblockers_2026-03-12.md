# P7-d Agent Review (Active Non-Blocking Residue)

Archived source snapshot:

- `reports/archive/deferred/p7d_agent_review_nonblockers.md`

Resolved or merely documented items were archived with the source snapshot.

## Open Items

### 1. `step_mu.py` still has substantial unannotated `isinstance` residue — **RESOLVED 2026-03-15**
- Fixed: MT2 wave (PR #599) — 29 isinstance calls annotated with AST_OK:infra. INFRA_CEILING 94→123.

### 2. `kernel.js` shadow-mode logic still duplicates the same check block twice — **RESOLVED 2026-03-15**
- Fixed: S1-B wave — shadow mode disabled (cutover=True). Shadow code paths are now dead code. The duplication is no longer executed.

### 3. `stepKernelStructural` is still a trivial pass-through wrapper
**No fix planned** — stable API surface, minimal cost (3 lines).

### 4. `_STAGE0_SHADOW_ENABLED` remains externally mutable — **RESOLVED 2026-03-15**
- Fixed: S1-B wave — `_STAGE0_SHADOW_ENABLED = false` in both substrates. Flag retained for diagnostic rollback but default is off.

### 5. `_STAGE0_VM_CUTOVER=True` path still has no direct test coverage — **RESOLVED 2026-03-15**
- Fixed: S1-A wave (PR #598) added 15 cutover=True tests. S1-B flipped the default to True — all 4,049 core tests now run under cutover=True by default.

### 6. Shadow mode still has no dedicated fuzz coverage — **RESOLVED 2026-03-15**
- Fixed: Shadow mode disabled at cutover. No longer a separate execution path to fuzz. Core fuzzers exercise the VM-primary path directly.
