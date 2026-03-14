# Deferred Findings — Wave 4c (Type/Classify/Runner/Seed/Kernel)

Date: 2026-03-10

## Deferred Items

### D1: 5 unmarked isinstance calls in classify_mu.py (Structural-Proof + Grounding) — RESOLVED (Wave 5, 2026-03-14)
- File: classify_mu.py:51,61,91,109,118
- No `@host_builtin` annotation; `host_builtin` not imported in this file
- Marker-truth wave scope, not runtime audit
- Defer to mt wave

### D2: 2 unmarked isinstance in projection_runner.py nested closures (Verifier + Structural-Proof)
- File: projection_runner.py:63,70
- `is_done()`/`is_state()` use isinstance without `@host_builtin`
- Nested functions can't use Python decorators; module comment acknowledges for-loop debt only
- Defer to mt wave

### D3: `_canonicalize_hash_numeric` no depth guard (Adversary)
- File: mu_type.py:574
- Recursive without depth limit, but always called after `assert_mu()` (MAX_MU_DEPTH=300)
- Private function (`_` prefix), all callers validate depth first
- Could add defensive depth param in future hardening wave

### D4: `NumericHashError` dead code (Expert)
- File: mu_type.py:560
- Defined but never raised; comment says "retained for future strictness"
- Intentional design

### D5: `_mu_hash_cache` not thread-safe (Fuzzer)
- File: mu_type.py:471,515-524
- Module-global OrderedDict with compound non-atomic operations
- Single-threaded runtime by design; GIL prevents corruption but not logical races
- No practical risk in current architecture

### D6: Dead code: `assert_handler_pure`/`validate_kernel_boundary` (Structural-Proof)
- File: mu_type.py:364-429
- Both carry explicit "WHY KEPT (0 production callers)" — intentional pre-wiring for L4+
- Tested in `test_mu_type.py` to prevent API drift

### D7: Max-steps stall indistinguishable from genuine stall (Expert)
- File: projection_runner.py:118
- `run()` returns `is_stall=True` for both timeout and genuine stall
- Would require API change (4-tuple return) affecting all callers

### D8: Stale "Phase 7d will eliminate" comment (Structural-Proof) — RESOLVED (2026-03-14)
- File: projection_runner.py:36
- Forward reference to Phase 7d which hasn't closed
- Informational, not blocking

### D9: Three parallel seed registries (Expert)
- File: seed_integrity.py
- `SEED_CHECKSUMS`, `EXPECTED_PROJECTION_IDS`, `MU_SEED_LOCATIONS` all 19 entries, currently synced
- Cross-validation tests now mechanically lock key alignment and path resolution,
  but adding a seed still requires manual 3-way sync across the registries
- Design decision, not a bug

### D10: classify_linked_list silent return at 10001-node boundary (Fuzzer) — RESOLVED (2026-03-14)
- File: classify_mu.py:85-90
- `_max_classify_walk = 10000` causes silent "list" classification with no diagnostic
- Defense-in-depth cap by design — alternative is unbounded iteration
- Could add logging in future observability wave
