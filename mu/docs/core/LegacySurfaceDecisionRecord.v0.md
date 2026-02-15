<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-02-14
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_governance.py

Decision record for legacy components identified in Round 18 full-stack audit.
These surfaces are NOT on the L3 self-hosting critical path.
-->

# Legacy Surface Decision Record v0

**Origin:** Round 18 Full-Stack Audit (2026-02-14), findings P3 #10-#12
**Audit report:** `reports/full_audit_round18/06_synthesis.md`

---

## Surface 1: rcx_pi_rust

| Field | Value |
|-------|-------|
| **Location** | `rcx_pi_rust/` |
| **Size** | ~2,700 LOC Rust, 18 examples, 3 tests |
| **Decision** | **ARCHIVE** |
| **Owner** | Founder (manual decision on Rust substrate revival) |
| **Time horizon** | No active work planned |
| **Exit criteria** | Move to `archive/` when founder confirms no Rust substrate needed |

### Current Status

Standalone Rust implementation of the pre-L1 rule-based engine. Uses `RcxProgram`/`RcxRule`/`RuleAction` structs with string-encoded patterns, not Mu projections. Zero production dependencies from Python selfhost path.

### Architectural Relationship to L3

**Incompatible.** rcx_pi_rust implements the old rule-based engine, not the projection/seed architecture:
- Does NOT load kernel.v1, match.v2, subst.v2 seeds
- Does NOT implement `eval_step` bootstrap primitive
- Uses native Rust `Vec<Mu>` instead of linked-list encoding
- Three incompatible variable conventions (`$x`, single-char `x`, uppercase `X`)
- No `KERNEL_RESERVED_FIELDS` validation
- No cross-substrate parity with `mu/host/js/eval_step.js`

### Dependencies

- CI: `rust_examples.yml` (manual trigger only, not green gate)
- Tests: 2 optional test files (`test_semantic_goldens.py`, `test_semantic_invariants.py`) both marked skip-capable in `conftest.py`
- Scripts: Several optional scripts fail gracefully if Cargo.toml missing

### Risks if Unchanged

Low. No production dependencies. CI cost is zero (manual trigger). Risk is confusion for new contributors who may attempt to integrate it with L3.

---

## Surface 2: rcx_omega

| Field | Value |
|-------|-------|
| **Location** | `rcx_omega/` |
| **Size** | ~1,800 LOC Python, 41 files, 17 test files |
| **Decision** | **ARCHIVE** |
| **Owner** | Founder (decision on observability architecture) |
| **Time horizon** | No active work planned |
| **Exit criteria** | Move to `archive/` when founder confirms observability approach |

### Current Status

Observer/analysis layer ("Omega observes, Pi computes"). Provides motif-based tracing, lens metrics, and trace analysis CLIs. Imports from deprecated `rcx_pi.engine.evaluator_pure` (legacy evaluator, NOT selfhost path).

### Architectural Relationship to L3

**Detached.** rcx_omega depends on the legacy evaluator, not the selfhost projection path:
- Imports `PureEvaluator` from `rcx_pi.engine.evaluator_pure`
- Does NOT interact with kernel.v1, match.v2, subst.v2 seeds
- Does NOT integrate with JavaScript substrate
- No cross-substrate parity claims or tests
- 100% of `core/report_contract.py` is dead code

### Dependencies

- CI: No explicit gate. `omega_status_postcard.sh` deprecated (Round 19C)
- Tests: 2 optional test files marked skip-capable in `conftest.py`
- Production: Zero imports from active selfhost path

### Risks if Unchanged

Low. No production dependencies. Risk is drift: developers may assume rcx_omega provides active observability when it's architecturally disconnected from L3.

### Migration Path (if revived)

If observability is needed, create unified observers in `mu/observables/` using the projection-based architecture rather than maintaining a parallel evaluator dependency.

---

## Surface 3: worlds_json

| Field | Value |
|-------|-------|
| **Location** | `mu/worlds_json/` (moved from root Round 23B) |
| **Size** | 5 JSON files, ~5 KB total |
| **Decision** | **MAINTAIN (minimal)** |
| **Owner** | Automated (generated artifacts) |
| **Time horizon** | Keep indefinitely as test fixtures |
| **Exit criteria** | N/A — test fixtures |

### Current Status

Bridge format for RCX rule sets (Mu pattern to action routing). Contains `rcx_core.json`, 3 mutation variants (`mut1-mut3`), and `paradox_1over0.json`. Used by rcx_pi_rust examples and `test_worlds_paradox_1over0.py`.

### Duplicate Policy

**`rcx_core_mut4.json` removed (Round 22J, 2026-02-14).** It was byte-identical to `rcx_core_mut3.json` — a duplicate artifact from `worlds_mutate_demo.py` generating the same output twice. Zero filename dependencies confirmed before deletion.

### Architectural Relationship to L3

**Legacy.** These JSON files are for the old rule-based engine format (string-encoded patterns, not structural Mu projections). They serve as documentation/test fixtures, not core runtime data.

### Dependencies

- `archive/rcx_pi_legacy/worlds_json.py`: Utility module for JSON/Mu format conversion (archived Round 24E — zero active importers)
- `test_worlds_paradox_1over0.py`: Active test using `paradox_1over0.json`
- `rcx_pi_rust/examples/`: Rust examples load these files

### Risks if Unchanged

Minimal. Duplicate `mut4` removed (Round 22J). Remaining files are distinct mutation variants.

---

## Summary Decision Table

| Surface | Decision | Owner | Timeline | Exit Criteria |
|---------|----------|-------|----------|---------------|
| **rcx_pi_rust** | ARCHIVED | — | Round 23A | Moved to `archive/rcx_pi_rust/` |
| **rcx_omega** | ARCHIVED | — | Round 23A | Moved to `archive/rcx_omega/` |
| **worlds_json** | MAINTAIN (at `mu/worlds_json/`) | Automated | Indefinite | N/A (test fixtures) |
| **worlds_json/mut4** | REMOVED | — | Round 22J | Byte-identical to mut3; deleted |
