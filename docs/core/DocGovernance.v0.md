<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-02-06
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_governance.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_governance.py -v
-->

# Documentation Governance v0

**Status:** ACTIVE (enforced by CI as of 2026-02-03)
**Problem:** Docs fragment truth, then drift. This wastes resources and causes confusion.
**Solution:** Single source of truth + mandatory lifecycle + automated enforcement.

---

## The Three Laws of RCX Documentation

### Law 1: Two Files Own Current State

| File | Owns | Everything Else |
|------|------|-----------------|
| `STATUS.md` | Where we ARE (phase, debt, test counts, what works) | Must NOT duplicate this |
| `TASKS.md` | Where we're GOING (Ra, NEXT, VECTOR, SINK) | Must NOT duplicate this |

**Corollary:** Any doc that says "Current State" or "In Progress" is WRONG. It should say:
> "See STATUS.md for current state."

### Law 2: Every Doc Has a Lifecycle

Every `.md` file outside the root must declare its status in a `DOC_STATUS` header:

| Status | Meaning | Can Contain "Current State"? |
|--------|---------|------------------------------|
| `REFERENCE` | Stable definitions (MuType, DebtCategories) | NO |
| `DESIGN_SPEC` | Architectural intent, may diverge | NO |
| `IMPLEMENTATION` | Active development, matches code | NO - reference STATUS.md |
| `SUPERSEDED` | Replaced by another doc | NO - must link to replacement |
| `ARCHIVED` | Historical only, do not follow | NO - frozen in time |

**No orphan docs.** A doc without `DOC_STATUS` fails CI.

### Law 3: Design Docs Describe WHAT, Not Progress

