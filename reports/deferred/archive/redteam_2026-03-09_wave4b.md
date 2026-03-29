# Deferred Findings — Wave 4b (step_mu.py)

Date: 2026-03-10

## Deferred Items

### D1: substrate_versions not cryptographically verified (Adversary)
- File: step_mu.py:983-984
- `_build_ontology_promotion_candidate` uses Python SEED_CHECKSUMS for both "python" and "js"
- Validator only checks type, not value
**Why deferred:** The ontology promotion candidate is validated by INV_OPROMO_1-4 invariants
which check structural shape, not content hashes. The substrate_versions field is informational
metadata. A malicious candidate with wrong checksums would still pass structural validation
but would be detected at the next substrate-parity check. The fix requires JS-side checksum
verification infrastructure that doesn't exist yet. **Target wave:** JS substrate-parity
verification wave (requires new JS infrastructure).

### D2: Shared kernel projection cache unverified purity (Adversary)
- File: step_mu.py:1044-1070
- `_load_combined_kernel_projections_shared()` returns live cache reference
- Relies on unverified assumption that eval_step never mutates projections
**Why deferred:** Converting the cache to immutable (tuple of frozen dicts) would require
deep changes to projection handling throughout the codebase. The current architecture
guarantees purity through structural discipline — projections are loaded once and never
modified. The `_step_trusted` function creates new state dicts, never modifying projection
objects. Adding a mutation guard (Object.freeze equivalent in Python) would require a
recursive freeze utility that doesn't exist. **Target wave:** Seed immutability hardening
wave (same scope as ADV-2).

### D3: Duplicate _emit closures (Expert)
- File: step_mu.py:2423-2444 and 2683-2703
- Boot1 and trampoline engine paths define nearly identical _emit closures
**Why deferred:** The two _emit closures are intentionally different — Boot1's version
includes `boot1_depth` key tracking that the trampoline version doesn't need. Extracting
a factory would require a parameter for optional key inclusion, adding complexity for a
2-line semantic difference. The code is clear as-is. **No fix planned** — intentional
semantic difference, not accidental duplication.

### D4: Unmarked isinstance in security validators (Fuzzer) — **RESOLVED 2026-03-15**
- Fixed: 29 isinstance calls in step_mu.py annotated with `# AST_OK:infra — type guard`. INFRA_CEILING 94→123 in STATUS.md. Original report overstated count (114 vs actual 29 unmarked at time of sweep).

### D5: hash_trace non-dict entries pass silently (Fuzzer) — RESOLVED (2026-03-14)

### D6: classify_terminal_kind no fuzz coverage for coincident keysets (Fuzzer)
- File: step_mu.py:228-243
- No fuzz test generates random Mu dicts whose keysets match terminal shapes
**Why deferred:** This is a test gap, not a code bug. Writing a fuzzer that generates
random dicts with keysets matching terminal classification shapes (e.g., `{"mode", "result"}`)
requires a custom Hypothesis strategy. The existing terminal classification is well-tested
by deterministic tests — the fuzzer gap is about discovering unexpected keyset collisions
that deterministic tests miss. **Target wave:** Fuzzer hygiene wave (same scope as NB4/NB5).
