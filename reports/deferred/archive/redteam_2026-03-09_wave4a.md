# Wave 4a (Core Kernel) Active Residue

Archived source snapshot:

- `reports/archive/deferred/redteam_2026-03-09_wave4a.md`

Archived from the source snapshot as resolved:

- D10 nested typed head/tail parity gap

## Open Items

### D1. Duplicate linked-list collection logic in `denormalize_from_match` — **RESOLVED 2026-03-15**
- Fixed: extracted `_traverse_linked_list` shared traversal function in match_mu.py.
- `_collect_kv_pairs` and `_collect_elements` now call the shared function.
- 5 new AST_OK:infra markers for previously-unmarked isinstance/set/id calls.
- INFRA_CEILING: 89→94, authority baseline updated.

### D2. Stage0/trusted-path duplication across `eval_seed.py`
**Why deferred:** The Stage0 VM and the trusted-path (`_step_trusted`, `_apply_projection_trusted`) share some pattern-matching logic but with intentionally different trust boundaries. The Stage0 VM has additional validation (source_digest, capture_ref deep copy). Deduplicating them requires careful analysis of which validation can be shared without weakening the Stage0 security boundary. This is a design decision, not a mechanical refactor. **Target wave:** Stage0 VM hardening wave (requires Wave A design review).

### D3. JSON round-trip defensive copy pattern — RESOLVED (2026-03-14)
### D4. Coverage late-import and repeated `is_enabled()` checks — RESOLVED (2026-03-14) — NOT ACTIONABLE — no residue found in current code
### D5. Depth `>` vs `>=` policy remains unresolved — RESOLVED (2026-03-14)
### D6. `AST_OK` comment wording remains sloppy — RESOLVED (2026-03-14)
### D7. `_apply_projection_trusted` docstring remains inconsistent — RESOLVED (2026-03-14)
### D9. Runtime imports of normalize/denormalize still need a clean explanation — RESOLVED (2026-03-14)
