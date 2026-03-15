# P7-d Agent Review (Active Non-Blocking Residue)

Archived source snapshot:

- `reports/archive/deferred/p7d_agent_review_nonblockers.md`

Resolved or merely documented items were archived with the source snapshot.

## Open Items

### 1. `step_mu.py` still has substantial unannotated `isinstance` residue
**Why deferred:** 114 isinstance calls in step_mu.py lack AST_OK markers. These are
type guards (checking `isinstance(x, dict)`, `isinstance(x, str)`) that are structurally
necessary for safe Mu value handling. Adding markers to all 114 would be a large annotation
pass touching runtime code (L4_STRUCTURAL). The markers exist to TRACK host dependencies,
not eliminate them. **Target wave:** Marker-truth wave (dedicated annotation sweep).

### 2. `kernel.js` shadow-mode logic still duplicates the same check block twice
**Why deferred:** The shadow-mode path in kernel.js runs both the host path and the VM
path, then compares results. This intentional duplication is the DEFINITION of shadow mode.
It will be eliminated when the VM cutover flips from shadow to production default.
**Target wave:** VM cutover production-flip wave.

### 3. `stepKernelStructural` is still a trivial pass-through wrapper
**Why deferred:** 3-line function that calls `runStructural`. It's an exported public API
surface used by `self_tests.js`. Removing it would break the JS self-test interface.
The cost of keeping it is 3 lines of code — removing it saves nothing meaningful.
**No fix planned** — stable API surface, minimal cost.

### 4. `_STAGE0_SHADOW_ENABLED` remains externally mutable
**Why deferred:** Module-level boolean flag used as a test seam for shadow-mode toggling.
It's intentionally mutable so tests can enable/disable shadow mode. When the VM cutover
is complete, this flag will either be removed (if shadow mode is eliminated) or frozen
(if shadow mode becomes a permanent diagnostic lane).
**Target wave:** VM cutover production-flip wave.

### 5. `_STAGE0_VM_CUTOVER=True` path still has no direct test coverage
**Why deferred:** The `_STAGE0_VM_CUTOVER=True` path (production VM mode) is not directly
tested because cutover hasn't been promoted from shadow to default yet. Testing the
`True` path requires changing the default, which is the cutover itself. Coverage will
be added as part of the production-flip wave.
**Target wave:** VM cutover production-flip wave.

### 6. Shadow mode still has no dedicated fuzz coverage
**Why deferred:** Shadow mode is a temporary dual-execution path for validation. Adding
fuzz coverage for it would be testing infrastructure that will be removed or simplified
at cutover. The core fuzzers (match, subst, engine) already exercise the projections
that shadow mode wraps. **Target wave:** Only if shadow mode persists beyond cutover.
