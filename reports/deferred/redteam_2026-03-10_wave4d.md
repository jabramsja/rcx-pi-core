# Deferred Findings — Wave 4d (JS Core Substrate Audit)

Date: 2026-03-10

## Deferred Items

### D1: 6 seeds in Python not in JS cli/main.js (Seed Agent)
- Seeds: classify.v1, eval.v1, evidence_walker.v1, match.v1, paxos_demo.v1, subst.v1
- v1 seeds superseded by v2; utility/demo seeds not needed for JS runtime
- By design — not a gap

### D2: substitute() error type divergence (Match/Subst Agent)
- File: bootstrap_core.js:124, eval_seed.py:561
- Python raises TypeError, JS throws generic Error
- Both THROW (abort), so behavior is same; classifyError handles mapping
- Not worth aligning since behavior is equivalent

### D3: Object.create(null) in JS denormalize (Normalize Agent)
- File: normalize.js:282,305,335
- JS creates dicts with null prototype; Python uses standard dict
- Intentional: prevents prototype pollution in JS
- Not a parity gap

### D4: Iterative (Python) vs recursive (JS) normalization (Normalize Agent)
- Files: match_mu.py:230-410,509-792 vs normalize.js:129-223,231-340
- Python uses iterative stack-based traversal; JS uses recursive depth-based
- Both produce identical output for valid Mu inputs
- Guard values match (MAX_DEPTH=300, MAX_DENORM_ITER=10000)
- Not worth changing unless a concrete divergence is found

### D5: run() double-match inefficiency (Claude audit)
- File: bootstrap_core.js:308-316
- run() matches all projections to find matchedId for trace, then step() re-matches
- Python run() gets matched projection from kernel state, doesn't double-match
- Performance-only — same semantics
