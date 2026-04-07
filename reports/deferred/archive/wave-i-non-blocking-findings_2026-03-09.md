# Wave I Non-Blocking Findings (Active Residue)

Archived source snapshot:

- `reports/archive/deferred/wave-i-non-blocking-findings.md`

Archived from the source snapshot:

- 11 resolved items
- 1 founder `NO-GO` design ruling (`_stage0_substitute` body validation in the
  execution path)

## Open Item

### `_match_inner` budget/depth path duplication
**Why deferred:** `_match_inner` in eval_seed.py has separate code paths for budget
tracking and depth tracking that share similar loop structure. Refactoring would consolidate
these into a unified traversal, but `_match_inner` is the hottest path in the kernel —
every projection match goes through it. Any refactor here risks performance regression
and requires careful benchmarking. The duplication is 2 loops of ~15 lines each with
different termination conditions (budget vs depth). **Target wave:** Dedicated
parity-locked cleanup wave with performance benchmarking before/after.
