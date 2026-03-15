# Wave 4e (JS Engine/API/CLI) Active Residue

Archived source snapshot:

- `reports/archive/deferred/redteam_2026-03-10_wave4e.md`

Archived from the source snapshot as resolved:

- D1 Python reserved `inject_key` handling mismatch
- D4 `run_exhaustion` stall-hash mismatch
- D5 `run()` double-match inefficiency

## Open Items

### D2. `collected_at` remains intentionally divergent across substrates — **RESOLVED**
Both substrates now use deterministic `derived:<hash>` for `collected_at` instead of
wall-clock timestamps. See `engine_pipeline.py:613`, `pipeline.js:803`, and gate
assertion in `test_ontology_promotion_runtime_gate.py:1774`.

### D3. `FORBIDDEN_INJECT_KEYS` remains JS-only hardening
**Why deferred:** Founder direction (2026-03-14): do NOT fix parity by importing JS
object-model quirks into Python. The JS `FORBIDDEN_INJECT_KEYS` set blocks keys like
`__proto__`, `constructor`, `prototype` that are dangerous in JS's prototype-based object
model. Python doesn't have this attack surface — `dict.__class__` manipulation doesn't
affect Mu values the same way.
**Better RCX direction (founder):** Either keep as JS-only edge hardening, or define a
substrate-agnostic reserved-key policy that both substrates can enforce without teaching
Python about JS built-in property semantics.
**Target wave:** Substrate-agnostic reserved-key policy wave (Wave A design needed).
