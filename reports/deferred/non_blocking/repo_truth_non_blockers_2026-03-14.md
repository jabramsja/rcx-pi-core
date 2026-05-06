# Repo Truth Non-Blockers (Active Residue)

Extracted on 2026-03-14 from:

- `reports/codex/Archive/non_blockers/drift_2026-03-12_repo_redteam_non_blockers.md`
- `reports/codex/Archive/non_blockers/redteam_2026-03-14_p7a_p7d_non_blockers.md`

Archived as stale/resolved from the source snapshots:

- the old JS public-path `vmConfig` wiring concern is resolved
- the old startup-cost-before-use concern is resolved
- Hypothesis fuzzer timeout in hemisphere routing parity tests is resolved
- old blocker carryovers N10/N11 were archived to `reports/archive/deferred/repo_truth_blockers_2026-03-14.md`

2026-05-06 cleanup note: resolved sections N4, N6, N7, N9, N12, N13,
N15, N16, N17, and N19 were moved to
`reports/archive/deferred/repo_truth_non_blockers_2026-03-14_partial-closed-by-deferred-non-blocking-cleanup-2026-05-06.md`.
Resolved section N18 was retained because it references Claude surfaces and was
not re-adjudicated by this cleanup.

## Active Non-Blockers

### N1. Python VM cutover coverage reconstruction is not directly locked

- `_step_kernel_with_vm()` reconstructs coverage semantics for compiled
  `match.v2` / `subst.v2`
- the current cutover gate proves equivalence and polarity, but not exact
  `record_no_match` / `record_match` bookkeeping parity
**Why deferred:** The cutover gate tests prove behavioral equivalence (same input → same
output) and polarity (VM path produces same match/subst results as host path). Adding
exact bookkeeping parity tests requires instrumenting the VM to emit coverage events,
which is a new capability in the Stage0 VM. **Target wave:** VM cutover production-flip
wave (when cutover is promoted from shadow to default).

### N2. JS bridge-mode VM shadow evidence is still thinner than the core lane

- JS self-tests prove bridge-mode smoke behavior and bridge ordering validation
- they do not yet directly lock the full `kernel.v1 -> bridge -> match.v2 ->
  subst.v2` ordering semantics under the VM-shadow lane
**Why deferred:** The JS substrate's VM shadow mode was added in P7-d as a parallel
execution path. The core lane (Python) has deeper evidence because it's the primary
development surface. Thickening JS shadow evidence requires writing JS-specific
ordering tests that exercise the bridge composition path end-to-end. **Target wave:**
JS bridge-mode evidence wave (requires JS test infrastructure expansion).

### N3. P7-d is execution-path progress, not broad host-surface reduction

- tracked markers are flat
- the broader authority and total inventory ledgers remain much larger than the
  narrow tracked-marker ledger
**Why deferred:** This is an honest observation, not a fixable defect. P7-d reduces
host-semantic debt on the kernel execution path (match/subst/step), but the broader
authority inventory (218 sites) and total inventory (305 sites) include all runtime
functions — most of which are not on the kernel path. Reducing the broader inventory
requires eliminating host constructs in engine pipeline, hemisphere routing, ontology
promotion, etc. — each of which is a separate L4 workstream.
**No single fix** — this is the nature of incremental reduction.

### N5. `pipeline.js` still has no explicit size/shape governance

- the file remains large (~800 lines)
- there is no explicit cap or decomposition contract comparable to the JS
  bootstrap-core governance gate
**Why deferred:** pipeline.js is the JS engine pipeline — it handles boundary dispatch,
ontology promotion, algorithm routing, and evidence collection. These are logically
related functions that share state (seedProjectionMap, kernelProjections). Splitting
into smaller files would create circular dependency issues or require a module loader.
The file is well-sectioned with clear function boundaries. A LOC cap without
decomposition guidance would be arbitrary. **Target wave:** JS architecture refactor
wave (requires Wave A design for module decomposition strategy).

### N14. Stage0 capture_ref returns null/None for hostile leaves (design gap)

- capture_ref deep-copies via _safe_mu_copy. Non-Mu types (subclasses) are canonicalized to null/None.
- Bridge considers this a "successful match on hostile input" since the VM returns match with root=null.
- Design decision: null/None is the correct fail-closed canonical value for non-Mu inputs. The alternative (stall on non-Mu capture) would require type-checking at capture_path time, which is a larger change.
- Status: documented design gap, not a production exploit path.

### N18. /checkpoint should force comprehensive memory.md + claude.md re-read — **RESOLVED 2026-03-14**

2026-05-06 cleanup note: retained because this resolved section references
Claude surfaces; it was not re-adjudicated or extracted by this cleanup.

- Fixed: /checkpoint skill Step 0 now includes MANDATORY re-read with explicit file list and "This is not a checkbox" instruction.
- Claude Code PreToolUse hook (`.claude/hooks/pre-commit-reminder.sh`) shows MEMORY.md + CLAUDE.md before git commit tool calls.
