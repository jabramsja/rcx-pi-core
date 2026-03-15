# Repo Truth Non-Blockers (Active Residue)

Extracted on 2026-03-14 from:

- `reports/codex/Archive/non_blockers/drift_2026-03-12_repo_redteam_non_blockers.md`
- `reports/codex/Archive/non_blockers/redteam_2026-03-14_p7a_p7d_non_blockers.md`

Archived as stale/resolved from the source snapshots:

- the old JS public-path `vmConfig` wiring concern is resolved
- the old startup-cost-before-use concern is resolved
- Hypothesis fuzzer timeout in hemisphere routing parity tests is resolved
- old blocker carryovers N10/N11 were archived to `reports/archive/deferred/repo_truth_blockers_2026-03-14.md`

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

### N4. JS locked seed registries still lack a direct subset/diff gate — **RESOLVED 2026-03-14**

- Fixed: `TestJsSeedLoaderSubsetGate` in `test_seed_loading_parity.py` proves CORE registries ⊂ main registries.
- 3 tests: checksum subset, projection ID subset, registry key symmetry.

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

### N9. debt_dashboard.sh scope differs from ratchet scope

- `debt_dashboard.sh` counts Python-only decorators (8 in rcx_pi/, includes deep_eval.py).
- `check_host_semantics_ratchet.py` counts 6 Python decorators (excludes deep_eval.py).
- Both pass independently but measure different Python scopes.
- Not blocking — canonical source is baseline JSON, not dashboard.

### N12. JS _ALGORITHM_SEED_ALLOWLIST uses Object.freeze(Set) — **RESOLVED 2026-03-14**

- Fixed: replaced `Object.freeze(new Set(...))` with `Object.freeze(Object.assign(Object.create(null), {...}))`.
- Null-prototype object: no prototype chain mutation, `in` operator for lookup, `Object.keys()` for enumeration.

### N13. reports/codex/ exempt from docs governance — attestation false-fail — **RESOLVED 2026-03-14**

- Founder directive (2026-03-14): reports/codex/ belongs to GPT, leave as-is.
- Attestation already changed to advisory (not failure) in founder_session_attest.sh.

### N14. Stage0 capture_ref returns null/None for hostile leaves (design gap)

- capture_ref deep-copies via _safe_mu_copy. Non-Mu types (subclasses) are canonicalized to null/None.
- Bridge considers this a "successful match on hostile input" since the VM returns match with root=null.
- Design decision: null/None is the correct fail-closed canonical value for non-Mu inputs. The alternative (stall on non-Mu capture) would require type-checking at capture_path time, which is a larger change.
- Status: documented design gap, not a production exploit path.

### N15. Stage0 source_digest format-only validation (design gap)

- Format validation catches malformed digests. Content verification (re-hashing source seed) requires runtime access to the source file.
- Design decision needed: should compiled bundles include a self-contained content hash, or should verification require the source seed?
- Status: documented design gap for future compiler evolution.

### N16. check_gate_behavioral_pairs.py: module-level test functions unclassified — **RESOLVED 2026-03-14**

- Fixed: `scan_file()` now scans module-level `test_*` functions under `<module>` key.
- Test: `test_module_level_functions_scanned` in `test_check_gate_behavioral_pairs.py`.

### N17. check_gate_behavioral_pairs.py: positional args accepted silently — **RESOLVED 2026-03-14**

- Fixed: positional args now rejected with exit code 2 (fail-closed).
- Test: `test_positional_args_rejected` in `test_check_gate_behavioral_pairs.py`.

### N18. /checkpoint should force comprehensive memory.md + claude.md re-read — **RESOLVED 2026-03-14**

- Fixed: /checkpoint skill Step 0 now includes MANDATORY re-read with explicit file list and "This is not a checkbox" instruction.
- Claude Code PreToolUse hook (`.claude/hooks/pre-commit-reminder.sh`) shows MEMORY.md + CLAUDE.md before git commit tool calls.

### N19. Three-scope debt counting mismatch (ratchet vs dashboard vs baseline)

- Ratchet: 12 decorators (6 Py selfhost/ + 6 JS). Dashboard: 12 (8 Py rcx_pi/ + 4 AST_OK). Baseline: 16 (6 Py + 6 JS + 4 AST_OK).
- Ratchet excludes deep_eval.py (2 extra decorators). Dashboard excludes JS. Baseline includes both.
- STATUS.md CURRENT=16 matches baseline. audit_semantic_purity.sh THRESHOLD=12 matches dashboard.
- Needs dedicated scope-unification wave to make all three agree.
- Status: documented design mismatch, not blocking.
