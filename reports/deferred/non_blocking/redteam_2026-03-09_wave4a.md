# Wave 4a (Core Kernel) Active Residue

Archived source snapshot:

- `reports/archive/deferred/redteam_2026-03-09_wave4a.md`

Archived from the source snapshot as resolved:

- D10 nested typed head/tail parity gap

## Open Items

### D1. Duplicate linked-list collection logic in `denormalize_from_match`
**Why deferred:** The linked-list collection pattern (`while node is not None: items.append(node["head"]); node = node["tail"]`) appears in `denormalize_from_match` and `_collect_linked_list`. These serve different call sites — `denormalize_from_match` is a public API function, `_collect_linked_list` is an internal helper. Extracting a shared function is straightforward but touches runtime code (`eval_seed.py`), requiring L4_STRUCTURAL overhead (tracker note, indicator artifact, l4_gates change). The code change is 5 lines — the L4 governance overhead is 50+ lines. **Target wave:** Next runtime refactoring wave where other eval_seed.py changes are also needed.

### D2. Stage0/trusted-path duplication across `eval_seed.py`
**Why deferred:** The Stage0 VM and the trusted-path (`_step_trusted`, `_apply_projection_trusted`) share some pattern-matching logic but with intentionally different trust boundaries. The Stage0 VM has additional validation (source_digest, capture_ref deep copy). Deduplicating them requires careful analysis of which validation can be shared without weakening the Stage0 security boundary. This is a design decision, not a mechanical refactor. **Target wave:** Stage0 VM hardening wave (requires Wave A design review).

### D3. JSON round-trip defensive copy pattern — RESOLVED (2026-03-14)
### D4. Coverage late-import and repeated `is_enabled()` checks — RESOLVED (2026-03-14) — NOT ACTIONABLE — no residue found in current code
### D5. Depth `>` vs `>=` policy remains unresolved — RESOLVED (2026-03-14)
### D6. `AST_OK` comment wording remains sloppy — RESOLVED (2026-03-14)
### D7. `_apply_projection_trusted` docstring remains inconsistent — RESOLVED (2026-03-14)
### D9. Runtime imports of normalize/denormalize still need a clean explanation — RESOLVED (2026-03-14)
