# Docs Migration Plan — Round 22A

**Date**: 2026-02-14
**Author**: Claude Code (22A)
**Status**: PLAN (no moves executed)

---

## 1. Current Inventory

### docs/ (99 files, 662 KB)

| Subfolder | Files | Size | DOC_STATUS Coverage | Purpose |
|-----------|-------|------|---------------------|---------|
| core/ | 23 | 305 KB | 23/23 (100%) | Design specs, implementations |
| agents/ | 14 | 110 KB | 3/3 active (100%) | Agent system docs + archive |
| execution/ | 10 | 86 KB | 4/10 (40%) | Runtime behavior specs |
| archive/ | 18 | 69 KB | N/A (frozen) | Historical, frozen |
| schemas/ | 15 | 21 KB | 6/6 md (100%) | JSON schema definitions |
| audit/ | 3 | 28 KB | 3/3 (100%) | Audit reports |
| cli/ | 5 | 10 KB | 5/5 (100%) | CLI documentation |
| reviews/ | 2 | 11 KB | 0/2 (0%) | Code review summaries |
| fixtures/ | 7 | 4 KB | N/A (data) | JSON test fixtures |
| root | 2 | 14 KB | N/A | README + historical note |

### roadmap/ (11 files, outside docs/)

| File | Size | Description | Proposed Action |
|------|------|-------------|-----------------|
| ROADMAP.md | 8 KB | Master roadmap | KEEP in roadmap/ |
| MANIFEST.md | 4 KB | Component manifest | KEEP in roadmap/ |
| MuHemispheresDesign.md | 12 KB | Hemisphere design spec | MOVE to docs/core/ |
| AlgorithmNormalizationSpec.v0.md | 6 KB | Normalization spec | MOVE to docs/core/ |
| ContentAddressedMu.md | 4 KB | Content-addressed Mu design | MOVE to docs/core/ |
| NormalizationDecisionMemo.md | 3 KB | Decision record | MOVE to docs/core/ |
| Gate0_Baseline_2026-02-04.md | 5 KB | Gate checkpoint | MOVE to docs/archive/ |
| Gate3_ArchitecturalDecision.md | 4 KB | Gate decision record | MOVE to docs/archive/ |
| MetaCircular_Boot0_GatePlan.md | 6 KB | Gate plan | MOVE to docs/archive/ |
| Hex0_Boot0_Checklist.md | 3 KB | Checklist | MOVE to docs/archive/ |
| ToolingDelta.md | 2 KB | Tooling changes | MOVE to docs/archive/ |

### Other scattered docs

| Location | File | Action |
|----------|------|--------|
| rcx_pi/specs/ | triad_plus_promotion_backlog.md | KEEP (code-adjacent) |
| rcx_pi/README.md | Package readme | KEEP |
| rcx_omega/README.md | Package readme | KEEP (archive-bound) |
| rcx_pi_rust/README.md | Package readme | KEEP (archive-bound) |
| tests/archive/README.md | Archive index | KEEP |
| tests/golden/README.md | Golden test index | KEEP |

---

## 2. Dependency Map

### Code → Doc References (must update on move)

| Source File | References | Target Doc |
|-------------|------------|------------|
| rcx_pi/selfhost/seed_integrity.py | `docs/core/SelfHosting.v0.md` | docs/core/ |
| rcx_pi/selfhost/seed_integrity.py | `docs/core/BootstrapPrimitives.v0.md` | docs/core/ |
| rcx_pi/selfhost/eval_seed.py | `docs/core/EVAL_SEED.v0.md` | docs/core/ |
| rcx_pi/selfhost/mu_type.py | `docs/core/MuType.v0.md` | docs/core/ |
| mu/programs/hemispheres.v1.json | `roadmap/MuHemispheresDesign.md` | roadmap/ → docs/core/ |
| mu/programs/rcx_engine.v1.json | `docs/core/RCXEngine.v0.md` | docs/core/ |
| mu/closures/recurrence.v1.json | `docs/core/EngineNewsStructural.v0.md` | docs/core/ |
| mu/closures/exhaustion.v1.json | `docs/core/OperatorExhaustion.v0.md` | docs/core/ |
| mu/bridge/bootstrap_structural.v1.json | `docs/core/BootstrapStructuralBridge.v0.md` | docs/core/ |

### Doc → Doc References (internal cross-refs)

| Source Doc | References |
|------------|------------|
| SelfHosting.v0.md | BootstrapPrimitives, MetaCircularKernel, MuType |
| MetaCircularKernel.v0.md | SelfHosting, RCXKernel, RecursiveKernel |
| Boot0Architecture.v0.md | BootstrapPrimitives, SelfHosting |
| RCXEngine.v0.md | EngineNewsStructural, OperatorExhaustion |
| DocGovernance.v0.md | All governed folders |

### Test → Doc References (DOC_CONTRACTS)

| Test File | Validates |
|-----------|-----------|
| tests/docs/test_doc_contracts.py | Code claims in docs match reality |
| tests/docs/test_doc_freshness.py | Semantic drift detection |
| tests/docs/test_doc_governance.py | DOC_STATUS headers, folder structure |
| tests/docs/test_root_files.py | Root file governance |

---

## 3. Move Map

### Phase 22B: roadmap/ Design Specs → docs/core/ (4 files)

