# Wave 2 (Tooling) Active Residue

Archived source snapshot:

- `reports/archive/deferred/redteam_2026-03-09_wave2.md`

Archived from the source snapshot as stale:

- item 14 (`JS parity NOT hard-gated in CI`) no longer belongs in the active
  residue because `scripts/green_gate.sh` still runs JS parity checks in the
  merge path

## Open Items

### 1. GitHub Actions are still tag-pinned rather than SHA-pinned
### 2. `$WAVE_ID_FLAG` is still passed unquoted in several shell/CI paths — RESOLVED (2026-03-14)
### 3. Tooling exemptions from host-semantics scanning still rely on convention
### 4. Wrapper scripts still lack staleness detection
### 5. Wave-ID branch-prefix coupling is still under-defended
### 6. Wave-ID derivation logic is still duplicated across CI workflows
### 7. Fixture gates still use repeated near-identical jobs instead of a matrix
### 8. Environment/setup repetition still lacks a shared composite action
### 9. Range-derivation logic still differs across workflows
### 10. `check_simulated_production_logic.py` still has the fallback parser path — RESOLVED (2026-03-14)
### 11. `agent-review.yml` still lacks strict numeric validation for PR input — RESOLVED (2026-03-14)
### 12. `agent-review.yml` permissions are still broader than necessary — RESOLVED (2026-03-14)

Note:

- the older dead-script item for `check_boot1_merge2_readiness.sh` was already
  resolved by a later cleanup wave and is no longer part of the active residue
