# Archive Move Plan — Round 21B

**Created:** 2026-02-14
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

### 2.1 Active References (must be resolved before move)

| File | Line(s) | Type | Resolution |
|------|---------|------|------------|
| rcx_pi/program_descriptor.py | 54 | Fallback search path | Remove candidate #4 (already has 3 other candidates) |
| rcx_pi/worlds/worlds_bridge.py | 28 | cwd="rcx_pi_rust" subprocess | Archive entire module (no L3 callers) |
| rcx_pi/worlds/worlds_mutate_demo.py | 43 | MU_PROGRAMS_DIR hardcoded | Archive entire module (no L3 callers) |
| rcx_pi/worlds/worlds_mutate_loop.py | 15 | MU_DIR hardcoded | Archive entire module (no L3 callers) |
| scripts/mutation_sandbox.sh | 121 | _stage_world_for_rust_mu_programs | Repoint to mu/ or remove trace-cli runner |
| scripts/world_score.sh | 205 | Fallback search path | Remove rcx_pi_rust candidate |
| scripts/tests/test_program_descriptor_cli_smoke.py | 32 | Fallback search dir | Remove rcx_pi_rust search dir |
| scripts/build_orbit_provenance.sh | 15 | cargo run | Already DEPRECATED — archive with rcx_pi_rust |
| scripts/check_replay_fixture.sh | 24 | cargo build | Already DEPRECATED — archive with rcx_pi_rust |
| scripts/gen_snapshot_fixture_variant.sh | 9-13 | cargo build/run | Already DEPRECATED — archive with rcx_pi_rust |
| scripts/green_examples.sh | 9-36 | cargo run | Already graceful-skip — remove rcx_pi_rust block |

### 2.2 Test References (already guarded)

| File | Guard | Notes |
|------|-------|-------|
| tests/test_world_doc_tool.py | @pytest.mark.skipif | Skips if path missing |
| tests/test_rule_precedence_tool.py | @pytest.mark.skipif | Skips if path missing |
| tests/test_mutation_sandbox_tool.py | @pytest.mark.skipif | Skips if path missing |
| tests/archive/legacy/ (4 files) | In archive, excluded from collection | Already archived Round 21A |

### 2.3 Documentation References

| File | Line(s) | Resolution |
|------|---------|------------|
| README.md | 187, 189 | Update example paths to use mu/ |
| STATUS.md | 625 | No change (governance record) |
| TASKS.md | 438 | No change (governance record) |
| docs/core/LegacySurfaceDecisionRecord.v0.md | throughout | No change (this IS the governance doc) |

### 2.4 Config/Manifest References

| File | Notes |
|------|-------|
| .rcx_manifest.json | Regenerate after move |
| .github/workflows/rust_examples.yml | Delete or archive |
| .github/CODEOWNERS | Remove rcx_pi_rust line |

---

## 3. Move Manifest — rcx_omega

### 3.1 Active References

| File | Line(s) | Type | Resolution |
|------|---------|------|------------|
| tests/test_semantic_goldens.py | 7-8 | Direct import | Already in conftest collect_ignore; archive test |
| tests/test_semantic_invariants.py | 6-7 | Direct import | Already in conftest collect_ignore; archive test |
| tests/conftest.py | 120-121 | collect_ignore entries | Remove entries after archiving test files |
| scripts/mutation_leaderboard_clean.sh | 92-95 | Conditional rcx_omega CLI | Already handles absence gracefully |
| scripts/omega_status_postcard.sh | 3-4 | DEPRECATED header | Already DEPRECATED — archive |

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

- [ ] All skipif guards tested locally (Round 21A — done)
- [ ] Structural guardrail in place (test_legacy_surface_guard.py — done)
- [ ] DEPRECATED headers on pure-legacy scripts (Round 21B — done)
- [ ] Legacy-path annotations on active code (Round 21B — done)
- [ ] Founder approval for archive move (PENDING)

---

## 5. Execution Order

1. Resolve active references in rcx_pi/ runtime code (Section 2.1)
2. Move rcx_pi_rust/ → archive/rcx_pi_rust/
3. Archive test_semantic_goldens.py and test_semantic_invariants.py
4. Move rcx_omega/ → archive/rcx_omega/
5. Clean up config/manifest references (Sections 2.4, 3.2)
6. Regenerate .rcx_manifest.json
7. Run full validation suite
8. Update README.md example paths

---

## 6. Rollback Strategy

If tests break after move:
1. `git revert <move-commit>` restores all files to original locations
2. No runtime code changes in this plan — rollback is clean
3. Guardrail test (test_legacy_surface_guard.py) will continue to catch re-coupling

---

## 7. CI Impact

| CI Job | Impact | Mitigation |
|--------|--------|------------|
| rust_examples.yml | Will no-op (already detects missing Cargo.toml) | Delete workflow after move |
| green_gate.sh | No impact (already skips if no Cargo.toml) | None needed |
| slow_tests.yml | No impact (doesn't use rcx_pi_rust) | None needed |
| Nightly fuzzer | No impact | None needed |