| Current Path | New Path | Risk |
|-------------|----------|------|
| roadmap/MuHemispheresDesign.md | docs/core/MuHemispheresDesign.md | LOW — 1 JSON meta.doc ref |
| roadmap/AlgorithmNormalizationSpec.v0.md | docs/core/AlgorithmNormalizationSpec.v0.md | LOW — no code refs |
| roadmap/ContentAddressedMu.md | docs/core/ContentAddressedMu.md | LOW — no code refs |
| roadmap/NormalizationDecisionMemo.md | docs/core/NormalizationDecisionMemo.md | LOW — no code refs |

### Phase 22C: roadmap/ Gate Docs → docs/archive/ (5 files)

| Current Path | New Path | Risk |
|-------------|----------|------|
| roadmap/Gate0_Baseline_2026-02-04.md | docs/archive/Gate0_Baseline_2026-02-04.md | LOW |
| roadmap/Gate3_ArchitecturalDecision.md | docs/archive/Gate3_ArchitecturalDecision.md | LOW |
| roadmap/MetaCircular_Boot0_GatePlan.md | docs/archive/MetaCircular_Boot0_GatePlan.md | LOW |
| roadmap/Hex0_Boot0_Checklist.md | docs/archive/Hex0_Boot0_Checklist.md | LOW |
| roadmap/ToolingDelta.md | docs/archive/ToolingDelta.md | LOW |

### Phase 22D: execution/ DOC_STATUS Gap Fill (6 files)

| File | Current Status | Action |
|------|----------------|--------|
| DeepStep_Guards.md | No header | Add REFERENCE header |
| DeepStep_HandTrace.md | No header | Add REFERENCE header |
| StallFixExecution.v0.md | No header | Add IMPLEMENTATION header |
| StallFixObservability.v0.md | No header | Add IMPLEMENTATION header |
| TraceReadingPrimer.v0.md | No header | Add REFERENCE header |
| IndependentEncounter.v0.md | Has header | No change |

### Phase 22E: reviews/ DOC_STATUS Gap Fill (2 files)

| File | Action |
|------|--------|
| mu_equal_fix_summary.md | Add REFERENCE header |
| tooling_improvement_designs.md | Add REFERENCE header |

---

## 4. Risk Tiers

### Tier 1 — No Risk (header-only changes, no path moves)
- Phase 22D: Add DOC_STATUS headers to execution/ files
- Phase 22E: Add DOC_STATUS headers to reviews/ files
- **Impact**: Zero code changes, governance tests improve

### Tier 2 — Low Risk (moves within docs/ tree)
- No files currently need this

### Tier 3 — Medium Risk (moves from outside docs/)
- Phase 22B: roadmap/ specs → docs/core/
- Phase 22C: roadmap/ gates → docs/archive/
- **Impact**: Need to update seed JSON meta.doc refs, governance registry
- **Mitigation**: docs_relocate.py --dry-run + governance dual-path window

### Tier 4 — High Risk (NOT planned)
- Moving docs/core/ files between subfolders
- Renaming versioned files
- **Policy**: Do not attempt without dedicated round

---

## 5. Phased Execution Sequence

| Phase | Round | Scope | Files | Risk | Prereq |
|-------|-------|-------|-------|------|--------|
| 22D | Next | DOC_STATUS headers for execution/ | 5 | Tier 1 | None |
| 22E | Next | DOC_STATUS headers for reviews/ | 2 | Tier 1 | None |
| 22B | After headers | roadmap/ specs → docs/core/ | 4 | Tier 3 | 22D, 22E |
| 22C | After specs | roadmap/ gates → docs/archive/ | 5 | Tier 3 | 22B |

**Total moves**: 9 files across 2 phases
**Total header-adds**: 7 files across 2 phases

### Execution Order Rationale

1. **Headers first** (22D/22E): No path changes, pure governance improvement. Gives the DOC_STATUS gate test more coverage before moves happen.
2. **Specs second** (22B): Design docs move to their canonical home. Small blast radius (4 files, 1 code ref to update).
3. **Gates last** (22C): Historical docs archive. Zero code refs.

---

## 6. Rollback Plan

Each phase uses `git mv` — rollback is `git revert <commit>`.

For the migration window approach:
1. `docs_relocate.py --dry-run` validates all paths before any move
2. `docs_registry.json` temporarily allows BOTH old and new paths
3. After moves + CI green, remove old-path entries from registry
4. If CI fails mid-phase, `git revert` the move commit

---

## 7. What Stays Where

### roadmap/ (retained files)
- `ROADMAP.md` — master roadmap (special_folder, not governed)
- `MANIFEST.md` — component manifest (special_folder)

### docs/fixtures/ (retained)
- All 7 JSON fixture files — used by tests, not docs

### docs/schemas/ (retained)
- All 15 schema files — stable, 100% governed

### docs/archive/ (grows by 5)
- Existing 18 files + 5 gate docs from roadmap/

---

## 8. Governance Readiness Changes

### For migration window (dual-path support):

**`tools/docs_registry.json`**:
- Add `^roadmap/.*\\.md$` to `exempt_patterns` (if not already exempt via `special_folders`)
- No changes needed for docs/ subfolders (already governed)

**`tests/docs/test_doc_governance.py`**:
- Verify `special_folders` exemption covers roadmap/ (it does — roadmap is already listed)
- After 22B/22C moves, remove roadmap/ from `special_folders` if empty

**`tests/docs/test_doc_freshness.py`**:
- No changes needed (operates on docs/ files only)

### Seed JSON meta.doc update (Phase 22B only):

| Seed File | Current meta.doc | New meta.doc |
|-----------|-----------------|--------------|
| hemispheres.v1.json | `roadmap/MuHemispheresDesign.md` | `docs/core/MuHemispheresDesign.md` |

This requires updating `seed_integrity.py` checksum for hemispheres.v1.json.
