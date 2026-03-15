# Native Agent Test Findings (Active Residue)

Archived source snapshot:

- `reports/archive/deferred/native_agent_test_findings_2026-03-11.md`

Only the still-open items remain active here.

## Open Items

### ADV-2. Loaded seed objects and projection arrays are mutable — DEFERRED (architecture-mitigated)

- JS substrate is single-invocation CLI — no cross-request mutation surface.
- Python loads seeds at startup and does not re-verify mid-execution.
- Fixing would require Object.freeze/deepfreeze on all loaded seeds — significant pipeline change.
- Deferred to: seed immutability hardening wave (when multi-invocation JS mode is considered).

### ADV-3. Parity vectors load without integrity verification — DEFERRED (test-fixture scope)

- Parity vectors are test fixtures (.json in tests/parity/), not runtime seed inputs.
- Runtime seeds are verified by SEED_CHECKSUMS registries (Python + JS).
- Fixing would mean adding checksums for test fixtures — not justified by risk.
- Deferred to: if parity vectors ever become runtime inputs.

### VER-5. `_match_inner` loops still lack per-loop `@host_iteration` coverage — **RESOLVED 2026-03-14**

- Resolved: HOST_LOOP inline markers added to _match_inner for-loops in eval_seed.py (P7 non-blocker sweep).
- These are debt-accounting markers, not behavioral changes.
