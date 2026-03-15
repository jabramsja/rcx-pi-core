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
**Why deferred:** While nested functions CAN be decorated in Python, these closures inside
`make_projection_runner` are returned as API functions — adding a decorator would change
the returned function object. The `@host_builtin` decorator adds metadata that callers
don't expect. Adding inline `# AST_OK:` markers to these 2 lines would inflate the infra
count for what are standard type guards (checking if a value is a dict).
**Target wave:** Marker-truth wave (decide whether inline markers or decorator wrappers
are appropriate for closure-returned functions).

### D3: `_canonicalize_hash_numeric` no depth guard (Adversary)
- File: mu_type.py:574
- Recursive without depth limit, but always called after `assert_mu()` (MAX_MU_DEPTH=300)
**Why deferred:** All callers pass through `assert_mu()` which enforces MAX_MU_DEPTH=300.
Adding a depth parameter to `_canonicalize_hash_numeric` would be defense-in-depth for a
call path that's already bounded. The function is private (`_` prefix) with no external
callers. Risk: zero in current architecture. **Target wave:** Defense-in-depth hardening wave.

### D4: `NumericHashError` dead code (Expert)
- File: mu_type.py:560
- Defined but never raised; comment says "retained for future strictness"
**Why deferred:** The exception class is 2 lines of code, costs nothing at runtime, and
serves as a named error type for future use when numeric hash strictness is tightened.
Removing it would require re-adding it later. The "WHY KEPT" comment explicitly documents
the decision. **No fix planned** — intentional pre-wiring, not dead code.

### D5: `_mu_hash_cache` not thread-safe (Fuzzer)
- File: mu_type.py:471,515-524
- Module-global OrderedDict with compound non-atomic operations
**Why deferred:** RCX is single-threaded by design — Python GIL prevents data corruption,
and no logical races exist because projection execution is sequential. Thread-safe
alternatives (e.g., `threading.Lock`, `concurrent.futures.ThreadPoolExecutor`) would add
host dependencies and complexity for zero benefit in the current architecture. If RCX ever
moves to multi-threaded execution, the cache would need redesign anyway (not just a lock).
**No fix planned** — single-threaded architecture makes this a non-issue.

### D6: Dead code: `assert_handler_pure`/`validate_kernel_boundary` (Structural-Proof)
- File: mu_type.py:364-429
- Both carry explicit "WHY KEPT (0 production callers)" — intentional pre-wiring for L4+
**Why deferred:** These functions define the API surface for L4 handler purity validation.
They have 0 production callers today but ARE tested (`test_mu_type.py`) to prevent API
drift. They will be called when L4 gate enforcement requires handler purity checks.
Removing them now would lose the validated API surface. **No fix planned** — intentional
pre-wiring with test coverage to prevent drift.

### D7: Max-steps stall indistinguishable from genuine stall (Expert) — **RESOLVED 2026-03-14**
- Fixed: documented distinguishability pattern in run() docstring (steps == max_steps = exhaustion, steps < max_steps = genuine stall)
- 3 new tests in `TestStallDistinguishability`: genuine stall, max-steps exhaustion, contract proof
- No API change — existing return values already contain the information

### D8: Stale "Phase 7d will eliminate" comment (Structural-Proof) — RESOLVED (2026-03-14)
- File: projection_runner.py:36
- Forward reference to Phase 7d which hasn't closed
- Informational, not blocking

### D9: Three parallel seed registries (Expert)
- File: seed_integrity.py
- `SEED_CHECKSUMS`, `EXPECTED_PROJECTION_IDS`, `MU_SEED_LOCATIONS` all 19 entries, currently synced
**Why deferred:** The three registries serve different purposes — checksums (integrity),
projection IDs (ordering), and locations (filesystem paths). Merging them into a single
registry would either (a) create a complex nested structure that's harder to read, or
(b) require a schema migration. Cross-validation tests (`test_seed_loading_parity.py`)
mechanically lock key alignment, so drift is caught immediately. The manual 3-way sync
when adding a seed is ~3 lines of code — not worth a schema redesign.
**No fix planned** — design decision with mechanical test enforcement.

### D10: classify_linked_list silent return at 10001-node boundary (Fuzzer) — RESOLVED (2026-03-14)
- File: classify_mu.py:85-90
- `_max_classify_walk = 10000` causes silent "list" classification with no diagnostic
- Defense-in-depth cap by design — alternative is unbounded iteration
- Could add logging in future observability wave
