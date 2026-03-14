# Native Agent Test Findings (Active Residue)

Archived source snapshot:

- `reports/archive/deferred/native_agent_test_findings_2026-03-11.md`

Only the still-open items remain active here.

## Open Items

### ADV-2. Loaded seed objects and projection arrays are mutable

- Status: STILL_OPEN (mitigated)
- Current truth: JS substrate is single-invocation CLI, so this is hardening
  residue rather than an active exploit surface

### ADV-3. Parity vectors load without integrity verification

- Status: STILL_OPEN (mitigated)
- Current truth: parity vectors are test fixtures, not runtime seed inputs

### VER-5. `_match_inner` loops still lack per-loop `@host_iteration` coverage — RESOLVED (2026-03-14)

- Status: STILL_OPEN
- Current truth: this is debt-accounting refinement, not a behavioral gap
