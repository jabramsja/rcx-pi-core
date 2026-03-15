# Wave 4e (JS Engine/API/CLI) Active Residue

Archived source snapshot:

- `reports/archive/deferred/redteam_2026-03-10_wave4e.md`

Archived from the source snapshot as resolved:

- D1 Python reserved `inject_key` handling mismatch
- D4 `run_exhaustion` stall-hash mismatch
- D5 `run()` double-match inefficiency

## Open Items

### D2. `collected_at` remains intentionally divergent across substrates
**Why deferred:** Python uses `datetime.utcnow().isoformat()` while JS uses `new Date().toISOString()`.
These produce slightly different formats (Python lacks `Z` suffix, JS includes it). This is an
intentional parity gap — the `collected_at` field is diagnostic metadata, not a semantic value.
Aligning them would require either (a) adding a datetime import to Python for ISO format, or
(b) stripping the Z from JS. Neither changes behavior. **No fix planned** — intentional
substrate-specific formatting for a non-semantic field.

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
