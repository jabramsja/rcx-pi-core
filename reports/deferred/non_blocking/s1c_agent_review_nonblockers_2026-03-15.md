# S1-C Agent Review Non-Blockers (2026-03-15)

## Source
SDK agent review (quick depth) on S1-C implementation files.

## Non-Blocking Findings

### NB1. Dead shadow-mode code paths in both substrates
- Shadow mode disabled (S1-B). Shadow code paths in step_mu.py and kernel.js are dead code.
- **Why deferred:** Retained for rollback per S1-B scope guard. Cleanup is post-stability.

### NB2. 4 identical compiled-bundle loader functions (Expert)
- `_load_compiled_match_v2_bundle`, `_load_compiled_subst_v2_bundle`, `_load_compiled_kernel_v1_bundle`, `_load_compiled_bridge_bundle` differ only by filename and cache variable.
- **Why deferred:** Mechanical DRY — extract factory function. Not a correctness issue. Target: Tier 2 cleanup.

### NB3. Repeated coverage-recording boilerplate in _step_kernel_with_vm (Expert)
- Coverage no_match/match recording pattern repeated 4 times (once per seed group).
- **Why deferred:** Same DRY pattern as NB2. Extract helper. Not a correctness issue.

### NB4. `_stepKernelCoreNonMeta` returns stalled:false on max-steps exhaustion (Adversary) — DESIGN-GATED
- Real JS semantic divergence: non-meta returns `stalled: false` on max-steps exhaustion (kernel.js:174). Meta path correctly returns `stall: true` (kernel.js:115).
- **Attempted fix failed:** Changing `stalled: false` to `true` broke 27 parity tests. Callers (engine pipeline, runAlgorithmWithBridge) depend on `stalled: false` for max-steps exhaustion to continue processing.
- **Root cause:** Non-meta path's `stalled` field has different semantics than meta path's `stall` field. Fixing requires coordinated caller updates.
- **Target:** Wave A design pass for non-meta/meta path unification.

### NB5. Bundle provenance bypass via field stripping (Adversary)
- If `source_seed` or `source_digest` fields are removed from a bundle, `_verify_bundle_provenance` silently passes.
- **Why deferred:** By design — hand-authored test bundles lack these fields. The provenance check is for compiled bundles which always have both fields. Hardening: fail-closed when `lowering_version` present but `source_digest` absent. Target: N15 follow-up.

### NB6. `isinstance` in test file without `@host_builtin` marker
- `test_meta_circular_evidence_gate.py` uses `isinstance` check without marker.
- **Why deferred:** Test file, not runtime code. Markers are for runtime debt tracking.

### NB7. JS `_stepKernelCoreNonMeta` omits `isKernelTerminal` check — DESIGN-GATED
- Real JS semantic gap: non-meta path never calls `isKernelTerminal()`. Returns raw kernel state ({_mode, _result, _stall}) instead of extracted domain output.
- **Attempted fix failed:** Adding `isKernelTerminal()` + `extractKernelResult()` broke callers who inspect raw kernel state for their own terminal logic.
- **Root cause:** Callers (engine pipeline, runAlgorithmWithBridge) build their own terminal detection on top of the raw kernel result. Centralizing extraction requires coordinating all callers.
- **Target:** Same Wave A as NB4 — non-meta/meta path unification.

### NB8. `guardMaxSteps` is a special case of `guardIterationCap` (Expert)
- JS utility function overlap.
- **Why deferred:** Trivial DRY. Not a correctness issue.

### NB9. STATUS.md prose describes pre-S1-C kernel path details (Bridge R5)
- STATUS.md:345+ still describes tracked markers as "4 AST_OK bootstrap" and kernel path as "host for kernel.v1/bridge".
- **Why deferred:** Prose update for STATUS.md is a MAINTENANCE tracker sync, not part of the L4_STRUCTURAL wave. Will be fixed in closeout.

### NB10. JS kernel.js: stage0VmStep match result lacks root/matched_program_id assertion (Bridge R6) — **RESOLVED 2026-03-15**
- Fixed: `_assertVmMatchResult()` added to `_stepKernelWithVM` in kernel.js. All 4 VM call sites now assert `.root` is defined before returning. Fail-closed on malformed VM results (parity with Python KeyError).

### NB11. test_meta_circular_evidence_gate.py header describes pre-S1-C trusted path (Bridge R5)
- Module docstring says step_kernel_mu proves structural execution through _step_trusted -> _apply_projection_trusted.
- **Why deferred:** Docstring-only, not a behavioral issue. Fix in next cleanup pass.
