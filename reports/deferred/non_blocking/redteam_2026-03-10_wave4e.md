# Wave 4e (JS Engine/API/CLI) Active Residue

Archived source snapshot:

- `reports/archive/deferred/redteam_2026-03-10_wave4e.md`

Archived from the source snapshot as resolved:

- D1 Python reserved `inject_key` handling mismatch
- D4 `run_exhaustion` stall-hash mismatch
- D5 `run()` double-match inefficiency

## Open Items

### D2. `collected_at` remains intentionally divergent across substrates
### D3. `FORBIDDEN_INJECT_KEYS` remains JS-only hardening

- Founder direction (2026-03-14): do not "fix parity" by importing JS
  object-model quirks into Python.
- If tightened later, the better RCX fix is either:
  - keep this as explicit JS edge hardening only, or
  - define a substrate-agnostic reserved-key policy that both substrates can
    enforce without teaching Python about JS built-in property semantics