Design docs answer: "What should this component do?"
They do NOT answer: "How far along are we?" (That's STATUS.md)

**Anti-pattern:**
```markdown
## Current State (Updated 2026-01-15)
- Phase 2 complete
- Phase 3 ongoing
- Blocker: deep_step
```

**Correct pattern:**
```markdown
## Implementation Status
See STATUS.md for current phase and progress.
```

---

## Folder Structure

```
WorkingRCX/
├── STATUS.md              # Law 1: Where we ARE
├── TASKS.md               # Law 1: Where we're GOING
├── CHANGELOG.md           # History (append-only)
├── README.md              # Entry point (links to STATUS.md)
├── CLAUDE.md              # AI instructions (links to STATUS.md)
│
├── .claude/
│   └── agents/            # Agent configuration docs (GOVERNED)
│       ├── adversary.md
│       ├── verifier.md
│       └── ...
│
├── docs/
│   ├── core/              # ACTIVE specs (REFERENCE, DESIGN_SPEC, IMPLEMENTATION)
│   │   ├── MuType.v0.md
│   │   ├── BootstrapPrimitives.v0.md
│   │   └── ...
│   │
│   ├── archive/           # EXEMPT - historical, read-only
│   │   ├── BytecodeVM.v0.md
│   │   └── ...
│   │
│   ├── agents/            # Agent-specific docs (GOVERNED)
│   │   └── AgentGuardrails.v0.md
│   │
│   ├── audit/             # Audit reports (GOVERNED)
│   │   └── MetaCircularReadiness.v1.md
│   │
│   ├── cli/               # CLI documentation (GOVERNED)
│   │   └── cli_quickstart.md
│   │
│   ├── schemas/           # Schema documentation (GOVERNED)
│   │   └── *.md
│   │
│   ├── reviews/           # Code review records (GOVERNED)
│   │   └── *.md
│   │
│   └── execution/         # Execution specs (GOVERNED)
│       └── *.md
```

**Governed Folders** (require DOC_STATUS headers with all 5 fields):
- `docs/core/`, `docs/agents/`, `docs/audit/`, `docs/execution/`
- `docs/cli/`, `docs/schemas/`, `docs/reviews/`
- `tools/agents/` (agent prompt files)

**Exempt Paths** (no governance required):
- `docs/archive/` - Historical, read-only, frozen in time
- `docs/TESTING_PERFORMANCE_ISSUE.md` - Historical context (resolved issue)
- Generated files, archived subprojects (`archive/rcx_pi_rust/`, etc.)

**Special Folder: `roadmap/`** (separate lightweight governance):
- Roadmap docs define SEQUENCE and DESIGN only, not current state
- They follow different rules: link UP to STATUS.md/TASKS.md, no DOC_STATUS headers
- Enforced by `tests/docs/test_roadmap_governance.py` (not test_doc_governance.py)
- See `roadmap/MANIFEST.md` for linking rules and reading order

**Rules:**
1. `docs/core/` = Active specs only (REFERENCE, DESIGN_SPEC, IMPLEMENTATION)
2. `docs/archive/` = EXEMPT from governance (historical, read-only)
3. Moving a doc to `archive/` removes it from governance but requires updating all references
4. New folders require updating `tools/docs_registry.json`

**Registry rule (fail-closed):**
- `tools/docs_registry.json` is the central registry for markdown governance classification.
- New markdown files/folders must be registered there or tests fail.
- Run `python3 tools/docs_sync_report.py --check` to validate registry coverage and placement rules.

---

## Required Header Format

Every doc in `docs/` must start with:

```markdown
<!--
DOC_STATUS
TYPE: REFERENCE | DESIGN_SPEC | IMPLEMENTATION | SUPERSEDED | ARCHIVED
LAST_VERIFIED: YYYY-MM-DD
OWNER: RCX Core Team | <specific owner>
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_contracts.py | tests/<specific_test>.py | none

Optional for SUPERSEDED:
SUPERSEDED_BY: docs/core/NewDoc.v0.md

Optional for ARCHIVED:
ARCHIVED_REASON: <why this is historical only>
-->
```

**Enforcement:** `tests/docs/test_doc_governance.py` validates all headers.

---

## Creating a New Doc

### Step 1: Choose the Right Type

| If you're writing... | Type | Location |
|---------------------|------|----------|
| A stable definition that rarely changes | REFERENCE | docs/core/ |
| An architectural design that code should follow | DESIGN_SPEC | docs/core/ |
| Documentation that must match current code | IMPLEMENTATION | docs/core/ |
| Notes for a specific agent | REFERENCE | docs/agents/ |
| An audit report | REFERENCE | docs/audit/ |

### Step 2: Add the Header

Copy from an existing doc of the same type. Update `LAST_VERIFIED` to today.

### Step 3: Register in DOC_CONTRACTS (if applicable)

If your doc claims specific things about code (function names, projection counts, constants):

```python
# In tests/docs/test_doc_contracts.py
DOC_CONTRACTS["YourDoc.v0.md"] = {
    "functions": ["rcx_pi.selfhost.module.function"],
    "constants": {"rcx_pi.selfhost.module.CONST": expected_value},
    "seeds": {"seed_name.json": projection_count},
}
```

### Step 4: Run Validation

```bash
PYTHONHASHSEED=0 pytest tests/docs/ -v
```

---

## Superseding a Doc

When a doc is replaced:

1. **Update the old doc's header:**
   ```markdown
   TYPE: SUPERSEDED
   SUPERSEDED_BY: docs/core/NewDoc.v0.md
   ```

2. **Move to archive:**
   ```bash
   git mv docs/core/OldDoc.v0.md docs/archive/OldDoc.v0.md
   ```

3. **Update all references:**
   - Search for `OldDoc.v0.md` in all files
   - Update to point to `NewDoc.v0.md` or remove

4. **Remove from DOC_CONTRACTS:**
   - Delete the entry for the old doc

---

## Archiving a Doc

When a doc is purely historical (not replaced, just obsolete):

1. **Update the header:**
   ```markdown
   TYPE: ARCHIVED
   ARCHIVED_REASON: BytecodeVM approach abandoned in favor of projection-based execution
   ```

2. **Move to archive:**
   ```bash
   git mv docs/core/OldDoc.v0.md docs/archive/OldDoc.v0.md
   ```

3. **Add to FORBIDDEN_PATTERNS** (optional):
   If references to this doc indicate drift, add to `test_doc_freshness.py`:
   ```python
   ForbiddenPattern(
       r'OldDoc\.v0\.md',
       "OldDoc was archived",
       "This approach is obsolete, see NewApproach.v0.md",
   )
   ```

---

## Projection Count Convention

**Problem:** Docs that say "kernel.v1.json has 7 projections" become stale when projections are added/removed.

**Solution:** Use estimates or test references, never hardcode exact counts.

| Type | Format | Example |
|------|--------|---------|
| **Estimate** | Use `~` prefix | "~6 projections" |
| **Claim** | Reference tests | "see `test_seed_counts.py` for count" |
| **Historical** | In changelog only | "v0.2: Simplified to 7 projections" |

**Enforcement:** `test_doc_freshness.py` warns on hardcoded counts (except estimates and historical context).

**Grounding tests:** Actual projection counts are verified by `tests/structural/test_seed_counts.py`. Always reference this file for authoritative counts.

---

## Enforcement Checklist

| Check | Tool | Runs In |
|-------|------|---------|
| All docs have DOC_STATUS header | `test_doc_governance.py` | CI |
| Header fields are valid | `test_doc_governance.py` | CI |
| SUPERSEDED docs have SUPERSEDED_BY | `test_doc_governance.py` | CI |
| No orphan docs in docs/core/ | `test_doc_governance.py` | CI |
| Functions/constants/seeds exist | `test_doc_contracts.py` | CI |
| No forbidden patterns | `test_doc_freshness.py` | CI |
| No inline "Current State" | `test_doc_freshness.py` | CI |
| Paths in docs exist | `test_doc_freshness.py` | CI |
| L-level claims match STATUS.md | `test_doc_freshness.py` | CI |
| No hardcoded projection counts | `test_doc_freshness.py` | CI |
| Debt count matches | `check_docs_consistency.sh` | CI |
| STATUS.md recently updated | `check_docs_consistency.sh` | CI |
| STATUS/TASKS execution-layer claims agree | `test_status_tasks_consistency.py` | CI |

---

## What This Prevents

| Problem | Prevention Mechanism |
|---------|---------------------|
| "Current State" sections that drift | Forbidden pattern + required STATUS.md reference |
| Docs claiming wrong phase/progress | L-level consistency check against STATUS.md |
| References to deleted files | Path existence validation |
| Orphan docs with no tests | DOC_CONTRACTS requirement for claims |
| Old docs without lifecycle status | Mandatory DOC_STATUS header |
| Superseded docs still referenced | FORBIDDEN_PATTERNS for archived content |
| Duplicate truth across docs | Law 1 enforcement (STATUS.md + TASKS.md only) |
| STATUS/TASKS claim contradictions | Cross-tracker consistency test (`test_status_tasks_consistency.py`) |

---

## Migration Plan for Existing Docs

See TASKS.md for current migration status. The phases are:

1. **Audit docs** - Identify inconsistencies and redundancies
2. **Add governance tests** - Create automated enforcement
3. **Create archive folder** - Move superseded docs to docs/archive/
4. **Enforce on new docs** - CI fails for docs without proper headers

---

## FAQ

**Q: What if I need to write temporary notes?**
A: Put them in a `scratch/` folder (gitignored) or use comments in code. Don't create docs that will drift.

**Q: What if a design doc's implementation diverges?**
A: Either update the doc to match implementation, or update implementation to match doc. The `DESIGN_SPEC` type means "this is the intent" - divergence should be tracked in STATUS.md or TASKS.md, not in the doc itself.

**Q: Who updates LAST_VERIFIED?**
A: Anyone who reviews a doc and confirms it's still accurate. CI warns if a doc hasn't been verified in 90 days.

**Q: Can I have "Current State" in a design doc if it's about design state, not implementation?**
A: No. Use TASKS.md VECTOR/SINK sections for design state. The doc itself should be timeless.

---

## Success Criteria

This governance is working when:
1. No doc contains "Current State" sections (except STATUS.md)
2. All docs in docs/core/ have valid DOC_STATUS headers
3. CI catches doc drift before it reaches main
4. New contributors can understand the system from README.md → STATUS.md → relevant docs
5. Time spent on doc maintenance drops to near zero

---

## References

- `STATUS.md` - The source of truth for current state
- `TASKS.md` - The source of truth for work items
- `tests/docs/test_doc_contracts.py` - Verifies code claims
- `tests/docs/test_doc_freshness.py` - Catches semantic drift
- `tests/docs/test_doc_governance.py` - Enforces this policy
