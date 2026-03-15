# Wave I Non-Blocking Findings (Active Residue)

Archived source snapshot:

- `reports/archive/deferred/wave-i-non-blocking-findings.md`

Archived from the source snapshot:

- 11 resolved items
- 1 founder `NO-GO` design ruling (`_stage0_substitute` body validation in the
  execution path)

## Open Item

### `_match_inner` budget/depth path duplication

- Status: DEFERRED
- Current truth: this is still hot-path refactoring with low research value and
  should only be touched in a dedicated parity-locked cleanup wave
