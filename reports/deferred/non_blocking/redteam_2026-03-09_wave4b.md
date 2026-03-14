# Deferred Findings — Wave 4b (step_mu.py)

Date: 2026-03-10

## Deferred Items

### D1: substrate_versions not cryptographically verified (Adversary)
- File: step_mu.py:983-984
- `_build_ontology_promotion_candidate` uses Python SEED_CHECKSUMS for both "python" and "js"
- Validator only checks type, not value
- Complex exploit path mitigated by strong structural constraints (INV_OPROMO_1-4)
- Needs JS parity discussion before fixing

### D2: Shared kernel projection cache unverified purity (Adversary)
- File: step_mu.py:1044-1070
- `_load_combined_kernel_projections_shared()` returns live cache reference
- Relies on unverified assumption that eval_step never mutates projections
- Would require converting to tuple of frozen structures (larger change)

### D3: Duplicate _emit closures (Expert)
- File: step_mu.py:2423-2444 and 2683-2703
- Boot1 and trampoline engine paths define nearly identical _emit closures
- Grounding confirmed they're intentionally different (boot1_depth key)
- Could extract factory but semantic difference makes it non-trivial

### D4: Unmarked isinstance in security validators (Fuzzer)
- File: step_mu.py:229,243,263-276,412-463,473-498,532,551,568,613-648
- 114 isinstance calls, security-critical ones lack AST_OK markers
- Scope: marker-truth wave (mt wave), not runtime audit

### D5: hash_trace non-dict entries pass silently (Fuzzer) — RESOLVED (2026-03-14)
- File: step_mu.py:2818-2827
- Non-dict or dict-without-"state" entries included without state_hash
- Edge case — traces are produced by trusted code (list_to_linked)
- Could add fail-closed guard for defense-in-depth

### D6: classify_terminal_kind no fuzz coverage for coincident keysets (Fuzzer)
- File: step_mu.py:228-243
- No fuzz test generates random Mu dicts whose keysets match terminal shapes
- Test gap, not code bug
