# Deferred Non-Blockers — Wave 4a (eval_seed.py, match_mu.py, subst_mu.py)

Date: 2026-03-10
Wave: redteam-2026-03-09-wave4-core, sub-batch 4a

## Deferred Items

### D1: 4× duplicate linked-list collection loop in denormalize_from_match
- **File:** match_mu.py:624-753 (~130 duplicate lines)
- **Source:** expert agent
- **Simplification:** Extract `_collect_linked_list_elements(val, transform, max_iter)` helper
- **Why deferred:** Code is correct; duplication is maintenance cost, not correctness risk

### D2: Stage 0 / trusted path code duplication (~240 lines across 5 sites)
- **File:** eval_seed.py (multiple locations)
- **Source:** expert agent
- **Sites:** _stage0_match vs _match_inner, _stage0_substitute vs substitute, apply_projection vs _apply_projection_trusted, step vs _step_trusted, non-linear conflict check (2×)
- **Why deferred:** Depends on D005 pilot decision; refactoring before decision wastes work

### D3: json.loads/json.dumps defensive copy
- **File:** match_mu.py:117-118, 148-149
- **Source:** expert agent
- **Alternative:** copy.deepcopy() or immutability contract
- **Why deferred:** Functional correctness unaffected; performance impact minimal

### D4: Coverage late-import + repeated is_enabled() checks
- **File:** eval_seed.py step():592-611
- **Source:** eval_seed red-team agent
- **Fix:** Move import to module level, cache is_enabled() before loop
- **Why deferred:** Instrumentation scaffolding, not semantic debt

### D5: Depth > vs >= off-by-one
- **File:** eval_seed.py:263, 370, 442, 491
- **Source:** eval_seed red-team agent
- **Issue:** `>` allows depth 0-300 inclusive (301 levels), `>=` would be exactly 300
- **Why deferred:** Needs JS parity verification before changing

### D6: AST_OK comment wording on comprehensions
- **File:** eval_seed.py:509, 513
- **Source:** eval_seed red-team agent
- **Fix:** Clarify "recursive substitution" vs "iteration" in comment
- **Why deferred:** Comment clarity, not correctness

### D7: _apply_projection_trusted docstring inconsistency
- **File:** eval_seed.py:629-644
- **Source:** eval_seed red-team agent
- **Issue:** Says "no validation" but validates projection structure
- **Why deferred:** Docstring accuracy, not behavior

### D8: Stage 0 pilot flag underdocumented
- **File:** eval_seed.py:365
- **Source:** eval_seed red-team agent
- **Fix:** Add module-level docstring explaining D005 purpose/risk
- **Why deferred:** Documentation, not correctness

### D9: Runtime imports of normalize/denormalize
- **File:** eval_seed.py:248-249, 561-562, 651-652, 669-670
- **Source:** eval_seed red-team agent
- **Issue:** Lazy imports create hidden dependencies and runtime overhead
- **Why deferred:** Circular import prevention may be the reason; needs investigation

### D10: subst_mu denormalizes nested typed head/tail payloads (parity gap)
- **File:** subst_mu.py:84-126
- **Source:** Codex bridge R4
- **Issue:** `body_was_head_tail` only checks the root body. Typed head/tail structures nested inside ordinary dicts or injected via bindings are denormalized to Python list/dict by `denormalize_from_match()`, while `eval_seed.substitute()` preserves them as-is.
- **Evidence:** `subst_mu({'outer': {'_type': 'list', 'head': {'var': 'x'}, 'tail': None}}, {'x': 1})` returns `{'outer': [1]}` but `substitute(...)` returns `{'outer': {'_type': 'list', 'head': 1, 'tail': None}}`
- **Why deferred:** Pre-existing parity gap, explicitly handled in fuzzers (`contains_head_tail` skip). Fixing properly requires redesigning normalize/denormalize pipeline to tag which parts were already in head/tail form vs created by normalization. Not a regression from wave 4a.
