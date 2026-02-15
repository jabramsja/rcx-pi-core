# Archive Move Plan — Round 21B/21C

**Created:** 2026-02-14
**Updated:** 2026-02-14 (Round 21C)
**Status:** PLAN (not yet executed)
**Governance:** LegacySurfaceDecisionRecord.v0.md

---

## 1. Surfaces to Move

| Surface | Decision | Current Location | Target |
|---------|----------|------------------|--------|
| rcx_pi_rust/ | ARCHIVE | repo root | archive/rcx_pi_rust/ |
| rcx_omega/ | ARCHIVE | repo root | archive/rcx_omega/ |

**NOT moved:** worlds_json/ (MAINTAIN decision).

---

## 2. Move Manifest — rcx_pi_rust

### 2.1 Active References (status after Round 21C)

| File | Type | Status | Resolution |
|------|------|--------|------------|
| rcx_pi/program_descriptor.py | Fallback search path | RESOLVED 21C | Primary now mu/mu_programs/; rcx_pi_rust is LEGACY_GUARDED fallback — remove at archive time |
| scripts/tests/test_program_descriptor_cli_smoke.py | Search dir | RESOLVED 21C | Repointed to mu/mu_programs/ only |
| scripts/world_score.sh | Fallback search path | RESOLVED 21C | Primary now mu/mu_programs/; rcx_pi_rust is LEGACY_GUARDED fallback — remove at archive time |
| tests/test_world_doc_tool.py | skipif path | RESOLVED 21C | Repointed to mu/mu_programs/rcx_core.mu |
| tests/test_rule_precedence_tool.py | skipif path | RESOLVED 21C | Repointed to mu/mu_programs/rcx_core.mu |
| tests/test_mutation_sandbox_tool.py | skipif path | RESOLVED 21C | Repointed to mu/mu_programs/rcx_core.mu |
| README.md | Example paths | RESOLVED 21C | Repointed to mu/mu_programs/ |
| scripts/mutation_sandbox.sh | _stage_world_for_rust_mu_programs | LEGACY_GUARDED | Used only by trace-cli runner; must repoint or remove at archive time |
| rcx_pi/worlds/worlds_bridge.py | cwd="rcx_pi_rust" subprocess | LEGACY (21B) | Archive entire module (no L3 callers) |
| rcx_pi/worlds/worlds_mutate_demo.py | MU_PROGRAMS_DIR hardcoded | LEGACY (21B) | Archive entire module (no L3 callers) |
| rcx_pi/worlds/worlds_mutate_loop.py | MU_DIR hardcoded | LEGACY (21B) | Archive entire module (no L3 callers) |
| scripts/build_orbit_provenance.sh | cargo run | DEPRECATED (21B) | Archive with rcx_pi_rust |
| scripts/check_replay_fixture.sh | cargo build | DEPRECATED (21B) | Archive with rcx_pi_rust |
| scripts/gen_snapshot_fixture_variant.sh | cargo build/run | DEPRECATED (R18) | Archive with rcx_pi_rust |
| scripts/green_examples.sh | cargo run | Graceful-skip | Remove rcx_pi_rust block at archive time |

### 2.2 Test References

| File | Status | Notes |
|------|--------|-------|
| tests/test_world_doc_tool.py | RESOLVED 21C | Now uses mu/mu_programs/ |
| tests/test_rule_precedence_tool.py | RESOLVED 21C | Now uses mu/mu_programs/ |
| tests/test_mutation_sandbox_tool.py | RESOLVED 21C | Now uses mu/mu_programs/ |
| tests/archive/legacy/ (4 files) | Archived 21A | Excluded from collection |

### 2.3 Documentation References

| File | Status | Resolution |
|------|--------|------------|
| README.md | RESOLVED 21C | Updated example paths to mu/mu_programs/ |
| STATUS.md | N/A | Governance record (no change needed) |
| TASKS.md | N/A | Governance record (no change needed) |
| docs/core/LegacySurfaceDecisionRecord.v0.md | N/A | IS the governance doc |

### 2.4 Config/Manifest References

| File | Notes |
|------|-------|
| .rcx_manifest.json | Regenerate after move |
| .github/workflows/rust_examples.yml | Delete or archive |
| .github/CODEOWNERS | Remove rcx_pi_rust line |

---

## 3. Move Manifest — rcx_omega

### 3.1 Active References

