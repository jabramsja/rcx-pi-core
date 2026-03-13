# Deferred Findings — Wave 4e (JS Engine/API/CLI Audit)

Date: 2026-03-10

## Deferred Items

### D1: Python ValueError for reserved inject_key fields (Python-side)
- File: mu/host/python/rcx_pi/selfhost/step_mu.py:2204
- Python raises ValueError for kernel-reserved inject_key; should be RcxEngineError
- JS correctly raises RcxError — Python-side fix, not JS scope

### D2: collected_at timestamp divergence
- Files: pipeline.js:765 vs step_mu.py:2375
- Python uses wall-clock `time.strftime()`; JS uses deterministic `derived:` + control hash
- Intentional: JS avoids non-deterministic wall-clock for reproducibility
- Not a semantic gap — evidence records will differ in this field

### D3: FORBIDDEN_INJECT_KEYS is JS-only hardening
- File: pipeline.js:22-27
- JS checks KERNEL_RESERVED_FIELDS + FORBIDDEN_INJECT_KEYS (JS prototype pollution defense)
- Python only checks KERNEL_RESERVED_FIELDS
- JS is intentionally stricter — defense-in-depth for prototype chain poisoning
- Asymmetric but safe: JS rejects more values than Python

### D4: run_exhaustion API handler uses muEqual for stall
- File: json_handlers.js:139
- Uses muEqual (content hash) for stall detection, not muHashControlCached (control hash)
- JS-only API action — no Python counterpart. Core runAlgorithmWithBridge correctly uses control hash.
- **Status:** RESOLVED (2026-03-13). Changed `muHashCached` → `muHashControlCached` in `json_handlers.js:139` stall detection. Now matches core engine path in `pipeline.js:128`.

### D5: run() double-match inefficiency (inherited from wave 4d)
- File: bootstrap_core.js:308-316
- run() matches all projections to find matchedId, then step() re-matches
- Performance-only — same semantics
