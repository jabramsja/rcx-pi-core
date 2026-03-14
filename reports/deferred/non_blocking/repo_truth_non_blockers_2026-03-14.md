# Repo Truth Non-Blockers (Active Residue)

Extracted on 2026-03-14 from:

- `reports/codex/Archive/non_blockers/drift_2026-03-12_repo_redteam_non_blockers.md`
- `reports/codex/Archive/non_blockers/redteam_2026-03-14_p7a_p7d_non_blockers.md`

Archived as stale/resolved from the source snapshots:

- the old JS public-path `vmConfig` wiring concern is resolved
- the old startup-cost-before-use concern is resolved

## Active Non-Blockers

### N1. Python VM cutover coverage reconstruction is not directly locked

- `_step_kernel_with_vm()` reconstructs coverage semantics for compiled
  `match.v2` / `subst.v2`
- the current cutover gate proves equivalence and polarity, but not exact
  `record_no_match` / `record_match` bookkeeping parity

### N2. JS bridge-mode VM shadow evidence is still thinner than the core lane

- JS self-tests prove bridge-mode smoke behavior and bridge ordering validation
- they do not yet directly lock the full `kernel.v1 -> bridge -> match.v2 ->
  subst.v2` ordering semantics under the VM-shadow lane

### N3. P7-d is execution-path progress, not broad host-surface reduction

- tracked markers are flat
- the broader authority and total inventory ledgers remain much larger than the
  narrow tracked-marker ledger

### N4. JS locked seed registries still lack a direct subset/diff gate

- `seed_loader.js` says the core locked registries must mirror `cli/main.js`
- there is still no direct test proving the locked subset matches the wider JS
  CLI registry entry-for-entry

### N5. `pipeline.js` still has no explicit size/shape governance

- the file remains large
- there is no explicit cap or decomposition contract comparable to the JS
  bootstrap-core governance gate

### N6. Historical report drift still requires date discipline

- older report files are easy to misread as current truth if read without their
  date and later archive moves

### N7. Wave indicator artifacts remain thin for deep replay

- the indicator JSON lane is strong provenance, but most artifacts still do not
  explain the wave narrative by themselves

### N8. Hypothesis fuzzer timeout in hemisphere routing parity tests — **RESOLVED** (2026-03-14)

- Fixed: `@pytest.mark.timeout(300)` added to both tests. Default 120s was insufficient for 150-example Hypothesis strategies with JS subprocess calls.

### N9. debt_dashboard.sh scope differs from ratchet scope

- `debt_dashboard.sh` counts Python-only decorators (8 in rcx_pi/, includes deep_eval.py).
- `check_host_semantics_ratchet.py` counts 6 Python decorators (excludes deep_eval.py).
- Both pass independently but measure different Python scopes.
- Not blocking — canonical source is baseline JSON, not dashboard.

### ~~N10.~~ Moved to blocking/repo_truth_blockers_2026-03-14.md B3 — RESOLVED (2026-03-14)

### ~~N11.~~ Moved to blocking/repo_truth_blockers_2026-03-14.md B4 — RESOLVED (2026-03-14)

### N12. JS _ALGORITHM_SEED_ALLOWLIST uses Object.freeze(Set) — bridge suggests frozen null-prototype object

- Bridge R2 noted: Object.freeze on a Set prevents .add()/.delete()/.clear() but the Set prototype methods are still callable via prototype chain. A frozen null-prototype object or frozen array + includes would be "truly immutable."
- Current implementation is sufficient (Set is module-private, not exported, no mutation paths exist). Defense-in-depth hardening only.
- Status: non-blocking advisory from bridge R2.