| File | Type | Resolution |
|------|------|------------|
| tests/test_semantic_goldens.py | Direct import | Already in conftest collect_ignore; archive test |
| tests/test_semantic_invariants.py | Direct import | Already in conftest collect_ignore; archive test |
| tests/conftest.py | collect_ignore entries | Remove entries after archiving test files |
| scripts/mutation_leaderboard_clean.sh | Conditional CLI | Already handles absence gracefully |
| scripts/omega_status_postcard.sh | DEPRECATED | Archive |

### 3.2 Config/Manifest References

| File | Notes |
|------|-------|
| .rcx_manifest.json | Regenerate after move |
| scripts/rcx_manifest.py | Remove rcx_omega from dir list |
| scripts/rcx_packlist.py | Remove rcx_omega globs |
| .github/CODEOWNERS | Remove rcx_omega line |
| RCX_MINIMAL_SPINE_MANIFEST.json | Remove Omega entry |
| tests/docs/test_doc_governance.py | Remove rcx_omega exclusion pattern |
| tools/docs_registry.json | Remove rcx_omega pattern |

---

## 4. Pre-Move Checklist

- [x] All skipif guards tested locally (Round 21A)
- [x] Structural guardrail in place (test_legacy_surface_guard.py — Round 21B)
- [x] DEPRECATED headers on pure-legacy scripts (Round 21B)
- [x] Legacy-path annotations on active code (Round 21B)
- [x] Active fixture home created at mu/mu_programs/ (Round 21C)
- [x] Test/tool references repointed to mu/mu_programs/ (Round 21C)
- [x] Guardrail tightened: empty GRANDFATHERED_RCX_PI_RUST_PATHS, script guard added (Round 21C)
- [ ] Founder approval for archive move (PENDING)

---

## 5. Blockers Removed in 21C

1. **No active test/tool fixture home** — RESOLVED: `mu/mu_programs/` created with 4 active .mu files
2. **3 test files skipped due to rcx_pi_rust path** — RESOLVED: repointed, now running
3. **program_descriptor.py primary search hits rcx_pi_rust first** — RESOLVED: mu/mu_programs/ is now candidate #3 (before rcx_pi_rust #4)
4. **README examples point to rcx_pi_rust** — RESOLVED: updated to mu/mu_programs/
5. **Guardrail allows re-coupling** — RESOLVED: GRANDFATHERED_RCX_PI_RUST_PATHS emptied, script guard added

---

## 6. Remaining Blockers for 21D (Actual Archive Move)

### rcx_pi_rust
1. `rcx_pi/program_descriptor.py` — Remove LEGACY_GUARDED fallback (candidate #4)
2. `scripts/world_score.sh` — Remove LEGACY_GUARDED fallback
3. `scripts/mutation_sandbox.sh` — Repoint `_stage_world_for_rust_mu_programs` to `mu/mu_programs/` or remove trace-cli runner
4. `rcx_pi/worlds/worlds_bridge.py`, `worlds_mutate_demo.py`, `worlds_mutate_loop.py` — Archive modules (no L3 callers)
5. `scripts/green_examples.sh` — Remove rcx_pi_rust block
6. Config cleanup: .rcx_manifest.json, rust_examples.yml, CODEOWNERS

### rcx_omega
1. Archive `test_semantic_goldens.py` and `test_semantic_invariants.py`
2. Remove from conftest.py collect_ignore
3. Config cleanup: .rcx_manifest.json, rcx_manifest.py, rcx_packlist.py, CODEOWNERS, etc.

---

## 7. Suggested 21D Execution Order

1. Remove LEGACY_GUARDED fallbacks from program_descriptor.py, world_score.sh
2. Repoint mutation_sandbox.sh staging to mu/mu_programs/
3. Archive rcx_pi/worlds/{worlds_bridge,worlds_mutate_demo,worlds_mutate_loop}.py
4. `git mv rcx_pi_rust/ archive/rcx_pi_rust/`
5. Archive test_semantic_goldens.py and test_semantic_invariants.py
6. `git mv rcx_omega/ archive/rcx_omega/`
7. Clean up configs/manifests
8. Run full validation, commit, PR

---

## 8. Rollback Strategy

If tests break after move:
1. `git revert <move-commit>` restores all files to original locations
2. No runtime code changes in this plan — rollback is clean
3. Guardrail test (test_legacy_surface_guard.py) will continue to catch re-coupling

---

## 9. CI Impact

| CI Job | Impact | Mitigation |
|--------|--------|------------|
| rust_examples.yml | Will no-op (already detects missing Cargo.toml) | Delete workflow after move |
| green_gate.sh | No impact (already skips if no Cargo.toml) | None needed |
| slow_tests.yml | No impact (doesn't use rcx_pi_rust) | None needed |
| Nightly fuzzer | No impact | None needed |
